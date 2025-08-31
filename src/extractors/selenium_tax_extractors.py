#!/usr/bin/env python3
"""
Comprehensive Selenium-based tax extractors for Maricopa County and Harris County
Handles JavaScript-heavy sites with proper waits and data validation
"""

import logging
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Optional, List, Tuple
from urllib.parse import urlparse, parse_qs

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException
)
from selenium.webdriver.common.keys import Keys
import pandas as pd
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('selenium_tax_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class TaxExtractionResult:
    """Standardized result structure for tax extraction"""
    property_id: Optional[str] = None
    property_name: Optional[str] = None
    property_address: Optional[str] = None
    owner_name: Optional[str] = None
    account_number: Optional[str] = None
    parcel_number: Optional[str] = None
    tax_year: Optional[str] = None
    amount_due: Optional[float] = None
    previous_year_taxes: Optional[float] = None
    total_assessed_value: Optional[float] = None
    due_date: Optional[str] = None
    extraction_status: str = 'pending'
    extraction_timestamp: Optional[str] = None
    extraction_notes: Optional[str] = None
    screenshot_path: Optional[str] = None
    raw_data: Optional[Dict] = None


class BaseSeleniumExtractor:
    """Base class for Selenium-based tax extractors"""
    
    def __init__(self, headless: bool = True, timeout: int = 20):
        self.headless = headless
        self.timeout = timeout
        self.driver = None
        self.wait = None
        self.setup_driver()
    
    def setup_driver(self):
        """Setup Chrome driver with optimized options"""
        options = Options()
        
        # Performance and stability options
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        # Anti-detection options
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # User agent to appear more legitimate
        options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        if self.headless:
            options.add_argument('--headless=new')  # Use new headless mode
        
        try:
            self.driver = webdriver.Chrome(options=options)
            self.wait = WebDriverWait(self.driver, self.timeout)
            # Set page load timeout
            self.driver.set_page_load_timeout(self.timeout)
            logger.info("Chrome driver initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Chrome driver: {e}")
            raise
    
    def parse_currency(self, text: str) -> Optional[float]:
        """Parse currency text to float, handling various formats"""
        if not text:
            return None
        
        try:
            # Remove all non-numeric characters except decimal point and minus
            cleaned = re.sub(r'[^\d.-]', '', text)
            # Handle cases with multiple decimals or formatting issues
            if cleaned.count('.') > 1:
                # Keep only last decimal point
                parts = cleaned.split('.')
                cleaned = '.'.join(parts[:-1]).replace('.', '') + '.' + parts[-1]
            
            value = float(cleaned) if cleaned else None
            # Validate reasonable tax amount range
            if value and (value < 0 or value > 1000000):
                logger.warning(f"Suspicious tax amount parsed: {value} from text: {text}")
            return value
        except (ValueError, AttributeError) as e:
            logger.debug(f"Could not parse currency from '{text}': {e}")
            return None
    
    def parse_date(self, text: str) -> Optional[str]:
        """Parse and standardize date formats"""
        if not text:
            return None
        
        # Common date patterns
        patterns = [
            r'\d{1,2}/\d{1,2}/\d{4}',
            r'\d{1,2}-\d{1,2}-\d{4}',
            r'\d{4}-\d{2}-\d{2}',
            r'[A-Za-z]+ \d{1,2}, \d{4}'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group()
        
        return text.strip() if text else None
    
    def take_screenshot(self, filename_prefix: str = "screenshot") -> str:
        """Take a screenshot for debugging"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{filename_prefix}_{timestamp}.png"
            self.driver.save_screenshot(filename)
            logger.info(f"Screenshot saved: {filename}")
            return filename
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            return None
    
    def safe_find_element(self, by: By, value: str, timeout: int = None) -> Optional:
        """Safely find an element with proper error handling"""
        try:
            timeout = timeout or self.timeout
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except TimeoutException:
            logger.debug(f"Element not found: {by}={value}")
            return None
        except Exception as e:
            logger.error(f"Error finding element {by}={value}: {e}")
            return None
    
    def safe_get_text(self, element) -> str:
        """Safely get text from an element"""
        try:
            if element:
                return element.text.strip()
        except StaleElementReferenceException:
            logger.debug("Stale element reference, retrying...")
            return ""
        except Exception as e:
            logger.debug(f"Error getting text: {e}")
            return ""
    
    def cleanup(self):
        """Clean up resources"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Driver closed successfully")
            except Exception as e:
                logger.error(f"Error closing driver: {e}")


class MaricopaCountySeleniumExtractor(BaseSeleniumExtractor):
    """Selenium extractor for Maricopa County Treasurer website"""
    
    BASE_URL = "https://treasurer.maricopa.gov/"
    
    def extract_parcel_from_data(self, property_data: Dict) -> Optional[str]:
        """Extract parcel number from property data"""
        # Try direct parcel number field
        parcel = property_data.get('parcel_number') or property_data.get('acct_number')
        
        if not parcel:
            # Try to extract from URL if available
            url = property_data.get('tax_bill_link', '')
            if 'Parcel=' in url:
                match = re.search(r'Parcel=([^&]+)', url)
                if match:
                    parcel = match.group(1)
        
        return parcel
    
    def split_parcel_number(self, parcel: str) -> Tuple[str, str, str, str]:
        """Split parcel number into components for Maricopa's form"""
        # Remove any spaces and convert to uppercase
        parcel = parcel.replace(' ', '').replace('-', '').upper()
        
        # Handle format: 214-05-025A or 21405025A
        # Expected format: XXX-XX-XXX[A-Z]
        
        if len(parcel) >= 8:
            book = parcel[0:3]
            map_num = parcel[3:5]
            # Check if there's a letter at position 8
            if len(parcel) > 8 and parcel[8].isalpha():
                item = parcel[5:8]
                split = parcel[8]
            else:
                # No letter, just numbers
                item = parcel[5:8] if len(parcel) >= 8 else parcel[5:]
                split = ''
            
            return book, map_num, item, split
        
        logger.warning(f"Invalid parcel format: {parcel}")
        return '', '', '', ''
    
    def extract(self, property_data: Dict) -> TaxExtractionResult:
        """Extract tax information for a Maricopa County property"""
        result = TaxExtractionResult(
            property_id=property_data.get('property_id'),
            property_name=property_data.get('property_name'),
            extraction_timestamp=datetime.now().isoformat()
        )
        
        try:
            # Get parcel number
            parcel = self.extract_parcel_from_data(property_data)
            if not parcel:
                result.extraction_status = 'failed'
                result.extraction_notes = 'No parcel number found'
                return result
            
            result.parcel_number = parcel
            logger.info(f"Extracting Maricopa County data for parcel: {parcel}")
            
            # Navigate to the website
            self.driver.get(self.BASE_URL)
            
            # Wait for the parcel input form to load
            try:
                # Wait for the first input field
                book_input = self.wait.until(
                    EC.presence_of_element_located((By.ID, "txtParcelNumBook"))
                )
                
                # Split the parcel number
                book, map_num, item, split = self.split_parcel_number(parcel)
                
                logger.info(f"Filling parcel form - Book: {book}, Map: {map_num}, Item: {item}, Split: {split}")
                
                # Fill in the form fields
                book_input.clear()
                book_input.send_keys(book)
                
                map_input = self.driver.find_element(By.ID, "txtParcelNumMap")
                map_input.clear()
                map_input.send_keys(map_num)
                
                item_input = self.driver.find_element(By.ID, "txtParcelNumItem")
                item_input.clear()
                item_input.send_keys(item)
                
                if split:
                    split_input = self.driver.find_element(By.ID, "txtParcelNumSplit")
                    split_input.clear()
                    split_input.send_keys(split)
                
                # Submit the form
                submit_button = self.driver.find_element(By.ID, "btnSubmit")
                submit_button.click()
                
                # Wait for navigation/results
                time.sleep(3)
                
                # Check if we got an error message
                error_elem = self.safe_find_element(By.CSS_SELECTOR, "#divError:not([style*='display: none'])", timeout=2)
                if error_elem and error_elem.is_displayed():
                    error_text = self.safe_get_text(error_elem)
                    if "not found" in error_text.lower():
                        result.extraction_status = 'failed'
                        result.extraction_notes = f'Parcel not found: {parcel}'
                        return result
                
                # Check if we're on a results page
                current_url = self.driver.current_url
                
                if '/Parcel/' in current_url:
                    # We're on the parcel detail page
                    logger.info(f"Navigated to parcel page: {current_url}")
                    
                    # Extract tax information
                    result = self.extract_parcel_details(result)
                    
                else:
                    # Try to find and click on the parcel link if it appears in search results
                    parcel_link = self.safe_find_element(By.PARTIAL_LINK_TEXT, parcel.replace('-', ''), timeout=5)
                    if parcel_link:
                        parcel_link.click()
                        time.sleep(3)
                        result = self.extract_parcel_details(result)
                    else:
                        result.extraction_status = 'failed'
                        result.extraction_notes = 'Could not navigate to parcel details'
                
            except TimeoutException:
                result.extraction_status = 'failed'
                result.extraction_notes = 'Parcel form not found - site may have changed'
                result.screenshot_path = self.take_screenshot('maricopa_error')
            
        except Exception as e:
            logger.error(f"Error extracting Maricopa County data: {e}")
            result.extraction_status = 'failed'
            result.extraction_notes = str(e)
            result.screenshot_path = self.take_screenshot('maricopa_error')
        
        return result
    
    def extract_parcel_details(self, result: TaxExtractionResult) -> TaxExtractionResult:
        """Extract details from the parcel detail page"""
        try:
            # Look for tax summary information
            # Common patterns on Maricopa County site
            
            # Try to find owner name
            owner_elem = self.safe_find_element(By.XPATH, "//td[contains(text(),'Owner')]/following-sibling::td", timeout=5)
            if owner_elem:
                result.owner_name = self.safe_get_text(owner_elem)
            
            # Try to find property address
            address_patterns = [
                "//td[contains(text(),'Situs')]/following-sibling::td",
                "//td[contains(text(),'Property Address')]/following-sibling::td",
                "//td[contains(text(),'Location')]/following-sibling::td"
            ]
            
            for pattern in address_patterns:
                addr_elem = self.safe_find_element(By.XPATH, pattern, timeout=2)
                if addr_elem:
                    result.property_address = self.safe_get_text(addr_elem)
                    break
            
            # Extract tax amounts
            # Look for "Total Due" or similar
            amount_patterns = [
                ("//td[contains(text(),'Total Due')]/following-sibling::td", "amount_due"),
                ("//td[contains(text(),'Total Amount Due')]/following-sibling::td", "amount_due"),
                ("//td[contains(text(),'Current Due')]/following-sibling::td", "amount_due"),
                ("//td[contains(text(),'Balance Due')]/following-sibling::td", "amount_due"),
                ("//span[contains(@class,'total-due')]", "amount_due"),
                ("//td[contains(text(),'2024')]/following-sibling::td[contains(text(),'$')]", "amount_due"),
                ("//td[contains(text(),'2023')]/following-sibling::td[contains(text(),'$')]", "previous_year_taxes"),
                ("//td[contains(text(),'Prior Year')]/following-sibling::td", "previous_year_taxes")
            ]
            
            for xpath, field in amount_patterns:
                elem = self.safe_find_element(By.XPATH, xpath, timeout=2)
                if elem:
                    text = self.safe_get_text(elem)
                    value = self.parse_currency(text)
                    if value is not None:
                        setattr(result, field, value)
                        logger.info(f"Found {field}: ${value}")
            
            # Try to find tax year
            year_elem = self.safe_find_element(By.XPATH, "//td[contains(text(),'Tax Year')]/following-sibling::td", timeout=2)
            if year_elem:
                result.tax_year = self.safe_get_text(year_elem)
            
            # If we still don't have amounts, look for any dollar amounts on the page
            if result.amount_due is None:
                dollar_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(),'$')]")
                for elem in dollar_elements:
                    text = self.safe_get_text(elem)
                    if text and len(text) < 50:  # Avoid long text blocks
                        value = self.parse_currency(text)
                        if value and value > 100 and value < 100000:  # Reasonable tax range
                            if result.amount_due is None:
                                result.amount_due = value
                                logger.info(f"Found potential amount due: ${value}")
                                break
            
            # Determine extraction status
            if result.amount_due is not None or result.previous_year_taxes is not None:
                result.extraction_status = 'success'
            else:
                result.extraction_status = 'partial'
                result.extraction_notes = 'Some tax information may be missing'
                result.screenshot_path = self.take_screenshot('maricopa_partial')
            
        except Exception as e:
            logger.error(f"Error extracting parcel details: {e}")
            result.extraction_status = 'failed'
            result.extraction_notes = str(e)
        
        return result


