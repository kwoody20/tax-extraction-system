"""
Python client SDK for Tax Extractor API
Provides a simple interface for interacting with the API
"""

import httpx
import asyncio
from typing import List, Optional, Dict, Any, Union
from pathlib import Path
import json
import time
from datetime import datetime
import pandas as pd

class TaxExtractorClient:
    """
    Client for Tax Extractor API
    
    Example usage:
        client = TaxExtractorClient("http://localhost:8000", "your-api-token")
        
        # Submit extraction job
        job_id = await client.extract_properties([
            {"property_name": "123 Main St", "tax_bill_link": "https://..."}
        ])
        
        # Monitor progress
        status = await client.get_job_status(job_id)
        
        # Get results
        results = await client.get_results(job_id, format="json")
    """
    
    def __init__(self, base_url: str, api_token: str, timeout: int = 30):
        """
        Initialize the client
        
        Args:
            base_url: API base URL (e.g., "http://localhost:8000")
            api_token: Authentication token
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.timeout = timeout
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
    
    async def extract_properties(
        self,
        properties: List[Dict[str, Any]],
        concurrent: bool = True,
        max_workers: int = 5,
        callback_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Submit properties for tax extraction
        
        Args:
            properties: List of property dictionaries
            concurrent: Enable concurrent extraction
            max_workers: Maximum concurrent workers
            callback_url: Optional webhook URL for completion notification
            metadata: Additional metadata
        
        Returns:
            Job ID
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/extract",
                headers=self.headers,
                json={
                    "properties": properties,
                    "concurrent": concurrent,
                    "max_workers": max_workers,
                    "callback_url": callback_url,
                    "metadata": metadata
                }
            )
            response.raise_for_status()
            return response.json()["job_id"]
    
    async def extract_from_urls(
        self,
        urls: List[str],
        concurrent: bool = True,
        max_workers: int = 5,
        callback_url: Optional[str] = None
    ) -> str:
        """
        Submit URLs for tax extraction
        
        Args:
            urls: List of tax bill URLs
            concurrent: Enable concurrent extraction
            max_workers: Maximum concurrent workers
            callback_url: Optional webhook URL
        
        Returns:
            Job ID
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/extract",
                headers=self.headers,
                json={
                    "urls": urls,
                    "concurrent": concurrent,
                    "max_workers": max_workers,
                    "callback_url": callback_url
                }
            )
            response.raise_for_status()
            return response.json()["job_id"]
    
    async def upload_csv(
        self,
        file_path: Union[str, Path],
        concurrent: bool = True,
        max_workers: int = 5
    ) -> str:
        """
        Upload CSV file for extraction
        
        Args:
            file_path: Path to CSV file
            concurrent: Enable concurrent extraction
            max_workers: Maximum concurrent workers
        
        Returns:
            Job ID
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            with open(file_path, 'rb') as f:
                files = {"file": (file_path.name, f, "text/csv")}
                response = await client.post(
                    f"{self.base_url}/api/v1/extract/upload",
                    headers={"Authorization": f"Bearer {self.api_token}"},
                    files=files,
                    params={
                        "concurrent": concurrent,
                        "max_workers": max_workers
                    }
                )
            response.raise_for_status()
            return response.json()["job_id"]
    
    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get job status
        
        Args:
            job_id: Job identifier
        
        Returns:
            Job status dictionary
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/api/v1/jobs/{job_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def wait_for_completion(
        self,
        job_id: str,
        poll_interval: int = 5,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Wait for job to complete
        
        Args:
            job_id: Job identifier
            poll_interval: Seconds between status checks
            timeout: Maximum wait time in seconds
        
        Returns:
            Final job status
        """
        start_time = time.time()
        
        while True:
            status = await self.get_job_status(job_id)
            
            if status["status"] in ["completed", "failed", "cancelled"]:
                return status
            
            if timeout and (time.time() - start_time) > timeout:
                raise TimeoutError(f"Job {job_id} did not complete within {timeout} seconds")
            
            await asyncio.sleep(poll_interval)
    
    async def get_results(
        self,
        job_id: str,
        format: str = "json",
        output_file: Optional[Union[str, Path]] = None
    ) -> Union[Dict[str, Any], bytes]:
        """
        Get extraction results
        
        Args:
            job_id: Job identifier
            format: Output format (json, excel, csv, parquet)
            output_file: Optional file path to save results
        
        Returns:
            Results data or bytes
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/api/v1/jobs/{job_id}/results",
                headers=self.headers,
                params={"format": format}
            )
            response.raise_for_status()
            
            if format == "json":
                data = response.json()
                if output_file:
                    with open(output_file, 'w') as f:
                        json.dump(data, f, indent=2)
                return data
            else:
                # Binary formats
                content = response.content
                if output_file:
                    with open(output_file, 'wb') as f:
                        f.write(content)
                return content
    
    async def list_jobs(
        self,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        List extraction jobs
        
        Args:
            status: Filter by status
            page: Page number
            page_size: Items per page
        
        Returns:
            Job list with pagination
        """
        params = {"page": page, "page_size": page_size}
        if status:
            params["status"] = status
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/api/v1/jobs",
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            return response.json()
    
    async def cancel_job(self, job_id: str) -> Dict[str, Any]:
        """
        Cancel a job
        
        Args:
            job_id: Job identifier
        
        Returns:
            Cancellation confirmation
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.delete(
                f"{self.base_url}/api/v1/jobs/{job_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get service statistics
        
        Returns:
            Statistics dictionary
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/api/v1/stats",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check service health
        
        Returns:
            Health status
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/health"
            )
            response.raise_for_status()
            return response.json()
    
    async def batch_extract(
        self,
        properties_list: List[List[Dict[str, Any]]],
        batch_size: int = 100,
        concurrent: bool = True,
        max_workers: int = 5
    ) -> List[str]:
        """
        Submit multiple batches of properties
        
        Args:
            properties_list: List of property batches
            batch_size: Maximum properties per batch
            concurrent: Enable concurrent extraction
            max_workers: Maximum concurrent workers
        
        Returns:
            List of job IDs
        """
        job_ids = []
        
        for batch in properties_list:
            # Split large batches
            for i in range(0, len(batch), batch_size):
                chunk = batch[i:i + batch_size]
                job_id = await self.extract_properties(
                    chunk,
                    concurrent=concurrent,
                    max_workers=max_workers
                )
                job_ids.append(job_id)
        
        return job_ids
    
    async def extract_and_wait(
        self,
        properties: List[Dict[str, Any]],
        format: str = "json",
        poll_interval: int = 5,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Submit extraction and wait for results
        
        Args:
            properties: List of properties
            format: Output format
            poll_interval: Status check interval
            timeout: Maximum wait time
        
        Returns:
            Extraction results
        """
        # Submit job
        job_id = await self.extract_properties(properties)
        
        # Wait for completion
        status = await self.wait_for_completion(
            job_id,
            poll_interval=poll_interval,
            timeout=timeout
        )
        
        if status["status"] == "completed":
            # Get results
            return await self.get_results(job_id, format=format)
        else:
            raise Exception(f"Job failed: {status.get('error', 'Unknown error')}")


