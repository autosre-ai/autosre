"""
Security Tests - RBAC
"""

import pytest
from opensre_core.security.rbac import (
    Permission,
    ROLE_PERMISSIONS,
    check_permission,
    get_role_permissions,
    get_user_permissions,
    has_admin,
    can_execute_command,
    require_permission,
)


class TestPermission:
    """Tests for Permission enum."""
    
    def test_permission_values(self):
        """Test permission value format."""
        assert Permission.READ_METRICS.value == "read:metrics"
        assert Permission.EXECUTE_HIGH.value == "execute:high"
        assert Permission.ADMIN.value == "admin:all"


class TestRolePermissions:
    """Tests for role-permission mappings."""
    
    def test_viewer_has_read_permissions(self):
        """Viewer can read but not execute."""
        perms = get_role_permissions("viewer")
        
        assert Permission.READ_METRICS in perms
        assert Permission.READ_LOGS in perms
        assert Permission.READ_EVENTS in perms
        assert Permission.EXECUTE_SAFE not in perms
        assert Permission.EXECUTE_HIGH not in perms
    
    def test_operator_has_safe_execute(self):
        """Operator can execute safe and medium commands."""
        perms = get_role_permissions("operator")
        
        assert Permission.READ_METRICS in perms
        assert Permission.EXECUTE_SAFE in perms
        assert Permission.EXECUTE_MEDIUM in perms
        assert Permission.EXECUTE_HIGH not in perms
        assert Permission.APPROVE_ACTIONS not in perms
    
    def test_sre_has_all_execute(self):
        """SRE can execute all commands and approve."""
        perms = get_role_permissions("sre")
        
        assert Permission.EXECUTE_SAFE in perms
        assert Permission.EXECUTE_MEDIUM in perms
        assert Permission.EXECUTE_HIGH in perms
        assert Permission.APPROVE_ACTIONS in perms
    
    def test_admin_has_admin_permission(self):
        """Admin has admin:all permission."""
        perms = get_role_permissions("admin")
        
        assert Permission.ADMIN in perms


class TestCheckPermission:
    """Tests for check_permission function."""
    
    def test_viewer_can_read(self):
        """Viewer can read metrics."""
        assert check_permission(["viewer"], Permission.READ_METRICS) == True
        assert check_permission(["viewer"], Permission.READ_LOGS) == True
    
    def test_viewer_cannot_execute(self):
        """Viewer cannot execute commands."""
        assert check_permission(["viewer"], Permission.EXECUTE_SAFE) == False
        assert check_permission(["viewer"], Permission.EXECUTE_HIGH) == False
    
    def test_operator_can_execute_safe(self):
        """Operator can execute safe commands."""
        assert check_permission(["operator"], Permission.EXECUTE_SAFE) == True
        assert check_permission(["operator"], Permission.EXECUTE_MEDIUM) == True
    
    def test_operator_cannot_execute_high(self):
        """Operator cannot execute high-risk commands."""
        assert check_permission(["operator"], Permission.EXECUTE_HIGH) == False
    
    def test_sre_can_execute_all(self):
        """SRE can execute all commands."""
        assert check_permission(["sre"], Permission.EXECUTE_SAFE) == True
        assert check_permission(["sre"], Permission.EXECUTE_MEDIUM) == True
        assert check_permission(["sre"], Permission.EXECUTE_HIGH) == True
    
    def test_admin_has_all_permissions(self):
        """Admin has all permissions."""
        assert check_permission(["admin"], Permission.READ_METRICS) == True
        assert check_permission(["admin"], Permission.EXECUTE_HIGH) == True
        assert check_permission(["admin"], Permission.MANAGE_USERS) == True
    
    def test_multiple_roles(self):
        """User with multiple roles has combined permissions."""
        # Viewer + operator
        assert check_permission(["viewer", "operator"], Permission.EXECUTE_SAFE) == True
        
        # Unknown + viewer
        assert check_permission(["unknown", "viewer"], Permission.READ_METRICS) == True
    
    def test_unknown_role(self):
        """Unknown role has no permissions."""
        assert check_permission(["unknown"], Permission.READ_METRICS) == False
        assert check_permission(["fake_role"], Permission.EXECUTE_SAFE) == False
    
    def test_empty_roles(self):
        """Empty roles list has no permissions."""
        assert check_permission([], Permission.READ_METRICS) == False


