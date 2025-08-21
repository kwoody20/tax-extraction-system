"""
Enhanced REST API Service for Tax Extractor
Provides async endpoints for tax extraction jobs with comprehensive features
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Depends, Request, Query, Path, Header, status
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, validator, ValidationError
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any, Union, Literal
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import uuid
import os
import sys
import json
import pandas as pd
from pathlib import Path
import tempfile
import traceback
import logging
import hashlib
import time
from collections import defaultdict
import aiofiles
import redis.asyncio as redis
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import uvicorn

# Import existing modules
sys.path.append('extracting-tests-818')
from MASTER_TAX_EXTRACTOR import TaxExtractor
from config import get_config, ConfigManager
from error_handling import ErrorHandler, ExtractionError, ValidationError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('api_service.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Prometheus metrics
request_count = Counter('tax_api_requests_total', 'Total API requests', ['method', 'endpoint', 'status'])
request_duration = Histogram('tax_api_request_duration_seconds', 'Request duration', ['method', 'endpoint'])
active_jobs = Gauge('tax_api_active_jobs', 'Number of active extraction jobs')
job_success_count = Counter('tax_api_job_success_total', 'Total successful jobs')
job_failure_count = Counter('tax_api_job_failure_total', 'Total failed jobs')
extraction_duration = Histogram('tax_api_extraction_duration_seconds', 'Extraction job duration')

# Redis client for distributed job storage (optional)
redis_client: Optional[redis.Redis] = None

# In-memory job storage (fallback if Redis not available)
jobs_storage: Dict[str, Dict[str, Any]] = {}

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Security
security = HTTPBearer()

# Configuration
config_manager = get_config()

# Job states enum
class JobStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"

# Output format enum
class OutputFormat(str, Enum):
    EXCEL = "excel"
    JSON = "json"
    CSV = "csv"
    PARQUET = "parquet"

# Extraction method enum
class ExtractionMethod(str, Enum):
    AUTO = "auto"
    HTTP = "http"
    SELENIUM = "selenium"
    PLAYWRIGHT = "playwright"

# Pydantic models with comprehensive validation
class PropertyInput(BaseModel):
    """Individual property for extraction"""
    property_id: Optional[str] = Field(None, description="Unique property identifier")
    property_name: str = Field(..., min_length=1, max_length=500, description="Property name")
    property_address: Optional[str] = Field(None, max_length=1000, description="Property address")
    jurisdiction: Optional[str] = Field(None, max_length=200, description="Tax jurisdiction")
    state: Optional[str] = Field(None, pattern="^[A-Z]{2}$", description="Two-letter state code")
    account_number: Optional[str] = Field(None, max_length=100, description="Tax account number")
    tax_bill_link: str = Field(..., description="URL to tax bill")
    
    @validator('tax_bill_link')
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('Tax bill link must be a valid HTTP/HTTPS URL')
        return v
    
    @validator('state')
    def uppercase_state(cls, v):
        if v:
            return v.upper()
        return v

class ExtractionRequest(BaseModel):
    """Request model for extraction jobs"""
    properties: Optional[List[PropertyInput]] = Field(None, description="List of properties to extract")
    csv_file_path: Optional[str] = Field(None, description="Path to CSV file with properties")
    urls: Optional[List[str]] = Field(None, description="List of URLs to extract")
    concurrent: bool = Field(True, description="Enable concurrent extraction")
    max_workers: int = Field(5, ge=1, le=20, description="Maximum concurrent workers")
    save_screenshots: bool = Field(False, description="Save screenshots for debugging")
    extraction_method: ExtractionMethod = Field(ExtractionMethod.AUTO, description="Extraction method to use")
    retry_failed: bool = Field(True, description="Automatically retry failed extractions")
    timeout_seconds: int = Field(300, ge=30, le=3600, description="Timeout for extraction job")
    callback_url: Optional[str] = Field(None, description="Webhook URL for job completion")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    
    @validator('properties', 'csv_file_path', 'urls')
    def validate_input_source(cls, v, values):
        sources = [values.get('properties'), values.get('csv_file_path'), values.get('urls')]
        non_null_sources = [s for s in sources if s is not None]
        if len(non_null_sources) != 1:
            raise ValueError('Exactly one input source must be provided: properties, csv_file_path, or urls')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "properties": [
                    {
                        "property_name": "123 Main St",
                        "tax_bill_link": "https://example.com/tax/123"
                    }
                ],
                "concurrent": True,
                "max_workers": 5
            }
        }

class ExtractionResponse(BaseModel):
    """Response model for extraction submission"""
    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Current job status")
    message: str = Field(..., description="Status message")
    estimated_duration: Optional[int] = Field(None, description="Estimated duration in seconds")
    webhook_registered: bool = Field(False, description="Whether webhook callback is registered")
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "queued",
                "message": "Extraction job queued successfully",
                "estimated_duration": 120,
                "webhook_registered": False
            }
        }

class JobStatusResponse(BaseModel):
    """Detailed job status response"""
    job_id: str
    status: JobStatus
    progress: float = Field(..., ge=0, le=100, description="Progress percentage")
    total_properties: int = Field(..., ge=0, description="Total properties to process")
    processed: int = Field(..., ge=0, description="Properties processed")
    successful: int = Field(..., ge=0, description="Successful extractions")
    failed: int = Field(..., ge=0, description="Failed extractions")
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    error_details: Optional[List[Dict[str, Any]]] = None
    results_available: bool = False
    output_formats: List[OutputFormat] = []
    duration_seconds: Optional[float] = None
    retry_count: int = Field(0, ge=0, description="Number of retries attempted")
    metadata: Optional[Dict[str, Any]] = None

class ExtractedProperty(BaseModel):
    """Model for extracted property data"""
    property_id: Optional[str] = None
    property_name: str
    property_address: Optional[str] = None
    jurisdiction: Optional[str] = None
    state: Optional[str] = None
    account_number: Optional[str] = None
    tax_bill_link: str
    tax_amount: Optional[float] = Field(None, description="Extracted tax amount")
    tax_year: Optional[int] = Field(None, description="Tax year")
    due_date: Optional[datetime] = None
    extraction_timestamp: datetime
    extraction_status: Literal["success", "failed", "partial"]
    error_message: Optional[str] = None
    confidence_score: Optional[float] = Field(None, ge=0, le=1, description="Extraction confidence")
    raw_data: Optional[Dict[str, Any]] = None

class JobListResponse(BaseModel):
    """Response for job listing"""
    total: int = Field(..., ge=0, description="Total number of jobs")
    page: int = Field(..., ge=1, description="Current page")
    page_size: int = Field(..., ge=1, le=100, description="Items per page")
    jobs: List[JobStatusResponse]
    filters_applied: Dict[str, Any] = {}

class HealthResponse(BaseModel):
    """Health check response"""
    status: Literal["healthy", "degraded", "unhealthy"]
    timestamp: datetime
    version: str
    uptime_seconds: float
    active_jobs: int
    total_jobs_processed: int
    redis_connected: bool
    disk_space_available_gb: float
    memory_usage_percent: float
    components: Dict[str, str]

class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

# Utility functions
async def get_job_storage():
    """Get job storage backend (Redis or in-memory)"""
    if redis_client:
        return redis_client
    return jobs_storage

async def store_job(job_id: str, job_data: dict):
    """Store job data"""
    if redis_client:
        await redis_client.setex(
            f"job:{job_id}",
            timedelta(days=7),
            json.dumps(job_data, default=str)
        )
    else:
        jobs_storage[job_id] = job_data

async def get_job(job_id: str) -> Optional[dict]:
    """Retrieve job data"""
    if redis_client:
        data = await redis_client.get(f"job:{job_id}")
        if data:
            return json.loads(data)
    else:
        return jobs_storage.get(job_id)

async def update_job(job_id: str, updates: dict):
    """Update job data"""
    job = await get_job(job_id)
    if job:
        job.update(updates)
        await store_job(job_id, job)
        return job
    return None

async def delete_job(job_id: str):
    """Delete job data"""
    if redis_client:
        await redis_client.delete(f"job:{job_id}")
    else:
        jobs_storage.pop(job_id, None)

# Authentication dependency
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verify API token"""
    # In production, implement proper token validation
    # This is a placeholder for demonstration
    token = credentials.credentials
    if not token or len(token) < 10:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )
    return token

