# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a property tax extraction system designed to scrape and extract tax information from various county tax websites. The system handles multiple extraction methods, robust error handling, data validation, and supports both simple HTTP requests and Selenium-based scraping for JavaScript-heavy sites.

## Key Architecture Components

### Core Extraction Engine
- **extracting-tests-818/MASTER_TAX_EXTRACTOR.py**: Unified extraction system with Playwright-based extractors for all jurisdictions
- **robust_tax_extractor.py**: Main extraction engine with circuit breakers, retry logic, connection pooling, and rate limiting
- **tax_extractor.py**: Basic HTTP-based extractor template
- **selenium_tax_extractors.py**: Enhanced Selenium extractors for Maricopa and Harris counties
- **nc_property_extractors.py**: Specialized extractors for North Carolina counties
- **simple_tax_extractor.py**: Analysis tool for Excel files and domain categorization

### Support Modules
- **config.py**: Configuration management with environment variable support
- **error_handling.py**: Retry logic, circuit breakers, and custom exception classes
- **data_validation.py**: Data validation and sanitization for extracted tax data
- **test_utilities.py**: Comprehensive testing framework

### Data Flow
1. Excel input file with property information and tax bill URLs
2. Domain analysis and extraction method selection (HTTP vs Selenium)
3. Parallel or sequential extraction with error handling
4. Data validation and normalization
5. Output to Excel/JSON with validation reports

## Common Commands

### Running Extractors
```bash
# Master extraction system (recommended)
python3 extracting-tests-818/MASTER_TAX_EXTRACTOR.py OFFICIAL-proptax-assets.csv --concurrent

# Selenium-based extraction for Maricopa/Harris
python3 selenium_tax_extractors.py

# NC property extraction
python3 process_with_selenium.py phase-two-taxes-8-17.xlsx --headless

# Robust extraction with all features
python3 robust_tax_extractor.py

# Simple analysis
python3 simple_tax_extractor.py
```

### Testing
```bash
# Run test suite
python3 test_utilities.py

# Test specific domain extraction
python3 extracting-tests-818/test_maricopa.py

# Test Selenium extractors
python3 test_selenium_extractors.py

# Test NC extractors
python3 test_nc_extractors.py
```

### Dependencies
```bash
# Install requirements
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Install ChromeDriver for Selenium (macOS)
brew install chromedriver

# Required Python packages
pip install pandas beautifulsoup4 requests playwright selenium openpyxl
```

## Key Extraction Patterns

### Domain-Specific Extractors

#### Working Extractors (High Success Rate)
- **Montgomery County, TX** (actweb.acttax.com): HTTP-based, account number in URL params - 100% success
- **Aldine ISD, Goose Creek ISD**: Direct link extraction with good success rates

#### Enhanced Extractors (Recently Fixed)
- **Maricopa County, AZ** (treasurer.maricopa.gov): Playwright/Selenium-based, parcel number form filling
- **Harris County, TX** (www.hctax.net): Enhanced JavaScript handling, waits for dynamic content

#### North Carolina County Extractors
- **Wayne County** (pwa.waynegov.com): Direct link, filters property values vs tax amounts
- **Johnston County** (taxpay.johnstonnc.com): Business name search, table extraction
- **Craven County** (bttaxpayerportal.com): Account number search, year-specific extraction
- **Wilson County** (wilsonnc.devnetwedge.com): Business search, detail page navigation
- **Vance, Moore, Beaufort Counties**: Use appropriate fallback extractors

### Error Handling Strategy
- Exponential backoff with configurable retry counts
- Circuit breakers to prevent cascading failures
- Domain-specific rate limiting
- Fallback extraction methods

### Data Validation
- Currency format validation
- Address normalization
- Date parsing and validation
- Tax amount range checks ($100-$50,000 typical)
- **Property value filtering**: Distinguishes tax amounts from property values
- **HTML/JavaScript detection**: Ensures extracted values are actual data, not page source

## Input/Output Formats

### Input Excel Columns
- Property ID
- Property Name
- Property Address (optional)
- Jurisdiction
- State
- Acct Number (optional)  
- Tax Bill Link

### Output Structure
- Excel with multiple sheets (results, summary, validation, errors)
- JSON for programmatic access
- Intermediate results saved periodically
- Screenshots for debugging (optional)

## Important Considerations

- Respect rate limits and robots.txt
- Handle authentication when required
- Process in batches for large datasets
- Validate extracted data before use
- Monitor circuit breaker states for failing domains
- **Use MASTER_TAX_EXTRACTOR.py** as the primary extraction tool - it includes all the latest fixes
- **Property vs Tax Validation**: Always verify amounts are taxes (1-3% of property value) not property values
- **JavaScript Sites**: Use Playwright/Selenium extractors for dynamic content (Maricopa, Harris, some NC counties)