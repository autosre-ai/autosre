"""Cross-Tenant Policy for AutoSRE V2 Multi-Tenancy.

Provides cross-tenant access control and sharing policies:
- Resource sharing between tenants
- Cross-tenant access rules
- Federated tenant groups
- Sharing audit trails
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class AccessLevel(str, Enum):
    """Level of access granted in cross-tenant sharing."""
    
    NONE = "none"  # No access
    VIEW = "view"  # Read-only access
    COMMENT = "comment"  # View + add comments
    EDIT = "edit"  # View + edit
    ADMIN = "admin"  # Full access including deletion


class ShareableResourceType(str, Enum):
    """Types of resources that can be shared across tenants."""
    
    RUNBOOK = "runbook"
    DASHBOARD = "dashboard"
    ALERT_RULE = "alert_rule"
    NOTIFICATION_CHANNEL = "notification_channel"
    INTEGRATION_CONFIG = "integration_config"
    REPORT_TEMPLATE = "report_template"


class SharingScope(str, Enum):
    """Scope of sharing."""
    
    PRIVATE = "private"  # Only within tenant
    SPECIFIC = "specific"  # Shared with specific tenants
    GROUP = "group"  # Shared with tenant group
    PUBLIC = "public"  # Shared with all tenants


class CrossTenantRule(BaseModel):
    """A rule defining cross-tenant access permissions."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: Optional[str] = None
    
    # Source tenant(s)
    source_tenant_id: Optional[str] = None  # None = any tenant
    source_tenant_group: Optional[str] = None
    
    # Target tenant(s)
    target_tenant_id: Optional[str] = None  # None = any tenant
    target_tenant_group: Optional[str] = None
    
    # Resource scope
    resource_types: List[ShareableResourceType] = Field(default_factory=list)
    
    # Access configuration
    access_level: AccessLevel = AccessLevel.VIEW
    
    # Conditions
    require_approval: bool = False
    max_shares_per_resource: Optional[int] = None
    allowed_actions: List[str] = Field(default_factory=list)
    
    # Time constraints
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    
    # Status
    enabled: bool = True
    priority: int = 0
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None
    
    def is_valid(self) -> bool:
        """Check if rule is currently valid."""
        if not self.enabled:
            return False
        
        now = datetime.now(timezone.utc)
        
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        
        return True
    
    def matches_source(self, tenant_id: str, tenant_groups: List[str]) -> bool:
        """Check if source tenant matches this rule."""
        if self.source_tenant_id:
            return self.source_tenant_id == tenant_id
        if self.source_tenant_group:
            return self.source_tenant_group in tenant_groups
        return True  # No restriction
    
    def matches_target(self, tenant_id: str, tenant_groups: List[str]) -> bool:
        """Check if target tenant matches this rule."""
        if self.target_tenant_id:
            return self.target_tenant_id == tenant_id
        if self.target_tenant_group:
            return self.target_tenant_group in tenant_groups
        return True  # No restriction


