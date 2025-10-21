# import streamlit as st

# # Define the page structure
# pages = {
#     "Your account": [
#         st.Page("create_account.py", title="Create your account"),
#         st.Page("manage_account.py", title="Manage your account"),
#     ],
#     "Resources": [
#         st.Page("learn.py", title="Learn about us"),
#         st.Page("trial.py", title="Try it out"),
#     ],
# }

# # Navigation bar (top position)
# pg = st.navigation(pages, position="top")

# # Run selected page
# pg.run()


import streamlit as st

# Flat list of pages (no grouped dropdowns)
pages = [
    st.Page("create_account.py", title="Create Account"),
    st.Page("manage_account.py", title="Manage Account"),
    st.Page("learn.py", title="Learn"),
    st.Page("trial.py", title="Try It Out"),
]

# Top navigation bar
pg = st.navigation(pages, position="top")

# Run selected page
pg.run()
