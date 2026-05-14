"""
Investigation Agent for AutoSRE V2.

Performs deep investigation into specific domains (metrics, logs, kubernetes, traces)
using the ReAct pattern with specialized tools.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from autosre.agents.base_agent import AgentResult, BaseAgent, ToolRegistry
from autosre.core.investigation import Evidence, EvidenceType, Finding, Investigation
from autosre.integrations.kubernetes import KubernetesClient
from autosre.integrations.loki import LokiClient
from autosre.integrations.prometheus import PrometheusClient
from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class InvestigationDomain(str, Enum):
    """Investigation domains."""

    KUBERNETES = "kubernetes"
    METRICS = "metrics"
    LOGS = "logs"
    TRACES = "traces"


class InvestigationAgent(BaseAgent):
    """
    Investigation agent for deep domain-specific analysis.

    Supports multiple domains (kubernetes, metrics, logs, traces)
    with specialized tools for each.
    """

    agent_id = "investigation"
    agent_name = "Investigation Agent"
    description = "Performs deep investigation using domain-specific tools"

    SYSTEM_PROMPT_TEMPLATE = """You are the {domain_name} Investigation Agent for an AI SRE system.

Your role is to INVESTIGATE a production incident by gathering evidence from {domain_name}.

## Investigation Context
Alert: {alert_summary}
Service: {service_name}
Namespace: {namespace}

## Service Context
{service_context}

## Hypotheses to Test
{hypotheses}

## Available Tools
{tool_descriptions}

## Investigation Guidelines
1. Start with the most relevant queries for this alert type
2. Look for anomalies, errors, and correlations
3. Test each hypothesis systematically
4. Collect concrete evidence (metrics, logs, events)
5. Stop when you have sufficient evidence or have exhausted useful queries

## Rules
- NEVER modify production resources - investigation is read-only
- Do NOT call the same tool with identical arguments twice
- Do NOT fabricate data - if a query returns nothing, report "no data found"
- If this domain has no relevant signals, say so and stop early
- Report WHAT you found (or didn't find), with evidence

## Output
Provide a clear summary of your findings with:
- What evidence you found
- Which hypotheses you can confirm or reject
- Your confidence level
- Recommendations for next steps
"""

    def __init__(
        self,
        domain: InvestigationDomain = InvestigationDomain.KUBERNETES,
        prometheus_client: PrometheusClient | None = None,
        kubernetes_client: KubernetesClient | None = None,
        loki_client: LokiClient | None = None,
        **kwargs,
    ):
        """
        Initialize investigation agent.

        Args:
            domain: Investigation domain
            prometheus_client: Prometheus client (created if not provided)
            kubernetes_client: Kubernetes client (created if not provided)
            loki_client: Loki client (created if not provided)
            **kwargs: Passed to BaseAgent
        """
        self.domain = domain
        self.agent_id = f"investigation_{domain.value}"
        self.agent_name = f"{domain.value.title()} Investigation Agent"

        super().__init__(**kwargs)

        # Initialize clients
        self.prometheus = prometheus_client or PrometheusClient()
        self.kubernetes = kubernetes_client or KubernetesClient()
        self.loki = loki_client or LokiClient()

        # Register domain-specific tools
        self._register_domain_tools()

    def _register_domain_tools(self) -> None:
        """Register tools based on domain."""
        if self.domain == InvestigationDomain.KUBERNETES:
            self._register_kubernetes_tools()
        elif self.domain == InvestigationDomain.METRICS:
            self._register_metrics_tools()
        elif self.domain == InvestigationDomain.LOGS:
            self._register_logs_tools()
        elif self.domain == InvestigationDomain.TRACES:
            self._register_traces_tools()

    def _register_kubernetes_tools(self) -> None:
        """Register Kubernetes investigation tools."""
        self.tools.register(
            name="get_pod_status",
            description="Get status of pods for a service, including container states and restarts",
            parameters={
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "Service/app name"},
                    "namespace": {"type": "string", "description": "Kubernetes namespace"},
                },
                "required": ["service", "namespace"],
            },
            handler=self._tool_get_pod_status,
        )

        self.tools.register(
            name="get_pod_events",
            description="Get recent Kubernetes events for pods, including warnings",
            parameters={
                "type": "object",
                "properties": {
                    "pod_name": {"type": "string", "description": "Pod name or pattern"},
                    "namespace": {"type": "string", "description": "Kubernetes namespace"},
                },
                "required": ["pod_name", "namespace"],
            },
            handler=self._tool_get_pod_events,
        )

        self.tools.register(
            name="get_deployment_status",
            description="Get deployment status including replica counts and conditions",
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Deployment name"},
                    "namespace": {"type": "string", "description": "Kubernetes namespace"},
                },
                "required": ["name", "namespace"],
            },
            handler=self._tool_get_deployment_status,
        )

        self.tools.register(
            name="get_pod_logs",
            description="Get recent logs from a pod",
            parameters={
                "type": "object",
                "properties": {
                    "pod_name": {"type": "string", "description": "Pod name"},
                    "namespace": {"type": "string", "description": "Kubernetes namespace"},
                    "container": {"type": "string", "description": "Container name (optional)"},
                    "tail_lines": {"type": "integer", "description": "Number of lines (default: 100)"},
                },
                "required": ["pod_name", "namespace"],
            },
            handler=self._tool_get_pod_logs,
        )

        self.tools.register(
            name="get_warning_events",
            description="Get all Warning events in a namespace",
            parameters={
                "type": "object",
                "properties": {
                    "namespace": {"type": "string", "description": "Kubernetes namespace"},
                    "limit": {"type": "integer", "description": "Max events (default: 50)"},
                },
                "required": ["namespace"],
            },
            handler=self._tool_get_warning_events,
        )

    def _register_metrics_tools(self) -> None:
        """Register Prometheus metrics tools."""
        self.tools.register(
            name="query_metrics",
            description="Execute a PromQL instant query",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "PromQL query"},
                },
                "required": ["query"],
            },
            handler=self._tool_query_metrics,
        )

        self.tools.register(
            name="query_range",
            description="Execute a PromQL range query over time",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "PromQL query"},
                    "duration": {"type": "string", "description": "Time range, e.g., '1h', '30m'"},
                    "step": {"type": "string", "description": "Query step, e.g., '1m', '15s'"},
                },
                "required": ["query"],
            },
            handler=self._tool_query_range,
        )

        self.tools.register(
            name="get_error_rate",
            description="Get error rate for a service",
            parameters={
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "Service name"},
                    "duration": {"type": "string", "description": "Time window, e.g., '5m'"},
                    "namespace": {"type": "string", "description": "Namespace (optional)"},
                },
                "required": ["service"],
            },
            handler=self._tool_get_error_rate,
        )

        self.tools.register(
            name="get_latency",
            description="Get latency percentiles for a service",
            parameters={
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "Service name"},
                    "percentile": {"type": "number", "description": "Percentile, e.g., 0.99"},
                    "duration": {"type": "string", "description": "Time window, e.g., '5m'"},
                },
                "required": ["service"],
            },
            handler=self._tool_get_latency,
        )

        self.tools.register(
            name="get_resource_usage",
            description="Get CPU and memory usage for pods",
            parameters={
                "type": "object",
                "properties": {
                    "pod_pattern": {"type": "string", "description": "Pod name pattern (regex)"},
                    "namespace": {"type": "string", "description": "Namespace"},
                },
                "required": ["pod_pattern", "namespace"],
            },
            handler=self._tool_get_resource_usage,
        )

    def _register_logs_tools(self) -> None:
        """Register Loki log tools."""
        self.tools.register(
            name="query_logs",
            description="Execute a LogQL query",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "LogQL query"},
                    "duration": {"type": "string", "description": "Time range, e.g., '1h'"},
                    "limit": {"type": "integer", "description": "Max entries (default: 200)"},
                },
                "required": ["query"],
            },
            handler=self._tool_query_logs,
        )

        self.tools.register(
            name="search_errors",
            description="Search for error logs in a service",
            parameters={
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "Service name"},
                    "namespace": {"type": "string", "description": "Namespace (optional)"},
                    "duration": {"type": "string", "description": "Time range (default: 1h)"},
                },
                "required": ["service"],
            },
            handler=self._tool_search_errors,
        )

        self.tools.register(
            name="search_pattern",
            description="Search logs for a specific pattern",
            parameters={
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "Service name"},
                    "pattern": {"type": "string", "description": "Pattern to search for"},
                    "duration": {"type": "string", "description": "Time range (default: 1h)"},
                },
                "required": ["service", "pattern"],
            },
            handler=self._tool_search_pattern,
        )

    def _register_traces_tools(self) -> None:
        """Register tracing tools (placeholder for integration)."""
        self.tools.register(
            name="search_traces",
            description="Search for traces by service and operation",
            parameters={
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "Service name"},
                    "operation": {"type": "string", "description": "Operation name (optional)"},
                    "min_duration": {"type": "string", "description": "Minimum duration, e.g., '100ms'"},
                },
                "required": ["service"],
            },
            handler=self._tool_search_traces,
        )

    # Tool implementations

    async def _tool_get_pod_status(self, service: str, namespace: str) -> str:
        """Get pod status for a service."""
        try:
            pods = await self.kubernetes.list_pods(
                namespace=namespace,
                label_selector=f"app={service}",
            )

            if not pods:
                return f"No pods found for service '{service}' in namespace '{namespace}'"

            results = []
            for pod in pods:
                status_line = f"Pod: {pod.name} | Phase: {pod.phase.value} | Ready: {pod.ready}"
                if pod.restart_count > 0:
                    status_line += f" | Restarts: {pod.restart_count}"

                results.append(status_line)

                # Add container details if unhealthy
                for container in pod.get_unhealthy_containers():
                    results.append(
                        f"  Container {container.name}: {container.state.value}"
                        f" - {container.state_reason or 'unknown reason'}"
                    )

            return "\n".join(results)

        except Exception as e:
            return f"Error getting pod status: {e}"

    async def _tool_get_pod_events(self, pod_name: str, namespace: str) -> str:
        """Get events for a pod."""
        try:
            events = await self.kubernetes.get_pod_events(pod_name, namespace)

            if not events:
                return f"No events found for pod '{pod_name}'"

            results = []
            for event in events[:20]:  # Limit to 20 events
                results.append(
                    f"[{event.type}] {event.reason}: {event.message}"
                    f" (count: {event.count})"
                )

            return "\n".join(results)

        except Exception as e:
            return f"Error getting pod events: {e}"

    async def _tool_get_deployment_status(self, name: str, namespace: str) -> str:
        """Get deployment status."""
        try:
            deploy = await self.kubernetes.get_deployment(name, namespace)

            if not deploy:
                return f"Deployment '{name}' not found in namespace '{namespace}'"

            status = (
                f"Deployment: {deploy.name}\n"
                f"Replicas: {deploy.ready_replicas}/{deploy.replicas} ready, "
                f"{deploy.available_replicas} available, {deploy.updated_replicas} updated\n"
                f"Strategy: {deploy.strategy}\n"
                f"Healthy: {deploy.is_healthy}"
            )

            if deploy.conditions:
                status += "\nConditions:"
                for c in deploy.conditions:
                    status += f"\n  {c['type']}: {c['status']} - {c.get('message', '')}"

            return status

        except Exception as e:
            return f"Error getting deployment status: {e}"

    async def _tool_get_pod_logs(
        self,
        pod_name: str,
        namespace: str,
        container: str | None = None,
        tail_lines: int = 100,
    ) -> str:
        """Get pod logs."""
        try:
            logs = await self.kubernetes.get_pod_logs(
                name=pod_name,
                namespace=namespace,
                container=container,
                tail_lines=tail_lines,
            )
            return logs[:10000]  # Truncate to 10KB

        except Exception as e:
            return f"Error getting pod logs: {e}"

    async def _tool_get_warning_events(
        self,
        namespace: str,
        limit: int = 50,
    ) -> str:
        """Get warning events in namespace."""
        try:
            events = await self.kubernetes.get_events(
                namespace=namespace,
                warning_only=True,
                limit=limit,
            )

            if not events:
                return f"No warning events in namespace '{namespace}'"

            results = []
            for event in events:
                obj = event.involved_object
                results.append(
                    f"[{event.reason}] {obj.get('kind', 'Unknown')}/{obj.get('name', 'unknown')}: "
                    f"{event.message} (count: {event.count})"
                )

            return "\n".join(results)

        except Exception as e:
            return f"Error getting events: {e}"

    async def _tool_query_metrics(self, query: str) -> str:
        """Execute instant metrics query."""
        try:
            results = await self.prometheus.query(query)

            if not results:
                return f"Query returned no results: {query}"

            output = []
            for r in results[:20]:  # Limit results
                labels = ", ".join(f"{k}={v}" for k, v in r.labels.items())
                output.append(f"{r.name}{{{labels}}} = {r.value}")

            return "\n".join(output)

        except Exception as e:
            return f"Error executing query: {e}"

    async def _tool_query_range(
        self,
        query: str,
        duration: str = "1h",
        step: str = "1m",
    ) -> str:
        """Execute range metrics query."""
        try:
            result = await self.prometheus.query_range(
                query=query,
                duration=timedelta(hours=1) if duration == "1h" else timedelta(minutes=int(duration[:-1])),
                step=step,
            )

            if result.is_empty:
                return f"Query returned no results: {query}"

            output = []
            for r in result.results[:10]:  # Limit to 10 series
                labels = ", ".join(f"{k}={v}" for k, v in r.labels.items())
                latest = r.values[-1].value if r.values else "N/A"
                output.append(f"{r.name}{{{labels}}} latest={latest}, points={len(r.values)}")

            return "\n".join(output)

        except Exception as e:
            return f"Error executing range query: {e}"

    async def _tool_get_error_rate(
        self,
        service: str,
        duration: str = "5m",
        namespace: str | None = None,
    ) -> str:
        """Get error rate for a service."""
        try:
            rate = await self.prometheus.get_error_rate(service, duration, namespace)

            if rate is None:
                return f"No error rate data found for service '{service}'"

            return f"Error rate for {service}: {rate*100:.2f}% over {duration}"

        except Exception as e:
            return f"Error getting error rate: {e}"

    async def _tool_get_latency(
        self,
        service: str,
        percentile: float = 0.99,
        duration: str = "5m",
    ) -> str:
        """Get latency percentile for a service."""
        try:
            latency = await self.prometheus.get_latency_percentile(
                service, percentile, duration
            )

            if latency is None:
                return f"No latency data found for service '{service}'"

            return f"p{int(percentile*100)} latency for {service}: {latency*1000:.2f}ms over {duration}"

        except Exception as e:
            return f"Error getting latency: {e}"

    async def _tool_get_resource_usage(
        self,
        pod_pattern: str,
        namespace: str,
    ) -> str:
        """Get resource usage for pods."""
        try:
            usage = await self.prometheus.get_resource_usage(
                pod_pattern=pod_pattern,
                namespace=namespace,
            )

            results = []
            for pod, cpu in usage.get("cpu", {}).items():
                mem = usage.get("memory", {}).get(pod, 0)
                results.append(
                    f"{pod}: CPU={cpu:.3f} cores, Memory={mem/1024/1024:.1f}MB"
                )

            return "\n".join(results) if results else "No resource data found"

        except Exception as e:
            return f"Error getting resource usage: {e}"

    async def _tool_query_logs(
        self,
        query: str,
        duration: str = "1h",
        limit: int = 200,
    ) -> str:
        """Execute LogQL query."""
        try:
            result = await self.loki.query(
                query=query,
                duration=duration,
                limit=limit,
            )

            if result.is_empty:
                return f"Query returned no logs: {query}"

            entries = result.all_entries()[:50]  # Limit output
            output = []
            for entry in entries:
                ts = entry.timestamp.strftime("%H:%M:%S")
                output.append(f"[{ts}] {entry.line[:500]}")

            return "\n".join(output)

        except Exception as e:
            return f"Error querying logs: {e}"

    async def _tool_search_errors(
        self,
        service: str,
        namespace: str | None = None,
        duration: str = "1h",
    ) -> str:
        """Search for error logs."""
        try:
            result = await self.loki.search_errors(
                service=service,
                namespace=namespace,
                duration=duration,
            )

            if result.is_empty:
                return f"No error logs found for service '{service}'"

            unique_errors = result.get_unique_error_messages(limit=10)
            return "Unique error messages:\n" + "\n---\n".join(unique_errors)

        except Exception as e:
            return f"Error searching logs: {e}"

    async def _tool_search_pattern(
        self,
        service: str,
        pattern: str,
        duration: str = "1h",
    ) -> str:
        """Search logs for a pattern."""
        try:
            result = await self.loki.query_service(
                service=service,
                pattern=pattern,
                duration=duration,
                limit=100,
            )

            if result.is_empty:
                return f"Pattern '{pattern}' not found in logs for '{service}'"

            entries = result.all_entries()[:20]
            output = []
            for entry in entries:
                ts = entry.timestamp.strftime("%H:%M:%S")
                output.append(f"[{ts}] {entry.line[:300]}")

            return "\n".join(output)

        except Exception as e:
            return f"Error searching pattern: {e}"

    async def _tool_search_traces(
        self,
        service: str,
        operation: str | None = None,
        min_duration: str | None = None,
    ) -> str:
        """Search traces (placeholder)."""
        return (
            f"Trace search for service='{service}', operation='{operation}', "
            f"min_duration='{min_duration}' - Tracing integration not configured"
        )

    def get_system_prompt(self, investigation: Investigation) -> str:
        """Generate system prompt with context."""
        alert = investigation.alert

        # Format hypotheses
        hypotheses_text = "No specific hypotheses provided."
        if investigation.hypotheses:
            hypotheses_text = "\n".join(
                f"- {h.description} (priority: {h.priority.value})"
                for h in investigation.hypotheses
            )

        # Format tool descriptions
        tool_descs = []
        for tool in self.tools.get_definitions():
            tool_descs.append(f"- {tool.name}: {tool.description}")
        tool_descriptions = "\n".join(tool_descs)

        # Service context
        service_context = ""
        if investigation.service_topology:
            st = investigation.service_topology
            service_context = f"Dependencies: {st.get('dependencies', 'unknown')}"

        return self.SYSTEM_PROMPT_TEMPLATE.format(
            domain_name=self.domain.value.title(),
            alert_summary=alert.summary,
            service_name=alert.service or "unknown",
            namespace=alert.namespace or "default",
            service_context=service_context or "No service topology available.",
            hypotheses=hypotheses_text,
            tool_descriptions=tool_descriptions,
        )

    async def execute(self, investigation: Investigation) -> AgentResult:
        """Execute domain-specific investigation."""
        initial_message = (
            f"Investigate the alert '{investigation.alert.name}' "
            f"using {self.domain.value} tools. "
            f"Focus on testing the provided hypotheses and gathering evidence."
        )

        return await self.run_react_loop(
            investigation=investigation,
            initial_message=initial_message,
        )
