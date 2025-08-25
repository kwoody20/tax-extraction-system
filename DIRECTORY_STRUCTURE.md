# Tax Extraction System - Complete Directory Structure

Generated: 2025-08-25

## Project Overview
This comprehensive property tax extraction system contains 199 files (excluding git and compiled files) organized across multiple functional areas including API services, database integration, extraction engines, and dashboards.

## Directory Tree Structure

```
taxes/
├── Root Configuration & Documentation Files
├── Python Source Files (Core Application)
├── Data Files (CSV, Excel, JSON)
├── Configuration Directories
│   ├── .claude/
│   ├── .devcontainer/
│   ├── .streamlit/
│   └── __pycache__/
├── Archive Directory
├── Extraction Test Suite (extracting-tests-818/)
└── Supabase Database (supabase/)
```

## Detailed File Listing by Category

### 📄 Root Documentation Files (*.md)
- `ARCHITECTURE_OVERVIEW.md` - System architecture documentation (Aug 24)
- `CLAUDE.md` - Claude AI assistant instructions (Aug 24)
- `DASHBOARD_GUIDE.md` - Dashboard usage guide (Aug 21)
- `DEPLOYMENT_GUIDE.md` - Deployment instructions (Aug 21)
- `DEPLOYMENT_SUCCESS.md` - Deployment success notes (Aug 21)
- `DEPLOYMENT.md` - General deployment documentation (Aug 22)
- `ENTITY_RELATIONSHIPS_SETUP.md` - Entity relationships setup guide (new)
- `LOCAL_EXTRACTION_README.md` - Local extraction setup guide (Aug 24)
- `NC_EXTRACTION_SUMMARY.md` - North Carolina extraction summary (Aug 24)
- `RAILWAY_DEPLOYMENT_FIX.md` - Railway deployment fixes (Aug 24)
- `RAILWAY_DEPLOYMENT.md` - Railway deployment guide (Aug 24)
- `RAILWAY_FIX.md` - Railway platform fixes (Aug 24)
- `RAILWAY_MINIMAL_DEPLOY.md` - Minimal Railway deployment (Aug 24)
- `README_SERVICES.md` - Services documentation (Aug 24)
- `README.md` - Main project README (Aug 22)
- `REPLIT_PROJECT_GUIDE.md` - Replit setup guide (Aug 24)
- `SELENIUM_USAGE_GUIDE.md` - Selenium usage documentation (Aug 24)
- `STREAMLIT_DEPLOYMENT.md` - Streamlit deployment guide (deleted)
- `SUPABASE_AUTH_GUIDE.md` - Supabase authentication guide (Aug 24)
- `SUPABASE_EMAIL_SETUP.md` - Supabase email configuration (Aug 24)
- `TAX_EXTRACTION_GUIDE.md` - Tax extraction guide (Aug 24)

### 🐍 Core Python API Services
- `api_minimal.py` - Minimal API implementation (Aug 24)
- `api_public_with_extraction.py` - Public API with extraction (Aug 24)
- `api_public.py` - Public API service (Aug 24)
- `api_service_enhanced.py` - Enhanced API with features (Aug 21)
- `api_service_supabase.py` - Supabase integrated API (Aug 24)
- `api_service.py` - Base API service (Aug 21)
- `api_with_auth.py` - API with authentication (Aug 21)
- `api_with_extraction.py` - API with extraction features (Aug 24)
- `app.py` - Main application entry (Aug 22)

### 🎯 Extraction Engine Files
- `cloud_extractor_enhanced.py` - Enhanced cloud extractor (Aug 24)
- `cloud_extractor.py` - Cloud-compatible extractor (Aug 24)
- `local_extraction_suite.py` - Local extraction suite (Aug 24)
- `nc_property_extractors.py` - North Carolina extractors (Aug 24)
- `robust_tax_extractor.py` - Robust extraction engine (Aug 23)
- `selenium_tax_extractor.py` - Selenium-based extractor (Aug 24)
- `selenium_tax_extractors.py` - Multiple Selenium extractors (Aug 23)
- `simple_extractor.py` - Simple extraction logic (Aug 24)
- `simple_tax_extractor.py` - Basic tax extractor (Aug 24)
- `tax_extractor_client.py` - Tax extractor client SDK (Aug 24)
- `tax_extractor.py` - Core tax extractor (Aug 19)
- `extract_missing_data.py` - Missing data extraction (Aug 24)
- `process_with_selenium.py` - Selenium processing (Aug 24)

