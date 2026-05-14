"""
Caching utilities for AutoSRE V2.

Provides both in-memory and Redis-backed caching with TTL support,
namespacing, and async compatibility.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Generic, ParamSpec, TypeVar

from autosre.utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")
P = ParamSpec("P")


@dataclass
class CacheEntry(Generic[T]):
    """A cached value with metadata."""

    value: T
    created_at: float = field(default_factory=time.time)
    ttl: float | None = None
    hits: int = 0

    @property
    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl

    def touch(self) -> None:
        """Record a cache hit."""
        self.hits += 1


class Cache(ABC):
    """
    Abstract base class for cache implementations.

    Provides a consistent interface for different cache backends.
    """

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """Get a value from the cache."""
        ...

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Set a value in the cache."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a value from the cache."""
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a key exists in the cache."""
        ...

    @abstractmethod
    async def clear(self) -> None:
        """Clear all entries from the cache."""
        ...

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: float | None = None,
    ) -> Any:
        """
        Get a value from cache, or compute and cache it.

        Args:
            key: Cache key
            factory: Function to compute value if not cached
            ttl: Time-to-live in seconds

        Returns:
            Cached or computed value
        """
        value = await self.get(key)
        if value is not None:
            return value

        # Compute value
        if asyncio.iscoroutinefunction(factory):
            value = await factory()
        else:
            value = factory()

        await self.set(key, value, ttl)
        return value


class MemoryCache(Cache):
    """
    In-memory LRU cache with TTL support.

    Thread-safe for basic operations. Uses OrderedDict for LRU eviction.
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: float | None = 3600,
        prefix: str = "",
    ):
        """
        Initialize memory cache.

        Args:
            max_size: Maximum number of entries
            default_ttl: Default TTL in seconds (None for no expiry)
            prefix: Key prefix for namespacing
        """
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._prefix = prefix
        self._hits = 0
        self._misses = 0
        self._lock = asyncio.Lock()

    def _make_key(self, key: str) -> str:
        """Create full key with prefix."""
        return f"{self._prefix}{key}" if self._prefix else key

    async def get(self, key: str) -> Any | None:
        """Get a value from the cache."""
        full_key = self._make_key(key)

        async with self._lock:
            entry = self._cache.get(full_key)

            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired:
                del self._cache[full_key]
                self._misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(full_key)
            entry.touch()
            self._hits += 1
            return entry.value

    async def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Set a value in the cache."""
        full_key = self._make_key(key)
        effective_ttl = ttl if ttl is not None else self._default_ttl

        async with self._lock:
            # Remove if exists (will re-add at end)
            if full_key in self._cache:
                del self._cache[full_key]

            # Evict oldest if at capacity
            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)

            self._cache[full_key] = CacheEntry(value=value, ttl=effective_ttl)

    async def delete(self, key: str) -> bool:
        """Delete a value from the cache."""
        full_key = self._make_key(key)

        async with self._lock:
            if full_key in self._cache:
                del self._cache[full_key]
                return True
            return False

    async def exists(self, key: str) -> bool:
        """Check if a key exists and is not expired."""
        full_key = self._make_key(key)

        async with self._lock:
            entry = self._cache.get(full_key)
            if entry is None:
                return False
            if entry.is_expired:
                del self._cache[full_key]
                return False
            return True

    async def clear(self) -> None:
        """Clear all entries from the cache."""
        async with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    @property
    def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / (self._hits + self._misses) if (self._hits + self._misses) > 0 else 0,
        }

    async def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count of removed entries."""
        removed = 0
        async with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired
            ]
            for key in expired_keys:
                del self._cache[key]
                removed += 1
        return removed


