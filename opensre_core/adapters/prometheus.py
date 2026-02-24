"""
Prometheus Adapter - Query metrics and alerts
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import httpx
from prometheus_api_client import PrometheusConnect

from opensre_core.config import settings


@dataclass
class MetricResult:
    """Result from a Prometheus query."""
    metric_name: str
    labels: dict[str, str]
    values: list[tuple[datetime, float]]
    current_value: float | None = None


@dataclass
class AlertResult:
    """Active alert from Prometheus."""
    alert_name: str
    state: str  # firing, pending
    labels: dict[str, str]
    annotations: dict[str, str]
    started_at: datetime | None = None


class PrometheusAdapter:
    """Adapter for Prometheus metrics and alerts."""
    
    def __init__(self, url: str | None = None):
        self.url = url or settings.prometheus_url
        self._client: PrometheusConnect | None = None
    
    @property
    def client(self) -> PrometheusConnect:
        """Lazy-initialize Prometheus client."""
        if self._client is None:
            self._client = PrometheusConnect(url=self.url, disable_ssl=True)
        return self._client
    
    async def health_check(self) -> dict[str, Any]:
        """Check Prometheus connection."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.url}/-/healthy", timeout=5)
            response.raise_for_status()
            return {"status": "healthy", "details": f"Connected to {self.url}"}
    
    async def query(self, promql: str) -> list[MetricResult]:
        """Execute instant PromQL query."""
        result = self.client.custom_query(query=promql)
        return self._parse_instant_result(result)
    
    async def query_range(
        self,
        promql: str,
        start: datetime | None = None,
        end: datetime | None = None,
        step: str = "15s",
    ) -> list[MetricResult]:
        """Execute range PromQL query."""
        end = end or datetime.now()
        start = start or (end - timedelta(hours=1))
        
        result = self.client.custom_query_range(
            query=promql,
            start_time=start,
            end_time=end,
            step=step,
        )
        return self._parse_range_result(result)
    
    async def get_alerts(self, state: str | None = None) -> list[AlertResult]:
        """Get active alerts."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.url}/api/v1/alerts", timeout=10)
            response.raise_for_status()
            data = response.json()
        
        alerts = []
        for alert in data.get("data", {}).get("alerts", []):
            if state and alert.get("state") != state:
                continue
            alerts.append(AlertResult(
                alert_name=alert.get("labels", {}).get("alertname", "unknown"),
                state=alert.get("state", "unknown"),
                labels=alert.get("labels", {}),
                annotations=alert.get("annotations", {}),
                started_at=self._parse_time(alert.get("activeAt")),
            ))
        
        return alerts
    
    async def get_service_metrics(self, service: str, namespace: str = "default") -> dict[str, Any]:
        """Get common metrics for a service."""
        queries = {
            "cpu_usage": f'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}", pod=~"{service}.*"}}[5m])) by (pod)',
            "memory_usage": f'sum(container_memory_usage_bytes{{namespace="{namespace}", pod=~"{service}.*"}}) by (pod)',
            "request_rate": f'sum(rate(http_requests_total{{namespace="{namespace}", service="{service}"}}[5m]))',
            "error_rate": f'sum(rate(http_requests_total{{namespace="{namespace}", service="{service}", status=~"5.."}}[5m])) / sum(rate(http_requests_total{{namespace="{namespace}", service="{service}"}}[5m]))',
            "latency_p99": f'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{{namespace="{namespace}", service="{service}"}}[5m])) by (le))',
        }
        
        results = {}
        for name, query in queries.items():
            try:
                metrics = await self.query(query)
                if metrics:
                    results[name] = metrics[0].current_value
            except Exception:
                results[name] = None
        
        return results
    
    async def find_anomalies(self, service: str, namespace: str = "default") -> list[dict[str, Any]]:
        """Detect metric anomalies for a service."""
        anomalies = []
        metrics = await self.get_service_metrics(service, namespace)
        
        # Simple threshold-based anomaly detection
        if metrics.get("cpu_usage") and metrics["cpu_usage"] > 0.8:
            anomalies.append({
                "type": "high_cpu",
                "severity": "warning",
                "value": metrics["cpu_usage"],
                "message": f"CPU usage at {metrics['cpu_usage']:.1%}",
            })
        
        if metrics.get("error_rate") and metrics["error_rate"] > 0.01:
            anomalies.append({
                "type": "high_error_rate",
                "severity": "critical",
                "value": metrics["error_rate"],
                "message": f"Error rate at {metrics['error_rate']:.2%}",
            })
        
        if metrics.get("latency_p99") and metrics["latency_p99"] > 1.0:
            anomalies.append({
                "type": "high_latency",
                "severity": "warning",
                "value": metrics["latency_p99"],
                "message": f"P99 latency at {metrics['latency_p99']:.2f}s",
            })
        
        return anomalies
    
    def _parse_instant_result(self, result: list) -> list[MetricResult]:
        """Parse instant query result."""
        metrics = []
        for item in result:
            metric = item.get("metric", {})
            value = item.get("value", [])
            
            metrics.append(MetricResult(
                metric_name=metric.get("__name__", "unknown"),
                labels={k: v for k, v in metric.items() if k != "__name__"},
                values=[],
                current_value=float(value[1]) if len(value) > 1 else None,
            ))
        
        return metrics
    
    def _parse_range_result(self, result: list) -> list[MetricResult]:
        """Parse range query result."""
        metrics = []
        for item in result:
            metric = item.get("metric", {})
            values = item.get("values", [])
            
            parsed_values = [
                (datetime.fromtimestamp(v[0]), float(v[1]))
                for v in values
            ]
            
            metrics.append(MetricResult(
                metric_name=metric.get("__name__", "unknown"),
                labels={k: v for k, v in metric.items() if k != "__name__"},
                values=parsed_values,
                current_value=parsed_values[-1][1] if parsed_values else None,
            ))
        
        return metrics
    
    def _parse_time(self, time_str: str | None) -> datetime | None:
        """Parse ISO timestamp."""
        if not time_str:
            return None
        try:
            return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        except ValueError:
            return None
