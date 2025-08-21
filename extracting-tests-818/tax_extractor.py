"""
Resilient Property Tax Data Extractor
Handles multiple extraction patterns with robust error recovery
"""

import asyncio
import csv
import io
import json
import logging
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urljoin, urlparse
import sys

from bs4 import BeautifulSoup
import requests
from playwright.async_api import async_playwright, Page, Browser, TimeoutError as PlaywrightTimeout

from selenium_tax_extractors import UnifiedTaxExtractor


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tax_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class PropertyTaxRecord:
    """Data model for property tax information"""
    property_id: str
    property_name: str
    jurisdiction: str
    state: str
    property_type: str
    close_date: Optional[str]
    amount_due: Optional[str]
    previous_year_taxes: Optional[str]
    extraction_steps: str
    acct_number: Optional[str]
    property_address: Optional[str]
    next_due_date: Optional[str]
    tax_bill_link: str
    parent_entity: Optional[str]
    extraction_status: str = "pending"
    extraction_error: Optional[str] = None
    extracted_data: Optional[Dict] = None
    extraction_timestamp: Optional[str] = None


class ExtractionStrategy:
    """Base class for extraction strategies"""
    
    def __init__(self, retry_count: int = 3, timeout: int = 30000):
        self.retry_count = retry_count
        self.timeout = timeout
    
    async def extract(self, record: PropertyTaxRecord, page: Page) -> Dict[str, Any]:
        """Extract data from the tax website"""
        raise NotImplementedError
    
    def parse_extraction_steps(self, steps: str) -> List[Dict[str, str]]:
        """Parse extraction steps from CSV"""
        if not steps or steps == 'entity' or steps == 'sub-entity':
            return []
        
        # Split by numbered steps
        step_pattern = r'\d+\.\s*'
        raw_steps = re.split(step_pattern, steps)
        parsed_steps = []
        
        for step in raw_steps:
            if step.strip():
                # Parse different step types
                if 'Enter' in step and 'in' in step:
                    # Form fill step
                    parts = step.split(' in ')
                    if len(parts) == 2:
                        value = parts[0].replace('Enter', '').strip()
                        field = parts[1].strip()
                        parsed_steps.append({
                            'action': 'fill',
                            'field': field,
                            'value': value
                        })
                elif 'Click' in step:
                    # Click step
                    target = step.replace('Click', '').strip()
                    parsed_steps.append({
                        'action': 'click',
                        'target': target
                    })
                elif 'Direct Link' in step:
                    # Direct navigation
                    parsed_steps.append({
                        'action': 'navigate',
                        'url': 'direct'
                    })
                elif 'search' in step.lower():
                    # Search action
                    parsed_steps.append({
                        'action': 'search',
                        'details': step
                    })
                else:
                    # Data extraction step
                    parsed_steps.append({
                        'action': 'extract',
                        'target': step.strip('"')
                    })
        
        return parsed_steps