class RedisCache(Cache):
    """
    Redis-backed cache with async support.

    Uses redis-py async client for non-blocking operations.
    """

    def __init__(
        self,
        url: str = "redis://localhost:6379/0",
        password: str | None = None,
        default_ttl: float | None = 3600,
        prefix: str = "autosre:",
    ):
        """
        Initialize Redis cache.

        Args:
            url: Redis connection URL
            password: Redis password
            default_ttl: Default TTL in seconds
            prefix: Key prefix for namespacing
        """
        self._url = url
        self._password = password
        self._default_ttl = default_ttl
        self._prefix = prefix
        self._client = None
        self._connected = False

    async def _ensure_connected(self) -> None:
        """Ensure Redis client is connected."""
        if self._client is None:
            try:
                import redis.asyncio as redis
                self._client = redis.from_url(
                    self._url,
                    password=self._password,
                    decode_responses=True,
                )
                await self._client.ping()
                self._connected = True
                logger.info("Connected to Redis", url=self._url)
            except ImportError:
                raise ImportError(
                    "redis package required for RedisCache. "
                    "Install with: pip install redis"
                )
            except Exception as e:
                logger.error("Failed to connect to Redis", error=str(e))
                raise

    def _make_key(self, key: str) -> str:
        """Create full key with prefix."""
        return f"{self._prefix}{key}"

    def _serialize(self, value: Any) -> str:
        """Serialize value for storage."""
        return json.dumps(value, default=str)

    def _deserialize(self, data: str | None) -> Any | None:
        """Deserialize stored value."""
        if data is None:
            return None
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return data

    async def get(self, key: str) -> Any | None:
        """Get a value from Redis."""
        await self._ensure_connected()
        full_key = self._make_key(key)
        try:
            data = await self._client.get(full_key)
            return self._deserialize(data)
        except Exception as e:
            logger.warning("Redis get failed", key=key, error=str(e))
            return None

    async def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Set a value in Redis."""
        await self._ensure_connected()
        full_key = self._make_key(key)
        effective_ttl = ttl if ttl is not None else self._default_ttl

        try:
            serialized = self._serialize(value)
            if effective_ttl:
                await self._client.setex(full_key, int(effective_ttl), serialized)
            else:
                await self._client.set(full_key, serialized)
        except Exception as e:
            logger.warning("Redis set failed", key=key, error=str(e))

    async def delete(self, key: str) -> bool:
        """Delete a value from Redis."""
        await self._ensure_connected()
        full_key = self._make_key(key)
        try:
            result = await self._client.delete(full_key)
            return result > 0
        except Exception as e:
            logger.warning("Redis delete failed", key=key, error=str(e))
            return False

    async def exists(self, key: str) -> bool:
        """Check if a key exists in Redis."""
        await self._ensure_connected()
        full_key = self._make_key(key)
        try:
            return await self._client.exists(full_key) > 0
        except Exception as e:
            logger.warning("Redis exists check failed", key=key, error=str(e))
            return False

    async def clear(self) -> None:
        """Clear all entries with the cache prefix."""
        await self._ensure_connected()
        try:
            pattern = f"{self._prefix}*"
            async for key in self._client.scan_iter(match=pattern):
                await self._client.delete(key)
        except Exception as e:
            logger.warning("Redis clear failed", error=str(e))

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None
            self._connected = False


def cache_key(*args: Any, **kwargs: Any) -> str:
    """
    Generate a cache key from function arguments.

    Creates a deterministic hash from the arguments.
    """
    key_data = json.dumps(
        {"args": args, "kwargs": kwargs},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(key_data.encode()).hexdigest()[:16]


def cached(
    cache: Cache,
    ttl: float | None = None,
    key_prefix: str = "",
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator for caching async function results.

    Args:
        cache: Cache instance to use
        ttl: Time-to-live in seconds
        key_prefix: Prefix for cache keys

    Usage:
        cache = MemoryCache()

        @cached(cache, ttl=300)
        async def fetch_metrics(query: str) -> dict:
            ...
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Generate cache key
            func_key = f"{key_prefix}{func.__name__}:{cache_key(*args, **kwargs)}"

            # Try to get from cache
            cached_value = await cache.get(func_key)
            if cached_value is not None:
                logger.debug("Cache hit", key=func_key)
                return cached_value

            # Compute and cache
            logger.debug("Cache miss", key=func_key)
            result = await func(*args, **kwargs)
            await cache.set(func_key, result, ttl)
            return result

        return wrapper
    return decorator
