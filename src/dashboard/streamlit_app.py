"""
Streamlit Dashboard for Tax Extraction System.
Enhanced version with improved UI/UX, filtering, and visualizations.
Rebuild trigger: 2024-08-31-v2 - Using correct Supabase versions
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import os
from datetime import datetime, timedelta, date
import json
from io import BytesIO
import time
import asyncio
from typing import Optional, List, Dict, Any, Tuple
import hashlib
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import numpy as np

st.set_page_config(
    page_title="Tax Dashboard Pro",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': 'Enhanced Property Tax Dashboard v2.0 - Powered by Advanced Analytics'
    }
)

# Enhanced Custom CSS for better styling with dark mode support
st.markdown("""
<style>
    /* Hide Streamlit branding and menu items */
    #MainMenu {visibility: hidden;}
    .stDeployButton {display: none;}
    footer {visibility: hidden;}
    /* Hide the viewer badge */
    ._profileContainer {display: none;}
    /* Hide the header but keep the space */
    header[data-testid="stHeader"] {height: 0px;}
    /* Hide the toolbar */
    .stToolbar {display: none;}
    /* Hide made with Streamlit footer */
    .viewerBadge_container__1QSob {display: none;}
    .stMetric {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .paid-by-landlord {
        background-color: #d4edda;
        color: #155724;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 500;
    }
    .paid-by-tenant {
        background-color: #d1ecf1;
        color: #0c5460;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 500;
    }
    .paid-by-reimburse {
        background-color: #fff3cd;
        color: #856404;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 500;
    }
    .due-soon {
        background-color: #f8d7da;
        color: #721c24;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 500;
    }
    .due-later {
        background-color: #e8f5e9;
        color: #2e7d32;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 500;
    }
    div[data-testid="stSidebarNav"] {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 10px;
    }
    /* Enhanced UI Elements */
    .bulk-action-checkbox {
        margin-right: 10px;
    }
    .status-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
        margin-left: 5px;
    }
    .status-badge-new {
        background-color: #ffd700;
        color: #333;
    }
    .activity-feed {
        max-height: 400px;
        overflow-y: auto;
        padding: 10px;
        background-color: #f9f9f9;
        border-radius: 8px;
    }
    .activity-item {
        padding: 8px;
        margin-bottom: 8px;
        background-color: white;
        border-radius: 4px;
        border-left: 3px solid #1f77b4;
    }
    .loading-skeleton {
        background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
        background-size: 200% 100%;
        animation: loading 1.5s ease-in-out infinite;
    }
    @keyframes loading {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
    }
    /* Dark mode styles */
    .dark-mode {
        background-color: #1a1a1a;
        color: #ffffff;
    }
    .dark-mode .stMetric {
        background-color: #2a2a2a;
    }
    .dark-mode .activity-feed {
        background-color: #2a2a2a;
    }
    .dark-mode .activity-item {
        background-color: #333;
    }
</style>
""", unsafe_allow_html=True)

# Get API URL from secrets or environment
try:
    API_URL = st.secrets["API_URL"]
except:
    API_URL = "https://tax-extraction-system-production.up.railway.app"

# Enhanced session state initialization
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = datetime.now()
if 'properties_data' not in st.session_state:
    st.session_state.properties_data = None
if 'stats_data' not in st.session_state:
    st.session_state.stats_data = None
if 'selected_properties' not in st.session_state:
    st.session_state.selected_properties = set()
if 'bulk_edit_mode' not in st.session_state:
    st.session_state.bulk_edit_mode = False
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = False
if 'refresh_interval' not in st.session_state:
    st.session_state.refresh_interval = 30
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = False
if 'filter_presets' not in st.session_state:
    st.session_state.filter_presets = {}
if 'activity_log' not in st.session_state:
    st.session_state.activity_log = []
if 'extraction_progress' not in st.session_state:
    st.session_state.extraction_progress = {}
if 'cache_data' not in st.session_state:
    st.session_state.cache_data = {}
if 'last_webhook_check' not in st.session_state:
    st.session_state.last_webhook_check = datetime.now()
if 'notifications' not in st.session_state:
    st.session_state.notifications = []

# Enhanced cache data fetching functions with advanced filtering
@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_properties(
    filters: Optional[Dict[str, Any]] = None,
    cursor: Optional[str] = None,
    limit: int = 100,
    offset: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], Optional[str], Dict[str, Any]]:
    """Fetch a single page of properties with optional filters and cursor.

    Returns (properties, next_cursor, meta) where meta may include count/limit/total_count.
    """
    try:
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if offset is not None:
            params["offset"] = offset
        if filters:
            # Add advanced filters
            if filters.get('jurisdiction'):
                params['jurisdiction'] = filters['jurisdiction']
            if filters.get('state'):
                params['state'] = filters['state']
            if filters.get('entity_id'):
                params['entity_id'] = filters['entity_id']
            if filters.get('amount_due_min') is not None:
                params['amount_due_min'] = filters['amount_due_min']
            if filters.get('amount_due_max') is not None:
                params['amount_due_max'] = filters['amount_due_max']
            if filters.get('due_date_before'):
                params['due_date_before'] = filters['due_date_before']
            if filters.get('due_date_after'):
                params['due_date_after'] = filters['due_date_after']
            if filters.get('needs_extraction') is not None:
                params['needs_extraction'] = filters['needs_extraction']
            if filters.get('sort_by'):
                params['sort_by'] = filters['sort_by']
            if filters.get('sort_order'):
                params['sort_order'] = filters['sort_order']
        
        # Increase timeout to accommodate slower API responses on large queries
        # Use separate connect/read timeouts: (connect_timeout, read_timeout)
        response = requests.get(
            f"{API_URL}/api/v1/properties",
            params=params,
            timeout=(5, 45)
        )
        if response.status_code == 200:
            data = response.json()
            meta = {k: data.get(k) for k in ("count", "limit", "total_count", "offset", "cursor") if k in data}
            return data.get("properties", []), data.get("next_cursor"), meta
    except Exception as e:
        st.error(f"Error fetching properties: {e}")
    return [], None, {}

@st.cache_data(ttl=300)
def fetch_all_properties(
    filters: Optional[Dict[str, Any]] = None,
    page_limit: int = 500,
    max_pages: int = 50
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Fetch all properties by following cursor pagination.

    Returns (all_properties, meta) where meta includes pages and last_cursor.
    """
    all_props: List[Dict[str, Any]] = []
    pages = 0
    offset = 0
    last_meta: Dict[str, Any] = {}
    while pages < max_pages:
        props, _, meta = fetch_properties(filters=filters, limit=page_limit, offset=offset)
        all_props.extend(props)
        last_meta = meta or {}
        pages += 1
        if not props or len(props) < page_limit:
            break
        offset += page_limit
    last_meta.update({"pages": pages, "last_offset": offset})
    return all_props, last_meta

@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_statistics():
    """Fetch statistics from API with caching."""
    try:
        response = requests.get(f"{API_URL}/api/v1/statistics", timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"Error fetching statistics: {e}")
    return {}

@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_entities(search: Optional[str] = None, limit: int = 100):
    """Fetch entities data from API with search capability."""
    try:
        params = {"limit": limit}
        if search:
            params["search"] = search
        response = requests.get(f"{API_URL}/api/v1/entities", params=params, timeout=10)
        if response.status_code == 200:
            return response.json().get("entities", [])
    except Exception as e:
        st.error(f"Error fetching entities: {e}")
    return []

def check_api_health():
    """Check API health status."""
    try:
        # Allow more time on cold starts and cross-cloud latency
        response = requests.get(f"{API_URL}/health", timeout=12)
        data = response.json()
        return response.status_code, data
    except Exception:
        return None, None

