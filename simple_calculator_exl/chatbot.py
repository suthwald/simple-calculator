import streamlit as st
import os
from dotenv import load_dotenv
import google.generativeai as genai

os.environ["GRPC_VERBOSITY"] = "NONE"
os.environ["GLOG_minloglevel"] = "2"

# Load environment variables
load_dotenv()

# Configure Streamlit page settings
st.set_page_config(
    page_title="Gemini 2.5 Flash Chatbot", page_icon="🤖", layout="centered"
)

# Configure Gemini API
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    st.error("Please set the GOOGLE_API_KEY in your .env file.")
else:
    genai.configure(api_key=API_KEY)

# Initialize the Gemini 2.5 Flash model
model = genai.GenerativeModel("gemini-2.5-flash")

# Initialize chat history in Streamlit session state
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Hello! I'm your chat assistant powered by Gemini 2.5 Flash. How can I help you today?",
        }
    ]

# Display the chatbot title
st.title("🤖 Gemini 2.5 Flash Chatbot")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle user input
if prompt := st.chat_input("Type your message here..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate response from Gemini
    try:
        response = model.generate_content(prompt)
        assistant_response = response.text
    except Exception as e:
        assistant_response = f"Sorry, I encountered an error: {e}. Please try again."

    # Add assistant response to chat history
    st.session_state.messages.append(
        {"role": "assistant", "content": assistant_response}
    )
    with st.chat_message("assistant"):
        st.markdown(assistant_response)
