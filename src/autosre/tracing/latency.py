"""
Latency Profiler for AutoSRE V2.

Tracks and analyzes latency distributions with SLO support.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger
from .models import Span, Trace

logger = get_logger(__name__)


@dataclass
class ProfilerConfig:
    """Configuration for latency profiler."""
    
    # Histogram buckets (in ms)
    histogram_buckets: list[float] = field(
        default_factory=lambda: [
            1, 5, 10, 25, 50, 75, 100, 150, 200, 250, 300, 400, 500,
            750, 1000, 1500, 2000, 3000, 5000, 10000, float("inf")
        ]
    )
    
    # Percentiles to track
    percentiles: list[float] = field(
        default_factory=lambda: [0.5, 0.75, 0.9, 0.95, 0.99, 0.999]
    )
    
    # Sampling
    max_samples_per_operation: int = 10000
    
    # Time bucketing
    time_bucket_minutes: int = 5
    
    # Alerting
    enable_alerts: bool = True
    alert_cooldown_seconds: float = 300.0


@dataclass
class SLOConfig:
    """Configuration for an SLO."""
    
    name: str
    service: str
    operation: Optional[str] = None
    
    # Latency SLO
    latency_p50_ms: Optional[float] = None
    latency_p95_ms: Optional[float] = None
    latency_p99_ms: Optional[float] = None
    
    # Availability SLO
    error_budget_percent: float = 0.1  # 99.9% availability
    
    # Throughput SLO
    min_throughput_per_minute: Optional[float] = None
    
    # Evaluation window
    window_minutes: int = 60
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "service": self.service,
            "operation": self.operation,
            "latency_p50_ms": self.latency_p50_ms,
            "latency_p95_ms": self.latency_p95_ms,
            "latency_p99_ms": self.latency_p99_ms,
            "error_budget_percent": self.error_budget_percent,
            "min_throughput_per_minute": self.min_throughput_per_minute,
            "window_minutes": self.window_minutes,
        }


@dataclass
class LatencyBucket:
    """A single histogram bucket."""
    
    le: float  # Less than or equal to
    count: int = 0
    
    def __str__(self) -> str:
        return f"le={self.le}: {self.count}"


@dataclass
class LatencyDistribution:
    """A complete latency distribution."""
    
    # Histogram
    buckets: list[LatencyBucket] = field(default_factory=list)
    
    # Raw samples (for percentile calculation)
    samples: list[float] = field(default_factory=list)
    
    # Summary statistics
    count: int = 0
    sum_ms: float = 0.0
    min_ms: float = float("inf")
    max_ms: float = 0.0
    
    # Time range
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    def record(self, latency_ms: float, timestamp: Optional[datetime] = None) -> None:
        """Record a latency sample."""
        self.count += 1
        self.sum_ms += latency_ms
        self.min_ms = min(self.min_ms, latency_ms)
        self.max_ms = max(self.max_ms, latency_ms)
        
        # Update histogram
        for bucket in self.buckets:
            if latency_ms <= bucket.le:
                bucket.count += 1
                break
        
        # Store sample (with limit)
        if len(self.samples) < 10000:
            self.samples.append(latency_ms)
        
        # Update time range
        if timestamp:
            if self.start_time is None or timestamp < self.start_time:
                self.start_time = timestamp
            if self.end_time is None or timestamp > self.end_time:
                self.end_time = timestamp
    
    @property
    def mean_ms(self) -> float:
        """Calculate mean latency."""
        if self.count == 0:
            return 0.0
        return self.sum_ms / self.count
    
    @property
    def std_ms(self) -> float:
        """Calculate standard deviation."""
        if len(self.samples) < 2:
            return 0.0
        return statistics.stdev(self.samples)
    
    def percentile(self, p: float) -> float:
        """Calculate a specific percentile."""
        if not self.samples:
            return 0.0
        
        sorted_samples = sorted(self.samples)
        idx = int(len(sorted_samples) * p)
        idx = min(idx, len(sorted_samples) - 1)
        return sorted_samples[idx]
    
    @property
    def p50_ms(self) -> float:
        return self.percentile(0.5)
    
    @property
    def p90_ms(self) -> float:
        return self.percentile(0.9)
    
    @property
    def p95_ms(self) -> float:
        return self.percentile(0.95)
    
    @property
    def p99_ms(self) -> float:
        return self.percentile(0.99)
    
    @property
    def p999_ms(self) -> float:
        return self.percentile(0.999)
    
    @property
    def duration_seconds(self) -> float:
        """Get duration of the distribution window."""
        if not self.start_time or not self.end_time:
            return 0.0
        return (self.end_time - self.start_time).total_seconds()
    
    @property
    def throughput_per_second(self) -> float:
        """Calculate throughput."""
        duration = self.duration_seconds
        if duration <= 0:
            return 0.0
        return self.count / duration
    
    def merge(self, other: "LatencyDistribution") -> None:
        """Merge another distribution into this one."""
        self.count += other.count
        self.sum_ms += other.sum_ms
        self.min_ms = min(self.min_ms, other.min_ms)
        self.max_ms = max(self.max_ms, other.max_ms)
        
        # Merge histograms
        for i, bucket in enumerate(self.buckets):
            if i < len(other.buckets):
                bucket.count += other.buckets[i].count
        
        # Merge samples (with limit)
        remaining = 10000 - len(self.samples)
        if remaining > 0:
            self.samples.extend(other.samples[:remaining])
        
        # Merge time range
        if other.start_time:
            if self.start_time is None or other.start_time < self.start_time:
                self.start_time = other.start_time
        if other.end_time:
            if self.end_time is None or other.end_time > self.end_time:
                self.end_time = other.end_time
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "mean_ms": self.mean_ms,
            "min_ms": self.min_ms if self.min_ms != float("inf") else 0,
            "max_ms": self.max_ms,
            "std_ms": self.std_ms,
            "p50_ms": self.p50_ms,
            "p90_ms": self.p90_ms,
            "p95_ms": self.p95_ms,
            "p99_ms": self.p99_ms,
            "p999_ms": self.p999_ms,
            "throughput_per_second": self.throughput_per_second,
            "histogram": [(b.le, b.count) for b in self.buckets],
        }
    
    @classmethod
    def with_buckets(cls, bucket_boundaries: list[float]) -> "LatencyDistribution":
        """Create a distribution with specified bucket boundaries."""
        buckets = [LatencyBucket(le=b) for b in bucket_boundaries]
        return cls(buckets=buckets)


@dataclass
class PercentileTracker:
    """Tracks percentiles over time windows."""
    
    service: str
    operation: str
    
    # Time-bucketed distributions
    time_buckets: dict[datetime, LatencyDistribution] = field(default_factory=dict)
    
    # Overall distribution
    overall: LatencyDistribution = field(default_factory=LatencyDistribution)
    
    # Configuration
    bucket_minutes: int = 5
    max_buckets: int = 288  # 24 hours at 5-min intervals
    histogram_boundaries: list[float] = field(default_factory=list)
    
    def record(self, latency_ms: float, timestamp: datetime) -> None:
        """Record a latency sample."""
        # Record to overall
        self.overall.record(latency_ms, timestamp)
        
        # Record to time bucket
        bucket_time = self._get_bucket_time(timestamp)
        
        if bucket_time not in self.time_buckets:
            if not self.histogram_boundaries:
                self.histogram_boundaries = [
                    1, 5, 10, 25, 50, 75, 100, 150, 200, 250, 300, 400, 500,
                    750, 1000, 1500, 2000, 3000, 5000, 10000, float("inf")
                ]
            
            self.time_buckets[bucket_time] = LatencyDistribution.with_buckets(
                self.histogram_boundaries
            )
            
            # Cleanup old buckets
            self._cleanup_old_buckets()
        
        self.time_buckets[bucket_time].record(latency_ms, timestamp)
    
    def _get_bucket_time(self, timestamp: datetime) -> datetime:
        """Get the bucket time for a timestamp."""
        minutes = (timestamp.minute // self.bucket_minutes) * self.bucket_minutes
        return timestamp.replace(minute=minutes, second=0, microsecond=0)
    
    def _cleanup_old_buckets(self) -> None:
        """Remove old time buckets."""
        if len(self.time_buckets) <= self.max_buckets:
            return
        
        sorted_times = sorted(self.time_buckets.keys())
        to_remove = len(self.time_buckets) - self.max_buckets
        
        for t in sorted_times[:to_remove]:
            del self.time_buckets[t]
    
    def get_distribution(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> LatencyDistribution:
        """Get distribution for a time range."""
        if start is None and end is None:
            return self.overall
        
        result = LatencyDistribution.with_buckets(self.histogram_boundaries)
        
        for bucket_time, dist in self.time_buckets.items():
            if start and bucket_time < start:
                continue
            if end and bucket_time > end:
                continue
            result.merge(dist)
        
        return result
    
    def get_time_series(
        self,
        percentile: float = 0.95,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[tuple[datetime, float]]:
        """Get percentile time series."""
        series = []
        
        for bucket_time in sorted(self.time_buckets.keys()):
            if start and bucket_time < start:
                continue
            if end and bucket_time > end:
                continue
            
            dist = self.time_buckets[bucket_time]
            value = dist.percentile(percentile)
            series.append((bucket_time, value))
        
        return series
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "operation": self.operation,
            "overall": self.overall.to_dict(),
            "bucket_count": len(self.time_buckets),
            "bucket_minutes": self.bucket_minutes,
        }


@dataclass
class LatencyAlert:
    """An alert for SLO violation."""
    
    slo: SLOConfig
    violation_type: str  # "latency_p50", "latency_p95", "latency_p99", "error_budget", "throughput"
    
    current_value: float
    threshold_value: float
    
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Context
    service: str = ""
    operation: str = ""
    sample_count: int = 0
    
    @property
    def severity(self) -> str:
        """Calculate alert severity."""
        if self.threshold_value == 0:
            return "critical"
        
        ratio = self.current_value / self.threshold_value
        
        if ratio >= 2.0:
            return "critical"
        elif ratio >= 1.5:
            return "high"
        elif ratio >= 1.2:
            return "medium"
        return "low"
    
    @property
    def message(self) -> str:
        """Generate alert message."""
        return (
            f"SLO violation for {self.slo.name}: "
            f"{self.violation_type} is {self.current_value:.1f} "
            f"(threshold: {self.threshold_value:.1f})"
        )
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "slo_name": self.slo.name,
            "violation_type": self.violation_type,
            "current_value": self.current_value,
            "threshold_value": self.threshold_value,
            "severity": self.severity,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "service": self.service,
            "operation": self.operation,
            "sample_count": self.sample_count,
        }


@dataclass
class LatencyProfile:
    """Complete latency profile for a service/operation."""
    
    service: str
    operation: str
    
    # Distributions
    overall: LatencyDistribution
    by_status: dict[str, LatencyDistribution] = field(default_factory=dict)  # "ok", "error"
    by_endpoint: dict[str, LatencyDistribution] = field(default_factory=dict)
    
    # Time-based tracking
    tracker: Optional[PercentileTracker] = None
    
    # SLO evaluation
    slo_status: dict[str, bool] = field(default_factory=dict)  # SLO name -> meeting?
    alerts: list[LatencyAlert] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "operation": self.operation,
            "overall": self.overall.to_dict(),
            "by_status": {k: v.to_dict() for k, v in self.by_status.items()},
            "slo_status": self.slo_status,
            "alert_count": len(self.alerts),
        }


class LatencyProfiler:
    """
    Tracks and profiles latency across services and operations.
    
    Example:
        profiler = LatencyProfiler()
        
        # Process traces
        profiler.process_traces(traces)
        
        # Get profile for a service
        profile = profiler.get_profile("api-gateway")
        print(f"P99: {profile.overall.p99_ms}ms")
        
        # Check SLOs
        alerts = profiler.check_slos()
    """
    
    def __init__(self, config: Optional[ProfilerConfig] = None):
        self.config = config or ProfilerConfig()
        
        # Trackers by service:operation
        self._trackers: dict[str, PercentileTracker] = {}
        
        # SLO configurations
        self._slos: list[SLOConfig] = []
        
        # Alert state
        self._last_alerts: dict[str, datetime] = {}
    
    def process_traces(self, traces: Sequence[Trace]) -> None:
        """Process traces and update latency tracking."""
        for trace in traces:
            for span in trace.spans:
                self._record_span(span)
    
    def process_spans(self, spans: Sequence[Span]) -> None:
        """Process individual spans."""
        for span in spans:
            self._record_span(span)
    
    def _record_span(self, span: Span) -> None:
        """Record a span's latency."""
        key = f"{span.service_name}:{span.name}"
        
        if key not in self._trackers:
            self._trackers[key] = PercentileTracker(
                service=span.service_name,
                operation=span.name,
                histogram_boundaries=self.config.histogram_buckets,
                bucket_minutes=self.config.time_bucket_minutes,
            )
        
        self._trackers[key].record(span.duration_ms, span.start_time)
    
    def get_profile(
        self,
        service: str,
        operation: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> LatencyProfile:
        """
        Get latency profile for a service/operation.
        
        If operation is None, aggregates across all operations.
        """
        # Find matching trackers
        matching_trackers = []
        
        for key, tracker in self._trackers.items():
            if tracker.service != service:
                continue
            if operation and tracker.operation != operation:
                continue
            matching_trackers.append(tracker)
        
        if not matching_trackers:
            # Return empty profile
            return LatencyProfile(
                service=service,
                operation=operation or "*",
                overall=LatencyDistribution.with_buckets(self.config.histogram_buckets),
            )
        
        # Aggregate distributions
        overall = LatencyDistribution.with_buckets(self.config.histogram_buckets)
        
        for tracker in matching_trackers:
            dist = tracker.get_distribution(start, end)
            overall.merge(dist)
        
        # Evaluate SLOs
        slo_status = {}
        for slo in self._slos:
            if slo.service != service:
                continue
            if slo.operation and slo.operation != operation:
                continue
            
            slo_status[slo.name] = self._evaluate_slo(slo, overall)
        
        return LatencyProfile(
            service=service,
            operation=operation or "*",
            overall=overall,
            tracker=matching_trackers[0] if len(matching_trackers) == 1 else None,
            slo_status=slo_status,
        )
    
    def get_all_profiles(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[LatencyProfile]:
        """Get profiles for all tracked services/operations."""
        profiles = []
        
        for key, tracker in self._trackers.items():
            dist = tracker.get_distribution(start, end)
            
            profiles.append(LatencyProfile(
                service=tracker.service,
                operation=tracker.operation,
                overall=dist,
                tracker=tracker,
            ))
        
        return profiles
    
    def get_percentile_timeseries(
        self,
        service: str,
        operation: str,
        percentile: float = 0.95,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[tuple[datetime, float]]:
        """Get percentile time series for a service/operation."""
        key = f"{service}:{operation}"
        
        if key not in self._trackers:
            return []
        
        return self._trackers[key].get_time_series(percentile, start, end)
    
    def add_slo(self, slo: SLOConfig) -> None:
        """Add an SLO configuration."""
        self._slos.append(slo)
    
    def remove_slo(self, name: str) -> bool:
        """Remove an SLO by name."""
        original_len = len(self._slos)
        self._slos = [s for s in self._slos if s.name != name]
        return len(self._slos) < original_len
    
    def check_slos(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[LatencyAlert]:
        """
        Check all SLOs and return alerts for violations.
        """
        alerts = []
        
        for slo in self._slos:
            profile = self.get_profile(slo.service, slo.operation, start, end)
            
            if profile.overall.count == 0:
                continue  # No data
            
            dist = profile.overall
            
            # Check latency SLOs
            if slo.latency_p50_ms and dist.p50_ms > slo.latency_p50_ms:
                alert = self._create_alert(
                    slo, "latency_p50",
                    dist.p50_ms, slo.latency_p50_ms,
                    profile,
                )
                if alert:
                    alerts.append(alert)
            
            if slo.latency_p95_ms and dist.p95_ms > slo.latency_p95_ms:
                alert = self._create_alert(
                    slo, "latency_p95",
                    dist.p95_ms, slo.latency_p95_ms,
                    profile,
                )
                if alert:
                    alerts.append(alert)
            
            if slo.latency_p99_ms and dist.p99_ms > slo.latency_p99_ms:
                alert = self._create_alert(
                    slo, "latency_p99",
                    dist.p99_ms, slo.latency_p99_ms,
                    profile,
                )
                if alert:
                    alerts.append(alert)
            
            # Check throughput SLO
            if slo.min_throughput_per_minute:
                throughput = dist.throughput_per_second * 60
                if throughput < slo.min_throughput_per_minute:
                    alert = self._create_alert(
                        slo, "throughput",
                        throughput, slo.min_throughput_per_minute,
                        profile,
                    )
                    if alert:
                        alerts.append(alert)
        
        return alerts
    
    def _evaluate_slo(
        self,
        slo: SLOConfig,
        dist: LatencyDistribution,
    ) -> bool:
        """Evaluate if an SLO is being met."""
        if slo.latency_p50_ms and dist.p50_ms > slo.latency_p50_ms:
            return False
        if slo.latency_p95_ms and dist.p95_ms > slo.latency_p95_ms:
            return False
        if slo.latency_p99_ms and dist.p99_ms > slo.latency_p99_ms:
            return False
        if slo.min_throughput_per_minute:
            if dist.throughput_per_second * 60 < slo.min_throughput_per_minute:
                return False
        return True
    
    def _create_alert(
        self,
        slo: SLOConfig,
        violation_type: str,
        current_value: float,
        threshold_value: float,
        profile: LatencyProfile,
    ) -> Optional[LatencyAlert]:
        """Create an alert if not in cooldown."""
        if not self.config.enable_alerts:
            return None
        
        # Check cooldown
        alert_key = f"{slo.name}:{violation_type}"
        now = datetime.now(timezone.utc)
        
        if alert_key in self._last_alerts:
            last_alert = self._last_alerts[alert_key]
            if (now - last_alert).total_seconds() < self.config.alert_cooldown_seconds:
                return None
        
        self._last_alerts[alert_key] = now
        
        return LatencyAlert(
            slo=slo,
            violation_type=violation_type,
            current_value=current_value,
            threshold_value=threshold_value,
            service=profile.service,
            operation=profile.operation,
            sample_count=profile.overall.count,
        )
    
    def get_summary(self) -> dict[str, Any]:
        """Get summary of all tracked latencies."""
        services: dict[str, dict] = defaultdict(lambda: {
            "operations": [],
            "total_count": 0,
            "avg_p50_ms": 0,
            "avg_p95_ms": 0,
            "avg_p99_ms": 0,
        })
        
        for key, tracker in self._trackers.items():
            dist = tracker.overall
            service_info = services[tracker.service]
            
            service_info["operations"].append({
                "name": tracker.operation,
                "count": dist.count,
                "p50_ms": dist.p50_ms,
                "p95_ms": dist.p95_ms,
                "p99_ms": dist.p99_ms,
            })
            service_info["total_count"] += dist.count
        
        # Calculate service-level averages
        for service, info in services.items():
            if info["operations"]:
                info["avg_p50_ms"] = statistics.mean(
                    op["p50_ms"] for op in info["operations"]
                )
                info["avg_p95_ms"] = statistics.mean(
                    op["p95_ms"] for op in info["operations"]
                )
                info["avg_p99_ms"] = statistics.mean(
                    op["p99_ms"] for op in info["operations"]
                )
        
        return {
            "service_count": len(services),
            "operation_count": len(self._trackers),
            "slo_count": len(self._slos),
            "services": dict(services),
        }
    
    def reset(self) -> None:
        """Reset all tracking data."""
        self._trackers.clear()
        self._last_alerts.clear()
    
    def export_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        
        # Export histogram metrics
        for key, tracker in self._trackers.items():
            dist = tracker.overall
            
            base_name = f"autosre_latency_ms"
            labels = f'service="{tracker.service}",operation="{tracker.operation}"'
            
            # Histogram buckets
            for bucket in dist.buckets:
                le = bucket.le if bucket.le != float("inf") else "+Inf"
                lines.append(f'{base_name}_bucket{{{labels},le="{le}"}} {bucket.count}')
            
            # Sum and count
            lines.append(f'{base_name}_sum{{{labels}}} {dist.sum_ms}')
            lines.append(f'{base_name}_count{{{labels}}} {dist.count}')
        
        return "\n".join(lines)
