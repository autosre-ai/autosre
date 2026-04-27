"""
Tests for the security/auth module.
"""

import os
import tempfile
import pytest
from datetime import datetime, timedelta
from pathlib import Path

from autosre.security.auth import (
    AuthToken,
    AuthManager,
    get_auth_manager,
    require_auth,
    validate_token,
)


class TestAuthToken:
    """Test AuthToken dataclass."""
    
    def test_token_creation(self):
        """Test creating an auth token."""
        token = AuthToken(
            token="test-token-123",
            user="testuser",
            roles=["viewer", "sre"],
        )
        assert token.token == "test-token-123"
        assert token.user == "testuser"
        assert token.roles == ["viewer", "sre"]
        assert token.created_at is not None
        assert token.expires_at is None
    
    def test_token_not_expired_when_no_expiry(self):
        """Test token without expiry is never expired."""
        token = AuthToken(
            token="test",
            user="user",
            roles=[],
            expires_at=None,
        )
        assert not token.is_expired()
    
    def test_token_not_expired_future(self):
        """Test token with future expiry is not expired."""
        token = AuthToken(
            token="test",
            user="user",
            roles=[],
            expires_at=datetime.now() + timedelta(hours=1),
        )
        assert not token.is_expired()
    
    def test_token_expired_past(self):
        """Test token with past expiry is expired."""
        token = AuthToken(
            token="test",
            user="user",
            roles=[],
            expires_at=datetime.now() - timedelta(hours=1),
        )
        assert token.is_expired()
    
    def test_token_to_dict(self):
        """Test converting token to dictionary."""
        token = AuthToken(
            token="test-token",
            user="testuser",
            roles=["admin"],
        )
        d = token.to_dict()
        assert "token_hash" in d
        assert len(d["token_hash"]) == 16
        assert d["user"] == "testuser"
        assert d["roles"] == ["admin"]
        assert "created_at" in d


class TestAuthManager:
    """Test AuthManager class."""
    
    @pytest.fixture
    def temp_keys_file(self):
        """Create a temporary keys file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"api_keys": {}}')
            yield f.name
        os.unlink(f.name)
    
    @pytest.fixture
    def auth_manager(self, temp_keys_file):
        """Create an AuthManager with temp file."""
        return AuthManager(keys_file=temp_keys_file)
    
    def test_init_without_file(self):
        """Test init without keys file."""
        manager = AuthManager()
        assert manager.api_keys == {}
        assert manager.tokens == {}
    
    def test_init_with_nonexistent_file(self, tmp_path):
        """Test init with file that doesn't exist."""
        manager = AuthManager(keys_file=str(tmp_path / "nonexistent.json"))
        assert manager.api_keys == {}
    
    def test_generate_api_key(self, auth_manager):
        """Test generating an API key."""
        key = auth_manager.generate_api_key("testuser", roles=["sre"])
        assert key is not None
        assert len(key) > 20
        # Key should be stored (hashed)
        assert len(auth_manager.api_keys) == 1
    
    def test_generate_api_key_default_roles(self, auth_manager):
        """Test generating API key with default roles."""
        key = auth_manager.generate_api_key("testuser")
        # Validate to check stored roles
        info = auth_manager.validate_api_key(key)
        assert info["roles"] == ["viewer"]
    
    def test_validate_api_key_valid(self, auth_manager):
        """Test validating a valid API key."""
        key = auth_manager.generate_api_key("testuser", roles=["admin"])
        info = auth_manager.validate_api_key(key)
        assert info is not None
        assert info["user"] == "testuser"
        assert info["roles"] == ["admin"]
    
    def test_validate_api_key_invalid(self, auth_manager):
        """Test validating an invalid API key."""
        info = auth_manager.validate_api_key("invalid-key-12345")
        assert info is None
    
    def test_validate_api_key_empty(self, auth_manager):
        """Test validating empty API key."""
        info = auth_manager.validate_api_key("")
        assert info is None
    
    def test_validate_api_key_none(self, auth_manager):
        """Test validating None API key."""
        info = auth_manager.validate_api_key(None)
        assert info is None
    
    def test_revoke_api_key_valid(self, auth_manager):
        """Test revoking a valid API key."""
        key = auth_manager.generate_api_key("testuser")
        result = auth_manager.revoke_api_key(key)
        assert result is True
        # Key should no longer be valid
        assert auth_manager.validate_api_key(key) is None
    
    def test_revoke_api_key_invalid(self, auth_manager):
        """Test revoking an invalid API key."""
        result = auth_manager.revoke_api_key("nonexistent-key")
        assert result is False
    
    def test_create_token(self, auth_manager):
        """Test creating a session token."""
        token = auth_manager.create_token(
            user="testuser",
            roles=["sre"],
            expires_in=timedelta(hours=1),
        )
        assert token.token is not None
        assert token.user == "testuser"
        assert token.roles == ["sre"]
        assert not token.is_expired()
    
    def test_validate_token_valid(self, auth_manager):
        """Test validating a valid token."""
        token = auth_manager.create_token("testuser", ["admin"])
        validated = auth_manager.validate_token(token.token)
        assert validated is not None
        assert validated.user == "testuser"
    
    def test_validate_token_invalid(self, auth_manager):
        """Test validating an invalid token."""
        result = auth_manager.validate_token("invalid-token")
        assert result is None
    
    def test_validate_token_empty(self, auth_manager):
        """Test validating empty token."""
        result = auth_manager.validate_token("")
        assert result is None
    
    def test_validate_token_expired(self, auth_manager):
        """Test validating an expired token."""
        token = auth_manager.create_token(
            "testuser",
            ["sre"],
            expires_in=timedelta(seconds=-1),  # Already expired
        )
        result = auth_manager.validate_token(token.token)
        assert result is None
    
    def test_get_current_user_with_api_key(self, auth_manager):
        """Test getting current user with API key."""
        key = auth_manager.generate_api_key("testuser", ["admin"])
        user = auth_manager.get_current_user(api_key=key)
        assert user is not None
        assert user["user"] == "testuser"
    
    def test_get_current_user_with_token(self, auth_manager):
        """Test getting current user with token."""
        token = auth_manager.create_token("testuser", ["sre"])
        user = auth_manager.get_current_user(token=token.token)
        assert user is not None
        assert user["user"] == "testuser"
    
    def test_get_current_user_with_env_var(self, auth_manager, monkeypatch):
        """Test getting current user from environment variable."""
        key = auth_manager.generate_api_key("envuser", ["viewer"])
        monkeypatch.setenv("OPENSRE_API_KEY", key)
        user = auth_manager.get_current_user()
        assert user is not None
        assert user["user"] == "envuser"
    
    def test_get_current_user_no_credentials(self, auth_manager):
        """Test getting current user without credentials."""
        user = auth_manager.get_current_user()
        assert user is None
    
    def test_keys_persistence(self, temp_keys_file):
        """Test that keys persist across manager instances."""
        manager1 = AuthManager(keys_file=temp_keys_file)
        key = manager1.generate_api_key("testuser", ["admin"])
        
        # Create new manager instance
        manager2 = AuthManager(keys_file=temp_keys_file)
        info = manager2.validate_api_key(key)
        assert info is not None
        assert info["user"] == "testuser"


