"""
Kubernetes integration for AutoSRE V2.

Provides async client for Kubernetes operations:
- Pod operations (list, get, logs, exec)
- Deployment operations (list, scale, rollout)
- Events fetch
- Resource describe
"""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterator

import httpx

from autosre.utils.logging import get_logger

from .base import (
    BaseIntegration,
    ConnectionConfig,
    HealthCheckResult,
    HealthStatus,
    IntegrationError,
    RetryConfig,
)

logger = get_logger(__name__)


class PodPhase(str, Enum):
    """Pod phase states."""

    PENDING = "Pending"
    RUNNING = "Running"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    UNKNOWN = "Unknown"


class ContainerState(str, Enum):
    """Container state types."""

    WAITING = "waiting"
    RUNNING = "running"
    TERMINATED = "terminated"


@dataclass
class ContainerStatus:
    """Status of a container in a pod."""

    name: str
    state: ContainerState
    ready: bool
    restart_count: int
    image: str
    started: bool = False
    state_reason: str | None = None
    state_message: str | None = None
    last_state: ContainerState | None = None
    last_state_reason: str | None = None


@dataclass
class PodCondition:
    """A condition of a pod."""

    type: str
    status: str
    reason: str | None = None
    message: str | None = None
    last_transition: datetime | None = None


@dataclass
class Pod:
    """Kubernetes Pod."""

    name: str
    namespace: str
    phase: PodPhase
    node_name: str | None
    pod_ip: str | None
    host_ip: str | None
    start_time: datetime | None
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)
    containers: list[ContainerStatus] = field(default_factory=list)
    conditions: list[PodCondition] = field(default_factory=list)
    owner_references: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_ready(self) -> bool:
        for cond in self.conditions:
            if cond.type == "Ready":
                return cond.status == "True"
        return False

    @property
    def total_restarts(self) -> int:
        return sum(c.restart_count for c in self.containers)


@dataclass
class Deployment:
    """Kubernetes Deployment."""

    name: str
    namespace: str
    replicas: int
    ready_replicas: int
    available_replicas: int
    updated_replicas: int
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)
    selector: dict[str, str] = field(default_factory=dict)
    strategy: str = "RollingUpdate"
    conditions: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime | None = None

    @property
    def is_available(self) -> bool:
        return self.available_replicas >= self.replicas

    @property
    def is_progressing(self) -> bool:
        for cond in self.conditions:
            if cond.get("type") == "Progressing":
                return cond.get("status") == "True"
        return False


class EventType(str, Enum):
    """Kubernetes event types."""

    NORMAL = "Normal"
    WARNING = "Warning"


@dataclass
class Event:
    """Kubernetes Event."""

    name: str
    namespace: str
    type: EventType
    reason: str
    message: str
    count: int
    first_timestamp: datetime | None
    last_timestamp: datetime | None
    involved_object: dict[str, str] = field(default_factory=dict)
    source: dict[str, str] = field(default_factory=dict)


@dataclass
class Node:
    """Kubernetes Node."""

    name: str
    labels: dict[str, str]
    annotations: dict[str, str]
    conditions: list[dict[str, Any]]
    allocatable: dict[str, str]
    capacity: dict[str, str]
    node_info: dict[str, str]
    unschedulable: bool = False

    @property
    def is_ready(self) -> bool:
        for cond in self.conditions:
            if cond.get("type") == "Ready":
                return cond.get("status") == "True"
        return False


