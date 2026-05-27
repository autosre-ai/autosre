"""
Istio Service Mesh Client

Provides comprehensive Istio service mesh integration:
- VirtualService and DestinationRule management
- Traffic management and routing
- mTLS and security policies
- Observability and telemetry
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Configuration
# =============================================================================


class IstioConfig(BaseModel):
    """Configuration for Istio client."""
    
    namespace: str = Field(default="istio-system", description="Istio control plane namespace")
    kubeconfig: Optional[str] = Field(default=None, description="Path to kubeconfig file")
    context: Optional[str] = Field(default=None, description="Kubernetes context to use")
    timeout_seconds: int = Field(default=30, description="API timeout in seconds")
    
    # Telemetry
    prometheus_url: Optional[str] = Field(default=None, description="Prometheus URL for metrics")
    jaeger_url: Optional[str] = Field(default=None, description="Jaeger URL for tracing")
    kiali_url: Optional[str] = Field(default=None, description="Kiali URL for visualization")


# =============================================================================
# Core Resource Models
# =============================================================================


class StringMatch(BaseModel):
    """String match condition for routing."""
    
    exact: Optional[str] = None
    prefix: Optional[str] = None
    regex: Optional[str] = None


class HTTPMatchRequest(BaseModel):
    """HTTP match request for routing rules."""
    
    name: Optional[str] = None
    uri: Optional[StringMatch] = None
    headers: dict[str, StringMatch] = Field(default_factory=dict)
    query_params: dict[str, StringMatch] = Field(default_factory=dict)
    method: Optional[StringMatch] = None
    port: Optional[int] = None
    source_labels: dict[str, str] = Field(default_factory=dict)


class HTTPRouteDestination(BaseModel):
    """Destination for HTTP routing."""
    
    host: str
    port: Optional[int] = None
    subset: Optional[str] = None
    weight: int = 100


class HTTPRetry(BaseModel):
    """Retry policy for HTTP routes."""
    
    attempts: int = 3
    per_try_timeout: str = "2s"
    retry_on: str = "5xx,reset,connect-failure,retriable-4xx"


class HTTPFaultInjection(BaseModel):
    """Fault injection configuration."""
    
    delay_percentage: float = 0.0
    delay_duration: str = "0s"
    abort_percentage: float = 0.0
    abort_http_status: int = 503


class HTTPRedirect(BaseModel):
    """HTTP redirect configuration."""
    
    uri: Optional[str] = None
    authority: Optional[str] = None
    redirect_code: int = 301


class HTTPRewrite(BaseModel):
    """HTTP rewrite configuration."""
    
    uri: Optional[str] = None
    authority: Optional[str] = None


class HTTPRoute(BaseModel):
    """HTTP route specification."""
    
    name: Optional[str] = None
    match: list[HTTPMatchRequest] = Field(default_factory=list)
    route: list[HTTPRouteDestination] = Field(default_factory=list)
    redirect: Optional[HTTPRedirect] = None
    rewrite: Optional[HTTPRewrite] = None
    timeout: str = "15s"
    retries: Optional[HTTPRetry] = None
    fault: Optional[HTTPFaultInjection] = None
    mirror: Optional[HTTPRouteDestination] = None
    mirror_percentage: float = 100.0
    headers: dict[str, dict[str, str]] = Field(default_factory=dict)


# =============================================================================
# VirtualService
# =============================================================================


class VirtualServiceSpec(BaseModel):
    """VirtualService specification."""
    
    hosts: list[str] = Field(default_factory=list)
    gateways: list[str] = Field(default_factory=list)
    http: list[HTTPRoute] = Field(default_factory=list)
    tls: list[dict[str, Any]] = Field(default_factory=list)
    tcp: list[dict[str, Any]] = Field(default_factory=list)
    export_to: list[str] = Field(default_factory=list)


@dataclass
class VirtualService:
    """Istio VirtualService resource."""
    
    name: str
    namespace: str
    spec: VirtualServiceSpec
    
    # Metadata
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to Kubernetes resource dict."""
        return {
            "apiVersion": "networking.istio.io/v1beta1",
            "kind": "VirtualService",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "labels": self.labels,
                "annotations": self.annotations,
            },
            "spec": self.spec.model_dump(exclude_none=True),
        }


