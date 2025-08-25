#!/usr/bin/env python3
"""
MASTER PROPERTY TAX DATA EXTRACTOR
Comprehensive extraction system for all property tax jurisdictions
Includes all extraction strategies, utilities, and execution modes
"""

import asyncio
import csv
import io
import json
import logging
import re
import time
import pandas as pd
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Union
from urllib.parse import urljoin, urlparse, parse_qs
import sys
import argparse

from bs4 import BeautifulSoup
import requests
from playwright.async_api import async_playwright, Page, Browser, TimeoutError as PlaywrightTimeout

# ================================================================================
# CONFIGURATION
# ================================================================================

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('master_tax_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Extraction configuration
EXTRACTION_CONFIG = {
    'timeout': 30000,
    'retry_count': 3,
    'max_concurrent': 3,
    'headless': True,
    'rate_limit_delay': 2,
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

# ================================================================================
# DATA MODELS
# ================================================================================

@dataclass
class PropertyTaxRecord:
    """Comprehensive data model for property tax information"""
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
    extraction_method: Optional[str] = None  # 'http', 'playwright', 'selenium'
    extraction_duration: Optional[float] = None  # seconds

# ================================================================================
# BASE EXTRACTION STRATEGY
# ================================================================================

class ExtractionStrategy:
    """Base class for all extraction strategies"""
    
    def __init__(self, retry_count: int = None, timeout: int = None):
        self.retry_count = retry_count or EXTRACTION_CONFIG['retry_count']
        self.timeout = timeout or EXTRACTION_CONFIG['timeout']
    
    async def extract(self, record: PropertyTaxRecord, page: Page = None) -> Dict[str, Any]:
        """Extract data from the tax website"""
        raise NotImplementedError
    
    def parse_extraction_steps(self, steps: str) -> List[Dict[str, str]]:
        """Parse extraction steps from CSV format"""
        if not steps or steps == 'entity' or steps == 'sub-entity':
            return []
        
        step_pattern = r'\d+\.\s*'
        raw_steps = re.split(step_pattern, steps)
        parsed_steps = []
        
        for step in raw_steps:
            if step.strip():
                if 'Enter' in step and 'in' in step:
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
                    target = step.replace('Click', '').strip()
                    parsed_steps.append({
                        'action': 'click',
                        'target': target
                    })
                elif 'Direct Link' in step:
                    parsed_steps.append({
                        'action': 'navigate',
                        'url': 'direct'
                    })
                elif 'search' in step.lower():
                    parsed_steps.append({
                        'action': 'search',
                        'details': step
                    })
                else:
                    parsed_steps.append({
                        'action': 'extract',
                        'target': step.strip('"')
                    })
        
        return parsed_steps
    
    def extract_dollar_amounts(self, text: str) -> List[str]:
        """Extract all dollar amounts from text"""
        return re.findall(r'\$[\d,]+\.?\d*', text)
    
    def filter_tax_amounts(self, amounts: List[str], min_val: float = 100, max_val: float = 50000) -> List[str]:
        """Filter amounts to reasonable tax range"""
        filtered = []
        for amount in amounts:
            value = float(amount.replace('$', '').replace(',', ''))
            if min_val < value < max_val:
                filtered.append(amount)
        return filtered

# ================================================================================
# COUNTY-SPECIFIC EXTRACTORS
# ================================================================================

class MaricopaExtractor(ExtractionStrategy):
    """Extractor for Maricopa County, AZ - Complex JavaScript site with Selenium fallback"""
    
    async def extract(self, record: PropertyTaxRecord, page: Page) -> Dict[str, Any]:
        steps = self.parse_extraction_steps(record.extraction_steps)
        extracted = {'extraction_method': 'playwright_maricopa'}
        
        try:
            # Try Playwright first
            await page.goto(record.tax_bill_link, wait_until='networkidle', timeout=self.timeout)
            
            # Wait for the form to be fully loaded
            try:
                await page.wait_for_selector('#txtParcelNumBook', timeout=10000)
            except:
                # If form not found, might already be on results page
                logger.info("Parcel form not found, checking if already on results page")
            
            for step in steps:
                if step['action'] == 'fill' and 'Parcel Number' in step['field']:
                    parcel_number = step['value'] or record.acct_number
                    if not parcel_number:
                        logger.error("No parcel number found")
                        continue
                        
                    parts = parcel_number.split('-')
                    
                    if len(parts) >= 3:
                        # Fill form fields with better error handling
                        try:
                            await page.fill('#txtParcelNumBook', parts[0])
                            await page.fill('#txtParcelNumMap', parts[1])
                            
                            if len(parts) == 3:
                                item_part = parts[2]
                                split_part = ''
                                
                                # Handle letter suffix (e.g., 025A)
                                if item_part and item_part[-1].isalpha():
                                    split_part = item_part[-1]
                                    item_part = item_part[:-1]
                                
                                await page.fill('#txtParcelNumItem', item_part)
                                await page.fill('#txtParcelNumSplit', split_part)
                            elif len(parts) == 4:
                                await page.fill('#txtParcelNumItem', parts[2])
                                await page.fill('#txtParcelNumSplit', parts[3])
                            
                            # Try multiple search button selectors
                            search_selectors = [
                                'a.button:has-text("Search")',
                                'button:has-text("Search")',
                                'input[type="submit"][value*="Search"]',
                                '#btnSearch'
                            ]
                            
                            clicked = False
                            for selector in search_selectors:
                                try:
                                    search_button = await page.query_selector(selector)
                                    if search_button and await search_button.is_visible():
                                        await search_button.click()
                                        clicked = True
                                        break
                                except:
                                    continue
                            
                            if not clicked:
                                # Fallback to pressing Enter
                                await page.press('#txtParcelNumSplit', 'Enter')
                            
                            await page.wait_for_load_state('networkidle', timeout=15000)
                            await page.wait_for_timeout(2000)
                        except Exception as e:
                            logger.warning(f"Error filling form: {e}")
                        
                        # Click on parcel link in results
                        link_selectors = [
                            f'a:has-text("{parcel_number}")',
                            f'a[href*="{parcel_number}"]',
                            'table a:first-of-type',
                            'td a',
                            '.results a'
                        ]
                        
                        for selector in link_selectors:
                            try:
                                parcel_link = await page.query_selector(selector)
                                if parcel_link and await parcel_link.is_visible():
                                    await parcel_link.click()
                                    await page.wait_for_load_state('networkidle', timeout=15000)
                                    await page.wait_for_timeout(2000)
                                    break
                            except:
                                continue
            
            # Extract tax data
            dollar_elements = await page.query_selector_all('*:has-text("$")')
            
            for element in dollar_elements[:20]:
                try:
                    text = await element.text_content()
                    if text and len(text) < 500:
                        text_lower = text.lower()
                        
                        if 'total' in text_lower and 'due' in text_lower:
                            amounts = self.extract_dollar_amounts(text)
                            if amounts:
                                extracted['total_amount_due'] = amounts[-1]
                        
                        elif 'current' in text_lower and ('tax' in text_lower or 'due' in text_lower):
                            amounts = self.extract_dollar_amounts(text)
                            if amounts:
                                extracted['current_amount'] = amounts[0]
                        
                        elif 'balance' in text_lower:
                            amounts = self.extract_dollar_amounts(text)
                            if amounts:
                                extracted['balance'] = amounts[0]
                except:
                    continue
            
            extracted['final_url'] = page.url
            
        except Exception as e:
            logger.error(f"Maricopa extraction failed: {e}")
            raise
        
        return extracted


class MontgomeryExtractor(ExtractionStrategy):
    """Extractor for Montgomery County, TX - Direct HTTP requests"""
    
    async def extract(self, record: PropertyTaxRecord, page: Page = None) -> Dict[str, Any]:
        extracted = {'extraction_method': 'http_montgomery'}
        
        try:
            headers = {
                'User-Agent': EXTRACTION_CONFIG['user_agent'],
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            }
            
            response = requests.get(record.tax_bill_link, headers=headers, timeout=30)
            
            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code} for {record.tax_bill_link}")
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract account number from URL
            parsed_url = urlparse(record.tax_bill_link)
            params = parse_qs(parsed_url.query)
            if 'can' in params:
                extracted['account_number'] = params['can'][0]
            
            # Find tax amounts
            all_amounts = self.extract_dollar_amounts(response.text)
            tax_amounts = self.filter_tax_amounts(all_amounts)
            
            if tax_amounts:
                extracted['current_amount_due'] = tax_amounts[0]
                extracted['total_amount_due'] = tax_amounts[0]
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
            
        except Exception as e:
            logger.error(f"Montgomery extraction failed: {e}")
            raise
        
        return extracted


class HarrisCountyExtractor(ExtractionStrategy):
    """Extractor for Harris County, TX - Enhanced with better selectors"""
    
    async def extract(self, record: PropertyTaxRecord, page: Page) -> Dict[str, Any]:
        extracted = {'extraction_method': 'playwright_harris'}
        
        try:
            # Navigate to the tax statement URL
            await page.goto(record.tax_bill_link, wait_until='networkidle', timeout=self.timeout)
            
            # Wait for content to load with multiple fallback selectors
            content_loaded = False
            load_selectors = [
                'body',
                '.tax-statement',
                '#tax-details',
                'table',
                'div[class*="amount"]'
            ]
            
            for selector in load_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                    content_loaded = True
                    break
                except:
                    continue
            
            if not content_loaded:
                logger.warning("Content may not be fully loaded")
            
            # Additional wait for JavaScript rendering
            await page.wait_for_timeout(2000)
            
            steps = self.parse_extraction_steps(record.extraction_steps)
            
            # Process extraction steps
            for step in steps:
                if step['action'] == 'extract':
                    target = step['target'].lower()
                    
                    if 'final total amount due' in target or 'total amount due' in target:
                        # Try multiple selectors for final amount
                        amount_selectors = [
                            'td:has-text("Final Total Amount Due") + td',
                            'td:has-text("Total Amount Due") + td',
                            'span.total-amount',
                            'div.amount-due',
                            '.final-total',
                            'td.amount:last-of-type'
                        ]
                        
                        for selector in amount_selectors:
                            try:
                                element = await page.query_selector(selector)
                                if element:
                                    text = await element.text_content()
                                    amounts = self.extract_dollar_amounts(text)
                                    if amounts:
                                        # Validate it's a reasonable tax amount
                                        filtered = self.filter_tax_amounts(amounts)
                                        if filtered:
                                            extracted['final_total_amount_due'] = filtered[0]
                                            break
                            except:
                                continue
                    
                    elif 'current taxes' in target:
                        value = await self._extract_amount(page, 'Current Taxes')
                        if value:
                            extracted['current_taxes_due'] = value
            
            # Extract all dollar amounts as fallback
            if 'final_total_amount_due' not in extracted:
                all_text = await page.text_content('body')
                all_amounts = self.extract_dollar_amounts(all_text)
                
                # Look for keywords near amounts
                for i, amount in enumerate(all_amounts):
                    # Check context around the amount
                    amount_index = all_text.find(amount)
                    if amount_index > 0:
                        context = all_text[max(0, amount_index-100):amount_index+100].lower()
                        if any(word in context for word in ['total', 'due', 'final', 'amount due', 'pay']):
                            filtered = self.filter_tax_amounts([amount])
                            if filtered:
                                extracted['final_total_amount_due'] = filtered[0]
                                break
            
            # Extract property details with better selectors
            extracted['property_address'] = await self._safe_extract(page, 'text=/Property.*Address/i + td')
            if not extracted['property_address']:
                extracted['property_address'] = await self._safe_extract(page, 'td:has-text("Address") + td')
            
            extracted['tax_year'] = await self._safe_extract(page, 'text=/Tax.*Year/i + td')
            if not extracted['tax_year']:
                extracted['tax_year'] = await self._safe_extract(page, 'td:has-text("Year") + td')
            
            extracted['owner_name'] = await self._safe_extract(page, 'td:has-text("Owner") + td')
            
            # Validate we got actual data, not HTML
            if extracted.get('final_total_amount_due'):
                amount_str = str(extracted['final_total_amount_due'])
                if any(x in amount_str.lower() for x in ['<', '>', 'function', 'var', 'script']):
                    logger.error("Extracted HTML/JavaScript instead of data")
                    extracted['final_total_amount_due'] = None
                    extracted['extraction_error'] = "HTML/JS extracted instead of data"
            
        except Exception as e:
            logger.error(f"Harris County extraction failed: {e}")
            raise
        
        return extracted
    
    async def _extract_amount(self, page: Page, keyword: str) -> Optional[str]:
        try:
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
                        amounts = self.extract_dollar_amounts(text)
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
        extracted = {'extraction_method': 'playwright_generic'}
        
        try:
            await page.goto(record.tax_bill_link, wait_until='networkidle', timeout=self.timeout)
            await page.wait_for_selector('body', timeout=self.timeout)
            
            keywords = [
                'amount due', 'total due', 'tax due', 'current due',
                'balance', 'total tax', 'property tax', 'tax bill'
            ]
            
            for keyword in keywords:
                elements = await page.query_selector_all(f'*:has-text("{keyword}")')
                
                for element in elements:
                    text = await element.text_content()
                    amounts = self.extract_dollar_amounts(text)
                    if amounts:
                        extracted[keyword.replace(' ', '_')] = amounts[0]
            
            title = await page.title()
            extracted['page_title'] = title
            
            body_text = await page.text_content('body')
            extracted['raw_text_sample'] = body_text[:500] if body_text else None
            
        except Exception as e:
            logger.error(f"Generic extraction failed: {e}")
            raise
        
        return extracted


# ================================================================================
# NORTH CAROLINA COUNTY EXTRACTORS
# ================================================================================

class WayneCountyNCExtractor(ExtractionStrategy):
    """Extractor for Wayne County, NC - Direct link with property value filtering"""
    
    async def extract(self, record: PropertyTaxRecord, page: Page) -> Dict[str, Any]:
        extracted = {'extraction_method': 'playwright_wayne_nc'}
        
        try:
            await page.goto(record.tax_bill_link, wait_until='networkidle', timeout=self.timeout)
            await page.wait_for_timeout(2000)
            
            # Look for "Total Billed" which contains the tax amount
            selectors = [
                'td:has-text("Total Billed") + td',
                'td:has-text("Total Due") + td',
                'td:has-text("Amount Due") + td',
                'span.total-billed',
                'div.total-amount'
            ]
            
            for selector in selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        text = await element.text_content()
                        amounts = self.extract_dollar_amounts(text)
                        if amounts:
                            # Validate it's a tax amount, not property value
                            filtered = self.filter_tax_amounts(amounts, min_val=100, max_val=50000)
                            if filtered:
                                extracted['tax_amount'] = filtered[0]
                                break
                except:
                    continue
            
            # Also extract property details
            extracted['property_address'] = await self._safe_extract(page, 'td:has-text("Property Address") + td')
            extracted['owner_name'] = await self._safe_extract(page, 'td:has-text("Owner") + td')
            
        except Exception as e:
            logger.error(f"Wayne County NC extraction failed: {e}")
            raise
        
        return extracted
    
    async def _safe_extract(self, page: Page, selector: str) -> Optional[str]:
        try:
            element = await page.query_selector(selector)
            if element:
                text = await element.text_content()
                return text.strip() if text else None
        except:
            return None


class JohnstonCountyNCExtractor(ExtractionStrategy):
    """Extractor for Johnston County, NC - Search by business name"""
    
    async def extract(self, record: PropertyTaxRecord, page: Page) -> Dict[str, Any]:
        extracted = {'extraction_method': 'playwright_johnston_nc'}
        steps = self.parse_extraction_steps(record.extraction_steps)
        
        try:
            await page.goto(record.tax_bill_link, wait_until='networkidle', timeout=self.timeout)
            await page.wait_for_timeout(2000)
            
            # Process extraction steps
            for step in steps:
                if 'Search by Business Name' in str(step.get('details', '')):
                    # Select dropdown
                    await page.select_option('select[name="searchType"]', 'business')
                    await page.wait_for_timeout(500)
                
                elif step.get('action') == 'fill' and step.get('value') == 'BCS':
                    # Fill search field
                    await page.fill('input[name="searchValue"]', 'BCS')
                    await page.press('input[name="searchValue"]', 'Enter')
                    await page.wait_for_timeout(3000)
                
                elif 'first record' in str(step.get('details', '')):
                    # Extract from first row
                    element = await page.query_selector('table tr:nth-child(2) td.amount')
                    if element:
                        text = await element.text_content()
                        extracted['tax_amount'] = self.extract_dollar_amounts(text)[0] if self.extract_dollar_amounts(text) else None
                
                elif 'second record' in str(step.get('details', '')):
                    # Extract from second row
                    element = await page.query_selector('table tr:nth-child(3) td.amount')
                    if element:
                        text = await element.text_content()
                        extracted['tax_amount'] = self.extract_dollar_amounts(text)[0] if self.extract_dollar_amounts(text) else None
                
                elif 'third record' in str(step.get('details', '')):
                    # Extract from third row
                    element = await page.query_selector('table tr:nth-child(4) td.amount')
                    if element:
                        text = await element.text_content()
                        extracted['tax_amount'] = self.extract_dollar_amounts(text)[0] if self.extract_dollar_amounts(text) else None
            
        except Exception as e:
            logger.error(f"Johnston County NC extraction failed: {e}")
            raise
        
        return extracted


class CravenCountyNCExtractor(ExtractionStrategy):
    """Extractor for Craven County, NC - Account number search"""
    
    async def extract(self, record: PropertyTaxRecord, page: Page) -> Dict[str, Any]:
        extracted = {'extraction_method': 'playwright_craven_nc'}
        steps = self.parse_extraction_steps(record.extraction_steps)
        
        try:
            await page.goto(record.tax_bill_link, wait_until='networkidle', timeout=self.timeout)
            await page.wait_for_timeout(2000)
            
            # Extract account number from steps
            account_number = None
            for step in steps:
                if 'acct number' in str(step.get('details', '')):
                    # Extract number from string like "acct number 114834"
                    import re
                    match = re.search(r'\d+', str(step.get('details', '')))
                    if match:
                        account_number = match.group()
                        break
            
            if account_number:
                # Fill account number
                await page.fill('input[name="accountNumber"]', account_number)
                await page.press('input[name="accountNumber"]', 'Enter')
                await page.wait_for_timeout(3000)
                
                # Look for last row (year 2025)
                rows = await page.query_selector_all('table tr')
                if rows:
                    last_row = rows[-1]
                    amount_cell = await last_row.query_selector('td.amount')
                    if amount_cell:
                        text = await amount_cell.text_content()
                        amounts = self.extract_dollar_amounts(text)
                        if amounts:
                            filtered = self.filter_tax_amounts(amounts)
                            if filtered:
                                extracted['tax_amount'] = filtered[0]
            
        except Exception as e:
            logger.error(f"Craven County NC extraction failed: {e}")
            raise
        
        return extracted


class WilsonCountyNCExtractor(ExtractionStrategy):
    """Extractor for Wilson County, NC - Business search"""
    
    async def extract(self, record: PropertyTaxRecord, page: Page) -> Dict[str, Any]:
        extracted = {'extraction_method': 'playwright_wilson_nc'}
        steps = self.parse_extraction_steps(record.extraction_steps)
        
        try:
            await page.goto(record.tax_bill_link, wait_until='networkidle', timeout=self.timeout)
            await page.wait_for_timeout(2000)
            
            # Fill BCS in search
            await page.fill('input[name="search"]', 'BCS')
            await page.press('input[name="search"]', 'Enter')
            await page.wait_for_timeout(3000)
            
            # Click first account number in table
            account_link = await page.query_selector('table a:first-of-type')
            if account_link:
                await account_link.click()
                await page.wait_for_timeout(3000)
                
                # Extract tax amount from detail page
                selectors = [
                    'td:has-text("Amount Due") + td',
                    'td:has-text("Total Due") + td',
                    'span.tax-amount',
                    'div.amount-due'
                ]
                
                for selector in selectors:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            text = await element.text_content()
                            amounts = self.extract_dollar_amounts(text)
                            if amounts:
                                filtered = self.filter_tax_amounts(amounts)
                                if filtered:
                                    extracted['tax_amount'] = filtered[0]
                                    break
                    except:
                        continue
            
        except Exception as e:
            logger.error(f"Wilson County NC extraction failed: {e}")
            raise
        
        return extracted

# ================================================================================
# MAIN EXTRACTOR ORCHESTRATOR
# ================================================================================

class PropertyTaxExtractor:
    """Master orchestrator for all property tax extractions"""
    
    def __init__(self, headless: bool = None, max_concurrent: int = None):
        self.headless = headless if headless is not None else EXTRACTION_CONFIG['headless']
        self.max_concurrent = max_concurrent or EXTRACTION_CONFIG['max_concurrent']
        self.extractors = {
            'maricopa': MaricopaExtractor(),
            'montgomery': MontgomeryExtractor(),
            'harris': HarrisCountyExtractor(),
            # North Carolina county extractors
            'wayne_nc': WayneCountyNCExtractor(),
            'johnston_nc': JohnstonCountyNCExtractor(),
            'craven_nc': CravenCountyNCExtractor(),
            'wilson_nc': WilsonCountyNCExtractor(),
            'generic': GenericExtractor()
        }
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'start_time': None,
            'end_time': None
        }
    
    def select_extractor(self, record: PropertyTaxRecord) -> ExtractionStrategy:
        """Select appropriate extractor based on jurisdiction and URL"""
        jurisdiction = record.jurisdiction.lower() if record.jurisdiction else ''
        
        # Check URL patterns as additional hints
        url = record.tax_bill_link.lower() if record.tax_bill_link else ''
        
        # Texas counties
        if 'maricopa' in jurisdiction or 'treasurer.maricopa.gov' in url:
            return self.extractors['maricopa']
        elif 'montgomery' in jurisdiction or 'actweb.acttax.com' in url:
            return self.extractors['montgomery']
        elif 'harris' in jurisdiction or 'hctax.net' in url:
            return self.extractors['harris']
        
        # North Carolina counties
        elif 'wayne' in jurisdiction or 'waynegov.com' in url:
            return self.extractors['wayne_nc']
        elif 'johnston' in jurisdiction or 'johnstonnc.com' in url:
            return self.extractors['johnston_nc']
        elif 'craven' in jurisdiction or 'bttaxpayerportal.com' in url:
            return self.extractors['craven_nc']
        elif 'wilson' in jurisdiction or 'wilsonnc.devnetwedge.com' in url:
            return self.extractors['wilson_nc']
        
        # Additional NC counties can use appropriate extractors based on patterns
        elif 'vance' in jurisdiction:
            # Vance County likely uses similar pattern to Wayne
            return self.extractors['wayne_nc']
        elif 'moore' in jurisdiction or 'selfservice.moorecountync.gov' in url:
            # Moore County might need special handling but try generic
            return self.extractors['generic']
        elif 'beaufort' in jurisdiction or 'bcpwa.ncptscloud.com' in url:
            # Beaufort County likely uses similar pattern to Wayne
            return self.extractors['wayne_nc']
        
        else:
            return self.extractors['generic']
    
    async def extract_single(self, record: PropertyTaxRecord, browser: Browser = None) -> PropertyTaxRecord:
        """Extract data for a single property record"""
        start_time = time.time()
        
        # Skip entities and sub-entities
        if record.property_type in ['entity', 'sub-entity']:
            record.extraction_status = 'skipped'
            record.extraction_error = 'Entity type - no extraction needed'
            self.stats['skipped'] += 1
            return record
        
        # Skip if no valid link
        if not record.tax_bill_link or record.tax_bill_link == 'entity':
            record.extraction_status = 'skipped'
            record.extraction_error = 'No valid tax bill link'
            self.stats['skipped'] += 1
            return record
        
        # Select appropriate extractor
        extractor = self.select_extractor(record)
        
        # Check if Montgomery County - use direct HTTP
        if isinstance(extractor, MontgomeryExtractor):
            for attempt in range(extractor.retry_count):
                try:
                    logger.info(f"Extracting {record.property_name} via HTTP (Attempt {attempt + 1})")
                    
                    extracted_data = await extractor.extract(record, None)
                    
                    record.extracted_data = extracted_data
                    record.extraction_status = 'success'
                    record.extraction_timestamp = datetime.now().isoformat()
                    record.extraction_duration = time.time() - start_time
                    record.extraction_method = extracted_data.get('extraction_method', 'http')
                    
                    logger.info(f"Successfully extracted: {record.property_name} in {record.extraction_duration:.2f}s")
                    self.stats['successful'] += 1
                    return record
                    
                except Exception as e:
                    logger.warning(f"HTTP extraction error on attempt {attempt + 1}: {e}")
                    if attempt == extractor.retry_count - 1:
                        record.extraction_status = 'failed'
                        record.extraction_error = str(e)
                        self.stats['failed'] += 1
                    else:
                        await asyncio.sleep(2 ** attempt)
            
            return record
        
        # For browser-based extraction
        if not browser:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=self.headless,
                    args=['--disable-blink-features=AutomationControlled']
                )
                try:
                    return await self._extract_with_browser(record, extractor, browser, start_time)
                finally:
                    await browser.close()
        else:
            return await self._extract_with_browser(record, extractor, browser, start_time)
    
    async def _extract_with_browser(self, record: PropertyTaxRecord, extractor: ExtractionStrategy, 
                                   browser: Browser, start_time: float) -> PropertyTaxRecord:
        """Extract using browser automation"""
        context = None
        page = None
        
        try:
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=EXTRACTION_CONFIG['user_agent']
            )
            page = await context.new_page()
            
            for attempt in range(extractor.retry_count):
                try:
                    logger.info(f"Extracting {record.property_name} via browser (Attempt {attempt + 1})")
                    
                    extracted_data = await extractor.extract(record, page)
                    
                    record.extracted_data = extracted_data
                    record.extraction_status = 'success'
                    record.extraction_timestamp = datetime.now().isoformat()
                    record.extraction_duration = time.time() - start_time
                    record.extraction_method = extracted_data.get('extraction_method', 'playwright')
                    
                    logger.info(f"Successfully extracted: {record.property_name} in {record.extraction_duration:.2f}s")
                    self.stats['successful'] += 1
                    break
                    
                except PlaywrightTimeout as e:
                    logger.warning(f"Timeout on attempt {attempt + 1}")
                    if attempt == extractor.retry_count - 1:
                        record.extraction_status = 'failed'
                        record.extraction_error = f"Timeout after {extractor.retry_count} attempts"
                        self.stats['failed'] += 1
                    else:
                        await asyncio.sleep(2 ** attempt)
                        
                except Exception as e:
                    logger.error(f"Error on attempt {attempt + 1}: {e}")
                    if attempt == extractor.retry_count - 1:
                        record.extraction_status = 'failed'
                        record.extraction_error = str(e)
                        self.stats['failed'] += 1
                    else:
                        await asyncio.sleep(2 ** attempt)
        
        except Exception as e:
            logger.error(f"Browser context error: {e}")
            record.extraction_status = 'failed'
            record.extraction_error = f"Browser error: {str(e)}"
            self.stats['failed'] += 1
        
        finally:
            if page:
                await page.close()
            if context:
                await context.close()
        
        self.stats['total_processed'] += 1
        return record
    
    async def extract_batch(self, records: List[PropertyTaxRecord]) -> List[PropertyTaxRecord]:
        """Extract data for multiple records with concurrency control"""
        self.stats['start_time'] = datetime.now()
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=['--disable-blink-features=AutomationControlled']
            )
            
            try:
                results = []
                
                for i in range(0, len(records), self.max_concurrent):
                    batch = records[i:i + self.max_concurrent]
                    
                    batch_tasks = [
                        self.extract_single(record, browser)
                        for record in batch
                    ]
                    
                    batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                    
                    for j, result in enumerate(batch_results):
                        if isinstance(result, Exception):
                            logger.error(f"Batch extraction error: {result}")
                            batch[j].extraction_status = 'failed'
                            batch[j].extraction_error = str(result)
                            results.append(batch[j])
                            self.stats['failed'] += 1
                        else:
                            results.append(result)
                    
                    # Rate limiting between batches
                    if i + self.max_concurrent < len(records):
                        await asyncio.sleep(EXTRACTION_CONFIG['rate_limit_delay'])
                
                self.stats['end_time'] = datetime.now()
                return results
                
            finally:
                await browser.close()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get extraction statistics"""
        stats = self.stats.copy()
        if stats['start_time'] and stats['end_time']:
            duration = (stats['end_time'] - stats['start_time']).total_seconds()
            stats['duration_seconds'] = duration
            if stats['total_processed'] > 0:
                stats['avg_time_per_record'] = duration / stats['total_processed']
        return stats

# ================================================================================
# CSV HANDLING
# ================================================================================

class CSVHandler:
    """Enhanced CSV handling with multiple format support"""
    
    @staticmethod
    def read_csv(filepath: str) -> List[PropertyTaxRecord]:
        """Read property records from CSV with encoding detection"""
        records = []
        
        try:
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
                with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                    used_encoding = 'utf-8 with replacements'
            
            logger.info(f"Successfully read CSV with encoding: {used_encoding}")
            
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
        
        fieldnames = list(asdict(records[0]).keys())
        
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for record in records:
                    row = asdict(record)
                    if row.get('extracted_data'):
                        row['extracted_data'] = json.dumps(row['extracted_data'])
                    writer.writerow(row)
            
            logger.info(f"Results written to {output_file}")
            
        except Exception as e:
            logger.error(f"Error writing results: {e}")
            raise
    
    @staticmethod
    def write_summary(records: List[PropertyTaxRecord], summary_file: str, stats: Dict = None):
        """Write comprehensive extraction summary"""
        summary = {
            'total_records': len(records),
            'successful': sum(1 for r in records if r.extraction_status == 'success'),
            'failed': sum(1 for r in records if r.extraction_status == 'failed'),
            'skipped': sum(1 for r in records if r.extraction_status == 'skipped'),
            'timestamp': datetime.now().isoformat()
        }
        
        # Add extractor stats if provided
        if stats:
            summary['extraction_stats'] = stats
        
        # Group by jurisdiction
        jurisdiction_summary = {}
        for record in records:
            if record.jurisdiction:
                if record.jurisdiction not in jurisdiction_summary:
                    jurisdiction_summary[record.jurisdiction] = {
                        'total': 0, 'successful': 0, 'failed': 0, 'skipped': 0
                    }
                jurisdiction_summary[record.jurisdiction]['total'] += 1
                if record.extraction_status == 'success':
                    jurisdiction_summary[record.jurisdiction]['successful'] += 1
                elif record.extraction_status == 'failed':
                    jurisdiction_summary[record.jurisdiction]['failed'] += 1
                elif record.extraction_status == 'skipped':
                    jurisdiction_summary[record.jurisdiction]['skipped'] += 1
        
        summary['jurisdiction_breakdown'] = jurisdiction_summary
        
        # Group failures by error type
        error_types = {}
        for record in records:
            if record.extraction_status == 'failed' and record.extraction_error:
                error_type = record.extraction_error.split(':')[0]
                error_types[error_type] = error_types.get(error_type, 0) + 1
        
        summary['error_breakdown'] = error_types
        
        # Extraction method breakdown
        method_breakdown = {}
        for record in records:
            if record.extraction_method:
                method_breakdown[record.extraction_method] = method_breakdown.get(record.extraction_method, 0) + 1
        
        summary['method_breakdown'] = method_breakdown
        
        try:
            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2)
            
            logger.info(f"Summary written to {summary_file}")
            
        except Exception as e:
            logger.error(f"Error writing summary: {e}")
    
    @staticmethod
    def export_to_excel(records: List[PropertyTaxRecord], excel_file: str):
        """Export results to Excel with multiple sheets"""
        try:
            with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
                # Main results sheet
                df_main = pd.DataFrame([asdict(r) for r in records])
                if 'extracted_data' in df_main.columns:
                    df_main['extracted_data'] = df_main['extracted_data'].apply(
                        lambda x: json.dumps(x) if x else None
                    )
                df_main.to_excel(writer, sheet_name='All Results', index=False)
                
                # Successful extractions
                df_success = df_main[df_main['extraction_status'] == 'success']
                if not df_success.empty:
                    df_success.to_excel(writer, sheet_name='Successful', index=False)
                
                # Failed extractions
                df_failed = df_main[df_main['extraction_status'] == 'failed']
                if not df_failed.empty:
                    df_failed.to_excel(writer, sheet_name='Failed', index=False)
                
                # Summary statistics
                summary_data = {
                    'Metric': ['Total Records', 'Successful', 'Failed', 'Skipped'],
                    'Count': [
                        len(records),
                        sum(1 for r in records if r.extraction_status == 'success'),
                        sum(1 for r in records if r.extraction_status == 'failed'),
                        sum(1 for r in records if r.extraction_status == 'skipped')
                    ]
                }
                df_summary = pd.DataFrame(summary_data)
                df_summary.to_excel(writer, sheet_name='Summary', index=False)
            
            logger.info(f"Excel export completed: {excel_file}")
            
        except Exception as e:
            logger.error(f"Error exporting to Excel: {e}")

# ================================================================================
# SPECIALIZED EXTRACTION FUNCTIONS
# ================================================================================

async def extract_new_properties(input_csv: str = 'completed-proptax-data.csv') -> List[PropertyTaxRecord]:
    """Extract newly added property records (NC Fund, Montgomery Tracts, etc.)"""
    csv_handler = CSVHandler()
    all_records = csv_handler.read_csv(input_csv)
    
    new_records = []
    for record in all_records:
        if any([
            'BCS NC Fund Propco' in record.property_name,
            'BCS Montgomery LLC - Tract' in record.property_name,
            'Houston QSR Propco LLC - 3101 FM 528' in record.property_name,
            'OCV Pueblo II' in record.property_name
        ]):
            if (record.tax_bill_link and 
                record.tax_bill_link != 'entity' and 
                record.property_type not in ['entity', 'sub-entity']):
                new_records.append(record)
    
    logger.info(f"Found {len(new_records)} new properties to extract")
    
    print("\n" + "="*60)
    print("NEW PROPERTIES TO EXTRACT:")
    print("="*60)
    for i, record in enumerate(new_records, 1):
        print(f"{i}. {record.property_name[:60]}...")
        print(f"   Jurisdiction: {record.jurisdiction}")
        print(f"   Link: {record.tax_bill_link[:70]}...")
    
    extractor = PropertyTaxExtractor()
    extracted_records = await extractor.extract_batch(new_records)
    
    # Save results
    output_file = 'new_properties_extraction.csv'
    csv_handler.write_results(extracted_records, output_file)
    csv_handler.write_summary(extracted_records, 'new_properties_summary.json', extractor.get_stats())
    
    # Print results
    successful = sum(1 for r in extracted_records if r.extraction_status == 'success')
    failed = sum(1 for r in extracted_records if r.extraction_status == 'failed')
    
    print("\n" + "="*60)
    print("EXTRACTION COMPLETE")
    print("="*60)
    print(f"Total: {len(extracted_records)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    
    return extracted_records

async def extract_by_jurisdiction(jurisdiction: str, input_csv: str) -> List[PropertyTaxRecord]:
    """Extract all properties for a specific jurisdiction"""
    csv_handler = CSVHandler()
    all_records = csv_handler.read_csv(input_csv)
    
    jurisdiction_records = [
        r for r in all_records 
        if r.jurisdiction and jurisdiction.lower() in r.jurisdiction.lower()
        and r.property_type not in ['entity', 'sub-entity']
        and r.tax_bill_link and r.tax_bill_link != 'entity'
    ]
    
    logger.info(f"Found {len(jurisdiction_records)} properties in {jurisdiction}")
    
    extractor = PropertyTaxExtractor()
    extracted_records = await extractor.extract_batch(jurisdiction_records)
    
    output_file = f'{jurisdiction.lower()}_extraction.csv'
    csv_handler.write_results(extracted_records, output_file)
    csv_handler.write_summary(extracted_records, f'{jurisdiction.lower()}_summary.json', extractor.get_stats())
    
    return extracted_records

async def test_extraction(input_csv: str, limit: int = 5) -> List[PropertyTaxRecord]:
    """Test extraction with a limited number of records"""
    csv_handler = CSVHandler()
    all_records = csv_handler.read_csv(input_csv)
    
    test_records = [
        r for r in all_records[:limit]
        if r.property_type not in ['entity', 'sub-entity']
        and r.tax_bill_link and r.tax_bill_link != 'entity'
    ]
    
    logger.info(f"Testing extraction with {len(test_records)} records")
    
    extractor = PropertyTaxExtractor()
    extracted_records = await extractor.extract_batch(test_records)
    
    csv_handler.write_results(extracted_records, 'test_extraction.csv')
    csv_handler.write_summary(extracted_records, 'test_summary.json', extractor.get_stats())
    
    return extracted_records

# ================================================================================
# MAIN EXECUTION
# ================================================================================

async def main():
    """Main execution function with CLI arguments"""
    parser = argparse.ArgumentParser(description='Master Property Tax Data Extractor')
    parser.add_argument('--input', '-i', default='completed-proptax-data.csv',
                       help='Input CSV file path')
    parser.add_argument('--output', '-o', default='extracted_tax_data.csv',
                       help='Output CSV file path')
    parser.add_argument('--mode', '-m', choices=['all', 'new', 'test', 'jurisdiction'],
                       default='all', help='Extraction mode')
    parser.add_argument('--jurisdiction', '-j', help='Specific jurisdiction to extract')
    parser.add_argument('--limit', '-l', type=int, default=5,
                       help='Limit for test mode')
    parser.add_argument('--concurrent', '-c', type=int, default=3,
                       help='Max concurrent extractions')
    parser.add_argument('--excel', '-e', help='Export results to Excel file')
    parser.add_argument('--headless', action='store_true', default=True,
                       help='Run browser in headless mode')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug logging')
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Update global config
    EXTRACTION_CONFIG['max_concurrent'] = args.concurrent
    EXTRACTION_CONFIG['headless'] = args.headless
    
    print("\n" + "="*60)
    print("MASTER PROPERTY TAX DATA EXTRACTOR")
    print("="*60)
    print(f"Mode: {args.mode}")
    print(f"Input: {args.input}")
    print(f"Max Concurrent: {args.concurrent}")
    print(f"Headless: {args.headless}")
    print("="*60 + "\n")
    
    # Execute based on mode
    if args.mode == 'new':
        extracted_records = await extract_new_properties(args.input)
    elif args.mode == 'test':
        extracted_records = await test_extraction(args.input, args.limit)
    elif args.mode == 'jurisdiction':
        if not args.jurisdiction:
            print("Error: --jurisdiction required for jurisdiction mode")
            return
        extracted_records = await extract_by_jurisdiction(args.jurisdiction, args.input)
    else:  # mode == 'all'
        # Standard full extraction
        csv_handler = CSVHandler()
        records = csv_handler.read_csv(args.input)
        
        logger.info(f"Loaded {len(records)} records from {args.input}")
        
        records_to_extract = [
            r for r in records 
            if r.property_type not in ['entity', 'sub-entity'] 
            and r.tax_bill_link 
            and r.tax_bill_link != 'entity'
        ]
        
        logger.info(f"Found {len(records_to_extract)} records to extract")
        
        extractor = PropertyTaxExtractor(
            headless=args.headless,
            max_concurrent=args.concurrent
        )
        
        extracted_records = await extractor.extract_batch(records_to_extract)
        
        # Combine with skipped records
        all_records = []
        for record in records:
            if record.property_type in ['entity', 'sub-entity'] or not record.tax_bill_link:
                record.extraction_status = 'skipped'
                all_records.append(record)
            else:
                extracted = next(
                    (r for r in extracted_records if r.property_id == record.property_id),
                    record
                )
                all_records.append(extracted)
        
        # Write results
        csv_handler.write_results(all_records, args.output)
        csv_handler.write_summary(all_records, 'extraction_summary.json', extractor.get_stats())
        
        # Export to Excel if requested
        if args.excel:
            csv_handler.export_to_excel(all_records, args.excel)
        
        extracted_records = all_records
    
    # Print final summary
    successful = sum(1 for r in extracted_records if r.extraction_status == 'success')
    failed = sum(1 for r in extracted_records if r.extraction_status == 'failed')
    skipped = sum(1 for r in extracted_records if r.extraction_status == 'skipped')
    
    print(f"\n" + "="*60)
    print("EXTRACTION COMPLETE")
    print("="*60)
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")
    print(f"  Skipped: {skipped}")
    print(f"  Total: {len(extracted_records)}")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())