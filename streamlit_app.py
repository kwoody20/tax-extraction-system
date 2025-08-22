"""
Streamlit Dashboard for Tax Extraction System.
"""

import streamlit as st
import pandas as pd
import requests
import os
from datetime import datetime

st.set_page_config(page_title="Tax Dashboard", page_icon="🏢", layout="wide")

# Get API URL from secrets or environment
try:
    API_URL = st.secrets["API_URL"]
except:
    API_URL = "https://tax-extraction-system-production.up.railway.app"

st.title("🏢 Property Tax Dashboard")
st.write("Real-time monitoring of property tax data")

# Sidebar
with st.sidebar:
    st.header("🔧 Controls")
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    # API Status
    st.subheader("🌐 API Status")
    with st.spinner("Checking API..."):
        try:
            response = requests.get(f"{API_URL}/health", timeout=5)
            data = response.json()
            if response.status_code == 200 and data.get("status") == "healthy":
                st.success("✅ API & Database Online")
            elif response.status_code == 200:
                st.warning(f"⚠️ API Online, Database Issue")
                st.caption("Railway needs Supabase credentials")
            else:
                st.error(f"❌ API Offline ({response.status_code})")
        except Exception as e:
            st.error(f"❌ Cannot reach API")
            st.caption(f"URL: {API_URL}")

# Main content
tab1, tab2, tab3 = st.tabs(["📊 Overview", "🏢 Properties", "👥 Entities"])

with tab1:
    st.header("System Overview")
    
    # Fetch statistics
    try:
        stats_response = requests.get(f"{API_URL}/api/v1/statistics", timeout=10)
        if stats_response.status_code == 200:
            stats = stats_response.json()
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Properties", stats.get("total_properties", 0))
            
            with col2:
                st.metric("Total Entities", stats.get("total_entities", 0))
            
            with col3:
                outstanding = stats.get("total_outstanding_tax", 0)
                st.metric("Outstanding Tax", f"${outstanding:,.2f}")
            
            with col4:
                success_rate = stats.get("extraction_success_rate", 0)
                st.metric("Success Rate", f"{success_rate:.1f}%")
        else:
            st.warning("Unable to fetch statistics")
    except Exception as e:
        st.error(f"Error: {e}")

