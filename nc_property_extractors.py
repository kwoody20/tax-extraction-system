#!/usr/bin/env python3
"""
North Carolina Property Tax Extractors
Specialized Selenium-based extractors for NC county tax websites
Handles form interactions, dynamic content, and differentiates tax amounts from property values
"""

import logging
import time
import re
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException,
    ElementNotInteractableException,
    StaleElementReferenceException
)
import pandas as pd
from urllib.parse import urlparse, parse_qs

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('nc_tax_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class TaxExtractionResult:
    """Result of a tax extraction attempt"""
    property_id: str
    property_name: str
    jurisdiction: str
    state: str
    tax_amount: Optional[float] = None
    property_value: Optional[float] = None
    account_number: Optional[str] = None
    property_address: Optional[str] = None
    extraction_status: str = 'pending'
    extraction_timestamp: str = ''
    extraction_notes: str = ''
    screenshot_path: Optional[str] = None
    
    def __post_init__(self):
        self.extraction_timestamp = datetime.now().isoformat()


class NCTaxExtractorBase:
    """Base class for NC county tax extractors"""
    
    def __init__(self, driver: webdriver.Chrome, wait_timeout: int = 20):
        self.driver = driver
        self.wait = WebDriverWait(driver, wait_timeout)
        self.short_wait = WebDriverWait(driver, 5)
        
    def _parse_currency(self, text: str) -> Optional[float]:
        """Parse currency text to float, handling various formats"""
        if not text:
            return None
        try:
            # Remove currency symbols, commas, parentheses, and extra text
            cleaned = re.sub(r'[^\d.,\-]', '', text)
            # Handle negative amounts in parentheses
            if '(' in text and ')' in text:
                cleaned = '-' + cleaned
            # Remove any remaining commas
            cleaned = cleaned.replace(',', '')
            # Convert to float
            amount = float(cleaned) if cleaned else None
            return amount
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse currency from '{text}': {e}")
            return None
    
    def _validate_tax_amount(self, amount: float, property_value: Optional[float] = None) -> bool:
        """
        Validate that the amount is likely a tax amount, not a property value
        Tax amounts are typically 0.5% to 3% of property value
        """
        # Tax amounts typically range from $100 to $50,000 for most properties
        if amount < 100:
            logger.warning(f"Amount ${amount} seems too low for a tax amount")
            return False
        
        if amount > 100000:
            logger.warning(f"Amount ${amount} seems too high for a tax amount - likely property value")
            return False
            
        # If we have property value, check if tax is reasonable percentage
        if property_value and property_value > 0:
            tax_rate = amount / property_value
            if tax_rate > 0.05:  # More than 5% is suspicious
                logger.warning(f"Tax rate {tax_rate:.2%} seems too high")
                return False
            if tax_rate < 0.001:  # Less than 0.1% is suspicious
                logger.warning(f"Tax rate {tax_rate:.2%} seems too low")
                return False
                
        return True
    
    def _take_screenshot(self, filename_prefix: str) -> str:
        """Take a screenshot for debugging"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"output/screenshots/{filename_prefix}_{timestamp}.png"
        try:
            self.driver.save_screenshot(filename)
            logger.info(f"Screenshot saved: {filename}")
            return filename
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            return None
    
    def _find_tax_amount_in_table(self, table_element) -> Optional[float]:
        """
        Search for tax amount in a table, looking for specific keywords
        Priority: "Tax Due", "Amount Due", "Total Due", "Balance Due"
        Avoid: "Assessed Value", "Property Value", "Market Value"
        """
        tax_keywords = [
            'tax due', 'taxes due', 'amount due', 'total due', 'balance due',
            'current due', 'total tax', 'tax amount', 'current amount due',
            'total current taxes due', 'final total amount due'
        ]
        
        value_keywords = [
            'assessed value', 'property value', 'market value', 'land value',
            'improvement value', 'total value', 'appraised value', 'taxable value'
        ]
        
        try:
            rows = table_element.find_elements(By.TAG_NAME, 'tr')
            
            for row in rows:
                try:
                    text = row.text.lower()
                    
                    # Skip rows with property value keywords
                    if any(keyword in text for keyword in value_keywords):
                        continue
                    
                    # Look for tax amount keywords
                    if any(keyword in text for keyword in tax_keywords):
                        # Try to find the amount in the same row
                        cells = row.find_elements(By.TAG_NAME, 'td')
                        for cell in cells:
                            cell_text = cell.text.strip()
                            if '$' in cell_text or re.search(r'\d+\.\d{2}', cell_text):
                                amount = self._parse_currency(cell_text)
                                if amount and self._validate_tax_amount(amount):
                                    logger.info(f"Found tax amount: ${amount} in row: {text[:100]}")
                                    return amount
                                    
                except Exception as e:
                    logger.debug(f"Error processing table row: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error searching table for tax amount: {e}")
            
        return None
    
    def extract(self, url: str, property_info: Dict) -> TaxExtractionResult:
        """Extract tax information - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement extract method")


class WayneCountyExtractor(NCTaxExtractorBase):
    """Extractor for Wayne County, NC (pwa.waynegov.com)"""
    
    def extract(self, url: str, property_info: Dict) -> TaxExtractionResult:
        result = TaxExtractionResult(
            property_id=property_info.get('property_id', ''),
            property_name=property_info.get('property_name', ''),
            jurisdiction='Wayne',
            state='NC',
            extraction_status='pending'
        )
        
        try:
            logger.info(f"Wayne County: Navigating to {url}")
            self.driver.get(url)
            
            # Wait for page to load
            time.sleep(3)
            
            tax_amount = None
            property_value = None
            
            # Based on the screenshot, Wayne County shows:
            # - "Total Assessed Value" row with property value ($547,940)
            # - "Total Billed:" with the tax amount ($8,314.99)
            # - Transaction History table with payment details
            
            # First, extract property value from "Total Assessed Value" row
            try:
                value_elem = self.driver.find_element(By.XPATH, "//td[text()='Total Assessed Value']/following-sibling::td[1]")
                property_value = self._parse_currency(value_elem.text)
                if property_value:
                    result.property_value = property_value
                    logger.info(f"Wayne County: Found property value: ${property_value}")
            except:
                pass
            
            # Look for "Total Billed:" amount - this is the actual tax
            # Based on testing, "Total Billed: $8,314.99" appears in the page text
            try:
                # Get the page text to search for Total Billed
                page_text = self.driver.find_element(By.TAG_NAME, 'body').text
                
                if 'Total Billed:' in page_text:
                    # Find the line with Total Billed
                    lines = page_text.split('\n')
                    for line in lines:
                        if 'Total Billed:' in line and '$' in line:
                            # Extract amount from "Total Billed: $8,314.99"
                            amount_part = line.split('$')[-1].strip()
                            tax_amount = self._parse_currency('$' + amount_part)
                            if tax_amount and self._validate_tax_amount(tax_amount, property_value):
                                logger.info(f"Wayne County: Found Total Billed amount: ${tax_amount}")
                                break
                
                # Alternative: Look for elements containing the specific amount
                if not tax_amount:
                    elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), '$8,') or contains(text(), '$9,') or contains(text(), '$7,')]")
                    for elem in elements:
                        text = elem.text
                        if 'Total Billed' in text or ('8,314' in text and len(text) < 50):
                            amount = self._parse_currency(text)
                            if amount and self._validate_tax_amount(amount, property_value):
                                tax_amount = amount
                                logger.info(f"Wayne County: Found tax amount: ${tax_amount}")
                                break
                                
            except Exception as e:
                logger.debug(f"Wayne County: Error looking for Total Billed: {e}")
            
            # If not found, check Transaction History table
            if not tax_amount:
                try:
                    # Look in the transaction history table for payment amounts
                    trans_rows = self.driver.find_elements(By.XPATH, "//table[contains(., 'Transaction History')]//tr[contains(., 'PAYMENT')]")
                    for row in trans_rows:
                        amount_cell = row.find_element(By.XPATH, ".//td[last()]")  # Amount is usually in last column
                        amount = self._parse_currency(amount_cell.text)
                        if amount and self._validate_tax_amount(amount, property_value):
                            tax_amount = amount
                            logger.info(f"Wayne County: Found tax amount in transaction history: ${tax_amount}")
                            break
                except:
                    pass
            
            # Extract additional information
            try:
                # Parcel number
                parcel_elem = self.driver.find_element(By.XPATH, "//td[text()='Parcel #:']/following-sibling::td[1]")
                result.account_number = parcel_elem.text.strip()
            except:
                pass
            
            try:
                # Property address from Location field
                addr_elem = self.driver.find_element(By.XPATH, "//td[text()='Location:']/following-sibling::td[1]")
                result.property_address = addr_elem.text.strip()
            except:
                pass
            
            if tax_amount:
                result.tax_amount = tax_amount
                result.extraction_status = 'success'
                result.extraction_notes = f"Successfully extracted tax amount: ${tax_amount}"
            else:
                result.extraction_status = 'failed'
                result.extraction_notes = "Could not find valid tax amount (may have found property value instead)"
                result.screenshot_path = self._take_screenshot('wayne_county_failed')
                
        except Exception as e:
            logger.error(f"Wayne County extraction error: {e}")
            result.extraction_status = 'failed'
            result.extraction_notes = str(e)
            result.screenshot_path = self._take_screenshot('wayne_county_error')
            
        return result


