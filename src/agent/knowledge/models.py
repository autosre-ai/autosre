"""
Graph data models for the knowledge graph.

Represents services, dependencies, infrastructure, and their relationships.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class DependencyType(str, Enum):
    """Types of service dependencies."""
    
    SYNC = "sync"           # Synchronous HTTP/gRPC calls
    ASYNC = "async"         # Async message passing
    DATABASE = "database"   # Database connections
    CACHE = "cache"         # Cache dependencies
    QUEUE = "queue"         # Message queue
    STREAM = "stream"       # Event streaming
    STORAGE = "storage"     # Object storage
    EXTERNAL = "external"   # External API


class ServiceStatus(str, Enum):
    """Service operational status."""
    
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    MAINTENANCE = "maintenance"


class HealthStatus(str, Enum):
    """Health check status."""
    
    PASSING = "passing"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class ServiceTier(str, Enum):
    """Service criticality tier."""
    
    TIER_0 = "tier_0"  # Mission critical
    TIER_1 = "tier_1"  # Business critical
    TIER_2 = "tier_2"  # Important
    TIER_3 = "tier_3"  # Standard
    TIER_4 = "tier_4"  # Non-critical


@dataclass
class BaseModel:
    """Base model with common fields."""
    
    id: str
    name: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for Neo4j storage."""
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "labels": self.labels,
            "annotations": self.annotations,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BaseModel:
        """Create from dictionary."""
        data = data.copy()
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if isinstance(data.get("updated_at"), str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)


@dataclass
class Service(BaseModel):
    """
    A service in the topology.
    
    Represents a microservice, API, or application component.
    """
    
    namespace: str = "default"
    version: str = ""
    tier: ServiceTier = ServiceTier.TIER_3
    status: ServiceStatus = ServiceStatus.UNKNOWN
    team: str = ""
    owner: str = ""
    repository: str = ""
    description: str = ""
    
    # Technical details
    language: str = ""
    framework: str = ""
    runtime: str = ""
    
    # SLOs
    slo_availability: float = 99.9
    slo_latency_p99_ms: int = 500
    
    # Endpoints
    endpoints: list[str] = field(default_factory=list)
    
    # Metrics
    replicas: int = 1
    cpu_request: str = ""
    memory_request: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update({
            "namespace": self.namespace,
            "version": self.version,
            "tier": self.tier.value,
            "status": self.status.value,
            "team": self.team,
            "owner": self.owner,
            "repository": self.repository,
            "description": self.description,
            "language": self.language,
            "framework": self.framework,
            "runtime": self.runtime,
            "slo_availability": self.slo_availability,
            "slo_latency_p99_ms": self.slo_latency_p99_ms,
            "endpoints": self.endpoints,
            "replicas": self.replicas,
            "cpu_request": self.cpu_request,
            "memory_request": self.memory_request,
        })
        return base


@dataclass
class Dependency:
    """
    A dependency relationship between services.
    
    Represents the edge in the service graph.
    """
    
    source_id: str
    target_id: str
    dependency_type: DependencyType = DependencyType.SYNC
    protocol: str = "http"
    port: int = 80
    path: str = ""
    
    # Traffic characteristics
    calls_per_minute: float = 0.0
    latency_p50_ms: float = 0.0
    latency_p99_ms: float = 0.0
    error_rate: float = 0.0
    
    # Criticality
    is_critical: bool = False
    has_fallback: bool = False
    timeout_ms: int = 30000
    retry_count: int = 3
    circuit_breaker: bool = False
    
    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "dependency_type": self.dependency_type.value,
            "protocol": self.protocol,
            "port": self.port,
            "path": self.path,
            "calls_per_minute": self.calls_per_minute,
            "latency_p50_ms": self.latency_p50_ms,
            "latency_p99_ms": self.latency_p99_ms,
            "error_rate": self.error_rate,
            "is_critical": self.is_critical,
            "has_fallback": self.has_fallback,
            "timeout_ms": self.timeout_ms,
            "retry_count": self.retry_count,
            "circuit_breaker": self.circuit_breaker,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Endpoint:
    """
    An API endpoint exposed by a service.
    """
    
    id: str
    service_id: str
    method: str = "GET"
    path: str = "/"
    protocol: str = "http"
    port: int = 80
    
    # Performance
    latency_p50_ms: float = 0.0
    latency_p99_ms: float = 0.0
    requests_per_minute: float = 0.0
    error_rate: float = 0.0
    
    # Documentation
    description: str = ""
    deprecated: bool = False
    authentication: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "service_id": self.service_id,
            "method": self.method,
            "path": self.path,
            "protocol": self.protocol,
            "port": self.port,
            "latency_p50_ms": self.latency_p50_ms,
            "latency_p99_ms": self.latency_p99_ms,
            "requests_per_minute": self.requests_per_minute,
            "error_rate": self.error_rate,
            "description": self.description,
            "deprecated": self.deprecated,
            "authentication": self.authentication,
        }


