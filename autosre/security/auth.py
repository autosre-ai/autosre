"""
Authentication Module - API Key and Token Management
"""

import hashlib
import json
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Callable, Optional


@dataclass
class AuthToken:
    """Represents an authentication token."""
    token: str
    user: str
    roles: list[str]
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None

    def is_expired(self) -> bool:
        """Check if token has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "token_hash": hashlib.sha256(self.token.encode()).hexdigest()[:16],
            "user": self.user,
            "roles": self.roles,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


class AuthManager:
    """
    Manages authentication for OpenSRE.

    Supports:
    - API key authentication
    - Token-based sessions
    - Environment variable configuration
    """

    def __init__(self, keys_file: Optional[str] = None):
        self.tokens: dict[str, AuthToken] = {}
        self.api_keys: dict[str, dict] = {}  # hash -> {user, roles}
        self.keys_file = Path(keys_file) if keys_file else None

        # Load existing keys
        if self.keys_file and self.keys_file.exists():
            self._load_keys()

    def _load_keys(self) -> None:
        """Load API keys from file."""
        if not self.keys_file:
            return
        try:
            with open(self.keys_file) as f:
                data = json.load(f)
                self.api_keys = data.get("api_keys", {})
        except Exception:
            pass

    def _save_keys(self) -> None:
        """Save API keys to file."""
        if self.keys_file:
            self.keys_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.keys_file, "w") as f:
                json.dump({"api_keys": self.api_keys}, f, indent=2)

    def generate_api_key(self, user: str, roles: Optional[list[str]] = None) -> str:
        """
        Generate a new API key for a user.

        Args:
            user: Username
            roles: List of roles (default: ["viewer"])

        Returns:
            The API key (only shown once!)
        """
        if roles is None:
            roles = ["viewer"]

        key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(key.encode()).hexdigest()

        self.api_keys[key_hash] = {
            "user": user,
            "roles": roles,
            "created_at": datetime.now().isoformat(),
        }

        self._save_keys()
        return key

    def revoke_api_key(self, key: str) -> bool:
        """Revoke an API key."""
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        if key_hash in self.api_keys:
            del self.api_keys[key_hash]
            self._save_keys()
            return True
        return False

    def validate_api_key(self, key: str) -> Optional[dict]:
        """
        Validate an API key.

        Args:
            key: The API key

        Returns:
            User info dict if valid, None otherwise
        """
        if not key:
            return None

        key_hash = hashlib.sha256(key.encode()).hexdigest()
        return self.api_keys.get(key_hash)

    def create_token(
        self,
        user: str,
        roles: list[str],
        expires_in: timedelta = timedelta(hours=24),
    ) -> AuthToken:
        """Create a session token."""
        token_str = secrets.token_urlsafe(32)
        token = AuthToken(
            token=token_str,
            user=user,
            roles=roles,
            created_at=datetime.now(),
            expires_at=datetime.now() + expires_in,
        )

        token_hash = hashlib.sha256(token_str.encode()).hexdigest()
        self.tokens[token_hash] = token

        return token

    def validate_token(self, token_str: str) -> Optional[AuthToken]:
        """Validate a session token."""
        if not token_str:
            return None

        token_hash = hashlib.sha256(token_str.encode()).hexdigest()
        token = self.tokens.get(token_hash)

        if token and not token.is_expired():
            return token

        # Clean up expired token
        if token and token.is_expired():
            del self.tokens[token_hash]

        return None

    def get_current_user(self, api_key: Optional[str] = None, token: Optional[str] = None) -> Optional[dict]:
        """
        Get current user from API key or token.

        Checks in order:
        1. Provided API key
        2. Provided token
        3. OPENSRE_API_KEY environment variable
        """
        # Check provided API key
        if api_key:
            user_info = self.validate_api_key(api_key)
            if user_info:
                return user_info

        # Check provided token
        if token:
            auth_token = self.validate_token(token)
            if auth_token:
                return {"user": auth_token.user, "roles": auth_token.roles}

        # Check environment variable
        env_key = os.environ.get("OPENSRE_API_KEY")
        if env_key:
            user_info = self.validate_api_key(env_key)
            if user_info:
                return user_info

        return None


# Global auth manager instance
_auth_manager: Optional[AuthManager] = None


def get_auth_manager() -> AuthManager:
    """Get or create the global auth manager."""
    global _auth_manager
    if _auth_manager is None:
        keys_file = os.environ.get("OPENSRE_KEYS_FILE", "config/api_keys.json")
        _auth_manager = AuthManager(keys_file)
    return _auth_manager


def require_auth(func: Optional[Callable] = None, *, roles: Optional[list[str]] = None):
    """
    Decorator to require authentication on a function.

    Usage:
        @require_auth
        async def my_endpoint():
            ...

        @require_auth(roles=["sre", "admin"])
        async def admin_endpoint():
            ...
    """
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        async def async_wrapper(*args, **kwargs):
            auth = get_auth_manager()

            # Try to get API key from kwargs or environment
            api_key = kwargs.pop("api_key", None) or os.environ.get("OPENSRE_API_KEY")
            token = kwargs.pop("auth_token", None)

            user_info = auth.get_current_user(api_key=api_key, token=token)

            if not user_info:
                raise PermissionError("Authentication required")

            # Check roles if specified
            if roles:
                user_roles = user_info.get("roles", [])
                if not any(r in user_roles for r in roles) and "admin" not in user_roles:
                    raise PermissionError(f"Required roles: {roles}")

            # Add user info to kwargs
            kwargs["_current_user"] = user_info

            return await fn(*args, **kwargs)

        @wraps(fn)
        def sync_wrapper(*args, **kwargs):
            auth = get_auth_manager()

            api_key = kwargs.pop("api_key", None) or os.environ.get("OPENSRE_API_KEY")
            token = kwargs.pop("auth_token", None)

            user_info = auth.get_current_user(api_key=api_key, token=token)

            if not user_info:
                raise PermissionError("Authentication required")

            if roles:
                user_roles = user_info.get("roles", [])
                if not any(r in user_roles for r in roles) and "admin" not in user_roles:
                    raise PermissionError(f"Required roles: {roles}")

            kwargs["_current_user"] = user_info

            return fn(*args, **kwargs)

        import inspect
        if inspect.iscoroutinefunction(fn):
            return async_wrapper
        return sync_wrapper

    if func is not None:
        return decorator(func)
    return decorator


def validate_token(token: str) -> Optional[dict]:
    """Validate a token and return user info."""
    auth = get_auth_manager()
    auth_token = auth.validate_token(token)
    if auth_token:
        return {"user": auth_token.user, "roles": auth_token.roles}
    return None
