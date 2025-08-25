"""
Public API for Tax Extraction Service with Cloud-Compatible Extraction.
Works entirely in the cloud - no local dependencies needed.
"""

import os
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv
import logging

# Import cloud extractor
from cloud_extractor import extract_tax_cloud, cloud_extractor

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
    title="Tax Extraction Public API with Cloud Extraction",
    version="2.0.0",
    description="Public endpoints for property tax data with cloud extraction"
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
    extraction_available: bool = True
    supported_jurisdictions: List[str] = []

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
    extracted_count: int = 0
    pending_count: int = 0

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
    extraction_method: Optional[str] = "HTTP"
    confidence: Optional[str] = None

class BatchExtractionRequest(BaseModel):
    property_ids: List[str]

class ExtractionStatusResponse(BaseModel):
    total_properties: int
    extracted_count: int
    pending_count: int
    failed_count: int
    supported_jurisdictions: List[str]

# ========================= Extraction Logic =========================

# Rate limiting for cloud
extraction_semaphore = asyncio.Semaphore(3)  # Max 3 concurrent extractions

async def perform_extraction(property_data: Dict[str, Any]) -> ExtractionResponse:
    """
    Perform extraction using cloud-compatible extractor.
    """
    property_id = property_data.get("id", "")
    
    async with extraction_semaphore:
        try:
            # Call cloud extractor (synchronous but fast)
            result = extract_tax_cloud(property_data)
            
            if result.get("success"):
                return ExtractionResponse(
                    success=True,
                    property_id=property_id,
                    jurisdiction=property_data.get("jurisdiction", ""),
                    tax_amount=result.get("tax_amount"),
                    property_address=result.get("property_address"),
                    account_number=result.get("account_number"),
                    extraction_date=datetime.now().isoformat(),
                    extraction_method=result.get("extraction_method", "HTTP"),
                    confidence=result.get("confidence")
                )
            else:
                return ExtractionResponse(
                    success=False,
                    property_id=property_id,
                    jurisdiction=property_data.get("jurisdiction", ""),
                    extraction_date=datetime.now().isoformat(),
                    error_message=result.get("error", "Extraction failed")
                )
                
        except Exception as e:
            logger.error(f"Extraction error for {property_id}: {e}")
            return ExtractionResponse(
                success=False,
                property_id=property_id,
                jurisdiction=property_data.get("jurisdiction", ""),
                extraction_date=datetime.now().isoformat(),
                error_message=str(e)
            )

# ========================= Endpoints =========================

@app.get("/health")
async def health_check():
    """Check API and database health."""
    error_detail = None
    supported_jurisdictions = list(cloud_extractor.get_supported_jurisdictions().keys())
    
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
        "timestamp": datetime.now().isoformat(),
        "extraction_available": True,
        "supported_jurisdictions": supported_jurisdictions
    }
    
    if error_detail:
        response["error"] = error_detail
    
    return response

