#!/usr/bin/env python3
"""
Test script for NC Property Tax Extractors
Tests specific problematic NC properties to ensure correct tax amount extraction
"""

import logging
import os
from nc_property_extractors import NCPropertyTaxExtractor
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_specific_properties():
    """Test specific NC properties that have been problematic"""
    
    # Create output directories
    os.makedirs('output/screenshots', exist_ok=True)
    
    # Test cases with expected values
    test_cases = [
        {
            'property_id': '4c5df72a-61c5-46e8-aaef-572c0fcd50f8',
            'property_name': 'BCS NC Fund Propco 01 LLC - 124 NC Highway 55 West, Mount Olive, NC',
            'jurisdiction': 'Wayne',
            'state': 'NC',
            'url': 'https://pwa.waynegov.com/PublicWebAccess/BillDetails.aspx?BillPk=2454000',
            'expected_range': (8000, 10000),  # Expected tax amount range
            'account_number': '6096'
        },
        {
            'property_id': 'cc27a22b-a591-4e86-9879-e9b7160f2d58',
            'property_name': 'BCS NC Fund Propco 02 LLC - 420 E. New Hope Road, Goldsboro, NC',
            'jurisdiction': 'Wayne',
            'state': 'NC',
            'url': 'https://pwa.waynegov.com/PublicWebAccess/BillDetails.aspx?BillPk=2454038',
            'expected_range': (9000, 11000),
            'account_number': '29924'
        },
        {
            'property_id': '90da0b23-fdb3-4989-90d8-318099dd6d11',
            'property_name': 'BCS NC Fund Propco 04 LLC - 2103 S Brightleaf Blvd, Smithfield, NC - Parcel 1 (0.72 Acre)',
            'jurisdiction': 'Johnston',
            'state': 'NC',
            'url': 'https://taxpay.johnstonnc.com/TaxPayOnline/prod/',
            'expected_range': (300, 500),
            'account_number': ''
        },
        {
            'property_id': '2367bda1-0fec-4786-a845-fc678c37f31c',
            'property_name': 'BCS NC Fund Propco 04 LLC - 2103 S Brightleaf Blvd, Smithfield, NC - Parcel 2 (0.3 Acre)',
            'jurisdiction': 'Johnston',
            'state': 'NC',
            'url': 'https://taxpay.johnstonnc.com/TaxPayOnline/prod/',
            'expected_range': (8000, 9000),
            'account_number': ''
        },
        {
            'property_id': 'a4add047-095d-4c1f-9312-02451b7ba600',
            'property_name': 'BCS NC Fund Propco 05 LLC - 334 E Main Street, Havelock, NC (Craven County)',
            'jurisdiction': 'Craven',
            'state': 'NC',
            'url': 'https://www.bttaxpayerportal.com/ITSPublicCR/TaxBillSearch',
            'expected_range': (4500, 5000),
            'account_number': '114834'
        },
        {
            'property_id': 'ff5d1f45-41e9-4c76-8704-6f45d0e22df0',
            'property_name': 'BCS NC Fund Propco 12 LLC - 1602 Martin Luther King Jr. Pkwy, Wilson, NC - Parcel 1',
            'jurisdiction': 'Wilson',
            'state': 'NC',
            'url': 'https://wilsonnc.devnetwedge.com/',
            'expected_range': (1000, 10000),  # Range unknown
            'account_number': ''
        },
        {
            'property_id': 'b091fee1-f139-4042-bd5d-94377a004986',
            'property_name': 'BCS NC Fund Propco 15 LLC - (Vance County) 1640 North Garnett Street, Henderson, NC',
            'jurisdiction': 'Vance',
            'state': 'NC',
            'url': 'https://vance.ustaxdata.com/account.cfm?parcelID=0044%2006010',
            'expected_range': (1000, 20000),  # Range unknown but should not be $500,000
            'account_number': ''
        },
        {
            'property_id': '11bf5daa-bd33-4e7e-8d79-9b4a8d71a126',
            'property_name': 'BCS NC Fund Propco 10 LLC - 2532 W. 5th Street, Washington, NC (Beaufort County)',
            'jurisdiction': 'Beaufort',
            'state': 'NC',
            'url': 'https://bcpwa.ncptscloud.com/beauforttax/BillDetails.aspx?BillPk=1125818',
            'expected_range': (1000, 20000),
            'account_number': ''
        }
    ]
    
    # Initialize extractor
    extractor = NCPropertyTaxExtractor(headless=False)  # Use headless=True for production
    
    results = []
    passed = 0
    failed = 0
    
    try:
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n{'='*60}")
            print(f"Test {i}/{len(test_cases)}: {test_case['jurisdiction']} County")
            print(f"Property: {test_case['property_name'][:50]}...")
            print(f"Expected Range: ${test_case['expected_range'][0]:,} - ${test_case['expected_range'][1]:,}")
            
            property_info = {
                'property_id': test_case['property_id'],
                'property_name': test_case['property_name'],
                'jurisdiction': test_case['jurisdiction'],
                'state': test_case['state'],
                'account_number': test_case['account_number']
            }
            
            # Extract tax information
            result = extractor.extract(test_case['url'], property_info)
            
            # Check results
            test_passed = False
            if result.extraction_status == 'success' and result.tax_amount:
                if test_case['expected_range'][0] <= result.tax_amount <= test_case['expected_range'][1]:
                    print(f"✓ PASSED: Extracted ${result.tax_amount:,.2f}")
                    test_passed = True
                    passed += 1
                else:
                    print(f"✗ FAILED: Extracted ${result.tax_amount:,.2f} (outside expected range)")
                    failed += 1
            else:
                print(f"✗ FAILED: {result.extraction_status} - {result.extraction_notes}")
                failed += 1
            
            # Add test results
            result_dict = {
                'test_case': i,
                'jurisdiction': test_case['jurisdiction'],
                'property_name': test_case['property_name'][:50],
                'expected_min': test_case['expected_range'][0],
                'expected_max': test_case['expected_range'][1],
                'extracted_tax': result.tax_amount,
                'extracted_property_value': result.property_value,
                'status': result.extraction_status,
                'passed': test_passed,
                'notes': result.extraction_notes[:100] if result.extraction_notes else ''
            }
            results.append(result_dict)
            
            # Show property value if extracted (for debugging)
            if result.property_value:
                print(f"  Property Value Found: ${result.property_value:,.2f} (avoided)")
    
    finally:
        extractor.close()
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Total Tests: {len(test_cases)}")
    print(f"Passed: {passed} ({passed/len(test_cases)*100:.1f}%)")
    print(f"Failed: {failed} ({failed/len(test_cases)*100:.1f}%)")
    
    # Save results to Excel
    results_df = pd.DataFrame(results)
    results_df.to_excel('nc_test_results.xlsx', index=False)
    print(f"\nDetailed results saved to: nc_test_results.xlsx")
    
    # Show failed tests
    if failed > 0:
        print("\nFailed Tests:")
        failed_results = [r for r in results if not r['passed']]
        for r in failed_results:
            print(f"  - {r['jurisdiction']}: {r['property_name']}")
            print(f"    Status: {r['status']}, Notes: {r['notes']}")
    
    return results