class TestGetAuthManager:
    """Test get_auth_manager singleton."""
    
    def test_returns_auth_manager(self):
        """Test that get_auth_manager returns an AuthManager."""
        # Reset global state
        import autosre.security.auth as auth_module
        auth_module._auth_manager = None
        
        manager = get_auth_manager()
        assert isinstance(manager, AuthManager)
    
    def test_returns_same_instance(self):
        """Test that get_auth_manager returns singleton."""
        import autosre.security.auth as auth_module
        auth_module._auth_manager = None
        
        manager1 = get_auth_manager()
        manager2 = get_auth_manager()
        assert manager1 is manager2


class TestRequireAuthDecorator:
    """Test require_auth decorator."""
    
    @pytest.fixture(autouse=True)
    def reset_auth(self):
        """Reset global auth manager before each test."""
        import autosre.security.auth as auth_module
        auth_module._auth_manager = None
        yield
        auth_module._auth_manager = None
    
    def test_sync_function_with_api_key(self, monkeypatch):
        """Test decorating sync function with API key auth."""
        manager = get_auth_manager()
        key = manager.generate_api_key("testuser", ["sre"])
        
        @require_auth
        def protected_func(_current_user=None):
            return _current_user
        
        result = protected_func(api_key=key)
        assert result is not None
        assert result["user"] == "testuser"
    
    def test_sync_function_without_auth(self):
        """Test decorating sync function without authentication."""
        @require_auth
        def protected_func(_current_user=None):
            return _current_user
        
        with pytest.raises(PermissionError, match="Authentication required"):
            protected_func()
    
    def test_sync_function_with_role_requirement(self):
        """Test decorating sync function with role requirement."""
        manager = get_auth_manager()
        key = manager.generate_api_key("testuser", ["viewer"])
        
        @require_auth(roles=["admin"])
        def admin_func(_current_user=None):
            return _current_user
        
        with pytest.raises(PermissionError, match="Required roles"):
            admin_func(api_key=key)
    
    def test_sync_function_admin_bypasses_roles(self):
        """Test that admin role bypasses specific role requirements."""
        manager = get_auth_manager()
        key = manager.generate_api_key("adminuser", ["admin"])
        
        @require_auth(roles=["special"])
        def special_func(_current_user=None):
            return _current_user
        
        result = special_func(api_key=key)
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_async_function_with_api_key(self):
        """Test decorating async function with API key auth."""
        manager = get_auth_manager()
        key = manager.generate_api_key("asyncuser", ["sre"])
        
        @require_auth
        async def async_protected(_current_user=None):
            return _current_user
        
        result = await async_protected(api_key=key)
        assert result is not None
        assert result["user"] == "asyncuser"
    
    @pytest.mark.asyncio
    async def test_async_function_without_auth(self):
        """Test decorating async function without authentication."""
        @require_auth
        async def async_protected(_current_user=None):
            return _current_user
        
        with pytest.raises(PermissionError, match="Authentication required"):
            await async_protected()


class TestValidateTokenFunction:
    """Test the module-level validate_token function."""
    
    @pytest.fixture(autouse=True)
    def reset_auth(self):
        """Reset global auth manager before each test."""
        import autosre.security.auth as auth_module
        auth_module._auth_manager = None
        yield
        auth_module._auth_manager = None
    
    def test_validate_valid_token(self):
        """Test validating a valid token."""
        manager = get_auth_manager()
        token = manager.create_token("testuser", ["sre"])
        
        result = validate_token(token.token)
        assert result is not None
        assert result["user"] == "testuser"
        assert result["roles"] == ["sre"]
    
    def test_validate_invalid_token(self):
        """Test validating an invalid token."""
        result = validate_token("invalid-token-string")
        assert result is None
