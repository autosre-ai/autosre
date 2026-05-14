"""Resource Isolation for AutoSRE V2 Multi-Tenancy.

Provides complete resource isolation between tenants including:
- Namespace-based isolation for all resources
- Data segregation at database and storage levels
- Network isolation policies
- Resource tagging and ownership tracking
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar, Set
from uuid import uuid4

from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class IsolationLevel(str, Enum):
    """Level of resource isolation between tenants."""
    
    # All tenants share resources with logical separation (tags/prefixes)
    SHARED = "shared"
    
    # Resources are logically isolated (separate schemas, namespaces)
    LOGICAL = "logical"
    
    # Resources are physically isolated (separate databases, clusters)
    PHYSICAL = "physical"
    
    # Complete isolation with dedicated infrastructure
    DEDICATED = "dedicated"


class ResourceType(str, Enum):
    """Types of resources that can be isolated."""
    
    # Data resources
    ALERT = "alert"
    INVESTIGATION = "investigation"
    RUNBOOK = "runbook"
    OBSERVATION = "observation"
    ACTION = "action"
    CHAT_MESSAGE = "chat_message"
    
    # Configuration resources
    INTEGRATION = "integration"
    NOTIFICATION_CHANNEL = "notification_channel"
    ESCALATION_POLICY = "escalation_policy"
    
    # User resources
    USER = "user"
    ROLE = "role"
    API_KEY = "api_key"
    
    # Infrastructure resources
    CLUSTER = "cluster"
    NAMESPACE = "namespace"
    SECRET = "secret"


class ResourceNamespace(BaseModel):
    """A namespace for tenant resource isolation."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    name: str
    display_name: Optional[str] = None
    
    # Isolation configuration
    isolation_level: IsolationLevel = IsolationLevel.LOGICAL
    
    # Resource identifiers
    database_schema: Optional[str] = None
    kubernetes_namespace: Optional[str] = None
    storage_bucket: Optional[str] = None
    
    # Labels for resource tagging
    labels: Dict[str, str] = Field(default_factory=dict)
    
    # Access control
    allowed_users: Set[str] = Field(default_factory=set)
    allowed_roles: Set[str] = Field(default_factory=set)
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def get_prefixed_name(self, base_name: str) -> str:
        """Get a resource name prefixed with namespace."""
        return f"{self.name}-{base_name}"
    
    def get_labels(self) -> Dict[str, str]:
        """Get labels for resource tagging."""
        return {
            "autosre.io/tenant-id": self.tenant_id,
            "autosre.io/namespace": self.name,
            "autosre.io/isolation-level": self.isolation_level.value,
            **self.labels,
        }


