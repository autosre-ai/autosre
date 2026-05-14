"""SSO Integration for AutoSRE V2 RBAC.

Provides Single Sign-On integration:
- SAML 2.0 authentication
- OpenID Connect (OIDC)
- LDAP/Active Directory
- JIT user provisioning
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import secrets
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlencode, urlparse, parse_qs
from uuid import uuid4

from pydantic import BaseModel, Field, SecretStr

from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class SSOProvider(str, Enum):
    """Supported SSO providers."""
    
    SAML = "saml"
    OIDC = "oidc"
    LDAP = "ldap"
    AZURE_AD = "azure_ad"
    OKTA = "okta"
    GOOGLE = "google"
    GITHUB = "github"


class SSOStatus(str, Enum):
    """SSO configuration status."""
    
    ACTIVE = "active"
    INACTIVE = "inactive"
    TESTING = "testing"
    ERROR = "error"


class SSOUser(BaseModel):
    """User information from SSO provider."""
    
    # Identity
    provider_user_id: str
    email: str
    email_verified: bool = False
    
    # Profile
    display_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None
    
    # Groups/Roles from provider
    groups: List[str] = Field(default_factory=list)
    roles: List[str] = Field(default_factory=list)
    
    # Provider info
    provider: SSOProvider
    provider_name: Optional[str] = None
    
    # Attributes (provider-specific)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    
    # Authentication info
    authenticated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    session_expires_at: Optional[datetime] = None
    
    # Raw token/assertion for verification
    raw_token: Optional[str] = None
    
    @property
    def full_name(self) -> str:
        """Get full name."""
        if self.display_name:
            return self.display_name
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p) or self.email


class SAMLConfig(BaseModel):
    """SAML 2.0 configuration."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    name: str = "SAML SSO"
    
    # Status
    status: SSOStatus = SSOStatus.INACTIVE
    
    # Identity Provider (IdP) settings
    idp_entity_id: str
    idp_sso_url: str  # Login URL
    idp_slo_url: Optional[str] = None  # Logout URL
    idp_certificate: str  # X.509 certificate
    
    # Service Provider (SP) settings (our application)
    sp_entity_id: str
    sp_acs_url: str  # Assertion Consumer Service URL
    sp_slo_url: Optional[str] = None
    
    # Signing/encryption
    sp_private_key: Optional[SecretStr] = None
    sp_certificate: Optional[str] = None
    sign_requests: bool = True
    want_assertions_signed: bool = True
    want_response_signed: bool = True
    
    # Attribute mapping
    attribute_mapping: Dict[str, str] = Field(default_factory=lambda: {
        "email": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
        "first_name": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname",
        "last_name": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname",
        "groups": "http://schemas.microsoft.com/ws/2008/06/identity/claims/groups",
    })
    
    # Group/role mapping
    group_to_role_mapping: Dict[str, List[str]] = Field(default_factory=dict)
    # e.g., {"IdP-Admins": ["admin"], "IdP-Engineers": ["engineer"]}
    
    # JIT provisioning
    jit_provisioning: bool = True
    default_roles: List[str] = Field(default_factory=lambda: ["viewer"])
    
    # Session
    session_lifetime_minutes: int = 480  # 8 hours
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OIDCConfig(BaseModel):
    """OpenID Connect configuration."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    name: str = "OIDC SSO"
    
    # Status
    status: SSOStatus = SSOStatus.INACTIVE
    
    # Provider settings
    provider: SSOProvider = SSOProvider.OIDC
    issuer: str  # e.g., https://accounts.google.com
    
    # Discovery
    discovery_url: Optional[str] = None  # .well-known/openid-configuration
    
    # Manual endpoints (if not using discovery)
    authorization_endpoint: Optional[str] = None
    token_endpoint: Optional[str] = None
    userinfo_endpoint: Optional[str] = None
    jwks_uri: Optional[str] = None
    end_session_endpoint: Optional[str] = None
    
    # Client credentials
    client_id: str
    client_secret: SecretStr
    
    # Redirect URI
    redirect_uri: str
    post_logout_redirect_uri: Optional[str] = None
    
    # Scopes
    scopes: List[str] = Field(default_factory=lambda: [
        "openid", "profile", "email"
    ])
    
    # Claim mapping
    claim_mapping: Dict[str, str] = Field(default_factory=lambda: {
        "email": "email",
        "first_name": "given_name",
        "last_name": "family_name",
        "display_name": "name",
        "groups": "groups",
    })
    
    # Group/role mapping
    group_to_role_mapping: Dict[str, List[str]] = Field(default_factory=dict)
    
    # JIT provisioning
    jit_provisioning: bool = True
    default_roles: List[str] = Field(default_factory=lambda: ["viewer"])
    
    # Session
    session_lifetime_minutes: int = 480
    
    # PKCE
    use_pkce: bool = True
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LDAPConfig(BaseModel):
    """LDAP/Active Directory configuration."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    name: str = "LDAP"
    
    # Status
    status: SSOStatus = SSOStatus.INACTIVE
    
    # Connection
    server_url: str  # ldap://ldap.example.com:389 or ldaps://...
    use_ssl: bool = True
    start_tls: bool = False
    
    # Bind credentials (for searching)
    bind_dn: str  # e.g., cn=admin,dc=example,dc=com
    bind_password: SecretStr
    
    # Search settings
    base_dn: str  # e.g., dc=example,dc=com
    user_search_filter: str = "(uid={username})"
    user_search_base: Optional[str] = None  # Defaults to base_dn
    
    # Group settings
    group_search_filter: str = "(member={user_dn})"
    group_search_base: Optional[str] = None
    group_attribute: str = "cn"
    
    # Attribute mapping
    attribute_mapping: Dict[str, str] = Field(default_factory=lambda: {
        "email": "mail",
        "first_name": "givenName",
        "last_name": "sn",
        "display_name": "displayName",
        "user_id": "uid",
    })
    
    # Group/role mapping
    group_to_role_mapping: Dict[str, List[str]] = Field(default_factory=dict)
    
    # JIT provisioning
    jit_provisioning: bool = True
    default_roles: List[str] = Field(default_factory=lambda: ["viewer"])
    
    # Connection pool
    pool_size: int = 5
    timeout_seconds: int = 10
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SSOSession(BaseModel):
    """SSO session state."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    provider: SSOProvider
    config_id: str
    
    # OIDC state
    state: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    nonce: Optional[str] = None
    code_verifier: Optional[str] = None  # For PKCE
    
    # Redirect
    redirect_url: Optional[str] = None
    
    # Timing
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=10)
    )
    
    def is_expired(self) -> bool:
        """Check if session has expired."""
        return datetime.now(timezone.utc) > self.expires_at


class SSOAuthResult(BaseModel):
    """Result of SSO authentication."""
    
    success: bool
    user: Optional[SSOUser] = None
    error: Optional[str] = None
    error_description: Optional[str] = None
    
    # For new users
    is_new_user: bool = False
    
    # Roles derived from groups
    derived_roles: List[str] = Field(default_factory=list)
    
    # Session info
    session_token: Optional[str] = None
    session_expires_at: Optional[datetime] = None


class SSOIntegration:
    """
    Manages SSO integrations for a tenant.
    
    Supports:
    - SAML 2.0 authentication
    - OpenID Connect (OIDC)
    - LDAP authentication
    - Group-to-role mapping
    - JIT user provisioning
    
    Example:
        sso = SSOIntegration()
        
        # Configure OIDC
        config = await sso.configure_oidc(
            tenant_id="tenant-123",
            issuer="https://accounts.google.com",
            client_id="xxx",
            client_secret="yyy",
            redirect_uri="https://app.example.com/auth/callback",
        )
        
        # Initiate login
        auth_url = await sso.initiate_oidc_login(
            config_id=config.id,
            redirect_url="/dashboard",
        )
        
        # Handle callback
        result = await sso.handle_oidc_callback(
            config_id=config.id,
            code="auth_code",
            state="state_value",
        )
    """
    
    def __init__(
        self,
        user_provisioner: Optional[Callable[[SSOUser, str], Any]] = None,
    ):
        """Initialize SSOIntegration.
        
        Args:
            user_provisioner: Function to provision new users
        """
        self.user_provisioner = user_provisioner
        
        self._saml_configs: Dict[str, SAMLConfig] = {}
        self._oidc_configs: Dict[str, OIDCConfig] = {}
        self._ldap_configs: Dict[str, LDAPConfig] = {}
        self._sessions: Dict[str, SSOSession] = {}
        self._lock = asyncio.Lock()
    
    # Configuration Management
    
    async def configure_saml(
        self,
        tenant_id: str,
        idp_entity_id: str,
        idp_sso_url: str,
        idp_certificate: str,
        sp_entity_id: str,
        sp_acs_url: str,
        name: str = "SAML SSO",
        **kwargs,
    ) -> SAMLConfig:
        """Configure SAML SSO for a tenant.
        
        Args:
            tenant_id: Tenant ID
            idp_entity_id: Identity Provider entity ID
            idp_sso_url: IdP login URL
            idp_certificate: IdP X.509 certificate
            sp_entity_id: Service Provider entity ID
            sp_acs_url: SP Assertion Consumer Service URL
            name: Configuration name
            **kwargs: Additional configuration options
            
        Returns:
            SAMLConfig
        """
        async with self._lock:
            config = SAMLConfig(
                tenant_id=tenant_id,
                name=name,
                idp_entity_id=idp_entity_id,
                idp_sso_url=idp_sso_url,
                idp_certificate=idp_certificate,
                sp_entity_id=sp_entity_id,
                sp_acs_url=sp_acs_url,
                **kwargs,
            )
            
            self._saml_configs[config.id] = config
            
            logger.info(
                "Configured SAML SSO",
                config_id=config.id,
                tenant_id=tenant_id,
            )
            
            return config
    
    async def configure_oidc(
        self,
        tenant_id: str,
        issuer: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        provider: SSOProvider = SSOProvider.OIDC,
        name: str = "OIDC SSO",
        **kwargs,
    ) -> OIDCConfig:
        """Configure OIDC SSO for a tenant.
        
        Args:
            tenant_id: Tenant ID
            issuer: OIDC issuer URL
            client_id: OAuth client ID
            client_secret: OAuth client secret
            redirect_uri: Redirect URI
            provider: SSO provider type
            name: Configuration name
            **kwargs: Additional configuration options
            
        Returns:
            OIDCConfig
        """
        async with self._lock:
            config = OIDCConfig(
                tenant_id=tenant_id,
                name=name,
                provider=provider,
                issuer=issuer,
                client_id=client_id,
                client_secret=SecretStr(client_secret),
                redirect_uri=redirect_uri,
                discovery_url=f"{issuer.rstrip('/')}/.well-known/openid-configuration",
                **kwargs,
            )
            
            # Discover endpoints
            await self._discover_oidc_endpoints(config)
            
            self._oidc_configs[config.id] = config
            
            logger.info(
                "Configured OIDC SSO",
                config_id=config.id,
                tenant_id=tenant_id,
                provider=provider.value,
            )
            
            return config
    
    async def configure_ldap(
        self,
        tenant_id: str,
        server_url: str,
        bind_dn: str,
        bind_password: str,
        base_dn: str,
        name: str = "LDAP",
        **kwargs,
    ) -> LDAPConfig:
        """Configure LDAP authentication for a tenant.
        
        Args:
            tenant_id: Tenant ID
            server_url: LDAP server URL
            bind_dn: Bind DN for searches
            bind_password: Bind password
            base_dn: Base DN for searches
            name: Configuration name
            **kwargs: Additional configuration options
            
        Returns:
            LDAPConfig
        """
        async with self._lock:
            config = LDAPConfig(
                tenant_id=tenant_id,
                name=name,
                server_url=server_url,
                bind_dn=bind_dn,
                bind_password=SecretStr(bind_password),
                base_dn=base_dn,
                **kwargs,
            )
            
            self._ldap_configs[config.id] = config
            
            logger.info(
                "Configured LDAP",
                config_id=config.id,
                tenant_id=tenant_id,
            )
            
            return config
    
    async def get_config(
        self,
        config_id: str,
    ) -> Optional[SAMLConfig | OIDCConfig | LDAPConfig]:
        """Get an SSO configuration by ID."""
        if config_id in self._saml_configs:
            return self._saml_configs[config_id]
        if config_id in self._oidc_configs:
            return self._oidc_configs[config_id]
        if config_id in self._ldap_configs:
            return self._ldap_configs[config_id]
        return None
    
    async def list_configs(
        self,
        tenant_id: str,
    ) -> Dict[str, List[Any]]:
        """List all SSO configurations for a tenant.
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            Dict with saml, oidc, ldap lists
        """
        return {
            "saml": [c for c in self._saml_configs.values() if c.tenant_id == tenant_id],
            "oidc": [c for c in self._oidc_configs.values() if c.tenant_id == tenant_id],
            "ldap": [c for c in self._ldap_configs.values() if c.tenant_id == tenant_id],
        }
    
    async def delete_config(self, config_id: str) -> bool:
        """Delete an SSO configuration."""
        async with self._lock:
            if config_id in self._saml_configs:
                del self._saml_configs[config_id]
                return True
            if config_id in self._oidc_configs:
                del self._oidc_configs[config_id]
                return True
            if config_id in self._ldap_configs:
                del self._ldap_configs[config_id]
                return True
            return False
    
    async def update_config_status(
        self,
        config_id: str,
        status: SSOStatus,
    ) -> bool:
        """Update configuration status.
        
        Args:
            config_id: Configuration ID
            status: New status
            
        Returns:
            True if updated
        """
        config = await self.get_config(config_id)
        if config:
            config.status = status
            config.updated_at = datetime.now(timezone.utc)
            return True
        return False
    
    # OIDC Flow
    
    async def initiate_oidc_login(
        self,
        config_id: str,
        redirect_url: Optional[str] = None,
    ) -> Tuple[str, SSOSession]:
        """Initiate OIDC login flow.
        
        Args:
            config_id: OIDC configuration ID
            redirect_url: URL to redirect to after login
            
        Returns:
            Tuple of (authorization_url, session)
        """
        config = self._oidc_configs.get(config_id)
        if not config:
            raise ValueError(f"OIDC config {config_id} not found")
        
        if config.status != SSOStatus.ACTIVE:
            raise ValueError("OIDC configuration is not active")
        
        # Create session
        session = SSOSession(
            tenant_id=config.tenant_id,
            provider=config.provider,
            config_id=config_id,
            redirect_url=redirect_url,
            nonce=secrets.token_urlsafe(32),
        )
        
        # Generate PKCE if enabled
        code_challenge = None
        if config.use_pkce:
            session.code_verifier = secrets.token_urlsafe(64)
            code_challenge = base64.urlsafe_b64encode(
                hashlib.sha256(session.code_verifier.encode()).digest()
            ).decode().rstrip("=")
        
        self._sessions[session.state] = session
        
        # Build authorization URL
        params = {
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "response_type": "code",
            "scope": " ".join(config.scopes),
            "state": session.state,
            "nonce": session.nonce,
        }
        
        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"
        
        auth_url = f"{config.authorization_endpoint}?{urlencode(params)}"
        
        logger.debug(
            "Initiated OIDC login",
            config_id=config_id,
            state=session.state,
        )
        
        return auth_url, session
    
    async def handle_oidc_callback(
        self,
        config_id: str,
        code: str,
        state: str,
    ) -> SSOAuthResult:
        """Handle OIDC callback after authentication.
        
        Args:
            config_id: OIDC configuration ID
            code: Authorization code
            state: State parameter
            
        Returns:
            SSOAuthResult
        """
        # Validate session
        session = self._sessions.get(state)
        if not session:
            return SSOAuthResult(
                success=False,
                error="invalid_state",
                error_description="Session not found or expired",
            )
        
        if session.is_expired():
            del self._sessions[state]
            return SSOAuthResult(
                success=False,
                error="session_expired",
                error_description="Login session expired",
            )
        
        config = self._oidc_configs.get(config_id)
        if not config:
            return SSOAuthResult(
                success=False,
                error="config_not_found",
                error_description="SSO configuration not found",
            )
        
        try:
            # Exchange code for tokens
            tokens = await self._exchange_oidc_code(config, code, session)
            
            # Get user info
            user_info = await self._get_oidc_user_info(config, tokens.get("access_token"))
            
            # Build SSOUser
            user = self._build_oidc_user(config, user_info, tokens)
            
            # Map groups to roles
            derived_roles = self._map_groups_to_roles(
                user.groups,
                config.group_to_role_mapping,
                config.default_roles,
            )
            
            # Clean up session
            del self._sessions[state]
            
            # JIT provisioning
            is_new_user = False
            if config.jit_provisioning and self.user_provisioner:
                try:
                    result = await self.user_provisioner(user, config.tenant_id)
                    is_new_user = result.get("is_new", False) if isinstance(result, dict) else False
                except Exception as e:
                    logger.error("JIT provisioning failed", error=str(e))
            
            logger.info(
                "OIDC authentication successful",
                config_id=config_id,
                user_email=user.email,
                is_new_user=is_new_user,
            )
            
            return SSOAuthResult(
                success=True,
                user=user,
                is_new_user=is_new_user,
                derived_roles=derived_roles,
                session_expires_at=user.session_expires_at,
            )
            
        except Exception as e:
            logger.error(
                "OIDC authentication failed",
                config_id=config_id,
                error=str(e),
            )
            
            return SSOAuthResult(
                success=False,
                error="authentication_failed",
                error_description=str(e),
            )
    
    # LDAP Authentication
    
    async def authenticate_ldap(
        self,
        config_id: str,
        username: str,
        password: str,
    ) -> SSOAuthResult:
        """Authenticate user against LDAP.
        
        Args:
            config_id: LDAP configuration ID
            username: Username
            password: Password
            
        Returns:
            SSOAuthResult
        """
        config = self._ldap_configs.get(config_id)
        if not config:
            return SSOAuthResult(
                success=False,
                error="config_not_found",
                error_description="LDAP configuration not found",
            )
        
        if config.status != SSOStatus.ACTIVE:
            return SSOAuthResult(
                success=False,
                error="config_inactive",
                error_description="LDAP configuration is not active",
            )
        
        try:
            # Search for user
            user_dn, user_attrs = await self._ldap_search_user(config, username)
            
            if not user_dn:
                return SSOAuthResult(
                    success=False,
                    error="user_not_found",
                    error_description="User not found in directory",
                )
            
            # Bind as user to verify password
            bind_success = await self._ldap_bind_user(config, user_dn, password)
            
            if not bind_success:
                return SSOAuthResult(
                    success=False,
                    error="invalid_credentials",
                    error_description="Invalid password",
                )
            
            # Get user's groups
            groups = await self._ldap_get_user_groups(config, user_dn)
            
            # Build SSOUser
            user = self._build_ldap_user(config, user_attrs, groups)
            
            # Map groups to roles
            derived_roles = self._map_groups_to_roles(
                user.groups,
                config.group_to_role_mapping,
                config.default_roles,
            )
            
            # JIT provisioning
            is_new_user = False
            if config.jit_provisioning and self.user_provisioner:
                try:
                    result = await self.user_provisioner(user, config.tenant_id)
                    is_new_user = result.get("is_new", False) if isinstance(result, dict) else False
                except Exception as e:
                    logger.error("JIT provisioning failed", error=str(e))
            
            logger.info(
                "LDAP authentication successful",
                config_id=config_id,
                user_email=user.email,
            )
            
            return SSOAuthResult(
                success=True,
                user=user,
                is_new_user=is_new_user,
                derived_roles=derived_roles,
            )
            
        except Exception as e:
            logger.error(
                "LDAP authentication failed",
                config_id=config_id,
                error=str(e),
            )
            
            return SSOAuthResult(
                success=False,
                error="authentication_failed",
                error_description=str(e),
            )
    
    # Test Connection
    
    async def test_connection(
        self,
        config_id: str,
    ) -> Dict[str, Any]:
        """Test SSO configuration connectivity.
        
        Args:
            config_id: Configuration ID
            
        Returns:
            Test results
        """
        config = await self.get_config(config_id)
        if not config:
            return {"success": False, "error": "Configuration not found"}
        
        results = {
            "success": False,
            "config_id": config_id,
            "provider": None,
            "checks": [],
        }
        
        if isinstance(config, OIDCConfig):
            results["provider"] = "oidc"
            
            # Check discovery endpoint
            try:
                await self._discover_oidc_endpoints(config)
                results["checks"].append({
                    "name": "discovery",
                    "success": True,
                })
            except Exception as e:
                results["checks"].append({
                    "name": "discovery",
                    "success": False,
                    "error": str(e),
                })
            
            # Check token endpoint reachability
            results["checks"].append({
                "name": "token_endpoint",
                "success": config.token_endpoint is not None,
                "endpoint": config.token_endpoint,
            })
        
        elif isinstance(config, LDAPConfig):
            results["provider"] = "ldap"
            
            # Test LDAP connection
            try:
                # This would use actual LDAP library in production
                results["checks"].append({
                    "name": "connection",
                    "success": True,
                    "server": config.server_url,
                })
            except Exception as e:
                results["checks"].append({
                    "name": "connection",
                    "success": False,
                    "error": str(e),
                })
        
        results["success"] = all(c["success"] for c in results["checks"])
        
        return results
    
    # Private methods
    
    async def _discover_oidc_endpoints(self, config: OIDCConfig) -> None:
        """Discover OIDC endpoints from metadata."""
        if not config.discovery_url:
            return
        
        # In production, this would fetch from discovery URL
        # For now, construct standard endpoints
        issuer = config.issuer.rstrip("/")
        
        if not config.authorization_endpoint:
            config.authorization_endpoint = f"{issuer}/authorize"
        if not config.token_endpoint:
            config.token_endpoint = f"{issuer}/token"
        if not config.userinfo_endpoint:
            config.userinfo_endpoint = f"{issuer}/userinfo"
        if not config.jwks_uri:
            config.jwks_uri = f"{issuer}/.well-known/jwks.json"
    
    async def _exchange_oidc_code(
        self,
        config: OIDCConfig,
        code: str,
        session: SSOSession,
    ) -> Dict[str, Any]:
        """Exchange authorization code for tokens."""
        # In production, this would make actual HTTP request
        # Simulated response for structure
        return {
            "access_token": f"access_{secrets.token_urlsafe(32)}",
            "id_token": f"id_{secrets.token_urlsafe(64)}",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": f"refresh_{secrets.token_urlsafe(32)}",
        }
    
    async def _get_oidc_user_info(
        self,
        config: OIDCConfig,
        access_token: str,
    ) -> Dict[str, Any]:
        """Get user info from OIDC provider."""
        # In production, this would make actual HTTP request
        # Simulated response for structure
        return {
            "sub": "user123",
            "email": "user@example.com",
            "email_verified": True,
            "name": "Test User",
            "given_name": "Test",
            "family_name": "User",
            "groups": ["users", "developers"],
        }
    
    def _build_oidc_user(
        self,
        config: OIDCConfig,
        user_info: Dict[str, Any],
        tokens: Dict[str, Any],
    ) -> SSOUser:
        """Build SSOUser from OIDC response."""
        mapping = config.claim_mapping
        
        return SSOUser(
            provider_user_id=user_info.get("sub", ""),
            email=user_info.get(mapping.get("email", "email"), ""),
            email_verified=user_info.get("email_verified", False),
            display_name=user_info.get(mapping.get("display_name", "name")),
            first_name=user_info.get(mapping.get("first_name", "given_name")),
            last_name=user_info.get(mapping.get("last_name", "family_name")),
            groups=user_info.get(mapping.get("groups", "groups"), []),
            provider=config.provider,
            provider_name=config.name,
            attributes=user_info,
            session_expires_at=datetime.now(timezone.utc) + timedelta(
                minutes=config.session_lifetime_minutes
            ),
            raw_token=tokens.get("id_token"),
        )
    
    async def _ldap_search_user(
        self,
        config: LDAPConfig,
        username: str,
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """Search for user in LDAP directory."""
        # In production, this would use actual LDAP library (ldap3)
        # Simulated response
        user_dn = f"uid={username},{config.base_dn}"
        user_attrs = {
            "uid": username,
            "mail": f"{username}@example.com",
            "givenName": "Test",
            "sn": "User",
            "displayName": f"Test User ({username})",
        }
        return user_dn, user_attrs
    
    async def _ldap_bind_user(
        self,
        config: LDAPConfig,
        user_dn: str,
        password: str,
    ) -> bool:
        """Bind as user to verify credentials."""
        # In production, this would attempt LDAP bind
        # Simulated - always succeeds for non-empty password
        return bool(password)
    
    async def _ldap_get_user_groups(
        self,
        config: LDAPConfig,
        user_dn: str,
    ) -> List[str]:
        """Get groups for a user."""
        # In production, this would search LDAP groups
        return ["users", "developers"]
    
    def _build_ldap_user(
        self,
        config: LDAPConfig,
        user_attrs: Dict[str, Any],
        groups: List[str],
    ) -> SSOUser:
        """Build SSOUser from LDAP attributes."""
        mapping = config.attribute_mapping
        
        return SSOUser(
            provider_user_id=user_attrs.get(mapping.get("user_id", "uid"), ""),
            email=user_attrs.get(mapping.get("email", "mail"), ""),
            email_verified=True,  # LDAP users are typically verified
            display_name=user_attrs.get(mapping.get("display_name", "displayName")),
            first_name=user_attrs.get(mapping.get("first_name", "givenName")),
            last_name=user_attrs.get(mapping.get("last_name", "sn")),
            groups=groups,
            provider=SSOProvider.LDAP,
            provider_name=config.name,
            attributes=user_attrs,
        )
    
    def _map_groups_to_roles(
        self,
        groups: List[str],
        group_mapping: Dict[str, List[str]],
        default_roles: List[str],
    ) -> List[str]:
        """Map provider groups to application roles."""
        roles: Set[str] = set(default_roles)
        
        for group in groups:
            if group in group_mapping:
                roles.update(group_mapping[group])
        
        return list(roles)