class SharingPolicy(BaseModel):
    """Policy for sharing a specific resource."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    
    # Resource being shared
    resource_type: ShareableResourceType
    resource_id: str
    owner_tenant_id: str
    
    # Sharing configuration
    scope: SharingScope = SharingScope.PRIVATE
    
    # Specific sharing targets (for SPECIFIC scope)
    shared_with_tenants: List[str] = Field(default_factory=list)
    shared_with_groups: List[str] = Field(default_factory=list)
    
    # Access settings per target
    access_levels: Dict[str, AccessLevel] = Field(default_factory=dict)
    # key = tenant_id or "group:{group_name}", value = AccessLevel
    
    # Default access level for scope
    default_access_level: AccessLevel = AccessLevel.VIEW
    
    # Constraints
    allow_resharing: bool = False
    require_attribution: bool = True
    
    # Expiry
    expires_at: Optional[datetime] = None
    
    # Tracking
    share_count: int = 0
    last_accessed_at: Optional[datetime] = None
    last_accessed_by_tenant: Optional[str] = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None
    
    def is_shared_with(self, tenant_id: str, tenant_groups: List[str]) -> bool:
        """Check if resource is shared with a tenant."""
        if self.scope == SharingScope.PRIVATE:
            return tenant_id == self.owner_tenant_id
        
        if self.scope == SharingScope.PUBLIC:
            return True
        
        if self.scope == SharingScope.SPECIFIC:
            if tenant_id in self.shared_with_tenants:
                return True
            return any(g in self.shared_with_groups for g in tenant_groups)
        
        if self.scope == SharingScope.GROUP:
            return any(g in self.shared_with_groups for g in tenant_groups)
        
        return False
    
    def get_access_level(
        self,
        tenant_id: str,
        tenant_groups: List[str],
    ) -> AccessLevel:
        """Get access level for a tenant."""
        if tenant_id == self.owner_tenant_id:
            return AccessLevel.ADMIN
        
        # Check specific tenant access
        if tenant_id in self.access_levels:
            return self.access_levels[tenant_id]
        
        # Check group access
        for group in tenant_groups:
            group_key = f"group:{group}"
            if group_key in self.access_levels:
                return self.access_levels[group_key]
        
        # Return default
        return self.default_access_level


class TenantGroup(BaseModel):
    """A group of tenants for federated access."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    
    # Members
    member_tenant_ids: Set[str] = Field(default_factory=set)
    
    # Group settings
    allow_member_sharing: bool = True  # Members can share with each other
    default_access_level: AccessLevel = AccessLevel.VIEW
    
    # Admin tenant (manages the group)
    admin_tenant_id: Optional[str] = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def add_member(self, tenant_id: str) -> None:
        """Add a tenant to the group."""
        self.member_tenant_ids.add(tenant_id)
        self.updated_at = datetime.now(timezone.utc)
    
    def remove_member(self, tenant_id: str) -> None:
        """Remove a tenant from the group."""
        self.member_tenant_ids.discard(tenant_id)
        self.updated_at = datetime.now(timezone.utc)
    
    def is_member(self, tenant_id: str) -> bool:
        """Check if tenant is a member."""
        return tenant_id in self.member_tenant_ids


class ShareRequest(BaseModel):
    """Request to share a resource with another tenant."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    
    # Resource
    resource_type: ShareableResourceType
    resource_id: str
    owner_tenant_id: str
    
    # Target
    target_tenant_id: str
    requested_access_level: AccessLevel = AccessLevel.VIEW
    
    # Request details
    message: Optional[str] = None
    
    # Status
    status: str = "pending"  # pending, approved, rejected, expired
    
    # Review
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    
    # Timing
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None


class ShareAuditEntry(BaseModel):
    """Audit log entry for sharing actions."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    
    # Action
    action: str  # shared, unshared, access_changed, accessed
    
    # Resource
    resource_type: ShareableResourceType
    resource_id: str
    
    # Parties
    owner_tenant_id: str
    target_tenant_id: str
    
    # Actor
    actor_tenant_id: str
    actor_user_id: Optional[str] = None
    
    # Details
    old_access_level: Optional[AccessLevel] = None
    new_access_level: Optional[AccessLevel] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    
    # Metadata
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ip_address: Optional[str] = None


