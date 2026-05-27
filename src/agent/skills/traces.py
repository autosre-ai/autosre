"""Distributed tracing tools for SRE agents.

Provides tools for searching and analyzing traces:
- Jaeger
- Tempo (via Grafana)
- Generic trace analysis
"""

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urljoin, urlencode

from langchain_core.tools import BaseTool, tool

from .base import BaseSRETool, SREToolError, ConnectionError, AuthenticationError

logger = logging.getLogger(__name__)


def _make_request(
    method: str,
    url: str,
    headers: Optional[dict] = None,
    params: Optional[dict] = None,
    data: Optional[dict] = None,
    timeout: int = 30,
    verify_ssl: bool = True,
) -> dict[str, Any]:
    """Make HTTP request using urllib."""
    import ssl
    import urllib.request
    import urllib.error
    
    if params:
        url = f"{url}?{urlencode(params)}"
    
    headers = headers or {}
    headers.setdefault("Accept", "application/json")
    
    body = None
    if data:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    
    context = None
    if not verify_ssl:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            response_data = response.read().decode("utf-8")
            if response_data:
                return json.loads(response_data)
            return {}
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise AuthenticationError(url)
        error_body = e.read().decode("utf-8") if e.fp else ""
        raise SREToolError(f"HTTP {e.code}: {error_body[:200]}")
    except urllib.error.URLError as e:
        raise ConnectionError(url, str(e.reason))
    except json.JSONDecodeError as e:
        raise SREToolError(f"Invalid JSON response: {e}")


@dataclass
class JaegerConfig:
    """Configuration for Jaeger client."""
    
    url: str = "http://localhost:16686"
    timeout_seconds: int = 30
    verify_ssl: bool = True
    
    @classmethod
    def from_env(cls) -> "JaegerConfig":
        """Create config from environment variables."""
        return cls(
            url=os.getenv("JAEGER_URL", "http://localhost:16686"),
            timeout_seconds=int(os.getenv("JAEGER_TIMEOUT", "30")),
            verify_ssl=os.getenv("JAEGER_VERIFY_SSL", "true").lower() == "true",
        )


@dataclass 
class TempoConfig:
    """Configuration for Grafana Tempo client."""
    
    url: str = "http://localhost:3200"
    timeout_seconds: int = 30
    verify_ssl: bool = True
    
    @classmethod
    def from_env(cls) -> "TempoConfig":
        """Create config from environment variables."""
        return cls(
            url=os.getenv("TEMPO_URL", "http://localhost:3200"),
            timeout_seconds=int(os.getenv("TEMPO_TIMEOUT", "30")),
            verify_ssl=os.getenv("TEMPO_VERIFY_SSL", "true").lower() == "true",
        )


