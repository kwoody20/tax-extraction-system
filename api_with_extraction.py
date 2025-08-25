"""
Enhanced API with Tax Extraction using MASTER_TAX_EXTRACTOR.
Conservative approach with rate limiting and safety controls.
"""

import os
import sys
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv
import logging

load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Tax Extraction API with Live Extraction",
    version="2.0.0",
    description="Property tax data with extraction capabilities"
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

class ExtractionRequest(BaseModel):
    property_id: str
    jurisdiction: str
    tax_bill_link: str
    account_number: Optional[str] = None
    property_name: Optional[str] = None

class ExtractionResponse(BaseModel):
    success: bool
    property_id: str
    jurisdiction: str
    tax_amount: Optional[float] = None
    property_address: Optional[str] = None
    account_number: Optional[str] = None
    extraction_date: str
    error_message: Optional[str] = None
    extraction_method: Optional[str] = None

class ExtractionStatusResponse(BaseModel):
    total_properties: int
    extracted_count: int
    pending_count: int
    failed_count: int
    supported_jurisdictions: List[str]

# ========================= Extraction Logic =========================

# Import from MASTER_TAX_EXTRACTOR
try:
    from MASTER_TAX_EXTRACTOR import (
        PropertyTaxRecord,
        MontgomeryExtractor,
        HarrisCountyExtractor,
        MaricopaExtractor,
        WayneCountyNCExtractor,
        JohnstonCountyNCExtractor,
        CravenCountyNCExtractor,
        WilsonCountyNCExtractor,
        GenericExtractor
    )
    EXTRACTOR_AVAILABLE = True
except ImportError as e:
    logger.error(f"Could not import MASTER_TAX_EXTRACTOR: {e}")
    EXTRACTOR_AVAILABLE = False

# Supported jurisdictions (conservative list for safety)
SUPPORTED_JURISDICTIONS = {
    "Montgomery": MontgomeryExtractor if EXTRACTOR_AVAILABLE else None,
    "Harris": HarrisCountyExtractor if EXTRACTOR_AVAILABLE else None,
    "Maricopa": MaricopaExtractor if EXTRACTOR_AVAILABLE else None,
    "Wayne": WayneCountyNCExtractor if EXTRACTOR_AVAILABLE else None,
    "Johnston": JohnstonCountyNCExtractor if EXTRACTOR_AVAILABLE else None,
    "Craven": CravenCountyNCExtractor if EXTRACTOR_AVAILABLE else None,
    "Wilson": WilsonCountyNCExtractor if EXTRACTOR_AVAILABLE else None,
}

# Rate limiting
extraction_semaphore = asyncio.Semaphore(2)  # Max 2 concurrent extractions

