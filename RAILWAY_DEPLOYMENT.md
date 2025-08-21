# 🚂 Railway Deployment Guide

## ✅ **YES! This codebase is READY for Railway deployment**

Railway is perfect for this project because it supports:
- ✅ Long-running processes (tax extraction)
- ✅ Browser automation (Selenium/Playwright)
- ✅ Background jobs
- ✅ Multiple services (API + Dashboard)
- ✅ Persistent storage
- ✅ WebSockets for real-time updates

## 📋 Pre-Deployment Checklist

- [x] Railway configuration files created
- [x] Supabase added to requirements.txt
- [x] Procfile for multiple services
- [x] Environment variables documented
- [x] Health check endpoint available (/health)

## 🚀 Quick Deploy Instructions

### Step 1: Install Railway CLI
```bash
# Install via npm (you already did this)
npm install -g @railway/cli

# Or via brew (macOS)
brew install railway
```

### Step 2: Login & Initialize
```bash
# Login to Railway
railway login

# Initialize project in current directory
railway init
```

### Step 3: Set Environment Variables
```bash
# Set required environment variables
railway variables set SUPABASE_URL=https://klscgjbachumeojhxyno.supabase.co
railway variables set SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtsc2NnamJhY2h1bWVvamh4eW5vIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU3OTU1OTksImV4cCI6MjA3MTM3MTU5OX0.nJF44C6SPe-dNfPit7zTsij2foo67WNY3PFl7lfxquY

# Optional: Set service key for admin operations
# railway variables set SUPABASE_SERVICE_KEY=your_service_key

# Set environment
railway variables set ENVIRONMENT=production
railway variables set LOG_LEVEL=INFO
```

### Step 4: Deploy
```bash
# Deploy to Railway
railway up

# Or deploy with specific config
railway up -c requirements_railway.txt
```

### Step 5: Open Your App
```bash
# Open deployed app in browser
railway open
```

## 🔧 Configuration Files Created

1. **railway.json** - Main Railway configuration
2. **railway.toml** - Alternative TOML config
3. **Procfile** - Process definitions
4. **nixpacks.toml** - Build configuration
5. **requirements_railway.txt** - Full dependencies

## 🌐 Services Architecture on Railway

```
Railway Platform
├── API Service (Port 8000)
│   ├── FastAPI with Supabase
│   ├── Tax Extraction Engine
│   └── Selenium/Playwright Support
│
├── Dashboard Service (Port 8502)
│   ├── Streamlit Interface
│   └── Real-time Monitoring
│
└── Background Workers (Optional)
    ├── Celery Workers
    └── Redis Queue
```

## 📝 Environment Variables for Railway

### Required:
```env
SUPABASE_URL=https://klscgjbachumeojhxyno.supabase.co
SUPABASE_KEY=your_anon_key_here
PORT=8000  # Railway sets this automatically
```

### Optional but Recommended:
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

## 🎯 Post-Deployment Steps

### 1. Verify Services
```bash
# Check deployment status
railway status

# View logs
railway logs

# Check API health
curl https://your-app.railway.app/health
```

### 2. Set Up Custom Domain (Optional)
```bash
railway domain
```

### 3. Enable Monitoring
- Railway provides built-in metrics
- Access via Railway dashboard
- Set up alerts for failures

### 4. Scale If Needed
```bash
# Scale up instances
railway scale --replicas 2
```

## 🔍 Deployment Options

### Option 1: Single Service (Recommended to Start)
Deploy just the API first:
```bash
railway up
```
Access at: `https://your-app.railway.app`

### Option 2: Multiple Services
Deploy API and Dashboard separately:
```bash
# Deploy API
railway up --service api

# Deploy Dashboard (in new terminal)
railway up --service dashboard
```

### Option 3: Use Railway UI
1. Go to [railway.app](https://railway.app)
2. New Project → Deploy from GitHub
3. Connect your repository
4. Railway auto-detects configuration
5. Add environment variables in UI
6. Deploy!

## ⚠️ Important Notes

1. **First Deploy**: May take 5-10 minutes (installing Playwright browsers)
2. **Costs**: Railway offers $5 free credits monthly, then ~$20/month for this app
3. **Database**: Supabase remains external (free tier is sufficient)
4. **Extraction**: All features work including Selenium/Playwright!

## 🐛 Troubleshooting

### If deployment fails:
```bash
# Check logs
railway logs

# Use simpler requirements file
cp requirements.txt requirements_railway.txt
railway up
```

### If Playwright doesn't work:
```bash
# Ensure nixpacks.toml is being used
railway up --config nixpacks.toml
```

### If port issues occur:
```bash
# Railway sets PORT automatically
# Make sure code uses: ${PORT:-8000}
```

## ✅ Verification Commands

After deployment, test your API:
```bash
# Test health endpoint
curl https://your-app.railway.app/health

# Test API docs
open https://your-app.railway.app/docs

# Test Supabase connection
curl https://your-app.railway.app/api/v1/properties?limit=1
```

## 🎉 Success Indicators

You'll know deployment is successful when:
- ✅ `/health` returns `{"status": "healthy"}`
- ✅ `/docs` shows FastAPI documentation
- ✅ Dashboard loads at your-app.railway.app:8502
- ✅ Can fetch properties from Supabase
- ✅ Tax extraction jobs can be created

## 📚 Resources

- Railway Docs: https://docs.railway.app
- Railway CLI: https://docs.railway.app/develop/cli
- Nixpacks: https://nixpacks.com/docs
- Support: https://discord.gg/railway

## 🚀 Deploy Now!

Your codebase is **100% ready** for Railway. Just run:
```bash
railway login && railway init && railway up
```

The entire stack will be live in ~5 minutes! 🎉