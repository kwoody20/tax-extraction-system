"""
Enhanced API with Supabase connection pooling.
This module shows how to integrate the pooled client into the existing API.
"""

import os
import asyncio
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel

# Import pooled clients
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.pooled_supabase_client import (
    create_pooled_client,
    create_async_pooled_client,
    PooledSupabasePropertyTaxClient,
    AsyncPooledSupabaseClient
)
from database.supabase_pool import get_sync_pool

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Global clients
pooled_client: Optional[PooledSupabasePropertyTaxClient] = None
async_client: Optional[AsyncPooledSupabaseClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle with connection pooling.
    """
    global pooled_client, async_client
    
    logger.info("Starting API with connection pooling...")
    
    # Initialize sync pooled client
    pooled_client = create_pooled_client(
        min_connections=3,
        max_connections=15,
        enable_caching=True
    )
    logger.info("Sync connection pool initialized")
    
    # Initialize async pooled client
    async_client = await create_async_pooled_client(
        min_connections=3,
        max_connections=15
    )
    logger.info("Async connection pool initialized")
    
    # Warm up the pools
    logger.info("Warming up connection pools...")
    
    # Sync pool warmup
    test_entities = pooled_client.get_entities(limit=1)
    logger.info(f"Sync pool test: Retrieved {len(test_entities)} entities")
    
    # Async pool warmup
    test_properties = await async_client.get_properties(limit=1)
    logger.info(f"Async pool test: Retrieved {len(test_properties)} properties")
    
    yield
    
    # Cleanup
    logger.info("Shutting down connection pools...")
    
    if pooled_client:
        pooled_client.close()
    
    if async_client:
        await async_client.close()
    
    logger.info("API shutdown complete")


# Create FastAPI app with lifespan
app = FastAPI(
    title="Tax Extraction API with Connection Pooling",
    version="2.0.0",
    lifespan=lifespan,
    default_response_class=ORJSONResponse
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


# Response models
class PoolStatsResponse(BaseModel):
    """Connection pool statistics response."""
    sync_pool: Dict[str, Any]
    async_pool: Dict[str, Any]
    cache_stats: Dict[str, Any]


class PropertyResponse(BaseModel):
    """Property response model."""
    property_id: str
    property_name: Optional[str]
    property_address: Optional[str]
    jurisdiction: Optional[str]
    state: Optional[str]


# API Endpoints using pooled connections

@app.get("/health")
async def health_check():
    """Enhanced health check with pool status."""
    try:
        # Check sync pool
        sync_stats = pooled_client.get_pool_stats() if pooled_client else None
        
        # Check async pool
        async_stats = await async_client.get_pool_stats() if async_client else None
        
        # Quick database check using pooled connection
        test_result = None
        if pooled_client:
            test_entities = pooled_client.get_entities(limit=1)
            test_result = len(test_entities) >= 0
        
        return {
            "status": "healthy",
            "database": "connected" if test_result else "unknown",
            "sync_pool": {
                "active": sync_stats.get("active", 0) if sync_stats else 0,
                "idle": sync_stats.get("idle", 0) if sync_stats else 0,
                "total_requests": sync_stats.get("total_requests", 0) if sync_stats else 0
            },
            "async_pool": {
                "active": async_stats.get("active", 0) if async_stats else 0,
                "idle": async_stats.get("idle", 0) if async_stats else 0
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/pool/stats", response_model=PoolStatsResponse)
async def get_pool_statistics():
    """Get detailed connection pool statistics."""
    try:
        sync_stats = pooled_client.get_pool_stats() if pooled_client else {}
        async_stats = await async_client.get_pool_stats() if async_client else {}
        cache_stats = pooled_client.get_cache_stats() if pooled_client else {}
        
        return PoolStatsResponse(
            sync_pool=sync_stats,
            async_pool=async_stats,
            cache_stats=cache_stats
        )
    except Exception as e:
        logger.error(f"Failed to get pool stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/properties")
async def get_properties(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    state: Optional[str] = None,
    jurisdiction: Optional[str] = None,
    entity_id: Optional[str] = None,
    use_async: bool = Query(True, description="Use async pool (recommended)")
):
    """
    Get properties using connection pooling.
    Demonstrates both sync and async pool usage.
    """
    try:
        filters = {}
        if state:
            filters["state"] = state
        if jurisdiction:
            filters["jurisdiction"] = jurisdiction
        if entity_id:
            filters["parent_entity_id"] = entity_id
        
        if use_async and async_client:
            # Use async pooled connection (recommended)
            properties = await async_client.get_properties(
                limit=limit,
                offset=offset,
                filters=filters
            )
        elif pooled_client:
            # Use sync pooled connection
            properties = pooled_client.get_properties(
                limit=limit,
                offset=offset,
                filters=filters
            )
        else:
            raise HTTPException(status_code=503, detail="No client available")
        
        return {
            "data": properties,
            "count": len(properties),
            "limit": limit,
            "offset": offset,
            "pool_type": "async" if use_async else "sync"
        }
        
    except Exception as e:
        logger.error(f"Failed to get properties: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/entities")
async def get_entities(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get entities using async pooled connection."""
    try:
        if async_client:
            entities = await async_client.get_entities(limit=limit, offset=offset)
        elif pooled_client:
            entities = pooled_client.get_entities(limit=limit, offset=offset)
        else:
            raise HTTPException(status_code=503, detail="No client available")
        
        return {
            "data": entities,
            "count": len(entities),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Failed to get entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/extract")
async def record_extraction(extraction_data: Dict[str, Any]):
    """Record extraction result using pooled connection."""
    try:
        if async_client:
            result = await async_client.record_extraction(extraction_data)
        elif pooled_client:
            result = pooled_client.record_extraction(extraction_data)
        else:
            raise HTTPException(status_code=503, detail="No client available")
        
        return {
            "status": "success",
            "data": result
        }
        
    except Exception as e:
        logger.error(f"Failed to record extraction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/batch/properties")
async def batch_upsert_properties(properties: List[Dict[str, Any]]):
    """Batch upsert properties using pooled connections."""
    try:
        if not properties:
            raise HTTPException(status_code=400, detail="No properties provided")
        
        # Use sync pooled client for batch operations
        # (async batch operations can be implemented if needed)
        if pooled_client:
            results = pooled_client.batch_upsert_properties(properties)
            
            return {
                "status": "success",
                "processed": len(results),
                "data": results
            }
        else:
            raise HTTPException(status_code=503, detail="No client available")
        
    except Exception as e:
        logger.error(f"Batch upsert failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/batch/operations")
async def batch_operations(operations: List[Dict[str, Any]]):
    """
    Execute multiple database operations concurrently.
    Demonstrates async pool's concurrent capabilities.
    """
    try:
        if not operations:
            raise HTTPException(status_code=400, detail="No operations provided")
        
        if async_client:
            results = await async_client.batch_operations(operations)
            
            # Count successes and failures
            successes = sum(1 for r in results if not isinstance(r, Exception))
            failures = sum(1 for r in results if isinstance(r, Exception))
            
            return {
                "status": "completed",
                "total": len(operations),
                "successes": successes,
                "failures": failures,
                "results": [
                    r if not isinstance(r, Exception) else {"error": str(r)}
                    for r in results
                ]
            }
        else:
            raise HTTPException(status_code=503, detail="Async client not available")
        
    except Exception as e:
        logger.error(f"Batch operations failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/pool/clear-cache")
async def clear_cache():
    """Clear the cache in pooled client."""
    try:
        if pooled_client:
            pooled_client.clear_cache()
            return {"status": "success", "message": "Cache cleared"}
        else:
            raise HTTPException(status_code=503, detail="Pooled client not available")
        
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/benchmark")
async def benchmark_pools():
    """
    Benchmark connection pool performance.
    Compares single connection vs pooled connections.
    """
    import time
    
    try:
        results = {}
        
        # Test pooled sync client
        if pooled_client:
            start = time.time()
            for _ in range(10):
                pooled_client.get_properties(limit=10)
            pooled_time = time.time() - start
            results["pooled_sync"] = {
                "time_seconds": pooled_time,
                "requests": 10,
                "avg_ms": (pooled_time / 10) * 1000
            }
        
        # Test pooled async client
        if async_client:
            start = time.time()
            tasks = [async_client.get_properties(limit=10) for _ in range(10)]
            await asyncio.gather(*tasks)
            async_time = time.time() - start
            results["pooled_async"] = {
                "time_seconds": async_time,
                "requests": 10,
                "avg_ms": (async_time / 10) * 1000
            }
        
        # Calculate improvement
        if "pooled_sync" in results and "pooled_async" in results:
            improvement = results["pooled_sync"]["time_seconds"] / results["pooled_async"]["time_seconds"]
            results["async_improvement"] = f"{improvement:.2f}x faster"
        
        # Add pool statistics
        if pooled_client:
            results["pool_stats"] = pooled_client.get_pool_stats()
        
        return results
        
    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)  # Run on different port for testing