"""Tenant Router for AutoSRE V2 Multi-Tenancy.

Provides request routing and tenant context management:
- Tenant identification from requests
- Tenant context propagation
- Multi-tenant middleware
- Subdomain and path-based routing
"""

from __future__ import annotations

import asyncio
import re
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Awaitable, TypeVar
from uuid import uuid4

from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger

logger = get_logger(__name__)


# Context variable for tenant context
_tenant_context: ContextVar[Optional["TenantContext"]] = ContextVar(
    "tenant_context", default=None
)


class TenantIdentificationMethod(str, Enum):
    """Methods for identifying tenant from requests."""
    
    HEADER = "header"  # X-Tenant-ID or similar header
    SUBDOMAIN = "subdomain"  # tenant.example.com
    PATH = "path"  # /api/v1/tenants/{tenant_id}/...
    API_KEY = "api_key"  # API key lookup
    JWT_CLAIM = "jwt_claim"  # Claim in JWT token
    QUERY_PARAM = "query_param"  # ?tenant_id=xxx


@dataclass
class TenantContext:
    """Context containing tenant information for the current request.
    
    This context is propagated through the request lifecycle and
    can be accessed anywhere using get_current_tenant_context().
    """
    
    tenant_id: str
    tenant_slug: Optional[str] = None
    tenant_name: Optional[str] = None
    
    # Identification
    identified_by: TenantIdentificationMethod = TenantIdentificationMethod.HEADER
    
    # User context (if authenticated)
    user_id: Optional[str] = None
    user_roles: List[str] = field(default_factory=list)
    
    # Effective permissions
    permissions: List[str] = field(default_factory=list)
    
    # Namespace
    namespace_id: Optional[str] = None
    database_schema: Optional[str] = None
    
    # Request metadata
    request_id: str = field(default_factory=lambda: str(uuid4()))
    request_timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    
    # Extracted from request
    source_ip: Optional[str] = None
    user_agent: Optional[str] = None
    
    def has_permission(self, permission: str) -> bool:
        """Check if context has a specific permission."""
        return permission in self.permissions
    
    def has_role(self, role: str) -> bool:
        """Check if context has a specific role."""
        return role in self.user_roles
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        return {
            "tenant_id": self.tenant_id,
            "tenant_slug": self.tenant_slug,
            "user_id": self.user_id,
            "request_id": self.request_id,
            "identified_by": self.identified_by.value,
        }


def get_current_tenant_context() -> Optional[TenantContext]:
    """Get the current tenant context from context var.
    
    Returns:
        TenantContext if set, None otherwise
    """
    return _tenant_context.get()


def set_tenant_context(context: TenantContext) -> None:
    """Set the current tenant context.
    
    Args:
        context: TenantContext to set
    """
    _tenant_context.set(context)


def clear_tenant_context() -> None:
    """Clear the current tenant context."""
    _tenant_context.set(None)


def require_tenant_context() -> TenantContext:
    """Get current tenant context or raise if not set.
    
    Returns:
        TenantContext
        
    Raises:
        RuntimeError: If no tenant context is set
    """
    context = get_current_tenant_context()
    if context is None:
        raise RuntimeError("No tenant context available")
    return context


class TenantIdentifier(BaseModel):
    """Configuration for tenant identification."""
    
    # Enabled methods (in priority order)
    methods: List[TenantIdentificationMethod] = Field(
        default_factory=lambda: [
            TenantIdentificationMethod.JWT_CLAIM,
            TenantIdentificationMethod.API_KEY,
            TenantIdentificationMethod.HEADER,
        ]
    )
    
    # Header configuration
    header_name: str = "X-Tenant-ID"
    header_prefix: str = ""  # e.g., "tenant:"
    
    # Subdomain configuration
    subdomain_suffix: str = ".example.com"
    
    # Path configuration
    path_pattern: str = r"/api/v\d+/tenants/([^/]+)"
    
    # Query param configuration
    query_param_name: str = "tenant_id"
    
    # JWT claim configuration
    jwt_claim_name: str = "tenant_id"
    
    # API key configuration
    api_key_header: str = "X-API-Key"
    api_key_prefix: str = "asr_"


