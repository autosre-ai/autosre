"""
Metrics Subagent — Investigates using Prometheus metrics.

Skills:
- query_prometheus: Execute PromQL queries
- query_range: Execute range queries
- find_anomalies: Detect metric anomalies
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from urllib.parse import urljoin

from .base import BaseSubagent, Skill

logger = logging.getLogger(__name__)


class PrometheusSkill(Skill):
    """Base skill for Prometheus queries."""
    
    prometheus_url: str = "http://localhost:9090"
    
    async def query_prom(
        self,
        query: str,
        time: Optional[datetime] = None,
    ) -> str:
        """Execute instant query."""
        try:
            import httpx
        except ImportError:
            return "Error: httpx not installed. Run: pip install httpx"
        
        url = urljoin(self.prometheus_url, "/api/v1/query")
        params = {"query": query}
        
        if time:
            params["time"] = time.isoformat()
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                if data.get("status") != "success":
                    return f"Error: {data.get('error', 'Unknown error')}"
                
                results = data.get("data", {}).get("result", [])
                if not results:
                    return "No data found"
                
                # Format results
                lines = []
                for r in results[:20]:  # Limit results
                    metric = r.get("metric", {})
                    value = r.get("value", [None, None])
                    labels = ", ".join(f"{k}={v}" for k, v in metric.items())
                    lines.append(f"{labels}: {value[1]}")
                
                return "\n".join(lines) or "No data found"
                
        except httpx.HTTPError as e:
            return f"HTTP Error: {e}"
        except Exception as e:
            return f"Error: {e}"
    
    async def query_range_prom(
        self,
        query: str,
        start: datetime,
        end: datetime,
        step: str = "1m",
    ) -> str:
        """Execute range query."""
        try:
            import httpx
        except ImportError:
            return "Error: httpx not installed"
        
        url = urljoin(self.prometheus_url, "/api/v1/query_range")
        params = {
            "query": query,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "step": step,
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                if data.get("status") != "success":
                    return f"Error: {data.get('error', 'Unknown error')}"
                
                results = data.get("data", {}).get("result", [])
                if not results:
                    return "No data found"
                
                # Summarize results
                lines = []
                for r in results[:10]:
                    metric = r.get("metric", {})
                    values = r.get("values", [])
                    labels = ", ".join(f"{k}={v}" for k, v in metric.items())
                    
                    if values:
                        nums = [float(v[1]) for v in values if v[1] != "NaN"]
                        if nums:
                            lines.append(
                                f"{labels}: min={min(nums):.2f}, max={max(nums):.2f}, "
                                f"avg={sum(nums)/len(nums):.2f} ({len(values)} points)"
                            )
                        else:
                            lines.append(f"{labels}: all NaN values")
                
                return "\n".join(lines) or "No data found"
                
        except Exception as e:
            return f"Error: {e}"


class QueryPrometheusSkill(PrometheusSkill):
    """Execute instant PromQL queries."""
    
    name: str = "query_prometheus"
    description: str = "Execute a PromQL instant query. Returns current metric values."
    parameters: dict[str, Any] = {
        "query": {"type": "string", "description": "PromQL query (e.g., 'rate(http_requests_total[5m])')"},
    }
    
    async def execute(self, query: str, **kwargs: Any) -> str:
        return await self.query_prom(query)


class QueryRangeSkill(PrometheusSkill):
    """Execute PromQL range queries."""
    
    name: str = "query_range"
    description: str = "Execute a PromQL range query over a time period. Good for trend analysis."
    parameters: dict[str, Any] = {
        "query": {"type": "string", "description": "PromQL query"},
        "duration": {"type": "string", "description": "Time range (e.g., '1h', '30m', '6h')"},
        "step": {"type": "string", "description": "Resolution step (default: '1m')"},
    }
    
    async def execute(
        self,
        query: str,
        duration: str = "1h",
        step: str = "1m",
        **kwargs: Any,
    ) -> str:
        # Parse duration
        now = datetime.utcnow()
        
        dur_map = {
            "m": timedelta(minutes=1),
            "h": timedelta(hours=1),
            "d": timedelta(days=1),
        }
        
        unit = duration[-1]
        try:
            amount = int(duration[:-1])
            delta = dur_map.get(unit, timedelta(hours=1)) * amount
        except (ValueError, IndexError):
            delta = timedelta(hours=1)
        
        start = now - delta
        
        return await self.query_range_prom(query, start, now, step)


class ErrorRateSkill(PrometheusSkill):
    """Calculate error rates for a service."""
    
    name: str = "error_rate"
    description: str = "Calculate HTTP error rate (5xx/total) for a service."
    parameters: dict[str, Any] = {
        "service": {"type": "string", "description": "Service name"},
        "duration": {"type": "string", "description": "Time range (default: '5m')"},
    }
    
    async def execute(
        self,
        service: str,
        duration: str = "5m",
        **kwargs: Any,
    ) -> str:
        # Common error rate queries
        queries = [
            f'sum(rate(http_requests_total{{service="{service}",status=~"5.."}}[{duration}])) / sum(rate(http_requests_total{{service="{service}"}}[{duration}]))',
            f'sum(rate(http_server_requests_seconds_count{{service="{service}",status=~"5.."}}[{duration}])) / sum(rate(http_server_requests_seconds_count{{service="{service}"}}[{duration}]))',
        ]
        
        for q in queries:
            result = await self.query_prom(q)
            if result and "No data" not in result and "Error" not in result:
                return f"Error rate for {service}: {result}"
        
        return f"No error rate data found for service: {service}"


class LatencySkill(PrometheusSkill):
    """Get latency percentiles for a service."""
    
    name: str = "latency"
    description: str = "Get p50, p95, p99 latency for a service."
    parameters: dict[str, Any] = {
        "service": {"type": "string", "description": "Service name"},
        "duration": {"type": "string", "description": "Time range (default: '5m')"},
    }
    
    async def execute(
        self,
        service: str,
        duration: str = "5m",
        **kwargs: Any,
    ) -> str:
        results = []
        
        for percentile in [0.5, 0.95, 0.99]:
            query = f'histogram_quantile({percentile}, sum(rate(http_request_duration_seconds_bucket{{service="{service}"}}[{duration}])) by (le))'
            result = await self.query_prom(query)
            if result and "No data" not in result and "Error" not in result:
                results.append(f"p{int(percentile*100)}: {result}")
        
        if results:
            return f"Latency for {service}:\n" + "\n".join(results)
        
        return f"No latency data found for service: {service}"


class MetricsSubagent(BaseSubagent):
    """Prometheus metrics investigation subagent."""
    
    name = "metrics"
    description = "Investigates using Prometheus metrics: error rates, latency, resource usage"
    custom_prompt = """You are an expert at metrics analysis with Prometheus.

Common investigation queries:
1. Error rate: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])
2. Latency: histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))
3. CPU usage: sum(rate(container_cpu_usage_seconds_total{pod=~"service.*"}[5m])) by (pod)
4. Memory: container_memory_usage_bytes{pod=~"service.*"}
5. Rate of change: deriv(metric[5m]) or delta(metric[1h])

Look for:
- Sudden spikes in error rates
- Latency percentile increases
- Resource saturation (CPU > 80%, memory near limits)
- Correlation between services
- Changes that coincide with deployment times"""
    
    def __init__(
        self,
        prometheus_url: str = "http://localhost:9090",
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.prometheus_url = prometheus_url
    
    def get_skills(self) -> list[Skill]:
        """Return available Prometheus skills."""
        skills = [
            QueryPrometheusSkill(prometheus_url=self.prometheus_url),
            QueryRangeSkill(prometheus_url=self.prometheus_url),
            ErrorRateSkill(prometheus_url=self.prometheus_url),
            LatencySkill(prometheus_url=self.prometheus_url),
        ]
        return skills
