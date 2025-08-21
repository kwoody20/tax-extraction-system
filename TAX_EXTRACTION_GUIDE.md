# Property Tax Extraction Guide

## Overview
This guide provides instructions for extracting property tax information from various county tax websites. The process can be automated for some sites and requires manual extraction for others.

## Current Status
- **Total Properties**: 145
- **Properties with Tax Links**: 121 (83.4%)
- **Unique Tax Domains**: 43
- **Top Domains**:
  - actweb.acttax.com: 31 properties (Montgomery County)
  - www.hctax.net: 16 properties (Harris County)
  - www.utilitytaxservice.com: 6 properties
  - treasurer.maricopa.gov: 4 properties

## Automation Tools

### 1. Simple Tax Extractor (`simple_tax_extractor.py`)
Basic extractor that analyzes the Excel file and creates extraction guides.

```bash
python3 simple_tax_extractor.py
```

**Output**: `tax_extraction_analysis.xlsx` with two sheets:
- Extraction Results: All properties with extraction status
- Domain Guide: Instructions for each domain

### 2. Selenium Tax Extractor (`selenium_tax_extractor.py`)
Advanced extractor for JavaScript-heavy sites (requires ChromeDriver).

```bash
# Install ChromeDriver first
brew install chromedriver  # Mac
# Or download from https://chromedriver.chromium.org/

python3 selenium_tax_extractor.py
```

### 3. Basic HTTP Extractor (`tax_extractor.py`)
Template for building custom scrapers per domain.

## Manual Extraction Instructions by Domain

### Montgomery County (actweb.acttax.com)
**31 properties**

1. Click the tax bill link (contains account number in URL)
2. Page loads with property details
3. Extract:
   - **Account Number**: In URL parameter `can=`
   - **Property Address**: Listed on page
   - **Total Due**: Current tax amount
   - **Previous Year**: Prior year tax amount

### Harris County (www.hctax.net)
**16 properties**

1. Click the tax bill link
2. If redirected to search:
   - Enter account number or property address
   - Click search
3. On tax statement page, extract:
   - **Property Address**: Top of statement
   - **Amount Due**: Total due section
   - **Due Date**: Payment deadline

### Maricopa County (treasurer.maricopa.gov)
**4 properties**

1. Navigate to treasurer website
2. Click "Property Tax" or "Search"
3. Search by:
   - Parcel number
   - Property address
   - Owner name
4. Extract from results:
   - **Parcel Number**: Tax ID
   - **Property Address**: Full address
   - **Tax Amount**: Current year taxes

### Utility Tax Service (www.utilitytaxservice.com)
**6 properties**

1. Access the provided link
2. May require login credentials
3. Navigate to property tax section
4. Extract available tax information

## Data Fields to Extract

For each property, attempt to extract:

| Field | Priority | Description |
|-------|----------|-------------|
| Account Number | High | Tax account or parcel number |
| Property Address | High | Physical property location |
| Amount Due | High | Current tax amount owed |
| Previous Year Taxes | Medium | Prior year tax amount for comparison |
| Next Due Date | Medium | Payment deadline |
| Tax ID | Low | Additional identification number |

## Extraction Workflow

### Automated Approach
1. Run `simple_tax_extractor.py` to generate analysis
2. Review `tax_extraction_analysis.xlsx`
3. For supported domains, run selenium extractor
4. Manually verify automated extractions

### Manual Approach
1. Open `phase-two-taxes-8-17.xlsx`
2. Filter by domain (sort Tax Bill Link column)
3. Process properties by domain batch
4. Use domain-specific instructions above
5. Update Excel with extracted values

### Semi-Automated Approach
1. Use browser automation tools (Selenium IDE, AutoHotkey)
2. Record extraction steps for each domain
3. Replay for similar properties
4. Manual verification and correction

## Tips for Efficient Extraction

1. **Batch by Domain**: Process all properties from same domain together
2. **Use Multiple Tabs**: Open 5-10 properties at once
3. **Create Templates**: Note extraction patterns for each site
4. **Track Progress**: Mark completed properties in Excel
5. **Handle Errors**: Note properties requiring special attention

## Common Issues and Solutions

| Issue | Solution |
|-------|----------|
| Login Required | Check if company has credentials |
| CAPTCHA | Manual intervention required |
| Session Timeout | Process in smaller batches |
| Missing Data | Note as "Not Available" |
| Different Tax Years | Note the tax year extracted |

## Data Validation

After extraction, validate:
- Account numbers match expected format
- Amounts are reasonable (not $0 unless confirmed)
- Addresses are complete
- Dates are in consistent format

## Next Steps

1. **Priority 1**: Extract data for top 5 domains (covers ~70% of properties)
2. **Priority 2**: Document extraction steps for remaining domains
3. **Priority 3**: Build automated extractors for high-volume domains
4. **Priority 4**: Create data validation and reconciliation process

## Support Files

- `requirements.txt`: Python dependencies
- `tax_extraction_analysis.xlsx`: Analysis results
- `extraction_results.xlsx`: Extraction output
- `tax_extraction.log`: Execution logs

## Contact for Issues

For properties that cannot be extracted:
1. Note the issue in Excel
2. Flag for manual review
3. Consider contacting the tax office directly