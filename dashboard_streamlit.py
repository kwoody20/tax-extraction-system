"""
Streamlit Dashboard for Tax Extraction System - Cloud Version.
This version works with Streamlit Cloud without local module dependencies.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import requests
import json
from typing import Optional, Dict, List, Any
import time
import os
from supabase import create_client, Client

# Page Configuration - MUST be first Streamlit command
st.set_page_config(
    page_title="Tax Extraction Dashboard",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========================= Configuration =========================

# Try to get from Streamlit secrets first (production), then environment
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    API_URL = st.secrets["API_URL"]
except Exception:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    API_URL = os.getenv("API_URL", "https://tax-extraction-system-production.up.railway.app")
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("⚠️ Supabase credentials not configured.")
        st.info("Please add SUPABASE_URL and SUPABASE_KEY to Streamlit secrets.")
        st.stop()

# Initialize Supabase client
@st.cache_resource
def init_supabase():
    """Initialize Supabase client with caching."""
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# ========================= Helper Functions =========================

def fetch_api_data(endpoint: str, params: Optional[Dict] = None) -> Optional[Any]:
    """Fetch data from the API with error handling."""
    try:
        url = f"{API_URL}/api/v1/{endpoint}"
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {e}")
        return None

def format_currency(value: float) -> str:
    """Format value as currency."""
    return f"${value:,.2f}"

def format_percentage(value: float) -> str:
    """Format value as percentage."""
    return f"{value:.1f}%"

# ========================= Data Loading =========================

@st.cache_data(ttl=60)
def load_properties():
    """Load properties from API."""
    data = fetch_api_data("properties")
    if data:
        return pd.DataFrame(data.get("properties", []))
    return pd.DataFrame()

@st.cache_data(ttl=60)
def load_entities():
    """Load entities from API."""
    data = fetch_api_data("entities")
    if data:
        return pd.DataFrame(data.get("entities", []))
    return pd.DataFrame()

@st.cache_data(ttl=60)
def load_statistics():
    """Load statistics from API."""
    return fetch_api_data("statistics") or {}

@st.cache_data(ttl=300)
def load_extractions(limit: int = 100):
    """Load recent extractions from API."""
    data = fetch_api_data("extractions", params={"limit": limit})
    if data:
        return pd.DataFrame(data.get("extractions", []))
    return pd.DataFrame()

# ========================= Main Dashboard =========================

def main():
    """Main dashboard application."""
    
    # Header
    st.title("🏢 Property Tax Extraction Dashboard")
    st.markdown("Real-time monitoring and management of property tax extractions")
    
    # Initialize Supabase
    supabase = init_supabase()
    
    # Sidebar
    with st.sidebar:
        st.header("🔧 Controls")
        
        # Refresh button
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        
        # View selector
        view_mode = st.radio(
            "Select View",
            ["📊 Overview", "🏢 Properties", "👥 Entities", "📈 Analytics", "🔍 Extractions"]
        )
        
        st.divider()
        
        # API Status
        st.subheader("🌐 API Status")
        try:
            health = requests.get(f"{API_URL}/health", timeout=5)
            if health.status_code == 200:
                st.success("✅ API Online")
            else:
                st.error("❌ API Offline")
        except:
            st.error("❌ API Unreachable")
        
        # Last update time
        st.caption(f"Last update: {datetime.now().strftime('%H:%M:%S')}")
    
    # Load data
    with st.spinner("Loading data..."):
        properties_df = load_properties()
        entities_df = load_entities()
        stats = load_statistics()
        extractions_df = load_extractions()
    
    # Main content based on view mode
    if view_mode == "📊 Overview":
        show_overview(stats, properties_df, entities_df, extractions_df)
    elif view_mode == "🏢 Properties":
        show_properties(properties_df, extractions_df)
    elif view_mode == "👥 Entities":
        show_entities(entities_df, properties_df)
    elif view_mode == "📈 Analytics":
        show_analytics(properties_df, entities_df, extractions_df)
    elif view_mode == "🔍 Extractions":
        show_extractions(extractions_df)

def show_overview(stats, properties_df, entities_df, extractions_df):
    """Show overview dashboard."""
    
    # Key Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Properties",
            f"{stats.get('total_properties', 0):,}",
            delta=None
        )
    
    with col2:
        st.metric(
            "Total Entities",
            f"{stats.get('total_entities', 0):,}",
            delta=None
        )
    
    with col3:
        outstanding = stats.get('total_outstanding_tax', 0)
        st.metric(
            "Outstanding Tax",
            format_currency(outstanding),
            delta=None
        )
    
    with col4:
        success_rate = stats.get('extraction_success_rate', 0)
        st.metric(
            "Success Rate",
            format_percentage(success_rate),
            delta=None
        )
    
    st.divider()
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Tax by Jurisdiction")
        if not properties_df.empty and 'jurisdiction' in properties_df.columns:
            jurisdiction_data = properties_df.groupby('jurisdiction').size().reset_index(name='count')
            fig = px.pie(jurisdiction_data, values='count', names='jurisdiction', 
                        title="Properties by Jurisdiction")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No jurisdiction data available")
    
    with col2:
        st.subheader("📈 Recent Extraction Activity")
        if not extractions_df.empty and 'extraction_date' in extractions_df.columns:
            # Convert to datetime
            extractions_df['extraction_date'] = pd.to_datetime(extractions_df['extraction_date'])
            daily_counts = extractions_df.groupby(extractions_df['extraction_date'].dt.date).size().reset_index(name='count')
            daily_counts.columns = ['date', 'count']
            
            fig = px.line(daily_counts, x='date', y='count', 
                         title="Daily Extractions", markers=True)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No extraction history available")
    
    # Recent Activity Feed
    st.subheader("🔄 Recent Activity")
    if not extractions_df.empty:
        recent = extractions_df.head(5)[['property_id', 'extraction_date', 'status', 'tax_amount']]
        st.dataframe(recent, use_container_width=True, hide_index=True)
    else:
        st.info("No recent activity")

def show_properties(properties_df, extractions_df):
    """Show properties view."""
    st.header("🏢 Properties Management")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        search = st.text_input("🔍 Search properties", placeholder="Enter property name or address")
    with col2:
        if not properties_df.empty and 'jurisdiction' in properties_df.columns:
            jurisdictions = ["All"] + list(properties_df['jurisdiction'].unique())
            selected_jurisdiction = st.selectbox("Jurisdiction", jurisdictions)
        else:
            selected_jurisdiction = "All"
    with col3:
        if not properties_df.empty and 'state' in properties_df.columns:
            states = ["All"] + list(properties_df['state'].unique())
            selected_state = st.selectbox("State", states)
        else:
            selected_state = "All"
    
    # Filter dataframe
    filtered_df = properties_df.copy()
    
    if search:
        mask = (
            filtered_df['property_name'].str.contains(search, case=False, na=False) |
            filtered_df['property_address'].str.contains(search, case=False, na=False)
        )
        filtered_df = filtered_df[mask]
    
    if selected_jurisdiction != "All":
        filtered_df = filtered_df[filtered_df['jurisdiction'] == selected_jurisdiction]
    
    if selected_state != "All":
        filtered_df = filtered_df[filtered_df['state'] == selected_state]
    
    # Display properties
    st.subheader(f"📋 Properties ({len(filtered_df)} results)")
    
    if not filtered_df.empty:
        # Add extraction status
        if not extractions_df.empty:
            latest_extractions = extractions_df.sort_values('extraction_date').groupby('property_id').last()
            filtered_df = filtered_df.merge(
                latest_extractions[['status', 'tax_amount']], 
                left_on='property_id', 
                right_index=True, 
                how='left'
            )
        
        st.dataframe(
            filtered_df[['property_name', 'property_address', 'jurisdiction', 'state', 'status', 'tax_amount']],
            use_container_width=True,
            hide_index=True
        )
        
        # Export button
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"properties_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    else:
        st.info("No properties found matching the filters")

def show_entities(entities_df, properties_df):
    """Show entities view."""
    st.header("👥 Entities Overview")
    
    if not entities_df.empty:
        # Entity metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Entities", len(entities_df))
        
        with col2:
            if not properties_df.empty:
                avg_properties = len(properties_df) / len(entities_df) if len(entities_df) > 0 else 0
                st.metric("Avg Properties/Entity", f"{avg_properties:.1f}")
        
        with col3:
            active_entities = len(entities_df[entities_df.get('is_active', True)])
            st.metric("Active Entities", active_entities)
        
        st.divider()
        
        # Entity table
        st.subheader("📋 Entity List")
        display_cols = ['entity_name', 'entity_type', 'primary_contact', 'created_at']
        available_cols = [col for col in display_cols if col in entities_df.columns]
        
        st.dataframe(
            entities_df[available_cols],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No entities found")

def show_analytics(properties_df, entities_df, extractions_df):
    """Show analytics view."""
    st.header("📈 Analytics Dashboard")
    
    # Tax distribution
    if not extractions_df.empty and 'tax_amount' in extractions_df.columns:
        st.subheader("💰 Tax Amount Distribution")
        
        # Remove nulls and zeros
        tax_data = extractions_df[extractions_df['tax_amount'] > 0]['tax_amount']
        
        if not tax_data.empty:
            fig = px.histogram(
                tax_data, 
                nbins=30,
                title="Distribution of Tax Amounts",
                labels={'value': 'Tax Amount', 'count': 'Frequency'}
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Summary statistics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Mean", format_currency(tax_data.mean()))
            with col2:
                st.metric("Median", format_currency(tax_data.median()))
            with col3:
                st.metric("Min", format_currency(tax_data.min()))
            with col4:
                st.metric("Max", format_currency(tax_data.max()))
    
    # Success rate over time
    if not extractions_df.empty and 'extraction_date' in extractions_df.columns:
        st.subheader("📊 Extraction Success Rate Trend")
        
        extractions_df['extraction_date'] = pd.to_datetime(extractions_df['extraction_date'])
        extractions_df['date'] = extractions_df['extraction_date'].dt.date
        
        daily_stats = extractions_df.groupby('date')['status'].apply(
            lambda x: (x == 'completed').sum() / len(x) * 100
        ).reset_index(name='success_rate')
        
        fig = px.line(
            daily_stats, 
            x='date', 
            y='success_rate',
            title="Daily Success Rate (%)",
            markers=True
        )
        fig.update_yaxis(range=[0, 100])
        st.plotly_chart(fig, use_container_width=True)

def show_extractions(extractions_df):
    """Show extractions history."""
    st.header("🔍 Extraction History")
    
    if not extractions_df.empty:
        # Status filter
        status_filter = st.multiselect(
            "Filter by Status",
            options=['completed', 'failed', 'pending', 'running'],
            default=['completed', 'failed']
        )
        
        if status_filter:
            filtered = extractions_df[extractions_df['status'].isin(status_filter)]
        else:
            filtered = extractions_df
        
        # Date range filter
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", value=datetime.now() - timedelta(days=7))
        with col2:
            end_date = st.date_input("End Date", value=datetime.now())
        
        # Apply date filter
        if 'extraction_date' in filtered.columns:
            filtered['extraction_date'] = pd.to_datetime(filtered['extraction_date'])
            mask = (filtered['extraction_date'].dt.date >= start_date) & (filtered['extraction_date'].dt.date <= end_date)
            filtered = filtered[mask]
        
        # Display
        st.subheader(f"📋 Extractions ({len(filtered)} results)")
        
        display_cols = ['extraction_id', 'property_id', 'extraction_date', 'status', 'tax_amount', 'error_message']
        available_cols = [col for col in display_cols if col in filtered.columns]
        
        st.dataframe(
            filtered[available_cols].sort_values('extraction_date', ascending=False),
            use_container_width=True,
            hide_index=True
        )
        
        # Export
        if st.button("📥 Export Results"):
            csv = filtered.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"extractions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
    else:
        st.info("No extraction history available")

# ========================= Run Application =========================

if __name__ == "__main__":
    main()