def trigger_extraction(property_data):
    """Trigger extraction for a single property."""
    try:
        payload = {
            "property_id": property_data.get("property_id", ""),
            "jurisdiction": property_data.get("jurisdiction", ""),
            "tax_bill_link": property_data.get("tax_bill_link", ""),
            "account_number": property_data.get("acct_number"),
            "property_name": property_data.get("property_name", "")
        }
        response = requests.post(
            f"{API_URL}/api/v1/extract",
            json=payload,
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
        else:
            return {"success": False, "error_message": f"API returned {response.status_code}"}
    except Exception as e:
        return {"success": False, "error_message": str(e)}

def trigger_batch_extraction(property_ids):
    """Trigger batch extraction for multiple properties."""
    try:
        payload = {"property_ids": property_ids}
        response = requests.post(
            f"{API_URL}/api/v1/extract/batch",
            json=payload,
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
        else:
            return {"status": "failed", "message": f"API returned {response.status_code}"}
    except Exception as e:
        return {"status": "failed", "message": str(e)}

def get_supported_jurisdictions():
    """Get list of supported jurisdictions from API."""
    try:
        response = requests.get(f"{API_URL}/api/v1/jurisdictions", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("jurisdictions", {})
        return {}
    except Exception:
        return {}

# New enhanced functions for advanced features
@st.cache_data(ttl=60)  # Cache for 1 minute
def fetch_extraction_trends(days: int = 30, jurisdiction: Optional[str] = None):
    """Fetch extraction trends from API."""
    try:
        params = {"days": days}
        if jurisdiction:
            params["jurisdiction"] = jurisdiction
        response = requests.get(f"{API_URL}/api/v1/analytics/trends", params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"Error fetching trends: {e}")
    return {}

@st.cache_data(ttl=60)
def fetch_property_history(property_id: str, limit: int = 10):
    """Fetch extraction history for a specific property."""
    try:
        response = requests.get(
            f"{API_URL}/api/v1/properties/{property_id}/history",
            params={"limit": limit},
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"Error fetching property history: {e}")
    return {}

def bulk_update_properties(updates: List[Dict[str, Any]]):
    """Perform bulk update of properties."""
    try:
        response = requests.put(
            f"{API_URL}/api/v1/properties/bulk",
            json={"updates": updates, "validate": True},
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
        else:
            return {"success": False, "message": f"API returned {response.status_code}"}
    except Exception as e:
        return {"success": False, "message": str(e)}

def create_entity_api(entity: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new entity via API."""
    try:
        response = requests.post(
            f"{API_URL}/api/v1/entities",
            json=entity,
            timeout=20
        )
        if response.status_code in (200, 201):
            return response.json()
        return {"error": f"API returned {response.status_code}", "details": response.text}
    except Exception as e:
        return {"error": str(e)}

def create_property_api(prop: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new property via API."""
    try:
        response = requests.post(
            f"{API_URL}/api/v1/properties",
            json=prop,
            timeout=20
        )
        if response.status_code in (200, 201):
            return response.json()
        return {"error": f"API returned {response.status_code}", "details": response.text}
    except Exception as e:
        return {"error": str(e)}

def clear_api_cache(pattern: Optional[str] = None):
    """Clear API cache."""
    try:
        params = {}
        if pattern:
            params["pattern"] = pattern
        response = requests.delete(
            f"{API_URL}/api/v1/cache/clear",
            params=params,
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        return {"success": False, "message": str(e)}

def register_webhook(webhook_url: str, events: List[str]):
    """Register webhook for notifications."""
    try:
        response = requests.post(
            f"{API_URL}/api/v1/webhooks/register",
            json={"webhook_url": webhook_url, "events": events},
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        return {"success": False, "message": str(e)}

# Helper functions for enhanced UI
def add_activity_log(message: str, type: str = "info"):
    """Add entry to activity log."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "message": message,
        "type": type
    }
    st.session_state.activity_log.insert(0, entry)
    # Keep only last 100 entries
    st.session_state.activity_log = st.session_state.activity_log[:100]

def format_amount_with_color(amount: float) -> str:
    """Format amount with color based on value."""
    if amount is None or amount == 0:
        return "-"
    color = "red" if amount > 10000 else "orange" if amount > 5000 else "green"
    return f'<span style="color: {color}; font-weight: bold;">${amount:,.2f}</span>'

def create_loading_skeleton(rows: int = 5, cols: int = 5):
    """Create loading skeleton for better UX."""
    skeleton_data = pd.DataFrame(
        np.full((rows, cols), "Loading..."),
        columns=[f"Col{i}" for i in range(cols)]
    )
    return skeleton_data

def format_paid_by(value: Any) -> str:
    """HTML version for paid_by badges (for card-style views)."""
    if pd.isna(value) or value == "":
        return "-"
    value_str = str(value)
    lower = value_str.lower()
    if "landlord" in lower:
        return f'<span class="paid-by-landlord">{value_str}</span>'
    if "reimburse" in lower:
        return f'<span class="paid-by-reimburse">{value_str}</span>'
    if "tenant" in lower:
        return f'<span class="paid-by-tenant">{value_str}</span>'
    return value_str

def format_paid_by_plain(value: Any) -> str:
    """Plain-text version for table cells (no HTML)."""
    if pd.isna(value) or value == "":
        return "-"
    return str(value)

def format_due_date_html(date_val: Any) -> str:
    """HTML version of due date with urgency coloring (for card-style views)."""
    if pd.isna(date_val) or date_val == "":
        return "-"
    try:
        due_date = pd.to_datetime(date_val)
        formatted = due_date.strftime('%m/%d/%Y')
        days_until = (due_date - datetime.now()).days
        if days_until < 0:
            return f'<span class="due-soon">⚠️ {formatted} (OVERDUE)</span>'
        if days_until <= 30:
            return f'<span class="due-soon">⏰ {formatted} ({days_until}d)</span>'
        return f'<span class="due-later">✓ {formatted}</span>'
    except Exception:
        return str(date_val)

def format_due_date_plain(date_val: Any) -> str:
    """Plain-text version for table cells (no HTML)."""
    if pd.isna(date_val) or date_val == "":
        return "-"
    try:
        due_date = pd.to_datetime(date_val)
        formatted = due_date.strftime('%m/%d/%Y')
        days_until = (due_date - datetime.now()).days
        if days_until < 0:
            return f"⚠️ {formatted} (OVERDUE)"
        if days_until <= 30:
            return f"⏰ {formatted} ({days_until}d)"
        return f"✓ {formatted}"
    except Exception:
        return str(date_val)

# Apply dark mode if enabled
if hasattr(st.session_state, 'dark_mode') and st.session_state.dark_mode:
    st.markdown('<style>body { background-color: #1a1a1a; color: #ffffff; }</style>', unsafe_allow_html=True)

# Header with enhanced controls
header_col1, header_col2, header_col3, header_col4 = st.columns([3, 1, 1, 1])
with header_col1:
    st.title("🏢 Property Tax Dashboard Pro")
    last_refresh_time = getattr(st.session_state, 'last_refresh', datetime.now())
    st.caption(f"Real-time monitoring with advanced analytics | Last refresh: {last_refresh_time.strftime('%H:%M:%S')}")

with header_col2:
    # Auto-refresh toggle
    auto_refresh_value = getattr(st.session_state, 'auto_refresh', False)
    auto_refresh = st.toggle("Auto-Refresh", value=auto_refresh_value, key="auto_refresh_toggle")
    if auto_refresh != auto_refresh_value:
        st.session_state.auto_refresh = auto_refresh
        if auto_refresh:
            add_activity_log("Auto-refresh enabled", "info")

    if getattr(st.session_state, 'auto_refresh', False):
        refresh_interval_value = getattr(st.session_state, 'refresh_interval', 30)
        refresh_interval = st.select_slider(
            "Interval (sec)",
            options=[10, 30, 60, 120, 300],
            value=refresh_interval_value,
            key="refresh_interval_slider"
        )
        st.session_state.refresh_interval = refresh_interval

with header_col3:
    # Dark mode toggle
    dark_mode_value = getattr(st.session_state, 'dark_mode', False)
    dark_mode = st.toggle("🌙 Dark Mode", value=dark_mode_value, key="dark_mode_toggle")
    if dark_mode != dark_mode_value:
        st.session_state.dark_mode = dark_mode
        st.rerun()

with header_col4:
    if st.button("🔄 Refresh Now", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.session_state.last_refresh = datetime.now()
        add_activity_log("Manual refresh triggered", "info")
        st.rerun()

# Auto-refresh implementation
if getattr(st.session_state, 'auto_refresh', False):
    last_refresh_time = getattr(st.session_state, 'last_refresh', datetime.now())
    time_since_refresh = (datetime.now() - last_refresh_time).seconds
    refresh_interval_value = getattr(st.session_state, 'refresh_interval', 30)
    if time_since_refresh >= refresh_interval_value:
        st.cache_data.clear()
        st.session_state.last_refresh = datetime.now()
        add_activity_log(f"Auto-refresh executed (interval: {refresh_interval_value}s)", "info")
        st.rerun()

# Notification banner for new updates
notifications_list = getattr(st.session_state, 'notifications', [])
if notifications_list:
    latest_notification = notifications_list[0]
    st.info(f"🔔 {latest_notification['message']}")
    if st.button("Dismiss", key="dismiss_notification"):
        st.session_state.notifications.pop(0)

# Sidebar
with st.sidebar:
    st.header("🔧 System Status")
    
    # API Status with better visual feedback
    with st.container():
        status_code, health_data = check_api_health()
        
        if status_code == 200 and health_data and health_data.get("status") == "healthy":
            st.success("✅ **API & Database Online**")
            with st.expander("Connection Details", expanded=False):
                st.json({
                    "API": API_URL,
                    "Status": "Healthy",
                    "Database": "Connected"
                })
        elif status_code == 200:
            st.warning("⚠️ **API Online, Database Issue**")
            st.caption("Check Railway Supabase credentials")
        else:
            st.error("❌ **API Offline**")
            st.caption(f"URL: {API_URL}")
    
    st.divider()
    
    # Enhanced Filters Section
    st.header("🔍 Advanced Filters")
    
    # Load initial data for filter options (limited prefetch)
    with st.spinner("Loading filter options..."):
        properties, _, _ = fetch_properties(limit=150)
    # Defer entity list loading to avoid extra blocking request on startup
    entities = []
    
    # Filter Presets
    with st.expander("📌 Filter Presets", expanded=False):
        preset_col1, preset_col2 = st.columns([2, 1])
        with preset_col1:
            filter_presets_dict = getattr(st.session_state, 'filter_presets', {})
            preset_names = list(filter_presets_dict.keys())
            if preset_names:
                selected_preset = st.selectbox("Load Preset", ["None"] + preset_names)
                if selected_preset != "None" and st.button("Load", key="load_preset"):
                    preset = filter_presets_dict[selected_preset]
                    # Apply preset filters
                    for key, value in preset.items():
                        st.session_state[f"filter_{key}"] = value
                    add_activity_log(f"Loaded filter preset: {selected_preset}", "info")
                    st.rerun()
        
        with preset_col2:
            if st.button("Save Current", key="save_preset"):
                preset_name = st.text_input("Preset Name", key="preset_name_input")
                if preset_name:
                    # Save current filters
                    current_filters = {}
                    for key in st.session_state:
                        if key.startswith("filter_"):
                            current_filters[key.replace("filter_", "")] = st.session_state[key]
                    st.session_state.filter_presets[preset_name] = current_filters
                    st.success(f"Saved preset: {preset_name}")
                    add_activity_log(f"Saved filter preset: {preset_name}", "success")
    
    # General controls
    st.subheader("⚙️ Data Loading")
    st.checkbox("Load all results (paginate)", value=False, key="load_all_results",
                help="Fetch all pages from the API. Can be slower.")
    st.number_input("Page size", min_value=50, max_value=1000, value=200, step=50, key="page_size",
                    help="Number of items to fetch per page when not loading all.")
    if st.button("Reset filters"):
        keys_to_clear = [k for k in st.session_state.keys() if k.startswith("filter_")]
        for k in keys_to_clear:
            del st.session_state[k]
        st.success("Filters reset. Reloading...")
        st.rerun()

    if properties:
        df_props = pd.DataFrame(properties)
        
        # Entity Filter (lazy-loaded to prevent initial hang)
        st.subheader("🏢 Entity Filter")
        enable_entity_filter = st.checkbox("Load entity list (optional)", key="enable_entity_filter")
        if enable_entity_filter:
            with st.spinner("Loading entities..."):
                entities = fetch_entities()
            if entities:
                entity_search = st.text_input("Search entities...", key="entity_search")
                entity_options = ["All"] + sorted([e.get('entity_name', 'Unknown') for e in entities
                                                    if e.get('entity_name') and (not entity_search or entity_search.lower() in e.get('entity_name', '').lower())])
                selected_entity = st.selectbox("Select Entity", entity_options, key="filter_entity")
            else:
                selected_entity = "All"
        else:
            selected_entity = "All"
        
        # Advanced Amount Range Filter
        st.subheader("💰 Amount Range")
        if 'amount_due' in df_props.columns:
            amounts = df_props['amount_due'].dropna()
            if not amounts.empty:
                min_amount = float(amounts.min())
                max_amount = float(amounts.max())
                
                amount_range = st.slider(
                    "Tax Amount Due Range",
                    min_value=min_amount,
                    max_value=max_amount,
                    value=(min_amount, max_amount),
                    format="$%.2f",
                    key="filter_amount_range"
                )
                st.checkbox("Apply amount filter", value=False, key="filter_amount_enabled", help="When enabled, restrict results to the selected amount range")
            else:
                amount_range = (0.0, 50000.0)
        else:
            amount_range = (0.0, 50000.0)
        
        # Multi-select Jurisdiction Filter
        st.subheader("🏛️ Jurisdictions")
        if 'jurisdiction' in df_props.columns:
            jurisdiction_options = sorted(df_props['jurisdiction'].dropna().unique().tolist())
            selected_jurisdictions = st.multiselect(
                "Select Jurisdictions",
                options=jurisdiction_options,
                default=None,
                key="filter_jurisdictions"
            )
        else:
            selected_jurisdictions = []
        
        # Paid By Filter
        if 'paid_by' in df_props.columns:
            paid_by_options = ["All"] + sorted(df_props['paid_by'].dropna().unique().tolist())
            selected_paid_by = st.selectbox("💳 Paid By", paid_by_options, key="filter_paid_by")
        else:
            selected_paid_by = "All"
        
        # State Filter
        if 'state' in df_props.columns:
            state_options = ["All"] + sorted(df_props['state'].dropna().unique().tolist())
            selected_state = st.selectbox("📍 State", state_options, key="filter_state")
        else:
            selected_state = "All"
        
        # Enhanced Due Date Range Filter
        st.subheader("📅 Due Date Range")
        
        if 'tax_due_date' in df_props.columns:
            # Convert to datetime for filtering
            df_props['tax_due_date_dt'] = pd.to_datetime(df_props['tax_due_date'], errors='coerce')
            
            # Find min and max dates
            valid_dates = df_props['tax_due_date_dt'].dropna()
            if not valid_dates.empty:
                min_date = valid_dates.min().date()
                max_date = valid_dates.max().date()
                
                date_range = st.date_input(
                    "Select range",
                    value=(min_date, max_date),
                    min_value=min_date,
                    max_value=max_date,
                    format="MM/DD/YYYY",
                    key="filter_date_range"
                )
                st.checkbox("Apply date filter", value=False, key="filter_date_enabled", help="When enabled, restrict results to the selected date range")
            else:
                date_range = None
        else:
            date_range = None
        
        # Quick Filters
        st.subheader("⚡ Quick Filters")
        show_overdue = st.checkbox("Show Overdue Only", value=False, key="filter_overdue")
        show_upcoming_30 = st.checkbox("Due in Next 30 Days", value=False, key="filter_upcoming_30")
        needs_extraction = st.checkbox("Needs Extraction", value=False, key="filter_needs_extraction")
        
        # Sorting Options
        st.subheader("↕️ Sorting")
        sort_col1, sort_col2 = st.columns(2)
        with sort_col1:
            sort_by = st.selectbox(
                "Sort By",
                options=["property_name", "amount_due", "tax_due_date", "jurisdiction", "state"],
                key="filter_sort_by"
            )
        with sort_col2:
            sort_order = st.selectbox(
                "Order",
                options=["asc", "desc"],
                format_func=lambda x: "Ascending ↑" if x == "asc" else "Descending ↓",
                key="filter_sort_order"
            )

# Main content with enhanced tabs
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "📊 Overview", 
    "🏢 Properties", 
    "👥 Entities", 
    "📈 Analytics", 
    "🔄 Tax Extraction",
    "📈 Trends & Insights",
    "⚙️ Admin Tools",
    "📋 Activity Log"
])

# Build filter parameters from sidebar selections
filter_params = {}
if 'filter_entity' in st.session_state and st.session_state.filter_entity != "All":
    # Find entity_id for selected entity
    for e in entities:
        if e.get('entity_name') == st.session_state.filter_entity:
            filter_params['entity_id'] = e.get('entity_id')
            break

if 'filter_jurisdictions' in st.session_state and st.session_state.filter_jurisdictions:
    # API supports single jurisdiction, so take first if multiple selected
    filter_params['jurisdiction'] = st.session_state.filter_jurisdictions[0]

if 'filter_state' in st.session_state and st.session_state.filter_state != "All":
    filter_params['state'] = st.session_state.filter_state

if 'filter_amount_range' in st.session_state and st.session_state.get('filter_amount_enabled'):
    filter_params['amount_due_min'] = st.session_state.filter_amount_range[0]
    filter_params['amount_due_max'] = st.session_state.filter_amount_range[1]

if 'filter_date_range' in st.session_state and st.session_state.filter_date_range and st.session_state.get('filter_date_enabled'):
    if len(st.session_state.filter_date_range) == 2:
        filter_params['due_date_after'] = st.session_state.filter_date_range[0].isoformat()
        filter_params['due_date_before'] = st.session_state.filter_date_range[1].isoformat()

if st.session_state.get('filter_needs_extraction'):
    filter_params['needs_extraction'] = True

if 'filter_sort_by' in st.session_state:
    filter_params['sort_by'] = st.session_state.filter_sort_by

if 'filter_sort_order' in st.session_state:
    filter_params['sort_order'] = st.session_state.filter_sort_order

# Load data with filters
with st.spinner("Loading data..."):
    if st.session_state.get("load_all_results"):
        properties, meta = fetch_all_properties(filters=filter_params, page_limit=st.session_state.get("page_size", 200))
        next_cursor = None
        load_info = f"Loaded all results in {meta.get('pages', 1)} page(s)"
    else:
        properties, next_cursor, meta = fetch_properties(filters=filter_params, limit=st.session_state.get("page_size", 200))
        load_info = f"Loaded {len(properties)} item(s), next page: {'yes' if next_cursor else 'no'}"
    stats = fetch_statistics()
    entities = fetch_entities()

# Apply additional client-side filters if needed
if properties:
    df = pd.DataFrame(properties)
    
    # Add datetime columns for filtering
    if 'tax_due_date' in df.columns:
        df['tax_due_date_dt'] = pd.to_datetime(df['tax_due_date'], errors='coerce')
    
    # Apply filters from sidebar
    if 'selected_entity' in locals() and selected_entity != "All" and entities:
        # Find the entity_id for the selected entity name
        entity_id = None
        for e in entities:
            if e.get('entity_name') == selected_entity:
                entity_id = e.get('entity_id')
                break
        
        # Filter properties by entity_id
        if entity_id and 'entity_id' in df.columns:
            df = df[df['entity_id'] == entity_id]
    
    if 'selected_paid_by' in locals() and selected_paid_by != "All":
        df = df[df['paid_by'] == selected_paid_by]
    
    if 'selected_state' in locals() and selected_state != "All":
        df = df[df['state'] == selected_state]
    
    if 'selected_jurisdiction' in locals() and selected_jurisdiction != "All":
        df = df[df['jurisdiction'] == selected_jurisdiction]
    
    if 'date_range' in locals() and date_range and len(date_range) == 2 and 'tax_due_date_dt' in df.columns:
        start_date, end_date = date_range
        df = df[(df['tax_due_date_dt'].dt.date >= start_date) & 
                (df['tax_due_date_dt'].dt.date <= end_date)]
    
    if 'show_overdue' in locals() and show_overdue and 'tax_due_date_dt' in df.columns:
        df = df[df['tax_due_date_dt'] < datetime.now()]
    
    if 'show_upcoming_30' in locals() and show_upcoming_30 and 'tax_due_date_dt' in df.columns:
        thirty_days = datetime.now() + timedelta(days=30)
        df = df[(df['tax_due_date_dt'] >= datetime.now()) & 
                (df['tax_due_date_dt'] <= thirty_days)]
else:
    df = pd.DataFrame()

with tab1:
    st.header("📊 System Overview")
    
    # Enhanced metrics with better layout
    if stats:
        # Primary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_props = len(df) if not df.empty else 0
            st.metric(
                "Total Properties",
                total_props,
                f"of {stats.get('total_properties', 0)} total"
            )
        
        with col2:
            st.metric("Total Entities", stats.get("total_entities", 0))
        
        with col3:
            outstanding = stats.get("total_outstanding_tax", 0)
            st.metric("Outstanding Tax", f"${outstanding:,.2f}")
        
        with col4:
            success_rate = stats.get("extraction_success_rate", 0)
            st.metric("Success Rate", f"{success_rate:.1f}%")
    
    # Summary metrics for new fields
    if not df.empty:
        st.divider()
        st.subheader("📊 Payment Responsibility Summary")
        
        if 'paid_by' in df.columns:
            # Count by paid_by category
            paid_by_counts = df['paid_by'].value_counts()
            
            # Create columns for paid_by metrics
            cols = st.columns(len(paid_by_counts))
            
            for idx, (category, count) in enumerate(paid_by_counts.items()):
                with cols[idx]:
                    # Color code the metric based on category
                    if pd.notna(category):
                        percentage = (count / len(df)) * 100
                        st.metric(
                            category,
                            count,
                            f"{percentage:.1f}%",
                            delta_color="off"
                        )
        
        st.divider()
        st.subheader("📅 Due Date Summary")
        
        if 'tax_due_date_dt' in df.columns:
            # Calculate due date statistics
            valid_dates = df[df['tax_due_date_dt'].notna()]
            
            if not valid_dates.empty:
                now = datetime.now()
                overdue = valid_dates[valid_dates['tax_due_date_dt'] < now]
                due_30 = valid_dates[(valid_dates['tax_due_date_dt'] >= now) & 
                                    (valid_dates['tax_due_date_dt'] <= now + timedelta(days=30))]
                due_60 = valid_dates[(valid_dates['tax_due_date_dt'] > now + timedelta(days=30)) & 
                                    (valid_dates['tax_due_date_dt'] <= now + timedelta(days=60))]
                due_later = valid_dates[valid_dates['tax_due_date_dt'] > now + timedelta(days=60)]
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("⚠️ Overdue", len(overdue), delta_color="inverse")
                
                with col2:
                    st.metric("🔴 Due in 30 days", len(due_30))
                
                with col3:
                    st.metric("🟡 Due in 31-60 days", len(due_60))
                
                with col4:
                    st.metric("🟢 Due after 60 days", len(due_later))
                
                # Visualization: Pie chart for paid_by distribution
                if 'paid_by' in df.columns:
                    st.divider()
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        fig_pie = px.pie(
                            values=paid_by_counts.values,
                            names=paid_by_counts.index,
                            title="Payment Responsibility Distribution",
                            color_discrete_map={
                                'Landlord': '#28a745',
                                'Tenant': '#17a2b8',
                                'Tenant to Reimburse': '#ffc107'
                            }
                        )
                        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                        st.plotly_chart(fig_pie, use_container_width=True)
                    
                    with col2:
                        # Timeline chart for due dates
                        timeline_data = valid_dates.groupby(
                            valid_dates['tax_due_date_dt'].dt.to_period('M')
                        ).size().reset_index()
                        timeline_data.columns = ['Month', 'Count']
                        timeline_data['Month'] = timeline_data['Month'].astype(str)
                        
                        fig_timeline = px.bar(
                            timeline_data,
                            x='Month',
                            y='Count',
                            title="Tax Due Dates by Month",
                            color_discrete_sequence=['#1f77b4']
                        )
                        st.plotly_chart(fig_timeline, use_container_width=True)

with tab2:
    st.header("🏢 Properties Detail")

    # Add Property UI (compact, single clickable row)
    with st.expander("➕ Add Property", expanded=False):
        # Local styles for clear visual separation
        st.markdown(
            """
            <style>
              .add-property-card {
                border: 1px solid rgba(0,0,0,0.1);
                border-radius: 10px;
                padding: 16px 16px 6px 16px;
                background: #fbfbfb;
                margin-top: 8px;
                box-shadow: 0 1px 2px rgba(0,0,0,0.04);
              }
              .add-property-card .section-title {
                font-weight: 600;
                margin: 6px 0 8px 0;
              }
              .add-property-card .fine-print {
                color: #666; font-size: 12px; margin-top: -2px; margin-bottom: 8px;
              }
            </style>
            """,
            unsafe_allow_html=True
        )
        st.markdown('<div class="add-property-card">', unsafe_allow_html=True)
        st.markdown("<div class='section-title'>Property Details</div>", unsafe_allow_html=True)
        with st.form("add_property_form", clear_on_submit=True):
            pc1, pc2 = st.columns(2)
            with pc1:
                new_property_id = st.text_input("Property ID", placeholder="e.g., PROP_12345")
                new_property_name = st.text_input("Property Name")
                new_property_address = st.text_input("Property Address")
                new_state = st.text_input("State", placeholder="e.g., TX")
                new_jurisdiction = st.text_input("Jurisdiction", placeholder="e.g., Harris County")
                new_account_number = st.text_input("Account Number", placeholder="Optional")
                new_tax_bill_link = st.text_input("Tax Bill Link", placeholder="https://...")
            with pc2:
                st.markdown("<div class='section-title'>Financials</div>", unsafe_allow_html=True)
                new_amount_due = st.number_input("Amount Due", min_value=0.0, step=100.0, format="%0.2f")
                new_prev_year = st.number_input("Previous Year Taxes", min_value=0.0, step=100.0, format="%0.2f")
                new_paid_by = st.selectbox("Paid By", options=["", "Landlord", "Tenant", "Tenant to Reimburse"], index=0)
                new_due_date = st.date_input("Tax Due Date", value=None, format="MM/DD/YYYY")
                new_close_date = st.date_input("Close Date", value=None, format="MM/DD/YYYY")
                new_property_type = st.text_input("Property Type", value="property")

            new_extraction_steps = st.text_area("Extraction Steps (notes)", height=80)

            st.divider()
            st.markdown("<div class='section-title'>Entity Assignment</div>", unsafe_allow_html=True)
            entity_mode = st.radio(
                "Entity Assignment",
                options=["Assign to Existing Entity", "Create New Entity"],
                horizontal=True,
                key="add_prop_entity_mode"
            )

            selected_parent_entity_id = None
            if entity_mode == "Assign to Existing Entity":
                # Build list of existing entities
                entity_names = [e.get("entity_name", "Unnamed") for e in (entities or [])]
                selected_entity_name = st.selectbox("Select Entity", options=entity_names or ["No entities available"]) if entities else st.selectbox("Select Entity", options=["No entities available"]) 
                if entities and selected_entity_name:
                    for e in entities:
                        if e.get("entity_name") == selected_entity_name:
                            selected_parent_entity_id = e.get("entity_id")
                            break
                new_entity_payload = None
            else:
                # Create new entity fields
                ec1, ec2 = st.columns(2)
                with ec1:
                    ent_name = st.text_input("New Entity Name")
                    ent_type = st.selectbox(
                        "New Entity Type",
                        options=["Parent Entity", "Sub-Entity", "Single-Property Entity"],
                        index=0
                    )
                with ec2:
                    ent_state = st.text_input("Entity State", placeholder="e.g., TX")
                    ent_juris = st.text_input("Entity Jurisdiction", placeholder="Optional")

                ent_parent_id = None
                if ent_type == "Sub-Entity":
                    parent_options = [e.get("entity_name", "Unnamed") for e in (entities or [])]
                    ent_parent_name = st.selectbox("Parent Entity", options=parent_options or ["No parent entities"])
                    if entities and ent_parent_name:
                        for e in entities:
                            if e.get("entity_name") == ent_parent_name:
                                ent_parent_id = e.get("entity_id")
                                break

                # For single-property entity we may capture some property-like fields
                include_prop_details = (ent_type == "Single-Property Entity")
                if include_prop_details:
                    st.caption("This entity will store property-like details as well.")

                new_entity_payload = {
                    "entity_name": ent_name,
                    "entity_type": ent_type.lower(),
                    "state": ent_state or None,
                    "jurisdiction": ent_juris or None,
                    "parent_entity_id": ent_parent_id or None,
                }
                if include_prop_details:
                    new_entity_payload.update({
                        "account_number": new_account_number or None,
                        "property_address": new_property_address or None,
                        "tax_bill_link": new_tax_bill_link or None,
                        "amount_due": float(new_amount_due or 0) if new_amount_due is not None else None,
                        "previous_year_taxes": float(new_prev_year or 0) if new_prev_year is not None else None,
                        "close_date": new_close_date.isoformat() if isinstance(new_close_date, (datetime, date)) else None,
                    })

            submitted = st.form_submit_button("Create Property", type="primary")

            if submitted:
                # Validate required
                if not new_property_id or not new_property_name:
                    st.error("Property ID and Property Name are required")
                elif entity_mode == "Assign to Existing Entity" and not selected_parent_entity_id:
                    st.error("Please select an entity to assign the property to")
                elif entity_mode == "Create New Entity" and (not new_entity_payload or not new_entity_payload.get("entity_name")):
                    st.error("Please provide a name for the new entity")
                else:
                    # Create entity first if requested
                    created_entity_id = selected_parent_entity_id
                    if entity_mode == "Create New Entity":
                        ent_result = create_entity_api(new_entity_payload)
                        if ent_result.get("entity"):
                            created_entity_id = ent_result["entity"].get("entity_id") or ent_result["entity"].get("id")
                        else:
                            st.error(f"Failed to create entity: {ent_result.get('error') or ent_result.get('details') or 'Unknown error'}")
                            st.stop()

                    # Build property payload
                    prop_payload: Dict[str, Any] = {
                        "property_id": new_property_id,
                        "property_name": new_property_name,
                        "property_address": new_property_address or None,
                        "jurisdiction": new_jurisdiction or None,
                        "state": new_state or None,
                        "property_type": new_property_type or None,
                        "account_number": new_account_number or None,
                        "tax_bill_link": new_tax_bill_link or None,
                        "amount_due": float(new_amount_due or 0) if new_amount_due is not None else None,
                        "previous_year_taxes": float(new_prev_year or 0) if new_prev_year is not None else None,
                        "paid_by": new_paid_by or None,
                        "extraction_steps": new_extraction_steps or None,
                        "parent_entity_id": created_entity_id or None,
                    }
                    if isinstance(new_due_date, (datetime, date)):
                        try:
                            prop_payload["tax_due_date"] = new_due_date.isoformat()
                        except Exception:
                            pass
                    if isinstance(new_close_date, (datetime, date)):
                        try:
                            prop_payload["close_date"] = new_close_date.isoformat()
                        except Exception:
                            pass

                    result = create_property_api(prop_payload)
                    if result.get("property"):
                        st.success("Property created successfully")
                        add_activity_log(f"Created property {new_property_name} ({new_property_id})", "success")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"Failed to create property: {result.get('error') or result.get('details') or 'Unknown error'}")
        st.markdown('</div>', unsafe_allow_html=True)
    
    if not df.empty:
        # Bulk operations toolbar
        bulk_col1, bulk_col2, bulk_col3, bulk_col4 = st.columns([1, 2, 2, 2])
        
        with bulk_col1:
            bulk_mode = st.checkbox("Bulk Edit Mode", key="bulk_edit_toggle")
            st.session_state.bulk_edit_mode = bulk_mode
        
        with bulk_col2:
            if st.session_state.bulk_edit_mode:
                if st.button("Select All", key="select_all_btn"):
                    st.session_state.selected_properties = set(df['property_id'].tolist())
                    add_activity_log(f"Selected all {len(df)} properties", "info")
                    st.rerun()
                
                if st.button("Clear Selection", key="clear_selection_btn"):
                    st.session_state.selected_properties = set()
                    add_activity_log("Cleared property selection", "info")
                    st.rerun()
        
        with bulk_col3:
            if st.session_state.bulk_edit_mode and st.session_state.selected_properties:
                st.write(f"Selected: {len(st.session_state.selected_properties)} properties")
                
                # Bulk update paid_by
                new_paid_by = st.selectbox(
                    "Update Paid By",
                    options=["No Change", "Landlord", "Tenant", "Tenant to Reimburse"],
                    key="bulk_paid_by"
                )
                
                if new_paid_by != "No Change" and st.button("Apply Update", key="apply_bulk_update"):
                    updates = [
                        {"property_id": prop_id, "paid_by": new_paid_by}
                        for prop_id in st.session_state.selected_properties
                    ]
                    result = bulk_update_properties(updates)
                    if result.get("success", False) or result.get("count"):
                        st.success(f"Updated {len(updates)} properties")
                        add_activity_log(f"Bulk updated paid_by for {len(updates)} properties", "success")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"Update failed: {result.get('message', 'Unknown error')}")
        
        with bulk_col4:
            if st.session_state.bulk_edit_mode and st.session_state.selected_properties:
                if st.button("🚀 Extract Selected", key="bulk_extract_btn", type="primary"):
                    selected_ids = list(st.session_state.selected_properties)
                    if len(selected_ids) <= 10:
                        result = trigger_batch_extraction(selected_ids)
                        if result.get("status") == "processing":
                            st.success(f"Started extraction for {len(selected_ids)} properties")
                            add_activity_log(f"Triggered batch extraction for {len(selected_ids)} properties", "success")
                        else:
                            st.error(f"Extraction failed: {result.get('message', 'Unknown error')}")
                    else:
                        st.warning("Please select 10 or fewer properties for batch extraction")
        
        # Display summary
        st.info(f"Showing {len(df)} properties | {load_info}")
        
        # Prepare display dataframe
        display_df = df.copy()
        
        # Format columns for display
        if 'tax_due_date' in display_df.columns:
            display_df['tax_due_date_formatted'] = display_df['tax_due_date_dt'].apply(
                lambda x: format_due_date_plain(x) if pd.notna(x) else "-"
            )
        
        if 'paid_by' in display_df.columns:
            display_df['paid_by_formatted'] = display_df['paid_by'].apply(format_paid_by_plain)
        
        # Enhanced property display with bulk selection
        if st.session_state.bulk_edit_mode:
            # Display properties with checkboxes
            st.subheader("Select Properties for Bulk Operations")
            
            # Create a container for scrollable property list
            with st.container():
                for idx, row in display_df.iterrows():
                    col1, col2 = st.columns([1, 9])
                    
                    with col1:
                        # Checkbox for selection
                        prop_id = df.iloc[idx]['property_id']
                        is_selected = prop_id in st.session_state.selected_properties
                        
                        if st.checkbox("Select", value=is_selected, key=f"select_{prop_id}", label_visibility="collapsed"):
                            st.session_state.selected_properties.add(prop_id)
                        else:
                            st.session_state.selected_properties.discard(prop_id)
                    
                    with col2:
                        # Property details with enhanced formatting
                        property_html = f"""
                        <div style="padding: 10px; border: 1px solid #ddd; border-radius: 5px; margin-bottom: 10px;">
                            <strong>{row.get('property_name', 'N/A')}</strong><br>
                            📍 {row.get('property_address', 'N/A')}<br>
                            🏛️ {row.get('jurisdiction', 'N/A')} | 📍 {row.get('state', 'N/A')}<br>
                            💰 Amount: {format_amount_with_color(row.get('amount_due', 0))}<br>
                            📅 Due: {format_due_date_html(row.get('tax_due_date'))}<br>
                            💳 Paid By: {format_paid_by(row.get('paid_by'))}
                        </div>
                        """
                        st.markdown(property_html, unsafe_allow_html=True)
        else:
            # Standard table display
            # Select columns to display
            display_cols = ['property_name', 'property_address', 'jurisdiction', 'state']
            
            # Add amount_due column if it exists
            if 'amount_due' in display_df.columns:
                display_cols.append('amount_due')
            
            if 'tax_due_date_formatted' in display_df.columns:
                display_cols.append('tax_due_date_formatted')
            
            if 'paid_by_formatted' in display_df.columns:
                display_cols.append('paid_by_formatted')
            
            # Add tax_bill_link column if it exists
            if 'tax_bill_link' in display_df.columns:
                display_cols.append('tax_bill_link')
            
            # Rename columns for display
            rename_map = {
                'property_name': 'Property Name',
                'property_address': 'Address',
                'jurisdiction': 'Jurisdiction',
                'state': 'State',
                'amount_due': 'Tax Amount Due',
                'tax_due_date_formatted': 'Due Date',
                'paid_by_formatted': 'Paid By',
                'tax_bill_link': 'Tax Bill URL'
            }
            
            display_df_renamed = display_df[display_cols].rename(columns=rename_map)
            
            # Display with enhanced data editor for inline editing
            edited_df = st.data_editor(
                display_df_renamed,
                hide_index=True,
                use_container_width=True,
                disabled=["Property Name", "Address", "Jurisdiction", "State", "Tax Bill URL"],
                column_config={
                    "Tax Amount Due": st.column_config.NumberColumn(
                        "Tax Amount Due",
                        format="$%.2f",
                        min_value=0,
                        max_value=100000
                    ),
                    "Due Date": st.column_config.Column(
                        "Due Date",
                        help="Tax payment due date"
                    ),
                    "Tax Bill URL": st.column_config.LinkColumn(
                        "Tax Bill URL",
                        help="Click to view tax bill"
                    )
                }
            )
            
            # Check for changes and update if needed
            if not display_df_renamed.equals(edited_df):
                st.info("⚠️ You have unsaved changes. Click 'Save Changes' to apply.")
                if st.button("💾 Save Changes", key="save_inline_edits"):
                    # Prepare updates from edited data
                    updates = []
                    for idx, row in edited_df.iterrows():
                        original_row = display_df_renamed.iloc[idx]
                        if not row.equals(original_row):
                            # Use logical property_id for updates, not internal id
                            update = {"property_id": df.iloc[idx]['property_id']}
                            if row.get('Paid By') != original_row.get('Paid By'):
                                update['paid_by'] = row['Paid By']
                            updates.append(update)
                    
                    if updates:
                        result = bulk_update_properties(updates)
                        if result.get("success", False) or result.get("count"):
                            st.success(f"Updated {len(updates)} properties")
                            add_activity_log(f"Updated {len(updates)} properties via inline editing", "success")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error(f"Update failed: {result.get('message', 'Unknown error')}")
        
        # Export options
        st.divider()
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # CSV export
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"properties_filtered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col2:
            # Excel export
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Properties', index=False)
                
                # Add summary sheet
                summary_data = {
                    'Metric': ['Total Properties', 'Total Outstanding Tax', 'Properties with Due Dates'],
                    'Value': [len(df), df['outstanding_tax'].sum() if 'outstanding_tax' in df.columns else 0,
                             df['tax_due_date'].notna().sum() if 'tax_due_date' in df.columns else 0]
                }
                pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)
            
            excel_data = output.getvalue()
            st.download_button(
                label="📊 Download Excel",
                data=excel_data,
                file_name=f"properties_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        
        with col3:
            # JSON export - convert dates to strings first
            json_df = df.copy()
            for col in json_df.columns:
                if json_df[col].dtype == 'datetime64[ns]' or 'date' in col.lower():
                    json_df[col] = json_df[col].astype(str).replace('NaT', '')
            json_data = json_df.to_json(orient='records', date_format='iso')
            st.download_button(
                label="📋 Download JSON",
                data=json_data,
                file_name=f"properties_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True
            )
    else:
        st.info("No properties found matching the current filters")

with tab3:
    st.header("👥 Entity Management")
    
    if entities:
        entities_df = pd.DataFrame(entities)
        
        # Categorize entities based on entity_type field
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
                # Fallback logic if entity_type is missing or unknown
                if entity.get('parent_entity_id'):
                    sub_entities.append(entity)
                elif entity.get('property_count', 0) == 1:
                    single_property_entities.append(entity)
                else:
                    parent_entities.append(entity)
        
        # Display entity statistics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Entities", len(entities))
        
        with col2:
            st.metric("Parent Entities", len(parent_entities))
        
        with col3:
            st.metric("Sub-Entities", len(sub_entities))
        
        with col4:
            st.metric("Single-Property", len(single_property_entities))
        
        # Entity Type Distribution
        st.subheader("🏢 Entity Type Distribution")
        
        entity_types = {
            'Parent Entities': len(parent_entities),
            'Sub-Entities': len(sub_entities),
            'Single-Property Entities': len(single_property_entities)
        }
        
        fig_entity_dist = px.pie(
            values=list(entity_types.values()),
            names=list(entity_types.keys()),
            title="Entity Classification",
            color_discrete_map={
                'Parent Entities': '#2E86AB',
                'Sub-Entities': '#A23B72',
                'Single-Property Entities': '#F18F01'
            }
        )
        st.plotly_chart(fig_entity_dist, use_container_width=True)
        
        # Entity Hierarchy Visualization
        st.subheader("🌳 Entity Hierarchy")
        
        # Create tabs for different entity types
        entity_tab1, entity_tab2, entity_tab3 = st.tabs(["Parent Entities", "Sub-Entities", "Single-Property"])
        
        with entity_tab1:
            if parent_entities:
                for entity in parent_entities:
                    with st.expander(f"🏢 {entity.get('entity_name', 'Unknown')}"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write(f"**Entity ID:** {entity.get('entity_id', 'N/A')}")
                            st.write(f"**Type:** {entity.get('entity_type', 'N/A')}")
                            st.write(f"**Property Count:** {entity.get('property_count', 0)}")
                            # Display tax amount due
                            amount_due = entity.get('amount_due', 0)
                            if amount_due is not None:
                                st.write(f"**Tax Amount Due:** ${amount_due:,.2f}")
                        
                        with col2:
                            st.write(f"**Created:** {entity.get('created_at', 'N/A')}")
                            if entity.get('notes'):
                                st.write(f"**Notes:** {entity.get('notes')}")
                        
                        # Show sub-entities if any
                        related_subs = [e for e in sub_entities if e.get('parent_entity_id') == entity.get('entity_id')]
                        if related_subs:
                            st.write("**Sub-Entities:**")
                            for sub in related_subs:
                                st.write(f"  • {sub.get('entity_name', 'Unknown')} ({sub.get('property_count', 0)} properties)")
            else:
                st.info("No parent entities found")
        
        with entity_tab2:
            if sub_entities:
                for entity in sub_entities:
                    with st.expander(f"📁 {entity.get('entity_name', 'Unknown')}"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write(f"**Entity ID:** {entity.get('entity_id', 'N/A')}")
                            st.write(f"**Type:** {entity.get('entity_type', 'N/A')}")
                            st.write(f"**Property Count:** {entity.get('property_count', 0)}")
                            # Display tax amount due
                            amount_due = entity.get('amount_due', 0)
                            if amount_due is not None:
                                st.write(f"**Tax Amount Due:** ${amount_due:,.2f}")
                        
                        with col2:
                            # Find parent entity name
                            parent_id = entity.get('parent_entity_id')
                            if parent_id:
                                parent_name = next((e.get('entity_name') for e in parent_entities if e.get('entity_id') == parent_id), 'Unknown')
                                st.write(f"**Parent Entity:** {parent_name}")
                            else:
                                st.write(f"**Parent Entity:** Not linked")
                            st.write(f"**Created:** {entity.get('created_at', 'N/A')}")
                            if entity.get('notes'):
                                st.write(f"**Notes:** {entity.get('notes')}")
            else:
                st.info("No sub-entities found")
        
        with entity_tab3:
            if single_property_entities:
                # Display as a table for better overview
                single_df = pd.DataFrame(single_property_entities)
                display_cols = ['entity_name', 'entity_type', 'property_count', 'amount_due', 'created_at']
                available_cols = [col for col in display_cols if col in single_df.columns]
                
                if available_cols:
                    # Rename columns for better display
                    column_rename = {
                        'entity_name': 'Entity Name',
                        'entity_type': 'Type',
                        'property_count': 'Properties',
                        'amount_due': 'Tax Amount Due',
                        'created_at': 'Created At'
                    }
                    display_df = single_df[available_cols].rename(columns=column_rename)
                    st.dataframe(
                        display_df,
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    for entity in single_property_entities:
                        st.write(f"• {entity.get('entity_name', 'Unknown')}")
            else:
                st.info("No single-property entities found")
        
        # Entity Relationship Network (if there are relationships)
        # Check if sub-entities have parent_entity_id set
        has_relationships = any(entity.get('parent_entity_id') for entity in sub_entities)
        
        if parent_entities and sub_entities and has_relationships:
            st.subheader("🔗 Entity Relationships Network")
            
            # Create a simple network visualization
            import plotly.graph_objects as go
            
            # Build edge and node lists
            edge_x = []
            edge_y = []
            node_x = []
            node_y = []
            node_text = []
            node_color = []
            
            # Position parent entities
            for i, entity in enumerate(parent_entities):
                x = i * 2
                y = 1
                node_x.append(x)
                node_y.append(y)
                node_text.append(entity.get('entity_name', 'Unknown'))
                node_color.append('#2E86AB')  # Blue for parent
                
                # Position and connect sub-entities
                related_subs = [e for e in sub_entities if e.get('parent_entity_id') == entity.get('entity_id')]
                for j, sub in enumerate(related_subs):
                    sub_x = x + (j - len(related_subs)/2) * 0.5
                    sub_y = 0
                    node_x.append(sub_x)
                    node_y.append(sub_y)
                    node_text.append(sub.get('entity_name', 'Unknown'))
                    node_color.append('#A23B72')  # Pink for sub-entity
                    
                    # Add edge
                    edge_x.extend([x, sub_x, None])
                    edge_y.extend([y, sub_y, None])
            
            # Create the network graph
            fig_network = go.Figure()
            
            # Add edges
            fig_network.add_trace(go.Scatter(
                x=edge_x, y=edge_y,
                line=dict(width=0.5, color='#888'),
                hoverinfo='none',
                mode='lines'
            ))
            
            # Add nodes
            fig_network.add_trace(go.Scatter(
                x=node_x, y=node_y,
                mode='markers+text',
                text=node_text,
                textposition="top center",
                marker=dict(
                    size=15,
                    color=node_color,
                    line=dict(width=2, color='white')
                ),
                hoverinfo='text'
            ))
            
            fig_network.update_layout(
                title="Entity Hierarchy Network",
                showlegend=False,
                hovermode='closest',
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                height=400
            )
            
            st.plotly_chart(fig_network, use_container_width=True)
        elif parent_entities and sub_entities and not has_relationships:
            st.info("ℹ️ Entity relationships are not configured in the database. Sub-entities exist but are not linked to parent entities.")
        
        # Export functionality
        st.subheader("📤 Export Entity Data")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # CSV export
            csv = entities_df.to_csv(index=False)
            st.download_button(
                label="📄 Download CSV",
                data=csv,
                file_name=f"entities_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col2:
            # JSON export - convert dates to strings first
            json_df = entities_df.copy()
            for col in json_df.columns:
                if json_df[col].dtype == 'datetime64[ns]' or 'date' in col.lower():
                    json_df[col] = json_df[col].astype(str).replace('NaT', '')
            json_data = json_df.to_json(orient='records', date_format='iso')
            st.download_button(
                label="📋 Download JSON",
                data=json_data,
                file_name=f"entities_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True
            )
    else:
        st.info("No entities found in the system")

with tab4:
    st.header("📈 Advanced Analytics")
    
    if not df.empty:
        # State-wise analysis
        if 'state' in df.columns and not df.empty:
            st.subheader("🗺️ Geographic Distribution")
            
            # Determine which columns to aggregate based on what's available
            agg_dict = {}
            
            # Use the first available column for counting
            if len(df.columns) > 0:
                first_col = df.columns[0]
                agg_dict[first_col] = 'count'
            
            # Add outstanding_tax sum if available
            if 'outstanding_tax' in df.columns:
                agg_dict['outstanding_tax'] = 'sum'
            
            # Only proceed if we have something to aggregate
            if agg_dict:
                state_summary = df.groupby('state').agg(agg_dict).reset_index()
                
                # Rename columns appropriately
                col_names = ['State']
                if first_col in agg_dict:
                    col_names.append('Property Count')
                if 'outstanding_tax' in agg_dict:
                    col_names.append('Total Outstanding Tax')
                state_summary.columns = col_names[:len(state_summary.columns)]
            else:
                # Create empty summary if no columns to aggregate
                state_summary = pd.DataFrame({'State': [], 'Property Count': [], 'Total Outstanding Tax': []})
            
            col1, col2 = st.columns(2)
            
            with col1:
                fig_state = px.bar(
                    state_summary,
                    x='State',
                    y='Property Count',
                    title='Properties by State',
                    color='Property Count',
                    color_continuous_scale='Blues'
                )
                st.plotly_chart(fig_state, use_container_width=True)
            
            with col2:
                if 'Total Outstanding Tax' in state_summary.columns:
                    fig_tax = px.bar(
                        state_summary,
                        x='State',
                        y='Total Outstanding Tax',
                        title='Outstanding Tax by State',
                        color='Total Outstanding Tax',
                        color_continuous_scale='Reds'
                    )
                    fig_tax.update_yaxis(tickformat='$,.0f')
                    st.plotly_chart(fig_tax, use_container_width=True)
        
        # Jurisdiction analysis
        if 'jurisdiction' in df.columns:
            st.divider()
            st.subheader("🏛️ Jurisdiction Analysis")
            
            jurisdiction_summary = df['jurisdiction'].value_counts().head(10)
            
            fig_jurisdiction = px.bar(
                x=jurisdiction_summary.values,
                y=jurisdiction_summary.index,
                orientation='h',
                title='Top 10 Jurisdictions by Property Count',
                labels={'x': 'Number of Properties', 'y': 'Jurisdiction'}
            )
            st.plotly_chart(fig_jurisdiction, use_container_width=True)
        
        # Combined analysis
        if 'paid_by' in df.columns and 'tax_due_date_dt' in df.columns:
            st.divider()
            st.subheader("🔄 Cross-Analysis: Payment Responsibility vs Due Dates")
            
            cross_df = df[df['tax_due_date_dt'].notna() & df['paid_by'].notna()].copy()
            
            if not cross_df.empty:
                # Calculate days until due
                cross_df['days_until_due'] = (cross_df['tax_due_date_dt'] - datetime.now()).dt.days
                cross_df['urgency'] = pd.cut(
                    cross_df['days_until_due'],
                    bins=[-float('inf'), 0, 30, 60, float('inf')],
                    labels=['Overdue', 'Due in 30 days', 'Due in 31-60 days', 'Due after 60 days']
                )
                
                # Create heatmap
                heatmap_data = pd.crosstab(cross_df['paid_by'], cross_df['urgency'])
                
                fig_heatmap = px.imshow(
                    heatmap_data,
                    labels=dict(x="Urgency", y="Paid By", color="Count"),
                    title="Payment Responsibility by Due Date Urgency",
                    color_continuous_scale='YlOrRd',
                    aspect='auto'
                )
                st.plotly_chart(fig_heatmap, use_container_width=True)
    else:
        st.info("No data available for analytics")

with tab5:
    st.header("🔄 Tax Extraction Service")
    
    # Get supported jurisdictions
    supported_jurisdictions = get_supported_jurisdictions()
    
    if supported_jurisdictions:
        # Display supported jurisdictions info
        st.subheader("📍 Supported Jurisdictions")
        
        # Define the 8 cloud-supported jurisdictions
        cloud_supported = {
            "Montgomery": {"name": "Montgomery County, TX", "confidence": "High", "method": "HTTP"},
            "Fort Bend": {"name": "Fort Bend County, TX", "confidence": "High", "method": "HTTP"},
            "Chambers": {"name": "Chambers County, TX", "confidence": "Medium", "method": "HTTP"},
            "Galveston": {"name": "Galveston County, TX", "confidence": "Medium", "method": "HTTP"},
            "Aldine ISD": {"name": "Aldine ISD, TX", "confidence": "High", "method": "HTTP"},
            "Goose Creek ISD": {"name": "Goose Creek ISD, TX", "confidence": "High", "method": "HTTP"},
            "Spring Creek": {"name": "Spring Creek U.D., TX", "confidence": "Medium", "method": "HTTP"},
            "Barbers Hill ISD": {"name": "Barbers Hill ISD, TX", "confidence": "Medium", "method": "HTTP"}
        }
        
        # Display jurisdiction cards
        cols = st.columns(4)
        for idx, (key, info) in enumerate(cloud_supported.items()):
            with cols[idx % 4]:
                confidence_color = "🟢" if info["confidence"] == "High" else "🟡"
                st.info(f"{confidence_color} **{info['name']}**\n\nConfidence: {info['confidence']}\nMethod: {info['method']}")
        
        st.divider()
        
        # Extraction interface
        st.subheader("🎯 Extract Tax Data")
        
        extraction_mode = st.radio(
            "Select extraction mode:",
            ["Single Property", "Batch Extraction", "By Jurisdiction"]
        )
        
        if extraction_mode == "Single Property":
            # Single property extraction
            st.write("Extract tax data for a single property")
            
            # Filter properties to show only supported jurisdictions
            if properties:
                # Filter for supported jurisdictions
                supported_props = []
                for prop in properties:
                    jurisdiction = prop.get("jurisdiction", "")
                    if any(key.lower() in jurisdiction.lower() for key in cloud_supported.keys()):
                        supported_props.append(prop)
                
                if supported_props:
                    # Create selection dropdown
                    property_options = {
                        f"{p.get('property_name', 'Unknown')} - {p.get('jurisdiction', 'Unknown')}": p
                        for p in supported_props
                    }
                    
                    selected_property = st.selectbox(
                        "Select a property to extract:",
                        options=list(property_options.keys()),
                        help="Only properties in supported jurisdictions are shown"
                    )
                    
                    if selected_property:
                        property_data = property_options[selected_property]
                        
                        # Display property details
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write("**Property Details:**")
                            st.write(f"• Name: {property_data.get('property_name', 'N/A')}")
                            st.write(f"• Jurisdiction: {property_data.get('jurisdiction', 'N/A')}")
                            st.write(f"• Account #: {property_data.get('acct_number', 'N/A')}")
                        
                        with col2:
                            st.write("**Current Status:**")
                            current_tax = property_data.get('amount_due', 0)
                            if current_tax and current_tax > 0:
                                st.write(f"• Tax Amount: ${current_tax:,.2f}")
                                st.write(f"• Last Updated: {property_data.get('updated_at', 'N/A')}")
                            else:
                                st.write("• No tax data available")
                                st.write("• Needs extraction")
                        
                        # Extraction button
                        if st.button("🚀 Extract Tax Data", type="primary", key="single_extract"):
                            with st.spinner(f"Extracting tax data for {property_data.get('property_name')}..."):
                                result = trigger_extraction(property_data)
                                
                                if result.get("success"):
                                    st.success(f"✅ Successfully extracted tax data!")
                                    st.write(f"**Tax Amount:** ${result.get('tax_amount', 0):,.2f}")
                                    if result.get('property_address'):
                                        st.write(f"**Property Address:** {result.get('property_address')}")
                                    st.write(f"**Extraction Method:** {result.get('extraction_method', 'HTTP')}")
                                    st.write(f"**Confidence:** {result.get('confidence', 'N/A')}")
                                else:
                                    st.error(f"❌ Extraction failed: {result.get('error_message', 'Unknown error')}")
                else:
                    st.warning("No properties found in supported jurisdictions")
            else:
                st.warning("No properties available")
        
        elif extraction_mode == "Batch Extraction":
            # Batch extraction
            st.write("Extract tax data for multiple properties at once (max 10)")
            
            if properties:
                # Filter for supported jurisdictions
                supported_props = []
                for prop in properties:
                    jurisdiction = prop.get("jurisdiction", "")
                    if any(key.lower() in jurisdiction.lower() for key in cloud_supported.keys()):
                        supported_props.append(prop)
                
                if supported_props:
                    # Multi-select for batch
                    property_options = {
                        f"{p.get('property_name', 'Unknown')} - {p.get('jurisdiction', 'Unknown')}": p.get('property_id')
                        for p in supported_props
                    }
                    
                    selected_properties = st.multiselect(
                        "Select properties to extract (max 10):",
                        options=list(property_options.keys()),
                        max_selections=10,
                        help="Select up to 10 properties for batch extraction"
                    )
                    
                    if selected_properties:
                        st.write(f"**Selected:** {len(selected_properties)} properties")
                        
                        # Batch extraction button
                        if st.button("🚀 Start Batch Extraction", type="primary", key="batch_extract"):
                            property_ids = [property_options[p] for p in selected_properties]
                            
                            with st.spinner(f"Starting batch extraction for {len(property_ids)} properties..."):
                                result = trigger_batch_extraction(property_ids)
                                
                                if result.get("status") == "processing":
                                    st.success(f"✅ Batch extraction started!")
                                    st.write(f"**Message:** {result.get('message')}")
                                    st.info("⏳ Extraction is processing in the background. Results will be stored in the database.")
                                    st.write("**Property IDs being processed:**")
                                    for pid in result.get("property_ids", []):
                                        st.write(f"• {pid}")
                                else:
                                    st.error(f"❌ Failed to start batch extraction: {result.get('message', 'Unknown error')}")
                else:
                    st.warning("No properties found in supported jurisdictions")
            else:
                st.warning("No properties available")
        
        else:  # By Jurisdiction
            # Extract by jurisdiction
            st.write("Extract all properties in a specific jurisdiction")
            
            # Group properties by jurisdiction
            if properties:
                jurisdiction_groups = {}
                for prop in properties:
                    jurisdiction = prop.get("jurisdiction", "Unknown")
                    # Check if it's a supported jurisdiction
                    is_supported = any(key.lower() in jurisdiction.lower() for key in cloud_supported.keys())
                    if is_supported:
                        if jurisdiction not in jurisdiction_groups:
                            jurisdiction_groups[jurisdiction] = []
                        jurisdiction_groups[jurisdiction].append(prop)
                
                if jurisdiction_groups:
                    selected_jurisdiction = st.selectbox(
                        "Select a jurisdiction:",
                        options=list(jurisdiction_groups.keys()),
                        help="Only supported jurisdictions are shown"
                    )
                    
                    if selected_jurisdiction:
                        props_in_jurisdiction = jurisdiction_groups[selected_jurisdiction]
                        st.write(f"**Properties in {selected_jurisdiction}:** {len(props_in_jurisdiction)}")
                        
                        # Show properties that would be extracted
                        with st.expander("View properties to be extracted"):
                            for prop in props_in_jurisdiction[:10]:  # Show first 10
                                st.write(f"• {prop.get('property_name', 'Unknown')} - Account: {prop.get('acct_number', 'N/A')}")
                            if len(props_in_jurisdiction) > 10:
                                st.write(f"... and {len(props_in_jurisdiction) - 10} more")
                        
                        # Extract button
                        if st.button(f"🚀 Extract All ({len(props_in_jurisdiction)} properties)", type="primary", key="jurisdiction_extract"):
                            if len(props_in_jurisdiction) <= 10:
                                property_ids = [p.get('property_id') for p in props_in_jurisdiction]
                                
                                with st.spinner(f"Extracting {len(property_ids)} properties from {selected_jurisdiction}..."):
                                    result = trigger_batch_extraction(property_ids)
                                    
                                    if result.get("status") == "processing":
                                        st.success(f"✅ Extraction started for {len(property_ids)} properties!")
                                        st.info("⏳ Processing in background. Results will be stored in the database.")
                                    else:
                                        st.error(f"❌ Failed: {result.get('message', 'Unknown error')}")
                            else:
                                st.warning(f"⚠️ This jurisdiction has {len(props_in_jurisdiction)} properties. Please use batch extraction with groups of 10 or less.")
                else:
                    st.warning("No properties found in supported jurisdictions")
            else:
                st.warning("No properties available")
        
        # Extraction status section
        st.divider()
        st.subheader("📊 Extraction Statistics")
        
        col1, col2, col3, col4 = st.columns(4)
        
        # Calculate extraction stats from properties
        if properties:
            total_props = len(properties)
            supported_count = sum(1 for p in properties if any(key.lower() in p.get("jurisdiction", "").lower() for key in cloud_supported.keys()))
            extracted_count = sum(1 for p in properties if p.get("amount_due") and p.get("amount_due") > 0)
            needs_extraction = supported_count - extracted_count
            
            with col1:
                st.metric("Total Properties", total_props)
            
            with col2:
                st.metric("Supported Properties", supported_count)
            
            with col3:
                st.metric("Already Extracted", extracted_count)
            
            with col4:
                st.metric("Needs Extraction", max(0, needs_extraction))
        
    else:
        st.error("❌ Could not connect to extraction service. Please check API connection.")
        st.info("API URL: " + API_URL)

# Tab 6: Trends & Insights
with tab6:
    st.header("📈 Trends & Insights")
    
    # Trend period selector
    trend_col1, trend_col2, trend_col3 = st.columns([2, 2, 1])
    
    with trend_col1:
        trend_days = st.select_slider(
            "Analysis Period",
            options=[7, 14, 30, 60, 90, 180, 365],
            value=30,
            format_func=lambda x: f"{x} days",
            key="trend_days"
        )
    
    with trend_col2:
        trend_jurisdiction = st.selectbox(
            "Filter by Jurisdiction",
            options=["All"] + (selected_jurisdictions if 'selected_jurisdictions' in locals() else []),
            key="trend_jurisdiction"
        )
    
    with trend_col3:
        if st.button("🔄 Refresh Trends", key="refresh_trends"):
            st.cache_data.clear()
            add_activity_log("Refreshed trend analysis", "info")
    
    # Fetch trend data
    trends_data = fetch_extraction_trends(
        days=trend_days,
        jurisdiction=None if trend_jurisdiction == "All" else trend_jurisdiction
    )
    
    if trends_data and trends_data.get("trends"):
        # Extraction Success Trends
        st.subheader("📊 Extraction Success Trends")
        
        trends_df = pd.DataFrame(trends_data["trends"])
        trends_df['date'] = pd.to_datetime(trends_df['date'])
        trends_df['total'] = trends_df['success'] + trends_df['failed']
        trends_df['success_rate'] = (trends_df['success'] / trends_df['total'] * 100).fillna(0)
        
        # Create subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=("Daily Extractions", "Success Rate Over Time", 
                          "Cumulative Extractions", "Success vs Failed"),
            specs=[[{"secondary_y": False}, {"secondary_y": False}],
                   [{"secondary_y": False}, {"type": "pie"}]]
        )
        
        # Daily extractions
        fig.add_trace(
            go.Bar(x=trends_df['date'], y=trends_df['success'], name='Successful', marker_color='green'),
            row=1, col=1
        )
        fig.add_trace(
            go.Bar(x=trends_df['date'], y=trends_df['failed'], name='Failed', marker_color='red'),
            row=1, col=1
        )
        
        # Success rate
        fig.add_trace(
            go.Scatter(x=trends_df['date'], y=trends_df['success_rate'], 
                      mode='lines+markers', name='Success Rate %',
                      line=dict(color='blue', width=2)),
            row=1, col=2
        )
        
        # Cumulative extractions
        trends_df['cumulative_success'] = trends_df['success'].cumsum()
        trends_df['cumulative_failed'] = trends_df['failed'].cumsum()
        
        fig.add_trace(
            go.Scatter(x=trends_df['date'], y=trends_df['cumulative_success'], 
                      mode='lines', name='Cumulative Success',
                      line=dict(color='green', width=2)),
            row=2, col=1
        )
        fig.add_trace(
            go.Scatter(x=trends_df['date'], y=trends_df['cumulative_failed'], 
                      mode='lines', name='Cumulative Failed',
                      line=dict(color='red', width=2)),
            row=2, col=1
        )
        
        # Pie chart
        total_success = trends_df['success'].sum()
        total_failed = trends_df['failed'].sum()
        fig.add_trace(
            go.Pie(labels=['Successful', 'Failed'], 
                  values=[total_success, total_failed],
                  marker_colors=['green', 'red']),
            row=2, col=2
        )
        
        fig.update_layout(height=800, showlegend=True, title_text=f"Extraction Analytics - Last {trend_days} Days")
        fig.update_xaxes(title_text="Date", row=1, col=1)
        fig.update_xaxes(title_text="Date", row=1, col=2)
        fig.update_xaxes(title_text="Date", row=2, col=1)
        fig.update_yaxes(title_text="Count", row=1, col=1)
        fig.update_yaxes(title_text="Success Rate (%)", row=1, col=2)
        fig.update_yaxes(title_text="Cumulative Count", row=2, col=1)
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Key Metrics
        st.subheader("📊 Key Performance Indicators")
        kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
        
        with kpi_col1:
            avg_daily = trends_df['total'].mean()
            st.metric("Avg Daily Extractions", f"{avg_daily:.1f}")
        
        with kpi_col2:
            overall_success_rate = (total_success / (total_success + total_failed) * 100) if (total_success + total_failed) > 0 else 0
            st.metric("Overall Success Rate", f"{overall_success_rate:.1f}%")
        
        with kpi_col3:
            peak_day = trends_df.loc[trends_df['total'].idxmax(), 'date'].strftime('%Y-%m-%d')
            peak_count = trends_df['total'].max()
            st.metric("Peak Day", peak_day, f"{peak_count} extractions")
        
        with kpi_col4:
            trend_direction = "📈" if trends_df.tail(7)['success_rate'].mean() > trends_df.head(7)['success_rate'].mean() else "📉"
            st.metric("7-Day Trend", trend_direction, "Success rate trend")
        
        # Insights
        st.subheader("💡 Automated Insights")
        
        insights = []
        
        # Best performing day
        best_day = trends_df.loc[trends_df['success_rate'].idxmax()]
        insights.append(f"✅ Best performance on {best_day['date'].strftime('%Y-%m-%d')} with {best_day['success_rate']:.1f}% success rate")
        
        # Worst performing day
        worst_day = trends_df.loc[trends_df['success_rate'].idxmin()]
        if worst_day['total'] > 0:
            insights.append(f"⚠️ Lowest performance on {worst_day['date'].strftime('%Y-%m-%d')} with {worst_day['success_rate']:.1f}% success rate")
        
        # Recent trend
        recent_avg = trends_df.tail(7)['success_rate'].mean()
        overall_avg = trends_df['success_rate'].mean()
        if recent_avg > overall_avg + 5:
            insights.append(f"📈 Recent performance ({recent_avg:.1f}%) is above average ({overall_avg:.1f}%)")
        elif recent_avg < overall_avg - 5:
            insights.append(f"📉 Recent performance ({recent_avg:.1f}%) is below average ({overall_avg:.1f}%)")
        
        for insight in insights:
            st.info(insight)
    else:
        st.info("No trend data available for the selected period")

# Tab 7: Admin Tools
with tab7:
    st.header("⚙️ Admin Tools")
    
    # Cache Management
    st.subheader("🗄️ Cache Management")
    
    cache_col1, cache_col2, cache_col3 = st.columns(3)
    
    with cache_col1:
        if st.button("Clear All Cache", key="clear_all_cache", type="secondary"):
            result = clear_api_cache()
            if result.get("cleared_entries"):
                st.success(f"Cleared {result['cleared_entries']} cache entries")
                add_activity_log(f"Cleared {result['cleared_entries']} cache entries", "success")
            st.cache_data.clear()
            st.success("Local cache cleared")
    
    with cache_col2:
        cache_pattern = st.text_input("Cache Pattern", placeholder="Enter pattern to clear specific cache", key="cache_pattern")
        if st.button("Clear Pattern", key="clear_pattern_cache"):
            if cache_pattern:
                result = clear_api_cache(pattern=cache_pattern)
                if result.get("cleared_entries"):
                    st.success(f"Cleared {result['cleared_entries']} matching entries")
                    add_activity_log(f"Cleared cache entries matching '{cache_pattern}'", "info")
    
    with cache_col3:
        cache_enabled = os.getenv("ENABLE_CACHE", "true").lower() == "true"
        st.metric("Cache Status", "Active" if cache_enabled else "Disabled")
        if hasattr(st.session_state, 'cache_data'):
            st.caption(f"Local cache size: {len(st.session_state.cache_data)} items")
    
    st.divider()
    
    # Webhook Configuration
    st.subheader("🔔 Webhook Configuration")
    
    webhook_col1, webhook_col2 = st.columns(2)
    
    with webhook_col1:
        webhook_url = st.text_input("Webhook URL", placeholder="https://your-webhook-endpoint.com", key="webhook_url")
        webhook_events = st.multiselect(
            "Events to Subscribe",
            options=["extraction_complete", "batch_complete", "error", "property_updated"],
            default=["extraction_complete", "batch_complete"],
            key="webhook_events"
        )
    
    with webhook_col2:
        if st.button("Register Webhook", key="register_webhook", type="primary"):
            if webhook_url and webhook_events:
                result = register_webhook(webhook_url, webhook_events)
                if result.get("status") == "registered":
                    st.success("Webhook registered successfully")
                    add_activity_log(f"Registered webhook: {webhook_url}", "success")
                else:
                    st.error(f"Failed to register webhook: {result.get('message', 'Unknown error')}")
            else:
                st.warning("Please provide webhook URL and select events")
    
    st.divider()
    
    # Performance Metrics
    st.subheader("📊 System Performance")
    
    # Get API health with detailed metrics
    status_code, health_data = check_api_health()
    
    if health_data:
        perf_col1, perf_col2, perf_col3, perf_col4 = st.columns(4)
        
        with perf_col1:
            st.metric("API Response Time", f"{health_data.get('response_time_ms', 0):.1f} ms")
        
        with perf_col2:
            st.metric("API Version", health_data.get('api_version', 'Unknown'))
        
        with perf_col3:
            cache_status = health_data.get('cache_status', 'Unknown')
            cache_color = "🟢" if cache_status in ["redis", "memory"] else "🔴"
            st.metric("Cache Type", f"{cache_color} {cache_status}")
        
        with perf_col4:
            metrics_enabled = health_data.get('metrics_enabled', False)
            metrics_color = "🟢" if metrics_enabled else "🔴"
            st.metric("Metrics", f"{metrics_color} {'Enabled' if metrics_enabled else 'Disabled'}")
    
    # Export Configuration
    st.divider()
    st.subheader("📤 Export Configuration")
    
    export_col1, export_col2 = st.columns(2)
    
    with export_col1:
        st.write("**Export Current Configuration**")
        
        # Safely extract serializable filter values
        def get_serializable_value(value):
            """Convert session state values to JSON-serializable format."""
            try:
                # Try to serialize to check if it's valid
                json.dumps(value)
                return value
            except (TypeError, ValueError):
                # Convert non-serializable objects to strings or None
                if hasattr(value, '__str__'):
                    return str(value)
                return None
        
        serializable_filters = {}
        for k, v in st.session_state.items():
            if k.startswith("filter_"):
                serializable_filters[k] = get_serializable_value(v)
        
        config_data = {
            "filters": serializable_filters,
            "presets": st.session_state.filter_presets,
            "settings": {
                "auto_refresh": st.session_state.auto_refresh,
                "refresh_interval": st.session_state.refresh_interval,
                "dark_mode": st.session_state.dark_mode
            }
        }
        
        config_json = json.dumps(config_data, indent=2)
        st.download_button(
            label="📥 Download Config",
            data=config_json,
            file_name=f"dashboard_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
    
    with export_col2:
        st.write("**Import Configuration**")
        uploaded_config = st.file_uploader("Choose config file", type="json", key="config_upload")
        
        if uploaded_config is not None:
            try:
                config_data = json.load(uploaded_config)
                if st.button("Apply Configuration", key="apply_config"):
                    # Apply filters
                    for key, value in config_data.get("filters", {}).items():
                        st.session_state[key] = value
                    # Apply presets
                    st.session_state.filter_presets = config_data.get("presets", {})
                    # Apply settings
                    settings = config_data.get("settings", {})
                    st.session_state.auto_refresh = settings.get("auto_refresh", False)
                    st.session_state.refresh_interval = settings.get("refresh_interval", 30)
                    st.session_state.dark_mode = settings.get("dark_mode", False)
                    
                    st.success("Configuration applied successfully")
                    add_activity_log("Imported dashboard configuration", "success")
                    st.rerun()
            except Exception as e:
                st.error(f"Error loading configuration: {e}")

# Tab 8: Activity Log
with tab8:
    st.header("📋 Activity Log")
    
    # Activity log controls
    log_col1, log_col2, log_col3 = st.columns([2, 2, 1])
    
    with log_col1:
        log_filter = st.selectbox(
            "Filter by Type",
            options=["All", "info", "success", "warning", "error"],
            key="log_filter"
        )
    
    with log_col2:
        log_search = st.text_input("Search logs...", key="log_search")
    
    with log_col3:
        if st.button("Clear Log", key="clear_log"):
            st.session_state.activity_log = []
            st.success("Activity log cleared")
    
    # Display activity log
    if st.session_state.activity_log:
        st.subheader(f"Recent Activities ({len(st.session_state.activity_log)} entries)")
        
        # Filter logs
        filtered_logs = st.session_state.activity_log
        if log_filter != "All":
            filtered_logs = [log for log in filtered_logs if log.get("type") == log_filter]
        if log_search:
            filtered_logs = [log for log in filtered_logs if log_search.lower() in log.get("message", "").lower()]
        
        # Create activity feed
        st.markdown('<div class="activity-feed">', unsafe_allow_html=True)
        
        for entry in filtered_logs[:50]:  # Show last 50 entries
            timestamp = datetime.fromisoformat(entry['timestamp']).strftime('%H:%M:%S')
            message = entry['message']
            entry_type = entry.get('type', 'info')
            
            # Color code by type
            type_colors = {
                'info': '#1f77b4',
                'success': '#28a745',
                'warning': '#ffc107',
                'error': '#dc3545'
            }
            color = type_colors.get(entry_type, '#6c757d')
            
            activity_html = f"""
            <div class="activity-item" style="border-left-color: {color};">
                <strong>{timestamp}</strong> - {message}
                <span class="status-badge" style="background-color: {color}; color: white;">{entry_type}</span>
            </div>
            """
            st.markdown(activity_html, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Export activity log
        st.divider()
        if st.button("📥 Export Activity Log", key="export_activity_log"):
            log_df = pd.DataFrame(st.session_state.activity_log)
            csv = log_df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"activity_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
    else:
        st.info("No activity recorded yet. Start using the dashboard to see activities here.")
    
    # Real-time extraction progress
    if st.session_state.extraction_progress:
        st.divider()
        st.subheader("🔄 Active Extractions")
        
        for prop_id, progress in st.session_state.extraction_progress.items():
            progress_col1, progress_col2 = st.columns([3, 1])
            
            with progress_col1:
                st.write(f"**Property:** {progress.get('name', prop_id)}")
                st.progress(progress.get('percent', 0) / 100)
                st.caption(progress.get('status', 'Processing...'))
            
            with progress_col2:
                if progress.get('percent', 0) >= 100:
                    st.success("✅ Complete")
                else:
                    st.info(f"{progress.get('percent', 0)}%")

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

# Signal to the entrypoint that the dashboard rendered successfully
try:
    import os as _os
    _os.environ["DASHBOARD_RENDERED"] = "1"
except Exception:
    # Environment may be restricted; safe to ignore as this only affects fallback UI
    pass
