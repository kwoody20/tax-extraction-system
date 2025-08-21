#!/usr/bin/env python3
"""
Test script for API service with Supabase integration.
"""

import requests
import json
import time
from datetime import datetime

# API Configuration
API_URL = "http://localhost:8000"
API_TOKEN = "your-secret-key-here"  # Update with your token

# Headers for authenticated requests
headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

def test_health():
    """Test health endpoint."""
    print("\n🏥 Testing Health Check...")
    response = requests.get(f"{API_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200

def test_get_properties():
    """Test getting properties from database."""
    print("\n🏢 Testing Get Properties...")
    response = requests.get(
        f"{API_URL}/api/v1/properties",
        headers=headers,
        params={"limit": 5}
    )
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Found {data.get('count', 0)} properties")
    if data.get('properties'):
        for prop in data['properties'][:2]:
            print(f"  - {prop.get('property_name', 'Unknown')[:50]}")
    return response.status_code == 200

def test_get_entities():
    """Test getting entities from database."""
    print("\n🏭 Testing Get Entities...")
    response = requests.get(
        f"{API_URL}/api/v1/entities",
        headers=headers,
        params={"limit": 5}
    )
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Found {data.get('count', 0)} entities")
    if data.get('entities'):
        for entity in data['entities'][:2]:
            print(f"  - {entity.get('entity_name', 'Unknown')}")
    return response.status_code == 200

def test_get_properties_needing_extraction():
    """Test getting properties that need extraction."""
    print("\n🔄 Testing Properties Needing Extraction...")
    response = requests.get(
        f"{API_URL}/api/v1/properties",
        headers=headers,
        params={"needs_extraction": True}
    )
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Found {data.get('count', 0)} properties needing extraction")
    return response.status_code == 200

def test_create_extraction_job():
    """Test creating an extraction job."""
    print("\n📋 Testing Create Extraction Job...")
    
    # First, get a property to extract
    response = requests.get(
        f"{API_URL}/api/v1/properties",
        headers=headers,
        params={"limit": 1, "state": "TX"}
    )
    
    if response.status_code == 200:
        properties = response.json().get('properties', [])
        if properties:
            property_id = properties[0]['property_id']
            print(f"Creating extraction job for property: {property_id}")
            
            # Create extraction job
            job_data = {
                "property_ids": [property_id],
                "days_since_last": 30,
                "priority": 5
            }
            
            response = requests.post(
                f"{API_URL}/api/v1/extract",
                headers=headers,
                json=job_data
            )
            print(f"Status: {response.status_code}")
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            
            if data.get('success'):
                return data.get('job_id')
    
    return None

def test_get_job_status(job_id):
    """Test getting job status."""
    print(f"\n📊 Testing Get Job Status for {job_id}...")
    response = requests.get(
        f"{API_URL}/api/v1/jobs/{job_id}",
        headers=headers
    )
    print(f"Status: {response.status_code}")
    data = response.json()
    if data.get('success'):
        job = data.get('job', {})
        print(f"Job Status: {job.get('status')}")
        print(f"Progress: {job.get('processed_properties')}/{job.get('total_properties')}")
        print(f"Successful: {job.get('successful_extractions')}")
        print(f"Failed: {job.get('failed_extractions')}")
    return response.status_code == 200

def test_get_statistics():
    """Test getting statistics."""
    print("\n📈 Testing Get Statistics...")
    response = requests.get(
        f"{API_URL}/api/v1/statistics",
        headers=headers
    )
    print(f"Status: {response.status_code}")
    data = response.json()
    if data.get('success'):
        stats = data.get('statistics', {})
        print(f"Total Properties: {stats.get('total_properties', 0)}")
        amount_due = stats.get('total_amount_due') if stats.get('total_amount_due') is not None else 0
        print(f"Total Amount Due: ${amount_due:,.2f}")
        print(f"Properties with Balance: {stats.get('properties_with_balance', 0)}")
        
        # Show top entities
        portfolio = data.get('portfolio_summary', [])
        if portfolio:
            print("\nTop Entities by Property Count:")
            for entity in portfolio[:3]:
                print(f"  - {entity.get('entity_name', 'Unknown')}: {entity.get('property_count', 0)} properties")
    return response.status_code == 200

def test_get_jurisdictions():
    """Test getting jurisdictions."""
    print("\n🏛️ Testing Get Jurisdictions...")
    response = requests.get(
        f"{API_URL}/api/v1/jurisdictions",
        headers=headers,
        params={"state": "TX"}
    )
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Found {data.get('count', 0)} jurisdictions in TX")
    return response.status_code == 200

def main():
    """Run all tests."""
    print("=" * 60)
    print("API SUPABASE INTEGRATION TEST SUITE")
    print("=" * 60)
    print(f"API URL: {API_URL}")
    print(f"Time: {datetime.now().isoformat()}")
    
    # Track test results
    results = []
    
    # Run tests
    results.append(("Health Check", test_health()))
    results.append(("Get Properties", test_get_properties()))
    results.append(("Get Entities", test_get_entities()))
    results.append(("Properties Needing Extraction", test_get_properties_needing_extraction()))
    
    # Create and monitor extraction job
    job_id = test_create_extraction_job()
    if job_id:
        results.append(("Create Extraction Job", True))
        
        # Wait a bit for processing
        print("\n⏳ Waiting 2 seconds for job processing...")
        time.sleep(2)
        
        results.append(("Get Job Status", test_get_job_status(job_id)))
    else:
        results.append(("Create Extraction Job", False))
    
    results.append(("Get Statistics", test_get_statistics()))
    results.append(("Get Jurisdictions", test_get_jurisdictions()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:30} {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! API is working correctly with Supabase.")
    else:
        print(f"\n⚠️ {total - passed} tests failed. Please check the API configuration.")

if __name__ == "__main__":
    main()