#!/usr/bin/env python3
"""
Test script for Selenium tax extractors
Tests both Maricopa County and Harris County extractors with real data
"""

import json
import logging
from datetime import datetime
from selenium_tax_extractors import (
    MaricopaCountySeleniumExtractor,
    HarrisCountySeleniumExtractor,
    UnifiedTaxExtractor,
    TaxExtractionResult
)

# Configure logging for testing
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_maricopa_county():
    """Test Maricopa County extractor with known parcels"""
    print("\n" + "="*60)
    print("TESTING MARICOPA COUNTY EXTRACTOR")
    print("="*60)
    
    test_cases = [
        {
            'property_id': 'test-1',
            'property_name': 'Jack In The Box - Phoenix',
            'parcel_number': '214-05-025A',
            'expected_address': '17017 N CAVE CREEK',
            'tax_bill_link': 'https://treasurer.maricopa.gov/'
        },
        {
            'property_id': 'test-2', 
            'property_name': 'Batteries Plus - Phoenix',
            'acct_number': '214-05-025B',  # Using acct_number field
            'expected_address': '2404 E BELL',
            'tax_bill_link': 'https://treasurer.maricopa.gov/'
        }
    ]
    
    extractor = MaricopaCountySeleniumExtractor(headless=False)
    results = []
    
    try:
        for test_case in test_cases:
            print(f"\nTesting: {test_case['property_name']}")
            print(f"Parcel: {test_case.get('parcel_number') or test_case.get('acct_number')}")
            
            result = extractor.extract(test_case)
            results.append(result)
            
            # Validate results
            print(f"Status: {result.extraction_status}")
            
            if result.extraction_status == 'success':
                print(f"✓ Property Address: {result.property_address}")
                print(f"✓ Owner Name: {result.owner_name}")
                print(f"✓ Amount Due: ${result.amount_due:,.2f}" if result.amount_due else "Amount Due: Not found")
                print(f"✓ Previous Year: ${result.previous_year_taxes:,.2f}" if result.previous_year_taxes else "Previous Year: Not found")
                
                # Check if address matches expected
                if test_case.get('expected_address'):
                    if result.property_address and test_case['expected_address'].upper() in result.property_address.upper():
                        print(f"✓ Address validation PASSED")
                    else:
                        print(f"✗ Address validation FAILED - Expected to contain: {test_case['expected_address']}")
            else:
                print(f"✗ Extraction failed: {result.extraction_notes}")
                if result.screenshot_path:
                    print(f"  Screenshot saved: {result.screenshot_path}")
    
    finally:
        extractor.cleanup()
    
    return results


