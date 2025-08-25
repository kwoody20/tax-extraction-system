# 🚀 Deployment Guide

## Current Production Status

### ✅ LIVE Production Deployment
- **🌐 Live API**: https://tax-extraction-system-production.up.railway.app/
- **📊 Live Dashboard**: Deployed on Streamlit Cloud  
- **📚 API Docs**: https://tax-extraction-system-production.up.railway.app/docs
- **🏗️ Platform**: Railway (API) + Streamlit Cloud (Dashboard)
- **📦 Repository**: https://github.com/kwoody20/tax-extraction-system
- **🔄 Extraction**: Cloud-ready with 8 supported jurisdictions
- **💾 Database**: Supabase PostgreSQL with 102 properties, 43 entities

### 🎉 What's Been Achieved
- ✅ Production API deployed on Railway
- ✅ Connected to Supabase database  
- ✅ 102 properties loaded (95 with account numbers)
- ✅ 43 entities configured
- ✅ Real-time dashboard with 5 tabs
- ✅ Geographic distribution visualization
- ✅ $50,058.52 in outstanding taxes tracked
- ✅ $434,291.55 in previous year taxes
- ✅ Automatic deploys from GitHub
- ✅ Scalable architecture

## Architecture Overview

### Current Deployment Stack
```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│    Railway      │────▶│    Supabase      │◀────│   Streamlit     │
│   (Main API)    │     │   (Database)     │     │     Cloud       │
│ Cloud Extraction│     └──────────────────┘     │   (Dashboard)   │
└─────────────────┘                              └─────────────────┘
```

### Services Deployed
1. **Database (Supabase)**: PostgreSQL with RLS policies
2. **API (Railway)**: FastAPI with cloud extraction support
3. **Dashboard (Streamlit Cloud)**: Real-time monitoring interface

## 🚂 Railway Deployment (Recommended Platform)

Railway is perfect because it supports:
- ✅ Long-running processes (tax extraction)
- ✅ Browser automation (Selenium/Playwright for local)
- ✅ Background jobs
- ✅ Multiple services
- ✅ Persistent storage
- ✅ WebSockets for real-time updates

### Quick Deploy to Railway

#### Prerequisites
```bash
# Install Railway CLI
npm install -g @railway/cli
# Or via brew (macOS)
brew install railway
```

#### Deploy Steps
```bash
# 1. Login & Initialize
railway login
railway init

# 2. Set Environment Variables
railway variables set SUPABASE_URL=https://klscgjbachumeojhxyno.supabase.co
railway variables set SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtsc2NnamJhY2h1bWVvamh4eW5vIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU3OTU1OTksImV4cCI6MjA3MTM3MTU5OX0.nJF44C6SPe-dNfPit7zTsij2foo67WNY3PFl7lfxquY

# 3. Deploy
railway up

# 4. Open deployed app
railway open
```

