#!/usr/bin/env python3
"""
Export all properties from Supabase with minimal fields for mapping new data.
"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client
import csv
from datetime import datetime

load_dotenv()

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_KEY must be set")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def export_properties_for_mapping():
    """Export properties with minimal fields needed for mapping"""
    
    print("=" * 80)
    print("EXPORTING PROPERTIES FOR FIELD MAPPING")
    print("=" * 80)
    
    # Get all properties with their parent entities
    try:
        # Query properties and join with entities to get parent entity name
        properties_response = supabase.table('properties').select(
            'id, property_name, jurisdiction, state, account_number, property_address, parent_entity_id'
        ).execute()
        
        properties = properties_response.data
        
        # Get all entities to map IDs to names
        entities_response = supabase.table('entities').select('entity_id, entity_name').execute()
        entities = entities_response.data
        entity_map = {e['entity_id']: e['entity_name'] for e in entities}
        
        print(f"Found {len(properties)} properties to export")
        
        # Prepare CSV filename with timestamp
        filename = f"properties_mapping_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        # Write to CSV with minimal fields for mapping
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            # Define fieldnames - only essential fields for identification
            # Plus empty columns for new fields to be added
            fieldnames = [
                'property_id',
                'property_name',
                'parent_entity_name',
                'jurisdiction',
                'state',
                'acct_number',
                'property_address',
                # Empty columns for new fields to be added by user
                'new_field_1',
                'new_field_2',
                'new_field_3',
                'new_field_4',
                'new_field_5'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            # Write each property
            for prop in properties:
                parent_entity_name = entity_map.get(prop.get('parent_entity_id'), '')
                
                row = {
                    'property_id': prop['id'],
                    'property_name': prop.get('property_name', ''),
                    'parent_entity_name': parent_entity_name,
                    'jurisdiction': prop.get('jurisdiction', ''),
                    'state': prop.get('state', ''),
                    'acct_number': prop.get('account_number', ''),
                    'property_address': prop.get('property_address', ''),
                    # Empty fields for user to fill
                    'new_field_1': '',
                    'new_field_2': '',
                    'new_field_3': '',
                    'new_field_4': '',
                    'new_field_5': ''
                }
                
                writer.writerow(row)
        
        print(f"\n✅ Successfully exported {len(properties)} properties to: {filename}")
        print("\nCSV Structure:")
        print("-" * 40)
        print("Columns included:")
        for field in fieldnames:
            if field.startswith('new_field'):
                print(f"  - {field} (empty - for your new data)")
            else:
                print(f"  - {field}")
        
        print("\n📝 Instructions:")
        print("-" * 40)
        print("1. Open the CSV file: " + filename)
        print("2. Rename the 'new_field_X' columns to your actual field names")
        print("3. Add your data in those columns")
        print("4. Save the file and provide it back for database update")
        print("\nNote: Do NOT modify the property_id column - it's needed for matching!")
        
        return filename
        
    except Exception as e:
        print(f"❌ Error exporting properties: {str(e)}")
        return None

if __name__ == "__main__":
    exported_file = export_properties_for_mapping()
    if exported_file:
        print(f"\n✨ Export complete! File ready: {exported_file}")
        exit(0)
    else:
        exit(1)