class IsolationPolicy(BaseModel):
    """Policy defining isolation rules for resources."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: Optional[str] = None
    
    # Scope
    tenant_id: Optional[str] = None  # None = global policy
    resource_types: List[ResourceType] = Field(default_factory=list)
    
    # Isolation rules
    isolation_level: IsolationLevel = IsolationLevel.LOGICAL
    
    # Data access rules
    allow_cross_tenant_read: bool = False
    allow_cross_tenant_write: bool = False
    
    # Network rules
    allow_external_access: bool = True
    allowed_ip_ranges: List[str] = Field(default_factory=list)
    
    # Encryption rules
    require_encryption_at_rest: bool = True
    require_encryption_in_transit: bool = True
    encryption_key_id: Optional[str] = None
    
    # Retention rules
    retention_days: Optional[int] = None
    
    # Priority (higher = more precedence)
    priority: int = 0
    
    # Status
    enabled: bool = True
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IsolatedResource(BaseModel):
    """A resource with isolation metadata."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    namespace_id: str
    resource_type: ResourceType
    resource_id: str
    
    # Labels
    labels: Dict[str, str] = Field(default_factory=dict)
    
    # Access tracking
    created_by: Optional[str] = None
    last_accessed_by: Optional[str] = None
    last_accessed_at: Optional[datetime] = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IsolationViolation(BaseModel):
    """Record of an isolation policy violation."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    
    # Context
    tenant_id: str
    user_id: Optional[str] = None
    resource_type: ResourceType
    resource_id: str
    
    # Violation details
    policy_id: str
    violation_type: str
    details: str
    
    # Target (for cross-tenant violations)
    target_tenant_id: Optional[str] = None
    target_resource_id: Optional[str] = None
    
    # Action taken
    action_taken: str = "blocked"  # blocked, logged, allowed
    
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


T = TypeVar('T')


class IsolationContext(BaseModel):
    """Context for isolated operations."""
    
    tenant_id: str
    namespace_id: Optional[str] = None
    user_id: Optional[str] = None
    roles: List[str] = Field(default_factory=list)
    
    # Effective policies
    policies: List[IsolationPolicy] = Field(default_factory=list)
    
    # Permissions derived from context
    can_read_cross_tenant: bool = False
    can_write_cross_tenant: bool = False
    
    @classmethod
    def for_tenant(
        cls,
        tenant_id: str,
        user_id: Optional[str] = None,
        roles: Optional[List[str]] = None,
    ) -> "IsolationContext":
        """Create an isolation context for a tenant."""
        return cls(
            tenant_id=tenant_id,
            user_id=user_id,
            roles=roles or [],
        )


class ResourceIsolation:
    """
    Manages resource isolation between tenants.
    
    Provides:
    - Namespace management per tenant
    - Resource registration and tracking
    - Policy enforcement
    - Cross-tenant access control
    - Violation logging
    
    Example:
        isolation = ResourceIsolation()
        
        # Create namespace for tenant
        namespace = await isolation.create_namespace(
            tenant_id="tenant-123",
            name="production",
            isolation_level=IsolationLevel.LOGICAL,
        )
        
        # Register a resource
        await isolation.register_resource(
            tenant_id="tenant-123",
            namespace_id=namespace.id,
            resource_type=ResourceType.ALERT,
            resource_id="alert-456",
        )
        
        # Check access
        context = IsolationContext.for_tenant("tenant-789")
        can_access = await isolation.can_access_resource(
            context,
            "tenant-123",
            "alert-456",
        )
    """
    
    def __init__(
        self,
        default_isolation_level: IsolationLevel = IsolationLevel.LOGICAL,
    ):
        """Initialize ResourceIsolation.
        
        Args:
            default_isolation_level: Default isolation level for new namespaces
        """
        self._default_isolation_level = default_isolation_level
        self._namespaces: Dict[str, ResourceNamespace] = {}
        self._policies: Dict[str, IsolationPolicy] = {}
        self._resources: Dict[str, IsolatedResource] = {}
        self._violations: List[IsolationViolation] = []
        self._lock = asyncio.Lock()
        
        # Index for fast lookups
        self._tenant_namespaces: Dict[str, Set[str]] = {}
        self._resource_index: Dict[str, Set[str]] = {}  # tenant_id -> resource_ids
    
    async def create_namespace(
        self,
        tenant_id: str,
        name: str,
        isolation_level: Optional[IsolationLevel] = None,
        labels: Optional[Dict[str, str]] = None,
    ) -> ResourceNamespace:
        """Create a new namespace for a tenant.
        
        Args:
            tenant_id: Tenant ID
            name: Namespace name
            isolation_level: Isolation level
            labels: Additional labels
            
        Returns:
            Created namespace
        """
        async with self._lock:
            namespace = ResourceNamespace(
                tenant_id=tenant_id,
                name=name,
                isolation_level=isolation_level or self._default_isolation_level,
                database_schema=f"tenant_{tenant_id.replace('-', '_')}_{name}",
                kubernetes_namespace=f"autosre-{tenant_id[:8]}-{name}",
                storage_bucket=f"autosre-{tenant_id}-{name}",
                labels=labels or {},
            )
            
            self._namespaces[namespace.id] = namespace
            
            if tenant_id not in self._tenant_namespaces:
                self._tenant_namespaces[tenant_id] = set()
            self._tenant_namespaces[tenant_id].add(namespace.id)
            
            logger.info(
                "Created namespace",
                tenant_id=tenant_id,
                namespace_id=namespace.id,
                name=name,
            )
            
            return namespace
    
    async def get_namespace(
        self,
        namespace_id: str,
    ) -> Optional[ResourceNamespace]:
        """Get a namespace by ID."""
        return self._namespaces.get(namespace_id)
    
    async def get_tenant_namespaces(
        self,
        tenant_id: str,
    ) -> List[ResourceNamespace]:
        """Get all namespaces for a tenant."""
        namespace_ids = self._tenant_namespaces.get(tenant_id, set())
        return [
            self._namespaces[ns_id]
            for ns_id in namespace_ids
            if ns_id in self._namespaces
        ]
    
    async def delete_namespace(
        self,
        namespace_id: str,
        force: bool = False,
    ) -> bool:
        """Delete a namespace.
        
        Args:
            namespace_id: Namespace ID
            force: Force deletion even if resources exist
            
        Returns:
            True if deleted
        """
        async with self._lock:
            namespace = self._namespaces.get(namespace_id)
            if not namespace:
                return False
            
            # Check for existing resources
            resources = [
                r for r in self._resources.values()
                if r.namespace_id == namespace_id
            ]
            
            if resources and not force:
                logger.warning(
                    "Cannot delete namespace with resources",
                    namespace_id=namespace_id,
                    resource_count=len(resources),
                )
                return False
            
            # Remove resources if forcing
            for resource in resources:
                del self._resources[resource.id]
                if resource.tenant_id in self._resource_index:
                    self._resource_index[resource.tenant_id].discard(resource.id)
            
            # Remove namespace
            del self._namespaces[namespace_id]
            if namespace.tenant_id in self._tenant_namespaces:
                self._tenant_namespaces[namespace.tenant_id].discard(namespace_id)
            
            logger.info(
                "Deleted namespace",
                namespace_id=namespace_id,
                resources_removed=len(resources),
            )
            
            return True
    
    async def add_policy(self, policy: IsolationPolicy) -> None:
        """Add an isolation policy.
        
        Args:
            policy: Policy to add
        """
        async with self._lock:
            self._policies[policy.id] = policy
            
            logger.info(
                "Added isolation policy",
                policy_id=policy.id,
                name=policy.name,
                tenant_id=policy.tenant_id,
            )
    
    async def get_effective_policies(
        self,
        tenant_id: str,
        resource_type: Optional[ResourceType] = None,
    ) -> List[IsolationPolicy]:
        """Get effective policies for a tenant and resource type.
        
        Policies are sorted by priority (highest first).
        
        Args:
            tenant_id: Tenant ID
            resource_type: Optional resource type filter
            
        Returns:
            List of applicable policies
        """
        policies = []
        
        for policy in self._policies.values():
            if not policy.enabled:
                continue
            
            # Check tenant scope
            if policy.tenant_id is not None and policy.tenant_id != tenant_id:
                continue
            
            # Check resource type scope
            if resource_type and policy.resource_types:
                if resource_type not in policy.resource_types:
                    continue
            
            policies.append(policy)
        
        # Sort by priority (descending)
        policies.sort(key=lambda p: p.priority, reverse=True)
        
        return policies
    
    async def register_resource(
        self,
        tenant_id: str,
        namespace_id: str,
        resource_type: ResourceType,
        resource_id: str,
        labels: Optional[Dict[str, str]] = None,
        created_by: Optional[str] = None,
    ) -> IsolatedResource:
        """Register a resource for isolation tracking.
        
        Args:
            tenant_id: Tenant ID
            namespace_id: Namespace ID
            resource_type: Type of resource
            resource_id: Resource identifier
            labels: Additional labels
            created_by: User who created the resource
            
        Returns:
            Registered resource
        """
        async with self._lock:
            resource = IsolatedResource(
                tenant_id=tenant_id,
                namespace_id=namespace_id,
                resource_type=resource_type,
                resource_id=resource_id,
                labels=labels or {},
                created_by=created_by,
            )
            
            self._resources[resource.id] = resource
            
            if tenant_id not in self._resource_index:
                self._resource_index[tenant_id] = set()
            self._resource_index[tenant_id].add(resource.id)
            
            return resource
    
    async def unregister_resource(self, resource_id: str) -> bool:
        """Unregister a resource.
        
        Args:
            resource_id: Resource registration ID
            
        Returns:
            True if unregistered
        """
        async with self._lock:
            resource = self._resources.get(resource_id)
            if not resource:
                return False
            
            del self._resources[resource_id]
            if resource.tenant_id in self._resource_index:
                self._resource_index[resource.tenant_id].discard(resource_id)
            
            return True
    
    async def get_resource(
        self,
        resource_id: str,
    ) -> Optional[IsolatedResource]:
        """Get a registered resource."""
        return self._resources.get(resource_id)
    
    async def find_resource(
        self,
        tenant_id: str,
        resource_type: ResourceType,
        original_resource_id: str,
    ) -> Optional[IsolatedResource]:
        """Find a resource by its original ID.
        
        Args:
            tenant_id: Tenant ID
            resource_type: Type of resource
            original_resource_id: Original resource ID
            
        Returns:
            Resource if found
        """
        resource_ids = self._resource_index.get(tenant_id, set())
        
        for rid in resource_ids:
            resource = self._resources.get(rid)
            if resource and resource.resource_type == resource_type and resource.resource_id == original_resource_id:
                return resource
        
        return None
    
    async def can_access_resource(
        self,
        context: IsolationContext,
        target_tenant_id: str,
        resource_id: str,
        access_type: str = "read",
    ) -> bool:
        """Check if context can access a resource.
        
        Args:
            context: Isolation context
            target_tenant_id: Target tenant ID
            resource_id: Resource ID
            access_type: Type of access (read/write)
            
        Returns:
            True if access is allowed
        """
        # Same tenant always allowed
        if context.tenant_id == target_tenant_id:
            return True
        
        # Cross-tenant access
        if access_type == "read" and context.can_read_cross_tenant:
            return True
        if access_type == "write" and context.can_write_cross_tenant:
            return True
        
        # Check policies
        policies = await self.get_effective_policies(context.tenant_id)
        
        for policy in policies:
            if access_type == "read" and policy.allow_cross_tenant_read:
                return True
            if access_type == "write" and policy.allow_cross_tenant_write:
                return True
        
        # Log violation
        await self._record_violation(
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            resource_type=ResourceType.ALERT,  # Would need to look up
            resource_id=resource_id,
            policy_id="default",
            violation_type=f"cross_tenant_{access_type}",
            details=f"Attempted {access_type} access to resource in tenant {target_tenant_id}",
            target_tenant_id=target_tenant_id,
        )
        
        return False
    
    async def enforce_isolation(
        self,
        context: IsolationContext,
        target_tenant_id: str,
        resource_type: ResourceType,
        resource_id: str,
        access_type: str = "read",
    ) -> None:
        """Enforce isolation policy.
        
        Raises IsolationViolationError if access is denied.
        
        Args:
            context: Isolation context
            target_tenant_id: Target tenant ID
            resource_type: Type of resource
            resource_id: Resource ID
            access_type: Type of access
        """
        can_access = await self.can_access_resource(
            context,
            target_tenant_id,
            resource_id,
            access_type,
        )
        
        if not can_access:
            raise IsolationViolationError(
                f"Access denied: {context.tenant_id} cannot {access_type} "
                f"{resource_type.value} in tenant {target_tenant_id}",
                tenant_id=context.tenant_id,
                resource_id=resource_id,
            )
    
    async def get_violations(
        self,
        tenant_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[IsolationViolation]:
        """Get recorded violations.
        
        Args:
            tenant_id: Filter by tenant
            since: Filter by time
            limit: Maximum results
            
        Returns:
            List of violations
        """
        violations = self._violations
        
        if tenant_id:
            violations = [v for v in violations if v.tenant_id == tenant_id]
        
        if since:
            violations = [v for v in violations if v.occurred_at >= since]
        
        # Sort by time descending
        violations.sort(key=lambda v: v.occurred_at, reverse=True)
        
        return violations[:limit]
    
    async def get_isolation_stats(
        self,
        tenant_id: str,
    ) -> Dict[str, Any]:
        """Get isolation statistics for a tenant.
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            Statistics dictionary
        """
        namespaces = await self.get_tenant_namespaces(tenant_id)
        resource_ids = self._resource_index.get(tenant_id, set())
        violations = await self.get_violations(tenant_id=tenant_id)
        
        # Count by resource type
        resource_counts: Dict[str, int] = {}
        for rid in resource_ids:
            resource = self._resources.get(rid)
            if resource:
                rt = resource.resource_type.value
                resource_counts[rt] = resource_counts.get(rt, 0) + 1
        
        return {
            "tenant_id": tenant_id,
            "namespace_count": len(namespaces),
            "resource_count": len(resource_ids),
            "resource_by_type": resource_counts,
            "violation_count": len(violations),
            "policies_applied": len(await self.get_effective_policies(tenant_id)),
        }
    
    async def _record_violation(
        self,
        tenant_id: str,
        user_id: Optional[str],
        resource_type: ResourceType,
        resource_id: str,
        policy_id: str,
        violation_type: str,
        details: str,
        target_tenant_id: Optional[str] = None,
        action_taken: str = "blocked",
    ) -> IsolationViolation:
        """Record an isolation violation."""
        violation = IsolationViolation(
            tenant_id=tenant_id,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            policy_id=policy_id,
            violation_type=violation_type,
            details=details,
            target_tenant_id=target_tenant_id,
            action_taken=action_taken,
        )
        
        self._violations.append(violation)
        
        logger.warning(
            "Isolation violation",
            tenant_id=tenant_id,
            violation_type=violation_type,
            resource_id=resource_id,
            action_taken=action_taken,
        )
        
        return violation


class IsolationViolationError(Exception):
    """Raised when an isolation policy is violated."""
    
    def __init__(
        self,
        message: str,
        tenant_id: str,
        resource_id: Optional[str] = None,
    ):
        super().__init__(message)
        self.tenant_id = tenant_id
        self.resource_id = resource_id


class IsolationFilterMixin(Generic[T]):
    """Mixin for repositories to add isolation filtering.
    
    Provides methods to automatically filter queries by tenant
    and enforce isolation policies.
    """
    
    def __init__(self, isolation: ResourceIsolation):
        self._isolation = isolation
    
    def get_tenant_filter(self, context: IsolationContext) -> Dict[str, Any]:
        """Get filter dict for tenant isolation.
        
        Args:
            context: Isolation context
            
        Returns:
            Filter dictionary
        """
        return {"tenant_id": context.tenant_id}
    
    async def apply_isolation(
        self,
        context: IsolationContext,
        items: List[T],
        tenant_id_getter: Any,
    ) -> List[T]:
        """Filter items based on isolation context.
        
        Args:
            context: Isolation context
            items: Items to filter
            tenant_id_getter: Function or attribute to get tenant_id
            
        Returns:
            Filtered items
        """
        filtered = []
        
        for item in items:
            if callable(tenant_id_getter):
                item_tenant_id = tenant_id_getter(item)
            else:
                item_tenant_id = getattr(item, tenant_id_getter)
            
            if item_tenant_id == context.tenant_id:
                filtered.append(item)
            elif context.can_read_cross_tenant:
                filtered.append(item)
        
        return filtered
