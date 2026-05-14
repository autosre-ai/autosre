"""Advanced RBAC module for AutoSRE V2.

Provides enterprise-grade role-based access control including:
- Granular role management
- Fine-grained permissions
- Attribute-based access control (ABAC)
- Comprehensive audit logging
- SSO integration (SAML, OIDC, LDAP)
"""

from autosre.enterprise.rbac.role_manager import (
    RoleManager,
    Role,
    RoleType,
    Permission,
    PermissionScope,
)
from autosre.enterprise.rbac.permission_engine import (
    PermissionEngine,
    PermissionCheck,
    PermissionResult,
    PermissionDeniedError,
)
from autosre.enterprise.rbac.policy_engine import (
    PolicyEngine,
    Policy,
    PolicyCondition,
    PolicyEffect,
    PolicyEvaluationContext,
)
from autosre.enterprise.rbac.audit_logger import (
    AuditLogger,
    AuditEvent,
    AuditEventType,
    AuditQuery,
)
from autosre.enterprise.rbac.sso_integration import (
    SSOIntegration,
    SSOProvider,
    SAMLConfig,
    OIDCConfig,
    LDAPConfig,
    SSOUser,
)

__all__ = [
    # Role Manager
    "RoleManager",
    "Role",
    "RoleType",
    "Permission",
    "PermissionScope",
    # Permission Engine
    "PermissionEngine",
    "PermissionCheck",
    "PermissionResult",
    "PermissionDeniedError",
    # Policy Engine
    "PolicyEngine",
    "Policy",
    "PolicyCondition",
    "PolicyEffect",
    "PolicyEvaluationContext",
    # Audit Logger
    "AuditLogger",
    "AuditEvent",
    "AuditEventType",
    "AuditQuery",
    # SSO Integration
    "SSOIntegration",
    "SSOProvider",
    "SAMLConfig",
    "OIDCConfig",
    "LDAPConfig",
    "SSOUser",
]
