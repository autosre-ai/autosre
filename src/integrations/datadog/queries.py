"""Pre-built Datadog queries and query builders."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any


class Aggregation(str, Enum):
    """Metric aggregation methods."""
    AVG = "avg"
    SUM = "sum"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    LAST = "last"


class TimeWindow(str, Enum):
    """Common time windows for rollups."""
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    TEN_MINUTES = "10m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    FOUR_HOURS = "4h"
    ONE_DAY = "1d"


@dataclass
class MetricQuery:
    """Builder for Datadog metric queries."""
    
    metric: str
    aggregation: Aggregation = Aggregation.AVG
    tags: dict[str, str] = field(default_factory=dict)
    group_by: list[str] = field(default_factory=list)
    rollup: str | None = None
    rollup_method: Aggregation | None = None
    fill: str | None = None
    as_rate: bool = False
    as_count: bool = False
    
    def with_tag(self, key: str, value: str) -> "MetricQuery":
        """Add a tag filter."""
        self.tags[key] = value
        return self
    
    def with_tags(self, tags: dict[str, str]) -> "MetricQuery":
        """Add multiple tag filters."""
        self.tags.update(tags)
        return self
    
    def grouped_by(self, *fields: str) -> "MetricQuery":
        """Group results by fields."""
        self.group_by.extend(fields)
        return self
    
    def with_rollup(
        self,
        window: TimeWindow | str,
        method: Aggregation = Aggregation.AVG,
    ) -> "MetricQuery":
        """Add a rollup."""
        self.rollup = window.value if isinstance(window, TimeWindow) else window
        self.rollup_method = method
        return self
    
    def with_fill(self, value: str = "null") -> "MetricQuery":
        """Fill missing values."""
        self.fill = value
        return self
    
    def rate(self) -> "MetricQuery":
        """Convert to rate."""
        self.as_rate = True
        return self
    
    def count(self) -> "MetricQuery":
        """Convert to count."""
        self.as_count = True
        return self
    
    def build(self) -> str:
        """Build the query string."""
        # Build tag filter
        if self.tags:
            tag_parts = [f"{k}:{v}" for k, v in self.tags.items()]
            if self.group_by:
                tag_filter = f"{{{','.join(tag_parts)}}} by {{{','.join(self.group_by)}}}"
            else:
                tag_filter = f"{{{','.join(tag_parts)}}}"
        elif self.group_by:
            tag_filter = f"{{*}} by {{{','.join(self.group_by)}}}"
        else:
            tag_filter = "{*}"
        
        # Base query
        query = f"{self.aggregation.value}:{self.metric}{tag_filter}"
        
        # Add modifiers
        if self.as_rate:
            query += ".as_rate()"
        if self.as_count:
            query += ".as_count()"
        if self.rollup:
            method = self.rollup_method.value if self.rollup_method else "avg"
            query += f".rollup({method}, {self.rollup})"
        if self.fill:
            query += f".fill({self.fill})"
        
        return query


@dataclass
class LogQuery:
    """Builder for Datadog log queries."""
    
    filters: list[str] = field(default_factory=list)
    service: str | None = None
    host: str | None = None
    status: str | None = None
    source: str | None = None
    
    def with_service(self, service: str) -> "LogQuery":
        """Filter by service."""
        self.service = service
        return self
    
    def with_host(self, host: str) -> "LogQuery":
        """Filter by host."""
        self.host = host
        return self
    
    def with_status(self, status: str) -> "LogQuery":
        """Filter by status (error, warn, info, etc.)."""
        self.status = status
        return self
    
    def with_source(self, source: str) -> "LogQuery":
        """Filter by source."""
        self.source = source
        return self
    
    def with_filter(self, filter_expr: str) -> "LogQuery":
        """Add a custom filter expression."""
        self.filters.append(filter_expr)
        return self
    
    def contains(self, text: str) -> "LogQuery":
        """Search for text in log message."""
        self.filters.append(f'"{text}"')
        return self
    
    def with_tag(self, key: str, value: str) -> "LogQuery":
        """Filter by tag."""
        self.filters.append(f"{key}:{value}")
        return self
    
    def with_attribute(self, key: str, value: str) -> "LogQuery":
        """Filter by attribute."""
        self.filters.append(f"@{key}:{value}")
        return self
    
    def build(self) -> str:
        """Build the query string."""
        parts = list(self.filters)
        
        if self.service:
            parts.append(f"service:{self.service}")
        if self.host:
            parts.append(f"host:{self.host}")
        if self.status:
            parts.append(f"status:{self.status}")
        if self.source:
            parts.append(f"source:{self.source}")
        
        return " ".join(parts) if parts else "*"


# ============================================================================
# Pre-built System Queries
# ============================================================================

class SystemMetrics:
    """Common system metric queries."""
    
    @staticmethod
    def cpu_usage(host: str | None = None, **tags) -> MetricQuery:
        """CPU usage percentage."""
        query = MetricQuery(
            metric="system.cpu.user",
            aggregation=Aggregation.AVG,
        )
        if host:
            query.with_tag("host", host)
        return query.with_tags(tags)
    
    @staticmethod
    def cpu_system(host: str | None = None, **tags) -> MetricQuery:
        """System CPU percentage."""
        query = MetricQuery(
            metric="system.cpu.system",
            aggregation=Aggregation.AVG,
        )
        if host:
            query.with_tag("host", host)
        return query.with_tags(tags)
    
    @staticmethod
    def memory_usage(host: str | None = None, **tags) -> MetricQuery:
        """Memory usage."""
        query = MetricQuery(
            metric="system.mem.pct_usable",
            aggregation=Aggregation.AVG,
        )
        if host:
            query.with_tag("host", host)
        return query.with_tags(tags)
    
    @staticmethod
    def disk_usage(host: str | None = None, device: str | None = None, **tags) -> MetricQuery:
        """Disk usage percentage."""
        query = MetricQuery(
            metric="system.disk.in_use",
            aggregation=Aggregation.AVG,
        )
        if host:
            query.with_tag("host", host)
        if device:
            query.with_tag("device", device)
        return query.with_tags(tags)
    
    @staticmethod
    def load_average(host: str | None = None, **tags) -> MetricQuery:
        """System load (1 minute average)."""
        query = MetricQuery(
            metric="system.load.1",
            aggregation=Aggregation.AVG,
        )
        if host:
            query.with_tag("host", host)
        return query.with_tags(tags)
    
    @staticmethod
    def network_bytes_in(host: str | None = None, interface: str | None = None, **tags) -> MetricQuery:
        """Network bytes received."""
        query = MetricQuery(
            metric="system.net.bytes_rcvd",
            aggregation=Aggregation.SUM,
        ).rate()
        if host:
            query.with_tag("host", host)
        if interface:
            query.with_tag("device", interface)
        return query.with_tags(tags)
    
    @staticmethod
    def network_bytes_out(host: str | None = None, interface: str | None = None, **tags) -> MetricQuery:
        """Network bytes sent."""
        query = MetricQuery(
            metric="system.net.bytes_sent",
            aggregation=Aggregation.SUM,
        ).rate()
        if host:
            query.with_tag("host", host)
        if interface:
            query.with_tag("device", interface)
        return query.with_tags(tags)


class ContainerMetrics:
    """Container and Docker metrics."""
    
    @staticmethod
    def cpu_usage(container: str | None = None, **tags) -> MetricQuery:
        """Container CPU usage."""
        query = MetricQuery(
            metric="docker.cpu.usage",
            aggregation=Aggregation.AVG,
        )
        if container:
            query.with_tag("container_name", container)
        return query.with_tags(tags)
    
    @staticmethod
    def memory_usage(container: str | None = None, **tags) -> MetricQuery:
        """Container memory usage."""
        query = MetricQuery(
            metric="docker.mem.rss",
            aggregation=Aggregation.AVG,
        )
        if container:
            query.with_tag("container_name", container)
        return query.with_tags(tags)
    
    @staticmethod
    def running_containers(**tags) -> MetricQuery:
        """Number of running containers."""
        return MetricQuery(
            metric="docker.containers.running",
            aggregation=Aggregation.SUM,
        ).with_tags(tags)


class KubernetesMetrics:
    """Kubernetes metrics."""
    
    @staticmethod
    def pod_cpu(namespace: str | None = None, pod: str | None = None, **tags) -> MetricQuery:
        """Pod CPU usage."""
        query = MetricQuery(
            metric="kubernetes.cpu.usage.total",
            aggregation=Aggregation.AVG,
        )
        if namespace:
            query.with_tag("kube_namespace", namespace)
        if pod:
            query.with_tag("pod_name", pod)
        return query.with_tags(tags)
    
    @staticmethod
    def pod_memory(namespace: str | None = None, pod: str | None = None, **tags) -> MetricQuery:
        """Pod memory usage."""
        query = MetricQuery(
            metric="kubernetes.memory.usage",
            aggregation=Aggregation.AVG,
        )
        if namespace:
            query.with_tag("kube_namespace", namespace)
        if pod:
            query.with_tag("pod_name", pod)
        return query.with_tags(tags)
    
    @staticmethod
    def pod_restarts(namespace: str | None = None, **tags) -> MetricQuery:
        """Pod restart count."""
        query = MetricQuery(
            metric="kubernetes_state.container.restarts",
            aggregation=Aggregation.SUM,
        )
        if namespace:
            query.with_tag("kube_namespace", namespace)
        return query.with_tags(tags)
    
    @staticmethod
    def deployment_replicas(namespace: str | None = None, deployment: str | None = None, **tags) -> MetricQuery:
        """Deployment replica count."""
        query = MetricQuery(
            metric="kubernetes_state.deployment.replicas_available",
            aggregation=Aggregation.LAST,
        )
        if namespace:
            query.with_tag("kube_namespace", namespace)
        if deployment:
            query.with_tag("kube_deployment", deployment)
        return query.with_tags(tags)


class APMMetrics:
    """Application Performance Monitoring metrics."""
    
    @staticmethod
    def request_count(service: str | None = None, resource: str | None = None, **tags) -> MetricQuery:
        """Request count."""
        query = MetricQuery(
            metric="trace.http.request.hits",
            aggregation=Aggregation.SUM,
        ).rate()
        if service:
            query.with_tag("service", service)
        if resource:
            query.with_tag("resource_name", resource)
        return query.with_tags(tags)
    
    @staticmethod
    def error_rate(service: str | None = None, **tags) -> MetricQuery:
        """Error rate."""
        query = MetricQuery(
            metric="trace.http.request.errors",
            aggregation=Aggregation.SUM,
        ).rate()
        if service:
            query.with_tag("service", service)
        return query.with_tags(tags)
    
    @staticmethod
    def latency_p50(service: str | None = None, **tags) -> MetricQuery:
        """P50 latency."""
        query = MetricQuery(
            metric="trace.http.request.duration.by.service.50p",
            aggregation=Aggregation.AVG,
        )
        if service:
            query.with_tag("service", service)
        return query.with_tags(tags)
    
    @staticmethod
    def latency_p95(service: str | None = None, **tags) -> MetricQuery:
        """P95 latency."""
        query = MetricQuery(
            metric="trace.http.request.duration.by.service.95p",
            aggregation=Aggregation.AVG,
        )
        if service:
            query.with_tag("service", service)
        return query.with_tags(tags)
    
    @staticmethod
    def latency_p99(service: str | None = None, **tags) -> MetricQuery:
        """P99 latency."""
        query = MetricQuery(
            metric="trace.http.request.duration.by.service.99p",
            aggregation=Aggregation.AVG,
        )
        if service:
            query.with_tag("service", service)
        return query.with_tags(tags)


class DatabaseMetrics:
    """Database metrics."""
    
    @staticmethod
    def postgres_connections(host: str | None = None, **tags) -> MetricQuery:
        """PostgreSQL connections."""
        query = MetricQuery(
            metric="postgresql.connections",
            aggregation=Aggregation.SUM,
        )
        if host:
            query.with_tag("host", host)
        return query.with_tags(tags)
    
    @staticmethod
    def postgres_queries_per_sec(host: str | None = None, **tags) -> MetricQuery:
        """PostgreSQL queries per second."""
        query = MetricQuery(
            metric="postgresql.queries",
            aggregation=Aggregation.SUM,
        ).rate()
        if host:
            query.with_tag("host", host)
        return query.with_tags(tags)
    
    @staticmethod
    def redis_connected_clients(host: str | None = None, **tags) -> MetricQuery:
        """Redis connected clients."""
        query = MetricQuery(
            metric="redis.net.clients",
            aggregation=Aggregation.AVG,
        )
        if host:
            query.with_tag("host", host)
        return query.with_tags(tags)
    
    @staticmethod
    def redis_memory_used(host: str | None = None, **tags) -> MetricQuery:
        """Redis memory usage."""
        query = MetricQuery(
            metric="redis.mem.used",
            aggregation=Aggregation.AVG,
        )
        if host:
            query.with_tag("host", host)
        return query.with_tags(tags)


# ============================================================================
# Pre-built Log Queries
# ============================================================================

class CommonLogQueries:
    """Common log query patterns."""
    
    @staticmethod
    def errors(service: str | None = None) -> LogQuery:
        """Error logs."""
        query = LogQuery().with_status("error")
        if service:
            query.with_service(service)
        return query
    
    @staticmethod
    def warnings(service: str | None = None) -> LogQuery:
        """Warning logs."""
        query = LogQuery().with_status("warn")
        if service:
            query.with_service(service)
        return query
    
    @staticmethod
    def exceptions(service: str | None = None) -> LogQuery:
        """Logs containing exceptions."""
        query = LogQuery().contains("exception").with_status("error")
        if service:
            query.with_service(service)
        return query
    
    @staticmethod
    def http_5xx(service: str | None = None) -> LogQuery:
        """HTTP 5xx errors."""
        query = LogQuery().with_attribute("http.status_code", "[500 TO 599]")
        if service:
            query.with_service(service)
        return query
    
    @staticmethod
    def http_4xx(service: str | None = None) -> LogQuery:
        """HTTP 4xx errors."""
        query = LogQuery().with_attribute("http.status_code", "[400 TO 499]")
        if service:
            query.with_service(service)
        return query
    
    @staticmethod
    def slow_requests(service: str | None = None, threshold_ms: int = 1000) -> LogQuery:
        """Slow HTTP requests."""
        query = LogQuery().with_attribute("http.response_time", f">{threshold_ms}")
        if service:
            query.with_service(service)
        return query
    
    @staticmethod
    def kubernetes_events(namespace: str | None = None) -> LogQuery:
        """Kubernetes events."""
        query = LogQuery().with_source("kubernetes")
        if namespace:
            query.with_tag("kube_namespace", namespace)
        return query


# ============================================================================
# Monitor Query Templates
# ============================================================================

@dataclass
class MonitorQuery:
    """Template for monitor alert queries."""
    
    name: str
    query: str
    message: str
    thresholds: dict[str, float]
    monitor_type: str = "metric alert"
    tags: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to monitor creation payload."""
        return {
            "name": self.name,
            "type": self.monitor_type,
            "query": self.query,
            "message": self.message,
            "tags": self.tags,
            "options": {
                "thresholds": self.thresholds,
                "notify_no_data": True,
                "no_data_timeframe": 10,
            },
        }


