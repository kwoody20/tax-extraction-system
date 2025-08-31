# Local Extraction Suite for Complex Jurisdictions

This local extraction suite handles jurisdictions that require browser automation (Playwright/Selenium) and automatically syncs results to your Supabase database.

## Why Local Extraction?

Browser automation tools like Playwright and Selenium are difficult/expensive to run on cloud platforms:
- Railway doesn't support them without complex Docker setups
- Cloud alternatives cost $25-100+/month
- Local execution gives you full control and debugging capabilities

## Features

- ✅ Handles complex jurisdictions (Harris, Maricopa, NC counties)
- ✅ Automatic Supabase synchronization
- ✅ No dashboard needed - runs from command line
- ✅ Supports both Playwright and Selenium
- ✅ Rate limiting and error handling
- ✅ Progress tracking and logging

## Supported Complex Jurisdictions

| Jurisdiction | State | Method | Confidence |
|-------------|-------|---------|------------|
| Harris | TX | Playwright | High |
| Maricopa | AZ | Playwright | High |
| Wayne | NC | Playwright | Medium |
| Johnston | NC | Selenium | Medium |
| Craven | NC | Selenium | Medium |  
| Wilson | NC | Selenium | Medium |
| Miami-Dade | FL | Playwright | Low |
| Travis | TX | Playwright | Low |

## Installation

### 1. Install Python Dependencies

```bash
pip install playwright selenium supabase pandas python-dotenv
```

### 2. Install Browser Drivers

For Playwright:
```bash
playwright install chromium
```

For Selenium (macOS):
```bash
brew install chromedriver
```

For Selenium (Linux/Windows):
- Download ChromeDriver from https://chromedriver.chromium.org/
- Add to PATH

### 3. Configure Environment

Your `.env` file should have:
```env
SUPABASE_URL="https://klscgjbachumeojhxyno.supabase.co"
SUPABASE_KEY="your-anon-or-service-role-key"
```

## Usage

### Quick Start - Interactive Menu

```bash
./run_local_extraction.sh
```

This provides an interactive menu with options:
1. Run extraction for all complex jurisdictions
2. Run extraction for specific jurisdiction
3. Check extraction status
4. Install missing dependencies
5. Run with browser visible (debugging)

### Direct Python Usage

```bash
# Extract 10 properties from complex jurisdictions
python local_extraction_suite.py --limit 10

# Extract with visible browser (for debugging)
python local_extraction_suite.py --show-browser --limit 5

# Extract all pending complex jurisdiction properties
python local_extraction_suite.py --limit 50
```

### Python Script Integration

```python
import asyncio
from local_extraction_suite import LocalExtractionSuite

async def run_extraction():
    suite = LocalExtractionSuite(headless=True)
    
    # Extract specific property
    property_data = {
        'id': 'property-uuid',
        'property_name': 'Test Property',
        'jurisdiction': 'Harris',
        'tax_bill_link': 'https://...',
        'account_number': '12345'
    }
    
    result = await suite.extract_property(property_data)
    
    if result.success:
        print(f"Tax amount: ${result.tax_amount}")
        suite.sync_to_supabase(result)
    
    await suite.cleanup_playwright()

asyncio.run(run_extraction())
```

## How It Works

1. **Fetches Properties**: Queries Supabase for properties in complex jurisdictions that need extraction
2. **Browser Automation**: Uses Playwright or Selenium based on jurisdiction requirements
3. **Extraction**: Navigates to tax sites, handles JavaScript, extracts tax amounts
4. **Sync to Supabase**: Updates the `properties` table with extracted data
5. **Logging**: Saves results to JSON files and logs

## Workflow Integration

### Daily Extraction Workflow

1. **Cloud handles simple jurisdictions** (Montgomery, Fort Bend, ISDs)
   - These run automatically via the dashboard

2. **Local handles complex jurisdictions** (Harris, Maricopa, etc.)
   - Run locally once per day/week
   - Results sync to Supabase automatically

3. **Dashboard shows all results**
   - No difference between cloud and local extractions
   - All data unified in Supabase

### Scheduling (Optional)

On macOS/Linux, add to crontab for daily runs:
```bash
# Run at 2 AM daily
0 2 * * * cd /path/to/taxes && python3 local_extraction_suite.py --limit 20 >> extraction.log 2>&1
```

On Windows, use Task Scheduler.

## Troubleshooting

### Playwright Issues

```bash
# Reinstall Playwright
pip uninstall playwright
pip install playwright
playwright install chromium
```

### Selenium Issues

```bash
# Check ChromeDriver version matches Chrome
chromedriver --version
google-chrome --version  # or chrome --version

# Update ChromeDriver
brew upgrade chromedriver  # macOS
```

### Supabase Connection Issues

```bash
# Test connection
python -c "
from supabase import create_client
import os
from dotenv import load_dotenv
load_dotenv()
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_KEY')
client = create_client(url, key)
result = client.table('properties').select('id').limit(1).execute()
print('✅ Connected!' if result else '❌ Failed')
"
```

## Output Files

- `local_extraction.log` - Detailed execution log
- `extraction_results_YYYYMMDD_HHMMSS.json` - Results from each run

## Cloud Alternatives (If Needed)

If you must run browser automation in the cloud:

1. **Render.com** ($25+/month)
   - Supports Docker with Playwright
   - Create Dockerfile with Playwright installed

2. **Google Cloud Run**
   - Containerized Playwright
   - Pay per execution

3. **Browserless.io** ($50+/month)
   - Hosted Chrome service
   - Change code to use their API

4. **GitHub Actions** (Free tier available)
   - Can run Playwright in workflows
   - Schedule daily extractions

## Support

The local extraction suite integrates seamlessly with your existing tax extraction system. All results are automatically visible in your Streamlit dashboard after syncing.