"""
Observer Agent - Collects data from infrastructure
"""

from dataclasses import dataclass, field
from typing import Any
from datetime import datetime

from opensre_core.adapters.prometheus import PrometheusAdapter
from opensre_core.adapters.kubernetes import KubernetesAdapter


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
        
        # Collect observations from all sources
        await self._observe_prometheus(result, service, namespace)
        await self._observe_kubernetes(result, service, namespace)
        
        return result
    
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
