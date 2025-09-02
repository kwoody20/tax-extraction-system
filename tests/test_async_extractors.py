"""
Test suite for async tax extractors.
Validates that async implementations work correctly and improve performance.
"""

import asyncio
import pytest
import time
from unittest.mock import Mock, patch, AsyncMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.extractors.async_cloud_extractor import AsyncCloudTaxExtractor
from src.extractors.async_selenium_wrapper import AsyncSeleniumDriver, AsyncSeleniumExtractor
from src.extractors.async_master_extractor import AsyncMasterTaxExtractor
from src.utils.async_helpers import (
    AsyncRateLimiter,
    AsyncRetryHandler,
    async_sleep,
    AsyncBatchProcessor
)


class TestAsyncHelpers:
    """Test async utility functions"""
    
    @pytest.mark.asyncio
    async def test_async_sleep(self):
        """Test non-blocking sleep"""
        start = time.time()
        await async_sleep(0.1, "test delay")
        duration = time.time() - start
        assert 0.09 < duration < 0.15
    
    @pytest.mark.asyncio
    async def test_rate_limiter(self):
        """Test async rate limiter"""
        limiter = AsyncRateLimiter(requests_per_second=10)
        
        start = time.time()
        for _ in range(5):
            await limiter.wait_if_needed()
        duration = time.time() - start
        
        # Should take at least 0.4 seconds for 5 requests at 10/sec
        assert duration >= 0.4
    
    @pytest.mark.asyncio
    async def test_retry_handler(self):
        """Test async retry with exponential backoff"""
        handler = AsyncRetryHandler(max_retries=3, base_delay=0.1)
        
        call_count = 0
        
        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Test error")
            return "success"
        
        result = await handler.execute_with_retry(failing_func)
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_batch_processor(self):
        """Test async batch processing"""
        processor = AsyncBatchProcessor(batch_size=2, delay_between_batches=0.1)
        
        async def process_item(item):
            await asyncio.sleep(0.05)
            return item * 2
        
        items = [1, 2, 3, 4, 5]
        results = await processor.process_items(items, process_item, concurrent=True)
        
        assert results == [2, 4, 6, 8, 10]


class TestAsyncCloudExtractor:
    """Test async cloud extractor"""
    
    @pytest.mark.asyncio
    async def test_extractor_initialization(self):
        """Test extractor initialization"""
        async with AsyncCloudTaxExtractor(rate_limit_per_second=2.0) as extractor:
            assert extractor.session is not None
            assert extractor.rate_limiter is not None
    
    @pytest.mark.asyncio
    async def test_supported_jurisdictions(self):
        """Test jurisdiction support check"""
        async with AsyncCloudTaxExtractor() as extractor:
            jurisdictions = extractor.get_supported_jurisdictions()
            assert "Montgomery" in jurisdictions
            assert "Fort Bend" in jurisdictions
            assert "Maricopa" not in jurisdictions  # Requires Selenium
    
    @pytest.mark.asyncio
    async def test_extract_unsupported_jurisdiction(self):
        """Test extraction for unsupported jurisdiction"""
        async with AsyncCloudTaxExtractor() as extractor:
            result = await extractor.extract({
                "jurisdiction": "Unknown County",
                "tax_bill_link": "https://example.com"
            })
            
            assert result["status"] == "error"
            assert "not supported" in result["error"]
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_montgomery_extraction(self, mock_get):
        """Test Montgomery County extraction"""
        # Mock response
        mock_response = AsyncMock()
        mock_response.text = AsyncMock(return_value="""
            <html>
                <table>
                    <tr><td>Total Tax Due:</td><td>$1,234.56</td></tr>
                </table>
            </html>
        """)
        mock_response.raise_for_status = AsyncMock()
        mock_get.return_value.__aenter__.return_value = mock_response
        
        async with AsyncCloudTaxExtractor() as extractor:
            result = await extractor.extract({
                "jurisdiction": "Montgomery County",
                "tax_bill_link": "https://actweb.acttax.com/test",
                "account_number": "123456"
            })
            
            assert result["status"] == "success"
            assert result["tax_amount"] == 1234.56
            assert result["extraction_method"] == "async_cloud_direct_url"
    
    @pytest.mark.asyncio
    async def test_batch_extraction(self):
        """Test batch extraction performance"""
        properties = [
            {"jurisdiction": f"Montgomery County", "tax_bill_link": f"https://test{i}.com"}
            for i in range(5)
        ]
        
        async with AsyncCloudTaxExtractor() as extractor:
            with patch.object(extractor, '_fetch_url', return_value="<html>Total Tax Due: $100</html>"):
                start = time.time()
                results = await extractor.extract_batch(properties, max_concurrent=3)
                duration = time.time() - start
                
                assert len(results) == 5
                # Should be faster than sequential (5 * rate_limit)
                assert duration < 3.0