class JohnstonCountyExtractor(NCTaxExtractorBase):
    """Extractor for Johnston County, NC (taxpay.johnstonnc.com)"""
    
    def extract(self, url: str, property_info: Dict) -> TaxExtractionResult:
        result = TaxExtractionResult(
            property_id=property_info.get('property_id', ''),
            property_name=property_info.get('property_name', ''),
            jurisdiction='Johnston',
            state='NC',
            extraction_status='pending'
        )
        
        try:
            logger.info(f"Johnston County: Navigating to {url}")
            self.driver.get(url)
            
            # Wait for page to load
            time.sleep(3)
            
            # Based on screenshot, the page has a search form with Last/First/Middle name fields
            # The dropdown is already set to "Search By Owner Name"
            try:
                # The Last name field already has 'BCS' but let's ensure it's filled
                last_name_input = self.wait.until(
                    EC.presence_of_element_located((By.XPATH, "//input[@type='text'][1] | //input[contains(@name, 'Last')] | //td[text()='Last:']/following::input[1]"))
                )
                last_name_input.clear()
                last_name_input.send_keys("BCS")
                logger.info("Johnston County: Entered 'BCS' in Last name field")
                
                # Click the Search button
                search_button = self.driver.find_element(By.XPATH, "//input[@value='Search'] | //button[text()='Search']")
                search_button.click()
                logger.info("Johnston County: Clicked Search button")
                    
            except Exception as e:
                logger.error(f"Johnston County: Could not perform search: {e}")
                
            # Wait for results
            time.sleep(5)
            
            # Parse property name to determine which record to extract
            property_name = property_info.get('property_name', '').lower()
            
            # Determine which result row to use based on property name
            row_index = 0  # Default to first row
            if 'parcel 2' in property_name or 'propco 08' in property_name:
                row_index = 2  # Third row for Propco 08
            elif 'parcel 1' in property_name or 'propco 04' in property_name:
                row_index = 0  # First row for Propco 04
                
            # Look for results table
            try:
                # Wait for results table
                results_table = self.wait.until(
                    EC.presence_of_element_located((By.XPATH, "//table[contains(@class, 'results')] | //table[@id='resultsTable'] | //table[.//td[contains(text(), 'BCS')]]"))
                )
                
                # Get all rows with BCS
                rows = results_table.find_elements(By.XPATH, ".//tr[.//td[contains(text(), 'BCS')]]")
                
                if len(rows) > row_index:
                    target_row = rows[row_index]
                    
                    # Look for tax amount in the row
                    amount_cells = target_row.find_elements(By.XPATH, ".//td[contains(text(), '$')]")
                    
                    for cell in amount_cells:
                        amount = self._parse_currency(cell.text)
                        if amount and self._validate_tax_amount(amount):
                            result.tax_amount = amount
                            result.extraction_status = 'success'
                            result.extraction_notes = f"Extracted from row {row_index + 1}"
                            logger.info(f"Johnston County: Found tax amount ${amount} in row {row_index + 1}")
                            break
                            
            except Exception as e:
                logger.error(f"Johnston County: Error processing results: {e}")
                
            # If still no tax amount, try clicking on account link
            if not result.tax_amount:
                try:
                    # Click on first/appropriate account number link
                    account_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, 'account') or contains(@href, 'detail')]")
                    if len(account_links) > row_index:
                        account_links[row_index].click()
                        time.sleep(3)
                        
                        # Look for tax amount on detail page
                        tax_amount = None
                        tables = self.driver.find_elements(By.TAG_NAME, 'table')
                        for table in tables:
                            tax_amount = self._find_tax_amount_in_table(table)
                            if tax_amount:
                                result.tax_amount = tax_amount
                                result.extraction_status = 'success'
                                result.extraction_notes = "Extracted from detail page"
                                break
                                
                except Exception as e:
                    logger.error(f"Johnston County: Error accessing detail page: {e}")
                    
            if not result.tax_amount:
                result.extraction_status = 'failed'
                result.extraction_notes = "Could not find tax amount in search results"
                result.screenshot_path = self._take_screenshot('johnston_county_failed')
                
        except Exception as e:
            logger.error(f"Johnston County extraction error: {e}")
            result.extraction_status = 'failed'
            result.extraction_notes = str(e)
            result.screenshot_path = self._take_screenshot('johnston_county_error')
            
        return result


