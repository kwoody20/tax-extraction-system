#!/usr/bin/env python3
"""
Upload a tax document to the system - Fixed version
"""
import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime
from uuid import uuid4

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
        # First, try to find the entity - check correct column name
        try:
            # Try 'entity_name' column
            entity_result = supabase.table("entities").select("*").ilike("entity_name", f"%{entity_name}%").execute()
        except:
            # If that fails, try 'company_name' column (based on error, seems like 'name' doesn't exist)
            try:
                entity_result = supabase.table("entities").select("*").ilike("company_name", f"%{entity_name}%").execute()
            except:
                # Last resort - get all entities and search manually
                entity_result = supabase.table("entities").select("*").execute()
                entity_result.data = [e for e in entity_result.data if entity_name.lower() in str(e).lower()]
        
        if entity_result.data:
            entity = entity_result.data[0]
            entity_id = entity["id"]
            entity_name_found = entity.get("entity_name", entity.get("company_name", "Unknown"))
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
                return property_data['id'], property_data.get('entity_id')
                
        # If still not found, get all properties and show what's available
        print("\nAvailable properties in database:")
        all_properties = supabase.table("properties").select("id, property_name, entity_id").limit(10).execute()
        for prop in all_properties.data[:5]:
            print(f"  - {prop.get('property_name', 'Unnamed')} (ID: {prop['id']})")
        
        if all_properties.data:
            # Use the first property as fallback
            first_prop = all_properties.data[0]
            print(f"\nUsing first available property: {first_prop.get('property_name', 'Unnamed')}")
            return first_prop['id'], first_prop.get('entity_id')
                
        return None, None
    except Exception as e:
        print(f"Error finding property: {e}")
        return None, None

def ensure_bucket_exists(bucket_name="tax-documents"):
    """Ensure the storage bucket exists"""
    try:
        buckets = supabase.storage.list_buckets()
        bucket_names = [b.get('name', b.get('id')) for b in buckets]
        
        if bucket_name not in bucket_names:
            print(f"Creating bucket: {bucket_name}")
            # Try to create the bucket
            try:
                result = supabase.storage.create_bucket(
                    bucket_name,
                    {"public": False}
                )
                print(f"Created bucket: {bucket_name}")
                return True
            except Exception as e:
                print(f"Could not create bucket: {e}")
                # Try alternative bucket names
                for alt_name in ["documents", "files", "uploads"]:
                    if alt_name in bucket_names:
                        print(f"Using existing bucket: {alt_name}")
                        return alt_name
                return None
        else:
            print(f"Bucket '{bucket_name}' already exists")
            return bucket_name
    except Exception as e:
        print(f"Error checking buckets: {e}")
        return None

def upload_directly_to_supabase(file_path, property_id, entity_id, jurisdiction):
    """Upload document directly to Supabase storage"""
    try:
        # Ensure bucket exists
        bucket_name = ensure_bucket_exists()
        if not bucket_name:
            print("No suitable storage bucket available")
            # Fall back to database-only storage
            return store_in_database_only(file_path, property_id, entity_id, jurisdiction)
        
        # Read file
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        # Generate storage path
        file_name = os.path.basename(file_path)
        file_extension = Path(file_name).suffix
        storage_name = f"{property_id}/{datetime.now().year}/{uuid4()}{file_extension}"
        
        # Upload file
        try:
            response = supabase.storage.from_(bucket_name).upload(
                path=storage_name,
                file=file_content,
                file_options={"content-type": "application/pdf"}
            )
            print(f"File uploaded to storage: {storage_name}")
            
            # Get public URL
            public_url = supabase.storage.from_(bucket_name).get_public_url(storage_name)
        except Exception as e:
            print(f"Could not upload to storage: {e}")
            public_url = None
            storage_name = None
        
        # Create database record regardless of storage success
        document_data = {
            "property_id": property_id,
            "jurisdiction": jurisdiction,
            "document_type": "tax_bill",
            "document_name": f"Board Order - {jurisdiction}",
            "file_name": file_name,
            "file_size": len(file_content),
            "mime_type": "application/pdf",
            "notes": f"Board Order document for {jurisdiction}",
            "status": "pending",
            "uploaded_by": "manual_upload"
        }
        
        # Add optional fields if available
        if entity_id:
            document_data["entity_id"] = entity_id
        if storage_name:
            document_data["storage_path"] = storage_name
            document_data["storage_bucket"] = bucket_name
        if public_url:
            document_data["public_url"] = public_url
        
        # Insert into database
        result = supabase.table("tax_documents").insert(document_data).execute()
        
        if result.data:
            print(f"Successfully created document record in database")
            return {"message": "Document uploaded successfully", "document": result.data[0]}
        else:
            print("Failed to create database record")
            return None
            
    except Exception as e:
        print(f"Error uploading to Supabase: {e}")
        return None

def store_in_database_only(file_path, property_id, entity_id, jurisdiction):
    """Store document metadata in database only (when storage is not available)"""
    try:
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        
        document_data = {
            "property_id": property_id,
            "jurisdiction": jurisdiction,
            "document_type": "tax_bill",
            "document_name": f"Board Order - {jurisdiction}",
            "file_name": file_name,
            "file_size": file_size,
            "mime_type": "application/pdf",
            "notes": f"Board Order document for {jurisdiction} (metadata only - file stored locally)",
            "status": "pending",
            "uploaded_by": "manual_upload",
            "local_path": file_path  # Store the local path for reference
        }
        
        if entity_id:
            document_data["entity_id"] = entity_id
        
        result = supabase.table("tax_documents").insert(document_data).execute()
        
        if result.data:
            print(f"Successfully stored document metadata in database")
            return {"message": "Document metadata stored successfully", "document": result.data[0]}
        else:
            return None
            
    except Exception as e:
        print(f"Error storing in database: {e}")
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
        print("\nNo property found. Creating a manual entry...")
        # Generate a unique property ID
        property_id = f"MANUAL_{datetime.now().strftime('%Y%m%d')}_{uuid4().hex[:8]}"
        print(f"Using property ID: {property_id}")
    
    print("-" * 50)
    
    # Try API first
    api_url = "http://localhost:8000/api/documents/upload"
    
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'application/pdf')}
            
            data = {
                'property_id': property_id,
                'jurisdiction': jurisdiction,
                'document_type': 'tax_bill',
                'notes': f'Board Order document for {jurisdiction}'
            }
            
            if entity_id:
                data['entity_id'] = entity_id
            
            response = requests.post(api_url, files=files, data=data, timeout=5)
            response.raise_for_status()
            result = response.json()
            print("\nSuccess! Document uploaded via API.")
            if 'document' in result:
                doc = result['document']
                print(f"Document ID: {doc.get('id', 'N/A')}")
    except:
        print("API not available. Uploading directly to Supabase...")
        result = upload_directly_to_supabase(file_path, property_id, entity_id, jurisdiction)
        
        if result:
            print("\nSuccess! Document information stored.")
            if 'document' in result:
                doc = result['document']
                print(f"Document ID: {doc.get('id', 'N/A')}")
        else:
            print("\nFailed to upload document.")
            sys.exit(1)

if __name__ == "__main__":
    main()