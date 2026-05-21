"""PromQL query utilities and builders."""

from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import Any


class AggregationOp(str, Enum):
    """PromQL aggregation operators."""
    SUM = "sum"
    MIN = "min"
    MAX = "max"
    AVG = "avg"
    GROUP = "group"
    STDDEV = "stddev"
    STDVAR = "stdvar"
    COUNT = "count"
    COUNT_VALUES = "count_values"
    BOTTOMK = "bottomk"
    TOPK = "topk"
    QUANTILE = "quantile"


class BinaryOp(str, Enum):
    """PromQL binary operators."""
    ADD = "+"
    SUB = "-"
    MUL = "*"
    DIV = "/"
    MOD = "%"
    POW = "^"
    # Comparison
    EQ = "=="
    NE = "!="
    GT = ">"
    LT = "<"
    GE = ">="
    LE = "<="
    # Set
    AND = "and"
    OR = "or"
    UNLESS = "unless"


class MatchType(str, Enum):
    """Label matcher types."""
    EQ = "="
    NE = "!="
    RE = "=~"
    NRE = "!~"


@dataclass
class LabelMatcher:
    """A label matcher for PromQL."""
    label: str
    value: str
    match_type: MatchType = MatchType.EQ
    
    def __str__(self) -> str:
        return f'{self.label}{self.match_type.value}"{self.value}"'


