#!/usr/bin/env python3
"""
Fix and import remaining records with data issues.
"""

import os
import sys
import pandas as pd
import numpy as np
from supabase import create_client
import uuid
from dotenv import load_dotenv

load_dotenv()

# Supabase credentials from environment
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: Please set SUPABASE_URL and SUPABASE_KEY environment variables")
    sys.exit(1)

def clean_amount(value):
    """Clean and convert amount values."""
    if pd.isna(value) or value in ['', 'nan', 'NaN', None]:
        return 0.0
    try:
        # Remove currency symbols and commas
        cleaned = str(value).replace('$', '').replace(',', '').replace('\t', '').strip()
        if cleaned == '' or cleaned.lower() == 'nan':
            return 0.0
        return float(cleaned)
    except:
        return 0.0

def main():
    print("Fixing remaining import issues...")
    
    # Connect to Supabase
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Read the problematic entities
    print("\n1. Fixing entities with invalid UUIDs...")
    df_entities = pd.read_csv("entities-proptax-8202025.csv", encoding='latin-1')
    
    # Check which entity had issues (row 22)
    problem_row = df_entities.iloc[22]
    entity_id = problem_row.iloc[0]
    
    if str(entity_id).lower() in ['nan', 'na', '']:
        # Generate a new UUID for this entity
        new_uuid = str(uuid.uuid4())
        entity_data = {
            "entity_id": new_uuid,
            "entity_name": str(problem_row.iloc[1]),
            "entity_type": "parent entity"
        }
        
        # Add other fields if available
        if pd.notna(problem_row.iloc[5]):
            entity_data["state"] = str(problem_row.iloc[5])
        
        try:
            response = client.table("entities").insert(entity_data).execute()
            if response.data:
                print(f"  ✓ Fixed entity: {entity_data['entity_name']}")
        except Exception as e:
            print(f"  ✗ Could not fix entity: {e}")
    
    # Fix remaining properties with NaN issues
    print("\n2. Fixing properties with NaN values...")
    df_props = pd.read_csv("OFFICIAL-proptax-assets.csv", encoding='latin-1')
    
    # Get indices of failed properties (starting from row 29)
    failed_indices = list(range(29, len(df_props)))
    fixed_count = 0
    
    for idx in failed_indices:
        if idx >= len(df_props):
            break
            
        row = df_props.iloc[idx]
        
        try:
            # Check if property already exists
            prop_id = str(row.get("Property ID"))
            existing = client.table("properties").select("property_id").eq("property_id", prop_id).execute()
            if existing.data:
                continue  # Skip if already imported
            
            # Prepare property data with careful NaN handling
            property_data = {
                "property_id": prop_id,
                "property_name": str(row.get("Property Name", "Unknown"))[:500],
            }
            
            # Handle all fields with NaN checks
            if pd.notna(row.get("Sub-Entity")):
                property_data["sub_entity"] = str(row.get("Sub-Entity"))
            
            if pd.notna(row.get("Parent Entity")):
                parent_name = str(row.get("Parent Entity"))
                property_data["parent_entity_name"] = parent_name
                
                # Try to find entity
                entity_response = client.table("entities").select("entity_id").eq("entity_name", parent_name).limit(1).execute()
                if entity_response.data:
                    property_data["parent_entity_id"] = entity_response.data[0]["entity_id"]
            
            if pd.notna(row.get("Jurisdiction")):
                property_data["jurisdiction"] = str(row.get("Jurisdiction"))
            
            if pd.notna(row.get("State")):
                property_data["state"] = str(row.get("State"))
            
            property_data["property_type"] = "property"
            
            # Handle date with NaN check
            close_date = row.get("Close Date")
            if pd.notna(close_date) and str(close_date).strip():
                try:
                    parsed_date = pd.to_datetime(close_date)
                    property_data["close_date"] = parsed_date.strftime('%Y-%m-%d')
                except:
                    pass
            
            # Clean amount fields - this is where NaN issues occur
            property_data["amount_due"] = clean_amount(row.get("Amount Due"))
            property_data["previous_year_taxes"] = clean_amount(row.get("Previous Year Taxes"))
            
            # Other fields
            if pd.notna(row.get("Extraction Steps")):
                property_data["extraction_steps"] = str(row.get("Extraction Steps"))
            
            if pd.notna(row.get("Acct Number")):
                acct = str(row.get("Acct Number"))
                if acct and acct.lower() not in ['nan', 'na']:
                    property_data["account_number"] = acct
            
            if pd.notna(row.get("Property Address")):
                property_data["property_address"] = str(row.get("Property Address"))
            
            if pd.notna(row.get("Tax Bill Link")):
                property_data["tax_bill_link"] = str(row.get("Tax Bill Link"))
            
            # Insert property
            response = client.table("properties").insert(property_data).execute()
            if response.data:
                fixed_count += 1
                if fixed_count % 10 == 0:
                    print(f"  Progress: {fixed_count} properties fixed...")
                    
        except Exception as e:
            if "duplicate key" not in str(e):
                print(f"  Issue with row {idx}: {str(e)[:100]}")
    
    print(f"\n  ✓ Fixed {fixed_count} additional properties")
    
    # Final statistics
    print("\n3. Final Database Statistics:")
    
    # Count entities
    entity_count = client.table("entities").select("entity_id", count="exact").execute()
    print(f"  Total Entities: {entity_count.count if hasattr(entity_count, 'count') else len(entity_count.data)}")
    
    # Count properties  
    property_count = client.table("properties").select("property_id", count="exact").execute()
    print(f"  Total Properties: {property_count.count if hasattr(property_count, 'count') else len(property_count.data)}")
    
    # Get summary by state
    print("\n  Properties by State:")
    state_summary = client.table("properties").select("state").execute()
    if state_summary.data:
        from collections import Counter
        states = Counter([p.get('state', 'Unknown') for p in state_summary.data])
        for state, count in states.most_common(5):
            print(f"    • {state}: {count} properties")
    
    print("\n✅ All fixable records have been imported!")
    print("\nRemember to re-enable RLS by running the 010_restore_rls.sql script in Supabase.")

if __name__ == "__main__":
    main()