"""Quota Manager for AutoSRE V2 Multi-Tenancy.

Provides comprehensive quota management including:
- Per-tenant resource quotas
- Usage tracking and reporting
- Quota enforcement and alerts
- Overage handling and rate limiting
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Awaitable
from uuid import uuid4

from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class QuotaType(str, Enum):
    """Types of quotas that can be enforced."""
    
    # User quotas
    MAX_USERS = "max_users"
    MAX_ROLES = "max_roles"
    MAX_API_KEYS = "max_api_keys"
    
    # Resource quotas
    MAX_CLUSTERS = "max_clusters"
    MAX_NAMESPACES = "max_namespaces"
    MAX_INTEGRATIONS = "max_integrations"
    MAX_RUNBOOKS = "max_runbooks"
    
    # Rate quotas (per period)
    ALERTS_PER_DAY = "alerts_per_day"
    ALERTS_PER_HOUR = "alerts_per_hour"
    INVESTIGATIONS_PER_DAY = "investigations_per_day"
    API_CALLS_PER_MINUTE = "api_calls_per_minute"
    API_CALLS_PER_HOUR = "api_calls_per_hour"
    
    # LLM quotas
    LLM_TOKENS_PER_MONTH = "llm_tokens_per_month"
    LLM_TOKENS_PER_DAY = "llm_tokens_per_day"
    LLM_CALLS_PER_INVESTIGATION = "llm_calls_per_investigation"
    
    # Storage quotas
    STORAGE_BYTES = "storage_bytes"
    RETENTION_DAYS = "retention_days"
    LOG_BYTES_PER_DAY = "log_bytes_per_day"


class QuotaPeriod(str, Enum):
    """Time periods for rate-based quotas."""
    
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    NONE = "none"  # For non-rate quotas


# Mapping of quota types to their periods
QUOTA_PERIODS: Dict[QuotaType, QuotaPeriod] = {
    QuotaType.MAX_USERS: QuotaPeriod.NONE,
    QuotaType.MAX_ROLES: QuotaPeriod.NONE,
    QuotaType.MAX_API_KEYS: QuotaPeriod.NONE,
    QuotaType.MAX_CLUSTERS: QuotaPeriod.NONE,
    QuotaType.MAX_NAMESPACES: QuotaPeriod.NONE,
    QuotaType.MAX_INTEGRATIONS: QuotaPeriod.NONE,
    QuotaType.MAX_RUNBOOKS: QuotaPeriod.NONE,
    QuotaType.ALERTS_PER_DAY: QuotaPeriod.DAY,
    QuotaType.ALERTS_PER_HOUR: QuotaPeriod.HOUR,
    QuotaType.INVESTIGATIONS_PER_DAY: QuotaPeriod.DAY,
    QuotaType.API_CALLS_PER_MINUTE: QuotaPeriod.MINUTE,
    QuotaType.API_CALLS_PER_HOUR: QuotaPeriod.HOUR,
    QuotaType.LLM_TOKENS_PER_MONTH: QuotaPeriod.MONTH,
    QuotaType.LLM_TOKENS_PER_DAY: QuotaPeriod.DAY,
    QuotaType.LLM_CALLS_PER_INVESTIGATION: QuotaPeriod.NONE,
    QuotaType.STORAGE_BYTES: QuotaPeriod.NONE,
    QuotaType.RETENTION_DAYS: QuotaPeriod.NONE,
    QuotaType.LOG_BYTES_PER_DAY: QuotaPeriod.DAY,
}


class QuotaAction(str, Enum):
    """Action to take when quota is exceeded."""
    
    BLOCK = "block"  # Block the operation
    WARN = "warn"  # Allow but warn
    THROTTLE = "throttle"  # Rate limit further operations
    OVERAGE = "overage"  # Allow with overage charges


class Quota(BaseModel):
    """A quota definition for a tenant."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    quota_type: QuotaType
    
    # Limits
    limit: int  # Maximum value
    warning_threshold: float = Field(default=0.8, ge=0, le=1)  # % to warn at
    
    # Action when exceeded
    action: QuotaAction = QuotaAction.BLOCK
    
    # Override behavior
    allow_temporary_override: bool = False
    override_limit: Optional[int] = None  # Higher limit for overrides
    override_expires_at: Optional[datetime] = None
    
    # Metadata
    enabled: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def period(self) -> QuotaPeriod:
        """Get the period for this quota type."""
        return QUOTA_PERIODS.get(self.quota_type, QuotaPeriod.NONE)
    
    @property
    def effective_limit(self) -> int:
        """Get effective limit considering overrides."""
        if self.override_limit and self.override_expires_at:
            if datetime.now(timezone.utc) < self.override_expires_at:
                return self.override_limit
        return self.limit
    
    @property
    def warning_limit(self) -> int:
        """Get the threshold for warnings."""
        return int(self.effective_limit * self.warning_threshold)


