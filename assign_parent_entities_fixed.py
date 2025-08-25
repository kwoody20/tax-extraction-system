#!/usr/bin/env python3
"""
Assign parent entity IDs to properties based on the cleaned-entities.csv mappings.
"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client
import json
import csv
from datetime import datetime

load_dotenv()

# Initialize Supabase client - use service role key for write permissions
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def load_entity_mappings():
    """Load entity mappings from cleaned-entities.csv"""
    entity_map = {}
    
    with open('cleaned-entities.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            entity_id = row.get('entity ID', '').strip()
            entity_name = row.get('entity name', '').strip()
            if entity_id and entity_name:
                entity_map[entity_name] = entity_id
                print(f"Loaded: {entity_name} -> {entity_id}")
    
    return entity_map

def assign_parent_entities():
    """Assign parent entity IDs to properties based on company name patterns"""
    
    print("=" * 80)
    print("ASSIGNING PARENT ENTITIES TO PROPERTIES")
    print("=" * 80)
    
    # Load entity mappings from CSV
    entity_map = load_entity_mappings()
    
    print("\n" + "-" * 80)
    print(f"Loaded {len(entity_map)} entities from cleaned-entities.csv")
    print("-" * 80)
    
    # Define property name patterns to parent entity mappings
    property_to_entity_mappings = {
        # BCS Phoenix Bell LLC
        "17017 N CAVE CREEK ROAD PHOENIX": "BCS Phoenix Bell LLC (TX)",
        "2404 E BELL ROAD PHOENIX": "BCS Phoenix Bell LLC (TX)",
        
        # BCS Aldine LLC
        "BCS Aldine LLC": "BCS Aldine LLC (TX)",
        
        # BCS Baytown Grove LLC
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
        
        # BCS Montgomery LLC
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
                print(f"   -> Parent: {parent_entity_name} ({parent_entity_id})")
                
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
            if parent_entity_name:
                print(f"⚠️  Entity not found in CSV: {parent_entity_name}")
            else:
                print(f"⚠️  No matching pattern for: {property_name}")
            updates_failed.append({
                'property_id': property_id,
                'property_name': property_name,
                'error': f'No matching entity found (looked for: {parent_entity_name})'
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