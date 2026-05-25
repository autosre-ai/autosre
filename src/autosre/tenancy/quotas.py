"""
Resource Quotas and Rate Limiting

Enterprise-grade quota management and rate limiting for multi-tenant SaaS:
- Per-tenant resource quotas
- Per-workspace quotas with inheritance
- Token bucket rate limiting
- Usage tracking and enforcement
"""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

from autosre.tenancy.models import Tenant, TenantTier


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class QuotaType(str, Enum):
    """Types of quotas that can be enforced."""
    # Investigation limits
    INVESTIGATIONS_PER_DAY = "investigations_per_day"
    INVESTIGATIONS_PER_MONTH = "investigations_per_month"
    CONCURRENT_INVESTIGATIONS = "concurrent_investigations"
    
    # API limits
    API_CALLS_PER_HOUR = "api_calls_per_hour"
    API_CALLS_PER_DAY = "api_calls_per_day"
    WEBHOOK_CALLS_PER_HOUR = "webhook_calls_per_hour"
    
    # Resource limits
    WORKSPACES = "workspaces"
    TEAM_MEMBERS = "team_members"
    SERVICES_MONITORED = "services_monitored"
    RUNBOOKS = "runbooks"
    INTEGRATIONS = "integrations"
    
    # Data limits
    DATA_RETENTION_DAYS = "data_retention_days"
    STORAGE_GB = "storage_gb"
    LOG_RETENTION_DAYS = "log_retention_days"
    
    # LLM limits
    LLM_TOKENS_PER_DAY = "llm_tokens_per_day"
    LLM_TOKENS_PER_MONTH = "llm_tokens_per_month"


class QuotaLimit(BaseModel):
    """Definition of a quota limit."""
    
    quota_type: QuotaType
    limit: int = Field(..., description="Maximum allowed value, -1 for unlimited")
    period_seconds: Optional[int] = Field(
        None, 
        description="Reset period in seconds (None for static limits)"
    )
    
    # Override settings
    can_override: bool = Field(default=False, description="Can be overridden per-tenant")
    soft_limit: Optional[int] = Field(None, description="Warning threshold")
    
    @property
    def is_unlimited(self) -> bool:
        return self.limit == -1


class QuotaUsage(BaseModel):
    """Current usage against a quota."""
    
    tenant_id: str
    workspace_id: Optional[str] = None
    quota_type: QuotaType
    
    # Usage tracking
    current_value: int = Field(default=0)
    limit: int = Field(..., description="Current limit")
    
    # Period tracking
    period_start: datetime = Field(default_factory=utcnow)
    period_end: Optional[datetime] = None
    
    # History
    last_updated: datetime = Field(default_factory=utcnow)
    peak_value: int = Field(default=0, description="Peak usage in current period")
    
    @property
    def remaining(self) -> int:
        """Remaining quota."""
        if self.limit == -1:
            return float('inf')
        return max(0, self.limit - self.current_value)
    
    @property
    def usage_percentage(self) -> float:
        """Usage as percentage of limit."""
        if self.limit == -1 or self.limit == 0:
            return 0.0
        return (self.current_value / self.limit) * 100
    
    @property
    def is_exceeded(self) -> bool:
        """Check if quota is exceeded."""
        if self.limit == -1:
            return False
        return self.current_value >= self.limit


class QuotaExceededError(Exception):
    """Raised when a quota limit is exceeded."""
    
    def __init__(
        self, 
        quota_type: QuotaType, 
        current: int, 
        limit: int,
        tenant_id: str,
        retry_after: Optional[int] = None,
    ):
        self.quota_type = quota_type
        self.current = current
        self.limit = limit
        self.tenant_id = tenant_id
        self.retry_after = retry_after
        super().__init__(
            f"Quota exceeded for {quota_type.value}: {current}/{limit} for tenant {tenant_id}"
        )