class MaricopaExtractor(ExtractionStrategy):
    """Extractor for Maricopa County, AZ"""
    
    async def extract(self, record: PropertyTaxRecord, page: Page) -> Dict[str, Any]:
        steps = self.parse_extraction_steps(record.extraction_steps)
        extracted = {}
        
        try:
            await page.goto(record.tax_bill_link, wait_until='networkidle', timeout=self.timeout)
            
            # Wait for the page to load
            await page.wait_for_selector('#txtParcelNumBook', timeout=10000)
            
            for step in steps:
                if step['action'] == 'fill' and 'Parcel Number' in step['field']:
                    parcel_number = step['value']
                    
                    # Maricopa uses a 4-part parcel number format: Book-Map-Item-Split
                    # Parse the parcel number (format: XXX-XX-XXXX or XXX-XX-XXX-X)
                    parts = parcel_number.split('-')
                    
                    if len(parts) >= 3:
                        # Fill the 4 input fields
                        await page.fill('#txtParcelNumBook', parts[0])
                        await page.fill('#txtParcelNumMap', parts[1])
                        
                        # Handle different formats
                        if len(parts) == 3:
                            # Check if the last part has a letter at the end (like 025A)
                            item_part = parts[2]
                            split_part = ''
                            
                            # Check if last character is a letter
                            if item_part and item_part[-1].isalpha():
                                split_part = item_part[-1]
                                item_part = item_part[:-1]
                            
                            await page.fill('#txtParcelNumItem', item_part)
                            await page.fill('#txtParcelNumSplit', split_part)
                        elif len(parts) == 4:
                            # Format: XXX-XX-XXX-X (with split)
                            await page.fill('#txtParcelNumItem', parts[2])
                            await page.fill('#txtParcelNumSplit', parts[3])
                        else:
                            # Fallback
                            await page.fill('#txtParcelNumItem', parts[2] if len(parts) > 2 else '')
                            await page.fill('#txtParcelNumSplit', '')
                        
                        # Click the search button
                        search_button = await page.query_selector('a.button:has-text("Search")')
                        if search_button:
                            await search_button.click()
                        else:
                            # Fallback: press Enter on the last field
                            await page.press('#txtParcelNumSplit', 'Enter')
                        
                        # Wait for navigation or results
                        await page.wait_for_load_state('networkidle', timeout=15000)
                        await page.wait_for_timeout(2000)
                        
                        # After search, we need to click on the parcel link to get to the tax details
                        # Look for the parcel number as a link in the results
                        parcel_link = None
                        
                        # Try multiple selectors for the parcel link
                        link_selectors = [
                            f'a:has-text("{parcel_number}")',
                            f'a[href*="{parcel_number}"]',
                            'table a:first-of-type',  # First link in results table
                            'td a',  # Link in table cell
                            '.results a'  # Link in results div
                        ]
                        
                        for selector in link_selectors:
                            try:
                                parcel_link = await page.query_selector(selector)
                                if parcel_link and await parcel_link.is_visible():
                                    logger.info(f"Found parcel link with selector: {selector}")
                                    await parcel_link.click()
                                    await page.wait_for_load_state('networkidle', timeout=15000)
                                    await page.wait_for_timeout(2000)
                                    break
                            except:
                                continue
            
            # Now extract tax data from the detail page
            current_url = page.url
            
            # Extract all text containing dollar amounts
            dollar_elements = await page.query_selector_all('*:has-text("$")')
            
            for element in dollar_elements[:20]:  # Check first 20 elements with $
                try:
                    text = await element.text_content()
                    if text and len(text) < 500:  # Reasonable length
                        text_lower = text.lower()
                        
                        # Look for specific patterns
                        if 'total' in text_lower and 'due' in text_lower:
                            amounts = re.findall(r'\$[\d,]+\.?\d*', text)
                            if amounts:
                                extracted['total_amount_due'] = amounts[-1]  # Last amount is usually the total
                        
                        elif 'current' in text_lower and ('tax' in text_lower or 'due' in text_lower):
                            amounts = re.findall(r'\$[\d,]+\.?\d*', text)
                            if amounts:
                                extracted['current_amount'] = amounts[0]
                        
                        elif 'tax' in text_lower and 'year' not in text_lower:
                            amounts = re.findall(r'\$[\d,]+\.?\d*', text)
                            if amounts and 'tax_amount' not in extracted:
                                extracted['tax_amount'] = amounts[0]
                        
                        elif 'balance' in text_lower:
                            amounts = re.findall(r'\$[\d,]+\.?\d*', text)
                            if amounts:
                                extracted['balance'] = amounts[0]
                except:
                    continue
            
            # Try to extract from tables as fallback
            if not extracted or len(extracted) < 2:
                tax_info = await self._extract_from_table(page)
                extracted.update(tax_info)
            
            # Get property details
            extracted['property_address'] = await self._extract_property_info(page, 'address')
            extracted['owner_name'] = await self._extract_property_info(page, 'owner')
            extracted['tax_year'] = await self._extract_property_info(page, 'year')
            
            # Store the final URL for debugging
            extracted['final_url'] = current_url
            
        except Exception as e:
            logger.error(f"Maricopa extraction failed: {e}")
            raise
        
        return extracted
    
    async def _extract_text(self, page: Page, selector: str) -> Optional[str]:
        try:
            element = await page.query_selector(selector)
            if element:
                return await element.text_content()
        except:
            pass
        return None
    
    async def _extract_amount(self, page: Page, keywords: list) -> Optional[str]:
        """Extract monetary amounts near keywords"""
        for keyword in keywords:
            try:
                elements = await page.query_selector_all(f'*:has-text("{keyword}")')
                for element in elements:
                    text = await element.text_content()
                    # Look for dollar amounts
                    import re
                    amounts = re.findall(r'\$[\d,]+\.?\d*', text)
                    if amounts:
                        return amounts[0]
            except:
                continue
        return None
    
    async def _extract_from_table(self, page: Page) -> Dict[str, Any]:
        """Extract data from tables on the page"""
        extracted = {}
        try:
            # Look for tables with tax information
            tables = await page.query_selector_all('table')
            for table in tables:
                rows = await table.query_selector_all('tr')
                for row in rows:
                    cells = await row.query_selector_all('td')
                    if len(cells) >= 2:
                        label = await cells[0].text_content()
                        value = await cells[1].text_content()
                        
                        if label and value:
                            label_lower = label.lower().strip()
                            value = value.strip()
                            
                            if 'tax' in label_lower and '$' in value:
                                extracted['tax_amount'] = value
                            elif 'due' in label_lower and '$' in value:
                                extracted['amount_due'] = value
                            elif 'address' in label_lower:
                                extracted['property_address'] = value
        except:
            pass
        
        return extracted
    
    async def _extract_property_info(self, page: Page, info_type: str) -> Optional[str]:
        """Extract specific property information"""
        try:
            if info_type == 'address':
                selectors = ['*:has-text("Property Address")', '*:has-text("Situs Address")', '*:has-text("Location")']
            elif info_type == 'owner':
                selectors = ['*:has-text("Owner Name")', '*:has-text("Owner")', '*:has-text("Taxpayer")']
            elif info_type == 'year':
                selectors = ['*:has-text("Tax Year")', '*:has-text("Year")']
            else:
                return None
            
            for selector in selectors:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    text = await element.text_content()
                    if text and ':' in text:
                        # Extract value after colon
                        parts = text.split(':', 1)
                        if len(parts) == 2:
                            return parts[1].strip()
                    # Check next sibling for value
                    next_elem = await element.query_selector('xpath=following-sibling::*[1]')
                    if next_elem:
                        value = await next_elem.text_content()
                        if value:
                            return value.strip()
        except:
            pass
        return None


