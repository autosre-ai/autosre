"""
Vault Skill for OpenSRE

HashiCorp Vault secrets management.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import logging

import httpx

from opensre_core.skills import Skill, ActionResult

logger = logging.getLogger(__name__)


@dataclass
class Secret:
    """Vault secret."""
    path: str
    data: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    version: int | None = None


@dataclass
class HealthStatus:
    """Vault health status."""
    initialized: bool
    sealed: bool
    standby: bool
    performance_standby: bool
    version: str
    cluster_name: str | None = None
    cluster_id: str | None = None


@dataclass
class SealStatus:
    """Vault seal status."""
    sealed: bool
    threshold: int
    shares: int
    progress: int
    version: str
    cluster_name: str | None = None
    cluster_id: str | None = None


@dataclass
class AuthMethod:
    """Vault auth method."""
    path: str
    type: str
    description: str
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class TokenInfo:
    """Vault token information."""
    accessor: str
    creation_time: int
    creation_ttl: int
    display_name: str
    expire_time: datetime | None = None
    policies: list[str] = field(default_factory=list)
    renewable: bool = False
    ttl: int = 0


class VaultSkill(Skill):
    """Skill for interacting with HashiCorp Vault."""

    name = "vault"
    version = "1.0.0"
    description = "HashiCorp Vault secrets management"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.url = self.config.get("url", "").rstrip("/")
        self.token = self.config.get("token", "")
        self.namespace = self.config.get("namespace")
        self.auth_method = self.config.get("auth_method", "token")
        self.timeout = self.config.get("timeout", 30)
        self._client: httpx.AsyncClient | None = None

        # Register actions
        self.register_action("read_secret", self.read_secret, "Read secret")
        self.register_action("list_secrets", self.list_secrets, "List secrets")
        self.register_action("get_health", self.get_health, "Get health status")
        self.register_action("get_seal_status", self.get_seal_status, "Get seal status")
        self.register_action("list_auth_methods", self.list_auth_methods, "List auth methods")
        self.register_action("renew_token", self.renew_token, "Renew token")

    async def initialize(self) -> None:
        """Initialize HTTP client and authenticate."""
        headers: dict[str, str] = {}
        
        if self.token:
            headers["X-Vault-Token"] = self.token
        if self.namespace:
            headers["X-Vault-Namespace"] = self.namespace

        self._client = httpx.AsyncClient(
            base_url=f"{self.url}/v1",
            headers=headers,
            timeout=self.timeout,
        )

        # Authenticate with AppRole if configured
        if self.auth_method == "approle":
            role_id = self.config.get("role_id")
            secret_id = self.config.get("secret_id")
            if role_id and secret_id:
                try:
                    response = await self._client.post(
                        "/auth/approle/login",
                        json={"role_id": role_id, "secret_id": secret_id},
                    )
                    response.raise_for_status()
                    data = response.json()
                    token = data.get("auth", {}).get("client_token")
                    if token:
                        self._client.headers["X-Vault-Token"] = token
                except Exception as e:
                    logger.error(f"AppRole authentication failed: {e}")

        self._initialized = True

    async def shutdown(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._initialized = False

    async def health_check(self) -> ActionResult[dict[str, Any]]:
        """Check Vault connectivity."""
        result = await self.get_health()
        if result.success:
            return ActionResult.ok({
                "status": "healthy" if not result.data.sealed else "sealed",
                "version": result.data.version,
            })
        return ActionResult.fail(result.error or "Health check failed")

    async def read_secret(
        self,
        path: str,
        version: int | None = None,
    ) -> ActionResult[Secret]:
        """Read a secret from Vault."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            params: dict[str, Any] = {}
            if version:
                params["version"] = version

            response = await self._client.get(f"/{path}", params=params)
            response.raise_for_status()
            data = response.json()

            secret_data = data.get("data", {})
            # KV v2 has nested data structure
            if "data" in secret_data and "metadata" in secret_data:
                return ActionResult.ok(Secret(
                    path=path,
                    data=secret_data["data"],
                    metadata=secret_data.get("metadata", {}),
                    version=secret_data.get("metadata", {}).get("version"),
                ))
            else:
                # KV v1
                return ActionResult.ok(Secret(
                    path=path,
                    data=secret_data,
                ))
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return ActionResult.fail(f"Secret not found: {path}")
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error reading secret")
            return ActionResult.fail(str(e))

    async def list_secrets(
        self,
        path: str,
    ) -> ActionResult[list[str]]:
        """List secrets at a path."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            response = await self._client.request(
                "LIST",
                f"/{path}",
            )
            response.raise_for_status()
            data = response.json()

            keys = data.get("data", {}).get("keys", [])
            return ActionResult.ok(keys)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return ActionResult.ok([])
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error listing secrets")
            return ActionResult.fail(str(e))

    async def get_health(self) -> ActionResult[HealthStatus]:
        """Get Vault health status."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            response = await self._client.get("/sys/health")
            # Vault returns different status codes based on state
            data = response.json()

            return ActionResult.ok(HealthStatus(
                initialized=data.get("initialized", False),
                sealed=data.get("sealed", True),
                standby=data.get("standby", False),
                performance_standby=data.get("performance_standby", False),
                version=data.get("version", ""),
                cluster_name=data.get("cluster_name"),
                cluster_id=data.get("cluster_id"),
            ))
        except Exception as e:
            logger.exception("Error getting health")
            return ActionResult.fail(str(e))

    async def get_seal_status(self) -> ActionResult[SealStatus]:
        """Get Vault seal status."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            response = await self._client.get("/sys/seal-status")
            response.raise_for_status()
            data = response.json()

            return ActionResult.ok(SealStatus(
                sealed=data.get("sealed", True),
                threshold=data.get("t", 0),
                shares=data.get("n", 0),
                progress=data.get("progress", 0),
                version=data.get("version", ""),
                cluster_name=data.get("cluster_name"),
                cluster_id=data.get("cluster_id"),
            ))
        except Exception as e:
            logger.exception("Error getting seal status")
            return ActionResult.fail(str(e))

    async def list_auth_methods(self) -> ActionResult[list[AuthMethod]]:
        """List enabled auth methods."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            response = await self._client.get("/sys/auth")
            response.raise_for_status()
            data = response.json()

            methods = []
            for path, info in data.get("data", data).items():
                methods.append(AuthMethod(
                    path=path.rstrip("/"),
                    type=info.get("type", ""),
                    description=info.get("description", ""),
                    config=info.get("config", {}),
                ))
            return ActionResult.ok(methods)
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error listing auth methods")
            return ActionResult.fail(str(e))

    async def renew_token(self) -> ActionResult[TokenInfo]:
        """Renew the current token."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            response = await self._client.post("/auth/token/renew-self")
            response.raise_for_status()
            data = response.json()
            auth = data.get("auth", {})

            return ActionResult.ok(TokenInfo(
                accessor=auth.get("accessor", ""),
                creation_time=auth.get("creation_time", 0),
                creation_ttl=auth.get("creation_ttl", 0),
                display_name=auth.get("display_name", ""),
                policies=auth.get("policies", []),
                renewable=auth.get("renewable", False),
                ttl=auth.get("lease_duration", 0),
            ))
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error renewing token")
            return ActionResult.fail(str(e))
