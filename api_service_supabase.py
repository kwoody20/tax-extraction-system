"""
Enhanced FastAPI Tax Extraction Service with Supabase Integration.
Integrates with Supabase for data persistence and authentication.
"""

import os
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union
from enum import Enum
import json
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request, UploadFile, File, Query, Header
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, validator, HttpUrl
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings

import pandas as pd
from supabase import create_client, Client
from supabase.client import AsyncClient, create_async_client
from dotenv import load_dotenv

# Import extraction modules
# from robust_tax_extractor import RobustTaxExtractor
# TODO: Switch to MASTER_TAX_EXTRACTOR when integrating extraction
from supabase_client import SupabasePropertyTaxClient, AsyncSupabasePropertyTaxClient
from cloud_extractor_enhanced import EnhancedCloudTaxExtractor, extract_tax_data

load_dotenv()

# ========================= Configuration =========================

class Settings(BaseSettings):
    """Application settings with Supabase integration."""
    
    # Supabase Configuration
    supabase_url: str = os.getenv("SUPABASE_URL")
    supabase_key: str = os.getenv("SUPABASE_KEY")
    supabase_service_key: str = os.getenv("SUPABASE_SERVICE_KEY", "")
    
    def __init__(self, **data):
        super().__init__(**data)
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("Please set SUPABASE_URL and SUPABASE_KEY environment variables")
    
    # API Configuration
    api_title: str = "Tax Extraction API with Supabase"
    api_version: str = "2.0.0"
    api_description: str = "Property tax extraction service with Supabase database integration"
    
    # Server Configuration
    host: str = os.getenv("API_HOST", "0.0.0.0")
    port: int = int(os.getenv("API_PORT", "8000"))
    workers: int = int(os.getenv("API_WORKERS", "4"))
    
    # Security
    secret_key: str = os.getenv("API_SECRET_KEY", "your-secret-key-change-in-production")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # CORS
    cors_origins: List[str] = ["*"]
    
    # File Storage
    upload_dir: str = "uploads"
    results_dir: str = "results"
    max_upload_size_mb: int = 50
    
    # Extraction Settings
    max_workers: int = int(os.getenv("MAX_WORKERS", "4"))
    extraction_timeout: int = int(os.getenv("EXTRACTION_TIMEOUT", "30"))
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
    
    # Job Management
    job_retention_days: int = 7
    max_concurrent_jobs: int = 10
    
    model_config = {
        "env_file": ".env",
        "extra": "ignore"
    }

settings = Settings()

# ========================= Logging Configuration =========================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========================= Database Client =========================

class DatabaseManager:
    """Manages Supabase database connections."""
    
    def __init__(self):
        self.client = None
        self.async_client = None
        
    def get_client(self) -> SupabasePropertyTaxClient:
        """Get synchronous Supabase client."""
        if not self.client:
            self.client = SupabasePropertyTaxClient(
                url=settings.supabase_url,
                key=settings.supabase_service_key or settings.supabase_key
            )
        return self.client
    
    async def get_async_client(self) -> AsyncSupabasePropertyTaxClient:
        """Get asynchronous Supabase client."""
        if not self.async_client:
            self.async_client = AsyncSupabasePropertyTaxClient(
                url=settings.supabase_url,
                key=settings.supabase_service_key or settings.supabase_key
            )
        return self.async_client

db_manager = DatabaseManager()

# ========================= FastAPI App =========================

app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ========================= Security =========================