# =============================================================================
# DestinationRule
# =============================================================================


class ConnectionPoolSettings(BaseModel):
    """Connection pool settings for load balancing."""
    
    # TCP settings
    tcp_max_connections: int = 1000
    tcp_connect_timeout: str = "10s"
    
    # HTTP settings
    http1_max_pending_requests: int = 1024
    http2_max_requests: int = 1024
    max_requests_per_connection: int = 0
    max_retries: int = 3
    idle_timeout: str = "1h"


class OutlierDetection(BaseModel):
    """Outlier detection for circuit breaking."""
    
    consecutive_errors: int = 5
    interval: str = "10s"
    base_ejection_time: str = "30s"
    max_ejection_percent: int = 100
    min_health_percent: int = 0
    consecutive_gateway_errors: int = 5
    consecutive_5xx_errors: int = 5


class LoadBalancerSettings(BaseModel):
    """Load balancer settings."""
    
    simple: str = "ROUND_ROBIN"  # ROUND_ROBIN, LEAST_CONN, RANDOM, PASSTHROUGH
    consistent_hash: Optional[dict[str, Any]] = None
    locality_lb_setting: Optional[dict[str, Any]] = None
    warmup_duration: str = "0s"


class TLSSettings(BaseModel):
    """TLS settings for connections."""
    
    mode: str = "ISTIO_MUTUAL"  # DISABLE, SIMPLE, MUTUAL, ISTIO_MUTUAL
    client_certificate: Optional[str] = None
    private_key: Optional[str] = None
    ca_certificates: Optional[str] = None
    sni: Optional[str] = None
    insecure_skip_verify: bool = False


class PortSelector(BaseModel):
    """Port selector for traffic policies."""
    
    number: int


class TrafficPolicy(BaseModel):
    """Traffic policy for destination rules."""
    
    connection_pool: Optional[ConnectionPoolSettings] = None
    load_balancer: Optional[LoadBalancerSettings] = None
    outlier_detection: Optional[OutlierDetection] = None
    tls: Optional[TLSSettings] = None
    port_level_settings: list[dict[str, Any]] = Field(default_factory=list)


class Subset(BaseModel):
    """Subset definition for routing."""
    
    name: str
    labels: dict[str, str] = Field(default_factory=dict)
    traffic_policy: Optional[TrafficPolicy] = None


class DestinationRuleSpec(BaseModel):
    """DestinationRule specification."""
    
    host: str
    traffic_policy: Optional[TrafficPolicy] = None
    subsets: list[Subset] = Field(default_factory=list)
    export_to: list[str] = Field(default_factory=list)


@dataclass
class DestinationRule:
    """Istio DestinationRule resource."""
    
    name: str
    namespace: str
    spec: DestinationRuleSpec
    
    # Metadata
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to Kubernetes resource dict."""
        return {
            "apiVersion": "networking.istio.io/v1beta1",
            "kind": "DestinationRule",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "labels": self.labels,
                "annotations": self.annotations,
            },
            "spec": self.spec.model_dump(exclude_none=True),
        }


# =============================================================================
# Gateway
# =============================================================================


class GatewaySpec(BaseModel):
    """Gateway specification."""
    
    selector: dict[str, str] = Field(default_factory=dict)
    servers: list[dict[str, Any]] = Field(default_factory=list)


@dataclass
class Gateway:
    """Istio Gateway resource."""
    
    name: str
    namespace: str
    spec: GatewaySpec
    
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to Kubernetes resource dict."""
        return {
            "apiVersion": "networking.istio.io/v1beta1",
            "kind": "Gateway",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "labels": self.labels,
                "annotations": self.annotations,
            },
            "spec": self.spec.model_dump(exclude_none=True),
        }


# =============================================================================
# ServiceEntry
# =============================================================================


