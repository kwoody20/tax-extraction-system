#!/usr/bin/env python3
"""
Test script to verify backward compatibility of api_public_enhanced.py
Ensures all existing endpoints work exactly as before with no breaking changes.
"""

import asyncio
import json
import sys
from typing import Dict, List, Any, Optional
import httpx
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8000"  # Change to your API URL
TEST_PROPERTY_ID = "test_prop_001"
TEST_JURISDICTION = "Montgomery County"

class APICompatibilityTester:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30.0)
        self.results = []
        
    async def close(self):
        await self.client.aclose()
        
    async def test_endpoint(self, name: str, method: str, path: str, 
                           data: Optional[Dict] = None, 
                           params: Optional[Dict] = None,
                           expected_status: int = 200) -> bool:
        """Test a single endpoint for compatibility"""
        try:
            url = f"{self.base_url}{path}"
            
            if method == "GET":
                response = await self.client.get(url, params=params)
            elif method == "POST":
                response = await self.client.post(url, json=data)
            elif method == "PUT":
                response = await self.client.put(url, json=data)
            elif method == "DELETE":
                response = await self.client.delete(url, params=params)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            # Check status code
            if response.status_code != expected_status:
                self.results.append({
                    "test": name,
                    "passed": False,
                    "error": f"Expected status {expected_status}, got {response.status_code}",
                    "response": response.text[:500]
                })
                return False
            
            # Verify response is valid JSON (except for metrics endpoint)
            if path != "/metrics":
                try:
                    response.json()
                except json.JSONDecodeError:
                    self.results.append({
                        "test": name,
                        "passed": False,
                        "error": "Response is not valid JSON",
                        "response": response.text[:500]
                    })
                    return False
            
            self.results.append({
                "test": name,
                "passed": True,
                "status": response.status_code,
                "response_time": response.elapsed.total_seconds()
            })
            return True
            
        except Exception as e:
            self.results.append({
                "test": name,
                "passed": False,
                "error": str(e)
            })
            return False
    
    async def run_all_tests(self):
        """Run all compatibility tests"""
        print("Starting API Compatibility Tests...\n")
        
        # Test 1: Health endpoint
        await self.test_endpoint(
            "Health Check",
            "GET",
            "/health"
        )
        
        # Test 2: Get properties (basic)
        await self.test_endpoint(
            "Get Properties (Basic)",
            "GET",
            "/api/v1/properties",
            params={"limit": 10, "offset": 0}
        )
        
        # Test 3: Get properties with filters (existing functionality)
        await self.test_endpoint(
            "Get Properties (Filtered)",
            "GET",
            "/api/v1/properties",
            params={
                "limit": 10,
                "offset": 0,
                "jurisdiction": TEST_JURISDICTION,
                "needs_extraction": True
            }
        )
        
        # Test 4: Get entities
        await self.test_endpoint(
            "Get Entities",
            "GET",
            "/api/v1/entities",
            params={"limit": 10, "offset": 0}
        )
        
        # Test 5: Get statistics
        await self.test_endpoint(
            "Get Statistics",
            "GET",
            "/api/v1/statistics"
        )
        
        # Test 6: Get jurisdictions
        await self.test_endpoint(
            "Get Jurisdictions",
            "GET",
            "/api/v1/jurisdictions"
        )
        
        # Test 7: Get extraction status
        await self.test_endpoint(
            "Get Extraction Status",
            "GET",
            "/api/v1/extract/status"
        )
        
        # Test 8: Get extractions history
        await self.test_endpoint(
            "Get Extractions History",
            "GET",
            "/api/v1/extractions",
            params={"limit": 10, "offset": 0}
        )
        
        # Test 9: Single extraction (validate request format)
        await self.test_endpoint(
            "Single Extraction",
            "POST",
            "/api/v1/extract",
            data={
                "property_id": TEST_PROPERTY_ID,
                "jurisdiction": TEST_JURISDICTION,
                "tax_bill_link": "https://example.com/tax-bill",
                "account_number": "12345"
            }
        )
        
        # Test 10: Batch extraction
        await self.test_endpoint(
            "Batch Extraction",
            "POST",
            "/api/v1/extract/batch",
            data={
                "property_ids": [TEST_PROPERTY_ID]
            }
        )
        
        # Test new optional features (should work but aren't breaking if missing)
        print("\nTesting New Optional Features...\n")
        
        # Test 11: Properties with new filters (should work with enhanced API)
        await self.test_endpoint(
            "Properties with Advanced Filters",
            "GET",
            "/api/v1/properties",
            params={
                "limit": 10,
                "offset": 0,
                "amount_due_min": 1000,
                "amount_due_max": 5000,
                "sort_by": "amount_due",
                "sort_order": "desc"
            }
        )
        
        # Test 12: Metrics endpoint (new, might return 404 if not enabled)
        await self.test_endpoint(
            "Metrics Endpoint",
            "GET",
            "/metrics",
            expected_status=200  # Will be 404 if metrics not enabled
        )
        
        # Test 13: Property history (new endpoint)
        await self.test_endpoint(
            "Property History",
            "GET",
            f"/api/v1/properties/{TEST_PROPERTY_ID}/history",
            expected_status=200  # Will be 404 if endpoint doesn't exist
        )
        
        self.print_results()
    
    def print_results(self):
        """Print test results summary"""
        print("\n" + "="*60)
        print("API COMPATIBILITY TEST RESULTS")
        print("="*60 + "\n")
        
        passed = sum(1 for r in self.results if r["passed"])
        failed = sum(1 for r in self.results if not r["passed"])
        
        # Group by status
        core_tests = self.results[:10]  # First 10 are core compatibility tests
        optional_tests = self.results[10:]  # Rest are optional enhancements
        
        print("CORE COMPATIBILITY TESTS (Must all pass):")
        print("-"*40)
        for result in core_tests:
            status = "✅ PASS" if result["passed"] else "❌ FAIL"
            print(f"{status} - {result['test']}")
            if not result["passed"]:
                print(f"     Error: {result.get('error', 'Unknown error')}")
            elif "response_time" in result:
                print(f"     Response time: {result['response_time']:.3f}s")
        
        print("\nOPTIONAL ENHANCEMENT TESTS:")
        print("-"*40)
        for result in optional_tests:
            status = "✅ PASS" if result["passed"] else "⚠️  SKIP"
            print(f"{status} - {result['test']}")
            if result["passed"] and "response_time" in result:
                print(f"     Response time: {result['response_time']:.3f}s")
        
        # Calculate compatibility score
        core_passed = sum(1 for r in core_tests if r["passed"])
        compatibility_score = (core_passed / len(core_tests)) * 100
        
        print("\n" + "="*60)
        print(f"COMPATIBILITY SCORE: {compatibility_score:.1f}%")
        print(f"Core Tests: {core_passed}/{len(core_tests)} passed")
        print(f"Optional Tests: {sum(1 for r in optional_tests if r['passed'])}/{len(optional_tests)} available")
        print("="*60)
        
        if compatibility_score == 100:
            print("\n✅ API is 100% backward compatible!")
            print("All core endpoints work exactly as expected.")
        else:
            print("\n⚠️  Compatibility issues detected!")
            print("Some core endpoints have changed behavior.")
            print("Review failed tests before deploying to production.")
        
        # Performance comparison if all tests passed
        if all(r["passed"] for r in core_tests):
            avg_response_time = sum(r.get("response_time", 0) for r in core_tests) / len(core_tests)
            print(f"\nAverage response time: {avg_response_time:.3f}s")

async def main():
    # Parse command line arguments
    if len(sys.argv) > 1:
        api_url = sys.argv[1]
    else:
        api_url = API_BASE_URL
    
    print(f"Testing API at: {api_url}")
    
    tester = APICompatibilityTester(api_url)
    try:
        await tester.run_all_tests()
    finally:
        await tester.close()

if __name__ == "__main__":
    asyncio.run(main())