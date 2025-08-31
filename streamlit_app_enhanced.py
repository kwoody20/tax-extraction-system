"""
Enhanced Streamlit Dashboard for Tax Extraction System.
Features comprehensive optimizations, improved UI/UX, and advanced functionality.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import os
from datetime import datetime, timedelta
import json
from io import BytesIO
import time
import hashlib
from typing import Dict, List, Optional, Tuple, Any
import logging
from functools import lru_cache
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration with enhanced settings
st.set_page_config(
    page_title="Tax Dashboard Pro",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/kwoody20/tax-extraction-system',
        'Report a bug': 'https://github.com/kwoody20/tax-extraction-system/issues',
        'About': 'Tax Extraction System v2.0 - Enhanced Dashboard'
    }
)

# Enhanced CSS with modern design and animations
st.markdown("""
<style>
    /* Base Theme */
    :root {
        --primary-color: #667eea;
        --secondary-color: #764ba2;
        --success-color: #48bb78;
        --warning-color: #f6ad55;
        --danger-color: #fc8181;
        --info-color: #63b3ed;
        --dark-color: #2d3748;
        --light-color: #f7fafc;
        --shadow-sm: 0 1px 3px rgba(0,0,0,0.12);
        --shadow-md: 0 4px 6px rgba(0,0,0,0.1);
        --shadow-lg: 0 10px 25px rgba(0,0,0,0.1);
        --transition: all 0.3s ease;
    }
    
    /* Hide Streamlit defaults */
    #MainMenu {visibility: hidden;}
    .stDeployButton {display: none;}
    footer {visibility: hidden;}
    ._profileContainer {display: none;}
    header[data-testid="stHeader"] {height: 0px;}
    .stToolbar {display: none;}
    .viewerBadge_container__1QSob {display: none;}
    
    /* Enhanced Metrics */
    .stMetric {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 20px;
        border-radius: 15px;
        box-shadow: var(--shadow-lg);
        transition: var(--transition);
        border: none;
    }
    
    .stMetric:hover {
        transform: translateY(-5px);
        box-shadow: 0 15px 30px rgba(102, 126, 234, 0.3);
    }
    
    .stMetric [data-testid="metric-container"] {
        color: white !important;
    }
    
    .stMetric [data-testid="metric-label"] {
        color: rgba(255, 255, 255, 0.9) !important;
        font-weight: 600;
        font-size: 14px;
    }
    
    .stMetric [data-testid="metric-value"] {
        color: white !important;
        font-weight: 700;
        font-size: 28px;
    }
    
    .stMetric [data-testid="metric-delta"] {
        color: rgba(255, 255, 255, 0.8) !important;
    }
    
    /* Status Badges */
    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        transition: var(--transition);
    }
    
    .paid-by-landlord {
        background-color: var(--success-color);
        color: white;
        box-shadow: 0 2px 4px rgba(72, 187, 120, 0.3);
    }
    
    .paid-by-tenant {
        background-color: var(--info-color);
        color: white;
        box-shadow: 0 2px 4px rgba(99, 179, 237, 0.3);
    }
    
    .paid-by-reimburse {
        background-color: var(--warning-color);
        color: white;
        box-shadow: 0 2px 4px rgba(246, 173, 85, 0.3);
    }
    
    .due-soon {
        background-color: var(--danger-color);
        color: white;
        animation: pulse 2s infinite;
    }
    
    .due-later {
        background-color: var(--success-color);
        color: white;
    }
    
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(252, 129, 129, 0.7); }
        70% { box-shadow: 0 0 0 10px rgba(252, 129, 129, 0); }
        100% { box-shadow: 0 0 0 0 rgba(252, 129, 129, 0); }
    }
    
    /* Enhanced Sidebar */
    .css-1d391kg {
        background: linear-gradient(180deg, var(--light-color) 0%, white 100%);
    }
    
    div[data-testid="stSidebarNav"] {
        background: white;
        border-radius: 15px;
        padding: 20px;
        box-shadow: var(--shadow-md);
        margin: 10px;
    }
    
    /* Enhanced Tables */
    .dataframe {
        box-shadow: var(--shadow-md);
        border-radius: 10px;
        overflow: hidden;
    }
    
    .dataframe thead th {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white !important;
        font-weight: 600;
        text-transform: uppercase;
        font-size: 12px;
        letter-spacing: 0.5px;
        padding: 12px !important;
    }
    
    .dataframe tbody tr:hover {
        background-color: rgba(102, 126, 234, 0.05);
        transition: var(--transition);
    }
    
    /* Enhanced Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 10px 24px;
        border-radius: 8px;
        font-weight: 600;
        transition: var(--transition);
        box-shadow: var(--shadow-md);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-lg);
    }
    
    /* Info boxes */
    .info-box {
        background: linear-gradient(135deg, #63b3ed 0%, #4299e1 100%);
        color: white;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
        box-shadow: var(--shadow-md);
    }
    
    .success-box {
        background: linear-gradient(135deg, #48bb78 0%, #38a169 100%);
        color: white;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
        box-shadow: var(--shadow-md);
    }
    
    .warning-box {
        background: linear-gradient(135deg, #f6ad55 0%, #ed8936 100%);
        color: white;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
        box-shadow: var(--shadow-md);
    }
    
    /* Loading animation */
    .loading-spinner {
        border: 4px solid var(--light-color);
        border-top: 4px solid var(--primary-color);
        border-radius: 50%;
        width: 40px;
        height: 40px;
        animation: spin 1s linear infinite;
        margin: 20px auto;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    /* Tooltips */
    .tooltip {
        position: relative;
        display: inline-block;
        cursor: help;
    }
    
    .tooltip .tooltiptext {
        visibility: hidden;
        width: 200px;
        background-color: var(--dark-color);
        color: white;
        text-align: center;
        border-radius: 6px;
        padding: 8px;
        position: absolute;
        z-index: 1;
        bottom: 125%;
        left: 50%;
        margin-left: -100px;
        opacity: 0;
        transition: opacity 0.3s;
        font-size: 12px;
    }
    
    .tooltip:hover .tooltiptext {
        visibility: visible;
        opacity: 1;
    }
    
    /* Responsive design */
    @media (max-width: 768px) {
        .stMetric {
            padding: 15px;
            margin-bottom: 10px;
        }
        
        .dataframe {
            font-size: 12px;
        }
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state with enhanced structure
def init_session_state():
    """Initialize all session state variables with proper defaults."""
    defaults = {
        'last_refresh': datetime.now(),
        'properties_data': None,
        'stats_data': None,
        'entities_data': None,
        'extraction_history': [],
        'filter_state': {},
        'view_mode': 'grid',
        'theme': 'light',
        'notifications': [],
        'cache_hash': {},
        'user_preferences': {
            'auto_refresh': False,
            'refresh_interval': 300,
            'compact_view': False,
            'show_tooltips': True
        }
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# Initialize session state
init_session_state()

# Get API URL from secrets or environment with fallback
@st.cache_data(ttl=3600)
def get_api_url() -> str:
    """Get API URL with proper fallback logic."""
    try:
        return st.secrets["API_URL"]
    except:
        return os.getenv("API_URL", "https://tax-extraction-system-production.up.railway.app")

API_URL = get_api_url()

# Enhanced caching with hash-based invalidation
def get_cache_key(endpoint: str, params: Dict = None) -> str:
    """Generate cache key for data fetching."""
    key_parts = [endpoint]
    if params:
        key_parts.append(json.dumps(params, sort_keys=True))
    return hashlib.md5(''.join(key_parts).encode()).hexdigest()

# Enhanced data fetching with retry logic and error handling
@st.cache_data(ttl=300, show_spinner=False)
def fetch_data_with_retry(endpoint: str, method: str = "GET", 
                          payload: Dict = None, max_retries: int = 3) -> Optional[Dict]:
    """Fetch data with retry logic and comprehensive error handling."""
    url = f"{API_URL}{endpoint}"
    
    for attempt in range(max_retries):
        try:
            if method == "GET":
                response = requests.get(url, timeout=10)
            else:
                response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:  # Rate limited
                wait_time = min(2 ** attempt, 10)
                time.sleep(wait_time)
                continue
            else:
                logger.warning(f"API returned {response.status_code} for {endpoint}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"Timeout on attempt {attempt + 1} for {endpoint}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
        except Exception as e:
            logger.error(f"Error fetching {endpoint}: {e}")
            return None
    
    return None

# Optimized data fetching functions
@st.cache_data(ttl=300)
def fetch_properties() -> List[Dict]:
    """Fetch properties data with caching."""
    data = fetch_data_with_retry("/api/v1/properties")
    return data.get("properties", []) if data else []

@st.cache_data(ttl=300)
def fetch_statistics() -> Dict:
    """Fetch statistics with caching."""
    return fetch_data_with_retry("/api/v1/statistics") or {}

@st.cache_data(ttl=300)
def fetch_entities() -> List[Dict]:
    """Fetch entities data with caching."""
    data = fetch_data_with_retry("/api/v1/entities")
    return data.get("entities", []) if data else []

@st.cache_data(ttl=300)
def fetch_jurisdictions() -> Dict:
    """Fetch supported jurisdictions."""
    data = fetch_data_with_retry("/api/v1/jurisdictions")
    return data.get("jurisdictions", {}) if data else {}

# Utility functions with performance optimizations
@st.cache_data
def format_currency(value: float) -> str:
    """Format currency values with proper handling of None/NaN."""
    if pd.isna(value) or value is None:
        return "$0.00"
    return f"${value:,.2f}"

@st.cache_data
def format_percentage(value: float) -> str:
    """Format percentage values."""
    if pd.isna(value) or value is None:
        return "0.0%"
    return f"{value:.1f}%"

def format_paid_by(value: str) -> str:
    """Format paid_by field with color coding."""
    if pd.isna(value) or value == "":
        return '<span class="status-badge">-</span>'
    
    value_lower = str(value).lower()
    if "landlord" in value_lower:
        return f'<span class="status-badge paid-by-landlord">{value}</span>'
    elif "reimburse" in value_lower:
        return f'<span class="status-badge paid-by-reimburse">{value}</span>'
    elif "tenant" in value_lower:
        return f'<span class="status-badge paid-by-tenant">{value}</span>'
    else:
        return f'<span class="status-badge">{value}</span>'

def format_due_date(date_value) -> str:
    """Format due date with enhanced color coding and urgency indicators."""
    if pd.isna(date_value) or date_value == "":
        return '<span class="status-badge">No Date</span>'
    
    try:
        if isinstance(date_value, str):
            due_date = pd.to_datetime(date_value)
        else:
            due_date = date_value
            
        formatted_date = due_date.strftime('%m/%d/%Y')
        days_until = (due_date - datetime.now()).days
        
        if days_until < 0:
            return f'<span class="status-badge due-soon">⚠️ OVERDUE ({abs(days_until)}d)</span>'
        elif days_until <= 7:
            return f'<span class="status-badge due-soon">🔴 {formatted_date} ({days_until}d)</span>'
        elif days_until <= 30:
            return f'<span class="status-badge paid-by-reimburse">🟡 {formatted_date} ({days_until}d)</span>'
        else:
            return f'<span class="status-badge due-later">🟢 {formatted_date}</span>'
    except:
        return f'<span class="status-badge">{date_value}</span>'

# Enhanced health check with detailed status
@st.cache_data(ttl=60)
def check_system_health() -> Tuple[str, Dict]:
    """Comprehensive system health check."""
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        data = response.json()
        
        if response.status_code == 200:
            status = data.get("status", "unknown")
            return status, data
        else:
            return "degraded", {"message": f"API returned {response.status_code}"}
    except requests.exceptions.Timeout:
        return "timeout", {"message": "Health check timed out"}
    except Exception as e:
        return "error", {"message": str(e)}

# Enhanced data filtering with memoization
@st.cache_data
def apply_filters(df: pd.DataFrame, filters: Dict) -> pd.DataFrame:
    """Apply filters to dataframe with optimized performance."""
    if df.empty:
        return df
    
    filtered_df = df.copy()
    
    # Entity filter
    if filters.get('entity') and filters['entity'] != "All":
        entity_id = filters.get('entity_id')
        if entity_id and 'entity_id' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['entity_id'] == entity_id]
    
    # Paid by filter
    if filters.get('paid_by') and filters['paid_by'] != "All":
        filtered_df = filtered_df[filtered_df['paid_by'] == filters['paid_by']]
    
    # State filter
    if filters.get('state') and filters['state'] != "All":
        filtered_df = filtered_df[filtered_df['state'] == filters['state']]
    
    # Jurisdiction filter
    if filters.get('jurisdiction') and filters['jurisdiction'] != "All":
        filtered_df = filtered_df[filtered_df['jurisdiction'] == filters['jurisdiction']]
    
    # Date range filter
    if filters.get('date_range') and len(filters['date_range']) == 2:
        start_date, end_date = filters['date_range']
        if 'tax_due_date_dt' in filtered_df.columns:
            filtered_df = filtered_df[
                (filtered_df['tax_due_date_dt'].dt.date >= start_date) & 
                (filtered_df['tax_due_date_dt'].dt.date <= end_date)
            ]
    
    # Quick filters
    if filters.get('show_overdue') and 'tax_due_date_dt' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['tax_due_date_dt'] < datetime.now()]
    
    if filters.get('show_upcoming_30') and 'tax_due_date_dt' in filtered_df.columns:
        thirty_days = datetime.now() + timedelta(days=30)
        filtered_df = filtered_df[
            (filtered_df['tax_due_date_dt'] >= datetime.now()) & 
            (filtered_df['tax_due_date_dt'] <= thirty_days)
        ]
    
    return filtered_df

# Progress indicator component
def show_progress(message: str, progress: float = None):
    """Display progress indicator with optional percentage."""
    if progress is not None:
        progress_bar = st.progress(progress)
        status_text = st.empty()
        status_text.text(f"{message} ({int(progress * 100)}%)")
        return progress_bar, status_text
    else:
        return st.spinner(message)

# Header with enhanced controls
def render_header():
    """Render enhanced header with controls."""
    col1, col2, col3 = st.columns([3, 1, 1])
    
    with col1:
        st.title("🏢 Property Tax Dashboard Pro")
        st.caption(f"Real-time monitoring with advanced analytics • Last refresh: {st.session_state.last_refresh.strftime('%H:%M:%S')}")
    
    with col2:
        # Auto-refresh toggle
        auto_refresh = st.checkbox(
            "Auto Refresh",
            value=st.session_state.user_preferences['auto_refresh'],
            help="Enable automatic data refresh every 5 minutes"
        )
        st.session_state.user_preferences['auto_refresh'] = auto_refresh
    
    with col3:
        if st.button("🔄 Refresh Now", use_container_width=True, type="primary"):
            st.cache_data.clear()
            st.session_state.last_refresh = datetime.now()
            st.rerun()

# Enhanced sidebar with better organization
def render_sidebar():
    """Render enhanced sidebar with improved filtering and status."""
    with st.sidebar:
        # System Status Card
        st.header("🔧 System Status")
        
        status, health_data = check_system_health()
        
        if status == "healthy":
            st.success("✅ **All Systems Operational**")
            with st.expander("Details", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("API", "Online", delta="100%")
                with col2:
                    st.metric("Database", "Connected", delta="Active")
        elif status == "degraded":
            st.warning("⚠️ **System Degraded**")
            st.caption(health_data.get("message", "Check logs for details"))
        else:
            st.error("❌ **System Offline**")
            st.caption(health_data.get("message", "Connection failed"))
        
        st.divider()
        
        # Enhanced Filters Section
        st.header("🔍 Advanced Filters")
        
        # Load data for filters
        properties = fetch_properties()
        entities = fetch_entities()
        
        filters = {}
        
        if properties:
            df_props = pd.DataFrame(properties)
            
            # Entity Filter with search
            if entities:
                st.subheader("🏢 Entity Selection")
                entity_names = ["All"] + sorted([e.get('entity_name', 'Unknown') for e in entities if e.get('entity_name')])
                
                # Add search box for entities
                entity_search = st.text_input("Search entities", placeholder="Type to filter...")
                if entity_search:
                    entity_names = ["All"] + [e for e in entity_names[1:] if entity_search.lower() in e.lower()]
                
                selected_entity = st.selectbox(
                    "Select Entity",
                    entity_names,
                    help="Filter properties by their parent entity"
                )
                filters['entity'] = selected_entity
                
                # Store entity_id for filtering
                if selected_entity != "All":
                    for e in entities:
                        if e.get('entity_name') == selected_entity:
                            filters['entity_id'] = e.get('entity_id')
                            break
            
            # Payment Responsibility Filter
            if 'paid_by' in df_props.columns:
                st.subheader("💰 Payment Responsibility")
                paid_by_options = ["All"] + sorted(df_props['paid_by'].dropna().unique().tolist())
                filters['paid_by'] = st.selectbox("Paid By", paid_by_options)
            
            # Location Filters
            st.subheader("📍 Location")
            col1, col2 = st.columns(2)
            
            with col1:
                if 'state' in df_props.columns:
                    state_options = ["All"] + sorted(df_props['state'].dropna().unique().tolist())
                    filters['state'] = st.selectbox("State", state_options)
            
            with col2:
                if 'jurisdiction' in df_props.columns:
                    jurisdiction_options = ["All"] + sorted(df_props['jurisdiction'].dropna().unique().tolist())
                    filters['jurisdiction'] = st.selectbox("Jurisdiction", jurisdiction_options)
            
            # Date Range Filter
            st.subheader("📅 Due Date Range")
            
            if 'tax_due_date' in df_props.columns:
                df_props['tax_due_date_dt'] = pd.to_datetime(df_props['tax_due_date'], errors='coerce')
                valid_dates = df_props['tax_due_date_dt'].dropna()
                
                if not valid_dates.empty:
                    min_date = valid_dates.min().date()
                    max_date = valid_dates.max().date()
                    
                    date_range = st.date_input(
                        "Select range",
                        value=(min_date, max_date),
                        min_value=min_date,
                        max_value=max_date,
                        format="MM/DD/YYYY"
                    )
                    filters['date_range'] = date_range
            
            # Quick Filters
            st.subheader("⚡ Quick Filters")
            filters['show_overdue'] = st.checkbox("🔴 Overdue Only", value=False)
            filters['show_upcoming_30'] = st.checkbox("🟡 Due in 30 Days", value=False)
            
            # Amount Range Filter
            if 'amount_due' in df_props.columns:
                st.subheader("💵 Amount Range")
                valid_amounts = df_props['amount_due'].dropna()
                if not valid_amounts.empty:
                    min_amount = float(valid_amounts.min())
                    max_amount = float(valid_amounts.max())
                    
                    amount_range = st.slider(
                        "Tax Amount Range",
                        min_value=min_amount,
                        max_value=max_amount,
                        value=(min_amount, max_amount),
                        format="$%.0f"
                    )
                    filters['amount_range'] = amount_range
        
        # Export Settings
        st.divider()
        st.subheader("⚙️ Export Settings")
        export_format = st.selectbox(
            "Default Format",
            ["Excel", "CSV", "JSON"],
            help="Choose default export format"
        )
        st.session_state.user_preferences['export_format'] = export_format
        
        return filters

# Enhanced overview tab with better visualizations
def render_overview_tab(df: pd.DataFrame, stats: Dict, entities: List[Dict]):
    """Render enhanced overview tab with comprehensive metrics."""
    st.header("📊 Executive Dashboard")
    
    # Primary KPI Cards with animations
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_props = len(df) if not df.empty else 0
        total_all = stats.get('total_properties', 0)
        st.metric(
            "Properties in View",
            total_props,
            f"{(total_props/total_all*100):.0f}% of total" if total_all > 0 else "N/A",
            help="Properties matching current filters"
        )
    
    with col2:
        total_entities = stats.get("total_entities", 0)
        active_entities = len(set(df['entity_id'].dropna())) if not df.empty and 'entity_id' in df.columns else 0
        st.metric(
            "Active Entities",
            active_entities,
            f"of {total_entities} total",
            help="Entities with properties in current view"
        )
    
    with col3:
        outstanding = df['outstanding_tax'].sum() if not df.empty and 'outstanding_tax' in df.columns else 0
        st.metric(
            "Outstanding Tax",
            format_currency(outstanding),
            "Current liability",
            help="Total tax amount currently due"
        )
    
    with col4:
        success_rate = stats.get("extraction_success_rate", 0)
        delta_color = "normal" if success_rate >= 80 else "inverse"
        st.metric(
            "Extraction Success",
            format_percentage(success_rate),
            "Last 24 hours",
            delta_color=delta_color,
            help="Percentage of successful extractions"
        )
    
    # Enhanced visualizations
    if not df.empty:
        # Payment Responsibility Analysis
        st.divider()
        st.subheader("💰 Payment Responsibility Analysis")
        
        if 'paid_by' in df.columns:
            col1, col2 = st.columns([1, 2])
            
            with col1:
                # Summary metrics
                paid_by_counts = df['paid_by'].value_counts()
                for category, count in paid_by_counts.items():
                    if pd.notna(category):
                        percentage = (count / len(df)) * 100
                        
                        # Calculate total amount for this category
                        category_amount = df[df['paid_by'] == category]['outstanding_tax'].sum() if 'outstanding_tax' in df.columns else 0
                        
                        st.info(f"""
                        **{category}**  
                        Properties: {count} ({percentage:.1f}%)  
                        Amount: {format_currency(category_amount)}
                        """)
            
            with col2:
                # Enhanced pie chart
                fig_pie = px.pie(
                    values=paid_by_counts.values,
                    names=paid_by_counts.index,
                    title="Distribution by Payment Responsibility",
                    color_discrete_map={
                        'Landlord': '#48bb78',
                        'Tenant': '#63b3ed',
                        'Tenant to Reimburse': '#f6ad55'
                    },
                    hole=0.4
                )
                fig_pie.update_traces(
                    textposition='inside',
                    textinfo='percent+label',
                    hovertemplate='<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>'
                )
                fig_pie.update_layout(
                    showlegend=True,
                    height=400,
                    font=dict(size=14)
                )
                st.plotly_chart(fig_pie, use_container_width=True)
        
        # Due Date Timeline Analysis
        st.divider()
        st.subheader("📅 Due Date Timeline")
        
        if 'tax_due_date_dt' in df.columns:
            valid_dates = df[df['tax_due_date_dt'].notna()]
            
            if not valid_dates.empty:
                # Calculate urgency categories
                now = datetime.now()
                overdue = valid_dates[valid_dates['tax_due_date_dt'] < now]
                due_7 = valid_dates[(valid_dates['tax_due_date_dt'] >= now) & 
                                   (valid_dates['tax_due_date_dt'] <= now + timedelta(days=7))]
                due_30 = valid_dates[(valid_dates['tax_due_date_dt'] > now + timedelta(days=7)) & 
                                    (valid_dates['tax_due_date_dt'] <= now + timedelta(days=30))]
                due_60 = valid_dates[(valid_dates['tax_due_date_dt'] > now + timedelta(days=30)) & 
                                    (valid_dates['tax_due_date_dt'] <= now + timedelta(days=60))]
                due_later = valid_dates[valid_dates['tax_due_date_dt'] > now + timedelta(days=60)]
                
                # Create urgency metrics
                col1, col2, col3, col4, col5 = st.columns(5)
                
                with col1:
                    st.metric("⚠️ Overdue", len(overdue), delta_color="inverse")
                
                with col2:
                    st.metric("🔴 Next 7 Days", len(due_7))
                
                with col3:
                    st.metric("🟡 8-30 Days", len(due_30))
                
                with col4:
                    st.metric("🟠 31-60 Days", len(due_60))
                
                with col5:
                    st.metric("🟢 60+ Days", len(due_later))
                
                # Timeline visualization
                col1, col2 = st.columns(2)
                
                with col1:
                    # Monthly distribution
                    timeline_data = valid_dates.copy()
                    timeline_data['month'] = timeline_data['tax_due_date_dt'].dt.to_period('M').astype(str)
                    monthly_counts = timeline_data.groupby('month').size().reset_index(name='count')
                    
                    fig_timeline = px.bar(
                        monthly_counts,
                        x='month',
                        y='count',
                        title="Tax Due Dates by Month",
                        color='count',
                        color_continuous_scale='Viridis',
                        labels={'month': 'Month', 'count': 'Number of Properties'}
                    )
                    fig_timeline.update_layout(
                        xaxis_tickangle=-45,
                        height=400,
                        showlegend=False
                    )
                    st.plotly_chart(fig_timeline, use_container_width=True)
                
                with col2:
                    # Urgency distribution gauge
                    total_with_dates = len(valid_dates)
                    urgency_data = {
                        'Overdue': len(overdue),
                        'Critical (≤7d)': len(due_7),
                        'Urgent (8-30d)': len(due_30),
                        'Normal (31-60d)': len(due_60),
                        'Future (>60d)': len(due_later)
                    }
                    
                    fig_urgency = px.funnel(
                        y=list(urgency_data.keys()),
                        x=list(urgency_data.values()),
                        title="Urgency Funnel",
                        color=list(urgency_data.values()),
                        color_continuous_scale='RdYlGn_r'
                    )
                    fig_urgency.update_layout(height=400)
                    st.plotly_chart(fig_urgency, use_container_width=True)
        
        # Geographic Distribution
        if 'state' in df.columns and 'jurisdiction' in df.columns:
            st.divider()
            st.subheader("🗺️ Geographic Distribution")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # State distribution
                state_data = df.groupby('state').agg({
                    df.columns[0]: 'count',
                    'outstanding_tax': 'sum' if 'outstanding_tax' in df.columns else lambda x: 0
                }).reset_index()
                state_data.columns = ['State', 'Count', 'Total Tax']
                
                fig_state = px.bar(
                    state_data,
                    x='State',
                    y='Count',
                    title='Properties by State',
                    text='Count',
                    color='Total Tax',
                    color_continuous_scale='Blues',
                    hover_data=['Total Tax']
                )
                fig_state.update_traces(texttemplate='%{text}', textposition='outside')
                fig_state.update_layout(height=400)
                st.plotly_chart(fig_state, use_container_width=True)
            
            with col2:
                # Top jurisdictions
                jurisdiction_data = df['jurisdiction'].value_counts().head(10).reset_index()
                jurisdiction_data.columns = ['Jurisdiction', 'Count']
                
                fig_jurisdiction = px.bar(
                    jurisdiction_data,
                    y='Jurisdiction',
                    x='Count',
                    title='Top 10 Jurisdictions',
                    orientation='h',
                    text='Count',
                    color='Count',
                    color_continuous_scale='Greens'
                )
                fig_jurisdiction.update_traces(texttemplate='%{text}', textposition='outside')
                fig_jurisdiction.update_layout(height=400)
                st.plotly_chart(fig_jurisdiction, use_container_width=True)

# Enhanced properties tab with advanced features
def render_properties_tab(df: pd.DataFrame):
    """Render enhanced properties tab with advanced data management."""
    st.header("🏢 Properties Management")
    
    if not df.empty:
        # View controls
        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
        
        with col1:
            st.info(f"📊 Showing {len(df)} properties based on current filters")
        
        with col2:
            view_mode = st.selectbox(
                "View Mode",
                ["Table", "Cards", "Compact"],
                help="Choose how to display properties"
            )
        
        with col3:
            sort_by = st.selectbox(
                "Sort By",
                ["Due Date", "Amount Due", "Property Name", "Jurisdiction"],
                help="Sort properties by selected field"
            )
        
        with col4:
            items_per_page = st.selectbox(
                "Items/Page",
                [10, 25, 50, 100],
                help="Number of items to display per page"
            )
        
        # Prepare display dataframe
        display_df = df.copy()
        
        # Add formatted columns
        if 'tax_due_date' in display_df.columns:
            display_df['tax_due_date_dt'] = pd.to_datetime(display_df['tax_due_date'], errors='coerce')
            display_df['due_date_formatted'] = display_df['tax_due_date_dt'].apply(
                lambda x: format_due_date(x) if pd.notna(x) else "-"
            )
        
        if 'paid_by' in display_df.columns:
            display_df['paid_by_formatted'] = display_df['paid_by'].apply(format_paid_by)
        
        if 'amount_due' in display_df.columns:
            display_df['amount_formatted'] = display_df['amount_due'].apply(format_currency)
        
        # Sort dataframe
        sort_mapping = {
            "Due Date": "tax_due_date_dt",
            "Amount Due": "amount_due",
            "Property Name": "property_name",
            "Jurisdiction": "jurisdiction"
        }
        
        sort_column = sort_mapping.get(sort_by)
        if sort_column and sort_column in display_df.columns:
            display_df = display_df.sort_values(sort_column, ascending=True)
        
        # Pagination
        total_pages = (len(display_df) - 1) // items_per_page + 1
        page = st.number_input(
            "Page",
            min_value=1,
            max_value=total_pages,
            value=1,
            step=1
        )
        
        start_idx = (page - 1) * items_per_page
        end_idx = min(start_idx + items_per_page, len(display_df))
        page_df = display_df.iloc[start_idx:end_idx]
        
        # Display based on view mode
        if view_mode == "Table":
            # Select columns to display
            display_cols = ['property_name', 'property_address', 'jurisdiction', 'state']
            
            if 'amount_formatted' in page_df.columns:
                display_cols.append('amount_formatted')
            if 'due_date_formatted' in page_df.columns:
                display_cols.append('due_date_formatted')
            if 'paid_by_formatted' in page_df.columns:
                display_cols.append('paid_by_formatted')
            if 'tax_bill_link' in page_df.columns:
                display_cols.append('tax_bill_link')
            
            # Rename columns for display
            rename_map = {
                'property_name': 'Property Name',
                'property_address': 'Address',
                'jurisdiction': 'Jurisdiction',
                'state': 'State',
                'amount_formatted': 'Tax Amount',
                'due_date_formatted': 'Due Date',
                'paid_by_formatted': 'Paid By',
                'tax_bill_link': 'Tax Bill URL'
            }
            
            table_df = page_df[display_cols].rename(columns=rename_map)
            
            # Display as HTML table with formatting
            st.write(table_df.to_html(escape=False, index=False), unsafe_allow_html=True)
            
        elif view_mode == "Cards":
            # Display as cards
            cols = st.columns(2)
            for idx, (_, row) in enumerate(page_df.iterrows()):
                with cols[idx % 2]:
                    with st.container():
                        st.markdown(f"""
                        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                    color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                            <h3 style="color: white; margin: 0;">{row.get('property_name', 'Unknown')}</h3>
                            <p style="color: rgba(255,255,255,0.9); margin: 5px 0;">{row.get('property_address', 'N/A')}</p>
                            <hr style="border-color: rgba(255,255,255,0.3);">
                            <p><strong>Jurisdiction:</strong> {row.get('jurisdiction', 'N/A')}</p>
                            <p><strong>State:</strong> {row.get('state', 'N/A')}</p>
                            <p><strong>Amount Due:</strong> {format_currency(row.get('amount_due', 0))}</p>
                            <p><strong>Due Date:</strong> {format_due_date(row.get('tax_due_date_dt'))}</p>
                            <p><strong>Paid By:</strong> {row.get('paid_by', 'N/A')}</p>
                        </div>
                        """, unsafe_allow_html=True)
        
        else:  # Compact view
            # Display as compact list
            for _, row in page_df.iterrows():
                col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                with col1:
                    st.write(f"**{row.get('property_name', 'Unknown')}**")
                    st.caption(row.get('property_address', 'N/A'))
                with col2:
                    st.write(row.get('jurisdiction', 'N/A'))
                with col3:
                    st.write(format_currency(row.get('amount_due', 0)))
                with col4:
                    if row.get('tax_bill_link'):
                        st.link_button("View", row['tax_bill_link'])
                st.divider()
        
        # Pagination controls
        st.divider()
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.write(f"Page {page} of {total_pages} • Items {start_idx + 1}-{end_idx} of {len(display_df)}")
        
        # Export section
        st.divider()
        st.subheader("📤 Export Data")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # CSV export
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Export as CSV",
                data=csv,
                file_name=f"properties_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col2:
            # Excel export with multiple sheets
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Main data sheet
                df.to_excel(writer, sheet_name='Properties', index=False)
                
                # Summary sheet
                summary_data = {
                    'Metric': [
                        'Total Properties',
                        'Total Outstanding Tax',
                        'Average Tax Amount',
                        'Properties with Due Dates',
                        'Overdue Properties'
                    ],
                    'Value': [
                        len(df),
                        df['outstanding_tax'].sum() if 'outstanding_tax' in df.columns else 0,
                        df['outstanding_tax'].mean() if 'outstanding_tax' in df.columns else 0,
                        df['tax_due_date'].notna().sum() if 'tax_due_date' in df.columns else 0,
                        len(df[df['tax_due_date_dt'] < datetime.now()]) if 'tax_due_date_dt' in df.columns else 0
                    ]
                }
                pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)
                
                # Statistics by jurisdiction
                if 'jurisdiction' in df.columns:
                    jurisdiction_stats = df.groupby('jurisdiction').agg({
                        df.columns[0]: 'count',
                        'outstanding_tax': 'sum' if 'outstanding_tax' in df.columns else lambda x: 0
                    }).reset_index()
                    jurisdiction_stats.columns = ['Jurisdiction', 'Count', 'Total Tax']
                    jurisdiction_stats.to_excel(writer, sheet_name='By Jurisdiction', index=False)
            
            excel_data = output.getvalue()
            st.download_button(
                label="📊 Export as Excel",
                data=excel_data,
                file_name=f"properties_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        
        with col3:
            # JSON export
            json_data = df.to_json(orient='records', date_format='iso', indent=2)
            st.download_button(
                label="📋 Export as JSON",
                data=json_data,
                file_name=f"properties_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True
            )
        
        with col4:
            # Custom filtered export
            if st.button("🎯 Custom Export", use_container_width=True):
                st.info("Custom export with selected columns - Feature coming soon!")
    
    else:
        st.info("No properties found matching the current filters")

# Enhanced entities tab
def render_entities_tab(entities: List[Dict], df: pd.DataFrame):
    """Render enhanced entities tab with relationship visualization."""
    st.header("👥 Entity Management")
    
    if entities:
        entities_df = pd.DataFrame(entities)
        
        # Categorize entities
        parent_entities = []
        sub_entities = []
        single_property_entities = []
        
        for entity in entities:
            entity_type = entity.get('entity_type', '').lower()
            if entity_type == 'parent entity':
                parent_entities.append(entity)
            elif entity_type == 'sub-entity':
                sub_entities.append(entity)
            elif entity_type == 'single-property entity':
                single_property_entities.append(entity)
            else:
                # Fallback logic
                if entity.get('parent_entity_id'):
                    sub_entities.append(entity)
                elif entity.get('property_count', 0) == 1:
                    single_property_entities.append(entity)
                else:
                    parent_entities.append(entity)
        
        # Display entity metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Entities", len(entities), help="All entities in the system")
        
        with col2:
            st.metric("Parent Entities", len(parent_entities), help="Top-level entity groups")
        
        with col3:
            st.metric("Sub-Entities", len(sub_entities), help="Child entities under parents")
        
        with col4:
            st.metric("Single-Property", len(single_property_entities), help="Entities with one property")
        
        # Entity visualization tabs
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "🌳 Hierarchy", "📈 Analytics", "⚙️ Management"])
        
        with tab1:
            # Entity type distribution
            st.subheader("🏢 Entity Distribution")
            
            col1, col2 = st.columns(2)
            
            with col1:
                entity_types = {
                    'Parent Entities': len(parent_entities),
                    'Sub-Entities': len(sub_entities),
                    'Single-Property': len(single_property_entities)
                }
                
                fig_dist = px.pie(
                    values=list(entity_types.values()),
                    names=list(entity_types.keys()),
                    title="Entity Classification",
                    color_discrete_map={
                        'Parent Entities': '#2E86AB',
                        'Sub-Entities': '#A23B72',
                        'Single-Property': '#F18F01'
                    },
                    hole=0.4
                )
                fig_dist.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig_dist, use_container_width=True)
            
            with col2:
                # Entity property distribution
                if 'entity_id' in df.columns:
                    entity_property_counts = df['entity_id'].value_counts().head(10)
                    
                    fig_props = px.bar(
                        x=entity_property_counts.values,
                        y=[next((e['entity_name'] for e in entities if e['entity_id'] == eid), eid) 
                           for eid in entity_property_counts.index],
                        orientation='h',
                        title="Top 10 Entities by Property Count",
                        labels={'x': 'Number of Properties', 'y': 'Entity'},
                        color=entity_property_counts.values,
                        color_continuous_scale='Viridis'
                    )
                    st.plotly_chart(fig_props, use_container_width=True)
        
        with tab2:
            # Interactive hierarchy visualization
            st.subheader("🌳 Entity Hierarchy Visualization")
            
            if parent_entities and sub_entities:
                # Create interactive network graph
                import plotly.graph_objects as go
                
                # Build the hierarchy tree
                fig_tree = go.Figure()
                
                # Add parent nodes
                parent_x = []
                parent_y = []
                parent_text = []
                parent_hover = []
                
                for i, parent in enumerate(parent_entities):
                    x = i * 3
                    y = 2
                    parent_x.append(x)
                    parent_y.append(y)
                    parent_text.append(parent.get('entity_name', 'Unknown'))
                    parent_hover.append(
                        f"Name: {parent.get('entity_name')}<br>"
                        f"Properties: {parent.get('property_count', 0)}<br>"
                        f"Tax Due: ${parent.get('amount_due', 0):,.2f}"
                    )
                
                # Add parent nodes to figure
                fig_tree.add_trace(go.Scatter(
                    x=parent_x,
                    y=parent_y,
                    mode='markers+text',
                    name='Parent Entities',
                    text=parent_text,
                    textposition="top center",
                    marker=dict(
                        symbol='square',
                        size=20,
                        color='#2E86AB',
                        line=dict(color='white', width=2)
                    ),
                    hovertext=parent_hover,
                    hoverinfo='text'
                ))
                
                # Add sub-entity nodes and connections
                edge_x = []
                edge_y = []
                sub_x = []
                sub_y = []
                sub_text = []
                sub_hover = []
                
                for parent_idx, parent in enumerate(parent_entities):
                    parent_id = parent.get('entity_id')
                    related_subs = [e for e in sub_entities if e.get('parent_entity_id') == parent_id]
                    
                    for sub_idx, sub in enumerate(related_subs):
                        # Position sub-entities
                        sub_x_pos = parent_x[parent_idx] + (sub_idx - len(related_subs)/2) * 0.8
                        sub_y_pos = 0
                        
                        sub_x.append(sub_x_pos)
                        sub_y.append(sub_y_pos)
                        sub_text.append(sub.get('entity_name', 'Unknown')[:20])
                        sub_hover.append(
                            f"Name: {sub.get('entity_name')}<br>"
                            f"Parent: {parent.get('entity_name')}<br>"
                            f"Properties: {sub.get('property_count', 0)}<br>"
                            f"Tax Due: ${sub.get('amount_due', 0):,.2f}"
                        )
                        
                        # Add edge
                        edge_x.extend([parent_x[parent_idx], sub_x_pos, None])
                        edge_y.extend([parent_y[parent_idx], sub_y_pos, None])
                
                # Add edges
                fig_tree.add_trace(go.Scatter(
                    x=edge_x,
                    y=edge_y,
                    mode='lines',
                    name='Relationships',
                    line=dict(color='#888', width=1),
                    hoverinfo='none'
                ))
                
                # Add sub-entity nodes
                fig_tree.add_trace(go.Scatter(
                    x=sub_x,
                    y=sub_y,
                    mode='markers+text',
                    name='Sub-Entities',
                    text=sub_text,
                    textposition="bottom center",
                    marker=dict(
                        symbol='circle',
                        size=15,
                        color='#A23B72',
                        line=dict(color='white', width=2)
                    ),
                    hovertext=sub_hover,
                    hoverinfo='text'
                ))
                
                fig_tree.update_layout(
                    title="Interactive Entity Hierarchy",
                    showlegend=True,
                    hovermode='closest',
                    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    height=500,
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)'
                )
                
                st.plotly_chart(fig_tree, use_container_width=True)
            else:
                st.info("Entity hierarchy relationships not configured")
        
        with tab3:
            # Entity analytics
            st.subheader("📈 Entity Performance Analytics")
            
            if not df.empty and 'entity_id' in df.columns:
                # Calculate entity metrics
                entity_metrics = []
                
                for entity in entities:
                    entity_id = entity.get('entity_id')
                    entity_props = df[df['entity_id'] == entity_id]
                    
                    if not entity_props.empty:
                        metrics = {
                            'Entity': entity.get('entity_name', 'Unknown'),
                            'Type': entity.get('entity_type', 'Unknown'),
                            'Properties': len(entity_props),
                            'Total Tax': entity_props['outstanding_tax'].sum() if 'outstanding_tax' in entity_props.columns else 0,
                            'Avg Tax': entity_props['outstanding_tax'].mean() if 'outstanding_tax' in entity_props.columns else 0,
                            'Overdue': len(entity_props[entity_props['tax_due_date_dt'] < datetime.now()]) if 'tax_due_date_dt' in entity_props.columns else 0
                        }
                        entity_metrics.append(metrics)
                
                if entity_metrics:
                    metrics_df = pd.DataFrame(entity_metrics)
                    
                    # Top entities by tax liability
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        top_tax = metrics_df.nlargest(10, 'Total Tax')
                        fig_tax = px.bar(
                            top_tax,
                            x='Total Tax',
                            y='Entity',
                            orientation='h',
                            title="Top 10 Entities by Tax Liability",
                            color='Total Tax',
                            color_continuous_scale='Reds'
                        )
                        fig_tax.update_layout(height=400)
                        st.plotly_chart(fig_tax, use_container_width=True)
                    
                    with col2:
                        # Entities with most overdue properties
                        top_overdue = metrics_df.nlargest(10, 'Overdue')
                        fig_overdue = px.bar(
                            top_overdue,
                            x='Overdue',
                            y='Entity',
                            orientation='h',
                            title="Entities with Most Overdue Properties",
                            color='Overdue',
                            color_continuous_scale='YlOrRd'
                        )
                        fig_overdue.update_layout(height=400)
                        st.plotly_chart(fig_overdue, use_container_width=True)
                    
                    # Detailed metrics table
                    st.subheader("📊 Detailed Entity Metrics")
                    st.dataframe(
                        metrics_df.sort_values('Total Tax', ascending=False),
                        use_container_width=True,
                        hide_index=True
                    )
        
        with tab4:
            # Entity management
            st.subheader("⚙️ Entity Management")
            
            # Search and filter
            col1, col2 = st.columns(2)
            
            with col1:
                search_term = st.text_input("🔍 Search entities", placeholder="Enter entity name...")
            
            with col2:
                filter_type = st.selectbox(
                    "Filter by type",
                    ["All", "Parent Entity", "Sub-Entity", "Single-Property Entity"]
                )
            
            # Filter entities
            filtered_entities = entities_df.copy()
            
            if search_term:
                filtered_entities = filtered_entities[
                    filtered_entities['entity_name'].str.contains(search_term, case=False, na=False)
                ]
            
            if filter_type != "All":
                filtered_entities = filtered_entities[
                    filtered_entities['entity_type'] == filter_type
                ]
            
            # Display filtered entities
            if not filtered_entities.empty:
                st.write(f"Found {len(filtered_entities)} entities")
                
                # Display as expandable cards
                for _, entity in filtered_entities.iterrows():
                    with st.expander(f"📁 {entity.get('entity_name', 'Unknown')}"):
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.write("**Basic Information**")
                            st.write(f"ID: `{entity.get('entity_id', 'N/A')}`")
                            st.write(f"Type: {entity.get('entity_type', 'N/A')}")
                            st.write(f"Properties: {entity.get('property_count', 0)}")
                        
                        with col2:
                            st.write("**Financial**")
                            st.write(f"Tax Due: ${entity.get('amount_due', 0):,.2f}")
                            st.write(f"Created: {entity.get('created_at', 'N/A')}")
                        
                        with col3:
                            st.write("**Actions**")
                            if st.button("Edit", key=f"edit_{entity.get('entity_id')}"):
                                st.info("Edit functionality coming soon")
                            if st.button("View Properties", key=f"view_{entity.get('entity_id')}"):
                                st.info("Property view coming soon")
            else:
                st.info("No entities found matching the criteria")
    else:
        st.info("No entities found in the system")

# Enhanced analytics tab
def render_analytics_tab(df: pd.DataFrame, entities: List[Dict]):
    """Render advanced analytics tab with interactive visualizations."""
    st.header("📈 Advanced Analytics & Insights")
    
    if not df.empty:
        # Create sub-tabs for different analytics
        analytics_tab1, analytics_tab2, analytics_tab3, analytics_tab4 = st.tabs([
            "📊 Trends", "🎯 Predictions", "⚡ Performance", "📉 Risk Analysis"
        ])
        
        with analytics_tab1:
            # Trend Analysis
            st.subheader("📈 Tax Liability Trends")
            
            if 'tax_due_date_dt' in df.columns and 'outstanding_tax' in df.columns:
                # Monthly trend analysis
                trend_df = df[df['tax_due_date_dt'].notna()].copy()
                trend_df['month'] = trend_df['tax_due_date_dt'].dt.to_period('M').astype(str)
                
                monthly_trend = trend_df.groupby('month').agg({
                    'outstanding_tax': 'sum',
                    'property_id': 'count'
                }).reset_index()
                monthly_trend.columns = ['Month', 'Total Tax', 'Property Count']
                
                # Create dual-axis chart
                fig_trend = make_subplots(
                    rows=1, cols=1,
                    specs=[[{"secondary_y": True}]]
                )
                
                fig_trend.add_trace(
                    go.Bar(
                        x=monthly_trend['Month'],
                        y=monthly_trend['Total Tax'],
                        name='Total Tax',
                        marker_color='lightblue'
                    ),
                    secondary_y=False,
                )
                
                fig_trend.add_trace(
                    go.Scatter(
                        x=monthly_trend['Month'],
                        y=monthly_trend['Property Count'],
                        name='Property Count',
                        line=dict(color='red', width=3),
                        mode='lines+markers'
                    ),
                    secondary_y=True,
                )
                
                fig_trend.update_xaxes(title_text="Month")
                fig_trend.update_yaxes(title_text="Total Tax ($)", secondary_y=False)
                fig_trend.update_yaxes(title_text="Property Count", secondary_y=True)
                fig_trend.update_layout(
                    title="Monthly Tax Liability Trend",
                    hovermode='x unified',
                    height=500
                )
                
                st.plotly_chart(fig_trend, use_container_width=True)
            
            # Comparative Analysis
            col1, col2 = st.columns(2)
            
            with col1:
                if 'state' in df.columns and 'outstanding_tax' in df.columns:
                    state_comparison = df.groupby('state')['outstanding_tax'].agg(['mean', 'sum', 'count']).reset_index()
                    state_comparison.columns = ['State', 'Avg Tax', 'Total Tax', 'Count']
                    
                    fig_state_comp = px.scatter(
                        state_comparison,
                        x='Count',
                        y='Avg Tax',
                        size='Total Tax',
                        color='State',
                        title="State Comparison: Properties vs Average Tax",
                        hover_data=['Total Tax'],
                        size_max=50
                    )
                    st.plotly_chart(fig_state_comp, use_container_width=True)
            
            with col2:
                if 'paid_by' in df.columns and 'outstanding_tax' in df.columns:
                    paid_by_analysis = df.groupby('paid_by')['outstanding_tax'].agg(['mean', 'sum', 'count']).reset_index()
                    paid_by_analysis.columns = ['Paid By', 'Avg Tax', 'Total Tax', 'Count']
                    
                    fig_paid_by = px.sunburst(
                        paid_by_analysis,
                        path=['Paid By'],
                        values='Total Tax',
                        title="Tax Distribution by Payment Responsibility",
                        color='Avg Tax',
                        color_continuous_scale='RdYlGn_r'
                    )
                    st.plotly_chart(fig_paid_by, use_container_width=True)
        
        with analytics_tab2:
            # Predictive Analytics
            st.subheader("🎯 Predictive Insights")
            
            # Forecast upcoming tax liabilities
            if 'tax_due_date_dt' in df.columns and 'outstanding_tax' in df.columns:
                future_df = df[df['tax_due_date_dt'] > datetime.now()].copy()
                
                if not future_df.empty:
                    # Group by future months
                    future_df['month'] = future_df['tax_due_date_dt'].dt.to_period('M').astype(str)
                    future_forecast = future_df.groupby('month')['outstanding_tax'].sum().reset_index()
                    future_forecast.columns = ['Month', 'Projected Tax']
                    
                    # Add cumulative sum
                    future_forecast['Cumulative'] = future_forecast['Projected Tax'].cumsum()
                    
                    # Create forecast chart
                    fig_forecast = go.Figure()
                    
                    fig_forecast.add_trace(go.Bar(
                        x=future_forecast['Month'],
                        y=future_forecast['Projected Tax'],
                        name='Monthly Tax',
                        marker_color='lightgreen'
                    ))
                    
                    fig_forecast.add_trace(go.Scatter(
                        x=future_forecast['Month'],
                        y=future_forecast['Cumulative'],
                        name='Cumulative',
                        line=dict(color='darkgreen', width=3),
                        mode='lines+markers'
                    ))
                    
                    fig_forecast.update_layout(
                        title="Projected Tax Liabilities (Next 12 Months)",
                        xaxis_title="Month",
                        yaxis_title="Amount ($)",
                        hovermode='x unified',
                        height=400
                    )
                    
                    st.plotly_chart(fig_forecast, use_container_width=True)
                    
                    # Key predictions
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        next_month_tax = future_forecast.iloc[0]['Projected Tax'] if len(future_forecast) > 0 else 0
                        st.metric("Next Month Tax", format_currency(next_month_tax))
                    
                    with col2:
                        next_quarter_tax = future_forecast.iloc[:3]['Projected Tax'].sum() if len(future_forecast) >= 3 else future_forecast['Projected Tax'].sum()
                        st.metric("Next Quarter Tax", format_currency(next_quarter_tax))
                    
                    with col3:
                        total_future_tax = future_forecast['Projected Tax'].sum()
                        st.metric("Total Future Liability", format_currency(total_future_tax))
        
        with analytics_tab3:
            # Performance Metrics
            st.subheader("⚡ System Performance Metrics")
            
            # Create performance dashboard
            col1, col2 = st.columns(2)
            
            with col1:
                # Data quality metrics
                st.write("**Data Quality Indicators**")
                
                total_properties = len(df)
                props_with_dates = df['tax_due_date'].notna().sum() if 'tax_due_date' in df.columns else 0
                props_with_amounts = df['amount_due'].notna().sum() if 'amount_due' in df.columns else 0
                props_with_links = df['tax_bill_link'].notna().sum() if 'tax_bill_link' in df.columns else 0
                
                quality_metrics = {
                    'Has Due Dates': (props_with_dates / total_properties * 100) if total_properties > 0 else 0,
                    'Has Amounts': (props_with_amounts / total_properties * 100) if total_properties > 0 else 0,
                    'Has Tax Links': (props_with_links / total_properties * 100) if total_properties > 0 else 0
                }
                
                fig_quality = go.Figure(go.Bar(
                    x=list(quality_metrics.values()),
                    y=list(quality_metrics.keys()),
                    orientation='h',
                    marker=dict(
                        color=list(quality_metrics.values()),
                        colorscale='RdYlGn',
                        cmin=0,
                        cmax=100
                    ),
                    text=[f"{v:.1f}%" for v in quality_metrics.values()],
                    textposition='outside'
                ))
                
                fig_quality.update_layout(
                    title="Data Completeness",
                    xaxis_title="Percentage (%)",
                    xaxis=dict(range=[0, 100]),
                    height=300
                )
                
                st.plotly_chart(fig_quality, use_container_width=True)
            
            with col2:
                # Extraction success metrics
                st.write("**Extraction Performance**")
                
                # Simulated metrics (would come from actual extraction data)
                extraction_metrics = {
                    'Successful': 85,
                    'Failed': 10,
                    'Pending': 5
                }
                
                fig_extraction = px.pie(
                    values=list(extraction_metrics.values()),
                    names=list(extraction_metrics.keys()),
                    title="Extraction Status Distribution",
                    color_discrete_map={
                        'Successful': '#48bb78',
                        'Failed': '#fc8181',
                        'Pending': '#f6ad55'
                    },
                    hole=0.4
                )
                
                fig_extraction.update_layout(height=300)
                st.plotly_chart(fig_extraction, use_container_width=True)
        
        with analytics_tab4:
            # Risk Analysis
            st.subheader("📉 Risk Analysis & Alerts")
            
            # Identify high-risk properties
            risk_properties = []
            
            if 'tax_due_date_dt' in df.columns and 'outstanding_tax' in df.columns:
                for _, row in df.iterrows():
                    risk_score = 0
                    risk_factors = []
                    
                    # Check if overdue
                    if pd.notna(row.get('tax_due_date_dt')):
                        days_overdue = (datetime.now() - row['tax_due_date_dt']).days
                        if days_overdue > 0:
                            risk_score += min(days_overdue / 30, 3)  # Max 3 points for overdue
                            risk_factors.append(f"Overdue by {days_overdue} days")
                    
                    # Check high amount
                    if pd.notna(row.get('outstanding_tax')):
                        if row['outstanding_tax'] > 10000:
                            risk_score += 2
                            risk_factors.append(f"High amount: ${row['outstanding_tax']:,.2f}")
                    
                    # Add to risk list if score > 0
                    if risk_score > 0:
                        risk_properties.append({
                            'Property': row.get('property_name', 'Unknown'),
                            'Risk Score': risk_score,
                            'Risk Factors': ', '.join(risk_factors),
                            'Amount': row.get('outstanding_tax', 0),
                            'Due Date': row.get('tax_due_date')
                        })
                
                if risk_properties:
                    # Sort by risk score
                    risk_df = pd.DataFrame(risk_properties).sort_values('Risk Score', ascending=False).head(10)
                    
                    # Display high-risk properties
                    st.warning(f"⚠️ Found {len(risk_properties)} high-risk properties")
                    
                    # Risk heatmap
                    fig_risk = px.treemap(
                        risk_df,
                        path=['Property'],
                        values='Risk Score',
                        color='Amount',
                        title="Risk Heatmap: Top 10 Properties",
                        color_continuous_scale='Reds'
                    )
                    fig_risk.update_layout(height=500)
                    st.plotly_chart(fig_risk, use_container_width=True)
                    
                    # Risk details table
                    st.subheader("📋 Risk Details")
                    st.dataframe(
                        risk_df,
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.success("✅ No high-risk properties identified")
    else:
        st.info("No data available for analytics")

# Main application
def main():
    """Main application entry point."""
    # Initialize
    init_session_state()
    
    # Render header
    render_header()
    
    # Render sidebar and get filters
    filters = render_sidebar()
    
    # Store filters in session state
    st.session_state.filter_state = filters
    
    # Load data with progress indicator
    with st.spinner("Loading data..."):
        properties = fetch_properties()
        stats = fetch_statistics()
        entities = fetch_entities()
    
    # Process data
    if properties:
        df = pd.DataFrame(properties)
        
        # Add datetime columns
        if 'tax_due_date' in df.columns:
            df['tax_due_date_dt'] = pd.to_datetime(df['tax_due_date'], errors='coerce')
        
        # Apply filters
        df = apply_filters(df, filters)
    else:
        df = pd.DataFrame()
    
    # Main content tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Overview",
        "🏢 Properties",
        "👥 Entities",
        "📈 Analytics",
        "🔄 Extraction"
    ])
    
    with tab1:
        render_overview_tab(df, stats, entities)
    
    with tab2:
        render_properties_tab(df)
    
    with tab3:
        render_entities_tab(entities, df)
    
    with tab4:
        render_analytics_tab(df, entities)
    
    with tab5:
        st.header("🔄 Tax Extraction Service")
        st.info("Tax extraction interface - Integration with existing extraction tab")
        # This would integrate with the existing extraction functionality
    
    # Footer
    st.divider()
    footer_col1, footer_col2, footer_col3 = st.columns(3)
    
    with footer_col1:
        st.caption(f"🕐 Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    with footer_col2:
        if not df.empty:
            st.caption(f"📊 Showing {len(df)} of {stats.get('total_properties', 0)} properties")
    
    with footer_col3:
        st.caption(f"🌐 API: {API_URL}")
    
    # Auto-refresh logic
    if st.session_state.user_preferences.get('auto_refresh'):
        time_since_refresh = (datetime.now() - st.session_state.last_refresh).seconds
        if time_since_refresh > st.session_state.user_preferences.get('refresh_interval', 300):
            st.cache_data.clear()
            st.session_state.last_refresh = datetime.now()
            st.rerun()

if __name__ == "__main__":
    main()