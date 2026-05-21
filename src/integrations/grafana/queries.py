"""Pre-built Grafana queries and query builders."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any


class GrafanaTimeRange(str, Enum):
    """Common Grafana time ranges."""
    LAST_5_MINUTES = "now-5m"
    LAST_15_MINUTES = "now-15m"
    LAST_30_MINUTES = "now-30m"
    LAST_1_HOUR = "now-1h"
    LAST_3_HOURS = "now-3h"
    LAST_6_HOURS = "now-6h"
    LAST_12_HOURS = "now-12h"
    LAST_24_HOURS = "now-24h"
    LAST_2_DAYS = "now-2d"
    LAST_7_DAYS = "now-7d"
    LAST_30_DAYS = "now-30d"
    LAST_90_DAYS = "now-90d"
    TODAY = "now/d"
    THIS_WEEK = "now/w"
    THIS_MONTH = "now/M"
    THIS_YEAR = "now/y"


class QueryFormat(str, Enum):
    """Query result formats."""
    TIME_SERIES = "time_series"
    TABLE = "table"
    HEATMAP = "heatmap"
    LOGS = "logs"


@dataclass
class PrometheusQuery:
    """Builder for Prometheus queries in Grafana."""
    
    expr: str
    legend_format: str | None = None
    format: QueryFormat = QueryFormat.TIME_SERIES
    instant: bool = False
    interval: str | None = None
    ref_id: str = "A"
    
    def with_legend(self, legend: str) -> "PrometheusQuery":
        """Set legend format."""
        self.legend_format = legend
        return self
    
    def as_instant(self) -> "PrometheusQuery":
        """Make this an instant query."""
        self.instant = True
        return self
    
    def as_range(self) -> "PrometheusQuery":
        """Make this a range query."""
        self.instant = False
        return self
    
    def with_interval(self, interval: str) -> "PrometheusQuery":
        """Set query interval."""
        self.interval = interval
        return self
    
    def with_format(self, fmt: QueryFormat) -> "PrometheusQuery":
        """Set result format."""
        self.format = fmt
        return self
    
    def build(self) -> dict[str, Any]:
        """Build query target dict."""
        result = {
            "refId": self.ref_id,
            "expr": self.expr,
            "format": self.format.value,
            "instant": self.instant,
            "range": not self.instant,
        }
        
        if self.legend_format:
            result["legendFormat"] = self.legend_format
        if self.interval:
            result["interval"] = self.interval
        
        return result


@dataclass
class ElasticsearchQuery:
    """Builder for Elasticsearch queries in Grafana."""
    
    query: str = "*"
    metrics: list[dict[str, Any]] = field(default_factory=list)
    bucket_aggs: list[dict[str, Any]] = field(default_factory=list)
    ref_id: str = "A"
    
    def with_query(self, query: str) -> "ElasticsearchQuery":
        """Set Lucene query."""
        self.query = query
        return self
    
    def with_count(self) -> "ElasticsearchQuery":
        """Add count metric."""
        self.metrics.append({
            "type": "count",
            "id": str(len(self.metrics) + 1),
        })
        return self
    
    def with_avg(self, field: str) -> "ElasticsearchQuery":
        """Add average metric."""
        self.metrics.append({
            "type": "avg",
            "field": field,
            "id": str(len(self.metrics) + 1),
        })
        return self
    
    def with_sum(self, field: str) -> "ElasticsearchQuery":
        """Add sum metric."""
        self.metrics.append({
            "type": "sum",
            "field": field,
            "id": str(len(self.metrics) + 1),
        })
        return self
    
    def with_percentiles(self, field: str, percentiles: list[int] | None = None) -> "ElasticsearchQuery":
        """Add percentile metric."""
        self.metrics.append({
            "type": "percentiles",
            "field": field,
            "id": str(len(self.metrics) + 1),
            "settings": {
                "percents": percentiles or [25, 50, 75, 90, 95, 99],
            },
        })
        return self
    
    def group_by_date_histogram(self, interval: str = "auto") -> "ElasticsearchQuery":
        """Group by date histogram."""
        self.bucket_aggs.append({
            "type": "date_histogram",
            "id": str(len(self.bucket_aggs) + 1),
            "field": "@timestamp",
            "settings": {
                "interval": interval,
            },
        })
        return self
    
    def group_by_terms(self, field: str, size: int = 10) -> "ElasticsearchQuery":
        """Group by terms."""
        self.bucket_aggs.append({
            "type": "terms",
            "id": str(len(self.bucket_aggs) + 1),
            "field": field,
            "settings": {
                "size": str(size),
                "order": "desc",
                "orderBy": "_count",
            },
        })
        return self
    
    def build(self) -> dict[str, Any]:
        """Build query target dict."""
        return {
            "refId": self.ref_id,
            "query": self.query,
            "metrics": self.metrics or [{"type": "count", "id": "1"}],
            "bucketAggs": self.bucket_aggs or [{
                "type": "date_histogram",
                "id": "1",
                "field": "@timestamp",
                "settings": {"interval": "auto"},
            }],
        }


@dataclass
class LokiQuery:
    """Builder for Loki (LogQL) queries in Grafana."""
    
    expr: str
    legend_format: str | None = None
    max_lines: int = 1000
    ref_id: str = "A"
    
    def with_legend(self, legend: str) -> "LokiQuery":
        """Set legend format."""
        self.legend_format = legend
        return self
    
    def with_max_lines(self, max_lines: int) -> "LokiQuery":
        """Set maximum lines."""
        self.max_lines = max_lines
        return self
    
    def build(self) -> dict[str, Any]:
        """Build query target dict."""
        result = {
            "refId": self.ref_id,
            "expr": self.expr,
            "maxLines": self.max_lines,
        }
        
        if self.legend_format:
            result["legendFormat"] = self.legend_format
        
        return result


# ============================================================================
# Dashboard Query Helpers
# ============================================================================

@dataclass
class DashboardQuery:
    """Helper for querying dashboards."""
    
    tags: list[str] = field(default_factory=list)
    folder_ids: list[int] = field(default_factory=list)
    starred: bool | None = None
    search: str | None = None
    
    def with_tag(self, tag: str) -> "DashboardQuery":
        """Add a tag filter."""
        self.tags.append(tag)
        return self
    
    def with_tags(self, tags: list[str]) -> "DashboardQuery":
        """Add multiple tag filters."""
        self.tags.extend(tags)
        return self
    
    def in_folder(self, folder_id: int) -> "DashboardQuery":
        """Filter by folder."""
        self.folder_ids.append(folder_id)
        return self
    
    def only_starred(self) -> "DashboardQuery":
        """Only return starred dashboards."""
        self.starred = True
        return self
    
    def search_for(self, query: str) -> "DashboardQuery":
        """Search for dashboards."""
        self.search = query
        return self
    
    def to_params(self) -> dict[str, Any]:
        """Convert to API params."""
        params: dict[str, Any] = {}
        
        if self.tags:
            params["tags"] = self.tags
        if self.folder_ids:
            params["folder_ids"] = self.folder_ids
        if self.starred is not None:
            params["starred"] = self.starred
        if self.search:
            params["query"] = self.search
        
        return params


# ============================================================================
# Common Prometheus Queries for Grafana
# ============================================================================

class PrometheusQueries:
    """Pre-built Prometheus queries for common metrics."""
    
    @staticmethod
    def cpu_usage(instance: str | None = None, job: str | None = None) -> PrometheusQuery:
        """CPU usage percentage."""
        labels = []
        if instance:
            labels.append(f'instance="{instance}"')
        if job:
            labels.append(f'job="{job}"')
        
        label_str = ",".join(labels) if labels else ""
        expr = f'100 - (avg by(instance) (irate(node_cpu_seconds_total{{mode="idle"{("," + label_str) if label_str else ""}}}[5m])) * 100)'
        
        return PrometheusQuery(expr=expr).with_legend("{{instance}}")
    
    @staticmethod
    def memory_usage(instance: str | None = None) -> PrometheusQuery:
        """Memory usage percentage."""
        label_filter = f'instance="{instance}"' if instance else ""
        expr = f'(1 - (node_memory_MemAvailable_bytes{{{label_filter}}} / node_memory_MemTotal_bytes{{{label_filter}}})) * 100'
        
        return PrometheusQuery(expr=expr).with_legend("{{instance}}")
    
    @staticmethod
    def disk_usage(instance: str | None = None, mountpoint: str = "/") -> PrometheusQuery:
        """Disk usage percentage."""
        labels = [f'mountpoint="{mountpoint}"']
        if instance:
            labels.append(f'instance="{instance}"')
        
        label_str = ",".join(labels)
        expr = f'(1 - (node_filesystem_avail_bytes{{{label_str}}} / node_filesystem_size_bytes{{{label_str}}})) * 100'
        
        return PrometheusQuery(expr=expr).with_legend("{{instance}}:{{mountpoint}}")
    
    @staticmethod
    def network_receive_rate(instance: str | None = None, interface: str | None = None) -> PrometheusQuery:
        """Network receive rate in bytes/sec."""
        labels = []
        if instance:
            labels.append(f'instance="{instance}"')
        if interface:
            labels.append(f'device="{interface}"')
        
        label_str = ",".join(labels) if labels else ""
        expr = f'irate(node_network_receive_bytes_total{{{label_str}}}[5m])'
        
        return PrometheusQuery(expr=expr).with_legend("{{instance}}:{{device}} RX")
    
    @staticmethod
    def network_transmit_rate(instance: str | None = None, interface: str | None = None) -> PrometheusQuery:
        """Network transmit rate in bytes/sec."""
        labels = []
        if instance:
            labels.append(f'instance="{instance}"')
        if interface:
            labels.append(f'device="{interface}"')
        
        label_str = ",".join(labels) if labels else ""
        expr = f'irate(node_network_transmit_bytes_total{{{label_str}}}[5m])'
        
        return PrometheusQuery(expr=expr).with_legend("{{instance}}:{{device}} TX")
    
    @staticmethod
    def http_request_rate(job: str | None = None) -> PrometheusQuery:
        """HTTP request rate."""
        label_filter = f'job="{job}"' if job else ""
        expr = f'sum(rate(http_requests_total{{{label_filter}}}[5m])) by (handler, method, status)'
        
        return PrometheusQuery(expr=expr).with_legend("{{method}} {{handler}} {{status}}")
    
    @staticmethod
    def http_error_rate(job: str | None = None) -> PrometheusQuery:
        """HTTP error rate (4xx + 5xx)."""
        label_filter = f'job="{job}",' if job else ""
        expr = f'sum(rate(http_requests_total{{{label_filter}status=~"[45].*"}}[5m])) / sum(rate(http_requests_total{{{label_filter[:-1] if label_filter else ""}}}[5m])) * 100'
        
        return PrometheusQuery(expr=expr).with_legend("Error Rate %")
    
    @staticmethod
    def http_latency_p99(job: str | None = None) -> PrometheusQuery:
        """HTTP latency P99."""
        label_filter = f'job="{job}"' if job else ""
        expr = f'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{{{label_filter}}}[5m])) by (le, handler))'
        
        return PrometheusQuery(expr=expr).with_legend("{{handler}} P99")
    
    @staticmethod
    def container_cpu(container: str | None = None, namespace: str | None = None) -> PrometheusQuery:
        """Container CPU usage."""
        labels = []
        if container:
            labels.append(f'container="{container}"')
        if namespace:
            labels.append(f'namespace="{namespace}"')
        
        label_str = ",".join(labels) if labels else ""
        expr = f'sum(rate(container_cpu_usage_seconds_total{{{label_str}}}[5m])) by (container, namespace) * 100'
        
        return PrometheusQuery(expr=expr).with_legend("{{namespace}}/{{container}}")
    
    @staticmethod
    def container_memory(container: str | None = None, namespace: str | None = None) -> PrometheusQuery:
        """Container memory usage."""
        labels = []
        if container:
            labels.append(f'container="{container}"')
        if namespace:
            labels.append(f'namespace="{namespace}"')
        
        label_str = ",".join(labels) if labels else ""
        expr = f'sum(container_memory_working_set_bytes{{{label_str}}}) by (container, namespace)'
        
        return PrometheusQuery(expr=expr).with_legend("{{namespace}}/{{container}}")
    
    @staticmethod
    def pod_restarts(namespace: str | None = None) -> PrometheusQuery:
        """Kubernetes pod restarts."""
        label_filter = f'namespace="{namespace}"' if namespace else ""
        expr = f'sum(kube_pod_container_status_restarts_total{{{label_filter}}}) by (pod, namespace)'
        
        return PrometheusQuery(expr=expr).with_legend("{{namespace}}/{{pod}}")
    
    @staticmethod
    def up_status(job: str | None = None) -> PrometheusQuery:
        """Target up status."""
        label_filter = f'job="{job}"' if job else ""
        expr = f'up{{{label_filter}}}'
        
        return PrometheusQuery(expr=expr).with_legend("{{instance}}")


# ============================================================================
# Common Loki Queries for Grafana
# ============================================================================

class LokiQueries:
    """Pre-built Loki queries for common log patterns."""
    
    @staticmethod
    def by_app(app: str, namespace: str | None = None) -> LokiQuery:
        """Logs by application."""
        labels = [f'app="{app}"']
        if namespace:
            labels.append(f'namespace="{namespace}"')
        
        expr = "{" + ",".join(labels) + "}"
        return LokiQuery(expr=expr)
    
    @staticmethod
    def errors(app: str | None = None, namespace: str | None = None) -> LokiQuery:
        """Error logs."""
        labels = []
        if app:
            labels.append(f'app="{app}"')
        if namespace:
            labels.append(f'namespace="{namespace}"')
        
        label_str = ",".join(labels) if labels else ""
        expr = f'{{{label_str}}} |= "error" or |= "Error" or |= "ERROR"'
        
        return LokiQuery(expr=expr)
    
    @staticmethod
    def warnings(app: str | None = None) -> LokiQuery:
        """Warning logs."""
        label_filter = f'app="{app}"' if app else ""
        expr = f'{{{label_filter}}} |= "warn" or |= "WARN" or |= "warning"'
        
        return LokiQuery(expr=expr)
    
    @staticmethod
    def http_errors(app: str | None = None) -> LokiQuery:
        """HTTP error logs (4xx, 5xx)."""
        label_filter = f'app="{app}"' if app else ""
        expr = f'{{{label_filter}}} |~ "HTTP/[12].[01].\\ [45][0-9][0-9]"'
        
        return LokiQuery(expr=expr)
    
    @staticmethod
    def exceptions(app: str | None = None) -> LokiQuery:
        """Exception/traceback logs."""
        label_filter = f'app="{app}"' if app else ""
        expr = f'{{{label_filter}}} |~ "(?i)(exception|traceback|stack.?trace)"'
        
        return LokiQuery(expr=expr)
    
    @staticmethod
    def error_rate(app: str | None = None, interval: str = "5m") -> LokiQuery:
        """Error rate over time."""
        label_filter = f'app="{app}"' if app else ""
        expr = f'sum(count_over_time({{{label_filter}}} |= "error"[{interval}]))'
        
        return LokiQuery(expr=expr).with_legend("Error Count")


# ============================================================================
# Time Helpers
# ============================================================================

def relative_time(offset: str) -> str:
    """Create a relative time string (e.g., "now-1h")."""
    return f"now-{offset}"


def time_range_from_duration(duration: timedelta) -> tuple[str, str]:
    """
    Create a time range from a duration.
    
    Args:
        duration: Time duration
    
    Returns:
        Tuple of (from_time, to_time) as relative strings
    """
    total_seconds = int(duration.total_seconds())
    
    if total_seconds < 3600:
        from_str = f"now-{total_seconds // 60}m"
    elif total_seconds < 86400:
        from_str = f"now-{total_seconds // 3600}h"
    else:
        from_str = f"now-{total_seconds // 86400}d"
    
    return from_str, "now"


def time_range_absolute(
    start: datetime,
    end: datetime | None = None,
) -> tuple[int, int]:
    """
    Create an absolute time range in milliseconds.
    
    Args:
        start: Start time
        end: End time (defaults to now)
    
    Returns:
        Tuple of (from_ms, to_ms)
    """
    from_ms = int(start.timestamp() * 1000)
    to_ms = int((end or datetime.now()).timestamp() * 1000)
    
    return from_ms, to_ms
