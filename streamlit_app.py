"""
Ultra-minimal Streamlit app for testing deployment.
"""

import streamlit as st

st.set_page_config(page_title="Tax Dashboard", page_icon="🏢")

st.title("🏢 Property Tax Dashboard")
st.write("Welcome to the Tax Extraction System Dashboard")

# Simple test
if st.button("Test Connection"):
    st.success("✅ Streamlit is working!")
    
# Show environment info
with st.expander("Debug Information"):
    st.write("App is running successfully")
    st.write(f"Streamlit version: {st.__version__}")

st.info("Dashboard is loading... API connection will be added after successful deployment.")