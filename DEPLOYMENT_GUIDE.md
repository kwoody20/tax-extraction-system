# 🚀 Deployment Guide

## Current Architecture Issues for Vercel

### ⚠️ **IMPORTANT: This project is NOT ready for Vercel deployment**

## Why Not Vercel?

1. **Browser Automation**: The tax extraction features use Selenium/Playwright which don't work in serverless environments
2. **Long-Running Jobs**: Tax extraction can take 30+ seconds per property (Vercel has 10-30 second limits)
3. **Streamlit Dashboard**: Requires separate deployment (not compatible with Vercel)
4. **Persistent Jobs**: Extraction jobs need background processing

## Recommended Deployment Architecture

### Option 1: Split Services (Recommended)
```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Vercel/       │────▶│    Supabase      │◀────│   Streamlit     │
│   Netlify       │     │   (Database)     │     │     Cloud       │
│   (API Only)    │     └──────────────────┘     │   (Dashboard)   │
└─────────────────┘              ▲               └─────────────────┘
                                 │
                    ┌────────────────────────┐
                    │   Railway/Render       │
                    │  (Extraction Service)  │
                    └────────────────────────┘
```

### Option 2: Single Platform
Use **Railway**, **Render**, or **Fly.io** for everything:
- Supports long-running processes
- Allows browser automation
- Can host both API and dashboard

## Deployment Steps

### 1. Database (Supabase) ✅
Already configured at: https://klscgjbachumeojhxyno.supabase.co

### 2. API Deployment (Vercel - Limited Features)

#### Prerequisites:
1. Install Vercel CLI: `npm i -g vercel`
2. Set environment variables in Vercel:
   ```
   SUPABASE_URL=https://klscgjbachumeojhxyno.supabase.co
   SUPABASE_KEY=your_anon_key
   SUPABASE_SERVICE_KEY=your_service_key
   ```

#### Deploy:
```bash
# Rename config file
mv vercel_correct.json vercel.json

# Deploy
vercel --prod
```

**Note**: This will deploy API only, NO extraction features will work.

### 3. Dashboard Deployment (Streamlit Cloud)

1. Push code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect GitHub repo
4. Deploy `dashboard_supabase.py`
5. Add secrets in Streamlit Cloud:
   ```toml
   SUPABASE_URL = "https://klscgjbachumeojhxyno.supabase.co"
   SUPABASE_KEY = "your_key"
   API_URL = "https://your-vercel-api.vercel.app"
   ```

### 4. Extraction Service (Separate Server Required)

For full extraction capabilities, deploy on:

#### Railway (Recommended)
```bash
# Install Railway CLI
npm i -g @railway/cli

# Login and initialize
railway login
railway init

# Deploy
railway up
```

#### Render
1. Create Web Service on render.com
2. Connect GitHub repo
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `python api_service_supabase.py`

## Environment Variables Required

### For API (Vercel/Railway):
```env
SUPABASE_URL=https://klscgjbachumeojhxyno.supabase.co
SUPABASE_KEY=eyJhbGc...
SUPABASE_SERVICE_KEY=eyJhbGc... (optional)
ENVIRONMENT=production
```

### For Dashboard (Streamlit):
```env
SUPABASE_URL=https://klscgjbachumeojhxyno.supabase.co
SUPABASE_KEY=eyJhbGc...
API_URL=https://your-api-url.com
```

### For Extraction Service:
All above plus:
```env
HEADLESS_BROWSER=true
MAX_WORKERS=4
TIMEOUT_SECONDS=60
```

## Current Limitations

### If deploying to Vercel:
- ❌ No Selenium/Playwright extraction
- ❌ No long-running jobs
- ❌ No background processing
- ✅ Basic CRUD operations only
- ✅ Database queries
- ✅ Authentication

### For Full Features:
Use Railway, Render, or AWS EC2/DigitalOcean Droplet

## Files to Update Before Deployment

1. **vercel.json**: Use `vercel_correct.json` content
2. **requirements.txt**: Add `supabase==2.15.1`
3. **.env**: Update with production values
4. **api_service_supabase.py**: Disable extraction endpoints for Vercel

## Quick Start Commands

```bash
# For local testing
python api_service_supabase.py  # API
streamlit run dashboard_supabase.py  # Dashboard

# For Vercel (API only, limited)
vercel --prod

# For Railway (full features)
railway up

# For Streamlit Cloud (dashboard)
# Use web interface at share.streamlit.io
```

## Recommended Next Steps

1. **Decision Required**: Choose deployment strategy
   - Limited Vercel (no extraction)
   - Full Railway/Render (all features)
   
2. **Update configurations** based on chosen platform

3. **Test locally** with production settings:
   ```bash
   export ENVIRONMENT=production
   python api_service_supabase.py
   ```

4. **Consider using** GitHub Actions for CI/CD

## Support & Documentation

- Vercel: https://vercel.com/docs
- Railway: https://docs.railway.app
- Render: https://render.com/docs
- Streamlit Cloud: https://docs.streamlit.io/streamlit-cloud
- Supabase: https://supabase.com/docs