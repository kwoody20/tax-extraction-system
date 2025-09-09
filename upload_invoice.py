#!/usr/bin/env python3
"""
Upload Invoice document to the system
"""
import os
import sys
from datetime import datetime
from uuid import uuid4
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://klscgjbachumeojhxyno.supabase.co")
SUPABASE_KEY = (
    os.getenv("SUPABASE_ANON_KEY")
    or os.getenv("SUPABASE_KEY")
    or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def find_property_by_address(address_part):
    """Find a property by address"""
    try:
        # Search for property by address
        prop_result = supabase.table("properties").select("*").execute()
        
        # Look for properties with matching address
        for prop in prop_result.data:
            prop_address = prop.get('property_address', '').upper()
            prop_name = prop.get('property_name', '').upper()
            
            if address_part.upper() in prop_address or address_part.upper() in prop_name:
                print(f"Found property: {prop.get('property_name')} (ID: {prop.get('id')})")
                print(f"Address: {prop.get('property_address')}")
                
                # Get entity info if available
                entity_id = prop.get('parent_entity_id')
                if entity_id:
                    entity_result = supabase.table("entities").select("*").eq("id", entity_id).execute()
                    if entity_result.data:
                        entity_name = entity_result.data[0].get('entity_name')
                        print(f"Entity: {entity_name}")
                        return prop.get('id'), entity_id, prop.get('property_name')
                
                return prop.get('id'), None, prop.get('property_name')
        
        print(f"No exact match found for address '{address_part}'")
        
        # Show similar properties
        print("\nShowing properties with INTERSTATE addresses:")
        interstate_props = [p for p in prop_result.data if 'INTERSTATE' in p.get('property_address', '').upper()]
        for prop in interstate_props[:5]:
            print(f"  - {prop.get('property_name')} | {prop.get('property_address')}")
        
        if interstate_props:
            # Use the first Interstate property as fallback
            first_prop = interstate_props[0]
            print(f"\nUsing first Interstate property: {first_prop.get('property_name')}")
            return first_prop.get('id'), first_prop.get('parent_entity_id'), first_prop.get('property_name')
        
        return None, None, None
        
    except Exception as e:
        print(f"Error finding property: {e}")
        return None, None, None

def create_document_record(file_path, property_id, entity_id, property_name):
    """Create a document record in the tax_documents table"""
    try:
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        
        # Extract address from filename
        address_match = file_name.replace('Invoice-', '').replace('.pdf', '')
        
        # Build document data
        document_data = {
            "property_id": property_id,
            "jurisdiction": "Harris County",  # Assuming Harris County based on Interstate 10
            "document_type": "invoice",
            "document_name": f"Invoice - {address_match}",
            "file_name": file_name,
            "file_size": file_size,
            "mime_type": "application/pdf",
            "notes": f"Invoice for property at {address_match}",
            "status": "pending",
            "uploaded_by": "manual_upload"
        }
        
        # Add entity_id if available
        if entity_id:
            try:
                document_data["entity_id"] = entity_id
                result = supabase.table("tax_documents").insert(document_data).execute()
                if result.data:
                    return result.data[0]
            except:
                del document_data["entity_id"]
        
        # Try inserting without entity_id
        result = supabase.table("tax_documents").insert(document_data).execute()
        
        if result.data:
            return result.data[0]
        else:
            print("Failed to create document record")
            return None
            
    except Exception as e:
        print(f"Error creating document record: {e}")
        return None

def main():
    # Document details
    file_path = "/Users/kwoody/Downloads/Invoice-7130 INTERSTATE 10 HWY.pdf"
    address_part = "7130 INTERSTATE 10"
    
    print("=" * 60)
    print("INVOICE DOCUMENT UPLOAD")
    print("=" * 60)
    print(f"Document: {os.path.basename(file_path)}")
    print(f"Address Reference: {address_part}")
    print("-" * 60)
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"❌ Error: File not found: {file_path}")
        sys.exit(1)
    else:
        print(f"✓ File found (size: {os.path.getsize(file_path):,} bytes)")
    
    print("-" * 60)
    print("Searching for related property...")
    
    # Find related property
    property_id, entity_id, property_name = find_property_by_address(address_part)
    
    if not property_id:
        print("\n❌ No property found with matching address")
        sys.exit(1)
    
    print("-" * 60)
    print("Creating document record...")
    
    # Create document record
    result = create_document_record(file_path, property_id, entity_id, property_name)
    
    if result:
        print("-" * 60)
        print("✅ SUCCESS! Invoice document stored.")
        print("-" * 60)
        print("Document Details:")
        print(f"  • Record ID: {result.get('id', 'N/A')}")
        print(f"  • Property: {property_name}")
        print(f"  • Property ID: {property_id}")
        if entity_id:
            print(f"  • Entity ID: {entity_id[:8]}...")
        print(f"  • File: {file_path}")
        print(f"  • Status: Invoice metadata saved to database")
        print("=" * 60)
    else:
        print("-" * 60)
        print("❌ Failed to upload document")
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    main()