class QuotaUsage(BaseModel):
    """Current usage against a quota."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    quota_type: QuotaType
    
    # Current usage
    current_usage: int = 0
    
    # Period tracking
    period_start: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    period_end: Optional[datetime] = None
    
    # Statistics
    peak_usage: int = 0
    total_consumed: int = 0  # Total ever consumed (for rate quotas)
    times_exceeded: int = 0
    
    # Last update
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def record_usage(self, amount: int = 1) -> int:
        """Record usage and return new total.
        
        Args:
            amount: Amount to add
            
        Returns:
            New usage total
        """
        self.current_usage += amount
        self.total_consumed += amount
        self.last_updated = datetime.now(timezone.utc)
        
        if self.current_usage > self.peak_usage:
            self.peak_usage = self.current_usage
        
        return self.current_usage
    
    def reset(self) -> None:
        """Reset usage for new period."""
        self.current_usage = 0
        self.period_start = datetime.now(timezone.utc)
        self.period_end = None
        self.last_updated = datetime.now(timezone.utc)


class QuotaCheckResult(BaseModel):
    """Result of a quota check."""
    
    allowed: bool
    quota_type: QuotaType
    limit: int
    current_usage: int
    remaining: int
    percentage_used: float
    
    # Status
    at_warning: bool = False
    exceeded: bool = False
    
    # Action
    action: QuotaAction = QuotaAction.BLOCK
    message: Optional[str] = None
    
    # Retry info (for throttling)
    retry_after_seconds: Optional[int] = None


class QuotaAlert(BaseModel):
    """Alert generated when quota threshold is reached."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    quota_type: QuotaType
    
    # Alert details
    alert_type: str  # "warning", "exceeded", "reset"
    message: str
    current_usage: int
    limit: int
    percentage_used: float
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None


# Type for quota check hooks
QuotaHook = Callable[[str, QuotaType, QuotaCheckResult], Awaitable[None]]


class QuotaExceededError(Exception):
    """Raised when a quota is exceeded and action is BLOCK."""
    
    def __init__(
        self,
        message: str,
        tenant_id: str,
        quota_type: QuotaType,
        limit: int,
        current_usage: int,
        retry_after: Optional[int] = None,
    ):
        super().__init__(message)
        self.tenant_id = tenant_id
        self.quota_type = quota_type
        self.limit = limit
        self.current_usage = current_usage
        self.retry_after = retry_after


