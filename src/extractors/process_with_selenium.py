#!/usr/bin/env python3
"""
Process Excel file with Selenium extractors for Maricopa and Harris counties
Integrates with existing tax extraction pipeline
"""

import pandas as pd
import json
import logging
from datetime import datetime
from urllib.parse import urlparse
import argparse
from typing import Dict, List, Optional
from .selenium_tax_extractors import UnifiedTaxExtractor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('selenium_processing.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ExcelTaxProcessor:
    """Process tax properties from Excel using Selenium extractors"""
    
    def __init__(self, input_file: str, output_file: str = None, headless: bool = True):
        self.input_file = input_file
        self.output_file = output_file or self._generate_output_filename()
        self.headless = headless
        self.extractor = UnifiedTaxExtractor(headless=headless)
    
    def _generate_output_filename(self) -> str:
        """Generate output filename based on input file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = self.input_file.replace('.xlsx', '').replace('.csv', '')
        return f"{base_name}_selenium_results_{timestamp}.xlsx"
    
    def load_data(self) -> pd.DataFrame:
        """Load data from Excel or CSV file"""
        if self.input_file.endswith('.xlsx'):
            df = pd.read_excel(self.input_file)
        elif self.input_file.endswith('.csv'):
            df = pd.read_csv(self.input_file)
        else:
            raise ValueError(f"Unsupported file format: {self.input_file}")
        
        logger.info(f"Loaded {len(df)} properties from {self.input_file}")
        return df
    
    def filter_selenium_counties(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter properties that need Selenium extraction (Maricopa and Harris)"""
        selenium_domains = ['treasurer.maricopa.gov', 'www.hctax.net']
        
        def needs_selenium(url):
            if pd.isna(url):
                return False
            domain = urlparse(str(url)).netloc
            return any(sd in domain for sd in selenium_domains)
        
        filtered_df = df[df['Tax Bill Link'].apply(needs_selenium)].copy()
        logger.info(f"Found {len(filtered_df)} properties requiring Selenium extraction")
        
        # Log breakdown by domain
        domain_counts = {}
        for url in filtered_df['Tax Bill Link']:
            if pd.notna(url):
                domain = urlparse(str(url)).netloc
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
        
        for domain, count in domain_counts.items():
            logger.info(f"  {domain}: {count} properties")
        
        return filtered_df
    
    def prepare_property_data(self, row: pd.Series) -> Dict:
        """Convert DataFrame row to property data dictionary"""
        return {
            'property_id': row.get('Property ID'),
            'property_name': row.get('Property Name'),
            'property_address': row.get('Property Address'),
            'jurisdiction': row.get('Jurisdiction'),
            'state': row.get('State'),
            'acct_number': row.get('Acct Number'),
            'parcel_number': row.get('Acct Number'),  # Use Acct Number as parcel for Maricopa
            'tax_bill_link': row.get('Tax Bill Link'),
            'parent_entity': row.get('Parent Entity'),
            'close_date': row.get('Close Date'),
            'property_type': row.get('Property Type')
        }
    
    def process(self, limit: Optional[int] = None, skip_existing: bool = True):
        """Process properties and extract tax information"""
        
        # Load data
        df = self.load_data()
        
        # Filter for Selenium counties
        selenium_df = self.filter_selenium_counties(df)
        
        if limit:
            selenium_df = selenium_df.head(limit)
            logger.info(f"Limited processing to {limit} properties")
        
        # Check for existing results if skip_existing
        existing_results = {}
        if skip_existing:
            try:
                existing_df = pd.read_excel(self.output_file)
                existing_results = {
                    row['property_id']: row.to_dict() 
                    for _, row in existing_df.iterrows() 
                    if row.get('extraction_status') == 'success'
                }
                logger.info(f"Found {len(existing_results)} existing successful extractions")
            except FileNotFoundError:
                pass
        
        # Process each property
        results = []
        skipped = 0
        processed = 0
        
        for idx, row in selenium_df.iterrows():
            property_id = row.get('Property ID')
            
            # Skip if already successfully processed
            if skip_existing and property_id in existing_results:
                results.append(existing_results[property_id])
                skipped += 1
                continue
            
            processed += 1
            property_data = self.prepare_property_data(row)
            
            logger.info(f"Processing {processed}/{len(selenium_df)}: {property_data.get('property_name')}")
            
            try:
                # Extract using Selenium
                result = self.extractor.extract(property_data)
                
                # Convert result to dictionary and merge with original data
                result_dict = result.__dict__
                result_dict.update(property_data)
                
                # Log result
                if result.extraction_status == 'success':
                    logger.info(f"  ✓ Success - Amount: ${result.amount_due:,.2f}" if result.amount_due else "  ✓ Success")
                elif result.extraction_status == 'partial':
                    logger.warning(f"  ⚠ Partial - {result.extraction_notes}")
                else:
                    logger.error(f"  ✗ Failed - {result.extraction_notes}")
                
                results.append(result_dict)
                
            except Exception as e:
                logger.error(f"  ✗ Error processing property: {e}")
                error_result = property_data.copy()
                error_result.update({
                    'extraction_status': 'error',
                    'extraction_notes': str(e),
                    'extraction_timestamp': datetime.now().isoformat()
                })
                results.append(error_result)
            
            # Save intermediate results every 10 properties
            if processed % 10 == 0:
                self.save_results(results, intermediate=True)
        
        # Final save
        self.save_results(results)
        
        # Print summary
        self.print_summary(results, skipped)
        
        # Cleanup
        self.extractor.cleanup()
        
        return results
    
    def save_results(self, results: List[Dict], intermediate: bool = False):
        """Save results to Excel file with multiple sheets"""
        
        df_results = pd.DataFrame(results)
        
        # Create summary statistics
        summary_data = {
            'Total Properties': len(results),
            'Successful': len([r for r in results if r.get('extraction_status') == 'success']),
            'Partial': len([r for r in results if r.get('extraction_status') == 'partial']),
            'Failed': len([r for r in results if r.get('extraction_status') == 'failed']),
            'Errors': len([r for r in results if r.get('extraction_status') == 'error']),
            'Total Amount Due': sum(r.get('amount_due', 0) for r in results if r.get('amount_due')),
            'Properties with Amount': len([r for r in results if r.get('amount_due')]),
            'Extraction Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        df_summary = pd.DataFrame([summary_data])
        
        # Create validation sheet - properties with issues
        validation_data = [
            r for r in results 
            if r.get('extraction_status') != 'success' or not r.get('amount_due')
        ]
        df_validation = pd.DataFrame(validation_data) if validation_data else pd.DataFrame()
        
        # Save to Excel with multiple sheets
        output_file = self.output_file
        if intermediate:
            output_file = output_file.replace('.xlsx', '_intermediate.xlsx')
        
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            df_results.to_excel(writer, sheet_name='Results', index=False)
            df_summary.to_excel(writer, sheet_name='Summary', index=False)
            if not df_validation.empty:
                df_validation.to_excel(writer, sheet_name='Validation', index=False)
        
        if not intermediate:
            logger.info(f"Results saved to: {output_file}")
            
            # Also save as JSON for programmatic access
            json_file = output_file.replace('.xlsx', '.json')
            with open(json_file, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            logger.info(f"JSON results saved to: {json_file}")
    
    def print_summary(self, results: List[Dict], skipped: int):
        """Print extraction summary"""
        
        print("\n" + "="*60)
        print("EXTRACTION SUMMARY")
        print("="*60)
        
        total = len(results)
        successful = len([r for r in results if r.get('extraction_status') == 'success'])
        partial = len([r for r in results if r.get('extraction_status') == 'partial'])
        failed = len([r for r in results if r.get('extraction_status') == 'failed'])
        errors = len([r for r in results if r.get('extraction_status') == 'error'])
        
        print(f"Total Properties Processed: {total}")
        if skipped:
            print(f"Skipped (already processed): {skipped}")
        print(f"Successful Extractions: {successful} ({successful/total*100:.1f}%)")
        print(f"Partial Extractions: {partial} ({partial/total*100:.1f}%)")
        print(f"Failed Extractions: {failed} ({failed/total*100:.1f}%)")
        if errors:
            print(f"Errors: {errors}")
        
        # Financial summary
        amounts = [r.get('amount_due', 0) for r in results if r.get('amount_due')]
        if amounts:
            print(f"\nFinancial Summary:")
            print(f"  Properties with amounts: {len(amounts)}")
            print(f"  Total Amount Due: ${sum(amounts):,.2f}")
            print(f"  Average Amount: ${sum(amounts)/len(amounts):,.2f}")
            print(f"  Min Amount: ${min(amounts):,.2f}")
            print(f"  Max Amount: ${max(amounts):,.2f}")
        
        # Domain breakdown
        domain_stats = {}
        for r in results:
            url = r.get('tax_bill_link')
            if url:
                domain = urlparse(url).netloc
                if domain not in domain_stats:
                    domain_stats[domain] = {'total': 0, 'success': 0, 'failed': 0}
                domain_stats[domain]['total'] += 1
                if r.get('extraction_status') == 'success':
                    domain_stats[domain]['success'] += 1
                elif r.get('extraction_status') in ['failed', 'error']:
                    domain_stats[domain]['failed'] += 1
        
        if domain_stats:
            print(f"\nDomain Breakdown:")
            for domain, stats in domain_stats.items():
                success_rate = (stats['success'] / stats['total'] * 100) if stats['total'] > 0 else 0
                print(f"  {domain}: {stats['success']}/{stats['total']} successful ({success_rate:.1f}%)")
        
        print("="*60)


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description='Process tax properties with Selenium extractors')
    parser.add_argument('input_file', help='Input Excel or CSV file')
    parser.add_argument('-o', '--output', help='Output file name')
    parser.add_argument('-l', '--limit', type=int, help='Limit number of properties to process')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    parser.add_argument('--no-skip', action='store_true', help='Don\'t skip already processed properties')
    
    args = parser.parse_args()
    
    # Create processor
    processor = ExcelTaxProcessor(
        input_file=args.input_file,
        output_file=args.output,
        headless=args.headless
    )
    
    # Process properties
    results = processor.process(
        limit=args.limit,
        skip_existing=not args.no_skip
    )
    
    print(f"\nProcessing complete. Results saved to: {processor.output_file}")


if __name__ == "__main__":
    # If no arguments provided, run with default test file
    import sys
    if len(sys.argv) == 1:
        # Test mode
        print("Running in test mode with sample data...")
        processor = ExcelTaxProcessor(
            input_file='phase-two-taxes-8-17.xlsx',
            output_file='selenium_extraction_results.xlsx',
            headless=False
        )
        processor.process(limit=5)  # Test with first 5 properties
    else:
        main()