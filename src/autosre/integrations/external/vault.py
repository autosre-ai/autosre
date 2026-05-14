"""Vault Integration for AutoSRE V2.

Provides HashiCorp Vault integration:
- Secret management
- Token authentication
- Multiple auth methods
- Secret engines
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field

from autosre.integrations.base import (
    AuthenticatedIntegration,
    ConnectionConfig,
    HealthCheckResult,
    HealthStatus,
    IntegrationError,
)
from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class VaultAuthMethod(str, Enum):
    """Vault authentication methods."""
    
    TOKEN = "token"
    USERPASS = "userpass"
    APPROLE = "approle"
    KUBERNETES = "kubernetes"
    LDAP = "ldap"
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"


@dataclass
class VaultConfig:
    """Configuration for Vault integration."""
    
    # Connection
    address: str  # e.g., https://vault.company.com:8200
    
    # Authentication
    auth_method: VaultAuthMethod = VaultAuthMethod.TOKEN
    token: Optional[str] = None
    
    # UserPass auth
    username: Optional[str] = None
    password: Optional[str] = None
    
    # AppRole auth
    role_id: Optional[str] = None
    secret_id: Optional[str] = None
    
    # Kubernetes auth
    jwt: Optional[str] = None
    role: Optional[str] = None
    
    # Namespace (for Vault Enterprise)
    namespace: Optional[str] = None
    
    # TLS
    tls_skip_verify: bool = False
    ca_cert: Optional[str] = None
    
    # Timeouts
    timeout_seconds: float = 30.0
    
    # Token renewal
    auto_renew: bool = True
    renewal_threshold_seconds: int = 300


class VaultToken(BaseModel):
    """Vault token information."""
    
    client_token: str
    accessor: str
    
    # Policies
    policies: List[str] = Field(default_factory=list)
    token_policies: List[str] = Field(default_factory=list)
    
    # Metadata
    metadata: Dict[str, str] = Field(default_factory=dict)
    
    # Timing
    lease_duration: int = 0  # seconds
    renewable: bool = False
    
    # Calculated expiry
    expires_at: Optional[datetime] = None
    
    def is_expired(self) -> bool:
        """Check if token is expired."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) >= self.expires_at
    
    def needs_renewal(self, threshold_seconds: int = 300) -> bool:
        """Check if token needs renewal."""
        if not self.renewable or not self.expires_at:
            return False
        
        renewal_time = self.expires_at - timedelta(seconds=threshold_seconds)
        return datetime.now(timezone.utc) >= renewal_time


class VaultSecret(BaseModel):
    """Vault secret data."""
    
    # Path
    path: str
    
    # Data
    data: Dict[str, Any] = Field(default_factory=dict)
    
    # Metadata (KV v2)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Version (KV v2)
    version: Optional[int] = None
    
    # Timing
    created_time: Optional[datetime] = None
    deletion_time: Optional[datetime] = None
    destroyed: bool = False
    
    # Lease
    lease_id: Optional[str] = None
    lease_duration: int = 0
    renewable: bool = False


class VaultMount(BaseModel):
    """Vault secret engine mount."""
    
    path: str
    type: str
    description: Optional[str] = None
    
    # Configuration
    config: Dict[str, Any] = Field(default_factory=dict)
    options: Dict[str, Any] = Field(default_factory=dict)
    
    # Status
    local: bool = False
    seal_wrap: bool = False