class MontgomeryExtractor(ExtractionStrategy):
    """Extractor for Montgomery County, TX - Uses direct HTTP requests"""
    
    async def extract(self, record: PropertyTaxRecord, page: Page = None) -> Dict[str, Any]:
        """Extract using direct HTTP request instead of Playwright"""
        extracted = {}
        
        try:
            # Use direct HTTP request for Montgomery County
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            }
            
            response = requests.get(record.tax_bill_link, headers=headers, timeout=30)
            
            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code} for {record.tax_bill_link}")
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract account number from URL
            from urllib.parse import urlparse, parse_qs
            parsed_url = urlparse(record.tax_bill_link)
            params = parse_qs(parsed_url.query)
            if 'can' in params:
                extracted['account_number'] = params['can'][0]
            
            # Find all dollar amounts on the page
            all_amounts = re.findall(r'\$[\d,]+\.?\d*', response.text)
            
            if all_amounts:
                # The first significant amount is usually the current tax due
                # Filter out very large amounts (property values) and zeros
                tax_amounts = []
                for amount in all_amounts:
                    value = float(amount.replace('$', '').replace(',', ''))
                    if 100 < value < 50000:  # Reasonable tax range
                        tax_amounts.append(amount)
                
                if tax_amounts:
                    extracted['current_amount_due'] = tax_amounts[0]
                    extracted['total_amount_due'] = tax_amounts[0]
                    
                # Store all amounts for reference
                extracted['all_amounts_found'] = all_amounts[:10]
            
            # Extract property details from tables
            tables = soup.find_all('table')
            for table in tables:
                cells = table.find_all('td')
                for i, cell in enumerate(cells):
                    text = cell.get_text(strip=True)
                    
                    if 'Owner Name' in text and i + 1 < len(cells):
                        extracted['owner_name'] = cells[i + 1].get_text(strip=True)
                    elif 'Property Address' in text and i + 1 < len(cells):
                        extracted['property_address'] = cells[i + 1].get_text(strip=True)
                    elif 'Tax Year' in text and i + 1 < len(cells):
                        extracted['tax_year'] = cells[i + 1].get_text(strip=True)
            
            extracted['extraction_method'] = 'direct_http'
            
        except Exception as e:
            logger.error(f"Montgomery extraction failed: {e}")
            raise
        
        return extracted
    
    async def _safe_extract(self, page: Page, selector: str) -> Optional[str]:
        """Legacy method kept for compatibility"""
        return None


