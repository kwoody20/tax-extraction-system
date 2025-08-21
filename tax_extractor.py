#!/usr/bin/env python3
"""
Property Tax Information Extractor
Automates extraction of tax information from various county tax websites
"""

import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
import logging
import json
from typing import Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tax_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class PropertyTaxInfo:
    """Data structure for property tax information"""
    property_id: str
    property_name: str
    property_address: Optional[str] = None
    account_number: Optional[str] = None
    tax_id: Optional[str] = None
    amount_due: Optional[float] = None
    previous_year_taxes: Optional[float] = None
    next_due_date: Optional[str] = None
    extraction_timestamp: Optional[str] = None
    extraction_status: str = "pending"
    extraction_notes: Optional[str] = None

class BaseTaxScraper:
    """Base class for tax website scrapers"""
    
    def __init__(self, domain: str):
        self.domain = domain
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def extract(self, url: str, **kwargs) -> PropertyTaxInfo:
        """Override this method in subclasses"""
        raise NotImplementedError("Subclasses must implement extract method")
    
    def parse_currency(self, text: str) -> Optional[float]:
        """Parse currency text to float"""
        if not text:
            return None
        try:
            # Remove common currency symbols and commas
            cleaned = text.replace('$', '').replace(',', '').strip()
            return float(cleaned)
        except (ValueError, AttributeError):
            return None

class MontgomeryCountyScraper(BaseTaxScraper):
    """Scraper for actweb.acttax.com (Montgomery County)"""
    
    def extract(self, url: str, property_info: PropertyTaxInfo) -> PropertyTaxInfo:
        """Extract tax information from Montgomery County website"""
        try:
            # Parse account number from URL if available
            parsed_url = urlparse(url)
            params = parse_qs(parsed_url.query)
            account_num = params.get('can', [None])[0]
            
            if account_num:
                property_info.account_number = account_num
                logger.info(f"Found account number: {account_num}")
            
            # Make request to get property details
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for tax information in common patterns
            # These selectors will need adjustment based on actual HTML structure
            tax_info_patterns = [
                ('td:contains("Total Amount Due")', 'amount_due'),
                ('td:contains("Property Address")', 'property_address'),
                ('td:contains("Previous Year")', 'previous_year_taxes'),
            ]
            
            for pattern, field in tax_info_patterns:
                # This is a simplified example - actual implementation would need proper selectors
                element = soup.select_one(pattern)
                if element:
                    value = element.find_next_sibling().text.strip()
                    if field in ['amount_due', 'previous_year_taxes']:
                        value = self.parse_currency(value)
                    setattr(property_info, field, value)
            
            property_info.extraction_status = "success"
            property_info.extraction_timestamp = datetime.now().isoformat()
            
        except Exception as e:
            logger.error(f"Error extracting from Montgomery County: {str(e)}")
            property_info.extraction_status = "failed"
            property_info.extraction_notes = str(e)
        
        return property_info

class HarrisCountyScraper(BaseTaxScraper):
    """Scraper for www.hctax.net (Harris County)"""
    
    def extract(self, url: str, property_info: PropertyTaxInfo) -> PropertyTaxInfo:
        """Extract tax information from Harris County website"""
        try:
            # Harris County uses encrypted account parameters
            # Would need to handle their specific search/authentication flow
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Placeholder for actual extraction logic
            property_info.extraction_status = "requires_manual"
            property_info.extraction_notes = "Harris County requires interactive session"
            property_info.extraction_timestamp = datetime.now().isoformat()
            
        except Exception as e:
            logger.error(f"Error extracting from Harris County: {str(e)}")
            property_info.extraction_status = "failed"
            property_info.extraction_notes = str(e)
        
        return property_info

