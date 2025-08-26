# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a comprehensive property tax extraction system with Supabase integration, designed to scrape and extract tax information from various county tax websites. The system features a REST API, real-time dashboard, database persistence, authentication, and supports both simple HTTP requests and Selenium-based scraping for JavaScript-heavy sites.

## 🏗️ System Architecture

### Core Components
1. **Supabase Database**: PostgreSQL database hosting 102 properties and 43 entities with RLS policies
2. **REST API**: FastAPI service with Supabase integration (`api_service_supabase.py`, `api_with_auth.py`)
3. **Dashboard**: Streamlit interface with real-time data visualization (`dashboard_supabase.py`)
4. **Extraction Engine**: Robust tax extraction with multiple methods
5. **Authentication**: Supabase Auth with JWT tokens

## 📁 Key Architecture Components

### Database Layer (Supabase)
- **supabase_client.py**: Database client with sync/async operations
- **supabase_auth.py**: Authentication manager with JWT handling
- **supabase/migrations/**: SQL migration files for schema setup
- PostgreSQL database with 5 core tables: entities, properties, tax_extractions, jurisdictions, entity_relationships

### API Layer
- **api_service_supabase.py**: Main API with Supabase integration
- **api_with_auth.py**: Enhanced API with full authentication
- **api_service_enhanced.py**: Production-ready API with advanced features
- FastAPI endpoints for properties, entities, extractions, and statistics

### Dashboard Layer
- **streamlit_app.py**: Production dashboard deployed on Streamlit Cloud
- Real-time data visualization with Plotly charts
- 5 tabs: Overview, Properties, Entities, Analytics, Tax Extraction
- Entity-based filtering for properties
- No CSV uploads needed - all data from Supabase

#### Dashboard Properties Tab Fields
- Property Name
- Address
- Jurisdiction
- State
- Tax Amount Due (including $0.00 and null values)
- Due Date (color-coded by urgency)
- Paid By (color-coded: Landlord/Tenant/Tenant to Reimburse)
- Tax Bill URL

### Core Extraction Engine
- **cloud_extractor.py**: Cloud-compatible HTTP-only extractor (deployed to production)
- **MASTER_TAX_EXTRACTOR.py**: Advanced Playwright-based extractors (local only)
- **robust_tax_extractor.py**: Main extraction engine with circuit breakers, retry logic
- **selenium_tax_extractors.py**: Browser-based extractors for complex sites (local only)
- **Supported Cloud Jurisdictions**: Montgomery, Fort Bend, Chambers, Galveston, Aldine ISD, Goose Creek ISD, Spring Creek, Barbers Hill ISD

### Support Modules
- **config.py**: Configuration management with environment variable support
- **error_handling.py**: Retry logic, circuit breakers, and custom exception classes
- **data_validation.py**: Data validation and sanitization for extracted tax data
- **test_utilities.py**: Comprehensive testing framework
- **tax_extractor_client.py**: Python SDK for API integration

### Data Flow
1. Properties and entities stored in Supabase database
2. API triggers extraction jobs for selected properties
3. Extraction engine fetches tax data from county websites
4. Results stored back in Supabase with validation
5. Dashboard displays real-time updates and analytics
6. Export to Excel/CSV for reporting

## 🚀 Quick Start

### Production Deployment (LIVE)
- **🌐 Live API**: https://tax-extraction-system-production.up.railway.app/
- **📊 Live Dashboard**: Deployed on Streamlit Cloud
- **📚 API Docs**: https://tax-extraction-system-production.up.railway.app/docs
- **🏗️ Platform**: Railway (API) + Streamlit Cloud (Dashboard)
- **📦 Repository**: https://github.com/kwoody20/tax-extraction-system
- **🔄 Extraction**: Cloud-ready with 8 supported jurisdictions

### Local Development
```bash
# 1. Start API Service
python api_service_supabase.py

# 2. Start Dashboard (in new terminal)
streamlit run streamlit_app.py

# 3. Access Services
# API: http://localhost:8000/docs
# Dashboard: http://localhost:8501
```

### Database Credentials
- **Supabase URL**: https://klscgjbachumeojhxyno.supabase.co
- **Current Data**: 102 properties, 43 entities
- **Total Tax Liability**: $50,058.52 outstanding, $434,291.55 previous year

## Common Commands

### Database Operations
```bash
# Import data from CSV to Supabase
python import_data_to_supabase_fixed.py

# Test Supabase authentication
python supabase_auth.py test

# Create test users
python supabase_auth.py create-users

# Verify database data
python verify_supabase_data.py
```

### API Operations
```bash
# Start API with Supabase integration
python api_service_supabase.py

# Start API with full authentication
python api_with_auth.py

# Test API endpoints
python test_api_supabase.py

# Test authentication flow
python test_auth_flow.py
```

### Dashboard Operations
```bash
# Start Streamlit dashboard
streamlit run streamlit_app.py
```

### Running Extractors
```bash
# Master extraction system (recommended)
python MASTER_TAX_EXTRACTOR.py extraction-links-and-steps.xlsx --concurrent

# Selenium-based extraction for Maricopa/Harris
python selenium_tax_extractors.py

# NC property extraction
python process_with_selenium.py phase-two-taxes-8-17.xlsx --headless

# Robust extraction with all features
python robust_tax_extractor.py
```

### Testing
```bash
# Run test suite
python test_utilities.py

# Test API with Supabase
python test_api_supabase.py

# Test authentication flow
python test_auth_flow.py

# Test specific extractors
python test_selenium_extractors.py
python test_nc_extractors.py
```

### Dependencies
```bash
# Install all requirements
pip install -r requirements.txt

# Supabase specific
pip install supabase

# Install Playwright browsers
playwright install chromium

# Install ChromeDriver for Selenium (macOS)
brew install chromedriver
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

### Input Excel Columns (extraction-links-and-steps.xlsx)
- Property ID
- Property Name
- Property Address
- Jurisdiction
- State
- Property Type
- Close Date
- Amount Due
- Previous Year Taxes
- Extraction Steps
- Acct Number
- Next Due Date
- Tax Bill Link
- Parent Entity

### Output Structure
- Excel with multiple sheets (results, summary, validation, errors)
- JSON for programmatic access
- Intermediate results saved periodically
- Screenshots for debugging (optional)

## Important Considerations

### System Architecture
- **Database First**: All property and entity data is stored in Supabase PostgreSQL
- **API Driven**: Use the FastAPI service for all extraction operations
- **Dashboard Monitoring**: Real-time monitoring via Streamlit dashboard
- **Authentication Required**: Supabase Auth with JWT tokens for protected endpoints

### Extraction Best Practices
- Respect rate limits and robots.txt
- Handle authentication when required
- Process in batches for large datasets
- Validate extracted data before use
- Monitor circuit breaker states for failing domains
- **Use MASTER_TAX_EXTRACTOR.py** as the primary extraction tool - it includes all the latest fixes
- **Property vs Tax Validation**: Always verify amounts are taxes (1-3% of property value) not property values
- **JavaScript Sites**: Use Playwright/Selenium extractors for dynamic content (Maricopa, Harris, some NC counties)

### Supabase Configuration
- **RLS Policies**: Row Level Security enabled on all tables
- **Auth Settings**: Email confirmation can be disabled for development
- **Service URLs**: 
  - Database: https://klscgjbachumeojhxyno.supabase.co
  - Production API: https://tax-extraction-system-production.up.railway.app
  - Local API: http://localhost:8000
  - Local Dashboard: http://localhost:8501

### Current System Status
- ✅ 102+ properties loaded in database
- ✅ 43+ entities configured with hierarchy (Parent/Sub/Single-Property)
- ✅ API service LIVE at https://tax-extraction-system-production.up.railway.app
- ✅ Dashboard LIVE on Streamlit Cloud with enhanced filtering
- ✅ Cloud extraction engine integrated (8 supported jurisdictions)
- ✅ Entity-based property filtering
- ✅ Tax Bill URLs visible in dashboard
- ✅ Enhanced Analytics tab with cross-analysis features

### Production API Endpoints
- **Health**: https://tax-extraction-system-production.up.railway.app/health
- **API Docs**: https://tax-extraction-system-production.up.railway.app/docs
- **Properties**: https://tax-extraction-system-production.up.railway.app/api/v1/properties
- **Entities**: https://tax-extraction-system-production.up.railway.app/api/v1/entities
- **Statistics**: https://tax-extraction-system-production.up.railway.app/api/v1/statistics
- **Extract Single**: POST https://tax-extraction-system-production.up.railway.app/api/v1/extract
- **Extract Batch**: POST https://tax-extraction-system-production.up.railway.app/api/v1/extract/batch
- **Extraction Status**: https://tax-extraction-system-production.up.railway.app/api/v1/extract/status
- **Jurisdictions**: https://tax-extraction-system-production.up.railway.app/api/v1/jurisdictions

### Key Files for Reference
- **SUPABASE_AUTH_GUIDE.md**: Complete authentication setup
- **DASHBOARD_GUIDE.md**: Dashboard usage instructions
- **supabase/README.md**: Database schema documentation
- **SUPABASE_EMAIL_SETUP.md**: Email confirmation configuration