class TracesTools(BaseSRETool):
    """Distributed tracing tools for SRE agents."""
    
    name = "traces"
    description = "Search and analyze distributed traces from Jaeger and Tempo"
    
    def __init__(
        self,
        jaeger_config: Optional[JaegerConfig] = None,
        tempo_config: Optional[TempoConfig] = None,
        mock_mode: bool = False,
    ):
        """Initialize tracing tools.
        
        Args:
            jaeger_config: Jaeger configuration.
            tempo_config: Tempo configuration.
            mock_mode: If True, return mock data.
        """
        super().__init__(mock_mode=mock_mode)
        self.jaeger = jaeger_config or JaegerConfig.from_env()
        self.tempo = tempo_config or TempoConfig.from_env()
    
    def get_tools(self) -> list[BaseTool]:
        """Return list of tracing tools."""
        return [
            self._make_search_jaeger_tool(),
            self._make_get_trace_tool(),
        ]
    
    def _make_search_jaeger_tool(self) -> BaseTool:
        """Create search_jaeger tool."""
        parent = self
        
        @tool
        def search_jaeger(
            service: str,
            operation: str = "",
            tags: str = "",
            min_duration: str = "",
            max_duration: str = "",
            time_range: str = "1h",
            limit: int = 20,
        ) -> str:
            """Search traces in Jaeger.
            
            Args:
                service: Service name to search (required).
                operation: Operation/span name to filter (optional).
                tags: Key-value tags to filter (e.g., 'http.status_code=500,error=true').
                min_duration: Minimum trace duration (e.g., '100ms', '1s').
                max_duration: Maximum trace duration (e.g., '5s', '10s').
                time_range: Time range to search (e.g., '1h', '6h', '1d').
                limit: Maximum number of traces to return.
                
            Returns:
                JSON with matching traces including trace IDs, durations, and span counts.
                
            Examples:
                - Find slow traces: min_duration='1s'
                - Find errors: tags='error=true'
                - Find specific HTTP errors: tags='http.status_code=500'
            """
            if parent.mock_mode:
                mock_data = parent.get_mock_response("search_jaeger", {
                    "traces": [
                        {
                            "traceID": "abc123def456",
                            "spans": [
                                {
                                    "spanID": "span1",
                                    "operationName": "GET /api/users",
                                    "duration": 1250000,
                                    "tags": {"http.status_code": 200},
                                }
                            ],
                            "services": ["api-gateway", "user-service"],
                            "duration": 1250000,
                        }
                    ]
                })
                return json.dumps(mock_data, indent=2)
            
            try:
                # Calculate time range
                now_micros = int(time.time() * 1e6)
                duration_map = {"m": 60, "h": 3600, "d": 86400}
                unit = time_range[-1]
                value = int(time_range[:-1])
                duration_micros = int(value * duration_map.get(unit, 3600) * 1e6)
                
                start = now_micros - duration_micros
                end = now_micros
                
                # Build query params
                params = {
                    "service": service,
                    "start": start,
                    "end": end,
                    "limit": limit,
                    "lookback": time_range,
                }
                
                if operation:
                    params["operation"] = operation
                
                if tags:
                    # Jaeger expects tags as JSON
                    tag_dict = {}
                    for tag in tags.split(","):
                        if "=" in tag:
                            key, val = tag.split("=", 1)
                            tag_dict[key] = val
                    params["tags"] = json.dumps(tag_dict)
                
                if min_duration:
                    params["minDuration"] = min_duration
                
                if max_duration:
                    params["maxDuration"] = max_duration
                
                url = urljoin(parent.jaeger.url, "/api/traces")
                result = _make_request(
                    "GET",
                    url,
                    params=params,
                    timeout=parent.jaeger.timeout_seconds,
                    verify_ssl=parent.jaeger.verify_ssl,
                )
                
                # Format traces
                traces = []
                for trace_data in result.get("data", []):
                    trace_id = trace_data.get("traceID")
                    spans = trace_data.get("spans", [])
                    processes = trace_data.get("processes", {})
                    
                    # Get unique services
                    services = set()
                    for span in spans:
                        proc_id = span.get("processID")
                        if proc_id and proc_id in processes:
                            services.add(processes[proc_id].get("serviceName", "unknown"))
                    
                    # Find root span and calculate duration
                    root_span = None
                    max_duration = 0
                    for span in spans:
                        duration = span.get("duration", 0)
                        if duration > max_duration:
                            max_duration = duration
                            root_span = span
                    
                    # Extract key tags from spans
                    error_spans = []
                    for span in spans:
                        span_tags = {t["key"]: t["value"] for t in span.get("tags", [])}
                        if span_tags.get("error") == True or span_tags.get("error") == "true":
                            error_spans.append({
                                "operationName": span.get("operationName"),
                                "serviceName": processes.get(span.get("processID"), {}).get("serviceName"),
                                "tags": span_tags,
                            })
                    
                    traces.append({
                        "traceID": trace_id,
                        "services": list(services),
                        "spanCount": len(spans),
                        "duration": max_duration,
                        "durationMs": max_duration / 1000,
                        "startTime": datetime.fromtimestamp(
                            root_span.get("startTime", 0) / 1e6
                        ).isoformat() if root_span else None,
                        "rootOperation": root_span.get("operationName") if root_span else None,
                        "hasErrors": len(error_spans) > 0,
                        "errorSpans": error_spans[:3],  # First 3 errors
                    })
                
                # Sort by duration descending
                traces.sort(key=lambda t: t.get("duration", 0), reverse=True)
                
                return json.dumps({
                    "service": service,
                    "operation": operation,
                    "timeRange": time_range,
                    "traces": traces,
                    "count": len(traces),
                }, indent=2)
                
            except (ConnectionError, AuthenticationError, SREToolError) as e:
                return json.dumps({"error": str(e)})
            except Exception as e:
                logger.exception("Jaeger search error")
                return json.dumps({"error": f"Unexpected error: {e}"})
        
        return search_jaeger
    
    def _make_get_trace_tool(self) -> BaseTool:
        """Create get_trace tool."""
        parent = self
        
        @tool
        def get_trace(
            trace_id: str,
            backend: str = "jaeger",
        ) -> str:
            """Get detailed information about a specific trace.
            
            Args:
                trace_id: The trace ID to retrieve.
                backend: Tracing backend ('jaeger' or 'tempo').
                
            Returns:
                JSON with full trace details including all spans, timing, and tags.
            """
            if parent.mock_mode:
                mock_data = parent.get_mock_response("get_trace", {
                    "traceID": trace_id,
                    "spans": [
                        {
                            "spanID": "span1",
                            "operationName": "GET /api/users",
                            "serviceName": "api-gateway",
                            "duration": 1250,
                            "startTime": "2024-01-15T10:30:00Z",
                            "tags": {"http.method": "GET", "http.status_code": 200},
                            "logs": [],
                        },
                        {
                            "spanID": "span2",
                            "parentSpanID": "span1",
                            "operationName": "SELECT users",
                            "serviceName": "user-service",
                            "duration": 45,
                            "tags": {"db.type": "postgresql"},
                        },
                    ],
                })
                return json.dumps(mock_data, indent=2)
            
            try:
                if backend == "tempo":
                    url = urljoin(parent.tempo.url, f"/api/traces/{trace_id}")
                    config = parent.tempo
                else:
                    url = urljoin(parent.jaeger.url, f"/api/traces/{trace_id}")
                    config = parent.jaeger
                
                result = _make_request(
                    "GET",
                    url,
                    timeout=config.timeout_seconds,
                    verify_ssl=config.verify_ssl,
                )
                
                # Jaeger returns data in a specific format
                if backend == "jaeger":
                    trace_data = result.get("data", [{}])[0]
                else:
                    trace_data = result
                
                trace_id = trace_data.get("traceID")
                spans = trace_data.get("spans", [])
                processes = trace_data.get("processes", {})
                
                # Format spans for readability
                formatted_spans = []
                for span in spans:
                    proc_id = span.get("processID")
                    service_name = processes.get(proc_id, {}).get("serviceName", "unknown") if proc_id else "unknown"
                    
                    # Extract tags
                    tags = {t["key"]: t["value"] for t in span.get("tags", [])}
                    
                    # Extract logs/events
                    logs = []
                    for log in span.get("logs", []):
                        log_fields = {f["key"]: f["value"] for f in log.get("fields", [])}
                        logs.append({
                            "timestamp": datetime.fromtimestamp(log.get("timestamp", 0) / 1e6).isoformat(),
                            "fields": log_fields,
                        })
                    
                    formatted_spans.append({
                        "spanID": span.get("spanID"),
                        "parentSpanID": span.get("references", [{}])[0].get("spanID") if span.get("references") else None,
                        "operationName": span.get("operationName"),
                        "serviceName": service_name,
                        "startTime": datetime.fromtimestamp(span.get("startTime", 0) / 1e6).isoformat(),
                        "duration": span.get("duration"),
                        "durationMs": span.get("duration", 0) / 1000,
                        "tags": tags,
                        "logs": logs,
                        "warnings": span.get("warnings", []),
                    })
                
                # Sort spans by start time
                formatted_spans.sort(key=lambda s: s.get("startTime", ""))
                
                # Build service dependency tree
                services = {}
                for span in formatted_spans:
                    svc = span["serviceName"]
                    if svc not in services:
                        services[svc] = {
                            "spanCount": 0,
                            "totalDurationMs": 0,
                            "operations": set(),
                        }
                    services[svc]["spanCount"] += 1
                    services[svc]["totalDurationMs"] += span.get("durationMs", 0)
                    services[svc]["operations"].add(span.get("operationName"))
                
                # Convert sets to lists for JSON
                for svc in services.values():
                    svc["operations"] = list(svc["operations"])
                
                # Find critical path (longest chain)
                root_span = next((s for s in formatted_spans if not s.get("parentSpanID")), None)
                
                return json.dumps({
                    "traceID": trace_id,
                    "spanCount": len(formatted_spans),
                    "services": services,
                    "rootSpan": root_span,
                    "spans": formatted_spans,
                }, indent=2)
                
            except (ConnectionError, AuthenticationError, SREToolError) as e:
                return json.dumps({"error": str(e)})
            except Exception as e:
                logger.exception("Get trace error")
                return json.dumps({"error": f"Unexpected error: {e}"})
        
        return get_trace


# Convenience function to get all tracing tools
def get_traces_tools(
    jaeger_config: Optional[JaegerConfig] = None,
    tempo_config: Optional[TempoConfig] = None,
    mock_mode: bool = False,
) -> list[BaseTool]:
    """Get all distributed tracing tools.
    
    Args:
        jaeger_config: Jaeger configuration.
        tempo_config: Tempo configuration.
        mock_mode: If True, return mock data.
        
    Returns:
        List of LangChain tools.
    """
    traces = TracesTools(
        jaeger_config=jaeger_config,
        tempo_config=tempo_config,
        mock_mode=mock_mode,
    )
    return traces.get_tools()
