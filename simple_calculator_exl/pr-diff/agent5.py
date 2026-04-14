from google.adk.agents import LlmAgent
from google.adk.tools.tool_context import ToolContext
from typing import Dict, Any
from google.adk.models.lite_llm import LiteLlm

from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv('GROQ_API_KEY')

# llama_scout = LiteLlm(
#     model="groq/meta-llama/llama-4-scout-17b-16e-instruct", 
#     api_key=api_key
# )

llama_scout = LiteLlm(
    model="groq/openai/gpt-oss-20b", 
    api_key=api_key
)


# ====================== TOOLS ======================

def update_itinerary(destination: str, dates: str, tool_context: ToolContext) -> Dict[str, Any]:
    """Set or update the travel itinerary."""
    state = tool_context.state
    
    state["itinerary"] = {
        "destination": destination,
        "dates": dates,
        "activities": []
    }
    state["total_spent"] = 0.0

    return {
        "status": "success",
        "message": f"Itinerary successfully set for {destination} ({dates})"
    }


def add_activity(activity: str, cost: float, tool_context: ToolContext) -> Dict[str, Any]:
    """Add an activity and update total spent."""
    state = tool_context.state

    # Initialize itinerary if missing
    if "itinerary" not in state or not isinstance(state.get("itinerary"), dict):
        state["itinerary"] = {
            "destination": "Not set",
            "dates": "Not set",
            "activities": []
        }
    
    if "activities" not in state["itinerary"] or not isinstance(state["itinerary"].get("activities"), list):
        state["itinerary"]["activities"] = []

    state["itinerary"]["activities"].append({
        "name": activity,
        "cost": float(cost)
    })

    state["total_spent"] = state.get("total_spent", 0.0) + float(cost)

    return {
        "status": "success",
        "new_total_spent": round(state["total_spent"], 2),
        "message": f"✅ Added '{activity}' costing ₹{cost:,.0f}. Total spent: ₹{state['total_spent']:,.0f}"
    }


def get_current_state(tool_context: ToolContext) -> Dict[str, Any]:
    """Return a clean, complete snapshot of the current state."""
    raw_state = tool_context.state

    # Safe conversion for ADK State object
    if hasattr(raw_state, "_value") and isinstance(raw_state._value, dict):
        current = dict(raw_state._value)
    else:
        current = dict(raw_state) if isinstance(raw_state, dict) else {}

    # Ensure all important keys exist to avoid partial JSON
    if "itinerary" not in current:
        current["itinerary"] = None
    if "total_spent" not in current:
        current["total_spent"] = 0
    if "budget" not in current:
        current["budget"] = 150000

    # Make sure activities is always a list
    if isinstance(current.get("itinerary"), dict):
        if "activities" not in current["itinerary"] or not isinstance(current["itinerary"]["activities"], list):
            current["itinerary"]["activities"] = []

    return {
        "status": "success",
        "current_state": current
    }


# ====================== AGENTS ======================

researcher = LlmAgent(
    name="Researcher",
    model=llama_scout,
    description="Researches destinations and creates itinerary.",
    tools=[update_itinerary, get_current_state],
    output_key="research_summary"
)

planner = LlmAgent(
    name="Planner",
    model=llama_scout,
    description="Adds activities to itinerary and manages budget.",
    tools=[add_activity, get_current_state],
    output_key="plan_summary"
)

travel_supervisor = LlmAgent(
    name="TravelSupervisor",
    model=llama_scout,
    description="Main travel assistant that coordinates research and planning.",
    sub_agents=[researcher, planner],
    instruction="""
Greet the user, understand their request, delegate to Researcher or Planner as needed, and always keep the shared state updated with itinerary and budget.
"""
)
