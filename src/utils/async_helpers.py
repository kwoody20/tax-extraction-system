"""
Async utility functions for non-blocking operations in extractors.
Provides async alternatives to time.sleep() and other blocking operations.
"""

import asyncio
import aiohttp
import time
from typing import Optional, Dict, Any, List, Callable
from functools import wraps
import random
from contextlib import asynccontextmanager


class AsyncRateLimiter:
    """Async rate limiter for API calls"""
    
    def __init__(self, requests_per_second: float = 1.0):
        self.rate_limit_seconds = 1.0 / requests_per_second
        self.last_request_time = 0
        self._lock = asyncio.Lock()
    
    async def wait_if_needed(self):
        """Wait if necessary to respect rate limit"""
        async with self._lock:
            current_time = time.time()
            elapsed = current_time - self.last_request_time
            
            if elapsed < self.rate_limit_seconds:
                await asyncio.sleep(self.rate_limit_seconds - elapsed)
            
            self.last_request_time = time.time()


class AsyncRetryHandler:
    """Async retry handler with exponential backoff"""
    
    def __init__(self, 
                 max_retries: int = 3,
                 base_delay: float = 1.0,
                 max_delay: float = 30.0,
                 exponential_base: float = 2.0,
                 jitter: bool = True):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
    
    async def execute_with_retry(self, 
                                  func: Callable,
                                  *args,
                                  **kwargs) -> Any:
        """Execute async function with retry logic"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    # Run sync function in executor
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(None, func, *args, **kwargs)
            
            except Exception as e:
                last_exception = e
                
                if attempt < self.max_retries:
                    delay = min(
                        self.base_delay * (self.exponential_base ** attempt),
                        self.max_delay
                    )
                    
                    if self.jitter:
                        delay *= (0.5 + random.random())
                    
                    await asyncio.sleep(delay)
                    continue
                
                raise last_exception


async def async_sleep(seconds: float, reason: str = None):
    """
    Async sleep with optional logging reason.
    Replaces time.sleep() for non-blocking delays.
    """
    if reason:
        print(f"Waiting {seconds}s: {reason}")
    await asyncio.sleep(seconds)


async def async_wait_with_timeout(condition: Callable,
                                   timeout: float = 30.0,
                                   poll_interval: float = 0.5,
                                   reason: str = None) -> bool:
    """
    Async wait for a condition to become true with timeout.
    
    Args:
        condition: Callable that returns True when condition is met
        timeout: Maximum wait time in seconds
        poll_interval: How often to check the condition
        reason: Optional description for logging
    
    Returns:
        True if condition was met, False if timeout
    """
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if asyncio.iscoroutinefunction(condition):
            if await condition():
                return True
        else:
            # Run sync function in executor
            loop = asyncio.get_event_loop()
            if await loop.run_in_executor(None, condition):
                return True
        
        await asyncio.sleep(poll_interval)
    
    if reason:
        print(f"Timeout waiting for: {reason}")
    return False


class AsyncBatchProcessor:
    """Process items in batches with async support"""
    
    def __init__(self, 
                 batch_size: int = 10,
                 delay_between_batches: float = 1.0):
        self.batch_size = batch_size
        self.delay_between_batches = delay_between_batches
    
    async def process_items(self,
                             items: List[Any],
                             processor: Callable,
                             concurrent: bool = True) -> List[Any]:
        """
        Process items in batches asynchronously.
        
        Args:
            items: List of items to process
            processor: Async function to process each item
            concurrent: Process items in batch concurrently
        
        Returns:
            List of processed results
        """
        results = []
        
        for i in range(0, len(items), self.batch_size):
            batch = items[i:i + self.batch_size]
            
            if concurrent:
                # Process batch items concurrently
                batch_results = await asyncio.gather(
                    *[processor(item) for item in batch],
                    return_exceptions=True
                )
            else:
                # Process batch items sequentially
                batch_results = []
                for item in batch:
                    try:
                        result = await processor(item)
                        batch_results.append(result)
                    except Exception as e:
                        batch_results.append(e)
            
            results.extend(batch_results)
            
            # Delay between batches except for the last one
            if i + self.batch_size < len(items):
                await asyncio.sleep(self.delay_between_batches)
        
        return results


@asynccontextmanager
async def async_timeout(seconds: float):
    """
    Async context manager for operations with timeout.
    
    Usage:
        async with async_timeout(10):
            await some_long_operation()
    """
    try:
        async with asyncio.timeout(seconds):
            yield
    except asyncio.TimeoutError:
        raise TimeoutError(f"Operation timed out after {seconds} seconds")


async def run_sync_in_async(sync_func: Callable, *args, **kwargs):
    """
    Run a synchronous function in an async context without blocking.
    
    Args:
        sync_func: Synchronous function to run
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function
    
    Returns:
        Function result
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, sync_func, *args, **kwargs)


class AsyncHTTPClient:
    """Async HTTP client with built-in retry and rate limiting"""
    
    def __init__(self,
                 rate_limiter: Optional[AsyncRateLimiter] = None,
                 retry_handler: Optional[AsyncRetryHandler] = None,
                 timeout: float = 30.0):
        self.rate_limiter = rate_limiter or AsyncRateLimiter()
        self.retry_handler = retry_handler or AsyncRetryHandler()
        self.timeout = timeout
        self._session = None
    
    async def __aenter__(self):
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()
    
    async def get(self, url: str, **kwargs) -> Dict[str, Any]:
        """Async GET request with rate limiting and retry"""
        await self.rate_limiter.wait_if_needed()
        
        async def _get():
            async with self._session.get(url, **kwargs) as response:
                response.raise_for_status()
                return await response.json()
        
        return await self.retry_handler.execute_with_retry(_get)
    
    async def post(self, url: str, **kwargs) -> Dict[str, Any]:
        """Async POST request with rate limiting and retry"""
        await self.rate_limiter.wait_if_needed()
        
        async def _post():
            async with self._session.post(url, **kwargs) as response:
                response.raise_for_status()
                return await response.json()
        
        return await self.retry_handler.execute_with_retry(_post)


def make_async(func: Callable) -> Callable:
    """
    Decorator to convert a synchronous function to async.
    Runs the sync function in a thread executor.
    """
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)
    
    return async_wrapper


async def parallel_map(func: Callable, items: List[Any], max_concurrent: int = 10) -> List[Any]:
    """
    Apply an async function to items in parallel with concurrency limit.
    
    Args:
        func: Async function to apply to each item
        items: List of items to process
        max_concurrent: Maximum concurrent executions
    
    Returns:
        List of results in the same order as input
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_item(item):
        async with semaphore:
            if asyncio.iscoroutinefunction(func):
                return await func(item)
            else:
                # Run sync function in executor
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, func, item)
    
    return await asyncio.gather(*[process_item(item) for item in items])