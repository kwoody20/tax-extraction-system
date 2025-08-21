#!/usr/bin/env python3
"""
Property Tax Data Extraction Runner
Simple script to run the tax data extraction
"""

import asyncio
import sys
import argparse
from pathlib import Path
import logging

from tax_extractor import (
    PropertyTaxExtractor,
    CSVHandler,
    PropertyTaxRecord
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def extract_specific_properties(property_ids: list, input_csv: str):
    """Extract data for specific property IDs only"""
    
    csv_handler = CSVHandler()
    all_records = csv_handler.read_csv(input_csv)
    
    # Filter to specific properties
    records_to_extract = [
        r for r in all_records
        if r.property_id in property_ids
        and r.property_type not in ['entity', 'sub-entity']
        and r.tax_bill_link
        and r.tax_bill_link != 'entity'
    ]
    
    if not records_to_extract:
        logger.warning("No matching properties found for extraction")
        return
    
    logger.info(f"Extracting {len(records_to_extract)} properties")
    
    # Run extraction
    extractor = PropertyTaxExtractor(headless=True, max_concurrent=1)
    extracted = await extractor.extract_batch(records_to_extract)
    
    # Save results
    output_file = f"extraction_results_{len(property_ids)}_properties.csv"
    csv_handler.write_results(extracted, output_file)
    
    # Print results
    for record in extracted:
        print(f"\nProperty: {record.property_name}")
        print(f"Status: {record.extraction_status}")
        if record.extracted_data:
            print(f"Extracted Data: {record.extracted_data}")
        if record.extraction_error:
            print(f"Error: {record.extraction_error}")


async def extract_by_jurisdiction(jurisdiction: str, input_csv: str):
    """Extract all properties for a specific jurisdiction"""
    
    csv_handler = CSVHandler()
    all_records = csv_handler.read_csv(input_csv)
    
    # Filter by jurisdiction
    records_to_extract = [
        r for r in all_records
        if r.jurisdiction and jurisdiction.lower() in r.jurisdiction.lower()
        and r.property_type not in ['entity', 'sub-entity']
        and r.tax_bill_link
        and r.tax_bill_link != 'entity'
    ]
    
    if not records_to_extract:
        logger.warning(f"No properties found for jurisdiction: {jurisdiction}")
        return
    
    logger.info(f"Extracting {len(records_to_extract)} properties from {jurisdiction}")
    
    # Run extraction
    extractor = PropertyTaxExtractor(headless=True, max_concurrent=2)
    extracted = await extractor.extract_batch(records_to_extract)
    
    # Save results
    output_file = f"extraction_{jurisdiction.lower().replace(' ', '_')}.csv"
    csv_handler.write_results(extracted, output_file)
    csv_handler.write_summary(extracted, f"summary_{jurisdiction.lower().replace(' ', '_')}.json")
    
    # Print summary
    successful = sum(1 for r in extracted if r.extraction_status == 'success')
    failed = sum(1 for r in extracted if r.extraction_status == 'failed')
    
    print(f"\nExtraction Results for {jurisdiction}:")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")
    print(f"  Total: {len(extracted)}")


async def test_extraction(input_csv: str, limit: int = 5):
    """Test extraction with a small sample"""
    
    csv_handler = CSVHandler()
    all_records = csv_handler.read_csv(input_csv)
    
    # Get a sample of different jurisdictions
    test_records = []
    jurisdictions_seen = set()
    
    for record in all_records:
        if (record.property_type not in ['entity', 'sub-entity'] 
            and record.tax_bill_link 
            and record.tax_bill_link != 'entity'):
            
            if record.jurisdiction not in jurisdictions_seen:
                test_records.append(record)
                jurisdictions_seen.add(record.jurisdiction)
                
                if len(test_records) >= limit:
                    break
    
    logger.info(f"Testing with {len(test_records)} properties from different jurisdictions")
    
    # Run extraction with visible browser for testing
    extractor = PropertyTaxExtractor(headless=False, max_concurrent=1)
    extracted = await extractor.extract_batch(test_records)
    
    # Save test results
    csv_handler.write_results(extracted, "test_extraction_results.csv")
    
    # Display results
    for record in extracted:
        print(f"\n{'='*60}")
        print(f"Property: {record.property_name}")
        print(f"Jurisdiction: {record.jurisdiction}")
        print(f"Status: {record.extraction_status}")
        
        if record.extracted_data:
            print("Extracted Data:")
            for key, value in record.extracted_data.items():
                print(f"  {key}: {value}")
        
        if record.extraction_error:
            print(f"Error: {record.extraction_error}")


async def main():
    parser = argparse.ArgumentParser(description='Property Tax Data Extractor')
    parser.add_argument('--input', '-i', default='completed-proptax-data.csv',
                       help='Input CSV file path')
    parser.add_argument('--mode', '-m', choices=['all', 'test', 'specific', 'jurisdiction'],
                       default='all', help='Extraction mode')
    parser.add_argument('--ids', nargs='+', help='Property IDs for specific mode')
    parser.add_argument('--jurisdiction', '-j', help='Jurisdiction name for jurisdiction mode')
    parser.add_argument('--limit', '-l', type=int, default=5,
                       help='Number of records for test mode')
    parser.add_argument('--headless', action='store_true',
                       help='Run browser in headless mode')
    parser.add_argument('--concurrent', '-c', type=int, default=3,
                       help='Number of concurrent extractions')
    
    args = parser.parse_args()
    
    # Check input file exists
    if not Path(args.input).exists():
        logger.error(f"Input file not found: {args.input}")
        sys.exit(1)
    
    # Run based on mode
    if args.mode == 'test':
        await test_extraction(args.input, args.limit)
    
    elif args.mode == 'specific':
        if not args.ids:
            logger.error("Property IDs required for specific mode")
            sys.exit(1)
        await extract_specific_properties(args.ids, args.input)
    
    elif args.mode == 'jurisdiction':
        if not args.jurisdiction:
            logger.error("Jurisdiction name required for jurisdiction mode")
            sys.exit(1)
        await extract_by_jurisdiction(args.jurisdiction, args.input)
    
    else:  # all mode
        # Run full extraction
        from tax_extractor import main as run_full_extraction
        await run_full_extraction()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Extraction interrupted by user")
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        sys.exit(1)