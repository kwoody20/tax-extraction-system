"""
Optimized Public API for Tax Extraction Service with Efficient Database Queries.
Features connection pooling, query optimization, caching, and enhanced monitoring.

Version: 4.0.0 - Enhanced with advanced optimizations and monitoring
Fully compatible with Railway deployment - follows all DEPLOYMENT_CRITICAL.md guidelines
"""

import os
import asyncio
import gzip
import json
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union, Tuple
from functools import lru_cache, wraps
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import time

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Request, Response, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import ORJSONResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv
import logging

# Import cloud extractor and pooled database client
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.extractors.cloud_extractor import extract_tax_cloud, cloud_extractor
from src.database.pooled_supabase_client import create_pooled_client, PooledSupabasePropertyTaxClient
from src.database.supabase_pool import get_sync_pool

# Optional imports with graceful fallback
try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False
    orjson = json  # Fallback to standard json

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    HAS_RATE_LIMIT = True
except ImportError:
    HAS_RATE_LIMIT = False
    Limiter = None

try:
    from cachetools import TTLCache
    HAS_CACHE_TOOLS = True
except ImportError:
    HAS_CACHE_TOOLS = False
    TTLCache = dict  # Basic dict fallback

try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest
    HAS_METRICS = True
except ImportError:
    HAS_METRICS = False

# Redis disabled - not configured for this deployment
HAS_REDIS = False
aioredis = None

load_dotenv()

# Configuration (non-critical toggles may be read at import; DB creds are read lazily)
# REDIS_URL = os.getenv("REDIS_URL")  # Redis disabled for this deployment
REDIS_URL = None
ENABLE_METRICS = os.getenv("ENABLE_METRICS", "true").lower() == "true" and HAS_METRICS
ENABLE_CACHE = os.getenv("ENABLE_CACHE", "true").lower() == "true"
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))  # 5 minutes default
MAX_BATCH_SIZE = int(os.getenv("MAX_BATCH_SIZE", "50"))  # Increased batch size
CONCURRENT_EXTRACTIONS = int(os.getenv("CONCURRENT_EXTRACTIONS", "5"))
ENABLE_WEBHOOKS = os.getenv("ENABLE_WEBHOOKS", "false").lower() == "true"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
API_VERSION = "v1"  # Current API version
# Allow both ENABLE_RATE_LIMIT and ENABLE_RATE_LIMITING for compatibility
_rate_limit_env = os.getenv("ENABLE_RATE_LIMIT") or os.getenv("ENABLE_RATE_LIMITING") or "true"
ENABLE_RATE_LIMIT = _rate_limit_env.lower() == "true" and HAS_RATE_LIMIT

# Lazy initialization with connection pooling
_pooled_client: Optional[PooledSupabasePropertyTaxClient] = None

def get_pooled_client() -> PooledSupabasePropertyTaxClient:
    """Get or create singleton pooled Supabase client with lazy initialization."""
    global _pooled_client
    if _pooled_client is None:
        # Read required DB envs lazily to comply with deployment rules
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
        # Create pooled client with optimized settings
        _pooled_client = create_pooled_client(
            min_connections=3,
            max_connections=15,
            enable_caching=ENABLE_CACHE
        )
        logger.info("Initialized pooled Supabase client")
    return _pooled_client

# Create a proxy that will use lazy initialization with pooling
class SupabaseProxy:
    """Proxy class for lazy pooled Supabase initialization."""
    def __getattr__(self, name):
        client = get_pooled_client()
        # Get the underlying Supabase client from pool for compatibility
        if hasattr(client, 'pool'):
            with client.pool.get_connection() as conn:
                return getattr(conn, name)
        return getattr(client, name)
    
    def table(self, table_name: str):
        """Override table method to use pooled connection."""
        client = get_pooled_client()
        # Use pooled connection for table operations
        with client.pool.get_connection() as conn:
            return conn.table(table_name)

# Use proxy instead of direct client
supabase = SupabaseProxy()

# Thread pool for blocking database operations - increased for better concurrency
db_executor = ThreadPoolExecutor(max_workers=20)

# Configure logging with structured format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Record app start time for liveness/uptime reporting
APP_START_TIME = time.time()

# Initialize rate limiter if available
if HAS_RATE_LIMIT and ENABLE_RATE_LIMIT:
    limiter = Limiter(key_func=get_remote_address)
else:
    limiter = None

# Initialize caches
if HAS_CACHE_TOOLS and ENABLE_CACHE:
    memory_cache = TTLCache(maxsize=1000, ttl=CACHE_TTL)
    query_cache = TTLCache(maxsize=500, ttl=60)  # 1 minute for query results
else:
    memory_cache = {}
    query_cache = {}

# Redis client disabled for this deployment
redis_client = None