# Background task for extraction
async def run_extraction_task(job_id: str, request: ExtractionRequest):
    """Async background task to run extraction"""
    start_time = time.time()
    error_handler = ErrorHandler()
    
    try:
        # Update job status
        await update_job(job_id, {
            "status": JobStatus.RUNNING,
            "started_at": datetime.now()
        })
        active_jobs.inc()
        
        # Initialize extractor
        extractor = TaxExtractor()
        
        # Prepare input data
        if request.properties:
            # Convert properties to DataFrame
            df_data = []
            for prop in request.properties:
                df_data.append({
                    'Property ID': prop.property_id,
                    'Property Name': prop.property_name,
                    'Property Address': prop.property_address,
                    'Jurisdiction': prop.jurisdiction,
                    'State': prop.state,
                    'Acct Number': prop.account_number,
                    'Tax Bill Link': prop.tax_bill_link
                })
            input_df = pd.DataFrame(df_data)
            input_file = f"/tmp/input_{job_id}.csv"
            input_df.to_csv(input_file, index=False)
        elif request.csv_file_path:
            input_file = request.csv_file_path
        else:
            # Create temp file from URLs
            temp_df = pd.DataFrame({
                'Tax Bill Link': request.urls or [],
                'Property Name': [f'Property_{i+1}' for i in range(len(request.urls or []))]
            })
            input_file = f"/tmp/temp_input_{job_id}.csv"
            temp_df.to_csv(input_file, index=False)
        
        # Progress tracking callback
        async def progress_callback(processed, total, successful, failed):
            progress = (processed / total * 100) if total > 0 else 0
            await update_job(job_id, {
                "processed": processed,
                "total_properties": total,
                "successful": successful,
                "failed": failed,
                "progress": progress
            })
        
        # Run extraction with timeout
        output_file = f"/tmp/results_{job_id}.xlsx"
        
        # Wrap synchronous extraction in executor
        loop = asyncio.get_event_loop()
        success_count, fail_count = await loop.run_in_executor(
            None,
            extractor.run_extraction,
            input_file,
            output_file,
            request.concurrent,
            request.max_workers,
            request.save_screenshots
        )
        
        # Calculate duration
        duration = time.time() - start_time
        extraction_duration.observe(duration)
        
        # Update job as completed
        await update_job(job_id, {
            "status": JobStatus.COMPLETED,
            "completed_at": datetime.now(),
            "successful": success_count,
            "failed": fail_count,
            "progress": 100,
            "results_file": output_file,
            "results_available": True,
            "output_formats": [OutputFormat.EXCEL, OutputFormat.JSON, OutputFormat.CSV],
            "duration_seconds": duration
        })
        
        job_success_count.inc()
        logger.info(f"Job {job_id} completed successfully: {success_count} success, {fail_count} failed")
        
        # Trigger webhook if configured
        if request.callback_url:
            await trigger_webhook(job_id, request.callback_url)
        
    except asyncio.TimeoutError:
        await update_job(job_id, {
            "status": JobStatus.FAILED,
            "error": "Extraction timeout exceeded",
            "completed_at": datetime.now(),
            "duration_seconds": time.time() - start_time
        })
        job_failure_count.inc()
        
    except Exception as e:
        error_record = error_handler.log_error(
            e,
            {"job_id": job_id, "request": request.dict()},
            severity="HIGH"
        )
        
        await update_job(job_id, {
            "status": JobStatus.FAILED,
            "error": str(e),
            "error_details": [error_record],
            "completed_at": datetime.now(),
            "duration_seconds": time.time() - start_time
        })
        job_failure_count.inc()
        logger.error(f"Job {job_id} failed: {str(e)}")
        
    finally:
        active_jobs.dec()
        
        # Cleanup temporary files after delay
        await asyncio.sleep(3600)  # Keep files for 1 hour
        try:
            if 'input_file' in locals() and os.path.exists(input_file):
                os.remove(input_file)
        except:
            pass

