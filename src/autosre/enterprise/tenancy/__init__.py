"""Multi-tenancy module for AutoSRE V2.

Provides complete tenant isolation, resource management, and quota enforcement
for enterprise multi-tenant deployments.
"""

from autosre.enterprise.tenancy.tenant_manager import (
    TenantManager,
    Tenant,
    TenantStatus,
    TenantTier,
    TenantConfig,
)
from autosre.enterprise.tenancy.resource_isolation import (
    ResourceIsolation,
    IsolationLevel,
    ResourceNamespace,
    IsolationPolicy,
)
from autosre.enterprise.tenancy.quota_manager import (
    QuotaManager,
    Quota,
    QuotaType,
    QuotaUsage,
    QuotaExceededError,
)
from autosre.enterprise.tenancy.tenant_router import (
    TenantRouter,
    TenantContext,
    TenantMiddleware,
)
from autosre.enterprise.tenancy.cross_tenant_policy import (
    CrossTenantPolicy,
    CrossTenantRule,
    AccessLevel,
    SharingPolicy,
)

__all__ = [
    # Tenant Manager
    "TenantManager",
    "Tenant",
    "TenantStatus",
    "TenantTier",
    "TenantConfig",
    # Resource Isolation
    "ResourceIsolation",
    "IsolationLevel",
    "ResourceNamespace",
    "IsolationPolicy",
    # Quota Manager
    "QuotaManager",
    "Quota",
    "QuotaType",
    "QuotaUsage",
    "QuotaExceededError",
    # Tenant Router
    "TenantRouter",
    "TenantContext",
    "TenantMiddleware",
    # Cross-Tenant Policy
    "CrossTenantPolicy",
    "CrossTenantRule",
    "AccessLevel",
    "SharingPolicy",
]