def test_full_nc_batch():
    """Test all NC properties from the CSV file"""
    
    # Create output directories
    os.makedirs('output/screenshots', exist_ok=True)
    
    print("Testing all NC properties from CSV...")
    
    extractor = NCPropertyTaxExtractor(headless=True)  # Use headless for batch
    
    try:
        # Process all NC properties
        results = extractor.process_excel_batch(
            'OFFICIAL-proptax-extract.csv',
            'nc_full_extraction_results.xlsx',
            nc_only=True
        )
        
        print(f"\nProcessed {len(results)} NC properties")
        
        # Analyze results
        successful = [r for r in results if r['extraction_status'] == 'success' and r['tax_amount']]
        failed = [r for r in results if r['extraction_status'] == 'failed']
        
        print(f"Successful: {len(successful)}")
        print(f"Failed: {len(failed)}")
        
        # Show some successful extractions
        if successful:
            print("\nSample Successful Extractions:")
            for r in successful[:5]:
                print(f"  {r['property_name'][:50]}: ${r['tax_amount']:,.2f}")
        
        # Show failed extractions
        if failed:
            print("\nFailed Extractions:")
            for r in failed[:10]:
                print(f"  {r['property_name'][:50]}: {r['extraction_notes'][:50]}")
    
    finally:
        extractor.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--full':
        # Run full batch test
        test_full_nc_batch()
    else:
        # Run specific property tests
        test_specific_properties()