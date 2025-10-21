from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import StreamableHTTPConnectionParams, McpToolset
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize the toolset
toolset = McpToolset(
    connection_params=StreamableHTTPConnectionParams(url="http://127.0.0.1:8001/mcp"),
)

upc_agent = LlmAgent(
    name="upc_agent",
    description="Handles queries related to product UPC codes",
    instruction="""As an Inventory Control Specialist, process queries containing a product's UPC code:
1. Use the `google_search` tool to retrieve accurate product information (e.g., product name, brand, description, category).
2. Return a concise response with the product details.
3. Include all relevant source URLs as a list.
4. If the UPC code is invalid or no information is found, respond exactly: 'No product information found for this UPC code.'

**Response Format:**
{
    "Product Name": "...",
    "Brand": "...",
    "Description": "...",
    "Category": "...",
    "Consumer Size Quantity": "...",
    "Pricing Size Quantity": "...",
    "Source URLs": ["<url1>", "<url2>", ...]
}
""",
    model="gemini-2.5-flash",
    tools=[google_search],
)

image_agent = LlmAgent(
    name="image_agent",
    description="Handles image-related queries by extracting and processing image URLs",
    instruction="""Follow these steps precisely:

1.  **Scan and Aggregate:** Read the *entire* user message from start to finish. Find *all* available image URLs (from text, links, or UI elements) and gather them into a *single* Python list.
    * Example: `['url1', 'url2', 'url3']`
2.  **Call Tool (ONCE):** Call the `get_image_content` tool *exactly one time*. You must pass the *complete list* of all URLs from Step 1 as the single argument.
    * **DO NOT** call the tool for each URL individually.
    * **DO NOT** call the tool multiple times. Wait until you have all URLs.
3.  **Parse Response:** The tool will return a JSON object. This JSON might be inside a wrapper (like result.content.text). Your job is to extract *only the inner product JSON* (the object with keys like "Product Name", "Brand", etc.).
4.  **Handle Errors:** If the extracted JSON *is* an error object (e.g., `{"error": "Failed to fetch..."}`), return that error message as a string: "Tool Error: [error message]".
5.  **Final Output:** Output *only* the clean, extracted product JSON as a string. Do not include any reasoning, explanations, or conversational text.
""",
    model="gemini-2.5-flash",
    tools=[toolset],
)

root_agent = LlmAgent(
    name="workflow_agent",
    description="Directs queries to the appropriate agent",
    instruction="""As a workflow orchestrator, route incoming queries to the correct agent:
1. Use the `decomposeQuestion` tool to analyze the input query. Do not attempt to answer the query directly.
2. Based on the tool's output, take the following actions:
   - If the output indicates `upc_agent`, forward the query to the `upc_agent`.
   - If the output indicates `image_agent`, forward the query to the `image_agent`.
   - If the output is "Default", respond with "I do not have tool to respond this question".
3. Return the response from the selected agent or the greeting, as appropriate.""",
    model="gemini-2.5-flash",
    tools=[toolset, AgentTool(upc_agent), AgentTool(image_agent)],
)


# Give me the details of the product with upc: 195949035937 and product name: Apple iPhone 15
# Give me the details of the product with upc: 072140038229 and product name: Copperstone Sunscreen Spray Sport
# Give me the details of the product with upc: 075486137632 and product name: Hawaiin Tropic Silk Hydration Weightless Sunscreen Sunscreen Clear Spray SPF 70
# Give me the details of the product with upc: 3606000580411 and product name: la Roche-Posay Anthelios 60 spray lotion sunscreen
# Give me the details of the product with upc: 054402250433 and product name: Australian Gold Moisture Lock Tan Extender Moisturizer


# Give me product details from these images:
# https://i.ebayimg.com/images/g/bw0AAeSwKe1o3I~A/s-l1600.webp
# https://i.ebayimg.com/images/g/OusAAeSwCr1o3I~B/s-l1600.webp
# https://i.ebayimg.com/images/g/bP0AAeSw2Xho3I~D/s-l1600.webp

# https://i.ebayimg.com/images/g/XycAAeSw-npo1EJU/s-l1600.webp
# https://i.ebayimg.com/images/g/1MsAAeSwP4hoY6o4/s-l1600.webp
# https://i.ebayimg.com/images/g/STYAAeSwkXtoY6o4/s-l1600.webp
# https://i.ebayimg.com/images/g/VqAAAeSwJR5oY6o5/s-l1600.webp
# https://i.ebayimg.com/images/g/7SYAAeSwbgxo1EJW/s-l1600.webp
# https://i.ebayimg.com/images/g/ATQAAeSw2lZo1EJV/s-l1600.webp
