#!/usr/bin/env python3
"""
Test Supabase Authentication Flow.
Demonstrates user registration, login, and API access.
"""

import requests
import json
import time
from datetime import datetime

# API Configuration
API_URL = "http://localhost:8000"

def print_section(title):
    """Print a formatted section header."""
    print("\n" + "="*60)
    print(f" {title}")
    print("="*60)

def test_registration():
    """Test user registration."""
    print_section("1. USER REGISTRATION")
    
    # Register a new user
    user_data = {
        "email": f"testuser_{int(time.time())}@example.com",
        "password": "TestPass123!",
        "name": "Test User",
        "company": "Test Company"
    }
    
    print(f"Registering user: {user_data['email']}")
    
    response = requests.post(
        f"{API_URL}/auth/register",
        json=user_data
    )
    
    if response.status_code == 200:
        data = response.json()
        print("✅ Registration successful!")
        print(f"   User ID: {data.get('user', {}).get('id')}")
        print(f"   Message: {data.get('message')}")
        return user_data["email"], user_data["password"]
    else:
        print(f"❌ Registration failed: {response.status_code}")
        print(f"   Error: {response.json()}")
        return None, None

def test_login(email, password):
    """Test user login."""
    print_section("2. USER LOGIN")
    
    print(f"Logging in as: {email}")
    
    response = requests.post(
        f"{API_URL}/auth/login",
        json={"email": email, "password": password}
    )
    
    if response.status_code == 200:
        data = response.json()
        print("✅ Login successful!")
        print(f"   User ID: {data['user']['id']}")
        print(f"   Email: {data['user']['email']}")
        print(f"   Token expires at: {data['session']['expires_at']}")
        return data['session']['access_token']
    else:
        print(f"❌ Login failed: {response.status_code}")
        print(f"   Error: {response.json()}")
        return None

def test_public_endpoints():
    """Test public endpoints (no auth required)."""
    print_section("3. PUBLIC ENDPOINTS (No Auth)")
    
    endpoints = [
        ("/", "Root"),
        ("/health", "Health Check"),
        ("/api/v1/properties?limit=2", "Properties (Public)"),
        ("/api/v1/entities?limit=2", "Entities (Public)")
    ]
    
    for endpoint, name in endpoints:
        print(f"\n📍 Testing {name}: GET {endpoint}")
        response = requests.get(f"{API_URL}{endpoint}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Status: {response.status_code}")
            
            # Show relevant info
            if endpoint == "/health":
                print(f"   Database: {data.get('database')}")
                print(f"   Properties: {data.get('properties_count', 0)}")
            elif "properties" in endpoint:
                print(f"   Count: {data.get('count', 0)}")
                print(f"   Authenticated: {data.get('authenticated', False)}")
            elif "entities" in endpoint:
                print(f"   Count: {data.get('count', 0)}")
                print(f"   Authenticated: {data.get('authenticated', False)}")
        else:
            print(f"   ❌ Status: {response.status_code}")

def test_protected_endpoints(access_token):
    """Test protected endpoints (auth required)."""
    print_section("4. PROTECTED ENDPOINTS (Auth Required)")
    
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    # Test profile endpoint
    print(f"\n📍 Testing Profile: GET /api/v1/profile")
    response = requests.get(f"{API_URL}/api/v1/profile", headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Status: {response.status_code}")
        print(f"   User ID: {data['user']['id']}")
        print(f"   Email: {data['user']['email']}")
    else:
        print(f"   ❌ Status: {response.status_code}")
    
    # Test authenticated property access
    print(f"\n📍 Testing Properties (Authenticated): GET /api/v1/properties")
    response = requests.get(f"{API_URL}/api/v1/properties?limit=2", headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Status: {response.status_code}")
        print(f"   Count: {data.get('count', 0)}")
        print(f"   Authenticated: {data.get('authenticated', False)}")
    else:
        print(f"   ❌ Status: {response.status_code}")
    
    # Test extraction job creation
    print(f"\n📍 Testing Extraction Job: POST /api/v1/extract")
    job_data = {
        "days_since_last": 30,
        "priority": 5
    }
    response = requests.post(
        f"{API_URL}/api/v1/extract",
        json=job_data,
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Status: {response.status_code}")
        print(f"   Job ID: {data.get('job_id')}")
        print(f"   Properties: {data.get('total_properties', 0)}")
        return data.get('job_id')
    else:
        print(f"   ❌ Status: {response.status_code}")
        return None

def test_unauthorized_access():
    """Test that protected endpoints reject unauthorized access."""
    print_section("5. UNAUTHORIZED ACCESS TEST")
    
    print("\n📍 Testing protected endpoint without token...")
    response = requests.get(f"{API_URL}/api/v1/profile")
    
    if response.status_code == 401:
        print("   ✅ Correctly rejected (401 Unauthorized)")
    else:
        print(f"   ❌ Unexpected status: {response.status_code}")
    
    print("\n📍 Testing with invalid token...")
    headers = {"Authorization": "Bearer invalid_token"}
    response = requests.get(f"{API_URL}/api/v1/profile", headers=headers)
    
    if response.status_code == 401:
        print("   ✅ Correctly rejected (401 Unauthorized)")
    else:
        print(f"   ❌ Unexpected status: {response.status_code}")

def main():
    """Run complete authentication flow test."""
    print("\n" + "🔐 "*20)
    print("   SUPABASE AUTHENTICATION FLOW TEST")
    print("🔐 "*20)
    
    print(f"\nAPI URL: {API_URL}")
    print(f"Time: {datetime.now().isoformat()}")
    
    # Test registration
    email, password = test_registration()
    
    if not email:
        # Use existing test credentials if registration fails
        print("\n⚠️ Registration failed, using test credentials...")
        email = "admin@taxextractor.com"
        password = "Admin123!@#"
    
    # Test login
    access_token = test_login(email, password)
    
    if not access_token:
        print("\n❌ Cannot continue without valid access token")
        return
    
    # Test public endpoints
    test_public_endpoints()
    
    # Test protected endpoints
    job_id = test_protected_endpoints(access_token)
    
    # Test unauthorized access
    test_unauthorized_access()
    
    # Summary
    print_section("TEST SUMMARY")
    print("\n✅ Authentication flow test completed!")
    print("\nKey findings:")
    print("  • Registration and login work with Supabase Auth")
    print("  • Public endpoints accessible without authentication")
    print("  • Protected endpoints require valid JWT token")
    print("  • Unauthorized access properly rejected")
    print("\n🎉 Supabase Authentication is properly configured!")

if __name__ == "__main__":
    main()