class VaultIntegration(AuthenticatedIntegration):
    """
    HashiCorp Vault integration for secrets management.
    
    Provides comprehensive Vault functionality:
    - Multiple authentication methods
    - Secret read/write operations
    - Token management and renewal
    - Multiple secret engines
    
    Example:
        config = VaultConfig(
            address="https://vault.company.com:8200",
            auth_method=VaultAuthMethod.APPROLE,
            role_id="xxx",
            secret_id="yyy",
        )
        
        async with VaultIntegration(config) as vault:
            # Read secret
            secret = await vault.read_secret("secret/data/myapp")
            password = secret.data["password"]
            
            # Write secret
            await vault.write_secret("secret/data/myapp", {
                "username": "admin",
                "password": "newpass",
            })
            
            # Generate dynamic credentials
            creds = await vault.read_secret("database/creds/readonly")
    """
    
    def __init__(self, config: VaultConfig):
        """Initialize Vault integration.
        
        Args:
            config: Vault configuration
        """
        self.vault_config = config
        
        headers = {}
        if config.namespace:
            headers["X-Vault-Namespace"] = config.namespace
        
        conn_config = ConnectionConfig(
            base_url=config.address,
            timeout=config.timeout_seconds,
            verify_ssl=not config.tls_skip_verify,
            headers=headers,
        )
        
        super().__init__(config=conn_config)
        
        self._token: Optional[VaultToken] = None
        self._renewal_task: Optional[asyncio.Task] = None
    
    @property
    def name(self) -> str:
        return "vault"
    
    async def __aenter__(self):
        await self._authenticate()
        
        if self.vault_config.auto_renew:
            self._renewal_task = asyncio.create_task(self._renewal_loop())
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._renewal_task:
            self._renewal_task.cancel()
            try:
                await self._renewal_task
            except asyncio.CancelledError:
                pass
        
        await super().__aexit__(exc_type, exc_val, exc_tb)
    
    async def health_check(self) -> HealthCheckResult:
        """Check Vault connectivity and seal status."""
        try:
            start = asyncio.get_event_loop().time()
            client = await self._get_client()
            response = await client.get("/v1/sys/health")
            latency = (asyncio.get_event_loop().time() - start) * 1000
            
            data = response.json()
            
            if data.get("sealed"):
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message="Vault is sealed",
                    latency_ms=latency,
                )
            
            if not data.get("initialized"):
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message="Vault is not initialized",
                    latency_ms=latency,
                )
            
            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message="Vault is unsealed and available",
                latency_ms=latency,
                details={
                    "version": data.get("version"),
                    "cluster_name": data.get("cluster_name"),
                },
            )
        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=str(e),
            )
    
    async def _authenticate(self) -> None:
        """Authenticate with Vault."""
        method = self.vault_config.auth_method
        
        if method == VaultAuthMethod.TOKEN:
            await self._auth_token()
        elif method == VaultAuthMethod.USERPASS:
            await self._auth_userpass()
        elif method == VaultAuthMethod.APPROLE:
            await self._auth_approle()
        elif method == VaultAuthMethod.KUBERNETES:
            await self._auth_kubernetes()
        else:
            raise IntegrationError(
                f"Unsupported auth method: {method}",
                integration=self.name,
            )
    
    async def _auth_token(self) -> None:
        """Authenticate with token."""
        if not self.vault_config.token:
            raise IntegrationError(
                "Token required for token auth",
                integration=self.name,
            )
        
        self._token = VaultToken(
            client_token=self.vault_config.token,
            accessor="",
        )
        
        # Look up token info
        try:
            await self._lookup_token()
        except Exception as e:
            logger.warning("Failed to lookup token", error=str(e))
    
    async def _auth_userpass(self) -> None:
        """Authenticate with username/password."""
        if not self.vault_config.username or not self.vault_config.password:
            raise IntegrationError(
                "Username and password required for userpass auth",
                integration=self.name,
            )
        
        client = await self._get_client()
        response = await client.post(
            f"/v1/auth/userpass/login/{self.vault_config.username}",
            json={"password": self.vault_config.password},
        )
        response.raise_for_status()
        
        data = response.json()
        self._parse_auth_response(data)
    
    async def _auth_approle(self) -> None:
        """Authenticate with AppRole."""
        if not self.vault_config.role_id or not self.vault_config.secret_id:
            raise IntegrationError(
                "Role ID and Secret ID required for AppRole auth",
                integration=self.name,
            )
        
        client = await self._get_client()
        response = await client.post(
            "/v1/auth/approle/login",
            json={
                "role_id": self.vault_config.role_id,
                "secret_id": self.vault_config.secret_id,
            },
        )
        response.raise_for_status()
        
        data = response.json()
        self._parse_auth_response(data)
    
    async def _auth_kubernetes(self) -> None:
        """Authenticate with Kubernetes."""
        if not self.vault_config.jwt or not self.vault_config.role:
            raise IntegrationError(
                "JWT and role required for Kubernetes auth",
                integration=self.name,
            )
        
        client = await self._get_client()
        response = await client.post(
            "/v1/auth/kubernetes/login",
            json={
                "jwt": self.vault_config.jwt,
                "role": self.vault_config.role,
            },
        )
        response.raise_for_status()
        
        data = response.json()
        self._parse_auth_response(data)
    
    def _parse_auth_response(self, data: Dict[str, Any]) -> None:
        """Parse authentication response."""
        auth = data.get("auth", {})
        
        self._token = VaultToken(
            client_token=auth.get("client_token", ""),
            accessor=auth.get("accessor", ""),
            policies=auth.get("policies", []),
            token_policies=auth.get("token_policies", []),
            metadata=auth.get("metadata", {}),
            lease_duration=auth.get("lease_duration", 0),
            renewable=auth.get("renewable", False),
        )
        
        if self._token.lease_duration > 0:
            self._token.expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=self._token.lease_duration
            )
        
        logger.info(
            "Authenticated with Vault",
            policies=self._token.policies,
            renewable=self._token.renewable,
            ttl_seconds=self._token.lease_duration,
        )
    
    async def _lookup_token(self) -> None:
        """Lookup current token info."""
        client = await self._get_client()
        response = await client.get(
            "/v1/auth/token/lookup-self",
            headers={"X-Vault-Token": self._token.client_token},
        )
        response.raise_for_status()
        
        data = response.json().get("data", {})
        
        self._token.policies = data.get("policies", [])
        self._token.accessor = data.get("accessor", "")
        self._token.renewable = data.get("renewable", False)
        
        ttl = data.get("ttl", 0)
        if ttl > 0:
            self._token.lease_duration = ttl
            self._token.expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)
    
    async def _renewal_loop(self) -> None:
        """Background token renewal loop."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                if self._token and self._token.needs_renewal(
                    self.vault_config.renewal_threshold_seconds
                ):
                    await self.renew_token()
            
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error("Token renewal failed", error=str(e))
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get client with token header."""
        client = await super()._get_client()
        
        # Add token header if we have one
        if self._token:
            client.headers["X-Vault-Token"] = self._token.client_token
        
        return client
    
    # Token Management
    
    async def renew_token(self, increment: Optional[int] = None) -> VaultToken:
        """Renew the current token.
        
        Args:
            increment: Requested TTL increment in seconds
            
        Returns:
            Updated token
        """
        if not self._token or not self._token.renewable:
            raise IntegrationError(
                "Token is not renewable",
                integration=self.name,
            )
        
        payload = {}
        if increment:
            payload["increment"] = increment
        
        client = await self._get_client()
        response = await client.post(
            "/v1/auth/token/renew-self",
            json=payload if payload else None,
        )
        response.raise_for_status()
        
        data = response.json()
        self._parse_auth_response(data)
        
        logger.info(
            "Renewed Vault token",
            ttl_seconds=self._token.lease_duration,
        )
        
        return self._token
    
    async def revoke_token(self) -> None:
        """Revoke the current token."""
        client = await self._get_client()
        response = await client.post("/v1/auth/token/revoke-self")
        response.raise_for_status()
        
        self._token = None
        logger.info("Revoked Vault token")
    
    # Secret Operations
    
    async def read_secret(
        self,
        path: str,
        version: Optional[int] = None,
    ) -> VaultSecret:
        """Read a secret.
        
        Args:
            path: Secret path (e.g., "secret/data/myapp")
            version: Specific version for KV v2
            
        Returns:
            VaultSecret
        """
        client = await self._get_client()
        
        params = {}
        if version is not None:
            params["version"] = version
        
        response = await client.get(
            f"/v1/{path}",
            params=params if params else None,
        )
        response.raise_for_status()
        
        data = response.json()
        
        # Handle KV v2 response
        secret_data = data.get("data", {})
        if "data" in secret_data and "metadata" in secret_data:
            # KV v2
            metadata = secret_data.get("metadata", {})
            return VaultSecret(
                path=path,
                data=secret_data.get("data", {}),
                metadata=metadata,
                version=metadata.get("version"),
                created_time=datetime.fromisoformat(
                    metadata["created_time"].replace("Z", "+00:00")
                ) if metadata.get("created_time") else None,
                destroyed=metadata.get("destroyed", False),
                lease_id=data.get("lease_id"),
                lease_duration=data.get("lease_duration", 0),
                renewable=data.get("renewable", False),
            )
        else:
            # KV v1 or other secrets
            return VaultSecret(
                path=path,
                data=secret_data,
                lease_id=data.get("lease_id"),
                lease_duration=data.get("lease_duration", 0),
                renewable=data.get("renewable", False),
            )
    
    async def write_secret(
        self,
        path: str,
        data: Dict[str, Any],
        cas: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Write a secret.
        
        Args:
            path: Secret path
            data: Secret data
            cas: Check-and-set version (KV v2)
            
        Returns:
            Response data
        """
        client = await self._get_client()
        
        # For KV v2, wrap data
        if "/data/" in path:
            payload = {"data": data}
            if cas is not None:
                payload["options"] = {"cas": cas}
        else:
            payload = data
        
        response = await client.post(
            f"/v1/{path}",
            json=payload,
        )
        response.raise_for_status()
        
        logger.info(
            "Wrote Vault secret",
            path=path,
        )
        
        return response.json() if response.text else None
    
    async def delete_secret(
        self,
        path: str,
        versions: Optional[List[int]] = None,
    ) -> None:
        """Delete a secret.
        
        Args:
            path: Secret path
            versions: Specific versions to delete (KV v2)
        """
        client = await self._get_client()
        
        if versions:
            # Soft delete specific versions (KV v2)
            response = await client.post(
                f"/v1/{path.replace('/data/', '/delete/')}",
                json={"versions": versions},
            )
        else:
            response = await client.delete(f"/v1/{path}")
        
        response.raise_for_status()
        
        logger.info(
            "Deleted Vault secret",
            path=path,
            versions=versions,
        )
    
    async def list_secrets(self, path: str) -> List[str]:
        """List secrets at a path.
        
        Args:
            path: Path to list
            
        Returns:
            List of secret names
        """
        client = await self._get_client()
        
        # Use metadata path for KV v2
        list_path = path
        if "/data/" in path:
            list_path = path.replace("/data/", "/metadata/")
        
        response = await client.request(
            "LIST",
            f"/v1/{list_path}",
        )
        response.raise_for_status()
        
        data = response.json()
        return data.get("data", {}).get("keys", [])
    
    # Dynamic Secrets
    
    async def generate_database_credentials(
        self,
        role: str,
        mount: str = "database",
    ) -> VaultSecret:
        """Generate dynamic database credentials.
        
        Args:
            role: Database role name
            mount: Secret engine mount
            
        Returns:
            Secret with credentials
        """
        return await self.read_secret(f"{mount}/creds/{role}")
    
    async def generate_aws_credentials(
        self,
        role: str,
        mount: str = "aws",
        ttl: Optional[str] = None,
    ) -> VaultSecret:
        """Generate dynamic AWS credentials.
        
        Args:
            role: AWS role name
            mount: Secret engine mount
            ttl: Requested TTL
            
        Returns:
            Secret with credentials
        """
        path = f"{mount}/creds/{role}"
        
        if ttl:
            # For STS credentials
            path = f"{mount}/sts/{role}"
            client = await self._get_client()
            response = await client.post(
                f"/v1/{path}",
                json={"ttl": ttl},
            )
            response.raise_for_status()
            data = response.json()
            
            return VaultSecret(
                path=path,
                data=data.get("data", {}),
                lease_id=data.get("lease_id"),
                lease_duration=data.get("lease_duration", 0),
                renewable=data.get("renewable", False),
            )
        
        return await self.read_secret(path)
    
    # Lease Management
    
    async def renew_lease(
        self,
        lease_id: str,
        increment: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Renew a secret lease.
        
        Args:
            lease_id: Lease ID
            increment: Requested TTL increment
            
        Returns:
            Renewal response
        """
        payload = {"lease_id": lease_id}
        if increment:
            payload["increment"] = increment
        
        client = await self._get_client()
        response = await client.post(
            "/v1/sys/leases/renew",
            json=payload,
        )
        response.raise_for_status()
        
        return response.json()
    
    async def revoke_lease(self, lease_id: str) -> None:
        """Revoke a secret lease.
        
        Args:
            lease_id: Lease ID
        """
        client = await self._get_client()
        response = await client.post(
            "/v1/sys/leases/revoke",
            json={"lease_id": lease_id},
        )
        response.raise_for_status()
        
        logger.info(
            "Revoked Vault lease",
            lease_id=lease_id,
        )
    
    # Encryption as a Service
    
    async def encrypt(
        self,
        key_name: str,
        plaintext: str,
        mount: str = "transit",
    ) -> str:
        """Encrypt data using Transit secrets engine.
        
        Args:
            key_name: Encryption key name
            plaintext: Base64-encoded plaintext
            mount: Transit mount path
            
        Returns:
            Ciphertext
        """
        client = await self._get_client()
        response = await client.post(
            f"/v1/{mount}/encrypt/{key_name}",
            json={"plaintext": plaintext},
        )
        response.raise_for_status()
        
        return response.json().get("data", {}).get("ciphertext", "")
    
    async def decrypt(
        self,
        key_name: str,
        ciphertext: str,
        mount: str = "transit",
    ) -> str:
        """Decrypt data using Transit secrets engine.
        
        Args:
            key_name: Encryption key name
            ciphertext: Ciphertext
            mount: Transit mount path
            
        Returns:
            Base64-encoded plaintext
        """
        client = await self._get_client()
        response = await client.post(
            f"/v1/{mount}/decrypt/{key_name}",
            json={"ciphertext": ciphertext},
        )
        response.raise_for_status()
        
        return response.json().get("data", {}).get("plaintext", "")
