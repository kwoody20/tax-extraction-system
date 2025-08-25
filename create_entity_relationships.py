#!/usr/bin/env python3
"""
Create and populate entity_relationships table as an alternative to modifying the entities table.
This stores parent-child relationships between entities.
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

def check_and_create_relationships():
    """Check if entity_relationships table exists and populate it."""
    
    print("Working with entity_relationships table...")
    print("="*60)
    
    # First, let's check if the table exists by trying to query it
    try:
        response = supabase.table("entity_relationships").select("*").limit(1).execute()
        print("✓ entity_relationships table exists")
        
        # Clear existing relationships to avoid duplicates
        print("Clearing existing relationships...")
        try:
            # Delete all relationships
            supabase.table("entity_relationships").delete().gte("id", 0).execute()
        except Exception as del_error:
            print(f"Note: Could not clear existing relationships: {del_error}")
        
    except Exception as e:
        if "entity_relationships" in str(e):
            print("✗ entity_relationships table doesn't exist")
            print("\nPlease create the table in Supabase with these columns:")
            print("  - id (int8, primary key)")
            print("  - parent_entity_id (uuid, foreign key to entities.entity_id)")
            print("  - child_entity_id (uuid, foreign key to entities.entity_id)")
            print("  - relationship_type (text)")
            print("  - created_at (timestamp)")
            return False
        else:
            print(f"Error checking table: {e}")
            return False
    
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
    
    # Insert relationships
    successful_inserts = 0
    print("\nCreating entity relationships...")
    print("-"*60)
    
    for sub_entity in sub_entities:
        sub_name = sub_entity['entity_name']
        
        if sub_name in relationships:
            parent_name = relationships[sub_name]
            
            if parent_name in parent_entities:
                parent_id = parent_entities[parent_name]
                child_id = sub_entity['entity_id']
                
                print(f"\nLinking: {sub_name}")
                print(f"  -> Parent: {parent_name}")
                
                # Insert relationship
                try:
                    response = supabase.table("entity_relationships").insert({
                        "parent_entity_id": parent_id,
                        "child_entity_id": child_id,
                        "relationship_type": "parent-child"
                    }).execute()
                    
                    if response.data:
                        print(f"  ✓ Relationship created")
                        successful_inserts += 1
                    else:
                        print(f"  ✗ Failed to create relationship")
                        
                except Exception as e:
                    print(f"  ✗ Error: {e}")
            else:
                print(f"\n⚠️ Parent entity not found for: {sub_name}")
                print(f"  Expected parent: {parent_name}")
        else:
            print(f"\n⚠️ No relationship defined for: {sub_name}")
    
    print("\n" + "="*60)
    print(f"Summary: Created {successful_inserts} out of {len(sub_entities)} relationships")
    
    # Verify the relationships
    print("\n" + "="*60)
    print("Verifying relationships...")
    
    try:
        response = supabase.table("entity_relationships").select("*").execute()
        relationships = response.data
        
        if relationships:
            print(f"Found {len(relationships)} relationships in database:")
            
            # Get entity names for display
            entity_map = {e['entity_id']: e['entity_name'] for e in entities}
            
            for rel in relationships:
                parent_name = entity_map.get(rel['parent_entity_id'], 'Unknown')
                child_name = entity_map.get(rel['child_entity_id'], 'Unknown')
                print(f"  • {child_name} -> {parent_name}")
        else:
            print("No relationships found in database")
            
    except Exception as e:
        print(f"Error verifying relationships: {e}")
    
    return True

if __name__ == "__main__":
    print("Managing entity relationships in Supabase...")
    print("="*60)
    
    success = check_and_create_relationships()
    
    if success:
        print("\n✓ Entity relationships successfully configured!")
        print("\nNote: The dashboard will need to be updated to use the")
        print("entity_relationships table instead of parent_entity_id column.")
    else:
        print("\n✗ Could not configure entity relationships.")
        print("Please create the entity_relationships table first.")