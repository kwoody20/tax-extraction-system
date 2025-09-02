"""
Async wrapper for Selenium operations.
Since Selenium itself is synchronous, this wrapper runs Selenium in thread executors
to prevent blocking the async event loop.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any, List, Callable
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
import logging
import time
from functools import wraps
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.async_helpers import (
    async_sleep,
    AsyncRetryHandler,
    make_async
)

logger = logging.getLogger(__name__)


class AsyncSeleniumDriver:
    """
    Async wrapper for Selenium WebDriver operations.
    Runs Selenium commands in thread executor to prevent blocking.
    """
    
    def __init__(self, 
                 headless: bool = True,
                 executor: Optional[ThreadPoolExecutor] = None,
                 max_workers: int = 4):
        """
        Initialize async Selenium wrapper.
        
        Args:
            headless: Run browser in headless mode
            executor: Thread executor for running sync operations
            max_workers: Max threads if creating new executor
        """
        self.headless = headless
        self.executor = executor or ThreadPoolExecutor(max_workers=max_workers)
        self.driver = None
        self.retry_handler = AsyncRetryHandler(max_retries=3)
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.quit()
    
    async def start(self):
        """Start the WebDriver in executor"""
        loop = asyncio.get_event_loop()
        
        def _create_driver():
            options = webdriver.ChromeOptions()
            if self.headless:
                options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            
            return webdriver.Chrome(options=options)
        
        self.driver = await loop.run_in_executor(self.executor, _create_driver)
        logger.info("Async Selenium driver started")
    
    async def quit(self):
        """Quit the WebDriver"""
        if self.driver:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self.executor, self.driver.quit)
            self.driver = None
            logger.info("Async Selenium driver closed")
    
    async def get(self, url: str):
        """Navigate to URL asynchronously"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self.executor, self.driver.get, url)
        
        # Non-blocking wait for page to start loading
        await async_sleep(0.5, "Initial page load delay")
    
    async def find_element(self, by: By, value: str, timeout: float = 10):
        """Find element asynchronously with wait"""
        loop = asyncio.get_event_loop()
        
        def _find():
            wait = WebDriverWait(self.driver, timeout)
            return wait.until(EC.presence_of_element_located((by, value)))
        
        return await loop.run_in_executor(self.executor, _find)
    
    async def find_elements(self, by: By, value: str, timeout: float = 10):
        """Find multiple elements asynchronously"""
        loop = asyncio.get_event_loop()
        
        def _find():
            wait = WebDriverWait(self.driver, timeout)
            wait.until(EC.presence_of_element_located((by, value)))
            return self.driver.find_elements(by, value)
        
        return await loop.run_in_executor(self.executor, _find)
    
    async def click_element(self, element):
        """Click element asynchronously"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self.executor, element.click)
        
        # Non-blocking wait after click
        await async_sleep(0.5, "Post-click delay")
    
    async def send_keys(self, element, keys: str):
        """Send keys to element asynchronously"""
        loop = asyncio.get_event_loop()
        
        def _send():
            element.clear()
            element.send_keys(keys)
        
        await loop.run_in_executor(self.executor, _send)
    
    async def wait_for_element(self, 
                                by: By, 
                                value: str, 
                                condition=EC.presence_of_element_located,
                                timeout: float = 10):
        """Wait for element with specific condition asynchronously"""
        loop = asyncio.get_event_loop()
        
        def _wait():
            wait = WebDriverWait(self.driver, timeout)
            return wait.until(condition((by, value)))
        
        return await loop.run_in_executor(self.executor, _wait)
    
    async def get_page_source(self) -> str:
        """Get page source asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor, 
            lambda: self.driver.page_source
        )
    
    async def execute_script(self, script: str, *args):
        """Execute JavaScript asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.driver.execute_script,
            script,
            *args
        )
    
    async def take_screenshot(self, filename: str):
        """Take screenshot asynchronously"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self.executor,
            self.driver.save_screenshot,
            filename
        )
    
    async def switch_to_frame(self, frame):
        """Switch to frame asynchronously"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self.executor,
            self.driver.switch_to.frame,
            frame
        )
    
    async def switch_to_default_content(self):
        """Switch to default content asynchronously"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self.executor,
            self.driver.switch_to.default_content
        )
    
    async def get_current_url(self) -> str:
        """Get current URL asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            lambda: self.driver.current_url
        )
    
    async def refresh(self):
        """Refresh page asynchronously"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self.executor, self.driver.refresh)
        await async_sleep(1, "Page refresh delay")


