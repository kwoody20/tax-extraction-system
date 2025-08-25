"""
Streamlit Dashboard for Tax Extraction System.
Enhanced version with improved UI/UX, filtering, and visualizations.
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

st.set_page_config(
    page_title="Tax Dashboard",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

# Custom CSS for better styling
st.markdown("""
<style>
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
</style>
""", unsafe_allow_html=True)

# Get API URL from secrets or environment
try:
    API_URL = st.secrets["API_URL"]
except:
    API_URL = "https://tax-extraction-system-production.up.railway.app"

# Initialize session state
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = datetime.now()
if 'properties_data' not in st.session_state:
    st.session_state.properties_data = None
if 'stats_data' not in st.session_state:
    st.session_state.stats_data = None

# Cache data fetching functions
@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_properties():
    """Fetch properties data from API with caching."""
    try:
        response = requests.get(f"{API_URL}/api/v1/properties", timeout=10)
        if response.status_code == 200:
            return response.json().get("properties", [])
    except Exception as e:
        st.error(f"Error fetching properties: {e}")
    return []

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
def fetch_entities():
    """Fetch entities data from API with caching."""
    try:
        response = requests.get(f"{API_URL}/api/v1/entities", timeout=10)
        if response.status_code == 200:
            return response.json().get("entities", [])
    except Exception as e:
        st.error(f"Error fetching entities: {e}")
    return []

def check_api_health():
    """Check API health status."""
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        data = response.json()
        return response.status_code, data
    except Exception:
        return None, None

def format_paid_by(value):
    """Format paid_by field with color coding."""
    if pd.isna(value) or value == "":
        return "-"
    
    value_lower = str(value).lower()
    if "landlord" in value_lower:
        return f'<span class="paid-by-landlord">{value}</span>'
    elif "reimburse" in value_lower:
        return f'<span class="paid-by-reimburse">{value}</span>'
    elif "tenant" in value_lower:
        return f'<span class="paid-by-tenant">{value}</span>'
    else:
        return value

def format_due_date(date_str):
    """Format due date with color coding based on urgency."""
    if pd.isna(date_str) or date_str == "":
        return "-"
    
    try:
        due_date = pd.to_datetime(date_str)
        formatted_date = due_date.strftime('%m/%d/%Y')
        days_until = (due_date - datetime.now()).days
        
        if days_until < 0:
            return f'<span class="due-soon">⚠️ {formatted_date} (OVERDUE)</span>'
        elif days_until <= 30:
            return f'<span class="due-soon">⏰ {formatted_date} ({days_until}d)</span>'
        else:
            return f'<span class="due-later">✓ {formatted_date}</span>'
    except:
        return date_str

# Header with title and refresh controls
col1, col2, col3 = st.columns([3, 1, 1])
with col1:
    st.title("🏢 Property Tax Dashboard")
    st.caption("Real-time monitoring of property tax data with enhanced analytics")

with col2:
    if st.button("🔄 Refresh Data", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.session_state.last_refresh = datetime.now()
        st.rerun()

with col3:
    refresh_time = st.session_state.last_refresh.strftime("%H:%M:%S")
    st.metric("Last Refresh", refresh_time, label_visibility="visible")

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
    
    # Filters Section
    st.header("🔍 Filters")
    
    # Load properties for filter options
    properties = fetch_properties()
    
    if properties:
        df_props = pd.DataFrame(properties)
        
        # Paid By Filter
        if 'paid_by' in df_props.columns:
            paid_by_options = ["All"] + sorted(df_props['paid_by'].dropna().unique().tolist())
            selected_paid_by = st.selectbox("💰 Paid By", paid_by_options)
        else:
            selected_paid_by = "All"
        
        # State Filter
        if 'state' in df_props.columns:
            state_options = ["All"] + sorted(df_props['state'].dropna().unique().tolist())
            selected_state = st.selectbox("📍 State", state_options)
        else:
            selected_state = "All"
        
        # Jurisdiction Filter
        if 'jurisdiction' in df_props.columns:
            jurisdiction_options = ["All"] + sorted(df_props['jurisdiction'].dropna().unique().tolist())
            selected_jurisdiction = st.selectbox("🏛️ Jurisdiction", jurisdiction_options, key="jurisdiction_filter")
        else:
            selected_jurisdiction = "All"
        
        # Due Date Range Filter
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
                    format="MM/DD/YYYY"
                )
            else:
                date_range = None
        else:
            date_range = None
        
        # Quick Filters
        st.subheader("⚡ Quick Filters")
        show_overdue = st.checkbox("Show Overdue Only", value=False)
        show_upcoming_30 = st.checkbox("Due in Next 30 Days", value=False)

# Main content with enhanced tabs
tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "🏢 Properties", "👥 Entities", "📈 Analytics"])

# Load data once for all tabs
with st.spinner("Loading data..."):
    properties = fetch_properties()
    stats = fetch_statistics()
    entities = fetch_entities()

# Apply filters if data is available
if properties:
    df = pd.DataFrame(properties)
    
    # Add datetime columns for filtering
    if 'tax_due_date' in df.columns:
        df['tax_due_date_dt'] = pd.to_datetime(df['tax_due_date'], errors='coerce')
    
    # Apply filters from sidebar
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
    
    if not df.empty:
        # Display summary
        st.info(f"Showing {len(df)} properties based on current filters")
        
        # Prepare display dataframe
        display_df = df.copy()
        
        # Format columns for display
        if 'tax_due_date' in display_df.columns:
            display_df['tax_due_date_formatted'] = display_df['tax_due_date_dt'].apply(
                lambda x: format_due_date(x) if pd.notna(x) else "-"
            )
        
        if 'paid_by' in display_df.columns:
            display_df['paid_by_formatted'] = display_df['paid_by'].apply(format_paid_by)
        
        # Select columns to display
        display_cols = ['property_name', 'property_address', 'jurisdiction', 'state']
        
        if 'tax_due_date_formatted' in display_df.columns:
            display_cols.append('tax_due_date_formatted')
        
        if 'paid_by_formatted' in display_df.columns:
            display_cols.append('paid_by_formatted')
        
        # Rename columns for display
        rename_map = {
            'property_name': 'Property Name',
            'property_address': 'Address',
            'jurisdiction': 'Jurisdiction',
            'state': 'State',
            'tax_due_date_formatted': 'Due Date',
            'paid_by_formatted': 'Paid By'
        }
        
        display_df = display_df[display_cols].rename(columns=rename_map)
        
        # Display with HTML for formatting
        st.write(display_df.to_html(escape=False, index=False), unsafe_allow_html=True)
        
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
            # JSON export
            json_data = df.to_json(orient='records', date_format='iso')
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
                display_cols = ['entity_name', 'entity_type', 'property_count', 'created_at']
                available_cols = [col for col in display_cols if col in single_df.columns]
                
                if available_cols:
                    st.dataframe(
                        single_df[available_cols],
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
            # JSON export
            json_data = entities_df.to_json(orient='records', date_format='iso')
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