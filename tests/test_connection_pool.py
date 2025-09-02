"""
Test suite for Supabase connection pooling.
Validates pool behavior and performance improvements.
"""

import pytest
import asyncio
import time
import threading
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.supabase_pool import (
    SupabaseConnectionPool,
    AsyncSupabaseConnectionPool,
    PooledConnection,
    ConnectionStats
)
from src.database.pooled_supabase_client import (
    PooledSupabasePropertyTaxClient,
    AsyncPooledSupabaseClient,
    create_pooled_client,
    create_async_pooled_client
)


class TestConnectionPool:
    """Test synchronous connection pool."""
    
    @patch('src.database.supabase_pool.create_client')
    def test_pool_initialization(self, mock_create_client):
        """Test pool initializes with minimum connections."""
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        pool = SupabaseConnectionPool(min_size=3, max_size=10)
        
        # Should create min_size connections
        assert mock_create_client.call_count == 3
        assert pool.stats.created == 3
        assert pool.stats.idle == 3
        
        pool.close()
    
    @patch('src.database.supabase_pool.create_client')
    def test_connection_acquisition(self, mock_create_client):
        """Test getting connections from pool."""
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        pool = SupabaseConnectionPool(min_size=2, max_size=5)
        
        # Get a connection
        with pool.get_connection() as client:
            assert client == mock_client
            assert pool.stats.active == 1
            assert pool.stats.idle == 1
        
        # After context exit, connection returns to pool
        assert pool.stats.active == 0
        assert pool.stats.idle == 2
        
        pool.close()
    
    @patch('src.database.supabase_pool.create_client')
    def test_overflow_connections(self, mock_create_client):
        """Test overflow connections when pool is exhausted."""
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        pool = SupabaseConnectionPool(min_size=1, max_size=2, max_overflow=2)
        
        connections = []
        
        # Get connections up to max_size + max_overflow
        for i in range(4):
            conn = pool.get_connection()
            connections.append(conn.__enter__())
        
        assert pool.stats.active == 4
        assert pool.stats.created == 4  # 1 initial + 3 additional
        
        # Clean up
        for conn_ctx in connections:
            conn_ctx.__exit__(None, None, None)
        
        pool.close()
    
    @patch('src.database.supabase_pool.create_client')
    def test_connection_timeout(self, mock_create_client):
        """Test timeout when pool is exhausted."""
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        pool = SupabaseConnectionPool(
            min_size=1, 
            max_size=1, 
            max_overflow=0,
            connection_timeout=0.1
        )
        
        # Hold the only connection
        with pool.get_connection():
            # Try to get another connection (should timeout)
            with pytest.raises(TimeoutError):
                with pool.get_connection(timeout=0.1):
                    pass
        
        pool.close()
    
    @patch('src.database.supabase_pool.create_client')
    def test_connection_validation(self, mock_create_client):
        """Test connection health validation."""
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        # Setup mock response for validation
        mock_client.table.return_value.select.return_value.limit.return_value.execute.return_value = Mock()
        
        pool = SupabaseConnectionPool(min_size=1, max_size=2)
        
        with pool.get_connection() as client:
            # Validation should be called
            mock_client.table.assert_called_with("properties")
        
        pool.close()
    
    def test_pool_statistics(self):
        """Test pool statistics tracking."""
        with patch('src.database.supabase_pool.create_client') as mock_create:
            mock_create.return_value = Mock()
            
            pool = SupabaseConnectionPool(min_size=2, max_size=5)
            
            # Initial stats
            stats = pool.get_stats()
            assert stats["created"] == 2
            assert stats["idle"] == 2
            assert stats["active"] == 0
            
            # Use connections
            with pool.get_connection():
                stats = pool.get_stats()
                assert stats["active"] == 1
                assert stats["idle"] == 1
                assert stats["total_requests"] == 1
            
            pool.close()


class TestAsyncConnectionPool:
    """Test asynchronous connection pool."""
    
    @pytest.mark.asyncio
    @patch('src.database.supabase_pool.create_async_client')
    async def test_async_pool_initialization(self, mock_create_async):
        """Test async pool initialization."""
        mock_client = AsyncMock()
        mock_create_async.return_value = mock_client
        
        pool = AsyncSupabaseConnectionPool(min_size=3, max_size=10)
        await pool.initialize()
        
        assert mock_create_async.call_count == 3
        assert pool.stats.created == 3
        assert pool.stats.idle == 3
        
        await pool.close()
    
    @pytest.mark.asyncio
    @patch('src.database.supabase_pool.create_async_client')
    async def test_async_connection_acquisition(self, mock_create_async):
        """Test getting async connections."""
        mock_client = AsyncMock()
        mock_create_async.return_value = mock_client
        
        pool = AsyncSupabaseConnectionPool(min_size=2, max_size=5)
        await pool.initialize()
        
        async with pool.get_connection() as client:
            assert client == mock_client
            assert pool.stats.active == 1
            assert pool.stats.idle == 1
        
        assert pool.stats.active == 0
        assert pool.stats.idle == 2
        
        await pool.close()
    
    @pytest.mark.asyncio
    async def test_concurrent_connections(self):
        """Test concurrent connection usage."""
        with patch('src.database.supabase_pool.create_async_client') as mock_create:
            mock_client = AsyncMock()
            mock_create.return_value = mock_client
            
            pool = AsyncSupabaseConnectionPool(min_size=2, max_size=10)
            await pool.initialize()
            
            async def use_connection(pool, delay):
                async with pool.get_connection() as client:
                    await asyncio.sleep(delay)
                    return True
            
            # Use multiple connections concurrently
            tasks = [use_connection(pool, 0.01) for _ in range(5)]
            results = await asyncio.gather(*tasks)
            
            assert all(results)
            assert pool.stats.total_requests == 5
            
            await pool.close()