@dataclass
class Namespace(BaseModel):
    """
    Kubernetes namespace or logical grouping.
    """
    
    environment: str = "production"
    cluster: str = ""
    resource_quota_cpu: str = ""
    resource_quota_memory: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update({
            "environment": self.environment,
            "cluster": self.cluster,
            "resource_quota_cpu": self.resource_quota_cpu,
            "resource_quota_memory": self.resource_quota_memory,
        })
        return base


@dataclass
class Pod:
    """
    A Kubernetes pod.
    """
    
    id: str
    name: str
    service_id: str
    namespace: str
    node_id: str
    
    status: str = "Running"
    phase: str = "Running"
    ip: str = ""
    
    # Resources
    cpu_request: str = ""
    cpu_limit: str = ""
    memory_request: str = ""
    memory_limit: str = ""
    
    # Health
    restart_count: int = 0
    ready: bool = True
    
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "service_id": self.service_id,
            "namespace": self.namespace,
            "node_id": self.node_id,
            "status": self.status,
            "phase": self.phase,
            "ip": self.ip,
            "cpu_request": self.cpu_request,
            "cpu_limit": self.cpu_limit,
            "memory_request": self.memory_request,
            "memory_limit": self.memory_limit,
            "restart_count": self.restart_count,
            "ready": self.ready,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Node(BaseModel):
    """
    A Kubernetes node.
    """
    
    cluster: str = ""
    zone: str = ""
    region: str = ""
    instance_type: str = ""
    
    # Resources
    cpu_capacity: str = ""
    memory_capacity: str = ""
    cpu_allocatable: str = ""
    memory_allocatable: str = ""
    
    # Status
    ready: bool = True
    schedulable: bool = True
    
    # Provider
    provider: str = ""  # aws, gcp, azure
    provider_id: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update({
            "cluster": self.cluster,
            "zone": self.zone,
            "region": self.region,
            "instance_type": self.instance_type,
            "cpu_capacity": self.cpu_capacity,
            "memory_capacity": self.memory_capacity,
            "cpu_allocatable": self.cpu_allocatable,
            "memory_allocatable": self.memory_allocatable,
            "ready": self.ready,
            "schedulable": self.schedulable,
            "provider": self.provider,
            "provider_id": self.provider_id,
        })
        return base


@dataclass
class Database(BaseModel):
    """
    A database resource.
    """
    
    engine: str = "postgresql"  # postgresql, mysql, mongodb, redis, etc.
    version: str = ""
    host: str = ""
    port: int = 5432
    
    # Cluster info
    cluster_name: str = ""
    is_primary: bool = True
    replicas: int = 0
    
    # Performance
    max_connections: int = 100
    current_connections: int = 0
    
    # Size
    storage_gb: int = 0
    storage_used_gb: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update({
            "engine": self.engine,
            "version": self.version,
            "host": self.host,
            "port": self.port,
            "cluster_name": self.cluster_name,
            "is_primary": self.is_primary,
            "replicas": self.replicas,
            "max_connections": self.max_connections,
            "current_connections": self.current_connections,
            "storage_gb": self.storage_gb,
            "storage_used_gb": self.storage_used_gb,
        })
        return base