### 📊 Dashboard & UI Files
- `dashboard_streamlit.py` - Streamlit dashboard (Aug 22)
- `dashboard_supabase.py` - Supabase dashboard (Aug 24)
- `dashboard.py` - Base dashboard (Aug 21)
- `streamlit_app.py` - Main Streamlit app (Aug 24)

### 🗄️ Database & Supabase Integration
- `supabase_auth.py` - Supabase authentication (Aug 24)
- `supabase_client.py` - Supabase client wrapper (Aug 24)
- `import_data_to_supabase_fixed.py` - Fixed data importer (Aug 24)
- `import_data_to_supabase.py` - Data importer (Aug 24)
- `update_supabase_data.py` - Data updater (Aug 24)
- `verify_supabase_data.py` - Data verification (Aug 24)
- `apply_migration.py` - Migration runner (Aug 24)

### 🔧 Entity & Relationship Management
- `assign_parent_entities_fixed.py` - Fixed parent assignment (Aug 24)
- `assign_parent_entities.py` - Parent entity assignment (Aug 24)
- `check_parent_entities.py` - Parent entity checker (Aug 24)
- `create_aldine_entity.py` - Aldine entity creator (Aug 24)
- `create_entity_relationships.py` - Relationship creator (Aug 24)
- `link_entity_relationships.py` - Relationship linker (Aug 24)
- `setup_and_link_entities.py` - Entity setup script (Aug 24)
- `add_parent_entity_column.sql` - SQL migration (new)

### 🧪 Testing Files
- `test_api_service.py` - API service tests (Aug 24)
- `test_api_supabase.py` - Supabase API tests (Aug 24)
- `test_app.py` - Application tests (Aug 24)
- `test_auth_flow.py` - Authentication flow tests (Aug 24)
- `test_cloud_extraction.py` - Cloud extraction tests (Aug 24)
- `test_extraction_tab.py` - Extraction tab tests (Aug 24)
- `test_nc_extractors.py` - NC extractor tests (Aug 24)
- `test_selenium_extractors.py` - Selenium tests (Aug 24)
- `test_streamlit.py` - Streamlit tests (Aug 24)
- `test_utilities.py` - Test utilities (Aug 19)
- `test_wayne_county.py` - Wayne County tests (Aug 24)
- `test_wayne_direct.py` - Wayne direct tests (Aug 24)

### 📈 Analysis & Utilities
- `analyze_data_completeness.py` - Data completeness analysis (Aug 24)
- `analyze_data_via_api.py` - API data analysis (Aug 24)
- `analyze_json_data.py` - JSON data analyzer (Aug 24)
- `export_properties_for_mapping.py` - Property exporter (Aug 24)
- `run_address_extraction.py` - Address extraction runner (Aug 24)
- `scrape_addresses.py` - Address scraper (Aug 24)
- `update_properties_with_new_fields.py` - Property updater (Aug 24)
- `fix_remaining_imports.py` - Import fixer (Aug 24)

### ⚙️ Support & Configuration
- `config.py` - Configuration management (Aug 17)
- `data_validation.py` - Data validation utilities (Aug 17)
- `error_handling.py` - Error handling utilities (Aug 17)
- `celery_queue.py` - Celery queue configuration (Aug 21)

