"""Grafana API client with rate limiting and error handling."""

import asyncio
import time
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel

from .models import (
    Annotation,
    DashboardResponse,
    DashboardSearchResult,
    Datasource,
    DatasourceHealth,
    Folder,
    Organization,
    QueryResponse,
    QueryTarget,
    RenderOptions,
    User,
)


class GrafanaConfig(BaseModel):
    """Configuration for Grafana client."""
    url: str  # Base URL (e.g., https://grafana.example.com)
    api_key: str | None = None  # API key (preferred)
    username: str | None = None  # Basic auth username
    password: str | None = None  # Basic auth password
    org_id: int | None = None  # Organization ID (for multi-org setups)
    timeout: float = 30.0
    max_retries: int = 3
    rate_limit_requests: int = 100  # requests per minute
    rate_limit_window: int = 60  # seconds
    verify_ssl: bool = True


class RateLimiter:
    """Token bucket rate limiter."""
    
    def __init__(self, requests_per_window: int, window_seconds: int):
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.tokens = requests_per_window
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> None:
        """Acquire a token, waiting if necessary."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            
            self.tokens = min(
                self.requests_per_window,
                self.tokens + (elapsed * self.requests_per_window / self.window_seconds)
            )
            self.last_update = now
            
            if self.tokens < 1:
                wait_time = (1 - self.tokens) * self.window_seconds / self.requests_per_window
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1


class GrafanaError(Exception):
    """Base exception for Grafana API errors."""
    
    def __init__(self, message: str, status_code: int | None = None, response: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class GrafanaAuthError(GrafanaError):
    """Authentication error."""
    pass


class GrafanaNotFoundError(GrafanaError):
    """Resource not found."""
    pass


class GrafanaRateLimitError(GrafanaError):
    """Rate limit exceeded."""
    pass


class GrafanaClient:
    """Async client for Grafana API."""
    
    def __init__(self, config: GrafanaConfig):
        self.config = config
        self.base_url = config.url.rstrip("/")
        self._client: httpx.AsyncClient | None = None
        self._rate_limiter = RateLimiter(
            config.rate_limit_requests,
            config.rate_limit_window
        )
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            headers = {"Content-Type": "application/json"}
            
            # Auth
            auth = None
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            elif self.config.username and self.config.password:
                auth = httpx.BasicAuth(self.config.username, self.config.password)
            
            # Org header
            if self.config.org_id:
                headers["X-Grafana-Org-Id"] = str(self.config.org_id)
            
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.timeout),
                headers=headers,
                auth=auth,
                verify=self.config.verify_ssl,
            )
        return self._client
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    async def __aenter__(self) -> "GrafanaClient":
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json_data: dict | None = None,
        raw_response: bool = False,
    ) -> dict[str, Any] | bytes:
        """Make an API request with rate limiting and retry logic."""
        url = urljoin(self.base_url, f"/api/{endpoint}")
        
        last_error = None
        for attempt in range(self.config.max_retries):
            await self._rate_limiter.acquire()
            
            try:
                response = await self.client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                )
                
                if response.status_code == 200:
                    if raw_response:
                        return response.content
                    return response.json()
                elif response.status_code == 401:
                    raise GrafanaAuthError(
                        "Invalid API key or credentials",
                        status_code=401,
                    )
                elif response.status_code == 403:
                    raise GrafanaAuthError(
                        "Access forbidden - check permissions",
                        status_code=403,
                    )
                elif response.status_code == 404:
                    raise GrafanaNotFoundError(
                        f"Resource not found: {endpoint}",
                        status_code=404,
                    )
                elif response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    if attempt < self.config.max_retries - 1:
                        await asyncio.sleep(retry_after)
                        continue
                    raise GrafanaRateLimitError(
                        "Rate limit exceeded",
                        status_code=429,
                    )
                else:
                    error_body = response.json() if response.content else {}
                    raise GrafanaError(
                        f"API error: {response.status_code} - {error_body.get('message', 'Unknown error')}",
                        status_code=response.status_code,
                        response=error_body,
                    )
                    
            except httpx.TimeoutException as e:
                last_error = GrafanaError(f"Request timeout: {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
            except httpx.RequestError as e:
                last_error = GrafanaError(f"Request error: {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
        
        raise last_error or GrafanaError("Max retries exceeded")
    
    # =========================================================================
    # Datasources API
    # =========================================================================
    
    async def get_datasources(self) -> list[Datasource]:
        """Get all datasources."""
        data = await self._request("GET", "datasources")
        return [Datasource(**ds) for ds in data]
    
    async def get_datasource(self, uid_or_name: str) -> Datasource:
        """Get a datasource by UID or name."""
        # Try by UID first
        try:
            data = await self._request("GET", f"datasources/uid/{uid_or_name}")
            return Datasource(**data)
        except GrafanaNotFoundError:
            # Try by name
            data = await self._request("GET", f"datasources/name/{uid_or_name}")
            return Datasource(**data)
    
    async def get_datasource_by_id(self, datasource_id: int) -> Datasource:
        """Get a datasource by ID."""
        data = await self._request("GET", f"datasources/{datasource_id}")
        return Datasource(**data)
    
    async def check_datasource_health(self, uid: str) -> DatasourceHealth:
        """Check datasource health."""
        data = await self._request("GET", f"datasources/uid/{uid}/health")
        return DatasourceHealth(**data)
    
    async def query_datasource(
        self,
        datasource: str | int,
        queries: list[dict[str, Any]] | list[QueryTarget],
        from_time: datetime | str | int,
        to_time: datetime | str | int,
    ) -> QueryResponse:
        """
        Query a datasource directly.
        
        Args:
            datasource: Datasource UID, name, or ID
            queries: List of query targets
            from_time: Start time (datetime, ISO string, or Unix ms)
            to_time: End time (datetime, ISO string, or Unix ms)
        
        Returns:
            QueryResponse with results
        """
        # Resolve datasource
        if isinstance(datasource, int):
            ds = await self.get_datasource_by_id(datasource)
        else:
            ds = await self.get_datasource(datasource)
        
        # Format times
        if isinstance(from_time, datetime):
            from_time = str(int(from_time.timestamp() * 1000))
        elif isinstance(from_time, int):
            from_time = str(from_time)
        
        if isinstance(to_time, datetime):
            to_time = str(int(to_time.timestamp() * 1000))
        elif isinstance(to_time, int):
            to_time = str(to_time)
        
        # Build query targets
        targets = []
        for i, q in enumerate(queries):
            if isinstance(q, QueryTarget):
                target = q.model_dump(by_alias=True, exclude_none=True)
            else:
                target = q.copy()
            
            if "refId" not in target:
                target["refId"] = chr(65 + i)  # A, B, C, ...
            
            target["datasource"] = {"uid": ds.uid, "type": ds.type}
            targets.append(target)
        
        json_data = {
            "queries": targets,
            "from": from_time,
            "to": to_time,
        }
        
        data = await self._request("POST", "ds/query", json_data=json_data)
        return QueryResponse(**data)
    
    # =========================================================================
    # Dashboards API
    # =========================================================================
    
    async def get_dashboards(
        self,
        query: str | None = None,
        tags: list[str] | None = None,
        folder_ids: list[int] | None = None,
        starred: bool | None = None,
        limit: int = 1000,
    ) -> list[DashboardSearchResult]:
        """
        Search dashboards.
        
        Args:
            query: Search query
            tags: Filter by tags
            folder_ids: Filter by folder IDs
            starred: Filter by starred status
            limit: Maximum results
        
        Returns:
            List of dashboard search results
        """
        params = {
            "type": "dash-db",
            "limit": limit,
        }
        
        if query:
            params["query"] = query
        if tags:
            params["tag"] = tags
        if folder_ids:
            params["folderIds"] = folder_ids
        if starred is not None:
            params["starred"] = str(starred).lower()
        
        data = await self._request("GET", "search", params=params)
        return [DashboardSearchResult(**d) for d in data]
    
    async def get_dashboard(self, uid: str) -> DashboardResponse:
        """Get a dashboard by UID."""
        data = await self._request("GET", f"dashboards/uid/{uid}")
        return DashboardResponse(**data)
    
    async def get_dashboard_by_slug(self, slug: str) -> DashboardResponse:
        """Get a dashboard by slug."""
        data = await self._request("GET", f"dashboards/db/{slug}")
        return DashboardResponse(**data)
    
    async def get_home_dashboard(self) -> DashboardResponse:
        """Get the home dashboard."""
        data = await self._request("GET", "dashboards/home")
        return DashboardResponse(**data)
    
    async def get_dashboard_tags(self) -> list[dict[str, Any]]:
        """Get all dashboard tags."""
        return await self._request("GET", "dashboards/tags")
    
    # =========================================================================
    # Annotations API
    # =========================================================================
    
    async def get_annotations(
        self,
        from_time: datetime | int,
        to_time: datetime | int,
        dashboard_id: int | None = None,
        dashboard_uid: str | None = None,
        panel_id: int | None = None,
        tags: list[str] | None = None,
        type_filter: str | None = None,
        limit: int = 100,
    ) -> list[Annotation]:
        """
        Get annotations within a time range.
        
        Args:
            from_time: Start time (datetime or Unix ms)
            to_time: End time (datetime or Unix ms)
            dashboard_id: Filter by dashboard ID
            dashboard_uid: Filter by dashboard UID
            panel_id: Filter by panel ID
            tags: Filter by tags
            type_filter: Filter by type (alert, annotation)
            limit: Maximum results
        
        Returns:
            List of annotations
        """
        if isinstance(from_time, datetime):
            from_time = int(from_time.timestamp() * 1000)
        if isinstance(to_time, datetime):
            to_time = int(to_time.timestamp() * 1000)
        
        params = {
            "from": from_time,
            "to": to_time,
            "limit": limit,
        }
        
        if dashboard_id:
            params["dashboardId"] = dashboard_id
        if dashboard_uid:
            params["dashboardUID"] = dashboard_uid
        if panel_id:
            params["panelId"] = panel_id
        if tags:
            params["tags"] = tags
        if type_filter:
            params["type"] = type_filter
        
        data = await self._request("GET", "annotations", params=params)
        return [Annotation(**a) for a in data]
    
    async def create_annotation(
        self,
        text: str,
        time_start: datetime | int,
        time_end: datetime | int | None = None,
        tags: list[str] | None = None,
        dashboard_uid: str | None = None,
        panel_id: int | None = None,
    ) -> Annotation:
        """
        Create an annotation.
        
        Args:
            text: Annotation text
            time_start: Start time
            time_end: End time (for region annotation)
            tags: Annotation tags
            dashboard_uid: Dashboard UID (optional)
            panel_id: Panel ID (optional)
        
        Returns:
            Created annotation
        """
        if isinstance(time_start, datetime):
            time_start = int(time_start.timestamp() * 1000)
        
        json_data = {
            "text": text,
            "time": time_start,
            "tags": tags or [],
        }
        
        if time_end:
            if isinstance(time_end, datetime):
                time_end = int(time_end.timestamp() * 1000)
            json_data["timeEnd"] = time_end
        
        if dashboard_uid:
            json_data["dashboardUID"] = dashboard_uid
        if panel_id:
            json_data["panelId"] = panel_id
        
        data = await self._request("POST", "annotations", json_data=json_data)
        return Annotation(
            id=data.get("id"),
            time=time_start,
            text=text,
            tags=tags or [],
        )
    
    async def delete_annotation(self, annotation_id: int) -> None:
        """Delete an annotation."""
        await self._request("DELETE", f"annotations/{annotation_id}")
    
    # =========================================================================
    # Render API
    # =========================================================================
    
    async def render_panel(
        self,
        dashboard_uid: str,
        panel_id: int,
        options: RenderOptions | None = None,
    ) -> bytes:
        """
        Render a panel as an image.
        
        Args:
            dashboard_uid: Dashboard UID
            panel_id: Panel ID
            options: Render options
        
        Returns:
            PNG image bytes
        """
        if options is None:
            options = RenderOptions()
        
        params = {
            "from": options.from_time,
            "to": options.to_time,
            "width": options.width,
            "height": options.height,
            "timeout": options.timeout,
            "scale": options.scale,
        }
        
        if options.tz:
            params["tz"] = options.tz
        
        # Use d-solo endpoint for single panel render
        endpoint = f"render/d-solo/{dashboard_uid}"
        params["panelId"] = panel_id
        
        return await self._request("GET", endpoint, params=params, raw_response=True)
    
    async def render_dashboard(
        self,
        dashboard_uid: str,
        options: RenderOptions | None = None,
    ) -> bytes:
        """
        Render a full dashboard as an image.
        
        Args:
            dashboard_uid: Dashboard UID
            options: Render options
        
        Returns:
            PNG image bytes
        """
        if options is None:
            options = RenderOptions(width=1200, height=800)
        
        params = {
            "from": options.from_time,
            "to": options.to_time,
            "width": options.width,
            "height": options.height,
            "timeout": options.timeout,
            "scale": options.scale,
        }
        
        if options.tz:
            params["tz"] = options.tz
        
        endpoint = f"render/d/{dashboard_uid}"
        return await self._request("GET", endpoint, params=params, raw_response=True)
    
    # =========================================================================
    # Folders API
    # =========================================================================
    
    async def get_folders(self) -> list[Folder]:
        """Get all folders."""
        data = await self._request("GET", "folders")
        return [Folder(**f) for f in data]
    
    async def get_folder(self, uid: str) -> Folder:
        """Get a folder by UID."""
        data = await self._request("GET", f"folders/{uid}")
        return Folder(**data)
    
    async def create_folder(self, title: str, uid: str | None = None) -> Folder:
        """Create a folder."""
        json_data = {"title": title}
        if uid:
            json_data["uid"] = uid
        
        data = await self._request("POST", "folders", json_data=json_data)
        return Folder(**data)
    
    async def delete_folder(self, uid: str, force_delete_rules: bool = False) -> None:
        """Delete a folder."""
        params = {}
        if force_delete_rules:
            params["forceDeleteRules"] = "true"
        
        await self._request("DELETE", f"folders/{uid}", params=params)
    
    # =========================================================================
    # Alerts API (Legacy)
    # =========================================================================
    
    async def get_alerts(
        self,
        dashboard_ids: list[int] | None = None,
        panel_id: int | None = None,
        query: str | None = None,
        state: str | None = None,
        folder_ids: list[int] | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """
        Get legacy alerts.
        
        Args:
            dashboard_ids: Filter by dashboard IDs
            panel_id: Filter by panel ID
            query: Search query
            state: Filter by state (alerting, ok, pending, etc.)
            folder_ids: Filter by folder IDs
            limit: Maximum results
        
        Returns:
            List of alerts
        """
        params = {"limit": limit}
        
        if dashboard_ids:
            params["dashboardId"] = dashboard_ids
        if panel_id:
            params["panelId"] = panel_id
        if query:
            params["query"] = query
        if state:
            params["state"] = state
        if folder_ids:
            params["folderId"] = folder_ids
        
        return await self._request("GET", "alerts", params=params)
    
    async def pause_alert(self, alert_id: int, paused: bool = True) -> None:
        """Pause or unpause an alert."""
        await self._request(
            "POST",
            f"alerts/{alert_id}/pause",
            json_data={"paused": paused}
        )
    
    # =========================================================================
    # User/Org API
    # =========================================================================
    
    async def get_current_user(self) -> User:
        """Get current user info."""
        data = await self._request("GET", "user")
        return User(**data)
    
    async def get_current_org(self) -> Organization:
        """Get current organization info."""
        data = await self._request("GET", "org")
        return Organization(**data)
    
    async def get_health(self) -> dict[str, Any]:
        """Get Grafana health status."""
        return await self._request("GET", "health")