class HarrisCountyExtractor(ExtractionStrategy):
    """Extractor for Harris County, TX"""
    
    async def extract(self, record: PropertyTaxRecord, page: Page) -> Dict[str, Any]:
        extracted = {}
        
        try:
            await page.goto(record.tax_bill_link, wait_until='networkidle', timeout=self.timeout)
            
            # Wait for tax statement to load
            await page.wait_for_selector('body', timeout=self.timeout)
            
            # Extract based on steps
            steps = self.parse_extraction_steps(record.extraction_steps)
            
            for step in steps:
                if step['action'] == 'extract':
                    target = step['target'].lower()
                    
                    if 'final total amount due' in target:
                        value = await self._extract_amount(page, 'Final Total')
                        if value:
                            extracted['final_total_amount_due'] = value
                    
                    elif 'total current taxes due' in target:
                        value = await self._extract_amount(page, 'Current Taxes')
                        if value:
                            extracted['current_taxes_due'] = value
                    
                    elif 'due amount' in target:
                        value = await self._extract_amount(page, 'Amount Due')
                        if value:
                            extracted['amount_due'] = value
            
            # Try to extract additional fields
            extracted['property_address'] = await self._safe_extract(page, 'text=/Property.*Address/i + td')
            extracted['tax_year'] = await self._safe_extract(page, 'text=/Tax.*Year/i + td')
            
        except Exception as e:
            logger.error(f"Harris County extraction failed: {e}")
            raise
        
        return extracted
    
    async def _extract_amount(self, page: Page, keyword: str) -> Optional[str]:
        """Extract monetary amounts from the page"""
        try:
            # Try different selector patterns
            patterns = [
                f'text=/{keyword}/i',
                f'td:has-text("{keyword}")',
                f'*:has-text("{keyword}")'
            ]
            
            for pattern in patterns:
                elements = await page.query_selector_all(pattern)
                for element in elements:
                    parent = await element.query_selector('xpath=..')
                    if parent:
                        text = await parent.text_content()
                        # Extract dollar amounts
                        amounts = re.findall(r'\$[\d,]+\.?\d*', text)
                        if amounts:
                            return amounts[0]
        except:
            pass
        return None
    
    async def _safe_extract(self, page: Page, selector: str) -> Optional[str]:
        try:
            element = await page.query_selector(selector)
            if element:
                text = await element.text_content()
                return text.strip() if text else None
        except:
            return None


