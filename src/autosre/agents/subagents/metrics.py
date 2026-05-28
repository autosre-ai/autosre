"""
Metrics Subagent — Investigates metrics and observability data.

Capabilities:
- Prometheus queries (PromQL)
- Anomaly detection
- Resource usage analysis
- Error rate and latency metrics
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urljoin

from .base import BaseSubagent, SubagentConfig
from .react import Tool, create_tool

logger = logging.getLogger(__name__)


METRICS_CAPABILITIES = """
**Metrics Investigation**:
- Query Prometheus/Victoria Metrics with PromQL
- Check error rates, latency percentiles
- Analyze resource usage (CPU, memory, network)
- Compare current vs historical baselines
- Detect anomalies and correlations

**Common queries**:
1. HTTP error rate: rate(http_requests_total{status=~"5.."}[5m])
2. P99 latency: histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))
3. CPU usage: rate(container_cpu_usage_seconds_total[5m])
4. Memory usage: container_memory_usage_bytes
5. Request rate: rate(http_requests_total[5m])
"""


class MetricsSubagent(BaseSubagent):
    """Metrics/observability domain investigation subagent."""
    
    agent_id = "metrics"
    agent_name = "Metrics Investigation Agent"
    capabilities_description = METRICS_CAPABILITIES
    
    def __init__(
        self,
        config: Optional[SubagentConfig] = None,
        prometheus_url: str = "http://prometheus:9090",
        alertmanager_url: Optional[str] = None,
        dry_run: bool = False,
    ):
        super().__init__(config)
        self.prometheus_url = prometheus_url.rstrip("/")
        self.alertmanager_url = alertmanager_url
        self.dry_run = dry_run
    
    async def _query_prometheus(
        self,
        query: str,
        time: Optional[str] = None,
    ) -> dict[str, Any]:
        """Execute an instant query against Prometheus."""
        if self.dry_run:
            return {
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [{"metric": {"__name__": "mock"}, "value": [0, "0"]}],
                },
                "_dry_run": True,
                "_query": query,
            }
        
        try:
            import httpx
        except ImportError:
            return {"status": "error", "error": "httpx not installed"}
        
        url = urljoin(self.prometheus_url, "/api/v1/query")
        params = {"query": query}
        if time:
            params["time"] = time
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params, timeout=30)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _query_prometheus_range(
        self,
        query: str,
        start: str,
        end: str,
        step: str = "1m",
    ) -> dict[str, Any]:
        """Execute a range query against Prometheus."""
        if self.dry_run:
            return {
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": [],
                },
                "_dry_run": True,
                "_query": query,
            }
        
        try:
            import httpx
        except ImportError:
            return {"status": "error", "error": "httpx not installed"}
        
        url = urljoin(self.prometheus_url, "/api/v1/query_range")
        params = {
            "query": query,
            "start": start,
            "end": end,
            "step": step,
        }
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params, timeout=30)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _get_alerts(self) -> dict[str, Any]:
        """Get active alerts from Prometheus."""
        if self.dry_run:
            return {
                "status": "success",
                "data": {"alerts": []},
                "_dry_run": True,
            }
        
        try:
            import httpx
        except ImportError:
            return {"status": "error", "error": "httpx not installed"}
        
        url = urljoin(self.prometheus_url, "/api/v1/alerts")
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=30)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _format_prometheus_result(self, data: dict[str, Any]) -> str:
        """Format Prometheus API response for display."""
        if data.get("status") == "error":
            return f"Error: {data.get('error', 'Unknown error')}"
        
        if data.get("_dry_run"):
            return f"[DRY RUN] Would query: {data.get('_query', 'unknown')}"
        
        result_data = data.get("data", {})
        result_type = result_data.get("resultType", "unknown")
        results = result_data.get("result", [])
        
        if not results:
            return "No data found for this query."
        
        lines = [f"Result type: {result_type}", f"Found {len(results)} series:", ""]
        
        for r in results[:20]:  # Limit to 20 series
            metric = r.get("metric", {})
            metric_str = ", ".join(f'{k}="{v}"' for k, v in metric.items() if k != "__name__")
            name = metric.get("__name__", "unknown")
            
            if result_type == "vector":
                # Instant query
                value = r.get("value", [0, ""])[1]
                lines.append(f"{name}{{{metric_str}}}: {value}")
            elif result_type == "matrix":
                # Range query
                values = r.get("values", [])
                if values:
                    latest = values[-1][1]
                    avg = sum(float(v[1]) for v in values) / len(values)
                    lines.append(f"{name}{{{metric_str}}}: latest={latest}, avg={avg:.2f}, samples={len(values)}")
        
        if len(results) > 20:
            lines.append(f"... and {len(results) - 20} more series")
        
        return "\n".join(lines)
    
    async def get_tools(self) -> list[Tool]:
        """Return Prometheus investigation tools."""
        
        # ----- Tool Implementations -----
        
        async def query_prometheus(query: str, time: Optional[str] = None) -> str:
            """Execute instant PromQL query."""
            result = await self._query_prometheus(query, time)
            return self._format_prometheus_result(result)
        
        async def query_range(
            query: str,
            duration: str = "1h",
            step: str = "1m",
        ) -> str:
            """Execute range PromQL query over a time window."""
            now = datetime.now(timezone.utc)
            
            # Parse duration
            duration_map = {
                "5m": timedelta(minutes=5),
                "15m": timedelta(minutes=15),
                "30m": timedelta(minutes=30),
                "1h": timedelta(hours=1),
                "3h": timedelta(hours=3),
                "6h": timedelta(hours=6),
                "12h": timedelta(hours=12),
                "24h": timedelta(hours=24),
                "1d": timedelta(days=1),
                "7d": timedelta(days=7),
            }
            
            delta = duration_map.get(duration, timedelta(hours=1))
            start = (now - delta).isoformat() + "Z"
            end = now.isoformat() + "Z"
            
            result = await self._query_prometheus_range(query, start, end, step)
            return self._format_prometheus_result(result)
        
        async def get_error_rate(
            service: str,
            window: str = "5m",
            status_codes: str = "5..",
        ) -> str:
            """Query HTTP error rate for a service."""
            query = f'sum(rate(http_requests_total{{service="{service}",status=~"{status_codes}"}}[{window}])) / sum(rate(http_requests_total{{service="{service}"}}[{window}])) * 100'
            result = await self._query_prometheus(query)
            formatted = self._format_prometheus_result(result)
            return f"Error rate (status {status_codes}) for {service} over {window}:\n{formatted}"
        
        async def get_latency_percentiles(
            service: str,
            percentiles: str = "50,90,99",
            window: str = "5m",
        ) -> str:
            """Query request latency percentiles for a service."""
            results = []
            for p in percentiles.split(","):
                p_val = float(p) / 100
                query = f'histogram_quantile({p_val}, sum(rate(http_request_duration_seconds_bucket{{service="{service}"}}[{window}])) by (le))'
                result = await self._query_prometheus(query)
                formatted = self._format_prometheus_result(result)
                results.append(f"P{p}: {formatted}")
            return f"Latency percentiles for {service} over {window}:\n" + "\n".join(results)
        
        async def get_resource_usage(
            pod: str,
            namespace: Optional[str] = None,
            window: str = "5m",
        ) -> str:
            """Query CPU and memory usage for a pod."""
            ns_filter = f',namespace="{namespace}"' if namespace else ""
            
            cpu_query = f'sum(rate(container_cpu_usage_seconds_total{{pod=~"{pod}.*"{ns_filter}}}[{window}])) by (pod)'
            mem_query = f'sum(container_memory_usage_bytes{{pod=~"{pod}.*"{ns_filter}}}) by (pod)'
            
            cpu_result = await self._query_prometheus(cpu_query)
            mem_result = await self._query_prometheus(mem_query)
            
            return f"""Resource usage for pods matching '{pod}':

