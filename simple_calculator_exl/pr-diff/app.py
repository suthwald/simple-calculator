from fastapi import FastAPI, status
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService
from google.adk.models.lite_llm import LiteLlm
from google.genai import types
from agent5 import travel_supervisor

import os

# -------------------------------------------------
# Load environment variables
# -------------------------------------------------
load_dotenv()

api_key = os.getenv('GROQ_API_KEY')

llama_scout = LiteLlm(
    model="groq/meta-llama/llama-4-scout-17b-16e-instruct",
    api_key=api_key
)
qwen = LiteLlm(model="groq/qwen/qwen3-32b", api_key=api_key)
gpt_oss = LiteLlm(model="groq/openai/gpt-oss-20b", api_key=api_key)

# -------------------------------------------------
# FastAPI App
# -------------------------------------------------
app = FastAPI(title="Google ADK Agent API")

# -------------------------------------------------
# GLOBAL SHARED SERVICES
# -------------------------------------------------
session_service = InMemorySessionService()
memory_service = InMemoryMemoryService()

# -------------------------------------------------
# Request Schemas
# -------------------------------------------------
class AgentRequest(BaseModel):
    question: str


# -------------------------------------------------
# Agent Factory
# -------------------------------------------------
async def get_agent() -> LlmAgent:
    return travel_supervisor


app_name = "test_app"
user_id = "test_user"
session_id = "test_session"


# -------------------------------------------------
# Core Agent Runner
# -------------------------------------------------
async def run_agent(
    question: str,
) -> str:

    # --- Initial State (this is what you asked for) ---
    initial_state: dict[str, Any] = {
        "user_name": "Dharmender",
        "user_location": "Delhi, India",
        "preferred_language": "en",
        "budget": 150000,           # in INR
        "total_spent": 0,
        "trip_type": "leisure",
        "itinerary": None,
        "preferences": {
            "food": "Indian + local cuisine",
            "activities": ["sightseeing", "nature"]
        }
    }

    await session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
        state=initial_state
    )

    agent = await get_agent()

    runner = Runner(
        app_name=app_name,
        agent=agent,
        session_service=session_service,
        memory_service=memory_service,
    )

    content = types.Content(
        role="user",
        parts=[types.Part(text=question)],
    )

    response_text = "(No response)"

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content,
    ):
        if event.is_final_response() and event.content and event.content.parts:
        # if event.content and event.content.parts:
            response_text = event.content.parts[0].text
            print(f"**"*50)
            print(f"Received response chunk: {response_text}")
            print(f"**"*50)
            print(f"Event details: {event}")
            print(f"**"*50)
            print(f"Event details: {event.is_final_response()}")
            print(f"**"*50)

    # Persist session into memory
    completed_session = await session_service.get_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
    )

    await memory_service.add_session_to_memory(completed_session)

    final_session = await session_service.get_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id
    )

    print(f"Final session state: {final_session.state}")
    print("**"*50)

    await session_service.delete_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
    )

    return response_text


# -------------------------------------------------
# API: Ask Agent
# -------------------------------------------------
@app.post("/ask", status_code=status.HTTP_201_CREATED)
async def ask_agent(request: AgentRequest):
    response = await run_agent(
        question=request.question,
    )

    return {
        "status": "success",
        "response": response,
    }
