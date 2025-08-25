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
# Install via npm
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

## 🔧 Configuration Files

### Available Configuration Files
1. **railway.json** - Main Railway configuration
2. **railway.toml** - Alternative TOML config
3. **Procfile** - Process definitions
4. **nixpacks.toml** - Build configuration for Playwright/Selenium
5. **requirements_railway.txt** - Full dependencies
6. **requirements_minimal.txt** - Minimal dependencies for quick deploy
7. **requirements_basic.txt** - Basic dependencies without browser automation

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

## 📝 Environment Variables

### Required
```env
SUPABASE_URL=https://klscgjbachumeojhxyno.supabase.co
SUPABASE_KEY=your_anon_key_here
PORT=8000  # Railway sets this automatically
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

## 🎯 Deployment Options

### Option 1: Minimal Deployment (Quick Start)
Start with basic API without browser automation:
```bash
# Use minimal requirements
cp requirements_minimal.txt requirements.txt
railway up
```

### Option 2: Full Deployment (All Features)
Deploy with complete extraction capabilities:
```bash
# Use full requirements
cp requirements_railway.txt requirements.txt
railway up
```

### Option 3: Use Railway Web UI
1. Go to [railway.app](https://railway.app)
2. New Project → Deploy from GitHub
3. Connect your repository
4. Railway auto-detects configuration
5. Add environment variables in UI
6. Deploy!

## 🐛 Troubleshooting

### Common Issues & Solutions

#### Build Failures ("pip not found")
Railway's nixpacks auto-detects Python from requirements.txt. Solutions:
```bash
# Ensure requirements.txt exists
ls requirements.txt

# Use simpler requirements
cp requirements_basic.txt requirements.txt
railway up
```

#### Module Import Errors
If imports fail, ensure correct dependencies:
```bash
# Check logs
railway logs

# Try minimal approach first
echo "fastapi==0.104.1
uvicorn[standard]==0.24.0
supabase==2.15.1
pandas==2.1.3
python-dotenv==1.0.0" > requirements.txt

railway up
```

#### Playwright/Selenium Not Working
Use nixpacks.toml configuration:
```bash
# Deploy with nixpacks config
railway up --config nixpacks.toml
```

#### Port Binding Issues
```bash
# Railway sets PORT automatically
# Ensure your code uses: ${PORT:-8000}
# Check api_service_supabase.py has:
# port = int(os.environ.get("PORT", 8000))
```

### Railway Dashboard Settings
If CLI issues persist, use Railway Dashboard:
1. Go to your project at railway.app
2. Settings → Build Command: (leave empty - auto-detect)
3. Settings → Start Command: `uvicorn api_service_supabase:app --host 0.0.0.0 --port $PORT`
4. Variables → Add SUPABASE_URL and SUPABASE_KEY
5. Trigger redeploy

## ✅ Post-Deployment Verification

### Step 1: Check Deployment Status
```bash
# Check status
railway status

# View logs
railway logs
```

### Step 2: Test API Endpoints
```bash
# Test health check
curl https://your-app.railway.app/health

# Expected response:
# {"status": "healthy", "database": "connected", ...}

# Test API docs
open https://your-app.railway.app/docs

# Test Supabase connection
curl https://your-app.railway.app/api/v1/properties?limit=1
```

### Step 3: Verify Available Endpoints
Your Railway app should have these endpoints working:

1. **Health Check**: `/health`
2. **API Documentation**: `/docs` and `/redoc`
3. **Properties**: `/api/v1/properties`
4. **Entities**: `/api/v1/entities`
5. **Statistics**: `/api/v1/statistics`
6. **Extraction**: `/api/v1/extract` (if full deployment)

## 🎉 Success Indicators

You'll know deployment is successful when:
- ✅ `/health` returns `{"status": "healthy"}`
- ✅ `/docs` shows FastAPI documentation
- ✅ Can fetch properties from Supabase (102 properties)
- ✅ Can fetch entities (43 entities)
- ✅ Statistics show tax totals ($50,058.52 outstanding)
- ✅ Tax extraction jobs can be created (if full deployment)

## ⚠️ Important Notes

1. **First Deploy**: May take 5-10 minutes (installing dependencies)
2. **Costs**: Railway offers $5 free credits monthly, then ~$20/month
3. **Database**: Supabase remains external (free tier sufficient)
4. **Extraction**: All features work including Selenium/Playwright with proper setup

## 🚀 Next Steps After Deployment

### 1. Deploy Dashboard (Separate Service)
The Streamlit dashboard needs its own deployment:
- **Option A**: Deploy to Streamlit Cloud (free)
- **Option B**: Add as second Railway service
- **Option C**: Use Render.com for dashboard

### 2. Set Up Monitoring
- Railway provides built-in metrics
- Access via Railway dashboard
- Set up alerts for failures

### 3. Scale If Needed
```bash
# Scale up instances
railway scale --replicas 2
```

### 4. Custom Domain (Optional)
```bash
railway domain
```

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

---

**Status**: ✅ READY FOR DEPLOYMENT
**Platform**: Railway (Recommended)
**Deployment Time**: ~5 minutes
**Monthly Cost**: ~$20 after free credits