security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify Bearer token using Supabase Auth."""
    token = credentials.credentials
    
    # For development/testing, accept the secret key as a valid token
    if token == settings.secret_key:
        return {"authenticated": True}
    
    # Try to verify with Supabase Auth
    try:
        supabase = create_client(settings.supabase_url, settings.supabase_key)
        user = supabase.auth.get_user(token)
        if user and user.user:
            return {"user": user.user, "authenticated": True}
    except:
        pass
    
    raise HTTPException(status_code=401, detail="Invalid authentication token")

# ========================= Models =========================

class ExtractionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"

class PropertyExtractionRequest(BaseModel):
    """Request to extract tax data for properties from database."""
    property_ids: Optional[List[str]] = Field(None, description="Specific property IDs to extract")
    entity_id: Optional[str] = Field(None, description="Extract all properties for an entity")
    jurisdiction: Optional[str] = Field(None, description="Extract all properties in a jurisdiction")
    state: Optional[str] = Field(None, description="Extract all properties in a state")
    days_since_last: int = Field(30, description="Only extract if data is older than N days")
    priority: int = Field(5, ge=1, le=10, description="Job priority (1-10)")
    webhook_url: Optional[HttpUrl] = Field(None, description="Webhook for completion notification")
    
    class Config:
        json_schema_extra = {
            "example": {
                "property_ids": ["property-uuid-1", "property-uuid-2"],
                "days_since_last": 30,
                "priority": 5
            }
        }

class ExtractionJob(BaseModel):
    """Extraction job details."""
    job_id: str
    status: ExtractionStatus
    created_at: datetime
    updated_at: datetime
    total_properties: int
    processed_properties: int
    successful_extractions: int
    failed_extractions: int
    error_message: Optional[str] = None
    results: Optional[List[Dict]] = None
    
class ExtractionResult(BaseModel):
    """Result of a single property extraction."""
    property_id: str
    property_name: str
    status: ExtractionStatus
    amount_due: Optional[float] = None
    previous_year_taxes: Optional[float] = None
    extraction_date: datetime
    error_message: Optional[str] = None
    raw_data: Optional[Dict] = None

# ========================= In-Memory Job Storage =========================
# In production, this would be stored in Supabase

jobs_store: Dict[str, ExtractionJob] = {}

# ========================= Extraction Functions =========================

async def extract_property_tax(property_data: Dict) -> ExtractionResult:
    """Extract tax data for a single property."""
    property_id = property_data.get("property_id")
    property_name = property_data.get("property_name", "Unknown")
    
    try:
        # TODO: Integrate MASTER_TAX_EXTRACTOR here
        # For now, use mock extraction for deployment
        # extractor = RobustTaxExtractor(None)  # We'll pass data directly
        
        # Extract based on the tax bill URL
        tax_url = property_data.get("tax_bill_link")
        if not tax_url:
            return ExtractionResult(
                property_id=property_id,
                property_name=property_name,
                status=ExtractionStatus.FAILED,
                extraction_date=datetime.utcnow(),
                error_message="No tax bill URL available"
            )
        
        # Perform extraction (simplified for demo)
        # In production, this would use the full extraction logic
        result = {
            "amount_due": property_data.get("amount_due", 0),
            "previous_year_taxes": property_data.get("previous_year_taxes", 0)
        }
        
        # Record extraction in database
        db_client = db_manager.get_client()
        db_client.record_extraction({
            "p_property_id": property_id,
            "p_amount_due": result["amount_due"],
            "p_extraction_status": "success",
            "p_extraction_method": "api",
            "p_raw_data": json.dumps(result)
        })
        
        return ExtractionResult(
            property_id=property_id,
            property_name=property_name,
            status=ExtractionStatus.SUCCESS,
            amount_due=result["amount_due"],
            previous_year_taxes=result["previous_year_taxes"],
            extraction_date=datetime.utcnow(),
            raw_data=result
        )
        
    except Exception as e:
        logger.error(f"Extraction failed for {property_id}: {str(e)}")
        
        # Record failed extraction
        db_client = db_manager.get_client()
        db_client.record_extraction({
            "p_property_id": property_id,
            "p_extraction_status": "failed",
            "p_extraction_method": "api",
            "p_error_message": str(e)
        })
        
        return ExtractionResult(
            property_id=property_id,
            property_name=property_name,
            status=ExtractionStatus.FAILED,
            extraction_date=datetime.utcnow(),
            error_message=str(e)
        )

async def process_extraction_job(job_id: str, properties: List[Dict]):
    """Process extraction job in background."""
    job = jobs_store.get(job_id)
    if not job:
        return
    
    job.status = ExtractionStatus.PROCESSING
    job.updated_at = datetime.utcnow()
    
    results = []
    for prop in properties:
        # Update progress
        job.processed_properties += 1
        
        # Extract tax data
        result = await extract_property_tax(prop)
        results.append(result.dict())
        
        # Update counters
        if result.status == ExtractionStatus.SUCCESS:
            job.successful_extractions += 1
        else:
            job.failed_extractions += 1
        
        job.updated_at = datetime.utcnow()
    
    # Update job status
    job.results = results
    job.status = ExtractionStatus.SUCCESS if job.failed_extractions == 0 else ExtractionStatus.PARTIAL
    job.updated_at = datetime.utcnow()

# ========================= API Endpoints =========================

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Tax Extraction API with Supabase",
        "version": settings.api_version,
        "status": "operational",
        "database": "supabase",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check database connection
        db_client = db_manager.get_client()
        stats = db_client.calculate_tax_statistics()
        
        # Get actual entity count directly
        entities = db_client.get_entities(limit=100)
        actual_entity_count = len(entities)
        
        return {
            "status": "healthy",
            "database": "connected",
            "properties_count": stats.get("total_properties", 0),
            "entities_count": actual_entity_count,  # Use actual count
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

@app.get("/api/v1/properties")
async def get_properties(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    state: Optional[str] = None,
    jurisdiction: Optional[str] = None,
    entity_id: Optional[str] = None,
    needs_extraction: bool = False,
    auth: dict = Depends(verify_token)
):
    """Get properties from database."""
    try:
        db_client = db_manager.get_client()
        
        if needs_extraction:
            # Get properties needing extraction
            properties = db_client.find_properties_needing_extraction(days_since_last=30)
        else:
            # Get properties with filters
            filters = {}
            if state:
                filters["state"] = state
            if jurisdiction:
                filters["jurisdiction"] = jurisdiction
            if entity_id:
                filters["parent_entity_id"] = entity_id
            
            properties = db_client.get_properties(limit=limit, offset=offset, filters=filters)
        
        return {
            "success": True,
            "count": len(properties),
            "properties": properties
        }
    except Exception as e:
        logger.error(f"Failed to get properties: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/entities")
async def get_entities(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    auth: dict = Depends(verify_token)
):
    """Get entities from database."""
    try:
        db_client = db_manager.get_client()
        entities = db_client.get_entities(limit=limit, offset=offset)
        
        return {
            "success": True,
            "count": len(entities),
            "entities": entities
        }
    except Exception as e:
        logger.error(f"Failed to get entities: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/extract")
async def create_extraction_job(
    request: PropertyExtractionRequest,
    background_tasks: BackgroundTasks,
    auth: dict = Depends(verify_token)
):
    """Create a new extraction job for properties in database."""
    try:
        db_client = db_manager.get_client()
        
        # Get properties to extract based on request
        properties_to_extract = []
        
        if request.property_ids:
            # Get specific properties
            for prop_id in request.property_ids:
                prop = db_client.get_property(prop_id)
                if prop:
                    properties_to_extract.append(prop)
        
        elif request.entity_id:
            # Get all properties for entity
            properties = db_client.get_properties(filters={"parent_entity_id": request.entity_id})
            properties_to_extract.extend(properties)
        
        elif request.jurisdiction:
            # Get all properties in jurisdiction
            properties = db_client.get_properties(filters={"jurisdiction": request.jurisdiction})
            properties_to_extract.extend(properties)
        
        elif request.state:
            # Get all properties in state
            properties = db_client.get_properties(filters={"state": request.state})
            properties_to_extract.extend(properties)
        
        else:
            # Get properties needing extraction
            properties_to_extract = db_client.find_properties_needing_extraction(
                days_since_last=request.days_since_last
            )
        
        if not properties_to_extract:
            return {
                "success": False,
                "message": "No properties found matching criteria"
            }
        
        # Create job
        job_id = str(uuid.uuid4())
        job = ExtractionJob(
            job_id=job_id,
            status=ExtractionStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            total_properties=len(properties_to_extract),
            processed_properties=0,
            successful_extractions=0,
            failed_extractions=0
        )
        
        jobs_store[job_id] = job
        
        # Start background extraction
        background_tasks.add_task(process_extraction_job, job_id, properties_to_extract)
        
        return {
            "success": True,
            "job_id": job_id,
            "status": job.status,
            "total_properties": job.total_properties,
            "message": f"Extraction job created for {len(properties_to_extract)} properties"
        }
        
    except Exception as e:
        logger.error(f"Failed to create extraction job: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    auth: dict = Depends(verify_token)
):
    """Get extraction job status."""
    job = jobs_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "success": True,
        "job": job.dict()
    }

@app.get("/api/v1/jobs/{job_id}/results")
async def get_job_results(
    job_id: str,
    format: str = Query("json", regex="^(json|csv|excel)$"),
    auth: dict = Depends(verify_token)
):
    """Get extraction job results."""
    job = jobs_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status in [ExtractionStatus.PENDING, ExtractionStatus.PROCESSING]:
        return {
            "success": False,
            "message": "Job is still processing"
        }
    
    if format == "json":
        return {
            "success": True,
            "job_id": job_id,
            "status": job.status,
            "results": job.results
        }
    
    elif format == "csv":
        # Convert to CSV
        df = pd.DataFrame(job.results or [])
        csv_buffer = df.to_csv(index=False)
        return StreamingResponse(
            iter([csv_buffer]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=extraction_results_{job_id}.csv"}
        )
    
    elif format == "excel":
        # Convert to Excel
        df = pd.DataFrame(job.results or [])
        excel_path = f"{settings.results_dir}/extraction_results_{job_id}.xlsx"
        Path(settings.results_dir).mkdir(exist_ok=True)
        df.to_excel(excel_path, index=False)
        return FileResponse(
            excel_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=f"extraction_results_{job_id}.xlsx"
        )

@app.get("/api/v1/statistics")
async def get_statistics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    auth: dict = Depends(verify_token)
):
    """Get tax extraction statistics from database."""
    try:
        db_client = db_manager.get_client()
        
        # Parse dates
        start = datetime.fromisoformat(start_date).date() if start_date else None
        end = datetime.fromisoformat(end_date).date() if end_date else None
        
        # Get statistics
        stats = db_client.calculate_tax_statistics(start_date=start, end_date=end)
        
        # Get extraction metrics
        metrics = db_client.get_extraction_metrics(days=30)
        
        # Get portfolio summary
        portfolio = db_client.get_entity_portfolio_summary()
        
        return {
            "success": True,
            "statistics": stats,
            "extraction_metrics": metrics,
            "portfolio_summary": portfolio[:10]  # Top 10 entities
        }
    except Exception as e:
        logger.error(f"Failed to get statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/jurisdictions")
async def get_jurisdictions(
    state: Optional[str] = None,
    auth: dict = Depends(verify_token)
):
    """Get configured jurisdictions."""
    try:
        db_client = db_manager.get_client()
        jurisdictions = db_client.get_jurisdictions(state=state)
        
        return {
            "success": True,
            "count": len(jurisdictions),
            "jurisdictions": jurisdictions
        }
    except Exception as e:
        logger.error(f"Failed to get jurisdictions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/extract-enhanced")
async def extract_enhanced(
    property_id: str,
    auth: dict = Depends(verify_token)
):
    """
    Enhanced extraction endpoint with browser automation support.
    Tests the new extraction capabilities for jurisdictions requiring browser automation.
    """
    try:
        db_client = db_manager.get_client()
        
        # Get property details
        property_data = db_client.get_property(property_id)
        if not property_data:
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Prepare extraction data
        extraction_data = {
            "jurisdiction": property_data.get("jurisdiction"),
            "tax_bill_link": property_data.get("tax_bill_link"),
            "account_number": property_data.get("acct_number")
        }
        
        # Use enhanced extractor with browser support
        result = await asyncio.to_thread(extract_tax_data, extraction_data)
        
        # Store result in database if successful
        if result.get("success"):
            extraction_record = {
                "property_id": property_id,
                "extraction_date": datetime.utcnow().isoformat(),
                "amount_due": result.get("amount_due"),
                "extraction_method": result.get("method"),
                "extraction_duration": result.get("duration"),
                "status": "success",
                "raw_data": result
            }
            db_client.create_extraction(extraction_record)
        
        return {
            "success": result.get("success", False),
            "property_id": property_id,
            "jurisdiction": property_data.get("jurisdiction"),
            "extraction_result": result
        }
        
    except Exception as e:
        logger.error(f"Enhanced extraction failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/extraction-capabilities")
async def get_extraction_capabilities():
    """
    Get information about extraction capabilities including supported jurisdictions.
    """
    try:
        extractor = EnhancedCloudTaxExtractor()
        
        return {
            "success": True,
            "total_supported": len(extractor.get_supported_jurisdictions()),
            "http_only": extractor.get_http_only_jurisdictions(),
            "browser_required": extractor.get_browser_required_jurisdictions(),
            "playwright_available": extractor.__dict__.get("PLAYWRIGHT_AVAILABLE", False),
            "selenium_available": extractor.__dict__.get("SELENIUM_AVAILABLE", False)
        }
    except Exception as e:
        logger.error(f"Failed to get extraction capabilities: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/sync-database")
async def sync_database(
    auth: dict = Depends(verify_token)
):
    """Sync local CSV files with Supabase database."""
    try:
        db_client = db_manager.get_client()
        
        results = {
            "entities": {"success": 0, "failed": 0},
            "properties": {"success": 0, "failed": 0}
        }
        
        # Check for CSV files
        if Path("entities-proptax-8202025.csv").exists():
            entity_results = db_client.bulk_import_entities_from_csv("entities-proptax-8202025.csv")
            results["entities"] = entity_results
        
        if Path("OFFICIAL-proptax-assets.csv").exists():
            property_results = db_client.bulk_import_properties_from_csv("OFFICIAL-proptax-assets.csv")
            results["properties"] = property_results
        
        return {
            "success": True,
            "results": results,
            "message": "Database sync completed"
        }
    except Exception as e:
        logger.error(f"Failed to sync database: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ========================= Run Server =========================

if __name__ == "__main__":
    import uvicorn
    
    # Create necessary directories
    Path(settings.upload_dir).mkdir(exist_ok=True)
    Path(settings.results_dir).mkdir(exist_ok=True)
    
    logger.info(f"Starting Tax Extraction API with Supabase on {settings.host}:{settings.port}")
    logger.info(f"Database: {settings.supabase_url}")
    logger.info(f"API Documentation: http://{settings.host}:{settings.port}/docs")
    
    uvicorn.run(
        "api_service_supabase:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        workers=1
    )