"""
FastAPI Middleware for Multi-Tenancy

Provides automatic tenant context resolution and injection
for all API requests.
"""

import time
from abc import ABC, abstractmethod
from functools import wraps
from typing import Annotated, Any, Callable, Optional

from fastapi import Depends, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from autosre.tenancy.isolation import (
    TenantContext,
    get_current_tenant,
    set_current_tenant,
    clear_tenant_context,
)
from autosre.tenancy.models import Tenant, Workspace, Team, TeamRole, TenantStatus
from autosre.tenancy.quotas import QuotaManager, QuotaExceededError, QuotaType


class TenantResolver(ABC):
    """
    Abstract base class for tenant resolution strategies.
    
    Implement this to define how tenants are resolved from requests
    (e.g., from headers, JWT tokens, API keys, subdomain, etc.)
    """
    
    @abstractmethod
    async def resolve_tenant(self, request: Request) -> Optional[Tenant]:
        """Resolve tenant from request."""
        pass
    
    @abstractmethod
    async def resolve_workspace(
        self, 
        request: Request, 
        tenant: Tenant,
    ) -> Optional[Workspace]:
        """Resolve workspace from request."""
        pass
    
    @abstractmethod
    async def resolve_team(
        self,
        request: Request,
        tenant: Tenant,
        workspace: Optional[Workspace],
    ) -> Optional[Team]:
        """Resolve team from request."""
        pass
    
    @abstractmethod
    async def resolve_user_role(
        self,
        request: Request,
        tenant: Tenant,
        team: Optional[Team],
    ) -> Optional[TeamRole]:
        """Resolve user's role from request."""
        pass


class HeaderBasedResolver(TenantResolver):
    """
    Resolves tenant from request headers.
    
    Headers:
    - X-Tenant-ID: Tenant identifier
    - X-Workspace-ID: Workspace identifier (optional)
    - X-Team-ID: Team identifier (optional)
    """
    
    def __init__(
        self,
        tenant_store: Any = None,
        workspace_store: Any = None,
        team_store: Any = None,
        user_store: Any = None,
    ):
        self.tenant_store = tenant_store
        self.workspace_store = workspace_store
        self.team_store = team_store
        self.user_store = user_store
    
    async def resolve_tenant(self, request: Request) -> Optional[Tenant]:
        """Resolve tenant from X-Tenant-ID header."""
        tenant_id = request.headers.get("X-Tenant-ID")
        if not tenant_id:
            return None
        
        if self.tenant_store:
            return await self.tenant_store.get(tenant_id)
        
        # Mock for development
        return Tenant(
            id=tenant_id,
            name=f"Tenant {tenant_id}",
            slug=tenant_id.lower(),
            admin_email=f"admin@{tenant_id}.example.com",
            status=TenantStatus.ACTIVE,
        )
    
    async def resolve_workspace(
        self,
        request: Request,
        tenant: Tenant,
    ) -> Optional[Workspace]:
        """Resolve workspace from X-Workspace-ID header."""
        workspace_id = request.headers.get("X-Workspace-ID")
        if not workspace_id:
            return None
        
        if self.workspace_store:
            workspace = await self.workspace_store.get(workspace_id)
            # Verify workspace belongs to tenant
            if workspace and workspace.tenant_id == tenant.id:
                return workspace
            return None
        
        return Workspace(
            id=workspace_id,
            tenant_id=tenant.id,
            name=f"Workspace {workspace_id}",
            slug=workspace_id.lower(),
        )
    
    async def resolve_team(
        self,
        request: Request,
        tenant: Tenant,
        workspace: Optional[Workspace],
    ) -> Optional[Team]:
        """Resolve team from X-Team-ID header."""
        team_id = request.headers.get("X-Team-ID")
        if not team_id:
            return None
        
        if self.team_store:
            team = await self.team_store.get(team_id)
            if team and team.tenant_id == tenant.id:
                return team
            return None
        
        return Team(
            id=team_id,
            tenant_id=tenant.id,
            name=f"Team {team_id}",
            slug=team_id.lower(),
        )
    
    async def resolve_user_role(
        self,
        request: Request,
        tenant: Tenant,
        team: Optional[Team],
    ) -> Optional[TeamRole]:
        """Resolve user role from team membership or header."""
        # Check header override (for admin access)
        role_header = request.headers.get("X-User-Role")
        if role_header:
            try:
                return TeamRole(role_header)
            except ValueError:
                pass
        
        # Check team membership
        user_id = request.headers.get("X-User-ID")
        if team and user_id:
            member = team.get_member(user_id)
            if member:
                return member.role
        
        return TeamRole.MEMBER


