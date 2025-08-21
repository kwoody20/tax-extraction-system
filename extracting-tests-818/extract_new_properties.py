#!/usr/bin/env python3
"""
Extract the newly added property records with tax bill links
"""

import asyncio
import pandas as pd
from tax_extractor import PropertyTaxExtractor, CSVHandler
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def extract_new_properties():
    """Extract the newly added property records"""
    
    # Read all records
    csv_handler = CSVHandler()
    all_records = csv_handler.read_csv('completed-proptax-data.csv')
    
    # Identify the new records by their patterns
    new_records = []
    for record in all_records:
        # Check for the new NC Fund properties, Montgomery Tracts, etc.
        if any([
            'BCS NC Fund Propco' in record.property_name,
            'BCS Montgomery LLC - Tract' in record.property_name,
            'Houston QSR Propco LLC - 3101 FM 528' in record.property_name,
            'OCV Pueblo II' in record.property_name
        ]):
            # Only include if it has a valid tax link and is not an entity
            if (record.tax_bill_link and 
                record.tax_bill_link != 'entity' and 
                record.property_type != 'entity' and
                record.property_type != 'sub-entity'):
                new_records.append(record)
    
    logger.info(f"Found {len(new_records)} new properties to extract")
    
    # Show what we're extracting
    print("\n" + "="*60)
    print("NEW PROPERTIES TO EXTRACT:")
    print("="*60)
    for i, record in enumerate(new_records, 1):
        print(f"{i}. {record.property_name[:60]}...")
        print(f"   Jurisdiction: {record.jurisdiction}")
        print(f"   Link: {record.tax_bill_link[:70]}...")
    
    # Initialize extractor
    extractor = PropertyTaxExtractor(headless=True, max_concurrent=2)
    
    # Extract data
    print("\n" + "="*60)
    print("STARTING EXTRACTION...")
    print("="*60)
    
    extracted_records = await extractor.extract_batch(new_records)
    
    # Save results
    output_file = 'new_properties_extraction.csv'
    csv_handler.write_results(extracted_records, output_file)
    csv_handler.write_summary(extracted_records, 'new_properties_summary.json')
    
    # Print results
    successful = sum(1 for r in extracted_records if r.extraction_status == 'success')
    failed = sum(1 for r in extracted_records if r.extraction_status == 'failed')
    
    print("\n" + "="*60)
    print("EXTRACTION COMPLETE")
    print("="*60)
    print(f"Total: {len(extracted_records)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    
    # Show detailed results
    print("\n" + "="*60)
    print("DETAILED RESULTS:")
    print("="*60)
    
    for record in extracted_records:
        status = "✅" if record.extraction_status == 'success' else "❌"
        print(f"\n{status} {record.property_name[:60]}...")
        print(f"   Jurisdiction: {record.jurisdiction}")
        
        if record.extraction_status == 'success' and record.extracted_data:
            data = record.extracted_data
            # Try to find and display the tax amount
            amount = None
            if 'current_amount_due' in data:
                amount = data['current_amount_due']
            elif 'total_amount_due' in data:
                amount = data['total_amount_due']
            elif 'all_amounts_found' in data and data['all_amounts_found']:
                amount = data['all_amounts_found'][0]
            
            if amount:
                print(f"   Tax Amount: {amount}")
            else:
                print(f"   Tax data extracted (check CSV for details)")
                
        elif record.extraction_status == 'failed':
            print(f"   Error: {record.extraction_error[:100]}...")
    
    return extracted_records

if __name__ == "__main__":
    asyncio.run(extract_new_properties())