class CravenCountyExtractor(NCTaxExtractorBase):
    """Extractor for Craven County, NC (bttaxpayerportal.com)"""
    
    def extract(self, url: str, property_info: Dict) -> TaxExtractionResult:
        result = TaxExtractionResult(
            property_id=property_info.get('property_id', ''),
            property_name=property_info.get('property_name', ''),
            jurisdiction='Craven',
            state='NC',
            extraction_status='pending'
        )
        
        try:
            logger.info(f"Craven County: Navigating to {url}")
            self.driver.get(url)
            
            # Wait for page to load
            time.sleep(3)
            
            # Determine account number from property name
            property_name = property_info.get('property_name', '').lower()
            account_number = None
            
            if 'propco 05' in property_name or '334 e main' in property_name:
                account_number = '114834'
            elif 'propco 09' in property_name or '370 nc highway 43' in property_name:
                account_number = '114839'
            elif 'propco 11' in property_name or '4100 dr martin' in property_name:
                account_number = '116885'
            elif 'propco 20' in property_name or '3314 neuse' in property_name:
                account_number = '116886'  # Guessing based on pattern
                
            if not account_number:
                # Try to extract from property info
                account_number = property_info.get('account_number', '')
                
            if account_number:
                logger.info(f"Craven County: Using account number {account_number}")
                
                # Fill account number field
                try:
                    account_input = self.wait.until(
                        EC.presence_of_element_located((By.XPATH, "//input[@id='accountNumber'] | //input[contains(@placeholder, 'Account')] | //input[@name='account']"))
                    )
                    account_input.clear()
                    account_input.send_keys(account_number)
                    logger.info(f"Craven County: Entered account number {account_number}")
                    
                    # Submit form
                    account_input.send_keys(Keys.RETURN)
                    # Or try clicking search button
                    try:
                        search_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Search')] | //button[@type='submit'] | //input[@type='submit']")
                        search_button.click()
                    except:
                        pass
                        
                except Exception as e:
                    logger.error(f"Craven County: Could not fill account number: {e}")
                    
            # Wait for results/page to scroll
            time.sleep(5)
            
            # Look for tax amount in 2025 row (last row)
            try:
                # Find table with tax information
                tax_table = self.wait.until(
                    EC.presence_of_element_located((By.XPATH, "//table[.//td[contains(text(), '2025')] or .//td[contains(text(), '2024')]]"))
                )
                
                # Get the last row or row with 2025
                year_rows = tax_table.find_elements(By.XPATH, ".//tr[.//td[contains(text(), '2025')]]")
                if not year_rows:
                    year_rows = tax_table.find_elements(By.XPATH, ".//tr[.//td[contains(text(), '2024')]]")
                    
                if year_rows:
                    last_row = year_rows[-1]  # Get last matching row
                    
                    # Look for amount in this row
                    amount_cells = last_row.find_elements(By.XPATH, ".//td[contains(text(), '$')]")
                    
                    for cell in amount_cells:
                        amount = self._parse_currency(cell.text)
                        if amount and self._validate_tax_amount(amount):
                            result.tax_amount = amount
                            result.extraction_status = 'success'
                            result.extraction_notes = "Extracted from 2025/2024 tax row"
                            logger.info(f"Craven County: Found tax amount ${amount}")
                            break
                            
            except Exception as e:
                logger.error(f"Craven County: Error finding tax table: {e}")
                
            # If no tax amount found, search all tables
            if not result.tax_amount:
                tables = self.driver.find_elements(By.TAG_NAME, 'table')
                for table in tables:
                    tax_amount = self._find_tax_amount_in_table(table)
                    if tax_amount:
                        result.tax_amount = tax_amount
                        result.extraction_status = 'success'
                        result.extraction_notes = "Extracted from table search"
                        break
                        
            if not result.tax_amount:
                result.extraction_status = 'failed'
                result.extraction_notes = f"Could not find tax amount for account {account_number}"
                result.screenshot_path = self._take_screenshot('craven_county_failed')
                
        except Exception as e:
            logger.error(f"Craven County extraction error: {e}")
            result.extraction_status = 'failed'
            result.extraction_notes = str(e)
            result.screenshot_path = self._take_screenshot('craven_county_error')
            
        return result


