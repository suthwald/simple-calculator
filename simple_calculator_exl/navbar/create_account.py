import streamlit as st

st.title("Create Your Account 🧾")
st.write("Fill in your details to create a new account.")

with st.form("account_form"):
    username = st.text_input("Username")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    submit = st.form_submit_button("Create Account")

if submit:
    if username and email and password:
        st.success(f"✅ Account created successfully for **{username}**!")
    else:
        st.warning("⚠️ Please fill out all fields.")
