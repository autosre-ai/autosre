"""
Observer Agent - Collects data from infrastructure
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from opensre_core.adapters.kubernetes import KubernetesAdapter
from opensre_core.adapters.prometheus import PrometheusAdapter


@dataclass
class Observation:
    """Single observation from infrastructure."""
    source: str  # prometheus, kubernetes, logs
    type: str  # metric, event, pod_status, log
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    severity: str = "info"  # info, warning, critical
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ObservationResult:
    """Collection of observations about an issue."""
    issue: str
    namespace: str
    observations: list[Observation] = field(default_factory=list)
    services_involved: list[str] = field(default_factory=list)
    timespan: str = "1h"

    def to_context(self) -> str:
        """Convert observations to text context for LLM."""
        lines = [
            f"Issue: {self.issue}",
            f"Namespace: {self.namespace}",
            f"Time span: {self.timespan}",
            "",
            "Observations:",
        ]

        for obs in self.observations:
            severity_icon = {"info": "ℹ️", "warning": "⚠️", "critical": "🔴"}[obs.severity]
            lines.append(f"  {severity_icon} [{obs.source}] {obs.summary}")
            if obs.details:
                for k, v in obs.details.items():
                    lines.append(f"      {k}: {v}")

        return "\n".join(lines)


class ObserverAgent:
    """
    Agent that observes infrastructure state.

    Collects:
    - Prometheus metrics and alerts
    - Kubernetes pod status, events, logs
    - Service health indicators
    """

    # Mapping of keywords to Prometheus queries
    METRIC_KEYWORD_QUERIES: dict[str, list[tuple[str, str]]] = {
        "memory": [
            ("container_memory_usage_bytes", 'sum(container_memory_usage_bytes{{namespace="{namespace}"}}) by (pod)'),
            ("container_memory_working_set_bytes", 'sum(container_memory_working_set_bytes{{namespace="{namespace}"}}) by (pod)'),
        ],
        "cpu": [
            ("container_cpu_usage_rate", 'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}"}}[5m])) by (pod)'),
        ],
        "latency": [
            ("http_request_duration_p50", 'histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket{{namespace="{namespace}"}}[5m])) by (le, service))'),
            ("http_request_duration_p99", 'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{{namespace="{namespace}"}}[5m])) by (le, service))'),
        ],
        "error": [
            ("http_5xx_rate", 'sum(rate(http_requests_total{{namespace="{namespace}", status=~"5.."}}[5m])) by (service)'),
            ("http_5xx_count", 'sum(increase(http_requests_total{{namespace="{namespace}", status=~"5.."}}[1h])) by (service)'),
        ],
        "disk": [
            ("container_fs_usage_bytes", 'sum(container_fs_usage_bytes{{namespace="{namespace}"}}) by (pod, device)'),
        ],
        "network": [
            ("container_network_receive_bytes", 'sum(rate(container_network_receive_bytes_total{{namespace="{namespace}"}}[5m])) by (pod)'),
            ("container_network_transmit_bytes", 'sum(rate(container_network_transmit_bytes_total{{namespace="{namespace}"}}[5m])) by (pod)'),
        ],
    }

    # Queries for resource limits (from kube-state-metrics)
    RESOURCE_LIMIT_QUERIES: dict[str, str] = {
        "memory_limit": 'sum(kube_pod_container_resource_limits{{namespace="{namespace}", resource="memory"}}) by (pod)',
        "memory_request": 'sum(kube_pod_container_resource_requests{{namespace="{namespace}", resource="memory"}}) by (pod)',
        "cpu_limit": 'sum(kube_pod_container_resource_limits{{namespace="{namespace}", resource="cpu"}}) by (pod)',
        "cpu_request": 'sum(kube_pod_container_resource_requests{{namespace="{namespace}", resource="cpu"}}) by (pod)',
    }

    def __init__(self):
        self.prometheus = PrometheusAdapter()
        self.kubernetes = KubernetesAdapter()

    async def observe(
        self,
        issue: str,
        namespace: str = "default",
        service: str | None = None,
    ) -> ObservationResult:
        """
        Observe infrastructure state related to an issue.

        Args:
            issue: Description of the issue/alert
            namespace: Kubernetes namespace
            service: Specific service to focus on (optional)

        Returns:
            ObservationResult with all collected observations
        """
        result = ObservationResult(issue=issue, namespace=namespace)

        # Extract service name from issue if not provided
        if not service:
            service = self._extract_service_from_issue(issue)

        if service:
            result.services_involved.append(service)

        # Query metrics based on issue keywords FIRST
        await self._observe_issue_metrics(result, issue, namespace)

        # Collect resource utilization with limits context
        await self._observe_resource_utilization(result, service, namespace)

        # Collect observations from all sources
        await self._observe_prometheus(result, service, namespace)
        await self._observe_kubernetes(result, service, namespace)

        return result

    def _extract_metric_keywords(self, issue: str) -> list[str]:
        """
        Extract metric-related keywords from issue description.

        Args:
            issue: The issue description text

        Returns:
            List of matched keywords (e.g., ["memory", "cpu"])
        """
        issue_lower = issue.lower()
        matched_keywords = []

        # Define keyword patterns and their aliases
        keyword_aliases: dict[str, list[str]] = {
            "memory": ["memory", "mem", "oom", "out of memory", "ram"],
            "cpu": ["cpu", "processor", "compute", "high load"],
            "latency": ["latency", "slow", "response time", "delay", "timeout"],
            "error": ["error", "5xx", "500", "502", "503", "504", "failed", "failure"],
            "disk": ["disk", "storage", "filesystem", "fs", "volume", "pvc"],
            "network": ["network", "bandwidth", "throughput", "packet", "connection"],
        }

        for keyword, aliases in keyword_aliases.items():
            for alias in aliases:
                if alias in issue_lower:
                    if keyword not in matched_keywords:
                        matched_keywords.append(keyword)
                    break

        return matched_keywords

    async def _observe_issue_metrics(
        self,
        result: ObservationResult,
        issue: str,
        namespace: str,
    ):
        """
        Query Prometheus metrics based on keywords extracted from the issue.

        Args:
            result: ObservationResult to append observations to
            issue: The issue description
            namespace: Kubernetes namespace to filter metrics
        """
        keywords = self._extract_metric_keywords(issue)

        if not keywords:
            return

        for keyword in keywords:
            queries = self.METRIC_KEYWORD_QUERIES.get(keyword, [])

            for metric_name, query_template in queries:
                try:
                    # Format query with namespace
                    query = query_template.format(namespace=namespace)
                    metrics = await self.prometheus.query(query)

                    if not metrics:
                        result.observations.append(Observation(
                            source="prometheus",
                            type="metric",
                            summary=f"No data for {metric_name} in {namespace}",
                            details={"metric": metric_name, "query": query},
                            severity="info",
                        ))
                        continue

                    # Create observation for each metric result
                    for metric in metrics:
                        # Format value for readability
                        value = metric.current_value
                        formatted_value = self._format_metric_value(metric_name, value)

                        # Determine severity based on metric type and value
                        severity = self._assess_metric_severity(metric_name, value)

                        # Build details dict
                        details = {
                            "metric": metric_name,
                            "value": value,
                            "formatted_value": formatted_value,
                        }
                        details.update(metric.labels)

                        result.observations.append(Observation(
                            source="prometheus",
                            type="metric",
                            summary=f"{metric_name}: {formatted_value}",
                            details=details,
                            severity=severity,
                        ))

                except Exception as e:
                    result.observations.append(Observation(
                        source="prometheus",
                        type="error",
                        summary=f"Failed to query {metric_name}: {e}",
                        details={"metric": metric_name, "keyword": keyword},
                        severity="warning",
                    ))

    async def _observe_resource_utilization(
        self,
        result: ObservationResult,
        service: str | None,
        namespace: str,
    ):
        """
        Observe resource utilization with limits context.

        Queries both usage metrics and limits from kube-state-metrics,
        then calculates utilization percentages.
        """
        try:
            # Get memory usage per pod
            memory_usage_query = f'sum(container_memory_usage_bytes{{namespace="{namespace}"}}) by (pod)'
            memory_usage_metrics = await self.prometheus.query(memory_usage_query)

            # Get CPU usage per pod (rate over 5m)
            cpu_usage_query = f'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}"}}[5m])) by (pod)'
            cpu_usage_metrics = await self.prometheus.query(cpu_usage_query)

            # Get limits from kube-state-metrics
            memory_limits = await self._get_resource_limits(namespace, "memory")
            cpu_limits = await self._get_resource_limits(namespace, "cpu")

            # Also try to get limits from Kubernetes API as fallback
            k8s_pods = await self._get_k8s_pod_resources(namespace, service)

            # Process memory utilization
            for metric in memory_usage_metrics:
                pod_name = metric.labels.get("pod", "unknown")

                # Filter by service if specified
                if service and service not in pod_name:
                    continue

                usage = metric.current_value
                if usage is None:
                    continue

                # Try to find limit from Prometheus first, then K8s API
                limit = memory_limits.get(pod_name) or k8s_pods.get(pod_name, {}).get("memory_limit")

                obs = self._create_utilization_observation(
                    pod_name=pod_name,
                    resource_type="memory",
                    usage=usage,
                    limit=limit,
                )
                result.observations.append(obs)

            # Process CPU utilization
            for metric in cpu_usage_metrics:
                pod_name = metric.labels.get("pod", "unknown")

                # Filter by service if specified
                if service and service not in pod_name:
                    continue

                usage = metric.current_value
                if usage is None:
                    continue

                # Try to find limit from Prometheus first, then K8s API
                limit = cpu_limits.get(pod_name) or k8s_pods.get(pod_name, {}).get("cpu_limit")

                obs = self._create_utilization_observation(
                    pod_name=pod_name,
                    resource_type="cpu",
                    usage=usage,
                    limit=limit,
                )
                result.observations.append(obs)

        except Exception as e:
            result.observations.append(Observation(
                source="prometheus",
                type="error",
                summary=f"Failed to observe resource utilization: {e}",
                severity="warning",
            ))

    async def _get_resource_limits(self, namespace: str, resource: str) -> dict[str, float]:
        """
        Query kube-state-metrics for resource limits.

        Returns:
            Dict mapping pod name to limit value (bytes for memory, cores for CPU)
        """
        query = f'sum(kube_pod_container_resource_limits{{namespace="{namespace}", resource="{resource}"}}) by (pod)'

        try:
            metrics = await self.prometheus.query(query)
            return {
                m.labels.get("pod", ""): m.current_value
                for m in metrics
                if m.current_value is not None
            }
        except Exception:
            return {}

    async def _get_k8s_pod_resources(self, namespace: str, service: str | None) -> dict[str, dict]:
        """
        Get resource limits from Kubernetes API as fallback.

        Returns:
            Dict mapping pod name to resource info dict
        """
        try:
            label_selector = f"app={service}" if service else None
            pods = await self.kubernetes.get_pods(namespace, label_selector)

            return {
                pod.name: {
                    "memory_limit": pod.memory_limit,
                    "memory_request": pod.memory_request,
                    "cpu_limit": pod.cpu_limit,
                    "cpu_request": pod.cpu_request,
                }
                for pod in pods
            }
        except Exception:
            return {}

    def _create_utilization_observation(
        self,
        pod_name: str,
        resource_type: str,  # "memory" or "cpu"
        usage: float,
        limit: float | None,
    ) -> Observation:
        """
        Create an observation with utilization context.

        Shows usage/limit format like "260MB / 512MB (51%)" when limits are known.
        """
        if resource_type == "memory":
            usage_formatted = self._format_bytes(usage)

            if limit and limit > 0:
                limit_formatted = self._format_bytes(limit)
                utilization = usage / limit
                severity = self._utilization_severity(utilization)

                return Observation(
                    source="prometheus",
                    type="resource_utilization",
                    summary=f"Pod {pod_name} memory: {usage_formatted} / {limit_formatted} ({utilization:.0%})",
                    details={
                        "pod": pod_name,
                        "resource": "memory",
                        "usage_bytes": usage,
                        "limit_bytes": limit,
                        "utilization": utilization,
                    },
                    severity=severity,
                )
            else:
                # No limit defined - can't calculate utilization
                return Observation(
                    source="prometheus",
                    type="resource_utilization",
                    summary=f"Pod {pod_name} memory: {usage_formatted} (no limit set)",
                    details={
                        "pod": pod_name,
                        "resource": "memory",
                        "usage_bytes": usage,
                        "limit_bytes": None,
                        "utilization": None,
                    },
                    severity="info",
                )

        else:  # cpu
            usage_formatted = f"{usage:.3f} cores"

            if limit and limit > 0:
                limit_formatted = f"{limit:.3f} cores"
                utilization = usage / limit
                severity = self._utilization_severity(utilization)

                return Observation(
                    source="prometheus",
                    type="resource_utilization",
                    summary=f"Pod {pod_name} CPU: {usage_formatted} / {limit_formatted} ({utilization:.0%})",
                    details={
                        "pod": pod_name,
                        "resource": "cpu",
                        "usage_cores": usage,
                        "limit_cores": limit,
                        "utilization": utilization,
                    },
                    severity=severity,
                )
            else:
                return Observation(
                    source="prometheus",
                    type="resource_utilization",
                    summary=f"Pod {pod_name} CPU: {usage_formatted} (no limit set)",
                    details={
                        "pod": pod_name,
                        "resource": "cpu",
                        "usage_cores": usage,
                        "limit_cores": None,
                        "utilization": None,
                    },
                    severity="info",
                )

    def _format_bytes(self, value: float) -> str:
        """Format bytes to human readable format."""
        if value >= 1024**3:
            return f"{value / 1024**3:.2f}GB"
        elif value >= 1024**2:
            return f"{value / 1024**2:.0f}MB"
        elif value >= 1024:
            return f"{value / 1024:.0f}KB"
        return f"{value:.0f}B"

    def _utilization_severity(self, utilization: float) -> str:
        """
        Determine severity based on utilization percentage.

        Thresholds:
        - < 50% = info
        - 50-80% = info (but worth noting)
        - 80-95% = warning
        - > 95% = critical
        """
        if utilization > 0.95:
            return "critical"
        elif utilization > 0.80:
            return "warning"
        return "info"

    def _format_metric_value(self, metric_name: str, value: float | None) -> str:
        """Format metric value with appropriate units."""
        if value is None:
            return "N/A"

        metric_lower = metric_name.lower()

        # Bytes metrics
        if "bytes" in metric_lower:
            if value >= 1024**3:
                return f"{value / 1024**3:.2f} GB"
            elif value >= 1024**2:
                return f"{value / 1024**2:.2f} MB"
            elif value >= 1024:
                return f"{value / 1024:.2f} KB"
            return f"{value:.0f} B"

        # Duration/latency metrics (seconds) - check before rate!
        if "duration" in metric_lower or "latency" in metric_lower:
            if value >= 1:
                return f"{value:.2f}s"
            return f"{value * 1000:.2f}ms"

        # Rate/percentage metrics
        if "rate" in metric_lower or "ratio" in metric_lower:
            return f"{value:.4f}"

        # CPU usage (cores)
        if "cpu" in metric_name.lower():
            return f"{value:.3f} cores"

        # Default
        return f"{value:.2f}"

    def _assess_metric_severity(self, metric_name: str, value: float | None) -> str:
        """Assess severity based on metric type and value."""
        if value is None:
            return "info"

        metric_lower = metric_name.lower()

        # Memory thresholds (in bytes, >1GB is warning, >4GB is critical)
        if "memory" in metric_lower:
            if value > 4 * 1024**3:
                return "critical"
            elif value > 1 * 1024**3:
                return "warning"

        # CPU thresholds (>0.8 cores is warning, >2 cores is critical)
        if "cpu" in metric_lower:
            if value > 2.0:
                return "critical"
            elif value > 0.8:
                return "warning"

        # Error metrics (any errors is at least warning)
        if "error" in metric_lower or "5xx" in metric_lower:
            if value > 10:
                return "critical"
            elif value > 0:
                return "warning"

        # Latency thresholds (>1s is warning, >5s is critical)
        if "duration" in metric_lower or "latency" in metric_lower:
            if value > 5.0:
                return "critical"
            elif value > 1.0:
                return "warning"

        return "info"

    async def _observe_prometheus(
        self,
        result: ObservationResult,
        service: str | None,
        namespace: str,
    ):
        """Collect Prometheus observations."""
        try:
            # Get firing alerts
            alerts = await self.prometheus.get_alerts(state="firing")
            for alert in alerts:
                if namespace != "all" and alert.labels.get("namespace") != namespace:
                    continue

                result.observations.append(Observation(
                    source="prometheus",
                    type="alert",
                    summary=f"Alert {alert.alert_name} is {alert.state}",
                    details={
                        "labels": alert.labels,
                        "annotations": alert.annotations,
                    },
                    severity="critical" if alert.alert_name.lower().startswith("critical") else "warning",
                ))

            # Get service metrics if service specified
            if service:
                anomalies = await self.prometheus.find_anomalies(service, namespace)
                for anomaly in anomalies:
                    result.observations.append(Observation(
                        source="prometheus",
                        type="metric_anomaly",
                        summary=anomaly["message"],
                        details={"type": anomaly["type"], "value": anomaly["value"]},
                        severity=anomaly["severity"],
                    ))

        except Exception as e:
            result.observations.append(Observation(
                source="prometheus",
                type="error",
                summary=f"Failed to query Prometheus: {e}",
                severity="warning",
            ))

    async def _observe_kubernetes(
        self,
        result: ObservationResult,
        service: str | None,
        namespace: str,
    ):
        """Collect Kubernetes observations."""
        try:
            # Get pods
            label_selector = f"app={service}" if service else None
            pods = await self.kubernetes.get_pods(namespace, label_selector)

            unhealthy_pods = []
            total_restarts = 0

            for pod in pods:
                total_restarts += pod.restarts

                if not pod.ready or pod.status not in ["Running", "Succeeded"]:
                    unhealthy_pods.append(pod)
                    result.observations.append(Observation(
                        source="kubernetes",
                        type="pod_status",
                        summary=f"Pod {pod.name} is {pod.status} (ready={pod.ready}, restarts={pod.restarts})",
                        details={
                            "containers": pod.containers,
                            "age": pod.age,
                            "node": pod.node,
                        },
                        severity="critical" if pod.status == "CrashLoopBackOff" else "warning",
                    ))

            # Add summary observation
            healthy_count = len(pods) - len(unhealthy_pods)
            if pods:
                result.observations.append(Observation(
                    source="kubernetes",
                    type="pod_summary",
                    summary=f"Pods: {healthy_count}/{len(pods)} healthy, {total_restarts} total restarts",
                    details={
                        "total": len(pods),
                        "healthy": healthy_count,
                        "unhealthy": len(unhealthy_pods),
                        "restarts": total_restarts,
                    },
                    severity="info" if not unhealthy_pods else "warning",
                ))

            # Get recent warning events
            events = await self.kubernetes.get_events(namespace)
            warning_events = [e for e in events if e.type == "Warning"][-5:]  # Last 5

            for event in warning_events:
                # Check if event is related to our service
                if service and service not in event.involved_object.lower():
                    continue

                result.observations.append(Observation(
                    source="kubernetes",
                    type="event",
                    summary=f"{event.reason}: {event.message}",
                    details={
                        "object": event.involved_object,
                        "count": event.count,
                    },
                    severity="warning",
                ))

            # Get logs from unhealthy pods
            for pod in unhealthy_pods[:2]:  # Limit to 2 pods
                try:
                    logs = await self.kubernetes.get_pod_logs(
                        pod.name,
                        namespace,
                        tail_lines=20,
                    )

                    # Extract error lines
                    error_lines = [
                        line for line in logs.split("\n")
                        if any(kw in line.lower() for kw in ["error", "exception", "fatal", "panic", "failed"])
                    ]

                    if error_lines:
                        result.observations.append(Observation(
                            source="kubernetes",
                            type="logs",
                            summary=f"Errors in {pod.name} logs",
                            details={"errors": error_lines[-5:]},  # Last 5 errors
                            severity="warning",
                        ))
                except Exception:
                    pass  # Logs might not be available

        except Exception as e:
            result.observations.append(Observation(
                source="kubernetes",
                type="error",
                summary=f"Failed to query Kubernetes: {e}",
                severity="warning",
            ))

    def _extract_service_from_issue(self, issue: str) -> str | None:
        """Try to extract service name from issue description."""
        # Common patterns: "high CPU on payment-service", "payment-service high latency"
        words = issue.lower().replace("-", "_").split()

        # Look for words that look like service names
        for word in words:
            if "_" in word or word.endswith("service") or word.endswith("api"):
                return word.replace("_", "-")

        # Look for "on <service>" pattern
        if "on " in issue.lower():
            after_on = issue.lower().split("on ")[-1].split()[0]
            return after_on.strip(".,;:")

        return None
