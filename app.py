"""
Simple Streamlit Dashboard for Tax Extraction System.
Minimal version for Streamlit Cloud deployment.
"""

import streamlit as st
import pandas as pd
import requests
import os
from datetime import datetime

# Page Configuration
st.set_page_config(
    page_title="Tax Extraction Dashboard",
    page_icon="🏢",
    layout="wide"
)

# Get configuration from secrets or environment
def get_config():
    try:
        return {
            "API_URL": st.secrets.get("API_URL", "https://tax-extraction-system-production.up.railway.app"),
            "SUPABASE_URL": st.secrets.get("SUPABASE_URL", ""),
            "SUPABASE_KEY": st.secrets.get("SUPABASE_KEY", "")
        }
    except:
        return {
            "API_URL": os.getenv("API_URL", "https://tax-extraction-system-production.up.railway.app"),
            "SUPABASE_URL": os.getenv("SUPABASE_URL", ""),
            "SUPABASE_KEY": os.getenv("SUPABASE_KEY", "")
        }

config = get_config()

# Header
st.title("🏢 Property Tax Extraction Dashboard")
st.markdown("Real-time monitoring of property tax data")

# Sidebar
with st.sidebar:
    st.header("🔧 Controls")
    
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    # API Status
    st.subheader("🌐 API Status")
    try:
        response = requests.get(f"{config['API_URL']}/health", timeout=5)
        if response.status_code == 200:
            st.success("✅ API Online")
        else:
            st.error("❌ API Offline")
    except Exception as e:
        st.error(f"❌ API Unreachable: {e}")

# Main content
tab1, tab2, tab3 = st.tabs(["📊 Overview", "🏢 Properties", "📈 Statistics"])

with tab1:
    st.header("System Overview")
    
    # Try to fetch statistics
    try:
        stats_response = requests.get(f"{config['API_URL']}/api/v1/statistics", timeout=10)
        if stats_response.status_code == 200:
            stats = stats_response.json()
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Properties", stats.get("total_properties", 0))
            
            with col2:
                st.metric("Total Entities", stats.get("total_entities", 0))
            
            with col3:
                outstanding = stats.get("total_outstanding_tax", 0)
                st.metric("Outstanding Tax", f"${outstanding:,.2f}")
            
            with col4:
                success_rate = stats.get("extraction_success_rate", 0)
                st.metric("Success Rate", f"{success_rate:.1f}%")
        else:
            st.warning("Unable to fetch statistics from API")
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        st.info("Make sure the API is running and accessible")

with tab2:
    st.header("Properties")
    
    # Try to fetch properties
    try:
        props_response = requests.get(f"{config['API_URL']}/api/v1/properties", timeout=10)
        if props_response.status_code == 200:
            properties = props_response.json().get("properties", [])
            
            if properties:
                df = pd.DataFrame(properties)
                
                # Display key columns if they exist
                display_cols = ['property_name', 'property_address', 'jurisdiction', 'state']
                available_cols = [col for col in display_cols if col in df.columns]
                
                if available_cols:
                    st.dataframe(df[available_cols], use_container_width=True)
                else:
                    st.dataframe(df, use_container_width=True)
                
                # Download button
                csv = df.to_csv(index=False)
                st.download_button(
                    label="📥 Download CSV",
                    data=csv,
                    file_name=f"properties_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("No properties found")
        else:
            st.warning("Unable to fetch properties from API")
    except Exception as e:
        st.error(f"Error fetching properties: {e}")

with tab3:
    st.header("Statistics")
    
    # Show API endpoint info
    st.subheader("API Endpoints")
    st.code(f"""
API Base URL: {config['API_URL']}
Health Check: {config['API_URL']}/health
API Docs: {config['API_URL']}/docs
Properties: {config['API_URL']}/api/v1/properties
Statistics: {config['API_URL']}/api/v1/statistics
    """)
    
    # Show configuration status
    st.subheader("Configuration Status")
    if config['SUPABASE_URL']:
        st.success("✅ Supabase URL configured")
    else:
        st.warning("⚠️ Supabase URL not configured")
    
    if config['SUPABASE_KEY']:
        st.success("✅ Supabase Key configured")
    else:
        st.warning("⚠️ Supabase Key not configured")

# Footer
st.divider()
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")