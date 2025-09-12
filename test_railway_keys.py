#!/usr/bin/env python3
"""
Test Railway deployment to verify correct keys are configured.
"""

import requests
import json
import time

BASE_URL = "https://tax-extraction-system-production.up.railway.app"

def test_endpoint(name: str, endpoint: str, timeout: int = 10):
    """Test an endpoint and return detailed results."""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"Endpoint: {BASE_URL}{endpoint}")
    print("-"*60)
    
    try:
        start = time.time()
        response = requests.get(f"{BASE_URL}{endpoint}", timeout=timeout)
        elapsed = time.time() - start
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Time: {elapsed:.2f}s")
        
        if response.status_code == 200:
            try:
                data = response.json()
                
                # Pretty print JSON response
                print("\nResponse Data:")
                print(json.dumps(data, indent=2)[:500])  # Limit output
                
                # Check for specific indicators
                if "database" in data:
                    db_status = data.get("database", {})
                    if isinstance(db_status, dict):
                        print(f"\n✓ Database Status: {db_status.get('status', 'unknown')}")
                        if db_status.get('status') == 'connected':
                            print("  → SUPABASE_URL and SUPABASE_KEY are configured correctly!")
                        else:
                            print("  → Database connection issue - check SUPABASE_URL and SUPABASE_KEY")
                
                return True, data
            except json.JSONDecodeError:
                print(f"Response (not JSON): {response.text[:200]}")
                return True, response.text
        else:
            print(f"Error Response: {response.text[:200]}")
            return False, response.text
            
    except requests.Timeout:
        print(f"❌ TIMEOUT after {timeout}s")
        return False, "timeout"
    except requests.ConnectionError as e:
        print(f"❌ CONNECTION ERROR: {e}")
        return False, "connection_error"
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False, str(e)

def test_data_endpoint(name: str, endpoint: str):
    """Test data endpoints to verify database access."""
    print(f"\n{'='*60}")
    print(f"Testing Data Endpoint: {name}")
    print(f"Endpoint: {BASE_URL}{endpoint}")
    print("-"*60)
    
    try:
        response = requests.get(f"{BASE_URL}{endpoint}", timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            # Check if we got data
            if isinstance(data, dict):
                # Check for common response structure
                if "properties" in data or "entities" in data:
                    count = len(data.get("properties", data.get("entities", [])))
                    print(f"✓ Successfully fetched data: {count} items")
                    print("  → Database connection is working!")
                    return True
                elif "total_properties" in data:  # Statistics endpoint
                    print(f"✓ Statistics fetched successfully")
                    print(f"  Total Properties: {data.get('total_properties', 0)}")
                    print(f"  Total Entities: {data.get('total_entities', 0)}")
                    print("  → Database queries are working!")
                    return True
            elif isinstance(data, list):
                print(f"✓ Successfully fetched {len(data)} items")
                return True
                
            print(f"Response structure: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            return True
        else:
            print(f"❌ Status {response.status_code}: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("="*60)
    print("RAILWAY DEPLOYMENT KEY VERIFICATION TEST")
    print("="*60)
    print(f"Target: {BASE_URL}")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test 1: Basic connectivity
    success, _ = test_endpoint("Liveness Check", "/livez", timeout=5)
    if not success:
        print("\n❌ API is not reachable. Check Railway deployment status.")
        return
    
    # Test 2: Health check (tests database connection)
    success, health_data = test_endpoint("Health Check with Database", "/health", timeout=10)
    
    # Test 3: Environment variables endpoint
    success, env_data = test_endpoint("Environment Check", "/debug/env", timeout=5)
    if success and isinstance(env_data, dict):
        print("\n📋 Environment Variables Status:")
        env_vars = env_data.get("environment_variables", {})
        
        required_keys = ["SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY"]
        for key in required_keys:
            if key in env_vars:
                if env_vars[key] and env_vars[key] != "not_set":
                    print(f"  ✓ {key}: Configured (value hidden)")
                else:
                    print(f"  ❌ {key}: NOT SET or empty")
            else:
                print(f"  ❌ {key}: Missing")
    
    # Test 4: Test actual data endpoints
    print("\n" + "="*60)
    print("TESTING DATA ENDPOINTS (Database Access)")
    print("="*60)
    
    test_data_endpoint("Statistics", "/api/v1/statistics")
    test_data_endpoint("Properties (limit=1)", "/api/v1/properties?limit=1")
    test_data_endpoint("Entities (limit=1)", "/api/v1/entities?limit=1")
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    if isinstance(health_data, dict):
        db_status = health_data.get("database", {}).get("status", "unknown")
        if db_status == "connected":
            print("✅ SUPABASE KEYS ARE CONFIGURED CORRECTLY!")
            print("   - Database connection is working")
            print("   - API can query data successfully")
        elif db_status == "degraded":
            print("⚠️ PARTIAL SUCCESS")
            print("   - Keys might be configured but connection is slow")
            print("   - Check SUPABASE_SERVICE_ROLE_KEY for better performance")
        else:
            print("❌ DATABASE CONNECTION FAILED")
            print("   - Check SUPABASE_URL is correct")
            print("   - Check SUPABASE_KEY or SUPABASE_SERVICE_ROLE_KEY is valid")
            print("   - Verify keys in Railway dashboard environment variables")
    else:
        print("❌ Could not verify database connection")
        print("   - Check Railway logs for errors")

if __name__ == "__main__":
    main()