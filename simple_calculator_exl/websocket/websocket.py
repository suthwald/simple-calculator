#agent.py
from google.adk.agents import Agent as LlmAgent
from google.adk.models.lite_llm import LiteLlm
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

api_key = os.getenv('GROQ_API_KEY')

# ---------------- AGENT ---------------- #

root_agent = LlmAgent(
    name="coding_agent",
    model=LiteLlm(model="groq/llama-3.1-8b-instant", api_key=api_key),
    instruction=(
        "You are a helpful agent that returns the answers related to coding questions"
    )
)





#main.py
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types

from agent2 import root_agent

# --- App-wide constants ---
app_name = "notification_app"
user_id = "admin"
session_id = "notification_app_session"

# --- Services ---
notification_session_service = InMemorySessionService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create session at startup
    await notification_session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
    )
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- HEALTH ROUTE ---------------- #

@app.get("/health")
async def health():
    return {"status": "healthy"}


# ---------------- BACKGROUND LOOP ---------------- #

async def agent_loop(websocket: WebSocket):
    runner = Runner(
        app_name=app_name,
        agent=root_agent,
        session_service=notification_session_service,
    )

    while True:
        try:
            # Hardcoded question
            content = types.Content(
                role="user",
                parts=[types.Part(text="Implement binary search")]
            )

            events = runner.run_async(
                new_message=content,
                user_id=user_id,
                session_id=session_id,
            )

            async for event in events:
                if event.is_final_response() and event.content and event.content.parts:
                    await websocket.send_text(event.content.parts[0].text)
                    break

            # Wait 2 minutes
            await asyncio.sleep(120)

        except Exception as e:
            await websocket.send_text(f"Error: {str(e)}")
            await asyncio.sleep(120)


# ---------------- WEBSOCKET ---------------- #

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        await agent_loop(websocket)
    except WebSocketDisconnect:
        print("WebSocket disconnected")






import asyncio
import websockets

async def listen():
    uri = "ws://localhost:8080/ws"
    async with websockets.connect(uri) as websocket:
        print("Connected to WebSocket")
        async for message in websocket:
            print("Agent:", message)
            print("*"*100)

if __name__ == "__main__":
    asyncio.run(listen())
