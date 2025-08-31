#!/usr/bin/env python3
"""
Simple Property Tax Extractor using web fetching
Extracts tax information from various county websites
"""

import pandas as pd
import requests
from urllib.parse import urlparse, parse_qs
import logging
from datetime import datetime
import time
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SimpleTaxExtractor:
    """Simple tax information extractor using requests"""
    
    def __init__(self, excel_file: str):
        self.excel_file = excel_file
        self.df = pd.read_excel(excel_file)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def extract_montgomery_county(self, url: str) -> dict:
        """Extract from Montgomery County (actweb.acttax.com)"""
        result = {
            'extraction_status': 'pending',
            'extraction_timestamp': datetime.now().isoformat()
        }
        
        try:
            # Extract account number from URL
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            account_num = params.get('can', [None])[0]
            
            if account_num:
                result['account_number'] = account_num
                logger.info(f"Found account number: {account_num}")
            
            # Make request
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            # For demonstration, marking as needing manual review
            # In production, would parse HTML here
            result['extraction_status'] = 'manual_required'
            result['extraction_notes'] = f'Visit URL to extract: {url}'
            result['extraction_steps'] = (
                "1. Click link to open tax page\n"
                "2. Look for 'Total Due' amount\n"
                "3. Find property address\n"
                "4. Note previous year taxes if available"
            )
            
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            result['extraction_status'] = 'error'
            result['extraction_notes'] = str(e)
        
        return result
    
    def process_all(self, output_file: str = 'extraction_results.xlsx'):
        """Process all properties and save results"""
        results = []
        
        # Group by domain for summary
        domain_counts = {}
        
        for idx, row in self.df.iterrows():
            property_info = {
                'Property ID': row.get('Property ID'),
                'Property Name': row.get('Property Name'),
                'Jurisdiction': row.get('Jurisdiction'),
                'State': row.get('State'),
                'Tax Bill Link': row.get('Tax Bill Link'),
                'Existing Account Number': row.get('Acct Number'),
                'Existing Property Address': row.get('Property Address'),
            }
            
            if pd.notna(row.get('Tax Bill Link')):
                url = row['Tax Bill Link']
                domain = urlparse(url).netloc
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
                
                # Extract based on domain
                if domain == 'actweb.acttax.com':
                    extraction = self.extract_montgomery_county(url)
                    property_info.update(extraction)
                else:
                    property_info['extraction_status'] = 'unsupported_domain'
                    property_info['extraction_notes'] = f'Domain: {domain}'
            else:
                property_info['extraction_status'] = 'no_link'
            
            results.append(property_info)
        
        # Create results DataFrame
        results_df = pd.DataFrame(results)
        
        # Add extraction guide sheet
        extraction_guide = self.create_extraction_guide(domain_counts)
        
        # Save to Excel with multiple sheets
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            results_df.to_excel(writer, sheet_name='Extraction Results', index=False)
            extraction_guide.to_excel(writer, sheet_name='Domain Guide', index=False)
        
        logger.info(f"Results saved to {output_file}")
        
        # Print summary
        self.print_summary(results, domain_counts)
        
        return results
    
    def create_extraction_guide(self, domain_counts: dict) -> pd.DataFrame:
        """Create a guide for manual extraction by domain"""
        guide_data = []
        
        domain_instructions = {
            'actweb.acttax.com': {
                'name': 'Montgomery County',
                'steps': (
                    "1. Click the tax bill link\n"
                    "2. Page loads with property details\n"
                    "3. Find 'Total Due' or 'Amount Due' field\n"
                    "4. Copy property address from page\n"
                    "5. Look for 'Prior Year Tax' amount\n"
                    "6. Account number is in the URL (can= parameter)"
                ),
                'fields': 'Account Number, Property Address, Amount Due, Previous Year'
            },
            'www.hctax.net': {
                'name': 'Harris County',
                'steps': (
                    "1. Click the tax bill link\n"
                    "2. May need to search by account number\n"
                    "3. Find tax statement page\n"
                    "4. Extract total amount due\n"
                    "5. Copy property address\n"
                    "6. Note any payment deadlines"
                ),
                'fields': 'Property Address, Amount Due, Due Date'
            },
            'treasurer.maricopa.gov': {
                'name': 'Maricopa County',
                'steps': (
                    "1. Navigate to treasurer website\n"
                    "2. Search for property by parcel or address\n"
                    "3. View tax information\n"
                    "4. Extract current year taxes\n"
                    "5. Note payment status"
                ),
                'fields': 'Parcel Number, Property Address, Tax Amount'
            }
        }
        
        for domain, count in sorted(domain_counts.items(), key=lambda x: x[1], reverse=True):
            info = domain_instructions.get(domain, {
                'name': domain,
                'steps': 'Manual extraction required - inspect website',
                'fields': 'Varies by site'
            })
            
            guide_data.append({
                'Domain': domain,
                'County/Name': info.get('name', domain),
                'Property Count': count,
                'Extraction Steps': info.get('steps', ''),
                'Available Fields': info.get('fields', '')
            })
        
        return pd.DataFrame(guide_data)
    
    def print_summary(self, results: list, domain_counts: dict):
        """Print extraction summary"""
        print("\n" + "="*60)
        print("PROPERTY TAX EXTRACTION SUMMARY")
        print("="*60)
        print(f"Total Properties: {len(results)}")
        print(f"Properties with Tax Links: {sum(1 for r in results if r.get('Tax Bill Link'))}")
        
        print("\nTop Domains:")
        for domain, count in sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {domain}: {count} properties")
        
        print("\nExtraction Status:")
        status_counts = {}
        for r in results:
            status = r.get('extraction_status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        for status, count in sorted(status_counts.items()):
            print(f"  {status}: {count}")
        
        print("\nNext Steps:")
        print("1. Review 'extraction_results.xlsx' for property list")
        print("2. Use 'Domain Guide' sheet for manual extraction instructions")
        print("3. For automated extraction, consider using Selenium for JavaScript sites")
        print("4. Update Excel with extracted values")

def main():
    """Main execution"""
    logger.info("Starting tax extraction analysis")
    
    extractor = SimpleTaxExtractor('phase-two-taxes-8-17.xlsx')
    results = extractor.process_all('tax_extraction_analysis.xlsx')
    
    logger.info("Analysis complete")

if __name__ == "__main__":
    main()