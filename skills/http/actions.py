"""
HTTP Skill Actions

Generic HTTP client for API calls, health checks, and webhooks.
"""

from dataclasses import dataclass, field
from typing import Any
import time
import logging

import httpx

from opensre_core.skills import Skill, ActionResult, action

logger = logging.getLogger(__name__)


@dataclass
class HTTPResponse:
    """HTTP response data."""
    status_code: int
    headers: dict[str, str]
    body: Any  # Can be dict (JSON) or str
    url: str
    elapsed_ms: float


@dataclass
class HealthStatus:
    """Health check result."""
    healthy: bool
    status_code: int | None
    response_time_ms: float
    url: str
    error: str | None = None


class HTTPSkill(Skill):
    """Generic HTTP client skill."""
    
    name = "http"
    version = "1.0.0"
    description = "Generic HTTP client for API calls and health checks"
    
    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.base_url = self.config.get("base_url", "").rstrip("/")
        self.timeout = self.config.get("timeout", 30)
        self.default_headers = self.config.get("headers", {})
        self.verify_ssl = self.config.get("verify_ssl", True)
        self._client: httpx.AsyncClient | None = None
        
        # Register actions
        self.register_action("get", self.get, "Make HTTP GET request")
        self.register_action("post", self.post, "Make HTTP POST request")
        self.register_action("health_check", self.health_check_action, "Check endpoint health")
    
    async def initialize(self) -> None:
        """Initialize HTTP client."""
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            verify=self.verify_ssl,
            headers=self.default_headers,
        )
        await super().initialize()
    
    async def shutdown(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        await super().shutdown()
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Get HTTP client, creating if needed."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                verify=self.verify_ssl,
                headers=self.default_headers,
            )
        return self._client
    
    def _build_url(self, url: str) -> str:
        """Build full URL from path or URL."""
        if url.startswith(("http://", "https://")):
            return url
        if self.base_url:
            return f"{self.base_url}/{url.lstrip('/')}"
        return url
    
    async def health_check(self) -> ActionResult[dict[str, Any]]:
        """Check skill health (HTTP client works)."""
        return ActionResult.ok({
            "status": "healthy",
            "base_url": self.base_url or "(none)",
            "timeout": self.timeout,
        })
    
    @action(description="Make HTTP GET request")
    async def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
    ) -> ActionResult[HTTPResponse]:
        """Make HTTP GET request.
        
        Args:
            url: URL or path to request
            headers: Additional headers
            params: Query parameters
            
        Returns:
            HTTPResponse with status, headers, body
        """
        full_url = self._build_url(url)
        
        try:
            start = time.monotonic()
            response = await self.client.get(
                full_url,
                headers=headers,
                params=params,
            )
            elapsed = (time.monotonic() - start) * 1000
            
            # Try to parse JSON body
            try:
                body = response.json()
            except Exception:
                body = response.text
            
            return ActionResult.ok(HTTPResponse(
                status_code=response.status_code,
                headers=dict(response.headers),
                body=body,
                url=str(response.url),
                elapsed_ms=elapsed,
            ))
            
        except httpx.TimeoutException:
            return ActionResult.fail(f"Request timed out: {full_url}")
        except httpx.ConnectError as e:
            return ActionResult.fail(f"Connection failed: {e}")
        except Exception as e:
            return ActionResult.fail(f"Request failed: {e}")
    
    @action(description="Make HTTP POST request")
    async def post(
        self,
        url: str,
        body: Any,
        headers: dict[str, str] | None = None,
    ) -> ActionResult[HTTPResponse]:
        """Make HTTP POST request.
        
        Args:
            url: URL or path to request
            body: Request body (dict for JSON, str for raw)
            headers: Additional headers
            
        Returns:
            HTTPResponse with status, headers, body
        """
        full_url = self._build_url(url)
        
        try:
            start = time.monotonic()
            
            # Determine content type and method
            if isinstance(body, dict):
                response = await self.client.post(
                    full_url,
                    json=body,
                    headers=headers,
                )
            else:
                response = await self.client.post(
                    full_url,
                    content=str(body),
                    headers=headers,
                )
            
            elapsed = (time.monotonic() - start) * 1000
            
            # Try to parse JSON body
            try:
                response_body = response.json()
            except Exception:
                response_body = response.text
            
            return ActionResult.ok(HTTPResponse(
                status_code=response.status_code,
                headers=dict(response.headers),
                body=response_body,
                url=str(response.url),
                elapsed_ms=elapsed,
            ))
            
        except httpx.TimeoutException:
            return ActionResult.fail(f"Request timed out: {full_url}")
        except httpx.ConnectError as e:
            return ActionResult.fail(f"Connection failed: {e}")
        except Exception as e:
            return ActionResult.fail(f"Request failed: {e}")
    
    @action(description="Check endpoint health")
    async def health_check_action(
        self,
        url: str,
        expected_status: int = 200,
        timeout: int = 5,
    ) -> ActionResult[HealthStatus]:
        """Check if an endpoint is healthy.
        
        Args:
            url: URL to check
            expected_status: Expected HTTP status code
            timeout: Timeout in seconds
            
        Returns:
            HealthStatus with result
        """
        full_url = self._build_url(url)
        
        try:
            start = time.monotonic()
            response = await self.client.get(
                full_url,
                timeout=timeout,
            )
            elapsed = (time.monotonic() - start) * 1000
            
            healthy = response.status_code == expected_status
            
            return ActionResult.ok(HealthStatus(
                healthy=healthy,
                status_code=response.status_code,
                response_time_ms=elapsed,
                url=full_url,
                error=None if healthy else f"Expected {expected_status}, got {response.status_code}",
            ))
            
        except httpx.TimeoutException:
            return ActionResult.ok(HealthStatus(
                healthy=False,
                status_code=None,
                response_time_ms=timeout * 1000,
                url=full_url,
                error="Request timed out",
            ))
        except Exception as e:
            return ActionResult.ok(HealthStatus(
                healthy=False,
                status_code=None,
                response_time_ms=0,
                url=full_url,
                error=str(e),
            ))
