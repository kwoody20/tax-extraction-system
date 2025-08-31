#!/usr/bin/env python3
"""
Verify that the new directory structure and imports work correctly.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """Test that all critical imports work."""
    print("Testing import structure...")
    
    try:
        # Test extractor imports
        from src.extractors.cloud_extractor import cloud_extractor
        print("✓ Cloud extractor import successful")
        
        # Test utils imports
        from src.utils.config import get_config
        print("✓ Config import successful")
        
        from src.utils.error_handling import ExtractionError
        print("✓ Error handling import successful")
        
        from src.utils.data_validation import DataValidator
        print("✓ Data validation import successful")
        
        # Test database imports
        from src.database.supabase_client import SupabaseClient
        print("✓ Supabase client import successful")
        
        from src.database.supabase_auth import SupabaseAuth
        print("✓ Supabase auth import successful")
        
        # Test API import (checking module exists)
        import src.api.api_public
        print("✓ API module found")
        
        # Test dashboard import (checking module exists)
        import src.dashboard.streamlit_app
        print("✓ Dashboard module found")
        
        print("\n✅ All imports successful! Directory structure is valid.")
        return True
        
    except ImportError as e:
        print(f"\n❌ Import failed: {e}")
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)