def test_harris_county():
    """Test Harris County extractor with real URLs"""
    print("\n" + "="*60)
    print("TESTING HARRIS COUNTY EXTRACTOR")
    print("="*60)
    
    test_cases = [
        {
            'property_id': 'test-harris-1',
            'property_name': 'BCS Auto Properties - Federal Rd',
            'expected_address': '1204 FEDERAL',
            'tax_bill_link': 'https://www.hctax.net/property/TaxStatement?account=H121C5X068PKoeFCzGBdue+rsqT9Ldjc83+oKTkml9U='
        },
        {
            'property_id': 'test-harris-2',
            'property_name': 'BCS Humble LLC',
            'expected_address': 'FM 1960',
            'tax_bill_link': 'https://www.hctax.net/Property/TaxStatement?account=8qkZXsVNHomOFw9TVPqs+xmvCp2keJ24TOejPl2lx9Y='
        },
        {
            'property_id': 'test-harris-3',
            'property_name': 'BCS Baytown Grove',
            'expected_address': 'INTERSTATE 10',
            'tax_bill_link': 'https://www.hctax.net/property/TaxStatement?account=QSwzVbdqmlLu7JpRwBhtTHJe2U8ZwsULJKmM+zQxijg='
        }
    ]
    
    extractor = HarrisCountySeleniumExtractor(headless=False)
    results = []
    
    try:
        for test_case in test_cases:
            print(f"\nTesting: {test_case['property_name']}")
            print(f"URL: {test_case['tax_bill_link'][:50]}...")
            
            result = extractor.extract(test_case)
            results.append(result)
            
            # Validate results
            print(f"Status: {result.extraction_status}")
            
            if result.extraction_status in ['success', 'partial']:
                if result.property_address:
                    print(f"✓ Property Address: {result.property_address}")
                if result.owner_name:
                    print(f"✓ Owner Name: {result.owner_name}")
                if result.amount_due:
                    print(f"✓ Amount Due: ${result.amount_due:,.2f}")
                if result.due_date:
                    print(f"✓ Due Date: {result.due_date}")
                if result.tax_year:
                    print(f"✓ Tax Year: {result.tax_year}")
                
                # Validate address if found
                if test_case.get('expected_address') and result.property_address:
                    if test_case['expected_address'].upper() in result.property_address.upper():
                        print(f"✓ Address validation PASSED")
                    else:
                        print(f"⚠ Address validation WARNING - Expected: {test_case['expected_address']}")
                
                # Check if we got the critical amount_due field
                if not result.amount_due:
                    print(f"⚠ WARNING: Amount due not extracted")
            else:
                print(f"✗ Extraction failed: {result.extraction_notes}")
                if result.screenshot_path:
                    print(f"  Screenshot saved: {result.screenshot_path}")
    
    finally:
        extractor.cleanup()
    
    return results


def test_unified_extractor():
    """Test the unified extractor with mixed county data"""
    print("\n" + "="*60)
    print("TESTING UNIFIED EXTRACTOR")
    print("="*60)
    
    test_properties = [
        {
            'property_id': 'unified-1',
            'property_name': 'Maricopa Test Property',
            'acct_number': '214-05-025A',
            'tax_bill_link': 'https://treasurer.maricopa.gov/'
        },
        {
            'property_id': 'unified-2',
            'property_name': 'Harris Test Property',
            'tax_bill_link': 'https://www.hctax.net/property/TaxStatement?account=H121C5X068PKoeFCzGBdue+rsqT9Ldjc83+oKTkml9U='
        }
    ]
    
    extractor = UnifiedTaxExtractor(headless=False)
    
    try:
        results = extractor.process_batch(test_properties, output_file='unified_test_results.json')
        
        # Analyze results
        success_count = sum(1 for r in results if r.get('extraction_status') == 'success')
        partial_count = sum(1 for r in results if r.get('extraction_status') == 'partial')
        failed_count = sum(1 for r in results if r.get('extraction_status') == 'failed')
        
        print(f"\nResults Summary:")
        print(f"  Success: {success_count}/{len(results)}")
        print(f"  Partial: {partial_count}/{len(results)}")
        print(f"  Failed: {failed_count}/{len(results)}")
        
    finally:
        extractor.cleanup()


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("SELENIUM TAX EXTRACTOR TEST SUITE")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    all_results = {}
    
    # Test Maricopa County
    try:
        maricopa_results = test_maricopa_county()
        all_results['maricopa'] = [r.__dict__ for r in maricopa_results]
    except Exception as e:
        logger.error(f"Maricopa test failed: {e}")
        all_results['maricopa'] = {'error': str(e)}
    
    # Test Harris County
    try:
        harris_results = test_harris_county()
        all_results['harris'] = [r.__dict__ for r in harris_results]
    except Exception as e:
        logger.error(f"Harris test failed: {e}")
        all_results['harris'] = {'error': str(e)}
    
    # Test Unified Extractor
    try:
        test_unified_extractor()
    except Exception as e:
        logger.error(f"Unified test failed: {e}")
    
    # Save all test results
    with open('test_results_summary.json', 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    
    print("\n" + "="*60)
    print("TEST SUITE COMPLETED")
    print(f"Results saved to: test_results_summary.json")
    print("="*60)


if __name__ == "__main__":
    main()