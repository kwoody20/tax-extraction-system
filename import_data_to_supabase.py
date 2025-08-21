#!/usr/bin/env python3
"""
Import property tax data from CSV files to Supabase database.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from supabase_client import SupabasePropertyTaxClient

# Supabase credentials
SUPABASE_URL = "https://klscgjbachumeojhxyno.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtsc2NnamJhY2h1bWVvamh4eW5vIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU3OTU1OTksImV4cCI6MjA3MTM3MTU5OX0.nJF44C6SPe-dNfPit7zTsij2foo67WNY3PFl7lfxquY"

def main():
    """Main function to import data."""
    print("=" * 60)
    print("Property Tax Data Import to Supabase")
    print("=" * 60)
    
    # Initialize Supabase client
    try:
        print("\n1. Connecting to Supabase...")
        client = SupabasePropertyTaxClient(url=SUPABASE_URL, key=SUPABASE_KEY)
        print("   ✓ Connected successfully")
    except Exception as e:
        print(f"   ✗ Connection failed: {e}")
        sys.exit(1)
    
    # Test connection by getting stats
    try:
        print("\n2. Testing database connection...")
        stats = client.calculate_tax_statistics()
        if stats:
            print(f"   ✓ Database is accessible")
            print(f"   Current properties in DB: {stats.get('total_properties', 0)}")
            print(f"   Current entities in DB: {stats.get('total_entities', 0)}")
        else:
            print("   ✓ Database is accessible (empty)")
    except Exception as e:
        print(f"   ✗ Could not retrieve statistics: {e}")
    
    # Import entities
    entities_file = "entities-proptax-8202025.csv"
    if Path(entities_file).exists():
        print(f"\n3. Importing entities from {entities_file}...")
        try:
            entity_results = client.bulk_import_entities_from_csv(entities_file)
            print(f"   ✓ Entities imported successfully")
            print(f"     - Success: {entity_results['success']}")
            print(f"     - Failed: {entity_results['failed']}")
            if entity_results['errors']:
                print(f"     - Errors (first 5):")
                for error in entity_results['errors'][:5]:
                    print(f"       • {error['row']}: {error['error']}")
        except Exception as e:
            print(f"   ✗ Entity import failed: {e}")
    else:
        print(f"\n3. Skipping entities import - {entities_file} not found")
    
    # Import properties
    properties_file = "OFFICIAL-proptax-assets.csv"
    if Path(properties_file).exists():
        print(f"\n4. Importing properties from {properties_file}...")
        try:
            property_results = client.bulk_import_properties_from_csv(properties_file)
            print(f"   ✓ Properties imported successfully")
            print(f"     - Success: {property_results['success']}")
            print(f"     - Failed: {property_results['failed']}")
            if property_results['errors']:
                print(f"     - Errors (first 5):")
                for error in property_results['errors'][:5]:
                    print(f"       • {error['row']}: {error['error']}")
        except Exception as e:
            print(f"   ✗ Property import failed: {e}")
    else:
        print(f"\n4. Skipping properties import - {properties_file} not found")
    
    # Get final statistics
    print("\n5. Final Database Statistics:")
    try:
        final_stats = client.calculate_tax_statistics()
        if final_stats:
            print(f"   - Total Properties: {final_stats.get('total_properties', 0):,}")
            print(f"   - Total Entities: {final_stats.get('total_entities', 0):,}")
            print(f"   - Total Amount Due: ${final_stats.get('total_amount_due', 0):,.2f}")
            print(f"   - Total Previous Year Taxes: ${final_stats.get('total_previous_year_taxes', 0):,.2f}")
            print(f"   - Properties with Balance: {final_stats.get('properties_with_balance', 0):,}")
            print(f"   - Properties Paid: {final_stats.get('properties_paid', 0):,}")
            print(f"   - Average Amount Due: ${final_stats.get('avg_amount_due', 0):,.2f}")
    except Exception as e:
        print(f"   ✗ Could not retrieve final statistics: {e}")
    
    # Get sample data
    print("\n6. Sample Data Verification:")
    try:
        # Get sample entities
        entities = client.get_entities(limit=3)
        if entities:
            print("   Sample Entities:")
            for entity in entities:
                print(f"     • {entity.get('entity_name', 'Unknown')} ({entity.get('state', 'N/A')})")
        
        # Get sample properties
        properties = client.get_properties(limit=3)
        if properties:
            print("   Sample Properties:")
            for prop in properties:
                print(f"     • {prop.get('property_name', 'Unknown')[:50]}... - ${prop.get('amount_due', 0):,.2f}")
        
        # Get properties needing extraction
        need_extraction = client.find_properties_needing_extraction(days_since_last=30)
        print(f"\n   Properties needing extraction: {len(need_extraction)}")
        
    except Exception as e:
        print(f"   ✗ Could not retrieve sample data: {e}")
    
    print("\n" + "=" * 60)
    print("Import Process Complete!")
    print("=" * 60)
    
    # Get jurisdictions summary
    try:
        print("\n7. Jurisdictions Summary:")
        jurisdictions = client.get_jurisdictions()
        if jurisdictions:
            print(f"   Total jurisdictions configured: {len(jurisdictions)}")
        
        # Get tax payment overview
        payment_overview = client.get_tax_payment_overview()
        if payment_overview:
            print(f"\n   Top 5 Jurisdictions by Tax Amount:")
            for item in payment_overview[:5]:
                print(f"     • {item.get('jurisdiction', 'Unknown')}, {item.get('state', 'N/A')}: ${item.get('total_amount_due', 0):,.2f}")
    except Exception as e:
        print(f"   Note: Jurisdiction data not yet populated")
    
    print("\n✅ Database is ready for use!")
    print("\nYou can now:")
    print("  1. Use the API service to extract tax data")
    print("  2. Access the dashboard to monitor extractions")
    print("  3. Query the database directly via Supabase dashboard")

if __name__ == "__main__":
    main()