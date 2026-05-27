"""
SLO Configuration Schema

Defines the configuration schema for SLO definitions and thresholds.
Supports both programmatic and YAML/JSON configuration.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import yaml
import json


class SLOType(Enum):
    """Types of SLO metrics."""
    AVAILABILITY = "availability"       # Request success rate
    LATENCY = "latency"                 # Response time percentile
    THROUGHPUT = "throughput"           # Requests per second
    ERROR_RATE = "error_rate"           # Error percentage
    SATURATION = "saturation"           # Resource utilization


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    PAGE = "page"


@dataclass
class LatencyTarget:
    """Latency SLO target."""
    percentile: float = 99.0        # p50, p90, p99, etc.
    threshold_ms: float = 200       # Target latency
    
    def to_dict(self) -> dict:
        return {
            "percentile": self.percentile,
            "threshold_ms": self.threshold_ms,
        }


@dataclass
class AlertConfig:
    """Alert configuration for SLO violation."""
    enabled: bool = True
    severity: AlertSeverity = AlertSeverity.WARNING
    burn_rate_threshold: float = 1.0    # Alert when burn rate exceeds this
    short_window: str = "5m"            # Short window for multi-window alerts
    long_window: str = "1h"             # Long window for multi-window alerts
    
    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "severity": self.severity.value,
            "burn_rate_threshold": self.burn_rate_threshold,
            "short_window": self.short_window,
            "long_window": self.long_window,
        }


@dataclass
class SLODefinition:
    """
    Complete SLO definition for a service.
    
    Example:
        slo = SLODefinition(
            name="api-availability",
            service="api-gateway",
            slo_type=SLOType.AVAILABILITY,
            target=0.999,
            window_days=30,
        )
    """
    name: str
    service: str
    slo_type: SLOType
    target: float                       # Target value (0.999 for 99.9%)
    window_days: int = 30               # Measurement window
    
    # Description
    description: str = ""
    owner: str = ""
    tier: str = "standard"              # critical, standard, best-effort
    
    # Latency-specific (only for latency SLOs)
    latency_target: Optional[LatencyTarget] = None
    
    # Alerting
    alerts: list[AlertConfig] = field(default_factory=list)
    
    # Deploy blocking
    block_deploys_below: float = 20.0   # Block deploys below this % budget
    
    # Prometheus queries
    prometheus_good_query: str = ""     # Query for good events
    prometheus_total_query: str = ""    # Query for total events
    
    # Metadata
    labels: dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "service": self.service,
            "slo_type": self.slo_type.value,
            "target": self.target,
            "target_percent": f"{self.target * 100:.3f}%",
            "window_days": self.window_days,
            "description": self.description,
            "owner": self.owner,
            "tier": self.tier,
            "latency_target": self.latency_target.to_dict() if self.latency_target else None,
            "alerts": [a.to_dict() for a in self.alerts],
            "block_deploys_below": self.block_deploys_below,
            "prometheus_good_query": self.prometheus_good_query,
            "prometheus_total_query": self.prometheus_total_query,
            "labels": self.labels,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SLODefinition":
        """Create SLODefinition from dictionary."""
        alerts = [
            AlertConfig(
                enabled=a.get("enabled", True),
                severity=AlertSeverity(a.get("severity", "warning")),
                burn_rate_threshold=a.get("burn_rate_threshold", 1.0),
                short_window=a.get("short_window", "5m"),
                long_window=a.get("long_window", "1h"),
            )
            for a in data.get("alerts", [])
        ]
        
        latency_target = None
        if data.get("latency_target"):
            lt = data["latency_target"]
            latency_target = LatencyTarget(
                percentile=lt.get("percentile", 99.0),
                threshold_ms=lt.get("threshold_ms", 200),
            )
        
        return cls(
            name=data["name"],
            service=data["service"],
            slo_type=SLOType(data.get("slo_type", "availability")),
            target=data["target"],
            window_days=data.get("window_days", 30),
            description=data.get("description", ""),
            owner=data.get("owner", ""),
            tier=data.get("tier", "standard"),
            latency_target=latency_target,
            alerts=alerts,
            block_deploys_below=data.get("block_deploys_below", 20.0),
            prometheus_good_query=data.get("prometheus_good_query", ""),
            prometheus_total_query=data.get("prometheus_total_query", ""),
            labels=data.get("labels", {}),
        )
    
    @property
    def error_budget(self) -> float:
        """Calculate error budget from target."""
        return 1 - self.target
    
    @property
    def error_budget_percent(self) -> float:
        """Error budget as percentage."""
        return self.error_budget * 100


@dataclass
class CascadeThresholds:
    """Thresholds for cascading failure detection."""
    accept_reject_ratio_critical: float = 0.5
    accept_reject_ratio_warning: float = 0.7
    queue_wait_critical_ms: float = 5000
    queue_wait_warning_ms: float = 1000
    error_rate_critical: float = 0.25
    error_rate_warning: float = 0.10
    cpu_critical: float = 90
    memory_critical: float = 90
    gc_pause_critical_ms: float = 500
    connection_pool_critical: float = 0.9
    
    def to_dict(self) -> dict:
        return {
            "accept_reject_ratio_critical": self.accept_reject_ratio_critical,
            "accept_reject_ratio_warning": self.accept_reject_ratio_warning,
            "queue_wait_critical_ms": self.queue_wait_critical_ms,
            "queue_wait_warning_ms": self.queue_wait_warning_ms,
            "error_rate_critical": self.error_rate_critical,
            "error_rate_warning": self.error_rate_warning,
            "cpu_critical": self.cpu_critical,
            "memory_critical": self.memory_critical,
            "gc_pause_critical_ms": self.gc_pause_critical_ms,
            "connection_pool_critical": self.connection_pool_critical,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "CascadeThresholds":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class RecoveryDefaults:
    """Default settings for recovery planning."""
    initial_load_reduction: float = 0.3     # Start at 30% of normal
    stabilization_minutes: float = 5        # Wait time for stabilization
    load_increment: float = 0.1             # Increase 10% at a time
    increment_wait_minutes: float = 2       # Wait between increments
    safe_headroom: float = 0.2              # Keep 20% headroom
    
    def to_dict(self) -> dict:
        return {
            "initial_load_reduction": self.initial_load_reduction,
            "stabilization_minutes": self.stabilization_minutes,
            "load_increment": self.load_increment,
            "increment_wait_minutes": self.increment_wait_minutes,
            "safe_headroom": self.safe_headroom,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "RecoveryDefaults":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class SLOConfig:
    """
    Complete SLO configuration for AutoSRE.
    
    Can be loaded from YAML:
        config = SLOConfig.from_yaml("slo-config.yaml")
    
    Or JSON:
        config = SLOConfig.from_json("slo-config.json")
    """
    # SLO definitions
    slos: list[SLODefinition] = field(default_factory=list)
    
    # Default SLOs by service type
    default_slos: dict[str, float] = field(default_factory=lambda: {
        "api": 0.999,
        "web": 0.995,
        "batch": 0.99,
        "internal": 0.999,
        "critical": 0.9999,
    })
    
    # Cascading failure thresholds
    cascade_thresholds: CascadeThresholds = field(default_factory=CascadeThresholds)
    
    # Recovery defaults
    recovery_defaults: RecoveryDefaults = field(default_factory=RecoveryDefaults)
    
    # Global settings
    prometheus_url: str = ""
    default_window_days: int = 30
    
    def to_dict(self) -> dict:
        return {
            "slos": [s.to_dict() for s in self.slos],
            "default_slos": self.default_slos,
            "cascade_thresholds": self.cascade_thresholds.to_dict(),
            "recovery_defaults": self.recovery_defaults.to_dict(),
            "prometheus_url": self.prometheus_url,
            "default_window_days": self.default_window_days,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SLOConfig":
        """Create SLOConfig from dictionary."""
        slos = [SLODefinition.from_dict(s) for s in data.get("slos", [])]
        
        cascade_thresholds = CascadeThresholds.from_dict(
            data.get("cascade_thresholds", {})
        )
        
        recovery_defaults = RecoveryDefaults.from_dict(
            data.get("recovery_defaults", {})
        )
        
        return cls(
            slos=slos,
            default_slos=data.get("default_slos", cls.__dataclass_fields__["default_slos"].default_factory()),
            cascade_thresholds=cascade_thresholds,
            recovery_defaults=recovery_defaults,
            prometheus_url=data.get("prometheus_url", ""),
            default_window_days=data.get("default_window_days", 30),
        )
    
    @classmethod
    def from_yaml(cls, path: str) -> "SLOConfig":
        """Load configuration from YAML file."""
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)
    
    @classmethod
    def from_json(cls, path: str) -> "SLOConfig":
        """Load configuration from JSON file."""
        with open(path, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)
    
    def to_yaml(self, path: str) -> None:
        """Save configuration to YAML file."""
        with open(path, 'w') as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False)
    
    def to_json(self, path: str) -> None:
        """Save configuration to JSON file."""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    def get_slo(self, service: str) -> Optional[SLODefinition]:
        """Get SLO definition for a service."""
        for slo in self.slos:
            if slo.service == service:
                return slo
        return None
    
    def get_default_slo(self, service_type: str) -> float:
        """Get default SLO for a service type."""
        return self.default_slos.get(service_type, 0.999)


# Example configuration YAML
EXAMPLE_CONFIG_YAML = """
# SLO Configuration for AutoSRE
prometheus_url: http://prometheus:9090
default_window_days: 30