# Default quota limits by tier
DEFAULT_TIER_QUOTAS: dict[TenantTier, dict[QuotaType, int]] = {
    TenantTier.FREE: {
        QuotaType.INVESTIGATIONS_PER_DAY: 10,
        QuotaType.INVESTIGATIONS_PER_MONTH: 100,
        QuotaType.CONCURRENT_INVESTIGATIONS: 1,
        QuotaType.API_CALLS_PER_HOUR: 1000,
        QuotaType.API_CALLS_PER_DAY: 10000,
        QuotaType.WORKSPACES: 1,
        QuotaType.TEAM_MEMBERS: 5,
        QuotaType.SERVICES_MONITORED: 10,
        QuotaType.RUNBOOKS: 20,
        QuotaType.INTEGRATIONS: 3,
        QuotaType.DATA_RETENTION_DAYS: 30,
        QuotaType.STORAGE_GB: 1,
        QuotaType.LLM_TOKENS_PER_DAY: 50000,
        QuotaType.LLM_TOKENS_PER_MONTH: 500000,
    },
    TenantTier.STARTER: {
        QuotaType.INVESTIGATIONS_PER_DAY: 50,
        QuotaType.INVESTIGATIONS_PER_MONTH: 500,
        QuotaType.CONCURRENT_INVESTIGATIONS: 3,
        QuotaType.API_CALLS_PER_HOUR: 10000,
        QuotaType.API_CALLS_PER_DAY: 100000,
        QuotaType.WORKSPACES: 3,
        QuotaType.TEAM_MEMBERS: 20,
        QuotaType.SERVICES_MONITORED: 50,
        QuotaType.RUNBOOKS: 100,
        QuotaType.INTEGRATIONS: 10,
        QuotaType.DATA_RETENTION_DAYS: 90,
        QuotaType.STORAGE_GB: 10,
        QuotaType.LLM_TOKENS_PER_DAY: 200000,
        QuotaType.LLM_TOKENS_PER_MONTH: 2000000,
    },
    TenantTier.PROFESSIONAL: {
        QuotaType.INVESTIGATIONS_PER_DAY: 200,
        QuotaType.INVESTIGATIONS_PER_MONTH: 2000,
        QuotaType.CONCURRENT_INVESTIGATIONS: 10,
        QuotaType.API_CALLS_PER_HOUR: 100000,
        QuotaType.API_CALLS_PER_DAY: 1000000,
        QuotaType.WORKSPACES: 10,
        QuotaType.TEAM_MEMBERS: 100,
        QuotaType.SERVICES_MONITORED: 200,
        QuotaType.RUNBOOKS: 500,
        QuotaType.INTEGRATIONS: 50,
        QuotaType.DATA_RETENTION_DAYS: 180,
        QuotaType.STORAGE_GB: 100,
        QuotaType.LLM_TOKENS_PER_DAY: 1000000,
        QuotaType.LLM_TOKENS_PER_MONTH: 10000000,
    },
    TenantTier.ENTERPRISE: {
        # -1 indicates unlimited
        QuotaType.INVESTIGATIONS_PER_DAY: -1,
        QuotaType.INVESTIGATIONS_PER_MONTH: -1,
        QuotaType.CONCURRENT_INVESTIGATIONS: -1,
        QuotaType.API_CALLS_PER_HOUR: -1,
        QuotaType.API_CALLS_PER_DAY: -1,
        QuotaType.WORKSPACES: -1,
        QuotaType.TEAM_MEMBERS: -1,
        QuotaType.SERVICES_MONITORED: -1,
        QuotaType.RUNBOOKS: -1,
        QuotaType.INTEGRATIONS: -1,
        QuotaType.DATA_RETENTION_DAYS: 365,
        QuotaType.STORAGE_GB: 1000,
        QuotaType.LLM_TOKENS_PER_DAY: -1,
        QuotaType.LLM_TOKENS_PER_MONTH: -1,
    },
}