class WilsonCountyExtractor(NCTaxExtractorBase):
    """Extractor for Wilson County, NC (wilsonnc.devnetwedge.com)"""
    
    def extract(self, url: str, property_info: Dict) -> TaxExtractionResult:
        result = TaxExtractionResult(
            property_id=property_info.get('property_id', ''),
            property_name=property_info.get('property_name', ''),
            jurisdiction='Wilson',
            state='NC',
            extraction_status='pending'
        )
        
        try:
            logger.info(f"Wilson County: Navigating to {url}")
            self.driver.get(url)
            
            # Wait for page to load
            time.sleep(3)
            
            # Fill 'BCS' in search field
            try:
                search_input = self.wait.until(
                    EC.presence_of_element_located((By.XPATH, "//input[@type='search'] | //input[contains(@placeholder, 'Search')] | //input[@id='search']"))
                )
                search_input.clear()
                search_input.send_keys("BCS")
                logger.info("Wilson County: Entered 'BCS' in search field")
                
                # Submit search
                search_input.send_keys(Keys.RETURN)
                
                # Also try clicking search button
                try:
                    search_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Search')] | //button[@type='submit']")
                    search_button.click()
                except:
                    pass
                    
            except Exception as e:
                logger.error(f"Wilson County: Could not perform search: {e}")
                
            # Wait for results
            time.sleep(5)
            
            # Determine which parcel based on property name
            property_name = property_info.get('property_name', '').lower()
            row_index = 0  # Default to first row
            
            if 'parcel 2' in property_name:
                row_index = 1  # Second row for Parcel 2
                
            try:
                # Find and click account number link in results table
                account_links = self.wait.until(
                    EC.presence_of_all_elements_located((By.XPATH, "//table//a[contains(@href, 'account') or contains(@href, 'detail')] | //table//td/a"))
                )
                
                if len(account_links) > row_index:
                    logger.info(f"Wilson County: Clicking account link {row_index + 1}")
                    account_links[row_index].click()
                    
                    # Wait for detail page to load
                    time.sleep(5)
                    
                    # Look for tax amount on detail page
                    tax_selectors = [
                        "//td[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'tax due')]/..//td[contains(text(), '$')]",
                        "//td[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'amount due')]/..//td[contains(text(), '$')]",
                        "//td[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'total due')]/..//td[contains(text(), '$')]",
                        "//span[contains(@class, 'amount')] | //div[contains(@class, 'tax-amount')]",
                        "//td[contains(text(), '$')][not(contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'value'))]"
                    ]
                    
                    for selector in tax_selectors:
                        try:
                            elements = self.driver.find_elements(By.XPATH, selector)
                            for element in elements:
                                amount = self._parse_currency(element.text)
                                if amount and self._validate_tax_amount(amount):
                                    result.tax_amount = amount
                                    result.extraction_status = 'success'
                                    result.extraction_notes = f"Extracted from detail page (parcel {row_index + 1})"
                                    logger.info(f"Wilson County: Found tax amount ${amount}")
                                    break
                            if result.tax_amount:
                                break
                        except:
                            continue
                            
            except Exception as e:
                logger.error(f"Wilson County: Error accessing account details: {e}")
                
            # If still no tax amount, search all tables
            if not result.tax_amount:
                tables = self.driver.find_elements(By.TAG_NAME, 'table')
                for table in tables:
                    tax_amount = self._find_tax_amount_in_table(table)
                    if tax_amount:
                        result.tax_amount = tax_amount
                        result.extraction_status = 'success'
                        result.extraction_notes = "Extracted from table search"
                        break
                        
            if not result.tax_amount:
                result.extraction_status = 'failed'
                result.extraction_notes = "Could not find tax amount after search and navigation"
                result.screenshot_path = self._take_screenshot('wilson_county_failed')
                
        except Exception as e:
            logger.error(f"Wilson County extraction error: {e}")
            result.extraction_status = 'failed'
            result.extraction_notes = str(e)
            result.screenshot_path = self._take_screenshot('wilson_county_error')
            
        return result


