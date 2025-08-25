#!/usr/bin/env python3
"""
Assign parent entity IDs to properties based on company name patterns.
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
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment or .env file")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def assign_parent_entities():
    """Assign parent entity IDs to properties based on company name patterns"""
    
    print("=" * 80)
    print("ASSIGNING PARENT ENTITIES TO PROPERTIES")
    print("=" * 80)
    
    # First, get all entities to map names to IDs
    entities_response = supabase.table('entities').select('*').execute()
    entities = entities_response.data
    
    # Create entity name to ID mapping
    entity_map = {}
    for entity in entities:
        name = entity['entity_name']
        entity_map[name] = entity['id']
        print(f"Found entity: {name} -> {entity['id']}")
    
    print("\n" + "-" * 80)
    print("ENTITY MAPPING:")
    print("-" * 80)
    
    # Define property name patterns to parent entity mappings
    # Note: Entity names in database have (TX) suffix
    property_to_entity_mappings = {
        # BCS Phoenix Bell LLC
        "17017 N CAVE CREEK ROAD PHOENIX": "BCS Phoenix Bell LLC (TX)",
        "2404 E BELL ROAD PHOENIX": "BCS Phoenix Bell LLC (TX)",
        
        # BCS Aldine LLC - Note: maps to BCS Humble LLC (TX) - Aldine ISD
        "BCS Aldine LLC": "BCS Humble LLC (TX) - Aldine ISD",
        
        # BCS Baytown Grove LLC - has special entity with description
        "BCS Baytown Grove LLC": "BCS Baytown Grove LLC (TX) - Total 47 Acres (entity, untaxed)",
        
        # BCS Clutch Shepherd LLC
        "BCS Clutch Shepherd LLC": "BCS Clutch Shepherd LLC (TX) (entity, untaxed)",
        
        # BCS Conroe Davis LLC
        "BCS Conroe Davis LLC": "BCS Conroe Davis LLC (TX)",
        
        # BCS Humble LLC
        "BCS Humble LLC": "BCS Humble LLC (TX) - Aldine ISD",
        
        # BCS Katy LLC
        "BCS Katy LLC": "BCS Katy LLC (TX)",
        
        # BCS Missouri City LLC
        "BCS Missouri City LLC": "BCS Missouri City LLC (TX)",
        
        # BCS Montgomery LLC - multiple entities, use the 33 Acres one
        "BCS Montgomery LLC": "BCS Montgomery LLC (TX) - 33 Acres",
        
        # BCS Splendora LLC
        "BCS Splendora LLC": "BCS Splendora LLC (TX)",
        
        # Houston QSR Propco LLC
        "Houston QSR Propco LLC": "Houston QSR Propco LLC (TX)",
        
        # PE 249 LLC
        "PE 249 LLC": "PE 249 LLC (TX)",
    }
    
    # Get all properties without parent entities
    properties_response = supabase.table('properties').select('*').is_('parent_entity_id', 'null').execute()
    properties = properties_response.data
    
    print(f"\nFound {len(properties)} properties without parent entities")
    print("-" * 80)
    
    updates_made = []
    updates_failed = []
    
    for prop in properties:
        property_name = prop['property_name']
        property_id = prop['id']
        
        # Find matching parent entity
        parent_entity_name = None
        for pattern, entity_name in property_to_entity_mappings.items():
            if pattern in property_name:
                parent_entity_name = entity_name
                break
        
        if parent_entity_name and parent_entity_name in entity_map:
            parent_entity_id = entity_map[parent_entity_name]
            
            # Update the property with parent entity ID
            try:
                update_response = supabase.table('properties').update({
                    'parent_entity_id': parent_entity_id
                }).eq('id', property_id).execute()
                
                print(f"✅ Updated: {property_name[:50]}...")
                print(f"   -> Parent: {parent_entity_name}")
                
                updates_made.append({
                    'property_id': property_id,
                    'property_name': property_name,
                    'parent_entity_name': parent_entity_name,
                    'parent_entity_id': parent_entity_id
                })
                
            except Exception as e:
                print(f"❌ Failed to update: {property_name}")
                print(f"   Error: {str(e)}")
                updates_failed.append({
                    'property_id': property_id,
                    'property_name': property_name,
                    'error': str(e)
                })
        else:
            print(f"⚠️  No matching parent entity for: {property_name}")
            updates_failed.append({
                'property_id': property_id,
                'property_name': property_name,
                'error': 'No matching parent entity found'
            })
    
    # Summary
    print("\n" + "=" * 80)
    print("ASSIGNMENT SUMMARY")
    print("=" * 80)
    print(f"✅ Successfully updated: {len(updates_made)} properties")
    print(f"❌ Failed or unmatched: {len(updates_failed)} properties")
    
    # Save report
    report_filename = f"parent_entity_assignment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_data = {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'total_processed': len(properties),
            'successful_updates': len(updates_made),
            'failed_updates': len(updates_failed)
        },
        'successful_assignments': updates_made,
        'failed_assignments': updates_failed
    }
    
    with open(report_filename, 'w') as f:
        json.dump(report_data, f, indent=2)
    
    print(f"\n📄 Assignment report saved to: {report_filename}")
    
    # Re-check to see if all properties now have parent entities
    print("\n" + "=" * 80)
    print("FINAL CHECK")
    print("=" * 80)
    
    final_check = supabase.table('properties').select('id').is_('parent_entity_id', 'null').execute()
    remaining_without_parent = len(final_check.data)
    
    if remaining_without_parent == 0:
        print("✅ SUCCESS: All properties now have parent entity IDs!")
    else:
        print(f"⚠️  Still {remaining_without_parent} properties without parent entities")
        print("These may need manual review or new parent entities created.")
    
    return remaining_without_parent == 0

if __name__ == "__main__":
    success = assign_parent_entities()
    exit(0 if success else 1)