# # test_workflow.py
# from google.adk.sessions.session import Session, InvocationContext
# from workflow_example import root_agent  # Import root_agent after fixing __init__.py

# # Create a session and context
# session = Session()
# context = InvocationContext(session=session, user="user")

# # Sample queries
# queries = [
#     "What's the weather and time in New York?",
#     "Tell me the weather in New York.",
#     "What is the current time in New York?",
#     "Can you give me the weather and time for New York right now?",
#     "What's the weather and time in London?",
#     "Tell me about New York.",
#     "What’s the weather and time in new york?"
# ]

# # Test each query
# for query in queries:
#     print(f"\nQuery: {query}")
#     response = root_agent.invoke(query, context)
#     print(f"Response: {response}")