### 📁 Data Files (CSV)
- `cleaned-entities.csv` - Cleaned entity data (Aug 24)
- `entities-proptax-8202025.csv` - Entity data (Aug 20)
- `extracted_data_20250823_134809.csv` - Extracted data (Aug 23)
- `field_completeness_20250823_134154.csv` - Field analysis (Aug 23)
- `OFFICIAL-proptax-assets.csv` - Official property assets (Aug 20)
- `OFFICIAL-proptax-extract.csv` - Official extractions (Aug 23)
- `properties_to_scrape_20250823_134809.csv` - Scraping queue (Aug 23)
- `properties-with-new-fields.csv` - Enhanced properties (Aug 24)
- `scraped_addresses_20250823_135124.csv` - Scraped addresses (Aug 23)

### 📁 Data Files (Excel)
- `entities-proptax-8202025.xlsx` - Entity spreadsheet (Aug 24)
- `phase-two-taxes-8-17.xlsx` - Phase 2 tax data (Aug 18)
- `tax_extraction_analysis.xlsx` - Extraction analysis (Aug 24)
- `test_extraction_results.xlsx` - Test results (Aug 24)
- `updated-asset-tracker.xlsx` - Updated asset tracker (Aug 24)

### 📁 Data Files (JSON)
- `parent_entity_assignment_20250824_150456.json` - Parent assignments (Aug 24)
- `parent_entity_assignment_20250824_150649.json` - Parent assignments (Aug 24)
- `parent_entity_assignment_20250824_151311.json` - Parent assignments (Aug 24)
- `parent_entity_report_20250824_145718.json` - Parent report (Aug 24)
- `parent_entity_report_20250824_151337.json` - Parent report (Aug 24)
- `properties_data.json` - Properties data (Aug 24)
- `railway.json` - Railway configuration (Aug 24)
- `supabase_update_log_20250823_140144.json` - Update log (Aug 23)
- `vercel_correct.json` - Vercel config (Aug 24)
- `vercel.json` - Vercel configuration (Aug 21)

### 🔧 Configuration Files
- `railway.toml` - Railway configuration (Aug 21)
- `runtime.txt` - Python runtime specification (Aug 21)
- `requirements.txt` - Main requirements (Aug 24)
- `requirements-railway.txt` - Railway requirements (Aug 22)
- `streamlit_secrets.toml` - Streamlit secrets (Aug 24)
- `railway-deployment.txt` - Deployment notes (Aug 24)

### 📝 Log Files
- `master_tax_extraction.log` - Master extraction log (Aug 23)
- `nc_tax_extraction.log` - NC extraction log (Aug 24)
- `robust_tax_extraction.log` - Robust extraction log (Aug 24)
- `tax_extraction.log` - Tax extraction log (Aug 24)

### 🐚 Shell Scripts
- `run_local_extraction.sh` - Local extraction runner (Aug 24)
- `setup.sh` - Setup script (Aug 18)
- `start_services.sh` - Service starter (Aug 24)
- `stop_services.sh` - Service stopper (Aug 24)

### 🔐 Environment Files
- `.env` - Environment variables (Aug 24)
- `.env.example` - Example environment file (Aug 21)
- `.gitignore` - Git ignore rules (Aug 21)
- `LICENSE` - Project license (Aug 21)
- `dump.rdb` - Redis dump file (Aug 22)

## 📂 Subdirectories

### .claude/ (4 files)
AI assistant configuration and agent definitions
```
.claude/
├── settings.local.json - Local settings (Aug 24)
└── agents/ (5 files)
    ├── directory-analyzer.md - Directory analysis agent (Aug 24)
    ├── rest-api-fastapi-expert.md - FastAPI expert agent (Aug 24)
    ├── selenium-automation-expert.md - Selenium expert agent (Aug 24)
    ├── streamlit-ui-developer.md - Streamlit developer agent (Aug 24)
    └── web-scraping-expert.md - Web scraping expert agent (Aug 24)
```

### .devcontainer/ (1 file)
Development container configuration
```
.devcontainer/
└── devcontainer.json - Dev container config (Aug 21)
```

### .streamlit/ (2 files)
Streamlit application configuration
```
.streamlit/
├── config.toml - Streamlit config (Aug 24)
└── secrets.toml - Streamlit secrets (Aug 24)
```

