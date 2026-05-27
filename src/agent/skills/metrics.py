"""Metrics query tools for SRE agents.

Provides tools for querying observability platforms:
- Prometheus (PromQL queries)
- Datadog (metrics API)
- Grafana (dashboard data)
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


@dataclass
class PrometheusConfig:
    """Configuration for Prometheus client."""
    
    url: str = "http://localhost:9090"
    timeout_seconds: int = 30
    auth_token: Optional[str] = None
    verify_ssl: bool = True
    
    @classmethod
    def from_env(cls) -> "PrometheusConfig":
        """Create config from environment variables."""
        return cls(
            url=os.getenv("PROMETHEUS_URL", "http://localhost:9090"),
            timeout_seconds=int(os.getenv("PROMETHEUS_TIMEOUT", "30")),
            auth_token=os.getenv("PROMETHEUS_TOKEN"),
            verify_ssl=os.getenv("PROMETHEUS_VERIFY_SSL", "true").lower() == "true",
        )


@dataclass
class DatadogConfig:
    """Configuration for Datadog client."""
    
    api_key: str = ""
    app_key: str = ""
    site: str = "datadoghq.com"
    timeout_seconds: int = 30
    
    @classmethod
    def from_env(cls) -> "DatadogConfig":
        """Create config from environment variables."""
        return cls(
            api_key=os.getenv("DD_API_KEY", ""),
            app_key=os.getenv("DD_APP_KEY", ""),
            site=os.getenv("DD_SITE", "datadoghq.com"),
            timeout_seconds=int(os.getenv("DD_TIMEOUT", "30")),
        )
    
    @property
    def api_url(self) -> str:
        """Get the API base URL."""
        return f"https://api.{self.site}"


@dataclass
class GrafanaConfig:
    """Configuration for Grafana client."""
    
    url: str = "http://localhost:3000"
    api_key: Optional[str] = None
    timeout_seconds: int = 30
    verify_ssl: bool = True
    
    @classmethod
    def from_env(cls) -> "GrafanaConfig":
        """Create config from environment variables."""
        return cls(
            url=os.getenv("GRAFANA_URL", "http://localhost:3000"),
            api_key=os.getenv("GRAFANA_API_KEY"),
            timeout_seconds=int(os.getenv("GRAFANA_TIMEOUT", "30")),
            verify_ssl=os.getenv("GRAFANA_VERIFY_SSL", "true").lower() == "true",
        )


def _make_request(
    method: str,
    url: str,
    headers: Optional[dict] = None,
    params: Optional[dict] = None,
    data: Optional[dict] = None,
    timeout: int = 30,
    verify_ssl: bool = True,
) -> dict[str, Any]:
    """Make HTTP request using urllib (no external dependencies).
    
    Args:
        method: HTTP method.
        url: Request URL.
        headers: Request headers.
        params: Query parameters.
        data: Request body (JSON).
        timeout: Request timeout in seconds.
        verify_ssl: Whether to verify SSL certificates.
        
    Returns:
        Response data as dict.
        
    Raises:
        ConnectionError: On connection failure.
        SREToolError: On other errors.
    """
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
        if e.code == 401:
            raise AuthenticationError(url)
        elif e.code == 403:
            raise AuthenticationError(url)
        else:
            error_body = e.read().decode("utf-8") if e.fp else ""
            raise SREToolError(f"HTTP {e.code}: {error_body[:200]}")
    except urllib.error.URLError as e:
        raise ConnectionError(url, str(e.reason))
    except json.JSONDecodeError as e:
        raise SREToolError(f"Invalid JSON response: {e}")


class MetricsTools(BaseSRETool):
    """Metrics query tools for observability platforms."""
    
    name = "metrics"
    description = "Query metrics from Prometheus, Datadog, and Grafana"
    
    def __init__(
        self,
        prometheus_config: Optional[PrometheusConfig] = None,
        datadog_config: Optional[DatadogConfig] = None,
        grafana_config: Optional[GrafanaConfig] = None,
        mock_mode: bool = False,
    ):
        """Initialize metrics tools.
        
        Args:
            prometheus_config: Prometheus configuration.
            datadog_config: Datadog configuration.
            grafana_config: Grafana configuration.
            mock_mode: If True, return mock data.
        """
        super().__init__(mock_mode=mock_mode)
        self.prometheus = prometheus_config or PrometheusConfig.from_env()
        self.datadog = datadog_config or DatadogConfig.from_env()
        self.grafana = grafana_config or GrafanaConfig.from_env()
    
    def get_tools(self) -> list[BaseTool]:
        """Return list of metrics tools."""
        return [
            self._make_query_prometheus_tool(),
            self._make_query_datadog_tool(),
            self._make_query_grafana_tool(),
        ]
    
    def _make_query_prometheus_tool(self) -> BaseTool:
        """Create query_prometheus tool."""
        parent = self
        
        @tool
        def query_prometheus(
            query: str,
            time_range: str = "1h",
            step: str = "1m",
            query_type: str = "range",
        ) -> str:
            """Execute a PromQL query against Prometheus.
            
            Args:
                query: PromQL query string (e.g., 'rate(http_requests_total[5m])').
                time_range: Time range for range queries (e.g., '1h', '30m', '1d').
                step: Query resolution step (e.g., '1m', '5m', '15s').
                query_type: 'instant' for current value, 'range' for time series.
                
            Returns:
                JSON with query results including metric values and labels.
                
            Examples:
                - CPU usage: 'rate(node_cpu_seconds_total{mode!="idle"}[5m])'
                - Memory: 'node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes'
                - HTTP errors: 'sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)'
            """
            if parent.mock_mode:
                mock_data = parent.get_mock_response("query_prometheus", {
                    "status": "success",
                    "data": {
                        "resultType": "vector",
                        "result": [
                            {
                                "metric": {"__name__": "mock_metric", "instance": "localhost:9090"},
                                "value": [1705315200, "42.5"],
                            }
                        ],
                    },
                })
                return json.dumps(mock_data, indent=2)
            
            try:
                headers = {}
                if parent.prometheus.auth_token:
                    headers["Authorization"] = f"Bearer {parent.prometheus.auth_token}"
                
                end_time = time.time()
                
                # Parse time range
                duration_map = {
                    "s": 1, "m": 60, "h": 3600,
                    "d": 86400, "w": 604800,
                }
                unit = time_range[-1]
                value = int(time_range[:-1])
                duration_seconds = value * duration_map.get(unit, 3600)
                start_time = end_time - duration_seconds
                
                if query_type == "instant":
                    url = urljoin(parent.prometheus.url, "/api/v1/query")
                    params = {"query": query, "time": end_time}
                else:
                    url = urljoin(parent.prometheus.url, "/api/v1/query_range")
                    params = {
                        "query": query,
                        "start": start_time,
                        "end": end_time,
                        "step": step,
                    }
                
                result = _make_request(
                    "GET",
                    url,
                    headers=headers,
                    params=params,
                    timeout=parent.prometheus.timeout_seconds,
                    verify_ssl=parent.prometheus.verify_ssl,
                )
                
                # Format the result for readability
                if result.get("status") == "success":
                    data = result.get("data", {})
                    formatted = {
                        "status": "success",
                        "resultType": data.get("resultType"),
                        "resultCount": len(data.get("result", [])),
                        "results": [],
                    }
                    
                    for r in data.get("result", [])[:50]:  # Limit results
                        metric = r.get("metric", {})
                        if data.get("resultType") == "matrix":
                            # Range query - get last few values
                            values = r.get("values", [])[-10:]
                            formatted["results"].append({
                                "labels": metric,
                                "values": [
                                    {"timestamp": v[0], "value": v[1]}
                                    for v in values
                                ],
                            })
                        else:
                            # Instant query
                            value = r.get("value", [])
                            formatted["results"].append({
                                "labels": metric,
                                "value": value[1] if len(value) > 1 else None,
                                "timestamp": value[0] if value else None,
                            })
                    
                    return json.dumps(formatted, indent=2)
                else:
                    return json.dumps({
                        "error": result.get("error", "Unknown error"),
                        "errorType": result.get("errorType"),
                    })
                
            except (ConnectionError, AuthenticationError, SREToolError) as e:
                return json.dumps({"error": str(e)})
            except Exception as e:
                logger.exception("Prometheus query error")
                return json.dumps({"error": f"Unexpected error: {e}"})
        
        return query_prometheus
    
    def _make_query_datadog_tool(self) -> BaseTool:
        """Create query_datadog tool."""
        parent = self
        
        @tool
        def query_datadog(
            query: str,
            time_range: str = "1h",
        ) -> str:
            """Query metrics from Datadog.
            
            Args:
                query: Datadog metrics query string.
                    Format: 'metric{tag:value}.aggregation()'
                    Examples:
                    - 'avg:system.cpu.user{host:web-1}'
                    - 'sum:aws.ec2.cpuutilization{env:production} by {instance_id}'
                time_range: Time range (e.g., '1h', '4h', '1d').
                
            Returns:
                JSON with metric values and metadata.
            """
            if parent.mock_mode:
                mock_data = parent.get_mock_response("query_datadog", {
                    "status": "ok",
                    "series": [
                        {
                            "metric": "system.cpu.user",
                            "scope": "host:web-1",
                            "pointlist": [[1705315200000, 45.2], [1705315260000, 47.1]],
                        }
                    ],
                })
                return json.dumps(mock_data, indent=2)
            
            if not parent.datadog.api_key or not parent.datadog.app_key:
                return json.dumps({
                    "error": "Datadog API key and App key are required. Set DD_API_KEY and DD_APP_KEY environment variables."
                })
            
            try:
                headers = {
                    "DD-API-KEY": parent.datadog.api_key,
                    "DD-APPLICATION-KEY": parent.datadog.app_key,
                }
                
                # Parse time range
                end_time = int(time.time())
                duration_map = {"m": 60, "h": 3600, "d": 86400}
                unit = time_range[-1]
                value = int(time_range[:-1])
                duration_seconds = value * duration_map.get(unit, 3600)
                start_time = end_time - duration_seconds
                
                url = f"{parent.datadog.api_url}/api/v1/query"
                params = {
                    "query": query,
                    "from": start_time,
                    "to": end_time,
                }
                
                result = _make_request(
                    "GET",
                    url,
                    headers=headers,
                    params=params,
                    timeout=parent.datadog.timeout_seconds,
                )
                
                # Format the result
                formatted = {
                    "status": result.get("status", "unknown"),
                    "query": query,
                    "timeRange": {"from": start_time, "to": end_time},
                    "series": [],
                }
                
                for series in result.get("series", []):
                    points = series.get("pointlist", [])
                    formatted["series"].append({
                        "metric": series.get("metric"),
                        "scope": series.get("scope"),
                        "tags": series.get("tag_set", []),
                        "unit": series.get("unit"),
                        "pointCount": len(points),
                        "points": [
                            {"timestamp": int(p[0] / 1000), "value": p[1]}
                            for p in points[-20:]  # Last 20 points
                        ],
                        "summary": {
                            "min": min((p[1] for p in points if p[1] is not None), default=None),
                            "max": max((p[1] for p in points if p[1] is not None), default=None),
                            "avg": sum((p[1] for p in points if p[1] is not None)) / len([p for p in points if p[1] is not None]) if points else None,
                            "last": points[-1][1] if points else None,
                        },
                    })
                
                return json.dumps(formatted, indent=2)
                
            except (ConnectionError, AuthenticationError, SREToolError) as e:
                return json.dumps({"error": str(e)})
            except Exception as e:
                logger.exception("Datadog query error")
                return json.dumps({"error": f"Unexpected error: {e}"})
        
        return query_datadog
    
    def _make_query_grafana_tool(self) -> BaseTool:
        """Create query_grafana tool."""
        parent = self
        
        @tool
        def query_grafana(
            datasource: str,
            query: str,
            time_range: str = "1h",
            query_type: str = "range",
        ) -> str:
            """Query data through Grafana's datasource proxy.
            
            This queries a Grafana datasource (Prometheus, InfluxDB, etc.)
            using Grafana's API.
            
            Args:
                datasource: Name or UID of the Grafana datasource.
                query: Query in the datasource's native format.
                time_range: Time range (e.g., '1h', '6h', '1d').
                query_type: 'range' for time series, 'instant' for current value.
                
            Returns:
                JSON with query results.
            """
            if parent.mock_mode:
                mock_data = parent.get_mock_response("query_grafana", {
                    "status": "success",
                    "data": {
                        "results": {
                            "A": {
                                "frames": [
                                    {
                                        "name": "mock_metric",
                                        "values": [42.0, 43.5, 41.2],
                                    }
                                ]
                            }
                        }
                    },
                })
                return json.dumps(mock_data, indent=2)
            
            try:
                headers = {}
                if parent.grafana.api_key:
                    headers["Authorization"] = f"Bearer {parent.grafana.api_key}"
                
                # First, get datasource info by name
                ds_url = urljoin(parent.grafana.url, f"/api/datasources/name/{datasource}")
                try:
                    ds_info = _make_request(
                        "GET",
                        ds_url,
                        headers=headers,
                        timeout=parent.grafana.timeout_seconds,
                        verify_ssl=parent.grafana.verify_ssl,
                    )
                    ds_uid = ds_info.get("uid")
                    ds_type = ds_info.get("type")
                except SREToolError:
                    # Maybe it's a UID already
                    ds_uid = datasource
                    ds_type = "prometheus"  # Assume prometheus
                
                # Calculate time range
                end_time = int(time.time() * 1000)  # Grafana uses milliseconds
                duration_map = {"m": 60000, "h": 3600000, "d": 86400000}
                unit = time_range[-1]
                value = int(time_range[:-1])
                duration_ms = value * duration_map.get(unit, 3600000)
                start_time = end_time - duration_ms
                
                # Query via ds/query endpoint (unified querying)
                query_url = urljoin(parent.grafana.url, "/api/ds/query")
                query_payload = {
                    "queries": [
                        {
                            "refId": "A",
                            "datasource": {"uid": ds_uid},
                            "expr": query,  # For Prometheus
                            "query": query,  # For other datasources
                            "instant": query_type == "instant",
                            "range": query_type == "range",
                            "intervalMs": 60000,
                            "maxDataPoints": 100,
                        }
                    ],
                    "from": str(start_time),
                    "to": str(end_time),
                }
                
                result = _make_request(
                    "POST",
                    query_url,
                    headers=headers,
                    data=query_payload,
                    timeout=parent.grafana.timeout_seconds,
                    verify_ssl=parent.grafana.verify_ssl,
                )
                
                # Format the result
                formatted = {
                    "status": "success",
                    "datasource": datasource,
                    "query": query,
                    "timeRange": {
                        "from": datetime.fromtimestamp(start_time / 1000).isoformat(),
                        "to": datetime.fromtimestamp(end_time / 1000).isoformat(),
                    },
                    "results": [],
                }
                
                # Parse Grafana's response format
                results = result.get("results", {})
                for ref_id, ref_data in results.items():
                    frames = ref_data.get("frames", [])
                    for frame in frames:
                        schema = frame.get("schema", {})
                        data = frame.get("data", {})
                        
                        formatted["results"].append({
                            "refId": ref_id,
                            "name": schema.get("name"),
                            "fields": schema.get("fields", []),
                            "values": data.get("values", []),
                        })
                
                return json.dumps(formatted, indent=2)
                
            except (ConnectionError, AuthenticationError, SREToolError) as e:
                return json.dumps({"error": str(e)})
            except Exception as e:
                logger.exception("Grafana query error")
                return json.dumps({"error": f"Unexpected error: {e}"})
        
        return query_grafana


# Convenience function to get all metrics tools
def get_metrics_tools(
    prometheus_config: Optional[PrometheusConfig] = None,
    datadog_config: Optional[DatadogConfig] = None,
    grafana_config: Optional[GrafanaConfig] = None,
    mock_mode: bool = False,
) -> list[BaseTool]:
    """Get all metrics query tools.
    
    Args:
        prometheus_config: Prometheus configuration.
        datadog_config: Datadog configuration.
        grafana_config: Grafana configuration.
        mock_mode: If True, return mock data.
        
    Returns:
        List of LangChain tools.
    """
    metrics = MetricsTools(
        prometheus_config=prometheus_config,
        datadog_config=datadog_config,
        grafana_config=grafana_config,
        mock_mode=mock_mode,
    )
    return metrics.get_tools()
