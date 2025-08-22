"""
Streamlit Dashboard for Tax Extraction System.
"""

import streamlit as st
import pandas as pd
import requests
import os
from datetime import datetime

st.set_page_config(page_title="Tax Dashboard", page_icon="🏢", layout="wide")

# Get API URL from secrets or environment
try:
    API_URL = st.secrets["API_URL"]
except:
    API_URL = "https://tax-extraction-system-production.up.railway.app"

st.title("🏢 Property Tax Dashboard")
st.write("Real-time monitoring of property tax data")

# Sidebar
with st.sidebar:
    st.header("🔧 Controls")
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    # API Status
    st.subheader("🌐 API Status")
    with st.spinner("Checking API..."):
        try:
            response = requests.get(f"{API_URL}/health", timeout=5)
            data = response.json()
            if response.status_code == 200 and data.get("status") == "healthy":
                st.success("✅ API & Database Online")
            elif response.status_code == 200:
                st.warning(f"⚠️ API Online, Database Issue")
                st.caption("Railway needs Supabase credentials")
            else:
                st.error(f"❌ API Offline ({response.status_code})")
        except Exception as e:
            st.error(f"❌ Cannot reach API")
            st.caption(f"URL: {API_URL}")

# Main content
tab1, tab2 = st.tabs(["📊 Overview", "🏢 Properties"])

with tab1:
    st.header("System Overview")
    
    # Fetch statistics
    try:
        stats_response = requests.get(f"{API_URL}/api/v1/statistics", timeout=10)
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
            st.warning("Unable to fetch statistics")
    except Exception as e:
        st.error(f"Error: {e}")

with tab2:
    st.header("Properties")
    
    # Fetch properties
    try:
        props_response = requests.get(f"{API_URL}/api/v1/properties", timeout=10)
        if props_response.status_code == 200:
            properties = props_response.json().get("properties", [])
            
            if properties:
                df = pd.DataFrame(properties)
                
                # Display key columns
                display_cols = ['property_name', 'property_address', 'jurisdiction', 'state']
                available_cols = [col for col in display_cols if col in df.columns]
                
                if available_cols:
                    st.dataframe(df[available_cols], use_container_width=True)
                
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
            st.warning("Unable to fetch properties")
    except Exception as e:
        st.error(f"Error: {e}")

st.divider()
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")