class HarrisCountySeleniumExtractor(BaseSeleniumExtractor):
    """Selenium extractor for Harris County tax website"""
    
    BASE_URL = "https://www.hctax.net"
    
    def extract(self, property_data: Dict) -> TaxExtractionResult:
        """Extract tax information for a Harris County property"""
        result = TaxExtractionResult(
            property_id=property_data.get('property_id'),
            property_name=property_data.get('property_name'),
            extraction_timestamp=datetime.now().isoformat()
        )
        
        try:
            url = property_data.get('tax_bill_link')
            if not url:
                result.extraction_status = 'failed'
                result.extraction_notes = 'No tax bill link provided'
                return result
            
            logger.info(f"Extracting Harris County data from: {url}")
            
            # Navigate to the tax statement URL
            self.driver.get(url)
            
            # Wait for the page to load - Harris County uses JavaScript heavily
            time.sleep(5)  # Initial wait for JavaScript
            
            # Check if we need to handle any popups or alerts
            try:
                alert = self.driver.switch_to.alert
                alert.accept()
            except:
                pass  # No alert present
            
            # Extract account number from URL if possible
            parsed_url = urlparse(url)
            params = parse_qs(parsed_url.query)
            if 'account' in params:
                result.account_number = params['account'][0]
            
            # Look for the main content area
            # Harris County typically shows tax information in a specific format
            
            # Extract property address
            address_patterns = [
                "//div[contains(@class,'property-address')]",
                "//td[contains(text(),'Property Address')]/following-sibling::td",
                "//span[contains(@class,'address')]",
                "//div[contains(text(),'Property Location')]/following-sibling::div",
                "//label[contains(text(),'Property Address')]/following-sibling::*"
            ]
            
            for pattern in address_patterns:
                addr_elem = self.safe_find_element(By.XPATH, pattern, timeout=3)
                if addr_elem:
                    result.property_address = self.safe_get_text(addr_elem)
                    logger.info(f"Found property address: {result.property_address}")
                    break
            
            # Extract owner name
            owner_patterns = [
                "//div[contains(@class,'owner-name')]",
                "//td[contains(text(),'Owner')]/following-sibling::td",
                "//span[contains(@class,'owner')]",
                "//label[contains(text(),'Owner Name')]/following-sibling::*"
            ]
            
            for pattern in owner_patterns:
                owner_elem = self.safe_find_element(By.XPATH, pattern, timeout=2)
                if owner_elem:
                    result.owner_name = self.safe_get_text(owner_elem)
                    break
            
            # Extract tax amounts - Harris County specific patterns
            amount_patterns = [
                ("//td[contains(text(),'Final Total Amount Due')]/following-sibling::td", "amount_due"),
                ("//span[contains(text(),'Final Total Amount Due')]/following::span[contains(text(),'$')]", "amount_due"),
                ("//div[contains(text(),'Total Amount Due')]/following-sibling::div[contains(text(),'$')]", "amount_due"),
                ("//label[contains(text(),'Total Due')]/following-sibling::*", "amount_due"),
                ("//td[contains(text(),'Total Due')]/following-sibling::td", "amount_due"),
                ("//span[contains(@class,'amount-due')]", "amount_due"),
                ("//div[contains(@class,'total-due')]", "amount_due"),
                ("//td[contains(text(),'Current Amount Due')]/following-sibling::td", "amount_due"),
                ("//td[contains(text(),'2023 Tax')]/following-sibling::td", "previous_year_taxes"),
                ("//td[contains(text(),'Prior Year')]/following-sibling::td", "previous_year_taxes")
            ]
            
            for xpath, field in amount_patterns:
                elem = self.safe_find_element(By.XPATH, xpath, timeout=3)
                if elem:
                    text = self.safe_get_text(elem)
                    value = self.parse_currency(text)
                    if value is not None:
                        setattr(result, field, value)
                        logger.info(f"Found {field}: ${value}")
            
            # If no amounts found, try a broader search
            if result.amount_due is None:
                # Look for any element containing "Final Total" and a dollar amount
                final_total_elems = self.driver.find_elements(By.XPATH, "//*[contains(text(),'Final Total')]")
                for elem in final_total_elems:
                    parent = elem.find_element(By.XPATH, "..")
                    text = self.safe_get_text(parent)
                    value = self.parse_currency(text)
                    if value and value > 100:
                        result.amount_due = value
                        logger.info(f"Found amount due from Final Total section: ${value}")
                        break
            
            # Still no amount? Look for any reasonable dollar amounts
            if result.amount_due is None:
                dollar_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(),'$')]")
                amounts_found = []
                for elem in dollar_elements:
                    text = self.safe_get_text(elem)
                    if text and len(text) < 50:
                        value = self.parse_currency(text)
                        if value and 500 < value < 50000:  # Reasonable property tax range
                            amounts_found.append(value)
                
                if amounts_found:
                    # Take the largest amount as it's likely the total
                    result.amount_due = max(amounts_found)
                    logger.info(f"Found potential amount due: ${result.amount_due}")
            
            # Extract tax year
            year_patterns = [
                "//td[contains(text(),'Tax Year')]/following-sibling::td",
                "//span[contains(text(),'Tax Year')]/following-sibling::span",
                "//div[contains(text(),'2024')]",
                "//div[contains(text(),'2023')]"
            ]
            
            for pattern in year_patterns:
                year_elem = self.safe_find_element(By.XPATH, pattern, timeout=2)
                if year_elem:
                    text = self.safe_get_text(year_elem)
                    year_match = re.search(r'20\d{2}', text)
                    if year_match:
                        result.tax_year = year_match.group()
                        break
            
            # Extract due date
            due_date_patterns = [
                "//td[contains(text(),'Due Date')]/following-sibling::td",
                "//span[contains(text(),'Due')]/following-sibling::span",
                "//div[contains(@class,'due-date')]"
            ]
            
            for pattern in due_date_patterns:
                date_elem = self.safe_find_element(By.XPATH, pattern, timeout=2)
                if date_elem:
                    result.due_date = self.parse_date(self.safe_get_text(date_elem))
                    break
            
            # Determine extraction status
            if result.amount_due is not None:
                result.extraction_status = 'success'
            elif result.property_address or result.owner_name:
                result.extraction_status = 'partial'
                result.extraction_notes = 'Tax amount not found but property information extracted'
                result.screenshot_path = self.take_screenshot('harris_partial')
            else:
                result.extraction_status = 'failed'
                result.extraction_notes = 'Could not extract tax information'
                result.screenshot_path = self.take_screenshot('harris_failed')
            
            # Store page source for debugging if extraction failed
            if result.extraction_status != 'success':
                page_source = self.driver.page_source
                # Store first 1000 chars of page source for debugging
                result.raw_data = {'page_preview': page_source[:1000]}
            
        except TimeoutException:
            logger.error("Timeout while loading Harris County page")
            result.extraction_status = 'failed'
            result.extraction_notes = 'Page load timeout'
            result.screenshot_path = self.take_screenshot('harris_timeout')
        except Exception as e:
            logger.error(f"Error extracting Harris County data: {e}")
            result.extraction_status = 'failed'
            result.extraction_notes = str(e)
            result.screenshot_path = self.take_screenshot('harris_error')
        
        return result


