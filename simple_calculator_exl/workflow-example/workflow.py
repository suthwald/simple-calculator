from google.adk.agents import LlmAgent, SequentialAgent, ParallelAgent
from dotenv import load_dotenv

load_dotenv()

# Define two agents that perform the same task: answering questions about weather and time in a city.
# But they can use different tools/methods.
# Agent 1: Uses a mock weather tool and time tool.
# Agent 2: Uses a different mock approach, perhaps combined tool or direct simulation.


def get_weather(city: str) -> dict:
    """Mock tool to get weather for a city."""
    if city.lower() == "new york":
        return {"status": "success", "report": "Sunny, 25°C in New York."}
    else:
        return {"status": "error", "error_message": f"No weather for {city}."}


def get_time(city: str) -> dict:
    """Mock tool to get current time for a city."""
    import datetime
    from zoneinfo import ZoneInfo

    if city.lower() == "new york":
        tz = ZoneInfo("America/New_York")
        now = datetime.datetime.now(tz)
        return {
            "status": "success",
            "report": f"Time in New York: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}.",
        }
    else:
        return {"status": "error", "error_message": f"No time for {city}."}


# Agent 1: Uses separate tools for weather and time.
agent1 = LlmAgent(
    model="gemini-2.5-flash",
    name="Agent1",
    description="Agent to answer weather and time questions using separate tools.",
    instruction="Answer questions about weather and time in a city using the provided tools.",
    tools=[get_weather, get_time],
)


# Agent 2: Uses a combined mock tool for both weather and time.
def get_weather_and_time(city: str) -> dict:
    """Mock combined tool for weather and time."""
    weather = get_weather(city)
    time = get_time(city)
    if weather["status"] == "success" and time["status"] == "success":
        return {"status": "success", "report": f"{weather['report']} {time['report']}"}
    else:
        return {"status": "error", "error_message": "Error retrieving info."}


agent2 = LlmAgent(
    model="gemini-2.5-flash",
    name="Agent2",
    description="Agent to answer weather and time questions using a combined tool.",
    instruction="Answer questions about weather and time in a city using the combined tool.",
    tools=[get_weather_and_time],
)

# Parallel Agent: Runs Agent1 and Agent2 in parallel for the same task.
parallel_agents = ParallelAgent(
    name="ParallelWeatherTimeAgents", sub_agents=[agent1, agent2]
)

# Supervisor Agent: Reviews and combines results from the parallel agents.
supervisor = LlmAgent(
    model="gemini-2.5-flash",
    name="Supervisor",
    description="Supervises and combines results from parallel agents.",
    instruction="""Review the outputs from Agent1 and Agent2. 
    Combine the best parts into a final coherent answer. 
    If there's discrepancy, note it and provide the most accurate response.""",
)

# Convert parallel_agents to a tool for the supervisor if needed, but here we use SequentialAgent for workflow.
# Root Workflow: SequentialAgent with parallel step followed by supervisor.
root_workflow = SequentialAgent(
    name="SupervisedParallelWorkflow", sub_agents=[parallel_agents, supervisor]
)

# To run the workflow, you would use ADK's execution methods, e.g., via adk web or programmatically.
# Example programmatic invocation (simplified):
# from google.adk.core import Session, InvocationContext
# But for full setup, refer to ADK docs.

# To test: Run 'adk web' in the directory and interact with the root_workflow agent.