@dataclass
class Cache(BaseModel):
    """
    A cache resource (Redis, Memcached, etc.).
    """
    
    engine: str = "redis"
    version: str = ""
    host: str = ""
    port: int = 6379
    
    # Cluster info
    cluster_mode: bool = False
    node_count: int = 1
    
    # Performance
    memory_mb: int = 0
    memory_used_mb: float = 0.0
    hit_rate: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update({
            "engine": self.engine,
            "version": self.version,
            "host": self.host,
            "port": self.port,
            "cluster_mode": self.cluster_mode,
            "node_count": self.node_count,
            "memory_mb": self.memory_mb,
            "memory_used_mb": self.memory_used_mb,
            "hit_rate": self.hit_rate,
        })
        return base


@dataclass
class MessageQueue(BaseModel):
    """
    A message queue resource (Kafka, RabbitMQ, SQS, etc.).
    """
    
    engine: str = "kafka"
    version: str = ""
    
    # Connection
    brokers: list[str] = field(default_factory=list)
    
    # Topics
    topic_count: int = 0
    partition_count: int = 0
    
    # Performance
    messages_per_second: float = 0.0
    consumer_lag: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update({
            "engine": self.engine,
            "version": self.version,
            "brokers": self.brokers,
            "topic_count": self.topic_count,
            "partition_count": self.partition_count,
            "messages_per_second": self.messages_per_second,
            "consumer_lag": self.consumer_lag,
        })
        return base


@dataclass
class LoadBalancer(BaseModel):
    """
    A load balancer resource.
    """
    
    lb_type: str = "application"  # application, network, classic
    scheme: str = "internet-facing"  # internet-facing, internal
    
    # Network
    dns_name: str = ""
    ip_addresses: list[str] = field(default_factory=list)
    
    # Health
    healthy_hosts: int = 0
    unhealthy_hosts: int = 0
    
    # Traffic
    requests_per_second: float = 0.0
    active_connections: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update({
            "lb_type": self.lb_type,
            "scheme": self.scheme,
            "dns_name": self.dns_name,
            "ip_addresses": self.ip_addresses,
            "healthy_hosts": self.healthy_hosts,
            "unhealthy_hosts": self.unhealthy_hosts,
            "requests_per_second": self.requests_per_second,
            "active_connections": self.active_connections,
        })
        return base


@dataclass
class Alert:
    """
    An active or historical alert.
    """
    
    id: str
    service_id: str
    severity: str = "warning"  # critical, warning, info
    title: str = ""
    description: str = ""
    
    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None
    
    # Status
    status: str = "firing"  # firing, resolved, acknowledged
    acknowledged_by: str = ""
    
    # Source
    source: str = ""  # prometheus, datadog, pagerduty, etc.
    runbook_url: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "service_id": self.service_id,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "started_at": self.started_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "status": self.status,
            "acknowledged_by": self.acknowledged_by,
            "source": self.source,
            "runbook_url": self.runbook_url,
        }


@dataclass
class Incident:
    """
    An incident affecting services.
    """
    
    id: str
    title: str
    description: str = ""
    severity: str = "sev3"  # sev1, sev2, sev3, sev4
    
    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    detected_at: datetime | None = None
    mitigated_at: datetime | None = None
    resolved_at: datetime | None = None
    
    # Status
    status: str = "investigating"  # investigating, identified, monitoring, resolved
    
    # People
    commander: str = ""
    responders: list[str] = field(default_factory=list)
    
    # Services affected
    affected_services: list[str] = field(default_factory=list)
    
    # Impact
    customer_impact: str = ""
    revenue_impact: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "started_at": self.started_at.isoformat(),
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
            "mitigated_at": self.mitigated_at.isoformat() if self.mitigated_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "status": self.status,
            "commander": self.commander,
            "responders": self.responders,
            "affected_services": self.affected_services,
            "customer_impact": self.customer_impact,
            "revenue_impact": self.revenue_impact,
        }
