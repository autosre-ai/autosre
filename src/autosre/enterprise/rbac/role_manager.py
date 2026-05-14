"""Role Manager for AutoSRE V2 RBAC.

Provides granular role and permission management:
- Hierarchical roles with inheritance
- Fine-grained permissions
- Scope-based access control
- Role assignment and management
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


class RoleType(str, Enum):
    """Types of roles in the system."""
    
    SYSTEM = "system"  # Built-in system roles
    TENANT = "tenant"  # Tenant-specific roles
    CUSTOM = "custom"  # User-defined roles


class PermissionScope(str, Enum):
    """Scope of a permission."""
    
    GLOBAL = "global"  # Applies to all resources
    TENANT = "tenant"  # Applies within a tenant
    NAMESPACE = "namespace"  # Applies within a namespace
    RESOURCE = "resource"  # Applies to specific resources


class ResourceAction(str, Enum):
    """Actions that can be performed on resources."""
    
    # CRUD
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LIST = "list"
    
    # Investigation actions
    INVESTIGATE = "investigate"
    REMEDIATE = "remediate"
    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"
    
    # Administrative actions
    MANAGE = "manage"
    CONFIGURE = "configure"
    ASSIGN = "assign"
    REVOKE = "revoke"
    
    # System actions
    EXECUTE = "execute"
    AUDIT = "audit"
    EXPORT = "export"
    IMPORT = "import"


class ResourceType(str, Enum):
    """Types of resources for permission checks."""
    
    # Core resources
    ALERT = "alert"
    INVESTIGATION = "investigation"
    RUNBOOK = "runbook"
    ACTION = "action"
    OBSERVATION = "observation"
    
    # Configuration
    INTEGRATION = "integration"
    NOTIFICATION = "notification"
    ESCALATION = "escalation"
    
    # User management
    USER = "user"
    ROLE = "role"
    PERMISSION = "permission"
    
    # Tenant management
    TENANT = "tenant"
    NAMESPACE = "namespace"
    QUOTA = "quota"
    
    # System
    SYSTEM = "system"
    AUDIT = "audit"
    SETTINGS = "settings"


class Permission(BaseModel):
    """A permission granting access to perform an action on a resource."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: Optional[str] = None
    
    # Permission definition
    resource_type: ResourceType
    action: ResourceAction
    scope: PermissionScope = PermissionScope.TENANT
    
    # Conditions (for fine-grained control)
    conditions: Dict[str, Any] = Field(default_factory=dict)
    # e.g., {"severity": ["critical", "high"]} - only for critical/high alerts
    
    # Metadata
    is_system: bool = False  # System permissions cannot be deleted
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    @classmethod
    def create(
        cls,
        resource_type: ResourceType,
        action: ResourceAction,
        scope: PermissionScope = PermissionScope.TENANT,
        conditions: Optional[Dict[str, Any]] = None,
    ) -> "Permission":
        """Create a permission with auto-generated name."""
        name = f"{resource_type.value}:{action.value}"
        if conditions:
            name += f":{hash(frozenset(conditions.items())) % 10000}"
        
        return cls(
            name=name,
            resource_type=resource_type,
            action=action,
            scope=scope,
            conditions=conditions or {},
        )
    
    def matches(
        self,
        resource_type: ResourceType,
        action: ResourceAction,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Check if this permission matches the requested access."""
        if self.resource_type != resource_type:
            return False
        if self.action != action:
            return False
        
        # Check conditions
        if self.conditions and context:
            for key, allowed_values in self.conditions.items():
                actual_value = context.get(key)
                if isinstance(allowed_values, list):
                    if actual_value not in allowed_values:
                        return False
                elif actual_value != allowed_values:
                    return False
        
        return True


class Role(BaseModel):
    """A role that groups permissions."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    
    # Role configuration
    role_type: RoleType = RoleType.CUSTOM
    tenant_id: Optional[str] = None  # None for system roles
    
    # Permissions
    permission_ids: Set[str] = Field(default_factory=set)
    
    # Inheritance
    parent_role_ids: Set[str] = Field(default_factory=set)
    
    # Status
    is_active: bool = True
    is_default: bool = False  # Automatically assigned to new users
    
    # Metadata
    max_users: Optional[int] = None  # Limit users with this role
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None
    
    def add_permission(self, permission_id: str) -> None:
        """Add a permission to this role."""
        self.permission_ids.add(permission_id)
        self.updated_at = datetime.now(timezone.utc)
    
    def remove_permission(self, permission_id: str) -> None:
        """Remove a permission from this role."""
        self.permission_ids.discard(permission_id)
        self.updated_at = datetime.now(timezone.utc)
    
    def add_parent(self, parent_role_id: str) -> None:
        """Add a parent role for inheritance."""
        self.parent_role_ids.add(parent_role_id)
        self.updated_at = datetime.now(timezone.utc)
    
    def remove_parent(self, parent_role_id: str) -> None:
        """Remove a parent role."""
        self.parent_role_ids.discard(parent_role_id)
        self.updated_at = datetime.now(timezone.utc)


class UserRole(BaseModel):
    """Assignment of a role to a user."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    role_id: str
    tenant_id: str
    
    # Scope limitation (optional)
    namespace_id: Optional[str] = None  # Limit to specific namespace
    resource_ids: Set[str] = Field(default_factory=set)  # Limit to specific resources
    
    # Time bounds
    valid_from: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    valid_until: Optional[datetime] = None
    
    # Metadata
    assigned_by: Optional[str] = None
    assignment_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def is_valid(self) -> bool:
        """Check if assignment is currently valid."""
        now = datetime.now(timezone.utc)
        
        if now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        
        return True


# Pre-defined system permissions
SYSTEM_PERMISSIONS: List[Permission] = [
    # Alert permissions
    Permission(name="alert:read", resource_type=ResourceType.ALERT, action=ResourceAction.READ, is_system=True),
    Permission(name="alert:list", resource_type=ResourceType.ALERT, action=ResourceAction.LIST, is_system=True),
    Permission(name="alert:create", resource_type=ResourceType.ALERT, action=ResourceAction.CREATE, is_system=True),
    Permission(name="alert:update", resource_type=ResourceType.ALERT, action=ResourceAction.UPDATE, is_system=True),
    Permission(name="alert:delete", resource_type=ResourceType.ALERT, action=ResourceAction.DELETE, is_system=True),
    
    # Investigation permissions
    Permission(name="investigation:read", resource_type=ResourceType.INVESTIGATION, action=ResourceAction.READ, is_system=True),
    Permission(name="investigation:list", resource_type=ResourceType.INVESTIGATION, action=ResourceAction.LIST, is_system=True),
    Permission(name="investigation:create", resource_type=ResourceType.INVESTIGATION, action=ResourceAction.CREATE, is_system=True),
    Permission(name="investigation:investigate", resource_type=ResourceType.INVESTIGATION, action=ResourceAction.INVESTIGATE, is_system=True),
    Permission(name="investigation:approve", resource_type=ResourceType.INVESTIGATION, action=ResourceAction.APPROVE, is_system=True),
    Permission(name="investigation:reject", resource_type=ResourceType.INVESTIGATION, action=ResourceAction.REJECT, is_system=True),
    
    # Runbook permissions
    Permission(name="runbook:read", resource_type=ResourceType.RUNBOOK, action=ResourceAction.READ, is_system=True),
    Permission(name="runbook:list", resource_type=ResourceType.RUNBOOK, action=ResourceAction.LIST, is_system=True),
    Permission(name="runbook:create", resource_type=ResourceType.RUNBOOK, action=ResourceAction.CREATE, is_system=True),
    Permission(name="runbook:update", resource_type=ResourceType.RUNBOOK, action=ResourceAction.UPDATE, is_system=True),
    Permission(name="runbook:delete", resource_type=ResourceType.RUNBOOK, action=ResourceAction.DELETE, is_system=True),
    Permission(name="runbook:execute", resource_type=ResourceType.RUNBOOK, action=ResourceAction.EXECUTE, is_system=True),
    
    # Action permissions
    Permission(name="action:read", resource_type=ResourceType.ACTION, action=ResourceAction.READ, is_system=True),
    Permission(name="action:approve", resource_type=ResourceType.ACTION, action=ResourceAction.APPROVE, is_system=True),
    Permission(name="action:reject", resource_type=ResourceType.ACTION, action=ResourceAction.REJECT, is_system=True),
    Permission(name="action:execute", resource_type=ResourceType.ACTION, action=ResourceAction.EXECUTE, is_system=True),
    
    # User management
    Permission(name="user:read", resource_type=ResourceType.USER, action=ResourceAction.READ, is_system=True),
    Permission(name="user:list", resource_type=ResourceType.USER, action=ResourceAction.LIST, is_system=True),
    Permission(name="user:create", resource_type=ResourceType.USER, action=ResourceAction.CREATE, is_system=True),
    Permission(name="user:update", resource_type=ResourceType.USER, action=ResourceAction.UPDATE, is_system=True),
    Permission(name="user:delete", resource_type=ResourceType.USER, action=ResourceAction.DELETE, is_system=True),
    
    # Role management
    Permission(name="role:read", resource_type=ResourceType.ROLE, action=ResourceAction.READ, is_system=True),
    Permission(name="role:list", resource_type=ResourceType.ROLE, action=ResourceAction.LIST, is_system=True),
    Permission(name="role:create", resource_type=ResourceType.ROLE, action=ResourceAction.CREATE, is_system=True),
    Permission(name="role:update", resource_type=ResourceType.ROLE, action=ResourceAction.UPDATE, is_system=True),
    Permission(name="role:delete", resource_type=ResourceType.ROLE, action=ResourceAction.DELETE, is_system=True),
    Permission(name="role:assign", resource_type=ResourceType.ROLE, action=ResourceAction.ASSIGN, is_system=True),
    Permission(name="role:revoke", resource_type=ResourceType.ROLE, action=ResourceAction.REVOKE, is_system=True),
    
    # Integration management
    Permission(name="integration:read", resource_type=ResourceType.INTEGRATION, action=ResourceAction.READ, is_system=True),
    Permission(name="integration:list", resource_type=ResourceType.INTEGRATION, action=ResourceAction.LIST, is_system=True),
    Permission(name="integration:create", resource_type=ResourceType.INTEGRATION, action=ResourceAction.CREATE, is_system=True),
    Permission(name="integration:update", resource_type=ResourceType.INTEGRATION, action=ResourceAction.UPDATE, is_system=True),
    Permission(name="integration:delete", resource_type=ResourceType.INTEGRATION, action=ResourceAction.DELETE, is_system=True),
    Permission(name="integration:configure", resource_type=ResourceType.INTEGRATION, action=ResourceAction.CONFIGURE, is_system=True),
    
    # Tenant management
    Permission(name="tenant:read", resource_type=ResourceType.TENANT, action=ResourceAction.READ, is_system=True),
    Permission(name="tenant:manage", resource_type=ResourceType.TENANT, action=ResourceAction.MANAGE, is_system=True, scope=PermissionScope.GLOBAL),
    
    # System administration
    Permission(name="system:audit", resource_type=ResourceType.SYSTEM, action=ResourceAction.AUDIT, is_system=True, scope=PermissionScope.GLOBAL),
    Permission(name="system:configure", resource_type=ResourceType.SYSTEM, action=ResourceAction.CONFIGURE, is_system=True, scope=PermissionScope.GLOBAL),
]

# Create permission name to ID mapping
SYSTEM_PERMISSION_MAP: Dict[str, Permission] = {p.name: p for p in SYSTEM_PERMISSIONS}


# Pre-defined system roles
def create_system_roles() -> List[Role]:
    """Create pre-defined system roles."""
    return [
        Role(
            name="viewer",
            display_name="Viewer",
            description="Read-only access to alerts, investigations, and runbooks",
            role_type=RoleType.SYSTEM,
            permission_ids={
                SYSTEM_PERMISSION_MAP["alert:read"].id,
                SYSTEM_PERMISSION_MAP["alert:list"].id,
                SYSTEM_PERMISSION_MAP["investigation:read"].id,
                SYSTEM_PERMISSION_MAP["investigation:list"].id,
                SYSTEM_PERMISSION_MAP["runbook:read"].id,
                SYSTEM_PERMISSION_MAP["runbook:list"].id,
            },
        ),
        Role(
            name="responder",
            display_name="Incident Responder",
            description="Can investigate and respond to incidents",
            role_type=RoleType.SYSTEM,
            permission_ids={
                SYSTEM_PERMISSION_MAP["alert:read"].id,
                SYSTEM_PERMISSION_MAP["alert:list"].id,
                SYSTEM_PERMISSION_MAP["alert:update"].id,
                SYSTEM_PERMISSION_MAP["investigation:read"].id,
                SYSTEM_PERMISSION_MAP["investigation:list"].id,
                SYSTEM_PERMISSION_MAP["investigation:create"].id,
                SYSTEM_PERMISSION_MAP["investigation:investigate"].id,
                SYSTEM_PERMISSION_MAP["runbook:read"].id,
                SYSTEM_PERMISSION_MAP["runbook:list"].id,
                SYSTEM_PERMISSION_MAP["runbook:execute"].id,
                SYSTEM_PERMISSION_MAP["action:read"].id,
                SYSTEM_PERMISSION_MAP["action:execute"].id,
            },
        ),
        Role(
            name="approver",
            display_name="Action Approver",
            description="Can approve remediation actions",
            role_type=RoleType.SYSTEM,
            permission_ids={
                SYSTEM_PERMISSION_MAP["alert:read"].id,
                SYSTEM_PERMISSION_MAP["alert:list"].id,
                SYSTEM_PERMISSION_MAP["investigation:read"].id,
                SYSTEM_PERMISSION_MAP["investigation:list"].id,
                SYSTEM_PERMISSION_MAP["investigation:approve"].id,
                SYSTEM_PERMISSION_MAP["investigation:reject"].id,
                SYSTEM_PERMISSION_MAP["action:read"].id,
                SYSTEM_PERMISSION_MAP["action:approve"].id,
                SYSTEM_PERMISSION_MAP["action:reject"].id,
            },
        ),
        Role(
            name="engineer",
            display_name="SRE Engineer",
            description="Full access to investigations, runbooks, and configurations",
            role_type=RoleType.SYSTEM,
            permission_ids={
                SYSTEM_PERMISSION_MAP["alert:read"].id,
                SYSTEM_PERMISSION_MAP["alert:list"].id,
                SYSTEM_PERMISSION_MAP["alert:update"].id,
                SYSTEM_PERMISSION_MAP["investigation:read"].id,
                SYSTEM_PERMISSION_MAP["investigation:list"].id,
                SYSTEM_PERMISSION_MAP["investigation:create"].id,
                SYSTEM_PERMISSION_MAP["investigation:investigate"].id,
                SYSTEM_PERMISSION_MAP["investigation:approve"].id,
                SYSTEM_PERMISSION_MAP["investigation:reject"].id,
                SYSTEM_PERMISSION_MAP["runbook:read"].id,
                SYSTEM_PERMISSION_MAP["runbook:list"].id,
                SYSTEM_PERMISSION_MAP["runbook:create"].id,
                SYSTEM_PERMISSION_MAP["runbook:update"].id,
                SYSTEM_PERMISSION_MAP["runbook:execute"].id,
                SYSTEM_PERMISSION_MAP["action:read"].id,
                SYSTEM_PERMISSION_MAP["action:approve"].id,
                SYSTEM_PERMISSION_MAP["action:reject"].id,
                SYSTEM_PERMISSION_MAP["action:execute"].id,
                SYSTEM_PERMISSION_MAP["integration:read"].id,
                SYSTEM_PERMISSION_MAP["integration:list"].id,
            },
        ),
        Role(
            name="admin",
            display_name="Administrator",
            description="Full tenant administration access",
            role_type=RoleType.SYSTEM,
            permission_ids={p.id for p in SYSTEM_PERMISSIONS if p.scope != PermissionScope.GLOBAL},
        ),
        Role(
            name="super_admin",
            display_name="Super Administrator",
            description="Full system-wide access",
            role_type=RoleType.SYSTEM,
            permission_ids={p.id for p in SYSTEM_PERMISSIONS},
        ),
    ]


class RoleManager:
    """
    Manages roles and permissions for the RBAC system.
    
    Provides:
    - Role CRUD operations
    - Permission management
    - Role assignment to users
    - Role inheritance
    - Permission resolution
    
    Example:
        manager = RoleManager()
        
        # Create a custom role
        role = await manager.create_role(
            name="incident-commander",
            tenant_id="tenant-123",
            permission_ids={perm_id_1, perm_id_2},
        )
        
        # Assign to user
        await manager.assign_role(
            user_id="user-456",
            role_id=role.id,
            tenant_id="tenant-123",
        )
        
        # Check user permissions
        permissions = await manager.get_user_permissions(
            user_id="user-456",
            tenant_id="tenant-123",
        )
    """
    
    def __init__(self):
        """Initialize RoleManager with system roles and permissions."""
        self._permissions: Dict[str, Permission] = {}
        self._roles: Dict[str, Role] = {}
        self._user_roles: Dict[str, List[UserRole]] = {}  # user_id -> assignments
        self._lock = asyncio.Lock()
        
        # Initialize system permissions
        for perm in SYSTEM_PERMISSIONS:
            self._permissions[perm.id] = perm
        
        # Initialize system roles
        for role in create_system_roles():
            self._roles[role.id] = role
    
    # Permission Management
    
    async def create_permission(
        self,
        name: str,
        resource_type: ResourceType,
        action: ResourceAction,
        scope: PermissionScope = PermissionScope.TENANT,
        description: Optional[str] = None,
        conditions: Optional[Dict[str, Any]] = None,
    ) -> Permission:
        """Create a custom permission.
        
        Args:
            name: Permission name
            resource_type: Type of resource
            action: Action allowed
            scope: Permission scope
            description: Optional description
            conditions: Optional conditions
            
        Returns:
            Created permission
        """
        async with self._lock:
            permission = Permission(
                name=name,
                resource_type=resource_type,
                action=action,
                scope=scope,
                description=description,
                conditions=conditions or {},
            )
            
            self._permissions[permission.id] = permission
            
            logger.info(
                "Created permission",
                permission_id=permission.id,
                name=name,
            )
            
            return permission
    
    async def get_permission(self, permission_id: str) -> Optional[Permission]:
        """Get a permission by ID."""
        return self._permissions.get(permission_id)
    
    async def get_permission_by_name(self, name: str) -> Optional[Permission]:
        """Get a permission by name."""
        for perm in self._permissions.values():
            if perm.name == name:
                return perm
        return None
    
    async def list_permissions(
        self,
        resource_type: Optional[ResourceType] = None,
        action: Optional[ResourceAction] = None,
        include_system: bool = True,
    ) -> List[Permission]:
        """List permissions with optional filters.
        
        Args:
            resource_type: Filter by resource type
            action: Filter by action
            include_system: Include system permissions
            
        Returns:
            List of permissions
        """
        permissions = list(self._permissions.values())
        
        if not include_system:
            permissions = [p for p in permissions if not p.is_system]
        
        if resource_type:
            permissions = [p for p in permissions if p.resource_type == resource_type]
        
        if action:
            permissions = [p for p in permissions if p.action == action]
        
        return permissions
    
    async def delete_permission(self, permission_id: str) -> bool:
        """Delete a custom permission.
        
        Args:
            permission_id: Permission ID
            
        Returns:
            True if deleted
        """
        async with self._lock:
            permission = self._permissions.get(permission_id)
            
            if not permission:
                return False
            
            if permission.is_system:
                raise ValueError("Cannot delete system permission")
            
            # Remove from all roles
            for role in self._roles.values():
                role.permission_ids.discard(permission_id)
            
            del self._permissions[permission_id]
            
            logger.info(
                "Deleted permission",
                permission_id=permission_id,
            )
            
            return True
    
    # Role Management
    
    async def create_role(
        self,
        name: str,
        tenant_id: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        permission_ids: Optional[Set[str]] = None,
        parent_role_ids: Optional[Set[str]] = None,
        created_by: Optional[str] = None,
    ) -> Role:
        """Create a custom role.
        
        Args:
            name: Role name (must be unique within tenant)
            tenant_id: Tenant ID
            display_name: Human-readable name
            description: Role description
            permission_ids: Initial permissions
            parent_role_ids: Parent roles to inherit from
            created_by: User creating the role
            
        Returns:
            Created role
        """
        async with self._lock:
            # Check for duplicate name in tenant
            for role in self._roles.values():
                if role.name == name and role.tenant_id == tenant_id:
                    raise ValueError(f"Role '{name}' already exists in tenant")
            
            role = Role(
                name=name,
                display_name=display_name or name,
                description=description,
                role_type=RoleType.CUSTOM,
                tenant_id=tenant_id,
                permission_ids=permission_ids or set(),
                parent_role_ids=parent_role_ids or set(),
                created_by=created_by,
            )
            
            self._roles[role.id] = role
            
            logger.info(
                "Created role",
                role_id=role.id,
                name=name,
                tenant_id=tenant_id,
            )
            
            return role
    
    async def get_role(self, role_id: str) -> Optional[Role]:
        """Get a role by ID."""
        return self._roles.get(role_id)
    
    async def get_role_by_name(
        self,
        name: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[Role]:
        """Get a role by name.
        
        Args:
            name: Role name
            tenant_id: Tenant ID (None for system roles)
            
        Returns:
            Role if found
        """
        for role in self._roles.values():
            if role.name == name:
                if tenant_id is None and role.role_type == RoleType.SYSTEM:
                    return role
                if role.tenant_id == tenant_id:
                    return role
        return None
    
    async def list_roles(
        self,
        tenant_id: Optional[str] = None,
        include_system: bool = True,
        active_only: bool = True,
    ) -> List[Role]:
        """List roles with optional filters.
        
        Args:
            tenant_id: Filter by tenant
            include_system: Include system roles
            active_only: Only active roles
            
        Returns:
            List of roles
        """
        roles = list(self._roles.values())
        
        if active_only:
            roles = [r for r in roles if r.is_active]
        
        if tenant_id:
            # Include tenant roles and system roles
            if include_system:
                roles = [
                    r for r in roles
                    if r.tenant_id == tenant_id or r.role_type == RoleType.SYSTEM
                ]
            else:
                roles = [r for r in roles if r.tenant_id == tenant_id]
        elif not include_system:
            roles = [r for r in roles if r.role_type != RoleType.SYSTEM]
        
        return roles
    
    async def update_role(
        self,
        role_id: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        permission_ids: Optional[Set[str]] = None,
        parent_role_ids: Optional[Set[str]] = None,
        is_active: Optional[bool] = None,
    ) -> Role:
        """Update a role.
        
        Args:
            role_id: Role ID
            display_name: New display name
            description: New description
            permission_ids: New permission set (replaces existing)
            parent_role_ids: New parent roles (replaces existing)
            is_active: Activate/deactivate
            
        Returns:
            Updated role
        """
        async with self._lock:
            role = self._roles.get(role_id)
            
            if not role:
                raise ValueError(f"Role {role_id} not found")
            
            if display_name is not None:
                role.display_name = display_name
            if description is not None:
                role.description = description
            if permission_ids is not None:
                role.permission_ids = permission_ids
            if parent_role_ids is not None:
                role.parent_role_ids = parent_role_ids
            if is_active is not None:
                role.is_active = is_active
            
            role.updated_at = datetime.now(timezone.utc)
            
            logger.info(
                "Updated role",
                role_id=role_id,
            )
            
            return role
    
    async def delete_role(self, role_id: str) -> bool:
        """Delete a custom role.
        
        Args:
            role_id: Role ID
            
        Returns:
            True if deleted
        """
        async with self._lock:
            role = self._roles.get(role_id)
            
            if not role:
                return False
            
            if role.role_type == RoleType.SYSTEM:
                raise ValueError("Cannot delete system role")
            
            # Remove all user assignments for this role
            for user_id, assignments in self._user_roles.items():
                self._user_roles[user_id] = [
                    a for a in assignments if a.role_id != role_id
                ]
            
            # Remove as parent from other roles
            for r in self._roles.values():
                r.parent_role_ids.discard(role_id)
            
            del self._roles[role_id]
            
            logger.info(
                "Deleted role",
                role_id=role_id,
            )
            
            return True
    
    async def add_permission_to_role(
        self,
        role_id: str,
        permission_id: str,
    ) -> Role:
        """Add a permission to a role.
        
        Args:
            role_id: Role ID
            permission_id: Permission ID to add
            
        Returns:
            Updated role
        """
        async with self._lock:
            role = self._roles.get(role_id)
            
            if not role:
                raise ValueError(f"Role {role_id} not found")
            
            if permission_id not in self._permissions:
                raise ValueError(f"Permission {permission_id} not found")
            
            role.add_permission(permission_id)
            
            return role
    
    async def remove_permission_from_role(
        self,
        role_id: str,
        permission_id: str,
    ) -> Role:
        """Remove a permission from a role.
        
        Args:
            role_id: Role ID
            permission_id: Permission ID to remove
            
        Returns:
            Updated role
        """
        async with self._lock:
            role = self._roles.get(role_id)
            
            if not role:
                raise ValueError(f"Role {role_id} not found")
            
            role.remove_permission(permission_id)
            
            return role
    
    # Role Assignment
    
    async def assign_role(
        self,
        user_id: str,
        role_id: str,
        tenant_id: str,
        namespace_id: Optional[str] = None,
        valid_until: Optional[datetime] = None,
        assigned_by: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> UserRole:
        """Assign a role to a user.
        
        Args:
            user_id: User ID
            role_id: Role ID
            tenant_id: Tenant ID
            namespace_id: Optional namespace scope
            valid_until: Optional expiry
            assigned_by: User making assignment
            reason: Assignment reason
            
        Returns:
            Created assignment
        """
        async with self._lock:
            role = self._roles.get(role_id)
            
            if not role:
                raise ValueError(f"Role {role_id} not found")
            
            # Check if already assigned
            if user_id in self._user_roles:
                for assignment in self._user_roles[user_id]:
                    if (assignment.role_id == role_id and 
                        assignment.tenant_id == tenant_id and
                        assignment.namespace_id == namespace_id and
                        assignment.is_valid()):
                        raise ValueError("Role already assigned to user")
            
            assignment = UserRole(
                user_id=user_id,
                role_id=role_id,
                tenant_id=tenant_id,
                namespace_id=namespace_id,
                valid_until=valid_until,
                assigned_by=assigned_by,
                assignment_reason=reason,
            )
            
            if user_id not in self._user_roles:
                self._user_roles[user_id] = []
            self._user_roles[user_id].append(assignment)
            
            logger.info(
                "Assigned role",
                user_id=user_id,
                role_id=role_id,
                tenant_id=tenant_id,
            )
            
            return assignment
    
    async def revoke_role(
        self,
        user_id: str,
        role_id: str,
        tenant_id: str,
    ) -> bool:
        """Revoke a role from a user.
        
        Args:
            user_id: User ID
            role_id: Role ID
            tenant_id: Tenant ID
            
        Returns:
            True if revoked
        """
        async with self._lock:
            if user_id not in self._user_roles:
                return False
            
            initial_count = len(self._user_roles[user_id])
            self._user_roles[user_id] = [
                a for a in self._user_roles[user_id]
                if not (a.role_id == role_id and a.tenant_id == tenant_id)
            ]
            
            revoked = len(self._user_roles[user_id]) < initial_count
            
            if revoked:
                logger.info(
                    "Revoked role",
                    user_id=user_id,
                    role_id=role_id,
                    tenant_id=tenant_id,
                )
            
            return revoked
    
    async def get_user_roles(
        self,
        user_id: str,
        tenant_id: Optional[str] = None,
        valid_only: bool = True,
    ) -> List[UserRole]:
        """Get roles assigned to a user.
        
        Args:
            user_id: User ID
            tenant_id: Optional tenant filter
            valid_only: Only return currently valid assignments
            
        Returns:
            List of role assignments
        """
        assignments = self._user_roles.get(user_id, [])
        
        if tenant_id:
            assignments = [a for a in assignments if a.tenant_id == tenant_id]
        
        if valid_only:
            assignments = [a for a in assignments if a.is_valid()]
        
        return assignments
    
    async def get_user_permissions(
        self,
        user_id: str,
        tenant_id: str,
        namespace_id: Optional[str] = None,
    ) -> Set[Permission]:
        """Get all permissions for a user (resolved through role hierarchy).
        
        Args:
            user_id: User ID
            tenant_id: Tenant ID
            namespace_id: Optional namespace scope
            
        Returns:
            Set of permissions
        """
        permissions: Set[Permission] = set()
        
        # Get user's role assignments
        assignments = await self.get_user_roles(user_id, tenant_id)
        
        # Filter by namespace if specified
        if namespace_id:
            assignments = [
                a for a in assignments
                if a.namespace_id is None or a.namespace_id == namespace_id
            ]
        
        # Collect role IDs (including inherited)
        role_ids_to_process: Set[str] = {a.role_id for a in assignments}
        processed_role_ids: Set[str] = set()
        
        while role_ids_to_process:
            role_id = role_ids_to_process.pop()
            
            if role_id in processed_role_ids:
                continue
            processed_role_ids.add(role_id)
            
            role = self._roles.get(role_id)
            if not role or not role.is_active:
                continue
            
            # Add direct permissions
            for perm_id in role.permission_ids:
                perm = self._permissions.get(perm_id)
                if perm:
                    permissions.add(perm)
            
            # Add parent roles to process
            role_ids_to_process.update(role.parent_role_ids - processed_role_ids)
        
        return permissions
    
    async def has_permission(
        self,
        user_id: str,
        tenant_id: str,
        resource_type: ResourceType,
        action: ResourceAction,
        context: Optional[Dict[str, Any]] = None,
        namespace_id: Optional[str] = None,
    ) -> bool:
        """Check if user has a specific permission.
        
        Args:
            user_id: User ID
            tenant_id: Tenant ID
            resource_type: Resource type
            action: Required action
            context: Optional context for condition checking
            namespace_id: Optional namespace scope
            
        Returns:
            True if permitted
        """
        permissions = await self.get_user_permissions(user_id, tenant_id, namespace_id)
        
        for perm in permissions:
            if perm.matches(resource_type, action, context):
                return True
        
        return False
