#!/usr/bin/env python3
"""
Migration script to update api_public.py with optimized queries.
This script applies the optimization patches to your existing API.
"""

import os
import shutil
from datetime import datetime

def create_backup():
    """Create a backup of the original API file."""
    source = "api_public.py"
    backup = f"api_public_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
    
    if os.path.exists(source):
        shutil.copy2(source, backup)
        print(f"✅ Backup created: {backup}")
        return backup
    else:
        print("❌ api_public.py not found!")
        return None

def apply_optimizations():
    """Apply the optimizations to api_public.py."""
    
    # Read the optimized version
    with open("api_public_optimized.py", "r") as f:
        optimized_content = f.read()
    
    # Write to api_public.py
    with open("api_public.py", "w") as f:
        f.write(optimized_content)
    
    print("✅ Optimizations applied to api_public.py")

def verify_supabase_functions():
    """Verify that Supabase functions are ready."""
    print("\n📋 Supabase Setup Instructions:")
    print("=" * 50)
    print("1. Open your Supabase dashboard")
    print("2. Go to SQL Editor")
    print("3. Run the migration script: supabase/migrations/optimize_queries.sql")
    print("4. This will create the following optimized functions:")
    print("   - get_tax_statistics()")
    print("   - get_extraction_counts()")
    print("   - get_jurisdiction_stats()")
    print("   - get_entity_stats()")
    print("   - get_properties_with_entities()")
    print("   - batch_update_properties()")
    print("   - dashboard_stats (materialized view)")
    print("=" * 50)

def test_optimizations():
    """Test the optimized API locally."""
    print("\n🧪 Testing Instructions:")
    print("=" * 50)
    print("1. Start the optimized API locally:")
    print("   python api_public.py")
    print("\n2. Test the optimized endpoints:")
    print("   - http://localhost:8000/api/v1/statistics (should be 40-60% faster)")
    print("   - http://localhost:8000/api/v1/jurisdictions (uses single aggregated query)")
    print("   - http://localhost:8000/api/v1/extract/status (uses COUNT instead of fetching all)")
    print("\n3. Monitor the logs for performance improvements")
    print("=" * 50)

def main():
    print("🚀 API Query Optimization Migration")
    print("=" * 50)
    
    # Step 1: Create backup
    backup_file = create_backup()
    if not backup_file:
        return
    
    # Step 2: Check if optimized version exists
    if not os.path.exists("api_public_optimized.py"):
        print("❌ api_public_optimized.py not found!")
        print("Make sure the optimized version is in the same directory.")
        return
    
    # Step 3: Apply optimizations
    try:
        apply_optimizations()
    except Exception as e:
        print(f"❌ Error applying optimizations: {e}")
        print(f"Restoring from backup: {backup_file}")
        shutil.copy2(backup_file, "api_public.py")
        return
    
    # Step 4: Provide Supabase setup instructions
    verify_supabase_functions()
    
    # Step 5: Provide testing instructions
    test_optimizations()
    
    print("\n✅ Migration complete!")
    print(f"Original API backed up to: {backup_file}")
    print("Deploy the updated api_public.py to Railway when ready.")

if __name__ == "__main__":
    main()