@dataclass
class PromQLBuilder:
    """Builder for PromQL queries."""
    
    metric: str = ""
    labels: list[LabelMatcher] = field(default_factory=list)
    range_duration: str | None = None
    offset: str | None = None
    aggregation: AggregationOp | None = None
    aggregation_by: list[str] = field(default_factory=list)
    aggregation_without: list[str] = field(default_factory=list)
    aggregation_param: Any = None
    functions: list[tuple[str, list[Any]]] = field(default_factory=list)
    
    def with_label(
        self,
        label: str,
        value: str,
        match_type: MatchType = MatchType.EQ,
    ) -> "PromQLBuilder":
        """Add a label matcher."""
        self.labels.append(LabelMatcher(label, value, match_type))
        return self
    
    def eq(self, label: str, value: str) -> "PromQLBuilder":
        """Add an equality label matcher."""
        return self.with_label(label, value, MatchType.EQ)
    
    def ne(self, label: str, value: str) -> "PromQLBuilder":
        """Add a not-equal label matcher."""
        return self.with_label(label, value, MatchType.NE)
    
    def re(self, label: str, pattern: str) -> "PromQLBuilder":
        """Add a regex label matcher."""
        return self.with_label(label, pattern, MatchType.RE)
    
    def nre(self, label: str, pattern: str) -> "PromQLBuilder":
        """Add a negative regex label matcher."""
        return self.with_label(label, pattern, MatchType.NRE)
    
    def over(self, duration: str) -> "PromQLBuilder":
        """Add a range duration (e.g., "5m", "1h")."""
        self.range_duration = duration
        return self
    
    def with_offset(self, offset: str) -> "PromQLBuilder":
        """Add an offset (e.g., "1h", "1d")."""
        self.offset = offset
        return self
    
    # Aggregation methods
    
    def agg(
        self,
        op: AggregationOp,
        by: list[str] | None = None,
        without: list[str] | None = None,
        param: Any = None,
    ) -> "PromQLBuilder":
        """Add an aggregation."""
        self.aggregation = op
        if by:
            self.aggregation_by = by
        if without:
            self.aggregation_without = without
        if param is not None:
            self.aggregation_param = param
        return self
    
    def sum(self, by: list[str] | None = None, without: list[str] | None = None) -> "PromQLBuilder":
        return self.agg(AggregationOp.SUM, by=by, without=without)
    
    def avg(self, by: list[str] | None = None, without: list[str] | None = None) -> "PromQLBuilder":
        return self.agg(AggregationOp.AVG, by=by, without=without)
    
    def min(self, by: list[str] | None = None, without: list[str] | None = None) -> "PromQLBuilder":
        return self.agg(AggregationOp.MIN, by=by, without=without)
    
    def max(self, by: list[str] | None = None, without: list[str] | None = None) -> "PromQLBuilder":
        return self.agg(AggregationOp.MAX, by=by, without=without)
    
    def count(self, by: list[str] | None = None, without: list[str] | None = None) -> "PromQLBuilder":
        return self.agg(AggregationOp.COUNT, by=by, without=without)
    
    def topk(self, k: int, by: list[str] | None = None) -> "PromQLBuilder":
        return self.agg(AggregationOp.TOPK, by=by, param=k)
    
    def bottomk(self, k: int, by: list[str] | None = None) -> "PromQLBuilder":
        return self.agg(AggregationOp.BOTTOMK, by=by, param=k)
    
    def quantile(self, q: float, by: list[str] | None = None) -> "PromQLBuilder":
        return self.agg(AggregationOp.QUANTILE, by=by, param=q)
    
    def stddev(self, by: list[str] | None = None, without: list[str] | None = None) -> "PromQLBuilder":
        return self.agg(AggregationOp.STDDEV, by=by, without=without)
    
    # Function methods
    
    def func(self, name: str, *args: Any) -> "PromQLBuilder":
        """Apply a function."""
        self.functions.append((name, list(args)))
        return self
    
    def rate(self) -> "PromQLBuilder":
        """Apply rate function (requires range)."""
        return self.func("rate")
    
    def irate(self) -> "PromQLBuilder":
        """Apply irate function (requires range)."""
        return self.func("irate")
    
    def increase(self) -> "PromQLBuilder":
        """Apply increase function (requires range)."""
        return self.func("increase")
    
    def delta(self) -> "PromQLBuilder":
        """Apply delta function (requires range)."""
        return self.func("delta")
    
    def idelta(self) -> "PromQLBuilder":
        """Apply idelta function (requires range)."""
        return self.func("idelta")
    
    def deriv(self) -> "PromQLBuilder":
        """Apply deriv function (requires range)."""
        return self.func("deriv")
    
    def abs(self) -> "PromQLBuilder":
        """Apply abs function."""
        return self.func("abs")
    
    def ceil(self) -> "PromQLBuilder":
        """Apply ceil function."""
        return self.func("ceil")
    
    def floor(self) -> "PromQLBuilder":
        """Apply floor function."""
        return self.func("floor")
    
    def round(self, to_nearest: float = 1) -> "PromQLBuilder":
        """Apply round function."""
        return self.func("round", to_nearest)
    
    def clamp(self, min_val: float, max_val: float) -> "PromQLBuilder":
        """Apply clamp function."""
        return self.func("clamp", min_val, max_val)
    
    def clamp_min(self, min_val: float) -> "PromQLBuilder":
        """Apply clamp_min function."""
        return self.func("clamp_min", min_val)
    
    def clamp_max(self, max_val: float) -> "PromQLBuilder":
        """Apply clamp_max function."""
        return self.func("clamp_max", max_val)
    
    def histogram_quantile(self, quantile: float) -> "PromQLBuilder":
        """Apply histogram_quantile function."""
        return self.func("histogram_quantile", quantile)
    
    def label_replace(
        self,
        dst_label: str,
        replacement: str,
        src_label: str,
        regex: str,
    ) -> "PromQLBuilder":
        """Apply label_replace function."""
        return self.func("label_replace", dst_label, replacement, src_label, regex)
    
    def label_join(
        self,
        dst_label: str,
        separator: str,
        *src_labels: str,
    ) -> "PromQLBuilder":
        """Apply label_join function."""
        return self.func("label_join", dst_label, separator, *src_labels)
    
    def sort(self) -> "PromQLBuilder":
        """Apply sort function."""
        return self.func("sort")
    
    def sort_desc(self) -> "PromQLBuilder":
        """Apply sort_desc function."""
        return self.func("sort_desc")
    
    def absent(self) -> "PromQLBuilder":
        """Apply absent function."""
        return self.func("absent")
    
    def present_over_time(self) -> "PromQLBuilder":
        """Apply present_over_time function (requires range)."""
        return self.func("present_over_time")
    
    def changes(self) -> "PromQLBuilder":
        """Apply changes function (requires range)."""
        return self.func("changes")
    
    def resets(self) -> "PromQLBuilder":
        """Apply resets function (requires range)."""
        return self.func("resets")
    
    # Build method
    
    def build(self) -> str:
        """Build the PromQL expression."""
        # Start with metric and labels
        if self.labels:
            label_str = ",".join(str(l) for l in self.labels)
            expr = f"{self.metric}{{{label_str}}}"
        else:
            expr = self.metric if self.metric else "{}"
        
        # Add range
        if self.range_duration:
            expr = f"{expr}[{self.range_duration}]"
        
        # Add offset
        if self.offset:
            expr = f"{expr} offset {self.offset}"
        
        # Apply functions (inner to outer)
        for func_name, func_args in self.functions:
            if func_args:
                args_str = ", ".join(str(a) for a in func_args)
                expr = f"{func_name}({args_str}, {expr})"
            else:
                expr = f"{func_name}({expr})"
        
        # Apply aggregation
        if self.aggregation:
            agg_str = self.aggregation.value
            
            # Handle param for topk, bottomk, quantile
            if self.aggregation_param is not None:
                agg_str = f"{agg_str}({self.aggregation_param}, {expr})"
            else:
                agg_str = f"{agg_str}({expr})"
            
            # Handle by/without
            if self.aggregation_by:
                labels = ", ".join(self.aggregation_by)
                expr = f"{self.aggregation.value} by ({labels}) ({expr})"
            elif self.aggregation_without:
                labels = ", ".join(self.aggregation_without)
                expr = f"{self.aggregation.value} without ({labels}) ({expr})"
            elif self.aggregation_param is not None:
                expr = agg_str
            else:
                expr = f"{self.aggregation.value}({expr})"
        
        return expr


