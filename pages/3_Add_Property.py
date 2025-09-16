#!/usr/bin/env python3
import os
from datetime import datetime, date
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

from src.dashboard.tracking import inject_google_analytics

st.set_page_config(page_title="Add Property", page_icon="➕", layout="wide")

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
        params: Dict[str, Any] = {"limit": limit}
        if search:
            params["search"] = search
        r = requests.get(f"{API_URL}/api/v1/entities", params=params, timeout=12)
        if r.status_code == 200:
            return r.json().get("entities", [])
    except Exception:
        pass
    return []


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
    try:
        payload = {"updates": updates, "validate": True}
        r = requests.put(f"{API_URL}/api/v1/properties/bulk", json=payload, timeout=20)
        if r.status_code in (200, 201):
            return r.json()
        return {"error": f"API {r.status_code}", "details": r.text}
    except Exception as e:
        return {"error": str(e)}


# --------------- Styles ---------------
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = False

hdr1, hdr2 = st.columns([6, 1])
with hdr1:
    st.title("➕ Add Property")
    st.caption(f"API: {API_URL}")
with hdr2:
    dm = st.toggle("Dark Mode", value=st.session_state.dark_mode, key="add_prop_dark_mode")
    if dm != st.session_state.dark_mode:
        st.session_state.dark_mode = dm
        st.rerun()

nav_cols = st.columns([2, 2, 6])
with nav_cols[0]:
    if hasattr(st, "page_link"):
        st.page_link("pages/4_Add_Entity.py", label="Add Entity", icon="🏢")
    else:
        st.info("Open 'Add Entity' from the sidebar.")
with nav_cols[1]:
    if hasattr(st, "page_link"):
        st.page_link("pages/2_Properties.py", label="View Properties", icon="🏠")
    else:
        st.info("Open 'Properties' from the sidebar.")

st.markdown(
    """
    <style>
      .card {
        border: 1px solid #d1d5db;
        border-radius: 12px;
        background: #fbfbfb;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        padding: 16px;
        margin-bottom: 12px;
      }
      .card h4 { margin: 0 0 8px 0; }
      .kv { color:#555; }
      .kv b { color:#222; }
      .help { color:#6b7280; font-size: 13px; }
    </style>
    """,
    unsafe_allow_html=True
)

if st.session_state.dark_mode:
    st.markdown(
        """
        <style>
          .stApp { background: #111827; color: #e5e7eb; }
          .card { background: #1f2937; border: 1px solid #374151; box-shadow: none; }
          .kv { color: #e5e7eb; }
          .kv b { color: #f3f4f6; }
          .help { color:#9ca3af; }
        </style>
        """,
        unsafe_allow_html=True
    )

# --------------- Add Property Form ---------------
entities = fetch_entities()

st.markdown('<div class="card">', unsafe_allow_html=True)
st.subheader("Property Details")