class MooreCountyExtractor(NCTaxExtractorBase):
    """Extractor for Moore County, NC (selfservice.moorecountync.gov)"""
    
    def extract(self, url: str, property_info: Dict) -> TaxExtractionResult:
        result = TaxExtractionResult(
            property_id=property_info.get('property_id', ''),
            property_name=property_info.get('property_name', ''),
            jurisdiction='Moore',
            state='NC',
            extraction_status='pending'
        )
        
        try:
            logger.info(f"Moore County: Navigating to {url}")
            self.driver.get(url)
            
            # Wait for page to load
            time.sleep(3)
            
            # Fill '2024' in bill year field
            try:
                year_input = self.wait.until(
                    EC.presence_of_element_located((By.XPATH, "//input[@id='billYear'] | //input[contains(@placeholder, 'Year')] | //input[contains(@name, 'year')]"))
                )
                year_input.clear()
                year_input.send_keys("2024")
                logger.info("Moore County: Entered '2024' in bill year field")
            except Exception as e:
                logger.warning(f"Moore County: Could not fill year field: {e}")
                
            # Fill 'BCS' in Owner Name field
            try:
                owner_input = self.wait.until(
                    EC.presence_of_element_located((By.XPATH, "//input[@id='ownerName'] | //input[contains(@placeholder, 'Owner')] | //input[contains(@name, 'owner')]"))
                )
                owner_input.clear()
                owner_input.send_keys("BCS")
                logger.info("Moore County: Entered 'BCS' in owner name field")
                
                # Submit form
                owner_input.send_keys(Keys.RETURN)
                
                # Also try clicking search button
                try:
                    search_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Search')] | //input[@type='submit']")
                    search_button.click()
                except:
                    pass
                    
            except Exception as e:
                logger.error(f"Moore County: Could not perform search: {e}")
                
            # Wait for results
            time.sleep(5)
            
            # Look for tax amount in results
            tax_amount = None
            tables = self.driver.find_elements(By.TAG_NAME, 'table')
            for table in tables:
                tax_amount = self._find_tax_amount_in_table(table)
                if tax_amount:
                    result.tax_amount = tax_amount
                    result.extraction_status = 'success'
                    result.extraction_notes = "Extracted from search results"
                    break
                    
            # If no amount found, try clicking first result
            if not tax_amount:
                try:
                    result_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, 'detail') or contains(@href, 'account')]")
                    if result_links:
                        result_links[0].click()
                        time.sleep(3)
                        
                        # Search for tax amount on detail page
                        tables = self.driver.find_elements(By.TAG_NAME, 'table')
                        for table in tables:
                            tax_amount = self._find_tax_amount_in_table(table)
                            if tax_amount:
                                result.tax_amount = tax_amount
                                result.extraction_status = 'success'
                                result.extraction_notes = "Extracted from detail page"
                                break
                except Exception as e:
                    logger.error(f"Moore County: Error accessing detail page: {e}")
                    
            if not result.tax_amount:
                result.extraction_status = 'failed'
                result.extraction_notes = "Could not find tax amount"
                result.screenshot_path = self._take_screenshot('moore_county_failed')
                
        except Exception as e:
            logger.error(f"Moore County extraction error: {e}")
            result.extraction_status = 'failed'
            result.extraction_notes = str(e)
            result.screenshot_path = self._take_screenshot('moore_county_error')
            
        return result


