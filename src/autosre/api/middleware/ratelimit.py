"""Rate limiting middleware for AutoSRE API."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from starlette.types import ASGIApp

logger = logging.getLogger("autosre.api")


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    remaining: int
    limit: int
    reset_at: float  # Unix timestamp
    retry_after: int | None = None  # Seconds until retry


class RateLimitBackend(ABC):
    """Abstract backend for rate limiting storage."""

    @abstractmethod
    async def check_and_increment(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        """Check rate limit and increment counter if allowed.

        Args:
            key: Unique key for the rate limit (e.g., user:123).
            limit: Maximum requests allowed in the window.
            window_seconds: Time window in seconds.

        Returns:
            RateLimitResult with check outcome.
        """
        ...

    @abstractmethod
    async def reset(self, key: str) -> None:
        """Reset rate limit for a key.

        Args:
            key: The rate limit key to reset.
        """
        ...


class InMemoryBackend(RateLimitBackend):
    """In-memory rate limiting backend.

    Suitable for single-instance deployments or development.
    For distributed systems, use RedisBackend.
    """

    def __init__(self) -> None:
        """Initialize in-memory storage."""
        self._storage: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def check_and_increment(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        """Check and increment rate limit counter.

        Uses sliding window algorithm for smooth rate limiting.
        """
        async with self._lock:
            now = time.time()
            window_start = now - window_seconds

            # Get or create window data
            if key not in self._storage:
                self._storage[key] = {"requests": [], "window_start": now}

            data = self._storage[key]

            # Remove expired requests
            data["requests"] = [
                ts for ts in data["requests"] if ts > window_start
            ]

            current_count = len(data["requests"])
            reset_at = now + window_seconds

            if current_count >= limit:
                # Rate limited
                oldest_request = min(data["requests"]) if data["requests"] else now
                retry_after = int(oldest_request + window_seconds - now) + 1

                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    limit=limit,
                    reset_at=reset_at,
                    retry_after=retry_after,
                )

            # Add request timestamp
            data["requests"].append(now)

            return RateLimitResult(
                allowed=True,
                remaining=limit - current_count - 1,
                limit=limit,
                reset_at=reset_at,
            )

    async def reset(self, key: str) -> None:
        """Reset rate limit for a key."""
        async with self._lock:
            self._storage.pop(key, None)


class RedisBackend(RateLimitBackend):
    """Redis-based rate limiting backend.

    Uses Redis for distributed rate limiting across multiple instances.
    Implements sliding window rate limiting using sorted sets.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        key_prefix: str = "ratelimit:",
    ) -> None:
        """Initialize Redis backend.

        Args:
            redis_url: Redis connection URL.
            key_prefix: Prefix for rate limit keys.
        """
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self._redis: Any = None

    async def _get_redis(self) -> Any:
        """Get or create Redis connection."""
        if self._redis is None:
            try:
                import redis.asyncio as redis
                self._redis = await redis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )
            except ImportError:
                raise ImportError(
                    "redis package required for RedisBackend. "
                    "Install with: pip install redis"
                )
        return self._redis

    async def check_and_increment(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        """Check and increment rate limit using Redis sorted set.

        Uses ZRANGEBYSCORE for sliding window implementation.
        """
        redis = await self._get_redis()
        full_key = f"{self.key_prefix}{key}"
        now = time.time()
        window_start = now - window_seconds

        # Use pipeline for atomic operations
        pipe = redis.pipeline()

        # Remove expired entries
        pipe.zremrangebyscore(full_key, 0, window_start)
        # Count current requests
        pipe.zcard(full_key)
        # Add new request
        pipe.zadd(full_key, {str(now): now})
        # Set expiry on key
        pipe.expire(full_key, window_seconds)

        results = await pipe.execute()
        current_count = results[1]  # Count before adding new request

        reset_at = now + window_seconds

        if current_count >= limit:
            # Rate limited - remove the request we just added
            await redis.zrem(full_key, str(now))

            # Find retry time
            oldest = await redis.zrange(full_key, 0, 0, withscores=True)
            retry_after = 1
            if oldest:
                oldest_time = oldest[0][1]
                retry_after = max(1, int(oldest_time + window_seconds - now) + 1)

            return RateLimitResult(
                allowed=False,
                remaining=0,
                limit=limit,
                reset_at=reset_at,
                retry_after=retry_after,
            )

        return RateLimitResult(
            allowed=True,
            remaining=limit - current_count - 1,
            limit=limit,
            reset_at=reset_at,
        )

    async def reset(self, key: str) -> None:
        """Reset rate limit for a key."""
        redis = await self._get_redis()
        await redis.delete(f"{self.key_prefix}{key}")


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""

    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 10  # Max requests per second


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Implement rate limiting per user/IP.

    Supports multiple rate limit windows and both user-based
    and IP-based limiting.
    """

    def __init__(
        self,
        app: ASGIApp,
        backend: RateLimitBackend | None = None,
        config: RateLimitConfig | None = None,
        exclude_paths: list[str] | None = None,
        key_func: Callable[[Request], str] | None = None,
    ) -> None:
        """Initialize rate limit middleware.

        Args:
            app: The ASGI application.
            backend: Rate limit storage backend.
            config: Rate limiting configuration.
            exclude_paths: Paths to exclude from rate limiting.
            key_func: Custom function to extract rate limit key from request.
        """
        super().__init__(app)
        self.backend = backend or InMemoryBackend()
        self.config = config or RateLimitConfig()
        self.exclude_paths = exclude_paths or ["/health", "/ready", "/metrics"]
        self.key_func = key_func or self._default_key_func

    def _default_key_func(self, request: Request) -> str:
        """Extract rate limit key from request.

        Uses user ID if authenticated, otherwise falls back to IP.
        """
        # Try to get user ID from authenticated user
        if hasattr(request.state, "user"):
            return f"user:{request.state.user.id}"

        # Fall back to IP address
        client_ip = self._get_client_ip(request)
        return f"ip:{client_ip}"

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request, handling proxies."""
        # Check for forwarded headers (when behind proxy)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Take first IP in chain
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Direct connection
        if request.client:
            return request.client.host

        return "unknown"

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Any],
    ) -> JSONResponse:
        """Check rate limits and process request.

        Args:
            request: The incoming request.
            call_next: The next middleware/handler in the chain.

        Returns:
            Response from handler or 429 error.
        """
        # Skip excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)

        key = self.key_func(request)

        # Check per-minute limit
        result = await self.backend.check_and_increment(
            key=f"{key}:minute",
            limit=self.config.requests_per_minute,
            window_seconds=60,
        )

        if not result.allowed:
            return self._rate_limit_response(result, "minute")

        # Check per-hour limit
        result_hour = await self.backend.check_and_increment(
            key=f"{key}:hour",
            limit=self.config.requests_per_hour,
            window_seconds=3600,
        )

        if not result_hour.allowed:
            return self._rate_limit_response(result_hour, "hour")

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(int(result.reset_at))

        return response

    def _rate_limit_response(
        self,
        result: RateLimitResult,
        window: str,
    ) -> JSONResponse:
        """Create 429 Too Many Requests response.

        Args:
            result: Rate limit check result.
            window: The window that was exceeded (minute/hour).

        Returns:
            JSON response with rate limit details.
        """
        logger.warning(
            f"Rate limit exceeded for {window} window",
            extra={
                "limit": result.limit,
                "reset_at": result.reset_at,
                "window": window,
            },
        )

        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": {
                    "message": f"Rate limit exceeded. Try again in {result.retry_after} seconds.",
                    "code": "RATE_LIMIT_EXCEEDED",
                    "details": {
                        "limit": result.limit,
                        "window": window,
                        "retry_after": result.retry_after,
                    },
                }
            },
            headers={
                "Retry-After": str(result.retry_after),
                "X-RateLimit-Limit": str(result.limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(result.reset_at)),
            },
        )


