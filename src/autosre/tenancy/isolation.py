"""
Data Isolation Layer

Provides tenant-scoped data isolation ensuring complete separation
of data between tenants. Uses context variables for request-scoped
tenant identification.
"""

import contextvars
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, Generic, Optional, TypeVar

from pydantic import BaseModel

from autosre.tenancy.models import Tenant, Workspace, Team, TeamRole


# Context variable for current tenant context
_tenant_context: contextvars.ContextVar[Optional["TenantContext"]] = contextvars.ContextVar(
    "tenant_context", default=None
)


class IsolationLevel(str, Enum):
    """Data isolation level."""
    TENANT = "tenant"           # Isolated by tenant only
    WORKSPACE = "workspace"     # Isolated by workspace within tenant
    TEAM = "team"              # Isolated by team within workspace


class IsolationPolicy(str, Enum):
    """Policy for handling cross-tenant access."""
    STRICT = "strict"           # Fail on any cross-tenant access
    AUDIT = "audit"            # Allow but audit cross-tenant access
    PERMISSIVE = "permissive"  # Allow cross-tenant (for admins/debugging)


@dataclass
class TenantContext:
    """
    Current tenant context for a request/operation.
    
    This context is set at the beginning of each request and
    used to scope all data access to the current tenant.
    """
    
    tenant: Tenant
    workspace: Optional[Workspace] = None
    team: Optional[Team] = None
    user_id: Optional[str] = None
    user_role: Optional[TeamRole] = None
    
    # Request metadata
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    
    # Access tracking
    accessed_resources: list[str] = field(default_factory=list)
    
    @property
    def tenant_id(self) -> str:
        """Get the current tenant ID."""
        return self.tenant.id
    
    @property
    def workspace_id(self) -> Optional[str]:
        """Get the current workspace ID."""
        return self.workspace.id if self.workspace else None
    
    @property
    def team_id(self) -> Optional[str]:
        """Get the current team ID."""
        return self.team.id if self.team else None
    
    @property
    def is_admin(self) -> bool:
        """Check if current user is admin or owner."""
        return self.user_role in (TeamRole.ADMIN, TeamRole.OWNER)
    
    def can_access_workspace(self, workspace_id: str) -> bool:
        """Check if current context can access a workspace."""
        if self.is_admin:
            return True
        if self.workspace and self.workspace.id == workspace_id:
            return True
        # Check team access
        if self.team and workspace_id in self.team.workspace_ids:
            return True
        return False
    
    def record_access(self, resource_type: str, resource_id: str) -> None:
        """Record resource access for audit trail."""
        self.accessed_resources.append(f"{resource_type}:{resource_id}")


def get_current_tenant() -> Optional[TenantContext]:
    """Get the current tenant context."""
    return _tenant_context.get()


def set_current_tenant(context: TenantContext) -> contextvars.Token:
    """Set the current tenant context."""
    return _tenant_context.set(context)


def clear_tenant_context() -> None:
    """Clear the current tenant context."""
    _tenant_context.set(None)


@contextmanager
def tenant_context(context: TenantContext):
    """
    Context manager for tenant-scoped operations.
    
    Usage:
        with tenant_context(ctx):
            # All operations here are scoped to the tenant
            data = service.get_data()
    """
    token = set_current_tenant(context)
    try:
        yield context
    finally:
        _tenant_context.reset(token)


