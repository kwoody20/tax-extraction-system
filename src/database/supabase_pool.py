"""
Supabase connection pooling implementation.
Manages multiple Supabase client connections for improved performance.
"""

import os
import asyncio
import time
import logging
from typing import Optional, Dict, Any, List, Callable
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import threading
from queue import Queue, Empty, Full
import weakref
from supabase import create_client, Client
from supabase.client import AsyncClient, create_async_client
from dotenv import load_dotenv
import httpx

load_dotenv()
logger = logging.getLogger(__name__)


@dataclass
class ConnectionStats:
    """Statistics for connection pool monitoring."""
    created: int = 0
    active: int = 0
    idle: int = 0
    failed: int = 0
    total_requests: int = 0
    total_wait_time: float = 0
    avg_wait_time: float = 0
    peak_connections: int = 0
    last_reset: datetime = field(default_factory=datetime.now)


@dataclass
class PooledConnection:
    """Wrapper for a pooled Supabase connection."""
    client: Client
    created_at: datetime
    last_used: datetime
    use_count: int = 0
    is_healthy: bool = True
    pool_ref: Optional[weakref.ref] = None
    
    def mark_used(self):
        """Mark connection as used."""
        self.last_used = datetime.now()
        self.use_count += 1
    
    def is_stale(self, max_age_seconds: int = 3600) -> bool:
        """Check if connection is too old."""
        age = (datetime.now() - self.created_at).total_seconds()
        return age > max_age_seconds
    
    def is_idle(self, idle_timeout_seconds: int = 300) -> bool:
        """Check if connection has been idle too long."""
        idle_time = (datetime.now() - self.last_used).total_seconds()
        return idle_time > idle_timeout_seconds


