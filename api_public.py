"""
Optimized Public API for Tax Extraction Service with Efficient Database Queries.
Features connection pooling, query optimization, and caching.
"""

import os
import asyncio
import json
import hashlib
import gzip
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union
from functools import lru_cache, wraps
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
import time
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Depends, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator, EmailStr
from supabase import create_client, Client
from dotenv import load_dotenv
import logging
from contextvars import ContextVar

# Import cloud extractor
from cloud_extractor import extract_tax_cloud, cloud_extractor

# Import authentication and error handling
from supabase_auth import SupabaseAuthManager, get_current_user, get_optional_user
from error_handling import (
    ExtractionError, NetworkError, ParseError, ValidationError,
    RateLimitError, AuthenticationError, ConfigurationError,
    ErrorHandler, CircuitBreaker, retry_with_backoff, ErrorSeverity
)
from data_validation import DataValidator

load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
REDIS_URL = os.getenv("REDIS_URL", "")
API_KEY_HEADER = os.getenv("API_KEY_HEADER", "X-API-Key")
ENABLE_CACHE = os.getenv("ENABLE_CACHE", "true").lower() == "true"
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))  # 5 minutes default
MAX_BATCH_SIZE = int(os.getenv("MAX_BATCH_SIZE", "50"))
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # seconds

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")

# Context variables for request tracking
request_id_var: ContextVar[str] = ContextVar('request_id', default='unknown')

# Connection pooling - singleton pattern
@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """Singleton Supabase client for connection reuse."""
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize Supabase client
supabase = get_supabase_client()

# Initialize auth manager
auth_manager = SupabaseAuthManager()

# Thread pool for blocking database operations
db_executor = ThreadPoolExecutor(max_workers=20)

# Configure logging with context
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize error handler and circuit breakers
error_handler = ErrorHandler()
circuit_breakers = {}

# Initialize data validator
data_validator = DataValidator()

# Memory cache implementation (fallback when Redis not available)
class MemoryCache:
    """Simple memory cache with TTL support."""
    def __init__(self):
        self.cache = {}
        self.timestamps = {}
    
    def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            if time.time() - self.timestamps[key] < CACHE_TTL:
                return self.cache[key]
            else:
                del self.cache[key]
                del self.timestamps[key]
        return None
    
    def set(self, key: str, value: Any, ttl: int = None):
        self.cache[key] = value
        self.timestamps[key] = time.time()
    
    def delete(self, key: str):
        if key in self.cache:
            del self.cache[key]
            del self.timestamps[key]
    
    def clear(self):
        self.cache.clear()
        self.timestamps.clear()

# Initialize cache
memory_cache = MemoryCache()

# Rate limiter implementation
class RateLimiter:
    """Token bucket rate limiter."""
    def __init__(self, requests: int, window: int):
        self.requests = requests
        self.window = window
        self.clients = defaultdict(lambda: deque(maxlen=requests))
    
    def is_allowed(self, client_id: str) -> bool:
        now = time.time()
        client_requests = self.clients[client_id]
        
        # Remove old requests outside the window
        while client_requests and client_requests[0] < now - self.window:
            client_requests.popleft()
        
        # Check if limit exceeded
        if len(client_requests) >= self.requests:
            return False
        
        # Add current request
        client_requests.append(now)
        return True
    
    def reset(self, client_id: str):
        if client_id in self.clients:
            del self.clients[client_id]

# Initialize rate limiter
rate_limiter = RateLimiter(RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW)

# API Key storage (in production, use database)
API_KEYS = {
    os.getenv("MASTER_API_KEY", "sk-master-key-123"): {"role": "admin", "name": "Master Key"},
    os.getenv("VIEWER_API_KEY", "sk-viewer-key-456"): {"role": "viewer", "name": "Viewer Key"},
    os.getenv("EXTRACTOR_API_KEY", "sk-extractor-key-789"): {"role": "extractor", "name": "Extractor Key"}
}

# Create FastAPI app with enhanced configuration
app = FastAPI(
    title="Tax Extraction API - Expert Edition",
    version="4.0.0",
    description="Advanced Tax Extraction API with authentication, caching, and monitoring",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add multiple middleware layers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add trusted host middleware for security
if os.getenv("ALLOWED_HOSTS"):
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=os.getenv("ALLOWED_HOSTS").split(",")
    )

# ========================= Enums =========================

class UserRole(str, Enum):
    """User roles for access control."""
    ADMIN = "admin"
    VIEWER = "viewer"
    EXTRACTOR = "extractor"
    USER = "user"

class PaidStatus(str, Enum):
    """Tax payment status."""
    PAID = "paid"
    UNPAID = "unpaid"
    PARTIAL = "partial"
    OVERDUE = "overdue"

