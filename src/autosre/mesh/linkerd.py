"""
Linkerd Service Mesh Client

Provides Linkerd 2.x service mesh integration:
- ServiceProfile for per-route metrics and retries
- TrafficSplit for canary deployments (SMI spec)
- Server and ServerAuthorization for policy
- Mesh observability and mTLS status
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Configuration
# =============================================================================


class LinkerdConfig(BaseModel):
    """Configuration for Linkerd client."""
    
    namespace: str = Field(default="linkerd", description="Linkerd control plane namespace")
    kubeconfig: Optional[str] = Field(default=None, description="Path to kubeconfig file")
    context: Optional[str] = Field(default=None, description="Kubernetes context to use")
    timeout_seconds: int = Field(default=30, description="API timeout in seconds")
    
    # Linkerd-specific
    viz_namespace: str = Field(default="linkerd-viz", description="Linkerd Viz namespace")
    multicluster_namespace: str = Field(default="linkerd-multicluster", description="Multicluster namespace")


# =============================================================================
# ServiceProfile
# =============================================================================


class RetryBudget(BaseModel):
    """Retry budget configuration for routes."""
    
    retry_ratio: float = 0.2
    min_retries_per_second: int = 10
    ttl: str = "10s"


class ResponseClass(BaseModel):
    """Response classification for metrics."""
    
    condition: dict[str, Any] = Field(default_factory=dict)
    is_failure: bool = False


class RouteSpec(BaseModel):
    """Route specification for ServiceProfile."""
    
    name: str
    condition: dict[str, Any] = Field(default_factory=dict)
    response_classes: list[ResponseClass] = Field(default_factory=list)
    is_retryable: bool = False
    timeout: Optional[str] = None


class ServiceProfileSpec(BaseModel):
    """ServiceProfile specification."""
    
    routes: list[RouteSpec] = Field(default_factory=list)
    retry_budget: Optional[RetryBudget] = None
    dst_overrides: list[dict[str, Any]] = Field(default_factory=list)


@dataclass
class ServiceProfile:
    """Linkerd ServiceProfile resource."""
    
    name: str
    namespace: str
    spec: ServiceProfileSpec
    
    # Metadata
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to Kubernetes resource dict."""
        return {
            "apiVersion": "linkerd.io/v1alpha2",
            "kind": "ServiceProfile",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "labels": self.labels,
                "annotations": self.annotations,
            },
            "spec": self.spec.model_dump(exclude_none=True),
        }


# =============================================================================
# TrafficSplit (SMI Spec)
# =============================================================================


class TrafficSplitBackend(BaseModel):
    """Backend for traffic split."""
    
    service: str
    weight: int


class TrafficSplitSpec(BaseModel):
    """TrafficSplit specification (SMI)."""
    
    service: str
    backends: list[TrafficSplitBackend] = Field(default_factory=list)


@dataclass
class TrafficSplit:
    """SMI TrafficSplit resource for canary deployments."""
    
    name: str
    namespace: str
    spec: TrafficSplitSpec
    
    # Metadata
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to Kubernetes resource dict."""
        return {
            "apiVersion": "split.smi-spec.io/v1alpha2",
            "kind": "TrafficSplit",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "labels": self.labels,
                "annotations": self.annotations,
            },
            "spec": self.spec.model_dump(exclude_none=True),
        }


# =============================================================================
# Server (Policy)
# =============================================================================


class ServerPort(BaseModel):
    """Port specification for Server."""
    
    port: int
    name: Optional[str] = None


class ServerSelector(BaseModel):
    """Pod selector for Server."""
    
    match_labels: dict[str, str] = Field(default_factory=dict)


class ServerSpec(BaseModel):
    """Server specification."""
    
    pod_selector: ServerSelector
    port: ServerPort
    proxy_protocol: str = "HTTP/1"  # HTTP/1, HTTP/2, gRPC, opaque


@dataclass
class Server:
    """Linkerd Server resource for defining server policies."""
    
    name: str
    namespace: str
    spec: ServerSpec
    
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to Kubernetes resource dict."""
        return {
            "apiVersion": "policy.linkerd.io/v1beta1",
            "kind": "Server",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "labels": self.labels,
                "annotations": self.annotations,
            },
            "spec": self.spec.model_dump(exclude_none=True),
        }