### Alternative: Railway Web UI
1. Go to [railway.app](https://railway.app)
2. New Project → Deploy from GitHub
3. Connect repository
4. Add environment variables in UI
5. Deploy!

### Post-Deployment Verification
```bash
# Check deployment status
railway status

# View logs
railway logs

# Test health endpoint
curl https://your-app.railway.app/health

# Test API docs
open https://your-app.railway.app/docs

# Test Supabase connection
curl https://your-app.railway.app/api/v1/properties?limit=1
```

## 📊 Dashboard Deployment (Streamlit Cloud)

### Deploy Steps
1. Push code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect GitHub repo
4. Deploy `streamlit_app.py` or `dashboard_supabase.py`
5. Add secrets in Streamlit Cloud:
   ```toml
   SUPABASE_URL = "https://klscgjbachumeojhxyno.supabase.co"
   SUPABASE_KEY = "your_key"
   API_URL = "https://tax-extraction-system-production.up.railway.app"
   ```

## 🔑 Environment Variables

### Required for API (Railway)
```env
SUPABASE_URL=https://klscgjbachumeojhxyno.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
PORT=8000  # Railway sets automatically
```

### Optional but Recommended
```env
SUPABASE_SERVICE_KEY=your_service_key
ENVIRONMENT=production
LOG_LEVEL=INFO
HEADLESS_BROWSER=true
MAX_WORKERS=4
TIMEOUT_SECONDS=60
ENABLE_CORS=true
CORS_ORIGINS=*
```

### For Dashboard (Streamlit)
```env
SUPABASE_URL=https://klscgjbachumeojhxyno.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
API_URL=https://tax-extraction-system-production.up.railway.app
```

## 📝 Available API Endpoints

### Core Endpoints (LIVE)
1. **Health Check**: `/health`
2. **API Documentation**: `/docs` and `/redoc`
3. **Properties**: 
   - GET `/api/v1/properties` - List all properties
   - GET `/api/v1/properties/{property_id}` - Get specific property
4. **Entities**:
   - GET `/api/v1/entities` - List all entities (43 total)
   - GET `/api/v1/entities/{entity_id}` - Get specific entity
5. **Statistics**: GET `/api/v1/statistics` - Tax statistics overview
6. **Extraction**:
   - POST `/api/v1/extract` - Extract single property
   - POST `/api/v1/extract/batch` - Batch extraction
   - GET `/api/v1/extract/status` - Check extraction status
7. **Jurisdictions**: GET `/api/v1/jurisdictions` - Supported jurisdictions

## ⚠️ Platform Limitations

### Railway (Current Platform)
- ✅ Full API features
- ✅ Database operations
- ✅ Cloud extraction (HTTP-based)
- ⚠️ Limited browser automation (Selenium/Playwright need special setup)
- ✅ Background jobs supported
- ✅ Long-running processes OK

### Alternative Platforms

#### For Serverless (Vercel/Netlify)
**NOT RECOMMENDED** for this project because:
- ❌ No browser automation
- ❌ 10-30 second timeout limits
- ❌ No background jobs
- ✅ Only basic CRUD operations

#### For Full Features (Render/Fly.io)
Similar to Railway with full support for:
- Browser automation
- Long-running jobs
- Background processing

## 🐛 Troubleshooting

### Common Issues & Fixes

#### Build Failures
```bash
# Check logs
railway logs

# Try minimal requirements
cp requirements_minimal.txt requirements.txt
railway up
```

#### Port Issues
```bash
# Railway sets PORT automatically
# Ensure code uses: ${PORT:-8000}
```

#### Playwright/Selenium Issues
```bash
# Use nixpacks.toml configuration
railway up --config nixpacks.toml
```

#### Database Connection Issues
- Verify Supabase URL and keys
- Check RLS policies in Supabase dashboard
- Ensure service key is set for admin operations

## 🚀 Quick Start Commands

### Local Development
```bash
# Start API Service
python api_public_with_extraction.py

# Start Dashboard (new terminal)
streamlit run streamlit_app.py

# Access Services
# API: http://localhost:8000/docs
# Dashboard: http://localhost:8501
```

### Production Testing
```bash
# Test production API
curl https://tax-extraction-system-production.up.railway.app/health

# Get first 5 properties
curl https://tax-extraction-system-production.up.railway.app/api/v1/properties?limit=5

# Get statistics
curl https://tax-extraction-system-production.up.railway.app/api/v1/statistics
```

## 📚 Resources & Documentation

- **Railway Docs**: https://docs.railway.app
- **Railway CLI**: https://docs.railway.app/develop/cli
- **Streamlit Cloud**: https://docs.streamlit.io/streamlit-cloud
- **Supabase**: https://supabase.com/docs
- **Project Dashboard**: https://railway.app/project/[your-project-id]
- **Supabase Dashboard**: https://app.supabase.com/project/klscgjbachumeojhxyno

## 🎯 Next Steps

1. **Monitor Production**: Check Railway dashboard for metrics
2. **Set Up Alerts**: Configure failure notifications
3. **Scale If Needed**: `railway scale --replicas 2`
4. **Custom Domain**: `railway domain` for custom URL
5. **Add Features**: Gradually add more extraction capabilities

## ✨ Success Indicators

Your deployment is successful when:
- ✅ `/health` returns `{"status": "healthy"}`
- ✅ `/docs` shows FastAPI documentation
- ✅ Dashboard loads with real-time data
- ✅ Can fetch properties from Supabase
- ✅ Tax extraction jobs complete successfully
- ✅ Statistics show correct tax totals

---

**Deployment Status**: ✅ PRODUCTION READY & LIVE
**Last Updated**: Current deployment running successfully with all core features