def rate_limit(
    requests: int = 10,
    window_seconds: int = 60,
    key_func: Callable[[Request], str] | None = None,
) -> Callable[..., Any]:
    """Decorator for route-specific rate limiting.

    Use this for fine-grained rate limiting on specific endpoints.

    Args:
        requests: Maximum requests allowed in the window.
        window_seconds: Time window in seconds.
        key_func: Custom function to extract rate limit key.

    Returns:
        FastAPI dependency.

    Example:
        @app.post("/expensive-operation")
        @rate_limit(requests=5, window_seconds=60)
        async def expensive_operation():
            ...
    """
    # Use in-memory backend for decorator-based limiting
    backend = InMemoryBackend()

    async def dependency(request: Request) -> None:
        if key_func:
            key = key_func(request)
        elif hasattr(request.state, "user"):
            key = f"user:{request.state.user.id}"
        elif request.client:
            key = f"ip:{request.client.host}"
        else:
            key = "unknown"

        result = await backend.check_and_increment(
            key=f"route:{request.url.path}:{key}",
            limit=requests,
            window_seconds=window_seconds,
        )

        if not result.allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "message": f"Rate limit exceeded. Try again in {result.retry_after} seconds.",
                    "retry_after": result.retry_after,
                },
                headers={"Retry-After": str(result.retry_after)},
            )

    return dependency
