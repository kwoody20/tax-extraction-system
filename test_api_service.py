"""
Comprehensive test suite for the enhanced Tax Extractor API
"""

import pytest
import asyncio
import json
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from httpx import AsyncClient
import tempfile
import os
from unittest.mock import Mock, patch, AsyncMock

# Import the API app
from api_service_enhanced import (
    app, 
    ExtractionRequest, 
    PropertyInput,
    JobStatus,
    OutputFormat,
    store_job,
    get_job,
    update_job
)

# Test fixtures
@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)

@pytest.fixture
def async_client():
    """Create async test client"""
    return AsyncClient(app=app, base_url="http://test")

@pytest.fixture
def auth_headers():
    """Create authentication headers"""
    return {"Authorization": "Bearer test-token-123456789"}

@pytest.fixture
def sample_property():
    """Create sample property data"""
    return PropertyInput(
        property_name="123 Main St",
        property_address="123 Main St, Houston, TX 77001",
        jurisdiction="Harris County",
        state="TX",
        account_number="12345",
        tax_bill_link="https://www.hctax.net/property/12345"
    )

@pytest.fixture
def sample_extraction_request(sample_property):
    """Create sample extraction request"""
    return ExtractionRequest(
        properties=[sample_property],
        concurrent=True,
        max_workers=5,
        save_screenshots=False
    )

@pytest.fixture
def sample_csv_file():
    """Create sample CSV file"""
    df = pd.DataFrame({
        'Property Name': ['Property 1', 'Property 2'],
        'Tax Bill Link': [
            'https://example.com/tax/1',
            'https://example.com/tax/2'
        ],
        'State': ['TX', 'AZ']
    })
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        df.to_csv(f, index=False)
        return f.name

# Unit Tests

class TestModels:
    """Test Pydantic models"""
    
    def test_property_input_validation(self):
        """Test PropertyInput model validation"""
        # Valid property
        prop = PropertyInput(
            property_name="Test Property",
            tax_bill_link="https://example.com/tax"
        )
        assert prop.property_name == "Test Property"
        
        # Invalid URL
        with pytest.raises(ValueError):
            PropertyInput(
                property_name="Test",
                tax_bill_link="not-a-url"
            )
        
        # State code validation
        prop = PropertyInput(
            property_name="Test",
            state="tx",
            tax_bill_link="https://example.com"
        )
        assert prop.state == "TX"  # Should be uppercase
    
    def test_extraction_request_validation(self):
        """Test ExtractionRequest model validation"""
        # Valid request with properties
        req = ExtractionRequest(
            properties=[
                PropertyInput(
                    property_name="Test",
                    tax_bill_link="https://example.com"
                )
            ]
        )
        assert len(req.properties) == 1
        
        # Invalid: multiple input sources
        with pytest.raises(ValueError):
            ExtractionRequest(
                properties=[],
                csv_file_path="/path/to/file.csv",
                urls=["https://example.com"]
            )
        
        # Valid: max workers range
        req = ExtractionRequest(
            urls=["https://example.com"],
            max_workers=20
        )
        assert req.max_workers == 20
        
        with pytest.raises(ValueError):
            ExtractionRequest(
                urls=["https://example.com"],
                max_workers=25  # Exceeds maximum
            )

