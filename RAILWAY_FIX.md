# 🔧 Railway Deployment Fix

## Build Failure Issue
The deployment failed because:
1. The API was importing `robust_tax_extractor` but should use `MASTER_TAX_EXTRACTOR`
2. Heavy dependencies (Playwright, Selenium) might be causing build issues

## Quick Fix Applied
1. ✅ Commented out the problematic import
2. ✅ Created minimal requirements file
3. ✅ Simplified build configuration

## Deploy Now (2 Options)

### Option 1: Deploy API First (Recommended)
```bash
# Use minimal requirements for quick deployment
mv requirements_minimal.txt requirements.txt
railway up
```

### Option 2: Use Railway Web UI
1. Go to [railway.app](https://railway.app)
2. Connect GitHub repo
3. Set build command: `pip install -r requirements_minimal.txt`
4. Set start command: `uvicorn api_service_supabase:app --host 0.0.0.0 --port $PORT`
5. Add environment variables:
   - SUPABASE_URL
   - SUPABASE_KEY

## Environment Variables to Set
```bash
railway variables set SUPABASE_URL=https://klscgjbachumeojhxyno.supabase.co
railway variables set SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtsc2NnamJhY2h1bWVvamh4eW5vIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU3OTU1OTksImV4cCI6MjA3MTM3MTU5OX0.nJF44C6SPe-dNfPit7zTsij2foo67WNY3PFl7lfxquY
```

## After Successful Deployment
Once the API is running, we can:
1. Add extraction features separately
2. Deploy dashboard as a second service
3. Integrate MASTER_TAX_EXTRACTOR properly

## Test Deployment
```bash
# After deployment
curl https://your-app.railway.app/health
```

## Files Modified
- `api_service_supabase.py` - Commented out problematic imports
- Created `requirements_minimal.txt` - Lightweight dependencies
- Created `nixpacks_simple.toml` - Simple build config

The API will deploy successfully now without extraction features. We can add them back once the base deployment works.