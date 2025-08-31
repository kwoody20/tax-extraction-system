"""
Streamlit UI for Document Management
Add this as a new tab to your existing Streamlit dashboard
"""

import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from typing import Optional, List, Dict, Any
import os
from supabase import create_client, Client

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://klscgjbachumeojhxyno.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_KEY else None

# Document Management API URL
DOC_API_URL = os.getenv("DOC_API_URL", "http://localhost:8002")

def document_management_tab():
    """Main document management tab for Streamlit"""
    st.header("📄 Document Management")
    
    # Create sub-tabs
    doc_tab1, doc_tab2, doc_tab3, doc_tab4, doc_tab5 = st.tabs([
        "📤 Upload", 
        "🔍 Search & View", 
        "💰 Payments", 
        "📊 Analytics",
        "🤖 Auto-Extract"
    ])
    
    with doc_tab1:
        upload_documents_section()
    
    with doc_tab2:
        search_documents_section()
    
    with doc_tab3:
        payment_tracking_section()
    
    with doc_tab4:
        document_analytics_section()
    
    with doc_tab5:
        auto_extraction_section()

def upload_documents_section():
    """Document upload section"""
    st.subheader("Upload Tax Documents")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Get properties for dropdown
        properties = supabase.table("properties").select("id, property_name, jurisdiction").execute()
        property_options = {f"{p['property_name']} - {p['jurisdiction']}": p['id'] 
                          for p in properties.data}
        
        selected_property = st.selectbox(
            "Select Property",
            options=list(property_options.keys()),
            help="Choose the property this document belongs to"
        )
        
        document_type = st.selectbox(
            "Document Type",
            options=[
                "tax_bill", "tax_receipt", "payment_confirmation",
                "assessment_notice", "invoice", "statement",
                "correspondence", "legal_document", "other"
            ],
            help="Type of document being uploaded"
        )
        
        tax_year = st.number_input(
            "Tax Year",
            min_value=2020,
            max_value=2030,
            value=datetime.now().year,
            help="Tax year this document relates to"
        )
    
    with col2:
        jurisdiction = st.text_input(
            "Jurisdiction",
            value=properties.data[0]['jurisdiction'] if properties.data else "",
            help="Tax jurisdiction (county, city, etc.)"
        )
        
        amount_due = st.number_input(
            "Amount Due ($)",
            min_value=0.0,
            step=0.01,
            format="%.2f",
            help="Amount due on this document (if applicable)"
        )
        
        due_date = st.date_input(
            "Due Date",
            value=None,
            help="Payment due date (if applicable)"
        )
    
    notes = st.text_area(
        "Notes",
        placeholder="Add any relevant notes about this document...",
        height=100
    )
    
    tags = st.text_input(
        "Tags (comma-separated)",
        placeholder="e.g., urgent, paid, pending-review",
        help="Add tags to help categorize and search documents"
    )
    
    # File upload
    uploaded_file = st.file_uploader(
        "Choose file",
        type=['pdf', 'png', 'jpg', 'jpeg'],
        help="Upload PDF or image files (max 10MB)"
    )
    
    if uploaded_file is not None:
        # Display file info
        st.info(f"📎 {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
        
        if st.button("📤 Upload Document", type="primary"):
            with st.spinner("Uploading and processing document..."):
                try:
                    # Prepare form data
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                    data = {
                        "property_id": property_options[selected_property],
                        "jurisdiction": jurisdiction,
                        "document_type": document_type,
                        "tax_year": tax_year,
                        "amount_due": amount_due if amount_due > 0 else None,
                        "due_date": due_date.isoformat() if due_date else None,
                        "notes": notes if notes else None,
                        "tags": tags if tags else None
                    }
                    
                    # Upload to API
                    response = requests.post(
                        f"{DOC_API_URL}/api/documents/upload",
                        files=files,
                        data=data
                    )
                    
                    if response.status_code == 200:
                        st.success("✅ Document uploaded successfully!")
                        result = response.json()
                        
                        # Show document details
                        if result.get("document"):
                            doc = result["document"]
                            st.json({
                                "Document ID": doc.get("id"),
                                "Storage Path": doc.get("storage_path"),
                                "Status": doc.get("status")
                            })
                            
                            # Trigger OCR if applicable
                            if document_type in ["tax_bill", "invoice", "assessment_notice"]:
                                st.info("🔄 OCR processing started. Text extraction will complete in background.")
                    else:
                        st.error(f"Upload failed: {response.text}")
                        
                except Exception as e:
                    st.error(f"Error uploading document: {str(e)}")

def search_documents_section():
    """Document search and viewing section"""
    st.subheader("Search Documents")
    
    # Search filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        search_text = st.text_input(
            "Search text",
            placeholder="Search in document content...",
            help="Search in document names, notes, and OCR text"
        )
        
        properties = supabase.table("properties").select("id, property_name").execute()
        property_filter = st.selectbox(
            "Filter by Property",
            options=["All"] + [p['property_name'] for p in properties.data]
        )
    
    with col2:
        doc_type_filter = st.selectbox(
            "Document Type",
            options=["All", "tax_bill", "tax_receipt", "invoice", "assessment_notice", "other"]
        )
        
        year_filter = st.selectbox(
            "Tax Year",
            options=["All"] + list(range(datetime.now().year, 2019, -1))
        )
    
    with col3:
        status_filter = st.selectbox(
            "Status",
            options=["All", "pending", "processed", "archived", "failed"]
        )
        
        date_range = st.date_input(
            "Date Range",
            value=(datetime.now() - timedelta(days=30), datetime.now()),
            help="Filter by upload date"
        )
    
    # Search button
    if st.button("🔍 Search Documents"):
        with st.spinner("Searching..."):
            try:
                # Build search parameters
                search_params = {
                    "search_text": search_text if search_text else None,
                    "document_type": doc_type_filter if doc_type_filter != "All" else None,
                    "tax_year": year_filter if year_filter != "All" else None,
                    "status": status_filter if status_filter != "All" else None,
                    "date_from": date_range[0].isoformat() if len(date_range) > 0 else None,
                    "date_to": date_range[1].isoformat() if len(date_range) > 1 else None,
                    "limit": 100
                }
                
                if property_filter != "All":
                    prop_id = next((p['id'] for p in properties.data 
                                  if p['property_name'] == property_filter), None)
                    search_params["property_id"] = prop_id
                
                # Search documents
                response = requests.post(
                    f"{DOC_API_URL}/api/documents/search",
                    json=search_params
                )
                
                if response.status_code == 200:
                    results = response.json()
                    documents = results.get("documents", [])
                    
                    if documents:
                        st.success(f"Found {len(documents)} documents")
                        
                        # Display results in a table
                        display_documents_table(documents)
                    else:
                        st.info("No documents found matching your criteria")
                else:
                    st.error("Search failed")
                    
            except Exception as e:
                st.error(f"Error searching documents: {str(e)}")
    
    # Recent documents
    st.subheader("Recent Documents")
    try:
        recent_docs = supabase.table("tax_documents")\
            .select("*")\
            .order("created_at", desc=True)\
            .limit(10)\
            .execute()
        
        if recent_docs.data:
            display_documents_table(recent_docs.data)
        else:
            st.info("No documents uploaded yet")
            
    except Exception as e:
        st.error(f"Error loading recent documents: {str(e)}")

