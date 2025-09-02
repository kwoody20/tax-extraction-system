"""
Enhanced Supabase client with connection pooling.
Drop-in replacement for the existing SupabasePropertyTaxClient with pooling support.
"""

import os
import asyncio
import pandas as pd
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date
from uuid import UUID
import json
import logging
from contextlib import contextmanager
from functools import wraps

from .supabase_pool import (
    get_sync_pool,
    get_async_pool,
    with_connection,
    async_with_connection,
    SupabaseConnectionPool,
    AsyncSupabaseConnectionPool
)

logger = logging.getLogger(__name__)


class PooledSupabasePropertyTaxClient:
    """
    Enhanced Supabase client with connection pooling.
    Drop-in replacement for SupabasePropertyTaxClient with better performance.
    """
    
    def __init__(self, 
                 pool: Optional[SupabaseConnectionPool] = None,
                 enable_caching: bool = True,
                 cache_ttl: int = 60):
        """
        Initialize pooled Supabase client.
        
        Args:
            pool: Optional connection pool instance (uses global if not provided)
            enable_caching: Enable result caching
            cache_ttl: Cache TTL in seconds
        """
        self.pool = pool or get_sync_pool()
        self.enable_caching = enable_caching
        self.cache_ttl = cache_ttl
        
        # Simple cache for frequently accessed data
        self._cache = {} if enable_caching else None
        self._cache_timestamps = {} if enable_caching else None
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid."""
        if not self.enable_caching or key not in self._cache_timestamps:
            return False
        
        age = (datetime.now() - self._cache_timestamps[key]).total_seconds()
        return age < self.cache_ttl
    
    def _get_from_cache(self, key: str) -> Optional[Any]:
        """Get data from cache if valid."""
        if self._is_cache_valid(key):
            logger.debug(f"Cache hit for key: {key}")
            return self._cache.get(key)
        return None
    
    def _set_cache(self, key: str, value: Any):
        """Set data in cache."""
        if self.enable_caching:
            self._cache[key] = value
            self._cache_timestamps[key] = datetime.now()
    
    # Entity Operations with Pooling
    
    def get_entities(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get all entities with pagination using pooled connection."""
        cache_key = f"entities_{limit}_{offset}"
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        
        with self.pool.get_connection() as client:
            response = client.table("entities").select("*").range(offset, offset + limit - 1).execute()
            result = response.data
            self._set_cache(cache_key, result)
            return result
    
    def get_entity(self, entity_id: str) -> Optional[Dict]:
        """Get a single entity by ID using pooled connection."""
        cache_key = f"entity_{entity_id}"
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        
        with self.pool.get_connection() as client:
            response = client.table("entities").select("*").eq("entity_id", entity_id).single().execute()
            result = response.data
            self._set_cache(cache_key, result)
            return result
    
    def create_entity(self, entity_data: Dict) -> Dict:
        """Create a new entity using pooled connection."""
        with self.pool.get_connection() as client:
            response = client.table("entities").insert(entity_data).execute()
            return response.data[0] if response.data else None
    
    def update_entity(self, entity_id: str, updates: Dict) -> Dict:
        """Update an existing entity using pooled connection."""
        # Invalidate cache
        if self.enable_caching:
            cache_key = f"entity_{entity_id}"
            if cache_key in self._cache:
                del self._cache[cache_key]
        
        with self.pool.get_connection() as client:
            response = client.table("entities").update(updates).eq("entity_id", entity_id).execute()
            return response.data[0] if response.data else None
    
    def upsert_entity(self, entity_data: Dict) -> Dict:
        """Insert or update an entity using pooled connection."""
        with self.pool.get_connection() as client:
            response = client.table("entities").upsert(entity_data).execute()
            return response.data[0] if response.data else None
    
    # Property Operations with Pooling
    
    def get_properties(self, limit: int = 100, offset: int = 0, filters: Optional[Dict] = None) -> List[Dict]:
        """Get properties with optional filters using pooled connection."""
        # Create cache key from parameters
        filter_str = json.dumps(filters, sort_keys=True) if filters else ""
        cache_key = f"properties_{limit}_{offset}_{filter_str}"
        
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        
        with self.pool.get_connection() as client:
            query = client.table("properties").select("*")
            
            if filters:
                if "state" in filters:
                    query = query.eq("state", filters["state"])
                if "jurisdiction" in filters:
                    query = query.eq("jurisdiction", filters["jurisdiction"])
                if "parent_entity_id" in filters:
                    query = query.eq("parent_entity_id", filters["parent_entity_id"])
            
            response = query.range(offset, offset + limit - 1).execute()
            result = response.data
            self._set_cache(cache_key, result)
            return result
    
    def get_property(self, property_id: str) -> Optional[Dict]:
        """Get a single property by ID using pooled connection."""
        cache_key = f"property_{property_id}"
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        
        with self.pool.get_connection() as client:
            response = client.table("properties").select("*").eq("property_id", property_id).single().execute()
            result = response.data
            self._set_cache(cache_key, result)
            return result
    
    def create_property(self, property_data: Dict) -> Dict:
        """Create a new property using pooled connection."""
        with self.pool.get_connection() as client:
            response = client.table("properties").insert(property_data).execute()
            return response.data[0] if response.data else None
    
    def update_property(self, property_id: str, updates: Dict) -> Dict:
        """Update an existing property using pooled connection."""
        # Invalidate cache
        if self.enable_caching:
            cache_key = f"property_{property_id}"
            if cache_key in self._cache:
                del self._cache[cache_key]
        
        with self.pool.get_connection() as client:
            response = client.table("properties").update(updates).eq("property_id", property_id).execute()
            return response.data[0] if response.data else None
    
    def upsert_property(self, property_data: Dict) -> Dict:
        """Insert or update a property using pooled connection."""
        with self.pool.get_connection() as client:
            response = client.rpc("upsert_property", property_data).execute()
            return response.data
    
    # Tax Extraction Operations with Pooling
    
    def record_extraction(self, extraction_data: Dict) -> Dict:
        """Record a tax extraction result using pooled connection."""
        with self.pool.get_connection() as client:
            response = client.rpc("record_extraction_result", extraction_data).execute()
            return response.data
    
    def get_extractions(self, 
                        property_id: Optional[str] = None,
                        limit: int = 100,
                        offset: int = 0) -> List[Dict]:
        """Get extraction history using pooled connection."""
        with self.pool.get_connection() as client:
            query = client.table("tax_extractions").select("*")
            
            if property_id:
                query = query.eq("property_id", property_id)
            
            response = query.range(offset, offset + limit - 1).order("extracted_at", desc=True).execute()
            return response.data
    
    # Batch Operations with Pooling
    
    def batch_upsert_properties(self, properties: List[Dict]) -> List[Dict]:
        """Batch upsert multiple properties using pooled connection."""
        results = []
        
        with self.pool.get_connection() as client:
            # Process in chunks to avoid overwhelming the connection
            chunk_size = 100
            for i in range(0, len(properties), chunk_size):
                chunk = properties[i:i + chunk_size]
                response = client.table("properties").upsert(chunk).execute()
                results.extend(response.data)
        
        return results
    
    def batch_record_extractions(self, extractions: List[Dict]) -> List[Dict]:
        """Batch record multiple extraction results using pooled connection."""
        results = []
        
        with self.pool.get_connection() as client:
            for extraction in extractions:
                try:
                    response = client.rpc("record_extraction_result", extraction).execute()
                    results.append(response.data)
                except Exception as e:
                    logger.error(f"Failed to record extraction: {e}")
                    results.append({"error": str(e), "data": extraction})
        
        return results
    
    # Statistics and Monitoring
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        return self.pool.get_stats()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self.enable_caching:
            return {"enabled": False}
        
        return {
            "enabled": True,
            "size": len(self._cache),
            "keys": list(self._cache.keys()),
            "ttl_seconds": self.cache_ttl
        }
    
    def clear_cache(self):
        """Clear the cache."""
        if self.enable_caching:
            self._cache.clear()
            self._cache_timestamps.clear()
            logger.info("Cache cleared")
    
    def close(self):
        """Close the connection pool."""
        self.pool.close()


