#!/usr/bin/env python3
"""
Test script to verify Supabase client initialization works correctly
with the specified library versions.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_supabase_versions():
    """Check installed versions of critical packages."""
    print("=" * 60)
    print("CHECKING PACKAGE VERSIONS")
    print("=" * 60)
    
    try:
        import supabase
        print(f"✓ supabase version: {supabase.__version__}")
    except Exception as e:
        print(f"✗ Error checking supabase: {e}")
    
    try:
        import gotrue
        print(f"✓ gotrue version: {gotrue.__version__}")
    except Exception as e:
        print(f"✗ Error checking gotrue: {e}")
    
    try:
        import httpx
        print(f"✓ httpx version: {httpx.__version__}")
    except Exception as e:
        print(f"✗ Error checking httpx: {e}")
    
    print()

def test_lazy_initialization():
    """Test that api_public imports without environment variables."""
    print("=" * 60)
    print("TESTING LAZY INITIALIZATION")
    print("=" * 60)
    
    # Temporarily remove env vars
    old_url = os.environ.pop("SUPABASE_URL", None)
    old_key = os.environ.pop("SUPABASE_KEY", None)
    
    try:
        import api_public
        print("✓ api_public module imports successfully without env vars")
        print("✓ Lazy initialization pattern is working correctly")
    except Exception as e:
        print(f"✗ Failed to import api_public: {e}")
        print("✗ Module-level initialization detected!")
    finally:
        # Restore env vars
        if old_url:
            os.environ["SUPABASE_URL"] = old_url
        if old_key:
            os.environ["SUPABASE_KEY"] = old_key
    
    print()

def test_supabase_connection():
    """Test actual Supabase connection."""
    print("=" * 60)
    print("TESTING SUPABASE CONNECTION")
    print("=" * 60)
    
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"):
        print("⚠ Skipping connection test - env vars not set")
        return
    
    try:
        from supabase import create_client
        
        # Test creating client with only URL and key (no proxy parameter)
        client = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY")
        )
        print("✓ Supabase client created successfully")
        
        # Test a simple query
        result = client.table("properties").select("id").limit(1).execute()
        print(f"✓ Database query successful - found {len(result.data)} records")
        
    except TypeError as e:
        if "proxy" in str(e):
            print(f"✗ PROXY PARAMETER ERROR DETECTED: {e}")
            print("✗ This is the exact error we're fixing!")
            print("✗ Solution: Update to supabase==2.8.1 and gotrue==2.8.1")
        else:
            print(f"✗ TypeError: {e}")
    except Exception as e:
        print(f"✗ Connection error: {e}")
    
    print()

def test_api_health_endpoint():
    """Test the API health endpoint."""
    print("=" * 60)
    print("TESTING API HEALTH ENDPOINT")
    print("=" * 60)
    
    try:
        import requests
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Health endpoint responded: {data['status']}")
            print(f"  Database: {data['database']}")
            if data.get('error'):
                print(f"  Error: {data['error']}")
        else:
            print(f"✗ Health endpoint returned status {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("⚠ API not running locally - start with: uvicorn api_public:app")
    except Exception as e:
        print(f"✗ Error testing health endpoint: {e}")
    
    print()

def main():
    """Run all tests."""
    print("\n🔍 SUPABASE AUTHENTICATION FIX VERIFICATION\n")
    
    test_supabase_versions()
    test_lazy_initialization()
    test_supabase_connection()
    test_api_health_endpoint()
    
    print("=" * 60)
    print("VERIFICATION COMPLETE")
    print("=" * 60)
    print("\n📝 Next Steps:")
    print("1. Ensure requirements.txt has supabase==2.8.1 and gotrue==2.8.1")
    print("2. Run: pip install -r requirements.txt")
    print("3. Commit and push to trigger Railway deployment")
    print("4. Monitor Railway logs for successful startup")
    print("5. Test: https://tax-extraction-system-production.up.railway.app/health")
    print()

if __name__ == "__main__":
    main()