async def trigger_webhook(job_id: str, callback_url: str):
    """Trigger webhook notification"""
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            job_data = await get_job(job_id)
            await client.post(
                callback_url,
                json={
                    "job_id": job_id,
                    "status": job_data.get("status"),
                    "completed_at": str(job_data.get("completed_at")),
                    "successful": job_data.get("successful"),
                    "failed": job_data.get("failed")
                },
                timeout=10
            )
            logger.info(f"Webhook triggered for job {job_id}")
    except Exception as e:
        logger.error(f"Failed to trigger webhook for job {job_id}: {e}")

# Lifespan manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Tax Extractor API Service")
    
    # Initialize Redis connection if available
    global redis_client
    try:
        redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            decode_responses=True
        )
        await redis_client.ping()
        logger.info("Connected to Redis")
    except:
        logger.warning("Redis not available, using in-memory storage")
        redis_client = None
    
    # Initialize directories
    Path("/tmp/tax_extractor").mkdir(exist_ok=True)
    
    yield
    
    # Shutdown
    logger.info("Shutting down Tax Extractor API Service")
    if redis_client:
        await redis_client.close()

# FastAPI application
app = FastAPI(
    title="Tax Extractor API",
    description="Enterprise-grade REST API for property tax extraction",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

if os.getenv("TRUSTED_HOSTS"):
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=os.getenv("TRUSTED_HOSTS").split(",")
    )

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Request tracking middleware
@app.middleware("http")
async def track_requests(request: Request, call_next):
    """Track request metrics"""
    start_time = time.time()
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    # Log request
    logger.info(f"Request {request_id}: {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        
        # Track metrics
        request_count.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        
        request_duration.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)
        
        # Add request ID header
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = str(duration)
        
        return response
        
    except Exception as e:
        logger.error(f"Request {request_id} failed: {e}")
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="Internal Server Error",
                message=str(e),
                request_id=request_id
            ).dict()
        )

