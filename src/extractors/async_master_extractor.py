"""
Async version of MASTER_TAX_EXTRACTOR with non-blocking operations.
Coordinates multiple async extractors for improved performance.
"""

import asyncio
import aiohttp
from typing import Dict, List, Any, Optional, Tuple
import logging
import json
from datetime import datetime
import pandas as pd
from pathlib import Path
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.async_helpers import (
    AsyncBatchProcessor,
    async_sleep,
    parallel_map,
    AsyncRetryHandler
)
from extractors.async_cloud_extractor import AsyncCloudTaxExtractor
from extractors.async_selenium_wrapper import (
    AsyncSeleniumExtractor,
    extract_maricopa_async,
    extract_harris_async
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class AsyncMasterTaxExtractor:
    """
    Master async coordinator for all tax extraction methods.
    Routes to appropriate extractor based on jurisdiction.
    """
    
    def __init__(self,
                 max_concurrent_extractions: int = 10,
                 use_selenium: bool = True,
                 headless: bool = True):
        """
        Initialize async master extractor.
        
        Args:
            max_concurrent_extractions: Max concurrent extraction tasks
            use_selenium: Enable Selenium-based extractors
            headless: Run browsers in headless mode
        """
        self.max_concurrent = max_concurrent_extractions
        self.use_selenium = use_selenium
        self.headless = headless
        
        # Initialize extractors
        self.cloud_extractor = None
        self.selenium_extractor = None
        
        # Track statistics
        self.stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "start_time": None,
            "end_time": None
        }
        
        # Jurisdiction routing map
        self.jurisdiction_routes = {
            # Cloud-compatible (HTTP only)
            "montgomery": "cloud",
            "fort bend": "cloud",
            "chambers": "cloud",
            "galveston": "cloud",
            "aldine": "cloud",
            "goose creek": "cloud",
            "spring creek": "cloud",
            "barbers hill": "cloud",
            
            # Selenium required (JavaScript-heavy)
            "maricopa": "selenium",
            "harris": "selenium",
            "dallas": "selenium",
            "tarrant": "selenium",
            
            # Playwright preferred (complex interactions)
            "wayne": "playwright",
            "johnston": "playwright",
            "craven": "playwright",
            "wilson": "playwright"
        }
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.cloud_extractor = AsyncCloudTaxExtractor(
            rate_limit_per_second=2.0,
            max_retries=3
        )
        await self.cloud_extractor.__aenter__()
        
        if self.use_selenium:
            self.selenium_extractor = AsyncSeleniumExtractor(
                headless=self.headless,
                max_concurrent=min(3, self.max_concurrent)
            )
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.cloud_extractor:
            await self.cloud_extractor.__aexit__(exc_type, exc_val, exc_tb)
    
    def _determine_extraction_method(self, jurisdiction: str) -> str:
        """
        Determine which extraction method to use for a jurisdiction.
        
        Args:
            jurisdiction: Jurisdiction name
            
        Returns:
            Extraction method: 'cloud', 'selenium', 'playwright', or 'unsupported'
        """
        jurisdiction_lower = jurisdiction.lower()
        
        for key, method in self.jurisdiction_routes.items():
            if key in jurisdiction_lower:
                return method
        
        return "unsupported"
    
    async def extract_property(self, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract tax data for a single property.
        Routes to appropriate extractor based on jurisdiction.
        
        Args:
            property_data: Property information dict
            
        Returns:
            Extraction results dict
        """
        jurisdiction = property_data.get("jurisdiction", "")
        property_id = property_data.get("property_id", "unknown")
        
        logger.info(f"Extracting property {property_id} - {jurisdiction}")
        
        # Determine extraction method
        method = self._determine_extraction_method(jurisdiction)
        
        try:
            if method == "cloud":
                # Use async cloud extractor
                result = await self.cloud_extractor.extract(property_data)
                
            elif method == "selenium" and self.use_selenium:
                # Use async Selenium wrapper
                result = await self._extract_with_selenium(property_data)
                
            elif method == "playwright":
                # Playwright extraction (would need separate implementation)
                result = await self._extract_with_playwright(property_data)
                
            else:
                result = {
                    "status": "error",
                    "error": f"Unsupported jurisdiction: {jurisdiction}",
                    "extraction_method": "none"
                }
            
            # Add metadata
            result["property_id"] = property_id
            result["jurisdiction"] = jurisdiction
            result["extracted_at"] = datetime.now().isoformat()
            
            return result
            
        except Exception as e:
            logger.error(f"Extraction error for {property_id}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "property_id": property_id,
                "jurisdiction": jurisdiction
            }
    
    async def _extract_with_selenium(self, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract using async Selenium wrapper.
        
        Args:
            property_data: Property information
            
        Returns:
            Extraction results
        """
        jurisdiction = property_data.get("jurisdiction", "").lower()
        
        # Route to specific Selenium extractor
        if "maricopa" in jurisdiction:
            extraction_func = extract_maricopa_async
        elif "harris" in jurisdiction:
            extraction_func = extract_harris_async
        else:
            # Generic Selenium extraction
            async def generic_extraction(driver, data):
                url = data.get("tax_bill_link", "")
                if not url:
                    return {"status": "error", "error": "No tax bill link"}
                
                await driver.get(url)
                await async_sleep(3, "Wait for page load")
                
                # Try to find tax amount
                page_source = await driver.get_page_source()
                
                import re
                from bs4 import BeautifulSoup
                
                soup = BeautifulSoup(page_source, 'html.parser')
                patterns = [
                    r'Total.*Due[:\s]+\$?([\d,]+\.?\d*)',
                    r'Amount.*Due[:\s]+\$?([\d,]+\.?\d*)',
                    r'Balance[:\s]+\$?([\d,]+\.?\d*)'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, str(soup), re.IGNORECASE)
                    if match:
                        tax_amount = float(match.group(1).replace(',', ''))
                        return {
                            "status": "success",
                            "tax_amount": tax_amount,
                            "extraction_method": "async_selenium_generic"
                        }
                
                return {"status": "error", "error": "Could not find tax amount"}
            
            extraction_func = generic_extraction
        
        return await self.selenium_extractor.extract_with_selenium(
            property_data,
            extraction_func
        )
    
    async def _extract_with_playwright(self, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Placeholder for Playwright extraction.
        Would need separate async Playwright implementation.
        """
        # For now, fall back to cloud extractor if available
        if "wayne" in property_data.get("jurisdiction", "").lower():
            # Direct link extraction for Wayne County
            return await self.cloud_extractor._generic_extract(
                property_data,
                "Wayne County, NC",
                [r'Total Tax[:\s]+\$?([\d,]+\.?\d*)']
            )
        
        return {
            "status": "error",
            "error": "Playwright extraction not yet implemented",
            "extraction_method": "none"
        }
    
    async def extract_batch(self,
                            properties: List[Dict[str, Any]],
                            save_intermediate: bool = True,
                            output_file: str = "async_extraction_results.json") -> Dict[str, Any]:
        """
        Extract multiple properties concurrently.
        
        Args:
            properties: List of property data dicts
            save_intermediate: Save results periodically
            output_file: Output file for results
            
        Returns:
            Summary dict with all results
        """
        self.stats["total"] = len(properties)
        self.stats["start_time"] = datetime.now()
        
        logger.info(f"Starting async batch extraction for {len(properties)} properties")
        
        # Create batch processor
        batch_processor = AsyncBatchProcessor(
            batch_size=self.max_concurrent,
            delay_between_batches=2.0
        )
        
        # Process properties in batches
        results = await batch_processor.process_items(
            properties,
            self.extract_property,
            concurrent=True
        )
        
        # Update statistics
        for result in results:
            if isinstance(result, Exception):
                self.stats["failed"] += 1
            elif result.get("status") == "success":
                self.stats["success"] += 1
            elif result.get("status") == "error":
                self.stats["failed"] += 1
            else:
                self.stats["skipped"] += 1
        
        self.stats["end_time"] = datetime.now()
        
        # Save results
        if save_intermediate:
            await self._save_results(results, output_file)
        
        # Generate summary
        duration = (self.stats["end_time"] - self.stats["start_time"]).total_seconds()
        
        summary = {
            "statistics": self.stats,
            "duration_seconds": duration,
            "properties_per_second": self.stats["total"] / duration if duration > 0 else 0,
            "success_rate": self.stats["success"] / self.stats["total"] if self.stats["total"] > 0 else 0,
            "results": results
        }
        
        logger.info(f"Extraction complete: {self.stats['success']}/{self.stats['total']} successful")
        
        return summary
    
    async def _save_results(self, results: List[Dict], output_file: str):
        """Save extraction results to file asynchronously"""
        loop = asyncio.get_event_loop()
        
        def _save():
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2, default=str)
        
        await loop.run_in_executor(None, _save)
        logger.info(f"Results saved to {output_file}")
    
    async def extract_from_excel(self,
                                  excel_file: str,
                                  sheet_name: str = None) -> Dict[str, Any]:
        """
        Extract properties from Excel file.
        
        Args:
            excel_file: Path to Excel file
            sheet_name: Specific sheet to read
            
        Returns:
            Extraction summary
        """
        loop = asyncio.get_event_loop()
        
        # Read Excel in executor to avoid blocking
        def _read_excel():
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            
            # Convert to list of dicts
            properties = []
            for _, row in df.iterrows():
                prop = {
                    "property_id": row.get("Property ID", row.get("property_id", "")),
                    "jurisdiction": row.get("Jurisdiction", row.get("jurisdiction", "")),
                    "tax_bill_link": row.get("Tax Bill Link", row.get("tax_bill_link", "")),
                    "account_number": row.get("Acct Number", row.get("account_number", "")),
                    "property_name": row.get("Property Name", row.get("property_name", "")),
                    "property_address": row.get("Property Address", row.get("property_address", ""))
                }
                properties.append(prop)
            
            return properties
        
        properties = await loop.run_in_executor(None, _read_excel)
        
        logger.info(f"Loaded {len(properties)} properties from {excel_file}")
        
        # Extract all properties
        return await self.extract_batch(properties)


async def main():
    """Example usage of async master extractor"""
    
    # Example property data
    test_properties = [
        {
            "property_id": "001",
            "jurisdiction": "Montgomery County, TX",
            "tax_bill_link": "https://actweb.acttax.com/act_webdev/mckinney/tax_bill.jsp?account=123456",
            "account_number": "123456"
        },
        {
            "property_id": "002",
            "jurisdiction": "Harris County, TX",
            "tax_bill_link": "https://www.hctax.net/Property/PropertyTax",
            "account_number": "789012"
        },
        {
            "property_id": "003",
            "jurisdiction": "Maricopa County, AZ",
            "account_number": "123-45-678"
        }
    ]
    
    # Run async extraction
    async with AsyncMasterTaxExtractor(
        max_concurrent_extractions=5,
        use_selenium=True,
        headless=True
    ) as extractor:
        
        # Extract single property
        result = await extractor.extract_property(test_properties[0])
        print(f"Single extraction: {json.dumps(result, indent=2)}")
        
        # Extract batch
        summary = await extractor.extract_batch(test_properties)
        print(f"\nBatch extraction summary:")
        print(f"  Total: {summary['statistics']['total']}")
        print(f"  Success: {summary['statistics']['success']}")
        print(f"  Failed: {summary['statistics']['failed']}")
        print(f"  Duration: {summary['duration_seconds']:.2f} seconds")
        print(f"  Rate: {summary['properties_per_second']:.2f} properties/second")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())