class GenericExtractor(ExtractionStrategy):
    """Generic extractor for unrecognized patterns"""
    
    async def extract(self, record: PropertyTaxRecord, page: Page) -> Dict[str, Any]:
        extracted = {}
        
        try:
            await page.goto(record.tax_bill_link, wait_until='networkidle', timeout=self.timeout)
            
            # Wait for content
            await page.wait_for_selector('body', timeout=self.timeout)
            
            # Try to extract common tax-related fields
            keywords = [
                'amount due', 'total due', 'tax due', 'current due',
                'balance', 'total tax', 'property tax', 'tax bill'
            ]
            
            for keyword in keywords:
                # Try to find elements containing these keywords
                elements = await page.query_selector_all(f'*:has-text("{keyword}")')
                
                for element in elements:
                    text = await element.text_content()
                    # Look for dollar amounts near keywords
                    amounts = re.findall(r'\$[\d,]+\.?\d*', text)
                    if amounts:
                        extracted[keyword.replace(' ', '_')] = amounts[0]
            
            # Extract page title
            title = await page.title()
            extracted['page_title'] = title
            
            # Get all text content for fallback parsing
            body_text = await page.text_content('body')
            extracted['raw_text_sample'] = body_text[:500] if body_text else None
            
        except Exception as e:
            logger.error(f"Generic extraction failed: {e}")
            raise
        
        return extracted


class PropertyTaxExtractor:
    """Main extractor orchestrator"""
    
    def __init__(self, headless: bool = True, max_concurrent: int = 3):
        self.headless = headless
        self.max_concurrent = max_concurrent
        self.extractors = {
            'maricopa': MaricopaExtractor(),
            'montgomery': MontgomeryExtractor(),
            'harris': HarrisCountyExtractor(),
            'generic': GenericExtractor()
        }
    
    def select_extractor(self, record: PropertyTaxRecord) -> ExtractionStrategy:
        """Select appropriate extractor based on jurisdiction"""
        jurisdiction = record.jurisdiction.lower() if record.jurisdiction else ''
        
        if 'maricopa' in jurisdiction:
            return self.extractors['maricopa']
        elif 'montgomery' in jurisdiction:
            return self.extractors['montgomery']
        elif 'harris' in jurisdiction:
            return self.extractors['harris']
        else:
            return self.extractors['generic']
    
    async def extract_single(self, record: PropertyTaxRecord, browser: Browser) -> PropertyTaxRecord:
        """Extract data for a single property record"""
        
        # Skip entities and sub-entities
        if record.property_type in ['entity', 'sub-entity']:
            record.extraction_status = 'skipped'
            record.extraction_error = 'Entity type - no extraction needed'
            return record
        
        # Skip if no valid link
        if not record.tax_bill_link or record.tax_bill_link == 'entity':
            record.extraction_status = 'skipped'
            record.extraction_error = 'No valid tax bill link'
            return record
        
        # Select appropriate extractor
        extractor = self.select_extractor(record)
        
        # Check if Montgomery County - use direct HTTP instead of browser
        if 'montgomery' in record.jurisdiction.lower():
            # Extract with retries for Montgomery using direct HTTP
            for attempt in range(extractor.retry_count):
                try:
                    logger.info(f"Extracting {record.property_name} via HTTP (Attempt {attempt + 1})")
                    
                    extracted_data = await extractor.extract(record, None)  # No page needed
                    
                    record.extracted_data = extracted_data
                    record.extraction_status = 'success'
                    record.extraction_timestamp = datetime.now().isoformat()
                    
                    logger.info(f"Successfully extracted: {record.property_name}")
                    return record
                    
                except Exception as e:
                    logger.warning(f"HTTP extraction error on attempt {attempt + 1} for {record.property_name}: {e}")
                    if attempt == extractor.retry_count - 1:
                        record.extraction_status = 'failed'
                        record.extraction_error = f"HTTP extraction failed after {extractor.retry_count} attempts: {str(e)}"
                    else:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
            
            return record
        
        # For non-Montgomery counties, use browser
        context = None
        page = None
        
        try:
            # Create browser context with retry logic
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = await context.new_page()
            
            # Extract with retries
            for attempt in range(extractor.retry_count):
                try:
                    logger.info(f"Extracting {record.property_name} (Attempt {attempt + 1})")
                    
                    extracted_data = await extractor.extract(record, page)
                    
                    record.extracted_data = extracted_data
                    record.extraction_status = 'success'
                    record.extraction_timestamp = datetime.now().isoformat()
                    
                    logger.info(f"Successfully extracted: {record.property_name}")
                    break
                    
                except PlaywrightTimeout as e:
                    logger.warning(f"Timeout on attempt {attempt + 1} for {record.property_name}")
                    if attempt == extractor.retry_count - 1:
                        record.extraction_status = 'failed'
                        record.extraction_error = f"Timeout after {extractor.retry_count} attempts"
                    else:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        
                except Exception as e:
                    logger.error(f"Error on attempt {attempt + 1}: {e}")
                    if attempt == extractor.retry_count - 1:
                        record.extraction_status = 'failed'
                        record.extraction_error = str(e)
                    else:
                        await asyncio.sleep(2 ** attempt)
        
        except Exception as e:
            logger.error(f"Browser context error: {e}")
            record.extraction_status = 'failed'
            record.extraction_error = f"Browser error: {str(e)}"
        
        finally:
            if page:
                await page.close()
            if context:
                await context.close()
        
        return record
    
    async def extract_batch(self, records: List[PropertyTaxRecord]) -> List[PropertyTaxRecord]:
        """Extract data for multiple records with concurrency control"""
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=['--disable-blink-features=AutomationControlled']
            )
            
            try:
                # Process in batches
                results = []
                
                for i in range(0, len(records), self.max_concurrent):
                    batch = records[i:i + self.max_concurrent]
                    
                    # Process batch concurrently
                    batch_tasks = [
                        self.extract_single(record, browser)
                        for record in batch
                    ]
                    
                    batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                    
                    # Handle results
                    for j, result in enumerate(batch_results):
                        if isinstance(result, Exception):
                            logger.error(f"Batch extraction error: {result}")
                            batch[j].extraction_status = 'failed'
                            batch[j].extraction_error = str(result)
                            results.append(batch[j])
                        else:
                            results.append(result)
                    
                    # Rate limiting between batches
                    if i + self.max_concurrent < len(records):
                        await asyncio.sleep(2)
                
                return results
                
            finally:
                await browser.close()

        