class TestAPIEndpoints:
    """Test API endpoints"""
    
    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert data["service"] == "Tax Extractor API"
        assert "endpoints" in data
    
    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        assert "components" in data
    
    @pytest.mark.asyncio
    async def test_submit_extraction(self, async_client, sample_extraction_request, auth_headers):
        """Test extraction submission"""
        with patch('api_service_enhanced.verify_token', return_value="test-token"):
            response = await async_client.post(
                "/api/v1/extract",
                json=sample_extraction_request.dict(),
                headers=auth_headers
            )
            
            assert response.status_code == 202
            data = response.json()
            assert "job_id" in data
            assert data["status"] == "queued"
            assert "message" in data
    
    @pytest.mark.asyncio
    async def test_upload_and_extract(self, async_client, sample_csv_file, auth_headers):
        """Test file upload and extraction"""
        with patch('api_service_enhanced.verify_token', return_value="test-token"):
            with open(sample_csv_file, 'rb') as f:
                response = await async_client.post(
                    "/api/v1/extract/upload",
                    files={"file": ("test.csv", f, "text/csv")},
                    params={"concurrent": True, "max_workers": 5},
                    headers=auth_headers
                )
            
            assert response.status_code == 202
            data = response.json()
            assert "job_id" in data
            assert "2 properties queued" in data["message"]
        
        # Cleanup
        os.unlink(sample_csv_file)
    
    @pytest.mark.asyncio
    async def test_get_job_status(self, async_client, auth_headers):
        """Test job status retrieval"""
        # Create a test job
        job_id = "test-job-123"
        await store_job(job_id, {
            "job_id": job_id,
            "status": JobStatus.RUNNING,
            "progress": 50,
            "total_properties": 10,
            "processed": 5,
            "successful": 4,
            "failed": 1,
            "created_at": datetime.now()
        })
        
        with patch('api_service_enhanced.verify_token', return_value="test-token"):
            response = await async_client.get(
                f"/api/v1/jobs/{job_id}",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["job_id"] == job_id
            assert data["status"] == "running"
            assert data["progress"] == 50
    
    @pytest.mark.asyncio
    async def test_get_job_results(self, async_client, auth_headers):
        """Test job results retrieval"""
        # Create a completed job with results
        job_id = "completed-job-123"
        
        # Create a test results file
        df = pd.DataFrame({
            'Property Name': ['Test Property'],
            'Tax Amount': [1000.00]
        })
        results_file = f"/tmp/results_{job_id}.xlsx"
        df.to_excel(results_file, index=False, sheet_name='Results')
        
        await store_job(job_id, {
            "job_id": job_id,
            "status": JobStatus.COMPLETED,
            "results_file": results_file,
            "results_available": True,
            "created_at": datetime.now(),
            "completed_at": datetime.now()
        })
        
        with patch('api_service_enhanced.verify_token', return_value="test-token"):
            # Test JSON format
            response = await async_client.get(
                f"/api/v1/jobs/{job_id}/results",
                params={"format": "json"},
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            assert len(data["data"]) == 1
        
        # Cleanup
        if os.path.exists(results_file):
            os.unlink(results_file)
    
    @pytest.mark.asyncio
    async def test_list_jobs(self, async_client, auth_headers):
        """Test job listing with pagination"""
        # Create multiple test jobs
        for i in range(5):
            await store_job(f"test-job-{i}", {
                "job_id": f"test-job-{i}",
                "status": JobStatus.COMPLETED if i % 2 == 0 else JobStatus.FAILED,
                "created_at": datetime.now() - timedelta(hours=i)
            })
        
        with patch('api_service_enhanced.verify_token', return_value="test-token"):
            # Test basic listing
            response = await async_client.get(
                "/api/v1/jobs",
                params={"page": 1, "page_size": 3},
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] >= 5
            assert len(data["jobs"]) <= 3
            
            # Test filtering by status
            response = await async_client.get(
                "/api/v1/jobs",
                params={"status": "completed"},
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert all(job["status"] == "completed" for job in data["jobs"])
    
    @pytest.mark.asyncio
    async def test_cancel_job(self, async_client, auth_headers):
        """Test job cancellation"""
        # Create a running job
        job_id = "running-job-123"
        await store_job(job_id, {
            "job_id": job_id,
            "status": JobStatus.RUNNING,
            "created_at": datetime.now()
        })
        
        with patch('api_service_enhanced.verify_token', return_value="test-token"):
            response = await async_client.delete(
                f"/api/v1/jobs/{job_id}",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "cancelled successfully" in data["message"]
            
            # Verify job status updated
            job = await get_job(job_id)
            assert job["status"] == JobStatus.CANCELLED
    
    @pytest.mark.asyncio
    async def test_statistics_endpoint(self, async_client, auth_headers):
        """Test statistics endpoint"""
        # Create test jobs with various statuses
        await store_job("stat-job-1", {
            "job_id": "stat-job-1",
            "status": JobStatus.COMPLETED,
            "total_properties": 10,
            "successful": 8,
            "failed": 2,
            "duration_seconds": 120,
            "created_at": datetime.now()
        })
        
        await store_job("stat-job-2", {
            "job_id": "stat-job-2",
            "status": JobStatus.RUNNING,
            "total_properties": 5,
            "successful": 2,
            "failed": 0,
            "created_at": datetime.now()
        })
        
        with patch('api_service_enhanced.verify_token', return_value="test-token"):
            response = await async_client.get(
                "/api/v1/stats",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "total_jobs" in data
            assert "status_breakdown" in data
            assert "success_rate_percent" in data
            assert data["total_jobs"] >= 2

class TestErrorHandling:
    """Test error handling"""
    
    def test_404_not_found(self, client, auth_headers):
        """Test 404 error for non-existent job"""
        with patch('api_service_enhanced.verify_token', return_value="test-token"):
            response = client.get(
                "/api/v1/jobs/non-existent-job",
                headers=auth_headers
            )
            
            assert response.status_code == 404
            data = response.json()
            assert "error" in data
            assert "not found" in data["message"].lower()
    
    def test_validation_error(self, client, auth_headers):
        """Test validation error handling"""
        with patch('api_service_enhanced.verify_token', return_value="test-token"):
            # Invalid extraction request
            response = client.post(
                "/api/v1/extract",
                json={
                    "properties": [
                        {
                            "property_name": "",  # Empty name
                            "tax_bill_link": "not-a-url"  # Invalid URL
                        }
                    ]
                },
                headers=auth_headers
            )
            
            assert response.status_code == 422
            data = response.json()
            assert "error" in data
    
    def test_authentication_error(self, client):
        """Test authentication error"""
        response = client.get("/api/v1/jobs")
        assert response.status_code == 401

class TestRateLimiting:
    """Test rate limiting functionality"""
    
    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self, async_client, auth_headers):
        """Test that rate limits are enforced"""
        with patch('api_service_enhanced.verify_token', return_value="test-token"):
            # Make multiple rapid requests
            responses = []
            for _ in range(15):  # Exceed 10/minute limit
                response = await async_client.post(
                    "/api/v1/extract",
                    json={"urls": ["https://example.com"]},
                    headers=auth_headers
                )
                responses.append(response.status_code)
            
            # Some requests should be rate limited
            assert 429 in responses  # Too Many Requests

class TestBackgroundTasks:
    """Test background task processing"""
    
    @pytest.mark.asyncio
    async def test_extraction_task_success(self):
        """Test successful extraction task"""
        from api_service_enhanced import run_extraction_task
        
        job_id = "test-extraction-job"
        request = ExtractionRequest(
            urls=["https://example.com/tax/123"],
            concurrent=False,
            max_workers=1
        )
        
        # Mock the extractor
        with patch('api_service_enhanced.TaxExtractor') as mock_extractor:
            mock_instance = Mock()
            mock_instance.run_extraction.return_value = (1, 0)  # 1 success, 0 failures
            mock_extractor.return_value = mock_instance
            
            # Store initial job
            await store_job(job_id, {
                "job_id": job_id,
                "status": JobStatus.PENDING,
                "created_at": datetime.now()
            })
            
            # Run the task
            await run_extraction_task(job_id, request)
            
            # Verify job completed
            job = await get_job(job_id)
            assert job["status"] == JobStatus.COMPLETED
            assert job["successful"] == 1
            assert job["failed"] == 0

class TestWebhooks:
    """Test webhook functionality"""
    
    @pytest.mark.asyncio
    async def test_webhook_trigger(self):
        """Test webhook is triggered on job completion"""
        from api_service_enhanced import trigger_webhook
        
        job_id = "webhook-test-job"
        callback_url = "https://example.com/webhook"
        
        await store_job(job_id, {
            "job_id": job_id,
            "status": JobStatus.COMPLETED,
            "successful": 5,
            "failed": 0,
            "completed_at": datetime.now()
        })
        
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value.status_code = 200
            
            await trigger_webhook(job_id, callback_url)
            
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[0][0] == callback_url
            assert "job_id" in call_args[1]["json"]

# Integration Tests

class TestIntegration:
    """End-to-end integration tests"""
    
    @pytest.mark.asyncio
    async def test_full_extraction_workflow(self, async_client, auth_headers):
        """Test complete extraction workflow"""
        with patch('api_service_enhanced.verify_token', return_value="test-token"):
            # 1. Submit extraction job
            response = await async_client.post(
                "/api/v1/extract",
                json={
                    "urls": ["https://example.com/tax/123"],
                    "concurrent": False
                },
                headers=auth_headers
            )
            
            assert response.status_code == 202
            job_id = response.json()["job_id"]
            
            # 2. Check job status
            response = await async_client.get(
                f"/api/v1/jobs/{job_id}",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            status = response.json()["status"]
            assert status in [JobStatus.PENDING, JobStatus.QUEUED, JobStatus.RUNNING]
            
            # 3. Simulate job completion
            await update_job(job_id, {
                "status": JobStatus.COMPLETED,
                "completed_at": datetime.now(),
                "successful": 1,
                "failed": 0,
                "results_available": True,
                "results_file": "/tmp/test_results.xlsx"
            })
            
            # 4. Check final status
            response = await async_client.get(
                f"/api/v1/jobs/{job_id}",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == JobStatus.COMPLETED
            assert data["successful"] == 1

# Performance Tests

class TestPerformance:
    """Performance and load tests"""
    
    @pytest.mark.asyncio
    async def test_concurrent_job_submission(self, async_client, auth_headers):
        """Test handling multiple concurrent job submissions"""
        with patch('api_service_enhanced.verify_token', return_value="test-token"):
            tasks = []
            for i in range(10):
                task = async_client.post(
                    "/api/v1/extract",
                    json={"urls": [f"https://example.com/tax/{i}"]},
                    headers=auth_headers
                )
                tasks.append(task)
            
            responses = await asyncio.gather(*tasks)
            
            # All should succeed
            for response in responses:
                assert response.status_code in [202, 429]  # Accepted or rate limited

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=api_service_enhanced"])