class KubernetesClient(BaseIntegration):
    """
    Async Kubernetes client.

    Features:
    - Pod operations (list, get, logs, delete)
    - Deployment operations (list, scale, restart)
    - Events fetch
    - Resource describe
    - In-cluster and kubeconfig auth
    - Connection pooling

    Usage:
        # Using kubeconfig
        async with KubernetesClient.from_kubeconfig() as k8s:
            pods = await k8s.list_pods("default")

        # Using in-cluster config
        async with KubernetesClient.in_cluster() as k8s:
            logs = await k8s.get_pod_logs("default", "my-pod")

        # Direct configuration
        async with KubernetesClient(
            server="https://kubernetes.default.svc",
            token="...",
        ) as k8s:
            events = await k8s.list_events("default")
    """

    def __init__(
        self,
        server: str,
        token: str | None = None,
        certificate_authority: str | None = None,
        client_certificate: str | None = None,
        client_key: str | None = None,
        verify_ssl: bool = True,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        """
        Initialize Kubernetes client.

        Args:
            server: Kubernetes API server URL
            token: Bearer token for authentication
            certificate_authority: Path to CA cert file
            client_certificate: Path to client cert file
            client_key: Path to client key file
            verify_ssl: Whether to verify SSL certificates
            timeout: Request timeout
            max_retries: Number of retries
        """
        connection_config = ConnectionConfig(
            base_url=server.rstrip("/"),
            timeout=timeout,
            verify_ssl=verify_ssl,
        )
        retry_config = RetryConfig(max_retries=max_retries)

        super().__init__(connection_config, retry_config)

        self._token = token
        self._ca_path = certificate_authority
        self._cert_path = client_certificate
        self._key_path = client_key

    @property
    def name(self) -> str:
        return "kubernetes"

    @classmethod
    def in_cluster(cls) -> "KubernetesClient":
        """
        Create client using in-cluster configuration.

        Uses the service account token mounted at
        /var/run/secrets/kubernetes.io/serviceaccount/
        """
        token_path = Path("/var/run/secrets/kubernetes.io/serviceaccount/token")
        ca_path = Path("/var/run/secrets/kubernetes.io/serviceaccount/ca.crt")
        namespace_path = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")

        if not token_path.exists():
            raise IntegrationError(
                "Not running in a Kubernetes cluster (token not found)",
                integration="kubernetes",
            )

        token = token_path.read_text().strip()
        server = "https://kubernetes.default.svc"

        return cls(
            server=server,
            token=token,
            certificate_authority=str(ca_path) if ca_path.exists() else None,
        )

    @classmethod
    def from_kubeconfig(
        cls,
        kubeconfig_path: str | None = None,
        context: str | None = None,
    ) -> "KubernetesClient":
        """
        Create client from kubeconfig file.

        Args:
            kubeconfig_path: Path to kubeconfig file (default: ~/.kube/config)
            context: Context to use (default: current-context)
        """
        import yaml

        if kubeconfig_path is None:
            kubeconfig_path = str(Path.home() / ".kube" / "config")

        with open(kubeconfig_path) as f:
            config = yaml.safe_load(f)

        # Get context
        context_name = context or config.get("current-context")
        context_data = None
        for ctx in config.get("contexts", []):
            if ctx.get("name") == context_name:
                context_data = ctx.get("context", {})
                break

        if not context_data:
            raise IntegrationError(
                f"Context '{context_name}' not found in kubeconfig",
                integration="kubernetes",
            )

        # Get cluster
        cluster_name = context_data.get("cluster")
        cluster_data = None
        for cluster in config.get("clusters", []):
            if cluster.get("name") == cluster_name:
                cluster_data = cluster.get("cluster", {})
                break

        if not cluster_data:
            raise IntegrationError(
                f"Cluster '{cluster_name}' not found in kubeconfig",
                integration="kubernetes",
            )

        # Get user
        user_name = context_data.get("user")
        user_data = None
        for user in config.get("users", []):
            if user.get("name") == user_name:
                user_data = user.get("user", {})
                break

        if not user_data:
            raise IntegrationError(
                f"User '{user_name}' not found in kubeconfig",
                integration="kubernetes",
            )

        # Extract credentials
        server = cluster_data.get("server")
        token = user_data.get("token")
        ca_path = cluster_data.get("certificate-authority")
        ca_data = cluster_data.get("certificate-authority-data")
        cert_path = user_data.get("client-certificate")
        cert_data = user_data.get("client-certificate-data")
        key_path = user_data.get("client-key")
        key_data = user_data.get("client-key-data")

        # Handle inline data (base64 encoded)
        # For simplicity, we'll write them to temp files if needed
        # In production, you'd want proper temp file handling

        verify_ssl = not cluster_data.get("insecure-skip-tls-verify", False)

        return cls(
            server=server,
            token=token,
            certificate_authority=ca_path,
            client_certificate=cert_path,
            client_key=key_path,
            verify_ssl=verify_ssl,
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """Get HTTP client with Kubernetes auth."""
        if self._client is None or self._client.is_closed:
            limits = httpx.Limits(
                max_connections=self._connection_config.max_connections,
                max_keepalive_connections=self._connection_config.max_keepalive,
            )

            headers = {}
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"

            # SSL configuration
            verify: bool | str = self._connection_config.verify_ssl
            if self._ca_path:
                verify = self._ca_path

            cert = None
            if self._cert_path and self._key_path:
                cert = (self._cert_path, self._key_path)

            self._client = httpx.AsyncClient(
                base_url=self._connection_config.base_url,
                timeout=httpx.Timeout(self._connection_config.timeout),
                limits=limits,
                verify=verify,
                cert=cert,
                headers=headers,
            )

        return self._client

    def _parse_datetime(self, value: str | None) -> datetime | None:
        """Parse Kubernetes datetime string."""
        if not value:
            return None
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)

    def _parse_container_status(self, data: dict[str, Any]) -> ContainerStatus:
        """Parse container status from pod status."""
        state = ContainerState.WAITING
        state_reason = None
        state_message = None

        state_data = data.get("state", {})
        if "running" in state_data:
            state = ContainerState.RUNNING
        elif "terminated" in state_data:
            state = ContainerState.TERMINATED
            state_reason = state_data["terminated"].get("reason")
            state_message = state_data["terminated"].get("message")
        elif "waiting" in state_data:
            state = ContainerState.WAITING
            state_reason = state_data["waiting"].get("reason")
            state_message = state_data["waiting"].get("message")

        last_state = None
        last_state_reason = None
        last_state_data = data.get("lastState", {})
        if "running" in last_state_data:
            last_state = ContainerState.RUNNING
        elif "terminated" in last_state_data:
            last_state = ContainerState.TERMINATED
            last_state_reason = last_state_data["terminated"].get("reason")
        elif "waiting" in last_state_data:
            last_state = ContainerState.WAITING
            last_state_reason = last_state_data["waiting"].get("reason")

        return ContainerStatus(
            name=data.get("name", ""),
            state=state,
            ready=data.get("ready", False),
            restart_count=data.get("restartCount", 0),
            image=data.get("image", ""),
            started=data.get("started", False),
            state_reason=state_reason,
            state_message=state_message,
            last_state=last_state,
            last_state_reason=last_state_reason,
        )

    def _parse_pod(self, data: dict[str, Any]) -> Pod:
        """Parse Pod from API response."""
        metadata = data.get("metadata", {})
        spec = data.get("spec", {})
        status = data.get("status", {})

        containers = []
        for cs in status.get("containerStatuses", []):
            containers.append(self._parse_container_status(cs))

        conditions = []
        for cond in status.get("conditions", []):
            conditions.append(PodCondition(
                type=cond.get("type", ""),
                status=cond.get("status", ""),
                reason=cond.get("reason"),
                message=cond.get("message"),
                last_transition=self._parse_datetime(cond.get("lastTransitionTime")),
            ))

        return Pod(
            name=metadata.get("name", ""),
            namespace=metadata.get("namespace", ""),
            phase=PodPhase(status.get("phase", "Unknown")),
            node_name=spec.get("nodeName"),
            pod_ip=status.get("podIP"),
            host_ip=status.get("hostIP"),
            start_time=self._parse_datetime(status.get("startTime")),
            labels=metadata.get("labels", {}),
            annotations=metadata.get("annotations", {}),
            containers=containers,
            conditions=conditions,
            owner_references=metadata.get("ownerReferences", []),
        )

    def _parse_deployment(self, data: dict[str, Any]) -> Deployment:
        """Parse Deployment from API response."""
        metadata = data.get("metadata", {})
        spec = data.get("spec", {})
        status = data.get("status", {})

        return Deployment(
            name=metadata.get("name", ""),
            namespace=metadata.get("namespace", ""),
            replicas=spec.get("replicas", 0),
            ready_replicas=status.get("readyReplicas", 0),
            available_replicas=status.get("availableReplicas", 0),
            updated_replicas=status.get("updatedReplicas", 0),
            labels=metadata.get("labels", {}),
            annotations=metadata.get("annotations", {}),
            selector=spec.get("selector", {}).get("matchLabels", {}),
            strategy=spec.get("strategy", {}).get("type", "RollingUpdate"),
            conditions=status.get("conditions", []),
            created_at=self._parse_datetime(metadata.get("creationTimestamp")),
        )

    def _parse_event(self, data: dict[str, Any]) -> Event:
        """Parse Event from API response."""
        metadata = data.get("metadata", {})

        return Event(
            name=metadata.get("name", ""),
            namespace=metadata.get("namespace", ""),
            type=EventType(data.get("type", "Normal")),
            reason=data.get("reason", ""),
            message=data.get("message", ""),
            count=data.get("count", 1),
            first_timestamp=self._parse_datetime(data.get("firstTimestamp")),
            last_timestamp=self._parse_datetime(data.get("lastTimestamp")),
            involved_object={
                "kind": data.get("involvedObject", {}).get("kind", ""),
                "name": data.get("involvedObject", {}).get("name", ""),
                "namespace": data.get("involvedObject", {}).get("namespace", ""),
            },
            source=data.get("source", {}),
        )

    # Pod Operations

    async def list_pods(
        self,
        namespace: str = "default",
        label_selector: str | None = None,
        field_selector: str | None = None,
    ) -> list[Pod]:
        """
        List pods in a namespace.

        Args:
            namespace: Kubernetes namespace
            label_selector: Label selector (e.g., "app=nginx")
            field_selector: Field selector (e.g., "status.phase=Running")

        Returns:
            List of pods
        """
        params = {}
        if label_selector:
            params["labelSelector"] = label_selector
        if field_selector:
            params["fieldSelector"] = field_selector

        response = await self._request(
            "GET",
            f"/api/v1/namespaces/{namespace}/pods",
            params=params,
        )

        return [self._parse_pod(item) for item in response.get("items", [])]

    async def get_pod(self, namespace: str, name: str) -> Pod:
        """
        Get a specific pod.

        Args:
            namespace: Kubernetes namespace
            name: Pod name

        Returns:
            Pod details
        """
        response = await self._request(
            "GET",
            f"/api/v1/namespaces/{namespace}/pods/{name}",
        )
        return self._parse_pod(response)

    async def get_pod_logs(
        self,
        namespace: str,
        name: str,
        container: str | None = None,
        previous: bool = False,
        since_seconds: int | None = None,
        tail_lines: int | None = None,
        timestamps: bool = False,
    ) -> str:
        """
        Get pod logs.

        Args:
            namespace: Kubernetes namespace
            name: Pod name
            container: Container name (required if multiple containers)
            previous: Get logs from previous container instance
            since_seconds: Return logs newer than this many seconds
            tail_lines: Number of lines from the end to return
            timestamps: Include timestamps

        Returns:
            Log content as string
        """
        params: dict[str, Any] = {}
        if container:
            params["container"] = container
        if previous:
            params["previous"] = "true"
        if since_seconds:
            params["sinceSeconds"] = since_seconds
        if tail_lines:
            params["tailLines"] = tail_lines
        if timestamps:
            params["timestamps"] = "true"

        response = await self._request(
            "GET",
            f"/api/v1/namespaces/{namespace}/pods/{name}/log",
            params=params,
        )

        # Logs endpoint returns text, not JSON
        if isinstance(response, dict) and "text" in response:
            return response["text"]
        return str(response)

    async def stream_pod_logs(
        self,
        namespace: str,
        name: str,
        container: str | None = None,
        since_seconds: int | None = None,
    ) -> AsyncIterator[str]:
        """
        Stream pod logs.

        Args:
            namespace: Kubernetes namespace
            name: Pod name
            container: Container name
            since_seconds: Start streaming from this many seconds ago

        Yields:
            Log lines as they arrive
        """
        params: dict[str, Any] = {"follow": "true"}
        if container:
            params["container"] = container
        if since_seconds:
            params["sinceSeconds"] = since_seconds

        client = await self._get_client()
        async with client.stream(
            "GET",
            f"/api/v1/namespaces/{namespace}/pods/{name}/log",
            params=params,
        ) as response:
            async for line in response.aiter_lines():
                yield line

    async def delete_pod(
        self,
        namespace: str,
        name: str,
        grace_period: int = 30,
    ) -> None:
        """
        Delete a pod.

        Args:
            namespace: Kubernetes namespace
            name: Pod name
            grace_period: Grace period in seconds
        """
        await self._request(
            "DELETE",
            f"/api/v1/namespaces/{namespace}/pods/{name}",
            params={"gracePeriodSeconds": grace_period},
        )

    # Deployment Operations

    async def list_deployments(
        self,
        namespace: str = "default",
        label_selector: str | None = None,
    ) -> list[Deployment]:
        """
        List deployments in a namespace.

        Args:
            namespace: Kubernetes namespace
            label_selector: Label selector

        Returns:
            List of deployments
        """
        params = {}
        if label_selector:
            params["labelSelector"] = label_selector

        response = await self._request(
            "GET",
            f"/apis/apps/v1/namespaces/{namespace}/deployments",
            params=params,
        )

        return [self._parse_deployment(item) for item in response.get("items", [])]

    async def get_deployment(self, namespace: str, name: str) -> Deployment:
        """
        Get a specific deployment.

        Args:
            namespace: Kubernetes namespace
            name: Deployment name

        Returns:
            Deployment details
        """
        response = await self._request(
            "GET",
            f"/apis/apps/v1/namespaces/{namespace}/deployments/{name}",
        )
        return self._parse_deployment(response)

    async def scale_deployment(
        self,
        namespace: str,
        name: str,
        replicas: int,
    ) -> Deployment:
        """
        Scale a deployment.

        Args:
            namespace: Kubernetes namespace
            name: Deployment name
            replicas: Target replica count

        Returns:
            Updated deployment
        """
        # Get current deployment
        deployment = await self._request(
            "GET",
            f"/apis/apps/v1/namespaces/{namespace}/deployments/{name}",
        )

        # Update replicas
        deployment["spec"]["replicas"] = replicas

        response = await self._request(
            "PUT",
            f"/apis/apps/v1/namespaces/{namespace}/deployments/{name}",
            json=deployment,
        )

        return self._parse_deployment(response)

    async def restart_deployment(
        self,
        namespace: str,
        name: str,
    ) -> Deployment:
        """
        Trigger a rolling restart of a deployment.

        Args:
            namespace: Kubernetes namespace
            name: Deployment name

        Returns:
            Updated deployment
        """
        # Patch to update restart annotation
        now = datetime.now(timezone.utc).isoformat()
        patch = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "kubectl.kubernetes.io/restartedAt": now,
                        }
                    }
                }
            }
        }

        response = await self._request(
            "PATCH",
            f"/apis/apps/v1/namespaces/{namespace}/deployments/{name}",
            json=patch,
            headers={"Content-Type": "application/strategic-merge-patch+json"},
        )

        return self._parse_deployment(response)

    # Events

    async def list_events(
        self,
        namespace: str = "default",
        field_selector: str | None = None,
        involved_object_name: str | None = None,
        involved_object_kind: str | None = None,
    ) -> list[Event]:
        """
        List events in a namespace.

        Args:
            namespace: Kubernetes namespace
            field_selector: Field selector
            involved_object_name: Filter by involved object name
            involved_object_kind: Filter by involved object kind

        Returns:
            List of events
        """
        params = {}

        selectors = []
        if field_selector:
            selectors.append(field_selector)
        if involved_object_name:
            selectors.append(f"involvedObject.name={involved_object_name}")
        if involved_object_kind:
            selectors.append(f"involvedObject.kind={involved_object_kind}")

        if selectors:
            params["fieldSelector"] = ",".join(selectors)

        response = await self._request(
            "GET",
            f"/api/v1/namespaces/{namespace}/events",
            params=params,
        )

        events = [self._parse_event(item) for item in response.get("items", [])]

        # Sort by last timestamp, most recent first
        events.sort(key=lambda e: e.last_timestamp or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

        return events

    # Nodes

    async def list_nodes(
        self,
        label_selector: str | None = None,
    ) -> list[Node]:
        """
        List cluster nodes.

        Args:
            label_selector: Label selector

        Returns:
            List of nodes
        """
        params = {}
        if label_selector:
            params["labelSelector"] = label_selector

        response = await self._request(
            "GET",
            "/api/v1/nodes",
            params=params,
        )

        nodes = []
        for item in response.get("items", []):
            metadata = item.get("metadata", {})
            spec = item.get("spec", {})
            status = item.get("status", {})

            nodes.append(Node(
                name=metadata.get("name", ""),
                labels=metadata.get("labels", {}),
                annotations=metadata.get("annotations", {}),
                conditions=status.get("conditions", []),
                allocatable=status.get("allocatable", {}),
                capacity=status.get("capacity", {}),
                node_info=status.get("nodeInfo", {}),
                unschedulable=spec.get("unschedulable", False),
            ))

        return nodes

    # Resource describe

    async def describe_resource(
        self,
        kind: str,
        namespace: str | None,
        name: str,
    ) -> dict[str, Any]:
        """
        Get detailed information about a resource.

        Args:
            kind: Resource kind (Pod, Deployment, Service, etc.)
            namespace: Kubernetes namespace (None for cluster-scoped)
            name: Resource name

        Returns:
            Full resource specification
        """
        # Map kind to API path
        kind_lower = kind.lower()
        paths = {
            "pod": f"/api/v1/namespaces/{namespace}/pods/{name}",
            "deployment": f"/apis/apps/v1/namespaces/{namespace}/deployments/{name}",
            "service": f"/api/v1/namespaces/{namespace}/services/{name}",
            "configmap": f"/api/v1/namespaces/{namespace}/configmaps/{name}",
            "secret": f"/api/v1/namespaces/{namespace}/secrets/{name}",
            "ingress": f"/apis/networking.k8s.io/v1/namespaces/{namespace}/ingresses/{name}",
            "statefulset": f"/apis/apps/v1/namespaces/{namespace}/statefulsets/{name}",
            "daemonset": f"/apis/apps/v1/namespaces/{namespace}/daemonsets/{name}",
            "job": f"/apis/batch/v1/namespaces/{namespace}/jobs/{name}",
            "cronjob": f"/apis/batch/v1/namespaces/{namespace}/cronjobs/{name}",
            "node": f"/api/v1/nodes/{name}",
            "namespace": f"/api/v1/namespaces/{name}",
            "persistentvolume": f"/api/v1/persistentvolumes/{name}",
            "persistentvolumeclaim": f"/api/v1/namespaces/{namespace}/persistentvolumeclaims/{name}",
        }

        path = paths.get(kind_lower)
        if not path:
            raise IntegrationError(
                f"Unknown resource kind: {kind}",
                integration=self.name,
            )

        return await self._request("GET", path)

    async def health_check(self) -> HealthCheckResult:
        """Check Kubernetes API health."""
        start = datetime.now(timezone.utc)
        try:
            response = await self._request("GET", "/healthz")
            latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000

            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message="Kubernetes API is healthy",
                latency_ms=latency,
            )
        except Exception as e:
            latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                latency_ms=latency,
            )

    async def get_server_version(self) -> dict[str, Any]:
        """Get Kubernetes server version."""
        return await self._request("GET", "/version")