with tab2:
    st.header("Properties")
    
    # Fetch properties
    try:
        props_response = requests.get(f"{API_URL}/api/v1/properties", timeout=10)
        if props_response.status_code == 200:
            properties = props_response.json().get("properties", [])
            
            if properties:
                df = pd.DataFrame(properties)
                
                # Search and Filter Section
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    # Text search across multiple fields
                    search_term = st.text_input("🔍 Search", placeholder="Search properties...")
                
                with col2:
                    # Entity filter
                    entities = ["All"] + sorted(df['entity_name'].dropna().unique().tolist()) if 'entity_name' in df.columns else ["All"]
                    selected_entity = st.selectbox("🏢 Entity", entities)
                
                with col3:
                    # State filter
                    states = ["All"] + sorted(df['state'].dropna().unique().tolist()) if 'state' in df.columns else ["All"]
                    selected_state = st.selectbox("📍 State", states)
                
                with col4:
                    # Jurisdiction filter
                    jurisdictions = ["All"] + sorted(df['jurisdiction'].dropna().unique().tolist()) if 'jurisdiction' in df.columns else ["All"]
                    selected_jurisdiction = st.selectbox("🏛️ Jurisdiction", jurisdictions)
                
                # Apply filters
                filtered_df = df.copy()
                
                # Apply text search
                if search_term:
                    search_cols = ['property_name', 'property_address', 'jurisdiction', 'state', 'entity_name']
                    existing_cols = [col for col in search_cols if col in filtered_df.columns]
                    
                    mask = filtered_df[existing_cols].apply(
                        lambda x: x.astype(str).str.contains(search_term, case=False, na=False)
                    ).any(axis=1)
                    filtered_df = filtered_df[mask]
                
                # Apply entity filter
                if selected_entity != "All" and 'entity_name' in filtered_df.columns:
                    filtered_df = filtered_df[filtered_df['entity_name'] == selected_entity]
                
                # Apply state filter
                if selected_state != "All" and 'state' in filtered_df.columns:
                    filtered_df = filtered_df[filtered_df['state'] == selected_state]
                
                # Apply jurisdiction filter
                if selected_jurisdiction != "All" and 'jurisdiction' in filtered_df.columns:
                    filtered_df = filtered_df[filtered_df['jurisdiction'] == selected_jurisdiction]
                
                # Display metrics for filtered data
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Properties Found", len(filtered_df))
                with col2:
                    unique_entities = filtered_df['entity_name'].nunique() if 'entity_name' in filtered_df.columns else 0
                    st.metric("Entities", unique_entities)
                with col3:
                    unique_states = filtered_df['state'].nunique() if 'state' in filtered_df.columns else 0
                    st.metric("States", unique_states)
                
                # Display filtered data
                display_cols = ['property_name', 'property_address', 'entity_name', 'jurisdiction', 'state']
                available_cols = [col for col in display_cols if col in filtered_df.columns]
                
                if available_cols and len(filtered_df) > 0:
                    st.dataframe(
                        filtered_df[available_cols], 
                        use_container_width=True,
                        height=400
                    )
                    
                    # Download filtered results
                    csv = filtered_df.to_csv(index=False)
                    st.download_button(
                        label=f"📥 Download Filtered Results ({len(filtered_df)} properties)",
                        data=csv,
                        file_name=f"filtered_properties_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("No properties match your filters")
            else:
                st.info("No properties found")
        else:
            st.warning("Unable to fetch properties")
    except Exception as e:
        st.error(f"Error: {e}")

with tab3:
    st.header("Entity View")
    st.caption("Properties grouped by entity with aggregated tax information")
    
    # Fetch data
    try:
        # Fetch properties and extractions
        props_response = requests.get(f"{API_URL}/api/v1/properties", timeout=10)
        extractions_response = requests.get(f"{API_URL}/api/v1/extractions", timeout=10)
        
        if props_response.status_code == 200 and extractions_response.status_code == 200:
            properties = props_response.json().get("properties", [])
            extractions = extractions_response.json().get("extractions", [])
            
            if properties:
                # Create DataFrames
                df_props = pd.DataFrame(properties)
                df_extracts = pd.DataFrame(extractions) if extractions else pd.DataFrame()
                
                # Get latest extraction for each property if we have extractions
                if not df_extracts.empty and 'property_id' in df_extracts.columns:
                    # Sort by extraction date and get the latest for each property
                    if 'extraction_date' in df_extracts.columns:
                        df_extracts['extraction_date'] = pd.to_datetime(df_extracts['extraction_date'])
                        latest_extracts = df_extracts.sort_values('extraction_date').groupby('property_id').last()
                    else:
                        latest_extracts = df_extracts.groupby('property_id').last()
                    
                    # Merge with properties
                    df_merged = df_props.merge(
                        latest_extracts[['tax_amount', 'previous_year_tax'] if 'tax_amount' in latest_extracts.columns else []],
                        left_on='id',
                        right_index=True,
                        how='left'
                    )
                else:
                    df_merged = df_props
                    df_merged['tax_amount'] = 0
                    df_merged['previous_year_tax'] = 0
                
                # Fill NaN values with 0 for tax amounts
                if 'tax_amount' in df_merged.columns:
                    df_merged['tax_amount'] = df_merged['tax_amount'].fillna(0)
                if 'previous_year_tax' in df_merged.columns:
                    df_merged['previous_year_tax'] = df_merged['previous_year_tax'].fillna(0)
                
                # Group by entity
                if 'entity_name' in df_merged.columns:
                    entity_groups = df_merged.groupby('entity_name').agg({
                        'property_name': 'count',
                        'tax_amount': 'sum',
                        'previous_year_tax': 'sum',
                        'state': lambda x: ', '.join(sorted(x.dropna().unique()))
                    }).round(2)
                    
                    entity_groups.columns = ['Properties', 'Current Tax', 'Previous Tax', 'States']
                    entity_groups['Tax Change'] = entity_groups['Current Tax'] - entity_groups['Previous Tax']
                    entity_groups['Change %'] = ((entity_groups['Tax Change'] / entity_groups['Previous Tax'] * 100)
                                                .replace([float('inf'), -float('inf')], 0)
                                                .fillna(0)
                                                .round(1))
                    
                    # Sort by current tax amount
                    entity_groups = entity_groups.sort_values('Current Tax', ascending=False)
                    
                    # Display summary metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Entities", len(entity_groups))
                    with col2:
                        st.metric("Total Current Tax", f"${entity_groups['Current Tax'].sum():,.2f}")
                    with col3:
                        st.metric("Total Previous Tax", f"${entity_groups['Previous Tax'].sum():,.2f}")
                    with col4:
                        total_change = entity_groups['Tax Change'].sum()
                        st.metric("Total Change", f"${total_change:,.2f}", 
                                delta=f"{total_change:+,.2f}")
                    
                    # Entity selector
                    selected_entity_detail = st.selectbox(
                        "Select an entity to view details:",
                        ["Overview"] + entity_groups.index.tolist()
                    )
                    
                    if selected_entity_detail == "Overview":
                        # Display entity summary table
                        st.subheader("All Entities Summary")
                        
                        # Format the dataframe for display
                        display_df = entity_groups.copy()
                        display_df['Current Tax'] = display_df['Current Tax'].apply(lambda x: f"${x:,.2f}")
                        display_df['Previous Tax'] = display_df['Previous Tax'].apply(lambda x: f"${x:,.2f}")
                        display_df['Tax Change'] = display_df['Tax Change'].apply(lambda x: f"${x:+,.2f}")
                        display_df['Change %'] = display_df['Change %'].apply(lambda x: f"{x:+.1f}%")
                        
                        st.dataframe(display_df, use_container_width=True, height=400)
                        
                        # Download button for entity summary
                        csv = entity_groups.to_csv()
                        st.download_button(
                            label="📥 Download Entity Summary",
                            data=csv,
                            file_name=f"entity_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                    else:
                        # Display details for selected entity
                        st.subheader(f"Entity Details: {selected_entity_detail}")
                        
                        # Get properties for this entity
                        entity_properties = df_merged[df_merged['entity_name'] == selected_entity_detail]
                        
                        # Entity metrics
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Properties", len(entity_properties))
                        with col2:
                            current_tax = entity_properties['tax_amount'].sum()
                            st.metric("Current Tax", f"${current_tax:,.2f}")
                        with col3:
                            prev_tax = entity_properties['previous_year_tax'].sum()
                            st.metric("Previous Tax", f"${prev_tax:,.2f}")
                        with col4:
                            change = current_tax - prev_tax
                            st.metric("Change", f"${change:,.2f}", delta=f"{change:+,.2f}")
                        
                        # Property details table
                        st.subheader("Properties")
                        display_cols = ['property_name', 'property_address', 'jurisdiction', 'state', 'tax_amount', 'previous_year_tax']
                        available_cols = [col for col in display_cols if col in entity_properties.columns]
                        
                        if available_cols:
                            detail_df = entity_properties[available_cols].copy()
                            if 'tax_amount' in detail_df.columns:
                                detail_df['tax_amount'] = detail_df['tax_amount'].apply(lambda x: f"${x:,.2f}" if x > 0 else "-")
                            if 'previous_year_tax' in detail_df.columns:
                                detail_df['previous_year_tax'] = detail_df['previous_year_tax'].apply(lambda x: f"${x:,.2f}" if x > 0 else "-")
                            
                            detail_df.columns = [col.replace('_', ' ').title() for col in detail_df.columns]
                            st.dataframe(detail_df, use_container_width=True, height=300)
                            
                            # Download entity properties
                            csv = entity_properties.to_csv(index=False)
                            st.download_button(
                                label=f"📥 Download {selected_entity_detail} Properties",
                                data=csv,
                                file_name=f"{selected_entity_detail.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv"
                            )
                else:
                    st.info("No entity information available")
            else:
                st.info("No properties found")
        else:
            st.warning("Unable to fetch data")
    except Exception as e:
        st.error(f"Error: {e}")

st.divider()
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")