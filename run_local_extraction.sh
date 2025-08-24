#!/bin/bash

# Local Extraction Runner Script
# Handles complex jurisdictions that need browser automation

echo "🚀 Local Tax Extraction Suite"
echo "=============================="
echo ""

# Check dependencies
check_dependency() {
    if ! command -v $1 &> /dev/null; then
        echo "❌ $1 is not installed"
        return 1
    else
        echo "✅ $1 is installed"
        return 0
    fi
}

echo "Checking dependencies..."
check_dependency python3
check_dependency pip

# Check Python packages
echo ""
echo "Checking Python packages..."

python3 -c "import playwright" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️ Playwright not installed"
    echo "   To install: pip install playwright && playwright install chromium"
else
    echo "✅ Playwright is installed"
fi

python3 -c "import selenium" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️ Selenium not installed"
    echo "   To install: pip install selenium"
else
    echo "✅ Selenium is installed"
fi

python3 -c "import supabase" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Supabase not installed"
    echo "   To install: pip install supabase"
    exit 1
else
    echo "✅ Supabase is installed"
fi

echo ""
echo "=============================="
echo ""

# Menu
PS3='Please select an option: '
options=(
    "Run extraction for all complex jurisdictions"
    "Run extraction for specific jurisdiction"
    "Check extraction status"
    "Install missing dependencies"
    "Run with browser visible (debugging)"
    "Exit"
)

select opt in "${options[@]}"
do
    case $opt in
        "Run extraction for all complex jurisdictions")
            echo "Starting extraction for complex jurisdictions..."
            python3 local_extraction_suite.py --limit 20
            break
            ;;
        "Run extraction for specific jurisdiction")
            echo "Available jurisdictions:"
            echo "  • Harris (TX)"
            echo "  • Maricopa (AZ)"
            echo "  • Wayne (NC)"
            echo "  • Johnston (NC)"
            echo "  • Craven (NC)"
            echo "  • Wilson (NC)"
            echo ""
            read -p "Enter jurisdiction name: " jurisdiction
            echo "Running extraction for $jurisdiction..."
            python3 -c "
import asyncio
from local_extraction_suite import LocalExtractionSuite
from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

async def run():
    suite = LocalExtractionSuite(headless=True)
    
    # Get properties for specific jurisdiction
    SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://klscgjbachumeojhxyno.supabase.co')
    SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')
    
    if not SUPABASE_KEY:
        with open('.env', 'r') as f:
            for line in f:
                if 'SUPABASE_KEY=' in line and 'SERVICE' not in line:
                    SUPABASE_KEY = line.split('=', 1)[1].strip().strip('\"').strip(\"'\")
                    break
    
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    response = supabase.table('properties').select('*').ilike('jurisdiction', f'%{\"$jurisdiction\"}%').execute()
    properties = response.data
    
    print(f'Found {len(properties)} properties for {\"$jurisdiction\"}')
    
    for prop in properties[:5]:  # Limit to 5 for testing
        print(f'Extracting: {prop[\"property_name\"][:50]}...')
        result = await suite.extract_property(prop)
        if result.success:
            print(f'  ✅ Extracted: \${result.tax_amount:.2f}')
            suite.sync_to_supabase(result)
        else:
            print(f'  ❌ Failed: {result.error_message}')
    
    await suite.cleanup_playwright()

asyncio.run(run())
"
            break
            ;;
        "Check extraction status")
            echo "Checking extraction status..."
            python3 -c "
from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://klscgjbachumeojhxyno.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')

if not SUPABASE_KEY:
    with open('.env', 'r') as f:
        for line in f:
            if 'SUPABASE_KEY=' in line and 'SERVICE' not in line:
                SUPABASE_KEY = line.split('=', 1)[1].strip().strip('\"').strip(\"'\")
                break

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Get all properties
response = supabase.table('properties').select('*').execute()
properties = response.data

total = len(properties)
extracted = sum(1 for p in properties if p.get('amount_due') is not None and p.get('amount_due') != 0)
paid = sum(1 for p in properties if p.get('amount_due') == 0)
pending = total - extracted - paid

print(f'Total Properties: {total}')
print(f'Extracted (with amount due): {extracted}')
print(f'Paid (0.00 due): {paid}')
print(f'Pending extraction: {pending}')

# Check complex jurisdictions
complex_jurs = ['Harris', 'Maricopa', 'Wayne', 'Johnston', 'Craven', 'Wilson']
print('\nComplex Jurisdictions Status:')
for jur in complex_jurs:
    jur_props = [p for p in properties if jur.lower() in p.get('jurisdiction', '').lower()]
    if jur_props:
        extracted_jur = sum(1 for p in jur_props if p.get('amount_due') is not None)
        print(f'  • {jur}: {extracted_jur}/{len(jur_props)} extracted')
"
            break
            ;;
        "Install missing dependencies")
            echo "Installing dependencies..."
            pip install playwright selenium supabase pandas python-dotenv
            echo ""
            echo "Installing Playwright browsers..."
            playwright install chromium
            echo "✅ Dependencies installed"
            break
            ;;
        "Run with browser visible (debugging)")
            echo "Starting extraction with visible browser..."
            python3 local_extraction_suite.py --show-browser --limit 5
            break
            ;;
        "Exit")
            break
            ;;
        *) echo "Invalid option $REPLY";;
    esac
done