class TaxExtractor:
    """Main tax extraction orchestrator"""
    
    def __init__(self, excel_file: str):
        self.excel_file = excel_file
        self.df = pd.read_excel(excel_file)
        self.scrapers = self._initialize_scrapers()
        self.results = []
    
    def _initialize_scrapers(self) -> Dict[str, BaseTaxScraper]:
        """Initialize scrapers for different domains"""
        return {
            'actweb.acttax.com': MontgomeryCountyScraper('actweb.acttax.com'),
            'www.hctax.net': HarrisCountyScraper('www.hctax.net'),
        }
    
    def extract_all(self, limit: Optional[int] = None):
        """Extract tax information for all properties"""
        properties_to_process = self.df.head(limit) if limit else self.df
        
        for idx, row in properties_to_process.iterrows():
            if pd.isna(row.get('Tax Bill Link')):
                logger.warning(f"No tax link for property: {row.get('Property Name')}")
                continue
            
            property_info = PropertyTaxInfo(
                property_id=row.get('Property ID', ''),
                property_name=row.get('Property Name', ''),
                property_address=row.get('Property Address'),
                account_number=row.get('Acct Number'),
            )
            
            url = row['Tax Bill Link']
            domain = urlparse(url).netloc
            
            if domain in self.scrapers:
                logger.info(f"Processing {property_info.property_name} using {domain} scraper")
                scraper = self.scrapers[domain]
                property_info = scraper.extract(url, property_info)
            else:
                logger.warning(f"No scraper available for domain: {domain}")
                property_info.extraction_status = "no_scraper"
                property_info.extraction_notes = f"No scraper for {domain}"
            
            self.results.append(property_info)
            
            # Rate limiting
            time.sleep(1)
    
    def save_results(self, output_file: str = 'extraction_results.xlsx'):
        """Save extraction results to Excel"""
        if not self.results:
            logger.warning("No results to save")
            return
        
        # Convert results to DataFrame
        results_data = []
        for result in self.results:
            results_data.append({
                'Property ID': result.property_id,
                'Property Name': result.property_name,
                'Property Address': result.property_address,
                'Account Number': result.account_number,
                'Tax ID': result.tax_id,
                'Amount Due': result.amount_due,
                'Previous Year Taxes': result.previous_year_taxes,
                'Next Due Date': result.next_due_date,
                'Extraction Status': result.extraction_status,
                'Extraction Timestamp': result.extraction_timestamp,
                'Extraction Notes': result.extraction_notes,
            })
        
        results_df = pd.DataFrame(results_data)
        
        # Merge with original data
        merged_df = self.df.merge(
            results_df[['Property ID', 'Property Address', 'Account Number', 
                       'Amount Due', 'Previous Year Taxes', 'Next Due Date',
                       'Extraction Status', 'Extraction Timestamp', 'Extraction Notes']],
            on='Property ID',
            how='left',
            suffixes=('_original', '_extracted')
        )
        
        # Save to Excel
        merged_df.to_excel(output_file, index=False)
        logger.info(f"Results saved to {output_file}")
    
    def generate_extraction_report(self):
        """Generate summary report of extraction results"""
        if not self.results:
            return "No extraction results available"
        
        status_counts = {}
        for result in self.results:
            status = result.extraction_status
            status_counts[status] = status_counts.get(status, 0) + 1
        
        report = f"""
Extraction Summary Report
========================
Total Properties Processed: {len(self.results)}

Status Breakdown:
"""
        for status, count in sorted(status_counts.items()):
            report += f"  {status}: {count}\n"
        
        success_rate = status_counts.get('success', 0) / len(self.results) * 100
        report += f"\nSuccess Rate: {success_rate:.1f}%"
        
        return report

def main():
    """Main execution function"""
    logger.info("Starting property tax extraction")
    
    # Initialize extractor
    extractor = TaxExtractor('phase-two-taxes-8-17.xlsx')
    
    # Test with first 5 properties
    logger.info("Running test extraction on first 5 properties")
    extractor.extract_all(limit=5)
    
    # Save results
    extractor.save_results('test_extraction_results.xlsx')
    
    # Print report
    report = extractor.generate_extraction_report()
    print(report)
    logger.info("Extraction complete")

if __name__ == "__main__":
    main()