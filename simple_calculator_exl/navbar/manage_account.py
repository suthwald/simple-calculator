import streamlit as st

st.title("Manage Your Account ⚙️")
st.write("Here you can view or update your account details.")

username = st.text_input("Username", value="dharmender_singh")
email = st.text_input("Email", value="dharmender@example.com")
new_password = st.text_input("New Password", type="password")

if st.button("Update Account"):
    st.success("✅ Your account details have been updated successfully!")
