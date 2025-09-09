#!/usr/bin/env python3
"""
Upload a tax document to the system
"""
import os
import sys
import requests
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

def find_property_for_entity(entity_name):
    """Find a property ID associated with the given entity"""
    try:
        # First, try to find the entity
        entity_result = supabase.table("entities").select("*").ilike("name", f"%{entity_name}%").execute()
        
        if entity_result.data:
            entity_id = entity_result.data[0]["id"]
            entity_name_found = entity_result.data[0]["name"]
            print(f"Found entity: {entity_name_found} (ID: {entity_id})")
            
            # Now find properties associated with this entity
            property_result = supabase.table("properties").select("*").eq("entity_id", entity_id).execute()
            
            if property_result.data:
                # Return the first property found
                property_data = property_result.data[0]
                print(f"Found property: {property_data.get('property_name', 'Unnamed')} (ID: {property_data['id']})")
                return property_data['id'], entity_id
            else:
                print(f"No properties found for entity {entity_name_found}")
                # Try to find any property that might be related
                property_result = supabase.table("properties").select("*").ilike("property_name", f"%{entity_name}%").execute()
                if property_result.data:
                    property_data = property_result.data[0]
                    print(f"Found property by name: {property_data.get('property_name', 'Unnamed')} (ID: {property_data['id']})")
                    return property_data['id'], entity_id
        else:
            print(f"Entity '{entity_name}' not found, searching for property directly...")
            # Try to find property by name
            property_result = supabase.table("properties").select("*").ilike("property_name", f"%{entity_name}%").execute()
            if property_result.data:
                property_data = property_result.data[0]
                print(f"Found property: {property_data.get('property_name', 'Unnamed')} (ID: {property_data['id']})")
                return property_data['id'], None
                
        return None, None
    except Exception as e:
        print(f"Error finding property: {e}")
        return None, None

def upload_document(file_path, property_id, entity_id, jurisdiction):
    """Upload document using the API"""
    # Check if API is running locally
    api_url = "http://localhost:8000/api/documents/upload"
    
    # Prepare the file
    with open(file_path, 'rb') as f:
        files = {'file': (os.path.basename(file_path), f, 'application/pdf')}
        
        # Prepare form data
        data = {
            'property_id': property_id,
            'jurisdiction': jurisdiction,
            'document_type': 'tax_bill',
            'notes': f'Board Order document for {jurisdiction}'
        }
        
        if entity_id:
            data['entity_id'] = entity_id
        
        # Make the request
        try:
            response = requests.post(api_url, files=files, data=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError:
            print("API not running locally. Uploading directly to Supabase...")
            return upload_directly_to_supabase(file_path, property_id, entity_id, jurisdiction)
        except Exception as e:
            print(f"Error uploading via API: {e}")
            return None

def upload_directly_to_supabase(file_path, property_id, entity_id, jurisdiction):
    """Upload document directly to Supabase storage"""
    try:
        from datetime import datetime
        from uuid import uuid4
        
        # Read file
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        # Generate storage path
        file_name = os.path.basename(file_path)
        file_extension = Path(file_name).suffix
        storage_name = f"{property_id}/{datetime.now().year}/{uuid4()}{file_extension}"
        
        # Upload to Supabase storage
        bucket_name = "tax-documents"
        
        # Ensure bucket exists
        try:
            buckets = supabase.storage.list_buckets()
            if not any(b['name'] == bucket_name for b in buckets):
                supabase.storage.create_bucket(bucket_name, options={"public": False})
                print(f"Created storage bucket: {bucket_name}")
        except:
            pass  # Bucket might already exist
        
        # Upload file
        response = supabase.storage.from_(bucket_name).upload(
            path=storage_name,
            file=file_content,
            file_options={"content-type": "application/pdf"}
        )
        
        # Get public URL
        public_url = supabase.storage.from_(bucket_name).get_public_url(storage_name)
        
        # Create database record
        document_data = {
            "property_id": property_id,
            "entity_id": entity_id,
            "jurisdiction": jurisdiction,
            "document_type": "tax_bill",
            "document_name": f"Board Order - {jurisdiction}",
            "file_name": file_name,
            "file_size": len(file_content),
            "mime_type": "application/pdf",
            "storage_path": storage_name,
            "storage_bucket": bucket_name,
            "public_url": public_url,
            "notes": f"Board Order document for {jurisdiction}",
            "status": "pending",
            "uploaded_by": "manual_upload"
        }
        
        # Insert into database
        result = supabase.table("tax_documents").insert(document_data).execute()
        
        if result.data:
            print(f"Successfully uploaded document to Supabase")
            return {"message": "Document uploaded successfully", "document": result.data[0]}
        else:
            print("Failed to create database record")
            return None
            
    except Exception as e:
        print(f"Error uploading directly to Supabase: {e}")
        return None

def main():
    # Document details
    file_path = "/Users/kwoody/Downloads/Board Order 0460540000003.pdf"
    entity_name = "Baytown Grove"
    jurisdiction = "Harris County"
    
    print(f"Uploading document: {os.path.basename(file_path)}")
    print(f"Entity: {entity_name}")
    print(f"Jurisdiction: {jurisdiction}")
    print("-" * 50)
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        sys.exit(1)
    
    # Find property ID
    property_id, entity_id = find_property_for_entity(entity_name)
    
    if not property_id:
        print("\nWarning: Could not find a property for this entity.")
        print("Creating a placeholder property ID...")
        # Use a placeholder or create a new property
        property_id = f"MANUAL_{entity_name.replace(' ', '_').upper()}"
        print(f"Using property ID: {property_id}")
    
    print("-" * 50)
    
    # Upload document
    result = upload_document(file_path, property_id, entity_id, jurisdiction)
    
    if result:
        print("\nSuccess! Document uploaded.")
        if 'document' in result:
            doc = result['document']
            print(f"Document ID: {doc.get('id', 'N/A')}")
            print(f"Storage path: {doc.get('storage_path', 'N/A')}")
    else:
        print("\nFailed to upload document.")
        sys.exit(1)

if __name__ == "__main__":
    main()