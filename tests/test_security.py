"""
Tests for the RBAC (Role-Based Access Control) module.
"""

import pytest

from autosre.security.rbac import (
    Permission,
    RBACContext,
    ROLE_PERMISSIONS,
    check_permission,
    get_role_permissions,
    get_user_permissions,
    has_admin,
    can_execute_command,
    require_permission,
)


class TestPermissionEnum:
    """Test Permission enum."""
    
    def test_permission_values(self):
        """Test permission enum has expected values."""
        assert Permission.READ_METRICS.value == "read:metrics"
        assert Permission.EXECUTE_SAFE.value == "execute:safe"
        assert Permission.EXECUTE_HIGH.value == "execute:high"
        assert Permission.ADMIN.value == "admin:all"


class TestRolePermissions:
    """Test role permission mappings."""
    
    def test_viewer_permissions(self):
        """Test viewer has read-only permissions."""
        perms = ROLE_PERMISSIONS["viewer"]
        assert Permission.READ_METRICS in perms
        assert Permission.READ_LOGS in perms
        assert Permission.EXECUTE_SAFE not in perms
    
    def test_operator_permissions(self):
        """Test operator can execute safe and medium commands."""
        perms = ROLE_PERMISSIONS["operator"]
        assert Permission.EXECUTE_SAFE in perms
        assert Permission.EXECUTE_MEDIUM in perms
        assert Permission.EXECUTE_HIGH not in perms
    
    def test_sre_permissions(self):
        """Test SRE has full execution permissions."""
        perms = ROLE_PERMISSIONS["sre"]
        assert Permission.EXECUTE_SAFE in perms
        assert Permission.EXECUTE_MEDIUM in perms
        assert Permission.EXECUTE_HIGH in perms
        assert Permission.APPROVE_ACTIONS in perms
    
    def test_admin_permissions(self):
        """Test admin has admin permission."""
        perms = ROLE_PERMISSIONS["admin"]
        assert Permission.ADMIN in perms


class TestCheckPermission:
    """Test check_permission function."""
    
    def test_viewer_can_read(self):
        """Test viewer can read metrics."""
        assert check_permission(["viewer"], Permission.READ_METRICS) is True
    
    def test_viewer_cannot_execute(self):
        """Test viewer cannot execute commands."""
        assert check_permission(["viewer"], Permission.EXECUTE_SAFE) is False
    
    def test_operator_can_execute_medium(self):
        """Test operator can execute medium-risk commands."""
        assert check_permission(["operator"], Permission.EXECUTE_MEDIUM) is True
    
    def test_operator_cannot_execute_high(self):
        """Test operator cannot execute high-risk commands."""
        assert check_permission(["operator"], Permission.EXECUTE_HIGH) is False
    
    def test_sre_can_execute_high(self):
        """Test SRE can execute high-risk commands."""
        assert check_permission(["sre"], Permission.EXECUTE_HIGH) is True
    
    def test_admin_can_do_anything(self):
        """Test admin has all permissions."""
        assert check_permission(["admin"], Permission.READ_METRICS) is True
        assert check_permission(["admin"], Permission.EXECUTE_HIGH) is True
        assert check_permission(["admin"], Permission.MANAGE_USERS) is True
    
    def test_multiple_roles(self):
        """Test user with multiple roles."""
        # Viewer + operator gets operator permissions
        assert check_permission(["viewer", "operator"], Permission.EXECUTE_SAFE) is True
    
    def test_unknown_role(self):
        """Test unknown role has no permissions."""
        assert check_permission(["unknown"], Permission.READ_METRICS) is False


class TestGetPermissions:
    """Test permission retrieval functions."""
    
    def test_get_role_permissions(self):
        """Test getting permissions for a role."""
        perms = get_role_permissions("viewer")
        assert Permission.READ_METRICS in perms
        assert len(perms) == 4  # 4 read permissions
    
    def test_get_unknown_role_permissions(self):
        """Test getting permissions for unknown role."""
        perms = get_role_permissions("nonexistent")
        assert perms == []
    
    def test_get_user_permissions_single_role(self):
        """Test getting all user permissions."""
        perms = get_user_permissions(["operator"])
        assert Permission.READ_METRICS in perms
        assert Permission.EXECUTE_MEDIUM in perms
    
    def test_get_user_permissions_admin(self):
        """Test admin gets all permissions."""
        perms = get_user_permissions(["admin"])
        assert len(perms) == len(Permission)


