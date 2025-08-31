"""
Local Extraction Suite with Supabase Sync
Handles complex jurisdictions that require Playwright/Selenium
Syncs results directly to Supabase without needing dashboard
"""

import asyncio
import sys
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client
import logging
from dataclasses import dataclass, asdict
import json

# Try importing MASTER_TAX_EXTRACTOR components
try:
    from playwright.async_api import async_playwright, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("⚠️ Playwright not installed. Run: pip install playwright && playwright install chromium")

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("⚠️ Selenium not installed. Run: pip install selenium")

load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://klscgjbachumeojhxyno.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

if not SUPABASE_KEY:
    # Try loading from .env
    with open('.env', 'r') as f:
        for line in f:
            if 'SUPABASE_SERVICE_ROLE_KEY=' in line:
                SUPABASE_KEY = line.split('=', 1)[1].strip().strip('"').strip("'")
                break
            elif 'SUPABASE_KEY=' in line and 'SERVICE' not in line:
                SUPABASE_KEY = line.split('=', 1)[1].strip().strip('"').strip("'")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('local_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class ExtractionResult:
    """Result from extraction attempt"""
    property_id: str
    property_name: str
    jurisdiction: str
    success: bool
    tax_amount: Optional[float] = None
    property_address: Optional[str] = None
    account_number: Optional[str] = None
    error_message: Optional[str] = None
    extraction_method: str = "unknown"
    extraction_date: str = ""
    
    def __post_init__(self):
        if not self.extraction_date:
            self.extraction_date = datetime.now().isoformat()

class LocalExtractionSuite:
    """
    Local extraction suite for complex jurisdictions
    Handles Playwright/Selenium extractions and syncs to Supabase
    """
    
    # Jurisdictions that need browser automation
    COMPLEX_JURISDICTIONS = {
        "Harris": {"method": "playwright", "confidence": "high"},
        "Maricopa": {"method": "playwright", "confidence": "high"},
        "Wayne": {"method": "playwright", "confidence": "medium"},
        "Johnston": {"method": "selenium", "confidence": "medium"},
        "Craven": {"method": "selenium", "confidence": "medium"},
        "Wilson": {"method": "selenium", "confidence": "medium"},
        "Miami-Dade": {"method": "playwright", "confidence": "low"},
        "Travis": {"method": "playwright", "confidence": "low"},
    }
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.results: List[ExtractionResult] = []
        self.browser = None
        self.playwright = None
        
    async def initialize_playwright(self):
        """Initialize Playwright browser"""
        if not PLAYWRIGHT_AVAILABLE:
            logger.error("Playwright not available")
            return False
            
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=['--disable-blink-features=AutomationControlled']
            )
            logger.info("Playwright browser initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Playwright: {e}")
            return False
    
    async def cleanup_playwright(self):
        """Clean up Playwright resources"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    def get_selenium_driver(self):
        """Get Selenium Chrome driver"""
        if not SELENIUM_AVAILABLE:
            logger.error("Selenium not available")
            return None
            
        try:
            options = Options()
            if self.headless:
                options.add_argument('--headless')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
            driver = webdriver.Chrome(options=options)
            return driver
        except Exception as e:
            logger.error(f"Failed to create Selenium driver: {e}")
            return None
    
    async def extract_with_playwright(self, property_data: Dict[str, Any]) -> ExtractionResult:
        """Extract using Playwright for JavaScript-heavy sites"""
        if not self.browser:
            await self.initialize_playwright()
            
        if not self.browser:
            return ExtractionResult(
                property_id=property_data['id'],
                property_name=property_data['property_name'],
                jurisdiction=property_data['jurisdiction'],
                success=False,
                error_message="Playwright not available",
                extraction_method="playwright"
            )
        
        page = await self.browser.new_page()
        
        try:
            url = property_data['tax_bill_link']
            jurisdiction = property_data['jurisdiction']
            
            # Navigate to page
            await page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Jurisdiction-specific extraction logic
            tax_amount = None
            property_address = None
            
            if "harris" in jurisdiction.lower():
                # Harris County specific
                await page.wait_for_selector('.tax-amount, .amount-due', timeout=10000)
                tax_element = await page.query_selector('.tax-amount, .amount-due')
                if tax_element:
                    tax_text = await tax_element.inner_text()
                    # Extract number from text
                    import re
                    match = re.search(r'[\d,]+\.?\d*', tax_text)
                    if match:
                        tax_amount = float(match.group().replace(',', ''))
                        
            elif "maricopa" in jurisdiction.lower():
                # Maricopa County - needs form submission
                if property_data.get('account_number'):
                    # Enter parcel number
                    await page.fill('#parcelNumber', property_data['account_number'])
                    await page.click('#searchButton')
                    await page.wait_for_selector('.tax-info', timeout=10000)
                    
                    tax_element = await page.query_selector('.total-due')
                    if tax_element:
                        tax_text = await tax_element.inner_text()
                        import re
                        match = re.search(r'[\d,]+\.?\d*', tax_text)
                        if match:
                            tax_amount = float(match.group().replace(',', ''))
            
            # Generic extraction for other jurisdictions
            else:
                # Try common selectors
                selectors = [
                    '.tax-amount', '.amount-due', '.total-due',
                    '#taxAmount', '#amountDue', '#totalDue',
                    '[class*="tax"]', '[class*="amount"]', '[class*="due"]'
                ]
                
                for selector in selectors:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            text = await element.inner_text()
                            import re
                            match = re.search(r'[\d,]+\.?\d*', text)
                            if match:
                                tax_amount = float(match.group().replace(',', ''))
                                break
                    except:
                        continue
            
            await page.close()
            
            return ExtractionResult(
                property_id=property_data['id'],
                property_name=property_data['property_name'],
                jurisdiction=jurisdiction,
                success=True if tax_amount is not None else False,
                tax_amount=tax_amount,
                property_address=property_address,
                account_number=property_data.get('account_number'),
                extraction_method="playwright"
            )
            
        except Exception as e:
            await page.close()
            logger.error(f"Playwright extraction error: {e}")
            return ExtractionResult(
                property_id=property_data['id'],
                property_name=property_data['property_name'],
                jurisdiction=property_data['jurisdiction'],
                success=False,
                error_message=str(e),
                extraction_method="playwright"
            )
    
    def extract_with_selenium(self, property_data: Dict[str, Any]) -> ExtractionResult:
        """Extract using Selenium"""
        driver = self.get_selenium_driver()
        if not driver:
            return ExtractionResult(
                property_id=property_data['id'],
                property_name=property_data['property_name'],
                jurisdiction=property_data['jurisdiction'],
                success=False,
                error_message="Selenium not available",
                extraction_method="selenium"
            )
        
        try:
            url = property_data['tax_bill_link']
            jurisdiction = property_data['jurisdiction']
            
            driver.get(url)
            
            # Wait for page to load
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.common.by import By
            
            wait = WebDriverWait(driver, 10)
            
            tax_amount = None
            
            # Try to find tax amount
            possible_selectors = [
                (By.CLASS_NAME, 'tax-amount'),
                (By.CLASS_NAME, 'amount-due'),
                (By.ID, 'taxAmount'),
                (By.XPATH, '//*[contains(text(), "Amount Due")]/../*'),
                (By.XPATH, '//*[contains(text(), "Total Due")]/../*'),
            ]
            
            for by, selector in possible_selectors:
                try:
                    element = wait.until(EC.presence_of_element_located((by, selector)))
                    if element:
                        text = element.text
                        import re
                        match = re.search(r'[\d,]+\.?\d*', text)
                        if match:
                            tax_amount = float(match.group().replace(',', ''))
                            break
                except:
                    continue
            
            driver.quit()
            
            return ExtractionResult(
                property_id=property_data['id'],
                property_name=property_data['property_name'],
                jurisdiction=jurisdiction,
                success=True if tax_amount is not None else False,
                tax_amount=tax_amount,
                account_number=property_data.get('account_number'),
                extraction_method="selenium"
            )
            
        except Exception as e:
            driver.quit()
            logger.error(f"Selenium extraction error: {e}")
            return ExtractionResult(
                property_id=property_data['id'],
                property_name=property_data['property_name'],
                jurisdiction=property_data['jurisdiction'],
                success=False,
                error_message=str(e),
                extraction_method="selenium"
            )
    
    async def extract_property(self, property_data: Dict[str, Any]) -> ExtractionResult:
        """Extract single property based on jurisdiction requirements"""
        jurisdiction = property_data.get('jurisdiction', '')
        
        # Check if this jurisdiction needs browser automation
        needs_browser = False
        method = "http"
        
        for complex_jur in self.COMPLEX_JURISDICTIONS:
            if complex_jur.lower() in jurisdiction.lower():
                needs_browser = True
                method = self.COMPLEX_JURISDICTIONS[complex_jur]["method"]
                break
        
        if not needs_browser:
            # This jurisdiction can use simple HTTP (already handled by cloud)
            return ExtractionResult(
                property_id=property_data['id'],
                property_name=property_data['property_name'],
                jurisdiction=jurisdiction,
                success=False,
                error_message="Use cloud extraction for this jurisdiction",
                extraction_method="http"
            )
        
        # Use appropriate browser automation
        if method == "playwright":
            return await self.extract_with_playwright(property_data)
        elif method == "selenium":
            return self.extract_with_selenium(property_data)
        else:
            return ExtractionResult(
                property_id=property_data['id'],
                property_name=property_data['property_name'],
                jurisdiction=jurisdiction,
                success=False,
                error_message=f"Unknown extraction method: {method}",
                extraction_method=method
            )
    
    def sync_to_supabase(self, result: ExtractionResult) -> bool:
        """Sync extraction result to Supabase"""
        try:
            # Update property record
            if result.success:
                update_data = {}
                if result.tax_amount is not None:
                    update_data['amount_due'] = result.tax_amount
                if result.property_address:
                    update_data['property_address'] = result.property_address
                if result.account_number:
                    update_data['account_number'] = result.account_number
                
                if update_data:
                    update_data['updated_at'] = datetime.now().isoformat()
                    
                    response = supabase.table('properties').update(
                        update_data
                    ).eq('id', result.property_id).execute()
                    
                    logger.info(f"✅ Synced {result.property_name}: ${result.tax_amount}")
                    return True
            
            # Log failed extraction
            extraction_record = {
                'property_id': result.property_id,
                'extraction_status': 'success' if result.success else 'failed',
                'extraction_date': result.extraction_date,
                'extraction_method': result.extraction_method,
                'error_message': result.error_message
            }
            
            if result.tax_amount is not None:
                extraction_record['tax_amount'] = result.tax_amount
            
            # Try to insert into tax_extractions table
            try:
                supabase.table('tax_extractions').insert(extraction_record).execute()
            except:
                # Table might not exist
                pass
            
            return result.success
            
        except Exception as e:
            logger.error(f"Failed to sync to Supabase: {e}")
            return False
    
    async def run_batch_extraction(self, limit: int = 10):
        """Run extraction for properties needing it"""
        print("\n" + "="*60)
        print("LOCAL EXTRACTION SUITE FOR COMPLEX JURISDICTIONS")
        print("="*60)
        
        # Get properties that need extraction
        try:
            # Get properties with complex jurisdictions
            response = supabase.table('properties').select('*').execute()
            all_properties = response.data
            
            # Filter for complex jurisdictions that need extraction
            properties_to_extract = []
            for prop in all_properties:
                jurisdiction = prop.get('jurisdiction', '')
                amount_due = prop.get('amount_due')
                
                # Check if it's a complex jurisdiction and needs extraction
                for complex_jur in self.COMPLEX_JURISDICTIONS:
                    if complex_jur.lower() in jurisdiction.lower():
                        if amount_due is None or amount_due == 0:
                            properties_to_extract.append(prop)
                            break
                
                if len(properties_to_extract) >= limit:
                    break
            
            if not properties_to_extract:
                print("✅ No properties need extraction with browser automation")
                return
            
            print(f"\n📋 Found {len(properties_to_extract)} properties needing browser extraction")
            print("\nProperties to process:")
            for prop in properties_to_extract:
                print(f"  • {prop['property_name'][:50]} - {prop['jurisdiction']}")
            
            print("\n" + "-"*60)
            print("Starting extraction...\n")
            
            # Process each property
            success_count = 0
            fail_count = 0
            
            for i, prop in enumerate(properties_to_extract, 1):
                print(f"[{i}/{len(properties_to_extract)}] {prop['property_name'][:50]}...")
                
                result = await self.extract_property(prop)
                self.results.append(result)
                
                if result.success:
                    print(f"  ✅ Extracted: ${result.tax_amount:.2f}")
                    success_count += 1
                else:
                    print(f"  ❌ Failed: {result.error_message}")
                    fail_count += 1
                
                # Sync to Supabase
                if self.sync_to_supabase(result):
                    print(f"  📤 Synced to Supabase")
                
                # Rate limiting
                await asyncio.sleep(2)
            
            # Cleanup
            await self.cleanup_playwright()
            
            # Summary
            print("\n" + "="*60)
            print("EXTRACTION COMPLETE")
            print(f"✅ Successful: {success_count}")
            print(f"❌ Failed: {fail_count}")
            
            # Save results to file
            self.save_results()
            
        except Exception as e:
            logger.error(f"Batch extraction error: {e}")
            print(f"❌ Error: {e}")
    
    def save_results(self):
        """Save results to JSON file"""
        if not self.results:
            return
            
        filename = f"extraction_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, 'w') as f:
            results_dict = [asdict(r) for r in self.results]
            json.dump(results_dict, f, indent=2)
        
        print(f"📄 Results saved to: {filename}")

async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Local Extraction Suite for Complex Jurisdictions')
    parser.add_argument('--limit', '-l', type=int, default=10, 
                       help='Number of properties to process (default: 10)')
    parser.add_argument('--headless', action='store_true', default=True,
                       help='Run browsers in headless mode')
    parser.add_argument('--show-browser', action='store_true',
                       help='Show browser window (disables headless)')
    
    args = parser.parse_args()
    
    # Create extraction suite
    suite = LocalExtractionSuite(headless=not args.show_browser)
    
    # Run batch extraction
    await suite.run_batch_extraction(limit=args.limit)

if __name__ == "__main__":
    asyncio.run(main())