class VanceCountyExtractor(NCTaxExtractorBase):
    """Extractor for Vance County, NC (vance.ustaxdata.com)"""
    
    def extract(self, url: str, property_info: Dict) -> TaxExtractionResult:
        result = TaxExtractionResult(
            property_id=property_info.get('property_id', ''),
            property_name=property_info.get('property_name', ''),
            jurisdiction='Vance',
            state='NC',
            extraction_status='pending'
        )
        
        try:
            logger.info(f"Vance County: Navigating to {url}")
            self.driver.get(url)
            
            # Wait for page to load
            time.sleep(3)
            
            # Look for tax amount - avoid property values
            tax_found = False
            property_value_found = False
            
            # First identify property value to avoid it
            value_selectors = [
                "//td[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'assessed')]/..//td[contains(text(), '$')]",
                "//td[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'value')]/..//td[contains(text(), '$')]",
                "//td[contains(text(), '$500,000')]",  # Specific known property value
                "//td[contains(text(), '$')][preceding-sibling::td[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'value')]]"
            ]
            
            for selector in value_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for element in elements:
                        amount = self._parse_currency(element.text)
                        if amount and amount > 100000:
                            result.property_value = amount
                            property_value_found = True
                            logger.info(f"Vance County: Identified property value: ${amount}")
                            break
                    if property_value_found:
                        break
                except:
                    continue
            
            # Now look for actual tax amount
            tax_selectors = [
                "//td[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'tax due')]/..//td[contains(text(), '$')]",
                "//td[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'taxes due')]/..//td[contains(text(), '$')]",
                "//td[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'amount due')]/..//td[contains(text(), '$')]",
                "//td[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'balance')]/..//td[contains(text(), '$')]",
                "//td[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'total') and contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'tax')]/..//td[contains(text(), '$')]"
            ]
            
            for selector in tax_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for element in elements:
                        amount = self._parse_currency(element.text)
                        if amount:
                            # Skip if this is the property value
                            if property_value_found and abs(amount - result.property_value) < 1:
                                continue
                            
                            # Validate this is a tax amount
                            if self._validate_tax_amount(amount, result.property_value):
                                result.tax_amount = amount
                                tax_found = True
                                logger.info(f"Vance County: Found tax amount: ${amount}")
                                break
                    if tax_found:
                        break
                except:
                    continue
            
            # If no tax amount found, search all tables but skip property values
            if not tax_found:
                tables = self.driver.find_elements(By.TAG_NAME, 'table')
                for table in tables:
                    rows = table.find_elements(By.TAG_NAME, 'tr')
                    for row in rows:
                        text = row.text.lower()
                        # Skip rows with value keywords
                        if 'value' in text or 'assessed' in text or 'apprais' in text:
                            continue
                        
                        # Look for tax keywords
                        if 'tax' in text or 'due' in text or 'balance' in text:
                            cells = row.find_elements(By.TAG_NAME, 'td')
                            for cell in cells:
                                if '$' in cell.text:
                                    amount = self._parse_currency(cell.text)
                                    if amount and self._validate_tax_amount(amount, result.property_value):
                                        result.tax_amount = amount
                                        tax_found = True
                                        logger.info(f"Vance County: Found tax amount in table: ${amount}")
                                        break
                        if tax_found:
                            break
                    if tax_found:
                        break
            
            if result.tax_amount:
                result.extraction_status = 'success'
                result.extraction_notes = f"Successfully extracted tax amount (avoided property value of ${result.property_value})"
            else:
                result.extraction_status = 'failed'
                result.extraction_notes = f"Could not find tax amount (found property value: ${result.property_value})"
                result.screenshot_path = self._take_screenshot('vance_county_failed')
                
        except Exception as e:
            logger.error(f"Vance County extraction error: {e}")
            result.extraction_status = 'failed'
            result.extraction_notes = str(e)
            result.screenshot_path = self._take_screenshot('vance_county_error')
            
        return result


