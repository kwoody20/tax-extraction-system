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
    initial_sidebar_state="expanded"
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
tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "🏢 Properties", "📅 Calendar View", "📈 Analytics"])

# Load data once for all tabs
with st.spinner("Loading data..."):
    properties = fetch_properties()
    stats = fetch_statistics()

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
    st.header("📅 Tax Due Date Calendar")
    
    if not df.empty and 'tax_due_date_dt' in df.columns:
        # Filter for valid dates
        calendar_df = df[df['tax_due_date_dt'].notna()].copy()
        
        if not calendar_df.empty:
            # Create calendar view
            calendar_df['due_date'] = calendar_df['tax_due_date_dt'].dt.date
            calendar_df['due_month'] = calendar_df['tax_due_date_dt'].dt.to_period('M')
            
            # Group by date for calendar
            events = []
            for _, row in calendar_df.iterrows():
                event_color = '#28a745'  # Default green
                if row['tax_due_date_dt'] < datetime.now():
                    event_color = '#dc3545'  # Red for overdue
                elif row['tax_due_date_dt'] <= datetime.now() + timedelta(days=30):
                    event_color = '#ffc107'  # Yellow for upcoming
                
                events.append({
                    'Property': row.get('property_name', 'Unknown'),
                    'Due Date': row['due_date'],
                    'Paid By': row.get('paid_by', 'Unknown'),
                    'Jurisdiction': row.get('jurisdiction', 'Unknown'),
                    'Color': event_color
                })
            
            # Create timeline visualization
            fig = go.Figure()
            
            for event in events:
                fig.add_trace(go.Scatter(
                    x=[event['Due Date']],
                    y=[event['Paid By']],
                    mode='markers+text',
                    marker=dict(size=12, color=event['Color']),
                    text=event['Property'],
                    textposition="top center",
                    hovertemplate=f"<b>{event['Property']}</b><br>" +
                                 f"Due: {event['Due Date']}<br>" +
                                 f"Paid By: {event['Paid By']}<br>" +
                                 f"Jurisdiction: {event['Jurisdiction']}<br>" +
                                 "<extra></extra>",
                    showlegend=False
                ))
            
            fig.update_layout(
                title="Tax Due Dates Timeline",
                xaxis_title="Due Date",
                yaxis_title="Payment Responsibility",
                height=600,
                hovermode='closest',
                xaxis=dict(
                    tickformat='%b %d, %Y',
                    tickangle=-45
                )
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Monthly view
            st.divider()
            st.subheader("📆 Monthly Summary")
            
            # Group by month
            # Determine which columns to aggregate
            month_agg_dict = {}
            
            # Use first available column for count
            if len(calendar_df.columns) > 0:
                count_col = calendar_df.columns[0]
                month_agg_dict[count_col] = 'count'
            
            # Add paid_by aggregation if available
            if 'paid_by' in calendar_df.columns:
                month_agg_dict['paid_by'] = lambda x: x.value_counts().to_dict()
            
            if month_agg_dict:
                monthly = calendar_df.groupby(calendar_df['tax_due_date_dt'].dt.to_period('M')).agg(month_agg_dict).reset_index()
                
                # Rename columns based on what was aggregated
                col_names = ['Month']
                if count_col in month_agg_dict:
                    col_names.append('Count')
                if 'paid_by' in month_agg_dict:
                    col_names.append('Paid By Distribution')
                monthly.columns = col_names[:len(monthly.columns)]
            else:
                # Create empty monthly dataframe if no aggregation possible
                monthly = pd.DataFrame({'Month': [], 'Count': [], 'Paid By Distribution': []})
            monthly['Month'] = monthly['Month'].astype(str)
            
            # Display monthly summary
            for _, row in monthly.iterrows():
                with st.expander(f"📅 {row['Month']} ({row['Count']} properties)"):
                    month_properties = calendar_df[
                        calendar_df['tax_due_date_dt'].dt.to_period('M').astype(str) == row['Month']
                    ]
                    
                    for _, prop in month_properties.iterrows():
                        st.write(f"• **{prop.get('property_name', 'Unknown')}** - "
                                f"Due: {prop['tax_due_date_dt'].strftime('%m/%d/%Y')} - "
                                f"Paid by: {prop.get('paid_by', 'Unknown')}")
        else:
            st.info("No properties with valid due dates found")
    else:
        st.info("No due date information available")

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