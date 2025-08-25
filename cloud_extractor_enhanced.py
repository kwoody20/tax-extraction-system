"""
Enhanced cloud-compatible tax extractor with browser automation support.
Combines HTTP requests for simple sites and Playwright for JavaScript-heavy sites.
Optimized for Railway/cloud deployments with proper browser handling.
"""

import asyncio
import requests
from bs4 import BeautifulSoup
import re
import time
import logging
from typing import Dict, Optional, Any, List
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import json

# Browser automation imports - optional for cloud deployment
try:
    from playwright.async_api import async_playwright, Page, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Page = None
    Browser = None
    logging.warning("Playwright not available - browser extraction disabled")

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logging.warning("Selenium not available - fallback browser extraction disabled")

logger = logging.getLogger(__name__)

class EnhancedCloudTaxExtractor:
    """
    Enhanced cloud-friendly tax extractor with browser automation support.
    Automatically selects the best extraction method for each jurisdiction.
    """
    
    # Jurisdiction configuration with extraction methods
    JURISDICTION_CONFIG = {
        # HTTP-only jurisdictions (work without browser)
        "Montgomery": {
            "name": "Montgomery County, TX",
            "method": "http",
            "confidence": "high",
            "url_pattern": "actweb.acttax.com"
        },
        "Fort Bend": {
            "name": "Fort Bend County, TX", 
            "method": "http",
            "confidence": "high",
            "url_pattern": "fortbendcountytx.gov"
        },
        "Chambers": {
            "name": "Chambers County, TX",
            "method": "http",
            "confidence": "medium",
            "url_pattern": "co.chambers.tx.us"
        },
        "Galveston": {
            "name": "Galveston County, TX",
            "method": "http",
            "confidence": "medium",
            "url_pattern": "galvestoncountytx.gov"
        },
        "Aldine ISD": {
            "name": "Aldine ISD, TX",
            "method": "http",
            "confidence": "high",
            "url_pattern": "tax.aldine.k12.tx.us"
        },
        "Goose Creek ISD": {
            "name": "Goose Creek ISD, TX",
            "method": "http",
            "confidence": "high",
            "url_pattern": "tax.gccisd.net"
        },
        
        # Browser-required jurisdictions
        "Maricopa": {
            "name": "Maricopa County, AZ",
            "method": "browser",
            "confidence": "high",
            "url_pattern": "treasurer.maricopa.gov",
            "browser_type": "playwright"  # Preferred
        },
        "Harris": {
            "name": "Harris County, TX",
            "method": "browser",
            "confidence": "high",
            "url_pattern": "hctax.net",
            "browser_type": "playwright"
        },
        "Wayne": {
            "name": "Wayne County, NC",
            "method": "browser",
            "confidence": "medium",
            "url_pattern": "waynegov.com",
            "browser_type": "selenium"  # Fallback
        },
        "Johnston": {
            "name": "Johnston County, NC",
            "method": "browser",
            "confidence": "medium",
            "url_pattern": "johnstonnc.com",
            "browser_type": "selenium"
        },
        "Orleans": {
            "name": "Orleans Parish, LA",
            "method": "browser",
            "confidence": "medium",
            "url_pattern": "nola.gov",
            "browser_type": "playwright"
        },
        "Miami": {
            "name": "Miami-Dade County, FL",
            "method": "browser",
            "confidence": "medium",
            "url_pattern": "miamidade.gov",
            "browser_type": "playwright"
        }
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.last_request_time = 0
        self.rate_limit_seconds = 1
        self.browser = None
        self.playwright = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup browser resources"""
        await self.cleanup()
        
    async def cleanup(self):
        """Clean up browser resources"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    def _rate_limit(self):
        """Enforce rate limiting"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_seconds:
            time.sleep(self.rate_limit_seconds - elapsed)
        self.last_request_time = time.time()
    
    def _identify_jurisdiction(self, property_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Identify jurisdiction and return its configuration"""
        jurisdiction = property_data.get("jurisdiction", "")
        tax_bill_link = property_data.get("tax_bill_link", "")
        
        # Check jurisdiction name
        for key, config in self.JURISDICTION_CONFIG.items():
            if key.lower() in jurisdiction.lower():
                return config
                
        # Check URL pattern as fallback
        for key, config in self.JURISDICTION_CONFIG.items():
            if config.get("url_pattern") and config["url_pattern"] in tax_bill_link:
                return config
                
        return None
    
    async def extract(self, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main extraction method - automatically selects HTTP or browser method.
        
        Args:
            property_data: Dict with jurisdiction, tax_bill_link, account_number, etc.
            
        Returns:
            Dict with extraction results
        """
        start_time = time.time()
        jurisdiction_config = self._identify_jurisdiction(property_data)
        
        if not jurisdiction_config:
            return {
                "success": False,
                "error": f"Unsupported jurisdiction: {property_data.get('jurisdiction')}",
                "method": "none",
                "duration": time.time() - start_time
            }
        
        extraction_method = jurisdiction_config["method"]
        
        try:
            if extraction_method == "http":
                result = await self._extract_http(property_data, jurisdiction_config)
            elif extraction_method == "browser":
                if PLAYWRIGHT_AVAILABLE and jurisdiction_config.get("browser_type") == "playwright":
                    result = await self._extract_playwright(property_data, jurisdiction_config)
                elif SELENIUM_AVAILABLE:
                    result = await self._extract_selenium(property_data, jurisdiction_config)
                else:
                    result = {
                        "success": False,
                        "error": "Browser automation not available in this environment"
                    }
            else:
                result = {
                    "success": False,
                    "error": f"Unknown extraction method: {extraction_method}"
                }
                
        except Exception as e:
            logger.error(f"Extraction failed for {property_data.get('jurisdiction')}: {e}")
            result = {
                "success": False,
                "error": str(e)
            }
        
        result["method"] = extraction_method
        result["duration"] = time.time() - start_time
        result["timestamp"] = datetime.utcnow().isoformat()
        result["jurisdiction"] = jurisdiction_config["name"]
        
        return result
    
    async def _extract_http(self, property_data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """Extract using simple HTTP requests"""
        self._rate_limit()
        
        tax_bill_link = property_data.get("tax_bill_link", "")
        account_number = property_data.get("account_number")
        
        # Special handling for Montgomery County
        if "montgomery" in config["name"].lower():
            return await self._extract_montgomery(tax_bill_link, account_number)
        
        # Special handling for Aldine ISD
        if "aldine" in config["name"].lower():
            return await self._extract_aldine(tax_bill_link)
        
        # Generic HTTP extraction
        try:
            response = self.session.get(tax_bill_link, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try common patterns for tax amounts
            amount_patterns = [
                r'amount\s*due[:\s]*\$?([\d,]+\.?\d*)',
                r'total\s*due[:\s]*\$?([\d,]+\.?\d*)',
                r'balance[:\s]*\$?([\d,]+\.?\d*)',
                r'current\s*amount[:\s]*\$?([\d,]+\.?\d*)'
            ]
            
            text = soup.get_text().lower()
            amount_due = None
            
            for pattern in amount_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    amount_str = match.group(1).replace(',', '')
                    try:
                        amount_due = float(amount_str)
                        break
                    except:
                        pass
            
            return {
                "success": bool(amount_due is not None),
                "amount_due": amount_due,
                "raw_response": response.text[:1000]  # First 1000 chars for debugging
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _extract_montgomery(self, url: str, account_number: str) -> Dict[str, Any]:
        """Special extraction for Montgomery County, TX"""
        try:
            # Montgomery uses direct URL with account number
            if account_number and 'can=' not in url:
                url = f"{url}?can={account_number}&ownerno=0"
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for specific Montgomery County patterns
            amount_due = None
            
            # Try to find "Current Amount Due" in table
            for td in soup.find_all('td'):
                if 'current amount due' in td.get_text().lower():
                    next_td = td.find_next_sibling('td')
                    if next_td:
                        amount_text = next_td.get_text().strip()
                        amount_text = re.sub(r'[^\d.]', '', amount_text)
                        try:
                            amount_due = float(amount_text)
                        except:
                            pass
            
            return {
                "success": bool(amount_due is not None),
                "amount_due": amount_due,
                "county": "Montgomery County, TX"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _extract_aldine(self, url: str) -> Dict[str, Any]:
        """Special extraction for Aldine ISD"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for "Due Amount" pattern specific to Aldine
            amount_due = None
            
            for elem in soup.find_all(['td', 'div', 'span']):
                if 'due amount' in elem.get_text().lower():
                    # Try to find amount in same element or next sibling
                    text = elem.get_text()
                    match = re.search(r'\$?([\d,]+\.?\d*)', text)
                    if match:
                        amount_str = match.group(1).replace(',', '')
                        try:
                            amount_due = float(amount_str)
                            break
                        except:
                            pass
            
            return {
                "success": bool(amount_due is not None),
                "amount_due": amount_due,
                "district": "Aldine ISD"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _extract_playwright(self, property_data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """Extract using Playwright for JavaScript-heavy sites"""
        if not PLAYWRIGHT_AVAILABLE:
            return {"success": False, "error": "Playwright not available"}
        
        jurisdiction = config["name"]
        
        try:
            if not self.playwright:
                self.playwright = await async_playwright().start()
                self.browser = await self.playwright.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
            
            page = await self.browser.new_page()
            await page.goto(property_data["tax_bill_link"], wait_until="networkidle")
            
            # Jurisdiction-specific extraction logic
            if "maricopa" in jurisdiction.lower():
                return await self._extract_maricopa_playwright(page, property_data)
            elif "harris" in jurisdiction.lower():
                return await self._extract_harris_playwright(page, property_data)
            elif "orleans" in jurisdiction.lower():
                return await self._extract_orleans_playwright(page, property_data)
            elif "miami" in jurisdiction.lower():
                return await self._extract_miami_playwright(page, property_data)
            else:
                # Generic browser extraction
                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')
                
                # Try to find amount due
                amount_patterns = [
                    r'amount\s*due[:\s]*\$?([\d,]+\.?\d*)',
                    r'total\s*due[:\s]*\$?([\d,]+\.?\d*)',
                    r'balance[:\s]*\$?([\d,]+\.?\d*)'
                ]
                
                text = soup.get_text().lower()
                amount_due = None
                
                for pattern in amount_patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        amount_str = match.group(1).replace(',', '')
                        try:
                            amount_due = float(amount_str)
                            break
                        except:
                            pass
                
                return {
                    "success": bool(amount_due is not None),
                    "amount_due": amount_due
                }
                
        except Exception as e:
            logger.error(f"Playwright extraction failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            if 'page' in locals():
                await page.close()
    
    async def _extract_maricopa_playwright(self, page: Page, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract Maricopa County using Playwright"""
        try:
            account_number = property_data.get("account_number", "")
            
            # Fill in parcel number
            await page.fill('input[name="parcel"]', account_number)
            await page.click('button[type="submit"]')
            
            # Wait for results
            await page.wait_for_selector('.tax-amount', timeout=10000)
            
            # Extract amount
            amount_elem = await page.query_selector('.tax-amount')
            if amount_elem:
                amount_text = await amount_elem.text_content()
                amount_text = re.sub(r'[^\d.]', '', amount_text)
                amount_due = float(amount_text) if amount_text else None
                
                return {
                    "success": True,
                    "amount_due": amount_due,
                    "county": "Maricopa County, AZ"
                }
            
            return {"success": False, "error": "Could not find tax amount"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _extract_harris_playwright(self, page: Page, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract Harris County using Playwright"""
        try:
            # Harris County specific logic
            await page.wait_for_selector('.amount-due', timeout=10000)
            
            amount_elem = await page.query_selector('.amount-due')
            if amount_elem:
                amount_text = await amount_elem.text_content()
                amount_text = re.sub(r'[^\d.]', '', amount_text)
                amount_due = float(amount_text) if amount_text else None
                
                return {
                    "success": True,
                    "amount_due": amount_due,
                    "county": "Harris County, TX"
                }
            
            return {"success": False, "error": "Could not find tax amount"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _extract_orleans_playwright(self, page: Page, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract Orleans Parish using Playwright"""
        try:
            # Orleans Parish specific logic
            await page.wait_for_selector('[data-tax-amount]', timeout=10000)
            
            amount_elem = await page.query_selector('[data-tax-amount]')
            if amount_elem:
                amount_text = await amount_elem.get_attribute('data-tax-amount')
                amount_due = float(amount_text) if amount_text else None
                
                return {
                    "success": True,
                    "amount_due": amount_due,
                    "parish": "Orleans Parish, LA"
                }
            
            return {"success": False, "error": "Could not find tax amount"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _extract_miami_playwright(self, page: Page, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract Miami-Dade County using Playwright"""
        try:
            # Miami-Dade specific logic
            await page.wait_for_selector('.tax-bill-amount', timeout=10000)
            
            amount_elem = await page.query_selector('.tax-bill-amount')
            if amount_elem:
                amount_text = await amount_elem.text_content()
                amount_text = re.sub(r'[^\d.]', '', amount_text)
                amount_due = float(amount_text) if amount_text else None
                
                return {
                    "success": True,
                    "amount_due": amount_due,
                    "county": "Miami-Dade County, FL"
                }
            
            return {"success": False, "error": "Could not find tax amount"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _extract_selenium(self, property_data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback extraction using Selenium"""
        if not SELENIUM_AVAILABLE:
            return {"success": False, "error": "Selenium not available"}
        
        # Selenium implementation for NC counties
        # This would be similar to playwright but using Selenium API
        return {"success": False, "error": "Selenium extraction not fully implemented"}
    
    def get_supported_jurisdictions(self) -> List[str]:
        """Get list of all supported jurisdictions"""
        return list(self.JURISDICTION_CONFIG.keys())
    
    def get_browser_required_jurisdictions(self) -> List[str]:
        """Get list of jurisdictions that require browser automation"""
        return [k for k, v in self.JURISDICTION_CONFIG.items() if v["method"] == "browser"]
    
    def get_http_only_jurisdictions(self) -> List[str]:
        """Get list of jurisdictions that work with HTTP only"""
        return [k for k, v in self.JURISDICTION_CONFIG.items() if v["method"] == "http"]

# Convenience function for synchronous usage
def extract_tax_data(property_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synchronous wrapper for tax extraction.
    
    Args:
        property_data: Dict with jurisdiction, tax_bill_link, account_number, etc.
        
    Returns:
        Dict with extraction results
    """
    async def _extract():
        async with EnhancedCloudTaxExtractor() as extractor:
            return await extractor.extract(property_data)
    
    return asyncio.run(_extract())

# Test function
if __name__ == "__main__":
    # Test with a Montgomery County property
    test_property = {
        "jurisdiction": "Montgomery",
        "tax_bill_link": "https://actweb.acttax.com/act_webdev/montgomery/showdetail2.jsp",
        "account_number": "0003510100300"
    }
    
    result = extract_tax_data(test_property)
    print(json.dumps(result, indent=2))