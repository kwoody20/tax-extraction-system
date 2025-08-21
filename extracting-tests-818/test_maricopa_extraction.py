#!/usr/bin/env python3
"""
Test the updated Maricopa County extractor
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from tax_extractor import PropertyTaxExtractor, CSVHandler, PropertyTaxRecord

async def test_maricopa_properties():
    """Test extraction for Maricopa County properties"""
    
    # Read the CSV to get Maricopa properties
    csv_handler = CSVHandler()
    all_records = csv_handler.read_csv('completed-proptax-data.csv')
    
    # Filter for Maricopa County properties only
    maricopa_records = [
        r for r in all_records
        if r.jurisdiction and 'maricopa' in r.jurisdiction.lower()
        and r.property_type not in ['entity', 'sub-entity']
        and r.tax_bill_link
    ]
    
    if not maricopa_records:
        print("No Maricopa County properties found")
        return
    
    print(f"Found {len(maricopa_records)} Maricopa County properties")
    print("\nTesting extraction with visible browser...\n")
    
    # Test with visible browser
    extractor = PropertyTaxExtractor(headless=False, max_concurrent=1)
    
    # Extract the properties
    results = await extractor.extract_batch(maricopa_records)
    
    # Display results
    for record in results:
        print(f"\n{'='*60}")
        print(f"Property: {record.property_name}")
        print(f"Parcel Number: {record.acct_number}")
        print(f"Status: {record.extraction_status}")
        
        if record.extracted_data:
            print("Extracted Data:")
            for key, value in record.extracted_data.items():
                print(f"  {key}: {value}")
        
        if record.extraction_error:
            print(f"Error: {record.extraction_error}")
    
    # Save results
    csv_handler.write_results(results, 'maricopa_test_results.csv')
    print(f"\n\nResults saved to maricopa_test_results.csv")

if __name__ == "__main__":
    asyncio.run(test_maricopa_properties())