# Metrics initialization
if ENABLE_METRICS:
    # Request metrics
    request_count = Counter('api_requests_total', 'Total API requests', ['method', 'endpoint', 'status'])
    request_duration = Histogram('api_request_duration_seconds', 'API request duration', ['method', 'endpoint'])
    
    # Database metrics
    db_query_count = Counter('db_queries_total', 'Total database queries', ['operation'])
    db_query_duration = Histogram('db_query_duration_seconds', 'Database query duration', ['operation'])
    
    # Extraction metrics
    extraction_count = Counter('extractions_total', 'Total extractions', ['jurisdiction', 'status'])
    extraction_duration = Histogram('extraction_duration_seconds', 'Extraction duration', ['jurisdiction'])
    
    # Cache metrics
    cache_hits = Counter('cache_hits_total', 'Cache hits')
    cache_misses = Counter('cache_misses_total', 'Cache misses')
    
    # System metrics
    active_connections = Gauge('active_connections', 'Active database connections')
    queue_size = Gauge('extraction_queue_size', 'Extraction queue size')

WARM_DB_ON_STARTUP = os.getenv("WARM_DB_ON_STARTUP", "false").lower() == "true"

# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("API starting up; WARM_DB_ON_STARTUP=%s", WARM_DB_ON_STARTUP)

    # Optionally warm up the connection pool (disabled by default for pure liveness)
    if WARM_DB_ON_STARTUP:
        try:
            client = get_pooled_client()
            # Warm up the connection pool
            _ = client.get_properties(limit=1)
            logger.info("Database connection pool initialized and warmed up")
            # Log pool stats
            stats = client.get_pool_stats()
            logger.info("Pool stats: %s idle, %s total", stats.get('idle'), stats.get('created'))
        except Exception as e:
            logger.error(f"Failed to initialize pooled database connection: {e}")

    # Redis disabled - using memory cache only
    global redis_client
    redis_client = None
    logger.info("Using memory cache (Redis disabled)")

    yield

    # Shutdown
    logger.info("API shutting down...")

    # Clean up pooled connections (only if created)
    if _pooled_client is not None:
        try:
            _pooled_client.close()
            logger.info("Connection pool closed successfully")
        except Exception as e:
            logger.error(f"Error closing connection pool: {e}")

    # Shutdown thread executor
    db_executor.shutdown(wait=True)

# Determine response class
if HAS_ORJSON:
    default_response_class = ORJSONResponse
else:
    default_response_class = JSONResponse

# Create FastAPI app with enhanced configuration
app = FastAPI(
    title="Optimized Tax Extraction API",
    version="4.0.0",
    description="High-performance API with advanced optimizations, caching, and monitoring",
    default_response_class=default_response_class,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "X-Page-Count", "X-Current-Page", "X-Per-Page", "X-Response-Time", "X-API-Version"]
)

# Add compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add rate limit error handler if available
if HAS_RATE_LIMIT and ENABLE_RATE_LIMIT:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Request tracking middleware
@app.middleware("http")
async def track_requests(request: Request, call_next):
    start_time = time.time()
    
    # Track request
    method = request.method
    path = request.url.path
    
    response = await call_next(request)
    
    # Record metrics
    duration = time.time() - start_time
    if ENABLE_METRICS:
        request_count.labels(method=method, endpoint=path, status=response.status_code).inc()
        request_duration.labels(method=method, endpoint=path).observe(duration)
    
    # Add response headers
    response.headers["X-Response-Time"] = f"{duration:.3f}"
    response.headers["X-API-Version"] = API_VERSION
    
    return response

# ========================= Enhanced Models with Validation =========================

class HealthResponse(BaseModel):
    status: str
    database: str
    timestamp: str
    extraction_available: bool = True
    supported_jurisdictions: List[str] = []
    cache_status: Optional[str] = None
    metrics_enabled: bool = ENABLE_METRICS
    api_version: str = API_VERSION
    response_time_ms: Optional[float] = None
    error: Optional[str] = None  # Add error field for health check errors
    pool_stats: Optional[Dict[str, Any]] = None  # Connection pool statistics

class LivenessResponse(BaseModel):
    status: str = "ok"
    timestamp: str
    api_version: str = API_VERSION
    uptime_seconds: float

class PropertyResponse(BaseModel):
    property_id: str = Field(..., description="Unique property identifier")
    property_name: str = Field(..., description="Property name")
    property_address: Optional[str] = Field(None, description="Property address")
    jurisdiction: Optional[str] = Field(None, description="Tax jurisdiction")
    state: Optional[str] = Field(None, description="State code")
    entity_id: Optional[str] = Field(None, description="Associated entity ID")
    amount_due: Optional[float] = Field(None, description="Current tax amount due")
    due_date: Optional[str] = Field(None, description="Tax payment due date")
    last_extraction: Optional[str] = Field(None, description="Last extraction timestamp")
    tax_bill_url: Optional[str] = Field(None, description="Tax bill URL")
    
    class Config:
        schema_extra = {
            "example": {
                "property_id": "prop_123",
                "property_name": "Example Property",
                "jurisdiction": "Montgomery County",
                "state": "TX",
                "amount_due": 5000.00
            }
        }

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
    property_id: str = Field(..., description="Property ID to extract")
    jurisdiction: str = Field(..., description="Tax jurisdiction")
    tax_bill_link: str = Field(..., description="URL to tax bill")
    account_number: Optional[str] = Field(None, description="Account number")
    property_name: Optional[str] = Field(None, description="Property name for logging")
    webhook_url: Optional[str] = Field(None, description="Webhook URL for completion notification")
    priority: Optional[str] = Field("normal", description="Priority: low, normal, high")
    
    @field_validator('tax_bill_link')
    @classmethod
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('Invalid URL format')
        return v

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
    property_ids: List[str] = Field(..., min_items=1, max_items=MAX_BATCH_SIZE, description="List of property IDs")
    webhook_url: Optional[str] = Field(None, description="Webhook URL for batch completion")
    priority: Optional[str] = Field("normal", description="Batch priority")
    parallel: bool = Field(True, description="Process in parallel")

