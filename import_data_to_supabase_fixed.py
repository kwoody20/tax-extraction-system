#!/usr/bin/env python3
"""
Import property tax data from CSV files to Supabase database.
Fixed version with proper date handling and encoding.
"""

import os
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime
from supabase import create_client, Client

# Supabase credentials
SUPABASE_URL = "https://klscgjbachumeojhxyno.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtsc2NnamJhY2h1bWVvamh4eW5vIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU3OTU1OTksImV4cCI6MjA3MTM3MTU5OX0.nJF44C6SPe-dNfPit7zTsij2foo67WNY3PFl7lfxquY"

def import_entities(client: Client, csv_path: str):
    """Import entities from CSV."""
    print(f"\nImporting entities from {csv_path}...")
    df = pd.read_csv(csv_path, encoding='latin-1')
    results = {"success": 0, "failed": 0, "errors": []}
    
    # Get column names
    columns = df.columns.tolist()
    print(f"  Found {len(df)} entities to import")
    
    for idx, row in df.iterrows():
        try:
            # Prepare entity data
            entity_data = {
                "entity_id": str(row[columns[0]]),
                "entity_name": str(row[columns[1]]),
            }
            
            # Add optional fields
            if len(columns) > 4 and pd.notna(row[columns[4]]):
                entity_data["jurisdiction"] = str(row[columns[4]])
            if len(columns) > 5 and pd.notna(row[columns[5]]):
                entity_data["state"] = str(row[columns[5]])
            if len(columns) > 6 and pd.notna(row[columns[6]]):
                entity_data["entity_type"] = str(row[columns[6]])
            else:
                entity_data["entity_type"] = "parent entity"
            
            # Handle date field
            if len(columns) > 7 and pd.notna(row[columns[7]]):
                try:
                    close_date = pd.to_datetime(row[columns[7]])
                    entity_data["close_date"] = close_date.strftime('%Y-%m-%d')
                except:
                    pass
            
            # Handle amount fields
            if len(columns) > 8 and pd.notna(row[columns[8]]):
                try:
                    amount = str(row[columns[8]]).replace("$", "").replace(",", "").strip()
                    if amount and amount != "entity":
                        entity_data["amount_due"] = float(amount)
                except:
                    pass
            
            if len(columns) > 9 and pd.notna(row[columns[9]]):
                try:
                    amount = str(row[columns[9]]).replace("$", "").replace(",", "").strip()
                    if amount and amount != "entity":
                        entity_data["previous_year_taxes"] = float(amount)
                except:
                    pass
            
            # Insert entity using upsert
            response = client.table("entities").upsert(entity_data).execute()
            if response.data:
                results["success"] += 1
                if (results["success"] % 10) == 0:
                    print(f"    Progress: {results['success']} imported...")
            else:
                results["failed"] += 1
                
        except Exception as e:
            results["failed"] += 1
            results["errors"].append({
                "row": idx,
                "entity": row[columns[1]] if len(columns) > 1 else "Unknown",
                "error": str(e)
            })
    
    return results

def import_properties(client: Client, csv_path: str):
    """Import properties from CSV."""
    print(f"\nImporting properties from {csv_path}...")
    df = pd.read_csv(csv_path, encoding='latin-1')
    results = {"success": 0, "failed": 0, "errors": []}
    
    print(f"  Found {len(df)} properties to import")
    
    for idx, row in df.iterrows():
        try:
            # Prepare property data
            property_data = {
                "property_id": str(row.get("Property ID")),
                "property_name": str(row.get("Property Name"))[:500] if pd.notna(row.get("Property Name")) else "Unknown",
            }
            
            # Add optional fields
            if pd.notna(row.get("Sub-Entity")):
                property_data["sub_entity"] = str(row.get("Sub-Entity"))
            
            if pd.notna(row.get("Parent Entity")):
                property_data["parent_entity_name"] = str(row.get("Parent Entity"))
                # Try to find matching entity ID
                entity_response = client.table("entities").select("entity_id").eq("entity_name", property_data["parent_entity_name"]).limit(1).execute()
                if entity_response.data and len(entity_response.data) > 0:
                    property_data["parent_entity_id"] = entity_response.data[0]["entity_id"]
            
            if pd.notna(row.get("Jurisdiction")):
                property_data["jurisdiction"] = str(row.get("Jurisdiction"))
            
            if pd.notna(row.get("State")):
                property_data["state"] = str(row.get("State"))
            
            property_data["property_type"] = str(row.get("Property Type", "property"))
            
            # Handle date
            if pd.notna(row.get("Close Date")):
                try:
                    close_date = pd.to_datetime(row.get("Close Date"))
                    property_data["close_date"] = close_date.strftime('%Y-%m-%d')
                except:
                    pass
            
            # Handle amounts
            try:
                amount_str = str(row.get("Amount Due", "0")).replace("$", "").replace(",", "").strip()
                property_data["amount_due"] = float(amount_str) if amount_str else 0
            except:
                property_data["amount_due"] = 0
            
            try:
                amount_str = str(row.get("Previous Year Taxes", "0")).replace("$", "").replace(",", "").strip()
                property_data["previous_year_taxes"] = float(amount_str) if amount_str else 0
            except:
                property_data["previous_year_taxes"] = 0
            
            # Other fields
            if pd.notna(row.get("Extraction Steps")):
                property_data["extraction_steps"] = str(row.get("Extraction Steps"))
            
            if pd.notna(row.get("Acct Number")):
                property_data["account_number"] = str(row.get("Acct Number"))
            
            if pd.notna(row.get("Property Address")):
                property_data["property_address"] = str(row.get("Property Address"))
            
            if pd.notna(row.get("Tax Bill Link")):
                property_data["tax_bill_link"] = str(row.get("Tax Bill Link"))
            
            # Insert property using upsert
            response = client.table("properties").upsert(property_data).execute()
            if response.data:
                results["success"] += 1
                if (results["success"] % 25) == 0:
                    print(f"    Progress: {results['success']} imported...")
            else:
                results["failed"] += 1
                
        except Exception as e:
            results["failed"] += 1
            results["errors"].append({
                "row": idx,
                "property": row.get("Property Name", "Unknown")[:50],
                "error": str(e)
            })
    
    return results

