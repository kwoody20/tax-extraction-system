#!/usr/bin/env python3
import os
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
import streamlit as st

from src.dashboard.tracking import inject_google_analytics
from src.dashboard.streamlit_utils import format_timestamp

st.set_page_config(page_title="Properties", page_icon="🏠", layout="wide")

inject_google_analytics(default="G-YTNYDRKJEF")

# --------------- Config & Helpers ---------------
def _get_api_url() -> str:
    try:
        return st.secrets.get("API_URL") or os.getenv("API_URL") or "https://tax-extraction-system-production.up.railway.app"
    except Exception:
        return os.getenv("API_URL") or "https://tax-extraction-system-production.up.railway.app"

API_URL = _get_api_url()

@st.cache_data(ttl=300)
def fetch_entities(search: Optional[str] = None, limit: int = 500) -> List[Dict[str, Any]]:
    try:
        params = {"limit": limit}
        if search:
            params["search"] = search
        r = requests.get(f"{API_URL}/api/v1/entities", params=params, timeout=12)
        if r.status_code == 200:
            return r.json().get("entities", [])
    except Exception:
        pass
    return []

@st.cache_data(ttl=180)
def fetch_properties(
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 200,
    offset: int = 0,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    params: Dict[str, Any] = {"limit": limit, "offset": offset}
    if filters:
        params.update(filters)
    try:
        r = requests.get(f"{API_URL}/api/v1/properties", params=params, timeout=(6, 30))
        if r.status_code == 200:
            data = r.json()
            return data.get("properties", []), {k: data.get(k) for k in ("count", "total_count", "limit", "offset")}
    except Exception:
        pass
    return [], {}

def update_property_fields(updates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Bulk update properties (used for single-record edit)."""
    try:
        payload = {"updates": updates, "validate": True}
        r = requests.put(f"{API_URL}/api/v1/properties/bulk", json=payload, timeout=20)
        if r.status_code in (200, 201):
            return r.json()
        return {"error": f"API {r.status_code}", "details": r.text}
    except Exception as e:
        return {"error": str(e)}

# --------------- Styles ---------------
# Dark mode state
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = False

# Header + dark mode toggle
hdr1, hdr2 = st.columns([6, 1])
with hdr1:
    st.title("🏠 Properties")
    st.caption(f"API: {API_URL}")
with hdr2:
    dm = st.toggle("Dark Mode", value=st.session_state.dark_mode, key="props_dark_mode")
    if dm != st.session_state.dark_mode:
        st.session_state.dark_mode = dm
        st.rerun()

st.markdown(
    """
    <style>
      .filter-card, .card {
        border: 1px solid #d1d5db;
        border-radius: 12px;
        background: #fbfbfb;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        padding: 16px;
        margin-bottom: 12px;
      }
      .card:hover { border-color: #9ca3af; }
      .card h4 { margin: 0 0 8px 0; }
      .pill { display:inline-block; padding:2px 8px; border-radius: 999px; background:#eef2ff; margin-left:6px; font-size:12px; }
      .kv { color:#555; }
      .kv b { color:#222; }
      .btn-link { display:inline-block; padding:6px 10px; background:#1f77b4; color:#fff !important; text-decoration:none; border-radius:6px; font-size:13px; }
      .btn-link:hover { background:#155a8a; }
    </style>
    """,
    unsafe_allow_html=True
)

if st.session_state.dark_mode:
    st.markdown(
        """
        <style>
          .stApp { background: #111827; color: #e5e7eb; }
          .filter-card, .card { background: #1f2937; border: 1px solid #374151; box-shadow: none; }
          .kv { color: #e5e7eb; }
          .kv b { color: #f3f4f6; }
          .pill { background:#374151; color:#e5e7eb; }
          .btn-link { background:#2563eb; }
          .btn-link:hover { background:#1d4ed8; }
        </style>
        """,
        unsafe_allow_html=True
    )

# --------------- Filters ---------------
entities = fetch_entities()

with st.container():
    st.markdown('<div class="filter-card">', unsafe_allow_html=True)
    fc1, fc2, fc3 = st.columns([2, 2, 2])
    with fc1:
        sel_entity = st.selectbox(
            "Entity",
            options=["All"] + sorted([e.get("entity_name", "Unnamed") for e in entities])
        )
        sel_state = st.text_input("State", placeholder="e.g., TX")
    with fc2:
        sel_juris = st.text_input("Jurisdiction", placeholder="e.g., Harris County")
    with fc3:
        dd1, dd2 = st.columns(2)
        with dd1:
            due_from = st.date_input("Due After", value=None, format="MM/DD/YYYY")
        with dd2:
            due_to = st.date_input("Due Before", value=None, format="MM/DD/YYYY")

    # Build filter params for API
    filter_params: Dict[str, Any] = {}
    if sel_entity and sel_entity != "All":
        e = next((x for x in entities if x.get("entity_name") == sel_entity), None)
        if e:
            filter_params["entity_id"] = e.get("entity_id")
    if sel_state:
        filter_params["state"] = sel_state
    if sel_juris:
        filter_params["jurisdiction"] = sel_juris
    if isinstance(due_from, (datetime, date)):
        filter_params["due_date_after"] = due_from.isoformat()
    if isinstance(due_to, (datetime, date)):
        filter_params["due_date_before"] = due_to.isoformat()
    refresh = st.button("Apply Filters", type="primary")
    st.markdown('</div>', unsafe_allow_html=True)

# --------------- Load Properties ---------------
if refresh:
    st.cache_data.clear()

with st.spinner("Loading properties..."):
    properties, meta = fetch_properties(filters=filter_params, limit=200)

if not properties:
    st.info("No properties found for current filters.")
else:
    # Render as cards
    for p in properties:
        amount = p.get("amount_due")
        due = p.get("tax_due_date") or p.get("due_date")
        amt_str = f"${float(amount):,.2f}" if amount not in (None, "") else "—"
        st.markdown('<div class="card">', unsafe_allow_html=True)
        # Header
        title = p.get("property_name") or p.get("property_id") or "Unnamed"
        subtitle = p.get("property_id") or ""
        st.markdown(f"<h4>{title} <span class='pill'>{subtitle}</span></h4>", unsafe_allow_html=True)
        # Body: two cols
        c1, c2, c3 = st.columns([3, 2, 2])
        with c1:
            st.markdown(f"<div class='kv'>📍 <b>Address:</b> {p.get('property_address') or '—'}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='kv'>🏛️ <b>Jurisdiction:</b> {p.get('jurisdiction') or '—'} · <b>State:</b> {p.get('state') or '—'}</div>", unsafe_allow_html=True)
            tax_url = p.get('tax_bill_link')
            if tax_url:
                if hasattr(st, "link_button"):
                    st.link_button("🧾 Open Tax Bill", tax_url)
                else:
                    st.markdown(f"<a class='btn-link' href='{tax_url}' target='_blank' rel='noopener'>🧾 Open Tax Bill</a>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='kv'>🧾 <b>Tax Bill:</b> —</div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='kv'>💰 <b>Amount Due:</b> {amt_str}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='kv'>📅 <b>Due Date:</b> {due or '—'}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='kv'>💳 <b>Paid By:</b> {p.get('paid_by') or '—'}</div>", unsafe_allow_html=True)
            try:
                av = p.get('appraised_value')
                av_str = f"${float(av):,.2f}" if av not in (None, "") else "—"
            except Exception:
                av_str = "—"
            st.markdown(f"<div class='kv'>🏷️ <b>Appraised Value:</b> {av_str}</div>", unsafe_allow_html=True)
        with c3:
            en = p.get('entity_name') or p.get('parent_entity_name') or p.get('sub_entity')
            st.markdown(f"<div class='kv'>🏢 <b>Entity:</b> {en or '—'}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='kv'>#️⃣ <b>Account #:</b> {p.get('account_number') or '—'}</div>", unsafe_allow_html=True)
            updated_display = format_timestamp(p.get('updated_at'))
            st.markdown(f"<div class='kv'>🔄 <b>Updated:</b> {updated_display}</div>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Inline edit form (account number and appraised value)
        with st.expander("✏️ Edit Property"):
            form_key = f"edit_form_{p.get('id') or p.get('property_id')}"
            with st.form(form_key):
                col_a, col_b = st.columns(2)
                with col_a:
                    new_acct = st.text_input(
                        "Account Number",
                        value=str(p.get("account_number") or ""),
                        key=f"acct_{form_key}"
                    )
                with col_b:
                    init_appraised = 0.0
                    try:
                        if p.get("appraised_value") is not None:
                            init_appraised = float(p.get("appraised_value"))
                    except Exception:
                        init_appraised = 0.0
                    new_appraised = st.number_input(
                        "Appraised Value",
                        min_value=0.0,
                        step=1000.0,
                        value=init_appraised,
                        format="%0.2f",
                        key=f"appraised_{form_key}"
                    )

                submitted = st.form_submit_button("Save Changes", type="primary")
                if submitted:
                    row_id = p.get("id")
                    if not row_id:
                        st.error("Missing property row id; cannot update.")
                    else:
                        update = {"id": row_id}
                        update["account_number"] = new_acct or None
                        update["appraised_value"] = float(new_appraised) if new_appraised is not None else None
                        result = update_property_fields([update])
                        if result.get("error"):
                            st.error(f"Update failed: {result.get('error')} | {result.get('details','')}")
                        else:
                            st.success("Property updated")
                            st.cache_data.clear()
                            st.rerun()