class JWTBasedResolver(TenantResolver):
    """
    Resolves tenant from JWT token claims.
    
    Expected claims:
    - tenant_id: Tenant identifier
    - workspace_id: Workspace identifier (optional)
    - team_id: Team identifier (optional)
    - role: User role
    """
    
    def __init__(
        self,
        jwt_decoder: Callable[[str], dict[str, Any]],
        tenant_store: Any = None,
    ):
        self.jwt_decoder = jwt_decoder
        self.tenant_store = tenant_store
        self._cached_claims: Optional[dict[str, Any]] = None
    
    def _decode_token(self, request: Request) -> Optional[dict[str, Any]]:
        """Decode JWT from Authorization header."""
        if self._cached_claims:
            return self._cached_claims
        
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        
        token = auth_header[7:]
        try:
            self._cached_claims = self.jwt_decoder(token)
            return self._cached_claims
        except Exception:
            return None
    
    async def resolve_tenant(self, request: Request) -> Optional[Tenant]:
        claims = self._decode_token(request)
        if not claims or "tenant_id" not in claims:
            return None
        
        tenant_id = claims["tenant_id"]
        
        if self.tenant_store:
            return await self.tenant_store.get(tenant_id)
        
        return Tenant(
            id=tenant_id,
            name=claims.get("tenant_name", f"Tenant {tenant_id}"),
            slug=tenant_id.lower(),
            admin_email=claims.get("email", f"admin@{tenant_id}.example.com"),
            status=TenantStatus.ACTIVE,
        )
    
    async def resolve_workspace(
        self,
        request: Request,
        tenant: Tenant,
    ) -> Optional[Workspace]:
        claims = self._decode_token(request)
        if not claims or "workspace_id" not in claims:
            return None
        
        return Workspace(
            id=claims["workspace_id"],
            tenant_id=tenant.id,
            name=claims.get("workspace_name", "Default"),
            slug=claims.get("workspace_slug", "default"),
        )
    
    async def resolve_team(
        self,
        request: Request,
        tenant: Tenant,
        workspace: Optional[Workspace],
    ) -> Optional[Team]:
        claims = self._decode_token(request)
        if not claims or "team_id" not in claims:
            return None
        
        return Team(
            id=claims["team_id"],
            tenant_id=tenant.id,
            name=claims.get("team_name", "Default"),
            slug=claims.get("team_slug", "default"),
        )
    
    async def resolve_user_role(
        self,
        request: Request,
        tenant: Tenant,
        team: Optional[Team],
    ) -> Optional[TeamRole]:
        claims = self._decode_token(request)
        if not claims:
            return None
        
        role_str = claims.get("role", "member")
        try:
            return TeamRole(role_str)
        except ValueError:
            return TeamRole.MEMBER


class TenantMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for tenant context management.
    
    Automatically resolves tenant context from requests and makes it
    available throughout the request lifecycle.
    
    Usage:
        resolver = HeaderBasedResolver(tenant_store=my_store)
        quota_manager = QuotaManager()
        
        app.add_middleware(
            TenantMiddleware,
            resolver=resolver,
            quota_manager=quota_manager,
        )
    """
    
    def __init__(
        self,
        app,
        resolver: TenantResolver,
        quota_manager: Optional[QuotaManager] = None,
        require_tenant: bool = True,
        exclude_paths: Optional[list[str]] = None,
    ):
        super().__init__(app)
        self.resolver = resolver
        self.quota_manager = quota_manager
        self.require_tenant = require_tenant
        self.exclude_paths = exclude_paths or [
            "/health",
            "/api/docs",
            "/api/redoc",
            "/openapi.json",
        ]
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request with tenant context."""
        # Skip excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # Resolve tenant
        tenant = await self.resolver.resolve_tenant(request)
        
        if not tenant:
            if self.require_tenant:
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": "tenant_required",
                        "message": "Valid tenant context is required",
                    },
                )
            return await call_next(request)
        
        # Validate tenant status
        if not tenant.is_active:
            return JSONResponse(
                status_code=403,
                content={
                    "error": "tenant_inactive",
                    "message": f"Tenant is {tenant.status.value}",
                    "tenant_id": tenant.id,
                },
            )
        
        # Resolve workspace and team
        workspace = await self.resolver.resolve_workspace(request, tenant)
        team = await self.resolver.resolve_team(request, tenant, workspace)
        user_role = await self.resolver.resolve_user_role(request, tenant, team)
        
        # Create tenant context
        context = TenantContext(
            tenant=tenant,
            workspace=workspace,
            team=team,
            user_id=request.headers.get("X-User-ID"),
            user_role=user_role,
            request_id=request.headers.get("X-Request-ID"),
            correlation_id=request.headers.get("X-Correlation-ID"),
        )
        
        # Set context
        token = set_current_tenant(context)
        
        try:
            # Check rate limits
            if self.quota_manager:
                allowed = await self.quota_manager.check_rate_limit(
                    tenant,
                    context.workspace_id,
                    context.user_id,
                    request.url.path,
                )
                if not allowed:
                    retry_after = self.quota_manager.get_rate_limiter(tenant).get_retry_after(
                        tenant.id, context.workspace_id, context.user_id, request.url.path
                    )
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": "rate_limit_exceeded",
                            "message": "Too many requests",
                            "retry_after": int(retry_after),
                        },
                        headers={"Retry-After": str(int(retry_after))},
                    )
            
            # Process request
            start_time = time.time()
            response = await call_next(request)
            duration = time.time() - start_time
            
            # Add tenant context headers to response
            response.headers["X-Tenant-ID"] = tenant.id
            if workspace:
                response.headers["X-Workspace-ID"] = workspace.id
            response.headers["X-Request-Duration-Ms"] = str(int(duration * 1000))
            
            return response
            
        except QuotaExceededError as e:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "quota_exceeded",
                    "message": str(e),
                    "quota_type": e.quota_type.value,
                    "current": e.current,
                    "limit": e.limit,
                    "retry_after": e.retry_after,
                },
                headers={"Retry-After": str(e.retry_after or 60)},
            )
        finally:
            clear_tenant_context()


# FastAPI dependencies for tenant context

async def get_tenant_context(request: Request) -> TenantContext:
    """
    FastAPI dependency to get current tenant context.
    
    Usage:
        @app.get("/data")
        async def get_data(ctx: TenantContext = Depends(get_tenant_context)):
            return {"tenant_id": ctx.tenant_id}
    """
    ctx = get_current_tenant()
    if ctx is None:
        raise HTTPException(
            status_code=401,
            detail="No tenant context available",
        )
    return ctx


# Type alias for dependency injection
TenantContextDep = Annotated[TenantContext, Depends(get_tenant_context)]


def require_tenant(func: Callable) -> Callable:
    """
    Decorator to require tenant context for an endpoint.
    
    Usage:
        @app.get("/data")
        @require_tenant
        async def get_data():
            ctx = get_current_tenant()
            ...
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        ctx = get_current_tenant()
        if ctx is None:
            raise HTTPException(
                status_code=401,
                detail="Tenant context required",
            )
        return await func(*args, **kwargs)
    return wrapper


def require_workspace(func: Callable) -> Callable:
    """
    Decorator to require workspace context for an endpoint.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        ctx = get_current_tenant()
        if ctx is None or ctx.workspace is None:
            raise HTTPException(
                status_code=401,
                detail="Workspace context required",
            )
        return await func(*args, **kwargs)
    return wrapper


def require_team_role(required_role: TeamRole) -> Callable:
    """
    Decorator to require a minimum team role for an endpoint.
    
    Usage:
        @app.delete("/workspace/{id}")
        @require_team_role(TeamRole.ADMIN)
        async def delete_workspace(id: str):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            ctx = get_current_tenant()
            if ctx is None:
                raise HTTPException(
                    status_code=401,
                    detail="Tenant context required",
                )
            
            if ctx.user_role is None:
                raise HTTPException(
                    status_code=403,
                    detail="Role information not available",
                )
            
            # Check role hierarchy
            role_hierarchy = {
                TeamRole.OWNER: 4,
                TeamRole.ADMIN: 3,
                TeamRole.MEMBER: 2,
                TeamRole.VIEWER: 1,
                TeamRole.SERVICE_ACCOUNT: 2,
            }
            
            user_level = role_hierarchy.get(ctx.user_role, 0)
            required_level = role_hierarchy.get(required_role, 0)
            
            if user_level < required_level:
                raise HTTPException(
                    status_code=403,
                    detail=f"Requires {required_role.value} role or higher",
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Utility functions for API routes

async def get_tenant_from_header(
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
) -> str:
    """Get tenant ID from header."""
    return x_tenant_id


async def get_optional_workspace_from_header(
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-ID")] = None,
) -> Optional[str]:
    """Get optional workspace ID from header."""
    return x_workspace_id
