"""
Minimal API for Railway deployment - No database dependency at startup.
This ensures the service can start even if environment variables aren't immediately available.
"""

import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Tax Extraction API - Minimal",
    version="1.0.0",
    description="Minimal API for Railway deployment"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Tax Extraction API",
        "status": "running",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint - always returns healthy for Railway."""
    return {
        "status": "healthy",
        "service": "tax-extraction-api",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": {
            "SUPABASE_URL": "configured" if os.getenv("SUPABASE_URL") else "not_configured",
            "SUPABASE_KEY": "configured" if os.getenv("SUPABASE_KEY") else "not_configured",
            "PORT": os.getenv("PORT", "not_set")
        }
    }

@app.get("/api/v1/properties")
async def get_properties(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get properties - returns empty list if database not configured."""
    
    # Try to import and use Supabase if available
    try:
        from supabase import create_client
        
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        
        if url and key:
            client = create_client(url, key)
            response = client.table("properties").select("*").range(offset, offset + limit - 1).execute()
            
            return {
                "properties": response.data,
                "total": len(response.data),
                "limit": limit,
                "offset": offset
            }
    except Exception as e:
        logger.error(f"Database error: {e}")
    
    # Return empty response if database not available
    return {
        "properties": [],
        "total": 0,
        "limit": limit,
        "offset": offset,
        "message": "Database not configured or temporarily unavailable"
    }

@app.get("/api/v1/entities")
async def get_entities(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get entities - returns empty list if database not configured."""
    
    # Try to import and use Supabase if available
    try:
        from supabase import create_client
        
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        
        if url and key:
            client = create_client(url, key)
            response = client.table("entities").select("*").range(offset, offset + limit - 1).execute()
            
            return {
                "entities": response.data,
                "total": len(response.data),
                "limit": limit,
                "offset": offset
            }
    except Exception as e:
        logger.error(f"Database error: {e}")
    
    # Return empty response if database not available
    return {
        "entities": [],
        "total": 0,
        "limit": limit,
        "offset": offset,
        "message": "Database not configured or temporarily unavailable"
    }

@app.get("/api/v1/statistics")
async def get_statistics():
    """Get statistics - returns zeros if database not configured."""
    
    stats = {
        "total_properties": 0,
        "total_entities": 0,
        "total_tax_current": 0,
        "total_tax_previous": 0,
        "properties_with_extractions": 0,
        "extraction_success_rate": 0,
        "last_extraction": None,
        "database_status": "unknown"
    }
    
    # Try to get real stats if database available
    try:
        from supabase import create_client
        
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        
        if url and key:
            client = create_client(url, key)
            
            # Get counts
            props = client.table("properties").select("*", count="exact").execute()
            ents = client.table("entities").select("*", count="exact").execute()
            
            stats["total_properties"] = len(props.data) if props.data else 0
            stats["total_entities"] = len(ents.data) if ents.data else 0
            stats["database_status"] = "connected"
            
            # Calculate tax totals from properties
            if props.data:
                stats["total_tax_current"] = sum(p.get("amount_due", 0) or 0 for p in props.data)
                stats["total_tax_previous"] = sum(p.get("previous_year_taxes", 0) or 0 for p in props.data)
                
    except Exception as e:
        logger.error(f"Statistics error: {e}")
        stats["database_status"] = "error"
        stats["error"] = str(e)[:100]
    
    return stats

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)