**CPU Usage (cores over {window})**:
{self._format_prometheus_result(cpu_result)}

**Memory Usage (bytes)**:
{self._format_prometheus_result(mem_result)}"""
        
        async def get_request_rate(
            service: str,
            window: str = "5m",
            group_by: str = "status",
        ) -> str:
            """Query request rate for a service, grouped by dimension."""
            query = f'sum(rate(http_requests_total{{service="{service}"}}[{window}])) by ({group_by})'
            result = await self._query_prometheus(query)
            return f"Request rate for {service} over {window} by {group_by}:\n{self._format_prometheus_result(result)}"
        
        async def get_alerts() -> str:
            """Get currently firing alerts from Prometheus."""
            result = await self._get_alerts()
            
            if result.get("status") == "error":
                return f"Error fetching alerts: {result.get('error')}"
            
            if result.get("_dry_run"):
                return "[DRY RUN] Would fetch active alerts"
            
            alerts = result.get("data", {}).get("alerts", [])
            
            if not alerts:
                return "No alerts currently firing."
            
            lines = [f"Found {len(alerts)} firing alerts:", ""]
            for alert in alerts[:20]:
                name = alert.get("labels", {}).get("alertname", "unknown")
                severity = alert.get("labels", {}).get("severity", "unknown")
                state = alert.get("state", "unknown")
                summary = alert.get("annotations", {}).get("summary", "No summary")
                lines.append(f"- [{severity}] {name} ({state}): {summary}")
            
            if len(alerts) > 20:
                lines.append(f"... and {len(alerts) - 20} more alerts")
            
            return "\n".join(lines)
        
        async def compare_to_baseline(
            query: str,
            baseline_offset: str = "1d",
        ) -> str:
            """Compare current metric value to historical baseline."""
            # Current value
            current_result = await self._query_prometheus(query)
            
            # Offset query for baseline
            offset_query = f"{query} offset {baseline_offset}"
            baseline_result = await self._query_prometheus(offset_query)
            
            return f"""Comparing '{query}' to {baseline_offset} ago:

