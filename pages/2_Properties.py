#!/usr/bin/env python3
import os
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Properties", page_icon="🏠", layout="wide")

# --------------- Config & Helpers ---------------
def _get_api_url() -> str:
    try:
        return st.secrets.get("API_URL") or os.getenv("API_URL") or "https://tax-extraction-system-production.up.railway.app"
    except Exception:
        return os.getenv("API_URL") or "https://tax-extraction-system-production.up.railway.app"

def _get_docs_api_url() -> Optional[str]:
    # Separate documents API if available; fallback to main API
    try:
        return st.secrets.get("DOC_API_URL") or os.getenv("DOC_API_URL") or _get_api_url()
    except Exception:
        return os.getenv("DOC_API_URL") or _get_api_url()

API_URL = _get_api_url()
DOC_API_URL = _get_docs_api_url()

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

def create_entity_api(entity: Dict[str, Any]) -> Dict[str, Any]:
    try:
        r = requests.post(f"{API_URL}/api/v1/entities", json=entity, timeout=20)
        if r.status_code in (200, 201):
            return r.json()
        return {"error": f"API {r.status_code}", "details": r.text}
    except Exception as e:
        return {"error": str(e)}

def create_property_api(prop: Dict[str, Any]) -> Dict[str, Any]:
    try:
        r = requests.post(f"{API_URL}/api/v1/properties", json=prop, timeout=20)
        if r.status_code in (200, 201):
            return r.json()
        return {"error": f"API {r.status_code}", "details": r.text}
    except Exception as e:
        return {"error": str(e)}

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
        amt_min, amt_max = st.columns(2)
        with amt_min:
            f_min = st.number_input("Min Amount", min_value=0.0, step=100.0, value=0.0, format="%0.2f")
        with amt_max:
            f_max = st.number_input("Max Amount", min_value=0.0, step=100.0, value=0.0, format="%0.2f")
    with fc3:
        dd1, dd2 = st.columns(2)
        with dd1:
            due_from = st.date_input("Due After", value=None, format="MM/DD/YYYY")
        with dd2:
            due_to = st.date_input("Due Before", value=None, format="MM/DD/YYYY")
        needs_ext = st.checkbox("Needs Extraction (amount is null/0)")

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
    if f_min and f_min > 0:
        filter_params["amount_due_min"] = f_min
    if f_max and f_max > 0:
        filter_params["amount_due_max"] = f_max
    if isinstance(due_from, (datetime, date)):
        filter_params["due_date_after"] = due_from.isoformat()
    if isinstance(due_to, (datetime, date)):
        filter_params["due_date_before"] = due_to.isoformat()
    if needs_ext:
        filter_params["needs_extraction"] = True

    refresh = st.button("Apply Filters", type="primary")
    st.markdown('</div>', unsafe_allow_html=True)

# --------------- Add Property ---------------
with st.expander("➕ Add Property", expanded=False):
    st.markdown('<div class="card">', unsafe_allow_html=True)
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
            st.markdown("<b>Financials</b>", unsafe_allow_html=True)
            new_amount_due = st.number_input("Amount Due", min_value=0.0, step=100.0, format="%0.2f")
            new_prev_year = st.number_input("Previous Year Taxes", min_value=0.0, step=100.0, format="%0.2f")
            new_paid_by = st.selectbox("Paid By", options=["", "Landlord", "Tenant", "Tenant to Reimburse"], index=0)
            new_due_date = st.date_input("Tax Due Date", value=None, format="MM/DD/YYYY")
            new_close_date = st.date_input("Close Date", value=None, format="MM/DD/YYYY")
            new_property_type = st.text_input("Property Type", value="property")

        new_extraction_steps = st.text_area("Extraction Steps (notes)", height=80)

        st.divider()
        st.markdown("<b>Entity Assignment</b>", unsafe_allow_html=True)
        entity_mode = st.radio(
            "Entity Assignment Mode",
            options=["Assign to Existing Entity", "Create New Entity"],
            horizontal=True,
            key="add_prop_entity_mode",
            label_visibility="collapsed"
        )

        selected_parent_entity_id = None
        if entity_mode == "Assign to Existing Entity":
            names = [e.get("entity_name", "Unnamed") for e in entities]
            selected_entity_name = st.selectbox("Select Entity", options=names or ["No entities available"]) 
            if entities and selected_entity_name:
                for e in entities:
                    if e.get("entity_name") == selected_entity_name:
                        selected_parent_entity_id = e.get("entity_id")
                        break
            new_entity_payload = None
        else:
            ec1, ec2 = st.columns(2)
            with ec1:
                ent_name = st.text_input("New Entity Name")
                ent_type = st.selectbox("New Entity Type", ["Parent Entity", "Sub-Entity", "Single-Property Entity"], index=0)
            with ec2:
                ent_state = st.text_input("Entity State", placeholder="e.g., TX")
                ent_juris = st.text_input("Entity Jurisdiction", placeholder="Optional")

            ent_parent_id = None
            if ent_type == "Sub-Entity":
                parent_options = [e.get("entity_name", "Unnamed") for e in entities]
                ent_parent_name = st.selectbox("Parent Entity", options=parent_options or ["No parent entities"])
                if entities and ent_parent_name:
                    for e in entities:
                        if e.get("entity_name") == ent_parent_name:
                            ent_parent_id = e.get("entity_id")
                            break

            include_prop_details = (ent_type == "Single-Property Entity")
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

        if st.form_submit_button("Create Property", type="primary"):
            if not new_property_id or not new_property_name:
                st.error("Property ID and Property Name are required")
            elif entity_mode == "Assign to Existing Entity" and not selected_parent_entity_id:
                st.error("Please select an entity to assign the property to")
            elif entity_mode == "Create New Entity" and (not new_entity_payload or not new_entity_payload.get("entity_name")):
                st.error("Please provide a name for the new entity")
            else:
                created_entity_id = selected_parent_entity_id
                if entity_mode == "Create New Entity":
                    ent_result = create_entity_api(new_entity_payload)
                    if ent_result.get("entity"):
                        created_entity_id = ent_result["entity"].get("entity_id") or ent_result["entity"].get("id")
                    else:
                        st.error(f"Failed to create entity: {ent_result.get('error') or ent_result.get('details') or 'Unknown error'}")
                        st.stop()

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
                    prop_payload["tax_due_date"] = new_due_date.isoformat()
                if isinstance(new_close_date, (datetime, date)):
                    prop_payload["close_date"] = new_close_date.isoformat()

                result = create_property_api(prop_payload)
                if result.get("property"):
                    st.success("Property created successfully")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"Failed to create property: {result.get('error') or result.get('details') or 'Unknown error'}")
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
            st.markdown(f"<div class='kv'>🔄 <b>Updated:</b> {p.get('updated_at') or '—'}</div>", unsafe_allow_html=True)
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
