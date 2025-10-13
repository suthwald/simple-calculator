import asyncio
import sys
import re
from mcp.server.fastmcp import FastMCP

# --- Windows asyncio fix ---
# Prevents "ConnectionResetError: [WinError 10054]" noise when clients close connections
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

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
        - "Hello nice to meet you" otherwise
    """

    # Check for 12-digit UPC pattern
    if re.search(r"\b\d{12}\b", query):
        return "upc_agent"

    # Check for image URLs with 6-digit product IDs (example pattern)
    if re.search(r"https?://\S+\b\d{6}\b\S*\.(jpg|jpeg|png|gif)", query):
        return "image_agent"

    # Default route
    return "Hello nice to meet you"


# --- Run the server ---
if __name__ == "__main__":
    print("🚀 Starting MCP Server on http://127.0.0.1:8001/mcp")
    print("Press Ctrl+C to stop.\n")
    mcp.run(transport="streamable-http")