**Current**:
{self._format_prometheus_result(current_result)}

**Baseline ({baseline_offset} ago)**:
{self._format_prometheus_result(baseline_result)}"""
        
        async def custom_query(
            query: str,
            range_duration: Optional[str] = None,
        ) -> str:
            """Execute a custom PromQL query."""
            if range_duration:
                return await query_range(query, range_duration)
            else:
                result = await self._query_prometheus(query)
                return f"Query: {query}\n\n{self._format_prometheus_result(result)}"
        
        # ----- Build Tool Objects -----
        
        return [
            create_tool(
                name="query_prometheus",
                description="Execute an instant PromQL query. Returns current values for matching time series.",
                executor=query_prometheus,
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "PromQL query expression"},
                        "time": {"type": "string", "description": "Evaluation timestamp (ISO8601 or Unix)"},
                    },
                    "required": ["query"],
                },
            ),
            create_tool(
                name="query_range",
                description="Execute a range PromQL query over a time window. Returns time series data.",
                executor=query_range,
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "PromQL query expression"},
                        "duration": {"type": "string", "description": "Time window (5m, 1h, 24h, etc.)"},
                        "step": {"type": "string", "description": "Query resolution (default: 1m)"},
                    },
                    "required": ["query"],
                },
            ),
            create_tool(
                name="get_error_rate",
                description="Calculate HTTP error rate percentage for a service. Essential for diagnosing service issues.",
                executor=get_error_rate,
                parameters={
                    "type": "object",
                    "properties": {
                        "service": {"type": "string", "description": "Service name"},
                        "window": {"type": "string", "description": "Rate window (default: 5m)"},
                        "status_codes": {"type": "string", "description": "Status code regex (default: 5.. for 5xx)"},
                    },
                    "required": ["service"],
                },
            ),
            create_tool(
                name="get_latency_percentiles",
                description="Get request latency percentiles (P50, P90, P99) for a service.",
                executor=get_latency_percentiles,
                parameters={
                    "type": "object",
                    "properties": {
                        "service": {"type": "string", "description": "Service name"},
                        "percentiles": {"type": "string", "description": "Comma-separated percentiles (default: 50,90,99)"},
                        "window": {"type": "string", "description": "Rate window (default: 5m)"},
                    },
                    "required": ["service"],
                },
            ),
            create_tool(
                name="get_resource_usage",
                description="Get CPU and memory usage for pods. Useful for resource exhaustion issues.",
                executor=get_resource_usage,
                parameters={
                    "type": "object",
                    "properties": {
                        "pod": {"type": "string", "description": "Pod name or regex pattern"},
                        "namespace": {"type": "string", "description": "Namespace filter"},
                        "window": {"type": "string", "description": "Rate window for CPU (default: 5m)"},
                    },
                    "required": ["pod"],
                },
            ),
            create_tool(
                name="get_request_rate",
                description="Get request rate for a service, optionally grouped by status code or other dimension.",
                executor=get_request_rate,
                parameters={
                    "type": "object",
                    "properties": {
                        "service": {"type": "string", "description": "Service name"},
                        "window": {"type": "string", "description": "Rate window (default: 5m)"},
                        "group_by": {"type": "string", "description": "Dimension to group by (default: status)"},
                    },
                    "required": ["service"],
                },
            ),
            create_tool(
                name="get_alerts",
                description="Get all currently firing alerts from Prometheus Alertmanager.",
                executor=get_alerts,
                parameters={"type": "object", "properties": {}},
            ),
            create_tool(
                name="compare_to_baseline",
                description="Compare current metric value to historical baseline. Good for detecting anomalies.",
                executor=compare_to_baseline,
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "PromQL query to compare"},
                        "baseline_offset": {"type": "string", "description": "How far back to compare (default: 1d)"},
                    },
                    "required": ["query"],
                },
            ),
            create_tool(
                name="custom_query",
                description="Execute any custom PromQL query. Use for ad-hoc investigation.",
                executor=custom_query,
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "PromQL query expression"},
                        "range_duration": {"type": "string", "description": "If set, execute as range query over this duration"},
                    },
                    "required": ["query"],
                },
            ),
        ]
    
    def get_hypothesis(
        self,
        alert: dict[str, Any],
        hypotheses: list[str],
        service_context: str = "",
    ) -> str:
        """Build metrics-focused hypothesis."""
        if hypotheses:
            return f"Metrics investigation: {'; '.join(hypotheses)}"
        
        alert_name = alert.get("name", alert.get("alert_name", "Unknown"))
        service = alert.get("service", alert.get("labels", {}).get("service", "unknown"))
        
        return f"""Investigating metrics for {service}:
- Check error rates (4xx, 5xx HTTP status codes)
- Examine latency percentiles (P50, P90, P99)
- Look for resource exhaustion (CPU, memory)
- Compare current values to historical baseline
- Check for correlations with related services

Alert: {alert_name}"""


def create_metrics_subagent(
    prometheus_url: str = "http://prometheus:9090",
    alertmanager_url: Optional[str] = None,
    config: Optional[SubagentConfig] = None,
    dry_run: bool = False,
) -> MetricsSubagent:
    """Factory function to create Metrics subagent.
    
    Args:
        prometheus_url: Prometheus API URL
        alertmanager_url: Optional Alertmanager URL
        config: Subagent configuration
        dry_run: If True, don't actually query Prometheus
    """
    return MetricsSubagent(
        config=config,
        prometheus_url=prometheus_url,
        alertmanager_url=alertmanager_url,
        dry_run=dry_run,
    )
