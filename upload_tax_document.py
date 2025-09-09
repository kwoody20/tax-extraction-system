#!/usr/bin/env python3
"""
Upload a tax document to the system - Working version based on actual schema
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

def find_related_property(entity_name):
    """Find a property related to the entity"""
    try:
        # Find the entity
        entity_result = supabase.table("entities").select("*").execute()
        baytown_entities = [e for e in entity_result.data if 'baytown' in e.get('entity_name', '').lower()]
        
        if baytown_entities:
            entity = baytown_entities[0]
            entity_id = entity.get('id')
            entity_name_found = entity.get('entity_name')
            print(f"Found entity: {entity_name_found}")
            print(f"Entity ID: {entity_id}")
            
            # Find properties that might be related (by parent_entity_id or name)
            prop_result = supabase.table("properties").select("*").execute()
            
            # First try to match by parent_entity_id
            for prop in prop_result.data:
                if prop.get('parent_entity_id') == entity_id:
                    print(f"Found related property: {prop.get('property_name')} (ID: {prop.get('id')})")
                    return prop.get('id'), entity_id, prop.get('property_name')
            
            # Then try to match by name
            for prop in prop_result.data:
                if 'baytown' in prop.get('property_name', '').lower():
                    print(f"Found property by name: {prop.get('property_name')} (ID: {prop.get('id')})")
                    return prop.get('id'), entity_id, prop.get('property_name')
            
            # No property found, return entity info only
            print(f"No specific property found for entity, will create document for entity")
            return None, entity_id, entity_name_found
            
        return None, None, None
        
    except Exception as e:
        print(f"Error finding property: {e}")
        return None, None, None

def create_document_record(file_path, property_id, entity_id, jurisdiction):
    """Create a document record in the tax_documents table"""
    try:
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        
        # Build document data matching the schema
        document_data = {
            "property_id": property_id if property_id else f"ENTITY_{entity_id[:8]}",
            "jurisdiction": jurisdiction,
            "document_type": "tax_bill",
            "document_name": f"Board Order - {jurisdiction}",
            "file_name": file_name,
            "file_size": file_size,
            "mime_type": "application/pdf",
            "notes": f"Board Order document 0460540000003 for {jurisdiction}",
            "status": "pending",
            "uploaded_by": "manual_upload"
        }
        
        # Add entity_id if available (check if column exists)
        if entity_id:
            # Try with entity_id first
            try:
                document_data["entity_id"] = entity_id
                result = supabase.table("tax_documents").insert(document_data).execute()
                if result.data:
                    return result.data[0]
            except:
                # If entity_id column doesn't exist, try without it
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
        # If tax_documents table doesn't work, try alternative approach
        return create_alternative_record(file_path, property_id, entity_id, jurisdiction)

def create_alternative_record(file_path, property_id, entity_id, jurisdiction):
    """Alternative: Store document info in properties or entities table as metadata"""
    try:
        file_name = os.path.basename(file_path)
        document_info = {
            "file_name": file_name,
            "upload_date": datetime.now().isoformat(),
            "jurisdiction": jurisdiction,
            "document_type": "Board Order",
            "document_number": "0460540000003"
        }
        
        if property_id:
            # Update property with document info
            result = supabase.table("properties").update({
                "tax_bill_link": f"Local file: {file_name}",
                "updated_at": datetime.now().isoformat()
            }).eq("id", property_id).execute()
            
            if result.data:
                print(f"Updated property record with document info")
                return {"id": property_id, "type": "property_update", **document_info}
        
        if entity_id:
            # Update entity with document info
            result = supabase.table("entities").update({
                "tax_bill_link": f"Local file: {file_name}",
                "updated_at": datetime.now().isoformat()
            }).eq("id", entity_id).execute()
            
            if result.data:
                print(f"Updated entity record with document info")
                return {"id": entity_id, "type": "entity_update", **document_info}
        
        return None
        
    except Exception as e:
        print(f"Error in alternative record creation: {e}")
        return None

def main():
    # Document details
    file_path = "/Users/kwoody/Downloads/Board Order 0460540000003.pdf"
    entity_name = "Baytown Grove"
    jurisdiction = "Harris County"
    
    print("=" * 60)
    print("TAX DOCUMENT UPLOAD")
    print("=" * 60)
    print(f"Document: {os.path.basename(file_path)}")
    print(f"Entity: {entity_name}")
    print(f"Jurisdiction: {jurisdiction}")
    print("-" * 60)
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"❌ Error: File not found: {file_path}")
        sys.exit(1)
    else:
        print(f"✓ File found (size: {os.path.getsize(file_path):,} bytes)")
    
    print("-" * 60)
    print("Searching for entity and property...")
    
    # Find related property
    property_id, entity_id, found_name = find_related_property(entity_name)
    
    print("-" * 60)
    print("Creating document record...")
    
    # Create document record
    result = create_document_record(file_path, property_id, entity_id, jurisdiction)
    
    if result:
        print("-" * 60)
        print("✅ SUCCESS! Document information stored.")
        print("-" * 60)
        print("Document Details:")
        print(f"  • Record ID: {result.get('id', 'N/A')}")
        if property_id:
            print(f"  • Property ID: {property_id}")
        if entity_id:
            print(f"  • Entity ID: {entity_id[:8]}...")
        print(f"  • File: {file_path}")
        print(f"  • Status: Document metadata saved to database")
        print("=" * 60)
    else:
        print("-" * 60)
        print("❌ Failed to upload document")
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    main()