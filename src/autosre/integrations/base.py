"""
Base classes for AutoSRE V2 integrations.

Provides common patterns for all integration clients:
- Async HTTP client management
- Retry logic with exponential backoff
- Health checks
- Error handling
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import httpx

from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class HealthStatus(str, Enum):
    """Health check status."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    status: HealthStatus
    message: str = ""
    latency_ms: float | None = None
    details: dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    retry_on_status: tuple[int, ...] = (429, 500, 502, 503, 504)


@dataclass
class ConnectionConfig:
    """Connection configuration for integrations."""

    base_url: str
    timeout: float = 30.0
    max_connections: int = 10
    verify_ssl: bool = True
    headers: dict[str, str] = field(default_factory=dict)


class IntegrationError(Exception):
    """Base exception for integration errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        integration: str | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.integration = integration


class ConnectionError(IntegrationError):
    """Connection error."""

    pass


class AuthenticationError(IntegrationError):
    """Authentication error."""

    pass


class RateLimitError(IntegrationError):
    """Rate limit error."""

    def __init__(
        self,
        message: str,
        status_code: int = 429,
        retry_after: float | None = None,
    ):
        super().__init__(message, status_code)
        self.retry_after = retry_after


class ValidationError(IntegrationError):
    """Validation error."""

    pass


class BaseIntegration(ABC):
    """
    Abstract base class for all integrations.

    Provides common functionality:
    - Async HTTP client management
    - Connection pooling
    - Health checks
    """

    def __init__(
        self,
        config: ConnectionConfig | None = None,
        retry_config: RetryConfig | None = None,
    ):
        self.config = config or ConnectionConfig(base_url="http://localhost")
        self.retry_config = retry_config or RetryConfig()
        self._client: httpx.AsyncClient | None = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Return integration name."""
        ...

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=self.config.timeout,
                verify=self.config.verify_ssl,
                headers=self.config.headers,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    @abstractmethod
    async def health_check(self) -> HealthCheckResult:
        """Perform health check."""
        ...

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> Any:
        """Make HTTP request with retry logic."""
        client = await self._get_client()

        last_error = None
        for attempt in range(self.retry_config.max_retries + 1):
            try:
                response = await client.request(method, path, **kwargs)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code in self.retry_config.retry_on_status:
                    last_error = e
                    delay = min(
                        self.retry_config.base_delay * (self.retry_config.exponential_base ** attempt),
                        self.retry_config.max_delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    raise IntegrationError(
                        message=str(e),
                        status_code=e.response.status_code,
                        integration=self.name,
                    )
            except httpx.ConnectError as e:
                raise ConnectionError(
                    message=str(e),
                    integration=self.name,
                )
            except Exception as e:
                raise IntegrationError(
                    message=str(e),
                    integration=self.name,
                )

        if last_error:
            raise IntegrationError(
                message=f"Max retries exceeded: {last_error}",
                status_code=last_error.response.status_code if hasattr(last_error, 'response') else None,
                integration=self.name,
            )


class AuthenticatedIntegration(BaseIntegration):
    """
    Base class for integrations requiring authentication.

    Supports:
    - Bearer token auth
    - API key auth
    - Basic auth
    """

    def __init__(
        self,
        config: ConnectionConfig | None = None,
        auth_token: str | None = None,
        api_key: str | None = None,
        api_key_header: str = "X-API-Key",
        username: str | None = None,
        password: str | None = None,
        **kwargs,
    ):
        super().__init__(config, **kwargs)
        self._auth_token = auth_token
        self._api_key = api_key
        self._api_key_header = api_key_header
        self._username = username
        self._password = password

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create authenticated HTTP client."""
        if self._client is None:
            headers = dict(self.config.headers)

            if self._auth_token:
                headers["Authorization"] = f"Bearer {self._auth_token}"
            elif self._api_key:
                headers[self._api_key_header] = self._api_key

            auth = None
            if self._username and self._password:
                auth = httpx.BasicAuth(self._username, self._password)

            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=self.config.timeout,
                verify=self.config.verify_ssl,
                headers=headers,
                auth=auth,
            )
        return self._client
