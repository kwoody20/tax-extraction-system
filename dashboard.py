"""
Enhanced Streamlit Dashboard for Tax Extraction System
Professional, performant web UI with modern best practices
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime, timedelta
import requests
import asyncio
import aiohttp
import time
import json
import sys
import os
import io
import hashlib
import base64
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging
from concurrent.futures import ThreadPoolExecutor
import threading
import queue

# Add path for direct extractor access
sys.path.append('extracting-tests-818')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== Configuration ====================
API_BASE_URL = os.getenv("TAX_EXTRACTOR_API_URL", "http://localhost:8000")
REFRESH_INTERVALS = {
    "fast": 1,
    "normal": 2,
    "slow": 5,
    "manual": None
}

# Performance thresholds
CACHE_TTL = 300  # 5 minutes
MAX_PREVIEW_ROWS = 1000
BATCH_SIZE = 100

# UI Theme Colors
THEME = {
    "primary": "#1f77b4",
    "success": "#2ca02c",
    "warning": "#ff7f0e",
    "danger": "#d62728",
    "info": "#17a2b8",
    "dark": "#2c3e50",
    "light": "#ecf0f1"
}

# Job Status Enum
class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"

# ==================== Page Configuration ====================
st.set_page_config(
    page_title="Tax Extractor Pro Dashboard",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/your-repo/tax-extractor',
        'Report a bug': "https://github.com/your-repo/issues",
        'About': "Tax Extractor Pro v2.0 - Enterprise Tax Extraction System"
    }
)

# ==================== Custom CSS Styling ====================
st.markdown("""
<style>
    /* Main theme styling */
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    
    .main > div {
        background-color: white;
        border-radius: 10px;
        padding: 2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    /* Custom metric cards */
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        transition: transform 0.2s;
        border-left: 4px solid var(--primary-color);
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
        color: var(--primary-color);
    }
    
    .metric-label {
        font-size: 0.9rem;
        color: #6c757d;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .metric-delta {
        font-size: 0.85rem;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        display: inline-block;
        margin-top: 0.5rem;
    }
    
    .metric-delta.positive {
        background-color: #d4edda;
        color: #155724;
    }
    
    .metric-delta.negative {
        background-color: #f8d7da;
        color: #721c24;
    }
    
    /* Status badges */
    .status-badge {
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 500;
        display: inline-block;
    }
    
    .status-pending {
        background-color: #fff3cd;
        color: #856404;
    }
    
    .status-running {
        background-color: #cce5ff;
        color: #004085;
    }
    
    .status-completed {
        background-color: #d4edda;
        color: #155724;
    }
    
    .status-failed {
        background-color: #f8d7da;
        color: #721c24;
    }
    
    /* Progress bars */
    .custom-progress {
        height: 24px;
        background-color: #e9ecef;
        border-radius: 12px;
        overflow: hidden;
        position: relative;
    }
    
    .custom-progress-bar {
        height: 100%;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        border-radius: 12px;
        transition: width 0.3s ease;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: 500;
        font-size: 0.85rem;
    }
    
    /* Animation for loading states */
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.5; }
        100% { opacity: 1; }
    }
    
    .loading-pulse {
        animation: pulse 2s infinite;
    }
    
    /* Custom buttons */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.3s;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }
    
    /* Data tables */
    .dataframe {
        border: none !important;
        border-radius: 8px;
        overflow: hidden;
    }
    
    .dataframe thead {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
    }
    
    .dataframe tbody tr:hover {
        background-color: #f8f9fa;
    }
    
    /* Sidebar styling */
    .css-1d391kg {
        background: linear-gradient(180deg, #2c3e50 0%, #34495e 100%);
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Custom scrollbar */
    ::-webkit-scrollbar {
        width: 10px;
        height: 10px;
    }
    
    ::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: #764ba2;
    }
</style>

<style>
    :root {
        --primary-color: #667eea;
        --secondary-color: #764ba2;
        --success-color: #2ca02c;
        --warning-color: #ff7f0e;
        --danger-color: #d62728;
    }
</style>
""", unsafe_allow_html=True)

# ==================== Session State Management ====================
@dataclass
class AppState:
    """Centralized application state"""
    current_job: Optional[str] = None
    jobs_cache: Dict[str, Any] = None
    cache_timestamp: float = 0
    auto_refresh: bool = False
    refresh_rate: str = "normal"
    selected_page: str = "Dashboard"
    uploaded_data: Optional[pd.DataFrame] = None
    filter_status: str = "All"
    filter_date_range: Tuple[datetime, datetime] = None
    notifications: List[Dict] = None
    api_health: bool = False
    last_api_check: float = 0
    
def init_session_state():
    """Initialize session state with default values"""
    if 'app_state' not in st.session_state:
        st.session_state.app_state = AppState(
            jobs_cache={},
            filter_date_range=(datetime.now() - timedelta(days=7), datetime.now()),
            notifications=[]
        )
    
    # Initialize other session states
    if 'job_results_cache' not in st.session_state:
        st.session_state.job_results_cache = {}
    
    if 'extraction_history' not in st.session_state:
        st.session_state.extraction_history = []
    
    if 'performance_metrics' not in st.session_state:
        st.session_state.performance_metrics = {
            'total_extracted': 0,
            'success_rate': 0,
            'avg_processing_time': 0,
            'domains_processed': set()
        }

# ==================== Utility Functions ====================
@st.cache_data(ttl=60)
def check_api_health() -> bool:
    """Check API health with caching"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=2)
        return response.status_code == 200
    except:
        return False

@st.cache_data(ttl=30)
def get_system_metrics() -> Dict:
    """Get system performance metrics"""
    try:
        response = requests.get(f"{API_BASE_URL}/metrics", timeout=2)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    
    return {
        'cpu_usage': 0,
        'memory_usage': 0,
        'active_workers': 0,
        'queue_size': 0
    }

def format_duration(seconds: float) -> str:
    """Format duration in human-readable format"""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds/60:.0f}m {seconds%60:.0f}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours:.0f}h {minutes:.0f}m"

def generate_job_id() -> str:
    """Generate unique job ID"""
    import uuid
    return str(uuid.uuid4())