def metric(name: str) -> PromQLBuilder:
    """Start building a PromQL query from a metric name."""
    return PromQLBuilder(metric=name)


def query(expr: str) -> str:
    """Return a raw PromQL expression (passthrough)."""
    return expr


# ============================================================================
# Pre-built Common Queries
# ============================================================================

class SystemQueries:
    """Common system metric queries."""
    
    @staticmethod
    def cpu_usage(instance: str | None = None, job: str | None = None) -> str:
        """CPU usage percentage (node_exporter)."""
        builder = metric("node_cpu_seconds_total").eq("mode", "idle")
        if instance:
            builder.eq("instance", instance)
        if job:
            builder.eq("job", job)
        
        # Calculate 100 - idle percentage
        expr = builder.over("5m").irate().avg(by=["instance"]).build()
        return f"100 - ({expr} * 100)"
    
    @staticmethod
    def memory_usage(instance: str | None = None) -> str:
        """Memory usage percentage (node_exporter)."""
        available = metric("node_memory_MemAvailable_bytes")
        total = metric("node_memory_MemTotal_bytes")
        
        if instance:
            available.eq("instance", instance)
            total.eq("instance", instance)
        
        return f"(1 - ({available.build()} / {total.build()})) * 100"
    
    @staticmethod
    def disk_usage(instance: str | None = None, mountpoint: str = "/") -> str:
        """Disk usage percentage (node_exporter)."""
        avail = metric("node_filesystem_avail_bytes").eq("mountpoint", mountpoint)
        size = metric("node_filesystem_size_bytes").eq("mountpoint", mountpoint)
        
        if instance:
            avail.eq("instance", instance)
            size.eq("instance", instance)
        
        return f"(1 - ({avail.build()} / {size.build()})) * 100"
    
    @staticmethod
    def load_average(instance: str | None = None, minutes: int = 1) -> str:
        """System load average (node_exporter)."""
        builder = metric(f"node_load{minutes}")
        if instance:
            builder.eq("instance", instance)
        return builder.build()
    
    @staticmethod
    def network_receive_rate(instance: str | None = None, device: str | None = None) -> str:
        """Network receive rate in bytes/sec."""
        builder = metric("node_network_receive_bytes_total").over("5m").irate()
        if instance:
            builder.eq("instance", instance)
        if device:
            builder.eq("device", device)
        return builder.build()
    
    @staticmethod
    def network_transmit_rate(instance: str | None = None, device: str | None = None) -> str:
        """Network transmit rate in bytes/sec."""
        builder = metric("node_network_transmit_bytes_total").over("5m").irate()
        if instance:
            builder.eq("instance", instance)
        if device:
            builder.eq("device", device)
        return builder.build()
    
    @staticmethod
    def up(job: str | None = None) -> str:
        """Target up status."""
        builder = metric("up")
        if job:
            builder.eq("job", job)
        return builder.build()


class KubernetesQueries:
    """Common Kubernetes metric queries."""
    
    @staticmethod
    def pod_cpu_usage(namespace: str | None = None, pod: str | None = None) -> str:
        """Pod CPU usage."""
        builder = metric("container_cpu_usage_seconds_total").ne("container", "").over("5m").rate()
        if namespace:
            builder.eq("namespace", namespace)
        if pod:
            builder.eq("pod", pod)
        return builder.sum(by=["namespace", "pod"]).build()
    
    @staticmethod
    def pod_memory_usage(namespace: str | None = None, pod: str | None = None) -> str:
        """Pod memory usage (working set)."""
        builder = metric("container_memory_working_set_bytes").ne("container", "")
        if namespace:
            builder.eq("namespace", namespace)
        if pod:
            builder.eq("pod", pod)
        return builder.sum(by=["namespace", "pod"]).build()
    
    @staticmethod
    def pod_restarts(namespace: str | None = None, pod: str | None = None) -> str:
        """Pod container restarts."""
        builder = metric("kube_pod_container_status_restarts_total")
        if namespace:
            builder.eq("namespace", namespace)
        if pod:
            builder.eq("pod", pod)
        return builder.sum(by=["namespace", "pod"]).build()
    
    @staticmethod
    def deployment_replicas_available(namespace: str | None = None, deployment: str | None = None) -> str:
        """Available deployment replicas."""
        builder = metric("kube_deployment_status_replicas_available")
        if namespace:
            builder.eq("namespace", namespace)
        if deployment:
            builder.eq("deployment", deployment)
        return builder.build()
    
    @staticmethod
    def deployment_replicas_desired(namespace: str | None = None, deployment: str | None = None) -> str:
        """Desired deployment replicas."""
        builder = metric("kube_deployment_spec_replicas")
        if namespace:
            builder.eq("namespace", namespace)
        if deployment:
            builder.eq("deployment", deployment)
        return builder.build()
    
    @staticmethod
    def node_conditions(condition: str = "Ready") -> str:
        """Node condition status."""
        return metric("kube_node_status_condition").eq("condition", condition).eq("status", "true").build()


