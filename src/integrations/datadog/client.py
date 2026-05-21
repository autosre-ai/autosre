"""Datadog API client with rate limiting and error handling."""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel

from .models import (
    Dashboard,
    DashboardListResult,
    DashboardSummary,
    Event,
    EventQueryResult,
    Host,
    HostListResult,
    Log,
    LogQueryResult,
    MetricQueryResult,
    MetricSeries,
    Monitor,
    MonitorSearchResult,
    MonitorStatus,
)


class DatadogConfig(BaseModel):
    """Configuration for Datadog client."""
    api_key: str
    app_key: str
    site: str = "datadoghq.com"  # or datadoghq.eu, us3.datadoghq.com, etc.
    timeout: float = 30.0
    max_retries: int = 3
    rate_limit_requests: int = 300  # requests per minute
    rate_limit_window: int = 60  # seconds


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
            
            # Refill tokens based on elapsed time
            self.tokens = min(
                self.requests_per_window,
                self.tokens + (elapsed * self.requests_per_window / self.window_seconds)
            )
            self.last_update = now
            
            if self.tokens < 1:
                # Wait for a token to become available
                wait_time = (1 - self.tokens) * self.window_seconds / self.requests_per_window
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1


class DatadogError(Exception):
    """Base exception for Datadog API errors."""
    
    def __init__(self, message: str, status_code: int | None = None, response: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class DatadogAuthError(DatadogError):
    """Authentication error."""
    pass


class DatadogRateLimitError(DatadogError):
    """Rate limit exceeded."""
    
    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class DatadogNotFoundError(DatadogError):
    """Resource not found."""
    pass


class DatadogClient:
    """Async client for Datadog API."""
    
    def __init__(self, config: DatadogConfig):
        self.config = config
        self.base_url = f"https://api.{config.site}"
        self._client: httpx.AsyncClient | None = None
        self._rate_limiter = RateLimiter(
            config.rate_limit_requests,
            config.rate_limit_window
        )
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.timeout),
                headers={
                    "DD-API-KEY": self.config.api_key,
                    "DD-APPLICATION-KEY": self.config.app_key,
                    "Content-Type": "application/json",
                }
            )
        return self._client
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    async def __aenter__(self) -> "DatadogClient":
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json_data: dict | None = None,
        api_version: str = "v1",
    ) -> dict[str, Any]:
        """Make an API request with rate limiting and retry logic."""
        url = urljoin(self.base_url, f"/api/{api_version}/{endpoint}")
        
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
                    return response.json()
                elif response.status_code == 401:
                    raise DatadogAuthError(
                        "Invalid API key or application key",
                        status_code=401,
                        response=response.json() if response.content else None
                    )
                elif response.status_code == 403:
                    raise DatadogAuthError(
                        "Access forbidden - check API key permissions",
                        status_code=403,
                        response=response.json() if response.content else None
                    )
                elif response.status_code == 404:
                    raise DatadogNotFoundError(
                        f"Resource not found: {endpoint}",
                        status_code=404
                    )
                elif response.status_code == 429:
                    retry_after = int(response.headers.get("X-RateLimit-Reset", 60))
                    if attempt < self.config.max_retries - 1:
                        await asyncio.sleep(retry_after)
                        continue
                    raise DatadogRateLimitError(
                        "Rate limit exceeded",
                        retry_after=retry_after
                    )
                else:
                    error_body = response.json() if response.content else {}
                    raise DatadogError(
                        f"API error: {response.status_code} - {error_body.get('errors', 'Unknown error')}",
                        status_code=response.status_code,
                        response=error_body
                    )
                    
            except httpx.TimeoutException as e:
                last_error = DatadogError(f"Request timeout: {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
            except httpx.RequestError as e:
                last_error = DatadogError(f"Request error: {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
        
        raise last_error or DatadogError("Max retries exceeded")
    
    # =========================================================================
    # Metrics API
    # =========================================================================
    
    async def query_metrics(
        self,
        query: str,
        start: datetime | int,
        end: datetime | int,
    ) -> MetricQueryResult:
        """
        Query time series metrics.
        
        Args:
            query: Datadog metric query string (e.g., "avg:system.cpu.user{*}")
            start: Start time (datetime or Unix timestamp in seconds)
            end: End time (datetime or Unix timestamp in seconds)
        
        Returns:
            MetricQueryResult with time series data
        """
        if isinstance(start, datetime):
            start = int(start.timestamp())
        if isinstance(end, datetime):
            end = int(end.timestamp())
        
        params = {
            "query": query,
            "from": start,
            "to": end,
        }
        
        data = await self._request("GET", "query", params=params)
        return MetricQueryResult(**data)
    
    async def get_metric_metadata(self, metric_name: str) -> dict[str, Any]:
        """Get metadata for a metric."""
        return await self._request("GET", f"metrics/{metric_name}")
    
    async def list_active_metrics(
        self,
        from_time: datetime | int,
        host: str | None = None,
        tag_filter: str | None = None,
    ) -> list[str]:
        """
        List active metrics.
        
        Args:
            from_time: Start time for active metrics window
            host: Filter by host
            tag_filter: Filter by tag
        
        Returns:
            List of metric names
        """
        if isinstance(from_time, datetime):
            from_time = int(from_time.timestamp())
        
        params = {"from": from_time}
        if host:
            params["host"] = host
        if tag_filter:
            params["tag_filter"] = tag_filter
        
        data = await self._request("GET", "metrics", params=params)
        return data.get("metrics", [])
    
    # =========================================================================
    # Logs API
    # =========================================================================
    
    async def get_logs(
        self,
        query: str,
        start: datetime | str,
        end: datetime | str,
        limit: int = 100,
        sort: str = "timestamp",
        sort_order: str = "desc",
        cursor: str | None = None,
    ) -> LogQueryResult:
        """
        Search and retrieve logs.
        
        Args:
            query: Log search query (Datadog log query syntax)
            start: Start time (datetime or ISO string)
            end: End time (datetime or ISO string)
            limit: Maximum logs to return (max 1000)
            sort: Sort field
            sort_order: "asc" or "desc"
            cursor: Pagination cursor
        
        Returns:
            LogQueryResult with matching logs
        """
        if isinstance(start, datetime):
            start = start.isoformat()
        if isinstance(end, datetime):
            end = end.isoformat()
        
        json_data = {
            "filter": {
                "query": query,
                "from": start,
                "to": end,
            },
            "sort": f"{'-' if sort_order == 'desc' else ''}{sort}",
            "page": {
                "limit": min(limit, 1000),
            },
        }
        
        if cursor:
            json_data["page"]["cursor"] = cursor
        
        data = await self._request(
            "POST",
            "logs/events/search",
            json_data=json_data,
            api_version="v2"
        )
        return LogQueryResult(**data)
    
    async def get_all_logs(
        self,
        query: str,
        start: datetime | str,
        end: datetime | str,
        max_logs: int = 10000,
    ) -> list[Log]:
        """
        Get all logs matching a query, handling pagination.
        
        Args:
            query: Log search query
            start: Start time
            end: End time
            max_logs: Maximum total logs to retrieve
        
        Returns:
            List of all matching logs
        """
        all_logs: list[Log] = []
        cursor = None
        
        while len(all_logs) < max_logs:
            result = await self.get_logs(
                query=query,
                start=start,
                end=end,
                limit=min(1000, max_logs - len(all_logs)),
                cursor=cursor,
            )
            
            all_logs.extend(result.logs)
            cursor = result.next_cursor
            
            if not cursor or not result.logs:
                break
        
        return all_logs
    
    # =========================================================================
    # Events API
    # =========================================================================
    
    async def get_events(
        self,
        start: datetime | int,
        end: datetime | int,
        tags: list[str] | str | None = None,
        sources: list[str] | str | None = None,
        priority: str | None = None,
        unaggregated: bool = False,
    ) -> EventQueryResult:
        """
        Get events within a time range.
        
        Args:
            start: Start time
            end: End time
            tags: Filter by tags (comma-separated string or list)
            sources: Filter by sources
            priority: Filter by priority ("low" or "normal")
            unaggregated: Return unaggregated events
        
        Returns:
            EventQueryResult with matching events
        """
        if isinstance(start, datetime):
            start = int(start.timestamp())
        if isinstance(end, datetime):
            end = int(end.timestamp())
        
        params = {
            "start": start,
            "end": end,
        }
        
        if tags:
            params["tags"] = tags if isinstance(tags, str) else ",".join(tags)
        if sources:
            params["sources"] = sources if isinstance(sources, str) else ",".join(sources)
        if priority:
            params["priority"] = priority
        if unaggregated:
            params["unaggregated"] = "true"
        
        data = await self._request("GET", "events", params=params)
        return EventQueryResult(**data)
    
    async def post_event(
        self,
        title: str,
        text: str,
        tags: list[str] | None = None,
        alert_type: str = "info",
        priority: str = "normal",
        host: str | None = None,
        aggregation_key: str | None = None,
    ) -> Event:
        """
        Post a new event.
        
        Args:
            title: Event title
            text: Event body text
            tags: Event tags
            alert_type: Alert type (error, warning, info, success)
            priority: Priority (normal, low)
            host: Associated host
            aggregation_key: Key for grouping events
        
        Returns:
            Created Event
        """
        json_data = {
            "title": title,
            "text": text,
            "alert_type": alert_type,
            "priority": priority,
        }
        
        if tags:
            json_data["tags"] = tags
        if host:
            json_data["host"] = host
        if aggregation_key:
            json_data["aggregation_key"] = aggregation_key
        
        data = await self._request("POST", "events", json_data=json_data)
        return Event(**data.get("event", data))
    
    # =========================================================================
    # Monitors API
    # =========================================================================
    
    async def get_monitors(
        self,
        status: MonitorStatus | str | None = None,
        name: str | None = None,
        tags: list[str] | str | None = None,
        monitor_tags: list[str] | str | None = None,
        group_states: list[str] | None = None,
        page: int = 0,
        page_size: int = 100,
    ) -> list[Monitor]:
        """
        Get monitors with optional filtering.
        
        Args:
            status: Filter by status (OK, Alert, Warn, No Data)
            name: Filter by name (partial match)
            tags: Filter by scope tags
            monitor_tags: Filter by monitor tags
            group_states: Include specific group states
            page: Page number (0-indexed)
            page_size: Results per page
        
        Returns:
            List of monitors
        """
        params = {
            "page": page,
            "page_size": page_size,
        }
        
        if status:
            params["monitor_status"] = status.value if isinstance(status, MonitorStatus) else status
        if name:
            params["name"] = name
        if tags:
            params["tags"] = tags if isinstance(tags, str) else ",".join(tags)
        if monitor_tags:
            params["monitor_tags"] = monitor_tags if isinstance(monitor_tags, str) else ",".join(monitor_tags)
        if group_states:
            params["group_states"] = ",".join(group_states)
        
        data = await self._request("GET", "monitor", params=params)
        
        # API returns a list directly
        if isinstance(data, list):
            return [Monitor(**m) for m in data]
        return [Monitor(**m) for m in data.get("monitors", [])]
    
    async def get_monitor(self, monitor_id: int, group_states: list[str] | None = None) -> Monitor:
        """Get a specific monitor by ID."""
        params = {}
        if group_states:
            params["group_states"] = ",".join(group_states)
        
        data = await self._request("GET", f"monitor/{monitor_id}", params=params)
        return Monitor(**data)
    
    async def search_monitors(
        self,
        query: str | None = None,
        page: int = 0,
        per_page: int = 30,
        sort: str | None = None,
    ) -> MonitorSearchResult:
        """
        Search monitors using query syntax.
        
        Args:
            query: Search query (e.g., "status:alert type:metric")
            page: Page number
            per_page: Results per page
            sort: Sort field
        
        Returns:
            MonitorSearchResult with matches
        """
        params = {
            "page": page,
            "per_page": per_page,
        }
        
        if query:
            params["query"] = query
        if sort:
            params["sort"] = sort
        
        data = await self._request("GET", "monitor/search", params=params)
        return MonitorSearchResult(**data)
    
    async def mute_monitor(
        self,
        monitor_id: int,
        scope: str | None = None,
        end: datetime | int | None = None,
    ) -> Monitor:
        """Mute a monitor."""
        json_data = {}
        if scope:
            json_data["scope"] = scope
        if end:
            json_data["end"] = int(end.timestamp()) if isinstance(end, datetime) else end
        
        data = await self._request("POST", f"monitor/{monitor_id}/mute", json_data=json_data)
        return Monitor(**data)
    
    async def unmute_monitor(self, monitor_id: int, scope: str | None = None) -> Monitor:
        """Unmute a monitor."""
        json_data = {}
        if scope:
            json_data["scope"] = scope
        
        data = await self._request("POST", f"monitor/{monitor_id}/unmute", json_data=json_data)
        return Monitor(**data)
    
    # =========================================================================
    # Hosts API
    # =========================================================================
    
    async def get_hosts(
        self,
        filter_query: str | None = None,
        sort_field: str | None = None,
        sort_dir: str = "asc",
        start: int = 0,
        count: int = 100,
        include_muted_hosts_data: bool = True,
        include_hosts_metadata: bool = True,
    ) -> HostListResult:
        """
        Get list of hosts.
        
        Args:
            filter_query: Filter query string
            sort_field: Field to sort by
            sort_dir: Sort direction (asc/desc)
            start: Offset for pagination
            count: Number of hosts to return
            include_muted_hosts_data: Include mute info
            include_hosts_metadata: Include host metadata
        
        Returns:
            HostListResult with matching hosts
        """
        params = {
            "start": start,
            "count": count,
            "include_muted_hosts_data": str(include_muted_hosts_data).lower(),
            "include_hosts_metadata": str(include_hosts_metadata).lower(),
        }
        
        if filter_query:
            params["filter"] = filter_query
        if sort_field:
            params["sort_field"] = sort_field
            params["sort_dir"] = sort_dir
        
        data = await self._request("GET", "hosts", params=params)
        return HostListResult(**data)
    
    async def get_host_metrics(
        self,
        host: str,
        metrics: list[str] | None = None,
        start: datetime | int | None = None,
        end: datetime | int | None = None,
    ) -> dict[str, MetricSeries]:
        """
        Get metrics for a specific host.
        
        Args:
            host: Hostname to query
            metrics: List of metric names (defaults to common system metrics)
            start: Start time (defaults to 1 hour ago)
            end: End time (defaults to now)
        
        Returns:
            Dictionary mapping metric names to their series data
        """
        if metrics is None:
            metrics = [
                "system.cpu.user",
                "system.cpu.system",
                "system.mem.used",
                "system.mem.total",
                "system.load.1",
                "system.disk.used",
                "system.disk.total",
                "system.net.bytes_rcvd",
                "system.net.bytes_sent",
            ]
        
        if end is None:
            end = datetime.now()
        if start is None:
            start = end - timedelta(hours=1)
        
        results = {}
        for metric in metrics:
            query = f"avg:{metric}{{host:{host}}}"
            try:
                result = await self.query_metrics(query, start, end)
                if result.series:
                    results[metric] = result.series[0]
            except DatadogError:
                # Skip metrics that error (may not exist for this host)
                continue
        
        return results
    
    async def mute_host(
        self,
        hostname: str,
        end: datetime | int | None = None,
        message: str | None = None,
        override: bool = False,
    ) -> dict[str, Any]:
        """Mute a host."""
        json_data = {"hostname": hostname, "override": override}
        if end:
            json_data["end"] = int(end.timestamp()) if isinstance(end, datetime) else end
        if message:
            json_data["message"] = message
        
        return await self._request("POST", "host/mute", json_data=json_data)
    
    async def unmute_host(self, hostname: str) -> dict[str, Any]:
        """Unmute a host."""
        return await self._request("POST", "host/unmute", json_data={"hostname": hostname})
    
    # =========================================================================
    # Dashboards API
    # =========================================================================
    
    async def get_dashboards(
        self,
        filter_shared: bool | None = None,
        filter_deleted: bool = False,
    ) -> list[DashboardSummary]:
        """
        Get all dashboards.
        
        Args:
            filter_shared: Filter shared dashboards
            filter_deleted: Include deleted dashboards
        
        Returns:
            List of dashboard summaries
        """
        params = {}
        if filter_shared is not None:
            params["filter[shared]"] = str(filter_shared).lower()
        if filter_deleted:
            params["filter[deleted]"] = "true"
        
        data = await self._request("GET", "dashboard", params=params)
        result = DashboardListResult(**data)
        return result.dashboards
    
    async def get_dashboard(self, dashboard_id: str) -> Dashboard:
        """Get a specific dashboard."""
        data = await self._request("GET", f"dashboard/{dashboard_id}")
        return Dashboard(**data)
    
    async def search_dashboards(self, query: str) -> list[DashboardSummary]:
        """Search dashboards by title."""
        dashboards = await self.get_dashboards()
        query_lower = query.lower()
        return [d for d in dashboards if query_lower in d.title.lower()]
