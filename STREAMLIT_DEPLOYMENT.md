# 🎯 Streamlit Dashboard Deployment Guide

## Option 1: Deploy to Streamlit Cloud (FREE & EASIEST)

### Prerequisites
- GitHub account (you have this ✓)
- Your repo is public or you have Streamlit Cloud access

### Step-by-Step Deployment

#### 1. Go to Streamlit Cloud
Visit: https://share.streamlit.io/

#### 2. Sign In
- Click "Sign in with GitHub"
- Authorize Streamlit

#### 3. Deploy New App
- Click "New app"
- Select your repository: `kwoody20/tax-extraction-system`
- Branch: `main`
- Main file path: `dashboard_supabase.py`

#### 4. Advanced Settings (IMPORTANT!)
Before deploying, click "Advanced settings" and add these secrets:

```toml
SUPABASE_URL = "https://klscgjbachumeojhxyno.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtsc2NnamJhY2h1bWVvamh4eW5vIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU3OTU1OTksImV4cCI6MjA3MTM3MTU5OX0.nJF44C6SPe-dNfPit7zTsij2foo67WNY3PFl7lfxquY"
API_URL = "https://web-production-45338.up.railway.app"
```

#### 5. Deploy
Click "Deploy!" and wait 2-3 minutes

### Your Dashboard URL
Once deployed, you'll get a URL like:
`https://your-app-name.streamlit.app`

---

## Option 2: Deploy to Railway (Same Platform as API)

### Add to Existing Project
```bash
# In Railway dashboard
1. Go to your project
2. New Service → GitHub Repo
3. Select same repo
4. Set start command:
   streamlit run dashboard_supabase.py --server.port $PORT --server.address 0.0.0.0
5. Add environment variables (same as above)
```

---

## Option 3: Local Testing First

### Test Locally with Production API
```bash
# Set environment variable to use production API
export API_URL="https://web-production-45338.up.railway.app"

# Run dashboard
streamlit run dashboard_supabase.py

# Open browser to http://localhost:8502
```

---

## What the Dashboard Provides

### Connected Features
- ✅ **Live Data** from your Railway API
- ✅ **Real-time Statistics** from Supabase
- ✅ **Entity Hierarchy** visualization
- ✅ **Property Management** interface
- ✅ **Tax Extraction Jobs** (create and monitor)
- ✅ **Outstanding Balance** tracking

### Pages Available
1. **Overview** - Metrics and outstanding properties
2. **Entities** - Hierarchy visualization and management
3. **Properties** - Full property table with filters
4. **Jobs** - Tax extraction job creation and monitoring
5. **Analytics** - Charts and insights
6. **Settings** - Configuration options

---

## Post-Deployment Checklist

### 1. Verify Connection
- Dashboard loads without errors
- Shows correct property count (102)
- Shows correct entity count (43)
- Health check shows "connected"

### 2. Test Features
- [ ] Login works (use demo mode if needed)
- [ ] Properties load correctly
- [ ] Entity hierarchy displays
- [ ] Can create extraction jobs
- [ ] Analytics charts render

### 3. Share Your Dashboard
Your dashboard URL can be shared with team members!

---

## Troubleshooting

### "Cannot connect to API"
- Check API_URL in secrets
- Ensure Railway API is running

### "No data showing"
- Check SUPABASE_URL and SUPABASE_KEY
- Verify Supabase connection

### "Login issues"
- Use Demo Mode for testing
- Or set up proper auth users in Supabase

---

## Environment Variables Summary

For any deployment platform, you need:
```env
SUPABASE_URL=https://klscgjbachumeojhxyno.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
API_URL=https://web-production-45338.up.railway.app
```

---

## 🎉 Ready to Deploy!

Your dashboard is configured to connect to:
- **Production API**: https://web-production-45338.up.railway.app
- **Supabase Database**: With 102 properties and 43 entities
- **Real-time Updates**: Live data from your production system

Deploy to Streamlit Cloud for the easiest, free hosting!