class SupabaseConnectionPool:
    """
    Thread-safe connection pool for Supabase clients.
    Manages connection lifecycle and provides health monitoring.
    """
    
    def __init__(self,
                 min_size: int = 2,
                 max_size: int = 10,
                 max_overflow: int = 5,
                 connection_timeout: float = 30.0,
                 idle_timeout: int = 300,
                 max_connection_age: int = 3600,
                 health_check_interval: int = 60):
        """
        Initialize connection pool.
        
        Args:
            min_size: Minimum number of connections to maintain
            max_size: Maximum number of persistent connections
            max_overflow: Additional connections that can be created under load
            connection_timeout: Timeout for acquiring a connection
            idle_timeout: Seconds before idle connections are closed
            max_connection_age: Maximum age of a connection in seconds
            health_check_interval: Seconds between health checks
        """
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")
        
        if not self.url or not self.key:
            raise ValueError("Supabase URL and Key must be set in environment variables")
        
        self.min_size = min_size
        self.max_size = max_size
        self.max_overflow = max_overflow
        self.connection_timeout = connection_timeout
        self.idle_timeout = idle_timeout
        self.max_connection_age = max_connection_age
        self.health_check_interval = health_check_interval
        
        # Connection storage
        self._pool = Queue(maxsize=max_size + max_overflow)
        self._overflow_connections = []
        self._lock = threading.RLock()
        
        # Statistics
        self.stats = ConnectionStats()
        
        # Health check thread
        self._health_check_thread = None
        self._stop_health_check = threading.Event()
        
        # Initialize pool
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize the connection pool with minimum connections."""
        logger.info(f"Initializing connection pool with min_size={self.min_size}")
        
        for _ in range(self.min_size):
            try:
                conn = self._create_connection()
                self._pool.put(conn, block=False)
                self.stats.idle += 1
            except Exception as e:
                logger.error(f"Failed to create initial connection: {e}")
                self.stats.failed += 1
        
        # Start health check thread
        self._start_health_check()
    
    def _create_connection(self) -> PooledConnection:
        """Create a new Supabase connection."""
        try:
            # Create client with custom timeout settings
            client = create_client(
                self.url, 
                self.key,
                options={
                    'auto_refresh_token': True,
                    'persist_session': True,
                    'detect_session_in_url': False,
                    'flow_type': 'implicit',
                    'timeout': self.connection_timeout
                }
            )
            
            conn = PooledConnection(
                client=client,
                created_at=datetime.now(),
                last_used=datetime.now(),
                pool_ref=weakref.ref(self)
            )
            
            self.stats.created += 1
            logger.debug(f"Created new connection (total: {self.stats.created})")
            
            return conn
            
        except Exception as e:
            logger.error(f"Failed to create connection: {e}")
            self.stats.failed += 1
            raise
    
    def _validate_connection(self, conn: PooledConnection) -> bool:
        """Validate that a connection is still healthy."""
        try:
            # Quick health check - try to fetch a single row
            conn.client.table("properties").select("property_id").limit(1).execute()
            return True
        except Exception as e:
            logger.warning(f"Connection validation failed: {e}")
            conn.is_healthy = False
            return False
    
    @contextmanager
    def get_connection(self, timeout: Optional[float] = None):
        """
        Get a connection from the pool (context manager).
        
        Usage:
            with pool.get_connection() as client:
                client.table("properties").select("*").execute()
        """
        timeout = timeout or self.connection_timeout
        conn = None
        wait_start = time.time()
        
        try:
            # Try to get from pool
            try:
                conn = self._pool.get(timeout=timeout)
                self.stats.idle -= 1
            except Empty:
                # Pool is empty, try to create overflow connection
                with self._lock:
                    current_total = self.stats.active + self.stats.idle
                    if current_total < self.max_size + self.max_overflow:
                        conn = self._create_connection()
                        self._overflow_connections.append(conn)
                    else:
                        raise TimeoutError(f"Connection pool exhausted (max: {self.max_size + self.max_overflow})")
            
            # Update statistics
            wait_time = time.time() - wait_start
            self.stats.total_wait_time += wait_time
            self.stats.total_requests += 1
            self.stats.avg_wait_time = self.stats.total_wait_time / self.stats.total_requests
            self.stats.active += 1
            
            # Update peak connections
            if self.stats.active > self.stats.peak_connections:
                self.stats.peak_connections = self.stats.active
            
            # Validate connection health
            if conn.is_stale(self.max_connection_age) or not self._validate_connection(conn):
                logger.info("Connection is stale or unhealthy, creating new one")
                conn = self._create_connection()
            
            conn.mark_used()
            
            # Yield the client
            yield conn.client
            
        finally:
            # Return connection to pool
            if conn:
                self.stats.active -= 1
                
                # Check if this was an overflow connection
                if conn in self._overflow_connections:
                    with self._lock:
                        self._overflow_connections.remove(conn)
                    # Don't return overflow connections to pool
                    logger.debug("Closing overflow connection")
                else:
                    # Return to pool if healthy and not full
                    try:
                        self._pool.put(conn, block=False)
                        self.stats.idle += 1
                    except Full:
                        logger.debug("Pool is full, discarding connection")
    
    def _start_health_check(self):
        """Start background thread for health checks."""
        def health_check_worker():
            while not self._stop_health_check.is_set():
                try:
                    self._perform_health_check()
                except Exception as e:
                    logger.error(f"Health check error: {e}")
                
                self._stop_health_check.wait(self.health_check_interval)
        
        self._health_check_thread = threading.Thread(
            target=health_check_worker,
            daemon=True,
            name="SupabasePoolHealthCheck"
        )
        self._health_check_thread.start()
        logger.info("Started health check thread")
    
    def _perform_health_check(self):
        """Perform health check on idle connections."""
        connections_to_check = []
        
        # Get all idle connections
        while True:
            try:
                conn = self._pool.get_nowait()
                connections_to_check.append(conn)
            except Empty:
                break
        
        healthy_connections = []
        removed_count = 0
        
        for conn in connections_to_check:
            # Check if connection is stale or idle
            if conn.is_stale(self.max_connection_age) or conn.is_idle(self.idle_timeout):
                logger.info(f"Removing stale/idle connection (age: {(datetime.now() - conn.created_at).total_seconds():.0f}s)")
                removed_count += 1
                self.stats.idle -= 1
            elif self._validate_connection(conn):
                healthy_connections.append(conn)
            else:
                logger.warning("Removing unhealthy connection")
                removed_count += 1
                self.stats.idle -= 1
        
        # Return healthy connections to pool
        for conn in healthy_connections:
            try:
                self._pool.put(conn, block=False)
            except Full:
                self.stats.idle -= 1
        
        # Ensure minimum connections
        current_size = self._pool.qsize()
        if current_size < self.min_size:
            for _ in range(self.min_size - current_size):
                try:
                    conn = self._create_connection()
                    self._pool.put(conn, block=False)
                    self.stats.idle += 1
                except Exception as e:
                    logger.error(f"Failed to create connection during health check: {e}")
        
        if removed_count > 0:
            logger.info(f"Health check completed: removed {removed_count} connections")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current pool statistics."""
        return {
            "created": self.stats.created,
            "active": self.stats.active,
            "idle": self.stats.idle,
            "failed": self.stats.failed,
            "total_requests": self.stats.total_requests,
            "avg_wait_time_ms": self.stats.avg_wait_time * 1000,
            "peak_connections": self.stats.peak_connections,
            "pool_size": self._pool.qsize(),
            "overflow_count": len(self._overflow_connections),
            "uptime_seconds": (datetime.now() - self.stats.last_reset).total_seconds()
        }
    
    def reset_stats(self):
        """Reset statistics."""
        self.stats = ConnectionStats(
            active=self.stats.active,
            idle=self.stats.idle
        )
    
    def close(self):
        """Close all connections and stop health checks."""
        logger.info("Closing connection pool")
        
        # Stop health check
        self._stop_health_check.set()
        if self._health_check_thread:
            self._health_check_thread.join(timeout=5)
        
        # Close all connections
        while True:
            try:
                conn = self._pool.get_nowait()
                # Supabase client doesn't have explicit close
                self.stats.idle -= 1
            except Empty:
                break
        
        # Close overflow connections
        with self._lock:
            self._overflow_connections.clear()
        
        logger.info("Connection pool closed")