# Custom tier inherits from Enterprise
DEFAULT_TIER_QUOTAS[TenantTier.CUSTOM] = DEFAULT_TIER_QUOTAS[TenantTier.ENTERPRISE].copy()


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    
    requests_per_second: float = 10.0
    burst_size: int = 20
    
    # Granularity
    per_tenant: bool = True
    per_workspace: bool = False
    per_user: bool = False
    per_endpoint: bool = False


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""
    
    capacity: float
    fill_rate: float  # Tokens per second
    tokens: float = field(init=False)
    last_update: float = field(init=False)
    
    def __post_init__(self):
        self.tokens = self.capacity
        self.last_update = time.monotonic()
    
    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens. Returns True if successful.
        """
        now = time.monotonic()
        elapsed = now - self.last_update
        
        # Refill tokens
        self.tokens = min(
            self.capacity,
            self.tokens + elapsed * self.fill_rate
        )
        self.last_update = now
        
        # Try to consume
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
    
    def wait_time(self, tokens: int = 1) -> float:
        """Calculate wait time until tokens are available."""
        if self.tokens >= tokens:
            return 0.0
        needed = tokens - self.tokens
        return needed / self.fill_rate


class RateLimiter:
    """
    Rate limiter using token bucket algorithm.
    
    Supports per-tenant, per-workspace, per-user, and per-endpoint limiting.
    """
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()
    
    def _get_key(
        self,
        tenant_id: str,
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        endpoint: Optional[str] = None,
    ) -> str:
        """Generate bucket key based on config."""
        parts = []
        if self.config.per_tenant:
            parts.append(f"t:{tenant_id}")
        if self.config.per_workspace and workspace_id:
            parts.append(f"w:{workspace_id}")
        if self.config.per_user and user_id:
            parts.append(f"u:{user_id}")
        if self.config.per_endpoint and endpoint:
            parts.append(f"e:{endpoint}")
        return ":".join(parts) if parts else "global"
    
    def _get_bucket(self, key: str) -> TokenBucket:
        """Get or create a token bucket."""
        if key not in self._buckets:
            self._buckets[key] = TokenBucket(
                capacity=self.config.burst_size,
                fill_rate=self.config.requests_per_second,
            )
        return self._buckets[key]
    
    async def acquire(
        self,
        tenant_id: str,
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        tokens: int = 1,
    ) -> bool:
        """
        Try to acquire rate limit tokens.
        
        Returns True if request is allowed, False if rate limited.
        """
        async with self._lock:
            key = self._get_key(tenant_id, workspace_id, user_id, endpoint)
            bucket = self._get_bucket(key)
            return bucket.consume(tokens)
    
    async def wait_and_acquire(
        self,
        tenant_id: str,
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        tokens: int = 1,
        max_wait: float = 30.0,
    ) -> bool:
        """
        Wait until tokens are available, up to max_wait seconds.
        """
        key = self._get_key(tenant_id, workspace_id, user_id, endpoint)
        
        start = time.monotonic()
        while True:
            async with self._lock:
                bucket = self._get_bucket(key)
                if bucket.consume(tokens):
                    return True
                wait_time = bucket.wait_time(tokens)
            
            elapsed = time.monotonic() - start
            if elapsed + wait_time > max_wait:
                return False
            
            await asyncio.sleep(min(wait_time, max_wait - elapsed))
    
    def get_retry_after(
        self,
        tenant_id: str,
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        endpoint: Optional[str] = None,
    ) -> float:
        """Get seconds until rate limit resets."""
        key = self._get_key(tenant_id, workspace_id, user_id, endpoint)
        bucket = self._get_bucket(key)
        return bucket.wait_time(1)
    
    def cleanup_old_buckets(self, max_age_seconds: float = 3600.0) -> int:
        """Remove buckets that haven't been used recently."""
        now = time.monotonic()
        to_remove = [
            key for key, bucket in self._buckets.items()
            if now - bucket.last_update > max_age_seconds
        ]
        for key in to_remove:
            del self._buckets[key]
        return len(to_remove)


