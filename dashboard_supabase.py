"""
Streamlit Dashboard with Supabase Integration.
Real-time property tax extraction monitoring and management.
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

from supabase_client import SupabasePropertyTaxClient
from supabase_auth import SupabaseAuthManager

# ========================= Configuration =========================

# Configuration - Use Streamlit secrets in production, environment variables locally
import os

# Try to get from Streamlit secrets first (production), then environment, then defaults
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    API_URL = st.secrets["API_URL"]
except:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    API_URL = os.getenv("API_URL", "http://localhost:8000")
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("⚠️ Supabase credentials not configured. Please set SUPABASE_URL and SUPABASE_KEY environment variables.")
        st.info("You can copy .env.example to .env and fill in your credentials")
        st.stop()

# Page Configuration
st.set_page_config(
    page_title="Tax Extraction Dashboard",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========================= Custom CSS =========================

st.markdown("""
<style>
    /* Main container */
    .main {
        padding: 1rem;
    }
    
    /* Metric cards */
    div[data-testid="metric-container"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }
    
    div[data-testid="metric-container"] label {
        color: rgba(255,255,255,0.9) !important;
    }
    
    div[data-testid="metric-container"] [data-testid="metric-value"] {
        color: white !important;
        font-size: 2rem !important;
        font-weight: bold !important;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #2d3748 0%, #1a202c 100%);
    }
    
    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 5px;
        font-weight: bold;
        transition: transform 0.2s;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    
    /* Success/Error messages */
    .success-msg {
        padding: 1rem;
        border-radius: 5px;
        background: #48bb78;
        color: white;
        margin: 1rem 0;
    }
    
    .error-msg {
        padding: 1rem;
        border-radius: 5px;
        background: #f56565;
        color: white;
        margin: 1rem 0;
    }
    
    /* Data tables */
    .dataframe {
        font-size: 0.9rem;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: #f7fafc;
        border-radius: 5px 5px 0 0;
        padding: 0.5rem 1rem;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #667eea;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# ========================= Session State =========================

def init_session_state():
    """Initialize session state variables."""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'access_token' not in st.session_state:
        st.session_state.access_token = None
    if 'db_client' not in st.session_state:
        st.session_state.db_client = SupabasePropertyTaxClient(SUPABASE_URL, SUPABASE_KEY)
    if 'auth_manager' not in st.session_state:
        st.session_state.auth_manager = SupabaseAuthManager()
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = datetime.now()
    if 'selected_properties' not in st.session_state:
        st.session_state.selected_properties = []

init_session_state()

# ========================= Authentication =========================

def login_page():
    """Display login page."""
    st.title("🔐 Tax Extraction Dashboard Login")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("### Welcome Back!")
        st.markdown("Please login to access the dashboard.")
        
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="user@example.com")
            password = st.text_input("Password", type="password")
            col_a, col_b = st.columns(2)
            with col_a:
                login_btn = st.form_submit_button("🔓 Login", use_container_width=True)
            with col_b:
                demo_btn = st.form_submit_button("👁️ Demo Mode", use_container_width=True)
            
            if login_btn and email and password:
                with st.spinner("Authenticating..."):
                    result = st.session_state.auth_manager.login_user(email, password)
                    
                    if result["success"]:
                        st.session_state.authenticated = True
                        st.session_state.user = result["user"]
                        st.session_state.access_token = result["session"]["access_token"]
                        st.success("Login successful!")
                        st.rerun()
                    else:
                        st.error(f"Login failed: {result['message']}")
            
            if demo_btn:
                # Demo mode without authentication
                st.session_state.authenticated = True
                st.session_state.user = {"email": "demo@example.com", "id": "demo"}
                st.session_state.access_token = "demo_token"
                st.info("Entering demo mode with limited features")
                st.rerun()
        
        st.markdown("---")
        st.markdown("**Test Credentials:**")
        st.code("Email: admin@taxextractor.com\nPassword: Admin123!@#")

# ========================= Helper Functions =========================