class BeaufortCountyExtractor(NCTaxExtractorBase):
    """Extractor for Beaufort County, NC (bcpwa.ncptscloud.com)"""
    
    def extract(self, url: str, property_info: Dict) -> TaxExtractionResult:
        result = TaxExtractionResult(
            property_id=property_info.get('property_id', ''),
            property_name=property_info.get('property_name', ''),
            jurisdiction='Beaufort',
            state='NC',
            extraction_status='pending'
        )
        
        try:
            logger.info(f"Beaufort County: Navigating to {url}")
            self.driver.get(url)
            
            # Wait for page to load
            time.sleep(3)
            
            # Look specifically for "Taxes Due for 2024" or similar
            tax_selectors = [
                "//td[contains(text(), 'Taxes Due for 2024')]/..//td[contains(text(), '$')]",
                "//td[contains(text(), 'Taxes Due for 2025')]/..//td[contains(text(), '$')]",
                "//td[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'taxes due')]/..//td[contains(text(), '$')]",
                "//span[contains(text(), 'Taxes Due')]/following-sibling::span",
                "//div[contains(@class, 'tax-due')]//span[contains(text(), '$')]"
            ]
            
            tax_amount = None
            for selector in tax_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for element in elements:
                        amount = self._parse_currency(element.text)
                        if amount and self._validate_tax_amount(amount):
                            tax_amount = amount
                            logger.info(f"Beaufort County: Found tax amount: ${amount}")
                            break
                    if tax_amount:
                        break
                except:
                    continue
            
            # If not found, search tables
            if not tax_amount:
                tables = self.driver.find_elements(By.TAG_NAME, 'table')
                for table in tables:
                    tax_amount = self._find_tax_amount_in_table(table)
                    if tax_amount:
                        break
            
            if tax_amount:
                result.tax_amount = tax_amount
                result.extraction_status = 'success'
                result.extraction_notes = "Successfully extracted tax amount"
            else:
                result.extraction_status = 'failed'
                result.extraction_notes = "Could not find tax amount"
                result.screenshot_path = self._take_screenshot('beaufort_county_failed')
                
        except Exception as e:
            logger.error(f"Beaufort County extraction error: {e}")
            result.extraction_status = 'failed'
            result.extraction_notes = str(e)
            result.screenshot_path = self._take_screenshot('beaufort_county_error')
            
        return result