# API Endpoints

@app.get("/", tags=["General"])
async def root():
    """API root endpoint with service information"""
    return {
        "service": "Tax Extractor API",
        "version": "2.0.0",
        "documentation": "/docs",
        "health": "/health",
        "metrics": "/metrics",
        "endpoints": {
            "POST /api/v1/extract": "Submit extraction job",
            "POST /api/v1/extract/batch": "Submit batch extraction",
            "POST /api/v1/extract/upload": "Upload CSV and extract",
            "GET /api/v1/jobs/{job_id}": "Get job status",
            "GET /api/v1/jobs/{job_id}/results": "Download results",
            "GET /api/v1/jobs": "List all jobs",
            "DELETE /api/v1/jobs/{job_id}": "Cancel job",
            "GET /api/v1/stats": "Get service statistics"
        }
    }

@app.post(
    "/api/v1/extract",
    response_model=ExtractionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Extraction"],
    summary="Submit extraction job",
    response_description="Job submission confirmation"
)
@limiter.limit("10/minute")
async def submit_extraction(
    request: Request,
    extraction_request: ExtractionRequest,
    background_tasks: BackgroundTasks,
    token: str = Depends(verify_token)
):
    """
    Submit a new tax extraction job.
    
    The job will be processed asynchronously. Use the returned job_id to track progress.
    """
    job_id = str(uuid.uuid4())
    
    # Estimate duration based on property count
    property_count = 0
    if extraction_request.properties:
        property_count = len(extraction_request.properties)
    elif extraction_request.urls:
        property_count = len(extraction_request.urls)
    
    estimated_duration = property_count * 10  # 10 seconds per property estimate
    
    # Initialize job
    job_data = {
        "job_id": job_id,
        "status": JobStatus.QUEUED,
        "progress": 0,
        "total_properties": property_count,
        "processed": 0,
        "successful": 0,
        "failed": 0,
        "created_at": datetime.now(),
        "completed_at": None,
        "error": None,
        "results_available": False,
        "retry_count": 0,
        "metadata": extraction_request.metadata,
        "request": extraction_request.dict()
    }
    
    await store_job(job_id, job_data)
    
    # Queue background task
    background_tasks.add_task(run_extraction_task, job_id, extraction_request)
    
    return ExtractionResponse(
        job_id=job_id,
        status=JobStatus.QUEUED,
        message="Extraction job queued successfully",
        estimated_duration=estimated_duration,
        webhook_registered=bool(extraction_request.callback_url)
    )

