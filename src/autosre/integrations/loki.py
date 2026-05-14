"""
Loki integration for AutoSRE V2.

Provides async client for Grafana Loki:
- Log queries (LogQL)
- Range queries
- Label discovery
- Log streaming
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, AsyncIterator

import httpx

from autosre.utils.logging import get_logger

from .base import (
    AuthenticatedIntegration,
    ConnectionConfig,
    HealthCheckResult,
    HealthStatus,
    IntegrationError,
    RetryConfig,
)

logger = get_logger(__name__)


class Direction(str, Enum):
    """Query direction."""

    FORWARD = "forward"
    BACKWARD = "backward"


class ResultType(str, Enum):
    """Query result type."""

    STREAMS = "streams"
    MATRIX = "matrix"
    VECTOR = "vector"


@dataclass
class LogEntry:
    """A single log entry."""

    timestamp: datetime
    line: str
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class LogStream:
    """A stream of log entries with common labels."""

    labels: dict[str, str]
    entries: list[LogEntry] = field(default_factory=list)


@dataclass
class MetricValue:
    """A metric value from LogQL metrics query."""

    labels: dict[str, str]
    value: float
    timestamp: datetime


@dataclass
class MetricSeries:
    """A time series of metric values."""

    labels: dict[str, str]
    values: list[tuple[datetime, float]] = field(default_factory=list)


@dataclass
class QueryResult:
    """Result of a Loki query."""

    result_type: ResultType
    streams: list[LogStream] = field(default_factory=list)
    metrics: list[MetricValue | MetricSeries] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def total_entries(self) -> int:
        """Total number of log entries."""
        return sum(len(s.entries) for s in self.streams)


@dataclass
class LabelInfo:
    """Label metadata."""

    name: str
    values: list[str] = field(default_factory=list)


class LokiClient(AuthenticatedIntegration):
    """
    Async Grafana Loki client.

    Features:
    - Log queries (instant and range)
    - Label discovery
    - Log streaming (tail)
    - Connection pooling
    - Automatic retries

    Usage:
        async with LokiClient("http://loki:3100") as loki:
            # Query logs
            result = await loki.query(
                '{job="api"} |= "error"',
                limit=100,
            )

            # Range query
            result = await loki.query_range(
                '{app="nginx"} | json | status >= 500',
                start=datetime.now() - timedelta(hours=1),
                end=datetime.now(),
            )

            # Get labels
            labels = await loki.get_labels()

            # Stream logs
            async for entry in loki.tail('{job="api"}'):
                print(entry.line)
    """

    def __init__(
        self,
        url: str,
        auth_token: str | None = None,
        api_key: str | None = None,
        org_id: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        verify_ssl: bool = True,
    ):
        """
        Initialize Loki client.

        Args:
            url: Loki server URL
            auth_token: Optional Bearer token
            api_key: Optional API key
            org_id: Optional X-Scope-OrgID header
            timeout: Request timeout in seconds
            max_retries: Number of retry attempts
            verify_ssl: Whether to verify SSL certificates
        """
        headers = {}
        if org_id:
            headers["X-Scope-OrgID"] = org_id

        connection_config = ConnectionConfig(
            base_url=url.rstrip("/"),
            timeout=timeout,
            verify_ssl=verify_ssl,
            headers=headers,
        )
        retry_config = RetryConfig(max_retries=max_retries)

        super().__init__(
            connection_config=connection_config,
            auth_token=auth_token,
            api_key=api_key,
            retry_config=retry_config,
        )

    @property
    def name(self) -> str:
        return "loki"

    def _parse_timestamp(self, ts: str) -> datetime:
        """Parse Loki timestamp (nanoseconds since epoch)."""
        # Loki returns nanoseconds as string
        ns = int(ts)
        return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc)

    def _parse_streams(self, data: list[dict[str, Any]]) -> list[LogStream]:
        """Parse streams from query result."""
        streams = []

        for stream_data in data:
            labels = stream_data.get("stream", {})
            entries = []

            for entry in stream_data.get("values", []):
                # Entry is [timestamp_ns, line]
                ts = self._parse_timestamp(entry[0])
                line = entry[1]
                entries.append(LogEntry(timestamp=ts, line=line, labels=labels))

            streams.append(LogStream(labels=labels, entries=entries))

        return streams

    def _parse_matrix(self, data: list[dict[str, Any]]) -> list[MetricSeries]:
        """Parse matrix result (range query metrics)."""
        series = []

        for item in data:
            labels = item.get("metric", {})
            values = []

            for v in item.get("values", []):
                # v is [timestamp, value]
                ts = datetime.fromtimestamp(float(v[0]), tz=timezone.utc)
                value = float(v[1])
                values.append((ts, value))

            series.append(MetricSeries(labels=labels, values=values))

        return series

    def _parse_vector(self, data: list[dict[str, Any]]) -> list[MetricValue]:
        """Parse vector result (instant query metrics)."""
        values = []

        for item in data:
            labels = item.get("metric", {})
            v = item.get("value", [0, "0"])
            ts = datetime.fromtimestamp(float(v[0]), tz=timezone.utc)
            value = float(v[1])
            values.append(MetricValue(labels=labels, value=value, timestamp=ts))

        return values

    async def query(
        self,
        query: str,
        time: datetime | None = None,
        limit: int = 100,
        direction: Direction = Direction.BACKWARD,
    ) -> QueryResult:
        """
        Execute an instant LogQL query.

        Args:
            query: LogQL query string
            time: Evaluation timestamp (default: now)
            limit: Maximum number of entries to return
            direction: Query direction (forward/backward)

        Returns:
            QueryResult with log streams or metric values
        """
        params: dict[str, Any] = {
            "query": query,
            "limit": limit,
            "direction": direction.value,
        }

        if time:
            # Loki expects nanoseconds
            params["time"] = str(int(time.timestamp() * 1e9))

        response = await self._request("GET", "/loki/api/v1/query", params=params)

        if response.get("status") != "success":
            raise IntegrationError(
                f"Query failed: {response.get('error', 'Unknown error')}",
                integration=self.name,
            )

        data = response.get("data", {})
        result_type = ResultType(data.get("resultType", "streams"))
        result = data.get("result", [])

        query_result = QueryResult(
            result_type=result_type,
            stats=data.get("stats", {}),
        )

        if result_type == ResultType.STREAMS:
            query_result.streams = self._parse_streams(result)
        elif result_type == ResultType.MATRIX:
            query_result.metrics = self._parse_matrix(result)
        elif result_type == ResultType.VECTOR:
            query_result.metrics = self._parse_vector(result)

        return query_result

    async def query_range(
        self,
        query: str,
        start: datetime,
        end: datetime,
        limit: int = 1000,
        step: str | None = None,
        direction: Direction = Direction.BACKWARD,
    ) -> QueryResult:
        """
        Execute a range LogQL query.

        Args:
            query: LogQL query string
            start: Start timestamp
            end: End timestamp
            limit: Maximum number of entries
            step: Query step (e.g., "15s", "1m") - required for metrics
            direction: Query direction

        Returns:
            QueryResult with log streams or metric series
        """
        params: dict[str, Any] = {
            "query": query,
            "start": str(int(start.timestamp() * 1e9)),
            "end": str(int(end.timestamp() * 1e9)),
            "limit": limit,
            "direction": direction.value,
        }

        if step:
            params["step"] = step

        response = await self._request("GET", "/loki/api/v1/query_range", params=params)

        if response.get("status") != "success":
            raise IntegrationError(
                f"Range query failed: {response.get('error', 'Unknown error')}",
                integration=self.name,
            )

        data = response.get("data", {})
        result_type = ResultType(data.get("resultType", "streams"))
        result = data.get("result", [])

        query_result = QueryResult(
            result_type=result_type,
            stats=data.get("stats", {}),
        )

        if result_type == ResultType.STREAMS:
            query_result.streams = self._parse_streams(result)
        elif result_type == ResultType.MATRIX:
            query_result.metrics = self._parse_matrix(result)
        elif result_type == ResultType.VECTOR:
            query_result.metrics = self._parse_vector(result)

        return query_result

    async def get_labels(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[str]:
        """
        Get all label names.

        Args:
            start: Start timestamp for label search
            end: End timestamp for label search

        Returns:
            List of label names
        """
        params = {}
        if start:
            params["start"] = str(int(start.timestamp() * 1e9))
        if end:
            params["end"] = str(int(end.timestamp() * 1e9))

        response = await self._request("GET", "/loki/api/v1/labels", params=params)

        if response.get("status") != "success":
            raise IntegrationError(
                f"Failed to get labels: {response.get('error', 'Unknown error')}",
                integration=self.name,
            )

        return response.get("data", [])

    async def get_label_values(
        self,
        label: str,
        start: datetime | None = None,
        end: datetime | None = None,
        query: str | None = None,
    ) -> list[str]:
        """
        Get values for a label.

        Args:
            label: Label name
            start: Start timestamp
            end: End timestamp
            query: Optional LogQL query to filter values

        Returns:
            List of label values
        """
        params = {}
        if start:
            params["start"] = str(int(start.timestamp() * 1e9))
        if end:
            params["end"] = str(int(end.timestamp() * 1e9))
        if query:
            params["query"] = query

        response = await self._request(
            "GET",
            f"/loki/api/v1/label/{label}/values",
            params=params,
        )

        if response.get("status") != "success":
            raise IntegrationError(
                f"Failed to get label values: {response.get('error', 'Unknown error')}",
                integration=self.name,
            )

        return response.get("data", [])

    async def get_series(
        self,
        match: list[str],
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[dict[str, str]]:
        """
        Get series (unique label sets) matching selectors.

        Args:
            match: List of log stream selectors
            start: Start timestamp
            end: End timestamp

        Returns:
            List of label sets
        """
        params: dict[str, Any] = {"match[]": match}
        if start:
            params["start"] = str(int(start.timestamp() * 1e9))
        if end:
            params["end"] = str(int(end.timestamp() * 1e9))

        response = await self._request("GET", "/loki/api/v1/series", params=params)

        if response.get("status") != "success":
            raise IntegrationError(
                f"Failed to get series: {response.get('error', 'Unknown error')}",
                integration=self.name,
            )

        return response.get("data", [])

    async def tail(
        self,
        query: str,
        delay_for: int = 0,
        limit: int = 100,
        start: datetime | None = None,
    ) -> AsyncIterator[LogEntry]:
        """
        Stream logs in real-time using WebSocket.

        Note: This is a simplified implementation that polls.
        For production, implement proper WebSocket streaming.

        Args:
            query: LogQL query string
            delay_for: Seconds to delay before streaming
            limit: Maximum entries per request
            start: Start timestamp

        Yields:
            LogEntry objects as they arrive
        """
        import asyncio

        last_ts = start or datetime.now(timezone.utc)
        seen = set()

        while True:
            try:
                result = await self.query_range(
                    query=query,
                    start=last_ts,
                    end=datetime.now(timezone.utc),
                    limit=limit,
                    direction=Direction.FORWARD,
                )

                for stream in result.streams:
                    for entry in stream.entries:
                        # Create unique key to avoid duplicates
                        key = (entry.timestamp.isoformat(), entry.line[:100])
                        if key not in seen:
                            seen.add(key)
                            yield entry

                            # Update last timestamp
                            if entry.timestamp > last_ts:
                                last_ts = entry.timestamp

                # Keep seen set bounded
                if len(seen) > 10000:
                    seen = set(list(seen)[-5000:])

            except Exception as e:
                logger.warning(f"Tail error, continuing: {e}")

            await asyncio.sleep(delay_for or 1)

    async def validate_query(self, query: str) -> tuple[bool, str | None]:
        """
        Validate a LogQL query without executing it.

        Args:
            query: LogQL query to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not query.strip():
            return False, "Query is empty"

        # Check basic syntax
        if not query.strip().startswith("{"):
            # Might be a metric query, still valid
            pass

        brace_count = query.count("{") - query.count("}")
        if brace_count != 0:
            return False, "Unbalanced curly braces"

        paren_count = query.count("(") - query.count(")")
        if paren_count != 0:
            return False, "Unbalanced parentheses"

        # Try a limited query to validate
        try:
            result = await self.query(query, limit=1)
            return True, None
        except IntegrationError as e:
            return False, str(e)

    async def health_check(self) -> HealthCheckResult:
        """Check Loki health."""
        start = datetime.now(timezone.utc)
        try:
            response = await self._request("GET", "/ready")
            latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000

            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message="Loki is ready",
                latency_ms=latency,
            )
        except Exception as e:
            latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                latency_ms=latency,
            )

    async def get_build_info(self) -> dict[str, Any]:
        """Get Loki build information."""
        response = await self._request("GET", "/loki/api/v1/status/buildinfo")
        return response

    async def get_config(self) -> dict[str, Any]:
        """Get Loki configuration."""
        response = await self._request("GET", "/config")
        return response