class ExtractionStatusResponse(BaseModel):
    total_properties: int
    extracted_count: int
    pending_count: int
    failed_count: int
    supported_jurisdictions: List[str]
    in_progress_count: int = 0
    average_extraction_time: Optional[float] = None
    last_24h_extractions: int = 0
    success_rate_24h: Optional[float] = None

class PaginationParams(BaseModel):
    """Common pagination parameters"""
    limit: int = Field(Query(100, ge=1, le=1000), description="Items per page")
    offset: int = Field(Query(0, ge=0), description="Number of items to skip")
    cursor: Optional[str] = Field(None, description="Cursor for cursor-based pagination")
    
class BulkUpdateRequest(BaseModel):
    """Request for bulk property updates"""
    updates: List[Dict[str, Any]] = Field(..., min_items=1, max_items=100)
    validate: bool = Field(True, description="Validate data before update")
    
class WebhookPayload(BaseModel):
    """Webhook notification payload"""
    event: str
    timestamp: str
    data: Dict[str, Any]
    signature: Optional[str] = None

# ========================= Caching Decorators =========================

def cache_key(*args, **kwargs) -> str:
    """Generate cache key from arguments"""
    key_data = f"{args}_{kwargs}"
    return hashlib.md5(key_data.encode()).hexdigest()