def display_documents_table(documents: List[Dict]):
    """Display documents in an interactive table"""
    if not documents:
        return
    
    # Prepare data for display
    df = pd.DataFrame(documents)
    
    # Format columns
    display_columns = [
        'document_name', 'document_type', 'jurisdiction',
        'tax_year', 'amount_due', 'due_date', 'status', 'created_at'
    ]
    
    # Filter to available columns
    display_columns = [col for col in display_columns if col in df.columns]
    
    # Format dates
    if 'created_at' in df.columns:
        df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d')
    if 'due_date' in df.columns:
        df['due_date'] = pd.to_datetime(df['due_date'], errors='coerce').dt.strftime('%Y-%m-%d')
    
    # Format amount
    if 'amount_due' in df.columns:
        df['amount_due'] = df['amount_due'].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "-")
    
    # Display table with actions
    for idx, row in df[display_columns].iterrows():
        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
        
        with col1:
            st.write(f"**{row.get('document_name', 'Unnamed')}**")
            st.caption(f"{row.get('document_type', '')} | {row.get('jurisdiction', '')}")
        
        with col2:
            if row.get('amount_due'):
                st.metric("Amount", row['amount_due'])
        
        with col3:
            status = row.get('status', 'pending')
            status_color = {
                'processed': '🟢',
                'pending': '🟡',
                'failed': '🔴',
                'archived': '⚫'
            }.get(status, '⚪')
            st.write(f"{status_color} {status}")
        
        with col4:
            doc_id = documents[idx]['id']
            
            # Action buttons
            action_col1, action_col2, action_col3 = st.columns(3)
            
            with action_col1:
                if st.button("👁️", key=f"view_{doc_id}", help="View details"):
                    view_document_details(documents[idx])
            
            with action_col2:
                if st.button("⬇️", key=f"download_{doc_id}", help="Download"):
                    download_document(doc_id)
            
            with action_col3:
                if st.button("🗑️", key=f"delete_{doc_id}", help="Delete"):
                    if st.confirm(f"Delete {row.get('document_name', 'this document')}?"):
                        delete_document(doc_id)
        
        st.divider()

