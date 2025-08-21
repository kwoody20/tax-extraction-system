# 🚂 Railway Minimal Deployment (Immediate Fix)

## Problem: Build failing immediately
Railway can't build because of complex dependencies. Let's fix it step by step.

## Step 1: Test with Minimal App First

### In Railway Dashboard:
1. Go to your project settings
2. **Change the start command to**: 
   ```
   python -m uvicorn test_app:app --host 0.0.0.0 --port $PORT
   ```
3. **Trigger redeploy**

This will test if basic Python/FastAPI works.

## Step 2: If Test App Works, Use Minimal Requirements

### Option A: Via GitHub (Recommended)
```bash
# Replace requirements.txt with minimal version
cp requirements_basic.txt requirements.txt

# Commit and push
git add .
git commit -m "Use minimal requirements for Railway"
git push
```

### Option B: Via Railway Dashboard
1. Go to Settings
2. Set **Build Command**: 
   ```
   pip install fastapi uvicorn supabase python-dotenv pandas
   ```
3. Keep **Start Command**:
   ```
   python -m uvicorn api_service_supabase:app --host 0.0.0.0 --port $PORT
   ```

## Step 3: Gradual Feature Addition
Once basic deployment works, gradually add features:

1. **First Deploy**: Basic API (no extraction)
2. **Second Deploy**: Add more dependencies
3. **Third Deploy**: Add extraction features (may need different platform)

## 🔧 Current Files Setup:
- `requirements_basic.txt` - Minimal deps (10 packages)
- `test_app.py` - Simple test API
- `railway.json` - Minimal config

## 🎯 Quick Fix Commands:
```bash
# Use this exact sequence:
cp requirements_basic.txt requirements.txt
rm -f nixpacks.toml railway.toml
git add .
git commit -m "Minimal Railway setup"
git push
```

## ✅ If Still Failing:
The absolute minimal test:
```bash
# Create super minimal requirements
echo "fastapi==0.104.1
uvicorn==0.24.0
supabase==2.15.1" > requirements.txt

# Push
git add requirements.txt
git commit -m "Ultra minimal requirements"
git push
```

## 📝 Railway Dashboard Settings:
- **Build Command**: (leave empty)
- **Start Command**: `python -m uvicorn api_service_supabase:app --host 0.0.0.0 --port $PORT`
- **Watch Paths**: (leave default)
- **Root Directory**: `/`

## 🚨 Common Issues:
1. **"pip not found"** → Railway isn't detecting Python
2. **"Module not found"** → Requirements not installing
3. **"Port binding"** → Use `$PORT` not hardcoded

## Alternative Platform:
If Railway continues to fail, consider:
- **Render.com** - Better Python support
- **Fly.io** - More control
- **DigitalOcean App Platform** - Simple setup

The key is starting with the absolute minimum and building up!