class CSVHandler:
    """Handle CSV reading and writing operations"""
    
    @staticmethod
    def read_csv(filepath: str) -> List[PropertyTaxRecord]:
        """Read property records from CSV"""
        records = []
        
        try:
            # Try different encodings to handle special characters
            encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
            content = None
            used_encoding = None
            
            for encoding in encodings:
                try:
                    with open(filepath, 'r', encoding=encoding) as f:
                        content = f.read()
                        used_encoding = encoding
                        break
                except UnicodeDecodeError:
                    continue
            
            if content is None:
                # If all encodings fail, try with error handling
                with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                    used_encoding = 'utf-8 with replacements'
            
            logger.info(f"Successfully read CSV with encoding: {used_encoding}")
            
            # Parse CSV from string
            import io
            reader = csv.DictReader(io.StringIO(content))
            
            for row in reader:
                record = PropertyTaxRecord(
                    property_id=row.get('Property ID', ''),
                    property_name=row.get('Property Name', ''),
                    jurisdiction=row.get('Jurisdiction', ''),
                    state=row.get('State', ''),
                    property_type=row.get('Property Type', ''),
                    close_date=row.get('Close Date'),
                    amount_due=row.get('Amount Due'),
                    previous_year_taxes=row.get('Previous Year Taxes'),
                    extraction_steps=row.get('Extraction Steps', ''),
                    acct_number=row.get('Acct Number'),
                    property_address=row.get('Property Address'),
                    next_due_date=row.get('Next Due Date'),
                    tax_bill_link=row.get('Tax Bill Link', ''),
                    parent_entity=row.get('Parent Entity')
                )
                records.append(record)
        
        except Exception as e:
            logger.error(f"Error reading CSV: {e}")
            raise
        
        return records
    
    @staticmethod
    def write_results(records: List[PropertyTaxRecord], output_file: str):
        """Write extraction results to CSV"""
        
        if not records:
            logger.warning("No records to write")
            return
        
        # Prepare fieldnames
        fieldnames = list(asdict(records[0]).keys())
        
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for record in records:
                    row = asdict(record)
                    # Convert extracted_data dict to JSON string for CSV storage
                    if row.get('extracted_data'):
                        row['extracted_data'] = json.dumps(row['extracted_data'])
                    writer.writerow(row)
            
            logger.info(f"Results written to {output_file}")
            
        except Exception as e:
            logger.error(f"Error writing results: {e}")
            raise
    
    @staticmethod
    def write_summary(records: List[PropertyTaxRecord], summary_file: str):
        """Write extraction summary"""
        
        summary = {
            'total_records': len(records),
            'successful': sum(1 for r in records if r.extraction_status == 'success'),
            'failed': sum(1 for r in records if r.extraction_status == 'failed'),
            'skipped': sum(1 for r in records if r.extraction_status == 'skipped'),
            'timestamp': datetime.now().isoformat()
        }
        
        # Group failures by error type
        error_types = {}
        for record in records:
            if record.extraction_status == 'failed' and record.extraction_error:
                error_type = record.extraction_error.split(':')[0]
                error_types[error_type] = error_types.get(error_type, 0) + 1
        
        summary['error_breakdown'] = error_types
        
        try:
            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2)
            
            logger.info(f"Summary written to {summary_file}")
            
        except Exception as e:
            logger.error(f"Error writing summary: {e}")