async def extract_tax_data(request: ExtractionRequest) -> ExtractionResponse:
    """
    Extract tax data using MASTER_TAX_EXTRACTOR.
    Conservative approach with proper error handling.
    """
    
    if not EXTRACTOR_AVAILABLE:
        return ExtractionResponse(
            success=False,
            property_id=request.property_id,
            jurisdiction=request.jurisdiction,
            extraction_date=datetime.now().isoformat(),
            error_message="Extraction system not available"
        )
    
    # Check if jurisdiction is supported
    extractor_class = None
    for supported_name, extractor in SUPPORTED_JURISDICTIONS.items():
        if supported_name.lower() in request.jurisdiction.lower():
            extractor_class = extractor
            break
    
    if not extractor_class:
        # Try generic extractor as fallback
        extractor_class = GenericExtractor if EXTRACTOR_AVAILABLE else None
        if not extractor_class:
            return ExtractionResponse(
                success=False,
                property_id=request.property_id,
                jurisdiction=request.jurisdiction,
                extraction_date=datetime.now().isoformat(),
                error_message=f"Jurisdiction '{request.jurisdiction}' not supported"
            )
    
    # Rate limiting
    async with extraction_semaphore:
        try:
            # Create property record
            record = PropertyTaxRecord(
                property_id=request.property_id,
                property_name=request.property_name or "",
                jurisdiction=request.jurisdiction,
                state="",  # Will be determined by extractor
                property_type="property",
                close_date=None,
                amount_due=None,
                previous_year_taxes=None,
                extraction_steps="",
                acct_number=request.account_number,
                property_address=None,
                next_due_date=None,
                tax_bill_link=request.tax_bill_link,
                parent_entity=None
            )
            
            # Initialize extractor
            extractor = extractor_class()
            
            # Perform extraction (synchronously for now)
            # Note: MASTER_TAX_EXTRACTOR uses async internally
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                try:
                    result = await extractor.extract(record, page)
                    
                    # Process result
                    if result.get('success'):
                        return ExtractionResponse(
                            success=True,
                            property_id=request.property_id,
                            jurisdiction=request.jurisdiction,
                            tax_amount=result.get('tax_amount'),
                            property_address=result.get('property_address'),
                            account_number=result.get('account_number') or request.account_number,
                            extraction_date=datetime.now().isoformat(),
                            extraction_method=extractor_class.__name__
                        )
                    else:
                        return ExtractionResponse(
                            success=False,
                            property_id=request.property_id,
                            jurisdiction=request.jurisdiction,
                            extraction_date=datetime.now().isoformat(),
                            error_message=result.get('error', 'Extraction failed')
                        )
                        
                finally:
                    await browser.close()
                    
        except Exception as e:
            logger.error(f"Extraction error: {e}")
            return ExtractionResponse(
                success=False,
                property_id=request.property_id,
                jurisdiction=request.jurisdiction,
                extraction_date=datetime.now().isoformat(),
                error_message=str(e)
            )

# ========================= API Endpoints =========================