class UnifiedTaxExtractor:
    """Unified extractor that routes to appropriate county extractor"""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.extractors = {}
    
    def get_extractor(self, domain: str) -> Optional[BaseSeleniumExtractor]:
        """Get or create appropriate extractor for domain"""
        if domain not in self.extractors:
            if 'treasurer.maricopa.gov' in domain:
                self.extractors[domain] = MaricopaCountySeleniumExtractor(self.headless)
            elif 'hctax.net' in domain:
                self.extractors[domain] = HarrisCountySeleniumExtractor(self.headless)
            else:
                logger.warning(f"No extractor available for domain: {domain}")
                return None
        
        return self.extractors.get(domain)
    
    def extract(self, property_data: Dict) -> TaxExtractionResult:
        """Extract tax information based on the URL domain"""
        url = property_data.get('tax_bill_link')
        if not url:
            return TaxExtractionResult(
                property_id=property_data.get('property_id'),
                extraction_status='failed',
                extraction_notes='No tax bill link provided'
            )
        
        domain = urlparse(url).netloc
        extractor = self.get_extractor(domain)
        
        if not extractor:
            return TaxExtractionResult(
                property_id=property_data.get('property_id'),
                extraction_status='unsupported',
                extraction_notes=f'No extractor for domain: {domain}'
            )
        
        return extractor.extract(property_data)
    
    def process_batch(self, properties: List[Dict], output_file: str = None) -> List[Dict]:
        """Process a batch of properties"""
        results = []
        
        for i, property_data in enumerate(properties, 1):
            logger.info(f"Processing property {i}/{len(properties)}: {property_data.get('property_name')}")
            
            result = self.extract(property_data)
            
            # Merge with original property data
            result_dict = asdict(result)
            result_dict.update(property_data)
            results.append(result_dict)
            
            # Log status
            if result.extraction_status == 'success':
                logger.info(f"✓ Successfully extracted: ${result.amount_due}")
            elif result.extraction_status == 'partial':
                logger.warning(f"⚠ Partial extraction: {result.extraction_notes}")
            else:
                logger.error(f"✗ Failed extraction: {result.extraction_notes}")
            
            # Rate limiting
            time.sleep(2)
        
        # Save results if output file specified
        if output_file:
            if output_file.endswith('.csv'):
                pd.DataFrame(results).to_csv(output_file, index=False)
            elif output_file.endswith('.json'):
                with open(output_file, 'w') as f:
                    json.dump(results, f, indent=2, default=str)
            elif output_file.endswith('.xlsx'):
                pd.DataFrame(results).to_excel(output_file, index=False)
            
            logger.info(f"Results saved to: {output_file}")
        
        return results
    
    def cleanup(self):
        """Clean up all extractors"""
        for extractor in self.extractors.values():
            extractor.cleanup()


