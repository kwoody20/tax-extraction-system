#!/usr/bin/env python3
"""
Verify and summarize the imported Supabase data.
"""

import os
from supabase import create_client
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

# Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Please set SUPABASE_URL and SUPABASE_KEY environment variables")

def main():
    print("=" * 70)
    print("SUPABASE DATA VERIFICATION REPORT")
    print("=" * 70)
    
    # Connect to Supabase
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # 1. Entity Summary
    print("\n📊 ENTITY SUMMARY")
    print("-" * 40)
    entities = client.table("entities").select("*").execute()
    print(f"Total Entities: {len(entities.data)}")
    
    entity_by_state = defaultdict(list)
    for entity in entities.data:
        state = entity.get('state', 'Unknown')
        entity_by_state[state].append(entity['entity_name'])
    
    print("\nEntities by State:")
    for state, names in sorted(entity_by_state.items(), key=lambda x: (x[0] is None, x[0])):
        print(f"  {state}: {len(names)} entities")
        for name in names[:2]:  # Show first 2
            print(f"    • {name[:50]}")
    
    # 2. Property Summary
    print("\n🏢 PROPERTY SUMMARY")
    print("-" * 40)
    properties = client.table("properties").select("*").execute()
    print(f"Total Properties: {len(properties.data)}")
    
    # Calculate totals
    total_amount_due = sum(p.get('amount_due', 0) for p in properties.data)
    total_previous_taxes = sum(p.get('previous_year_taxes', 0) for p in properties.data)
    properties_with_balance = sum(1 for p in properties.data if p.get('amount_due', 0) > 0)
    
    print(f"\nFinancial Summary:")
    print(f"  Total Amount Due: ${total_amount_due:,.2f}")
    print(f"  Total Previous Year Taxes: ${total_previous_taxes:,.2f}")
    print(f"  Properties with Balance: {properties_with_balance}")
    print(f"  Properties Paid (Zero Balance): {len(properties.data) - properties_with_balance}")
    
    # Properties by jurisdiction
    print("\nTop Jurisdictions:")
    jurisdiction_counts = defaultdict(int)
    jurisdiction_amounts = defaultdict(float)
    
    for prop in properties.data:
        jurisdiction = prop.get('jurisdiction', 'Unknown')
        jurisdiction_counts[jurisdiction] += 1
        jurisdiction_amounts[jurisdiction] += prop.get('amount_due', 0)
    
    # Sort by amount due
    sorted_jurisdictions = sorted(jurisdiction_amounts.items(), key=lambda x: x[1], reverse=True)
    for jurisdiction, amount in sorted_jurisdictions[:10]:
        count = jurisdiction_counts[jurisdiction]
        print(f"  {jurisdiction}: {count} properties, ${amount:,.2f} due")
    
    # 3. Data Quality Check
    print("\n✅ DATA QUALITY CHECK")
    print("-" * 40)
    
    # Properties with missing data
    missing_address = sum(1 for p in properties.data if not p.get('property_address'))
    missing_tax_link = sum(1 for p in properties.data if not p.get('tax_bill_link'))
    missing_parent = sum(1 for p in properties.data if not p.get('parent_entity_id'))
    
    print(f"Properties missing address: {missing_address}")
    print(f"Properties missing tax bill link: {missing_tax_link}")
    print(f"Properties without parent entity link: {missing_parent}")
    
    # 4. Extraction Readiness
    print("\n🔄 EXTRACTION READINESS")
    print("-" * 40)
    
    extractable = [p for p in properties.data if p.get('tax_bill_link')]
    print(f"Properties ready for extraction: {len(extractable)}")
    
    # Group by domain
    domain_counts = defaultdict(int)
    for prop in extractable:
        url = prop.get('tax_bill_link', '')
        if url:
            try:
                from urllib.parse import urlparse
                domain = urlparse(url).netloc
                domain_counts[domain] += 1
            except:
                pass
    
    print("\nTop Tax Website Domains:")
    for domain, count in sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {domain}: {count} properties")
    
    # 5. Sample Properties for Testing
    print("\n🧪 SAMPLE PROPERTIES FOR TESTING")
    print("-" * 40)
    
    # Get one property from each major jurisdiction
    test_properties = []
    seen_jurisdictions = set()
    
    for prop in properties.data:
        jurisdiction = prop.get('jurisdiction')
        if jurisdiction and jurisdiction not in seen_jurisdictions and prop.get('tax_bill_link'):
            test_properties.append(prop)
            seen_jurisdictions.add(jurisdiction)
            if len(test_properties) >= 5:
                break
    
    for prop in test_properties:
        print(f"\n{prop.get('property_name', 'Unknown')[:60]}")
        print(f"  ID: {prop.get('property_id')}")
        print(f"  Jurisdiction: {prop.get('jurisdiction')}, {prop.get('state')}")
        print(f"  Amount Due: ${prop.get('amount_due', 0):,.2f}")
        print(f"  Tax Link: {prop.get('tax_bill_link', 'N/A')[:80]}")
    
    print("\n" + "=" * 70)
    print("✅ DATA IMPORT VERIFICATION COMPLETE")
    print("=" * 70)
    print("\nYour Supabase database is ready with:")
    print(f"  • {len(entities.data)} entities")
    print(f"  • {len(properties.data)} properties")
    print(f"  • ${total_amount_due:,.2f} in total tax amounts")
    print(f"  • {len(extractable)} properties ready for extraction")
    print(f"\nDatabase URL: {SUPABASE_URL}")

if __name__ == "__main__":
    main()