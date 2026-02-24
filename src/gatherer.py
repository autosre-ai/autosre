"""
SRE Agent - Context Gatherer

Collects data from multiple sources to build incident context.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

from .models import (
    Alert, IncidentContext, PrometheusData, GitHubData, 
    LogsData, KubernetesData, TrafficData, DependencyStatus,
    MetricSnapshot, Deployment, LogEntry, LogPattern, PodStatus,
    Severity, HealthStatus
)


class ContextGatherer:
    """Gathers context from multiple data sources"""
    
    def __init__(self, config: dict, mock_data_path: Optional[Path] = None):
        self.config = config
        self.mock_data_path = mock_data_path
        self._mock_data = None
        
    def _load_mock_data(self) -> dict:
        """Load mock data from file"""
        if self._mock_data is None:
            if self.mock_data_path and self.mock_data_path.exists():
                with open(self.mock_data_path) as f:
                    self._mock_data = json.load(f)
            else:
                self._mock_data = {}
        return self._mock_data
    
    def gather(self, alert_text: str, service: str) -> IncidentContext:
        """Gather all context for an incident"""
        
        # Create alert object
        alert = self._create_alert(alert_text, service)
        
        # Gather from all sources
        prometheus_data = self._gather_prometheus(service)
        github_data = self._gather_github(service)
        logs_data = self._gather_logs(service)
        k8s_data = self._gather_kubernetes(service)
        traffic_data = self._gather_traffic(service)
        dependencies = self._gather_dependencies(service)
        
        return IncidentContext(
            alert=alert,
            prometheus=prometheus_data,
            github=github_data,
            logs=logs_data,
            kubernetes=k8s_data,
            traffic=traffic_data,
            dependencies=dependencies,
            gathered_at=datetime.utcnow()
        )
    
    def _create_alert(self, alert_text: str, service: str) -> Alert:
        """Create alert object from input"""
        mock = self._load_mock_data()
        
        if mock and "alert" in mock:
            alert_data = mock["alert"]
            return Alert(
                id=alert_data.get("id", "MANUAL-001"),
                source=alert_data.get("source", "manual"),
                severity=Severity(alert_data.get("severity", "high")),
                service=service,
                title=alert_text,
                description=alert_data.get("description", alert_text),
                started_at=datetime.fromisoformat(alert_data["started_at"].replace("Z", "+00:00")),
                labels=alert_data.get("labels", {})
            )
        
        return Alert(
            id="MANUAL-001",
            source="manual",
            severity=Severity.HIGH,
            service=service,
            title=alert_text,
            description=alert_text,
            started_at=datetime.utcnow(),
            labels={}
        )
    
    def _gather_prometheus(self, service: str) -> Optional[PrometheusData]:
        """Gather metrics from Prometheus"""
        source_config = self.config.get("sources", {}).get("prometheus", {})
        
        if not source_config.get("enabled", False):
            return None
            
        if source_config.get("mode") == "mock":
            return self._mock_prometheus()
        else:
            return self._live_prometheus(service, source_config)
    
    def _mock_prometheus(self) -> PrometheusData:
        """Return mock Prometheus data"""
        mock = self._load_mock_data()
        prom = mock.get("prometheus", {})
        
        return PrometheusData(
            error_rate=MetricSnapshot(
                current=prom.get("error_rate", {}).get("current", 0),
                baseline=prom.get("error_rate", {}).get("baseline", 0),
                unit=prom.get("error_rate", {}).get("unit", "percent")
            ),
            request_rate=MetricSnapshot(
                current=prom.get("request_rate", {}).get("current", 0),
                baseline=prom.get("request_rate", {}).get("baseline", 0),
                unit=prom.get("request_rate", {}).get("unit", "req/s")
            ),
            latency_p99=MetricSnapshot(
                current=prom.get("latency_p99", {}).get("current", 0),
                baseline=prom.get("latency_p99", {}).get("baseline", 0),
                unit=prom.get("latency_p99", {}).get("unit", "ms")
            ),
            latency_p50=MetricSnapshot(
                current=prom.get("latency_p50", {}).get("current", 0),
                baseline=prom.get("latency_p50", {}).get("baseline", 0),
                unit=prom.get("latency_p50", {}).get("unit", "ms")
            ),
            error_breakdown=prom.get("error_breakdown", {}),
            time_series=prom.get("time_series", [])
        )
    
    def _live_prometheus(self, service: str, config: dict) -> Optional[PrometheusData]:
        """Query live Prometheus - TODO: implement"""
        # TODO: Implement actual Prometheus API calls
        return None
    
    def _gather_github(self, service: str) -> Optional[GitHubData]:
        """Gather deployment info from GitHub"""
        source_config = self.config.get("sources", {}).get("github", {})
        
        if not source_config.get("enabled", False):
            return None
            
        if source_config.get("mode") == "mock":
            return self._mock_github()
        else:
            return self._live_github(service, source_config)
    
    def _mock_github(self) -> GitHubData:
        """Return mock GitHub data"""
        mock = self._load_mock_data()
        gh = mock.get("github", {})
        
        deployments = []
        for dep in gh.get("recent_deployments", []):
            deployments.append(Deployment(
                sha=dep["sha"],
                short_sha=dep["short_sha"],
                author=dep["author"],
                message=dep["message"],
                deployed_at=datetime.fromisoformat(dep["deployed_at"].replace("Z", "+00:00")),
                hours_ago=dep["hours_ago"],
                files_changed=dep.get("files_changed", []),
                additions=dep.get("additions", 0),
                deletions=dep.get("deletions", 0)
            ))
        
        return GitHubData(
            recent_deployments=deployments,
            open_prs=gh.get("open_prs", [])
        )
    
    def _live_github(self, service: str, config: dict) -> Optional[GitHubData]:
        """Query live GitHub - TODO: implement"""
        return None
    
    def _gather_logs(self, service: str) -> Optional[LogsData]:
        """Gather error logs"""
        source_config = self.config.get("sources", {}).get("logs", {})
        
        if not source_config.get("enabled", False):
            return None
            
        if source_config.get("mode") == "mock":
            return self._mock_logs()
        else:
            return self._live_logs(service, source_config)
    
    def _mock_logs(self) -> LogsData:
        """Return mock log data"""
        mock = self._load_mock_data()
        logs = mock.get("logs", {})
        
        error_samples = []
        for entry in logs.get("error_samples", []):
            error_samples.append(LogEntry(
                timestamp=datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00")),
                level=entry["level"],
                message=entry["message"],
                trace_id=entry.get("trace_id"),
                count=entry.get("count", 1)
            ))
        
        error_patterns = []
        for pattern in logs.get("error_patterns", []):
            error_patterns.append(LogPattern(
                pattern=pattern["pattern"],
                count=pattern["count"],
                percentage=pattern["percentage"]
            ))
        
        first_error = None
        if logs.get("first_error_at"):
            first_error = datetime.fromisoformat(logs["first_error_at"].replace("Z", "+00:00"))
        
        return LogsData(
            error_samples=error_samples,
            error_patterns=error_patterns,
            first_error_at=first_error,
            total_errors_last_5m=logs.get("total_errors_last_5m", 0)
        )
    
    def _live_logs(self, service: str, config: dict) -> Optional[LogsData]:
        """Query live logs - TODO: implement"""
        return None
    
    def _gather_kubernetes(self, service: str) -> Optional[KubernetesData]:
        """Gather Kubernetes/OpenShift status"""
        source_config = self.config.get("sources", {}).get("kubernetes", {})
        
        if not source_config.get("enabled", False):
            return None
            
        if source_config.get("mode") == "mock":
            return self._mock_kubernetes()
        else:
            return self._live_kubernetes(service, source_config)
    
    def _mock_kubernetes(self) -> KubernetesData:
        """Return mock Kubernetes data"""
        mock = self._load_mock_data()
        k8s = mock.get("kubernetes", {})
        
        pods = []
        for pod in k8s.get("pods", []):
            pods.append(PodStatus(
                name=pod["name"],
                status=pod["status"],
                restarts=pod["restarts"],
                cpu_usage=pod["cpu_usage"],
                cpu_limit=pod["cpu_limit"],
                memory_usage=pod["memory_usage"],
                memory_limit=pod["memory_limit"],
                ready=pod["ready"]
            ))
        
        return KubernetesData(
            pods=pods,
            replica_count=k8s.get("replica_count", {}),
            recent_events=k8s.get("recent_events", []),
            resource_pressure=k8s.get("resource_pressure", False)
        )
    
    def _live_kubernetes(self, service: str, config: dict) -> Optional[KubernetesData]:
        """Query live Kubernetes - TODO: implement"""
        return None
    
    def _gather_traffic(self, service: str) -> Optional[TrafficData]:
        """Gather traffic analysis data"""
        mock = self._load_mock_data()
        traffic = mock.get("traffic", {})
        
        return TrafficData(
            suspicious_ips=traffic.get("suspicious_ips", []),
            geo_distribution=traffic.get("geo_distribution", {}),
            is_ddos=traffic.get("is_ddos", False),
            is_malicious=traffic.get("is_malicious", False),
            akamai_status=traffic.get("akamai_status", "unknown")
        )
    
    def _gather_dependencies(self, service: str) -> list[DependencyStatus]:
        """Gather dependency health status"""
        mock = self._load_mock_data()
        deps_data = mock.get("dependencies", {})
        
        dependencies = []
        for name, dep in deps_data.items():
            last_healthy = None
            if dep.get("last_healthy"):
                last_healthy = datetime.fromisoformat(dep["last_healthy"].replace("Z", "+00:00"))
            
            dependencies.append(DependencyStatus(
                name=name,
                status=HealthStatus(dep.get("status", "unknown")),
                latency_p99=dep.get("latency_p99", 0),
                error_rate=dep.get("error_rate", 0),
                last_healthy=last_healthy
            ))
        
        return dependencies
