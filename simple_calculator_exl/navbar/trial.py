import streamlit as st

st.title("Try It Out 🧠")
st.write("Experiment with our features below!")

name = st.text_input("Enter your name to start the trial:")
if name:
    st.success(f"🎉 Welcome, {name}! You’re now using the demo version.")
else:
    st.info("Please enter your name to begin.")