class AsyncSupabaseConnectionPool:
    """
    Async connection pool for Supabase clients.
    Provides non-blocking connection management.
    """
    
    def __init__(self,
                 min_size: int = 2,
                 max_size: int = 10,
                 connection_timeout: float = 30.0):
        """Initialize async connection pool."""
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")
        
        if not self.url or not self.key:
            raise ValueError("Supabase URL and Key must be set")
        
        self.min_size = min_size
        self.max_size = max_size
        self.connection_timeout = connection_timeout
        
        self._pool: asyncio.Queue = None
        self._semaphore: asyncio.Semaphore = None
        self._lock = asyncio.Lock()
        self.stats = ConnectionStats()
        self._initialized = False
    
    async def initialize(self):
        """Initialize the async pool."""
        if self._initialized:
            return
        
        self._pool = asyncio.Queue(maxsize=self.max_size)
        self._semaphore = asyncio.Semaphore(self.max_size)
        
        # Create initial connections
        for _ in range(self.min_size):
            client = await self._create_async_connection()
            await self._pool.put(client)
            self.stats.idle += 1
        
        self._initialized = True
        logger.info(f"Initialized async pool with {self.min_size} connections")
    
    async def _create_async_connection(self) -> AsyncClient:
        """Create an async Supabase client."""
        try:
            # Custom HTTP client with connection pooling
            limits = httpx.Limits(
                max_keepalive_connections=5,
                max_connections=10,
                keepalive_expiry=30
            )
            
            timeout = httpx.Timeout(
                connect=10.0,
                read=30.0,
                write=30.0,
                pool=30.0
            )
            
            transport = httpx.AsyncHTTPTransport(
                limits=limits,
                retries=3
            )
            
            http_client = httpx.AsyncClient(
                transport=transport,
                timeout=timeout
            )
            
            client = await create_async_client(
                self.url,
                self.key,
                options={
                    'auto_refresh_token': True,
                    'persist_session': True,
                    'httpx_client': http_client
                }
            )
            
            self.stats.created += 1
            return client
            
        except Exception as e:
            logger.error(f"Failed to create async connection: {e}")
            self.stats.failed += 1
            raise
    
    @asynccontextmanager
    async def get_connection(self):
        """Get an async connection from the pool."""
        if not self._initialized:
            await self.initialize()
        
        client = None
        wait_start = time.time()
        
        async with self._semaphore:
            try:
                # Get connection with timeout
                client = await asyncio.wait_for(
                    self._pool.get(),
                    timeout=self.connection_timeout
                )
                
                self.stats.idle -= 1
                self.stats.active += 1
                
                # Update statistics
                wait_time = time.time() - wait_start
                self.stats.total_wait_time += wait_time
                self.stats.total_requests += 1
                self.stats.avg_wait_time = self.stats.total_wait_time / self.stats.total_requests
                
                # Update peak
                if self.stats.active > self.stats.peak_connections:
                    self.stats.peak_connections = self.stats.active
                
                yield client
                
            finally:
                if client:
                    self.stats.active -= 1
                    self.stats.idle += 1
                    await self._pool.put(client)
    
    async def close(self):
        """Close all async connections."""
        if not self._initialized:
            return
        
        while not self._pool.empty():
            try:
                client = self._pool.get_nowait()
                # Close HTTP client if it exists
                if hasattr(client, '_http_client'):
                    await client._http_client.aclose()
            except asyncio.QueueEmpty:
                break
        
        logger.info("Async connection pool closed")


# Global pool instances
_sync_pool: Optional[SupabaseConnectionPool] = None
_async_pool: Optional[AsyncSupabaseConnectionPool] = None


def get_sync_pool() -> SupabaseConnectionPool:
    """Get or create the global sync connection pool."""
    global _sync_pool
    if _sync_pool is None:
        _sync_pool = SupabaseConnectionPool(
            min_size=2,
            max_size=10,
            max_overflow=5
        )
    return _sync_pool


async def get_async_pool() -> AsyncSupabaseConnectionPool:
    """Get or create the global async connection pool."""
    global _async_pool
    if _async_pool is None:
        _async_pool = AsyncSupabaseConnectionPool(
            min_size=2,
            max_size=10
        )
        await _async_pool.initialize()
    return _async_pool


# Convenience functions
def with_connection(func: Callable) -> Callable:
    """Decorator to automatically provide a pooled connection."""
    def wrapper(*args, **kwargs):
        pool = get_sync_pool()
        with pool.get_connection() as client:
            return func(client, *args, **kwargs)
    return wrapper


def async_with_connection(func: Callable) -> Callable:
    """Async decorator to automatically provide a pooled connection."""
    async def wrapper(*args, **kwargs):
        pool = await get_async_pool()
        async with pool.get_connection() as client:
            return await func(client, *args, **kwargs)
    return wrapper