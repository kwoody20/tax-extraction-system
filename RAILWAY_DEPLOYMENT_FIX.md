# 🔧 Railway Deployment Fix Guide

## Issue: "pip: command not found"
Railway's build was failing because pip wasn't available. This is now fixed.

## ✅ Files Fixed:
1. **Simplified nixpacks.toml** - Auto-detects Python
2. **Cleaned railway.toml** - Minimal configuration
3. **Updated Procfile** - Simple web process
4. **Removed complex railway.json** - Let Railway auto-detect

## 🚀 Deploy Now:

### Step 1: Set Environment Variables
```bash
# Use Railway CLI
railway variables set SUPABASE_URL="https://klscgjbachumeojhxyno.supabase.co"
railway variables set SUPABASE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtsc2NnamJhY2h1bWVvamh4eW5vIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU3OTU1OTksImV4cCI6MjA3MTM3MTU5OX0.nJF44C6SPe-dNfPit7zTsij2foo67WNY3PFl7lfxquY"
```

**OR** use Railway Dashboard:
1. Go to your project at railway.app
2. Click on Variables tab
3. Add:
   - `SUPABASE_URL` = `https://klscgjbachumeojhxyno.supabase.co`
   - `SUPABASE_KEY` = (the key above)

### Step 2: Deploy
```bash
# Push changes to GitHub
git add .
git commit -m "Fix Railway deployment configuration"
git push

# Railway will auto-deploy, or manually trigger:
railway up
```

## 📋 What Railway Will Do:
1. **Auto-detect Python** from requirements.txt
2. **Install Python 3.11** via nixpacks
3. **Install all dependencies** from requirements.txt
4. **Start the API** on the assigned PORT

## 🎯 Alternative: Use Railway Dashboard
If CLI issues persist:
1. Go to [railway.app](https://railway.app)
2. Your project: **earnest-reprieve**
3. Settings → Build Command: (leave empty - auto-detect)
4. Settings → Start Command: `uvicorn api_service_supabase:app --host 0.0.0.0 --port $PORT`
5. Variables → Add the two environment variables
6. Trigger redeploy

## ✅ Success Indicators:
- Build completes without "pip not found"
- Deploy logs show "Uvicorn running on http://0.0.0.0:..."
- Health check passes at your-app.railway.app/health

## 🐛 If Still Failing:
Try the minimal approach:
```bash
# Create a simple requirements.txt with only essentials
echo "fastapi==0.104.1
uvicorn[standard]==0.24.0
supabase==2.15.1
pandas==2.1.3
python-dotenv==1.0.0" > requirements.txt

# Push and deploy
git add requirements.txt
git commit -m "Use minimal requirements"
git push
```

## 📝 Notes:
- Railway uses **Nixpacks** by default (not Docker)
- Python is auto-detected from requirements.txt
- No need for complex build commands
- The simpler the config, the better

Your deployment should work now! The key was simplifying the configuration and letting Railway's auto-detection handle the Python setup.