### archive/ (9 files)
Archived requirement files
```
archive/
├── requirements-api.txt - API requirements (Aug 21)
├── requirements-full.txt - Full requirements (Aug 21)
├── requirements_api.txt - API requirements alt (Aug 21)
├── requirements_auto.txt - Auto requirements (Aug 21)
├── requirements_basic.txt - Basic requirements (Aug 21)
├── requirements_minimal.txt - Minimal requirements (Aug 21)
├── requirements_services.txt - Services requirements (Aug 21)
├── requirements_streamlit.txt - Streamlit requirements (Aug 21)
└── requirements_vercel.txt - Vercel requirements (Aug 21)
```

### extracting-tests-818/ (38 files)
Advanced extraction test suite with Playwright/Selenium extractors
```
extracting-tests-818/
├── Python Scripts (11 files)
│   ├── MASTER_TAX_EXTRACTOR.py - Master extraction system (Aug 20)
│   ├── debug_maricopa.py - Maricopa debugger (Aug 18)
│   ├── extract_montgomery_direct.py - Montgomery extractor (Aug 20)
│   ├── extract_new_properties.py - New property extractor (Aug 20)
│   ├── extract_new_records.py - New record extractor (Aug 20)
│   ├── investigate_montgomery.py - Montgomery investigator (Aug 20)
│   ├── run_extraction.py - Extraction runner (Aug 18)
│   ├── test_extraction.py - Extraction tests (Aug 20)
│   ├── test_maricopa_extraction.py - Maricopa tests (Aug 18)
│   └── test_maricopa.py - Maricopa unit tests (Aug 18)
│
├── Data Files (CSV) (8 files)
│   ├── extracted_tax_data.csv - Extracted data (Aug 20)
│   ├── extraction_maricopa.csv - Maricopa results (Aug 18)
│   ├── extraction_montgomery.csv - Montgomery results (Aug 20)
│   ├── maricopa_test_results.csv - Test results (Aug 18)
│   ├── montgomery_direct_extraction.csv - Direct extraction (Aug 20)
│   ├── new_properties_extraction.csv - New properties (Aug 20)
│   └── test_extraction_results.csv - Test results (Aug 20)
│
├── JSON Files (7 files)
│   ├── extraction_summary.json - Extraction summary (Aug 20)
│   ├── montgomery_direct_extraction.json - Direct results (Aug 20)
│   ├── montgomery_investigation_results.json - Investigation (Aug 20)
│   ├── new_properties_summary.json - New properties summary (Aug 20)
│   ├── new_records_summary.json - New records summary (Aug 20)
│   ├── summary_maricopa.json - Maricopa summary (Aug 18)
│   └── summary_montgomery.json - Montgomery summary (Aug 20)
│
├── Log Files (5 files)
│   ├── full_extraction.log - Full extraction log (Aug 20)
│   ├── master_tax_extraction.log - Master log (Aug 23)
│   ├── montgomery_investigation.log - Investigation log (Aug 20)
│   └── tax_extraction.log - Tax extraction log (Aug 20)
│
├── Other Files (3 files)
│   ├── phase-two-taxes-8-17.xlsx - Phase 2 data (Aug 19)
│   ├── requirements.txt - Package requirements (Aug 18)
│   └── setup.sh - Setup script (Aug 18)
│
└── __pycache__/ (2 compiled files)
```