class QuotaManager:
    """
    Manages quotas and usage tracking for tenants.
    
    Provides:
    - Quota definition and management
    - Real-time usage tracking
    - Quota enforcement with configurable actions
    - Alerting on threshold breaches
    - Usage reporting and analytics
    
    Example:
        manager = QuotaManager()
        
        # Set quota for tenant
        await manager.set_quota(
            tenant_id="tenant-123",
            quota_type=QuotaType.ALERTS_PER_DAY,
            limit=1000,
        )
        
        # Check and increment
        result = await manager.check_and_increment(
            tenant_id="tenant-123",
            quota_type=QuotaType.ALERTS_PER_DAY,
        )
        
        if not result.allowed:
            raise QuotaExceededError(...)
        
        # Get usage report
        report = await manager.get_usage_report("tenant-123")
    """
    
    def __init__(
        self,
        on_warning: Optional[QuotaHook] = None,
        on_exceeded: Optional[QuotaHook] = None,
    ):
        """Initialize QuotaManager.
        
        Args:
            on_warning: Callback when warning threshold reached
            on_exceeded: Callback when quota exceeded
        """
        self._quotas: Dict[str, Dict[QuotaType, Quota]] = {}
        self._usage: Dict[str, Dict[QuotaType, QuotaUsage]] = {}
        self._alerts: List[QuotaAlert] = []
        self._on_warning = on_warning
        self._on_exceeded = on_exceeded
        self._lock = asyncio.Lock()
    
    async def set_quota(
        self,
        tenant_id: str,
        quota_type: QuotaType,
        limit: int,
        warning_threshold: float = 0.8,
        action: QuotaAction = QuotaAction.BLOCK,
    ) -> Quota:
        """Set a quota for a tenant.
        
        Args:
            tenant_id: Tenant ID
            quota_type: Type of quota
            limit: Maximum limit
            warning_threshold: Percentage at which to warn
            action: Action when exceeded
            
        Returns:
            Created quota
        """
        async with self._lock:
            if tenant_id not in self._quotas:
                self._quotas[tenant_id] = {}
            
            quota = Quota(
                tenant_id=tenant_id,
                quota_type=quota_type,
                limit=limit,
                warning_threshold=warning_threshold,
                action=action,
            )
            
            self._quotas[tenant_id][quota_type] = quota
            
            # Initialize usage if needed
            if tenant_id not in self._usage:
                self._usage[tenant_id] = {}
            if quota_type not in self._usage[tenant_id]:
                self._usage[tenant_id][quota_type] = QuotaUsage(
                    tenant_id=tenant_id,
                    quota_type=quota_type,
                )
            
            logger.info(
                "Set quota",
                tenant_id=tenant_id,
                quota_type=quota_type.value,
                limit=limit,
            )
            
            return quota
    
    async def set_quotas_from_config(
        self,
        tenant_id: str,
        config: Dict[QuotaType, int],
    ) -> List[Quota]:
        """Set multiple quotas from a configuration dict.
        
        Args:
            tenant_id: Tenant ID
            config: Dict of quota_type -> limit
            
        Returns:
            List of created quotas
        """
        quotas = []
        for quota_type, limit in config.items():
            quota = await self.set_quota(tenant_id, quota_type, limit)
            quotas.append(quota)
        return quotas
    
    async def get_quota(
        self,
        tenant_id: str,
        quota_type: QuotaType,
    ) -> Optional[Quota]:
        """Get a quota for a tenant."""
        tenant_quotas = self._quotas.get(tenant_id, {})
        return tenant_quotas.get(quota_type)
    
    async def get_all_quotas(
        self,
        tenant_id: str,
    ) -> List[Quota]:
        """Get all quotas for a tenant."""
        return list(self._quotas.get(tenant_id, {}).values())
    
    async def update_quota(
        self,
        tenant_id: str,
        quota_type: QuotaType,
        limit: Optional[int] = None,
        warning_threshold: Optional[float] = None,
        action: Optional[QuotaAction] = None,
        enabled: Optional[bool] = None,
    ) -> Quota:
        """Update an existing quota.
        
        Args:
            tenant_id: Tenant ID
            quota_type: Type of quota
            limit: New limit (optional)
            warning_threshold: New warning threshold (optional)
            action: New action (optional)
            enabled: Enable/disable (optional)
            
        Returns:
            Updated quota
        """
        async with self._lock:
            quota = await self.get_quota(tenant_id, quota_type)
            if not quota:
                raise ValueError(f"Quota {quota_type.value} not found for tenant {tenant_id}")
            
            if limit is not None:
                quota.limit = limit
            if warning_threshold is not None:
                quota.warning_threshold = warning_threshold
            if action is not None:
                quota.action = action
            if enabled is not None:
                quota.enabled = enabled
            
            quota.updated_at = datetime.now(timezone.utc)
            
            logger.info(
                "Updated quota",
                tenant_id=tenant_id,
                quota_type=quota_type.value,
            )
            
            return quota
    
    async def set_temporary_override(
        self,
        tenant_id: str,
        quota_type: QuotaType,
        override_limit: int,
        duration_hours: int = 24,
    ) -> Quota:
        """Set a temporary quota override.
        
        Args:
            tenant_id: Tenant ID
            quota_type: Type of quota
            override_limit: Temporary higher limit
            duration_hours: How long the override lasts
            
        Returns:
            Updated quota
        """
        async with self._lock:
            quota = await self.get_quota(tenant_id, quota_type)
            if not quota:
                raise ValueError(f"Quota {quota_type.value} not found for tenant {tenant_id}")
            
            if not quota.allow_temporary_override:
                raise ValueError(f"Quota {quota_type.value} does not allow overrides")
            
            quota.override_limit = override_limit
            quota.override_expires_at = datetime.now(timezone.utc) + timedelta(hours=duration_hours)
            quota.updated_at = datetime.now(timezone.utc)
            
            logger.info(
                "Set quota override",
                tenant_id=tenant_id,
                quota_type=quota_type.value,
                override_limit=override_limit,
                expires_in_hours=duration_hours,
            )
            
            return quota
    
    async def check_quota(
        self,
        tenant_id: str,
        quota_type: QuotaType,
        amount: int = 1,
    ) -> QuotaCheckResult:
        """Check if an operation is allowed by quota.
        
        Args:
            tenant_id: Tenant ID
            quota_type: Type of quota
            amount: Amount to check
            
        Returns:
            Check result
        """
        quota = await self.get_quota(tenant_id, quota_type)
        
        if not quota or not quota.enabled:
            # No quota or disabled = unlimited
            return QuotaCheckResult(
                allowed=True,
                quota_type=quota_type,
                limit=0,
                current_usage=0,
                remaining=999999,
                percentage_used=0,
                action=QuotaAction.WARN,
            )
        
        usage = await self._get_or_create_usage(tenant_id, quota_type)
        
        # Check if period needs reset
        await self._maybe_reset_period(quota, usage)
        
        new_usage = usage.current_usage + amount
        limit = quota.effective_limit
        percentage_used = new_usage / limit if limit > 0 else 0
        
        # Determine if allowed
        exceeded = new_usage > limit
        at_warning = percentage_used >= quota.warning_threshold and not exceeded
        
        if exceeded:
            allowed = quota.action != QuotaAction.BLOCK
            action = quota.action
            message = f"Quota exceeded: {quota_type.value} ({new_usage}/{limit})"
        else:
            allowed = True
            action = QuotaAction.WARN if at_warning else QuotaAction.OVERAGE
            message = None
        
        result = QuotaCheckResult(
            allowed=allowed,
            quota_type=quota_type,
            limit=limit,
            current_usage=usage.current_usage,
            remaining=max(0, limit - usage.current_usage),
            percentage_used=min(1.0, percentage_used),
            at_warning=at_warning,
            exceeded=exceeded,
            action=action,
            message=message,
        )
        
        # Calculate retry time for rate quotas
        if exceeded and quota.action == QuotaAction.THROTTLE:
            result.retry_after_seconds = self._calculate_retry_after(quota, usage)
        
        return result
    
    async def check_and_increment(
        self,
        tenant_id: str,
        quota_type: QuotaType,
        amount: int = 1,
        raise_on_exceeded: bool = True,
    ) -> QuotaCheckResult:
        """Check quota and increment usage if allowed.
        
        Args:
            tenant_id: Tenant ID
            quota_type: Type of quota
            amount: Amount to consume
            raise_on_exceeded: Whether to raise exception if exceeded
            
        Returns:
            Check result
            
        Raises:
            QuotaExceededError: If exceeded and raise_on_exceeded=True
        """
        async with self._lock:
            result = await self.check_quota(tenant_id, quota_type, amount)
            
            if result.exceeded:
                # Record exceeded count
                usage = self._usage.get(tenant_id, {}).get(quota_type)
                if usage:
                    usage.times_exceeded += 1
                
                # Create alert
                await self._create_alert(
                    tenant_id=tenant_id,
                    quota_type=quota_type,
                    alert_type="exceeded",
                    message=result.message or "Quota exceeded",
                    current_usage=result.current_usage + amount,
                    limit=result.limit,
                )
                
                # Call hook
                if self._on_exceeded:
                    await self._on_exceeded(tenant_id, quota_type, result)
                
                if raise_on_exceeded and not result.allowed:
                    raise QuotaExceededError(
                        message=result.message or "Quota exceeded",
                        tenant_id=tenant_id,
                        quota_type=quota_type,
                        limit=result.limit,
                        current_usage=result.current_usage,
                        retry_after=result.retry_after_seconds,
                    )
            
            elif result.at_warning:
                # Create warning alert
                await self._create_alert(
                    tenant_id=tenant_id,
                    quota_type=quota_type,
                    alert_type="warning",
                    message=f"Quota warning: approaching limit for {quota_type.value}",
                    current_usage=result.current_usage + amount,
                    limit=result.limit,
                )
                
                # Call hook
                if self._on_warning:
                    await self._on_warning(tenant_id, quota_type, result)
            
            if result.allowed:
                # Increment usage
                usage = await self._get_or_create_usage(tenant_id, quota_type)
                usage.record_usage(amount)
            
            return result
    
    async def get_usage(
        self,
        tenant_id: str,
        quota_type: QuotaType,
    ) -> Optional[QuotaUsage]:
        """Get current usage for a quota."""
        return self._usage.get(tenant_id, {}).get(quota_type)
    
    async def set_usage(
        self,
        tenant_id: str,
        quota_type: QuotaType,
        usage: int,
    ) -> QuotaUsage:
        """Set current usage directly (for syncing from external sources).
        
        Args:
            tenant_id: Tenant ID
            quota_type: Type of quota
            usage: Current usage value
            
        Returns:
            Updated usage
        """
        async with self._lock:
            usage_obj = await self._get_or_create_usage(tenant_id, quota_type)
            usage_obj.current_usage = usage
            usage_obj.last_updated = datetime.now(timezone.utc)
            
            if usage > usage_obj.peak_usage:
                usage_obj.peak_usage = usage
            
            return usage_obj
    
    async def decrement_usage(
        self,
        tenant_id: str,
        quota_type: QuotaType,
        amount: int = 1,
    ) -> int:
        """Decrement usage (for resource deletion).
        
        Args:
            tenant_id: Tenant ID
            quota_type: Type of quota
            amount: Amount to decrement
            
        Returns:
            New usage value
        """
        async with self._lock:
            usage = self._usage.get(tenant_id, {}).get(quota_type)
            if usage:
                usage.current_usage = max(0, usage.current_usage - amount)
                usage.last_updated = datetime.now(timezone.utc)
                return usage.current_usage
            return 0
    
    async def reset_usage(
        self,
        tenant_id: str,
        quota_type: QuotaType,
    ) -> None:
        """Reset usage for a quota.
        
        Args:
            tenant_id: Tenant ID
            quota_type: Type of quota
        """
        async with self._lock:
            usage = self._usage.get(tenant_id, {}).get(quota_type)
            if usage:
                usage.reset()
                
                await self._create_alert(
                    tenant_id=tenant_id,
                    quota_type=quota_type,
                    alert_type="reset",
                    message=f"Quota reset: {quota_type.value}",
                    current_usage=0,
                    limit=self._quotas.get(tenant_id, {}).get(quota_type, Quota(tenant_id="", quota_type=quota_type, limit=0)).limit,
                )
    
    async def get_usage_report(
        self,
        tenant_id: str,
    ) -> Dict[str, Any]:
        """Get comprehensive usage report for a tenant.
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            Usage report dictionary
        """
        quotas = await self.get_all_quotas(tenant_id)
        
        report: Dict[str, Any] = {
            "tenant_id": tenant_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "quotas": [],
            "summary": {
                "total_quotas": len(quotas),
                "quotas_at_warning": 0,
                "quotas_exceeded": 0,
            },
        }
        
        for quota in quotas:
            usage = await self.get_usage(tenant_id, quota.quota_type)
            current = usage.current_usage if usage else 0
            limit = quota.effective_limit
            percentage = (current / limit * 100) if limit > 0 else 0
            
            quota_report = {
                "type": quota.quota_type.value,
                "limit": limit,
                "current_usage": current,
                "remaining": max(0, limit - current),
                "percentage_used": round(percentage, 2),
                "period": quota.period.value,
                "status": "ok",
            }
            
            if percentage >= 100:
                quota_report["status"] = "exceeded"
                report["summary"]["quotas_exceeded"] += 1
            elif percentage >= quota.warning_threshold * 100:
                quota_report["status"] = "warning"
                report["summary"]["quotas_at_warning"] += 1
            
            if usage:
                quota_report["peak_usage"] = usage.peak_usage
                quota_report["total_consumed"] = usage.total_consumed
                quota_report["times_exceeded"] = usage.times_exceeded
                quota_report["period_start"] = usage.period_start.isoformat()
            
            report["quotas"].append(quota_report)
        
        return report
    
    async def get_alerts(
        self,
        tenant_id: Optional[str] = None,
        unacknowledged_only: bool = False,
        limit: int = 100,
    ) -> List[QuotaAlert]:
        """Get quota alerts.
        
        Args:
            tenant_id: Filter by tenant
            unacknowledged_only: Only return unacknowledged alerts
            limit: Maximum number of alerts
            
        Returns:
            List of alerts
        """
        alerts = self._alerts
        
        if tenant_id:
            alerts = [a for a in alerts if a.tenant_id == tenant_id]
        
        if unacknowledged_only:
            alerts = [a for a in alerts if not a.acknowledged]
        
        # Sort by creation time descending
        alerts.sort(key=lambda a: a.created_at, reverse=True)
        
        return alerts[:limit]
    
    async def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_by: str,
    ) -> bool:
        """Acknowledge a quota alert.
        
        Args:
            alert_id: Alert ID
            acknowledged_by: User acknowledging
            
        Returns:
            True if acknowledged
        """
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                alert.acknowledged_at = datetime.now(timezone.utc)
                alert.acknowledged_by = acknowledged_by
                return True
        return False
    
    async def cleanup_expired_overrides(self) -> int:
        """Clean up expired quota overrides.
        
        Returns:
            Number of overrides cleaned up
        """
        count = 0
        now = datetime.now(timezone.utc)
        
        async with self._lock:
            for tenant_quotas in self._quotas.values():
                for quota in tenant_quotas.values():
                    if quota.override_expires_at and quota.override_expires_at < now:
                        quota.override_limit = None
                        quota.override_expires_at = None
                        count += 1
        
        if count > 0:
            logger.info("Cleaned up expired quota overrides", count=count)
        
        return count
    
    # Private methods
    
    async def _get_or_create_usage(
        self,
        tenant_id: str,
        quota_type: QuotaType,
    ) -> QuotaUsage:
        """Get or create usage tracking for a quota."""
        if tenant_id not in self._usage:
            self._usage[tenant_id] = {}
        
        if quota_type not in self._usage[tenant_id]:
            self._usage[tenant_id][quota_type] = QuotaUsage(
                tenant_id=tenant_id,
                quota_type=quota_type,
            )
        
        return self._usage[tenant_id][quota_type]
    
    async def _maybe_reset_period(
        self,
        quota: Quota,
        usage: QuotaUsage,
    ) -> None:
        """Reset usage if period has expired."""
        if quota.period == QuotaPeriod.NONE:
            return
        
        now = datetime.now(timezone.utc)
        period_duration = self._get_period_duration(quota.period)
        period_end = usage.period_start + period_duration
        
        if now >= period_end:
            usage.period_end = period_end
            usage.reset()
            
            logger.debug(
                "Reset quota period",
                tenant_id=quota.tenant_id,
                quota_type=quota.quota_type.value,
            )
    
    def _get_period_duration(self, period: QuotaPeriod) -> timedelta:
        """Get timedelta for a period."""
        return {
            QuotaPeriod.MINUTE: timedelta(minutes=1),
            QuotaPeriod.HOUR: timedelta(hours=1),
            QuotaPeriod.DAY: timedelta(days=1),
            QuotaPeriod.WEEK: timedelta(weeks=1),
            QuotaPeriod.MONTH: timedelta(days=30),
            QuotaPeriod.NONE: timedelta(days=36500),  # ~100 years
        }.get(period, timedelta(days=1))
    
    def _calculate_retry_after(
        self,
        quota: Quota,
        usage: QuotaUsage,
    ) -> int:
        """Calculate seconds until quota resets."""
        if quota.period == QuotaPeriod.NONE:
            return 0
        
        now = datetime.now(timezone.utc)
        period_duration = self._get_period_duration(quota.period)
        period_end = usage.period_start + period_duration
        
        return max(0, int((period_end - now).total_seconds()))
    
    async def _create_alert(
        self,
        tenant_id: str,
        quota_type: QuotaType,
        alert_type: str,
        message: str,
        current_usage: int,
        limit: int,
    ) -> QuotaAlert:
        """Create a quota alert."""
        alert = QuotaAlert(
            tenant_id=tenant_id,
            quota_type=quota_type,
            alert_type=alert_type,
            message=message,
            current_usage=current_usage,
            limit=limit,
            percentage_used=(current_usage / limit * 100) if limit > 0 else 0,
        )
        
        self._alerts.append(alert)
        
        # Keep alerts manageable
        if len(self._alerts) > 10000:
            self._alerts = self._alerts[-5000:]
        
        return alert