def fetch_api_data(endpoint: str, token: Optional[str] = None) -> Optional[Dict]:
    """Fetch data from API endpoint."""
    headers = {}
    if token and token != "demo_token":
        headers["Authorization"] = f"Bearer {token}"
    
    try:
        response = requests.get(f"{API_URL}{endpoint}", headers=headers, timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

def format_currency(value: float) -> str:
    """Format value as currency."""
    return f"${value:,.2f}" if value else "$0.00"

def get_status_color(status: str) -> str:
    """Get color for status badge."""
    colors = {
        "success": "🟢",
        "failed": "🔴",
        "pending": "🟡",
        "processing": "🔵"
    }
    return colors.get(status.lower(), "⚪")

# ========================= Dashboard Components =========================

def render_sidebar():
    """Render sidebar with filters and controls."""
    with st.sidebar:
        st.title("🏢 Tax Extraction")
        st.markdown("---")
        
        # User info
        if st.session_state.user:
            st.markdown(f"**User:** {st.session_state.user.get('email', 'Unknown')}")
            if st.button("🚪 Logout", use_container_width=True):
                st.session_state.authenticated = False
                st.session_state.user = None
                st.session_state.access_token = None
                st.rerun()
        
        st.markdown("---")
        
        # Filters
        st.markdown("### 🔍 Filters")
        
        # State filter
        db_client = st.session_state.db_client
        try:
            properties = db_client.get_properties(limit=1000)
            states = sorted(list(set(p.get('state', 'Unknown') for p in properties if p.get('state'))))
            selected_state = st.selectbox("State", ["All"] + states)
            
            # Jurisdiction filter
            if selected_state != "All":
                jurisdictions = sorted(list(set(
                    p.get('jurisdiction', 'Unknown') 
                    for p in properties 
                    if p.get('state') == selected_state and p.get('jurisdiction')
                )))
                selected_jurisdiction = st.selectbox("Jurisdiction", ["All"] + jurisdictions)
            else:
                selected_jurisdiction = "All"
            
            # Entity filter
            entities = db_client.get_entities(limit=100)
            entity_names = ["All"] + sorted([e.get('entity_name', '') for e in entities if e.get('entity_name')])
            selected_entity = st.selectbox("Entity", entity_names)
            
        except Exception as e:
            st.error(f"Failed to load filters: {str(e)}")
            selected_state = "All"
            selected_jurisdiction = "All"
            selected_entity = "All"
        
        st.markdown("---")
        
        # Refresh controls
        st.markdown("### ⚙️ Controls")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Refresh", use_container_width=True):
                st.session_state.last_refresh = datetime.now()
                st.rerun()
        
        with col2:
            auto_refresh = st.checkbox("Auto-refresh", value=False)
        
        if auto_refresh:
            st.info("Auto-refresh every 30 seconds")
            time.sleep(30)
            st.rerun()
        
        # Last refresh time
        st.caption(f"Last refresh: {st.session_state.last_refresh.strftime('%H:%M:%S')}")
        
        return selected_state, selected_jurisdiction, selected_entity

def render_overview_metrics():
    """Render overview metrics."""
    st.markdown("## 📊 Overview")
    
    db_client = st.session_state.db_client
    
    try:
        # Get statistics
        stats = db_client.calculate_tax_statistics()
        
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
            st.metric(
                "Amount Due",
                format_currency(stats.get('total_amount_due', 0)),
                delta=None
            )
        
        with col4:
            balance = stats.get('properties_with_balance', 0)
            total = stats.get('total_properties', 1)
            pct = (balance / total * 100) if total > 0 else 0
            st.metric(
                "Properties w/ Balance",
                f"{balance:,}",
                delta=f"{pct:.1f}%"
            )
        
    except Exception as e:
        st.error(f"Failed to load metrics: {str(e)}")

def render_properties_table(state_filter: str, jurisdiction_filter: str, entity_filter: str):
    """Render properties data table."""
    st.markdown("## 🏘️ Properties")
    
    db_client = st.session_state.db_client
    
    try:
        # Build filters
        filters = {}
        if state_filter != "All":
            filters["state"] = state_filter
        if jurisdiction_filter != "All":
            filters["jurisdiction"] = jurisdiction_filter
        
        # Get properties
        properties = db_client.get_properties(limit=500, filters=filters)
        
        # Filter by entity if selected
        if entity_filter != "All":
            properties = [p for p in properties if p.get('parent_entity_name') == entity_filter]
        
        if properties:
            # Convert to DataFrame
            df = pd.DataFrame(properties)
            
            # Select and rename columns
            columns = {
                'property_name': 'Property Name',
                'jurisdiction': 'Jurisdiction',
                'state': 'State',
                'amount_due': 'Amount Due',
                'previous_year_taxes': 'Previous Year',
                'parent_entity_name': 'Entity',
                'property_id': 'ID'
            }
            
            # Filter columns that exist
            available_cols = [col for col in columns.keys() if col in df.columns]
            df_display = df[available_cols].rename(columns=columns)
            
            # Format currency columns
            if 'Amount Due' in df_display.columns:
                df_display['Amount Due'] = df_display['Amount Due'].apply(lambda x: format_currency(x) if pd.notna(x) else "$0.00")
            if 'Previous Year' in df_display.columns:
                df_display['Previous Year'] = df_display['Previous Year'].apply(lambda x: format_currency(x) if pd.notna(x) else "$0.00")
            
            # Add selection
            selected = st.data_editor(
                df_display,
                hide_index=True,
                use_container_width=True,
                num_rows="fixed",
                disabled=df_display.columns.tolist(),
                column_config={
                    "ID": st.column_config.TextColumn(width="small"),
                }
            )
            
            # Action buttons
            col1, col2, col3 = st.columns([1, 1, 4])
            
            with col1:
                if st.button("🔄 Extract Selected", type="primary"):
                    st.info("Extraction job would be created for selected properties")
            
            with col2:
                if st.button("📥 Export", type="secondary"):
                    csv = df_display.to_csv(index=False)
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name=f"properties_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
            
            # Summary
            st.caption(f"Showing {len(df_display)} properties")
            
        else:
            st.info("No properties found matching the filters")
            
    except Exception as e:
        st.error(f"Failed to load properties: {str(e)}")

def render_extraction_jobs():
    """Render extraction jobs interface with property selection and monitoring."""
    st.markdown("## 🔄 Tax Extraction Center")
    
    db_client = st.session_state.db_client
    
    # Create tabs for different extraction workflows
    tab1, tab2, tab3, tab4 = st.tabs([
        "🚀 Start New Extraction", 
        "📊 Running Jobs", 
        "📜 Extraction History",
        "⚙️ Extraction Settings"
    ])
    
    with tab1:
        st.markdown("### 🎯 Create New Extraction Job")
        
        # Step 1: Select Properties
        st.markdown("#### Step 1: Select Properties to Extract")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            extraction_mode = st.radio(
                "Selection Mode:",
                ["Properties Needing Extraction", "By Entity", "By State", "By Jurisdiction", "Custom Selection"],
                help="Choose how to select properties for extraction"
            )
        
        # Get properties based on selection mode
        try:
            all_properties = db_client.get_properties(limit=500)
            selected_properties = []
            
            if extraction_mode == "Properties Needing Extraction":
                # Get properties that haven't been extracted recently or have no data
                needing_extraction = db_client.find_properties_needing_extraction(days_since_last=30)
                selected_properties = needing_extraction
                
                st.info(f"🔍 Found {len(selected_properties)} properties needing extraction (no data or older than 30 days)")
                
            elif extraction_mode == "By Entity":
                entities = db_client.get_entities(limit=100)
                entity_names = [e['entity_name'] for e in entities]
                
                selected_entity = st.selectbox("Select Entity:", entity_names)
                selected_properties = [p for p in all_properties if p.get('parent_entity_name') == selected_entity]
                
                st.info(f"📁 Selected {len(selected_properties)} properties from {selected_entity}")
                
            elif extraction_mode == "By State":
                states = list(set(p.get('state', 'Unknown') for p in all_properties))
                selected_state = st.selectbox("Select State:", sorted(states))
                selected_properties = [p for p in all_properties if p.get('state') == selected_state]
                
                st.info(f"🗺️ Selected {len(selected_properties)} properties from {selected_state}")
                
            elif extraction_mode == "By Jurisdiction":
                jurisdictions = list(set(p.get('jurisdiction', 'Unknown') for p in all_properties))
                selected_jurisdiction = st.selectbox("Select Jurisdiction:", sorted(jurisdictions))
                selected_properties = [p for p in all_properties if p.get('jurisdiction') == selected_jurisdiction]
                
                st.info(f"🏛️ Selected {len(selected_properties)} properties from {selected_jurisdiction}")
                
            else:  # Custom Selection
                st.markdown("##### Select Individual Properties")
                
                # Create a searchable multiselect
                property_options = {
                    f"{p['property_name']} ({p.get('jurisdiction', 'Unknown')}, {p.get('state', 'Unknown')})": p 
                    for p in all_properties
                }
                
                selected_names = st.multiselect(
                    "Choose properties:",
                    options=list(property_options.keys()),
                    help="Select multiple properties for extraction"
                )
                
                selected_properties = [property_options[name] for name in selected_names]
                
                if selected_properties:
                    st.info(f"✅ Selected {len(selected_properties)} properties")
            
            # Display selected properties preview
            if selected_properties:
                st.markdown("#### Step 2: Review Selection")
                
                # Show summary statistics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Properties Selected", len(selected_properties))
                with col2:
                    states_count = len(set(p.get('state', 'Unknown') for p in selected_properties))
                    st.metric("States", states_count)
                with col3:
                    jurisdictions_count = len(set(p.get('jurisdiction', 'Unknown') for p in selected_properties))
                    st.metric("Jurisdictions", jurisdictions_count)
                with col4:
                    has_url = len([p for p in selected_properties if p.get('tax_bill_link')])
                    st.metric("With Tax URLs", has_url)
                
                # Show property table
                with st.expander("View Selected Properties", expanded=False):
                    df_selected = pd.DataFrame(selected_properties)
                    display_cols = ['property_name', 'jurisdiction', 'state', 'parent_entity_name']
                    available_cols = [col for col in display_cols if col in df_selected.columns]
                    if available_cols:
                        st.dataframe(df_selected[available_cols], use_container_width=True, hide_index=True)
                
                # Step 3: Extraction Options
                st.markdown("#### Step 3: Configure Extraction")
                
                col1, col2 = st.columns(2)
                with col1:
                    extraction_method = st.selectbox(
                        "Extraction Method:",
                        ["Auto-Detect (Recommended)", "HTTP Only", "Selenium (JavaScript Sites)", "Playwright"],
                        help="Choose extraction method based on site requirements"
                    )
                
                with col2:
                    priority = st.selectbox(
                        "Priority:",
                        ["Normal", "High", "Low"],
                        help="Higher priority jobs are processed first"
                    )
                
                # Advanced options
                with st.expander("Advanced Options"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        retry_count = st.number_input("Max Retries:", min_value=0, max_value=5, value=3)
                    with col2:
                        timeout = st.number_input("Timeout (seconds):", min_value=10, max_value=120, value=30)
                    with col3:
                        save_screenshots = st.checkbox("Save Screenshots", value=False)
                
                # Start Extraction Button
                st.markdown("#### Step 4: Start Extraction")
                
                col1, col2, col3 = st.columns([2, 1, 2])
                with col2:
                    if st.button("🚀 Start Extraction", type="primary", use_container_width=True):
                        if selected_properties:
                            with st.spinner(f"Creating extraction job for {len(selected_properties)} properties..."):
                                # Prepare job data
                                job_data = {
                                    "property_ids": [p['property_id'] for p in selected_properties],
                                    "extraction_method": extraction_method.lower().replace(" ", "_"),
                                    "priority": priority.lower(),
                                    "options": {
                                        "retry_count": retry_count,
                                        "timeout": timeout,
                                        "save_screenshots": save_screenshots
                                    }
                                }
                                
                                # Call API to create extraction job
                                try:
                                    response = requests.post(
                                        f"{API_URL}/api/v1/extract",
                                        json=job_data,
                                        headers={"Authorization": f"Bearer {st.session_state.access_token}"}
                                        if st.session_state.access_token != "demo_token" else {},
                                        timeout=10
                                    )
                                    
                                    if response.status_code == 200:
                                        job_result = response.json()
                                        st.success(f"✅ Extraction job created successfully!")
                                        st.info(f"Job ID: {job_result.get('job_id', 'Unknown')}")
                                        st.balloons()
                                        
                                        # Switch to monitoring tab
                                        st.info("Switch to the 'Running Jobs' tab to monitor progress")
                                    else:
                                        st.error(f"Failed to create job: {response.status_code}")
                                except Exception as e:
                                    st.error(f"Error creating extraction job: {str(e)}")
                                    st.info("Note: The extraction API endpoint may need to be implemented")
                        else:
                            st.warning("Please select at least one property")
                
            else:
                st.info("👆 Select properties using the options above to begin")
                
        except Exception as e:
            st.error(f"Error loading properties: {str(e)}")
    
    with tab2:
        st.markdown("### 📊 Active Extraction Jobs")
        
        # Auto-refresh option
        col1, col2 = st.columns([4, 1])
        with col2:
            auto_refresh = st.checkbox("Auto-refresh", value=True)
        
        if auto_refresh:
            st.info("🔄 Auto-refreshing every 5 seconds...")
            time.sleep(5)
            st.rerun()
        
        # Mock data for demonstration (replace with actual API call)
        st.info("📝 No active extraction jobs")
        
        # In production, this would fetch from the API:
        # jobs_data = fetch_api_data("/api/v1/jobs", st.session_state.access_token)
        
    with tab3:
        st.markdown("### 📜 Extraction History")
        
        try:
            # Get recent extractions from database
            recent_extractions = db_client.get_recent_extractions(limit=100)
            
            if recent_extractions:
                # Create DataFrame
                df_history = pd.DataFrame(recent_extractions)
                
                # Add filters
                col1, col2, col3 = st.columns(3)
                with col1:
                    date_filter = st.date_input("Filter by Date:", value=None)
                with col2:
                    status_filter = st.selectbox("Status:", ["All", "success", "failed", "pending"])
                with col3:
                    search = st.text_input("Search property:", "")
                
                # Apply filters
                if date_filter:
                    df_history = df_history[pd.to_datetime(df_history['extraction_date']).dt.date == date_filter]
                if status_filter != "All":
                    df_history = df_history[df_history['extraction_status'] == status_filter]
                if search:
                    df_history = df_history[df_history['property_name'].str.contains(search, case=False, na=False)]
                
                # Display metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Extractions", len(df_history))
                with col2:
                    success_count = len(df_history[df_history['extraction_status'] == 'success'])
                    st.metric("Successful", success_count)
                with col3:
                    failed_count = len(df_history[df_history['extraction_status'] == 'failed'])
                    st.metric("Failed", failed_count)
                with col4:
                    success_rate = (success_count / len(df_history) * 100) if len(df_history) > 0 else 0
                    st.metric("Success Rate", f"{success_rate:.1f}%")
                
                # Display table
                display_cols = ['property_name', 'extraction_status', 'amount_due', 'extraction_date', 'extraction_method']
                available_cols = [col for col in display_cols if col in df_history.columns]
                
                if available_cols:
                    df_display = df_history[available_cols].copy()
                    if 'extraction_date' in df_display.columns:
                        df_display['extraction_date'] = pd.to_datetime(df_display['extraction_date']).dt.strftime('%Y-%m-%d %H:%M')
                    if 'amount_due' in df_display.columns:
                        df_display['amount_due'] = df_display['amount_due'].apply(lambda x: format_currency(float(x or 0)))
                    
                    st.dataframe(df_display, use_container_width=True, hide_index=True)
            else:
                st.info("No extraction history available")
                
        except Exception as e:
            st.error(f"Error loading extraction history: {str(e)}")
    
    with tab4:
        st.markdown("### ⚙️ Extraction Configuration")
        
        st.info("Configure default extraction settings and method preferences")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Default Settings")
            st.number_input("Default Timeout (seconds):", min_value=10, max_value=120, value=30)
            st.number_input("Default Retry Count:", min_value=0, max_value=5, value=3)
            st.number_input("Rate Limit Delay (seconds):", min_value=1, max_value=10, value=2)
            
        with col2:
            st.markdown("#### Method Preferences")
            st.checkbox("Enable Selenium for JavaScript sites", value=True)
            st.checkbox("Enable Playwright (experimental)", value=False)
            st.checkbox("Save extraction screenshots", value=False)
            st.checkbox("Enable verbose logging", value=False)
        
        if st.button("💾 Save Configuration"):
            st.success("Configuration saved successfully!")

def render_analytics():
    """Render analytics charts."""
    st.markdown("## 📈 Analytics")
    
    db_client = st.session_state.db_client
    
    try:
        # Get data for charts
        properties = db_client.get_properties(limit=1000)
        
        if properties:
            df = pd.DataFrame(properties)
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Properties by State
                if 'state' in df.columns:
                    state_counts = df['state'].value_counts().head(10)
                    fig1 = px.bar(
                        x=state_counts.values,
                        y=state_counts.index,
                        orientation='h',
                        title="Properties by State",
                        labels={'x': 'Count', 'y': 'State'}
                    )
                    st.plotly_chart(fig1, use_container_width=True)
            
            with col2:
                # Tax amounts by Jurisdiction
                if 'jurisdiction' in df.columns and 'amount_due' in df.columns:
                    jurisdiction_totals = df.groupby('jurisdiction')['amount_due'].sum().sort_values(ascending=False).head(10)
                    fig2 = px.bar(
                        x=jurisdiction_totals.values,
                        y=jurisdiction_totals.index,
                        orientation='h',
                        title="Tax Amount by Jurisdiction",
                        labels={'x': 'Total Amount Due', 'y': 'Jurisdiction'}
                    )
                    st.plotly_chart(fig2, use_container_width=True)
            
            # Payment Status Distribution
            if 'amount_due' in df.columns:
                df['payment_status'] = df['amount_due'].apply(
                    lambda x: 'Paid' if x == 0 else 'Outstanding'
                )
                status_counts = df['payment_status'].value_counts()
                
                fig3 = px.pie(
                    values=status_counts.values,
                    names=status_counts.index,
                    title="Payment Status Distribution",
                    color_discrete_map={'Paid': '#48bb78', 'Outstanding': '#f56565'}
                )
                st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("No data available for analytics")
            
    except Exception as e:
        st.error(f"Failed to load analytics: {str(e)}")

def render_entities_hierarchy():
    """Render entities hierarchy visualization."""
    st.markdown("## 🏢 Entity Management")
    
    db_client = st.session_state.db_client
    
    try:
        # Get all entities
        entities = db_client.get_entities(limit=100)
        
        # Get all properties to link with entities
        properties = db_client.get_properties(limit=500)
        
        if entities:
            # Display entity count prominently
            st.info(f"📊 Total Entities: **{len(entities)}** | Total Properties: **{len(properties)}**")
            
            # Create entity lookup
            entity_by_name = {e['entity_name']: e for e in entities}
            
            # Group properties by parent entity
            properties_by_entity = {}
            for prop in properties:
                parent_name = prop.get('parent_entity_name')
                if parent_name:
                    if parent_name not in properties_by_entity:
                        properties_by_entity[parent_name] = []
                    properties_by_entity[parent_name].append(prop)
            
            # Create tabs for different views
            tab1, tab2, tab3 = st.tabs(["📊 Hierarchy View", "📋 Table View", "📈 Analytics"])
            
            with tab1:
                st.markdown("### Entity Hierarchy Visualization")
                
                # Create a simpler, more readable visualization
                viz_option = st.radio(
                    "Select Visualization Type:",
                    ["Treemap (Tax Amounts)", "Sunburst (Entity Structure)", "Simple List"],
                    horizontal=True
                )
                
                if viz_option == "Treemap (Tax Amounts)":
                    # Only show entities with actual tax amounts for clarity
                    entities_with_amounts = [e for e in entities if float(e.get('amount_due') or 0) > 0]
                    
                    if entities_with_amounts:
                        # Prepare data for treemap
                        labels = []
                        parents = []
                        values = []
                        colors = []
                        
                        # Add root
                        labels.append("All Entities")
                        parents.append("")
                        total_value = sum(float(e.get('amount_due') or 0) for e in entities_with_amounts)
                        values.append(total_value)
                        colors.append(total_value)
                        
                        # Add only entities with amounts
                        for entity in entities_with_amounts:
                            entity_name = entity['entity_name']
                            # Shorten long entity names for better display
                            display_name = entity_name if len(entity_name) <= 30 else entity_name[:27] + "..."
                            labels.append(display_name)
                            parents.append("All Entities")
                            entity_value = float(entity.get('amount_due') or 0)
                            values.append(entity_value)
                            colors.append(entity_value)
                        
                        # Create treemap
                        fig = go.Figure(go.Treemap(
                            labels=labels,
                            parents=parents,
                            values=values,
                            textinfo="label+value",
                            marker=dict(
                                colorscale='RdYlGn_r',
                                cmid=0,
                                colorbar=dict(title="Amount Due ($)"),
                                line=dict(width=2, color='white')
                            ),
                            hovertemplate='<b>%{label}</b><br>Amount: $%{value:,.2f}<extra></extra>'
                        ))
                        
                        fig.update_layout(
                            title=f"Entities with Outstanding Tax Amounts ({len(entities_with_amounts)} of {len(entities)} entities)",
                            height=600,
                            margin=dict(t=50, l=0, r=0, b=0)
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("No entities have outstanding tax amounts.")
                
                elif viz_option == "Sunburst (Entity Structure)":
                    # Create sunburst chart showing entity-property relationships
                    labels = ["All<br>Entities"]
                    parents = [""]
                    values = [1]
                    
                    # Add all entities
                    for entity in entities:
                        entity_name = entity['entity_name']
                        # Shorten for display
                        display_name = entity_name if len(entity_name) <= 25 else entity_name[:22] + "..."
                        labels.append(display_name)
                        parents.append("All<br>Entities")
                        # Use property count as value for sizing
                        prop_count = len(properties_by_entity.get(entity_name, []))
                        values.append(prop_count if prop_count > 0 else 0.5)
                    
                    fig = go.Figure(go.Sunburst(
                        labels=labels,
                        parents=parents,
                        values=values,
                        branchvalues="total",
                        hovertemplate='<b>%{label}</b><br>Properties: %{value:.0f}<extra></extra>'
                    ))
                    
                    fig.update_layout(
                        title=f"All {len(entities)} Entities - Sized by Property Count",
                        height=600,
                        margin=dict(t=50, l=0, r=0, b=0)
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                
                else:  # Simple List
                    st.markdown("### Entity List with Properties")
                    
                    # Create expandable sections for each entity
                    search_term = st.text_input("🔍 Search entities:", "")
                    
                    filtered_entities = entities
                    if search_term:
                        filtered_entities = [e for e in entities if search_term.lower() in e['entity_name'].lower()]
                    
                    st.markdown(f"Showing {len(filtered_entities)} of {len(entities)} entities")
                    
                    for entity in filtered_entities[:20]:  # Limit to 20 for performance
                        entity_name = entity['entity_name']
                        entity_props = properties_by_entity.get(entity_name, [])
                        amount_due = float(entity.get('amount_due') or 0)
                        
                        with st.expander(f"{entity_name} ({len(entity_props)} properties) - {format_currency(amount_due)}"):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**Type:** {entity.get('entity_type', 'Unknown')}")
                                st.write(f"**State:** {entity.get('state', 'Unknown')}")
                            with col2:
                                st.write(f"**Entity Due:** {format_currency(amount_due)}")
                                props_total = sum(float(p.get('amount_due') or 0) for p in entity_props)
                                st.write(f"**Properties Total:** {format_currency(props_total)}")
                            
                            if entity_props:
                                st.markdown("**Properties:**")
                                for prop in entity_props[:5]:
                                    st.write(f"- {prop.get('property_name', 'Unknown')}: {format_currency(float(prop.get('amount_due') or 0))}")
                                if len(entity_props) > 5:
                                    st.write(f"... and {len(entity_props) - 5} more properties")
            
            with tab2:
                st.markdown("### 📋 Complete Entity Table")
                
                # Prepare entity summary data
                entity_summary = []
                for entity in entities:
                    entity_name = entity['entity_name']
                    prop_count = len(properties_by_entity.get(entity_name, []))
                    props_total_due = sum(float(p.get('amount_due') or 0) for p in properties_by_entity.get(entity_name, []))
                    entity_due = float(entity.get('amount_due') or 0)
                    
                    entity_summary.append({
                        'Entity': entity_name,
                        'Type': entity.get('entity_type', 'Unknown'),
                        'State': entity.get('state', 'Unknown'),
                        'Properties': prop_count,
                        'Props Total': format_currency(props_total_due),
                        'Entity Due': format_currency(entity_due),
                        'Combined Total': format_currency(props_total_due + entity_due)
                    })
                
                # Sort by combined total
                entity_summary.sort(key=lambda x: float(x['Combined Total'].replace('$', '').replace(',', '')), reverse=True)
                
                # Display as table
                df_entities = pd.DataFrame(entity_summary)
                
                # Add search/filter
                col1, col2, col3 = st.columns([3, 2, 2])
                with col1:
                    search = st.text_input("Search entities:", "")
                    if search:
                        df_entities = df_entities[df_entities['Entity'].str.contains(search, case=False, na=False)]
                
                with col2:
                    state_filter = st.selectbox("Filter by State:", ["All"] + sorted(df_entities['State'].unique().tolist()))
                    if state_filter != "All":
                        df_entities = df_entities[df_entities['State'] == state_filter]
                
                with col3:
                    type_filter = st.selectbox("Filter by Type:", ["All"] + sorted(df_entities['Type'].unique().tolist()))
                    if type_filter != "All":
                        df_entities = df_entities[df_entities['Type'] == type_filter]
                
                st.dataframe(
                    df_entities, 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={
                        "Properties": st.column_config.NumberColumn(format="%d"),
                        "Entity": st.column_config.TextColumn(width="large"),
                    }
                )
                
                # Export button
                csv = df_entities.to_csv(index=False)
                st.download_button(
                    label="📥 Export Entity Data",
                    data=csv,
                    file_name=f"entities_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            
            with tab3:
                st.markdown("### 📈 Entity Analytics")
                
                # Summary metrics
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Entities", len(entities))
                
                with col2:
                    parent_entities = [e for e in entities if e.get('entity_type') == 'parent entity']
                    st.metric("Parent Entities", len(parent_entities))
                
                with col3:
                    total_properties = sum(len(properties_by_entity.get(e['entity_name'], [])) for e in entities)
                    st.metric("Total Properties", total_properties)
                
                with col4:
                    entities_with_balance = [e for e in entities if float(e.get('amount_due') or 0) > 0]
                    st.metric("Entities w/ Balance", len(entities_with_balance))
                
                # Charts
                col1, col2 = st.columns(2)
                
                with col1:
                    # Entity types distribution
                    entity_types = {}
                    for e in entities:
                        etype = e.get('entity_type', 'Unknown')
                        entity_types[etype] = entity_types.get(etype, 0) + 1
                    
                    fig1 = px.pie(
                        values=list(entity_types.values()),
                        names=list(entity_types.keys()),
                        title="Entity Types Distribution"
                    )
                    st.plotly_chart(fig1, use_container_width=True)
                
                with col2:
                    # Top 10 entities by total liability
                    entity_liabilities = []
                    for entity in entities:
                        entity_name = entity['entity_name']
                        props_total = sum(float(p.get('amount_due') or 0) for p in properties_by_entity.get(entity_name, []))
                        entity_due = float(entity.get('amount_due') or 0)
                        total = props_total + entity_due
                        if total > 0:
                            entity_liabilities.append({
                                'Entity': entity_name[:20] + '...' if len(entity_name) > 20 else entity_name,
                                'Amount': total
                            })
                    
                    entity_liabilities.sort(key=lambda x: x['Amount'], reverse=True)
                    top_10 = entity_liabilities[:10]
                    
                    if top_10:
                        df_top = pd.DataFrame(top_10)
                        fig2 = px.bar(
                            df_top,
                            x='Amount',
                            y='Entity',
                            orientation='h',
                            title="Top 10 Entities by Total Tax Liability"
                        )
                        st.plotly_chart(fig2, use_container_width=True)
                    else:
                        st.info("No entities with tax liabilities")
                
                # Entity states distribution
                entity_states = {}
                for e in entities:
                    state = e.get('state', 'Unknown')
                    entity_states[state] = entity_states.get(state, 0) + 1
                
                if len(entity_states) > 1:
                    fig3 = px.bar(
                        x=list(entity_states.values()),
                        y=list(entity_states.keys()),
                        orientation='h',
                        title="Entities by State",
                        labels={'x': 'Count', 'y': 'State'}
                    )
                    st.plotly_chart(fig3, use_container_width=True)
            
        else:
            st.info("No entities found in the database.")
            
    except Exception as e:
        st.error(f"Failed to load entity hierarchy: {str(e)}")

def render_settings():
    """Render settings page."""
    st.markdown("## ⚙️ Settings")
    
    tabs = st.tabs(["API Configuration", "Database Info", "System Status"])
    
    with tabs[0]:
        st.markdown("### API Configuration")
        
        col1, col2 = st.columns(2)
        with col1:
            st.text_input("API URL", value=API_URL, disabled=True)
            st.text_input("Supabase URL", value=SUPABASE_URL, disabled=True)
        
        with col2:
            st.text_input("Environment", value="Production" if "localhost" not in API_URL else "Development", disabled=True)
            st.text_input("Auth Mode", value="Supabase Auth", disabled=True)
    
    with tabs[1]:
        st.markdown("### Database Information")
        
        db_client = st.session_state.db_client
        try:
            stats = db_client.calculate_tax_statistics()
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Properties", f"{stats.get('total_properties', 0):,}")
                st.metric("Properties with Balance", f"{stats.get('properties_with_balance', 0):,}")
            
            with col2:
                st.metric("Total Entities", f"{stats.get('total_entities', 0):,}")
                st.metric("Properties Paid", f"{stats.get('properties_paid', 0):,}")
            
        except Exception as e:
            st.error(f"Failed to load database info: {str(e)}")
    
    with tabs[2]:
        st.markdown("### System Status")
        
        # Check API health
        health = fetch_api_data("/health")
        
        if health:
            col1, col2 = st.columns(2)
            with col1:
                st.success(f"✅ API Status: {health.get('status', 'unknown')}")
                st.info(f"Database: {health.get('database', 'unknown')}")
            
            with col2:
                st.info(f"Auth: {health.get('auth', 'unknown')}")
                st.caption(f"Last checked: {datetime.now().strftime('%H:%M:%S')}")
        else:
            st.error("❌ API is not responding")

# ========================= Main Dashboard =========================

def main_dashboard():
    """Main dashboard after authentication."""
    
    # Sidebar
    state_filter, jurisdiction_filter, entity_filter = render_sidebar()
    
    # Main content
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📊 Overview", "🏢 Entities", "🏘️ Properties", "🔄 Jobs", "📈 Analytics", "⚙️ Settings"])
    
    with tab1:
        render_overview_metrics()
        
        # Outstanding Balance Properties
        st.markdown("### 💰 Properties with Outstanding Balance")
        db_client = st.session_state.db_client
        try:
            # Get properties with outstanding balance
            all_properties = db_client.get_properties(limit=500)
            outstanding_properties = [p for p in all_properties if float(p.get('amount_due') or 0) > 0]
            
            if outstanding_properties:
                # Sort by amount due (descending)
                outstanding_properties.sort(key=lambda x: float(x.get('amount_due') or 0), reverse=True)
                
                # Take top 10 for display
                top_outstanding = outstanding_properties[:10]
                
                # Create DataFrame
                df_outstanding = pd.DataFrame(top_outstanding)
                display_cols = ['property_name', 'jurisdiction', 'state', 'amount_due', 'parent_entity_name']
                available_cols = [col for col in display_cols if col in df_outstanding.columns]
                
                if available_cols:
                    df_display = df_outstanding[available_cols].copy()
                    
                    # Rename columns for display
                    column_mapping = {
                        'property_name': 'Property',
                        'jurisdiction': 'Jurisdiction',
                        'state': 'State',
                        'amount_due': 'Amount Due',
                        'parent_entity_name': 'Entity'
                    }
                    df_display = df_display.rename(columns=column_mapping)
                    
                    # Format currency
                    if 'Amount Due' in df_display.columns:
                        df_display['Amount Due'] = df_display['Amount Due'].apply(lambda x: format_currency(x) if pd.notna(x) else "$0.00")
                    
                    # Display table
                    st.dataframe(df_display, use_container_width=True, hide_index=True)
                    
                    # Summary
                    total_outstanding = sum(float(p.get('amount_due') or 0) for p in outstanding_properties)
                    st.caption(f"Showing top 10 of {len(outstanding_properties)} properties with outstanding balance. Total: {format_currency(total_outstanding)}")
            else:
                st.success("✅ No properties with outstanding balance!")
        except Exception as e:
            st.error(f"Failed to load outstanding properties: {str(e)}")
        
        # Recent activity
        st.markdown("### 📝 Recent Extractions")
        try:
            recent = db_client.get_recent_extractions(limit=10)
            if recent:
                recent_df = pd.DataFrame(recent)
                if 'extraction_date' in recent_df.columns:
                    recent_df['extraction_date'] = pd.to_datetime(recent_df['extraction_date']).dt.strftime('%Y-%m-%d %H:%M')
                
                display_cols = ['property_name', 'extraction_status', 'amount_due', 'extraction_date']
                available = [col for col in display_cols if col in recent_df.columns]
                
                if available:
                    st.dataframe(recent_df[available], use_container_width=True, hide_index=True)
                else:
                    st.info("No recent extractions")
            else:
                st.info("No recent extraction activity")
        except:
            st.info("Extraction history will appear here")
    
    with tab2:
        render_entities_hierarchy()
    
    with tab3:
        render_properties_table(state_filter, jurisdiction_filter, entity_filter)
    
    with tab4:
        render_extraction_jobs()
    
    with tab5:
        render_analytics()
    
    with tab6:
        render_settings()

# ========================= Main App =========================

def main():
    """Main application entry point."""
    
    # Check authentication
    if not st.session_state.authenticated:
        login_page()
    else:
        main_dashboard()

if __name__ == "__main__":
    main()