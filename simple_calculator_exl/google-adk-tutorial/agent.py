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





# from google.adk import Agent, Runner
# from google.adk.sessions import InMemorySessionService
# from google.adk.tools.langchain_tool import LangchainTool
# from google.genai import types
# from langchain_community.tools import DuckDuckGoSearchRun
# import asyncio
# from dotenv import load_dotenv
# load_dotenv()

# APP_NAME = "news_app"
# USER_ID = "1234"
# SESSION_ID = "session1234"

# # Wrap with LangchainTool
# adk_tavily_tool = LangchainTool(tool=DuckDuckGoSearchRun())

# # Define Agent with the wrapped tool
# async def get_agent():
#     my_agent = Agent(
#         name="langchain_tool_agent",
#         model="gemini-2.0-flash-001",
#         description="Agent to answer questions using TavilySearch.",
#         instruction="I can answer your questions by searching the internet. Just ask me anything!",
#         tools=[adk_tavily_tool] # Add the wrapped tool here
#     )
#     return my_agent


# # step 2 : run the agent
# async def main(query):

#     # create memory session 
#     session_serivce = InMemorySessionService()
#     await session_serivce.create_session(app_name= APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
    
#     # get the agent 
#     root_agent = await get_agent()

#     # create runnner instance
#     runner = Runner(app_name=APP_NAME, agent = root_agent, session_service=session_serivce)

#     # format the query 
#     content = types.Content(role = "user", parts= [types.Part(text=query)])

#     print("Running agent with query:", query)
#     # run the agent 
#     events = runner.run_async (
#         new_message = content,
#         user_id=USER_ID,
#         session_id=SESSION_ID,
#     )


#     # print the response
#     async for event in events:
#         if event.is_final_response():
#             final_response = event.content.parts[0].text
#             print("Agent Response:", final_response)


# if __name__ == "__main__":
#     asyncio.run(main("Who won he cricket mach between India and Australia on 25th October 2025? Give me detailed statistics"))
