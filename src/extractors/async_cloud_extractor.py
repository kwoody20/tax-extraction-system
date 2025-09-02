"""
Async cloud-compatible tax extractor using aiohttp for non-blocking operations.
Improved performance through concurrent requests and async patterns.
"""

import aiohttp
import asyncio
from bs4 import BeautifulSoup
import re
import time
import logging
from typing import Dict, Optional, Any, List
from urllib.parse import urlparse, parse_qs
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.async_helpers import (
    AsyncRateLimiter,
    AsyncRetryHandler,
    async_sleep,
    async_wait_with_timeout,
    AsyncHTTPClient,
    AsyncBatchProcessor
)

logger = logging.getLogger(__name__)


class AsyncCloudTaxExtractor:
    """
    Async cloud-friendly tax extractor with improved performance.
    Uses aiohttp for concurrent HTTP requests without blocking.
    """
    
    # These jurisdictions work well with simple HTTP requests
    SUPPORTED_JURISDICTIONS = {
        "Montgomery": {
            "name": "Montgomery County, TX",
            "method": "direct_url",
            "confidence": "high"
        },
        "Fort Bend": {
            "name": "Fort Bend County, TX", 
            "method": "direct_url",
            "confidence": "high"
        },
        "Chambers": {
            "name": "Chambers County, TX",
            "method": "direct_url",
            "confidence": "medium"
        },
        "Galveston": {
            "name": "Galveston County, TX",
            "method": "direct_url",
            "confidence": "medium"
        },
        "Aldine ISD": {
            "name": "Aldine ISD, TX",
            "method": "direct_link",
            "confidence": "high"
        },
        "Goose Creek ISD": {
            "name": "Goose Creek ISD, TX",
            "method": "direct_link",
            "confidence": "high"
        },
        "Spring Creek": {
            "name": "Spring Creek U.D., TX",
            "method": "direct_link",
            "confidence": "medium"
        },
        "Barbers Hill ISD": {
            "name": "Barbers Hill ISD, TX",
            "method": "direct_link",
            "confidence": "medium"
        }
    }
    
    def __init__(self, 
                 rate_limit_per_second: float = 1.0,
                 max_retries: int = 3,
                 timeout: float = 30.0):
        """
        Initialize async extractor with configurable settings.
        
        Args:
            rate_limit_per_second: Max requests per second
            max_retries: Maximum retry attempts
            timeout: Request timeout in seconds
        """
        self.rate_limiter = AsyncRateLimiter(requests_per_second=rate_limit_per_second)
        self.retry_handler = AsyncRetryHandler(max_retries=max_retries)
        self.timeout = timeout
        self.session = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            headers=self.headers,
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def _fetch_url(self, url: str) -> Optional[str]:
        """
        Fetch URL content asynchronously with rate limiting and retry.
        
        Args:
            url: URL to fetch
            
        Returns:
            HTML content or None if failed
        """
        await self.rate_limiter.wait_if_needed()
        
        async def _get():
            async with self.session.get(url) as response:
                response.raise_for_status()
                return await response.text()
        
        try:
            return await self.retry_handler.execute_with_retry(_get)
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None
    
    async def extract(self, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Async extraction method for cloud deployment.
        
        Args:
            property_data: Dict with jurisdiction, tax_bill_link, account_number, etc.
            
        Returns:
            Dict with extraction results
        """
        jurisdiction = property_data.get("jurisdiction", "")
        tax_bill_link = property_data.get("tax_bill_link", "")
        account_number = property_data.get("account_number")
        
        # Check if jurisdiction is supported
        supported = False
        for key in self.SUPPORTED_JURISDICTIONS:
            if key.lower() in jurisdiction.lower():
                supported = True
                break
        
        if not supported:
            return {
                "status": "error",
                "error": f"Jurisdiction '{jurisdiction}' not supported for cloud extraction",
                "supported_jurisdictions": list(self.SUPPORTED_JURISDICTIONS.keys())
            }
        
        # Route to appropriate extraction method
        if "montgomery" in jurisdiction.lower():
            return await self._extract_montgomery(property_data)
        elif "fort bend" in jurisdiction.lower():
            return await self._extract_fort_bend(property_data)
        elif "chambers" in jurisdiction.lower():
            return await self._extract_chambers(property_data)
        elif "galveston" in jurisdiction.lower():
            return await self._extract_galveston(property_data)
        elif "aldine" in jurisdiction.lower() or "goose creek" in jurisdiction.lower():
            return await self._extract_direct_link(property_data)
        elif "spring creek" in jurisdiction.lower() or "barbers hill" in jurisdiction.lower():
            return await self._extract_direct_link(property_data)
        else:
            return {
                "status": "error",
                "error": f"No extraction method for {jurisdiction}"
            }
    
    async def _extract_montgomery(self, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract Montgomery County taxes (async version).
        Works via direct URL with account number in params.
        """
        tax_bill_link = property_data.get("tax_bill_link", "")
        account_number = property_data.get("account_number")
        
        if not tax_bill_link:
            return {"status": "error", "error": "No tax bill link provided"}
        
        try:
            # Extract account from URL if not provided
            if not account_number and "account=" in tax_bill_link:
                parsed = urlparse(tax_bill_link)
                params = parse_qs(parsed.query)
                account_number = params.get("account", [None])[0]
            
            if not account_number:
                return {"status": "error", "error": "No account number found"}
            
            # Fetch the page
            html = await self._fetch_url(tax_bill_link)
            if not html:
                return {"status": "error", "error": "Failed to fetch tax page"}
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract tax amount
            tax_amount = None
            amount_patterns = [
                r'Total Tax Due[:\s]+\$?([\d,]+\.?\d*)',
                r'Amount Due[:\s]+\$?([\d,]+\.?\d*)',
                r'Balance[:\s]+\$?([\d,]+\.?\d*)',
                r'Total Due[:\s]+\$?([\d,]+\.?\d*)'
            ]
            
            for pattern in amount_patterns:
                match = re.search(pattern, str(soup), re.IGNORECASE)
                if match:
                    tax_amount = match.group(1).replace(',', '')
                    break
            
            # Try table extraction if regex fails
            if not tax_amount:
                for table in soup.find_all('table'):
                    text = table.get_text()
                    for pattern in amount_patterns:
                        match = re.search(pattern, text, re.IGNORECASE)
                        if match:
                            tax_amount = match.group(1).replace(',', '')
                            break
                    if tax_amount:
                        break
            
            if tax_amount:
                return {
                    "status": "success",
                    "jurisdiction": "Montgomery County, TX",
                    "tax_amount": float(tax_amount),
                    "account_number": account_number,
                    "extraction_method": "async_cloud_direct_url"
                }
            else:
                return {
                    "status": "error",
                    "error": "Could not find tax amount on page"
                }
            
        except Exception as e:
            logger.error(f"Montgomery extraction error: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _extract_fort_bend(self, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract Fort Bend County taxes asynchronously"""
        tax_bill_link = property_data.get("tax_bill_link", "")
        
        if not tax_bill_link:
            return {"status": "error", "error": "No tax bill link provided"}
        
        try:
            html = await self._fetch_url(tax_bill_link)
            if not html:
                return {"status": "error", "error": "Failed to fetch tax page"}
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Fort Bend specific extraction logic
            tax_amount = None
            amount_elements = soup.find_all(text=re.compile(r'Total.*Due|Amount.*Due', re.IGNORECASE))
            
            for element in amount_elements:
                parent = element.parent
                if parent:
                    text = parent.get_text()
                    match = re.search(r'\$?([\d,]+\.?\d*)', text)
                    if match:
                        tax_amount = match.group(1).replace(',', '')
                        break
            
            if tax_amount:
                return {
                    "status": "success",
                    "jurisdiction": "Fort Bend County, TX",
                    "tax_amount": float(tax_amount),
                    "extraction_method": "async_cloud_direct_url"
                }
            else:
                return {
                    "status": "error",
                    "error": "Could not find tax amount on page"
                }
            
        except Exception as e:
            logger.error(f"Fort Bend extraction error: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _extract_chambers(self, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract Chambers County taxes asynchronously"""
        return await self._generic_extract(
            property_data,
            "Chambers County, TX",
            [
                r'Total Tax[:\s]+\$?([\d,]+\.?\d*)',
                r'Total Due[:\s]+\$?([\d,]+\.?\d*)',
                r'Balance Due[:\s]+\$?([\d,]+\.?\d*)'
            ]
        )
    
    async def _extract_galveston(self, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract Galveston County taxes asynchronously"""
        return await self._generic_extract(
            property_data,
            "Galveston County, TX",
            [
                r'Amount Due[:\s]+\$?([\d,]+\.?\d*)',
                r'Total Tax[:\s]+\$?([\d,]+\.?\d*)',
                r'Tax Due[:\s]+\$?([\d,]+\.?\d*)'
            ]
        )
    
    async def _extract_direct_link(self, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract from jurisdictions with direct links (ISDs)"""
        jurisdiction = property_data.get("jurisdiction", "")
        
        return await self._generic_extract(
            property_data,
            jurisdiction,
            [
                r'Total Amount Due[:\s]+\$?([\d,]+\.?\d*)',
                r'Total Due[:\s]+\$?([\d,]+\.?\d*)',
                r'Amount Due[:\s]+\$?([\d,]+\.?\d*)',
                r'Total[:\s]+\$?([\d,]+\.?\d*)'
            ]
        )
    
    async def _generic_extract(self, 
                                property_data: Dict[str, Any],
                                jurisdiction_name: str,
                                amount_patterns: List[str]) -> Dict[str, Any]:
        """
        Generic async extraction method for simple patterns.
        
        Args:
            property_data: Property information
            jurisdiction_name: Name of jurisdiction
            amount_patterns: List of regex patterns to try
            
        Returns:
            Extraction results
        """
        tax_bill_link = property_data.get("tax_bill_link", "")
        
        if not tax_bill_link:
            return {"status": "error", "error": "No tax bill link provided"}
        
        try:
            html = await self._fetch_url(tax_bill_link)
            if not html:
                return {"status": "error", "error": "Failed to fetch tax page"}
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Try each pattern
            tax_amount = None
            for pattern in amount_patterns:
                match = re.search(pattern, str(soup), re.IGNORECASE)
                if match:
                    tax_amount = match.group(1).replace(',', '')
                    break
            
            if tax_amount:
                return {
                    "status": "success",
                    "jurisdiction": jurisdiction_name,
                    "tax_amount": float(tax_amount),
                    "extraction_method": "async_cloud_generic"
                }
            else:
                return {
                    "status": "error",
                    "error": "Could not find tax amount on page"
                }
            
        except Exception as e:
            logger.error(f"{jurisdiction_name} extraction error: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def extract_batch(self, properties: List[Dict[str, Any]], 
                            max_concurrent: int = 10) -> List[Dict[str, Any]]:
        """
        Extract multiple properties concurrently.
        
        Args:
            properties: List of property data dicts
            max_concurrent: Maximum concurrent extractions
            
        Returns:
            List of extraction results
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def extract_with_semaphore(prop):
            async with semaphore:
                return await self.extract(prop)
        
        results = await asyncio.gather(
            *[extract_with_semaphore(prop) for prop in properties],
            return_exceptions=True
        )
        
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
    
    def get_supported_jurisdictions(self) -> Dict[str, Any]:
        """Return list of supported jurisdictions"""
        return self.SUPPORTED_JURISDICTIONS


async def main():
    """Example usage of async extractor"""
    
    # Test data
    test_properties = [
        {
            "jurisdiction": "Montgomery County",
            "tax_bill_link": "https://actweb.acttax.com/act_webdev/mckinney/tax_bill.jsp?account=123456",
            "account_number": "123456"
        },
        {
            "jurisdiction": "Fort Bend County",
            "tax_bill_link": "https://fortbend.county-taxes.com/property/123456",
            "account_number": "789012"
        }
    ]
    
    # Use async context manager
    async with AsyncCloudTaxExtractor(rate_limit_per_second=2.0) as extractor:
        # Extract single property
        result = await extractor.extract(test_properties[0])
        print(f"Single extraction: {result}")
        
        # Extract batch
        results = await extractor.extract_batch(test_properties, max_concurrent=5)
        print(f"Batch extraction: {results}")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())