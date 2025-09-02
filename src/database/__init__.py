"""Database Module - Supabase Integration"""

from .supabase_client import SupabasePropertyTaxClient
from .supabase_auth import SupabaseAuthManager
from .pooled_supabase_client import (
    PooledSupabasePropertyTaxClient,
    AsyncPooledSupabaseClient,
    create_pooled_client,
    create_async_pooled_client
)
from .supabase_pool import (
    SupabaseConnectionPool,
    AsyncSupabaseConnectionPool,
    get_sync_pool,
    get_async_pool
)

__all__ = [
    'SupabasePropertyTaxClient',
    'SupabaseAuthManager',
    'PooledSupabasePropertyTaxClient',
    'AsyncPooledSupabaseClient',
    'create_pooled_client',
    'create_async_pooled_client',
    'SupabaseConnectionPool',
    'AsyncSupabaseConnectionPool',
    'get_sync_pool',
    'get_async_pool'
]