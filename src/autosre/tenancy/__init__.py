"""
AutoSRE Multi-Tenancy Module

Enterprise SaaS-ready multi-tenancy support providing:
- Tenant, Workspace, and Team models
- Data isolation layer
- Resource quotas and rate limiting
- Usage tracking and billing
- FastAPI middleware for tenant context

Usage:
    from autosre.tenancy import (
        Tenant, Workspace, Team,
        TenantContext, get_current_tenant,
        TenantIsolation, QuotaManager,
        UsageTracker, BillingService,
        TenantMiddleware,
    )
"""

from autosre.tenancy.models import (
    Tenant,
    TenantStatus,
    TenantTier,
    Workspace,
    WorkspaceType,
    Team,
    TeamRole,
    TeamMember,
    TenantSettings,
    WorkspaceSettings,
)
from autosre.tenancy.isolation import (
    TenantContext,
    TenantIsolation,
    get_current_tenant,
    set_current_tenant,
    clear_tenant_context,
    tenant_context,
    IsolationLevel,
    IsolationPolicy,
)
from autosre.tenancy.quotas import (
    QuotaManager,
    QuotaType,
    QuotaLimit,
    QuotaUsage,
    QuotaExceededError,
    RateLimiter,
    RateLimitConfig,
)
from autosre.tenancy.billing import (
    UsageTracker,
    BillingService,
    UsageEvent,
    UsageMetric,
    BillingPeriod,
    Invoice,
    InvoiceStatus,
    PricingTier,
)
from autosre.tenancy.middleware import (
    TenantMiddleware,
    TenantResolver,
    HeaderBasedResolver,
    JWTBasedResolver,
    TenantContextDep,
    require_tenant,
    require_workspace,
    require_team_role,
)

__all__ = [
    # Models
    "Tenant",
    "TenantStatus",
    "TenantTier",
    "Workspace",
    "WorkspaceType",
    "Team",
    "TeamRole",
    "TeamMember",
    "TenantSettings",
    "WorkspaceSettings",
    # Isolation
    "TenantContext",
    "TenantIsolation",
    "get_current_tenant",
    "set_current_tenant",
    "clear_tenant_context",
    "tenant_context",
    "IsolationLevel",
    "IsolationPolicy",
    # Quotas
    "QuotaManager",
    "QuotaType",
    "QuotaLimit",
    "QuotaUsage",
    "QuotaExceededError",
    "RateLimiter",
    "RateLimitConfig",
    # Billing
    "UsageTracker",
    "BillingService",
    "UsageEvent",
    "UsageMetric",
    "BillingPeriod",
    "Invoice",
    "InvoiceStatus",
    "PricingTier",
    # Middleware
    "TenantMiddleware",
    "TenantResolver",
    "HeaderBasedResolver",
    "JWTBasedResolver",
    "TenantContextDep",
    "require_tenant",
    "require_workspace",
    "require_team_role",
]
