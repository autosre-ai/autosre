"""
Role-Based Access Control (RBAC) Module
"""

from enum import Enum
from typing import Optional
from dataclasses import dataclass


class Permission(Enum):
    """Permissions available in OpenSRE."""
    
    # Read permissions
    READ_METRICS = "read:metrics"
    READ_LOGS = "read:logs"
    READ_EVENTS = "read:events"
    READ_INVESTIGATIONS = "read:investigations"
    
    # Execute permissions (tiered by risk)
    EXECUTE_SAFE = "execute:safe"        # Low-risk commands (get, describe, logs)
    EXECUTE_MEDIUM = "execute:medium"    # Medium-risk (scale, cordon, rollout)
    EXECUTE_HIGH = "execute:high"        # High-risk/destructive (delete, apply, patch)
    
    # Management permissions
    APPROVE_ACTIONS = "approve:actions"
    MANAGE_RUNBOOKS = "manage:runbooks"
    MANAGE_USERS = "manage:users"
    
    # Admin
    ADMIN = "admin:all"


# Role definitions with their permissions
ROLE_PERMISSIONS: dict[str, list[Permission]] = {
    "viewer": [
        Permission.READ_METRICS,
        Permission.READ_LOGS,
        Permission.READ_EVENTS,
        Permission.READ_INVESTIGATIONS,
    ],
    
    "operator": [
        Permission.READ_METRICS,
        Permission.READ_LOGS,
        Permission.READ_EVENTS,
        Permission.READ_INVESTIGATIONS,
        Permission.EXECUTE_SAFE,
        Permission.EXECUTE_MEDIUM,
    ],
    
    "sre": [
        Permission.READ_METRICS,
        Permission.READ_LOGS,
        Permission.READ_EVENTS,
        Permission.READ_INVESTIGATIONS,
        Permission.EXECUTE_SAFE,
        Permission.EXECUTE_MEDIUM,
        Permission.EXECUTE_HIGH,
        Permission.APPROVE_ACTIONS,
        Permission.MANAGE_RUNBOOKS,
    ],
    
    "admin": [
        Permission.ADMIN,
    ],
}


@dataclass
class RBACContext:
    """Context for RBAC checks."""
    user: str
    roles: list[str]
    resource: Optional[str] = None
    namespace: Optional[str] = None


def check_permission(user_roles: list[str], required: Permission) -> bool:
    """
    Check if a user with the given roles has a specific permission.
    
    Args:
        user_roles: List of role names the user has
        required: The permission to check
    
    Returns:
        True if user has the permission, False otherwise
    """
    for role in user_roles:
        if role in ROLE_PERMISSIONS:
            permissions = ROLE_PERMISSIONS[role]
            # Admin has all permissions
            if Permission.ADMIN in permissions:
                return True
            if required in permissions:
                return True
    return False


def get_role_permissions(role: str) -> list[Permission]:
    """Get all permissions for a role."""
    return ROLE_PERMISSIONS.get(role, [])


def get_user_permissions(roles: list[str]) -> set[Permission]:
    """Get all permissions a user has based on their roles."""
    permissions = set()
    for role in roles:
        if role in ROLE_PERMISSIONS:
            role_perms = ROLE_PERMISSIONS[role]
            # If admin, return all permissions
            if Permission.ADMIN in role_perms:
                return set(Permission)
            permissions.update(role_perms)
    return permissions


def has_admin(roles: list[str]) -> bool:
    """Check if user has admin role."""
    return "admin" in roles or check_permission(roles, Permission.ADMIN)


def can_execute_command(roles: list[str], risk_level: str) -> bool:
    """
    Check if user can execute a command based on its risk level.
    
    Args:
        roles: User's roles
        risk_level: "low", "medium", or "high"
    
    Returns:
        True if user can execute
    """
    risk_to_permission = {
        "low": Permission.EXECUTE_SAFE,
        "medium": Permission.EXECUTE_MEDIUM,
        "high": Permission.EXECUTE_HIGH,
    }
    
    required = risk_to_permission.get(risk_level.lower())
    if not required:
        return False
    
    return check_permission(roles, required)


def require_permission(permission: Permission):
    """
    Decorator to require a specific permission.
    
    Usage:
        @require_permission(Permission.EXECUTE_HIGH)
        async def delete_resource():
            ...
    """
    from functools import wraps
    
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            user_info = kwargs.get("_current_user")
            if not user_info:
                raise PermissionError("Authentication required")
            
            roles = user_info.get("roles", [])
            if not check_permission(roles, permission):
                raise PermissionError(f"Permission denied: {permission.value}")
            
            return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            user_info = kwargs.get("_current_user")
            if not user_info:
                raise PermissionError("Authentication required")
            
            roles = user_info.get("roles", [])
            if not check_permission(roles, permission):
                raise PermissionError(f"Permission denied: {permission.value}")
            
            return func(*args, **kwargs)
        
        import asyncio
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator
