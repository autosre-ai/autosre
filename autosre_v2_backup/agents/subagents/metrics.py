"""
Metrics Subagent — Investigates metrics and observability data.

Capabilities:
- Prometheus queries (PromQL)
- Anomaly detection
- Resource usage analysis
- Error rate and latency metrics
"""

import logging
from typing import Any, Optional

from .base import BaseSubagent, SubagentConfig

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
    ):
        super().__init__(config)
        self.prometheus_url = prometheus_url
    
    async def get_tools(self) -> list[Any]:
        """Return metrics investigation tools."""
        return [
            "query_prometheus",
            "query_range",
            "get_alerts",
            "compare_baseline",
        ]
    
    async def execute_tool(self, tool_name: str, **kwargs: Any) -> str:
        """Execute a metrics tool.
        
        In a real implementation, this would query Prometheus/VictoriaMetrics.
        """
        self.record_tool_call(tool_name, kwargs, f"Would execute: {tool_name}")
        
        if tool_name == "query_prometheus":
            return f"[Would query: {kwargs.get('query', 'unknown')}]"
        elif tool_name == "query_range":
            return f"[Would query range: {kwargs.get('query', 'unknown')}]"
        elif tool_name == "get_alerts":
            return "[Would fetch active alerts from Alertmanager]"
        elif tool_name == "compare_baseline":
            return f"[Would compare {kwargs.get('metric', 'unknown')} to baseline]"
        else:
            return f"Unknown tool: {tool_name}"
    
    async def _run_investigation(
        self,
        alert: dict[str, Any],
        hypotheses: list[str],
        service_context: str,
        llm_client: Optional[Any],
    ) -> str:
        """Run metrics investigation."""
        service_name = alert.get("service", alert.get("name", "unknown"))
        
        findings = []
        self._loop_count = 0
        
        # Check error rate
        self._loop_count += 1
        error_query = f'rate(http_requests_total{{service="{service_name}",status=~"5.."}}[5m])'
        error_result = await self.execute_tool("query_prometheus", query=error_query)
        self.add_evidence(
            skill="query_prometheus",
            query=error_query,
            result=error_result,
            relevance=0.8,
        )
        findings.append(f"**Error Rate Query**: {error_result}")
        
        # Check latency
        self._loop_count += 1
        latency_query = f'histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{{service="{service_name}"}}[5m]))'
        latency_result = await self.execute_tool("query_prometheus", query=latency_query)
        self.add_evidence(
            skill="query_prometheus",
            query=latency_query,
            result=latency_result,
            relevance=0.7,
        )
        findings.append(f"**P99 Latency Query**: {latency_result}")
        
        # Check resource usage
        self._loop_count += 1
        cpu_query = f'rate(container_cpu_usage_seconds_total{{container="{service_name}"}}[5m])'
        cpu_result = await self.execute_tool("query_prometheus", query=cpu_query)
        self.add_evidence(
            skill="query_prometheus",
            query=cpu_query,
            result=cpu_result,
            relevance=0.6,
        )
        findings.append(f"**CPU Usage Query**: {cpu_result}")
        
        # Check active alerts
        self._loop_count += 1
        alerts_result = await self.execute_tool("get_alerts")
        self.add_evidence(
            skill="get_alerts",
            query="Get active alerts",
            result=alerts_result,
            relevance=0.9,
        )
        findings.append(f"**Active Alerts**: {alerts_result}")
        
        summary = f"""## Metrics Investigation: {service_name}

{chr(10).join(findings)}

### Summary
Queried error rates, latency, CPU usage, and active alerts for {service_name}.
This is a placeholder - real implementation would query actual Prometheus.

**Metrics Checked**:
- HTTP 5xx error rate
- P99 request latency
- Container CPU usage
- Active Alertmanager alerts

**Confidence**: Low (placeholder data)
**Recommendation**: Implement actual Prometheus integration.
"""
        
        return summary


def create_metrics_subagent(
    prometheus_url: str = "http://prometheus:9090",
    config: Optional[SubagentConfig] = None,
) -> MetricsSubagent:
    """Factory function to create Metrics subagent."""
    return MetricsSubagent(config=config, prometheus_url=prometheus_url)
