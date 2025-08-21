#!/usr/bin/env python3
"""
Extract new records from rows 125-146 of the CSV
"""

import asyncio
import pandas as pd
import sys
from tax_extractor import PropertyTaxExtractor, CSVHandler, PropertyTaxRecord
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def extract_new_records():
    """Extract rows 125-146 from the CSV"""
    
    # Read the CSV
    csv_handler = CSVHandler()
    all_records = csv_handler.read_csv('completed-proptax-data.csv')
    
    logger.info(f"Total records in CSV: {len(all_records)}")
    
    # Get records 125-146 (0-indexed: 124-145, but we need to account for the index)
    # Filter to get the new records by checking the row range
    new_records = all_records[124:146]  # Python 0-indexed slicing
    
    logger.info(f"Extracting {len(new_records)} new records (rows 125-146)")
    
    # Filter out any entities
    records_to_extract = [
        r for r in new_records 
        if r.property_type not in ['entity', 'sub-entity'] 
        and r.tax_bill_link 
        and r.tax_bill_link != 'entity'
    ]
    
    logger.info(f"Found {len(records_to_extract)} valid records to extract")
    
    # Show what we're extracting
    print("\nRecords to extract:")
    for i, record in enumerate(records_to_extract, 1):
        print(f"{i}. {record.property_name[:60]}... ({record.jurisdiction})")
    
    # Initialize extractor
    extractor = PropertyTaxExtractor(headless=True, max_concurrent=2)
    
    # Extract data
    extracted_records = await extractor.extract_batch(records_to_extract)
    
    # Save results
    output_file = 'new_records_extraction.csv'
    csv_handler.write_results(extracted_records, output_file)
    csv_handler.write_summary(extracted_records, 'new_records_summary.json')
    
    # Print summary
    successful = sum(1 for r in extracted_records if r.extraction_status == 'success')
    failed = sum(1 for r in extracted_records if r.extraction_status == 'failed')
    
    print(f"\n{'='*60}")
    print("Extraction Complete:")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")
    print(f"  Total: {len(extracted_records)}")
    print('='*60)
    
    # Show details of failed extractions
    if failed > 0:
        print("\nFailed extractions:")
        for record in extracted_records:
            if record.extraction_status == 'failed':
                print(f"  - {record.property_name[:50]}...")
                print(f"    Error: {record.extraction_error}")
    
    return extracted_records

if __name__ == "__main__":
    asyncio.run(extract_new_records())