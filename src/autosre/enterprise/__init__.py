"""Enterprise features for AutoSRE V2.

This module provides enterprise-grade capabilities including:
- Multi-tenancy with resource isolation
- Advanced RBAC with attribute-based access control
- SSO integration (SAML, OIDC, LDAP)
- Comprehensive audit logging
"""

from autosre.enterprise.tenancy import (
    TenantManager,
    ResourceIsolation,
    QuotaManager,
    TenantRouter,
    CrossTenantPolicy,
)
from autosre.enterprise.rbac import (
    RoleManager,
    PermissionEngine,
    PolicyEngine,
    AuditLogger,
    SSOIntegration,
)

__all__ = [
    # Tenancy
    "TenantManager",
    "ResourceIsolation",
    "QuotaManager",
    "TenantRouter",
    "CrossTenantPolicy",
    # RBAC
    "RoleManager",
    "PermissionEngine",
    "PolicyEngine",
    "AuditLogger",
    "SSOIntegration",
]
