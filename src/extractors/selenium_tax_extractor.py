#!/usr/bin/env python3
"""
Selenium-based Property Tax Information Extractor
Handles JavaScript-heavy tax websites with interactive elements
"""

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from urllib.parse import urlparse, parse_qs
import logging
import json
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import time
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('selenium_tax_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class TaxExtractionConfig:
    """Configuration for each tax website"""
    domain: str
    search_method: str  # 'direct_link', 'search_form', 'interactive'
    selectors: Dict[str, str]
    extraction_steps: List[str]
    wait_time: int = 10

class SeleniumTaxExtractor:
    """Selenium-based tax information extractor"""
    
    def __init__(self, headless: bool = True):
        self.driver = self._setup_driver(headless)
        self.wait = WebDriverWait(self.driver, 10)
        self.configs = self._load_site_configs()
    
    def _setup_driver(self, headless: bool) -> webdriver.Chrome:
        """Setup Chrome driver with appropriate options"""
        options = Options()
        if headless:
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Note: You'll need to have ChromeDriver installed
        # Install with: brew install chromedriver (Mac) or download from https://chromedriver.chromium.org/
        return webdriver.Chrome(options=options)
    
    def _load_site_configs(self) -> Dict[str, TaxExtractionConfig]:
        """Load configuration for different tax websites"""
        return {
            'actweb.acttax.com': TaxExtractionConfig(
                domain='actweb.acttax.com',
                search_method='direct_link',
                selectors={
                    'property_address': '//td[contains(text(),"Property Address")]/following-sibling::td',
                    'amount_due': '//td[contains(text(),"Total Due")]/following-sibling::td',
                    'previous_year': '//td[contains(text(),"Prior Year")]/following-sibling::td',
                    'account_number': '//td[contains(text(),"Account")]/following-sibling::td',
                },
                extraction_steps=[
                    'Navigate to URL',
                    'Wait for page load',
                    'Extract tax information from table'
                ]
            ),
            'www.hctax.net': TaxExtractionConfig(
                domain='www.hctax.net',
                search_method='search_form',
                selectors={
                    'search_button': '//a[contains(text(),"Search/Pay")]',
                    'account_input': '//input[@id="account"]',
                    'submit_button': '//button[@type="submit"]',
                    'property_address': '//div[@class="property-address"]',
                    'amount_due': '//span[@class="amount-due"]',
                },
                extraction_steps=[
                    'Navigate to main page',
                    'Click search button',
                    'Enter account number',
                    'Submit search',
                    'Extract results'
                ]
            ),
            'tax.aldine.k12.tx.us': TaxExtractionConfig(
                domain='tax.aldine.k12.tx.us',
                search_method='direct_link',
                selectors={
                    'property_info': '//div[@class="account-details"]',
                    'amount_due': '//span[contains(@class,"total-due")]',
                    'property_address': '//div[contains(@class,"address")]',
                },
                extraction_steps=[
                    'Navigate to account URL',
                    'Wait for details to load',
                    'Extract information'
                ]
            ),
        }
    
    def extract_montgomery_county(self, url: str, account_number: Optional[str] = None) -> Dict:
        """Extract tax info from Montgomery County (actweb.acttax.com)"""
        results = {
            'extraction_status': 'pending',
            'extraction_timestamp': datetime.now().isoformat()
        }
        
        try:
            logger.info(f"Navigating to Montgomery County URL: {url}")
            self.driver.get(url)
            
            # Wait for page to load
            time.sleep(3)
            
            # Try to extract account number from URL if not provided
            if not account_number:
                parsed = urlparse(url)
                params = parse_qs(parsed.query)
                account_number = params.get('can', [None])[0]
            
            if account_number:
                results['account_number'] = account_number
            
            # Look for common tax information patterns
            extraction_map = {
                'property_address': [
                    '//td[contains(text(),"Property Address")]/following-sibling::td',
                    '//td[contains(text(),"Situs")]/following-sibling::td',
                    '//span[@class="property-address"]'
                ],
                'amount_due': [
                    '//td[contains(text(),"Total Due")]/following-sibling::td',
                    '//td[contains(text(),"Total Amount Due")]/following-sibling::td',
                    '//td[contains(text(),"Balance Due")]/following-sibling::td'
                ],
                'previous_year_taxes': [
                    '//td[contains(text(),"Prior Year")]/following-sibling::td',
                    '//td[contains(text(),"Previous Year")]/following-sibling::td',
                    '//td[contains(text(),"2023 Tax")]/following-sibling::td'
                ]
            }
            
            for field, xpaths in extraction_map.items():
                for xpath in xpaths:
                    try:
                        element = self.driver.find_element(By.XPATH, xpath)
                        value = element.text.strip()
                        if field in ['amount_due', 'previous_year_taxes']:
                            value = self._parse_currency(value)
                        results[field] = value
                        logger.info(f"Found {field}: {value}")
                        break
                    except NoSuchElementException:
                        continue
            
            results['extraction_status'] = 'success'
            
        except Exception as e:
            logger.error(f"Error extracting Montgomery County data: {str(e)}")
            results['extraction_status'] = 'failed'
            results['extraction_notes'] = str(e)
        
        return results
    
    def extract_harris_county(self, url: str, account_number: Optional[str] = None) -> Dict:
        """Extract tax info from Harris County (www.hctax.net)"""
        results = {
            'extraction_status': 'pending',
            'extraction_timestamp': datetime.now().isoformat()
        }
        
        try:
            logger.info(f"Navigating to Harris County URL: {url}")
            self.driver.get(url)
            
            # Harris County requires interaction - this is a simplified example
            # Real implementation would need to handle their specific flow
            
            if 'TaxStatement' in url:
                # Direct link to tax statement
                time.sleep(3)
                
                # Try to extract information
                try:
                    address_elem = self.wait.until(
                        EC.presence_of_element_located((By.XPATH, '//div[contains(@class,"property")]'))
                    )
                    results['property_address'] = address_elem.text.strip()
                except TimeoutException:
                    logger.warning("Could not find property address")
                
                try:
                    amount_elem = self.driver.find_element(By.XPATH, '//span[contains(text(),"Total Due")]/following::span[1]')
                    results['amount_due'] = self._parse_currency(amount_elem.text)
                except NoSuchElementException:
                    logger.warning("Could not find amount due")
            
            else:
                # Need to search for property
                results['extraction_notes'] = "Requires manual search - account number needed"
                results['extraction_status'] = 'requires_manual'
                return results
            
            results['extraction_status'] = 'success'
            
        except Exception as e:
            logger.error(f"Error extracting Harris County data: {str(e)}")
            results['extraction_status'] = 'failed'
            results['extraction_notes'] = str(e)
        
        return results
    
    def _parse_currency(self, text: str) -> Optional[float]:
        """Parse currency text to float"""
        if not text:
            return None
        try:
            # Remove currency symbols, commas, and extra text
            cleaned = re.sub(r'[^0-9.]', '', text)
            return float(cleaned) if cleaned else None
        except (ValueError, AttributeError):
            return None
    
    def extract_from_url(self, url: str, property_info: Dict) -> Dict:
        """Extract tax information from any supported URL"""
        domain = urlparse(url).netloc
        
        # Merge property info with extraction results
        results = property_info.copy()
        
        if domain == 'actweb.acttax.com':
            extraction_results = self.extract_montgomery_county(
                url, 
                property_info.get('account_number')
            )
        elif domain == 'www.hctax.net':
            extraction_results = self.extract_harris_county(
                url,
                property_info.get('account_number')
            )
        else:
            extraction_results = {
                'extraction_status': 'unsupported',
                'extraction_notes': f'No extractor for domain: {domain}'
            }
        
        results.update(extraction_results)
        return results
    
    def process_excel_batch(self, excel_file: str, output_file: str, limit: Optional[int] = None):
        """Process properties from Excel file"""
        df = pd.read_excel(excel_file)
        
        # Limit processing if specified
        if limit:
            df = df.head(limit)
        
        results = []
        
        for idx, row in df.iterrows():
            if pd.isna(row.get('Tax Bill Link')):
                logger.warning(f"Skipping property without tax link: {row.get('Property Name')}")
                continue
            
            logger.info(f"Processing {idx+1}/{len(df)}: {row.get('Property Name')}")
            
            property_info = {
                'property_id': row.get('Property ID'),
                'property_name': row.get('Property Name'),
                'jurisdiction': row.get('Jurisdiction'),
                'state': row.get('State'),
                'tax_bill_link': row.get('Tax Bill Link'),
                'existing_account_number': row.get('Acct Number'),
                'existing_property_address': row.get('Property Address'),
            }
            
            extraction_results = self.extract_from_url(
                row['Tax Bill Link'],
                {'account_number': row.get('Acct Number')}
            )
            
            property_info.update(extraction_results)
            results.append(property_info)
            
            # Rate limiting
            time.sleep(2)
        
        # Save results
        results_df = pd.DataFrame(results)
        results_df.to_excel(output_file, index=False)
        logger.info(f"Results saved to {output_file}")
        
        # Generate summary
        self._generate_summary(results)
        
        return results
    
    def _generate_summary(self, results: List[Dict]):
        """Generate extraction summary"""
        status_counts = {}
        for result in results:
            status = result.get('extraction_status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print("\n" + "="*50)
        print("EXTRACTION SUMMARY")
        print("="*50)
        print(f"Total Properties Processed: {len(results)}")
        print("\nStatus Breakdown:")
        for status, count in sorted(status_counts.items()):
            percentage = (count / len(results)) * 100
            print(f"  {status}: {count} ({percentage:.1f}%)")
        
        success_count = status_counts.get('success', 0)
        if success_count > 0:
            print(f"\nSuccessfully extracted: {success_count} properties")
            
            # Count fields extracted
            field_counts = {}
            for result in results:
                if result.get('extraction_status') == 'success':
                    for field in ['property_address', 'account_number', 'amount_due', 'previous_year_taxes']:
                        if result.get(field):
                            field_counts[field] = field_counts.get(field, 0) + 1
            
            print("\nFields extracted:")
            for field, count in field_counts.items():
                print(f"  {field}: {count}")
    
    def close(self):
        """Close the browser driver"""
        if self.driver:
            self.driver.quit()

def main():
    """Main execution function"""
    extractor = SeleniumTaxExtractor(headless=False)  # Set to True for headless mode
    
    try:
        # Test with first 3 properties
        results = extractor.process_excel_batch(
            'phase-two-taxes-8-17.xlsx',
            'selenium_extraction_results.xlsx',
            limit=3
        )
        
    finally:
        extractor.close()

if __name__ == "__main__":
    main()