class QuotaMiddleware:
    """Middleware for automatic quota enforcement in API routes.
    
    Example usage with FastAPI:
        
        quota_middleware = QuotaMiddleware(quota_manager)
        
        @app.middleware("http")
        async def quota_middleware_handler(request, call_next):
            return await quota_middleware(request, call_next)
    """
    
    def __init__(
        self,
        quota_manager: QuotaManager,
        quota_type: QuotaType = QuotaType.API_CALLS_PER_MINUTE,
        tenant_extractor: Optional[Callable] = None,
    ):
        """Initialize QuotaMiddleware.
        
        Args:
            quota_manager: QuotaManager instance
            quota_type: Default quota type to check
            tenant_extractor: Function to extract tenant_id from request
        """
        self.quota_manager = quota_manager
        self.quota_type = quota_type
        self.tenant_extractor = tenant_extractor
    
    async def __call__(self, request: Any, call_next: Callable) -> Any:
        """Process request with quota check."""
        # Extract tenant ID
        tenant_id = None
        if self.tenant_extractor:
            tenant_id = self.tenant_extractor(request)
        elif hasattr(request.state, 'tenant_id'):
            tenant_id = request.state.tenant_id
        
        if not tenant_id:
            return await call_next(request)
        
        try:
            await self.quota_manager.check_and_increment(
                tenant_id=tenant_id,
                quota_type=self.quota_type,
            )
        except QuotaExceededError as e:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={
                    "error": "quota_exceeded",
                    "message": str(e),
                    "quota_type": e.quota_type.value,
                    "retry_after": e.retry_after,
                },
                headers={
                    "Retry-After": str(e.retry_after or 60),
                },
            )
        
        return await call_next(request)
