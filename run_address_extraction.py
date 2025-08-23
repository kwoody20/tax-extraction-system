"""
Use MASTER_TAX_EXTRACTOR to get addresses for properties
"""

import pandas as pd
import sys
import os
import json
from datetime import datetime

# Add the extracting-tests-818 directory to path
sys.path.insert(0, 'extracting-tests-818')

# Import the master extractor
from MASTER_TAX_EXTRACTOR import extract_tax_info

# Load properties that need addresses
scrape_df = pd.read_csv('properties_to_scrape_20250823_134809.csv')

print("🔍 Using MASTER_TAX_EXTRACTOR for Address Extraction")
print("=" * 60)
print(f"Properties to process: {len(scrape_df)}")
print()

# Results storage
results = []
errors = []

# Process a sample of properties to avoid rate limiting
sample_size = 20
sample_df = scrape_df.head(sample_size)

print(f"Processing {len(sample_df)} properties as a sample...")
print("-" * 60)

for idx, prop in sample_df.iterrows():
    print(f"\n[{idx+1}/{len(sample_df)}] {prop['property_name'][:50]}...")
    print(f"  Jurisdiction: {prop['jurisdiction']}")
    print(f"  URL: {prop['tax_bill_link'][:60]}...")
    
    try:
        # Call the master extractor
        result = extract_tax_info(
            jurisdiction=prop['jurisdiction'],
            tax_bill_link=prop['tax_bill_link'],
            account_number=prop['account_number'] if pd.notna(prop['account_number']) else None,
            property_name=prop['property_name']
        )
        
        if result['success']:
            # Extract address from result
            address = result.get('property_address') or result.get('address')
            account = result.get('account_number')
            
            if address and address != 'N/A':
                results.append({
                    'id': prop['id'],
                    'property_name': prop['property_name'],
                    'found_address': address,
                    'found_account': account,
                    'tax_amount': result.get('tax_amount'),
                    'source': 'MASTER_TAX_EXTRACTOR'
                })
                print(f"  ✅ Found address: {address[:60]}")
            else:
                print(f"  ⚠️ No address found in extraction")
                
        else:
            print(f"  ❌ Extraction failed: {result.get('error', 'Unknown error')}")
            errors.append({
                'property_name': prop['property_name'],
                'error': result.get('error', 'Unknown error')
            })
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        errors.append({
            'property_name': prop['property_name'],
            'error': str(e)
        })

print()
print("=" * 60)
print("\n📊 Extraction Results")
print("-" * 60)
print(f"Successfully extracted: {len(results)} addresses")
print(f"Failed extractions: {len(errors)}")

if results:
    # Save results
    results_df = pd.DataFrame(results)
    filename = f"master_extracted_addresses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    results_df.to_csv(filename, index=False)
    print(f"\n✅ Results saved to: {filename}")
    
    # Show sample
    print("\n📋 Sample Results:")
    for result in results[:5]:
        print(f"\n  Property: {result['property_name'][:50]}...")
        print(f"  Address: {result['found_address']}")
        if result.get('found_account'):
            print(f"  Account: {result['found_account']}")
        if result.get('tax_amount'):
            print(f"  Tax Amount: ${result['tax_amount']}")

if errors:
    print("\n⚠️ Errors encountered:")
    for error in errors[:5]:
        print(f"  • {error['property_name'][:40]}: {error['error'][:50]}")