"""Prometheus API client with rate limiting and error handling."""

import asyncio
import time
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel

from .models import (
    Alert,
    AlertsResponse,
    BuildInfo,
    MatrixResult,
    MetricMetadata,
    QueryResponse,
    RangeSample,
    RuleGroup,
    RulesResponse,
    RuntimeInfo,
    ScalarResult,
    Target,
    TargetHealth,
    TargetsResponse,
    VectorResult,
    VectorSample,
)


class PrometheusConfig(BaseModel):
    """Configuration for Prometheus client."""
    url: str  # Base URL (e.g., http://prometheus:9090)
    username: str | None = None  # Basic auth username
    password: str | None = None  # Basic auth password
    bearer_token: str | None = None  # Bearer token auth
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


class PrometheusError(Exception):
    """Base exception for Prometheus API errors."""
    
    def __init__(self, message: str, status_code: int | None = None, response: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class PrometheusAuthError(PrometheusError):
    """Authentication error."""
    pass


class PrometheusQueryError(PrometheusError):
    """Query execution error."""
    
    def __init__(self, message: str, error_type: str | None = None):
        super().__init__(message)
        self.error_type = error_type


class PrometheusTimeoutError(PrometheusError):
    """Query timeout error."""
    pass


class PrometheusClient:
    """Async client for Prometheus API."""
    
    def __init__(self, config: PrometheusConfig):
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
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            
            # Auth
            auth = None
            if self.config.bearer_token:
                headers["Authorization"] = f"Bearer {self.config.bearer_token}"
            elif self.config.username and self.config.password:
                auth = httpx.BasicAuth(self.config.username, self.config.password)
            
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
    
    async def __aenter__(self) -> "PrometheusClient":
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        data: dict | None = None,
    ) -> dict[str, Any]:
        """Make an API request with rate limiting and retry logic."""
        url = urljoin(self.base_url, f"/api/v1/{endpoint}")
        
        last_error = None
        for attempt in range(self.config.max_retries):
            await self._rate_limiter.acquire()
            
            try:
                response = await self.client.request(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                )
                
                result = response.json()
                
                if response.status_code == 200:
                    if result.get("status") == "error":
                        raise PrometheusQueryError(
                            result.get("error", "Unknown query error"),
                            error_type=result.get("errorType")
                        )
                    return result
                elif response.status_code == 401:
                    raise PrometheusAuthError(
                        "Invalid credentials",
                        status_code=401,
                    )
                elif response.status_code == 403:
                    raise PrometheusAuthError(
                        "Access forbidden",
                        status_code=403,
                    )
                elif response.status_code == 422:
                    # Unprocessable entity - bad query
                    raise PrometheusQueryError(
                        result.get("error", "Invalid query"),
                        error_type=result.get("errorType")
                    )
                elif response.status_code == 503:
                    # Service unavailable - might be temporary
                    if attempt < self.config.max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    raise PrometheusError(
                        "Prometheus service unavailable",
                        status_code=503,
                    )
                else:
                    raise PrometheusError(
                        f"API error: {response.status_code} - {result.get('error', 'Unknown error')}",
                        status_code=response.status_code,
                        response=result,
                    )
                    
            except httpx.TimeoutException as e:
                last_error = PrometheusTimeoutError(f"Request timeout: {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
            except httpx.RequestError as e:
                last_error = PrometheusError(f"Request error: {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
        
        raise last_error or PrometheusError("Max retries exceeded")
    
    # =========================================================================
    # Query API
    # =========================================================================
    
    async def query(
        self,
        promql: str,
        time: datetime | float | None = None,
        timeout: str | None = None,
    ) -> QueryResponse:
        """
        Execute an instant query.
        
        Args:
            promql: PromQL expression
            time: Evaluation timestamp (defaults to now)
            timeout: Evaluation timeout
        
        Returns:
            QueryResponse with vector or scalar result
        """
        params: dict[str, Any] = {"query": promql}
        
        if time is not None:
            if isinstance(time, datetime):
                params["time"] = time.timestamp()
            else:
                params["time"] = time
        
        if timeout:
            params["timeout"] = timeout
        
        data = await self._request("POST", "query", data=params)
        
        # Parse result based on type
        result_data = data.get("data", {})
        result_type = result_data.get("resultType")
        
        if result_type == "vector":
            parsed_data = VectorResult(
                result=[VectorSample(**s) for s in result_data.get("result", [])]
            )
        elif result_type == "matrix":
            parsed_data = MatrixResult(
                result=[RangeSample(**s) for s in result_data.get("result", [])]
            )
        elif result_type == "scalar":
            parsed_data = ScalarResult(result=result_data.get("result", [0, "0"]))
        else:
            parsed_data = result_data
        
        return QueryResponse(
            status=data.get("status", "success"),
            data=parsed_data,
            warnings=data.get("warnings", []),
        )
    
    async def query_range(
        self,
        promql: str,
        start: datetime | float,
        end: datetime | float,
        step: str | float | None = None,
        timeout: str | None = None,
    ) -> QueryResponse:
        """
        Execute a range query.
        
        Args:
            promql: PromQL expression
            start: Start time
            end: End time
            step: Query resolution step (duration string or seconds)
            timeout: Evaluation timeout
        
        Returns:
            QueryResponse with matrix result
        """
        if isinstance(start, datetime):
            start = start.timestamp()
        if isinstance(end, datetime):
            end = end.timestamp()
        
        # Auto-calculate step if not provided
        if step is None:
            duration = end - start
            if duration <= 3600:  # 1 hour
                step = "15s"
            elif duration <= 86400:  # 1 day
                step = "1m"
            elif duration <= 604800:  # 1 week
                step = "5m"
            else:
                step = "1h"
        
        params: dict[str, Any] = {
            "query": promql,
            "start": start,
            "end": end,
            "step": step,
        }
        
        if timeout:
            params["timeout"] = timeout
        
        data = await self._request("POST", "query_range", data=params)
        
        result_data = data.get("data", {})
        parsed_data = MatrixResult(
            result=[RangeSample(**s) for s in result_data.get("result", [])]
        )
        
        return QueryResponse(
            status=data.get("status", "success"),
            data=parsed_data,
            warnings=data.get("warnings", []),
        )
    
    async def query_exemplars(
        self,
        promql: str,
        start: datetime | float,
        end: datetime | float,
    ) -> dict[str, Any]:
        """Query exemplars for a PromQL expression."""
        if isinstance(start, datetime):
            start = start.timestamp()
        if isinstance(end, datetime):
            end = end.timestamp()
        
        params = {
            "query": promql,
            "start": start,
            "end": end,
        }
        
        return await self._request("POST", "query_exemplars", data=params)
    
    # =========================================================================
    # Alerts API
    # =========================================================================
    
    async def get_alerts(self) -> list[Alert]:
        """Get all active alerts."""
        data = await self._request("GET", "alerts")
        response = AlertsResponse(**data)
        return response.alerts
    
    async def get_alerting_alerts(self) -> list[Alert]:
        """Get only firing alerts."""
        alerts = await self.get_alerts()
        return [a for a in alerts if a.state.value == "firing"]
    
    async def get_pending_alerts(self) -> list[Alert]:
        """Get only pending alerts."""
        alerts = await self.get_alerts()
        return [a for a in alerts if a.state.value == "pending"]
    
    # =========================================================================
    # Rules API
    # =========================================================================
    
    async def get_rules(self, type_filter: str | None = None) -> list[RuleGroup]:
        """
        Get all rules.
        
        Args:
            type_filter: Filter by type ("alert" or "record")
        
        Returns:
            List of rule groups
        """
        params = {}
        if type_filter:
            params["type"] = type_filter
        
        data = await self._request("GET", "rules", params=params)
        response = RulesResponse(**data)
        return response.groups
    
    async def get_alerting_rules(self) -> list[RuleGroup]:
        """Get only alerting rules."""
        return await self.get_rules(type_filter="alert")
    
    async def get_recording_rules(self) -> list[RuleGroup]:
        """Get only recording rules."""
        return await self.get_rules(type_filter="record")
    
    # =========================================================================
    # Targets API
    # =========================================================================
    
    async def get_targets(
        self,
        state: str | None = None,
        scrape_pool: str | None = None,
    ) -> TargetsResponse:
        """
        Get all scrape targets.
        
        Args:
            state: Filter by state ("active", "dropped", "any")
            scrape_pool: Filter by scrape pool
        
        Returns:
            TargetsResponse with active and dropped targets
        """
        params = {}
        if state:
            params["state"] = state
        if scrape_pool:
            params["scrapePool"] = scrape_pool
        
        data = await self._request("GET", "targets", params=params)
        return TargetsResponse(**data)
    
    async def get_active_targets(self) -> list[Target]:
        """Get active targets."""
        response = await self.get_targets(state="active")
        return response.active_targets
    
    async def get_down_targets(self) -> list[Target]:
        """Get targets that are down."""
        targets = await self.get_active_targets()
        return [t for t in targets if t.health == TargetHealth.DOWN]
    
    async def get_targets_by_job(self, job: str) -> list[Target]:
        """Get targets for a specific job."""
        targets = await self.get_active_targets()
        return [t for t in targets if t.job == job]
    
    async def get_target_metadata(
        self,
        match_target: str | None = None,
        metric: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get target metadata."""
        params = {}
        if match_target:
            params["match_target"] = match_target
        if metric:
            params["metric"] = metric
        if limit:
            params["limit"] = limit
        
        data = await self._request("GET", "targets/metadata", params=params)
        return data.get("data", [])
    
    # =========================================================================
    # Series API
    # =========================================================================
    
    async def get_series(
        self,
        match: list[str],
        start: datetime | float | None = None,
        end: datetime | float | None = None,
    ) -> list[dict[str, str]]:
        """
        Get time series matching label selectors.
        
        Args:
            match: List of series selectors
            start: Start time
            end: End time
        
        Returns:
            List of label sets
        """
        params: dict[str, Any] = {"match[]": match}
        
        if start:
            params["start"] = start.timestamp() if isinstance(start, datetime) else start
        if end:
            params["end"] = end.timestamp() if isinstance(end, datetime) else end
        
        data = await self._request("POST", "series", data=params)
        return data.get("data", [])
    
    async def delete_series(
        self,
        match: list[str],
        start: datetime | float | None = None,
        end: datetime | float | None = None,
    ) -> None:
        """Delete time series matching label selectors."""
        params: dict[str, Any] = {"match[]": match}
        
        if start:
            params["start"] = start.timestamp() if isinstance(start, datetime) else start
        if end:
            params["end"] = end.timestamp() if isinstance(end, datetime) else end
        
        await self._request("POST", "admin/tsdb/delete_series", data=params)
    
    # =========================================================================
    # Labels API
    # =========================================================================
    
    async def get_labels(
        self,
        match: list[str] | None = None,
        start: datetime | float | None = None,
        end: datetime | float | None = None,
    ) -> list[str]:
        """
        Get label names.
        
        Args:
            match: Optional series selectors to filter labels
            start: Start time
            end: End time
        
        Returns:
            List of label names
        """
        params: dict[str, Any] = {}
        
        if match:
            params["match[]"] = match
        if start:
            params["start"] = start.timestamp() if isinstance(start, datetime) else start
        if end:
            params["end"] = end.timestamp() if isinstance(end, datetime) else end
        
        data = await self._request("GET", "labels", params=params)
        return data.get("data", [])
    
    async def get_label_values(
        self,
        label_name: str,
        match: list[str] | None = None,
        start: datetime | float | None = None,
        end: datetime | float | None = None,
    ) -> list[str]:
        """
        Get values for a label.
        
        Args:
            label_name: Label name
            match: Optional series selectors
            start: Start time
            end: End time
        
        Returns:
            List of label values
        """
        params: dict[str, Any] = {}
        
        if match:
            params["match[]"] = match
        if start:
            params["start"] = start.timestamp() if isinstance(start, datetime) else start
        if end:
            params["end"] = end.timestamp() if isinstance(end, datetime) else end
        
        data = await self._request("GET", f"label/{label_name}/values", params=params)
        return data.get("data", [])
    
    # =========================================================================
    # Metadata API
    # =========================================================================
    
    async def get_metric_metadata(
        self,
        metric: str | None = None,
        limit: int | None = None,
    ) -> dict[str, list[MetricMetadata]]:
        """
        Get metric metadata.
        
        Args:
            metric: Filter by metric name
            limit: Maximum entries per metric
        
        Returns:
            Dictionary mapping metric names to metadata
        """
        params = {}
        if metric:
            params["metric"] = metric
        if limit:
            params["limit"] = limit
        
        data = await self._request("GET", "metadata", params=params)
        result = {}
        for name, entries in data.get("data", {}).items():
            result[name] = [MetricMetadata(**e) for e in entries]
        return result
    
    # =========================================================================
    # Status API
    # =========================================================================
    
    async def get_build_info(self) -> BuildInfo:
        """Get Prometheus build information."""
        data = await self._request("GET", "status/buildinfo")
        return BuildInfo(**data.get("data", {}))
    
    async def get_runtime_info(self) -> RuntimeInfo:
        """Get Prometheus runtime information."""
        data = await self._request("GET", "status/runtimeinfo")
        return RuntimeInfo(**data.get("data", {}))
    
    async def get_config(self) -> str:
        """Get current Prometheus configuration."""
        data = await self._request("GET", "status/config")
        return data.get("data", {}).get("yaml", "")
    
    async def get_flags(self) -> dict[str, str]:
        """Get Prometheus command line flags."""
        data = await self._request("GET", "status/flags")
        return data.get("data", {})
    
    async def get_tsdb_status(self) -> dict[str, Any]:
        """Get TSDB status."""
        data = await self._request("GET", "status/tsdb")
        return data.get("data", {})
    
    async def get_wal_replay_status(self) -> dict[str, Any]:
        """Get WAL replay status."""
        data = await self._request("GET", "status/walreplay")
        return data.get("data", {})
    
    async def ready(self) -> bool:
        """Check if Prometheus is ready."""
        try:
            url = urljoin(self.base_url, "/-/ready")
            response = await self.client.get(url)
            return response.status_code == 200
        except Exception:
            return False
    
    async def healthy(self) -> bool:
        """Check if Prometheus is healthy."""
        try:
            url = urljoin(self.base_url, "/-/healthy")
            response = await self.client.get(url)
            return response.status_code == 200
        except Exception:
            return False
    
    # =========================================================================
    # Admin API
    # =========================================================================
    
    async def reload_config(self) -> bool:
        """Trigger configuration reload."""
        try:
            url = urljoin(self.base_url, "/-/reload")
            response = await self.client.post(url)
            return response.status_code == 200
        except Exception:
            return False
    
    async def quit(self) -> bool:
        """Trigger graceful shutdown."""
        try:
            url = urljoin(self.base_url, "/-/quit")
            response = await self.client.post(url)
            return response.status_code == 200
        except Exception:
            return False
    
    async def snapshot(self, skip_head: bool = False) -> str:
        """
        Create TSDB snapshot.
        
        Args:
            skip_head: Skip data in head block
        
        Returns:
            Snapshot name
        """
        params = {}
        if skip_head:
            params["skip_head"] = "true"
        
        data = await self._request("POST", "admin/tsdb/snapshot", params=params)
        return data.get("data", {}).get("name", "")
    
    async def clean_tombstones(self) -> None:
        """Remove deleted data from disk."""
        await self._request("POST", "admin/tsdb/clean_tombstones")
