from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import StreamableHTTPConnectionParams, McpToolset
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize the toolset
toolset = McpToolset(
    connection_params=StreamableHTTPConnectionParams(url="http://127.0.0.1:8001/mcp")
)

# Define the UPC agent
upc_agent = LlmAgent(
    name="upc_agent",
    description="Handles UPC-related queries",
    instruction="""You are an Inventory Control Specialist. For a user query containing a product's UPC code:
    1. Use the `google_search` tool to retrieve accurate product information (e.g., product name, description, brand, or category) based on the UPC code.
    2. Provide a concise response with the product details.
    3. If the UPC code is invalid or no information is found, respond: 'No product information found for this UPC code.'""",
    model="gemini-2.5-flash",
    tools=[google_search],
)

# Define the image agent
image_agent = LlmAgent(
    name="image_agent",
    description="Handles image-related queries",
    instruction="""You are an Inventory Control Specialist. For a user query containing the image urls:
    1. Use the Gemini model to get information about the product in the image.
    2. Provide a concise response with the product details.
    """,
    model="gemini-2.5-flash",
)


# # Define the workflow agent
root_agent = LlmAgent(
    name="workflow_agent",
    description="Orchestrates the flow of queries to the appropriate agent",
    instruction="""You are a workflow orchestrator responsible for directing incoming queries to the correct agent.
    Your task:
    1. Always use the `decomposeQuestion` tool to analyze the input query. **Do not** attempt to answer the query yourself.
    2. Based on the tool's output, take the following actions:
    - If the output indicates `upc_agent`, forward the original query to the `upc_agent`.
    - If the output indicates `image_agent`, forward the original query to the `image_agent`.
    - If the output is "Hello nice to meet you", simply respond with "Hello".
    3. Return the final response from the selected agent or the greeting, as appropriate.
    """,
    model="gemini-2.5-flash",
    tools=[toolset, AgentTool(upc_agent), AgentTool(image_agent)],
)