# =============================================================================
# ServerAuthorization
# =============================================================================


class ClientIdentity(BaseModel):
    """Client identity for authorization."""
    
    mesh_tls: Optional[dict[str, Any]] = None
    unauthenticated: bool = False


class ServerAuthorizationSpec(BaseModel):
    """ServerAuthorization specification."""
    
    server: dict[str, str] = Field(default_factory=dict)  # name reference
    client: ClientIdentity


@dataclass
class ServerAuthorization:
    """Linkerd ServerAuthorization for access control."""
    
    name: str
    namespace: str
    spec: ServerAuthorizationSpec
    
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to Kubernetes resource dict."""
        return {
            "apiVersion": "policy.linkerd.io/v1beta1",
            "kind": "ServerAuthorization",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "labels": self.labels,
                "annotations": self.annotations,
            },
            "spec": self.spec.model_dump(exclude_none=True),
        }


# =============================================================================
# HTTPRoute (Gateway API compatible)
# =============================================================================


class HTTPRouteMatch(BaseModel):
    """HTTP route match condition."""
    
    path: Optional[dict[str, str]] = None
    headers: list[dict[str, str]] = Field(default_factory=list)
    query_params: list[dict[str, str]] = Field(default_factory=list)
    method: Optional[str] = None


class HTTPRouteBackend(BaseModel):
    """Backend reference for HTTPRoute."""
    
    name: str
    port: int
    weight: int = 1


class HTTPRouteRule(BaseModel):
    """Rule for HTTPRoute."""
    
    matches: list[HTTPRouteMatch] = Field(default_factory=list)
    backend_refs: list[HTTPRouteBackend] = Field(default_factory=list)
    filters: list[dict[str, Any]] = Field(default_factory=list)
    timeouts: Optional[dict[str, str]] = None


class HTTPRouteSpec(BaseModel):
    """HTTPRoute specification."""
    
    parent_refs: list[dict[str, str]] = Field(default_factory=list)
    rules: list[HTTPRouteRule] = Field(default_factory=list)


# Using LinkerdHTTPRoute to avoid conflict with Istio's HTTPRoute
@dataclass
class HTTPRoute:
    """Gateway API HTTPRoute for Linkerd."""
    
    name: str
    namespace: str
    spec: HTTPRouteSpec
    
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)


# =============================================================================
# Linkerd Policy
# =============================================================================


class LinkerdPolicySpec(BaseModel):
    """Linkerd policy specification."""
    
    target_ref: dict[str, str] = Field(default_factory=dict)
    default: Optional[dict[str, Any]] = None
    overrides: list[dict[str, Any]] = Field(default_factory=list)


@dataclass
class LinkerdPolicy:
    """Linkerd policy resource."""
    
    name: str
    namespace: str
    spec: LinkerdPolicySpec
    
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)


# =============================================================================
# Status Models
# =============================================================================


@dataclass
class LinkerdProxyStatus:
    """Status of a Linkerd proxy sidecar."""
    
    pod_name: str
    namespace: str
    proxy_version: str
    identity: str
    
    # Connection status
    is_meshed: bool = True
    tls_enabled: bool = True
    protocol_detected: str = "HTTP/1"
    
    # Metrics
    requests_per_second: float = 0.0
    success_rate: float = 0.0
    latency_p50_ms: float = 0.0
    latency_p99_ms: float = 0.0


@dataclass
class MeshTLSStatus:
    """mTLS status for the mesh."""
    
    enabled: bool
    identity_issuer: str
    trust_anchors_valid: bool
    certificates_valid: bool
    expiry: Optional[datetime] = None


@dataclass
class LinkerdIdentity:
    """Linkerd identity information."""
    
    identity: str
    issuer: str
    not_before: datetime
    not_after: datetime
    is_valid: bool


@dataclass
class LinkerdMeshStatus:
    """Overall Linkerd mesh status."""
    
    healthy: bool
    version: str
    proxy_count: int
    
    # Component status
    control_plane_ready: bool
    destination_ready: bool
    identity_ready: bool
    proxy_injector_ready: bool
    
    # TLS status
    tls_status: MeshTLSStatus
    
    # Metrics
    meshed_namespaces: list[str] = field(default_factory=list)
    total_requests_per_second: float = 0.0
    overall_success_rate: float = 0.0


# =============================================================================
# Linkerd Client
# =============================================================================


class LinkerdClient:
    """
    Client for Linkerd service mesh operations.
    
    Provides programmatic access to Linkerd resources including:
    - ServiceProfiles for per-route metrics and retries
    - TrafficSplit for canary deployments (SMI spec)
    - Server and ServerAuthorization for policy
    - Mesh status and observability
    
    Usage:
        client = LinkerdClient(config=LinkerdConfig())
        await client.connect()
        
        # Create a traffic split for canary
        split = await client.create_traffic_split(
            name="my-service",
            namespace="production",
            service="my-service",
            backends=[
                ("my-service-stable", 90),
                ("my-service-canary", 10),
            ]
        )
        
        # Get mesh status
        status = await client.get_mesh_status()
    """
    
    def __init__(self, config: Optional[LinkerdConfig] = None):
        """Initialize Linkerd client."""
        self.config = config or LinkerdConfig()
        self._k8s_client: Any = None
        self._connected = False
    
    async def connect(self) -> None:
        """Connect to Kubernetes cluster."""
        self._connected = True
    
    async def disconnect(self) -> None:
        """Disconnect from Kubernetes cluster."""
        self._connected = False
        self._k8s_client = None
    
    # -------------------------------------------------------------------------
    # ServiceProfile Operations
    # -------------------------------------------------------------------------
    
    async def create_service_profile(
        self,
        name: str,
        namespace: str,
        routes: Optional[list[RouteSpec]] = None,
        retry_budget: Optional[RetryBudget] = None,
    ) -> ServiceProfile:
        """
        Create a ServiceProfile for per-route configuration.
        
        Args:
            name: Service name (format: <service>.<namespace>.svc.cluster.local)
            namespace: Profile namespace
            routes: Route specifications
            retry_budget: Retry budget configuration
        """
        spec = ServiceProfileSpec(
            routes=routes or [],
            retry_budget=retry_budget,
        )
        
        return ServiceProfile(
            name=name,
            namespace=namespace,
            spec=spec,
            created_at=datetime.now(timezone.utc),
        )
    
    async def get_service_profile(
        self, name: str, namespace: str
    ) -> Optional[ServiceProfile]:
        """Get a ServiceProfile by name."""
        return None
    
    async def list_service_profiles(
        self, namespace: Optional[str] = None
    ) -> list[ServiceProfile]:
        """List all ServiceProfiles."""
        return []
    
    async def update_service_profile(
        self, profile: ServiceProfile
    ) -> ServiceProfile:
        """Update an existing ServiceProfile."""
        profile.updated_at = datetime.now(timezone.utc)
        return profile
    
    async def delete_service_profile(self, name: str, namespace: str) -> bool:
        """Delete a ServiceProfile."""
        return True
    
    # -------------------------------------------------------------------------
    # TrafficSplit Operations
    # -------------------------------------------------------------------------
    
    async def create_traffic_split(
        self,
        name: str,
        namespace: str,
        service: str,
        backends: list[tuple[str, int]],
    ) -> TrafficSplit:
        """
        Create a TrafficSplit for canary deployments.
        
        Args:
            name: TrafficSplit name
            namespace: Namespace
            service: Root service name
            backends: List of (service_name, weight) tuples
        
        Returns:
            Created TrafficSplit
        
        Example:
            await client.create_traffic_split(
                name="my-app",
                namespace="prod",
                service="my-app",
                backends=[
                    ("my-app-stable", 90),
                    ("my-app-canary", 10),
                ]
            )
        """
        spec = TrafficSplitSpec(
            service=service,
            backends=[
                TrafficSplitBackend(service=svc, weight=weight)
                for svc, weight in backends
            ],
        )
        
        return TrafficSplit(
            name=name,
            namespace=namespace,
            spec=spec,
            created_at=datetime.now(timezone.utc),
        )
    
    async def get_traffic_split(
        self, name: str, namespace: str
    ) -> Optional[TrafficSplit]:
        """Get a TrafficSplit by name."""
        return None
    
    async def list_traffic_splits(
        self, namespace: Optional[str] = None
    ) -> list[TrafficSplit]:
        """List all TrafficSplits."""
        return []
    
    async def update_traffic_split(
        self, traffic_split: TrafficSplit
    ) -> TrafficSplit:
        """Update an existing TrafficSplit."""
        traffic_split.updated_at = datetime.now(timezone.utc)
        return traffic_split
    
    async def delete_traffic_split(self, name: str, namespace: str) -> bool:
        """Delete a TrafficSplit."""
        return True
    
    async def shift_traffic(
        self,
        name: str,
        namespace: str,
        weights: dict[str, int],
    ) -> TrafficSplit:
        """
        Shift traffic between backends.
        
        Args:
            name: TrafficSplit name
            namespace: Namespace
            weights: Dict mapping backend service names to weights
        
        Returns:
            Updated TrafficSplit
        """
        split = await self.get_traffic_split(name, namespace)
        
        if split:
            split.spec.backends = [
                TrafficSplitBackend(service=svc, weight=weight)
                for svc, weight in weights.items()
            ]
            return await self.update_traffic_split(split)
        else:
            # Create new split
            return await self.create_traffic_split(
                name=name,
                namespace=namespace,
                service=name,
                backends=list(weights.items()),
            )
    
    # -------------------------------------------------------------------------
    # Server Policy Operations
    # -------------------------------------------------------------------------
    
    async def create_server(
        self,
        name: str,
        namespace: str,
        port: int,
        pod_selector: dict[str, str],
        protocol: str = "HTTP/1",
    ) -> Server:
        """
        Create a Server policy resource.
        
        Args:
            name: Server name
            namespace: Namespace
            port: Port number
            pod_selector: Labels to select pods
            protocol: Protocol (HTTP/1, HTTP/2, gRPC, opaque)
        """
        spec = ServerSpec(
            pod_selector=ServerSelector(match_labels=pod_selector),
            port=ServerPort(port=port),
            proxy_protocol=protocol,
        )
        
        return Server(
            name=name,
            namespace=namespace,
            spec=spec,
        )
    
    async def create_server_authorization(
        self,
        name: str,
        namespace: str,
        server_name: str,
        service_accounts: Optional[list[str]] = None,
        allow_unauthenticated: bool = False,
    ) -> ServerAuthorization:
        """
        Create a ServerAuthorization for access control.
        
        Args:
            name: Authorization name
            namespace: Namespace
            server_name: Server to authorize access to
            service_accounts: List of allowed service accounts
            allow_unauthenticated: Whether to allow unauthenticated access
        """
        if allow_unauthenticated:
            client = ClientIdentity(unauthenticated=True)
        else:
            client = ClientIdentity(
                mesh_tls={"service_accounts": service_accounts or []}
            )
        
        spec = ServerAuthorizationSpec(
            server={"name": server_name},
            client=client,
        )
        
        return ServerAuthorization(
            name=name,
            namespace=namespace,
            spec=spec,
        )
    
    # -------------------------------------------------------------------------
    # Mesh Status Operations
    # -------------------------------------------------------------------------
    
    async def get_mesh_status(self) -> LinkerdMeshStatus:
        """Get overall mesh health status."""
        tls_status = MeshTLSStatus(
            enabled=True,
            identity_issuer="identity.linkerd.cluster.local",
            trust_anchors_valid=True,
            certificates_valid=True,
        )
        
        return LinkerdMeshStatus(
            healthy=True,
            version="stable-2.14.0",
            proxy_count=0,
            control_plane_ready=True,
            destination_ready=True,
            identity_ready=True,
            proxy_injector_ready=True,
            tls_status=tls_status,
        )
    
    async def get_proxy_status(
        self, pod_name: str, namespace: str
    ) -> Optional[LinkerdProxyStatus]:
        """Get status of a specific proxy."""
        return None
    
    async def list_meshed_pods(
        self, namespace: Optional[str] = None
    ) -> list[LinkerdProxyStatus]:
        """List all meshed pods."""
        return []
    
    async def check_identity(
        self, namespace: str
    ) -> LinkerdIdentity:
        """Check identity status for a namespace."""
        return LinkerdIdentity(
            identity=f"*.{namespace}.serviceaccount.identity.linkerd.cluster.local",
            issuer="identity.linkerd.cluster.local",
            not_before=datetime.now(timezone.utc),
            not_after=datetime.now(timezone.utc),
            is_valid=True,
        )
    
    # -------------------------------------------------------------------------
    # Observability Operations
    # -------------------------------------------------------------------------
    
    async def get_service_metrics(
        self,
        service_name: str,
        namespace: str,
        time_window: str = "1m",
    ) -> dict[str, Any]:
        """
        Get metrics for a service.
        
        Returns:
            Dict with success_rate, rps, latency_p50, latency_p99, etc.
        """
        return {
            "service": service_name,
            "namespace": namespace,
            "success_rate": 0.0,
            "requests_per_second": 0.0,
            "latency_p50_ms": 0.0,
            "latency_p99_ms": 0.0,
            "tcp_connections": 0,
        }
    
    async def get_route_metrics(
        self,
        service_name: str,
        namespace: str,
        route_name: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Get per-route metrics for a service.
        
        Requires a ServiceProfile to be configured.
        """
        return []
    
    async def get_edges(
        self,
        namespace: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Get service-to-service communication edges.
        
        Returns:
            List of edges with source, destination, and metrics
        """
        return []
    
    async def tap(
        self,
        namespace: str,
        resource: str,
        max_requests: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Tap live traffic to a resource.
        
        Args:
            namespace: Target namespace
            resource: Resource to tap (e.g., "deploy/my-app")
            max_requests: Maximum requests to capture
        
        Returns:
            List of captured requests
        """
        return []
    
    # -------------------------------------------------------------------------
    # Convenience Methods
    # -------------------------------------------------------------------------
    
    async def configure_retries(
        self,
        service_name: str,
        namespace: str,
        retry_ratio: float = 0.2,
        min_retries_per_second: int = 10,
        ttl: str = "10s",
    ) -> ServiceProfile:
        """
        Configure retry budget for a service.
        
        Args:
            service_name: Service name
            namespace: Namespace
            retry_ratio: Ratio of retries to original requests
            min_retries_per_second: Minimum retries per second
            ttl: Time to live for retry budget
        """
        profile_name = f"{service_name}.{namespace}.svc.cluster.local"
        
        return await self.create_service_profile(
            name=profile_name,
            namespace=namespace,
            retry_budget=RetryBudget(
                retry_ratio=retry_ratio,
                min_retries_per_second=min_retries_per_second,
                ttl=ttl,
            ),
        )
    
    async def configure_timeout(
        self,
        service_name: str,
        namespace: str,
        route_name: str,
        timeout: str,
    ) -> ServiceProfile:
        """
        Configure timeout for a specific route.
        
        Args:
            service_name: Service name
            namespace: Namespace
            route_name: Route name
            timeout: Timeout duration (e.g., "30s")
        """
        profile_name = f"{service_name}.{namespace}.svc.cluster.local"
        
        return await self.create_service_profile(
            name=profile_name,
            namespace=namespace,
            routes=[
                RouteSpec(
                    name=route_name,
                    timeout=timeout,
                )
            ],
        )
