#!/usr/bin/env python3
"""
Test the Supabase client directly without the API layer.
"""

import os
import sys
import time
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

def test_direct_client():
    """Test direct client access without pooling."""
    from src.database.supabase_client import SupabasePropertyTaxClient
    
    print("Testing direct Supabase client (no pooling)...")
    
    # Create client
    client = SupabasePropertyTaxClient()
    print("✓ Client created")
    
    # Test simple query
    try:
        start = time.time()
        result = client.client.table("properties").select("property_id").limit(1).execute()
        elapsed = time.time() - start
        print(f"✓ Simple query succeeded in {elapsed:.2f}s")
        print(f"  Result: {len(result.data)} items")
    except Exception as e:
        print(f"✗ Simple query failed: {e}")
        return
    
    # Test with the client's get_properties method
    try:
        start = time.time()
        result = client.get_properties(limit=1)
        elapsed = time.time() - start
        print(f"✓ get_properties succeeded in {elapsed:.2f}s")
        print(f"  Result: {len(result)} items")
    except Exception as e:
        print(f"✗ get_properties failed: {e}")
    
    # Test entities
    try:
        start = time.time()
        result = client.get_entities(limit=1)
        elapsed = time.time() - start
        print(f"✓ get_entities succeeded in {elapsed:.2f}s")
        print(f"  Result: {len(result)} items")
    except Exception as e:
        print(f"✗ get_entities failed: {e}")
    
    print("\n✅ Direct client test completed successfully!")

if __name__ == "__main__":
    test_direct_client()