async def main():
    """Main execution function"""
    
    # Configuration
    input_csv = 'completed-proptax-data.csv'
    output_csv = 'extracted_tax_data.csv'
    summary_file = 'extraction_summary.json'
    
    # Read records
    csv_handler = CSVHandler()
    records = csv_handler.read_csv(input_csv)
    
    logger.info(f"Loaded {len(records)} records from {input_csv}")
    
    # Filter records that need extraction (exclude entities)
    records_to_extract = [
        r for r in records 
        if r.property_type not in ['entity', 'sub-entity'] 
        and r.tax_bill_link 
        and r.tax_bill_link != 'entity'
    ]
    
    logger.info(f"Found {len(records_to_extract)} records to extract")
    
    # Initialize extractor
    extractor = PropertyTaxExtractor(headless=True, max_concurrent=3)
    
    # Extract data
    extracted_records = await extractor.extract_batch(records_to_extract)
    
    # Combine with skipped records
    all_records = []
    for record in records:
        if record.property_type in ['entity', 'sub-entity'] or not record.tax_bill_link:
            record.extraction_status = 'skipped'
            all_records.append(record)
        else:
            # Find the extracted version
            extracted = next(
                (r for r in extracted_records if r.property_id == record.property_id),
                record
            )
            all_records.append(extracted)
    
    # Write results
    csv_handler.write_results(all_records, output_csv)
    csv_handler.write_summary(all_records, summary_file)
    
    # Print summary
    successful = sum(1 for r in all_records if r.extraction_status == 'success')
    failed = sum(1 for r in all_records if r.extraction_status == 'failed')
    skipped = sum(1 for r in all_records if r.extraction_status == 'skipped')
    
    print(f"\nExtraction Complete:")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")
    print(f"  Skipped: {skipped}")
    print(f"  Total: {len(all_records)}")


if __name__ == "__main__":
    asyncio.run(main())