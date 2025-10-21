import json
import httpx
import re
import asyncio
import sys
import os
from mcp.server.fastmcp import FastMCP
from google.genai.types import Part, GenerateContentConfig
from google import genai
from dotenv import load_dotenv


# --- Windows asyncio fix ---
# Prevents "ConnectionResetError: [WinError 10054]" noise when clients close connections
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# --- Load API key ---
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in environment variables")

client = genai.Client(api_key=api_key)

# --- Create MCP server instance ---
mcp = FastMCP(name="Product Info Server", port=8001)


# --- Define tools ---
@mcp.tool()
def decomposeQuestion(query: str) -> str:
    """
    Decomposes the user query and decides which agent should handle it.

    Returns:
        - "Use upc" if a 12-digit UPC code is detected
        - "Use image" if an image URL with a 6-digit ID is detected
        - "Default" otherwise
    """

    # Check for 12-digit UPC pattern
    if re.search(r"\b\d{12,13}\b", query):
        return "upc_agent"

    if re.findall(
        r"(https?:\/\/[^\s]+?\.(?:jpg|jpeg|png|gif|bmp|webp|svg)(?:\?[^\s]*)?)", query
    ):
        return "image_agent"

    # Default route
    return "Default"


PROMPT = """
You are an **Inventory Control Specialist** responsible for identifying and extracting accurate product details from images using visual understanding and text extraction (OCR).

### Objective
Analyze the provided product images and extract structured product attributes based solely on visible text, labels, logos, or packaging in the images.

---

### Steps to Follow
- Analyze all images collectively to extract product details.
- Extract attributes only from visible text, labels, or logos in the images.
- If any field is not visible/clear, use null or omit it—do not guess.

### Output Format
Return a **JSON object** with the following fields (use null for missing data):

{
    "Product Name": "...",
    "Brand": "...",
    "Description": "...",
    "Manufacturer": "...",
    "Category": "...",
    "Consumer Size Quantity": "...",
    "Consumer Size Unit of Measure": "...",
    "Price": "...",
    "UPC number of the product": "...",
    "Active Ingredients": "...",
    "Inactive Ingredients": "...",
    "Warning": "..."
}
"""


@mcp.tool()
async def get_image_content(image_urls: list) -> dict:
    """
    Fetches image content from a list of URLs and sends them to the Gemini model
    for product detail extraction based on the internal PROMPT.

    This function performs the following steps:
    1.  Validates the list of image URLs.
    2.  Asynchronously fetches the image data for each URL.
    3.  Validates image content types.
    4.  Constructs a prompt for the Gemini model, including the PROMPT and image data.
    5.  Calls the Gemini API (gemini-2.0-flash-001) requesting a JSON response.
    6.  Cleans and parses the JSON response from the model.
    7.  Validates the parsed JSON to ensure it contains required product keys.
    8.  Returns the clean product JSON object or an error dictionary.

    Args:
        image_urls: A list of strings, where each string is a fully qualified
                    URL to a product image (jpg, jpeg, png, gif, webp).

    Returns:
        A dictionary containing the extracted product attributes on success.
        Example:
        {
            "Product Name": "Alpha Lipoic Acid",
            "Brand": "Nutricost",
            ...
        }

        On failure, returns a dictionary with an "error" key.
        Example:
        {"error": "No image URLs provided"}
        {"error": "Failed to fetch image 1 (http://...): 404 Not Found"}
        {"error": "Failed to parse JSON from Gemini", "raw_output": "..."}
    """
    if not image_urls:
        return {"error": "No image URLs provided"}

    contents = []
    async with httpx.AsyncClient(timeout=30) as client_http:
        for i, image_url in enumerate(image_urls, start=1):
            if not re.match(
                r"https?://.*\.(jpg|jpeg|png|gif|webp)", image_url, re.IGNORECASE
            ):
                # Note: This is a basic check. A more robust check might be needed
                # if URLs don't have extensions (e.g., presigned URLs).
                # For this implementation, we'll raise an error.
                return {
                    "error": f"Invalid or unsupported image URL format: {image_url}"
                }

            try:
                resp = await client_http.get(image_url)
                resp.raise_for_status()  # Raise HTTPStatusError for 4xx/5xx responses
                content_type = (
                    resp.headers.get("content-type", "").split(";")[0].strip()
                )
                if not content_type.startswith("image/"):
                    content_type = (
                        "image/jpeg"  # Fallback if content-type is missing or wrong
                    )
                contents.append(f"Image {i} (URL: {image_url}):")
                contents.append(
                    Part.from_bytes(data=resp.content, mime_type=content_type)
                )
            except Exception as e:
                return {"error": f"Failed to fetch image {i} ({image_url}): {str(e)}"}

    full_contents = [PROMPT] + contents

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-001",
            contents=full_contents,
            config=GenerateContentConfig(
                response_mime_type="application/json", temperature=0.1
            ),
        )

        text = response.text or ""

        # --- 🧹 Clean JSON-like output ---
        # Remove markdown code fences (```json ... ``` or just ``` ... ```)
        cleaned = re.sub(r"```(?:json)?|```", "", text).strip()

        # Try to parse JSON
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # If parsing fails, try to extract JSON substring (as a fallback)
            match = re.search(r"\{[\s\S]*\}", cleaned)
            if match:
                try:
                    data = json.loads(match.group(0))
                except json.JSONDecodeError:
                    return {
                        "error": "Failed to parse JSON from Gemini",
                        "raw_output": text,
                    }
            else:
                return {
                    "error": "No valid JSON detected in Gemini response",
                    "raw_output": text,
                }

        # --- NEW: Return ONLY the clean product JSON, no wrappers ---
        # If it's already the product shape, return as-is; else error
        required_keys = {"Product Name", "Brand", "Description"}  # Minimal check
        if all(key in data for key in required_keys):
            return data  # Clean product JSON only!
        else:
            # This handles cases where Gemini might return valid JSON,
            # but not in the expected product attribute format.
            return {
                "error": "Gemini output missing required fields",
                "raw_output": text,
            }

    except Exception as e:
        return {"error": f"Tool execution failed: {str(e)}"}


# --- Run the server ---
if __name__ == "__main__":
    print("🚀 Starting MCP Server on http://127.0.0.1:8001/mcp")
    print("Press Ctrl+C to stop.\n")
    mcp.run(transport="streamable-http")
