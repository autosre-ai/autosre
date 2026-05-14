"""
Prometheus integration for AutoSRE V2.

Provides async Prometheus querying with support for:
- Instant and range queries
- Query building helpers
- Result parsing and normalization
- Connection pooling and retries
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, Field

from autosre.utils.config import PrometheusConfig, get_config
from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class MetricType(str, Enum):
    """Prometheus metric types."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    UNKNOWN = "unknown"


@dataclass
class MetricSample:
    """A single metric sample."""

    timestamp: datetime
    value: float

    @classmethod
    def from_prometheus(cls, data: list) -> MetricSample:
        """Parse from Prometheus [timestamp, value] format."""
        ts, val = data
        return cls(
            timestamp=datetime.fromtimestamp(ts, tz=timezone.utc),
            value=float(val),
        )


@dataclass
class MetricResult:
    """A single metric series with labels and value(s)."""

    metric: dict[str, str]
    value: float | None = None
    values: list[MetricSample] = field(default_factory=list)

    @property
    def name(self) -> str:
        """Get metric name."""
        return self.metric.get("__name__", "unknown")

    @property
    def labels(self) -> dict[str, str]:
        """Get labels without __name__."""
        return {k: v for k, v in self.metric.items() if k != "__name__"}

    def label(self, key: str, default: str = "") -> str:
        """Get a specific label value."""
        return self.metric.get(key, default)

    @classmethod
    def from_instant(cls, data: dict) -> MetricResult:
        """Parse instant query result."""
        metric = data.get("metric", {})
        value_data = data.get("value", [])

        value = float(value_data[1]) if len(value_data) >= 2 else None
        return cls(metric=metric, value=value)

    @classmethod
    def from_range(cls, data: dict) -> MetricResult:
        """Parse range query result."""
        metric = data.get("metric", {})
        values_data = data.get("values", [])

        values = [MetricSample.from_prometheus(v) for v in values_data]

        # Also set value to latest
        latest_value = values[-1].value if values else None

        return cls(metric=metric, value=latest_value, values=values)


@dataclass
class RangeVector:
    """Collection of metric results from a range query."""

    results: list[MetricResult]
    query: str
    start: datetime
    end: datetime
    step: str

    @property
    def is_empty(self) -> bool:
        """Check if no results."""
        return len(self.results) == 0

    def filter_by_label(self, key: str, value: str) -> list[MetricResult]:
        """Filter results by label value."""
        return [r for r in self.results if r.label(key) == value]

    def get_series(self, labels: dict[str, str]) -> MetricResult | None:
        """Get a specific series by labels."""
        for result in self.results:
            if all(result.label(k) == v for k, v in labels.items()):
                return result
        return None


class QueryResponse(BaseModel):
    """Prometheus API response."""

    status: str
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    error_type: str | None = None
    warnings: list[str] = Field(default_factory=list)