class ServiceEntrySpec(BaseModel):
    """ServiceEntry specification for external services."""
    
    hosts: list[str] = Field(default_factory=list)
    addresses: list[str] = Field(default_factory=list)
    ports: list[dict[str, Any]] = Field(default_factory=list)
    location: str = "MESH_EXTERNAL"  # MESH_INTERNAL, MESH_EXTERNAL
    resolution: str = "DNS"  # NONE, STATIC, DNS, DNS_ROUND_ROBIN
    endpoints: list[dict[str, Any]] = Field(default_factory=list)
    export_to: list[str] = Field(default_factory=list)


@dataclass
class ServiceEntry:
    """Istio ServiceEntry resource."""
    
    name: str
    namespace: str
    spec: ServiceEntrySpec
    
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)


# =============================================================================
# Sidecar
# =============================================================================


class SidecarSpec(BaseModel):
    """Sidecar specification."""
    
    workload_selector: Optional[dict[str, str]] = None
    ingress: list[dict[str, Any]] = Field(default_factory=list)
    egress: list[dict[str, Any]] = Field(default_factory=list)
    outbound_traffic_policy: dict[str, str] = Field(default_factory=dict)


@dataclass
class Sidecar:
    """Istio Sidecar resource."""
    
    name: str
    namespace: str
    spec: SidecarSpec
    
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)


# =============================================================================
# Security Resources
# =============================================================================


class WorkloadSelector(BaseModel):
    """Workload selector for security policies."""
    
    match_labels: dict[str, str] = Field(default_factory=dict)


class AuthorizationPolicySpec(BaseModel):
    """AuthorizationPolicy specification."""
    
    selector: Optional[WorkloadSelector] = None
    action: str = "ALLOW"  # ALLOW, DENY, AUDIT, CUSTOM
    rules: list[dict[str, Any]] = Field(default_factory=list)
    provider: Optional[dict[str, str]] = None