@app.get("/health")
async def health_check():
    """Check API and database health."""
    try:
        result = supabase.table("properties").select("id").limit(1).execute()
        db_status = "connected" if result else "disconnected"
        
        return {
            "status": "healthy",
            "database": db_status,
            "extractor_available": EXTRACTOR_AVAILABLE,
            "supported_jurisdictions": list(SUPPORTED_JURISDICTIONS.keys()),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/api/v1/properties")
async def get_properties(
    limit: int = Query(100, le=500),
    offset: int = 0,
    jurisdiction: Optional[str] = None,
    state: Optional[str] = None,
    needs_extraction: Optional[bool] = None
):
    """Get list of properties with optional filtering."""
    try:
        query = supabase.table("properties").select("*")
        
        if jurisdiction:
            query = query.eq("jurisdiction", jurisdiction)
        if state:
            query = query.eq("state", state)
        if needs_extraction:
            query = query.is_("amount_due", "null") if needs_extraction else query.not_.is_("amount_due", "null")
        
        query = query.range(offset, offset + limit - 1)
        result = query.execute()
        
        return {
            "properties": result.data,
            "count": len(result.data),
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/extract", response_model=ExtractionResponse)
async def extract_property_tax(request: ExtractionRequest):
    """
    Extract tax data for a single property.
    Conservative approach with rate limiting.
    """
    
    # Validate request
    if not request.tax_bill_link:
        raise HTTPException(status_code=400, detail="Tax bill link is required")
    
    # Perform extraction
    result = await extract_tax_data(request)
    
    # Store result in database if successful
    if result.success:
        try:
            # Update property with extracted data
            update_data = {
                "amount_due": result.tax_amount,
                "account_number": result.account_number,
                "property_address": result.property_address,
                "updated_at": datetime.now().isoformat()
            }
            
            # Remove None values
            update_data = {k: v for k, v in update_data.items() if v is not None}
            
            supabase.table("properties").update(update_data).eq("id", request.property_id).execute()
            
            # Also store in extractions table
            extraction_record = {
                "property_id": request.property_id,
                "tax_amount": result.tax_amount,
                "extraction_date": result.extraction_date,
                "extraction_status": "success",
                "extraction_method": result.extraction_method
            }
            supabase.table("tax_extractions").insert(extraction_record).execute()
            
        except Exception as e:
            logger.error(f"Failed to store extraction result: {e}")
    
    return result

@app.post("/api/v1/extract/batch")
async def extract_batch(
    property_ids: List[str],
    background_tasks: BackgroundTasks,
    max_items: int = Query(10, le=20)
):
    """
    Extract tax data for multiple properties (limited for safety).
    Runs in background to avoid timeout.
    """
    
    if len(property_ids) > max_items:
        raise HTTPException(
            status_code=400, 
            detail=f"Maximum {max_items} properties allowed per batch"
        )
    
    # Get properties from database
    try:
        result = supabase.table("properties").select("*").in_("id", property_ids).execute()
        properties = result.data
        
        if not properties:
            raise HTTPException(status_code=404, detail="No properties found")
        
        # Schedule background extraction
        background_tasks.add_task(process_batch_extraction, properties)
        
        return {
            "message": f"Batch extraction started for {len(properties)} properties",
            "property_ids": property_ids,
            "status": "processing"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def process_batch_extraction(properties: List[Dict]):
    """Process batch extraction in background"""
    for prop in properties:
        try:
            request = ExtractionRequest(
                property_id=prop["id"],
                jurisdiction=prop.get("jurisdiction", ""),
                tax_bill_link=prop.get("tax_bill_link", ""),
                account_number=prop.get("account_number"),
                property_name=prop.get("property_name")
            )
            
            await extract_tax_data(request)
            
            # Add delay between extractions
            await asyncio.sleep(2)
            
        except Exception as e:
            logger.error(f"Batch extraction error for property {prop['id']}: {e}")

@app.get("/api/v1/extract/status", response_model=ExtractionStatusResponse)
async def get_extraction_status():
    """Get overall extraction status and statistics."""
    try:
        # Get all properties
        all_props = supabase.table("properties").select("id, amount_due").execute()
        
        total = len(all_props.data)
        extracted = sum(1 for p in all_props.data if p.get("amount_due") is not None)
        
        return ExtractionStatusResponse(
            total_properties=total,
            extracted_count=extracted,
            pending_count=total - extracted,
            failed_count=0,  # Would need to track this separately
            supported_jurisdictions=list(SUPPORTED_JURISDICTIONS.keys())
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/jurisdictions")
async def get_jurisdictions():
    """Get list of all jurisdictions and their extraction support status."""
    try:
        result = supabase.table("properties").select("jurisdiction").execute()
        
        jurisdictions = {}
        for prop in result.data:
            jur = prop.get("jurisdiction")
            if jur:
                if jur not in jurisdictions:
                    # Check if supported
                    is_supported = any(
                        s.lower() in jur.lower() 
                        for s in SUPPORTED_JURISDICTIONS.keys()
                    )
                    jurisdictions[jur] = {
                        "name": jur,
                        "supported": is_supported,
                        "count": 0
                    }
                jurisdictions[jur]["count"] += 1
        
        return {
            "jurisdictions": list(jurisdictions.values()),
            "total": len(jurisdictions),
            "supported_count": sum(1 for j in jurisdictions.values() if j["supported"])
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========================= Existing Endpoints =========================

@app.get("/api/v1/entities")
async def get_entities():
    """Get all entities."""
    try:
        result = supabase.table("entities").select("*").execute()
        return {"entities": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/statistics")
async def get_statistics():
    """Get system statistics."""
    try:
        # Get properties
        props = supabase.table("properties").select("*").execute()
        properties = props.data
        
        # Get entities
        ents = supabase.table("entities").select("*").execute()
        entities = ents.data
        
        # Calculate statistics
        total_outstanding = sum(p.get("amount_due", 0) or 0 for p in properties)
        total_previous = sum(p.get("previous_year_taxes", 0) or 0 for p in properties)
        
        extracted_count = sum(1 for p in properties if p.get("amount_due") is not None)
        success_rate = (extracted_count / len(properties) * 100) if properties else 0
        
        return {
            "total_properties": len(properties),
            "total_entities": len(entities),
            "total_outstanding_tax": total_outstanding,
            "total_previous_year_tax": total_previous,
            "extraction_success_rate": success_rate,
            "extracted_count": extracted_count,
            "pending_count": len(properties) - extracted_count
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)