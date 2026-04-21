"""
Security Tests - Authentication
"""

import os
import tempfile
from datetime import timedelta
from pathlib import Path

import pytest

from opensre_core.security.auth import (
    AuthManager,
    AuthToken,
    require_auth,
)


class TestAuthToken:
    """Tests for AuthToken dataclass."""

    def test_token_not_expired_by_default(self):
        """Tokens without expiry are never expired."""
        token = AuthToken(
            token="test_token",
            user="test_user",
            roles=["viewer"],
        )
        assert not token.is_expired()

    def test_token_expiry(self):
        """Test token expiration check."""
        from datetime import datetime

        # Expired token
        token = AuthToken(
            token="test_token",
            user="test_user",
            roles=["viewer"],
            expires_at=datetime(2020, 1, 1),
        )
        assert token.is_expired()

        # Future expiry
        token = AuthToken(
            token="test_token",
            user="test_user",
            roles=["viewer"],
            expires_at=datetime(2099, 1, 1),
        )
        assert not token.is_expired()

    def test_token_to_dict(self):
        """Test token serialization."""
        token = AuthToken(
            token="test_token",
            user="test_user",
            roles=["viewer", "operator"],
        )
        d = token.to_dict()

        assert d["user"] == "test_user"
        assert d["roles"] == ["viewer", "operator"]
        assert "token_hash" in d
        # Token hash should not reveal the actual token
        assert d["token_hash"] != "test_token"


class TestAuthManager:
    """Tests for AuthManager."""

    def test_generate_api_key(self):
        """Test API key generation."""
        auth = AuthManager()

        key = auth.generate_api_key("test_user", roles=["sre"])

        # Key should be a valid string
        assert isinstance(key, str)
        assert len(key) > 20

    def test_validate_api_key(self):
        """Test API key validation."""
        auth = AuthManager()

        key = auth.generate_api_key("test_user", roles=["sre"])

        # Valid key
        result = auth.validate_api_key(key)
        assert result is not None
        assert result["user"] == "test_user"
        assert "sre" in result["roles"]

        # Invalid key
        result = auth.validate_api_key("invalid_key")
        assert result is None

    def test_revoke_api_key(self):
        """Test API key revocation."""
        auth = AuthManager()

        key = auth.generate_api_key("test_user")

        # Key should be valid
        assert auth.validate_api_key(key) is not None

        # Revoke
        result = auth.revoke_api_key(key)
        assert result

        # Key should now be invalid
        assert auth.validate_api_key(key) is None

    def test_create_token(self):
        """Test session token creation."""
        auth = AuthManager()

        token = auth.create_token(
            user="test_user",
            roles=["operator"],
            expires_in=timedelta(hours=1),
        )

        assert token.user == "test_user"
        assert "operator" in token.roles
        assert token.expires_at is not None

    def test_validate_token(self):
        """Test session token validation."""
        auth = AuthManager()

        token = auth.create_token(
            user="test_user",
            roles=["operator"],
            expires_in=timedelta(hours=1),
        )

        # Valid token
        result = auth.validate_token(token.token)
        assert result is not None
        assert result.user == "test_user"

        # Invalid token
        result = auth.validate_token("invalid_token")
        assert result is None

    def test_get_current_user_from_api_key(self):
        """Test getting current user from API key."""
        auth = AuthManager()

        key = auth.generate_api_key("api_user", roles=["viewer"])

        user = auth.get_current_user(api_key=key)
        assert user is not None
        assert user["user"] == "api_user"

    def test_get_current_user_from_token(self):
        """Test getting current user from token."""
        auth = AuthManager()

        token = auth.create_token("token_user", roles=["sre"])

        user = auth.get_current_user(token=token.token)
        assert user is not None
        assert user["user"] == "token_user"

    def test_get_current_user_from_env(self):
        """Test getting current user from environment variable."""
        auth = AuthManager()

        key = auth.generate_api_key("env_user", roles=["admin"])

        # Set environment variable
        old_env = os.environ.get("OPENSRE_API_KEY")
        try:
            os.environ["OPENSRE_API_KEY"] = key
            user = auth.get_current_user()
            assert user is not None
            assert user["user"] == "env_user"
        finally:
            if old_env:
                os.environ["OPENSRE_API_KEY"] = old_env
            else:
                os.environ.pop("OPENSRE_API_KEY", None)

    def test_keys_persistence(self):
        """Test API keys are persisted to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            keys_file = Path(tmpdir) / "keys.json"

            # Create auth manager and generate key
            auth1 = AuthManager(keys_file=str(keys_file))
            key = auth1.generate_api_key("persistent_user")

            # Create new auth manager that loads from same file
            auth2 = AuthManager(keys_file=str(keys_file))

            # Key should still be valid
            result = auth2.validate_api_key(key)
            assert result is not None
            assert result["user"] == "persistent_user"


class TestRequireAuth:
    """Tests for require_auth decorator."""

    def test_require_auth_sync(self):
        """Test require_auth on sync function."""
        import opensre_core.security.auth as auth_module

        # Create a fresh auth manager and set it as global
        auth = AuthManager()
        key = auth.generate_api_key("test_user", roles=["viewer"])
        auth_module._auth_manager = auth

        @require_auth
        def protected_function(_current_user=None):
            return _current_user

        # Set environment variable
        old_env = os.environ.get("OPENSRE_API_KEY")
        try:
            os.environ["OPENSRE_API_KEY"] = key
            result = protected_function()
            assert result is not None
            assert result["user"] == "test_user"
        finally:
            if old_env:
                os.environ["OPENSRE_API_KEY"] = old_env
            else:
                os.environ.pop("OPENSRE_API_KEY", None)
            auth_module._auth_manager = None

    @pytest.mark.asyncio
    async def test_require_auth_async(self):
        """Test require_auth on async function."""
        import opensre_core.security.auth as auth_module

        # Create a fresh auth manager and set it as global
        auth = AuthManager()
        key = auth.generate_api_key("async_user", roles=["sre"])
        auth_module._auth_manager = auth

        @require_auth
        async def protected_async_function(_current_user=None):
            return _current_user

        # Set environment variable
        old_env = os.environ.get("OPENSRE_API_KEY")
        try:
            os.environ["OPENSRE_API_KEY"] = key
            result = await protected_async_function()
            assert result is not None
            assert result["user"] == "async_user"
        finally:
            if old_env:
                os.environ["OPENSRE_API_KEY"] = old_env
            else:
                os.environ.pop("OPENSRE_API_KEY", None)
            auth_module._auth_manager = None

    def test_require_auth_no_key(self):
        """Test require_auth fails without key."""
        # Remove any existing key
        old_env = os.environ.get("OPENSRE_API_KEY")
        os.environ.pop("OPENSRE_API_KEY", None)

        @require_auth
        def protected_function(_current_user=None):
            return _current_user

        try:
            with pytest.raises(PermissionError) as exc_info:
                protected_function()
            assert "Authentication required" in str(exc_info.value)
        finally:
            if old_env:
                os.environ["OPENSRE_API_KEY"] = old_env
