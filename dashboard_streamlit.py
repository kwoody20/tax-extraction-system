"""
Streamlit Dashboard for Tax Extraction System - Simplified for Cloud Deployment
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import requests
import json
from typing import Optional, Dict, List, Any
import os
from supabase import create_client, Client

# ========================= Configuration =========================

# Page Configuration
st.set_page_config(
    page_title="Tax Extraction Dashboard",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Try to get from Streamlit secrets first (production), then environment
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    API_URL = st.secrets.get("API_URL", "http://localhost:8000")
except:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    API_URL = os.getenv("API_URL", "http://localhost:8000")
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("⚠️ Supabase credentials not configured.")
        st.info("Please configure your Supabase credentials in Streamlit Cloud secrets or environment variables.")
        st.stop()

# Initialize Supabase client
@st.cache_resource
def init_supabase():
    """Initialize Supabase client."""
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# ========================= Custom CSS =========================

st.markdown("""
<style>
    /* Main container styling */
    .main {
        padding: 1rem;
    }
    
    /* Metric cards */
    div[data-testid="metric-container"] {
        background-color: #f0f2f6;
        border: 1px solid #e0e0e0;
        padding: 1rem;
        border-radius: 0.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    /* Success/Error message styling */
    .success-message {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        margin: 1rem 0;
    }
    
    .error-message {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
        margin: 1rem 0;
    }
    
    /* Table styling */
    .dataframe {
        font-size: 0.9rem;
    }
    
    /* Button styling */
    div.stButton > button {
        background-color: #1f77b4;
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 0.25rem;
        font-weight: 500;
    }
    
    div.stButton > button:hover {
        background-color: #1557b0;
    }
</style>
""", unsafe_allow_html=True)

# ========================= Helper Functions =========================

def fetch_properties():
    """Fetch properties from Supabase."""
    try:
        response = supabase.table('properties').select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error fetching properties: {str(e)}")
        return pd.DataFrame()

def fetch_entities():
    """Fetch entities from Supabase."""
    try:
        response = supabase.table('entities').select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error fetching entities: {str(e)}")
        return pd.DataFrame()

def fetch_extractions():
    """Fetch recent tax extractions from Supabase."""
    try:
        response = supabase.table('tax_extractions').select("*").order('created_at', desc=True).limit(100).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error fetching extractions: {str(e)}")
        return pd.DataFrame()

def calculate_statistics(properties_df, entities_df, extractions_df):
    """Calculate dashboard statistics."""
    stats = {
        'total_properties': len(properties_df),
        'total_entities': len(entities_df),
        'total_extractions': len(extractions_df),
        'total_tax_due': properties_df['amount_due'].sum() if 'amount_due' in properties_df.columns else 0,
        'avg_tax_amount': properties_df['amount_due'].mean() if 'amount_due' in properties_df.columns else 0,
        'properties_with_tax': len(properties_df[properties_df['amount_due'] > 0]) if 'amount_due' in properties_df.columns else 0
    }
    return stats

# ========================= Main Dashboard =========================

def main():
    # Header
    st.title("🏢 Property Tax Extraction Dashboard")
    st.markdown("Real-time monitoring and management of property tax data")
    
    # Sidebar
    with st.sidebar:
        st.header("Navigation")
        page = st.radio(
            "Select Page",
            ["📊 Overview", "🏘️ Properties", "👥 Entities", "📋 Extractions", "⚙️ Settings"]
        )
        
        st.divider()
        
        # Refresh button
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_resource.clear()
            st.rerun()
        
        # Connection status
        st.divider()
        try:
            # Test connection
            test = supabase.table('properties').select("id").limit(1).execute()
            st.success("✅ Connected to Supabase")
        except:
            st.error("❌ Connection Error")
        
        # Show API URL
        st.caption(f"API: {API_URL}")
    
    # Load data
    with st.spinner("Loading data..."):
        properties_df = fetch_properties()
        entities_df = fetch_entities()
        extractions_df = fetch_extractions()
        stats = calculate_statistics(properties_df, entities_df, extractions_df)
    
    # Page routing
    if page == "📊 Overview":
        show_overview(stats, properties_df, entities_df, extractions_df)
    elif page == "🏘️ Properties":
        show_properties(properties_df)
    elif page == "👥 Entities":
        show_entities(entities_df)
    elif page == "📋 Extractions":
        show_extractions(extractions_df)
    elif page == "⚙️ Settings":
        show_settings()

def show_overview(stats, properties_df, entities_df, extractions_df):
    """Show overview page with statistics and charts."""
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Properties",
            f"{stats['total_properties']:,}",
            delta=None
        )
    
    with col2:
        st.metric(
            "Total Entities",
            f"{stats['total_entities']:,}",
            delta=None
        )
    
    with col3:
        st.metric(
            "Total Tax Due",
            f"${stats['total_tax_due']:,.2f}",
            delta=None
        )
    
    with col4:
        st.metric(
            "Avg Tax Amount",
            f"${stats['avg_tax_amount']:,.2f}",
            delta=None
        )
    
    st.divider()
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Tax Distribution by Jurisdiction")
        if 'jurisdiction' in properties_df.columns and 'amount_due' in properties_df.columns:
            jurisdiction_data = properties_df.groupby('jurisdiction')['amount_due'].sum().reset_index()
            fig = px.pie(
                jurisdiction_data,
                values='amount_due',
                names='jurisdiction',
                title="Tax Amount by Jurisdiction"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No jurisdiction data available")
    
    with col2:
        st.subheader("Properties by State")
        if 'state' in properties_df.columns:
            state_data = properties_df['state'].value_counts().reset_index()
            state_data.columns = ['state', 'count']
            fig = px.bar(
                state_data,
                x='state',
                y='count',
                title="Number of Properties by State"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No state data available")
    
    # Recent activity
    st.divider()
    st.subheader("Recent Extractions")
    if not extractions_df.empty:
        recent = extractions_df.head(10)[['property_id', 'status', 'created_at', 'total_due']]
        st.dataframe(recent, use_container_width=True, hide_index=True)
    else:
        st.info("No recent extractions")

def show_properties(properties_df):
    """Show properties page."""
    st.header("🏘️ Properties Management")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if 'jurisdiction' in properties_df.columns:
            jurisdictions = ["All"] + sorted(properties_df['jurisdiction'].dropna().unique().tolist())
            selected_jurisdiction = st.selectbox("Filter by Jurisdiction", jurisdictions)
    
    with col2:
        if 'state' in properties_df.columns:
            states = ["All"] + sorted(properties_df['state'].dropna().unique().tolist())
            selected_state = st.selectbox("Filter by State", states)
    
    with col3:
        if 'entity_id' in properties_df.columns:
            entities = ["All"] + sorted(properties_df['entity_id'].dropna().unique().tolist())
            selected_entity = st.selectbox("Filter by Entity", entities)
    
    # Apply filters
    filtered_df = properties_df.copy()
    
    if 'jurisdiction' in properties_df.columns and selected_jurisdiction != "All":
        filtered_df = filtered_df[filtered_df['jurisdiction'] == selected_jurisdiction]
    
    if 'state' in properties_df.columns and selected_state != "All":
        filtered_df = filtered_df[filtered_df['state'] == selected_state]
    
    if 'entity_id' in properties_df.columns and selected_entity != "All":
        filtered_df = filtered_df[filtered_df['entity_id'] == selected_entity]
    
    # Display properties
    st.subheader(f"Properties ({len(filtered_df)} total)")
    
    if not filtered_df.empty:
        # Select columns to display
        display_columns = ['property_name', 'address', 'jurisdiction', 'state', 'amount_due', 'account_number']
        available_columns = [col for col in display_columns if col in filtered_df.columns]
        
        st.dataframe(
            filtered_df[available_columns],
            use_container_width=True,
            hide_index=True
        )
        
        # Export button
        csv = filtered_df[available_columns].to_csv(index=False)
        st.download_button(
            label="📥 Download as CSV",
            data=csv,
            file_name=f"properties_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    else:
        st.info("No properties found with selected filters")

def show_entities(entities_df):
    """Show entities page."""
    st.header("👥 Entities Management")
    
    # Statistics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Entities", len(entities_df))
    
    with col2:
        if 'entity_type' in entities_df.columns:
            unique_types = entities_df['entity_type'].nunique()
            st.metric("Entity Types", unique_types)
    
    with col3:
        if 'created_at' in entities_df.columns:
            recent_count = len(entities_df[pd.to_datetime(entities_df['created_at']) > datetime.now() - timedelta(days=30)])
            st.metric("New (30 days)", recent_count)
    
    st.divider()
    
    # Display entities
    if not entities_df.empty:
        display_columns = ['entity_name', 'entity_type', 'contact_email', 'contact_phone', 'created_at']
        available_columns = [col for col in display_columns if col in entities_df.columns]
        
        st.dataframe(
            entities_df[available_columns],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No entities found")

def show_extractions(extractions_df):
    """Show extractions page."""
    st.header("📋 Tax Extractions")
    
    # Statistics
    if not extractions_df.empty:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Extractions", len(extractions_df))
        
        with col2:
            if 'status' in extractions_df.columns:
                success_count = len(extractions_df[extractions_df['status'] == 'success'])
                st.metric("Successful", success_count)
        
        with col3:
            if 'total_due' in extractions_df.columns:
                total_extracted = extractions_df['total_due'].sum()
                st.metric("Total Extracted", f"${total_extracted:,.2f}")
        
        with col4:
            if 'created_at' in extractions_df.columns:
                recent = len(extractions_df[pd.to_datetime(extractions_df['created_at']) > datetime.now() - timedelta(days=7)])
                st.metric("Last 7 Days", recent)
        
        st.divider()
        
        # Display extractions
        display_columns = ['property_id', 'status', 'total_due', 'created_at', 'error_message']
        available_columns = [col for col in display_columns if col in extractions_df.columns]
        
        st.dataframe(
            extractions_df[available_columns],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No extractions found")
    
    # Manual extraction trigger
    st.divider()
    st.subheader("Manual Extraction")
    
    with st.form("manual_extraction"):
        property_id = st.text_input("Property ID")
        submitted = st.form_submit_button("Start Extraction")
        
        if submitted and property_id:
            st.info(f"Extraction started for property {property_id}")
            # Here you would typically call the API to start extraction

def show_settings():
    """Show settings page."""
    st.header("⚙️ Settings")
    
    # Connection info
    st.subheader("Connection Information")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.text_input("Supabase URL", value=SUPABASE_URL[:30] + "...", disabled=True)
        st.text_input("API URL", value=API_URL, disabled=True)
    
    with col2:
        st.text_input("Supabase Key", value="***" + SUPABASE_KEY[-4:] if SUPABASE_KEY else "Not configured", disabled=True, type="password")
    
    # Test connection
    if st.button("Test Connection"):
        with st.spinner("Testing connection..."):
            try:
                # Test Supabase
                test = supabase.table('properties').select("id").limit(1).execute()
                st.success("✅ Supabase connection successful")
                
                # Test API
                if API_URL and API_URL != "http://localhost:8000":
                    try:
                        response = requests.get(f"{API_URL}/health", timeout=5)
                        if response.status_code == 200:
                            st.success("✅ API connection successful")
                        else:
                            st.warning(f"⚠️ API returned status {response.status_code}")
                    except:
                        st.warning("⚠️ Could not connect to API")
            except Exception as e:
                st.error(f"❌ Connection failed: {str(e)}")
    
    # Info
    st.divider()
    st.subheader("System Information")
    st.info("""
    **Tax Extraction Dashboard v2.0**
    
    This dashboard provides real-time monitoring and management of property tax extraction data.
    
    - **Properties**: View and manage property records
    - **Entities**: Manage property owners and entities
    - **Extractions**: Monitor tax extraction jobs and results
    - **API Integration**: Connected to FastAPI backend service
    - **Database**: Powered by Supabase (PostgreSQL)
    """)

# ========================= Run App =========================

if __name__ == "__main__":
    main()