def main():
    """Main function to import data."""
    print("=" * 60)
    print("Property Tax Data Import to Supabase (Fixed)")
    print("=" * 60)
    
    # Initialize Supabase client
    try:
        print("\n1. Connecting to Supabase...")
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("   ✓ Connected successfully")
    except Exception as e:
        print(f"   ✗ Connection failed: {e}")
        sys.exit(1)
    
    # Import entities
    entities_file = "entities-proptax-8202025.csv"
    if Path(entities_file).exists():
        entity_results = import_entities(client, entities_file)
        print(f"\n   ✓ Entities import complete")
        print(f"     - Success: {entity_results['success']}")
        print(f"     - Failed: {entity_results['failed']}")
        if entity_results['errors'] and entity_results['errors'][:3]:
            print(f"     - Sample errors:")
            for error in entity_results['errors'][:3]:
                print(f"       • Row {error['row']}: {error['error'][:100]}")
    else:
        print(f"\n   ⚠ Skipping entities - {entities_file} not found")
    
    # Import properties
    properties_file = "OFFICIAL-proptax-assets.csv"
    if Path(properties_file).exists():
        property_results = import_properties(client, properties_file)
        print(f"\n   ✓ Properties import complete")
        print(f"     - Success: {property_results['success']}")
        print(f"     - Failed: {property_results['failed']}")
        if property_results['errors'] and property_results['errors'][:3]:
            print(f"     - Sample errors:")
            for error in property_results['errors'][:3]:
                print(f"       • Row {error['row']}: {error['error'][:100]}")
    else:
        print(f"\n   ⚠ Skipping properties - {properties_file} not found")
    
    # Get final statistics
    print("\n" + "=" * 60)
    print("Final Database Statistics:")
    print("=" * 60)
    
    try:
        # Count entities
        entity_count = client.table("entities").select("entity_id", count="exact").execute()
        print(f"Total Entities: {entity_count.count if hasattr(entity_count, 'count') else len(entity_count.data)}")
        
        # Count properties
        property_count = client.table("properties").select("property_id", count="exact").execute()
        print(f"Total Properties: {property_count.count if hasattr(property_count, 'count') else len(property_count.data)}")
        
        # Get sample data
        print("\nSample Entities:")
        entities = client.table("entities").select("entity_name, state, entity_type").limit(5).execute()
        for entity in entities.data[:5]:
            print(f"  • {entity['entity_name']} ({entity.get('state', 'N/A')})")
        
        print("\nSample Properties:")
        properties = client.table("properties").select("property_name, jurisdiction, state, amount_due").limit(5).execute()
        for prop in properties.data[:5]:
            name = prop['property_name'][:60] + "..." if len(prop['property_name']) > 60 else prop['property_name']
            print(f"  • {name}")
            print(f"    {prop.get('jurisdiction', 'N/A')}, {prop.get('state', 'N/A')} - ${prop.get('amount_due', 0):,.2f}")
        
    except Exception as e:
        print(f"Could not retrieve statistics: {e}")
    
    print("\n✅ Import complete! You can now:")
    print("  1. View your data at: https://supabase.com/dashboard/project/klscgjbachumeojhxyno")
    print("  2. Use the API service to extract tax data")
    print("  3. Access the dashboard to monitor extractions")

if __name__ == "__main__":
    main()