class AsyncSeleniumExtractor:
    """
    Base class for async Selenium-based tax extractors.
    Provides common async patterns for web scraping.
    """
    
    def __init__(self, 
                 headless: bool = True,
                 max_concurrent: int = 3):
        """
        Initialize async Selenium extractor.
        
        Args:
            headless: Run browsers in headless mode
            max_concurrent: Maximum concurrent browser instances
        """
        self.headless = headless
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def extract_with_selenium(self, 
                                     property_data: Dict[str, Any],
                                     extraction_func: Callable) -> Dict[str, Any]:
        """
        Extract using Selenium with async wrapper.
        
        Args:
            property_data: Property information
            extraction_func: Async function to perform extraction
            
        Returns:
            Extraction results
        """
        async with self.semaphore:  # Limit concurrent browsers
            async with AsyncSeleniumDriver(headless=self.headless) as driver:
                try:
                    result = await extraction_func(driver, property_data)
                    return result
                except Exception as e:
                    logger.error(f"Selenium extraction error: {e}")
                    return {
                        "status": "error",
                        "error": str(e)
                    }
    
    async def extract_batch(self,
                            properties: List[Dict[str, Any]],
                            extraction_func: Callable) -> List[Dict[str, Any]]:
        """
        Extract multiple properties concurrently with Selenium.
        
        Args:
            properties: List of property data
            extraction_func: Async extraction function
            
        Returns:
            List of extraction results
        """
        tasks = [
            self.extract_with_selenium(prop, extraction_func) 
            for prop in properties
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error results
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append({
                    "status": "error",
                    "error": str(result),
                    "property": properties[i]
                })
            else:
                final_results.append(result)
        
        return final_results


# Example async extraction functions for specific counties

async def extract_maricopa_async(driver: AsyncSeleniumDriver, 
                                  property_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Async extraction for Maricopa County using Selenium.
    """
    try:
        parcel_number = property_data.get("account_number", "")
        if not parcel_number:
            return {"status": "error", "error": "No parcel number provided"}
        
        # Navigate to Maricopa treasurer site
        url = "https://treasurer.maricopa.gov/propertytax/"
        await driver.get(url)
        
        # Wait for and fill parcel number field
        await async_sleep(2, "Wait for page load")
        
        parcel_input = await driver.find_element(By.ID, "parcel-number-input")
        await driver.send_keys(parcel_input, parcel_number)
        
        # Click search button
        search_button = await driver.find_element(By.ID, "search-button")
        await driver.click_element(search_button)
        
        # Wait for results
        await async_sleep(3, "Wait for search results")
        
        # Extract tax amount
        tax_element = await driver.find_element(By.CLASS_NAME, "tax-amount")
        tax_text = await asyncio.get_event_loop().run_in_executor(
            driver.executor,
            lambda: tax_element.text
        )
        
        # Parse amount
        import re
        match = re.search(r'\$?([\d,]+\.?\d*)', tax_text)
        if match:
            tax_amount = float(match.group(1).replace(',', ''))
            return {
                "status": "success",
                "jurisdiction": "Maricopa County, AZ",
                "tax_amount": tax_amount,
                "extraction_method": "async_selenium"
            }
        
        return {"status": "error", "error": "Could not parse tax amount"}
        
    except Exception as e:
        logger.error(f"Maricopa async extraction error: {e}")
        return {"status": "error", "error": str(e)}


async def extract_harris_async(driver: AsyncSeleniumDriver,
                                property_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Async extraction for Harris County using Selenium.
    """
    try:
        account_number = property_data.get("account_number", "")
        if not account_number:
            return {"status": "error", "error": "No account number provided"}
        
        # Navigate to Harris County tax site
        url = f"https://www.hctax.net/Property/PropertyTax?account={account_number}"
        await driver.get(url)
        
        # Wait for dynamic content to load
        await async_sleep(3, "Wait for JavaScript rendering")
        
        # Find tax amount element
        tax_element = await driver.wait_for_element(
            By.XPATH,
            "//td[contains(text(), 'Total Due')]/following-sibling::td",
            timeout=10
        )
        
        tax_text = await asyncio.get_event_loop().run_in_executor(
            driver.executor,
            lambda: tax_element.text
        )
        
        # Parse amount
        import re
        match = re.search(r'\$?([\d,]+\.?\d*)', tax_text)
        if match:
            tax_amount = float(match.group(1).replace(',', ''))
            return {
                "status": "success",
                "jurisdiction": "Harris County, TX",
                "tax_amount": tax_amount,
                "extraction_method": "async_selenium"
            }
        
        return {"status": "error", "error": "Could not parse tax amount"}
        
    except Exception as e:
        logger.error(f"Harris async extraction error: {e}")
        return {"status": "error", "error": str(e)}


# Example usage
async def main():
    """Example of using async Selenium extractors"""
    
    # Test property data
    test_properties = [
        {
            "jurisdiction": "Maricopa County",
            "account_number": "123-45-678"
        },
        {
            "jurisdiction": "Harris County",
            "account_number": "987654321"
        }
    ]
    
    # Create extractor
    extractor = AsyncSeleniumExtractor(headless=True, max_concurrent=2)
    
    # Extract single property
    result = await extractor.extract_with_selenium(
        test_properties[0],
        extract_maricopa_async
    )
    print(f"Single extraction: {result}")
    
    # Extract batch
    async def route_extraction(driver, prop):
        if "maricopa" in prop["jurisdiction"].lower():
            return await extract_maricopa_async(driver, prop)
        elif "harris" in prop["jurisdiction"].lower():
            return await extract_harris_async(driver, prop)
        else:
            return {"status": "error", "error": "Unknown jurisdiction"}
    
    results = await extractor.extract_batch(test_properties, route_extraction)
    print(f"Batch extraction: {results}")


if __name__ == "__main__":
    asyncio.run(main())