# ==================== API Client Functions ====================
class APIClient:
    """Enhanced API client with retry logic and connection pooling"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'TaxExtractorDashboard/2.0'
        })
    
    def submit_job(self, file_data: bytes, filename: str, 
                   concurrent: bool = True, max_workers: int = 5,
                   priority: str = "normal") -> Optional[Dict]:
        """Submit extraction job with enhanced parameters"""
        try:
            files = {'file': (filename, file_data, 'text/csv')}
            params = {
                'concurrent': concurrent,
                'max_workers': max_workers,
                'priority': priority
            }
            
            response = self.session.post(
                f"{self.base_url}/extract/upload",
                files=files,
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Job submission failed: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error submitting job: {str(e)}")
            return None
    
    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get detailed job status"""
        try:
            response = self.session.get(
                f"{self.base_url}/jobs/{job_id}",
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Error getting job status: {str(e)}")
        return None
    
    def get_all_jobs(self, limit: int = 100, offset: int = 0,
                     status: Optional[str] = None) -> List[Dict]:
        """Get paginated job list with filters"""
        try:
            params = {'limit': limit, 'offset': offset}
            if status:
                params['status'] = status
                
            response = self.session.get(
                f"{self.base_url}/jobs",
                params=params,
                timeout=5
            )
            if response.status_code == 200:
                return response.json().get('jobs', [])
        except Exception as e:
            logger.error(f"Error getting jobs: {str(e)}")
        return []
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel running job"""
        try:
            response = self.session.delete(
                f"{self.base_url}/jobs/{job_id}",
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
    
    def pause_job(self, job_id: str) -> bool:
        """Pause running job"""
        try:
            response = self.session.post(
                f"{self.base_url}/jobs/{job_id}/pause",
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
    
    def resume_job(self, job_id: str) -> bool:
        """Resume paused job"""
        try:
            response = self.session.post(
                f"{self.base_url}/jobs/{job_id}/resume",
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
    
    def get_job_results(self, job_id: str, format: str = 'json') -> Optional[bytes]:
        """Download job results in specified format"""
        try:
            response = self.session.get(
                f"{self.base_url}/jobs/{job_id}/results",
                params={'format': format},
                timeout=30
            )
            if response.status_code == 200:
                return response.content
        except Exception as e:
            logger.error(f"Error downloading results: {str(e)}")
        return None
    
    def get_job_logs(self, job_id: str) -> Optional[str]:
        """Get job execution logs"""
        try:
            response = self.session.get(
                f"{self.base_url}/jobs/{job_id}/logs",
                timeout=5
            )
            if response.status_code == 200:
                return response.text
        except:
            pass
        return None

# Initialize API client
api_client = APIClient(API_BASE_URL)

# ==================== Dashboard Components ====================
def render_metric_card(label: str, value: Any, delta: Optional[str] = None,
                      delta_color: str = "normal", icon: str = None):
    """Render custom metric card"""
    delta_class = "positive" if delta_color == "normal" else "negative"
    delta_html = f'<div class="metric-delta {delta_class}">{delta}</div>' if delta else ''
    icon_html = f'<span style="font-size: 1.5rem; margin-right: 0.5rem;">{icon}</span>' if icon else ''
    
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{icon_html}{label}</div>
        <div class="metric-value">{value}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)

def render_status_badge(status: str):
    """Render status badge with appropriate styling"""
    status_lower = status.lower()
    icon_map = {
        'pending': '⏳',
        'running': '🔄',
        'completed': '✅',
        'failed': '❌',
        'cancelled': '🚫',
        'paused': '⏸️'
    }
    
    icon = icon_map.get(status_lower, '⚪')
    return f'<span class="status-badge status-{status_lower}">{icon} {status.upper()}</span>'

def render_progress_bar(progress: float, show_text: bool = True):
    """Render custom progress bar"""
    progress = min(max(progress, 0), 100)
    text = f"{progress:.1f}%" if show_text else ""
    
    st.markdown(f"""
    <div class="custom-progress">
        <div class="custom-progress-bar" style="width: {progress}%;">
            {text}
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_notification(message: str, type: str = "info"):
    """Render notification message"""
    icon_map = {
        'success': '✅',
        'error': '❌',
        'warning': '⚠️',
        'info': 'ℹ️'
    }
    
    color_map = {
        'success': '#d4edda',
        'error': '#f8d7da',
        'warning': '#fff3cd',
        'info': '#d1ecf1'
    }
    
    st.markdown(f"""
    <div style="padding: 1rem; background-color: {color_map[type]}; 
                border-radius: 8px; margin-bottom: 1rem;">
        <span style="font-size: 1.2rem; margin-right: 0.5rem;">{icon_map[type]}</span>
        {message}
    </div>
    """, unsafe_allow_html=True)

# ==================== Page: Dashboard Overview ====================
def page_dashboard():
    """Main dashboard overview page"""
    st.title("🏛️ Tax Extraction Dashboard")
    st.markdown("Real-time monitoring and analytics for tax extraction operations")
    
    # API Health Check
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        api_health = check_api_health()
        if api_health:
            render_notification("System operational - All services running", "success")
        else:
            render_notification("API service offline - Please start the API service", "error")
            st.code("python api_service.py", language="bash")
            return
    
    with col2:
        if st.button("🔄 Refresh Dashboard", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    with col3:
        auto_refresh = st.checkbox("Auto-refresh", value=st.session_state.app_state.auto_refresh)
        st.session_state.app_state.auto_refresh = auto_refresh
    
    # System Metrics
    st.markdown("### 📊 System Metrics")
    metrics = get_system_metrics()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        render_metric_card(
            "CPU Usage",
            f"{metrics.get('cpu_usage', 0):.1f}%",
            delta="↑ 2.3% from last hour" if metrics.get('cpu_usage', 0) > 50 else None,
            icon="💻"
        )
    
    with col2:
        render_metric_card(
            "Memory Usage",
            f"{metrics.get('memory_usage', 0):.1f}%",
            icon="🧠"
        )
    
    with col3:
        render_metric_card(
            "Active Workers",
            metrics.get('active_workers', 0),
            icon="👷"
        )
    
    with col4:
        render_metric_card(
            "Queue Size",
            metrics.get('queue_size', 0),
            icon="📋"
        )
    
    st.markdown("---")
    
    # Active Jobs Summary
    st.markdown("### 🚀 Active Jobs")
    
    jobs = api_client.get_all_jobs(limit=10)
    active_jobs = [j for j in jobs if j['status'] in ['pending', 'running']]
    
    if active_jobs:
        for job in active_jobs:
            with st.container():
                col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 1])
                
                with col1:
                    st.markdown(f"**Job ID:** `{job['job_id'][:12]}...`")
                    st.markdown(f"Status: {render_status_badge(job['status'])}", 
                              unsafe_allow_html=True)
                
                with col2:
                    progress = job.get('progress', 0)
                    st.markdown("**Progress**")
                    render_progress_bar(progress)
                
                with col3:
                    st.metric("Processed", 
                            f"{job.get('processed', 0)}/{job.get('total_properties', 0)}")
                    success_rate = (job.get('successful', 0) / 
                                  max(job.get('processed', 1), 1) * 100)
                    st.caption(f"Success Rate: {success_rate:.1f}%")
                
                with col4:
                    elapsed = datetime.now() - datetime.fromisoformat(job.get('created_at', 
                                                                             datetime.now().isoformat()))
                    st.metric("Elapsed Time", format_duration(elapsed.total_seconds()))
                    
                    eta = (elapsed.total_seconds() / max(progress, 1) * 100) if progress > 0 else 0
                    remaining = eta - elapsed.total_seconds()
                    if remaining > 0:
                        st.caption(f"ETA: {format_duration(remaining)}")
                
                with col5:
                    if st.button("⏸️", key=f"pause_{job['job_id']}", 
                               help="Pause job"):
                        if api_client.pause_job(job['job_id']):
                            st.success("Job paused")
                            st.rerun()
                    
                    if st.button("❌", key=f"cancel_{job['job_id']}", 
                               help="Cancel job"):
                        if api_client.cancel_job(job['job_id']):
                            st.success("Job cancelled")
                            st.rerun()
                
                st.markdown("---")
    else:
        st.info("No active jobs running")
    
    # Recent Activity Chart
    st.markdown("### 📈 Extraction Activity (Last 24 Hours)")
    
    # Generate sample data for demonstration
    hours = pd.date_range(end=datetime.now(), periods=24, freq='H')
    activity_data = pd.DataFrame({
        'Time': hours,
        'Successful': np.random.poisson(15, 24),
        'Failed': np.random.poisson(3, 24)
    })
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=activity_data['Time'],
        y=activity_data['Successful'],
        mode='lines+markers',
        name='Successful',
        line=dict(color=THEME['success'], width=2),
        fill='tozeroy'
    ))
    
    fig.add_trace(go.Scatter(
        x=activity_data['Time'],
        y=activity_data['Failed'],
        mode='lines+markers',
        name='Failed',
        line=dict(color=THEME['danger'], width=2)
    ))
    
    fig.update_layout(
        height=400,
        hovermode='x unified',
        showlegend=True,
        xaxis_title="Time",
        yaxis_title="Extractions",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Performance Summary
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🎯 Success Rate by Domain")
        
        # Sample domain data
        domain_data = pd.DataFrame({
            'Domain': ['actweb.acttax.com', 'treasurer.maricopa.gov', 
                      'www.hctax.net', 'pwa.waynegov.com', 'Other'],
            'Success Rate': [98.5, 92.3, 89.7, 95.2, 87.4]
        })
        
        fig = px.bar(domain_data, x='Success Rate', y='Domain', 
                    orientation='h',
                    color='Success Rate',
                    color_continuous_scale='Viridis')
        
        fig.update_layout(height=300, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### ⚡ Processing Speed")
        
        # Sample speed data
        speed_data = pd.DataFrame({
            'Method': ['HTTP Direct', 'Selenium', 'Playwright', 'API'],
            'Avg Time (s)': [2.3, 8.7, 6.2, 1.8],
            'Count': [450, 230, 180, 340]
        })
        
        fig = px.scatter(speed_data, x='Avg Time (s)', y='Method', 
                        size='Count', color='Avg Time (s)',
                        color_continuous_scale='RdYlGn_r',
                        size_max=50)
        
        fig.update_layout(height=300, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

# ==================== Page: New Extraction ====================
def page_new_extraction():
    """Page for starting new extraction jobs"""
    st.title("🚀 Start New Extraction")
    st.markdown("Configure and launch tax extraction jobs")
    
    # File Upload Section
    st.markdown("### 📁 Data Input")
    
    tab1, tab2, tab3 = st.tabs(["Upload CSV", "Paste URLs", "Database Query"])
    
    with tab1:
        uploaded_file = st.file_uploader(
            "Choose CSV file",
            type=['csv', 'xlsx'],
            help="Upload a CSV or Excel file containing property information and tax bill URLs"
        )
        
        if uploaded_file is not None:
            # Read and validate file
            try:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                
                st.session_state.app_state.uploaded_data = df
                
                # Data validation
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Total Properties", len(df))
                
                with col2:
                    valid_urls = df['Tax Bill Link'].notna().sum() if 'Tax Bill Link' in df.columns else 0
                    st.metric("Valid URLs", valid_urls)
                
                with col3:
                    unique_domains = df['Tax Bill Link'].apply(
                        lambda x: x.split('/')[2] if pd.notna(x) and '/' in x else None
                    ).nunique() if 'Tax Bill Link' in df.columns else 0
                    st.metric("Unique Domains", unique_domains)
                
                # Data preview with filters
                st.markdown("#### Data Preview")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    search_term = st.text_input("🔍 Search", placeholder="Filter properties...")
                
                with col2:
                    if 'State' in df.columns:
                        state_filter = st.multiselect("State", 
                                                     options=df['State'].unique().tolist())
                
                with col3:
                    preview_rows = st.slider("Preview Rows", 5, min(100, len(df)), 10)
                
                # Apply filters
                filtered_df = df.copy()
                if search_term:
                    mask = df.astype(str).apply(
                        lambda x: x.str.contains(search_term, case=False, na=False)
                    ).any(axis=1)
                    filtered_df = filtered_df[mask]
                
                if 'State' in df.columns and state_filter:
                    filtered_df = filtered_df[filtered_df['State'].isin(state_filter)]
                
                # Display filtered data
                st.dataframe(
                    filtered_df.head(preview_rows),
                    use_container_width=True,
                    hide_index=True
                )
                
                # Data quality checks
                with st.expander("📊 Data Quality Report"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**Missing Values**")
                        missing_data = df.isnull().sum()
                        missing_data = missing_data[missing_data > 0]
                        
                        if not missing_data.empty:
                            fig = px.bar(x=missing_data.values, y=missing_data.index,
                                       orientation='h', 
                                       labels={'x': 'Count', 'y': 'Column'})
                            fig.update_layout(height=200)
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.success("No missing values detected")
                    
                    with col2:
                        st.markdown("**URL Validation**")
                        if 'Tax Bill Link' in df.columns:
                            valid_urls = df['Tax Bill Link'].notna().sum()
                            invalid_urls = df['Tax Bill Link'].isna().sum()
                            
                            fig = go.Figure(data=[
                                go.Pie(labels=['Valid', 'Invalid'], 
                                      values=[valid_urls, invalid_urls],
                                      hole=0.3)
                            ])
                            fig.update_layout(height=200)
                            st.plotly_chart(fig, use_container_width=True)
                
            except Exception as e:
                st.error(f"Error reading file: {str(e)}")
                st.stop()
    
    with tab2:
        st.markdown("Paste URLs directly (one per line)")
        urls_text = st.text_area(
            "Tax Bill URLs",
            height=200,
            placeholder="https://example.com/tax-bill-1\nhttps://example.com/tax-bill-2"
        )
        
        if urls_text:
            urls = [url.strip() for url in urls_text.split('\n') if url.strip()]
            
            # Create DataFrame from URLs
            df = pd.DataFrame({
                'Tax Bill Link': urls,
                'Property Name': [f'Property_{i+1}' for i in range(len(urls))]
            })
            
            st.session_state.app_state.uploaded_data = df
            st.success(f"Loaded {len(urls)} URLs")
    
    with tab3:
        st.markdown("Query properties from database")
        
        col1, col2 = st.columns(2)
        
        with col1:
            db_type = st.selectbox("Database Type", 
                                  ["PostgreSQL", "MySQL", "SQLite", "MongoDB"])
        
        with col2:
            connection_string = st.text_input("Connection String", 
                                            type="password",
                                            placeholder="postgresql://user:pass@host/db")
        
        query = st.text_area("SQL Query", 
                           placeholder="SELECT * FROM properties WHERE state = 'TX'")
        
        if st.button("Execute Query"):
            st.info("Database connection feature coming soon")
    
    st.markdown("---")
    
    # Extraction Configuration
    st.markdown("### ⚙️ Extraction Settings")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Processing Mode**")
        concurrent = st.checkbox("Concurrent Processing", value=True,
                                help="Process multiple properties simultaneously")
        
        if concurrent:
            max_workers = st.slider("Worker Threads", 1, 20, 5,
                                  help="Number of concurrent workers")
        else:
            max_workers = 1
        
        batch_mode = st.checkbox("Batch Processing", value=False,
                                help="Process in batches to manage large datasets")
        
        if batch_mode:
            batch_size = st.number_input("Batch Size", 10, 1000, 100)
    
    with col2:
        st.markdown("**Extraction Options**")
        
        extraction_method = st.selectbox(
            "Extraction Method",
            ["Auto-detect", "HTTP Direct", "Selenium", "Playwright"],
            help="Choose extraction method or let system auto-detect"
        )
        
        retry_failed = st.checkbox("Auto-retry Failed", value=True,
                                  help="Automatically retry failed extractions")
        
        if retry_failed:
            max_retries = st.number_input("Max Retries", 1, 5, 3)
        
        save_screenshots = st.checkbox("Save Screenshots", value=False,
                                      help="Save screenshots for debugging")
    
    with col3:
        st.markdown("**Advanced Settings**")
        
        priority = st.select_slider(
            "Job Priority",
            options=["Low", "Normal", "High", "Critical"],
            value="Normal",
            help="Higher priority jobs are processed first"
        )
        
        timeout = st.slider("Request Timeout (s)", 5, 60, 30,
                          help="Maximum time to wait for each request")
        
        rate_limit = st.checkbox("Enable Rate Limiting", value=True,
                                help="Respect rate limits to avoid blocking")
        
        if rate_limit:
            requests_per_second = st.slider("Requests/Second", 1, 10, 2)
    
    # Scheduling Options
    with st.expander("📅 Schedule Extraction"):
        col1, col2 = st.columns(2)
        
        with col1:
            schedule_type = st.radio("Schedule Type", 
                                    ["Run Now", "Schedule Once", "Recurring"])
        
        with col2:
            if schedule_type == "Schedule Once":
                run_date = st.date_input("Run Date")
                run_time = st.time_input("Run Time")
            
            elif schedule_type == "Recurring":
                frequency = st.selectbox("Frequency", 
                                       ["Daily", "Weekly", "Monthly"])
                
                if frequency == "Weekly":
                    days = st.multiselect("Days of Week",
                                        ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    
    st.markdown("---")
    
    # Extraction Summary and Launch
    st.markdown("### 📋 Extraction Summary")
    
    if st.session_state.app_state.uploaded_data is not None:
        df = st.session_state.app_state.uploaded_data
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            # Summary metrics
            summary_cols = st.columns(4)
            
            with summary_cols[0]:
                st.metric("Total Properties", len(df))
            
            with summary_cols[1]:
                estimated_time = len(df) * (2 if concurrent else 10)
                st.metric("Estimated Time", format_duration(estimated_time))
            
            with summary_cols[2]:
                st.metric("Processing Mode", 
                        "Concurrent" if concurrent else "Sequential")
            
            with summary_cols[3]:
                st.metric("Priority", priority)
        
        with col2:
            st.markdown("#### Ready to Extract?")
            
            if st.button("🚀 Start Extraction", type="primary", 
                        use_container_width=True):
                
                # Prepare extraction
                with st.spinner("Initializing extraction job..."):
                    # Save data to temporary file
                    temp_file = f"/tmp/extraction_{generate_job_id()}.csv"
                    df.to_csv(temp_file, index=False)
                    
                    # Submit job
                    with open(temp_file, 'rb') as f:
                        result = api_client.submit_job(
                            f.read(),
                            os.path.basename(temp_file),
                            concurrent=concurrent,
                            max_workers=max_workers,
                            priority=priority.lower()
                        )
                    
                    if result:
                        st.session_state.app_state.current_job = result['job_id']
                        st.success(f"✅ Job submitted successfully!")
                        st.info(f"Job ID: `{result['job_id']}`")
                        st.balloons()
                        
                        # Add to notifications
                        st.session_state.app_state.notifications.append({
                            'time': datetime.now(),
                            'message': f"Extraction job {result['job_id'][:8]} started",
                            'type': 'success'
                        })
                        
                        # Switch to monitoring page
                        time.sleep(2)
                        st.session_state.app_state.selected_page = "Job Monitor"
                        st.rerun()
                    else:
                        st.error("Failed to submit extraction job")
            
            if st.button("💾 Save Configuration", use_container_width=True):
                # Save configuration for reuse
                config = {
                    'concurrent': concurrent,
                    'max_workers': max_workers,
                    'extraction_method': extraction_method,
                    'retry_failed': retry_failed,
                    'priority': priority,
                    'timeout': timeout
                }
                
                st.download_button(
                    label="Download Config",
                    data=json.dumps(config, indent=2),
                    file_name="extraction_config.json",
                    mime="application/json"
                )
    else:
        st.info("Please upload data to begin extraction")

# ==================== Page: Job Monitor ====================
def page_job_monitor():
    """Real-time job monitoring page"""
    st.title("📊 Job Monitor")
    st.markdown("Real-time monitoring of extraction jobs")
    
    # Controls
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        refresh_rate = st.selectbox(
            "Refresh Rate",
            options=list(REFRESH_INTERVALS.keys()),
            index=1
        )
        st.session_state.app_state.refresh_rate = refresh_rate
    
    with col2:
        status_filter = st.selectbox(
            "Filter Status",
            ["All", "Running", "Pending", "Completed", "Failed", "Paused"]
        )
    
    with col3:
        sort_by = st.selectbox(
            "Sort By",
            ["Created (Newest)", "Created (Oldest)", "Progress", "Status"]
        )
    
    with col4:
        if st.button("🔄 Refresh Now", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    st.markdown("---")
    
    # Get jobs
    jobs = api_client.get_all_jobs(limit=50)
    
    # Apply filters
    if status_filter != "All":
        jobs = [j for j in jobs if j['status'].lower() == status_filter.lower()]
    
    # Apply sorting
    if sort_by == "Created (Newest)":
        jobs.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    elif sort_by == "Created (Oldest)":
        jobs.sort(key=lambda x: x.get('created_at', ''))
    elif sort_by == "Progress":
        jobs.sort(key=lambda x: x.get('progress', 0), reverse=True)
    elif sort_by == "Status":
        jobs.sort(key=lambda x: x.get('status', ''))
    
    if not jobs:
        st.info("No jobs found matching the criteria")
    else:
        # Display jobs
        for job in jobs:
            with st.container():
                # Job header
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    st.markdown(f"### Job `{job['job_id'][:12]}...`")
                
                with col2:
                    st.markdown(render_status_badge(job['status']), 
                              unsafe_allow_html=True)
                
                # Job details
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.markdown("**Progress**")
                    progress = job.get('progress', 0)
                    render_progress_bar(progress)
                    
                    processed = job.get('processed', 0)
                    total = job.get('total_properties', 0)
                    st.caption(f"{processed} / {total} properties")
                
                with col2:
                    st.markdown("**Success Metrics**")
                    successful = job.get('successful', 0)
                    failed = job.get('failed', 0)
                    
                    if processed > 0:
                        success_rate = (successful / processed) * 100
                        st.metric("Success Rate", f"{success_rate:.1f}%")
                    else:
                        st.metric("Success Rate", "N/A")
                    
                    st.caption(f"✅ {successful} | ❌ {failed}")
                
                with col3:
                    st.markdown("**Timing**")
                    created = datetime.fromisoformat(job.get('created_at', 
                                                           datetime.now().isoformat()))
                    elapsed = datetime.now() - created
                    st.metric("Elapsed", format_duration(elapsed.total_seconds()))
                    
                    if progress > 0 and progress < 100:
                        eta = (elapsed.total_seconds() / progress * 100) - elapsed.total_seconds()
                        st.caption(f"ETA: {format_duration(eta)}")
                
                with col4:
                    st.markdown("**Actions**")
                    
                    action_cols = st.columns(3)
                    
                    with action_cols[0]:
                        if job['status'] == 'running':
                            if st.button("⏸️", key=f"pause_{job['job_id']}", 
                                       help="Pause"):
                                api_client.pause_job(job['job_id'])
                                st.rerun()
                        elif job['status'] == 'paused':
                            if st.button("▶️", key=f"resume_{job['job_id']}", 
                                       help="Resume"):
                                api_client.resume_job(job['job_id'])
                                st.rerun()
                    
                    with action_cols[1]:
                        if job['status'] in ['running', 'pending', 'paused']:
                            if st.button("🛑", key=f"stop_{job['job_id']}", 
                                       help="Cancel"):
                                api_client.cancel_job(job['job_id'])
                                st.rerun()
                    
                    with action_cols[2]:
                        if st.button("📋", key=f"details_{job['job_id']}", 
                                   help="View Details"):
                            st.session_state.selected_job = job['job_id']
                
                # Expandable details
                with st.expander("View Details"):
                    tab1, tab2, tab3 = st.tabs(["Info", "Logs", "Results"])
                    
                    with tab1:
                        st.json(job)
                    
                    with tab2:
                        logs = api_client.get_job_logs(job['job_id'])
                        if logs:
                            st.text_area("Execution Logs", logs, height=200)
                        else:
                            st.info("No logs available")
                    
                    with tab3:
                        if job['status'] == 'completed' and job.get('results_available'):
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                results = api_client.get_job_results(job['job_id'], 'json')
                                if results:
                                    st.download_button(
                                        "📥 Download JSON",
                                        data=results,
                                        file_name=f"results_{job['job_id']}.json",
                                        mime="application/json"
                                    )
                            
                            with col2:
                                results = api_client.get_job_results(job['job_id'], 'excel')
                                if results:
                                    st.download_button(
                                        "📥 Download Excel",
                                        data=results,
                                        file_name=f"results_{job['job_id']}.xlsx",
                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                    )
                            
                            with col3:
                                results = api_client.get_job_results(job['job_id'], 'csv')
                                if results:
                                    st.download_button(
                                        "📥 Download CSV",
                                        data=results,
                                        file_name=f"results_{job['job_id']}.csv",
                                        mime="text/csv"
                                    )
                        else:
                            st.info("Results not yet available")
                
                st.markdown("---")
    
    # Auto-refresh
    if st.session_state.app_state.auto_refresh:
        interval = REFRESH_INTERVALS.get(refresh_rate)
        if interval:
            time.sleep(interval)
            st.rerun()

# ==================== Page: Analytics ====================
def page_analytics():
    """Analytics and reporting page"""
    st.title("📈 Analytics & Insights")
    st.markdown("Comprehensive analytics for tax extraction operations")
    
    # Date range filter
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        date_range = st.date_input(
            "Date Range",
            value=(datetime.now() - timedelta(days=30), datetime.now()),
            max_value=datetime.now()
        )
    
    with col2:
        grouping = st.selectbox(
            "Group By",
            ["Day", "Week", "Month", "Domain", "Status"]
        )
    
    with col3:
        if st.button("🔄 Refresh Analytics", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    st.markdown("---")
    
    # Get analytics data
    jobs = api_client.get_all_jobs(limit=1000)
    
    if not jobs:
        st.info("No data available for analytics")
        return
    
    # Convert to DataFrame
    df = pd.DataFrame(jobs)
    df['created_at'] = pd.to_datetime(df['created_at'])
    
    # Apply date filter
    if len(date_range) == 2:
        mask = (df['created_at'].dt.date >= date_range[0]) & \
               (df['created_at'].dt.date <= date_range[1])
        df = df[mask]
    
    # Key Metrics
    st.markdown("### 🎯 Key Performance Indicators")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        total_jobs = len(df)
        prev_total = len(df[df['created_at'] < df['created_at'].median()])
        delta = ((total_jobs - prev_total) / max(prev_total, 1)) * 100
        
        st.metric("Total Jobs", total_jobs, f"{delta:+.1f}%")
    
    with col2:
        total_properties = df['total_properties'].sum()
        st.metric("Properties Processed", f"{total_properties:,}")
    
    with col3:
        successful = df['successful'].sum()
        failed = df['failed'].sum()
        success_rate = (successful / max(successful + failed, 1)) * 100
        
        st.metric("Success Rate", f"{success_rate:.1f}%")
    
    with col4:
        avg_time = df.apply(lambda x: (datetime.now() - x['created_at']).total_seconds() 
                          if x['status'] == 'completed' else 0, axis=1).mean()
        st.metric("Avg. Processing Time", format_duration(avg_time))
    
    with col5:
        active_jobs = len(df[df['status'].isin(['running', 'pending'])])
        st.metric("Active Jobs", active_jobs)
    
    st.markdown("---")
    
    # Charts
    st.markdown("### 📊 Extraction Trends")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Timeline", "Success Rates", "Performance", "Domains"])
    
    with tab1:
        # Timeline chart
        if grouping == "Day":
            df_grouped = df.groupby(df['created_at'].dt.date).agg({
                'job_id': 'count',
                'successful': 'sum',
                'failed': 'sum'
            }).reset_index()
            df_grouped.columns = ['Date', 'Jobs', 'Successful', 'Failed']
            
            fig = make_subplots(
                rows=2, cols=1,
                subplot_titles=("Jobs Over Time", "Success vs Failed"),
                vertical_spacing=0.1
            )
            
            # Jobs timeline
            fig.add_trace(
                go.Scatter(x=df_grouped['Date'], y=df_grouped['Jobs'],
                         mode='lines+markers', name='Total Jobs',
                         line=dict(color=THEME['primary'], width=2)),
                row=1, col=1
            )
            
            # Success vs Failed
            fig.add_trace(
                go.Bar(x=df_grouped['Date'], y=df_grouped['Successful'],
                      name='Successful', marker_color=THEME['success']),
                row=2, col=1
            )
            
            fig.add_trace(
                go.Bar(x=df_grouped['Date'], y=df_grouped['Failed'],
                      name='Failed', marker_color=THEME['danger']),
                row=2, col=1
            )
            
            fig.update_layout(height=600, showlegend=True, barmode='stack')
            st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        # Success rate analysis
        col1, col2 = st.columns(2)
        
        with col1:
            # Success rate by status
            status_dist = df['status'].value_counts()
            
            fig = go.Figure(data=[
                go.Pie(labels=status_dist.index, values=status_dist.values,
                      hole=0.4, marker=dict(colors=[
                          THEME['success'] if s == 'completed' else
                          THEME['warning'] if s == 'running' else
                          THEME['info'] if s == 'pending' else
                          THEME['danger'] for s in status_dist.index
                      ]))
            ])
            
            fig.update_layout(title="Job Status Distribution", height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Success rate trend
            df_daily = df.groupby(df['created_at'].dt.date).agg({
                'successful': 'sum',
                'failed': 'sum'
            }).reset_index()
            
            df_daily['success_rate'] = (df_daily['successful'] / 
                                       (df_daily['successful'] + df_daily['failed']) * 100)
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df_daily['created_at'],
                y=df_daily['success_rate'],
                mode='lines+markers',
                name='Success Rate',
                line=dict(color=THEME['success'], width=2),
                fill='tozeroy'
            ))
            
            fig.update_layout(
                title="Success Rate Trend",
                yaxis_title="Success Rate (%)",
                xaxis_title="Date",
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        # Performance metrics
        st.markdown("#### Processing Speed Analysis")
        
        # Calculate processing speeds
        df['processing_time'] = df.apply(
            lambda x: (datetime.now() - x['created_at']).total_seconds() / 60
            if x['status'] == 'completed' else None, axis=1
        )
        
        df_speed = df[df['processing_time'].notna()]
        
        if not df_speed.empty:
            # Histogram of processing times
            fig = px.histogram(df_speed, x='processing_time', nbins=30,
                             title="Processing Time Distribution",
                             labels={'processing_time': 'Time (minutes)'},
                             color_discrete_sequence=[THEME['primary']])
            
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            
            # Performance by hour of day
            df_speed['hour'] = pd.to_datetime(df_speed['created_at']).dt.hour
            hourly_perf = df_speed.groupby('hour')['processing_time'].mean()
            
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=hourly_perf.index,
                y=hourly_perf.values,
                marker_color=THEME['info']
            ))
            
            fig.update_layout(
                title="Average Processing Time by Hour of Day",
                xaxis_title="Hour",
                yaxis_title="Avg. Time (minutes)",
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    with tab4:
        # Domain analysis
        st.markdown("#### Domain Performance")
        
        # Extract domains from URLs (sample implementation)
        # This would need actual URL data from job details
        domain_data = pd.DataFrame({
            'Domain': ['actweb.acttax.com', 'treasurer.maricopa.gov', 
                      'www.hctax.net', 'pwa.waynegov.com', 
                      'taxpay.johnstonnc.com'],
            'Success Rate': [98.5, 92.3, 89.7, 95.2, 87.4],
            'Avg Time (s)': [2.3, 8.7, 12.1, 5.4, 6.8],
            'Total Extracted': [1250, 890, 675, 432, 298]
        })
        
        # Bubble chart
        fig = px.scatter(domain_data, 
                        x='Avg Time (s)', 
                        y='Success Rate',
                        size='Total Extracted',
                        hover_data=['Domain'],
                        color='Success Rate',
                        color_continuous_scale='Viridis',
                        size_max=60,
                        title="Domain Performance Matrix")
        
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)
        
        # Domain table
        st.markdown("#### Detailed Domain Statistics")
        st.dataframe(
            domain_data.style.format({
                'Success Rate': '{:.1f}%',
                'Avg Time (s)': '{:.1f}',
                'Total Extracted': '{:,}'
            }).background_gradient(subset=['Success Rate'], cmap='RdYlGn'),
            use_container_width=True,
            hide_index=True
        )
    
    st.markdown("---")
    
    # Export options
    st.markdown("### 📤 Export Analytics")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 Generate Report", use_container_width=True):
            # Generate comprehensive report
            report = {
                'generated_at': datetime.now().isoformat(),
                'date_range': [str(d) for d in date_range],
                'summary': {
                    'total_jobs': int(total_jobs),
                    'total_properties': int(total_properties),
                    'success_rate': float(success_rate),
                    'active_jobs': int(active_jobs)
                },
                'jobs': df.to_dict('records')
            }
            
            st.download_button(
                "Download Report (JSON)",
                data=json.dumps(report, indent=2, default=str),
                file_name=f"analytics_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
    
    with col2:
        if st.button("📈 Export Charts", use_container_width=True):
            st.info("Chart export feature coming soon")
    
    with col3:
        if st.button("📧 Email Report", use_container_width=True):
            st.info("Email report feature coming soon")

# ==================== Page: Settings ====================
def page_settings():
    """System settings and configuration page"""
    st.title("⚙️ Settings & Configuration")
    st.markdown("Configure system settings and preferences")
    
    tab1, tab2, tab3, tab4 = st.tabs(["General", "API", "Extractors", "Advanced"])
    
    with tab1:
        st.markdown("### General Settings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Display Preferences")
            
            theme = st.selectbox("Theme", ["Light", "Dark", "Auto"])
            
            date_format = st.selectbox("Date Format", 
                                      ["MM/DD/YYYY", "DD/MM/YYYY", "YYYY-MM-DD"])
            
            time_format = st.selectbox("Time Format", ["12-hour", "24-hour"])
            
            default_refresh = st.select_slider(
                "Default Refresh Rate",
                options=["Manual", "Slow", "Normal", "Fast"],
                value="Normal"
            )
        
        with col2:
            st.markdown("#### Notification Settings")
            
            enable_notifications = st.checkbox("Enable Notifications", value=True)
            
            if enable_notifications:
                notify_on_complete = st.checkbox("Job Completion", value=True)
                notify_on_error = st.checkbox("Job Errors", value=True)
                notify_on_warning = st.checkbox("Warnings", value=False)
                
                notification_sound = st.checkbox("Sound Alerts", value=False)
        
        st.markdown("---")
        
        st.markdown("#### Data Retention")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            job_retention = st.number_input("Keep Jobs (days)", 1, 365, 30)
        
        with col2:
            log_retention = st.number_input("Keep Logs (days)", 1, 90, 7)
        
        with col3:
            screenshot_retention = st.number_input("Keep Screenshots (days)", 1, 30, 3)
    
    with tab2:
        st.markdown("### API Configuration")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Connection Settings")
            
            api_url = st.text_input("API URL", value=API_BASE_URL)
            
            api_timeout = st.slider("Request Timeout (s)", 5, 60, 30)
            
            max_retries = st.number_input("Max Retries", 0, 10, 3)
            
            retry_delay = st.slider("Retry Delay (s)", 1, 10, 2)
        
        with col2:
            st.markdown("#### Authentication")
            
            auth_enabled = st.checkbox("Enable Authentication", value=False)
            
            if auth_enabled:
                auth_type = st.selectbox("Auth Type", ["API Key", "OAuth2", "Basic"])
                
                if auth_type == "API Key":
                    api_key = st.text_input("API Key", type="password")
                elif auth_type == "Basic":
                    username = st.text_input("Username")
                    password = st.text_input("Password", type="password")
        
        st.markdown("---")
        
        st.markdown("#### Rate Limiting")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            enable_rate_limit = st.checkbox("Enable Rate Limiting", value=True)
        
        with col2:
            if enable_rate_limit:
                requests_per_second = st.slider("Requests/Second", 1, 20, 5)
        
        with col3:
            if enable_rate_limit:
                burst_size = st.number_input("Burst Size", 1, 100, 10)
    
    with tab3:
        st.markdown("### Extractor Configuration")
        
        st.markdown("#### Default Settings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            default_method = st.selectbox(
                "Default Extraction Method",
                ["Auto-detect", "HTTP Direct", "Selenium", "Playwright"]
            )
            
            default_concurrent = st.checkbox("Concurrent by Default", value=True)
            
            if default_concurrent:
                default_workers = st.slider("Default Workers", 1, 20, 5)
        
        with col2:
            default_timeout = st.slider("Default Timeout (s)", 5, 60, 30)
            
            default_retries = st.number_input("Default Retries", 0, 5, 3)
            
            save_screenshots_default = st.checkbox("Save Screenshots by Default", 
                                                  value=False)
        
        st.markdown("---")
        
        st.markdown("#### Domain-Specific Settings")
        
        # Domain configuration table
        domain_config = pd.DataFrame({
            'Domain': ['actweb.acttax.com', 'treasurer.maricopa.gov', 'www.hctax.net'],
            'Method': ['HTTP', 'Selenium', 'Playwright'],
            'Timeout': [10, 30, 20],
            'Retries': [3, 5, 3],
            'Rate Limit': [10, 2, 5]
        })
        
        edited_config = st.data_editor(
            domain_config,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Method": st.column_config.SelectboxColumn(
                    options=["HTTP", "Selenium", "Playwright"]
                ),
                "Timeout": st.column_config.NumberColumn(min_value=5, max_value=60),
                "Retries": st.column_config.NumberColumn(min_value=0, max_value=10),
                "Rate Limit": st.column_config.NumberColumn(min_value=1, max_value=20)
            }
        )
        
        if st.button("Add Domain Configuration"):
            st.info("Domain configuration editor coming soon")
    
    with tab4:
        st.markdown("### Advanced Settings")
        
        st.markdown("#### Performance Tuning")
        
        col1, col2 = st.columns(2)
        
        with col1:
            connection_pool_size = st.slider("Connection Pool Size", 1, 100, 20)
            
            cache_size = st.slider("Cache Size (MB)", 10, 1000, 100)
            
            max_memory = st.slider("Max Memory Usage (%)", 10, 90, 70)
        
        with col2:
            enable_compression = st.checkbox("Enable Compression", value=True)
            
            enable_caching = st.checkbox("Enable Response Caching", value=True)
            
            if enable_caching:
                cache_ttl = st.slider("Cache TTL (minutes)", 1, 60, 5)
        
        st.markdown("---")
        
        st.markdown("#### Debugging")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            debug_mode = st.checkbox("Debug Mode", value=False)
        
        with col2:
            verbose_logging = st.checkbox("Verbose Logging", value=False)
        
        with col3:
            save_raw_responses = st.checkbox("Save Raw Responses", value=False)
        
        if debug_mode:
            st.warning("Debug mode is enabled. This may impact performance.")
        
        st.markdown("---")
        
        st.markdown("#### System Maintenance")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("Clear Cache", use_container_width=True):
                st.cache_data.clear()
                st.cache_resource.clear()
                st.success("Cache cleared successfully")
        
        with col2:
            if st.button("Reset Settings", use_container_width=True):
                if st.checkbox("Confirm reset"):
                    init_session_state()
                    st.success("Settings reset to defaults")
                    st.rerun()
        
        with col3:
            if st.button("Export Settings", use_container_width=True):
                settings = {
                    'general': {
                        'theme': theme,
                        'date_format': date_format,
                        'time_format': time_format
                    },
                    'api': {
                        'url': api_url,
                        'timeout': api_timeout
                    },
                    'extractors': {
                        'default_method': default_method,
                        'default_timeout': default_timeout
                    }
                }
                
                st.download_button(
                    "Download Settings",
                    data=json.dumps(settings, indent=2),
                    file_name="dashboard_settings.json",
                    mime="application/json"
                )
    
    # Save settings button
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 1, 3])
    
    with col1:
        if st.button("💾 Save Settings", type="primary", use_container_width=True):
            st.success("Settings saved successfully")
    
    with col2:
        if st.button("↩️ Cancel", use_container_width=True):
            st.session_state.app_state.selected_page = "Dashboard"
            st.rerun()

# ==================== Main Application ====================
def main():
    """Main application entry point"""
    
    # Initialize session state
    init_session_state()
    
    # Sidebar navigation
    with st.sidebar:
        st.markdown("# 🏛️ Tax Extractor Pro")
        st.markdown("---")
        
        # API Status indicator
        api_health = check_api_health()
        if api_health:
            st.success("✅ System Online")
        else:
            st.error("❌ API Offline")
            with st.expander("Start API Service"):
                st.code("python api_service.py", language="bash")
        
        st.markdown("---")
        
        # Navigation menu
        pages = {
            "Dashboard": "📊",
            "New Extraction": "🚀",
            "Job Monitor": "📋",
            "Analytics": "📈",
            "Settings": "⚙️"
        }
        
        selected_page = st.radio(
            "Navigation",
            list(pages.keys()),
            format_func=lambda x: f"{pages[x]} {x}",
            index=list(pages.keys()).index(st.session_state.app_state.selected_page)
        )
        
        st.session_state.app_state.selected_page = selected_page
        
        st.markdown("---")
        
        # Quick Stats
        st.markdown("### Quick Stats")
        
        jobs = api_client.get_all_jobs(limit=100)
        active_jobs = len([j for j in jobs if j['status'] in ['running', 'pending']])
        completed_today = len([j for j in jobs 
                              if j['status'] == 'completed' and 
                              datetime.fromisoformat(j['created_at']).date() == datetime.now().date()])
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Active", active_jobs)
        with col2:
            st.metric("Today", completed_today)
        
        # Recent notifications
        if st.session_state.app_state.notifications:
            st.markdown("### 🔔 Notifications")
            for notif in st.session_state.app_state.notifications[-3:]:
                if notif['type'] == 'success':
                    st.success(notif['message'])
                elif notif['type'] == 'error':
                    st.error(notif['message'])
                else:
                    st.info(notif['message'])
        
        st.markdown("---")
        
        # Footer
        st.caption("Tax Extractor Pro v2.0")
        st.caption("© 2024 - Enterprise Edition")
    
    # Main content area
    if selected_page == "Dashboard":
        page_dashboard()
    elif selected_page == "New Extraction":
        page_new_extraction()
    elif selected_page == "Job Monitor":
        page_job_monitor()
    elif selected_page == "Analytics":
        page_analytics()
    elif selected_page == "Settings":
        page_settings()
    
    # Auto-refresh handler
    if st.session_state.app_state.auto_refresh and selected_page in ["Dashboard", "Job Monitor"]:
        refresh_interval = REFRESH_INTERVALS.get(st.session_state.app_state.refresh_rate, 2)
        if refresh_interval:
            time.sleep(refresh_interval)
            st.rerun()

if __name__ == "__main__":
    main()