def view_document_details(document: Dict):
    """Display detailed document information"""
    with st.expander(f"📄 {document.get('document_name', 'Document Details')}", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Basic Information**")
            st.json({
                "Document ID": document.get('id'),
                "Type": document.get('document_type'),
                "Status": document.get('status'),
                "Tax Year": document.get('tax_year'),
                "Jurisdiction": document.get('jurisdiction')
            })
        
        with col2:
            st.write("**Financial Details**")
            st.json({
                "Amount Due": f"${document.get('amount_due', 0):,.2f}" if document.get('amount_due') else "N/A",
                "Due Date": document.get('due_date'),
                "Paid Date": document.get('paid_date', 'Not paid')
            })
        
        # OCR Text
        if document.get('ocr_text'):
            st.write("**Extracted Text (OCR)**")
            st.text_area(
                "OCR Content",
                value=document['ocr_text'][:1000] + "..." if len(document.get('ocr_text', '')) > 1000 else document.get('ocr_text'),
                height=200,
                disabled=True
            )
        
        # Extracted data
        if document.get('extracted_data'):
            st.write("**Extracted Data**")
            st.json(document['extracted_data'])
        
        # Tags and notes
        if document.get('tags'):
            st.write("**Tags**")
            for tag in document['tags']:
                st.badge(tag)
        
        if document.get('notes'):
            st.write("**Notes**")
            st.info(document['notes'])

def download_document(document_id: str):
    """Download a document"""
    try:
        response = requests.get(f"{DOC_API_URL}/api/documents/{document_id}/download")
        if response.status_code == 200:
            st.download_button(
                label="Download File",
                data=response.content,
                file_name=f"document_{document_id}.pdf",
                mime="application/pdf"
            )
        else:
            st.error("Failed to download document")
    except Exception as e:
        st.error(f"Error downloading: {str(e)}")

def delete_document(document_id: str):
    """Delete a document"""
    try:
        response = requests.delete(f"{DOC_API_URL}/api/documents/{document_id}")
        if response.status_code == 200:
            st.success("Document deleted successfully")
            st.rerun()
        else:
            st.error("Failed to delete document")
    except Exception as e:
        st.error(f"Error deleting: {str(e)}")

def payment_tracking_section():
    """Payment tracking section"""
    st.subheader("Payment Tracking")
    
    # Upcoming payments
    st.write("### 📅 Upcoming Payments")
    
    try:
        upcoming = supabase.table("upcoming_payments").select("*").execute()
        
        if upcoming.data:
            # Group by status
            overdue = [p for p in upcoming.data if p.get('payment_status') == 'overdue']
            due_soon = [p for p in upcoming.data if p.get('payment_status') == 'due_soon']
            upcoming_later = [p for p in upcoming.data if p.get('payment_status') == 'upcoming']
            
            # Display by urgency
            if overdue:
                st.error(f"⚠️ {len(overdue)} Overdue Payments")
                for payment in overdue:
                    display_payment_card(payment, "overdue")
            
            if due_soon:
                st.warning(f"🔔 {len(due_soon)} Due Soon (within 7 days)")
                for payment in due_soon:
                    display_payment_card(payment, "due_soon")
            
            if upcoming_later:
                st.info(f"📅 {len(upcoming_later)} Upcoming Payments")
                for payment in upcoming_later[:5]:  # Show only first 5
                    display_payment_card(payment, "upcoming")
        else:
            st.info("No upcoming payments")
            
    except Exception as e:
        st.error(f"Error loading payments: {str(e)}")
    
    # Record payment
    st.write("### 💳 Record Payment")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Get unpaid documents
        unpaid_docs = supabase.table("tax_documents")\
            .select("id, document_name, amount_due")\
            .is_("paid_date", "null")\
            .not_.is_("amount_due", "null")\
            .execute()
        
        if unpaid_docs.data:
            doc_options = {f"{d['document_name']} (${d['amount_due']:,.2f})": d['id'] 
                          for d in unpaid_docs.data}
            
            selected_doc = st.selectbox(
                "Select Document",
                options=list(doc_options.keys())
            )
            
            payment_amount = st.number_input(
                "Payment Amount ($)",
                min_value=0.01,
                step=0.01,
                format="%.2f"
            )
            
            payment_date = st.date_input(
                "Payment Date",
                value=datetime.now()
            )
    
    with col2:
        payment_method = st.selectbox(
            "Payment Method",
            options=["check", "ach", "credit_card", "wire", "cash"]
        )
        
        confirmation_number = st.text_input(
            "Confirmation Number",
            placeholder="Optional confirmation/check number"
        )
        
        paid_by = st.selectbox(
            "Paid By",
            options=["landlord", "tenant", "property_manager", "other"]
        )
    
    payment_notes = st.text_area(
        "Payment Notes",
        placeholder="Any additional notes about this payment..."
    )
    
    if st.button("💾 Record Payment", type="primary"):
        if unpaid_docs.data and selected_doc:
            try:
                payment_data = {
                    "document_id": doc_options[selected_doc],
                    "property_id": unpaid_docs.data[0].get('property_id'),  # You might need to fetch this
                    "payment_amount": payment_amount,
                    "payment_date": payment_date.isoformat(),
                    "payment_method": payment_method,
                    "confirmation_number": confirmation_number if confirmation_number else None,
                    "paid_by": paid_by,
                    "notes": payment_notes if payment_notes else None
                }
                
                response = requests.post(
                    f"{DOC_API_URL}/api/documents/record-payment",
                    json=payment_data
                )
                
                if response.status_code == 200:
                    st.success("✅ Payment recorded successfully!")
                    st.balloons()
                else:
                    st.error("Failed to record payment")
                    
            except Exception as e:
                st.error(f"Error recording payment: {str(e)}")

def display_payment_card(payment: Dict, status: str):
    """Display a payment card"""
    colors = {
        "overdue": "🔴",
        "due_soon": "🟡",
        "upcoming": "🟢"
    }
    
    with st.container():
        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
        
        with col1:
            st.write(f"{colors[status]} **{payment.get('property_name', 'Unknown Property')}**")
            st.caption(f"{payment.get('jurisdiction', '')} - {payment.get('document_name', '')}")
        
        with col2:
            st.metric("Amount", f"${payment.get('amount_due', 0):,.2f}")
        
        with col3:
            due_date = payment.get('due_date')
            if due_date:
                days_until = (pd.to_datetime(due_date) - pd.Timestamp.now()).days
                st.metric("Due", due_date, f"{days_until} days")
        
        with col4:
            if st.button("Pay", key=f"pay_{payment.get('document_id')}"):
                st.info("Redirect to payment recording...")

def document_analytics_section():
    """Document analytics section"""
    st.subheader("Document Analytics")
    
    # Get summary statistics
    try:
        summary = supabase.table("document_summary").select("*").execute()
        
        if summary.data:
            # Overall metrics
            col1, col2, col3, col4 = st.columns(4)
            
            total_docs = sum(s.get('total_documents', 0) for s in summary.data)
            total_bills = sum(s.get('tax_bills', 0) for s in summary.data)
            total_receipts = sum(s.get('receipts', 0) for s in summary.data)
            total_due = sum(s.get('total_amount_due', 0) for s in summary.data if s.get('total_amount_due'))
            
            with col1:
                st.metric("Total Documents", total_docs)
            with col2:
                st.metric("Tax Bills", total_bills)
            with col3:
                st.metric("Receipts", total_receipts)
            with col4:
                st.metric("Total Due", f"${total_due:,.2f}")
            
            # Charts
            col1, col2 = st.columns(2)
            
            with col1:
                # Documents by type
                doc_types = supabase.table("tax_documents")\
                    .select("document_type")\
                    .execute()
                
                if doc_types.data:
                    df_types = pd.DataFrame(doc_types.data)
                    type_counts = df_types['document_type'].value_counts()
                    
                    fig = px.pie(
                        values=type_counts.values,
                        names=type_counts.index,
                        title="Documents by Type"
                    )
                    st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Documents by jurisdiction
                df_summary = pd.DataFrame(summary.data)
                if 'jurisdiction' in df_summary.columns:
                    fig = px.bar(
                        df_summary,
                        x='jurisdiction',
                        y='total_documents',
                        title="Documents by Jurisdiction"
                    )
                    st.plotly_chart(fig, use_container_width=True)
            
            # Timeline chart
            timeline_data = supabase.table("tax_documents")\
                .select("created_at, document_type")\
                .execute()
            
            if timeline_data.data:
                df_timeline = pd.DataFrame(timeline_data.data)
                df_timeline['created_at'] = pd.to_datetime(df_timeline['created_at'])
                df_timeline['month'] = df_timeline['created_at'].dt.to_period('M')
                
                monthly_counts = df_timeline.groupby(['month', 'document_type']).size().reset_index(name='count')
                monthly_counts['month'] = monthly_counts['month'].astype(str)
                
                fig = px.line(
                    monthly_counts,
                    x='month',
                    y='count',
                    color='document_type',
                    title="Document Upload Timeline",
                    markers=True
                )
                st.plotly_chart(fig, use_container_width=True)
                
    except Exception as e:
        st.error(f"Error loading analytics: {str(e)}")

def auto_extraction_section():
    """Auto-extraction configuration section"""
    st.subheader("🤖 Automated Document Extraction")
    
    st.info("""
    Configure automatic extraction of tax documents from county websites.
    Documents will be automatically downloaded, processed with OCR, and stored.
    """)
    
    # Queue new extraction
    st.write("### Queue Document Extraction")
    
    col1, col2 = st.columns(2)
    
    with col1:
        properties = supabase.table("properties").select("id, property_name, jurisdiction").execute()
        property_options = {f"{p['property_name']} - {p['jurisdiction']}": p 
                          for p in properties.data}
        
        selected_property = st.selectbox(
            "Select Property",
            options=list(property_options.keys()),
            key="extract_property"
        )
        
        extraction_url = st.text_input(
            "Document URL",
            placeholder="https://county-tax-site.com/bill/12345.pdf",
            help="Direct URL to the tax document"
        )
    
    with col2:
        extraction_type = st.selectbox(
            "Document Type",
            options=["tax_bill", "assessment_notice", "tax_receipt"],
            key="extract_type"
        )
        
        priority = st.slider(
            "Priority",
            min_value=1,
            max_value=10,
            value=5,
            help="1 = Highest priority, 10 = Lowest"
        )
    
    if st.button("🚀 Queue Extraction", type="primary"):
        if selected_property and extraction_url:
            try:
                prop_data = property_options[selected_property]
                
                extraction_data = {
                    "property_id": prop_data['id'],
                    "url": extraction_url,
                    "jurisdiction": prop_data['jurisdiction'],
                    "extraction_type": extraction_type,
                    "priority": priority
                }
                
                response = requests.post(
                    f"{DOC_API_URL}/api/documents/extract",
                    json=extraction_data
                )
                
                if response.status_code == 200:
                    st.success("✅ Extraction queued successfully!")
                    result = response.json()
                    st.info(f"Queue ID: {result.get('queue_id')}")
                else:
                    st.error("Failed to queue extraction")
                    
            except Exception as e:
                st.error(f"Error queuing extraction: {str(e)}")
    
    # Extraction queue status
    st.write("### 📋 Extraction Queue Status")
    
    try:
        queue_data = supabase.table("document_extraction_queue")\
            .select("*")\
            .order("queued_at", desc=True)\
            .limit(20)\
            .execute()
        
        if queue_data.data:
            df_queue = pd.DataFrame(queue_data.data)
            
            # Format display
            display_cols = ['jurisdiction', 'extraction_type', 'status', 'priority', 'queued_at']
            available_cols = [col for col in display_cols if col in df_queue.columns]
            
            if 'queued_at' in df_queue.columns:
                df_queue['queued_at'] = pd.to_datetime(df_queue['queued_at']).dt.strftime('%Y-%m-%d %H:%M')
            
            # Color code status
            def color_status(status):
                colors = {
                    'completed': '🟢',
                    'processing': '🔵',
                    'queued': '🟡',
                    'failed': '🔴'
                }
                return f"{colors.get(status, '⚪')} {status}"
            
            if 'status' in df_queue.columns:
                df_queue['status'] = df_queue['status'].apply(color_status)
            
            st.dataframe(
                df_queue[available_cols],
                use_container_width=True,
                hide_index=True
            )
            
            # Process queue button
            if st.button("⚙️ Process Queue Now"):
                response = requests.post(f"{DOC_API_URL}/api/documents/process-queue")
                if response.status_code == 200:
                    st.success("Queue processing started")
                else:
                    st.error("Failed to start queue processing")
        else:
            st.info("No items in extraction queue")
            
    except Exception as e:
        st.error(f"Error loading queue: {str(e)}")

# Export the main function to be imported in your main Streamlit app
if __name__ == "__main__":
    st.set_page_config(
        page_title="Tax Document Manager",
        page_icon="📄",
        layout="wide"
    )
    
    st.title("📄 Tax Document Management System")
    document_management_tab()