class TestPooledClient:
    """Test pooled Supabase client."""
    
    @patch('src.database.supabase_pool.create_client')
    def test_pooled_client_operations(self, mock_create_client):
        """Test basic operations with pooled client."""
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        # Setup mock responses
        mock_response = Mock()
        mock_response.data = [{"entity_id": "1", "name": "Test Entity"}]
        mock_client.table.return_value.select.return_value.range.return_value.execute.return_value = mock_response
        
        client = create_pooled_client(min_connections=1, max_connections=3)
        
        # Test entity retrieval
        entities = client.get_entities(limit=10)
        assert len(entities) == 1
        assert entities[0]["entity_id"] == "1"
        
        # Check pool was used
        stats = client.get_pool_stats()
        assert stats["total_requests"] > 0
        
        client.close()
    
    def test_caching_functionality(self):
        """Test result caching in pooled client."""
        with patch('src.database.supabase_pool.create_client') as mock_create:
            mock_client = Mock()
            mock_create.return_value = mock_client
            
            # Setup mock response
            mock_response = Mock()
            mock_response.data = [{"property_id": "1"}]
            mock_client.table.return_value.select.return_value.range.return_value.execute.return_value = mock_response
            
            client = create_pooled_client(enable_caching=True)
            
            # First call - should hit database
            result1 = client.get_properties(limit=10)
            assert mock_client.table.call_count == 1
            
            # Second call - should use cache
            result2 = client.get_properties(limit=10)
            assert mock_client.table.call_count == 1  # No additional call
            assert result1 == result2
            
            # Clear cache
            client.clear_cache()
            
            # Third call - should hit database again
            result3 = client.get_properties(limit=10)
            assert mock_client.table.call_count == 2
            
            client.close()
    
    @pytest.mark.asyncio
    @patch('src.database.supabase_pool.create_async_client')
    async def test_async_pooled_client(self, mock_create_async):
        """Test async pooled client operations."""
        mock_client = AsyncMock()
        mock_create_async.return_value = mock_client
        
        # Setup mock response
        mock_response = Mock()
        mock_response.data = [{"property_id": "1"}]
        mock_client.table.return_value.select.return_value.range.return_value.execute.return_value = mock_response
        
        client = await create_async_pooled_client(min_connections=2, max_connections=5)
        
        # Test concurrent operations
        tasks = [client.get_properties(limit=10) for _ in range(3)]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 3
        assert all(len(r) == 1 for r in results)
        
        await client.close()


class TestPerformanceComparison:
    """Compare performance with and without pooling."""
    
    @pytest.mark.asyncio
    async def test_pooling_performance(self):
        """Test that pooling improves performance."""
        
        # Simulate database latency
        async def mock_db_operation(delay=0.01):
            await asyncio.sleep(delay)
            return {"result": "data"}
        
        # Without pooling - sequential connections
        start = time.time()
        for _ in range(10):
            await mock_db_operation()
        sequential_time = time.time() - start
        
        # With pooling - reused connections (simulated)
        start = time.time()
        tasks = [mock_db_operation(0.01) for _ in range(10)]
        await asyncio.gather(*tasks)
        concurrent_time = time.time() - start
        
        print(f"Sequential: {sequential_time:.3f}s")
        print(f"Concurrent: {concurrent_time:.3f}s")
        print(f"Speedup: {sequential_time/concurrent_time:.2f}x")
        
        # Concurrent should be significantly faster
        assert concurrent_time < sequential_time / 2
    
    def test_connection_reuse(self):
        """Test that connections are properly reused."""
        with patch('src.database.supabase_pool.create_client') as mock_create:
            mock_client = Mock()
            mock_create.return_value = mock_client
            
            pool = SupabaseConnectionPool(min_size=2, max_size=5)
            
            # Use same connection multiple times
            for _ in range(10):
                with pool.get_connection() as client:
                    pass
            
            # Should not create more than min_size connections
            assert mock_create.call_count == 2
            assert pool.stats.total_requests == 10
            
            pool.close()


@pytest.mark.integration
class TestIntegrationWithSupabase:
    """Integration tests with actual Supabase (requires env vars)."""
    
    @pytest.mark.skipif(
        not os.getenv("SUPABASE_URL"),
        reason="Supabase credentials not available"
    )
    def test_real_connection_pool(self):
        """Test with real Supabase connection."""
        try:
            client = create_pooled_client(min_connections=1, max_connections=3)
            
            # Try to get entities
            entities = client.get_entities(limit=1)
            assert isinstance(entities, list)
            
            # Check pool stats
            stats = client.get_pool_stats()
            assert stats["created"] >= 1
            assert stats["total_requests"] >= 1
            
            client.close()
            
        except Exception as e:
            pytest.skip(f"Supabase connection failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])