class QuotaManager:
    """
    Manages quotas across tenants and workspaces.
    
    Provides:
    - Quota checking and enforcement
    - Usage tracking
    - Quota alerts and notifications
    """
    
    def __init__(
        self,
        storage_backend: Optional[Any] = None,
        alert_callback: Optional[Callable[[str, QuotaType, float], None]] = None,
    ):
        self.storage = storage_backend
        self.alert_callback = alert_callback
        
        # In-memory cache for fast checking
        self._usage_cache: dict[str, QuotaUsage] = {}
        self._custom_limits: dict[str, dict[QuotaType, int]] = {}
        
        # Alert thresholds
        self.warning_threshold = 0.8  # 80%
        self.critical_threshold = 0.95  # 95%
        
        # Rate limiters
        self._rate_limiters: dict[str, RateLimiter] = {}
    
    def _cache_key(
        self,
        tenant_id: str,
        quota_type: QuotaType,
        workspace_id: Optional[str] = None,
    ) -> str:
        """Generate cache key for quota usage."""
        if workspace_id:
            return f"{tenant_id}:{workspace_id}:{quota_type.value}"
        return f"{tenant_id}:{quota_type.value}"
    
    def get_limit(
        self,
        tenant: Tenant,
        quota_type: QuotaType,
        workspace_id: Optional[str] = None,
    ) -> int:
        """
        Get the limit for a specific quota.
        
        Checks custom limits first, then falls back to tier defaults.
        """
        # Check custom tenant limits
        if tenant.id in self._custom_limits:
            custom = self._custom_limits[tenant.id].get(quota_type)
            if custom is not None:
                return custom
        
        # Fall back to tier defaults
        tier_quotas = DEFAULT_TIER_QUOTAS.get(tenant.tier, {})
        return tier_quotas.get(quota_type, 0)
    
    def set_custom_limit(
        self,
        tenant_id: str,
        quota_type: QuotaType,
        limit: int,
    ) -> None:
        """Set a custom limit for a tenant (e.g., during sales negotiation)."""
        if tenant_id not in self._custom_limits:
            self._custom_limits[tenant_id] = {}
        self._custom_limits[tenant_id][quota_type] = limit
    
    async def get_usage(
        self,
        tenant_id: str,
        quota_type: QuotaType,
        workspace_id: Optional[str] = None,
    ) -> QuotaUsage:
        """Get current usage for a quota."""
        key = self._cache_key(tenant_id, quota_type, workspace_id)
        
        if key in self._usage_cache:
            usage = self._usage_cache[key]
            # Check if period needs reset
            if usage.period_end and utcnow() >= usage.period_end:
                usage.current_value = 0
                usage.period_start = utcnow()
                usage.peak_value = 0
        else:
            # Initialize new usage tracking
            usage = QuotaUsage(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                quota_type=quota_type,
                current_value=0,
                limit=0,  # Will be set by check_quota
            )
            self._usage_cache[key] = usage
        
        return usage
    
    async def check_quota(
        self,
        tenant: Tenant,
        quota_type: QuotaType,
        workspace_id: Optional[str] = None,
        requested: int = 1,
    ) -> QuotaUsage:
        """
        Check if a quota allows the requested operation.
        
        Raises QuotaExceededError if limit would be exceeded.
        Returns current usage if allowed.
        """
        limit = self.get_limit(tenant, quota_type, workspace_id)
        usage = await self.get_usage(tenant.id, quota_type, workspace_id)
        usage.limit = limit
        
        # Unlimited quota
        if limit == -1:
            return usage
        
        # Check if exceeded
        if usage.current_value + requested > limit:
            raise QuotaExceededError(
                quota_type=quota_type,
                current=usage.current_value,
                limit=limit,
                tenant_id=tenant.id,
            )
        
        return usage
    
    async def consume_quota(
        self,
        tenant: Tenant,
        quota_type: QuotaType,
        amount: int = 1,
        workspace_id: Optional[str] = None,
    ) -> QuotaUsage:
        """
        Consume quota after successful operation.
        
        Should be called after check_quota passes and operation succeeds.
        """
        usage = await self.get_usage(tenant.id, quota_type, workspace_id)
        limit = self.get_limit(tenant, quota_type, workspace_id)
        
        usage.current_value += amount
        usage.limit = limit
        usage.last_updated = utcnow()
        
        # Track peak
        if usage.current_value > usage.peak_value:
            usage.peak_value = usage.current_value
        
        # Send alerts if approaching limit
        if limit > 0:
            percentage = usage.usage_percentage
            if percentage >= self.critical_threshold * 100 and self.alert_callback:
                self.alert_callback(tenant.id, quota_type, percentage)
            elif percentage >= self.warning_threshold * 100 and self.alert_callback:
                self.alert_callback(tenant.id, quota_type, percentage)
        
        return usage
    
    async def release_quota(
        self,
        tenant: Tenant,
        quota_type: QuotaType,
        amount: int = 1,
        workspace_id: Optional[str] = None,
    ) -> QuotaUsage:
        """Release quota (e.g., when investigation completes)."""
        usage = await self.get_usage(tenant.id, quota_type, workspace_id)
        usage.current_value = max(0, usage.current_value - amount)
        usage.last_updated = utcnow()
        return usage
    
    async def get_all_usage(
        self,
        tenant: Tenant,
        workspace_id: Optional[str] = None,
    ) -> dict[QuotaType, QuotaUsage]:
        """Get usage for all quotas."""
        result = {}
        for quota_type in QuotaType:
            usage = await self.get_usage(tenant.id, quota_type, workspace_id)
            usage.limit = self.get_limit(tenant, quota_type, workspace_id)
            result[quota_type] = usage
        return result
    
    def get_rate_limiter(
        self,
        tenant: Tenant,
        config: Optional[RateLimitConfig] = None,
    ) -> RateLimiter:
        """Get or create rate limiter for a tenant."""
        if tenant.id not in self._rate_limiters:
            # Calculate rate based on tier
            tier_rates = {
                TenantTier.FREE: 10.0,
                TenantTier.STARTER: 50.0,
                TenantTier.PROFESSIONAL: 200.0,
                TenantTier.ENTERPRISE: 1000.0,
                TenantTier.CUSTOM: 1000.0,
            }
            
            if config is None:
                config = RateLimitConfig(
                    requests_per_second=tier_rates.get(tenant.tier, 10.0),
                    burst_size=int(tier_rates.get(tenant.tier, 10.0) * 2),
                )
            
            self._rate_limiters[tenant.id] = RateLimiter(config)
        
        return self._rate_limiters[tenant.id]
    
    async def check_rate_limit(
        self,
        tenant: Tenant,
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        endpoint: Optional[str] = None,
    ) -> bool:
        """Check if request is within rate limits."""
        limiter = self.get_rate_limiter(tenant)
        return await limiter.acquire(
            tenant.id,
            workspace_id,
            user_id,
            endpoint,
        )