class TestAsyncSeleniumWrapper:
    """Test async Selenium wrapper"""
    
    @pytest.mark.asyncio
    @patch('selenium.webdriver.Chrome')
    async def test_driver_initialization(self, mock_chrome):
        """Test async Selenium driver initialization"""
        mock_driver = Mock()
        mock_chrome.return_value = mock_driver
        
        async with AsyncSeleniumDriver(headless=True) as driver:
            assert driver.driver is not None
            mock_driver.quit.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('selenium.webdriver.Chrome')
    async def test_async_navigation(self, mock_chrome):
        """Test async page navigation"""
        mock_driver = Mock()
        mock_chrome.return_value = mock_driver
        
        async with AsyncSeleniumDriver() as driver:
            await driver.get("https://example.com")
            mock_driver.get.assert_called_with("https://example.com")
    
    @pytest.mark.asyncio
    async def test_concurrent_selenium_extraction(self):
        """Test concurrent Selenium extractions"""
        extractor = AsyncSeleniumExtractor(headless=True, max_concurrent=2)
        
        async def mock_extraction(driver, data):
            await asyncio.sleep(0.1)
            return {"status": "success", "property_id": data["property_id"]}
        
        properties = [{"property_id": i} for i in range(4)]
        
        start = time.time()
        results = await extractor.extract_batch(properties, mock_extraction)
        duration = time.time() - start
        
        assert len(results) == 4
        # With max_concurrent=2, should take ~0.2 seconds (2 batches of 0.1s each)
        assert duration < 0.3


class TestAsyncMasterExtractor:
    """Test async master extractor coordinator"""
    
    @pytest.mark.asyncio
    async def test_jurisdiction_routing(self):
        """Test correct routing based on jurisdiction"""
        async with AsyncMasterTaxExtractor(use_selenium=False) as extractor:
            assert extractor._determine_extraction_method("Montgomery County") == "cloud"
            assert extractor._determine_extraction_method("Maricopa County") == "selenium"
            assert extractor._determine_extraction_method("Wayne County") == "playwright"
            assert extractor._determine_extraction_method("Unknown") == "unsupported"
    
    @pytest.mark.asyncio
    @patch('src.extractors.async_cloud_extractor.AsyncCloudTaxExtractor.extract')
    async def test_cloud_extraction_routing(self, mock_extract):
        """Test routing to cloud extractor"""
        mock_extract.return_value = {"status": "success", "tax_amount": 100}
        
        async with AsyncMasterTaxExtractor(use_selenium=False) as extractor:
            result = await extractor.extract_property({
                "property_id": "001",
                "jurisdiction": "Montgomery County",
                "tax_bill_link": "https://test.com"
            })
            
            assert result["status"] == "success"
            assert result["property_id"] == "001"
            assert "extracted_at" in result
            mock_extract.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_batch_extraction_statistics(self):
        """Test batch extraction with statistics"""
        async with AsyncMasterTaxExtractor(use_selenium=False) as extractor:
            with patch.object(extractor, 'extract_property') as mock_extract:
                mock_extract.side_effect = [
                    {"status": "success"},
                    {"status": "error"},
                    {"status": "success"}
                ]
                
                properties = [{"property_id": i} for i in range(3)]
                summary = await extractor.extract_batch(properties)
                
                assert summary["statistics"]["total"] == 3
                assert summary["statistics"]["success"] == 2
                assert summary["statistics"]["failed"] == 1
                assert summary["success_rate"] == 2/3
    
    @pytest.mark.asyncio
    async def test_concurrent_performance(self):
        """Test performance improvement with concurrent extraction"""
        
        async def slow_extract(data):
            await asyncio.sleep(0.1)
            return {"status": "success"}
        
        async with AsyncMasterTaxExtractor(max_concurrent_extractions=5) as extractor:
            with patch.object(extractor, 'extract_property', side_effect=slow_extract):
                properties = [{"property_id": i} for i in range(10)]
                
                start = time.time()
                await extractor.extract_batch(properties)
                duration = time.time() - start
                
                # With max_concurrent=5, 10 items at 0.1s each should take ~0.2s
                # (2 batches), not 1.0s (sequential)
                assert duration < 0.4


@pytest.mark.asyncio
async def test_performance_comparison():
    """Compare sync vs async extraction performance"""
    
    # Simulate sync extraction
    def sync_extract(properties):
        results = []
        for prop in properties:
            time.sleep(0.05)  # Simulate network delay
            results.append({"status": "success"})
        return results
    
    # Simulate async extraction
    async def async_extract(properties):
        async def extract_one(prop):
            await asyncio.sleep(0.05)  # Non-blocking delay
            return {"status": "success"}
        
        return await asyncio.gather(*[extract_one(p) for p in properties])
    
    properties = [{"property_id": i} for i in range(10)]
    
    # Measure sync time
    start = time.time()
    sync_results = sync_extract(properties)
    sync_duration = time.time() - start
    
    # Measure async time
    start = time.time()
    async_results = await async_extract(properties)
    async_duration = time.time() - start
    
    print(f"Sync extraction: {sync_duration:.2f}s")
    print(f"Async extraction: {async_duration:.2f}s")
    print(f"Speed improvement: {sync_duration/async_duration:.1f}x")
    
    assert len(sync_results) == len(async_results) == 10
    assert async_duration < sync_duration / 2  # At least 2x faster


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])