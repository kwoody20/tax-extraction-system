#!/usr/bin/env python3
"""
Multipage Streamlit App — Overview page

This is the main (home) page. Additional pages live under ./pages/
"""

import os
import requests
from datetime import datetime
import streamlit as st
import plotly.express as px

st.set_page_config(
    page_title="Tax Dashboard",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Resolve API URLs
def _get_api_url() -> str:
    try:
        return st.secrets.get("API_URL") or os.getenv("API_URL") or "https://tax-extraction-system-production.up.railway.app"
    except Exception:
        return os.getenv("API_URL") or "https://tax-extraction-system-production.up.railway.app"

API_URL = _get_api_url()

@st.cache_data(ttl=300)
def fetch_statistics():
    try:
        r = requests.get(f"{API_URL}/api/v1/statistics", timeout=12)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}

@st.cache_data(ttl=300)
def fetch_jurisdictions():
    try:
        r = requests.get(f"{API_URL}/api/v1/jurisdictions", timeout=12)
        if r.status_code == 200:
            return r.json().get("jurisdictions", [])
    except Exception:
        pass
    return []

if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = False

hdr1, hdr2 = st.columns([6, 1])
with hdr1:
    st.title("🏢 Property Tax Dashboard — Overview")
    st.caption(f"Updated {datetime.now().strftime('%H:%M:%S')} · API: {API_URL}")
with hdr2:
    dm = st.toggle("Dark Mode", value=st.session_state.dark_mode, key="overview_dark_mode")
    if dm != st.session_state.dark_mode:
        st.session_state.dark_mode = dm
        st.rerun()

if st.session_state.dark_mode:
    st.markdown(
        """
        <style>
          .stApp { background: #111827; color: #e5e7eb; }
        </style>
        """,
        unsafe_allow_html=True
    )

stats = fetch_statistics() or {}

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Properties", stats.get("total_properties", 0))
with col2:
    st.metric("Total Entities", stats.get("total_entities", 0))
with col3:
    st.metric("Outstanding Tax", f"${stats.get('total_outstanding_tax', stats.get('total_outstanding', 0)):,.2f}")
with col4:
    led = stats.get("last_extraction_date") or stats.get("last_extraction")
    st.metric("Last Extraction", led if led else "—")

st.divider()
st.subheader("Jurisdictions — Property Count")
jur_data = fetch_jurisdictions()
if jur_data:
    # Build a compact bar chart of top 12 jurisdictions by count
    top = sorted(jur_data, key=lambda x: x.get("count", 0), reverse=True)[:12]
    if top:
        fig = px.bar(
            x=[j.get("name") for j in top],
            y=[j.get("count", 0) for j in top],
            labels={"x": "Jurisdiction", "y": "Properties"},
            title="Top Jurisdictions by Property Count"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No jurisdiction counts available.")
else:
    st.info("No jurisdiction data available.")

# Mark page as rendered for legacy blank-page fallback
try:
    os.environ["DASHBOARD_RENDERED"] = "1"
except Exception:
    pass