class ExtractionStatus(str, Enum):
    """Extraction job status."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    RETRY = "retry"

# ========================= Enhanced Models =========================

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

# Advanced search and filter models
class PropertySearchRequest(BaseModel):
    """Advanced property search with multiple filters."""
    tax_amount_min: Optional[float] = Field(None, ge=0)
    tax_amount_max: Optional[float] = Field(None, ge=0)
    due_date_start: Optional[datetime] = None
    due_date_end: Optional[datetime] = None
    paid_status: Optional[PaidStatus] = None
    jurisdictions: Optional[List[str]] = None
    states: Optional[List[str]] = None
    entity_ids: Optional[List[str]] = None
    has_extraction: Optional[bool] = None
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)
    sort_by: Optional[str] = Field("updated_at", regex="^(updated_at|amount_due|due_date|property_name)$")
    sort_order: Optional[str] = Field("desc", regex="^(asc|desc)$")

class BulkPropertyUpdate(BaseModel):
    """Bulk property update request."""
    property_id: str
    amount_due: Optional[float] = None
    due_date: Optional[datetime] = None
    paid_status: Optional[PaidStatus] = None
    paid_by: Optional[str] = None
    notes: Optional[str] = None

class BulkUpdateRequest(BaseModel):
    """Request for bulk property updates."""
    updates: List[BulkPropertyUpdate]
    validate_before_update: bool = Field(True)

class EntityRelationship(BaseModel):
    """Entity relationship model."""
    parent_entity_id: str
    child_entity_id: str
    relationship_type: str = Field(..., regex="^(parent|subsidiary|affiliate|partner)$")
    ownership_percentage: Optional[float] = Field(None, ge=0, le=100)
    effective_date: Optional[datetime] = None
    notes: Optional[str] = None

class TaxPayment(BaseModel):
    """Tax payment tracking model."""
    property_id: str
    payment_amount: float = Field(..., gt=0)
    payment_date: datetime
    payment_method: str = Field(..., regex="^(check|wire|ach|credit_card|cash)$")
    confirmation_number: Optional[str] = None
    paid_by: str = Field(..., regex="^(landlord|tenant|tenant_reimburse|other)$")
    notes: Optional[str] = None

class WebhookConfig(BaseModel):
    """Webhook configuration for notifications."""
    url: str = Field(..., regex="^https?://")
    events: List[str] = Field(..., min_items=1)
    secret: Optional[str] = None
    active: bool = Field(True)
    headers: Optional[Dict[str, str]] = None

class ExtractionAnalytics(BaseModel):
    """Detailed extraction analytics response."""
    total_extractions: int
    success_rate: float
    average_extraction_time: float
    extractions_by_jurisdiction: Dict[str, int]
    extractions_by_status: Dict[str, int]
    recent_failures: List[Dict[str, Any]]
    peak_hours: List[int]
    daily_trend: List[Dict[str, Any]]

class ApiKeyCreate(BaseModel):
    """API key creation request."""
    name: str = Field(..., min_length=3, max_length=100)
    role: UserRole
    expires_at: Optional[datetime] = None
    rate_limit: Optional[int] = Field(None, ge=1)
    allowed_ips: Optional[List[str]] = None

class ApiKeyResponse(BaseModel):
    """API key response."""
    key: str
    name: str
    role: UserRole
    created_at: datetime
    expires_at: Optional[datetime]
    last_used: Optional[datetime]

class HealthCheckResponse(BaseModel):
    """Detailed health check response."""
    status: str
    timestamp: datetime
    version: str
    subsystems: Dict[str, Dict[str, Any]]
    metrics: Dict[str, Any]
    warnings: List[str]
    errors: List[str]

# ========================= Middleware and Dependencies =========================

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add unique request ID for tracking and collect metrics."""
    request_id = request.headers.get("X-Request-ID", 
                                     hashlib.md5(f"{time.time()}{request.url}".encode()).hexdigest()[:12])
    request_id_var.set(request_id)
    
    # Increment request counter
    if hasattr(app.state, "total_requests"):
        app.state.total_requests += 1
    
    # Add to logger context
    logger_context = {'request_id': request_id}
    
    # Log request
    logger.info(f"Request: {request.method} {request.url.path}", extra=logger_context)
    
    # Process request
    start_time = time.time()
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Add headers to response
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(process_time)
        
        # Log response
        logger.info(f"Response: {response.status_code} in {process_time:.3f}s", extra=logger_context)
        
        return response
    
    except Exception as e:
        process_time = time.time() - start_time
        
        # Log error
        error_handler.log_error(
            e,
            {"path": request.url.path, "method": request.method},
            severity=ErrorSeverity.HIGH
        )
        
        logger.error(f"Request failed: {e} in {process_time:.3f}s", extra=logger_context)
        
        # Return error response
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Internal server error", "request_id": request_id}
        )

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware."""
    # Skip rate limiting for health checks
    if request.url.path == "/health":
        return await call_next(request)
    
    # Get client identifier (IP or API key)
    client_id = request.client.host if request.client else "unknown"
    api_key = request.headers.get(API_KEY_HEADER)
    if api_key:
        client_id = f"api_key:{api_key[:8]}"
    
    # Check rate limit
    if not rate_limiter.is_allowed(client_id):
        logger.warning(f"Rate limit exceeded for {client_id}")
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"error": "Rate limit exceeded", "retry_after": RATE_LIMIT_WINDOW}
        )
    
    return await call_next(request)

# Security dependencies
security = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)

async def get_api_key(api_key: Optional[str] = Depends(api_key_header)) -> Optional[Dict]:
    """Validate API key and return key info."""
    if not api_key or api_key not in API_KEYS:
        return None
    
    key_info = API_KEYS[api_key].copy()
    key_info["key"] = api_key
    
    # Update last used timestamp (in production, update in database)
    key_info["last_used"] = datetime.now().isoformat()
    
    return key_info

async def require_api_key(api_key_info: Optional[Dict] = Depends(get_api_key)) -> Dict:
    """Require valid API key."""
    if not api_key_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )
    return api_key_info

async def require_role(required_role: UserRole):
    """Require specific role for access."""
    async def role_checker(
        api_key_info: Optional[Dict] = Depends(get_api_key),
        user: Optional[Dict] = Depends(get_optional_user)
    ) -> Dict:
        # Check API key first
        if api_key_info:
            if api_key_info.get("role") == required_role.value or api_key_info.get("role") == "admin":
                return api_key_info
        
        # Check JWT token
        if user:
            user_role = user.get("metadata", {}).get("role", "user")
            if user_role == required_role.value or user_role == "admin":
                return user
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires {required_role.value} role"
        )
    
    return role_checker

# Cache decorator
def cache_result(ttl: int = CACHE_TTL):
    """Decorator to cache function results."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not ENABLE_CACHE:
                return await func(*args, **kwargs)
            
            # Generate cache key
            cache_key = f"{func.__name__}:{hashlib.md5(str((args, kwargs)).encode()).hexdigest()}"
            
            # Check cache
            cached = memory_cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for {cache_key}")
                return cached
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Store in cache
            memory_cache.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator

# ========================= Enhanced Database Functions =========================