def main():
    """Main execution for testing"""
    
    # Test data for Maricopa and Harris counties
    test_properties = [
        {
            'property_id': '0647afda-e37a-4044-83df-89b1a44a6f35',
            'property_name': '17017 N CAVE CREEK ROAD PHOENIX, AZ',
            'acct_number': '214-05-025A',
            'tax_bill_link': 'https://treasurer.maricopa.gov/'
        },
        {
            'property_id': '227cece5-26e4-4f96-a81c-4b2eec6d7ce5',
            'property_name': '2404 E BELL ROAD PHOENIX, AZ',
            'acct_number': '214-05-025B',
            'tax_bill_link': 'https://treasurer.maricopa.gov/'
        },
        {
            'property_id': '5b934179-a5c0-48f3-84a8-7ef846c6fb6f',
            'property_name': 'BCS Auto Properties LLC - 1204 Federal Rd, Houston',
            'tax_bill_link': 'https://www.hctax.net/property/TaxStatement?account=H121C5X068PKoeFCzGBdue+rsqT9Ldjc83+oKTkml9U='
        }
    ]
    
    # Initialize extractor
    extractor = UnifiedTaxExtractor(headless=False)  # Set to True for production
    
    try:
        # Process test properties
        results = extractor.process_batch(
            test_properties,
            output_file='selenium_test_results.json'
        )
        
        # Print summary
        print("\n" + "="*50)
        print("EXTRACTION SUMMARY")
        print("="*50)
        
        for result in results:
            print(f"\nProperty: {result.get('property_name')}")
            print(f"Status: {result.get('extraction_status')}")
            if result.get('amount_due'):
                print(f"Amount Due: ${result.get('amount_due'):,.2f}")
            if result.get('property_address'):
                print(f"Address: {result.get('property_address')}")
            if result.get('extraction_notes'):
                print(f"Notes: {result.get('extraction_notes')}")
        
    finally:
        extractor.cleanup()


if __name__ == "__main__":
    main()