class AsyncPooledSupabaseClient:
    """
    Async version of the pooled Supabase client.
    For use in async contexts like FastAPI endpoints.
    """
    
    def __init__(self, pool: Optional[AsyncSupabaseConnectionPool] = None):
        """Initialize async pooled client."""
        self.pool = pool
        self._initialized = False
    
    async def initialize(self):
        """Initialize the async pool if needed."""
        if not self._initialized:
            if self.pool is None:
                self.pool = await get_async_pool()
            self._initialized = True
    
    async def get_entities(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get entities asynchronously."""
        await self.initialize()
        
        async with self.pool.get_connection() as client:
            response = await client.table("entities").select("*").range(offset, offset + limit - 1).execute()
            return response.data
    
    async def get_properties(self, 
                            limit: int = 100, 
                            offset: int = 0,
                            filters: Optional[Dict] = None) -> List[Dict]:
        """Get properties asynchronously."""
        await self.initialize()
        
        async with self.pool.get_connection() as client:
            query = client.table("properties").select("*")
            
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            
            response = await query.range(offset, offset + limit - 1).execute()
            return response.data
    
    async def record_extraction(self, extraction_data: Dict) -> Dict:
        """Record extraction asynchronously."""
        await self.initialize()
        
        async with self.pool.get_connection() as client:
            response = await client.rpc("record_extraction_result", extraction_data).execute()
            return response.data
    
    async def batch_operations(self, operations: List[Dict]) -> List[Dict]:
        """Execute multiple operations concurrently."""
        await self.initialize()
        
        async def execute_operation(op):
            async with self.pool.get_connection() as client:
                table = op.get("table")
                action = op.get("action")
                data = op.get("data")
                
                if action == "select":
                    response = await client.table(table).select("*").execute()
                elif action == "insert":
                    response = await client.table(table).insert(data).execute()
                elif action == "update":
                    response = await client.table(table).update(data).execute()
                elif action == "upsert":
                    response = await client.table(table).upsert(data).execute()
                else:
                    raise ValueError(f"Unknown action: {action}")
                
                return response.data
        
        # Execute all operations concurrently
        results = await asyncio.gather(
            *[execute_operation(op) for op in operations],
            return_exceptions=True
        )
        
        return results
    
    async def get_pool_stats(self) -> Dict[str, Any]:
        """Get async pool statistics."""
        await self.initialize()
        return {
            "created": self.pool.stats.created,
            "active": self.pool.stats.active,
            "idle": self.pool.stats.idle,
            "failed": self.pool.stats.failed,
            "total_requests": self.pool.stats.total_requests,
            "avg_wait_time_ms": self.pool.stats.avg_wait_time * 1000,
            "peak_connections": self.pool.stats.peak_connections
        }
    
    async def close(self):
        """Close the async pool."""
        if self._initialized and self.pool:
            await self.pool.close()


# Factory functions for easy client creation

def create_pooled_client(
    min_connections: int = 2,
    max_connections: int = 10,
    enable_caching: bool = True
) -> PooledSupabasePropertyTaxClient:
    """
    Create a pooled Supabase client with optimal settings.
    
    Args:
        min_connections: Minimum pool size
        max_connections: Maximum pool size
        enable_caching: Enable result caching
    
    Returns:
        Configured pooled client
    """
    pool = SupabaseConnectionPool(
        min_size=min_connections,
        max_size=max_connections,
        max_overflow=5,
        idle_timeout=300,
        max_connection_age=3600
    )
    
    return PooledSupabasePropertyTaxClient(
        pool=pool,
        enable_caching=enable_caching,
        cache_ttl=60
    )


async def create_async_pooled_client(
    min_connections: int = 2,
    max_connections: int = 10
) -> AsyncPooledSupabaseClient:
    """
    Create an async pooled Supabase client.
    
    Args:
        min_connections: Minimum pool size
        max_connections: Maximum pool size
    
    Returns:
        Configured async pooled client
    """
    pool = AsyncSupabaseConnectionPool(
        min_size=min_connections,
        max_size=max_connections
    )
    await pool.initialize()
    
    client = AsyncPooledSupabaseClient(pool=pool)
    await client.initialize()
    
    return client