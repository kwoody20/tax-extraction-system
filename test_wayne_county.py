#!/usr/bin/env python3
"""Quick test for Wayne County extractor"""

import os
from nc_property_extractors import NCPropertyTaxExtractor

# Create output directories
os.makedirs('output/screenshots', exist_ok=True)

# Test Wayne County specifically
extractor = NCPropertyTaxExtractor(headless=False)

try:
    test_case = {
        'property_id': '4c5df72a-61c5-46e8-aaef-572c0fcd50f8',
        'property_name': 'BCS NC Fund Propco 01 LLC - Wayne County',
        'jurisdiction': 'Wayne',
        'state': 'NC',
        'account_number': '6096'
    }
    
    url = 'https://pwa.waynegov.com/PublicWebAccess/BillDetails.aspx?BillPk=2454000'
    
    print(f"Testing Wayne County extraction...")
    print(f"URL: {url}")
    
    result = extractor.extract(url, test_case)
    
    print(f"\nResults:")
    print(f"Status: {result.extraction_status}")
    print(f"Tax Amount: ${result.tax_amount:,.2f}" if result.tax_amount else "Tax Amount: None")
    print(f"Property Value: ${result.property_value:,.2f}" if result.property_value else "Property Value: None")
    print(f"Notes: {result.extraction_notes}")
    
    if result.tax_amount and 8000 <= result.tax_amount <= 10000:
        print("\n✓ SUCCESS: Tax amount is in expected range ($8,000-$10,000)")
    else:
        print("\n✗ FAILED: Tax amount not found or outside expected range")
        
finally:
    extractor.close()