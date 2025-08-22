# Tax Extraction System

A comprehensive property tax extraction system with database integration, REST API, and real-time dashboard. This system automates the extraction of tax information from various county tax websites using both HTTP requests and browser automation for JavaScript-heavy sites.

## Features

### Core Capabilities
- **Multi-source extraction**: Supports multiple county tax websites
- **Dual extraction methods**: Uses both `requests` (for simple sites) and `selenium` (for JavaScript-heavy sites)
- **Robust error handling**: Comprehensive error recovery with retry logic and circuit breakers
- **Data validation**: Validates and sanitizes all extracted data
- **Configuration management**: Flexible configuration system with environment variable support
- **Parallel processing**: Optional parallel extraction for improved performance
- **Progress tracking**: Real-time progress updates and intermediate result saving
- **Comprehensive logging**: Detailed logging for debugging and monitoring

### Robustness Features
- **Retry Logic**: Automatic retry with exponential backoff for transient failures
- **Circuit Breaker Pattern**: Prevents cascading failures by temporarily disabling failing endpoints
- **Connection Pooling**: Efficient connection management for better performance
- **Rate Limiting**: Configurable rate limiting per domain to avoid being blocked
- **Request Caching**: Avoids duplicate requests to the same URL
- **Data Validation**: Comprehensive validation of extracted data (currency, addresses, dates, etc.)
- **Error Recovery**: Graceful handling of various error scenarios
- **Intermediate Saves**: Saves progress periodically to prevent data loss

## Installation

1. Install Python 3.8 or higher
2. Install required packages:
```bash
pip install -r requirements.txt
```

3. For Selenium support, install ChromeDriver:
```bash
# macOS
brew install chromedriver

# Or download from https://chromedriver.chromium.org/
```

## Quick Start

### Basic Usage

```python
from robust_tax_extractor import RobustTaxExtractor

# Initialize extractor
extractor = RobustTaxExtractor('your_properties.xlsx')

# Process all properties
results = extractor.process_all()

# Save results
extractor.save_results('extraction_results.xlsx')
```

### Using Configuration

Create a `config.json` file:

```json
{
  "system": {
    "headless": true,
    "max_workers": 4,
    "batch_size": 10,
    "output_dir": "output",
    "save_screenshots": false
  },
  "scrapers": {
    "actweb.acttax.com": {
      "name": "Montgomery County",
      "rate_limit_delay": 2.0,
      "retry_count": 3
    }
  }
}
```

### Environment Variables

You can override configuration using environment variables:

```bash
export TAX_EXTRACTOR_HEADLESS=false
export TAX_EXTRACTOR_MAX_WORKERS=8
export TAX_EXTRACTOR_LOG_LEVEL=DEBUG
```

## Project Structure

```
taxes/
├── robust_tax_extractor.py  # Main extraction engine with all robustness features
├── config.py                # Configuration management system
├── error_handling.py        # Error handling, retry logic, and circuit breakers
├── data_validation.py       # Data validation and sanitization
├── test_utilities.py        # Comprehensive testing framework
├── tax_extractor.py         # Original basic extractor
├── selenium_tax_extractor.py # Selenium-based extractor
├── simple_tax_extractor.py  # Simple analysis tool
└── requirements.txt         # Python dependencies
```

## Input Excel Format

Your Excel file should have the following columns:
- `Property ID`: Unique identifier for the property
- `Property Name`: Name/description of the property
- `Property Address`: Physical address (optional)
- `Jurisdiction`: Tax jurisdiction
- `State`: State code
- `Acct Number`: Account number (optional)
- `Tax Bill Link`: URL to the tax information page

## Output Format

The system generates multiple output formats:

### Excel Output (extraction_results.xlsx)
Multiple sheets containing:
1. **Extraction Results**: Complete extraction data for all properties
2. **Summary Statistics**: Overall extraction statistics
3. **Validation Report**: Data validation issues
4. **Error Log**: Detailed error information

### JSON Output (extraction_results.json)
Structured JSON with all extraction data, suitable for programmatic access.

## Supported Tax Websites

Currently configured for:
- Montgomery County (actweb.acttax.com)
- Harris County (www.hctax.net)
- Maricopa County (treasurer.maricopa.gov)
- Aldine ISD (tax.aldine.k12.tx.us)
- And more can be easily added via configuration

## Advanced Features

### Parallel Processing

Enable parallel processing for faster extraction:

```python
extractor = RobustTaxExtractor('properties.xlsx')
results = extractor.process_all(parallel=True)
```

### Custom Validation Rules

Add custom validation in `data_validation.py`:

```python
validator = DataValidator()
validator.config = {
    'min_tax_amount': 100.0,
    'max_tax_amount': 100000.0
}
```

### Error Handling

The system includes multiple levels of error handling:

1. **Network Errors**: Automatic retry with backoff
2. **Parse Errors**: Fallback extraction methods
3. **Validation Errors**: Data sanitization and correction
4. **Rate Limiting**: Automatic delay and retry
5. **Authentication Errors**: Logged and skipped

### Circuit Breaker

Prevents overwhelming failing services:

```python
breaker = CircuitBreaker(
    failure_threshold=5,    # Open after 5 failures
    recovery_timeout=60     # Try again after 60 seconds
)
```

## Testing

Run the comprehensive test suite:

```bash
python test_utilities.py
```

The test suite includes:
- Unit tests for all components
- Integration tests
- Mock testing for external services
- Data validation tests
- Error handling tests

## Monitoring and Debugging

### Logging

Detailed logs are saved to `robust_tax_extraction.log` with:
- Timestamp
- Log level
- Module and line number
- Detailed error messages

### Progress Tracking

Real-time progress updates show:
- Current property being processed
- Percentage complete
- Extraction success/failure rates
- Error summaries

### Intermediate Results

Results are saved periodically to prevent data loss:
- Located in `output/intermediate/`
- JSON format for easy recovery
- Timestamped for tracking

## Performance Optimization

1. **Connection Pooling**: Reuses HTTP connections
2. **Request Caching**: Avoids duplicate requests
3. **Parallel Processing**: Process multiple properties simultaneously
4. **Batch Processing**: Efficient memory usage for large datasets
5. **Selective Extraction**: Skip already-processed properties

## Troubleshooting

### Common Issues

1. **ChromeDriver not found**
   - Install ChromeDriver and ensure it's in PATH
   - Or specify path in configuration

2. **Rate limiting errors**
   - Increase `rate_limit_delay` in configuration
   - Reduce `max_workers` for parallel processing

3. **Memory issues with large datasets**
   - Reduce `batch_size` in configuration
   - Process in smaller chunks

4. **SSL/Certificate errors**
   - Update certificates: `pip install --upgrade certifi`
   - Or disable SSL verification (not recommended)

## Contributing

To add support for a new tax website:

1. Add configuration in `config.py`
2. Implement extraction logic in `robust_tax_extractor.py`
3. Add validation rules if needed
4. Write tests in `test_utilities.py`

## Security Considerations

- Never commit credentials or API keys
- Use environment variables for sensitive data
- Be respectful of rate limits
- Follow robots.txt guidelines
- Consider legal implications of web scraping

## License

This project is for educational and legitimate tax management purposes only. Ensure compliance with all applicable laws and website terms of service.

## Support

For issues or questions:
1. Check the logs in `robust_tax_extraction.log`
2. Review error reports in the Excel output
3. Run tests to verify system integrity
4. Check configuration settings