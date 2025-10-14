from google.adk.agents import LlmAgent, SequentialAgent
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
    description="Extracts image URLs from queries",
    instruction="""Receive a single image URL or a list of image URLs. Return a Python list containing the provided URLs.  
**Example Output:** `['url1', 'url2', 'url3']`  
Do not process or answer the query beyond extracting the URLs.""",
    model="gemini-2.5-flash",
    output_key="images_list",
)

get_image_content_agent = LlmAgent(
    name="get_image_content_agent",
    description="Extracts product details from image URLs",
    instruction="""As an Inventory Control Specialist, process the provided list of image URLs: {images_list}.
1. Use the Gemini model to extract product attributes solely from the images.

**Response Format:**
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

DO NOT attempt to answer the query yourself
""",
    model="gemini-2.5-flash",
)

image_sequential_agent = SequentialAgent(
    name="image_sequential_agent",
    description="Handles image-related queries by extracting and processing image URLs",
    sub_agents=[image_agent, get_image_content_agent],
)

root_agent = LlmAgent(
    name="workflow_agent",
    description="Directs queries to the appropriate agent",
    instruction="""As a workflow orchestrator, route incoming queries to the correct agent:
1. Use the `decomposeQuestion` tool to analyze the input query. Do not attempt to answer the query directly.
2. Based on the tool's output, take the following actions:
   - If the output indicates `upc_agent`, forward the query to the `upc_agent`.
   - If the output indicates `image_agent`, forward the query to the `image_sequential_agent`.
   - If the output is "Hello nice to meet you", respond with "Hello".
3. Return the response from the selected agent or the greeting, as appropriate.""",
    model="gemini-2.5-flash",
    tools=[toolset, AgentTool(upc_agent), AgentTool(image_sequential_agent)],
)
