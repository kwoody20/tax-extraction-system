"""
Utility functions for Streamlit dashboard optimization.
Provides reusable components and helper functions.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import numpy as np

# Color schemes for consistent visualization
COLORS = {
    'primary': '#667eea',
    'secondary': '#764ba2',
    'success': '#48bb78',
    'warning': '#f6ad55',
    'danger': '#fc8181',
    'info': '#63b3ed',
    'dark': '#2d3748',
    'light': '#f7fafc'
}

COLOR_SCALES = {
    'sequential': 'Viridis',
    'diverging': 'RdYlGn',
    'categorical': px.colors.qualitative.Set3
}

@st.cache_data
def format_currency(value: float, symbol: str = "$") -> str:
    """Format currency values with proper handling."""
    if pd.isna(value) or value is None:
        return f"{symbol}0.00"
    return f"{symbol}{value:,.2f}"

@st.cache_data
def format_percentage(value: float, decimals: int = 1) -> str:
    """Format percentage values."""
    if pd.isna(value) or value is None:
        return "0.0%"
    return f"{value:.{decimals}f}%"

@st.cache_data
def calculate_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    """Calculate comprehensive metrics from dataframe."""
    metrics = {}
    
    if df.empty:
        return metrics
    
    # Basic counts
    metrics['total_properties'] = len(df)
    
    # Financial metrics
    if 'outstanding_tax' in df.columns:
        metrics['total_outstanding'] = df['outstanding_tax'].sum()
        metrics['avg_outstanding'] = df['outstanding_tax'].mean()
        metrics['median_outstanding'] = df['outstanding_tax'].median()
        metrics['max_outstanding'] = df['outstanding_tax'].max()
    
    if 'amount_due' in df.columns:
        metrics['total_due'] = df['amount_due'].sum()
        metrics['avg_due'] = df['amount_due'].mean()
    
    # Date-based metrics
    if 'tax_due_date_dt' in df.columns:
        now = datetime.now()
        valid_dates = df[df['tax_due_date_dt'].notna()]
        
        metrics['overdue_count'] = len(valid_dates[valid_dates['tax_due_date_dt'] < now])
        metrics['due_7_days'] = len(valid_dates[
            (valid_dates['tax_due_date_dt'] >= now) & 
            (valid_dates['tax_due_date_dt'] <= now + timedelta(days=7))
        ])
        metrics['due_30_days'] = len(valid_dates[
            (valid_dates['tax_due_date_dt'] >= now) & 
            (valid_dates['tax_due_date_dt'] <= now + timedelta(days=30))
        ])
    
    # Category metrics
    if 'paid_by' in df.columns:
        metrics['paid_by_distribution'] = df['paid_by'].value_counts().to_dict()
    
    if 'state' in df.columns:
        metrics['state_distribution'] = df['state'].value_counts().to_dict()
    
    if 'jurisdiction' in df.columns:
        metrics['jurisdiction_count'] = df['jurisdiction'].nunique()
        metrics['top_jurisdictions'] = df['jurisdiction'].value_counts().head(5).to_dict()
    
    return metrics

def create_metric_card(label: str, value: Any, delta: Any = None, 
                       delta_color: str = "normal", help_text: str = None) -> None:
    """Create an enhanced metric card with styling."""
    col = st.container()
    with col:
        if help_text:
            st.metric(label, value, delta, delta_color=delta_color, help=help_text)
        else:
            st.metric(label, value, delta, delta_color=delta_color)

def create_kpi_dashboard(metrics: Dict[str, Any]) -> None:
    """Create a KPI dashboard from metrics dictionary."""
    # Primary KPIs
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        create_metric_card(
            "Total Properties",
            metrics.get('total_properties', 0),
            help_text="Total number of properties in current view"
        )
    
    with col2:
        create_metric_card(
            "Total Outstanding",
            format_currency(metrics.get('total_outstanding', 0)),
            help_text="Total tax amount outstanding"
        )
    
    with col3:
        create_metric_card(
            "Overdue Properties",
            metrics.get('overdue_count', 0),
            delta_color="inverse" if metrics.get('overdue_count', 0) > 0 else "normal",
            help_text="Properties with overdue tax payments"
        )
    
    with col4:
        due_soon = metrics.get('due_7_days', 0)
        create_metric_card(
            "Due in 7 Days",
            due_soon,
            delta_color="inverse" if due_soon > 5 else "normal",
            help_text="Properties with tax due within a week"
        )

def create_distribution_chart(df: pd.DataFrame, column: str, title: str,
                             chart_type: str = "pie", top_n: int = None) -> go.Figure:
    """Create a distribution chart for categorical data."""
    if column not in df.columns:
        return None
    
    value_counts = df[column].value_counts()
    
    if top_n:
        value_counts = value_counts.head(top_n)
    
    if chart_type == "pie":
        fig = px.pie(
            values=value_counts.values,
            names=value_counts.index,
            title=title,
            hole=0.4
        )
        fig.update_traces(textposition='inside', textinfo='percent+label')
    
    elif chart_type == "bar":
        fig = px.bar(
            x=value_counts.index,
            y=value_counts.values,
            title=title,
            labels={'x': column, 'y': 'Count'},
            color=value_counts.values,
            color_continuous_scale=COLOR_SCALES['sequential']
        )
    
    elif chart_type == "horizontal_bar":
        fig = px.bar(
            x=value_counts.values,
            y=value_counts.index,
            orientation='h',
            title=title,
            labels={'x': 'Count', 'y': column},
            color=value_counts.values,
            color_continuous_scale=COLOR_SCALES['sequential']
        )
    
    else:
        return None
    
    fig.update_layout(
        showlegend=True,
        height=400,
        font=dict(size=12)
    )
    
    return fig

def create_timeline_chart(df: pd.DataFrame, date_column: str, 
                         value_column: str = None, title: str = "Timeline") -> go.Figure:
    """Create a timeline chart for date-based data."""
    if date_column not in df.columns:
        return None
    
    # Prepare data
    timeline_df = df[df[date_column].notna()].copy()
    timeline_df['month'] = pd.to_datetime(timeline_df[date_column]).dt.to_period('M').astype(str)
    
    if value_column and value_column in timeline_df.columns:
        # Aggregate by month with value
        monthly_data = timeline_df.groupby('month')[value_column].sum().reset_index()
        
        fig = px.bar(
            monthly_data,
            x='month',
            y=value_column,
            title=title,
            color=value_column,
            color_continuous_scale=COLOR_SCALES['sequential']
        )
    else:
        # Count by month
        monthly_data = timeline_df.groupby('month').size().reset_index(name='count')
        
        fig = px.bar(
            monthly_data,
            x='month',
            y='count',
            title=title,
            color='count',
            color_continuous_scale=COLOR_SCALES['sequential']
        )
    
    fig.update_layout(
        xaxis_tickangle=-45,
        height=400,
        showlegend=False
    )
    
    return fig

def create_heatmap(df: pd.DataFrame, row_col: str, col_col: str, 
                  value_col: str = None, title: str = "Heatmap") -> go.Figure:
    """Create a heatmap for cross-tabulation analysis."""
    if row_col not in df.columns or col_col not in df.columns:
        return None
    
    if value_col and value_col in df.columns:
        # Pivot with values
        pivot_table = df.pivot_table(
            index=row_col,
            columns=col_col,
            values=value_col,
            aggfunc='sum',
            fill_value=0
        )
    else:
        # Cross-tabulation (count)
        pivot_table = pd.crosstab(df[row_col], df[col_col])
    
    fig = px.imshow(
        pivot_table,
        labels=dict(x=col_col, y=row_col, color="Value"),
        title=title,
        color_continuous_scale=COLOR_SCALES['diverging'],
        aspect='auto'
    )
    
    fig.update_layout(height=400)
    
    return fig

def create_treemap(df: pd.DataFrame, path_cols: List[str], 
                  value_col: str, title: str = "Treemap") -> go.Figure:
    """Create a hierarchical treemap visualization."""
    if not all(col in df.columns for col in path_cols):
        return None
    
    if value_col not in df.columns:
        return None
    
    fig = px.treemap(
        df,
        path=path_cols,
        values=value_col,
        title=title,
        color=value_col,
        color_continuous_scale=COLOR_SCALES['sequential']
    )
    
    fig.update_layout(height=500)
    
    return fig

def create_gauge_chart(value: float, max_value: float, title: str,
                      thresholds: List[float] = None) -> go.Figure:
    """Create a gauge chart for single metric visualization."""
    if thresholds is None:
        thresholds = [max_value * 0.3, max_value * 0.7, max_value]
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=value,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': title},
        delta={'reference': max_value * 0.5},
        gauge={
            'axis': {'range': [None, max_value]},
            'bar': {'color': COLORS['primary']},
            'steps': [
                {'range': [0, thresholds[0]], 'color': COLORS['success']},
                {'range': [thresholds[0], thresholds[1]], 'color': COLORS['warning']},
                {'range': [thresholds[1], thresholds[2]], 'color': COLORS['danger']}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': max_value * 0.9
            }
        }
    ))
    
    fig.update_layout(height=300)
    
    return fig

def create_comparison_chart(df1: pd.DataFrame, df2: pd.DataFrame, 
                           label1: str, label2: str, 
                           value_col: str, title: str) -> go.Figure:
    """Create a comparison chart between two datasets."""
    fig = go.Figure()
    
    # Add first dataset
    if value_col in df1.columns:
        fig.add_trace(go.Bar(
            name=label1,
            x=df1.index,
            y=df1[value_col],
            marker_color=COLORS['primary']
        ))
    
    # Add second dataset
    if value_col in df2.columns:
        fig.add_trace(go.Bar(
            name=label2,
            x=df2.index,
            y=df2[value_col],
            marker_color=COLORS['secondary']
        ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Category",
        yaxis_title=value_col,
        barmode='group',
        height=400
    )
    
    return fig

def create_progress_indicator(current: int, total: int, label: str = "Progress") -> None:
    """Create a progress indicator with percentage."""
    if total > 0:
        progress = current / total
        percentage = progress * 100
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.progress(progress)
        with col2:
            st.write(f"{percentage:.1f}%")
        
        st.caption(f"{label}: {current} of {total}")

def create_data_quality_report(df: pd.DataFrame) -> Dict[str, Any]:
    """Generate a data quality report for the dataframe."""
    report = {
        'total_rows': len(df),
        'total_columns': len(df.columns),
        'missing_values': {},
        'completeness': {},
        'data_types': {}
    }
    
    for col in df.columns:
        # Missing values
        missing = df[col].isna().sum()
        report['missing_values'][col] = missing
        
        # Completeness percentage
        completeness = ((len(df) - missing) / len(df)) * 100
        report['completeness'][col] = completeness
        
        # Data types
        report['data_types'][col] = str(df[col].dtype)
    
    # Overall completeness
    total_cells = len(df) * len(df.columns)
    total_missing = sum(report['missing_values'].values())
    report['overall_completeness'] = ((total_cells - total_missing) / total_cells) * 100
    
    return report

def display_data_quality_report(report: Dict[str, Any]) -> None:
    """Display the data quality report in a formatted way."""
    st.subheader("📊 Data Quality Report")
    
    # Overview metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Rows", report['total_rows'])
    
    with col2:
        st.metric("Total Columns", report['total_columns'])
    
    with col3:
        st.metric("Overall Completeness", f"{report['overall_completeness']:.1f}%")
    
    with col4:
        total_missing = sum(report['missing_values'].values())
        st.metric("Total Missing Values", total_missing)
    
    # Detailed completeness by column
    if st.checkbox("Show detailed column analysis"):
        completeness_df = pd.DataFrame({
            'Column': list(report['completeness'].keys()),
            'Completeness (%)': list(report['completeness'].values()),
            'Missing Values': list(report['missing_values'].values()),
            'Data Type': list(report['data_types'].values())
        })
        
        completeness_df = completeness_df.sort_values('Completeness (%)', ascending=False)
        
        # Color code based on completeness
        def color_completeness(val):
            if val >= 90:
                color = 'green'
            elif val >= 70:
                color = 'yellow'
            else:
                color = 'red'
            return f'color: {color}'
        
        styled_df = completeness_df.style.applymap(
            color_completeness,
            subset=['Completeness (%)']
        )
        
        st.dataframe(styled_df, use_container_width=True)

def export_data(df: pd.DataFrame, format: str = "csv", filename_prefix: str = "export") -> None:
    """Create export buttons for dataframe in multiple formats."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if format == "csv" or format == "all":
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"{filename_prefix}_{timestamp}.csv",
            mime="text/csv"
        )
    
    if format == "excel" or format == "all":
        from io import BytesIO
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Data', index=False)
        excel_data = output.getvalue()
        
        st.download_button(
            label="📊 Download Excel",
            data=excel_data,
            file_name=f"{filename_prefix}_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    if format == "json" or format == "all":
        json_data = df.to_json(orient='records', date_format='iso', indent=2)
        st.download_button(
            label="📋 Download JSON",
            data=json_data,
            file_name=f"{filename_prefix}_{timestamp}.json",
            mime="application/json"
        )

def create_filter_sidebar(df: pd.DataFrame) -> Dict[str, Any]:
    """Create an advanced filter sidebar and return selected filters."""
    filters = {}
    
    st.sidebar.header("🔍 Advanced Filters")
    
    # Text search
    search_term = st.sidebar.text_input("🔎 Search", placeholder="Search all fields...")
    if search_term:
        filters['search'] = search_term
    
    # Column-specific filters
    for col in df.select_dtypes(include=['object']).columns[:5]:  # Limit to first 5 categorical
        unique_values = df[col].dropna().unique()
        if len(unique_values) <= 20:  # Only show filter if reasonable number of options
            selected = st.sidebar.multiselect(
                f"Filter {col}",
                options=unique_values,
                default=None,
                key=f"filter_{col}"
            )
            if selected:
                filters[col] = selected
    
    # Numeric range filters
    for col in df.select_dtypes(include=['int64', 'float64']).columns[:3]:  # Limit to first 3 numeric
        min_val = float(df[col].min())
        max_val = float(df[col].max())
        
        range_values = st.sidebar.slider(
            f"{col} Range",
            min_value=min_val,
            max_value=max_val,
            value=(min_val, max_val),
            key=f"range_{col}"
        )
        
        if range_values != (min_val, max_val):
            filters[f"{col}_range"] = range_values
    
    # Date range filters
    date_columns = df.select_dtypes(include=['datetime64']).columns
    if len(date_columns) > 0:
        for col in date_columns[:2]:  # Limit to first 2 date columns
            min_date = df[col].min()
            max_date = df[col].max()
            
            if pd.notna(min_date) and pd.notna(max_date):
                date_range = st.sidebar.date_input(
                    f"{col} Range",
                    value=(min_date.date(), max_date.date()),
                    min_value=min_date.date(),
                    max_value=max_date.date(),
                    key=f"date_{col}"
                )
                
                if len(date_range) == 2:
                    filters[f"{col}_range"] = date_range
    
    return filters

def apply_advanced_filters(df: pd.DataFrame, filters: Dict[str, Any]) -> pd.DataFrame:
    """Apply advanced filters to dataframe."""
    filtered_df = df.copy()
    
    # Text search across all string columns
    if 'search' in filters:
        search_term = filters['search'].lower()
        mask = pd.Series([False] * len(filtered_df))
        
        for col in filtered_df.select_dtypes(include=['object']).columns:
            mask |= filtered_df[col].astype(str).str.lower().str.contains(search_term, na=False)
        
        filtered_df = filtered_df[mask]
    
    # Apply column-specific filters
    for key, value in filters.items():
        if key in filtered_df.columns:
            filtered_df = filtered_df[filtered_df[key].isin(value)]
        elif key.endswith('_range'):
            col = key.replace('_range', '')
            if col in filtered_df.columns:
                if filtered_df[col].dtype in ['datetime64[ns]', 'datetime64']:
                    # Date range
                    start, end = value
                    filtered_df = filtered_df[
                        (filtered_df[col].dt.date >= start) & 
                        (filtered_df[col].dt.date <= end)
                    ]
                else:
                    # Numeric range
                    min_val, max_val = value
                    filtered_df = filtered_df[
                        (filtered_df[col] >= min_val) & 
                        (filtered_df[col] <= max_val)
                    ]
    
    return filtered_df