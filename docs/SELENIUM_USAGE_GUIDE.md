# Selenium Tax Extractors Usage Guide

## Overview
This guide covers the new Selenium-based tax extractors for Maricopa County and Harris County property tax websites. These extractors handle JavaScript-heavy sites that require browser automation.

## Files Created

### 1. `selenium_tax_extractors.py`
Main module containing:
- `MaricopaCountySeleniumExtractor`: Handles treasurer.maricopa.gov
- `HarrisCountySeleniumExtractor`: Handles www.hctax.net  
- `UnifiedTaxExtractor`: Routes to appropriate county extractor
- `BaseSeleniumExtractor`: Base class with common functionality

### 2. `test_selenium_extractors.py`
Comprehensive test suite for validating extractors with real data.

### 3. `process_with_selenium.py`
Production script for processing Excel/CSV files with Selenium extractors.

## Installation

1. Ensure ChromeDriver is installed:
```bash
# macOS
brew install chromedriver

# Linux
sudo apt-get install chromium-chromedriver

# Windows
# Download from https://chromedriver.chromium.org/
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Quick Test
Run the test suite to verify everything works:
```bash
python3 test_selenium_extractors.py
```

### Process Excel File
Process properties from an Excel file:
```bash
# Process all Maricopa and Harris properties
python3 process_with_selenium.py phase-two-taxes-8-17.xlsx

# Process with options
python3 process_with_selenium.py input.xlsx --output results.xlsx --limit 10 --headless

# Options:
#   -o, --output: Specify output file name
#   -l, --limit: Limit number of properties to process
#   --headless: Run browser in headless mode (no GUI)
#   --no-skip: Don't skip already processed properties
```

### Direct Usage in Code
```python
from selenium_tax_extractors import UnifiedTaxExtractor

# Initialize extractor
extractor = UnifiedTaxExtractor(headless=True)

# Process a single property
property_data = {
    'property_id': '123',
    'property_name': 'Test Property',
    'acct_number': '214-05-025A',  # Maricopa parcel
    'tax_bill_link': 'https://treasurer.maricopa.gov/'
}

result = extractor.extract(property_data)
print(f"Status: {result.extraction_status}")
print(f"Amount Due: ${result.amount_due}")

# Process batch
results = extractor.process_batch(properties_list, output_file='results.xlsx')

# Cleanup
extractor.cleanup()
```

## How It Works

### Maricopa County (treasurer.maricopa.gov)
1. Navigates to the main page
2. Fills in parcel number form (splits parcel into 4 fields)
3. Submits form
4. Extracts tax information from results page
5. Handles "Parcel not found" errors gracefully

### Harris County (www.hctax.net)
1. Navigates directly to tax statement URL
2. Waits for JavaScript to load content
3. Searches for "Final Total Amount Due" and related fields
4. Extracts property address, owner name, and tax amounts
5. Falls back to broader search patterns if primary selectors fail

## Features

### Robust Element Location
- Multiple fallback selectors for each field
- Handles dynamic content with explicit waits
- Validates extracted amounts are reasonable (not HTML/JS)

### Error Handling
- Takes screenshots on failure for debugging
- Comprehensive logging of extraction steps
- Graceful handling of timeouts and missing elements
- Retry logic for stale element references

### Data Validation
- Currency parsing handles various formats
- Date parsing and standardization
- Range validation for tax amounts
- Address normalization

### Output Formats
- Excel with multiple sheets (Results, Summary, Validation)
- JSON for programmatic access
- Intermediate saves during batch processing
- Detailed logging

## Troubleshooting

### Common Issues

1. **ChromeDriver not found**
   - Install ChromeDriver using package manager or download manually
   - Ensure it's in PATH

2. **Timeout errors**
   - Increase timeout in extractor initialization
   - Check if site structure has changed

3. **Extraction returns null amounts**
   - Run with headless=False to see browser
   - Check screenshots for visual debugging
   - Review logs for selector failures

4. **"Parcel not found" for Maricopa**
   - Verify parcel format (XXX-XX-XXX[A-Z])
   - Check if parcel exists on website manually

### Debug Mode
Run with visible browser for debugging:
```python
extractor = UnifiedTaxExtractor(headless=False)
```

### Logs
Check `selenium_tax_extraction.log` for detailed extraction steps and errors.

## Performance

- Processes ~20-30 properties per minute
- 2-second delay between requests (rate limiting)
- Saves intermediate results every 10 properties
- Can resume from last successful extraction

## Validation

Expected success rates:
- Maricopa County: 85-95% (depends on parcel validity)
- Harris County: 80-90% (depends on page load times)

## Next Steps

To integrate with existing pipeline:
1. Replace failing extractors in main pipeline
2. Route Maricopa/Harris properties to Selenium extractors
3. Keep HTTP extractors for other counties
4. Monitor success rates and adjust selectors as needed