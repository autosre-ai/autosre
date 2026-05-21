"""HTTP client for AutoSRE API calls with SSE streaming support."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Iterator

import httpx
import yaml


@dataclass
class APIConfig:
    """API configuration loaded from config file."""
    
    base_url: str = "http://localhost:8000"
    api_key: str | None = None
    timeout: float = 30.0
    
    @classmethod
    def load(cls, config_path: Path | None = None) -> "APIConfig":
        """Load API config from file."""
        if config_path is None:
            config_path = Path.home() / ".autosre" / "config.yaml"
        
        config = cls()
        
        if config_path.exists():
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}
            
            api_config = data.get("api", {})
            if "base_url" in api_config:
                config.base_url = api_config["base_url"]
            if "api_key" in api_config:
                config.api_key = api_config["api_key"]
            if "timeout" in api_config:
                config.timeout = float(api_config["timeout"])
        
        return config


class AutoSREClient:
    """HTTP client for interacting with the AutoSRE API."""
    
    def __init__(self, config: APIConfig | None = None):
        """Initialize the client with optional config."""
        self.config = config or APIConfig.load()
        self._client: httpx.Client | None = None
    
    @property
    def client(self) -> httpx.Client:
        """Get or create the HTTP client."""
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            
            self._client = httpx.Client(
                base_url=self.config.base_url,
                headers=headers,
                timeout=self.config.timeout,
            )
        return self._client
    
    def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            self._client.close()
            self._client = None
    
    def __enter__(self) -> "AutoSREClient":
        return self
    
    def __exit__(self, *args) -> None:
        self.close()
    
    # Investigation endpoints
    
    def create_investigation(
        self,
        description: str,
        service: str | None = None,
        severity: str = "medium",
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new investigation."""
        payload = {
            "description": description,
            "severity": severity,
        }
        if service:
            payload["service"] = service
        if context:
            payload["context"] = context
        
        response = self.client.post("/api/v1/investigations", json=payload)
        response.raise_for_status()
        return response.json()
    
    def get_investigation(self, investigation_id: str) -> dict[str, Any]:
        """Get investigation status and details."""
        response = self.client.get(f"/api/v1/investigations/{investigation_id}")
        response.raise_for_status()
        return response.json()
    
    def list_investigations(
        self,
        limit: int = 10,
        status: str | None = None,
        service: str | None = None,
    ) -> list[dict[str, Any]]:
        """List recent investigations."""
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        if service:
            params["service"] = service
        
        response = self.client.get("/api/v1/investigations", params=params)
        response.raise_for_status()
        return response.json()
    
    def stream_investigation(self, investigation_id: str) -> Iterator[dict[str, Any]]:
        """Stream investigation progress via SSE."""
        with self.client.stream(
            "GET",
            f"/api/v1/investigations/{investigation_id}/stream",
            headers={"Accept": "text/event-stream"},
        ) as response:
            response.raise_for_status()
            
            buffer = ""
            for chunk in response.iter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    event_str, buffer = buffer.split("\n\n", 1)
                    event = self._parse_sse_event(event_str)
                    if event:
                        yield event
    
    def _parse_sse_event(self, event_str: str) -> dict[str, Any] | None:
        """Parse an SSE event string into a dictionary."""
        event_type = "message"
        data_lines = []
        
        for line in event_str.split("\n"):
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].strip())
        
        if data_lines:
            data_str = "\n".join(data_lines)
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                data = data_str
            return {"event": event_type, "data": data}
        
        return None
    
    # Memory endpoints
    
    def search_memory(
        self,
        query: str,
        limit: int = 10,
        memory_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search investigation memory."""
        params: dict[str, Any] = {"query": query, "limit": limit}
        if memory_type:
            params["type"] = memory_type
        
        response = self.client.get("/api/v1/memory/search", params=params)
        response.raise_for_status()
        return response.json()
    
    def get_memory_stats(self) -> dict[str, Any]:
        """Get memory statistics."""
        response = self.client.get("/api/v1/memory/stats")
        response.raise_for_status()
        return response.json()
    
    # Topology endpoints
    
    def get_topology(self, service: str | None = None) -> dict[str, Any]:
        """Get service topology."""
        params = {}
        if service:
            params["service"] = service
        
        response = self.client.get("/api/v1/topology", params=params)
        response.raise_for_status()
        return response.json()
    
    def get_blast_radius(self, service: str) -> dict[str, Any]:
        """Get blast radius for a service."""
        response = self.client.get(f"/api/v1/topology/{service}/blast-radius")
        response.raise_for_status()
        return response.json()
    
    # Config endpoints
    
    def get_config(self) -> dict[str, Any]:
        """Get current server configuration."""
        response = self.client.get("/api/v1/config")
        response.raise_for_status()
        return response.json()


class AsyncAutoSREClient:
    """Async HTTP client for AutoSRE API."""
    
    def __init__(self, config: APIConfig | None = None):
        """Initialize the async client."""
        self.config = config or APIConfig.load()
        self._client: httpx.AsyncClient | None = None
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client."""
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                headers=headers,
                timeout=self.config.timeout,
            )
        return self._client
    
    async def close(self) -> None:
        """Close the async HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def __aenter__(self) -> "AsyncAutoSREClient":
        return self
    
    async def __aexit__(self, *args) -> None:
        await self.close()
    
    async def create_investigation(
        self,
        description: str,
        service: str | None = None,
        severity: str = "medium",
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new investigation."""
        payload = {
            "description": description,
            "severity": severity,
        }
        if service:
            payload["service"] = service
        if context:
            payload["context"] = context
        
        response = await self.client.post("/api/v1/investigations", json=payload)
        response.raise_for_status()
        return response.json()
    
    async def stream_investigation(
        self, investigation_id: str
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream investigation progress via SSE (async)."""
        async with self.client.stream(
            "GET",
            f"/api/v1/investigations/{investigation_id}/stream",
            headers={"Accept": "text/event-stream"},
        ) as response:
            response.raise_for_status()
            
            buffer = ""
            async for chunk in response.aiter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    event_str, buffer = buffer.split("\n\n", 1)
                    event = self._parse_sse_event(event_str)
                    if event:
                        yield event
    
    def _parse_sse_event(self, event_str: str) -> dict[str, Any] | None:
        """Parse an SSE event string into a dictionary."""
        event_type = "message"
        data_lines = []
        
        for line in event_str.split("\n"):
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].strip())
        
        if data_lines:
            data_str = "\n".join(data_lines)
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                data = data_str
            return {"event": event_type, "data": data}
        
        return None
