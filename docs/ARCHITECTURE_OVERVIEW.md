# Tax Extraction System - Architecture Overview

## 🏗️ Current Production Architecture

### Live System Components

```mermaid
graph TB
    A[Streamlit Dashboard] -->|API Calls| B[Railway API]
    B -->|Database Queries| C[Supabase PostgreSQL]
    D[GitHub Repository] -->|Auto Deploy| A
    D -->|Auto Deploy| B
    
    subgraph "Production Branch"
        B
    end
    
    subgraph "Main Branch"
        A
    end
```

### Production URLs
- **Dashboard**: Streamlit Cloud (from `main` branch)
- **API**: https://tax-extraction-system-production.up.railway.app (from `production` branch)
- **Database**: https://klscgjbachumeojhxyno.supabase.co

---

## 📁 File Architecture - What's Actually Being Used

### ✅ **ACTIVE FILES IN PRODUCTION**

#### API Files (Railway Deployment)
- **`api_public.py`** ✅ **[CURRENTLY DEPLOYED]**
  - Public API without authentication
  - Simple, direct Supabase queries
  - Read-only endpoints for dashboard
  - Deployed on Railway via `production` branch

#### Dashboard Files (Streamlit Cloud)
- **`streamlit_app.py`** ✅ **[CURRENTLY DEPLOYED]**
  - Simplified dashboard for Streamlit Cloud
  - No local module dependencies
  - Direct API calls to Railway
  - Uses Streamlit secrets for configuration

#### Configuration Files
- **`railway.json`** - Railway deployment configuration
- **`requirements.txt`** - Streamlit dependencies (minimal)
- **`requirements-railway.txt`** - Railway/API dependencies (full)
- **`.streamlit/config.toml`** - Streamlit configuration

---

### ❓ **CURRENTLY UNUSED FILES** (Might Actually Work Now!)

#### API Files (Not Currently Used - But Probably Work!)
- **`api_service_supabase.py`** ❓
  - Full-featured API with authentication
  - **Probably works fine now with correct keys**
  - Has protected endpoints (dashboard would need auth tokens)

- **`api_with_auth.py`** ❓
  - Enhanced authentication features
  - JWT token management
  - **Likely works, just needs auth headers from dashboard**

- **`api_service_enhanced.py`** ❓
  - Advanced features (webhooks, background jobs)
  - Requires Redis, Celery (actually complex)
  - But database parts probably work fine

- **`api_service.py`** ❌
  - Original API without Supabase
  - Used local file storage
  - Superseded by Supabase integration

#### Dashboard Files (Not Used)
- **`dashboard_supabase.py`** ❌
  - Imports local modules (`supabase_client.py`, `supabase_auth.py`)
  - Failed on Streamlit Cloud due to module dependencies
  - Too tightly coupled with local code

- **`dashboard.py`** ❌
  - Original dashboard without Supabase
  - Used local file system
  - No longer relevant

- **`dashboard_streamlit.py`** ❌
  - Intermediate attempt
  - Still had complex dependencies
  - Replaced by simpler `streamlit_app.py`

- **`app.py`** ❌
  - Testing version
  - Replaced by `streamlit_app.py`

#### Support Files (Not Deployed)
- **`supabase_client.py`** - Local development only
- **`supabase_auth.py`** - Local development only
- **All extraction files** - Run locally when needed

---

## 🚀 Deployment Strategy

### Branch Strategy
```
main branch (development)
    ├── streamlit_app.py (auto-deploys to Streamlit)
    └── All development work
    
production branch (stable)
    └── api_public.py (auto-deploys to Railway)
```

### Why This Architecture Works

1. **Separation of Concerns**
   - API and Dashboard deploy independently
   - Different branches prevent accidental deployments
   - Each service has its own requirements file

2. **Simplicity Over Features**
   - Removed authentication complexity
   - No local module dependencies
   - Direct database queries instead of complex ORMs

3. **Public Access**
   - Dashboard doesn't need auth tokens
   - API provides read-only public endpoints
   - Suitable for internal dashboards

---

## 📊 Data Flow

```
1. User → Streamlit Dashboard (streamlit_app.py)
2. Dashboard → HTTP Request → Railway API (api_public.py)
3. API → Query → Supabase Database
4. API → JSON Response → Dashboard
5. Dashboard → Display → User
```

---

## 🔧 Local Development Files (Not Deployed)

### Extraction System
- `MASTER_TAX_EXTRACTOR.py` - Main extraction engine
- `robust_tax_extractor.py` - Enhanced extraction with retry logic
- `selenium_tax_extractors.py` - Browser-based extraction
- Other extractors - Various specialized extractors

### Utilities
- `import_data_to_supabase_fixed.py` - Data import tool
- `verify_supabase_data.py` - Data verification
- `test_*.py` files - Testing utilities

---

## 🗂️ Requirements Files Chaos (Now Organized)

### Active
- `requirements.txt` - For Streamlit (4 packages only)
- `requirements-railway.txt` - For Railway API (full stack)

### Archived (in `/archive` folder)
- 9 different requirements_*.txt files
- Created confusion during deployment
- Now safely archived

---

## 💡 The REAL Lesson Learned

### The Actual Problem
**IT WAS THE SUPABASE KEY ALL ALONG!** 🤯

The Railway environment variable had:
1. Wrong format initially (had quotes in the .env file)
2. A trailing newline character (`\n`) that Railway added
3. This caused ALL database connections to fail with "Invalid API key"

### What We Thought Failed (But Might Actually Work)
1. **Complex Authentication** - Probably works fine, we just couldn't test it
2. **Local Module Imports** - Streamlit Cloud CAN handle these if files exist
3. **Feature-Rich APIs** - Would have worked with correct database credentials
4. **`api_service_supabase.py`** - Likely works perfectly with the fixed keys

### What Actually Helped
1. **Creating `api_public.py`** - Gave us a simpler file to debug with
2. **Adding debug endpoints** - Finally revealed the malformed key
3. **Checking key character by character** - Found the hidden newline
4. **Simple is easier to debug** - But complex might have worked too!

---

## 🎯 Current System Status

- ✅ **102 Properties** loaded in database
- ✅ **43 Entities** configured
- ✅ **$50,058.52** outstanding taxes tracked
- ✅ **$434,291.55** previous year taxes
- ✅ **API** fully operational
- ✅ **Dashboard** displaying real-time data
- ✅ **Auto-deployment** working on both platforms

---

## 📝 Notes for Future Development

1. **CHECK YOUR ENVIRONMENT VARIABLES FIRST!** - A single newline character caused hours of debugging
2. **The complex files might work** - We created simpler versions to debug, but the originals probably work
3. **Debug endpoints are invaluable** - Adding key inspection to `/health` found the issue
4. **Railway can modify your variables** - Watch for trailing newlines or spaces
5. **Sometimes it's not the code** - It's the configuration

### The Irony
We rewrote everything to be "simpler" when the real issue was a newline character in an environment variable. The original "complex" architecture probably worked fine. 😅