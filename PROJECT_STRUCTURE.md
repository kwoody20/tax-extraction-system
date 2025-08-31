# Project Structure - Tax Extraction System

## Overview
This document describes the organized directory structure of the Tax Extraction System after refactoring for better maintainability and clarity.

## Directory Layout

```
taxes/
├── src/                          # Main application source code
│   ├── __init__.py
│   ├── extractors/              # Tax extraction modules
│   │   ├── __init__.py
│   │   ├── cloud_extractor.py
│   │   ├── cloud_extractor_enhanced.py
│   │   ├── MASTER_TAX_EXTRACTOR.py
│   │   ├── robust_tax_extractor.py
│   │   ├── selenium_tax_extractors.py
│   │   ├── selenium_tax_extractor.py
│   │   ├── nc_property_extractors.py
│   │   ├── simple_extractor.py
│   │   ├── simple_tax_extractor.py
│   │   ├── tax_extractor.py
│   │   ├── tax_extractor_client.py
│   │   ├── process_with_selenium.py
│   │   └── local_extraction_suite.py
│   │
│   ├── api/                     # API services
│   │   ├── __init__.py
│   │   ├── api_public.py        # Main FastAPI application
│   │   ├── extractor_ui_service.py
│   │   └── celery_queue.py      # Async task queue
│   │
│   ├── dashboard/               # Streamlit dashboard
│   │   ├── __init__.py
│   │   ├── streamlit_app.py
│   │   ├── streamlit_utils.py
│   │   └── streamlit_document_manager.py
│   │
│   ├── database/                # Database integration
│   │   ├── __init__.py
│   │   ├── supabase_client.py
│   │   ├── supabase_auth.py
│   │   └── migrate_to_optimized_api.py
│   │
│   └── utils/                   # Shared utilities
│       ├── __init__.py
│       ├── config.py
│       ├── error_handling.py
│       ├── data_validation.py
│       └── document_manager.py
│
├── tests/                       # Test suite
│   ├── __init__.py
│   ├── test_api_compatibility.py
│   ├── test_deployment_safety.py
│   └── test_performance_improvements.py
│
├── docs/                        # Documentation
│   ├── API_COMPARISON_ANALYSIS.md
│   ├── API_ENHANCEMENT_GUIDE.md
│   ├── ARCHITECTURE_OVERVIEW.md
│   ├── DASHBOARD_ENHANCEMENTS.md
│   ├── DIRECTORY_STRUCTURE.md
│   ├── EXTRACTOR_UI_README.md
│   ├── LOCAL_EXTRACTION_README.md
│   ├── NC_EXTRACTION_SUMMARY.md
│   ├── README_SERVICES.md
│   ├── SELENIUM_USAGE_GUIDE.md
│   └── TAX_EXTRACTION_GUIDE.md
│
├── supabase/                    # Supabase configuration
│   ├── migrations/              # Database migrations
│   └── README.md
│
├── config/                      # Configuration files (empty for now)
│
├── Root Level Files (Deployment & Config)
│   ├── api_public.py           # Entry point wrapper for API
│   ├── streamlit_app.py        # Entry point wrapper for dashboard
│   ├── requirements.txt
│   ├── runtime.txt
│   ├── railway.json
│   ├── docker-compose.yml
│   ├── docker-compose.extractor.yml
│   ├── README.md               # Main project README
│   ├── CLAUDE.md               # Claude AI instructions
│   ├── DEPLOYMENT_CRITICAL.md  # Critical deployment patterns
│   ├── DEPLOYMENT_GUIDE.md     # General deployment guide
│   ├── RAILWAY_DEPLOYMENT.md   # Railway-specific deployment
│   └── PROJECT_STRUCTURE.md    # This file
│
└── Other Files
    ├── .git/
    ├── .gitignore
    ├── .streamlit/
    ├── .devcontainer/
    └── __pycache__/
```

## Module Organization

### 1. Extractors (`src/extractors/`)
All tax extraction logic organized by extraction method:
- **Cloud-based**: `cloud_extractor.py`, `cloud_extractor_enhanced.py`
- **Browser-based**: `selenium_tax_extractors.py`, `selenium_tax_extractor.py`
- **Specialized**: `nc_property_extractors.py`, `MASTER_TAX_EXTRACTOR.py`
- **Core Engine**: `robust_tax_extractor.py`
- **Utilities**: `local_extraction_suite.py`, `process_with_selenium.py`

### 2. API Services (`src/api/`)
FastAPI application and related services:
- **Main API**: `api_public.py` - Production API with optimized queries
- **UI Service**: `extractor_ui_service.py` - UI-related extraction service
- **Task Queue**: `celery_queue.py` - Asynchronous task processing

### 3. Dashboard (`src/dashboard/`)
Streamlit-based web interface:
- **Main App**: `streamlit_app.py` - Production dashboard
- **Utilities**: `streamlit_utils.py` - Dashboard helper functions
- **Document Manager**: `streamlit_document_manager.py` - Document handling UI

### 4. Database (`src/database/`)
Supabase integration layer:
- **Client**: `supabase_client.py` - Database operations
- **Auth**: `supabase_auth.py` - Authentication management
- **Migration**: `migrate_to_optimized_api.py` - Database optimization scripts

### 5. Utilities (`src/utils/`)
Shared functionality across modules:
- **Configuration**: `config.py` - System configuration
- **Error Handling**: `error_handling.py` - Exception classes and retry logic
- **Validation**: `data_validation.py` - Data validation and normalization
- **Documents**: `document_manager.py` - Document storage service

## Import Conventions

### For modules within src/
Use relative imports when importing from the same package:
```python
from .module_name import function_name
```

### For cross-package imports within src/
Use absolute imports from src:
```python
from src.extractors.cloud_extractor import cloud_extractor
from src.utils.config import get_config
from src.database.supabase_client import SupabaseClient
```

### Entry Point Files
Root-level entry points (`api_public.py`, `streamlit_app.py`) add src to path:
```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from src.api.api_public import *
```

## Deployment Considerations

### Production Files
The following files remain at root level for deployment compatibility:
- `api_public.py` - Wrapper for Railway deployment
- `streamlit_app.py` - Wrapper for Streamlit Cloud deployment
- `requirements.txt` - Python dependencies
- `railway.json` - Railway configuration
- `runtime.txt` - Python version specification

### Critical Documentation
These files stay at root for immediate visibility:
- `README.md` - Project overview
- `CLAUDE.md` - AI assistant instructions
- `DEPLOYMENT_CRITICAL.md` - Critical deployment patterns
- `DEPLOYMENT_GUIDE.md` - General deployment guide
- `RAILWAY_DEPLOYMENT.md` - Railway-specific guide

## Benefits of This Structure

1. **Clear Separation of Concerns**: Each directory has a specific purpose
2. **Improved Maintainability**: Related files are grouped together
3. **Better Testing**: Tests are isolated in their own directory
4. **Documentation Organization**: All docs in one place (except critical ones)
5. **Deployment Compatibility**: Root-level wrappers maintain deployment paths
6. **Scalability**: Easy to add new modules or services
7. **Import Clarity**: Clear import paths reduce confusion

## Migration Notes

### Files Moved
- All Python modules moved to appropriate subdirectories under `src/`
- Tests moved to `tests/`
- Most documentation moved to `docs/`
- Configuration and deployment files remain at root

### Import Updates
- All imports updated to use new structure
- Entry point wrappers created for backward compatibility
- Package __init__ files created for clean imports

### Testing
Run `python verify_structure.py` to validate the new structure and imports.