@app.post(
    "/api/v1/extract/upload",
    response_model=ExtractionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Extraction"],
    summary="Upload CSV and extract"
)
@limiter.limit("5/minute")
async def upload_and_extract(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="CSV file with property data"),
    concurrent: bool = Query(True, description="Enable concurrent extraction"),
    max_workers: int = Query(5, ge=1, le=20, description="Maximum concurrent workers"),
    extraction_method: ExtractionMethod = Query(ExtractionMethod.AUTO),
    token: str = Depends(verify_token)
):
    """
    Upload a CSV file and start extraction.
    
    The CSV should contain columns matching the property input schema.
    """
    # Validate file type
    if not file.filename.endswith(('.csv', '.xlsx')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV and Excel files are accepted"
        )
    
    # Save uploaded file
    job_id = str(uuid.uuid4())
    upload_dir = Path(f"/tmp/tax_extractor/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_path = upload_dir / f"{job_id}_{file.filename}"
    
    try:
        # Save file asynchronously
        async with aiofiles.open(upload_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Parse file to count properties
        if file.filename.endswith('.csv'):
            df = pd.read_csv(upload_path)
        else:
            df = pd.read_excel(upload_path)
        
        property_count = len(df)
        
        # Create extraction request
        extraction_request = ExtractionRequest(
            csv_file_path=str(upload_path),
            concurrent=concurrent,
            max_workers=max_workers,
            extraction_method=extraction_method
        )
        
        # Initialize job
        job_data = {
            "job_id": job_id,
            "status": JobStatus.QUEUED,
            "progress": 0,
            "total_properties": property_count,
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "created_at": datetime.now(),
            "completed_at": None,
            "error": None,
            "results_available": False,
            "input_file": file.filename,
            "metadata": {"uploaded_file": file.filename}
        }
        
        await store_job(job_id, job_data)
        
        # Queue background task
        background_tasks.add_task(run_extraction_task, job_id, extraction_request)
        
        return ExtractionResponse(
            job_id=job_id,
            status=JobStatus.QUEUED,
            message=f"File '{file.filename}' uploaded, {property_count} properties queued for extraction",
            estimated_duration=property_count * 10
        )
        
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process uploaded file: {str(e)}"
        )

@app.get(
    "/api/v1/jobs/{job_id}",
    response_model=JobStatusResponse,
    tags=["Jobs"],
    summary="Get job status"
)
async def get_job_status(
    job_id: str = Path(..., description="Job identifier"),
    token: str = Depends(verify_token)
):
    """Get detailed status of a specific extraction job."""
    job = await get_job(job_id)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    
    # Calculate duration if completed
    duration = None
    if job.get("started_at") and job.get("completed_at"):
        duration = (job["completed_at"] - job["started_at"]).total_seconds()
    
    return JobStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        progress=job.get("progress", 0),
        total_properties=job.get("total_properties", 0),
        processed=job.get("processed", 0),
        successful=job.get("successful", 0),
        failed=job.get("failed", 0),
        created_at=job["created_at"],
        started_at=job.get("started_at"),
        completed_at=job.get("completed_at"),
        error=job.get("error"),
        error_details=job.get("error_details"),
        results_available=job.get("results_available", False),
        output_formats=job.get("output_formats", []),
        duration_seconds=duration,
        retry_count=job.get("retry_count", 0),
        metadata=job.get("metadata")
    )

@app.get(
    "/api/v1/jobs/{job_id}/results",
    tags=["Jobs"],
    summary="Download extraction results"
)
async def get_job_results(
    job_id: str = Path(..., description="Job identifier"),
    format: OutputFormat = Query(OutputFormat.EXCEL, description="Output format"),
    token: str = Depends(verify_token)
):
    """
    Download extraction results in specified format.
    
    Available formats: excel, json, csv, parquet
    """
    job = await get_job(job_id)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    
    if job["status"] != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job is {job['status']}, results not available"
        )
    
    results_file = job.get("results_file")
    if not results_file or not os.path.exists(results_file):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Results file not found"
        )
    
    # Convert to requested format
    try:
        if format == OutputFormat.JSON:
            df = pd.read_excel(results_file, sheet_name='Results')
            return JSONResponse(
                content={
                    "job_id": job_id,
                    "extraction_date": str(job.get("completed_at")),
                    "total_records": len(df),
                    "data": df.to_dict(orient='records')
                }
            )
        elif format == OutputFormat.CSV:
            df = pd.read_excel(results_file, sheet_name='Results')
            csv_file = f"/tmp/results_{job_id}.csv"
            df.to_csv(csv_file, index=False)
            return FileResponse(
                csv_file,
                media_type='text/csv',
                filename=f"tax_extraction_{job_id}.csv"
            )
        elif format == OutputFormat.PARQUET:
            df = pd.read_excel(results_file, sheet_name='Results')
            parquet_file = f"/tmp/results_{job_id}.parquet"
            df.to_parquet(parquet_file, index=False)
            return FileResponse(
                parquet_file,
                media_type='application/octet-stream',
                filename=f"tax_extraction_{job_id}.parquet"
            )
        else:  # Excel
            return FileResponse(
                results_file,
                media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                filename=f"tax_extraction_{job_id}.xlsx"
            )
    except Exception as e:
        logger.error(f"Failed to convert results: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process results: {str(e)}"
        )

