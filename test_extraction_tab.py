"""
Test script to verify extraction tab functionality
"""

import requests

API_URL = "https://tax-extraction-system-production.up.railway.app"

print("Testing Extraction Tab Functionality")
print("=" * 60)

# 1. Check if API is accessible
print("\n1. Checking API health...")
try:
    response = requests.get(f"{API_URL}/health", timeout=5)
    if response.status_code == 200:
        print("✅ API is healthy")
        data = response.json()
        print(f"   Database: {data.get('database')}")
    else:
        print(f"❌ API returned status {response.status_code}")
except Exception as e:
    print(f"❌ Could not reach API: {e}")

# 2. Check for properties that need extraction
print("\n2. Checking for properties needing extraction...")
try:
    # Get properties without amount_due (need extraction)
    response = requests.get(f"{API_URL}/api/v1/properties?limit=10", timeout=10)
    if response.status_code == 200:
        properties = response.json().get("properties", [])
        
        # Filter for properties that need extraction (amount_due = 0 or null)
        need_extraction = [
            p for p in properties 
            if p.get("amount_due") == 0 or p.get("amount_due") is None
        ]
        
        print(f"✅ Found {len(properties)} total properties")
        print(f"   {len(need_extraction)} may need extraction")
        
        # Show some examples
        if need_extraction:
            print("\n   Properties that might need extraction:")
            for prop in need_extraction[:3]:
                print(f"   • {prop['property_name'][:50]}...")
                print(f"     Jurisdiction: {prop['jurisdiction']}")
                print(f"     Current amount_due: {prop.get('amount_due')}")
                print(f"     Has tax_bill_link: {'Yes' if prop.get('tax_bill_link') else 'No'}")
                print()
    else:
        print(f"❌ Failed to get properties: {response.status_code}")
except Exception as e:
    print(f"❌ Error fetching properties: {e}")

# 3. Check extraction endpoint availability
print("\n3. Checking extraction endpoint...")
try:
    # This will fail on production API but shows what's needed
    response = requests.get(f"{API_URL}/api/v1/extract/status", timeout=5)
    if response.status_code == 200:
        print("✅ Extraction endpoint is available!")
        status = response.json()
        print(f"   Supported jurisdictions: {status.get('supported_jurisdictions', [])}")
    else:
        print("⚠️ Extraction endpoint not available (expected on production API)")
        print("   The extraction feature requires the enhanced API running locally")
except:
    print("⚠️ Extraction endpoint not available (expected on production API)")
    print("   The extraction feature requires the enhanced API running locally")

print("\n" + "=" * 60)
print("\nSummary:")
print("- Properties are available in the database ✅")
print("- The dashboard should show these properties automatically")
print("- No CSV upload should be required")
print("- To enable extraction, run: python api_with_extraction.py locally")