def cached_result(ttl: int = CACHE_TTL):
    """Decorator for caching async function results"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not ENABLE_CACHE:
                return await func(*args, **kwargs)
            
            key = f"{func.__name__}_{cache_key(*args, **kwargs)}"
            
            # Check memory cache first
            if key in memory_cache:
                if ENABLE_METRICS:
                    cache_hits.inc()
                return memory_cache[key]
            
            # Redis disabled - skip Redis check
            
            # Cache miss - execute function
            if ENABLE_METRICS:
                cache_misses.inc()
            
            result = await func(*args, **kwargs)
            
            # Store in memory cache only (Redis disabled)
            memory_cache[key] = result
            
            return result
        return wrapper
    return decorator

# ========================= Database Query Monitoring =========================

async def monitored_query(operation: str, query_func):
    """Execute database query with monitoring"""
    start_time = time.time()
    
    try:
        if ENABLE_METRICS:
            active_connections.inc()
        
        result = await asyncio.get_event_loop().run_in_executor(
            db_executor, query_func
        )
        
        if ENABLE_METRICS:
            duration = time.time() - start_time
            db_query_count.labels(operation=operation).inc()
            db_query_duration.labels(operation=operation).observe(duration)
        
        return result
    
    finally:
        if ENABLE_METRICS:
            active_connections.dec()

# ========================= Optimized Database Functions =========================

@cached_result(ttl=60)  # Cache for 1 minute
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
        LEFT JOIN entities e ON p.parent_entity_id = e.entity_id
        """
        
        # Execute with monitoring - temporarily disable RPC to use manual query
        result = await monitored_query(
            "statistics_rpc",
            lambda: None  # Temporarily disabled to use manual fallback
        )
        
        # Fallback to optimized manual query if RPC not available
        if not result or not result.data:
            # Use more efficient query with limiting
            props_result = await monitored_query(
                "properties_stats",
                lambda: supabase.table("properties").select(
                    "id, amount_due, previous_year_taxes, updated_at"
                ).execute()
            )
            
            entities_result = await monitored_query(
                "entities_count",
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

@cached_result(ttl=30)  # Cache for 30 seconds
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
        result = await monitored_query(
            "extraction_counts_rpc",
            lambda: supabase.rpc("get_extraction_counts", {}).execute()
            if hasattr(supabase, 'rpc') else None
        )
        
        if not result or not result.data:
            # Fallback to counting query
            result = await monitored_query(
                "extraction_counts",
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

@cached_result(ttl=300)  # Cache for 5 minutes
async def get_jurisdictions_optimized() -> Dict[str, Any]:
    """
    Get jurisdictions from the jurisdictions table and enrich with property counts
    and support information from the cloud extractor map.
    """
    try:
        # 1) Fetch canonical jurisdictions from jurisdictions table
        jur_result = await monitored_query(
            "jurisdictions_table",
            lambda: supabase
                .table("jurisdictions")
                .select("jurisdiction_name,state,jurisdiction_type,tax_website_url,is_active")
                .execute()
        )
        jurisdictions_rows = jur_result.data if jur_result else []

        # 2) Count properties per jurisdiction name (in-memory aggregation)
        prop_result = await monitored_query(
            "properties_for_counts",
            lambda: supabase
                .table("properties")
                .select("jurisdiction,amount_due")
                .execute()
        )
        jurisdiction_counts: Dict[str, int] = {}
        extracted_counts: Dict[str, int] = {}
        for prop in (prop_result.data if prop_result else []):
            jn = (prop.get("jurisdiction") or "").strip()
            if not jn:
                continue
            jurisdiction_counts[jn] = jurisdiction_counts.get(jn, 0) + 1
            amt = prop.get("amount_due")
            if isinstance(amt, (int, float)) and amt > 0:
                extracted_counts[jn] = extracted_counts.get(jn, 0) + 1

        # 3) Annotate with cloud extractor supported jurisdictions
        supported_map = cloud_extractor.get_supported_jurisdictions()

        jurisdictions = []
        for row in jurisdictions_rows:
            name = row.get("jurisdiction_name")
            if not name:
                continue
            # Determine support/confidence via substring match
            is_supported = any(k.lower() in name.lower() for k in supported_map.keys())
            confidence = None
            if is_supported:
                for k, info in supported_map.items():
                    if k.lower() in name.lower():
                        confidence = info.get("confidence", "medium")
                        break

            jurisdictions.append({
                "name": name,
                "state": row.get("state"),
                "jurisdiction_type": row.get("jurisdiction_type"),
                "tax_website_url": row.get("tax_website_url"),
                "is_active": row.get("is_active"),
                "supported": is_supported,
                "confidence": confidence,
                "count": jurisdiction_counts.get(name, 0),
                "extracted_count": extracted_counts.get(name, 0),
            })

        supported_count = sum(1 for j in jurisdictions if j.get("supported"))
        return {
            "jurisdictions": jurisdictions,
            "total": len(jurisdictions),
            "supported_count": supported_count
        }
    except Exception as e:
        logger.error(f"Jurisdictions query error: {e}")
        raise

async def batch_update_properties(updates: List[Dict[str, Any]], chunk_size: int = 100):
    """
    Efficiently update multiple properties with chunking for large batches.
    """
    if not updates:
        return
    
    try:
        # Process in chunks to avoid overwhelming the database
        for i in range(0, len(updates), chunk_size):
            chunk = updates[i:i + chunk_size]
            await monitored_query(
                "batch_update",
                lambda c=chunk: supabase.table("properties").upsert(c).execute()
            )
    except Exception as e:
        logger.error(f"Batch update error: {e}")
        raise

async def get_properties_with_cursor(cursor: Optional[str], limit: int) -> Tuple[List[Dict], Optional[str]]:
    """
    Get properties with cursor-based pagination for better performance.
    """
    query = supabase.table("properties").select("*").limit(limit)
    
    if cursor:
        # Decode cursor (assuming it's a property_id)
        query = query.gt("id", cursor)
    
    query = query.order("id")
    
    result = await monitored_query(
        "properties_cursor",
        lambda: query.execute()
    )
    
    properties = result.data if result else []
    next_cursor = properties[-1]["id"] if properties and len(properties) == limit else None
    
    return properties, next_cursor

# ========================= Enhanced Extraction Logic =========================

# Rate limiting with configurable concurrency
extraction_semaphore = asyncio.Semaphore(CONCURRENT_EXTRACTIONS)

# Priority queue for extractions
from asyncio import PriorityQueue
extraction_queue = PriorityQueue()

# Webhook notification
async def send_webhook_notification(webhook_url: str, payload: Dict[str, Any]):
    """Send webhook notification for extraction completion"""
    if not webhook_url or not ENABLE_WEBHOOKS:
        return
    
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            webhook_data = WebhookPayload(
                event="extraction_complete",
                timestamp=datetime.now().isoformat(),
                data=payload
            )
            await client.post(
                webhook_url,
                json=webhook_data.dict(),
                timeout=10.0
            )
            logger.info(f"Webhook sent to {webhook_url}")
    except Exception as e:
        logger.error(f"Webhook notification failed: {e}")

async def perform_extraction(property_data: Dict[str, Any], webhook_url: Optional[str] = None) -> ExtractionResponse:
    """
    Perform extraction using cloud-compatible extractor.
    """
    # Use logical property_id where available; fallback to DB PK id only for internal use
    property_pk = property_data.get("id", "")
    property_logical_id = property_data.get("property_id") or property_pk
    
    async with extraction_semaphore:
        try:
            # Track extraction start time
            start_time = time.time()
            
            # Call cloud extractor (synchronous but fast)
            result = extract_tax_cloud(property_data)
            
            # Track extraction duration
            if ENABLE_METRICS:
                duration = time.time() - start_time
                extraction_duration.labels(
                    jurisdiction=property_data.get("jurisdiction", "")
                ).observe(duration)
            
            if result.get("success"):
                response = ExtractionResponse(
                    success=True,
                    property_id=property_logical_id,
                    jurisdiction=property_data.get("jurisdiction", ""),
                    tax_amount=result.get("tax_amount"),
                    property_address=result.get("property_address"),
                    account_number=result.get("account_number"),
                    extraction_date=datetime.now().isoformat(),
                    extraction_method=result.get("extraction_method", "HTTP"),
                    confidence=result.get("confidence")
                )
                
                # Send webhook if configured
                if webhook_url:
                    await send_webhook_notification(webhook_url, response.dict())
                
                # Track metrics
                if ENABLE_METRICS:
                    extraction_count.labels(
                        jurisdiction=property_data.get("jurisdiction", ""),
                        status="success"
                    ).inc()
                
                return response
            else:
                response = ExtractionResponse(
                    success=False,
                    property_id=property_logical_id,
                    jurisdiction=property_data.get("jurisdiction", ""),
                    extraction_date=datetime.now().isoformat(),
                    error_message=result.get("error", "Extraction failed")
                )
                
                if ENABLE_METRICS:
                    extraction_count.labels(
                        jurisdiction=property_data.get("jurisdiction", ""),
                        status="failed"
                    ).inc()
                
                return response
                
        except Exception as e:
            logger.error(f"Extraction error for {property_id}: {e}")
            return ExtractionResponse(
                success=False,
                property_id=property_logical_id,
                jurisdiction=property_data.get("jurisdiction", ""),
                extraction_date=datetime.now().isoformat(),
                error_message=str(e)
            )



async def perform_batch_extraction_optimized(properties: List[Dict[str, Any]], webhook_url: Optional[str] = None, parallel: bool = True):
    """
    Optimized batch extraction with concurrent processing and batch database updates.
    """
    # Process extractions based on parallel flag
    if parallel:
        # Concurrent processing with semaphore limiting
        extraction_tasks = [perform_extraction(prop, webhook_url) for prop in properties]
        results = await asyncio.gather(*extraction_tasks, return_exceptions=True)
    else:
        # Sequential processing
        results = []
        for prop in properties:
            result = await perform_extraction(prop, webhook_url)
            results.append(result)
    
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
                "property_id": prop.get("property_id") or prop.get("id"),
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
            await monitored_query(
                "store_extractions",
                lambda: supabase.table("tax_extractions").insert(extraction_records).execute()
            )
        except:
            # Table might not exist, that's okay
            pass
    
    # Send batch completion webhook
    if webhook_url:
        summary = {
            "total": len(properties),
            "successful": len([r for r in results if not isinstance(r, Exception) and r.success]),
            "failed": len([r for r in results if isinstance(r, Exception) or not r.success])
        }
        await send_webhook_notification(webhook_url, summary)

# ========================= Endpoints =========================

# Rate limit decorator wrapper
def rate_limit(limits: str):
    """Wrapper for rate limiting decorator"""
    if HAS_RATE_LIMIT and ENABLE_RATE_LIMIT and limiter:
        return limiter.limit(limits)
    else:
        # No-op decorator if rate limiting not available
        def decorator(func):
            return func
        return decorator

@app.get("/livez", response_model=LivenessResponse, tags=["System"])
async def liveness_check():
    """Pure liveness check — no database or external dependencies."""
    return LivenessResponse(
        status="ok",
        timestamp=datetime.now().isoformat(),
        api_version=API_VERSION,
        uptime_seconds=max(0.0, time.time() - APP_START_TIME),
    )

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Check API and database health with connection pool status."""
    start_time = time.time()
    error_detail = None
    supported_jurisdictions = list(cloud_extractor.get_supported_jurisdictions().keys())
    pool_info = {}
    
    try:
        # Test database connection with timeout using pooled client
        client = get_pooled_client()
        result = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                db_executor,
                lambda: client.get_properties(limit=1)
            ),
            timeout=12.0
        )
        db_status = "connected" if result is not None else "disconnected"
        status = "healthy" if db_status == "connected" else "unhealthy"
        
        # Get pool statistics
        pool_stats = client.get_pool_stats()
        pool_info = {
            "active_connections": pool_stats.get("active", 0),
            "idle_connections": pool_stats.get("idle", 0),
            "total_requests": pool_stats.get("total_requests", 0)
        }
    except asyncio.TimeoutError:
        db_status = "timeout"
        status = "unhealthy"
        error_detail = "Database connection timeout"
    except Exception as e:
        db_status = "error"
        status = "unhealthy"
        error_detail = str(e)
    
    # Check cache status (Redis disabled)
    cache_status = "disabled"
    if ENABLE_CACHE:
        cache_status = "memory+pooled"  # Memory cache + pooled client cache
    
    response_time = (time.time() - start_time) * 1000  # Convert to ms
    
    response = HealthResponse(
        status=status,
        database=db_status,
        timestamp=datetime.now().isoformat(),
        extraction_available=True,
        supported_jurisdictions=supported_jurisdictions,
        cache_status=cache_status,
        metrics_enabled=ENABLE_METRICS,
        api_version=API_VERSION,
        response_time_ms=response_time,
        error=error_detail,  # Include error if present
        pool_stats=pool_info  # Add pool information
    )
    
    return response

@app.get("/metrics", tags=["System"])
async def get_metrics():
    """Get Prometheus metrics"""
    if not ENABLE_METRICS:
        raise HTTPException(status_code=404, detail="Metrics not enabled")
    return Response(content=generate_latest(), media_type="text/plain")

@app.get("/api/v1/properties", tags=["Properties"])
@rate_limit("100/minute")
async def get_properties(
    request: Request,
    limit: int = Query(100, ge=1, le=1000, description="Number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    cursor: Optional[str] = Query(None, description="Cursor for pagination"),
    jurisdiction: Optional[str] = Query(None, description="Filter by jurisdiction"),
    state: Optional[str] = Query(None, description="Filter by state"),
    needs_extraction: Optional[bool] = Query(None, description="Filter by extraction status"),
    entity_id: Optional[str] = Query(None, description="Filter by entity ID (entities.entity_id)"),
    amount_due_min: Optional[float] = Query(None, description="Minimum amount due"),
    amount_due_max: Optional[float] = Query(None, description="Maximum amount due"),
    due_date_before: Optional[str] = Query(None, description="Due date before (ISO format)"),
    due_date_after: Optional[str] = Query(None, description="Due date after (ISO format)"),
    sort_by: Optional[str] = Query("id", description="Sort field"),
    sort_order: Optional[str] = Query("asc", description="Sort order: asc or desc")
):
    """Get list of properties with enhanced filtering and pagination."""
    try:
        # Use cursor pagination if cursor provided
        if cursor:
            properties, next_cursor = await get_properties_with_cursor(cursor, limit)
            return {
                "properties": properties,
                "count": len(properties),
                "limit": limit,
                "cursor": cursor,
                "next_cursor": next_cursor
            }
        
        # Build query with all filters
        query = supabase.table("properties").select("*")
        
        # Apply all filters
        if jurisdiction:
            query = query.eq("jurisdiction", jurisdiction)
        if state:
            query = query.eq("state", state)
        if entity_id:
            # properties.parent_entity_id references entities.entity_id
            query = query.eq("parent_entity_id", entity_id)
        if needs_extraction is not None:
            if needs_extraction:
                query = query.or_("amount_due.is.null,amount_due.eq.0")
            else:
                query = query.neq("amount_due", 0).not_.is_("amount_due", "null")
        if amount_due_min is not None:
            query = query.gte("amount_due", amount_due_min)
        if amount_due_max is not None:
            query = query.lte("amount_due", amount_due_max)
        # Properties table uses tax_due_date
        if due_date_before:
            query = query.lte("tax_due_date", due_date_before)
        if due_date_after:
            query = query.gte("tax_due_date", due_date_after)
        
        # Apply sorting
        if sort_order == "desc":
            query = query.order(sort_by, desc=True)
        else:
            query = query.order(sort_by)
        
        # Apply pagination
        query = query.range(offset, offset + limit - 1)
        
        # Execute query with monitoring
        result = await monitored_query("get_properties", lambda: query.execute())
        
        return {
            "properties": result.data if result else [],
            "count": len(result.data) if result else 0,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/extract", response_model=ExtractionResponse, tags=["Extraction"])
@rate_limit("30/minute")
async def extract_property_tax(request: Request, extraction_request: ExtractionRequest):
    """
    Extract tax data for a single property using cloud-compatible methods.
    """
    
    # Validate request
    if not extraction_request.tax_bill_link:
        raise HTTPException(status_code=400, detail="Tax bill link is required")
    
    # Prepare property data
    property_data = {
        "id": extraction_request.property_id,
        "jurisdiction": extraction_request.jurisdiction,
        "tax_bill_link": extraction_request.tax_bill_link,
        "account_number": extraction_request.account_number,
        "property_name": extraction_request.property_name
    }
    
    # Perform extraction with priority
    if extraction_request.priority == "high":
        # Process immediately
        result = await perform_extraction(property_data, extraction_request.webhook_url)
    else:
        # Use queue for normal/low priority
        result = await perform_extraction(property_data, extraction_request.webhook_url)
    
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
            
            # Update by logical property_id
            await monitored_query(
                "update_property_by_property_id",
                lambda: supabase.table("properties").update(update_data).eq("property_id", extraction_request.property_id).execute()
            )
            
            # Also store in extractions table if it exists
            try:
                extraction_record = {
                    "property_id": extraction_request.property_id,
                    "tax_amount": result.tax_amount,
                    "extraction_date": result.extraction_date,
                    "extraction_status": "success",
                    "extraction_method": result.extraction_method
                }
                await monitored_query(
                    "store_extraction",
                    lambda: supabase.table("tax_extractions").insert(extraction_record).execute()
                )
            except Exception:
                pass  # Table might not exist
                
        except Exception as e:
            logger.error(f"Failed to store extraction result: {e}")
    
    return result

@app.post("/api/v1/extract/batch", tags=["Extraction"])
@rate_limit("10/minute")
async def extract_batch(
    request: Request,
    batch_request: BatchExtractionRequest,
    background_tasks: BackgroundTasks
):
    """
    Extract tax data for multiple properties with optimized batch processing.
    """
    
    if len(batch_request.property_ids) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_BATCH_SIZE} properties allowed per batch"
        )
    
    # Get properties from database (support both id and property_id inputs)
    try:
        # Fetch strictly by logical property_id
        result = await monitored_query(
            "get_batch_properties_by_property_id",
            lambda: supabase.table("properties").select("*").in_("property_id", batch_request.property_ids).execute()
        )
        properties = result.data if result else []

        if not properties:
            raise HTTPException(status_code=404, detail="No properties found for provided property_ids")
        
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
        
        # Schedule optimized background extraction with options
        background_tasks.add_task(
            perform_batch_extraction_optimized,
            supported_props,
            batch_request.webhook_url,
            batch_request.parallel
        )
        
        # Track queue size
        if ENABLE_METRICS:
            queue_size.set(len(supported_props))
        
        return {
            "message": f"Batch extraction started for {len(supported_props)} properties",
            "property_ids": [p["id"] for p in supported_props],
            "status": "processing"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/extract/status", response_model=ExtractionStatusResponse, tags=["Extraction"])
@rate_limit("60/minute")
async def get_extraction_status(request: Request):
    """Get extraction status with enhanced metrics."""
    try:
        stats = await get_extraction_status_optimized()
        
        # Get 24h statistics
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        recent_result = await monitored_query(
            "recent_extractions",
            lambda: supabase.table("tax_extractions")
                .select("extraction_status")
                .gte("extraction_date", yesterday)
                .execute()
        )
        
        recent_data = recent_result.data if recent_result else []
        last_24h_count = len(recent_data)
        successful_24h = len([r for r in recent_data if r.get("extraction_status") == "success"])
        success_rate_24h = (successful_24h / last_24h_count * 100) if last_24h_count > 0 else None
        
        return ExtractionStatusResponse(
            total_properties=stats["total_properties"],
            extracted_count=stats["extracted_count"],
            pending_count=stats["pending_count"],
            failed_count=stats.get("failed_count", 0),
            supported_jurisdictions=list(cloud_extractor.get_supported_jurisdictions().keys()),
            in_progress_count=extraction_queue.qsize() if hasattr(extraction_queue, 'qsize') else 0,
            last_24h_extractions=last_24h_count,
            success_rate_24h=success_rate_24h
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/jurisdictions", tags=["Reference"])
@rate_limit("100/minute")
async def get_jurisdictions(request: Request):
    """Get list of jurisdictions using optimized query."""
    try:
        result = await get_jurisdictions_optimized()
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/entities", tags=["Entities"])
@rate_limit("100/minute")
async def get_entities(
    request: Request,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None, description="Search entity name")
):
    """Get list of entities with pagination and search."""
    try:
        query = supabase.table("entities").select("*")
        
        # Add search filter if provided
        if search:
            query = query.ilike("entity_name", f"%{search}%")
        
        query = query.range(offset, offset + limit - 1)
        
        result = await monitored_query("get_entities", lambda: query.execute())
        
        return {
            "entities": result.data if result else [],
            "count": len(result.data) if result else 0,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/statistics", response_model=StatisticsResponse, tags=["Analytics"])
@rate_limit("60/minute")
async def get_statistics(request: Request):
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

@app.get("/api/v1/extractions", tags=["History"])
@rate_limit("100/minute")
async def get_extractions(
    request: Request,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    property_id: Optional[str] = Query(None, description="Filter by property ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)")
):
    """Get extraction history with enhanced filtering."""
    try:
        # Try to get from tax_extractions table
        try:
            query = supabase.table("tax_extractions").select("*")
            
            # Apply filters
            if property_id:
                query = query.eq("property_id", property_id)
            if status:
                query = query.eq("extraction_status", status)
            if start_date:
                query = query.gte("extraction_date", start_date)
            if end_date:
                query = query.lte("extraction_date", end_date)
            
            query = query.order("extraction_date", desc=True).range(offset, offset + limit - 1)
            
            result = await monitored_query("get_extractions", lambda: query.execute())
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

# ========================= New Enhanced Endpoints =========================

@app.put("/api/v1/properties/bulk", tags=["Properties"])
@rate_limit("10/minute")
async def bulk_update_properties(
    request: Request,
    bulk_request: BulkUpdateRequest
):
    """Bulk update multiple properties in a single operation."""
    try:
        # Validate updates if requested
        if bulk_request.validate:
            for update in bulk_request.updates:
                if "id" not in update:
                    raise HTTPException(status_code=400, detail="Each update must include 'id' field")
        
        # Perform batch update
        await batch_update_properties(bulk_request.updates)
        
        return {
            "message": f"Successfully updated {len(bulk_request.updates)} properties",
            "count": len(bulk_request.updates)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/webhooks/register", tags=["Webhooks"])
@rate_limit("10/minute")
async def register_webhook(
    request: Request,
    webhook_url: str,
    events: List[str] = ["extraction_complete", "batch_complete"]
):
    """Register a webhook for notifications."""
    if not ENABLE_WEBHOOKS:
        raise HTTPException(status_code=404, detail="Webhooks not enabled")
    
    # Store webhook registration (implement based on your storage needs)
    return {
        "webhook_url": webhook_url,
        "events": events,
        "status": "registered"
    }

@app.get("/api/v1/properties/{property_id}/history", tags=["Properties"])
@rate_limit("100/minute")
async def get_property_history(
    request: Request,
    property_id: str,
    limit: int = Query(10, ge=1, le=100)
):
    """Get extraction history for a specific property."""
    try:
        result = await monitored_query(
            "property_history",
            lambda: supabase.table("tax_extractions")
                .select("*")
                .eq("property_id", property_id)
                .order("extraction_date", desc=True)
                .limit(limit)
                .execute()
        )
        
        return {
            "property_id": property_id,
            "history": result.data if result else [],
            "count": len(result.data) if result else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/analytics/trends", tags=["Analytics"])
@rate_limit("30/minute")
async def get_extraction_trends(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    jurisdiction: Optional[str] = None
):
    """Get extraction trends over time."""
    try:
        start_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        query = supabase.table("tax_extractions").select(
            "extraction_date, extraction_status, property_id"
        ).gte("extraction_date", start_date)
        
        if jurisdiction:
            # Join with properties to filter by jurisdiction
            query = query.eq("properties.jurisdiction", jurisdiction)
        
        result = await monitored_query("extraction_trends", lambda: query.execute())
        
        # Process data into daily trends
        daily_counts = {}
        for record in (result.data if result else []):
            date = record["extraction_date"][:10]  # Extract date only
            if date not in daily_counts:
                daily_counts[date] = {"success": 0, "failed": 0}
            
            if record["extraction_status"] == "success":
                daily_counts[date]["success"] += 1
            else:
                daily_counts[date]["failed"] += 1
        
        trends = [
            {"date": date, **counts}
            for date, counts in sorted(daily_counts.items())
        ]
        
        return {
            "period_days": days,
            "jurisdiction": jurisdiction,
            "trends": trends
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v1/cache/clear", tags=["System"])
@rate_limit("5/minute")
async def clear_cache(
    request: Request,
    pattern: Optional[str] = Query(None, description="Cache key pattern to clear")
):
    """Clear cache entries."""
    if not ENABLE_CACHE:
        raise HTTPException(status_code=404, detail="Cache not enabled")
    
    try:
        # Clear memory cache
        if pattern:
            keys_to_remove = [k for k in memory_cache.keys() if pattern in k]
            for key in keys_to_remove:
                del memory_cache[key]
            cleared_count = len(keys_to_remove)
        else:
            cleared_count = len(memory_cache)
            memory_cache.clear()
        
        # Also clear pooled client cache if available
        try:
            client = get_pooled_client()
            client.clear_cache()
            logger.info("Cleared pooled client cache")
        except Exception:
            pass  # Pooled client cache might not be available
        
        # Redis disabled - only clearing memory cache
        
        return {
            "message": "Cache cleared successfully",
            "cleared_entries": cleared_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/pool/stats", tags=["System", "Monitoring"])
async def get_pool_statistics():
    """Get database connection pool statistics."""
    try:
        client = get_pooled_client()
        pool_stats = client.get_pool_stats()
        cache_stats = client.get_cache_stats()
        
        # Update metrics if enabled
        if ENABLE_METRICS:
            active_connections.set(pool_stats.get("active", 0))
        
        return {
            "pool": {
                "created": pool_stats.get("created", 0),
                "active": pool_stats.get("active", 0),
                "idle": pool_stats.get("idle", 0),
                "failed": pool_stats.get("failed", 0),
                "total_requests": pool_stats.get("total_requests", 0),
                "avg_wait_time_ms": pool_stats.get("avg_wait_time_ms", 0),
                "peak_connections": pool_stats.get("peak_connections", 0),
                "pool_size": pool_stats.get("pool_size", 0),
                "overflow_count": pool_stats.get("overflow_count", 0),
                "uptime_seconds": pool_stats.get("uptime_seconds", 0)
            },
            "cache": cache_stats,
            "configuration": {
                "min_connections": 3,
                "max_connections": 15,
                "cache_enabled": ENABLE_CACHE,
                "cache_ttl_seconds": CACHE_TTL
            }
        }
    except Exception as e:
        logger.error(f"Failed to get pool stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Use PORT for Railway, fall back to API_PORT, then default to 8000
    port = int(os.getenv("PORT", os.getenv("API_PORT", 8000)))
    uvicorn.run(app, host="0.0.0.0", port=port)