class TestHasAdmin:
    """Test has_admin function."""
    
    def test_admin_role(self):
        """Test user with admin role."""
        assert has_admin(["admin"]) is True
    
    def test_non_admin_role(self):
        """Test user without admin role."""
        assert has_admin(["sre"]) is False
    
    def test_multiple_roles_with_admin(self):
        """Test user with multiple roles including admin."""
        assert has_admin(["viewer", "admin"]) is True


class TestCanExecuteCommand:
    """Test can_execute_command function."""
    
    def test_viewer_cannot_execute_any(self):
        """Test viewer cannot execute any commands."""
        assert can_execute_command(["viewer"], "low") is False
        assert can_execute_command(["viewer"], "medium") is False
        assert can_execute_command(["viewer"], "high") is False
    
    def test_operator_low_medium(self):
        """Test operator can execute low and medium."""
        assert can_execute_command(["operator"], "low") is True
        assert can_execute_command(["operator"], "medium") is True
        assert can_execute_command(["operator"], "high") is False
    
    def test_sre_all_levels(self):
        """Test SRE can execute all levels."""
        assert can_execute_command(["sre"], "low") is True
        assert can_execute_command(["sre"], "medium") is True
        assert can_execute_command(["sre"], "high") is True
    
    def test_invalid_risk_level(self):
        """Test invalid risk level returns False."""
        assert can_execute_command(["sre"], "extreme") is False


class TestRBACContext:
    """Test RBACContext dataclass."""
    
    def test_context_creation(self):
        """Test creating RBAC context."""
        ctx = RBACContext(
            user="alice@example.com",
            roles=["sre", "operator"],
            namespace="production",
            resource="deployment/api",
        )
        assert ctx.user == "alice@example.com"
        assert "sre" in ctx.roles
        assert ctx.namespace == "production"
    
    def test_context_defaults(self):
        """Test context defaults."""
        ctx = RBACContext(user="bob", roles=["viewer"])
        assert ctx.resource is None
        assert ctx.namespace is None


class TestRequirePermissionDecorator:
    """Test require_permission decorator."""
    
    def test_sync_function_allowed(self):
        """Test sync function with correct permission."""
        @require_permission(Permission.READ_METRICS)
        def read_metrics(_current_user=None):
            return "metrics"
        
        result = read_metrics(_current_user={"roles": ["viewer"]})
        assert result == "metrics"
    
    def test_sync_function_denied(self):
        """Test sync function without permission."""
        @require_permission(Permission.EXECUTE_HIGH)
        def dangerous_action(_current_user=None):
            return "done"
        
        with pytest.raises(PermissionError, match="Permission denied"):
            dangerous_action(_current_user={"roles": ["viewer"]})
    
    def test_missing_user(self):
        """Test function without user context."""
        @require_permission(Permission.READ_METRICS)
        def read_metrics(_current_user=None):
            return "metrics"
        
        with pytest.raises(PermissionError, match="Authentication required"):
            read_metrics()
    
    @pytest.mark.asyncio
    async def test_async_function_allowed(self):
        """Test async function with correct permission."""
        @require_permission(Permission.READ_METRICS)
        async def async_read(_current_user=None):
            return "async metrics"
        
        result = await async_read(_current_user={"roles": ["viewer"]})
        assert result == "async metrics"
    
    @pytest.mark.asyncio
    async def test_async_function_denied(self):
        """Test async function without permission."""
        @require_permission(Permission.EXECUTE_HIGH)
        async def async_dangerous(_current_user=None):
            return "done"
        
        with pytest.raises(PermissionError, match="Permission denied"):
            await async_dangerous(_current_user={"roles": ["operator"]})