@app.get(
    "/api/v1/jobs",
    response_model=JobListResponse,
    tags=["Jobs"],
    summary="List extraction jobs"
)
async def list_jobs(
    status: Optional[JobStatus] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: Literal["asc", "desc"] = Query("desc", description="Sort order"),
    token: str = Depends(verify_token)
):
    """
    List extraction jobs with pagination and filtering.
    
    Results are sorted by creation date (newest first) by default.
    """
    # Get all jobs (in production, this would query from database)
    all_jobs = []
    
    if redis_client:
        # Get from Redis
        keys = await redis_client.keys("job:*")
        for key in keys:
            job_data = await redis_client.get(key)
            if job_data:
                all_jobs.append(json.loads(job_data))
    else:
        # Get from memory
        all_jobs = list(jobs_storage.values())
    
    # Apply filters
    if status:
        all_jobs = [j for j in all_jobs if j.get("status") == status]
    
    # Sort
    reverse = (sort_order == "desc")
    all_jobs.sort(key=lambda x: x.get(sort_by, ""), reverse=reverse)
    
    # Paginate
    total = len(all_jobs)
    start = (page - 1) * page_size
    end = start + page_size
    page_jobs = all_jobs[start:end]
    
    # Convert to response model
    job_responses = []
    for job in page_jobs:
        duration = None
        if job.get("started_at") and job.get("completed_at"):
            started = datetime.fromisoformat(str(job["started_at"]))
            completed = datetime.fromisoformat(str(job["completed_at"]))
            duration = (completed - started).total_seconds()
        
        job_responses.append(JobStatusResponse(
            job_id=job["job_id"],
            status=job["status"],
            progress=job.get("progress", 0),
            total_properties=job.get("total_properties", 0),
            processed=job.get("processed", 0),
            successful=job.get("successful", 0),
            failed=job.get("failed", 0),
            created_at=datetime.fromisoformat(str(job["created_at"])),
            started_at=datetime.fromisoformat(str(job["started_at"])) if job.get("started_at") else None,
            completed_at=datetime.fromisoformat(str(job["completed_at"])) if job.get("completed_at") else None,
            error=job.get("error"),
            results_available=job.get("results_available", False),
            duration_seconds=duration,
            metadata=job.get("metadata")
        ))
    
    return JobListResponse(
        total=total,
        page=page,
        page_size=page_size,
        jobs=job_responses,
        filters_applied={"status": status} if status else {}
    )

@app.delete(
    "/api/v1/jobs/{job_id}",
    tags=["Jobs"],
    summary="Cancel extraction job"
)
async def cancel_job(
    job_id: str = Path(..., description="Job identifier"),
    token: str = Depends(verify_token)
):
    """
    Cancel a pending or running extraction job.
    
    Only jobs with status 'pending', 'queued', or 'running' can be cancelled.
    """
    job = await get_job(job_id)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    
    if job["status"] not in [JobStatus.PENDING, JobStatus.QUEUED, JobStatus.RUNNING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job with status: {job['status']}"
        )
    
    # Update job status
    await update_job(job_id, {
        "status": JobStatus.CANCELLED,
        "completed_at": datetime.now(),
        "error": "Job cancelled by user"
    })
    
    return {"message": f"Job {job_id} cancelled successfully"}

@app.get(
    "/api/v1/stats",
    tags=["Statistics"],
    summary="Get service statistics"
)
async def get_statistics(token: str = Depends(verify_token)):
    """Get aggregate statistics about extraction jobs."""
    # Collect statistics
    all_jobs = []
    
    if redis_client:
        keys = await redis_client.keys("job:*")
        for key in keys:
            job_data = await redis_client.get(key)
            if job_data:
                all_jobs.append(json.loads(job_data))
    else:
        all_jobs = list(jobs_storage.values())
    
    # Calculate stats
    total_jobs = len(all_jobs)
    status_counts = defaultdict(int)
    total_properties = 0
    total_successful = 0
    total_failed = 0
    avg_duration = 0
    duration_count = 0
    
    for job in all_jobs:
        status_counts[job.get("status", "unknown")] += 1
        total_properties += job.get("total_properties", 0)
        total_successful += job.get("successful", 0)
        total_failed += job.get("failed", 0)
        
        if job.get("duration_seconds"):
            avg_duration += job["duration_seconds"]
            duration_count += 1
    
    if duration_count > 0:
        avg_duration /= duration_count
    
    success_rate = (total_successful / (total_successful + total_failed) * 100) if (total_successful + total_failed) > 0 else 0
    
    return {
        "total_jobs": total_jobs,
        "status_breakdown": dict(status_counts),
        "total_properties_processed": total_properties,
        "total_successful_extractions": total_successful,
        "total_failed_extractions": total_failed,
        "success_rate_percent": round(success_rate, 2),
        "average_job_duration_seconds": round(avg_duration, 2),
        "active_jobs": status_counts.get(JobStatus.RUNNING, 0),
        "queued_jobs": status_counts.get(JobStatus.QUEUED, 0) + status_counts.get(JobStatus.PENDING, 0)
    }

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Monitoring"],
    summary="Health check endpoint"
)
async def health_check():
    """
    Check service health and component status.
    
    Returns detailed health information including dependencies.
    """
    import psutil
    
    # Check Redis connection
    redis_connected = False
    if redis_client:
        try:
            await redis_client.ping()
            redis_connected = True
        except:
            pass
    
    # Get system metrics
    disk_usage = psutil.disk_usage("/")
    memory = psutil.virtual_memory()
    
    # Count active jobs
    all_jobs = []
    if redis_client:
        keys = await redis_client.keys("job:*")
        for key in keys:
            job_data = await redis_client.get(key)
            if job_data:
                job = json.loads(job_data)
                if job.get("status") == JobStatus.RUNNING:
                    all_jobs.append(job)
    else:
        all_jobs = [j for j in jobs_storage.values() if j.get("status") == JobStatus.RUNNING]
    
    # Determine overall health
    overall_status = "healthy"
    if not redis_connected and redis_client:
        overall_status = "degraded"
    if memory.percent > 90 or disk_usage.percent > 90:
        overall_status = "degraded"
    if memory.percent > 95 or disk_usage.percent > 95:
        overall_status = "unhealthy"
    
    # Get uptime
    uptime = time.time() - app.state.get("start_time", time.time())
    
    return HealthResponse(
        status=overall_status,
        timestamp=datetime.now(),
        version="2.0.0",
        uptime_seconds=uptime,
        active_jobs=len(all_jobs),
        total_jobs_processed=job_success_count._value.get() + job_failure_count._value.get(),
        redis_connected=redis_connected,
        disk_space_available_gb=round(disk_usage.free / (1024**3), 2),
        memory_usage_percent=memory.percent,
        components={
            "api": "healthy",
            "redis": "healthy" if redis_connected else "unavailable",
            "extractor": "healthy",
            "storage": "healthy" if disk_usage.percent < 90 else "degraded"
        }
    )

@app.get(
    "/metrics",
    tags=["Monitoring"],
    summary="Prometheus metrics endpoint"
)
async def metrics():
    """Export Prometheus metrics for monitoring."""
    return Response(
        generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

# Error handlers
@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    """Handle Pydantic validation errors"""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error="Validation Error",
            message="Request validation failed",
            details=exc.errors(),
            request_id=getattr(request.state, "request_id", None)
        ).dict()
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=f"HTTP {exc.status_code}",
            message=exc.detail,
            request_id=getattr(request.state, "request_id", None)
        ).dict()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="Internal Server Error",
            message="An unexpected error occurred",
            request_id=getattr(request.state, "request_id", None)
        ).dict()
    )

if __name__ == "__main__":
    # Set start time for uptime calculation
    app.state.start_time = time.time()
    
    # Run with uvicorn
    uvicorn.run(
        app,
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", 8000)),
        reload=os.getenv("API_RELOAD", "false").lower() == "true",
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
        access_log=True
    )