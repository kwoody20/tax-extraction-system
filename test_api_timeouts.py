#!/usr/bin/env python3
"""
Test script to verify API endpoints are responsive after timeout fixes.
"""

import asyncio
import aiohttp
import time
from typing import Dict, Any

# Production API URL
BASE_URL = "https://tax-extraction-system-production.up.railway.app"

# Test endpoints
ENDPOINTS = [
    "/livez",
    "/health", 
    "/api/v1/properties?limit=10",
    "/api/v1/entities?limit=10",
    "/api/v1/statistics",
    "/api/v1/jurisdictions"
]

async def test_endpoint(session: aiohttp.ClientSession, endpoint: str) -> Dict[str, Any]:
    """Test a single endpoint and measure response time."""
    url = f"{BASE_URL}{endpoint}"
    start_time = time.time()
    
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
            response_time = (time.time() - start_time) * 1000  # Convert to ms
            
            # Try to get JSON response
            try:
                data = await response.json()
            except:
                data = await response.text()
            
            return {
                "endpoint": endpoint,
                "status": response.status,
                "response_time_ms": round(response_time, 2),
                "success": response.status == 200,
                "error": None
            }
    
    except asyncio.TimeoutError:
        response_time = (time.time() - start_time) * 1000
        return {
            "endpoint": endpoint,
            "status": "TIMEOUT",
            "response_time_ms": round(response_time, 2),
            "success": False,
            "error": "Request timed out after 30 seconds"
        }
    
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        return {
            "endpoint": endpoint,
            "status": "ERROR",
            "response_time_ms": round(response_time, 2),
            "success": False,
            "error": str(e)
        }

async def test_all_endpoints():
    """Test all endpoints concurrently."""
    print(f"Testing API endpoints at {BASE_URL}")
    print("=" * 80)
    
    async with aiohttp.ClientSession() as session:
        # First, warm up with livez endpoint
        print("Warming up API...")
        await test_endpoint(session, "/livez")
        
        # Test all endpoints concurrently
        print("\nTesting all endpoints...")
        tasks = [test_endpoint(session, endpoint) for endpoint in ENDPOINTS]
        results = await asyncio.gather(*tasks)
        
        # Display results
        print("\n" + "=" * 80)
        print(f"{'Endpoint':<40} {'Status':<10} {'Time (ms)':<12} {'Result'}")
        print("-" * 80)
        
        for result in results:
            status_str = str(result['status'])
            if result['success']:
                status_emoji = "✅"
            else:
                status_emoji = "❌"
            
            print(f"{result['endpoint']:<40} {status_str:<10} {result['response_time_ms']:<12.2f} {status_emoji}")
            
            if result['error']:
                print(f"  └─ Error: {result['error']}")
        
        # Summary
        print("\n" + "=" * 80)
        successful = sum(1 for r in results if r['success'])
        total = len(results)
        avg_response_time = sum(r['response_time_ms'] for r in results if r['success']) / max(successful, 1)
        
        print(f"Summary: {successful}/{total} endpoints successful")
        print(f"Average response time: {avg_response_time:.2f} ms")
        
        # Recommendations
        print("\n" + "=" * 80)
        print("Recommendations:")
        
        slow_endpoints = [r for r in results if r['success'] and r['response_time_ms'] > 5000]
        if slow_endpoints:
            print("⚠️  The following endpoints are slow (>5s):")
            for endpoint in slow_endpoints:
                print(f"   - {endpoint['endpoint']}: {endpoint['response_time_ms']:.2f} ms")
        
        failed_endpoints = [r for r in results if not r['success']]
        if failed_endpoints:
            print("❌ The following endpoints failed:")
            for endpoint in failed_endpoints:
                print(f"   - {endpoint['endpoint']}: {endpoint['error']}")
        
        if successful == total and avg_response_time < 3000:
            print("✅ All endpoints are healthy and responsive!")

if __name__ == "__main__":
    asyncio.run(test_all_endpoints())