### supabase/ (15 files)
Supabase database configuration and migrations
```
supabase/
├── README.md - Database documentation (Aug 21)
├── .gitignore - Git ignore rules (Aug 21)
└── migrations/ (13 SQL files)
    ├── 001_create_entities.sql - Entity table (Aug 21)
    ├── 002_create_properties.sql - Property table (Aug 21)
    ├── 003_create_tax_extractions.sql - Extraction table (Aug 21)
    ├── 004_create_jurisdictions.sql - Jurisdiction table (Aug 21)
    ├── 005_create_relationships.sql - Relationship table (Aug 21)
    ├── 006_create_views.sql - Database views (Aug 21)
    ├── 007_create_functions.sql - SQL functions (Aug 21)
    ├── 008_create_rls_policies.sql - RLS policies (Aug 21)
    ├── 009_temporary_disable_rls.sql - Disable RLS (Aug 21)
    ├── 010_restore_rls.sql - Restore RLS (Aug 21)
    ├── 011_fix_anon_access.sql - Fix access (Aug 21)
    ├── 011_fix_anon_access_v2.sql - Fix access v2 (Aug 21)
    └── 012_add_tax_due_date_and_paid_by.sql - Add fields (Aug 24)
```

### __pycache__/ (15 compiled files)
Python bytecode cache files
```
__pycache__/
├── api_minimal.cpython-312.pyc
├── api_service_supabase.cpython-312.pyc
├── api_service.cpython-312.pyc
├── celery_queue.cpython-312.pyc
├── cloud_extractor_enhanced.cpython-312.pyc
├── cloud_extractor.cpython-312.pyc
├── config.cpython-312.pyc
├── data_validation.cpython-312.pyc
├── error_handling.cpython-312.pyc
├── nc_property_extractors.cpython-312.pyc
├── robust_tax_extractor.cpython-312.pyc
├── streamlit_app.cpython-312.pyc
├── supabase_auth.cpython-312.pyc
├── supabase_client.cpython-312.pyc
└── tax_extractor.cpython-312.pyc
```

## 📊 File Statistics

### Total File Count by Type
- Python files (.py): 87 files
- Markdown documentation (.md): 20 files
- CSV data files (.csv): 10 files
- JSON files (.json): 15 files
- SQL migrations (.sql): 13 files
- Excel files (.xlsx): 5 files
- Text files (.txt): 11 files
- Log files (.log): 9 files
- Shell scripts (.sh): 5 files
- Configuration files (.toml): 3 files
- Other files: 21 files

### Total: 199 files (excluding .git and compiled files)

### Directory Summary
- Root directory: 130 files
- .claude/agents: 5 files
- .devcontainer: 1 file
- .streamlit: 2 files
- archive: 9 files
- extracting-tests-818: 36 files
- supabase/migrations: 13 files
- __pycache__: 15 compiled files

## 🕐 Recent Activity (Last 7 Days)

### Most Recently Modified Files (August 24-25, 2025)
1. Entity relationship management files (create_entity_relationships.py, link_entity_relationships.py)
2. Supabase integration updates
3. Dashboard enhancements
4. API service improvements
5. Documentation updates

### Active Development Areas
- Entity relationship system
- Supabase database integration
- Cloud extraction capabilities
- Dashboard features
- API authentication

## 🔗 Key File Dependencies

### Core System Flow
1. **Database Layer**: supabase_client.py → supabase_auth.py → migrations/
2. **API Layer**: api_service_supabase.py → config.py → error_handling.py
3. **Extraction Engine**: robust_tax_extractor.py → cloud_extractor.py → data_validation.py
4. **Dashboard**: streamlit_app.py → dashboard_supabase.py → supabase_client.py
5. **Testing**: test_utilities.py → test_api_supabase.py → test_extraction_tab.py

### External Dependencies
- Supabase (database and authentication)
- FastAPI (API framework)
- Streamlit (dashboard framework)
- Playwright/Selenium (web scraping)
- Pandas (data processing)
- Redis/Celery (task queue)

## 🚀 Deployment Configuration

### Production Files
- railway.toml - Railway platform config
- vercel.json - Vercel deployment
- requirements-railway.txt - Railway dependencies
- runtime.txt - Python version
- .env.example - Environment template

### Local Development
- .devcontainer/devcontainer.json - VS Code dev container
- .streamlit/config.toml - Streamlit settings
- run_local_extraction.sh - Local runner
- start_services.sh / stop_services.sh - Service management

---

*This directory structure represents the complete Tax Extraction System as of August 25, 2025.*