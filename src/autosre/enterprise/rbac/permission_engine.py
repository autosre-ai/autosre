"""Permission Engine for AutoSRE V2 RBAC.

Provides centralized permission checking and enforcement:
- Permission evaluation with context
- Caching for performance
- Batch permission checks
- Integration with role manager
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar
from uuid import uuid4

from pydantic import BaseModel, Field

from autosre.enterprise.rbac.role_manager import (
    Permission,
    ResourceAction,
    ResourceType,
    RoleManager,
)
from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class PermissionResult(BaseModel):
    """Result of a permission check."""
    
    allowed: bool
    user_id: str
    tenant_id: str
    resource_type: ResourceType
    action: ResourceAction
    
    # Details
    matched_permission: Optional[str] = None
    matched_role: Optional[str] = None
    
    # Denial reason if not allowed
    denial_reason: Optional[str] = None
    
    # Metadata
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cache_hit: bool = False
    check_duration_ms: Optional[float] = None


class PermissionCheck(BaseModel):
    """A permission check request."""
    
    user_id: str
    tenant_id: str
    resource_type: ResourceType
    action: ResourceAction
    
    # Optional context for condition evaluation
    resource_id: Optional[str] = None
    namespace_id: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)


class BatchPermissionResult(BaseModel):
    """Result of batch permission checks."""
    
    results: Dict[str, PermissionResult]  # check_id -> result
    all_allowed: bool
    any_allowed: bool
    duration_ms: float


class PermissionDeniedError(Exception):
    """Raised when a permission check fails."""
    
    def __init__(
        self,
        message: str,
        user_id: str,
        tenant_id: str,
        resource_type: ResourceType,
        action: ResourceAction,
        resource_id: Optional[str] = None,
    ):
        super().__init__(message)
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.resource_type = resource_type
        self.action = action
        self.resource_id = resource_id


class CacheEntry(BaseModel):
    """Permission cache entry."""
    
    result: PermissionResult
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PermissionEngine:
    """
    Evaluates and enforces permissions.
    
    Provides:
    - Efficient permission checking with caching
    - Context-aware permission evaluation
    - Batch permission checks
    - Permission enforcement decorators
    
    Example:
        engine = PermissionEngine(role_manager)
        
        # Check single permission
        result = await engine.check_permission(PermissionCheck(
            user_id="user-123",
            tenant_id="tenant-456",
            resource_type=ResourceType.ALERT,
            action=ResourceAction.READ,
        ))
        
        if not result.allowed:
            raise PermissionDeniedError(...)
        
        # Use decorator
        @engine.require_permission(ResourceType.ALERT, ResourceAction.UPDATE)
        async def update_alert(alert_id: str, data: dict):
            ...
    """
    
    def __init__(
        self,
        role_manager: RoleManager,
        cache_enabled: bool = True,
        cache_ttl_seconds: int = 300,
        max_cache_size: int = 10000,
    ):
        """Initialize PermissionEngine.
        
        Args:
            role_manager: RoleManager instance
            cache_enabled: Enable permission caching
            cache_ttl_seconds: Cache TTL in seconds
            max_cache_size: Maximum cache entries
        """
        self.role_manager = role_manager
        self.cache_enabled = cache_enabled
        self.cache_ttl_seconds = cache_ttl_seconds
        self.max_cache_size = max_cache_size
        
        self._cache: Dict[str, CacheEntry] = {}
        self._cache_lock = asyncio.Lock()
        self._check_count = 0
        self._cache_hits = 0
    
    async def check_permission(
        self,
        check: PermissionCheck,
        use_cache: bool = True,
    ) -> PermissionResult:
        """Check if a permission is granted.
        
        Args:
            check: Permission check request
            use_cache: Whether to use cache
            
        Returns:
            PermissionResult
        """
        import time
        start_time = time.time()
        self._check_count += 1
        
        # Try cache
        cache_key = self._get_cache_key(check)
        if self.cache_enabled and use_cache:
            cached = await self._get_cached(cache_key)
            if cached:
                self._cache_hits += 1
                cached.cache_hit = True
                cached.check_duration_ms = (time.time() - start_time) * 1000
                return cached
        
        # Perform check
        allowed = await self.role_manager.has_permission(
            user_id=check.user_id,
            tenant_id=check.tenant_id,
            resource_type=check.resource_type,
            action=check.action,
            context=check.context,
            namespace_id=check.namespace_id,
        )
        
        # Build result
        result = PermissionResult(
            allowed=allowed,
            user_id=check.user_id,
            tenant_id=check.tenant_id,
            resource_type=check.resource_type,
            action=check.action,
            denial_reason=None if allowed else f"No permission for {check.action.value} on {check.resource_type.value}",
            check_duration_ms=(time.time() - start_time) * 1000,
        )
        
        # Cache result
        if self.cache_enabled and use_cache:
            await self._set_cached(cache_key, result)
        
        return result
    
    async def check_permission_simple(
        self,
        user_id: str,
        tenant_id: str,
        resource_type: ResourceType,
        action: ResourceAction,
        resource_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Simple permission check returning bool.
        
        Args:
            user_id: User ID
            tenant_id: Tenant ID
            resource_type: Resource type
            action: Required action
            resource_id: Optional resource ID
            context: Optional context
            
        Returns:
            True if allowed
        """
        result = await self.check_permission(PermissionCheck(
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            action=action,
            resource_id=resource_id,
            context=context or {},
        ))
        return result.allowed
    
    async def enforce_permission(
        self,
        check: PermissionCheck,
    ) -> PermissionResult:
        """Check permission and raise if denied.
        
        Args:
            check: Permission check request
            
        Returns:
            PermissionResult (only if allowed)
            
        Raises:
            PermissionDeniedError: If permission denied
        """
        result = await self.check_permission(check)
        
        if not result.allowed:
            raise PermissionDeniedError(
                message=result.denial_reason or "Permission denied",
                user_id=check.user_id,
                tenant_id=check.tenant_id,
                resource_type=check.resource_type,
                action=check.action,
                resource_id=check.resource_id,
            )
        
        return result
    
    async def check_batch(
        self,
        checks: List[PermissionCheck],
    ) -> BatchPermissionResult:
        """Check multiple permissions in batch.
        
        Args:
            checks: List of permission checks
            
        Returns:
            BatchPermissionResult
        """
        import time
        start_time = time.time()
        
        results: Dict[str, PermissionResult] = {}
        
        # Run checks concurrently
        async def check_one(idx: int, check: PermissionCheck):
            result = await self.check_permission(check)
            return str(idx), result
        
        tasks = [check_one(i, c) for i, c in enumerate(checks)]
        completed = await asyncio.gather(*tasks)
        
        for check_id, result in completed:
            results[check_id] = result
        
        all_allowed = all(r.allowed for r in results.values())
        any_allowed = any(r.allowed for r in results.values())
        
        return BatchPermissionResult(
            results=results,
            all_allowed=all_allowed,
            any_allowed=any_allowed,
            duration_ms=(time.time() - start_time) * 1000,
        )
    
    async def filter_allowed(
        self,
        user_id: str,
        tenant_id: str,
        resource_type: ResourceType,
        action: ResourceAction,
        resource_ids: List[str],
        context_getter: Optional[Callable[[str], Dict[str, Any]]] = None,
    ) -> List[str]:
        """Filter a list of resources to only those the user can access.
        
        Args:
            user_id: User ID
            tenant_id: Tenant ID
            resource_type: Resource type
            action: Required action
            resource_ids: List of resource IDs to check
            context_getter: Optional function to get context for each resource
            
        Returns:
            List of allowed resource IDs
        """
        checks = []
        for rid in resource_ids:
            context = context_getter(rid) if context_getter else {}
            checks.append(PermissionCheck(
                user_id=user_id,
                tenant_id=tenant_id,
                resource_type=resource_type,
                action=action,
                resource_id=rid,
                context=context,
            ))
        
        batch_result = await self.check_batch(checks)
        
        allowed_ids = []
        for idx, rid in enumerate(resource_ids):
            if batch_result.results[str(idx)].allowed:
                allowed_ids.append(rid)
        
        return allowed_ids
    
    def require_permission(
        self,
        resource_type: ResourceType,
        action: ResourceAction,
        resource_id_param: Optional[str] = None,
        context_params: Optional[List[str]] = None,
    ):
        """Decorator to require permission for a function.
        
        Args:
            resource_type: Required resource type
            action: Required action
            resource_id_param: Name of parameter containing resource ID
            context_params: Names of parameters to include in context
            
        Returns:
            Decorator function
            
        Example:
            @engine.require_permission(ResourceType.ALERT, ResourceAction.UPDATE, "alert_id")
            async def update_alert(alert_id: str, user_id: str, tenant_id: str):
                ...
        """
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Extract user_id and tenant_id from kwargs
                user_id = kwargs.get('user_id')
                tenant_id = kwargs.get('tenant_id')
                
                if not user_id or not tenant_id:
                    raise ValueError("user_id and tenant_id must be provided")
                
                # Build resource_id
                resource_id = None
                if resource_id_param:
                    resource_id = kwargs.get(resource_id_param)
                
                # Build context
                context = {}
                if context_params:
                    for param in context_params:
                        if param in kwargs:
                            context[param] = kwargs[param]
                
                # Check permission
                await self.enforce_permission(PermissionCheck(
                    user_id=user_id,
                    tenant_id=tenant_id,
                    resource_type=resource_type,
                    action=action,
                    resource_id=resource_id,
                    context=context,
                ))
                
                return await func(*args, **kwargs)
            
            return wrapper
        return decorator
    
    async def invalidate_cache(
        self,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> int:
        """Invalidate cached permissions.
        
        Args:
            user_id: Invalidate for specific user
            tenant_id: Invalidate for specific tenant
            
        Returns:
            Number of entries invalidated
        """
        async with self._cache_lock:
            if not user_id and not tenant_id:
                count = len(self._cache)
                self._cache.clear()
                return count
            
            keys_to_remove = []
            for key, entry in self._cache.items():
                if user_id and entry.result.user_id == user_id:
                    keys_to_remove.append(key)
                elif tenant_id and entry.result.tenant_id == tenant_id:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self._cache[key]
            
            return len(keys_to_remove)
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Cache statistics
        """
        return {
            "enabled": self.cache_enabled,
            "size": len(self._cache),
            "max_size": self.max_cache_size,
            "ttl_seconds": self.cache_ttl_seconds,
            "total_checks": self._check_count,
            "cache_hits": self._cache_hits,
            "hit_rate": self._cache_hits / self._check_count if self._check_count > 0 else 0,
        }
    
    def _get_cache_key(self, check: PermissionCheck) -> str:
        """Generate cache key for a permission check."""
        key_data = {
            "user_id": check.user_id,
            "tenant_id": check.tenant_id,
            "resource_type": check.resource_type.value,
            "action": check.action.value,
            "namespace_id": check.namespace_id,
            "context": json.dumps(check.context, sort_keys=True),
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()[:32]
    
    async def _get_cached(self, key: str) -> Optional[PermissionResult]:
        """Get cached permission result."""
        async with self._cache_lock:
            entry = self._cache.get(key)
            if not entry:
                return None
            
            # Check expiry
            if datetime.now(timezone.utc) > entry.expires_at:
                del self._cache[key]
                return None
            
            return entry.result.model_copy()
    
    async def _set_cached(self, key: str, result: PermissionResult) -> None:
        """Cache a permission result."""
        from datetime import timedelta
        
        async with self._cache_lock:
            # Evict if at capacity
            if len(self._cache) >= self.max_cache_size:
                # Remove oldest 10%
                entries_by_time = sorted(
                    self._cache.items(),
                    key=lambda x: x[1].created_at,
                )
                for old_key, _ in entries_by_time[:self.max_cache_size // 10]:
                    del self._cache[old_key]
            
            self._cache[key] = CacheEntry(
                result=result,
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=self.cache_ttl_seconds),
            )


class PermissionMiddleware:
    """
    FastAPI middleware for permission checking.
    
    Example:
        app.middleware("http")(PermissionMiddleware(
            engine=permission_engine,
            route_permissions={
                "/api/v1/alerts": (ResourceType.ALERT, ResourceAction.LIST),
                "/api/v1/alerts/*": (ResourceType.ALERT, ResourceAction.READ),
            },
        ))
    """
    
    def __init__(
        self,
        engine: PermissionEngine,
        route_permissions: Optional[Dict[str, tuple]] = None,
        exclude_paths: Optional[Set[str]] = None,
        user_extractor: Optional[Callable] = None,
    ):
        """Initialize PermissionMiddleware.
        
        Args:
            engine: PermissionEngine instance
            route_permissions: Map of path patterns to (resource_type, action) tuples
            exclude_paths: Paths to exclude from checks
            user_extractor: Function to extract (user_id, tenant_id) from request
        """
        self.engine = engine
        self.route_permissions = route_permissions or {}
        self.exclude_paths = exclude_paths or {'/health', '/metrics', '/api/docs'}
        self.user_extractor = user_extractor
    
    async def __call__(self, request: Any, call_next: Callable) -> Any:
        """Process request with permission check."""
        path = str(request.url.path)
        
        # Check exclusions
        if path in self.exclude_paths:
            return await call_next(request)
        
        # Find matching permission requirement
        permission_req = self._find_permission_requirement(path, request.method)
        if not permission_req:
            return await call_next(request)
        
        # Extract user info
        if self.user_extractor:
            user_id, tenant_id = self.user_extractor(request)
        elif hasattr(request.state, 'user'):
            user_id = request.state.user.id
            tenant_id = getattr(request.state, 'tenant_id', None)
        else:
            # No user info, deny
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=401,
                content={"error": "authentication_required"},
            )
        
        if not tenant_id:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=400,
                content={"error": "tenant_id_required"},
            )
        
        # Check permission
        resource_type, action = permission_req
        try:
            await self.engine.enforce_permission(PermissionCheck(
                user_id=user_id,
                tenant_id=tenant_id,
                resource_type=resource_type,
                action=action,
            ))
        except PermissionDeniedError as e:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=403,
                content={
                    "error": "permission_denied",
                    "message": str(e),
                    "resource_type": e.resource_type.value,
                    "action": e.action.value,
                },
            )
        
        return await call_next(request)
    
    def _find_permission_requirement(
        self,
        path: str,
        method: str,
    ) -> Optional[tuple]:
        """Find permission requirement for a path."""
        import fnmatch
        
        # Try exact match first
        if path in self.route_permissions:
            return self.route_permissions[path]
        
        # Try method-specific match
        method_path = f"{method}:{path}"
        if method_path in self.route_permissions:
            return self.route_permissions[method_path]
        
        # Try wildcard patterns
        for pattern, perm in self.route_permissions.items():
            if fnmatch.fnmatch(path, pattern):
                return perm
        
        return None
