#!/usr/bin/env python3
"""
Deployment Safety Test Script
Run this before pushing to ensure Railway deployment won't break.
"""

import sys
import ast
import re
from pathlib import Path

def check_api_public():
    """Check api_public.py for dangerous patterns."""
    
    issues = []
    api_file = Path("api_public.py")
    
    if not api_file.exists():
        print("❌ api_public.py not found!")
        return False
    
    content = api_file.read_text()
    
    # Check 1: Module-level create_client
    if re.search(r'^supabase\s*=\s*create_client', content, re.MULTILINE):
        issues.append("❌ Module-level Supabase initialization detected (supabase = create_client)")
    
    # Check 2: Module-level env var validation
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")' in line:
            # Check if this is at module level (not inside a function)
            indent = len(line) - len(line.lstrip())
            if indent == 0:
                issues.append(f"❌ Module-level environment variable check at line {i+1}")
    
    # Check 3: Verify SupabaseProxy exists
    if 'class SupabaseProxy' not in content:
        issues.append("❌ SupabaseProxy class not found - lazy loading pattern missing")
    
    # Check 4: Verify get_supabase_client exists
    if 'def get_supabase_client' not in content:
        issues.append("❌ get_supabase_client function not found")
    
    # Check 5: Verify lazy loading pattern is in place
    if 'supabase = SupabaseProxy()' not in content:
        issues.append("❌ SupabaseProxy not being used for supabase variable")
    
    if issues:
        print("🚨 DEPLOYMENT SAFETY CHECK FAILED:")
        for issue in issues:
            print(f"  {issue}")
        return False
    else:
        print("✅ api_public.py passed all safety checks")
        return True

def check_railway_config():
    """Check Railway configuration files."""
    issues = []
    
    # Check railway.json
    railway_json = Path("railway.json")
    if railway_json.exists():
        content = railway_json.read_text()
        if 'api_public:app' not in content:
            issues.append("❌ railway.json doesn't reference api_public:app")
        if '${PORT' not in content and '$PORT' not in content:
            issues.append("❌ railway.json missing PORT variable")
        print("✅ railway.json found and checked")
    else:
        print("⚠️  railway.json not found (may be OK if using railway.toml)")
    
    # Check for railway.toml
    railway_toml = Path("railway.toml")
    if railway_toml.exists():
        content = railway_toml.read_text()
        if 'api_minimal:app' in content:
            issues.append("❌ railway.toml still references deleted api_minimal:app!")
        print("ℹ️  railway.toml found - ensure it references api_public:app")
    
    if issues:
        print("🚨 RAILWAY CONFIG ISSUES:")
        for issue in issues:
            print(f"  {issue}")
        return False
    
    return True

def check_requirements():
    """Check requirements-railway.txt for known issues."""
    req_file = Path("requirements-railway.txt")
    
    if not req_file.exists():
        print("❌ requirements-railway.txt not found!")
        return False
    
    content = req_file.read_text()
    issues = []
    
    # Check for problematic gotrue versions
    if re.search(r'gotrue==2\.(9|1[0-9])', content):
        issues.append("❌ gotrue version 2.9+ detected - has proxy parameter bug!")
    
    # Check for supabase/gotrue presence
    if 'supabase' not in content:
        issues.append("❌ supabase not in requirements-railway.txt")
    
    if 'gotrue' not in content:
        issues.append("⚠️  gotrue not explicitly specified - may get incompatible version")
    
    if issues:
        print("🚨 REQUIREMENTS ISSUES:")
        for issue in issues:
            print(f"  {issue}")
        return False
    else:
        print("✅ requirements-railway.txt passed checks")
        return True

def main():
    """Run all deployment safety checks."""
    print("🔍 Running Deployment Safety Checks...\n")
    
    results = []
    results.append(("API Module", check_api_public()))
    print()
    results.append(("Railway Config", check_railway_config()))
    print()
    results.append(("Requirements", check_requirements()))
    print()
    
    # Summary
    print("=" * 50)
    all_passed = all(r[1] for r in results)
    
    if all_passed:
        print("✅ ALL CHECKS PASSED - Safe to deploy!")
        print("\nNext steps:")
        print("  1. git add .")
        print("  2. git commit -m 'your message'")
        print("  3. git push origin main")
        return 0
    else:
        print("❌ DEPLOYMENT CHECKS FAILED")
        print("\n⚠️  DO NOT PUSH TO MAIN until issues are resolved!")
        print("📖 See DEPLOYMENT_CRITICAL.md for guidance")
        return 1

if __name__ == "__main__":
    sys.exit(main())