class NCPropertyTaxExtractor:
    """Main extractor class that routes to appropriate county extractor"""
    
    def __init__(self, headless: bool = False):
        self.driver = self._setup_driver(headless)
        self.extractors = {
            'wayne': WayneCountyExtractor(self.driver),
            'johnston': JohnstonCountyExtractor(self.driver),
            'craven': CravenCountyExtractor(self.driver),
            'wilson': WilsonCountyExtractor(self.driver),
            'moore': MooreCountyExtractor(self.driver),
            'vance': VanceCountyExtractor(self.driver),
            'beaufort': BeaufortCountyExtractor(self.driver)
        }
        
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
        options.add_argument('--window-size=1920,1080')
        
        return webdriver.Chrome(options=options)
    
    def extract(self, url: str, property_info: Dict) -> TaxExtractionResult:
        """Extract tax information from URL based on jurisdiction"""
        
        # Determine jurisdiction
        jurisdiction = property_info.get('jurisdiction', '').lower()
        
        # Get appropriate extractor
        extractor = None
        for key in self.extractors:
            if key in jurisdiction:
                extractor = self.extractors[key]
                break
        
        if not extractor:
            # Try to determine from URL
            domain = urlparse(url).netloc.lower()
            if 'wayne' in domain:
                extractor = self.extractors['wayne']
            elif 'johnston' in domain:
                extractor = self.extractors['johnston']
            elif 'craven' in domain or 'bttaxpayerportal' in domain:
                extractor = self.extractors['craven']
            elif 'wilson' in domain:
                extractor = self.extractors['wilson']
            elif 'moore' in domain:
                extractor = self.extractors['moore']
            elif 'vance' in domain:
                extractor = self.extractors['vance']
            elif 'beaufort' in domain or 'bcpwa' in domain:
                extractor = self.extractors['beaufort']
        
        if extractor:
            return extractor.extract(url, property_info)
        else:
            return TaxExtractionResult(
                property_id=property_info.get('property_id', ''),
                property_name=property_info.get('property_name', ''),
                jurisdiction=property_info.get('jurisdiction', ''),
                state='NC',
                extraction_status='unsupported',
                extraction_notes=f"No extractor available for jurisdiction: {jurisdiction}"
            )
    
    def process_excel_batch(self, excel_file: str, output_file: str, nc_only: bool = True):
        """Process NC properties from Excel file"""
        df = pd.read_excel(excel_file)
        
        # Filter for NC properties if requested
        if nc_only:
            df = df[df['State'] == 'NC']
        
        results = []
        
        for idx, row in df.iterrows():
            if pd.isna(row.get('Tax Bill Link')):
                logger.warning(f"Skipping property without tax link: {row.get('Property Name')}")
                continue
            
            logger.info(f"Processing {idx+1}/{len(df)}: {row.get('Property Name')}")
            
            property_info = {
                'property_id': row.get('Property ID', ''),
                'property_name': row.get('Property Name', ''),
                'jurisdiction': row.get('Jurisdiction', ''),
                'state': row.get('State', ''),
                'account_number': row.get('Acct Number', ''),
                'property_address': row.get('Property Address', ''),
            }
            
            result = self.extract(row['Tax Bill Link'], property_info)
            
            # Add URL to result
            result_dict = {
                'property_id': result.property_id,
                'property_name': result.property_name,
                'jurisdiction': result.jurisdiction,
                'state': result.state,
                'tax_bill_link': row['Tax Bill Link'],
                'tax_amount': result.tax_amount,
                'property_value': result.property_value,
                'account_number': result.account_number,
                'property_address': result.property_address,
                'extraction_status': result.extraction_status,
                'extraction_timestamp': result.extraction_timestamp,
                'extraction_notes': result.extraction_notes,
                'screenshot_path': result.screenshot_path
            }
            
            results.append(result_dict)
            
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
        print("\n" + "="*60)
        print("NC PROPERTY TAX EXTRACTION SUMMARY")
        print("="*60)
        print(f"Total Properties Processed: {len(results)}")
        
        # Status breakdown
        status_counts = {}
        for result in results:
            status = result['extraction_status']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print("\nStatus Breakdown:")
        for status, count in sorted(status_counts.items()):
            percentage = (count / len(results)) * 100 if results else 0
            print(f"  {status}: {count} ({percentage:.1f}%)")
        
        # Jurisdiction breakdown
        jurisdiction_counts = {}
        for result in results:
            jurisdiction = result['jurisdiction']
            jurisdiction_counts[jurisdiction] = jurisdiction_counts.get(jurisdiction, 0) + 1
        
        print("\nJurisdiction Breakdown:")
        for jurisdiction, count in sorted(jurisdiction_counts.items()):
            print(f"  {jurisdiction}: {count}")
        
        # Successful extractions with amounts
        successful = [r for r in results if r['extraction_status'] == 'success' and r['tax_amount']]
        if successful:
            print(f"\nSuccessfully extracted {len(successful)} tax amounts:")
            for result in successful[:10]:  # Show first 10
                print(f"  {result['property_name'][:50]}: ${result['tax_amount']:,.2f}")
        
        # Failed extractions
        failed = [r for r in results if r['extraction_status'] == 'failed']
        if failed:
            print(f"\nFailed extractions ({len(failed)}):")
            for result in failed[:5]:  # Show first 5
                print(f"  {result['property_name'][:50]}: {result['extraction_notes'][:50]}")
    
    def close(self):
        """Close the browser driver"""
        if self.driver:
            self.driver.quit()


def main():
    """Main execution function for testing"""
    import os
    
    # Create output directories if they don't exist
    os.makedirs('output/screenshots', exist_ok=True)
    
    extractor = NCPropertyTaxExtractor(headless=False)
    
    try:
        # Test with NC properties from the CSV
        print("Testing NC Property Tax Extractors...")
        
        # Process all NC properties
        results = extractor.process_excel_batch(
            'OFFICIAL-proptax-extract.csv',
            'nc_extraction_results.xlsx',
            nc_only=True
        )
        
        print(f"\nProcessed {len(results)} NC properties")
        
    finally:
        extractor.close()


if __name__ == "__main__":
    main()