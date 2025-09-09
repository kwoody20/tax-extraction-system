#!/usr/bin/env python3
"""
Check Supabase database schema
"""
import os
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

print("Checking database schema...")
print("-" * 50)

# Check entities table
try:
    entities = supabase.table("entities").select("*").limit(1).execute()
    if entities.data:
        print("Entities table columns:")
        for key in entities.data[0].keys():
            print(f"  - {key}")
except Exception as e:
    print(f"Error checking entities: {e}")

print("-" * 50)

# Check properties table
try:
    properties = supabase.table("properties").select("*").limit(1).execute()
    if properties.data:
        print("Properties table columns:")
        for key in properties.data[0].keys():
            print(f"  - {key}")
except Exception as e:
    print(f"Error checking properties: {e}")

print("-" * 50)

# Check tax_documents table
try:
    documents = supabase.table("tax_documents").select("*").limit(1).execute()
    if documents.data:
        print("Tax_documents table columns:")
        for key in documents.data[0].keys():
            print(f"  - {key}")
    else:
        print("Tax_documents table exists but is empty")
except Exception as e:
    print(f"Error checking tax_documents: {e}")

print("-" * 50)

# Check storage buckets
try:
    buckets = supabase.storage.list_buckets()
    print("Available storage buckets:")
    for bucket in buckets:
        print(f"  - {bucket}")
except Exception as e:
    print(f"Error checking buckets: {e}")

print("-" * 50)

# Find Baytown Grove entity
try:
    entity_result = supabase.table("entities").select("*").execute()
    baytown_entities = [e for e in entity_result.data if 'baytown' in str(e).lower()]
    if baytown_entities:
        print("Found Baytown Grove entity:")
        entity = baytown_entities[0]
        print(f"  ID: {entity.get('id')}")
        print(f"  Entity Name: {entity.get('entity_name', 'N/A')}")
        
        # Find related properties
        entity_id = entity.get('id')
        prop_result = supabase.table("properties").select("*").execute()
        
        # Since entity_id column doesn't exist, look for properties that might be related
        print("\nSearching for related properties...")
        for prop in prop_result.data:
            if 'baytown' in str(prop).lower() or entity_id in str(prop).values():
                print(f"  Found property: {prop.get('property_name', 'Unnamed')} (ID: {prop.get('id')})")
                break
except Exception as e:
    print(f"Error finding Baytown Grove: {e}")