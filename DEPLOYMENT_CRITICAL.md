# 🚨 CRITICAL DEPLOYMENT CONFIGURATION - DO NOT BREAK 🚨

## Last Working Deployment
- **Date**: August 31, 2025
- **Commit**: 5b2a041 (Fix Railway deployment: lazy initialize Supabase client)
- **API Endpoint**: https://tax-extraction-system-production.up.railway.app/

## ⛔ CRITICAL RULES - NEVER CHANGE THESE

### 1. Supabase Initialization (api_public.py)
```python
# ✅ CORRECT - Lazy initialization with proxy
_supabase_client: Optional[Client] = None

def get_supabase_client() -> Client:
    global _supabase_client
    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client

class SupabaseProxy:
    def __getattr__(self, name):
        return getattr(get_supabase_client(), name)

supabase = SupabaseProxy()
```

**❌ NEVER DO THIS:**
```python
# This will break Railway deployment!
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)  # Module-level initialization
```

### 2. Railway Configuration (railway.json)
```json
{
  "deploy": {
    "startCommand": "uvicorn api_public:app --host 0.0.0.0 --port ${PORT:-8000}"
  }
}
```
Alternative (Nixpacks): If the `uvicorn` CLI isn’t on PATH at runtime, it’s safe to use the venv explicitly:
```json
{
  "deploy": {
    "startCommand": "/opt/venv/bin/python -m uvicorn api_public:app --host 0.0.0.0 --port ${PORT:-8000}"
  }
}
```
**⚠️ NEVER:** 
- Change from `api_public:app` to another file
- Remove the `${PORT:-8000}` variable syntax
- Add module-level database connections

### 3. Dependencies (requirements-railway.txt)
**✅ WORKING VERSIONS:**
```
supabase==2.8.1
gotrue==2.8.1  # DO NOT UPGRADE - versions 2.9.0+ have proxy parameter bug
httpx==0.27.0
```

## ✅ SAFE IMPROVEMENTS YOU CAN MAKE

### Adding New Endpoints
```python
@app.get("/new-endpoint")
async def new_endpoint():
    # Safe to add new endpoints
    # Just ensure any database calls use the existing supabase proxy
    result = await run_in_executor(
        db_executor,
        lambda: supabase.table("table_name").select("*").execute()
    )
    return result
```

### Adding New Features
- ✅ New API endpoints
- ✅ New data processing functions
- ✅ New utility modules
- ✅ Enhanced error handling
- ✅ Additional middleware
- ✅ New Pydantic models

### Updating Dependencies
**SAFE TO UPDATE:**
- fastapi
- pandas
- beautifulsoup4
- requests
- Most other packages

**⚠️ REQUIRES TESTING:**
- supabase (currently locked at 2.8.1)
- gotrue (currently locked at 2.8.1)
- httpx (currently locked at 0.27.0)

## 🧪 TESTING CHECKLIST BEFORE DEPLOYMENT

Before pushing any changes that touch api_public.py:

1. **Local Test**:
   ```bash
   python -c "import api_public; print('Module loads OK')"
   ```

2. **Check Lazy Loading**:
   ```bash
   # This should NOT fail even without env vars
   python -c "import api_public"
   ```

3. **Verify No Module-Level DB Calls**:
   ```bash
   # Check for any create_client calls outside functions
   grep -n "create_client" api_public.py
   # Should only see it inside get_supabase_client function
   ```

4. **Test Liveness Endpoint**:
```bash
# Start locally
uvicorn api_public:app --reload
# In another terminal
curl http://localhost:8000/livez
```

## 🔒 GIT HOOKS RECOMMENDATION

Consider adding a pre-commit hook to check for dangerous patterns:

```bash
#!/bin/bash
# .git/hooks/pre-commit

# Check for module-level supabase initialization
if grep -q "^supabase = create_client" api_public.py; then
    echo "❌ ERROR: Module-level Supabase initialization detected!"
    echo "Use the SupabaseProxy pattern instead."
    exit 1
fi

# Check for direct environment variable checks at module level
if grep -q "^if not SUPABASE_URL or not SUPABASE_KEY:" api_public.py; then
    echo "⚠️  WARNING: Module-level env var check detected"
    echo "Move this inside get_supabase_client() function"
fi
```

## 📝 FOR CLAUDE AGENTS

When working with Claude agents, include this instruction:

```
CRITICAL: When modifying api_public.py:
1. NEVER initialize Supabase at module level
2. ALWAYS use the existing SupabaseProxy pattern
3. NEVER check environment variables at module import
4. Read DEPLOYMENT_CRITICAL.md before making changes
5. Platform should use a pure liveness endpoint (`/livez`) that never touches the DB; `/health` may perform readiness/DB checks but must not crash and should return JSON even when DB is unavailable
```

## 🚀 DEPLOYMENT COMMANDS

```bash
# Safe deployment sequence
git add .
git commit -m "your message"
git push origin main
# Railway auto-deploys from main branch

# Monitor deployment
# Check Railway dashboard for logs
# Verify liveness: curl https://tax-extraction-system-production.up.railway.app/livez
```

## 🆘 EMERGENCY ROLLBACK

If deployment breaks:
```bash
# Rollback to last known working commit
git revert HEAD
git push origin main

# Or reset to specific working commit
git reset --hard 5b2a041
git push --force origin main
```

## 📊 MONITORING

Always check these after deployment:
1. Liveness endpoint: `/livez` (platform health)
2. Health endpoint: `/health` (readiness/DB)
2. API docs: `/docs`
3. Railway logs for startup errors
4. Test a simple GET endpoint before database operations

---
**Last Updated**: August 31, 2025
**Maintained By**: System Administrator
**Review Frequency**: After each deployment issue