class CrossTenantPolicy:
    """
    Manages cross-tenant access and sharing policies.
    
    Provides:
    - Cross-tenant access rules
    - Resource sharing management
    - Tenant groups/federation
    - Share request workflow
    - Audit logging
    
    Example:
        policy = CrossTenantPolicy()
        
        # Create a tenant group
        group = await policy.create_group(
            name="enterprise-customers",
            admin_tenant_id="tenant-1",
        )
        await policy.add_to_group(group.id, "tenant-2")
        await policy.add_to_group(group.id, "tenant-3")
        
        # Share a runbook with the group
        sharing = await policy.share_resource(
            resource_type=ShareableResourceType.RUNBOOK,
            resource_id="runbook-123",
            owner_tenant_id="tenant-1",
            scope=SharingScope.GROUP,
            groups=["enterprise-customers"],
        )
        
        # Check access
        can_view = await policy.can_access(
            tenant_id="tenant-2",
            resource_type=ShareableResourceType.RUNBOOK,
            resource_id="runbook-123",
            access_level=AccessLevel.VIEW,
        )
    """
    
    def __init__(self):
        """Initialize CrossTenantPolicy."""
        self._rules: Dict[str, CrossTenantRule] = {}
        self._sharing_policies: Dict[str, SharingPolicy] = {}
        self._groups: Dict[str, TenantGroup] = {}
        self._share_requests: Dict[str, ShareRequest] = {}
        self._audit_log: List[ShareAuditEntry] = []
        self._tenant_groups: Dict[str, Set[str]] = {}  # tenant_id -> group_ids
        self._lock = asyncio.Lock()
    
    # Rule Management
    
    async def add_rule(self, rule: CrossTenantRule) -> CrossTenantRule:
        """Add a cross-tenant access rule.
        
        Args:
            rule: Rule to add
            
        Returns:
            Added rule
        """
        async with self._lock:
            self._rules[rule.id] = rule
            
            logger.info(
                "Added cross-tenant rule",
                rule_id=rule.id,
                name=rule.name,
            )
            
            return rule
    
    async def get_rule(self, rule_id: str) -> Optional[CrossTenantRule]:
        """Get a rule by ID."""
        return self._rules.get(rule_id)
    
    async def list_rules(
        self,
        source_tenant_id: Optional[str] = None,
        target_tenant_id: Optional[str] = None,
        enabled_only: bool = True,
    ) -> List[CrossTenantRule]:
        """List cross-tenant rules.
        
        Args:
            source_tenant_id: Filter by source tenant
            target_tenant_id: Filter by target tenant
            enabled_only: Only return enabled rules
            
        Returns:
            List of matching rules
        """
        rules = list(self._rules.values())
        
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        
        if source_tenant_id:
            source_groups = list(self._tenant_groups.get(source_tenant_id, set()))
            rules = [r for r in rules if r.matches_source(source_tenant_id, source_groups)]
        
        if target_tenant_id:
            target_groups = list(self._tenant_groups.get(target_tenant_id, set()))
            rules = [r for r in rules if r.matches_target(target_tenant_id, target_groups)]
        
        # Sort by priority
        rules.sort(key=lambda r: r.priority, reverse=True)
        
        return rules
    
    async def delete_rule(self, rule_id: str) -> bool:
        """Delete a rule."""
        async with self._lock:
            if rule_id in self._rules:
                del self._rules[rule_id]
                return True
            return False
    
    # Group Management
    
    async def create_group(
        self,
        name: str,
        admin_tenant_id: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> TenantGroup:
        """Create a tenant group.
        
        Args:
            name: Unique group name
            admin_tenant_id: Tenant that administers the group
            display_name: Human-readable name
            description: Group description
            
        Returns:
            Created group
        """
        async with self._lock:
            group = TenantGroup(
                name=name,
                display_name=display_name or name,
                description=description,
                admin_tenant_id=admin_tenant_id,
                member_tenant_ids={admin_tenant_id},
            )
            
            self._groups[group.id] = group
            
            # Update tenant's group membership
            if admin_tenant_id not in self._tenant_groups:
                self._tenant_groups[admin_tenant_id] = set()
            self._tenant_groups[admin_tenant_id].add(group.id)
            
            logger.info(
                "Created tenant group",
                group_id=group.id,
                name=name,
                admin_tenant_id=admin_tenant_id,
            )
            
            return group
    
    async def get_group(self, group_id: str) -> Optional[TenantGroup]:
        """Get a group by ID."""
        return self._groups.get(group_id)
    
    async def get_group_by_name(self, name: str) -> Optional[TenantGroup]:
        """Get a group by name."""
        for group in self._groups.values():
            if group.name == name:
                return group
        return None
    
    async def add_to_group(
        self,
        group_id: str,
        tenant_id: str,
    ) -> TenantGroup:
        """Add a tenant to a group.
        
        Args:
            group_id: Group ID
            tenant_id: Tenant ID to add
            
        Returns:
            Updated group
        """
        async with self._lock:
            group = self._groups.get(group_id)
            if not group:
                raise ValueError(f"Group {group_id} not found")
            
            group.add_member(tenant_id)
            
            # Update tenant's group membership
            if tenant_id not in self._tenant_groups:
                self._tenant_groups[tenant_id] = set()
            self._tenant_groups[tenant_id].add(group_id)
            
            logger.info(
                "Added tenant to group",
                group_id=group_id,
                tenant_id=tenant_id,
            )
            
            return group
    
    async def remove_from_group(
        self,
        group_id: str,
        tenant_id: str,
    ) -> TenantGroup:
        """Remove a tenant from a group.
        
        Args:
            group_id: Group ID
            tenant_id: Tenant ID to remove
            
        Returns:
            Updated group
        """
        async with self._lock:
            group = self._groups.get(group_id)
            if not group:
                raise ValueError(f"Group {group_id} not found")
            
            group.remove_member(tenant_id)
            
            # Update tenant's group membership
            if tenant_id in self._tenant_groups:
                self._tenant_groups[tenant_id].discard(group_id)
            
            logger.info(
                "Removed tenant from group",
                group_id=group_id,
                tenant_id=tenant_id,
            )
            
            return group
    
    async def get_tenant_groups(self, tenant_id: str) -> List[TenantGroup]:
        """Get all groups a tenant belongs to."""
        group_ids = self._tenant_groups.get(tenant_id, set())
        return [
            self._groups[gid]
            for gid in group_ids
            if gid in self._groups
        ]
    
    # Sharing Management
    
    async def share_resource(
        self,
        resource_type: ShareableResourceType,
        resource_id: str,
        owner_tenant_id: str,
        scope: SharingScope = SharingScope.SPECIFIC,
        tenants: Optional[List[str]] = None,
        groups: Optional[List[str]] = None,
        access_level: AccessLevel = AccessLevel.VIEW,
        allow_resharing: bool = False,
        expires_at: Optional[datetime] = None,
        created_by: Optional[str] = None,
    ) -> SharingPolicy:
        """Share a resource with other tenants.
        
        Args:
            resource_type: Type of resource
            resource_id: Resource identifier
            owner_tenant_id: Tenant that owns the resource
            scope: Sharing scope
            tenants: Specific tenant IDs to share with
            groups: Group names to share with
            access_level: Default access level
            allow_resharing: Whether recipients can reshare
            expires_at: When sharing expires
            created_by: User who created the share
            
        Returns:
            Created sharing policy
        """
        async with self._lock:
            # Check for existing policy
            policy_key = f"{resource_type.value}:{resource_id}"
            existing = self._sharing_policies.get(policy_key)
            
            if existing:
                # Update existing policy
                existing.scope = scope
                existing.shared_with_tenants = tenants or []
                existing.shared_with_groups = groups or []
                existing.default_access_level = access_level
                existing.allow_resharing = allow_resharing
                existing.expires_at = expires_at
                existing.updated_at = datetime.now(timezone.utc)
                
                policy = existing
            else:
                # Create new policy
                policy = SharingPolicy(
                    resource_type=resource_type,
                    resource_id=resource_id,
                    owner_tenant_id=owner_tenant_id,
                    scope=scope,
                    shared_with_tenants=tenants or [],
                    shared_with_groups=groups or [],
                    default_access_level=access_level,
                    allow_resharing=allow_resharing,
                    expires_at=expires_at,
                    created_by=created_by,
                )
                
                self._sharing_policies[policy_key] = policy
            
            # Audit log
            for tenant_id in (tenants or []):
                await self._audit(
                    action="shared",
                    resource_type=resource_type,
                    resource_id=resource_id,
                    owner_tenant_id=owner_tenant_id,
                    target_tenant_id=tenant_id,
                    actor_tenant_id=owner_tenant_id,
                    actor_user_id=created_by,
                    new_access_level=access_level,
                )
            
            logger.info(
                "Shared resource",
                resource_type=resource_type.value,
                resource_id=resource_id,
                owner_tenant_id=owner_tenant_id,
                scope=scope.value,
                tenant_count=len(tenants or []),
                group_count=len(groups or []),
            )
            
            return policy
    
    async def unshare_resource(
        self,
        resource_type: ShareableResourceType,
        resource_id: str,
        owner_tenant_id: str,
        target_tenant_id: Optional[str] = None,
    ) -> bool:
        """Unshare a resource.
        
        Args:
            resource_type: Type of resource
            resource_id: Resource identifier
            owner_tenant_id: Tenant that owns the resource
            target_tenant_id: Specific tenant to unshare with (None = all)
            
        Returns:
            True if unshared
        """
        async with self._lock:
            policy_key = f"{resource_type.value}:{resource_id}"
            policy = self._sharing_policies.get(policy_key)
            
            if not policy:
                return False
            
            if policy.owner_tenant_id != owner_tenant_id:
                raise ValueError("Only owner can unshare resource")
            
            if target_tenant_id:
                # Remove specific tenant
                if target_tenant_id in policy.shared_with_tenants:
                    policy.shared_with_tenants.remove(target_tenant_id)
                    
                    await self._audit(
                        action="unshared",
                        resource_type=resource_type,
                        resource_id=resource_id,
                        owner_tenant_id=owner_tenant_id,
                        target_tenant_id=target_tenant_id,
                        actor_tenant_id=owner_tenant_id,
                    )
            else:
                # Remove all sharing
                del self._sharing_policies[policy_key]
                
                for tenant_id in policy.shared_with_tenants:
                    await self._audit(
                        action="unshared",
                        resource_type=resource_type,
                        resource_id=resource_id,
                        owner_tenant_id=owner_tenant_id,
                        target_tenant_id=tenant_id,
                        actor_tenant_id=owner_tenant_id,
                    )
            
            return True
    
    async def get_sharing_policy(
        self,
        resource_type: ShareableResourceType,
        resource_id: str,
    ) -> Optional[SharingPolicy]:
        """Get sharing policy for a resource."""
        policy_key = f"{resource_type.value}:{resource_id}"
        return self._sharing_policies.get(policy_key)
    
    async def can_access(
        self,
        tenant_id: str,
        resource_type: ShareableResourceType,
        resource_id: str,
        required_level: AccessLevel = AccessLevel.VIEW,
    ) -> bool:
        """Check if a tenant can access a shared resource.
        
        Args:
            tenant_id: Tenant requesting access
            resource_type: Type of resource
            resource_id: Resource identifier
            required_level: Required access level
            
        Returns:
            True if access is allowed
        """
        policy = await self.get_sharing_policy(resource_type, resource_id)
        
        if not policy:
            return False
        
        # Owner always has access
        if policy.owner_tenant_id == tenant_id:
            return True
        
        # Check expiry
        if policy.expires_at and datetime.now(timezone.utc) > policy.expires_at:
            return False
        
        # Get tenant's groups
        tenant_groups = [
            g.name for g in await self.get_tenant_groups(tenant_id)
        ]
        
        # Check if shared with tenant
        if not policy.is_shared_with(tenant_id, tenant_groups):
            return False
        
        # Check access level
        granted_level = policy.get_access_level(tenant_id, tenant_groups)
        
        # Compare access levels
        level_hierarchy = [
            AccessLevel.NONE,
            AccessLevel.VIEW,
            AccessLevel.COMMENT,
            AccessLevel.EDIT,
            AccessLevel.ADMIN,
        ]
        
        granted_index = level_hierarchy.index(granted_level)
        required_index = level_hierarchy.index(required_level)
        
        return granted_index >= required_index
    
    async def record_access(
        self,
        tenant_id: str,
        resource_type: ShareableResourceType,
        resource_id: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Record access to a shared resource.
        
        Args:
            tenant_id: Tenant accessing the resource
            resource_type: Type of resource
            resource_id: Resource identifier
            user_id: User accessing
            ip_address: IP address
        """
        policy = await self.get_sharing_policy(resource_type, resource_id)
        
        if policy:
            policy.share_count += 1
            policy.last_accessed_at = datetime.now(timezone.utc)
            policy.last_accessed_by_tenant = tenant_id
            
            await self._audit(
                action="accessed",
                resource_type=resource_type,
                resource_id=resource_id,
                owner_tenant_id=policy.owner_tenant_id,
                target_tenant_id=tenant_id,
                actor_tenant_id=tenant_id,
                actor_user_id=user_id,
                ip_address=ip_address,
            )
    
    # Share Requests
    
    async def request_share(
        self,
        resource_type: ShareableResourceType,
        resource_id: str,
        owner_tenant_id: str,
        requester_tenant_id: str,
        access_level: AccessLevel = AccessLevel.VIEW,
        message: Optional[str] = None,
        expires_in_days: int = 7,
    ) -> ShareRequest:
        """Request access to a resource.
        
        Args:
            resource_type: Type of resource
            resource_id: Resource identifier
            owner_tenant_id: Tenant that owns the resource
            requester_tenant_id: Tenant requesting access
            access_level: Requested access level
            message: Optional message to owner
            expires_in_days: Days until request expires
            
        Returns:
            Created share request
        """
        async with self._lock:
            request = ShareRequest(
                resource_type=resource_type,
                resource_id=resource_id,
                owner_tenant_id=owner_tenant_id,
                target_tenant_id=requester_tenant_id,
                requested_access_level=access_level,
                message=message,
                expires_at=datetime.now(timezone.utc) + timedelta(days=expires_in_days),
            )
            
            self._share_requests[request.id] = request
            
            logger.info(
                "Share request created",
                request_id=request.id,
                resource_type=resource_type.value,
                resource_id=resource_id,
                requester_tenant_id=requester_tenant_id,
            )
            
            return request
    
    async def approve_share_request(
        self,
        request_id: str,
        reviewer_user_id: str,
        notes: Optional[str] = None,
    ) -> ShareRequest:
        """Approve a share request.
        
        Args:
            request_id: Request ID
            reviewer_user_id: User approving
            notes: Optional notes
            
        Returns:
            Updated request
        """
        async with self._lock:
            request = self._share_requests.get(request_id)
            if not request:
                raise ValueError(f"Request {request_id} not found")
            
            if request.status != "pending":
                raise ValueError(f"Request is already {request.status}")
            
            request.status = "approved"
            request.reviewed_by = reviewer_user_id
            request.reviewed_at = datetime.now(timezone.utc)
            request.review_notes = notes
            
            # Create the sharing policy
            await self.share_resource(
                resource_type=request.resource_type,
                resource_id=request.resource_id,
                owner_tenant_id=request.owner_tenant_id,
                scope=SharingScope.SPECIFIC,
                tenants=[request.target_tenant_id],
                access_level=request.requested_access_level,
            )
            
            logger.info(
                "Share request approved",
                request_id=request_id,
                reviewer_user_id=reviewer_user_id,
            )
            
            return request
    
    async def reject_share_request(
        self,
        request_id: str,
        reviewer_user_id: str,
        notes: Optional[str] = None,
    ) -> ShareRequest:
        """Reject a share request.
        
        Args:
            request_id: Request ID
            reviewer_user_id: User rejecting
            notes: Rejection reason
            
        Returns:
            Updated request
        """
        async with self._lock:
            request = self._share_requests.get(request_id)
            if not request:
                raise ValueError(f"Request {request_id} not found")
            
            if request.status != "pending":
                raise ValueError(f"Request is already {request.status}")
            
            request.status = "rejected"
            request.reviewed_by = reviewer_user_id
            request.reviewed_at = datetime.now(timezone.utc)
            request.review_notes = notes
            
            logger.info(
                "Share request rejected",
                request_id=request_id,
                reviewer_user_id=reviewer_user_id,
            )
            
            return request
    
    async def list_share_requests(
        self,
        tenant_id: str,
        as_owner: bool = True,
        status: Optional[str] = None,
    ) -> List[ShareRequest]:
        """List share requests for a tenant.
        
        Args:
            tenant_id: Tenant ID
            as_owner: If True, show requests TO this tenant. If False, FROM.
            status: Filter by status
            
        Returns:
            List of requests
        """
        requests = list(self._share_requests.values())
        
        if as_owner:
            requests = [r for r in requests if r.owner_tenant_id == tenant_id]
        else:
            requests = [r for r in requests if r.target_tenant_id == tenant_id]
        
        if status:
            requests = [r for r in requests if r.status == status]
        
        return requests
    
    # Audit
    
    async def _audit(
        self,
        action: str,
        resource_type: ShareableResourceType,
        resource_id: str,
        owner_tenant_id: str,
        target_tenant_id: str,
        actor_tenant_id: str,
        actor_user_id: Optional[str] = None,
        old_access_level: Optional[AccessLevel] = None,
        new_access_level: Optional[AccessLevel] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> ShareAuditEntry:
        """Create an audit log entry."""
        entry = ShareAuditEntry(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            owner_tenant_id=owner_tenant_id,
            target_tenant_id=target_tenant_id,
            actor_tenant_id=actor_tenant_id,
            actor_user_id=actor_user_id,
            old_access_level=old_access_level,
            new_access_level=new_access_level,
            details=details or {},
            ip_address=ip_address,
        )
        
        self._audit_log.append(entry)
        
        # Keep audit log manageable
        if len(self._audit_log) > 100000:
            self._audit_log = self._audit_log[-50000:]
        
        return entry
    
    async def get_audit_log(
        self,
        tenant_id: Optional[str] = None,
        resource_type: Optional[ShareableResourceType] = None,
        resource_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[ShareAuditEntry]:
        """Get audit log entries.
        
        Args:
            tenant_id: Filter by tenant (owner or target)
            resource_type: Filter by resource type
            resource_id: Filter by resource ID
            since: Filter by time
            limit: Maximum entries
            
        Returns:
            List of audit entries
        """
        entries = self._audit_log
        
        if tenant_id:
            entries = [
                e for e in entries
                if e.owner_tenant_id == tenant_id or e.target_tenant_id == tenant_id
            ]
        
        if resource_type:
            entries = [e for e in entries if e.resource_type == resource_type]
        
        if resource_id:
            entries = [e for e in entries if e.resource_id == resource_id]
        
        if since:
            entries = [e for e in entries if e.timestamp >= since]
        
        # Sort by timestamp descending
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        
        return entries[:limit]


# Import timedelta at module level for ShareRequest
from datetime import timedelta