@app.get("/api/v1/properties")
async def get_properties(
    limit: int = 100,
    offset: int = 0,
    jurisdiction: Optional[str] = None,
    state: Optional[str] = None,
    needs_extraction: Optional[bool] = None
):
    """Get list of properties."""
    try:
        query = supabase.table("properties").select("*")
        
        if jurisdiction:
            query = query.eq("jurisdiction", jurisdiction)
        if state:
            query = query.eq("state", state)
        if needs_extraction is not None:
            if needs_extraction:
                # Properties with 0 or null amount_due need extraction
                query = query.or_("amount_due.is.null,amount_due.eq.0")
            else:
                # Properties with non-zero amount_due
                query = query.neq("amount_due", 0).not_.is_("amount_due", "null")
        
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
    Extract tax data for a single property using cloud-compatible methods.
    """
    
    # Validate request
    if not request.tax_bill_link:
        raise HTTPException(status_code=400, detail="Tax bill link is required")
    
    # Prepare property data
    property_data = {
        "id": request.property_id,
        "jurisdiction": request.jurisdiction,
        "tax_bill_link": request.tax_bill_link,
        "account_number": request.account_number,
        "property_name": request.property_name
    }
    
    # Perform extraction
    result = await perform_extraction(property_data)
    
    # Store result in database if successful
    if result.success:
        try:
            # Update property with extracted data
            update_data = {}
            if result.tax_amount is not None:
                update_data["amount_due"] = result.tax_amount
            if result.account_number:
                update_data["account_number"] = result.account_number
            if result.property_address:
                update_data["property_address"] = result.property_address
            
            if update_data:
                update_data["updated_at"] = datetime.now().isoformat()
                supabase.table("properties").update(update_data).eq("id", request.property_id).execute()
            
            # Also store in extractions table if it exists
            try:
                extraction_record = {
                    "property_id": request.property_id,
                    "tax_amount": result.tax_amount,
                    "extraction_date": result.extraction_date,
                    "extraction_status": "success",
                    "extraction_method": result.extraction_method
                }
                supabase.table("tax_extractions").insert(extraction_record).execute()
            except:
                # Table might not exist, that's okay
                pass
                
        except Exception as e:
            logger.error(f"Failed to store extraction result: {e}")
    
    return result

@app.post("/api/v1/extract/batch")
async def extract_batch(
    request: BatchExtractionRequest,
    background_tasks: BackgroundTasks
):
    """
    Extract tax data for multiple properties (max 10 for safety).
    """
    
    if len(request.property_ids) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 properties allowed per batch"
        )
    
    # Get properties from database
    try:
        result = supabase.table("properties").select("*").in_("id", request.property_ids).execute()
        properties = result.data
        
        if not properties:
            raise HTTPException(status_code=404, detail="No properties found")
        
        # Filter for supported jurisdictions
        supported_props = []
        for prop in properties:
            jurisdiction = prop.get("jurisdiction", "")
            is_supported = any(
                key.lower() in jurisdiction.lower()
                for key in cloud_extractor.get_supported_jurisdictions().keys()
            )
            if is_supported:
                supported_props.append(prop)
        
        if not supported_props:
            return {
                "message": "No properties in supported jurisdictions",
                "supported_jurisdictions": list(cloud_extractor.get_supported_jurisdictions().keys()),
                "status": "failed"
            }
        
        # Schedule background extraction
        background_tasks.add_task(process_batch_extraction, supported_props)
        
        return {
            "message": f"Batch extraction started for {len(supported_props)} properties",
            "property_ids": [p["id"] for p in supported_props],
            "status": "processing"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def process_batch_extraction(properties: List[Dict]):
    """Process batch extraction in background"""
    for prop in properties:
        try:
            # Perform extraction
            result = await perform_extraction(prop)
            
            # Log result
            if result.success:
                logger.info(f"Extracted {prop['property_name']}: ${result.tax_amount}")
            else:
                logger.warning(f"Failed to extract {prop['property_name']}: {result.error_message}")
            
            # Add delay between extractions
            await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"Batch extraction error for {prop.get('id')}: {e}")

@app.get("/api/v1/extract/status", response_model=ExtractionStatusResponse)
async def get_extraction_status():
    """Get extraction status and statistics."""
    try:
        # Get all properties
        all_props = supabase.table("properties").select("id, amount_due").execute()
        
        total = len(all_props.data)
        extracted = sum(1 for p in all_props.data if p.get("amount_due") and p.get("amount_due") != 0)
        pending = total - extracted
        
        return ExtractionStatusResponse(
            total_properties=total,
            extracted_count=extracted,
            pending_count=pending,
            failed_count=0,
            supported_jurisdictions=list(cloud_extractor.get_supported_jurisdictions().keys())
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/jurisdictions")
async def get_jurisdictions():
    """Get list of jurisdictions with extraction support status."""
    try:
        result = supabase.table("properties").select("jurisdiction").execute()
        
        supported_list = cloud_extractor.get_supported_jurisdictions()
        jurisdictions = {}
        
        for prop in result.data:
            jur = prop.get("jurisdiction")
            if jur and jur not in jurisdictions:
                # Check if supported
                is_supported = any(
                    key.lower() in jur.lower()
                    for key in supported_list.keys()
                )
                
                # Get confidence if supported
                confidence = None
                if is_supported:
                    for key, info in supported_list.items():
                        if key.lower() in jur.lower():
                            confidence = info.get("confidence", "medium")
                            break
                
                jurisdictions[jur] = {
                    "name": jur,
                    "supported": is_supported,
                    "confidence": confidence,
                    "count": 0
                }
            
            if jur:
                jurisdictions[jur]["count"] += 1
        
        return {
            "jurisdictions": list(jurisdictions.values()),
            "total": len(jurisdictions),
            "supported_count": sum(1 for j in jurisdictions.values() if j["supported"])
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
        # Get properties
        props = supabase.table("properties").select("*").execute()
        properties = props.data
        
        # Get entities  
        ents = supabase.table("entities").select("*").execute()
        entities = ents.data
        
        # Calculate statistics
        total_outstanding = sum(p.get("amount_due", 0) or 0 for p in properties)
        total_previous = sum(p.get("previous_year_taxes", 0) or 0 for p in properties)
        
        extracted_count = sum(1 for p in properties if p.get("amount_due") and p.get("amount_due") != 0)
        pending_count = len(properties) - extracted_count
        success_rate = (extracted_count / len(properties) * 100) if properties else 0
        
        # Get last extraction date
        last_date = None
        for p in properties:
            if p.get("updated_at"):
                if not last_date or p["updated_at"] > last_date:
                    last_date = p["updated_at"]
        
        return StatisticsResponse(
            total_properties=len(properties),
            total_entities=len(entities),
            total_outstanding_tax=total_outstanding,
            total_previous_year_tax=total_previous,
            extraction_success_rate=success_rate,
            last_extraction_date=last_date,
            extracted_count=extracted_count,
            pending_count=pending_count
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/extractions")
async def get_extractions(limit: int = 100, offset: int = 0):
    """Get extraction history."""
    try:
        # Try to get from tax_extractions table
        try:
            result = supabase.table("tax_extractions").select("*").order("extraction_date", desc=True).limit(limit).offset(offset).execute()
            return {"extractions": result.data}
        except:
            # If table doesn't exist, return empty
            return {"extractions": []}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)