async def get_statistics_optimized() -> Dict[str, Any]:
    """
    Get statistics using a single optimized query.
    Uses database aggregation functions instead of fetching all rows.
    """
    try:
        # Single aggregated query for all statistics
        stats_query = """
        SELECT 
            COUNT(DISTINCT p.id) as total_properties,
            COUNT(DISTINCT e.entity_id) as total_entities,
            COALESCE(SUM(p.amount_due), 0) as total_outstanding,
            COALESCE(SUM(p.previous_year_taxes), 0) as total_previous,
            COUNT(DISTINCT CASE WHEN p.amount_due > 0 THEN p.id END) as extracted_count,
            COUNT(DISTINCT CASE WHEN (p.amount_due IS NULL OR p.amount_due = 0) THEN p.id END) as pending_count,
            MAX(p.updated_at) as last_extraction_date
        FROM properties p
        LEFT JOIN entities e ON p.entity_id = e.entity_id
        """
        
        # Execute in thread pool to avoid blocking
        result = await asyncio.get_event_loop().run_in_executor(
            db_executor,
            lambda: supabase.rpc("get_tax_statistics", {}).execute()
            if hasattr(supabase, 'rpc') else None
        )
        
        # Fallback to optimized manual query if RPC not available
        if not result or not result.data:
            # Use more efficient query with limiting
            props_result = await asyncio.get_event_loop().run_in_executor(
                db_executor,
                lambda: supabase.table("properties").select(
                    "id, amount_due, previous_year_taxes, updated_at"
                ).execute()
            )
            
            entities_result = await asyncio.get_event_loop().run_in_executor(
                db_executor,
                lambda: supabase.table("entities").select("entity_id").execute()
            )
            
            properties = props_result.data if props_result else []
            entities = entities_result.data if entities_result else []
            
            # Calculate in memory (still more efficient than original)
            total_outstanding = sum(p.get("amount_due", 0) or 0 for p in properties)
            total_previous = sum(p.get("previous_year_taxes", 0) or 0 for p in properties)
            extracted_count = sum(1 for p in properties if p.get("amount_due") and p.get("amount_due") > 0)
            pending_count = len(properties) - extracted_count
            
            # Get last extraction date
            last_date = max(
                (p.get("updated_at") for p in properties if p.get("updated_at")),
                default=None
            )
            
            return {
                "total_properties": len(properties),
                "total_entities": len(entities),
                "total_outstanding": total_outstanding,
                "total_previous": total_previous,
                "extracted_count": extracted_count,
                "pending_count": pending_count,
                "last_extraction_date": last_date
            }
        
        # Parse RPC result
        data = result.data[0] if result.data else {}
        return {
            "total_properties": data.get("total_properties", 0),
            "total_entities": data.get("total_entities", 0),
            "total_outstanding": data.get("total_outstanding", 0),
            "total_previous": data.get("total_previous", 0),
            "extracted_count": data.get("extracted_count", 0),
            "pending_count": data.get("pending_count", 0),
            "last_extraction_date": data.get("last_extraction_date")
        }
        
    except Exception as e:
        logger.error(f"Statistics query error: {e}")
        raise

async def get_extraction_status_optimized() -> Dict[str, Any]:
    """
    Get extraction status using optimized counting query.
    """
    try:
        # Use COUNT with conditions instead of fetching all rows
        count_query = """
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN amount_due > 0 THEN 1 END) as extracted,
            COUNT(CASE WHEN amount_due IS NULL OR amount_due = 0 THEN 1 END) as pending
        FROM properties
        """
        
        # Try RPC first
        result = await asyncio.get_event_loop().run_in_executor(
            db_executor,
            lambda: supabase.rpc("get_extraction_counts", {}).execute()
            if hasattr(supabase, 'rpc') else None
        )
        
        if not result or not result.data:
            # Fallback to counting query
            result = await asyncio.get_event_loop().run_in_executor(
                db_executor,
                lambda: supabase.table("properties").select(
                    "id, amount_due",
                    count="exact"
                ).execute()
            )
            
            if result and result.data:
                total = len(result.data)
                extracted = sum(1 for p in result.data if p.get("amount_due") and p.get("amount_due") > 0)
                pending = total - extracted
            else:
                total = extracted = pending = 0
        else:
            data = result.data[0] if result.data else {}
            total = data.get("total", 0)
            extracted = data.get("extracted", 0)
            pending = data.get("pending", 0)
        
        return {
            "total_properties": total,
            "extracted_count": extracted,
            "pending_count": pending,
            "failed_count": 0
        }
        
    except Exception as e:
        logger.error(f"Extraction status query error: {e}")
        raise

async def get_jurisdictions_optimized() -> Dict[str, Any]:
    """
    Get jurisdictions with counts using a single aggregated query.
    """
    try:
        # Single query to get jurisdictions with counts
        jurisdiction_query = """
        SELECT 
            jurisdiction,
            COUNT(*) as count,
            COUNT(CASE WHEN amount_due > 0 THEN 1 END) as extracted_count
        FROM properties
        WHERE jurisdiction IS NOT NULL
        GROUP BY jurisdiction
        ORDER BY count DESC
        """
        
        # Try RPC first
        result = await asyncio.get_event_loop().run_in_executor(
            db_executor,
            lambda: supabase.rpc("get_jurisdiction_stats", {}).execute()
            if hasattr(supabase, 'rpc') else None
        )
        
        if not result or not result.data:
            # Fallback to regular query
            result = await asyncio.get_event_loop().run_in_executor(
                db_executor,
                lambda: supabase.table("properties").select("jurisdiction").execute()
            )
            
            # Group and count in memory
            jurisdiction_counts = {}
            for prop in (result.data if result else []):
                jur = prop.get("jurisdiction")
                if jur:
                    jurisdiction_counts[jur] = jurisdiction_counts.get(jur, 0) + 1
            
            jurisdictions_data = [
                {"jurisdiction": k, "count": v}
                for k, v in jurisdiction_counts.items()
            ]
        else:
            jurisdictions_data = result.data
        
        # Get supported jurisdictions
        supported_list = cloud_extractor.get_supported_jurisdictions()
        
        # Process jurisdictions
        jurisdictions = []
        for item in jurisdictions_data:
            jur = item.get("jurisdiction")
            if not jur:
                continue
            
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
            
            jurisdictions.append({
                "name": jur,
                "supported": is_supported,
                "confidence": confidence,
                "count": item.get("count", 0),
                "extracted_count": item.get("extracted_count", 0)
            })
        
        supported_count = sum(1 for j in jurisdictions if j["supported"])
        
        return {
            "jurisdictions": jurisdictions,
            "total": len(jurisdictions),
            "supported_count": supported_count
        }
        
    except Exception as e:
        logger.error(f"Jurisdictions query error: {e}")
        raise

@retry_with_backoff(max_attempts=3, exceptions=(Exception,))
async def batch_update_properties(updates: List[Dict[str, Any]]):
    """
    Efficiently update multiple properties in a single batch operation.
    """
    if not updates:
        return
    
    try:
        # Batch update using upsert
        await asyncio.get_event_loop().run_in_executor(
            db_executor,
            lambda: supabase.table("properties").upsert(updates).execute()
        )
    except Exception as e:
        logger.error(f"Batch update error: {e}")
        raise