with st.form("create_property_form", clear_on_submit=False):
    b1, b2 = st.columns(2)
    with b1:
        property_id = st.text_input("Property ID", placeholder="e.g., PROP_12345")
        property_name = st.text_input("Property Name")
        property_address = st.text_input("Property Address")
        state = st.text_input("State", placeholder="e.g., TX")
        jurisdiction = st.text_input("Jurisdiction", placeholder="e.g., Harris County")
        account_number = st.text_input("Account Number", placeholder="Optional")
        tax_bill_link = st.text_input("Tax Bill Link", placeholder="https://...")
    with b2:
        st.markdown("<b>Dates & Values</b>", unsafe_allow_html=True)
        amount_due = st.number_input("Amount Due", min_value=0.0, step=100.0, format="%0.2f")
        previous_year = st.number_input("Previous Year Taxes", min_value=0.0, step=100.0, format="%0.2f")
        appraised_value = st.number_input("Appraised Value", min_value=0.0, step=1000.0, format="%0.2f")
        paid_by = st.selectbox("Paid By", options=["", "Landlord", "Tenant", "Tenant to Reimburse"], index=0)
        tax_due_date = st.date_input("Tax Due Date", value=None, format="MM/DD/YYYY")
        close_date = st.date_input("Close Date", value=None, format="MM/DD/YYYY")
        property_type = st.text_input("Property Type", value="property")

    extraction_steps = st.text_area("Extraction Steps (notes)", height=80)

    st.divider()
    st.subheader("Entity Assignment")
    entity_mode = st.radio(
        "Entity Assignment Mode",
        options=["Assign to Existing Entity", "Create New Entity"],
        horizontal=True,
        key="entity_mode_radio",
    )

    created_or_selected_entity_id: Optional[str] = None
    new_entity_payload: Optional[Dict[str, Any]] = None

    if entity_mode == "Assign to Existing Entity":
        names = [e.get("entity_name", "Unnamed") for e in entities]
        selected_entity_name = st.selectbox("Select Existing Entity", options=names or ["No entities available"])
        if entities and selected_entity_name:
            for e in entities:
                if e.get("entity_name") == selected_entity_name:
                    created_or_selected_entity_id = e.get("entity_id")
                    break
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
                "account_number": account_number or None,
                "property_address": property_address or None,
                "tax_bill_link": tax_bill_link or None,
                "amount_due": float(amount_due or 0) if amount_due is not None else None,
                "previous_year_taxes": float(previous_year or 0) if previous_year is not None else None,
                "close_date": close_date.isoformat() if isinstance(close_date, (datetime, date)) else None,
                "extraction_steps": extraction_steps or None,
            })

    submitted = st.form_submit_button("Create Property", type="primary")

    if submitted:
        # Basic validation
        if not property_id or not property_name:
            st.error("Property ID and Property Name are required")
            st.stop()
        if entity_mode == "Assign to Existing Entity" and not created_or_selected_entity_id:
            st.error("Please select an entity to assign the property to")
            st.stop()
        if entity_mode == "Create New Entity" and (not new_entity_payload or not new_entity_payload.get("entity_name")):
            st.error("Please provide a name for the new entity")
            st.stop()

        # Create entity if needed
        if entity_mode == "Create New Entity":
            with st.spinner("Creating entity..."):
                ent_result = create_entity_api(new_entity_payload)  # type: ignore[arg-type]
            if ent_result.get("entity"):
                created_or_selected_entity_id = ent_result["entity"].get("entity_id") or ent_result["entity"].get("id")
            else:
                st.error(f"Failed to create entity: {ent_result.get('error') or ent_result.get('details') or 'Unknown error'}")
                st.stop()

        # Build property payload
        prop_payload: Dict[str, Any] = {
            "property_id": property_id,
            "property_name": property_name,
            "property_address": property_address or None,
            "jurisdiction": jurisdiction or None,
            "state": state or None,
            "property_type": property_type or None,
            "account_number": account_number or None,
            "tax_bill_link": tax_bill_link or None,
            "amount_due": float(amount_due or 0) if amount_due is not None else None,
            "previous_year_taxes": float(previous_year or 0) if previous_year is not None else None,
            "paid_by": paid_by or None,
            "extraction_steps": extraction_steps or None,
            "parent_entity_id": created_or_selected_entity_id or None,
        }
        if isinstance(tax_due_date, (datetime, date)):
            prop_payload["tax_due_date"] = tax_due_date.isoformat()
        if isinstance(close_date, (datetime, date)):
            prop_payload["close_date"] = close_date.isoformat()

        # Create property
        with st.spinner("Creating property..."):
            result = create_property_api(prop_payload)

        if not result.get("property"):
            st.error(f"Failed to create property: {result.get('error') or result.get('details') or 'Unknown error'}")
            st.stop()

        created = result["property"]
        row_id = created.get("id")

        # If appraised value was provided, update record post-create
        if row_id is not None and appraised_value and float(appraised_value) > 0:
            with st.spinner("Applying appraised value..."):
                upd = update_property_fields([{"id": row_id, "appraised_value": float(appraised_value)}])
            if upd.get("error"):
                st.warning("Property created, but failed to set appraised value.")

        st.success(f"Property {created.get('property_id') or property_id} created successfully")
        st.cache_data.clear()

st.markdown('</div>', unsafe_allow_html=True)
