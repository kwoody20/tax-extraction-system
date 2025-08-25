#!/usr/bin/env python3
"""
Script to add parent_entity_id column and link sub-entities to parent entities.
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

# Initialize Supabase client with service role key for schema changes
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://klscgjbachumeojhxyno.supabase.co")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtsc2NnamJhY2h1bWVvamh4eW5vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NTc5NTU5OSwiZXhwIjoyMDcxMzcxNTk5fQ.QlATw42GJhAvSr1DEwgfOQpHN_ZRN19Nsxc9v6o74Q8")

def add_parent_entity_column():
    """Add parent_entity_id column to entities table using REST API."""
    
    print("Adding parent_entity_id column to entities table...")
    
    # SQL query to add the column
    sql_query = """
    ALTER TABLE entities 
    ADD COLUMN IF NOT EXISTS parent_entity_id UUID REFERENCES entities(entity_id);
    """
    
    # Execute via REST API
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json"
    }
    
    # Use the SQL endpoint
    url = f"{SUPABASE_URL}/rest/v1/rpc/exec_sql"
    
    # First, let's try a simpler approach using the direct SQL API
    # Note: This requires the SQL endpoint to be enabled
    
    # Alternative approach: Use psycopg2 if available
    try:
        import psycopg2
        from urllib.parse import urlparse
        
        # Parse database URL from Supabase
        # The pattern is usually: postgresql://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
        db_url = f"postgresql://postgres.klscgjbachumeojhxyno:Kw00dy-24@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
        
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        # Add the column
        cur.execute(sql_query)
        conn.commit()
        
        print("✓ Column added successfully")
        
        cur.close()
        conn.close()
        return True
        
    except ImportError:
        print("psycopg2 not installed, trying alternative method...")
    except Exception as e:
        print(f"Direct database connection failed: {e}")
        print("Trying alternative method...")
    
    # Alternative: Update via Supabase client (may not work for schema changes)
    print("Note: Schema changes typically require direct database access.")
    print("You may need to add the column manually via Supabase dashboard:")
    print("1. Go to Table Editor")
    print("2. Select 'entities' table")
    print("3. Add column: parent_entity_id (UUID, nullable, foreign key to entities.entity_id)")
    
    return False

def link_entities():
    """Link sub-entities to their parent entities."""
    
    # Use regular anon key for data operations
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtsc2NnamJhY2h1bWVvamh4eW5vIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU3OTU1OTksImV4cCI6MjA3MTM3MTU5OX0.nJF44C6SPe-dNfPit7zTsij2foo67WNY3PFl7lfxquY")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Fetch all entities
    response = supabase.table("entities").select("*").execute()
    entities = response.data
    
    # Separate by type
    parent_entities = {e['entity_name']: e['entity_id'] for e in entities if e['entity_type'] == 'parent entity'}
    sub_entities = [e for e in entities if e['entity_type'] == 'sub-entity']
    
    print(f"\nFound {len(parent_entities)} parent entities and {len(sub_entities)} sub-entities")
    
    # Define the relationships
    relationships = {
        "BCS Mont Belvieu LLC - Barbers Hill ISD: (Total 5.33 Acres)": "BCS Mont Belvieu LLC (TX) - Total 5.33 Acres (Remaining  4.3260 Acres)",
        "BCS Baytown Grove LLC - Goose Creek ISD: (Total 35.430 Acres) - Pending 11 Acre Bill?": "BCS Baytown Grove LLC (TX) - Total 47 Acres (entity, untaxed)",
        "BCS Montgomery LLC - 32 Acres": "BCS Montgomery LLC (TX) - 33 Acres",
        "BCS Montgomery LLC - 6.59 Acres:": "BCS Montgomery LLC (TX) - 33 Acres",
        "3202 Riley Fuzzell Rd - (18.1 acres):": "BCS Magnolia Place LLC (TX) - Total 51.13 Acres"
    }
    
    # Try to update using alternative approach
    print("\nSince parent_entity_id column might not exist yet, here are the relationships to set up:")
    print("="*60)
    
    for sub_entity in sub_entities:
        sub_name = sub_entity['entity_name']
        
        if sub_name in relationships:
            parent_name = relationships[sub_name]
            
            if parent_name in parent_entities:
                parent_id = parent_entities[parent_name]
                
                print(f"\nSub-Entity: {sub_name}")
                print(f"  Entity ID: {sub_entity['entity_id']}")
                print(f"  Should link to Parent: {parent_name}")
                print(f"  Parent ID: {parent_id}")
                
                # Try to update
                try:
                    response = supabase.table("entities").update({
                        "parent_entity_id": parent_id
                    }).eq("entity_id", sub_entity['entity_id']).execute()
                    
                    if response.data:
                        print(f"  ✓ Successfully linked")
                    else:
                        print(f"  ✗ Update failed - column might not exist")
                        
                except Exception as e:
                    if "parent_entity_id" in str(e):
                        print(f"  ✗ Column 'parent_entity_id' doesn't exist yet")
                    else:
                        print(f"  ✗ Error: {e}")

if __name__ == "__main__":
    print("Setting up entity relationships in Supabase...")
    print("="*60)
    
    # Try to add the column first
    column_added = add_parent_entity_column()
    
    if column_added:
        print("\n" + "="*60)
        print("Now linking entities...")
        link_entities()
    else:
        print("\n" + "="*60)
        print("Manual step required:")
        print("Please add the parent_entity_id column via Supabase dashboard first.")
        print("\nThen run: python3 link_entity_relationships.py")
        
        # Still show the relationships that need to be set
        link_entities()