@dataclass
class AuthorizationPolicy:
    """Istio AuthorizationPolicy resource."""
    
    name: str
    namespace: str
    spec: AuthorizationPolicySpec
    
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to Kubernetes resource dict."""
        return {
            "apiVersion": "security.istio.io/v1beta1",
            "kind": "AuthorizationPolicy",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "labels": self.labels,
                "annotations": self.annotations,
            },
            "spec": self.spec.model_dump(exclude_none=True),
        }


class PeerAuthenticationSpec(BaseModel):
    """PeerAuthentication specification for mTLS."""
    
    selector: Optional[WorkloadSelector] = None
    mtls: dict[str, str] = Field(default_factory=lambda: {"mode": "STRICT"})
    port_level_mtls: dict[int, dict[str, str]] = Field(default_factory=dict)


@dataclass
class PeerAuthentication:
    """Istio PeerAuthentication resource."""
    
    name: str
    namespace: str
    spec: PeerAuthenticationSpec
    
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)


class RequestAuthenticationSpec(BaseModel):
    """RequestAuthentication specification for JWT."""
    
    selector: Optional[WorkloadSelector] = None
    jwt_rules: list[dict[str, Any]] = Field(default_factory=list)


@dataclass
class RequestAuthentication:
    """Istio RequestAuthentication resource."""
    
    name: str
    namespace: str
    spec: RequestAuthenticationSpec
    
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)


# =============================================================================
# EnvoyFilter
# =============================================================================


class EnvoyFilterSpec(BaseModel):
    """EnvoyFilter specification."""
    
    workload_selector: Optional[dict[str, Any]] = None
    config_patches: list[dict[str, Any]] = Field(default_factory=list)
    priority: int = 0


@dataclass
class EnvoyFilter:
    """Istio EnvoyFilter resource."""
    
    name: str
    namespace: str
    spec: EnvoyFilterSpec
    
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)


# =============================================================================
# WorkloadEntry / WorkloadGroup
# =============================================================================


@dataclass
class WorkloadEntry:
    """Istio WorkloadEntry for non-K8s workloads."""
    
    name: str
    namespace: str
    address: str
    labels: dict[str, str] = field(default_factory=dict)
    ports: dict[str, int] = field(default_factory=dict)
    service_account: Optional[str] = None
    network: Optional[str] = None
    locality: Optional[str] = None


@dataclass
class WorkloadGroup:
    """Istio WorkloadGroup for VM onboarding."""
    
    name: str
    namespace: str
    template: dict[str, Any] = field(default_factory=dict)
    probe: Optional[dict[str, Any]] = None


# =============================================================================
# IstioOperator
# =============================================================================


@dataclass
class IstioOperator:
    """Istio Operator resource for installation."""
    
    name: str
    namespace: str = "istio-system"
    profile: str = "default"  # minimal, default, demo, preview
    components: dict[str, Any] = field(default_factory=dict)
    mesh_config: dict[str, Any] = field(default_factory=dict)
    values: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Status Models
# =============================================================================


@dataclass
class IstiodStatus:
    """Status of istiod control plane."""
    
    ready: bool
    version: str
    replicas: int
    available_replicas: int
    
    # Health metrics
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    xds_pushes: int = 0
    xds_errors: int = 0


@dataclass
class IstioMeshStatus:
    """Overall mesh health status."""
    
    healthy: bool
    istiod_status: IstiodStatus
    proxy_count: int
    namespaces_with_injection: list[str] = field(default_factory=list)
    
    # Mesh-wide metrics
    total_requests_per_second: float = 0.0
    success_rate: float = 0.0
    p50_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0


# =============================================================================
# Istio Client
# =============================================================================


class IstioClient:
    """
    Client for Istio service mesh operations.
    
    Provides programmatic access to Istio resources including:
    - VirtualServices and DestinationRules
    - Gateways and ServiceEntries
    - Security policies (AuthorizationPolicy, PeerAuthentication)
    - Traffic management and fault injection
    
    Usage:
        client = IstioClient(config=IstioConfig())
        await client.connect()
        
        # Create a canary deployment
        vs = await client.create_virtual_service(
            name="my-service",
            namespace="production",
            spec=VirtualServiceSpec(
                hosts=["my-service"],
                http=[HTTPRoute(
                    route=[
                        HTTPRouteDestination(host="my-service", subset="stable", weight=90),
                        HTTPRouteDestination(host="my-service", subset="canary", weight=10),
                    ]
                )]
            )
        )
    """
    
    def __init__(self, config: Optional[IstioConfig] = None):
        """Initialize Istio client."""
        self.config = config or IstioConfig()
        self._k8s_client: Any = None
        self._connected = False
    
    async def connect(self) -> None:
        """Connect to Kubernetes cluster."""
        # In production, this would initialize the K8s client
        self._connected = True
    
    async def disconnect(self) -> None:
        """Disconnect from Kubernetes cluster."""
        self._connected = False
        self._k8s_client = None
    
    # -------------------------------------------------------------------------
    # VirtualService Operations
    # -------------------------------------------------------------------------
    
    async def create_virtual_service(
        self,
        name: str,
        namespace: str,
        spec: VirtualServiceSpec,
        labels: Optional[dict[str, str]] = None,
        annotations: Optional[dict[str, str]] = None,
    ) -> VirtualService:
        """Create a new VirtualService."""
        vs = VirtualService(
            name=name,
            namespace=namespace,
            spec=spec,
            labels=labels or {},
            annotations=annotations or {},
            created_at=datetime.now(timezone.utc),
        )
        # In production: apply to cluster via K8s API
        return vs
    
    async def get_virtual_service(
        self, name: str, namespace: str
    ) -> Optional[VirtualService]:
        """Get a VirtualService by name."""
        # In production: fetch from K8s API
        return None
    
    async def list_virtual_services(
        self, namespace: Optional[str] = None
    ) -> list[VirtualService]:
        """List all VirtualServices."""
        # In production: list from K8s API
        return []
    
    async def update_virtual_service(
        self, virtual_service: VirtualService
    ) -> VirtualService:
        """Update an existing VirtualService."""
        virtual_service.updated_at = datetime.now(timezone.utc)
        # In production: update via K8s API
        return virtual_service
    
    async def delete_virtual_service(self, name: str, namespace: str) -> bool:
        """Delete a VirtualService."""
        # In production: delete via K8s API
        return True
    
    # -------------------------------------------------------------------------
    # DestinationRule Operations
    # -------------------------------------------------------------------------
    
    async def create_destination_rule(
        self,
        name: str,
        namespace: str,
        spec: DestinationRuleSpec,
        labels: Optional[dict[str, str]] = None,
        annotations: Optional[dict[str, str]] = None,
    ) -> DestinationRule:
        """Create a new DestinationRule."""
        dr = DestinationRule(
            name=name,
            namespace=namespace,
            spec=spec,
            labels=labels or {},
            annotations=annotations or {},
            created_at=datetime.now(timezone.utc),
        )
        # In production: apply to cluster via K8s API
        return dr
    
    async def get_destination_rule(
        self, name: str, namespace: str
    ) -> Optional[DestinationRule]:
        """Get a DestinationRule by name."""
        return None
    
    async def list_destination_rules(
        self, namespace: Optional[str] = None
    ) -> list[DestinationRule]:
        """List all DestinationRules."""
        return []
    
    async def update_destination_rule(
        self, destination_rule: DestinationRule
    ) -> DestinationRule:
        """Update an existing DestinationRule."""
        destination_rule.updated_at = datetime.now(timezone.utc)
        return destination_rule
    
    async def delete_destination_rule(self, name: str, namespace: str) -> bool:
        """Delete a DestinationRule."""
        return True
    
    # -------------------------------------------------------------------------
    # Traffic Management Operations
    # -------------------------------------------------------------------------
    
    async def set_traffic_weight(
        self,
        service_name: str,
        namespace: str,
        weights: dict[str, int],
    ) -> VirtualService:
        """
        Set traffic weights for service subsets.
        
        Args:
            service_name: Name of the service
            namespace: Namespace of the service
            weights: Dict mapping subset names to weights (must sum to 100)
        
        Returns:
            Updated VirtualService
        """
        routes = [
            HTTPRouteDestination(
                host=service_name,
                subset=subset,
                weight=weight,
            )
            for subset, weight in weights.items()
        ]
        
        spec = VirtualServiceSpec(
            hosts=[service_name],
            http=[HTTPRoute(route=routes)],
        )
        
        return await self.create_virtual_service(
            name=service_name,
            namespace=namespace,
            spec=spec,
        )
    
    async def inject_fault(
        self,
        service_name: str,
        namespace: str,
        delay_percentage: float = 0.0,
        delay_duration: str = "0s",
        abort_percentage: float = 0.0,
        abort_code: int = 503,
    ) -> VirtualService:
        """
        Inject faults into service traffic for testing.
        
        Args:
            service_name: Target service
            namespace: Target namespace
            delay_percentage: Percentage of requests to delay
            delay_duration: Duration of delays (e.g., "5s")
            abort_percentage: Percentage of requests to abort
            abort_code: HTTP status code for aborted requests
        """
        spec = VirtualServiceSpec(
            hosts=[service_name],
            http=[
                HTTPRoute(
                    route=[HTTPRouteDestination(host=service_name)],
                    fault=HTTPFaultInjection(
                        delay_percentage=delay_percentage,
                        delay_duration=delay_duration,
                        abort_percentage=abort_percentage,
                        abort_http_status=abort_code,
                    ),
                )
            ],
        )
        
        return await self.create_virtual_service(
            name=f"{service_name}-fault",
            namespace=namespace,
            spec=spec,
        )
    
    async def mirror_traffic(
        self,
        service_name: str,
        namespace: str,
        mirror_host: str,
        mirror_percentage: float = 100.0,
    ) -> VirtualService:
        """
        Mirror traffic to another service for shadow testing.
        
        Args:
            service_name: Source service
            namespace: Namespace
            mirror_host: Destination to mirror traffic to
            mirror_percentage: Percentage of traffic to mirror
        """
        spec = VirtualServiceSpec(
            hosts=[service_name],
            http=[
                HTTPRoute(
                    route=[HTTPRouteDestination(host=service_name)],
                    mirror=HTTPRouteDestination(host=mirror_host),
                    mirror_percentage=mirror_percentage,
                )
            ],
        )
        
        return await self.create_virtual_service(
            name=f"{service_name}-mirror",
            namespace=namespace,
            spec=spec,
        )
    
    # -------------------------------------------------------------------------
    # Security Operations
    # -------------------------------------------------------------------------
    
    async def enable_mtls(
        self,
        namespace: str,
        mode: str = "STRICT",
        workload_selector: Optional[dict[str, str]] = None,
    ) -> PeerAuthentication:
        """
        Enable mTLS for a namespace or workload.
        
        Args:
            namespace: Target namespace
            mode: mTLS mode (STRICT, PERMISSIVE, DISABLE)
            workload_selector: Optional selector for specific workloads
        """
        spec = PeerAuthenticationSpec(
            selector=WorkloadSelector(match_labels=workload_selector) if workload_selector else None,
            mtls={"mode": mode},
        )
        
        return PeerAuthentication(
            name=f"{namespace}-mtls" if not workload_selector else "workload-mtls",
            namespace=namespace,
            spec=spec,
        )
    
    async def create_authorization_policy(
        self,
        name: str,
        namespace: str,
        action: str = "ALLOW",
        rules: Optional[list[dict[str, Any]]] = None,
        workload_selector: Optional[dict[str, str]] = None,
    ) -> AuthorizationPolicy:
        """
        Create an authorization policy.
        
        Args:
            name: Policy name
            namespace: Target namespace
            action: Action (ALLOW, DENY, AUDIT)
            rules: Authorization rules
            workload_selector: Optional workload selector
        """
        spec = AuthorizationPolicySpec(
            selector=WorkloadSelector(match_labels=workload_selector) if workload_selector else None,
            action=action,
            rules=rules or [],
        )
        
        return AuthorizationPolicy(
            name=name,
            namespace=namespace,
            spec=spec,
        )
    
    # -------------------------------------------------------------------------
    # Mesh Status Operations
    # -------------------------------------------------------------------------
    
    async def get_mesh_status(self) -> IstioMeshStatus:
        """Get overall mesh health status."""
        istiod = await self.get_istiod_status()
        
        return IstioMeshStatus(
            healthy=istiod.ready,
            istiod_status=istiod,
            proxy_count=0,  # In production: count from proxies
            namespaces_with_injection=[],
        )
    
    async def get_istiod_status(self) -> IstiodStatus:
        """Get istiod control plane status."""
        # In production: query istiod deployment status
        return IstiodStatus(
            ready=True,
            version="1.20.0",
            replicas=3,
            available_replicas=3,
        )
    
    async def get_proxy_status(
        self, namespace: Optional[str] = None
    ) -> dict[str, Any]:
        """Get sidecar proxy status across the mesh."""
        # In production: aggregate proxy status
        return {
            "total_proxies": 0,
            "synced": 0,
            "not_synced": 0,
            "by_namespace": {},
        }
    
    # -------------------------------------------------------------------------
    # Convenience Methods
    # -------------------------------------------------------------------------
    
    async def configure_circuit_breaker(
        self,
        service_name: str,
        namespace: str,
        max_connections: int = 100,
        max_pending_requests: int = 100,
        max_requests: int = 100,
        consecutive_errors: int = 5,
        ejection_time: str = "30s",
    ) -> DestinationRule:
        """
        Configure circuit breaker for a service.
        
        Args:
            service_name: Target service
            namespace: Target namespace
            max_connections: Maximum TCP connections
            max_pending_requests: Maximum pending HTTP requests
            max_requests: Maximum HTTP requests
            consecutive_errors: Errors before ejection
            ejection_time: How long to eject unhealthy hosts
        """
        spec = DestinationRuleSpec(
            host=service_name,
            traffic_policy=TrafficPolicy(
                connection_pool=ConnectionPoolSettings(
                    tcp_max_connections=max_connections,
                    http1_max_pending_requests=max_pending_requests,
                    http2_max_requests=max_requests,
                ),
                outlier_detection=OutlierDetection(
                    consecutive_errors=consecutive_errors,
                    base_ejection_time=ejection_time,
                ),
            ),
        )
        
        return await self.create_destination_rule(
            name=f"{service_name}-circuit-breaker",
            namespace=namespace,
            spec=spec,
        )