class TenantResolverResult(BaseModel):
    """Result of tenant resolution."""
    
    resolved: bool = False
    tenant_id: Optional[str] = None
    tenant_slug: Optional[str] = None
    method: Optional[TenantIdentificationMethod] = None
    error: Optional[str] = None


# Type for tenant lookup functions
TenantLookup = Callable[[str], Awaitable[Optional[Dict[str, Any]]]]
APIKeyValidator = Callable[[str], Awaitable[Optional[str]]]


class TenantRouter:
    """
    Routes requests to the correct tenant context.
    
    Provides:
    - Multiple identification methods
    - Configurable priority
    - Tenant lookup and validation
    - Context creation and propagation
    
    Example:
        router = TenantRouter(
            identifier=TenantIdentifier(
                methods=[
                    TenantIdentificationMethod.JWT_CLAIM,
                    TenantIdentificationMethod.HEADER,
                ]
            ),
            tenant_lookup=tenant_manager.get_tenant,
        )
        
        # In middleware
        context = await router.resolve_tenant(request)
        set_tenant_context(context)
    """
    
    def __init__(
        self,
        identifier: Optional[TenantIdentifier] = None,
        tenant_lookup: Optional[TenantLookup] = None,
        api_key_validator: Optional[APIKeyValidator] = None,
        default_tenant_id: Optional[str] = None,
        require_tenant: bool = True,
    ):
        """Initialize TenantRouter.
        
        Args:
            identifier: Tenant identification configuration
            tenant_lookup: Async function to lookup tenant by ID/slug
            api_key_validator: Async function to validate API key and return tenant_id
            default_tenant_id: Default tenant if none identified
            require_tenant: Whether to require tenant identification
        """
        self.identifier = identifier or TenantIdentifier()
        self.tenant_lookup = tenant_lookup
        self.api_key_validator = api_key_validator
        self.default_tenant_id = default_tenant_id
        self.require_tenant = require_tenant
        
        # Compile regex patterns
        self._path_pattern = re.compile(self.identifier.path_pattern)
    
    async def resolve_tenant(
        self,
        request: Any,
        jwt_payload: Optional[Dict[str, Any]] = None,
    ) -> TenantResolverResult:
        """Resolve tenant from request.
        
        Args:
            request: HTTP request object
            jwt_payload: Decoded JWT payload if available
            
        Returns:
            TenantResolverResult
        """
        for method in self.identifier.methods:
            result = await self._try_method(request, method, jwt_payload)
            if result.resolved:
                return result
        
        # Use default if available
        if self.default_tenant_id:
            return TenantResolverResult(
                resolved=True,
                tenant_id=self.default_tenant_id,
                method=TenantIdentificationMethod.HEADER,
            )
        
        return TenantResolverResult(
            resolved=False,
            error="Could not identify tenant from request",
        )
    
    async def create_context(
        self,
        request: Any,
        jwt_payload: Optional[Dict[str, Any]] = None,
    ) -> TenantContext:
        """Create tenant context from request.
        
        Args:
            request: HTTP request object
            jwt_payload: Decoded JWT payload if available
            
        Returns:
            TenantContext
            
        Raises:
            TenantNotIdentifiedError: If tenant cannot be identified and required
        """
        result = await self.resolve_tenant(request, jwt_payload)
        
        if not result.resolved:
            if self.require_tenant:
                raise TenantNotIdentifiedError(result.error or "Tenant not identified")
            # Return anonymous context
            return TenantContext(
                tenant_id="anonymous",
                identified_by=TenantIdentificationMethod.HEADER,
            )
        
        # Lookup tenant details if lookup function provided
        tenant_data: Dict[str, Any] = {}
        if self.tenant_lookup and result.tenant_id:
            tenant_data = await self.tenant_lookup(result.tenant_id) or {}
        
        # Extract user info from JWT
        user_id = None
        user_roles: List[str] = []
        if jwt_payload:
            user_id = jwt_payload.get("sub")
            user_roles = jwt_payload.get("roles", [])
        
        # Create context
        context = TenantContext(
            tenant_id=result.tenant_id or "",
            tenant_slug=result.tenant_slug or tenant_data.get("slug"),
            tenant_name=tenant_data.get("name"),
            identified_by=result.method or TenantIdentificationMethod.HEADER,
            user_id=user_id,
            user_roles=user_roles,
            namespace_id=tenant_data.get("namespace_id"),
            database_schema=tenant_data.get("database_schema"),
            source_ip=self._get_client_ip(request),
            user_agent=self._get_user_agent(request),
        )
        
        return context
    
    async def _try_method(
        self,
        request: Any,
        method: TenantIdentificationMethod,
        jwt_payload: Optional[Dict[str, Any]],
    ) -> TenantResolverResult:
        """Try a single identification method.
        
        Args:
            request: HTTP request
            method: Method to try
            jwt_payload: JWT payload if available
            
        Returns:
            TenantResolverResult
        """
        try:
            if method == TenantIdentificationMethod.JWT_CLAIM:
                return await self._from_jwt(jwt_payload)
            elif method == TenantIdentificationMethod.API_KEY:
                return await self._from_api_key(request)
            elif method == TenantIdentificationMethod.HEADER:
                return self._from_header(request)
            elif method == TenantIdentificationMethod.SUBDOMAIN:
                return self._from_subdomain(request)
            elif method == TenantIdentificationMethod.PATH:
                return self._from_path(request)
            elif method == TenantIdentificationMethod.QUERY_PARAM:
                return self._from_query_param(request)
        except Exception as e:
            logger.debug(
                "Tenant identification method failed",
                method=method.value,
                error=str(e),
            )
        
        return TenantResolverResult(resolved=False)
    
    async def _from_jwt(
        self,
        jwt_payload: Optional[Dict[str, Any]],
    ) -> TenantResolverResult:
        """Extract tenant from JWT claim."""
        if not jwt_payload:
            return TenantResolverResult(resolved=False)
        
        tenant_id = jwt_payload.get(self.identifier.jwt_claim_name)
        if tenant_id:
            return TenantResolverResult(
                resolved=True,
                tenant_id=str(tenant_id),
                method=TenantIdentificationMethod.JWT_CLAIM,
            )
        
        return TenantResolverResult(resolved=False)
    
    async def _from_api_key(self, request: Any) -> TenantResolverResult:
        """Extract tenant from API key."""
        api_key = self._get_header(request, self.identifier.api_key_header)
        
        if not api_key:
            return TenantResolverResult(resolved=False)
        
        # Check prefix
        if not api_key.startswith(self.identifier.api_key_prefix):
            return TenantResolverResult(resolved=False)
        
        # Validate API key
        if self.api_key_validator:
            tenant_id = await self.api_key_validator(api_key)
            if tenant_id:
                return TenantResolverResult(
                    resolved=True,
                    tenant_id=tenant_id,
                    method=TenantIdentificationMethod.API_KEY,
                )
        
        # Try to extract tenant slug from key format: asr_{slug}_{secret}
        parts = api_key.split("_")
        if len(parts) >= 3:
            tenant_slug = parts[1]
            return TenantResolverResult(
                resolved=True,
                tenant_slug=tenant_slug,
                method=TenantIdentificationMethod.API_KEY,
            )
        
        return TenantResolverResult(resolved=False)
    
    def _from_header(self, request: Any) -> TenantResolverResult:
        """Extract tenant from header."""
        header_value = self._get_header(request, self.identifier.header_name)
        
        if not header_value:
            return TenantResolverResult(resolved=False)
        
        # Strip prefix if configured
        if self.identifier.header_prefix:
            if header_value.startswith(self.identifier.header_prefix):
                header_value = header_value[len(self.identifier.header_prefix):]
            else:
                return TenantResolverResult(resolved=False)
        
        return TenantResolverResult(
            resolved=True,
            tenant_id=header_value,
            method=TenantIdentificationMethod.HEADER,
        )
    
    def _from_subdomain(self, request: Any) -> TenantResolverResult:
        """Extract tenant from subdomain."""
        host = self._get_host(request)
        
        if not host:
            return TenantResolverResult(resolved=False)
        
        # Check if host ends with expected suffix
        suffix = self.identifier.subdomain_suffix
        if not host.endswith(suffix):
            return TenantResolverResult(resolved=False)
        
        # Extract subdomain
        subdomain = host[:-len(suffix)]
        if not subdomain or subdomain in ('www', 'api', 'app'):
            return TenantResolverResult(resolved=False)
        
        return TenantResolverResult(
            resolved=True,
            tenant_slug=subdomain,
            method=TenantIdentificationMethod.SUBDOMAIN,
        )
    
    def _from_path(self, request: Any) -> TenantResolverResult:
        """Extract tenant from URL path."""
        path = self._get_path(request)
        
        if not path:
            return TenantResolverResult(resolved=False)
        
        match = self._path_pattern.match(path)
        if match:
            tenant_id = match.group(1)
            return TenantResolverResult(
                resolved=True,
                tenant_id=tenant_id,
                method=TenantIdentificationMethod.PATH,
            )
        
        return TenantResolverResult(resolved=False)
    
    def _from_query_param(self, request: Any) -> TenantResolverResult:
        """Extract tenant from query parameter."""
        tenant_id = self._get_query_param(
            request,
            self.identifier.query_param_name,
        )
        
        if tenant_id:
            return TenantResolverResult(
                resolved=True,
                tenant_id=tenant_id,
                method=TenantIdentificationMethod.QUERY_PARAM,
            )
        
        return TenantResolverResult(resolved=False)
    
    # Request abstraction methods (work with different frameworks)
    
    def _get_header(self, request: Any, name: str) -> Optional[str]:
        """Get header from request."""
        # FastAPI/Starlette
        if hasattr(request, 'headers'):
            return request.headers.get(name)
        # Flask
        if hasattr(request, 'headers') and hasattr(request.headers, 'get'):
            return request.headers.get(name)
        # Dict-like
        if isinstance(request, dict):
            headers = request.get('headers', {})
            return headers.get(name)
        return None
    
    def _get_host(self, request: Any) -> Optional[str]:
        """Get host from request."""
        # Try headers first
        host = self._get_header(request, 'Host')
        if host:
            return host.split(':')[0]  # Remove port
        
        # FastAPI/Starlette
        if hasattr(request, 'url') and hasattr(request.url, 'hostname'):
            return request.url.hostname
        
        return None
    
    def _get_path(self, request: Any) -> Optional[str]:
        """Get URL path from request."""
        # FastAPI/Starlette
        if hasattr(request, 'url') and hasattr(request.url, 'path'):
            return request.url.path
        # Flask
        if hasattr(request, 'path'):
            return request.path
        # Dict-like
        if isinstance(request, dict):
            return request.get('path')
        return None
    
    def _get_query_param(self, request: Any, name: str) -> Optional[str]:
        """Get query parameter from request."""
        # FastAPI/Starlette
        if hasattr(request, 'query_params'):
            return request.query_params.get(name)
        # Flask
        if hasattr(request, 'args'):
            return request.args.get(name)
        return None
    
    def _get_client_ip(self, request: Any) -> Optional[str]:
        """Get client IP from request."""
        # Check forwarded headers first
        forwarded = self._get_header(request, 'X-Forwarded-For')
        if forwarded:
            return forwarded.split(',')[0].strip()
        
        real_ip = self._get_header(request, 'X-Real-IP')
        if real_ip:
            return real_ip
        
        # FastAPI/Starlette
        if hasattr(request, 'client') and request.client:
            return request.client.host
        
        return None
    
    def _get_user_agent(self, request: Any) -> Optional[str]:
        """Get user agent from request."""
        return self._get_header(request, 'User-Agent')


