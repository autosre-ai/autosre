"""
SRE Agent - Data Models
"""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class Alert(BaseModel):
    id: str
    source: str
    severity: Severity
    service: str
    title: str
    description: str
    started_at: datetime
    labels: Dict[str, str] = {}


class MetricSnapshot(BaseModel):
    current: float
    baseline: float
    unit: str
    is_anomaly: bool = False
    
    @property
    def change_percent(self) -> float:
        if self.baseline == 0:
            return 100.0 if self.current > 0 else 0.0
        return ((self.current - self.baseline) / self.baseline) * 100


class PrometheusData(BaseModel):
    error_rate: MetricSnapshot
    request_rate: MetricSnapshot
    latency_p99: MetricSnapshot
    latency_p50: MetricSnapshot
    error_breakdown: Dict[str, int] = {}
    time_series: List[Dict[str, Any]] = []


class Deployment(BaseModel):
    sha: str
    short_sha: str
    author: str
    message: str
    deployed_at: datetime
    hours_ago: float
    files_changed: List[str] = []
    additions: int = 0
    deletions: int = 0


class GitHubData(BaseModel):
    recent_deployments: List[Deployment] = []
    open_prs: List[Dict[str, Any]] = []


class LogEntry(BaseModel):
    timestamp: datetime
    level: str
    message: str
    trace_id: Optional[str] = None
    count: int = 1


class LogPattern(BaseModel):
    pattern: str
    count: int
    percentage: float


class LogsData(BaseModel):
    error_samples: List[LogEntry] = []
    error_patterns: List[LogPattern] = []
    first_error_at: Optional[datetime] = None
    total_errors_last_5m: int = 0


class PodStatus(BaseModel):
    name: str
    status: str
    restarts: int
    cpu_usage: str
    cpu_limit: str
    memory_usage: str
    memory_limit: str
    ready: bool


class KubernetesData(BaseModel):
    pods: List[PodStatus] = []
    replica_count: Dict[str, int] = {}
    recent_events: List[Dict[str, Any]] = []
    resource_pressure: bool = False


class DependencyStatus(BaseModel):
    name: str
    status: HealthStatus
    latency_p99: float
    error_rate: float
    last_healthy: Optional[datetime] = None


class TrafficData(BaseModel):
    suspicious_ips: List[str] = []
    geo_distribution: Dict[str, int] = {}
    is_ddos: bool = False
    is_malicious: bool = False
    akamai_status: str = "unknown"


class IncidentContext(BaseModel):
    """Complete context gathered for an incident"""
    alert: Alert
    prometheus: Optional[PrometheusData] = None
    github: Optional[GitHubData] = None
    logs: Optional[LogsData] = None
    kubernetes: Optional[KubernetesData] = None
    traffic: Optional[TrafficData] = None
    dependencies: List[DependencyStatus] = []
    gathered_at: datetime = datetime.utcnow()


class RootCauseSignal(BaseModel):
    """A signal pointing to potential root cause"""
    source: str  # deployment, infrastructure, dependency, traffic, etc.
    description: str
    confidence: float  # 0.0 to 1.0
    evidence: List[str] = []
    is_likely_cause: bool = False


class RecommendedAction(BaseModel):
    """An action the SRE should take"""
    priority: int
    action: str
    runbook_link: Optional[str] = None
    command: Optional[str] = None


class SituationReport(BaseModel):
    """Final output of the SRE Agent"""
    alert: Alert
    summary: str
    impact: str
    duration_minutes: float
    affected_customers_estimate: Optional[int] = None
    
    root_cause_signals: List[RootCauseSignal] = []
    likely_root_cause: Optional[str] = None
    confidence: str  # LOW, MEDIUM, HIGH
    
    recommended_actions: List[RecommendedAction] = []
    runbooks: List[Dict[str, str]] = []
    
    raw_context: Optional[IncidentContext] = None
    analysis_reasoning: Optional[str] = None
    generated_at: datetime = datetime.utcnow()