# Default SLOs by service type
default_slos:
  api: 0.999        # 99.9% - ~43 min/month downtime
  web: 0.995        # 99.5% - ~3.6 hours/month
  batch: 0.99       # 99% - ~7.3 hours/month
  internal: 0.999
  critical: 0.9999  # 99.99% - ~4.3 min/month

# Service-specific SLO definitions
slos:
  - name: api-gateway-availability
    service: api-gateway
    slo_type: availability
    target: 0.999
    window_days: 30
    description: API Gateway must maintain 99.9% request success rate
    owner: platform-team
    tier: critical
    block_deploys_below: 20
    prometheus_good_query: |
      sum(rate(http_requests_total{service="api-gateway",status=~"2.."}[5m]))
    prometheus_total_query: |
      sum(rate(http_requests_total{service="api-gateway"}[5m]))
    alerts:
      - severity: warning
        burn_rate_threshold: 1.5
        short_window: 5m
        long_window: 1h
      - severity: critical
        burn_rate_threshold: 3.0
        short_window: 5m
        long_window: 30m
    labels:
      team: platform
      env: production

  - name: api-gateway-latency
    service: api-gateway
    slo_type: latency
    target: 0.99
    window_days: 30
    description: 99% of requests should complete under 200ms
    owner: platform-team
    tier: critical
    latency_target:
      percentile: 99
      threshold_ms: 200
    prometheus_good_query: |
      sum(rate(http_request_duration_seconds_bucket{service="api-gateway",le="0.2"}[5m]))
    prometheus_total_query: |
      sum(rate(http_request_duration_seconds_count{service="api-gateway"}[5m]))

  - name: payment-service-availability
    service: payment-service
    slo_type: availability
    target: 0.9999
    window_days: 30
    description: Payment service requires 99.99% availability
    owner: payments-team
    tier: critical
    block_deploys_below: 30
    labels:
      team: payments
      compliance: pci

# Cascading failure detection thresholds
cascade_thresholds:
  accept_reject_ratio_critical: 0.5
  accept_reject_ratio_warning: 0.7
  queue_wait_critical_ms: 5000
  queue_wait_warning_ms: 1000
  error_rate_critical: 0.25
  error_rate_warning: 0.10
  cpu_critical: 90
  memory_critical: 90
  gc_pause_critical_ms: 500
  connection_pool_critical: 0.9

# Recovery planning defaults
recovery_defaults:
  initial_load_reduction: 0.3     # Start recovery at 30% load
  stabilization_minutes: 5        # Wait 5 min for stabilization
  load_increment: 0.1             # Increase 10% at a time
  increment_wait_minutes: 2       # Wait 2 min between increments
  safe_headroom: 0.2              # Keep 20% headroom
"""


def generate_example_config(path: str = "slo-config.yaml") -> None:
    """Generate an example configuration file."""
    with open(path, 'w') as f:
        f.write(EXAMPLE_CONFIG_YAML)
