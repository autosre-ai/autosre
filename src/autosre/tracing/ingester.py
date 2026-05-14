"""
Trace Ingester for AutoSRE V2.

Fetches and normalizes traces from various backends:
- Jaeger
- OpenTelemetry (OTLP)
- Zipkin
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, AsyncIterator, Optional, Sequence
from urllib.parse import urlencode, quote

import httpx
from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger
from .models import Span, Trace, SpanKind, SpanStatus

logger = get_logger(__name__)


@dataclass
class IngesterConfig:
    """Configuration for trace ingestion."""
    
    # Backend URLs
    jaeger_url: str = "http://localhost:16686"
    otlp_url: str = "http://localhost:4318"
    zipkin_url: str = "http://localhost:9411"
    
    # Query settings
    default_lookback_hours: int = 1
    max_traces_per_query: int = 100
    query_timeout_seconds: float = 30.0
    
    # Retry settings
    retry_attempts: int = 3
    retry_base_delay: float = 1.0
    
    # Caching
    enable_cache: bool = True
    cache_ttl_seconds: float = 60.0
    
    # Processing
    batch_size: int = 50
    max_concurrent_fetches: int = 5


@dataclass
class TraceFilter:
    """Filter criteria for trace queries."""
    
    service: Optional[str] = None
    operation: Optional[str] = None
    tags: dict[str, str] = field(default_factory=dict)
    
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    min_duration_ms: Optional[float] = None
    max_duration_ms: Optional[float] = None
    
    limit: int = 100
    
    # Error filtering
    has_error: Optional[bool] = None
    
    def to_jaeger_params(self) -> dict[str, Any]:
        """Convert to Jaeger API query parameters."""
        params: dict[str, Any] = {}
        
        if self.service:
            params["service"] = self.service
        if self.operation:
            params["operation"] = self.operation
        
        for key, value in self.tags.items():
            params[f"tag:{key}"] = value
        
        if self.start_time:
            params["start"] = int(self.start_time.timestamp() * 1_000_000)
        if self.end_time:
            params["end"] = int(self.end_time.timestamp() * 1_000_000)
        
        if self.min_duration_ms:
            params["minDuration"] = f"{int(self.min_duration_ms * 1000)}us"
        if self.max_duration_ms:
            params["maxDuration"] = f"{int(self.max_duration_ms * 1000)}us"
        
        params["limit"] = self.limit
        
        return params
    
    def to_zipkin_params(self) -> dict[str, Any]:
        """Convert to Zipkin API query parameters."""
        params: dict[str, Any] = {}
        
        if self.service:
            params["serviceName"] = self.service
        if self.operation:
            params["spanName"] = self.operation
        
        if self.start_time and self.end_time:
            params["endTs"] = int(self.end_time.timestamp() * 1000)
            params["lookback"] = int((self.end_time - self.start_time).total_seconds() * 1000)
        elif self.end_time:
            params["endTs"] = int(self.end_time.timestamp() * 1000)
        
        if self.min_duration_ms:
            params["minDuration"] = int(self.min_duration_ms * 1000)
        
        params["limit"] = self.limit
        
        # Tags as annotation query
        if self.tags:
            params["annotationQuery"] = " and ".join(f'{k}="{v}"' for k, v in self.tags.items())
        
        return params


class TraceFetcher(ABC):
    """Abstract base class for trace fetchers."""
    
    def __init__(self, config: Optional[IngesterConfig] = None):
        self.config = config or IngesterConfig()
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.config.query_timeout_seconds,
            )
        return self._client
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def __aenter__(self) -> "TraceFetcher":
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
    
    @abstractmethod
    async def fetch_trace(self, trace_id: str) -> Optional[Trace]:
        """Fetch a single trace by ID."""
        ...
    
    @abstractmethod
    async def fetch_traces(
        self,
        filter: Optional[TraceFilter] = None,
    ) -> list[Trace]:
        """Fetch traces matching filter criteria."""
        ...
    
    @abstractmethod
    async def get_services(self) -> list[str]:
        """Get list of available services."""
        ...
    
    @abstractmethod
    async def get_operations(self, service: str) -> list[str]:
        """Get list of operations for a service."""
        ...


class JaegerIngester(TraceFetcher):
    """
    Jaeger trace ingester.
    
    Fetches traces from Jaeger via its HTTP API.
    """
    
    def __init__(
        self,
        config: Optional[IngesterConfig] = None,
        url: Optional[str] = None,
    ):
        super().__init__(config)
        self._base_url = url or self.config.jaeger_url
    
    async def fetch_trace(self, trace_id: str) -> Optional[Trace]:
        """Fetch a single trace by ID."""
        client = await self._get_client()
        
        try:
            response = await client.get(f"{self._base_url}/api/traces/{trace_id}")
            response.raise_for_status()
            data = response.json()
            
            traces = self._parse_jaeger_response(data)
            return traces[0] if traces else None
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
        except Exception as e:
            logger.error(f"Failed to fetch trace {trace_id}: {e}")
            return None
    
    async def fetch_traces(
        self,
        filter: Optional[TraceFilter] = None,
    ) -> list[Trace]:
        """Fetch traces matching filter criteria."""
        client = await self._get_client()
        filter = filter or TraceFilter()
        
        # Set default time range if not specified
        if not filter.start_time:
            filter.end_time = datetime.now(timezone.utc)
            filter.start_time = filter.end_time - timedelta(hours=self.config.default_lookback_hours)
        
        params = filter.to_jaeger_params()
        
        try:
            response = await client.get(
                f"{self._base_url}/api/traces",
                params=params,
            )
            response.raise_for_status()
            data = response.json()
            
            return self._parse_jaeger_response(data)
            
        except Exception as e:
            logger.error(f"Failed to fetch traces: {e}")
            return []
    
    async def get_services(self) -> list[str]:
        """Get list of available services."""
        client = await self._get_client()
        
        try:
            response = await client.get(f"{self._base_url}/api/services")
            response.raise_for_status()
            data = response.json()
            
            return data.get("data", [])
            
        except Exception as e:
            logger.error(f"Failed to fetch services: {e}")
            return []
    
    async def get_operations(self, service: str) -> list[str]:
        """Get list of operations for a service."""
        client = await self._get_client()
        
        try:
            response = await client.get(
                f"{self._base_url}/api/services/{quote(service)}/operations"
            )
            response.raise_for_status()
            data = response.json()
            
            return data.get("data", [])
            
        except Exception as e:
            logger.error(f"Failed to fetch operations for {service}: {e}")
            return []
    
    def _parse_jaeger_response(self, data: dict[str, Any]) -> list[Trace]:
        """Parse Jaeger API response into Trace objects."""
        traces = []
        
        for trace_data in data.get("data", []):
            trace_id = trace_data.get("traceID", "")
            spans = []
            
            for span_data in trace_data.get("spans", []):
                # Include process info in span data
                process_id = span_data.get("processID", "")
                process = trace_data.get("processes", {}).get(process_id, {})
                span_data["process"] = process
                
                try:
                    span = Span.from_jaeger(span_data)
                    spans.append(span)
                except Exception as e:
                    logger.warning(f"Failed to parse span: {e}")
            
            if spans:
                traces.append(Trace(trace_id=trace_id, spans=spans))
        
        return traces
    
    async def get_dependencies(
        self,
        end_time: Optional[datetime] = None,
        lookback_hours: int = 24,
    ) -> list[dict[str, Any]]:
        """Get service dependencies from Jaeger."""
        client = await self._get_client()
        
        if end_time is None:
            end_time = datetime.now(timezone.utc)
        
        params = {
            "endTs": int(end_time.timestamp() * 1000),
            "lookback": lookback_hours * 3600 * 1000,
        }
        
        try:
            response = await client.get(
                f"{self._base_url}/api/dependencies",
                params=params,
            )
            response.raise_for_status()
            data = response.json()
            
            return data.get("data", [])
            
        except Exception as e:
            logger.error(f"Failed to fetch dependencies: {e}")
            return []


class OTLPIngester(TraceFetcher):
    """
    OpenTelemetry (OTLP) trace ingester.
    
    Note: OTLP is primarily a push protocol. This ingester is for
    querying backends that expose an OTLP-compatible query API
    (like Tempo with its HTTP API).
    """
    
    def __init__(
        self,
        config: Optional[IngesterConfig] = None,
        url: Optional[str] = None,
    ):
        super().__init__(config)
        self._base_url = url or self.config.otlp_url
    
    async def fetch_trace(self, trace_id: str) -> Optional[Trace]:
        """Fetch a single trace by ID (Tempo-style API)."""
        client = await self._get_client()
        
        try:
            response = await client.get(f"{self._base_url}/api/traces/{trace_id}")
            response.raise_for_status()
            data = response.json()
            
            return self._parse_otlp_trace(trace_id, data)
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
        except Exception as e:
            logger.error(f"Failed to fetch trace {trace_id}: {e}")
            return None
    
    async def fetch_traces(
        self,
        filter: Optional[TraceFilter] = None,
    ) -> list[Trace]:
        """
        Fetch traces matching filter criteria.
        
        Note: Requires a backend with search capability (like Tempo).
        """
        client = await self._get_client()
        filter = filter or TraceFilter()
        
        # Build TraceQL query (Tempo-style)
        query_parts = []
        
        if filter.service:
            query_parts.append(f'resource.service.name="{filter.service}"')
        if filter.operation:
            query_parts.append(f'name="{filter.operation}"')
        if filter.has_error:
            query_parts.append('status=error')
        if filter.min_duration_ms:
            query_parts.append(f'duration>{int(filter.min_duration_ms)}ms')
        if filter.max_duration_ms:
            query_parts.append(f'duration<{int(filter.max_duration_ms)}ms')
        
        for key, value in filter.tags.items():
            query_parts.append(f'span.{key}="{value}"')
        
        query = " && ".join(query_parts) if query_parts else "{}"
        
        params: dict[str, Any] = {
            "q": query,
            "limit": filter.limit,
        }
        
        if filter.start_time:
            params["start"] = int(filter.start_time.timestamp() * 1e9)
        if filter.end_time:
            params["end"] = int(filter.end_time.timestamp() * 1e9)
        
        try:
            response = await client.get(
                f"{self._base_url}/api/search",
                params=params,
            )
            response.raise_for_status()
            data = response.json()
            
            traces = []
            for trace_info in data.get("traces", []):
                trace_id = trace_info.get("traceID", "")
                if trace_id:
                    trace = await self.fetch_trace(trace_id)
                    if trace:
                        traces.append(trace)
            
            return traces
            
        except Exception as e:
            logger.error(f"Failed to search traces: {e}")
            return []
    
    async def get_services(self) -> list[str]:
        """Get list of available services (Tempo-style API)."""
        client = await self._get_client()
        
        try:
            response = await client.get(f"{self._base_url}/api/search/tags")
            response.raise_for_status()
            data = response.json()
            
            # Get values for service.name tag
            for tag in data.get("tagNames", []):
                if tag == "service.name":
                    values_resp = await client.get(
                        f"{self._base_url}/api/search/tag/service.name/values"
                    )
                    values_resp.raise_for_status()
                    values_data = values_resp.json()
                    return values_data.get("tagValues", [])
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to fetch services: {e}")
            return []
    
    async def get_operations(self, service: str) -> list[str]:
        """Get list of operations for a service."""
        # OTLP/Tempo doesn't have a direct operations endpoint
        # We'd need to search spans and extract unique operation names
        return []
    
    def _parse_otlp_trace(self, trace_id: str, data: dict[str, Any]) -> Optional[Trace]:
        """Parse OTLP trace response."""
        spans = []
        
        # OTLP format has nested structure
        for resource_spans in data.get("resourceSpans", data.get("batches", [])):
            resource = {}
            resource_attrs = resource_spans.get("resource", {}).get("attributes", [])
            
            for attr in resource_attrs:
                key = attr.get("key", "")
                value = attr.get("value", {})
                if "stringValue" in value:
                    resource[key] = value["stringValue"]
                    if key == "service.name":
                        resource["service_name"] = value["stringValue"]
            
            for scope_spans in resource_spans.get("scopeSpans", resource_spans.get("instrumentationLibrarySpans", [])):
                for span_data in scope_spans.get("spans", []):
                    try:
                        span = Span.from_otlp(span_data, resource)
                        spans.append(span)
                    except Exception as e:
                        logger.warning(f"Failed to parse span: {e}")
        
        if spans:
            return Trace(trace_id=trace_id, spans=spans)
        return None


class ZipkinIngester(TraceFetcher):
    """
    Zipkin trace ingester.
    
    Fetches traces from Zipkin via its HTTP API.
    """
    
    def __init__(
        self,
        config: Optional[IngesterConfig] = None,
        url: Optional[str] = None,
    ):
        super().__init__(config)
        self._base_url = url or self.config.zipkin_url
    
    async def fetch_trace(self, trace_id: str) -> Optional[Trace]:
        """Fetch a single trace by ID."""
        client = await self._get_client()
        
        try:
            response = await client.get(f"{self._base_url}/api/v2/trace/{trace_id}")
            response.raise_for_status()
            spans_data = response.json()
            
            spans = []
            for span_data in spans_data:
                try:
                    span = Span.from_zipkin(span_data)
                    spans.append(span)
                except Exception as e:
                    logger.warning(f"Failed to parse span: {e}")
            
            if spans:
                return Trace(trace_id=trace_id, spans=spans)
            return None
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
        except Exception as e:
            logger.error(f"Failed to fetch trace {trace_id}: {e}")
            return None
    
    async def fetch_traces(
        self,
        filter: Optional[TraceFilter] = None,
    ) -> list[Trace]:
        """Fetch traces matching filter criteria."""
        client = await self._get_client()
        filter = filter or TraceFilter()
        
        # Set default time range
        if not filter.end_time:
            filter.end_time = datetime.now(timezone.utc)
        if not filter.start_time:
            filter.start_time = filter.end_time - timedelta(hours=self.config.default_lookback_hours)
        
        params = filter.to_zipkin_params()
        
        try:
            response = await client.get(
                f"{self._base_url}/api/v2/traces",
                params=params,
            )
            response.raise_for_status()
            traces_data = response.json()
            
            traces = []
            for trace_spans in traces_data:
                if not trace_spans:
                    continue
                
                trace_id = trace_spans[0].get("traceId", "")
                spans = []
                
                for span_data in trace_spans:
                    try:
                        span = Span.from_zipkin(span_data)
                        spans.append(span)
                    except Exception as e:
                        logger.warning(f"Failed to parse span: {e}")
                
                if spans:
                    traces.append(Trace(trace_id=trace_id, spans=spans))
            
            return traces
            
        except Exception as e:
            logger.error(f"Failed to fetch traces: {e}")
            return []
    
    async def get_services(self) -> list[str]:
        """Get list of available services."""
        client = await self._get_client()
        
        try:
            response = await client.get(f"{self._base_url}/api/v2/services")
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to fetch services: {e}")
            return []
    
    async def get_operations(self, service: str) -> list[str]:
        """Get list of operations for a service."""
        client = await self._get_client()
        
        try:
            response = await client.get(
                f"{self._base_url}/api/v2/spans",
                params={"serviceName": service},
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to fetch operations for {service}: {e}")
            return []


class TraceIngester:
    """
    High-level trace ingester for AutoSRE.
    
    Provides unified interface for multiple tracing backends.
    
    Example:
        ingester = TraceIngester(jaeger_url="http://jaeger:16686")
        
        # Fetch recent traces for a service
        traces = await ingester.fetch_traces(
            TraceFilter(service="api-gateway", limit=10)
        )
        
        # Get a specific trace
        trace = await ingester.fetch_trace("abc123")
    """
    
    def __init__(
        self,
        config: Optional[IngesterConfig] = None,
        jaeger_url: Optional[str] = None,
        otlp_url: Optional[str] = None,
        zipkin_url: Optional[str] = None,
        backend: str = "auto",
    ):
        self.config = config or IngesterConfig()
        
        if jaeger_url:
            self.config.jaeger_url = jaeger_url
        if otlp_url:
            self.config.otlp_url = otlp_url
        if zipkin_url:
            self.config.zipkin_url = zipkin_url
        
        self._backend = backend
        self._ingesters: dict[str, TraceFetcher] = {}
        
        # Initialize configured backends
        if backend == "auto" or backend == "jaeger":
            self._ingesters["jaeger"] = JaegerIngester(self.config)
        if backend == "auto" or backend == "otlp":
            self._ingesters["otlp"] = OTLPIngester(self.config)
        if backend == "auto" or backend == "zipkin":
            self._ingesters["zipkin"] = ZipkinIngester(self.config)
        
        self._primary_backend: Optional[str] = None
    
    async def close(self) -> None:
        """Close all backend connections."""
        for ingester in self._ingesters.values():
            await ingester.close()
    
    async def __aenter__(self) -> "TraceIngester":
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
    
    async def _get_ingester(self) -> TraceFetcher:
        """Get the primary ingester, auto-detecting if needed."""
        if self._primary_backend and self._primary_backend in self._ingesters:
            return self._ingesters[self._primary_backend]
        
        # Auto-detect available backend
        for name, ingester in self._ingesters.items():
            try:
                services = await ingester.get_services()
                if services is not None:  # Backend responded
                    self._primary_backend = name
                    logger.info(f"Using {name} as primary tracing backend")
                    return ingester
            except Exception:
                continue
        
        # Fall back to first configured
        if self._ingesters:
            self._primary_backend = next(iter(self._ingesters))
            return self._ingesters[self._primary_backend]
        
        raise RuntimeError("No tracing backend configured")
    
    async def fetch_trace(self, trace_id: str) -> Optional[Trace]:
        """Fetch a single trace by ID."""
        ingester = await self._get_ingester()
        return await ingester.fetch_trace(trace_id)
    
    async def fetch_traces(
        self,
        filter: Optional[TraceFilter] = None,
        **kwargs,
    ) -> list[Trace]:
        """
        Fetch traces matching filter criteria.
        
        Args:
            filter: TraceFilter with query criteria
            **kwargs: Shorthand for common filter fields
        
        Returns:
            List of matching Trace objects
        """
        if filter is None:
            filter = TraceFilter(**kwargs)
        
        ingester = await self._get_ingester()
        return await ingester.fetch_traces(filter)
    
    async def get_services(self) -> list[str]:
        """Get list of available services."""
        ingester = await self._get_ingester()
        return await ingester.get_services()
    
    async def get_operations(self, service: str) -> list[str]:
        """Get list of operations for a service."""
        ingester = await self._get_ingester()
        return await ingester.get_operations(service)
    
    async def fetch_traces_batch(
        self,
        filters: list[TraceFilter],
    ) -> list[list[Trace]]:
        """Fetch traces for multiple filters concurrently."""
        tasks = [self.fetch_traces(f) for f in filters]
        return await asyncio.gather(*tasks)
    
    async def stream_traces(
        self,
        filter: Optional[TraceFilter] = None,
        poll_interval_seconds: float = 5.0,
    ) -> AsyncIterator[Trace]:
        """
        Stream traces as they arrive.
        
        Polls the backend periodically for new traces.
        """
        filter = filter or TraceFilter()
        seen_trace_ids: set[str] = set()
        
        # Initialize time window
        if not filter.end_time:
            filter.end_time = datetime.now(timezone.utc)
        if not filter.start_time:
            filter.start_time = filter.end_time - timedelta(minutes=5)
        
        while True:
            # Fetch new traces
            filter.end_time = datetime.now(timezone.utc)
            traces = await self.fetch_traces(filter)
            
            for trace in traces:
                if trace.trace_id not in seen_trace_ids:
                    seen_trace_ids.add(trace.trace_id)
                    yield trace
            
            # Advance window
            filter.start_time = filter.end_time
            
            # Cleanup old IDs to prevent memory leak
            if len(seen_trace_ids) > 10000:
                seen_trace_ids = set(list(seen_trace_ids)[-5000:])
            
            await asyncio.sleep(poll_interval_seconds)
    
    def set_backend(self, backend: str) -> None:
        """Set the primary backend to use."""
        if backend in self._ingesters:
            self._primary_backend = backend
        else:
            raise ValueError(f"Unknown backend: {backend}")
