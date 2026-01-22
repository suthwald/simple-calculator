from google.adk.agents import LlmAgent
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
import asyncio
from pydantic import BaseModel, Field
from google.adk.models.lite_llm import LiteLlm
import json


from dotenv import load_dotenv
import os


# Load environment variables
load_dotenv()

api_key = os.getenv('GROQ_API_KEY')
llama7b_model = LiteLlm(model="groq/llama-3.1-8b-instant", api_key=api_key)

APP_NAME = "basic_agent_no_web"
USER_ID = "user_12345"
SESSION_ID = "session_12345"

class CapitalOutput(BaseModel):
    capital: str = Field(description="The capital of the country.")

# step 1 : get the agent
async def get_agent():
    root_agent = LlmAgent(
    name="structured_capital_agent",
    instruction="""You are a Capital Information Agent. Given a country, respond ONLY with a JSON object containing the capital. Format: {"capital": "capital_name"}""",
    model=llama7b_model,
    output_schema=CapitalOutput,
    output_key="found_capital"
)
    return root_agent

# step 2 : run the agent
async def main(query):

    # create memory session 
    session_serivce = InMemorySessionService()
    await session_serivce.create_session(app_name= APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
    
    # get the agent 
    root_agent = await get_agent()

    # create runnner instance
    runner = Runner(app_name=APP_NAME, agent = root_agent, session_service=session_serivce)

    # format the query 
    content = types.Content(role = "user", parts= [types.Part(text=query)])

    print("Running agent with query:", query)
    # run the agent 
    events = runner.run_async (
        new_message = content,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )


    # # print the response
    # async for event in events:
    #     if event.is_final_response():
    #         final_response = event.content.parts[0].text
            
    #         print("Agent Response:", final_response)
    #         print("Agent Response Type:", type(json.loads(final_response)))

    # print the response
    async for event in events:
        if event.is_final_response() and event.content and event.content.parts:
            final_response = event.content.parts[0].text
            
            print("Agent Response:", final_response)
            print("Agent Response Type:", type(final_response))
            print("Agent Response Type:", type(json.loads(final_response)))


if __name__ == "__main__":
    asyncio.run(main("China"))