class MonitorTemplates:
    """Pre-built monitor templates."""
    
    @staticmethod
    def high_cpu(
        host: str | None = None,
        warning: float = 80,
        critical: float = 90,
    ) -> MonitorQuery:
        """High CPU usage monitor."""
        scope = f"host:{host}" if host else "*"
        return MonitorQuery(
            name=f"High CPU Usage{f' on {host}' if host else ''}",
            query=f"avg(last_5m):avg:system.cpu.user{{{scope}}} > {critical}",
            message="CPU usage is high. @pagerduty",
            thresholds={"warning": warning, "critical": critical},
        )
    
    @staticmethod
    def high_memory(
        host: str | None = None,
        warning: float = 80,
        critical: float = 90,
    ) -> MonitorQuery:
        """High memory usage monitor."""
        scope = f"host:{host}" if host else "*"
        return MonitorQuery(
            name=f"High Memory Usage{f' on {host}' if host else ''}",
            query=f"avg(last_5m):avg:system.mem.pct_usable{{{scope}}} < {100 - critical}",
            message="Memory usage is high. @pagerduty",
            thresholds={"warning": 100 - warning, "critical": 100 - critical},
        )
    
    @staticmethod
    def high_disk(
        host: str | None = None,
        warning: float = 80,
        critical: float = 90,
    ) -> MonitorQuery:
        """High disk usage monitor."""
        scope = f"host:{host}" if host else "*"
        return MonitorQuery(
            name=f"High Disk Usage{f' on {host}' if host else ''}",
            query=f"avg(last_5m):avg:system.disk.in_use{{{scope}}} * 100 > {critical}",
            message="Disk usage is high. @pagerduty",
            thresholds={"warning": warning, "critical": critical},
        )
    
    @staticmethod
    def error_rate(
        service: str,
        warning: float = 1,
        critical: float = 5,
    ) -> MonitorQuery:
        """Error rate monitor for a service."""
        return MonitorQuery(
            name=f"High Error Rate - {service}",
            query=f"sum(last_5m):sum:trace.http.request.errors{{service:{service}}}.as_rate() / sum:trace.http.request.hits{{service:{service}}}.as_rate() * 100 > {critical}",
            message=f"Error rate for {service} is elevated. @pagerduty",
            thresholds={"warning": warning, "critical": critical},
        )
    
    @staticmethod
    def latency_p95(
        service: str,
        warning_ms: float = 500,
        critical_ms: float = 1000,
    ) -> MonitorQuery:
        """P95 latency monitor for a service."""
        return MonitorQuery(
            name=f"High P95 Latency - {service}",
            query=f"avg(last_5m):avg:trace.http.request.duration.by.service.95p{{service:{service}}} > {critical_ms}",
            message=f"P95 latency for {service} is high. @pagerduty",
            thresholds={"warning": warning_ms, "critical": critical_ms},
        )
    
    @staticmethod
    def pod_restarts(
        namespace: str,
        warning: int = 3,
        critical: int = 5,
    ) -> MonitorQuery:
        """Pod restart monitor."""
        return MonitorQuery(
            name=f"Pod Restarts - {namespace}",
            query=f"sum(last_10m):sum:kubernetes_state.container.restarts{{kube_namespace:{namespace}}} by {{pod_name}} > {critical}",
            message=f"Pods in {namespace} are restarting frequently. @pagerduty",
            thresholds={"warning": warning, "critical": critical},
        )


# ============================================================================
# Time Helpers
# ============================================================================

def time_range(
    duration: timedelta | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> tuple[datetime, datetime]:
    """
    Calculate a time range.
    
    Args:
        duration: Duration of the range (end - start)
        start: Start time
        end: End time (defaults to now)
    
    Returns:
        Tuple of (start, end) datetimes
    """
    if end is None:
        end = datetime.now()
    
    if start is None:
        if duration is None:
            duration = timedelta(hours=1)
        start = end - duration
    
    return start, end


def last_hour() -> tuple[datetime, datetime]:
    """Get time range for the last hour."""
    return time_range(timedelta(hours=1))


def last_day() -> tuple[datetime, datetime]:
    """Get time range for the last 24 hours."""
    return time_range(timedelta(days=1))


def last_week() -> tuple[datetime, datetime]:
    """Get time range for the last 7 days."""
    return time_range(timedelta(weeks=1))