class PrometheusClient:
    """
    Async Prometheus client.

    Provides methods for querying metrics with automatic retries
    and result parsing.
    """

    def __init__(self, config: PrometheusConfig | None = None):
        """
        Initialize Prometheus client.

        Args:
            config: Prometheus configuration. Uses global config if not provided.
        """
        self.config = config or get_config().prometheus
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            auth = None
            if self.config.basic_auth_user and self.config.basic_auth_password:
                auth = httpx.BasicAuth(
                    self.config.basic_auth_user,
                    self.config.basic_auth_password.get_secret_value(),
                )

            self._client = httpx.AsyncClient(
                base_url=self.config.url,
                auth=auth,
                verify=self.config.verify_ssl,
                timeout=self.config.timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _query_api(
        self,
        endpoint: str,
        params: dict[str, Any],
    ) -> QueryResponse:
        """Execute API query with retry logic."""
        client = await self._get_client()

        for attempt in range(3):
            try:
                response = await client.get(endpoint, params=params)
                response.raise_for_status()

                data = response.json()
                result = QueryResponse(**data)

                if result.status != "success":
                    logger.warning(
                        "Prometheus query returned non-success",
                        status=result.status,
                        error=result.error,
                    )

                return result

            except httpx.HTTPStatusError as e:
                logger.error(
                    "Prometheus HTTP error",
                    status_code=e.response.status_code,
                    attempt=attempt + 1,
                )
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)

            except Exception as e:
                logger.error(
                    "Prometheus query error",
                    error=str(e),
                    attempt=attempt + 1,
                )
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)

        raise RuntimeError("Failed to query Prometheus after retries")

    async def query(
        self,
        query: str,
        time: datetime | None = None,
    ) -> list[MetricResult]:
        """
        Execute instant query.

        Args:
            query: PromQL query string
            time: Evaluation timestamp (default: now)

        Returns:
            List of metric results
        """
        params: dict[str, Any] = {"query": query}
        if time:
            params["time"] = time.timestamp()

        logger.debug("Executing instant query", query=query)

        response = await self._query_api("/api/v1/query", params)

        if response.status != "success":
            return []

        result_type = response.data.get("resultType")
        results = response.data.get("result", [])

        if result_type == "vector":
            return [MetricResult.from_instant(r) for r in results]
        elif result_type == "scalar":
            return [MetricResult(metric={}, value=float(results[1]))]

        return []

    async def query_range(
        self,
        query: str,
        start: datetime | None = None,
        end: datetime | None = None,
        step: str | None = None,
        duration: timedelta | None = None,
    ) -> RangeVector:
        """
        Execute range query.

        Args:
            query: PromQL query string
            start: Start time (default: end - duration)
            end: End time (default: now)
            step: Query step (default: from config)
            duration: Time range duration (default: 1 hour)

        Returns:
            RangeVector with results
        """
        # Set defaults
        if end is None:
            end = datetime.now(timezone.utc)

        if duration is None:
            duration = timedelta(hours=1)

        if start is None:
            start = end - duration

        if step is None:
            step = self.config.default_step

        params = {
            "query": query,
            "start": start.timestamp(),
            "end": end.timestamp(),
            "step": step,
        }

        logger.debug(
            "Executing range query",
            query=query,
            start=start.isoformat(),
            end=end.isoformat(),
            step=step,
        )

        response = await self._query_api("/api/v1/query_range", params)

        if response.status != "success":
            return RangeVector(
                results=[],
                query=query,
                start=start,
                end=end,
                step=step,
            )

        results = response.data.get("result", [])

        return RangeVector(
            results=[MetricResult.from_range(r) for r in results],
            query=query,
            start=start,
            end=end,
            step=step,
        )

    async def get_metric_metadata(self, metric: str) -> dict[str, Any]:
        """Get metadata for a metric."""
        response = await self._query_api(
            "/api/v1/metadata",
            {"metric": metric},
        )

        if response.status != "success":
            return {}

        data = response.data.get("data", {})
        return data.get(metric, [{}])[0] if metric in data else {}

    async def get_labels(self, label: str = "__name__") -> list[str]:
        """Get all values for a label."""
        response = await self._query_api(
            f"/api/v1/label/{label}/values",
            {},
        )

        if response.status != "success":
            return []

        return response.data.get("data", [])

    async def get_series(
        self,
        match: list[str],
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[dict[str, str]]:
        """Get all series matching selectors."""
        params: dict[str, Any] = {"match[]": match}
        if start:
            params["start"] = start.timestamp()
        if end:
            params["end"] = end.timestamp()

        response = await self._query_api("/api/v1/series", params)

        if response.status != "success":
            return []

        return response.data.get("data", [])

    # Common query helpers

    async def get_error_rate(
        self,
        service: str,
        duration: str = "5m",
        namespace: str | None = None,
    ) -> float | None:
        """
        Get error rate for a service.

        Tries common error rate metric patterns.
        """
        label_selector = f'service="{service}"'
        if namespace:
            label_selector += f', namespace="{namespace}"'

        # Try different common patterns
        queries = [
            # Standard rate of errors
            f'sum(rate(http_requests_total{{{label_selector}, status=~"5.."}}[{duration}])) / sum(rate(http_requests_total{{{label_selector}}}[{duration}]))',
            # Alternative naming
            f'sum(rate(http_server_requests_seconds_count{{{label_selector}, status=~"5.."}}[{duration}])) / sum(rate(http_server_requests_seconds_count{{{label_selector}}}[{duration}]))',
            # gRPC style
            f'sum(rate(grpc_server_handled_total{{{label_selector}, grpc_code!="OK"}}[{duration}])) / sum(rate(grpc_server_handled_total{{{label_selector}}}[{duration}]))',
        ]

        for query in queries:
            results = await self.query(query)
            if results and results[0].value is not None:
                return results[0].value

        return None

    async def get_latency_percentile(
        self,
        service: str,
        percentile: float = 0.99,
        duration: str = "5m",
        namespace: str | None = None,
    ) -> float | None:
        """
        Get latency percentile for a service.

        Uses histogram_quantile for histogram metrics.
        """
        label_selector = f'service="{service}"'
        if namespace:
            label_selector += f', namespace="{namespace}"'

        # Try common histogram patterns
        queries = [
            f'histogram_quantile({percentile}, sum(rate(http_request_duration_seconds_bucket{{{label_selector}}}[{duration}])) by (le))',
            f'histogram_quantile({percentile}, sum(rate(http_server_requests_seconds_bucket{{{label_selector}}}[{duration}])) by (le))',
        ]

        for query in queries:
            results = await self.query(query)
            if results and results[0].value is not None:
                return results[0].value

        return None

    async def get_request_rate(
        self,
        service: str,
        duration: str = "5m",
        namespace: str | None = None,
    ) -> float | None:
        """Get request rate (QPS) for a service."""
        label_selector = f'service="{service}"'
        if namespace:
            label_selector += f', namespace="{namespace}"'

        queries = [
            f'sum(rate(http_requests_total{{{label_selector}}}[{duration}]))',
            f'sum(rate(http_server_requests_seconds_count{{{label_selector}}}[{duration}]))',
        ]

        for query in queries:
            results = await self.query(query)
            if results and results[0].value is not None:
                return results[0].value

        return None

    async def get_resource_usage(
        self,
        pod_pattern: str,
        namespace: str,
        duration: str = "5m",
    ) -> dict[str, Any]:
        """
        Get resource usage for pods matching pattern.

        Returns CPU and memory metrics.
        """
        results = {}

        # CPU usage
        cpu_query = f'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}", pod=~"{pod_pattern}"}}[{duration}])) by (pod)'
        cpu_results = await self.query(cpu_query)
        results["cpu"] = {
            r.label("pod"): r.value
            for r in cpu_results
            if r.value is not None
        }

        # Memory usage
        mem_query = f'sum(container_memory_working_set_bytes{{namespace="{namespace}", pod=~"{pod_pattern}"}}) by (pod)'
        mem_results = await self.query(mem_query)
        results["memory"] = {
            r.label("pod"): r.value
            for r in mem_results
            if r.value is not None
        }

        return results

    async def check_connection(self) -> bool:
        """Check if Prometheus is reachable."""
        try:
            response = await self._query_api("/api/v1/status/buildinfo", {})
            return response.status == "success"
        except Exception as e:
            logger.warning("Prometheus connection check failed", error=str(e))
            return False


# Module-level convenience functions
_default_client: PrometheusClient | None = None


def get_client() -> PrometheusClient:
    """Get the default Prometheus client."""
    global _default_client
    if _default_client is None:
        _default_client = PrometheusClient()
    return _default_client


async def query(query_str: str, **kwargs) -> list[MetricResult]:
    """Execute instant query using default client."""
    return await get_client().query(query_str, **kwargs)


async def query_range(query_str: str, **kwargs) -> RangeVector:
    """Execute range query using default client."""
    return await get_client().query_range(query_str, **kwargs)