class HTTPQueries:
    """Common HTTP metric queries."""
    
    @staticmethod
    def request_rate(job: str | None = None, handler: str | None = None) -> str:
        """HTTP request rate."""
        builder = metric("http_requests_total").over("5m").rate()
        if job:
            builder.eq("job", job)
        if handler:
            builder.eq("handler", handler)
        return builder.sum(by=["handler", "method", "status"]).build()
    
    @staticmethod
    def error_rate(job: str | None = None) -> str:
        """HTTP error rate (4xx + 5xx / total)."""
        errors = metric("http_requests_total").re("status", "[45]..").over("5m").rate().sum()
        total = metric("http_requests_total").over("5m").rate().sum()
        
        if job:
            errors.eq("job", job)
            total.eq("job", job)
        
        return f"({errors.build()}) / ({total.build()}) * 100"
    
    @staticmethod
    def latency_p50(job: str | None = None) -> str:
        """HTTP P50 latency."""
        builder = metric("http_request_duration_seconds_bucket").over("5m").rate()
        if job:
            builder.eq("job", job)
        inner = builder.sum(by=["le", "handler"]).build()
        return f"histogram_quantile(0.50, {inner})"
    
    @staticmethod
    def latency_p95(job: str | None = None) -> str:
        """HTTP P95 latency."""
        builder = metric("http_request_duration_seconds_bucket").over("5m").rate()
        if job:
            builder.eq("job", job)
        inner = builder.sum(by=["le", "handler"]).build()
        return f"histogram_quantile(0.95, {inner})"
    
    @staticmethod
    def latency_p99(job: str | None = None) -> str:
        """HTTP P99 latency."""
        builder = metric("http_request_duration_seconds_bucket").over("5m").rate()
        if job:
            builder.eq("job", job)
        inner = builder.sum(by=["le", "handler"]).build()
        return f"histogram_quantile(0.99, {inner})"


class GRPCQueries:
    """Common gRPC metric queries."""
    
    @staticmethod
    def request_rate(service: str | None = None, method: str | None = None) -> str:
        """gRPC request rate."""
        builder = metric("grpc_server_handled_total").over("5m").rate()
        if service:
            builder.eq("grpc_service", service)
        if method:
            builder.eq("grpc_method", method)
        return builder.sum(by=["grpc_service", "grpc_method", "grpc_code"]).build()
    
    @staticmethod
    def error_rate(service: str | None = None) -> str:
        """gRPC error rate (non-OK codes)."""
        errors = metric("grpc_server_handled_total").ne("grpc_code", "OK").over("5m").rate().sum()
        total = metric("grpc_server_handled_total").over("5m").rate().sum()
        
        if service:
            errors.eq("grpc_service", service)
            total.eq("grpc_service", service)
        
        return f"({errors.build()}) / ({total.build()}) * 100"


# ============================================================================
# Duration Helpers
# ============================================================================

def duration_string(td: timedelta) -> str:
    """Convert a timedelta to a Prometheus duration string."""
    total_seconds = int(td.total_seconds())
    
    if total_seconds < 60:
        return f"{total_seconds}s"
    elif total_seconds < 3600:
        return f"{total_seconds // 60}m"
    elif total_seconds < 86400:
        return f"{total_seconds // 3600}h"
    else:
        return f"{total_seconds // 86400}d"


def parse_duration(duration: str) -> timedelta:
    """Parse a Prometheus duration string to timedelta."""
    import re
    
    match = re.match(r"^(\d+)([smhdwy])$", duration)
    if not match:
        raise ValueError(f"Invalid duration: {duration}")
    
    value = int(match.group(1))
    unit = match.group(2)
    
    units = {
        "s": timedelta(seconds=1),
        "m": timedelta(minutes=1),
        "h": timedelta(hours=1),
        "d": timedelta(days=1),
        "w": timedelta(weeks=1),
        "y": timedelta(days=365),
    }
    
    return units[unit] * value
