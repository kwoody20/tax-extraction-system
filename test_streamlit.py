"""
Minimal Streamlit test to debug deployment issues.
"""

import streamlit as st

st.set_page_config(page_title="Test Dashboard", page_icon="🧪")

st.title("🧪 Streamlit Test Page")

st.write("Testing basic Streamlit functionality...")

# Test secrets
st.subheader("Secrets Check")
try:
    if "SUPABASE_URL" in st.secrets:
        st.success("✅ SUPABASE_URL found in secrets")
    else:
        st.warning("⚠️ SUPABASE_URL not in secrets")
        
    if "SUPABASE_KEY" in st.secrets:
        st.success("✅ SUPABASE_KEY found in secrets")
    else:
        st.warning("⚠️ SUPABASE_KEY not in secrets")
        
    if "API_URL" in st.secrets:
        st.success("✅ API_URL found in secrets")
    else:
        st.warning("⚠️ API_URL not in secrets")
except Exception as e:
    st.error(f"Error accessing secrets: {e}")

# Test imports
st.subheader("Import Check")
try:
    import pandas
    st.success("✅ pandas imported")
except:
    st.error("❌ pandas import failed")
    
try:
    import plotly
    st.success("✅ plotly imported")
except:
    st.error("❌ plotly import failed")
    
try:
    import supabase
    st.success("✅ supabase imported")
except:
    st.error("❌ supabase import failed")
    
try:
    from supabase_client import SupabasePropertyTaxClient
    st.success("✅ supabase_client imported")
except Exception as e:
    st.error(f"❌ supabase_client import failed: {e}")
    
try:
    from supabase_auth import SupabaseAuthManager
    st.success("✅ supabase_auth imported")
except Exception as e:
    st.error(f"❌ supabase_auth import failed: {e}")

st.divider()
st.info("If you see this message, basic Streamlit is working!")