class TenantNotIdentifiedError(Exception):
    """Raised when tenant cannot be identified from request."""
    pass


class TenantMiddleware:
    """
    Middleware for automatic tenant context setup.
    
    Works with FastAPI/Starlette applications.
    
    Example:
        from fastapi import FastAPI
        
        app = FastAPI()
        
        middleware = TenantMiddleware(
            router=TenantRouter(...),
            exclude_paths=["/health", "/metrics"],
        )
        
        app.middleware("http")(middleware)
    """
    
    def __init__(
        self,
        router: TenantRouter,
        exclude_paths: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        on_tenant_resolved: Optional[Callable[[TenantContext], Awaitable[None]]] = None,
    ):
        """Initialize TenantMiddleware.
        
        Args:
            router: TenantRouter instance
            exclude_paths: Exact paths to exclude from tenant resolution
            exclude_patterns: Regex patterns to exclude
            on_tenant_resolved: Callback when tenant is resolved
        """
        self.router = router
        self.exclude_paths = set(exclude_paths or [])
        self.exclude_patterns = [
            re.compile(p) for p in (exclude_patterns or [])
        ]
        self.on_tenant_resolved = on_tenant_resolved
        
        # Add common excluded paths
        self.exclude_paths.update({
            '/health',
            '/healthz',
            '/ready',
            '/readyz',
            '/metrics',
            '/api/docs',
            '/api/redoc',
            '/api/openapi.json',
        })
    
    async def __call__(self, request: Any, call_next: Callable) -> Any:
        """Process request with tenant context."""
        path = self._get_path(request)
        
        # Check exclusions
        if self._should_exclude(path):
            return await call_next(request)
        
        # Get JWT payload if available
        jwt_payload = self._get_jwt_payload(request)
        
        try:
            # Create and set tenant context
            context = await self.router.create_context(request, jwt_payload)
            set_tenant_context(context)
            
            # Store in request state for access in routes
            if hasattr(request, 'state'):
                request.state.tenant_context = context
                request.state.tenant_id = context.tenant_id
            
            # Callback
            if self.on_tenant_resolved:
                await self.on_tenant_resolved(context)
            
            # Log
            logger.debug(
                "Tenant context set",
                tenant_id=context.tenant_id,
                method=context.identified_by.value,
                request_id=context.request_id,
            )
            
            # Process request
            response = await call_next(request)
            
            # Add tenant ID to response headers
            if hasattr(response, 'headers'):
                response.headers['X-Tenant-ID'] = context.tenant_id
                response.headers['X-Request-ID'] = context.request_id
            
            return response
            
        except TenantNotIdentifiedError as e:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=401,
                content={
                    "error": "tenant_not_identified",
                    "message": str(e),
                },
            )
        finally:
            # Always clear context
            clear_tenant_context()
    
    def _get_path(self, request: Any) -> str:
        """Get path from request."""
        if hasattr(request, 'url') and hasattr(request.url, 'path'):
            return request.url.path
        return '/'
    
    def _should_exclude(self, path: str) -> bool:
        """Check if path should be excluded."""
        # Exact match
        if path in self.exclude_paths:
            return True
        
        # Pattern match
        for pattern in self.exclude_patterns:
            if pattern.match(path):
                return True
        
        return False
    
    def _get_jwt_payload(self, request: Any) -> Optional[Dict[str, Any]]:
        """Get JWT payload from request state if available."""
        if hasattr(request, 'state') and hasattr(request.state, 'user'):
            user = request.state.user
            if hasattr(user, 'model_dump'):
                return user.model_dump()
            elif hasattr(user, 'dict'):
                return user.dict()
            elif isinstance(user, dict):
                return user
        return None


def tenant_scoped(func: Callable) -> Callable:
    """Decorator to ensure function runs in tenant context.
    
    Example:
        @tenant_scoped
        async def get_alerts():
            context = require_tenant_context()
            # ... fetch alerts for context.tenant_id
    """
    import functools
    
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        context = get_current_tenant_context()
        if context is None:
            raise RuntimeError(f"Function {func.__name__} requires tenant context")
        return await func(*args, **kwargs)
    
    return wrapper