class SyncTaxExtractorClient:
    """
    Synchronous wrapper for TaxExtractorClient
    
    For use in non-async environments
    """
    
    def __init__(self, base_url: str, api_token: str, timeout: int = 30):
        self.async_client = TaxExtractorClient(base_url, api_token, timeout)
    
    def _run_async(self, coro):
        """Run async coroutine in sync context"""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    
    def extract_properties(self, properties: List[Dict[str, Any]], **kwargs) -> str:
        return self._run_async(
            self.async_client.extract_properties(properties, **kwargs)
        )
    
    def extract_from_urls(self, urls: List[str], **kwargs) -> str:
        return self._run_async(
            self.async_client.extract_from_urls(urls, **kwargs)
        )
    
    def upload_csv(self, file_path: Union[str, Path], **kwargs) -> str:
        return self._run_async(
            self.async_client.upload_csv(file_path, **kwargs)
        )
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        return self._run_async(
            self.async_client.get_job_status(job_id)
        )
    
    def wait_for_completion(self, job_id: str, **kwargs) -> Dict[str, Any]:
        return self._run_async(
            self.async_client.wait_for_completion(job_id, **kwargs)
        )
    
    def get_results(self, job_id: str, **kwargs) -> Union[Dict[str, Any], bytes]:
        return self._run_async(
            self.async_client.get_results(job_id, **kwargs)
        )
    
    def list_jobs(self, **kwargs) -> Dict[str, Any]:
        return self._run_async(
            self.async_client.list_jobs(**kwargs)
        )
    
    def cancel_job(self, job_id: str) -> Dict[str, Any]:
        return self._run_async(
            self.async_client.cancel_job(job_id)
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        return self._run_async(
            self.async_client.get_statistics()
        )
    
    def health_check(self) -> Dict[str, Any]:
        return self._run_async(
            self.async_client.health_check()
        )
    
    def extract_and_wait(self, properties: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        return self._run_async(
            self.async_client.extract_and_wait(properties, **kwargs)
        )


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def main():
        # Initialize client
        client = TaxExtractorClient(
            base_url="http://localhost:8000",
            api_token="your-api-token-here"
        )
        
        # Example 1: Extract from properties
        properties = [
            {
                "property_name": "123 Main St",
                "property_address": "123 Main St, Houston, TX 77001",
                "state": "TX",
                "tax_bill_link": "https://www.hctax.net/property/123"
            }
        ]
        
        try:
            # Submit job
            job_id = await client.extract_properties(properties)
            print(f"Job submitted: {job_id}")
            
            # Wait for completion
            status = await client.wait_for_completion(job_id)
            print(f"Job completed: {status['successful']} successful, {status['failed']} failed")
            
            # Get results
            results = await client.get_results(job_id, format="json")
            print(f"Results: {json.dumps(results, indent=2)}")
            
        except Exception as e:
            print(f"Error: {e}")
        
        # Example 2: Upload CSV
        try:
            job_id = await client.upload_csv("properties.csv")
            print(f"CSV upload job: {job_id}")
            
            # Monitor progress
            while True:
                status = await client.get_job_status(job_id)
                print(f"Progress: {status['progress']}%")
                
                if status["status"] in ["completed", "failed"]:
                    break
                
                await asyncio.sleep(5)
            
        except Exception as e:
            print(f"Error: {e}")
        
        # Example 3: Get statistics
        stats = await client.get_statistics()
        print(f"Service statistics: {json.dumps(stats, indent=2)}")
    
    # Run async example
    # asyncio.run(main())
    
    # Synchronous example
    sync_client = SyncTaxExtractorClient(
        base_url="http://localhost:8000",
        api_token="your-api-token-here"
    )
    
    # Submit and wait synchronously
    # results = sync_client.extract_and_wait(properties)
    # print(results)