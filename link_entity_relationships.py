#!/usr/bin/env python3
"""
Script to link sub-entities to their parent entities in Supabase database.
Based on naming patterns from cleaned-entities.csv
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://klscgjbachumeojhxyno.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtsc2NnamJhY2h1bWVvamh4eW5vIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU3OTU1OTksImV4cCI6MjA3MTM3MTU5OX0.nJF44C6SPe-dNfPit7zTsij2foo67WNY3PFl7lfxquY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_entities():
    """Fetch all entities from database."""
    response = supabase.table("entities").select("*").execute()
    return response.data

def link_entities():
    """Link sub-entities to their parent entities based on naming patterns."""
    
    # Fetch all entities
    entities = fetch_entities()
    
    # Separate by type
    parent_entities = {e['entity_name']: e['entity_id'] for e in entities if e['entity_type'] == 'parent entity'}
    sub_entities = [e for e in entities if e['entity_type'] == 'sub-entity']
    
    print(f"Found {len(parent_entities)} parent entities and {len(sub_entities)} sub-entities")
    
    # Define the relationships based on naming patterns
    relationships = {
        "BCS Mont Belvieu LLC - Barbers Hill ISD: (Total 5.33 Acres)": "BCS Mont Belvieu LLC (TX) - Total 5.33 Acres (Remaining  4.3260 Acres)",
        "BCS Baytown Grove LLC - Goose Creek ISD: (Total 35.430 Acres) - Pending 11 Acre Bill?": "BCS Baytown Grove LLC (TX) - Total 47 Acres (entity, untaxed)",
        "BCS Montgomery LLC - 32 Acres": "BCS Montgomery LLC (TX) - 33 Acres",
        "BCS Montgomery LLC - 6.59 Acres:": "BCS Montgomery LLC (TX) - 33 Acres",
        "3202 Riley Fuzzell Rd - (18.1 acres):": "BCS Magnolia Place LLC (TX) - Total 51.13 Acres"
    }
    
    # Update each sub-entity with its parent_entity_id
    updates_made = 0
    for sub_entity in sub_entities:
        sub_name = sub_entity['entity_name']
        
        if sub_name in relationships:
            parent_name = relationships[sub_name]
            
            if parent_name in parent_entities:
                parent_id = parent_entities[parent_name]
                
                print(f"\nLinking: {sub_name}")
                print(f"  -> Parent: {parent_name}")
                print(f"  -> Parent ID: {parent_id}")
                
                # Update the sub-entity with parent_entity_id
                try:
                    response = supabase.table("entities").update({
                        "parent_entity_id": parent_id
                    }).eq("entity_id", sub_entity['entity_id']).execute()
                    
                    if response.data:
                        print(f"  ✓ Successfully linked")
                        updates_made += 1
                    else:
                        print(f"  ✗ Failed to update")
                        
                except Exception as e:
                    print(f"  ✗ Error: {e}")
            else:
                print(f"\n⚠️ Parent entity not found for: {sub_name}")
                print(f"  Expected parent: {parent_name}")
        else:
            print(f"\n⚠️ No relationship defined for: {sub_name}")
    
    print(f"\n{'='*50}")
    print(f"Summary: Updated {updates_made} out of {len(sub_entities)} sub-entities")
    
    # Verify the updates
    print(f"\n{'='*50}")
    print("Verifying updates...")
    updated_entities = fetch_entities()
    updated_subs = [e for e in updated_entities if e['entity_type'] == 'sub-entity']
    
    for sub in updated_subs:
        parent_id = sub.get('parent_entity_id')
        if parent_id:
            parent = next((e for e in updated_entities if e['entity_id'] == parent_id), None)
            if parent:
                print(f"✓ {sub['entity_name']} -> {parent['entity_name']}")
            else:
                print(f"⚠️ {sub['entity_name']} has parent_id {parent_id} but parent not found")
        else:
            print(f"✗ {sub['entity_name']} - No parent linked")

if __name__ == "__main__":
    print("Linking sub-entities to parent entities in Supabase...")
    print("="*50)
    link_entities()