def require_tenant_context(func: Callable) -> Callable:
    """
    Decorator to require tenant context for a function.
    
    Usage:
        @require_tenant_context
        def get_data():
            ctx = get_current_tenant()
            # ctx is guaranteed to exist
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        ctx = get_current_tenant()
        if ctx is None:
            raise TenantContextError("No tenant context available")
        return func(*args, **kwargs)
    return wrapper


class TenantContextError(Exception):
    """Error when tenant context is missing or invalid."""
    pass


class CrossTenantAccessError(Exception):
    """Error when cross-tenant access is attempted."""
    
    def __init__(self, source_tenant: str, target_tenant: str, resource: str):
        self.source_tenant = source_tenant
        self.target_tenant = target_tenant
        self.resource = resource
        super().__init__(
            f"Cross-tenant access denied: tenant '{source_tenant}' "
            f"attempted to access resource '{resource}' belonging to tenant '{target_tenant}'"
        )


T = TypeVar('T', bound=BaseModel)


class TenantIsolation(Generic[T]):
    """
    Data isolation layer for tenant-scoped resources.
    
    Wraps data access operations to ensure tenant isolation.
    All operations automatically scope to the current tenant.
    
    Usage:
        class AlertStore:
            def __init__(self):
                self.isolation = TenantIsolation[Alert](
                    isolation_level=IsolationLevel.WORKSPACE,
                    policy=IsolationPolicy.STRICT,
                )
            
            def get_alerts(self) -> list[Alert]:
                ctx = self.isolation.get_context()
                # Query scoped to ctx.tenant_id and ctx.workspace_id
    """
    
    def __init__(
        self,
        isolation_level: IsolationLevel = IsolationLevel.TENANT,
        policy: IsolationPolicy = IsolationPolicy.STRICT,
        audit_callback: Optional[Callable[[str, str, str], None]] = None,
    ):
        self.isolation_level = isolation_level
        self.policy = policy
        self.audit_callback = audit_callback
    
    def get_context(self) -> TenantContext:
        """Get current tenant context, raising if none."""
        ctx = get_current_tenant()
        if ctx is None:
            raise TenantContextError("No tenant context available")
        return ctx
    
    def get_tenant_filter(self) -> dict[str, str]:
        """
        Get filter criteria for the current isolation scope.
        
        Returns a dict that can be used in database queries.
        """
        ctx = self.get_context()
        
        filters = {"tenant_id": ctx.tenant_id}
        
        if self.isolation_level in (IsolationLevel.WORKSPACE, IsolationLevel.TEAM):
            if ctx.workspace_id:
                filters["workspace_id"] = ctx.workspace_id
        
        if self.isolation_level == IsolationLevel.TEAM:
            if ctx.team_id:
                filters["team_id"] = ctx.team_id
        
        return filters
    
    def validate_access(
        self,
        resource_tenant_id: str,
        resource_workspace_id: Optional[str] = None,
        resource_team_id: Optional[str] = None,
    ) -> bool:
        """
        Validate that current context can access a resource.
        
        Returns True if access is allowed, raises or returns False otherwise.
        """
        ctx = self.get_context()
        
        # Check tenant-level access
        if resource_tenant_id != ctx.tenant_id:
            self._handle_cross_tenant_access(
                ctx.tenant_id, 
                resource_tenant_id, 
                "tenant_resource"
            )
            return False
        
        # Check workspace-level access
        if self.isolation_level in (IsolationLevel.WORKSPACE, IsolationLevel.TEAM):
            if resource_workspace_id and not ctx.can_access_workspace(resource_workspace_id):
                self._handle_cross_tenant_access(
                    ctx.workspace_id or "none",
                    resource_workspace_id,
                    "workspace_resource"
                )
                return False
        
        # Check team-level access
        if self.isolation_level == IsolationLevel.TEAM:
            if resource_team_id and ctx.team_id != resource_team_id:
                # Team members can access their team's resources
                if not ctx.is_admin:
                    self._handle_cross_tenant_access(
                        ctx.team_id or "none",
                        resource_team_id,
                        "team_resource"
                    )
                    return False
        
        return True
    
    def _handle_cross_tenant_access(
        self,
        source: str,
        target: str,
        resource: str,
    ) -> None:
        """Handle cross-tenant access based on policy."""
        if self.policy == IsolationPolicy.STRICT:
            raise CrossTenantAccessError(source, target, resource)
        elif self.policy == IsolationPolicy.AUDIT:
            if self.audit_callback:
                self.audit_callback(source, target, resource)
        # PERMISSIVE: do nothing
    
    def scope_query(self, query: dict[str, Any]) -> dict[str, Any]:
        """
        Add tenant scoping to a query.
        
        Takes a query dict and adds the appropriate tenant/workspace/team
        filters based on the isolation level.
        """
        filters = self.get_tenant_filter()
        return {**query, **filters}
    
    def validate_create(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Validate and scope data for creation.
        
        Ensures the tenant_id (and optionally workspace_id, team_id)
        are set correctly on new records.
        """
        ctx = self.get_context()
        
        # Always set tenant_id
        data["tenant_id"] = ctx.tenant_id
        
        # Set workspace_id if isolation requires it
        if self.isolation_level in (IsolationLevel.WORKSPACE, IsolationLevel.TEAM):
            if "workspace_id" not in data and ctx.workspace_id:
                data["workspace_id"] = ctx.workspace_id
        
        # Set team_id if isolation requires it
        if self.isolation_level == IsolationLevel.TEAM:
            if "team_id" not in data and ctx.team_id:
                data["team_id"] = ctx.team_id
        
        return data


class TenantAwareModel(BaseModel):
    """
    Base model for tenant-scoped resources.
    
    Inherit from this model to automatically include tenant scoping fields.
    """
    
    tenant_id: str
    workspace_id: Optional[str] = None
    team_id: Optional[str] = None
    
    @classmethod
    def for_current_tenant(cls, **kwargs) -> "TenantAwareModel":
        """Create an instance scoped to the current tenant."""
        ctx = get_current_tenant()
        if ctx is None:
            raise TenantContextError("No tenant context available")
        
        return cls(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            team_id=ctx.team_id,
            **kwargs,
        )


class IsolatedDataStore:
    """
    Base class for tenant-isolated data stores.
    
    Provides common patterns for CRUD operations with tenant isolation.
    Subclasses implement the actual storage backend.
    """
    
    def __init__(
        self,
        isolation_level: IsolationLevel = IsolationLevel.WORKSPACE,
        policy: IsolationPolicy = IsolationPolicy.STRICT,
    ):
        self.isolation = TenantIsolation(
            isolation_level=isolation_level,
            policy=policy,
        )
    
    def _get_scope(self) -> dict[str, str]:
        """Get current tenant scope for queries."""
        return self.isolation.get_tenant_filter()
    
    def _validate_access(self, item: TenantAwareModel) -> bool:
        """Validate access to an item."""
        return self.isolation.validate_access(
            item.tenant_id,
            item.workspace_id,
            item.team_id,
        )
    
    def _scope_create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Scope data for creation."""
        return self.isolation.validate_create(data)
