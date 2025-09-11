#!/usr/bin/env python3
"""
Test script to measure API endpoint performance after optimizations.
"""
import os
import time
import requests
import json
from statistics import mean, median

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# API base URL
BASE_URL = "http://localhost:8000"

def test_endpoint(name, url, params=None):
    """Test an endpoint and measure response time."""
    print(f"\n📊 Testing {name}...")
    print(f"   URL: {url}")
    if params:
        print(f"   Params: {params}")
    
    response_times = []
    errors = []
    
    # Run multiple tests
    for i in range(5):
        try:
            start = time.time()
            response = requests.get(url, params=params, timeout=10)
            elapsed = time.time() - start
            response_times.append(elapsed)
            
            if response.status_code == 200:
                data = response.json()
                if i == 0:  # Print first response details
                    if 'count' in data:
                        print(f"   ✓ Retrieved {data.get('count')} items")
                    elif 'total_properties' in data:
                        print(f"   ✓ Total properties: {data.get('total_properties')}")
                    elif 'jurisdictions' in data:
                        print(f"   ✓ Total jurisdictions: {len(data.get('jurisdictions', []))}")
                    elif 'entities' in data:
                        print(f"   ✓ Total entities: {len(data.get('entities', []))}")
            else:
                errors.append(f"Status {response.status_code}: {response.text[:100]}")
                
        except Exception as e:
            errors.append(str(e))
            response_times.append(10.0)  # Timeout value
    
    # Calculate statistics
    if response_times:
        avg_time = mean(response_times)
        med_time = median(response_times)
        min_time = min(response_times)
        max_time = max(response_times)
        
        print(f"\n   📈 Performance Results:")
        print(f"      Average: {avg_time:.3f}s")
        print(f"      Median:  {med_time:.3f}s")
        print(f"      Min:     {min_time:.3f}s")
        print(f"      Max:     {max_time:.3f}s")
        
        # Performance assessment
        if avg_time < 0.5:
            print(f"      Status: ✅ EXCELLENT (< 0.5s)")
        elif avg_time < 1.0:
            print(f"      Status: ✅ GOOD (< 1s)")
        elif avg_time < 2.0:
            print(f"      Status: ⚠️ ACCEPTABLE (< 2s)")
        else:
            print(f"      Status: ❌ SLOW (> 2s)")
    
    if errors:
        print(f"\n   ⚠️ Errors encountered:")
        for error in errors[:3]:  # Show first 3 errors
            print(f"      - {error}")
    
    return response_times

def main():
    print("=" * 60)
    print("🚀 TAX EXTRACTION API PERFORMANCE TEST")
    print("=" * 60)
    
    # Check if API is running
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=2)
        if response.status_code == 200:
            print("✅ API is running and healthy")
            health_data = response.json()
            print(f"   Database: {health_data.get('database')}")
            print(f"   Cache: {health_data.get('cache_status')}")
        else:
            print(f"⚠️ API returned status {response.status_code}")
    except Exception as e:
        print(f"❌ API is not running or not accessible: {e}")
        print("\nPlease start the API with:")
        print("  python src/api/api_public.py")
        return
    
    # Test each endpoint
    all_times = {}
    
    # 1. Properties endpoint (with optimized field selection)
    all_times['properties'] = test_endpoint(
        "Properties Endpoint",
        f"{BASE_URL}/api/v1/properties",
        {"limit": 100}
    )
    
    # 2. Properties with filters
    all_times['properties_filtered'] = test_endpoint(
        "Properties Endpoint (Filtered)",
        f"{BASE_URL}/api/v1/properties",
        {"limit": 50, "state": "TX", "needs_extraction": True}
    )
    
    # 3. Statistics endpoint
    all_times['statistics'] = test_endpoint(
        "Statistics Endpoint",
        f"{BASE_URL}/api/v1/statistics"
    )
    
    # 4. Entities endpoint
    all_times['entities'] = test_endpoint(
        "Entities Endpoint",
        f"{BASE_URL}/api/v1/entities",
        {"limit": 50}
    )
    
    # 5. Jurisdictions endpoint
    all_times['jurisdictions'] = test_endpoint(
        "Jurisdictions Endpoint",
        f"{BASE_URL}/api/v1/jurisdictions"
    )
    
    # 6. Extraction status endpoint
    all_times['extraction_status'] = test_endpoint(
        "Extraction Status Endpoint",
        f"{BASE_URL}/api/v1/extract/status"
    )
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 PERFORMANCE SUMMARY")
    print("=" * 60)
    
    total_tests = 0
    fast_tests = 0
    slow_tests = 0
    
    for endpoint, times in all_times.items():
        if times:
            avg_time = mean(times)
            total_tests += 1
            if avg_time < 2.0:
                fast_tests += 1
                status = "✅"
            else:
                slow_tests += 1
                status = "❌"
            print(f"{status} {endpoint:25s}: {avg_time:.3f}s avg")
    
    print(f"\n📈 Overall Results:")
    print(f"   Total endpoints tested: {total_tests}")
    print(f"   Fast endpoints (< 2s): {fast_tests}")
    print(f"   Slow endpoints (> 2s): {slow_tests}")
    
    if slow_tests == 0:
        print("\n🎉 SUCCESS: All endpoints are performing well!")
        print("   All endpoints respond in under 2 seconds.")
    elif slow_tests < total_tests / 2:
        print("\n✅ GOOD: Most endpoints are performing well.")
        print(f"   {fast_tests}/{total_tests} endpoints respond in under 2 seconds.")
    else:
        print("\n⚠️ NEEDS IMPROVEMENT: Several endpoints are still slow.")
        print(f"   Only {fast_tests}/{total_tests} endpoints respond in under 2 seconds.")
    
    print("\n💡 Optimization Tips Applied:")
    print("   1. Selective field queries (only fetching needed columns)")
    print("   2. Database-level aggregations via RPC functions")
    print("   3. Parallel query execution for statistics")
    print("   4. Efficient counting without fetching all data")
    print("   5. Result caching with TTL")
    print("   6. Reduced query timeouts for faster failures")

if __name__ == "__main__":
    main()