class TestGetUserPermissions:
    """Tests for get_user_permissions function."""
    
    def test_single_role(self):
        """Get permissions for single role."""
        perms = get_user_permissions(["viewer"])
        
        assert Permission.READ_METRICS in perms
        assert Permission.EXECUTE_SAFE not in perms
    
    def test_multiple_roles(self):
        """Get combined permissions for multiple roles."""
        perms = get_user_permissions(["viewer", "operator"])
        
        # Should have viewer permissions
        assert Permission.READ_METRICS in perms
        # Should also have operator permissions
        assert Permission.EXECUTE_SAFE in perms
        assert Permission.EXECUTE_MEDIUM in perms
    
    def test_admin_gets_all(self):
        """Admin gets all permissions."""
        perms = get_user_permissions(["admin"])
        
        # Should have all Permission enum values
        assert len(perms) == len(Permission)


class TestHasAdmin:
    """Tests for has_admin function."""
    
    def test_admin_role(self):
        """User with admin role has admin."""
        assert has_admin(["admin"]) == True
        assert has_admin(["viewer", "admin"]) == True
    
    def test_no_admin(self):
        """User without admin doesn't have admin."""
        assert has_admin(["viewer"]) == False
        assert has_admin(["sre"]) == False
        assert has_admin([]) == False


class TestCanExecuteCommand:
    """Tests for can_execute_command function."""
    
    def test_viewer_cannot_execute(self):
        """Viewer cannot execute any commands."""
        assert can_execute_command(["viewer"], "low") == False
        assert can_execute_command(["viewer"], "medium") == False
        assert can_execute_command(["viewer"], "high") == False
    
    def test_operator_can_execute_low_medium(self):
        """Operator can execute low and medium risk."""
        assert can_execute_command(["operator"], "low") == True
        assert can_execute_command(["operator"], "medium") == True
        assert can_execute_command(["operator"], "high") == False
    
    def test_sre_can_execute_all(self):
        """SRE can execute all risk levels."""
        assert can_execute_command(["sre"], "low") == True
        assert can_execute_command(["sre"], "medium") == True
        assert can_execute_command(["sre"], "high") == True
    
    def test_invalid_risk_level(self):
        """Invalid risk level returns False."""
        assert can_execute_command(["sre"], "invalid") == False
        assert can_execute_command(["admin"], "extreme") == False


class TestRequirePermission:
    """Tests for require_permission decorator."""
    
    def test_require_permission_sync(self):
        """Test require_permission on sync function."""
        @require_permission(Permission.READ_METRICS)
        def protected_read(_current_user=None):
            return "success"
        
        # With valid permission
        result = protected_read(_current_user={"user": "test", "roles": ["viewer"]})
        assert result == "success"
    
    def test_require_permission_denied_sync(self):
        """Test require_permission denies without permission."""
        @require_permission(Permission.EXECUTE_HIGH)
        def protected_execute(_current_user=None):
            return "success"
        
        # Viewer cannot execute high
        with pytest.raises(PermissionError) as exc_info:
            protected_execute(_current_user={"user": "test", "roles": ["viewer"]})
        assert "Permission denied" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_require_permission_async(self):
        """Test require_permission on async function."""
        @require_permission(Permission.EXECUTE_MEDIUM)
        async def protected_async(_current_user=None):
            return "async_success"
        
        # With valid permission
        result = await protected_async(_current_user={"user": "test", "roles": ["operator"]})
        assert result == "async_success"
    
    @pytest.mark.asyncio
    async def test_require_permission_denied_async(self):
        """Test require_permission denies without permission (async)."""
        @require_permission(Permission.EXECUTE_HIGH)
        async def protected_async(_current_user=None):
            return "success"
        
        # Operator cannot execute high
        with pytest.raises(PermissionError):
            await protected_async(_current_user={"user": "test", "roles": ["operator"]})
    
    def test_require_permission_no_user(self):
        """Test require_permission fails without user."""
        @require_permission(Permission.READ_METRICS)
        def protected_func(_current_user=None):
            return "success"
        
        with pytest.raises(PermissionError) as exc_info:
            protected_func()
        assert "Authentication required" in str(exc_info.value)
