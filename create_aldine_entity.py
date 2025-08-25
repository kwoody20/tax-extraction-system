#!/usr/bin/env python3
"""
Create BCS Aldine LLC (TX) entity and assign remaining properties.
"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client
import json
from datetime import datetime

load_dotenv()

# Initialize Supabase client - use service role key for write permissions
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def create_and_assign_aldine():
    """Create BCS Aldine LLC (TX) entity and assign properties"""
    
    print("=" * 80)
    print("CREATING BCS ALDINE LLC (TX) AND ASSIGNING PROPERTIES")
    print("=" * 80)
    
    # Entity ID from cleaned-entities.csv
    aldine_entity_id = "86a9b572-454e-4652-aa63-029642eddda8"
    aldine_entity_name = "BCS Aldine LLC (TX)"
    
    # First, check if entity exists
    try:
        check_response = supabase.table('entities').select('*').eq('entity_id', aldine_entity_id).execute()
        
        if check_response.data and len(check_response.data) > 0:
            print(f"✅ Entity already exists: {aldine_entity_name}")
            print(f"   ID: {aldine_entity_id}")
        else:
            print(f"Entity not found, creating: {aldine_entity_name}")
            
            # Create the entity with required fields matching the database schema
            entity_data = {
                'entity_id': aldine_entity_id,  # This is the key field from CSV
                'entity_name': aldine_entity_name,
                'entity_type': 'parent entity',
                'jurisdiction': 'Harris',
                'state': 'TX'
            }
            
            create_response = supabase.table('entities').insert(entity_data).execute()
            print(f"✅ Created entity: {aldine_entity_name}")
            print(f"   ID: {aldine_entity_id}")
    
    except Exception as e:
        print(f"❌ Error checking/creating entity: {str(e)}")
        return False
    
    # Now assign the two remaining properties
    print("\n" + "-" * 80)
    print("ASSIGNING PROPERTIES TO BCS ALDINE LLC (TX)")
    print("-" * 80)
    
    # Get properties that need BCS Aldine LLC
    properties_to_update = [
        "BCS Aldine LLC - Aldine ISD",
        "BCS Aldine LLC - Memorial Hills UD"
    ]
    
    success_count = 0
    
    for property_name_pattern in properties_to_update:
        try:
            # Find the property
            prop_response = supabase.table('properties').select('*').like('property_name', f'%{property_name_pattern}%').execute()
            
            if prop_response.data and len(prop_response.data) > 0:
                prop = prop_response.data[0]
                property_id = prop['id']
                property_name = prop['property_name']
                
                # Update with parent entity ID
                update_response = supabase.table('properties').update({
                    'parent_entity_id': aldine_entity_id
                }).eq('id', property_id).execute()
                
                print(f"✅ Updated: {property_name}")
                print(f"   -> Parent: {aldine_entity_name} ({aldine_entity_id})")
                success_count += 1
            else:
                print(f"⚠️  Property not found: {property_name_pattern}")
                
        except Exception as e:
            print(f"❌ Failed to update property: {property_name_pattern}")
            print(f"   Error: {str(e)}")
    
    # Final check
    print("\n" + "=" * 80)
    print("FINAL VERIFICATION")
    print("=" * 80)
    
    final_check = supabase.table('properties').select('id').is_('parent_entity_id', 'null').execute()
    remaining_without_parent = len(final_check.data)
    
    if remaining_without_parent == 0:
        print("✅ SUCCESS: All 102 properties now have parent entity IDs!")
        return True
    else:
        print(f"⚠️  Still {remaining_without_parent} properties without parent entities")
        return False

if __name__ == "__main__":
    success = create_and_assign_aldine()
    exit(0 if success else 1)