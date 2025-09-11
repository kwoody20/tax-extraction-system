#!/usr/bin/env python3
"""
Test script to verify API works without connection pooling.
"""

import requests
import time
import json

# API base URL - adjust if needed
BASE_URL = "https://tax-extraction-system-production.up.railway.app"

def test_endpoint(endpoint: str, timeout: int = 30) -> tuple:
    """Test an endpoint and return status code and response time."""
    try:
        start = time.time()
        response = requests.get(f"{BASE_URL}{endpoint}", timeout=timeout)
        elapsed = time.time() - start
        
        print(f"✓ {endpoint}: {response.status_code} in {elapsed:.2f}s")
        
        if response.status_code == 200:
            try:
                data = response.json()
                if isinstance(data, dict):
                    print(f"  Response keys: {list(data.keys())[:5]}...")
                elif isinstance(data, list):
                    print(f"  Response: list with {len(data)} items")
            except:
                print(f"  Response: {response.text[:100]}...")
        
        return response.status_code, elapsed
        
    except requests.Timeout:
        print(f"✗ {endpoint}: TIMEOUT after {timeout}s")
        return None, timeout
    except Exception as e:
        print(f"✗ {endpoint}: ERROR - {str(e)}")
        return None, None

def main():
    """Test all critical endpoints."""
    print("Testing API endpoints without connection pooling...")
    print(f"Target: {BASE_URL}\n")
    
    endpoints = [
        ("/livez", 5),  # Simple liveness check
        ("/health", 10),  # Health check with DB
        ("/api/v1/statistics", 15),  # Statistics endpoint
        ("/api/v1/properties?limit=1", 15),  # Properties with limit
        ("/api/v1/entities?limit=1", 15),  # Entities with limit
        ("/api/v1/jurisdictions", 10),  # Jurisdictions
    ]
    
    results = []
    for endpoint, timeout in endpoints:
        status, elapsed = test_endpoint(endpoint, timeout)
        results.append({
            "endpoint": endpoint,
            "status": status,
            "time": elapsed
        })
        time.sleep(1)  # Small delay between requests
    
    print("\n" + "="*50)
    print("SUMMARY:")
    print("="*50)
    
    successful = sum(1 for r in results if r["status"] == 200)
    total = len(results)
    
    print(f"Successful: {successful}/{total}")
    
    if successful == total:
        print("✅ All endpoints working without connection pooling!")
    elif successful > 0:
        print("⚠️ Some endpoints working - partial success")
    else:
        print("❌ No endpoints working - check deployment")
    
    # Show failed endpoints
    failed = [r for r in results if r["status"] != 200]
    if failed:
        print("\nFailed endpoints:")
        for r in failed:
            print(f"  - {r['endpoint']}")

if __name__ == "__main__":
    main()