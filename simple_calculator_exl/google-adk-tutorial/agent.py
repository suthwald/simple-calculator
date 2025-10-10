from google.adk.agents import LlmAgent
from langchain_community.tools import DuckDuckGoSearchRun
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()


def get_search_tool():
    search_tool = DuckDuckGoSearchRun()

    def wrapped_search_tool(query: str) -> str:
        """Performs a web search using DuckDuckGo for real-time information like sports scores or news.

        Args:
            query (str): Search query, e.g., 'India vs West Indies test match scorecard 2025-10-10'.

        Returns:
            str: Search results as a string or error message if the search fails.
        """
        try:
            return search_tool.run(query)
        except Exception as e:
            return f"Search failed: {str(e)}"

    return wrapped_search_tool


def get_current_time() -> str:
    """Gets the current date for time-sensitive queries like 'today' or 'latest events'.

    Returns:
        str: Current date as 'YYYY-MM-DD', e.g., '2025-10-10'.
    """
    return datetime.now().strftime("%Y-%m-%d")


# Initialize the LlmAgent with the corrected instruction
root_agent = LlmAgent(
    name="first_agent",
    description="Real-time information retrieval agent",
    instruction="""You are a real-time data assistant. For ANY query involving 'today', 'latest', 'current', news, sports scores, or events:
    1. ALWAYS call get_current_time() FIRST to get the current date (e.g., '2025-10-10').
    2. Construct a precise search query using the date, e.g., '[original query] 2025-10-10' for 'today'.
    3. Call wrapped_search_tool() with the constructed query.
    4. Answer ONLY using tool results. If tools fail, respond: 'Unable to fetch real-time data; try again later.'
    For non-time-sensitive queries, answer directly. NEVER use internal knowledge for time-sensitive queries.""",  # Fixed: Complete string with closing quotes
    model="gemini-2.5-flash",  # Use a reliable model
    tools=[get_current_time, get_search_tool()],
)