async def search_properties_advanced(request: PropertySearchRequest) -> Dict[str, Any]:
    """Advanced property search with multiple filters."""
    try:
        query = supabase.table("properties").select("*")
        
        # Apply filters
        if request.tax_amount_min is not None:
            query = query.gte("amount_due", request.tax_amount_min)
        if request.tax_amount_max is not None:
            query = query.lte("amount_due", request.tax_amount_max)
        if request.due_date_start:
            query = query.gte("due_date", request.due_date_start.isoformat())
        if request.due_date_end:
            query = query.lte("due_date", request.due_date_end.isoformat())
        if request.jurisdictions:
            query = query.in_("jurisdiction", request.jurisdictions)
        if request.states:
            query = query.in_("state", request.states)
        if request.entity_ids:
            query = query.in_("entity_id", request.entity_ids)
        if request.has_extraction is not None:
            if request.has_extraction:
                query = query.not_.is_("amount_due", "null").neq("amount_due", 0)
            else:
                query = query.or_("amount_due.is.null,amount_due.eq.0")
        
        # Apply sorting
        query = query.order(request.sort_by, desc=(request.sort_order == "desc"))
        
        # Apply pagination
        query = query.range(request.offset, request.offset + request.limit - 1)
        
        # Execute query
        result = await asyncio.get_event_loop().run_in_executor(
            db_executor,
            lambda: query.execute()
        )
        
        return {
            "properties": result.data if result else [],
            "count": len(result.data) if result else 0,
            "filters_applied": request.dict(exclude_none=True)
        }
    except Exception as e:
        logger.error(f"Advanced search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def bulk_update_properties_validated(request: BulkUpdateRequest) -> Dict[str, Any]:
    """Bulk update properties with validation."""
    try:
        results = {"successful": [], "failed": []}
        
        # Validate updates if requested
        if request.validate_before_update:
            for update in request.updates:
                # Validate tax amount if provided
                if update.amount_due is not None:
                    validated_amount = data_validator.validate_currency(
                        update.amount_due, min_amount=0, max_amount=1000000
                    )
                    if validated_amount is None:
                        results["failed"].append({
                            "property_id": update.property_id,
                            "error": "Invalid tax amount"
                        })
                        continue
                    update.amount_due = validated_amount
        
        # Prepare batch updates
        updates_data = []
        for update in request.updates:
            update_dict = update.dict(exclude_none=True)
            update_dict["updated_at"] = datetime.now().isoformat()
            updates_data.append(update_dict)
        
        # Execute batch update
        if updates_data:
            await batch_update_properties(updates_data)
            results["successful"] = [u["property_id"] for u in updates_data]
        
        return results
    except Exception as e:
        logger.error(f"Bulk update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def manage_entity_relationships(relationship: EntityRelationship, action: str = "create") -> Dict[str, Any]:
    """Manage entity relationships."""
    try:
        if action == "create":
            # Check if relationship already exists
            existing = await asyncio.get_event_loop().run_in_executor(
                db_executor,
                lambda: supabase.table("entity_relationships").select("*")
                .eq("parent_entity_id", relationship.parent_entity_id)
                .eq("child_entity_id", relationship.child_entity_id)
                .execute()
            )
            
            if existing and existing.data:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Relationship already exists"
                )
            
            # Create relationship
            result = await asyncio.get_event_loop().run_in_executor(
                db_executor,
                lambda: supabase.table("entity_relationships").insert(
                    relationship.dict()
                ).execute()
            )
            
            return {"status": "created", "relationship": result.data[0] if result.data else None}
        
        elif action == "delete":
            result = await asyncio.get_event_loop().run_in_executor(
                db_executor,
                lambda: supabase.table("entity_relationships").delete()
                .eq("parent_entity_id", relationship.parent_entity_id)
                .eq("child_entity_id", relationship.child_entity_id)
                .execute()
            )
            
            return {"status": "deleted", "count": len(result.data) if result.data else 0}
        
        else:
            raise HTTPException(status_code=400, detail="Invalid action")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Entity relationship error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def track_tax_payment(payment: TaxPayment) -> Dict[str, Any]:
    """Track tax payment for a property."""
    try:
        # Validate payment amount
        validated_amount = data_validator.validate_currency(
            payment.payment_amount, min_amount=1, max_amount=1000000
        )
        if validated_amount is None:
            raise HTTPException(status_code=400, detail="Invalid payment amount")
        
        payment_data = payment.dict()
        payment_data["created_at"] = datetime.now().isoformat()
        payment_data["payment_amount"] = validated_amount
        
        # Store payment record
        result = await asyncio.get_event_loop().run_in_executor(
            db_executor,
            lambda: supabase.table("tax_payments").insert(payment_data).execute()
        )
        
        # Update property paid status
        property_update = {
            "id": payment.property_id,
            "paid_status": "paid",
            "paid_by": payment.paid_by,
            "last_payment_date": payment.payment_date.isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        await asyncio.get_event_loop().run_in_executor(
            db_executor,
            lambda: supabase.table("properties").update(property_update)
            .eq("id", payment.property_id).execute()
        )
        
        return {
            "status": "payment_recorded",
            "payment_id": result.data[0]["id"] if result.data else None,
            "property_updated": True
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Payment tracking error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_extraction_analytics(days: int = 30) -> ExtractionAnalytics:
    """Get detailed extraction analytics."""
    try:
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        # Get extraction records
        extractions = await asyncio.get_event_loop().run_in_executor(
            db_executor,
            lambda: supabase.table("tax_extractions").select("*")
            .gte("extraction_date", cutoff_date).execute()
        )
        
        if not extractions or not extractions.data:
            return ExtractionAnalytics(
                total_extractions=0,
                success_rate=0.0,
                average_extraction_time=0.0,
                extractions_by_jurisdiction={},
                extractions_by_status={},
                recent_failures=[],
                peak_hours=[],
                daily_trend=[]
            )
        
        data = extractions.data
        total = len(data)
        successful = sum(1 for e in data if e.get("extraction_status") == "success")
        
        # Calculate metrics
        by_jurisdiction = defaultdict(int)
        by_status = defaultdict(int)
        by_hour = defaultdict(int)
        by_date = defaultdict(int)
        recent_failures = []
        
        for extraction in data:
            # By jurisdiction
            jurisdiction = extraction.get("jurisdiction", "unknown")
            by_jurisdiction[jurisdiction] += 1
            
            # By status
            status = extraction.get("extraction_status", "unknown")
            by_status[status] += 1
            
            # By hour
            try:
                date_obj = datetime.fromisoformat(extraction.get("extraction_date"))
                by_hour[date_obj.hour] += 1
                by_date[date_obj.date().isoformat()] += 1
            except:
                pass
            
            # Collect failures
            if status == "failed" and len(recent_failures) < 10:
                recent_failures.append({
                    "property_id": extraction.get("property_id"),
                    "jurisdiction": jurisdiction,
                    "error": extraction.get("error_message"),
                    "date": extraction.get("extraction_date")
                })
        
        # Find peak hours
        peak_hours = sorted(by_hour.items(), key=lambda x: x[1], reverse=True)[:3]
        peak_hours = [hour for hour, _ in peak_hours]
        
        # Daily trend
        daily_trend = [
            {"date": date, "count": count}
            for date, count in sorted(by_date.items())[-7:]
        ]
        
        return ExtractionAnalytics(
            total_extractions=total,
            success_rate=(successful / total * 100) if total > 0 else 0,
            average_extraction_time=5.2,  # Placeholder - calculate from actual data
            extractions_by_jurisdiction=dict(by_jurisdiction),
            extractions_by_status=dict(by_status),
            recent_failures=recent_failures,
            peak_hours=peak_hours,
            daily_trend=daily_trend
        )
    
    except Exception as e:
        logger.error(f"Analytics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Webhook management
webhooks_storage = {}  # In production, use database

async def trigger_webhook(event: str, data: Dict[str, Any]):
    """Trigger webhooks for an event."""
    for webhook_id, config in webhooks_storage.items():
        if event in config["events"] and config["active"]:
            try:
                # Prepare payload
                payload = {
                    "event": event,
                    "timestamp": datetime.now().isoformat(),
                    "data": data
                }
                
                # Add signature if secret configured
                headers = config.get("headers", {}).copy()
                if config.get("secret"):
                    signature = hashlib.sha256(
                        f"{config['secret']}:{json.dumps(payload)}".encode()
                    ).hexdigest()
                    headers["X-Webhook-Signature"] = signature
                
                # Send webhook (in production, use async HTTP client)
                logger.info(f"Triggering webhook {webhook_id} for event {event}")
                
            except Exception as e:
                logger.error(f"Webhook trigger error: {e}")

# ========================= Extraction Logic =========================

# Rate limiting for cloud
extraction_semaphore = asyncio.Semaphore(3)  # Max 3 concurrent extractions

async def perform_extraction(property_data: Dict[str, Any]) -> ExtractionResponse:
    """
    Perform extraction using cloud-compatible extractor with enhanced error handling.
    """
    property_id = property_data.get("id", "")
    jurisdiction = property_data.get("jurisdiction", "")
    
    # Check circuit breaker for jurisdiction
    if jurisdiction in circuit_breakers:
        breaker = circuit_breakers[jurisdiction]
        if breaker.state == "open":
            logger.warning(f"Circuit breaker open for {jurisdiction}")
            return ExtractionResponse(
                success=False,
                property_id=property_id,
                jurisdiction=jurisdiction,
                extraction_date=datetime.now().isoformat(),
                error_message=f"Extraction temporarily disabled for {jurisdiction} due to repeated failures"
            )
    
    async with extraction_semaphore:
        start_time = time.time()
        
        try:
            # Call cloud extractor with circuit breaker
            if jurisdiction in circuit_breakers:
                result = circuit_breakers[jurisdiction].call(
                    extract_tax_cloud, property_data
                )
            else:
                result = extract_tax_cloud(property_data)
            
            extraction_time = time.time() - start_time
            
            if result.get("success"):
                # Validate extracted amount
                tax_amount = result.get("tax_amount")
                if tax_amount is not None:
                    validated_amount = data_validator.validate_currency(
                        tax_amount, min_amount=0, max_amount=100000
                    )
                    if validated_amount is None:
                        logger.warning(f"Invalid tax amount extracted: {tax_amount}")
                        tax_amount = None
                    else:
                        tax_amount = validated_amount
                
                # Reset circuit breaker on success
                if jurisdiction in circuit_breakers:
                    circuit_breakers[jurisdiction]._on_success()
                
                return ExtractionResponse(
                    success=True,
                    property_id=property_id,
                    jurisdiction=jurisdiction,
                    tax_amount=tax_amount,
                    property_address=result.get("property_address"),
                    account_number=result.get("account_number"),
                    extraction_date=datetime.now().isoformat(),
                    extraction_method=result.get("extraction_method", "HTTP"),
                    confidence=result.get("confidence")
                )
            else:
                # Record failure in circuit breaker
                if jurisdiction in circuit_breakers:
                    circuit_breakers[jurisdiction]._on_failure()
                
                error_msg = result.get("error", "Extraction failed")
                error_handler.log_error(
                    ExtractionError(error_msg),
                    {"property_id": property_id, "jurisdiction": jurisdiction},
                    severity=ErrorSeverity.MEDIUM
                )
                
                return ExtractionResponse(
                    success=False,
                    property_id=property_id,
                    jurisdiction=jurisdiction,
                    extraction_date=datetime.now().isoformat(),
                    error_message=error_msg
                )
                
        except Exception as e:
            # Record failure in circuit breaker
            if jurisdiction in circuit_breakers:
                circuit_breakers[jurisdiction]._on_failure()
            
            error_handler.log_error(
                e,
                {"property_id": property_id, "jurisdiction": jurisdiction},
                severity=ErrorSeverity.HIGH
            )
            
            logger.error(f"Extraction error for {property_id}: {e}")
            return ExtractionResponse(
                success=False,
                property_id=property_id,
                jurisdiction=jurisdiction,
                extraction_date=datetime.now().isoformat(),
                error_message=str(e)
            )

async def perform_batch_extraction_optimized(properties: List[Dict[str, Any]]):
    """
    Optimized batch extraction with concurrent processing and batch database updates.
    """
    # Process extractions concurrently
    extraction_tasks = [perform_extraction(prop) for prop in properties]
    results = await asyncio.gather(*extraction_tasks, return_exceptions=True)
    
    # Prepare batch updates
    updates = []
    extraction_records = []
    
    for prop, result in zip(properties, results):
        if isinstance(result, Exception):
            logger.error(f"Extraction failed for {prop.get('id')}: {result}")
            continue
        
        if result.success:
            # Prepare property update
            update_data = {
                "id": prop.get("id"),
                "updated_at": datetime.now().isoformat()
            }
            
            if result.tax_amount is not None:
                update_data["amount_due"] = result.tax_amount
            if result.account_number:
                update_data["account_number"] = result.account_number
            if result.property_address:
                update_data["property_address"] = result.property_address
            
            updates.append(update_data)
            
            # Prepare extraction record
            extraction_records.append({
                "property_id": prop.get("id"),
                "tax_amount": result.tax_amount,
                "extraction_date": result.extraction_date,
                "extraction_status": "success",
                "extraction_method": result.extraction_method
            })
            
            logger.info(f"Extracted {prop.get('property_name')}: ${result.tax_amount}")
        else:
            logger.warning(f"Failed to extract {prop.get('property_name')}: {result.error_message}")
    
    # Batch update database
    if updates:
        await batch_update_properties(updates)
    
    # Store extraction records if table exists
    if extraction_records:
        try:
            await asyncio.get_event_loop().run_in_executor(
                db_executor,
                lambda: supabase.table("tax_extractions").insert(extraction_records).execute()
            )
        except:
            # Table might not exist, that's okay
            pass

# ========================= Endpoints =========================

@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Check API and database health."""
    error_detail = None
    supported_jurisdictions = list(cloud_extractor.get_supported_jurisdictions().keys())
    
    try:
        # Test database connection with timeout
        result = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                db_executor,
                lambda: supabase.table("properties").select("property_id").limit(1).execute()
            ),
            timeout=5.0
        )
        db_status = "connected" if result else "disconnected"
        status = "healthy" if db_status == "connected" else "unhealthy"
    except asyncio.TimeoutError:
        db_status = "timeout"
        status = "unhealthy"
        error_detail = "Database connection timeout"
    except Exception as e:
        db_status = "error"
        status = "unhealthy"
        error_detail = str(e)
    
    # Collect subsystem status
    subsystems = {
        "database": {
            "status": db_status,
            "error": error_detail
        },
        "cache": {
            "status": "healthy",
            "type": "memory",
            "entries": len(memory_cache.cache)
        },
        "extraction": {
            "status": "healthy",
            "supported_jurisdictions": len(supported_jurisdictions),
            "circuit_breakers": len(circuit_breakers)
        },
        "auth": {
            "status": "healthy" if auth_manager else "unavailable"
        }
    }
    
    # Collect metrics
    metrics = {
        "uptime_seconds": time.time() - app.state.start_time if hasattr(app.state, "start_time") else 0,
        "total_requests": getattr(app.state, "total_requests", 0),
        "error_rate": error_handler.get_error_summary()["error_rate"],
        "cache_hit_rate": 0.0  # Calculate from actual metrics
    }
    
    # Collect warnings and errors
    warnings = []
    errors = []
    
    if db_status != "connected":
        errors.append(f"Database {db_status}")
    
    if len(circuit_breakers) > 0:
        open_breakers = [k for k, v in circuit_breakers.items() if v.state == "open"]
        if open_breakers:
            warnings.append(f"Circuit breakers open: {', '.join(open_breakers)}")
    
    return HealthCheckResponse(
        status=status,
        timestamp=datetime.now(),
        version="4.0.0",
        subsystems=subsystems,
        metrics=metrics,
        warnings=warnings,
        errors=errors
    )

# ========================= Advanced Property Endpoints =========================

@app.post("/api/v1/properties/search", response_model=Dict[str, Any])
@cache_result(ttl=60)
async def search_properties(
    request: PropertySearchRequest,
    user: Optional[Dict] = Depends(get_optional_user)
):
    """Advanced property search with multiple filters."""
    return await search_properties_advanced(request)

@app.put("/api/v1/properties/bulk", response_model=Dict[str, Any])
async def bulk_update_properties_endpoint(
    request: BulkUpdateRequest,
    _: Dict = Depends(require_role(UserRole.ADMIN))
):
    """Bulk update multiple properties."""
    return await bulk_update_properties_validated(request)

@app.get("/api/v1/properties")
async def get_properties(
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    jurisdiction: Optional[str] = None,
    state: Optional[str] = None,
    needs_extraction: Optional[bool] = None,
    entity_id: Optional[str] = None
):
    """Get list of properties with optimized query."""
    try:
        # Build query
        query = supabase.table("properties").select("*")
        
        # Apply filters
        if jurisdiction:
            query = query.eq("jurisdiction", jurisdiction)
        if state:
            query = query.eq("state", state)
        if entity_id:
            query = query.eq("entity_id", entity_id)
        if needs_extraction is not None:
            if needs_extraction:
                query = query.or_("amount_due.is.null,amount_due.eq.0")
            else:
                query = query.neq("amount_due", 0).not_.is_("amount_due", "null")
        
        # Apply pagination
        query = query.range(offset, offset + limit - 1)
        
        # Execute query
        result = await asyncio.get_event_loop().run_in_executor(
            db_executor,
            lambda: query.execute()
        )
        
        return {
            "properties": result.data if result else [],
            "count": len(result.data) if result else 0,
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
            update_data = {"updated_at": datetime.now().isoformat()}
            
            if result.tax_amount is not None:
                update_data["amount_due"] = result.tax_amount
            if result.account_number:
                update_data["account_number"] = result.account_number
            if result.property_address:
                update_data["property_address"] = result.property_address
            
            # Use async update
            await asyncio.get_event_loop().run_in_executor(
                db_executor,
                lambda: supabase.table("properties").update(update_data).eq("id", request.property_id).execute()
            )
            
            # Also store in extractions table if it exists
            try:
                extraction_record = {
                    "property_id": request.property_id,
                    "tax_amount": result.tax_amount,
                    "extraction_date": result.extraction_date,
                    "extraction_status": "success",
                    "extraction_method": result.extraction_method
                }
                await asyncio.get_event_loop().run_in_executor(
                    db_executor,
                    lambda: supabase.table("tax_extractions").insert(extraction_record).execute()
                )
            except:
                pass  # Table might not exist
                
        except Exception as e:
            logger.error(f"Failed to store extraction result: {e}")
    
    return result

@app.post("/api/v1/extract/batch", dependencies=[Depends(require_role(UserRole.EXTRACTOR))])
async def extract_batch(
    request: BatchExtractionRequest,
    background_tasks: BackgroundTasks
):
    """
    Extract tax data for multiple properties with optimized batch processing.
    """
    
    if len(request.property_ids) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 properties allowed per batch"
        )
    
    # Get properties from database
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            db_executor,
            lambda: supabase.table("properties").select("*").in_("id", request.property_ids).execute()
        )
        properties = result.data if result else []
        
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
        
        # Schedule optimized background extraction
        background_tasks.add_task(perform_batch_extraction_optimized, supported_props)
        
        return {
            "message": f"Batch extraction started for {len(supported_props)} properties",
            "property_ids": [p["id"] for p in supported_props],
            "status": "processing"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/extract/status", response_model=ExtractionStatusResponse)
async def get_extraction_status():
    """Get extraction status using optimized query."""
    try:
        stats = await get_extraction_status_optimized()
        
        return ExtractionStatusResponse(
            total_properties=stats["total_properties"],
            extracted_count=stats["extracted_count"],
            pending_count=stats["pending_count"],
            failed_count=stats.get("failed_count", 0),
            supported_jurisdictions=list(cloud_extractor.get_supported_jurisdictions().keys())
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/jurisdictions")
async def get_jurisdictions():
    """Get list of jurisdictions using optimized query."""
    try:
        result = await get_jurisdictions_optimized()
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========================= Entity Relationship Endpoints =========================

@app.post("/api/v1/entities/relationships", response_model=Dict[str, Any])
async def create_entity_relationship(
    relationship: EntityRelationship,
    _: Dict = Depends(require_role(UserRole.ADMIN))
):
    """Create a new entity relationship."""
    return await manage_entity_relationships(relationship, "create")

@app.delete("/api/v1/entities/relationships", response_model=Dict[str, Any])
async def delete_entity_relationship(
    parent_entity_id: str,
    child_entity_id: str,
    _: Dict = Depends(require_role(UserRole.ADMIN))
):
    """Delete an entity relationship."""
    relationship = EntityRelationship(
        parent_entity_id=parent_entity_id,
        child_entity_id=child_entity_id,
        relationship_type="parent"
    )
    return await manage_entity_relationships(relationship, "delete")

@app.get("/api/v1/entities/relationships/{entity_id}", response_model=Dict[str, Any])
@cache_result(ttl=300)
async def get_entity_relationships(
    entity_id: str,
    user: Optional[Dict] = Depends(get_optional_user)
):
    """Get all relationships for an entity."""
    try:
        # Get parent relationships
        parents = await asyncio.get_event_loop().run_in_executor(
            db_executor,
            lambda: supabase.table("entity_relationships").select("*")
            .eq("child_entity_id", entity_id).execute()
        )
        
        # Get child relationships
        children = await asyncio.get_event_loop().run_in_executor(
            db_executor,
            lambda: supabase.table("entity_relationships").select("*")
            .eq("parent_entity_id", entity_id).execute()
        )
        
        return {
            "entity_id": entity_id,
            "parents": parents.data if parents else [],
            "children": children.data if children else []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/entities")
async def get_entities(
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get list of entities with pagination."""
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            db_executor,
            lambda: supabase.table("entities").select("*").range(offset, offset + limit - 1).execute()
        )
        
        return {
            "entities": result.data if result else [],
            "count": len(result.data) if result else 0,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========================= Tax Payment Tracking Endpoints =========================

@app.post("/api/v1/payments", response_model=Dict[str, Any])
async def record_tax_payment(
    payment: TaxPayment,
    _: Dict = Depends(require_role(UserRole.ADMIN))
):
    """Record a tax payment for a property."""
    result = await track_tax_payment(payment)
    
    # Trigger webhook
    await trigger_webhook("payment.recorded", {
        "property_id": payment.property_id,
        "amount": payment.payment_amount,
        "paid_by": payment.paid_by
    })
    
    return result

@app.get("/api/v1/payments/{property_id}", response_model=List[Dict[str, Any]])
@cache_result(ttl=120)
async def get_property_payments(
    property_id: str,
    limit: int = Query(100, le=1000),
    user: Optional[Dict] = Depends(get_optional_user)
):
    """Get payment history for a property."""
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            db_executor,
            lambda: supabase.table("tax_payments").select("*")
            .eq("property_id", property_id)
            .order("payment_date", desc=True)
            .limit(limit).execute()
        )
        return result.data if result else []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========================= Analytics Endpoints =========================

@app.get("/api/v1/analytics/extractions", response_model=ExtractionAnalytics)
@cache_result(ttl=300)
async def get_extraction_analytics_endpoint(
    days: int = Query(30, ge=1, le=365),
    user: Optional[Dict] = Depends(get_optional_user)
):
    """Get detailed extraction analytics."""
    return await get_extraction_analytics(days)

@app.get("/api/v1/analytics/performance", response_model=Dict[str, Any])
@cache_result(ttl=60)
async def get_performance_metrics(
    user: Optional[Dict] = Depends(get_optional_user)
):
    """Get API performance metrics."""
    return {
        "uptime_seconds": time.time() - app.state.start_time if hasattr(app.state, "start_time") else 0,
        "total_requests": getattr(app.state, "total_requests", 0),
        "error_summary": error_handler.get_error_summary(),
        "cache_stats": {
            "entries": len(memory_cache.cache),
            "hit_rate": 0.0  # Calculate from actual metrics
        },
        "circuit_breakers": {
            name: {"state": cb.state, "failures": cb.failure_count}
            for name, cb in circuit_breakers.items()
        }
    }

# ========================= Webhook Management Endpoints =========================

@app.post("/api/v1/webhooks", response_model=Dict[str, Any])
async def create_webhook(
    config: WebhookConfig,
    _: Dict = Depends(require_role(UserRole.ADMIN))
):
    """Create a new webhook configuration."""
    webhook_id = hashlib.md5(f"{config.url}{time.time()}".encode()).hexdigest()[:12]
    webhooks_storage[webhook_id] = config.dict()
    
    return {
        "webhook_id": webhook_id,
        "status": "created",
        "config": config.dict()
    }

@app.get("/api/v1/webhooks", response_model=List[Dict[str, Any]])
async def list_webhooks(
    _: Dict = Depends(require_role(UserRole.ADMIN))
):
    """List all webhook configurations."""
    return [
        {"webhook_id": wid, **config}
        for wid, config in webhooks_storage.items()
    ]

@app.delete("/api/v1/webhooks/{webhook_id}", response_model=Dict[str, Any])
async def delete_webhook(
    webhook_id: str,
    _: Dict = Depends(require_role(UserRole.ADMIN))
):
    """Delete a webhook configuration."""
    if webhook_id not in webhooks_storage:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    del webhooks_storage[webhook_id]
    return {"status": "deleted", "webhook_id": webhook_id}

@app.post("/api/v1/webhooks/{webhook_id}/test", response_model=Dict[str, Any])
async def test_webhook(
    webhook_id: str,
    _: Dict = Depends(require_role(UserRole.ADMIN))
):
    """Test a webhook configuration."""
    if webhook_id not in webhooks_storage:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    await trigger_webhook("test", {"message": "Test webhook trigger"})
    
    return {"status": "triggered", "webhook_id": webhook_id}

# ========================= API Key Management Endpoints =========================

@app.post("/api/v1/api-keys", response_model=ApiKeyResponse)
async def create_api_key(
    request: ApiKeyCreate,
    _: Dict = Depends(require_role(UserRole.ADMIN))
):
    """Create a new API key."""
    # Generate API key
    key = f"sk-{request.role.value}-{hashlib.sha256(f'{request.name}{time.time()}'.encode()).hexdigest()[:16]}"
    
    # Store API key (in production, use database)
    API_KEYS[key] = {
        "role": request.role.value,
        "name": request.name,
        "created_at": datetime.now().isoformat(),
        "expires_at": request.expires_at.isoformat() if request.expires_at else None,
        "rate_limit": request.rate_limit,
        "allowed_ips": request.allowed_ips
    }
    
    return ApiKeyResponse(
        key=key,
        name=request.name,
        role=request.role,
        created_at=datetime.now(),
        expires_at=request.expires_at,
        last_used=None
    )

@app.get("/api/v1/api-keys", response_model=List[ApiKeyResponse])
async def list_api_keys(
    _: Dict = Depends(require_role(UserRole.ADMIN))
):
    """List all API keys (without revealing the actual keys)."""
    return [
        ApiKeyResponse(
            key=f"sk-****-{key[-8:]}",  # Mask most of the key
            name=info["name"],
            role=UserRole(info["role"]),
            created_at=datetime.fromisoformat(info.get("created_at", datetime.now().isoformat())),
            expires_at=datetime.fromisoformat(info["expires_at"]) if info.get("expires_at") else None,
            last_used=datetime.fromisoformat(info["last_used"]) if info.get("last_used") else None
        )
        for key, info in API_KEYS.items()
    ]

@app.delete("/api/v1/api-keys/{key_suffix}", response_model=Dict[str, Any])
async def revoke_api_key(
    key_suffix: str,
    _: Dict = Depends(require_role(UserRole.ADMIN))
):
    """Revoke an API key by its suffix."""
    # Find the full key by suffix
    full_key = None
    for key in API_KEYS:
        if key.endswith(key_suffix):
            full_key = key
            break
    
    if not full_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    del API_KEYS[full_key]
    return {"status": "revoked", "key_suffix": key_suffix}

# ========================= Monitoring Endpoints =========================

@app.get("/api/v1/metrics", response_model=Dict[str, Any])
async def get_metrics(
    _: Dict = Depends(require_api_key)
):
    """Get detailed system metrics."""
    return {
        "timestamp": datetime.now().isoformat(),
        "system": {
            "uptime": time.time() - app.state.start_time if hasattr(app.state, "start_time") else 0,
            "version": "4.0.0",
            "environment": os.getenv("ENVIRONMENT", "production")
        },
        "requests": {
            "total": getattr(app.state, "total_requests", 0),
            "rate_limited": getattr(app.state, "rate_limited_requests", 0)
        },
        "database": {
            "pool_size": db_executor._max_workers,
            "active_connections": db_executor._threads.__len__() if hasattr(db_executor, "_threads") else 0
        },
        "cache": {
            "type": "memory",
            "entries": len(memory_cache.cache),
            "size_bytes": sum(len(str(v)) for v in memory_cache.cache.values())
        },
        "errors": error_handler.get_error_summary()
    }

@app.get("/api/v1/logs", response_model=List[Dict[str, Any]])
async def get_recent_logs(
    limit: int = Query(100, le=1000),
    level: Optional[str] = Query(None, regex="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$"),
    _: Dict = Depends(require_role(UserRole.ADMIN))
):
    """Get recent application logs."""
    # In production, retrieve from logging service
    return [
        {
            "timestamp": datetime.now().isoformat(),
            "level": "INFO",
            "message": "Sample log entry",
            "context": {}
        }
    ]

@app.get("/api/v1/statistics", response_model=StatisticsResponse)
async def get_statistics():
    """Get system statistics using optimized query."""
    try:
        stats = await get_statistics_optimized()
        
        # Calculate success rate
        total = stats.get("total_properties", 0)
        extracted = stats.get("extracted_count", 0)
        success_rate = (extracted / total * 100) if total > 0 else 0
        
        return StatisticsResponse(
            total_properties=total,
            total_entities=stats.get("total_entities", 0),
            total_outstanding_tax=stats.get("total_outstanding", 0),
            total_previous_year_tax=stats.get("total_previous", 0),
            extraction_success_rate=success_rate,
            last_extraction_date=stats.get("last_extraction_date"),
            extracted_count=extracted,
            pending_count=stats.get("pending_count", 0)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/extractions")
async def get_extractions(
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get extraction history with pagination."""
    try:
        # Try to get from tax_extractions table
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                db_executor,
                lambda: supabase.table("tax_extractions").select("*").order(
                    "extraction_date", desc=True
                ).range(offset, offset + limit - 1).execute()
            )
            return {
                "extractions": result.data if result else [],
                "count": len(result.data) if result else 0,
                "limit": limit,
                "offset": offset
            }
        except:
            # If table doesn't exist, return empty
            return {"extractions": [], "count": 0, "limit": limit, "offset": offset}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========================= Startup/Shutdown Events =========================

@app.on_event("startup")
async def startup_event():
    """Initialize resources on startup."""
    logger.info("Tax Extraction API v4.0.0 starting up...")
    
    # Store startup time
    app.state.start_time = time.time()
    app.state.total_requests = 0
    app.state.rate_limited_requests = 0
    
    # Initialize circuit breakers for known jurisdictions
    for jurisdiction in cloud_extractor.get_supported_jurisdictions().keys():
        circuit_breakers[jurisdiction] = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60,
            expected_exception=ExtractionError
        )
    
    # Warm up the connection pool
    try:
        await asyncio.get_event_loop().run_in_executor(
            db_executor,
            lambda: supabase.table("properties").select("id").limit(1).execute()
        )
        logger.info("Database connection pool initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database connection: {e}")
    
    # Log configuration
    logger.info(f"Cache enabled: {ENABLE_CACHE}")
    logger.info(f"Rate limiting: {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW} seconds")
    logger.info(f"Max batch size: {MAX_BATCH_SIZE}")
    logger.info(f"Supported jurisdictions: {len(cloud_extractor.get_supported_jurisdictions())}")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    logger.info("API shutting down...")
    
    # Log final metrics
    if hasattr(app.state, "start_time"):
        uptime = time.time() - app.state.start_time
        logger.info(f"Total uptime: {uptime:.2f} seconds")
        logger.info(f"Total requests served: {getattr(app.state, 'total_requests', 0)}")
    
    # Clear cache
    memory_cache.clear()
    
    # Shutdown thread pool
    db_executor.shutdown(wait=True)
    
    logger.info("Shutdown complete")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)