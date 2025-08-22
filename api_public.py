"""
Public API for Tax Extraction Service - No Authentication Required.
Simplified version for dashboard access.
"""

import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Create FastAPI app
app = FastAPI(
    title="Tax Extraction Public API",
    version="1.0.0",
    description="Public endpoints for property tax data"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========================= Models =========================

class HealthResponse(BaseModel):
    status: str
    database: str
    timestamp: str

class PropertyResponse(BaseModel):
    property_id: str
    property_name: str
    property_address: Optional[str]
    jurisdiction: Optional[str]
    state: Optional[str]
    entity_id: Optional[str]

class StatisticsResponse(BaseModel):
    total_properties: int
    total_entities: int
    total_outstanding_tax: float
    total_previous_year_tax: float
    extraction_success_rate: float
    last_extraction_date: Optional[str]

# ========================= Endpoints =========================

@app.get("/health")
async def health_check():
    """Check API and database health."""
    error_detail = None
    try:
        # Test database connection
        result = supabase.table("properties").select("property_id").limit(1).execute()
        db_status = "connected" if result else "disconnected"
        status = "healthy" if db_status == "connected" else "unhealthy"
    except Exception as e:
        db_status = "error"
        status = "unhealthy"
        error_detail = str(e)
    
    response = {
        "status": status,
        "database": db_status,
        "timestamp": datetime.now().isoformat()
    }
    
    # Add error detail if present
    if error_detail:
        response["error"] = error_detail
        
    # Add debug info
    response["debug"] = {
        "supabase_url_configured": bool(SUPABASE_URL),
        "supabase_key_configured": bool(SUPABASE_KEY),
        "supabase_url": SUPABASE_URL[:30] + "..." if SUPABASE_URL else None,
        "key_length": len(SUPABASE_KEY) if SUPABASE_KEY else 0
    }
    
    return response

@app.get("/api/v1/properties")
async def get_properties(
    limit: int = 100,
    offset: int = 0,
    jurisdiction: Optional[str] = None,
    state: Optional[str] = None
):
    """Get list of properties."""
    try:
        query = supabase.table("properties").select("*")
        
        if jurisdiction:
            query = query.eq("jurisdiction", jurisdiction)
        if state:
            query = query.eq("state", state)
        
        query = query.limit(limit).offset(offset)
        result = query.execute()
        
        return {
            "properties": result.data,
            "count": len(result.data),
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/entities")
async def get_entities(limit: int = 100, offset: int = 0):
    """Get list of entities."""
    try:
        result = supabase.table("entities").select("*").limit(limit).offset(offset).execute()
        
        return {
            "entities": result.data,
            "count": len(result.data),
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/statistics", response_model=StatisticsResponse)
async def get_statistics():
    """Get system statistics."""
    try:
        # Get counts
        properties = supabase.table("properties").select("property_id", count="exact").execute()
        entities = supabase.table("entities").select("entity_id", count="exact").execute()
        
        # Get tax amounts from extractions
        extractions = supabase.table("tax_extractions").select("tax_amount, status, extraction_date").execute()
        
        total_outstanding = 0
        total_previous = 0
        successful = 0
        total_extractions = len(extractions.data) if extractions.data else 0
        last_date = None
        
        if extractions.data:
            for ext in extractions.data:
                if ext.get("tax_amount"):
                    total_outstanding += float(ext["tax_amount"])
                if ext.get("status") == "completed":
                    successful += 1
                if ext.get("extraction_date"):
                    last_date = ext["extraction_date"]
        
        success_rate = (successful / total_extractions * 100) if total_extractions > 0 else 0
        
        return StatisticsResponse(
            total_properties=properties.count or 0,
            total_entities=entities.count or 0,
            total_outstanding_tax=total_outstanding,
            total_previous_year_tax=total_previous,
            extraction_success_rate=success_rate,
            last_extraction_date=last_date
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/extractions")
async def get_extractions(
    limit: int = 100,
    offset: int = 0,
    property_id: Optional[str] = None,
    status: Optional[str] = None
):
    """Get extraction history."""
    try:
        query = supabase.table("tax_extractions").select("*")
        
        if property_id:
            query = query.eq("property_id", property_id)
        if status:
            query = query.eq("status", status)
        
        query = query.order("extraction_date", desc=True).limit(limit).offset(offset)
        result = query.execute()
        
        return {
            "extractions": result.data,
            "count": len(result.data),
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)