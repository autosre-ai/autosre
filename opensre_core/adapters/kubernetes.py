"""
Kubernetes Adapter - Interact with K8s cluster
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

from opensre_core.config import settings


@dataclass
class PodInfo:
    """Information about a Kubernetes pod."""
    name: str
    namespace: str
    status: str
    ready: bool
    restarts: int
    age: str
    containers: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    node: str | None = None


@dataclass
class EventInfo:
    """Kubernetes event."""
    type: str  # Normal, Warning
    reason: str
    message: str
    count: int
    first_seen: datetime | None
    last_seen: datetime | None
    involved_object: str


@dataclass 
class DeploymentInfo:
    """Information about a Kubernetes deployment."""
    name: str
    namespace: str
    replicas: int
    ready_replicas: int
    available_replicas: int
    strategy: str
    conditions: list[dict[str, Any]] = field(default_factory=list)


class KubernetesAdapter:
    """Adapter for Kubernetes cluster interactions."""
    
    def __init__(self, kubeconfig: str | None = None):
        self.kubeconfig = kubeconfig or str(settings.kubeconfig_path) if settings.kubeconfig_path else None
        self._v1: client.CoreV1Api | None = None
        self._apps_v1: client.AppsV1Api | None = None
        self._initialized = False
    
    def _init_client(self):
        """Initialize Kubernetes client."""
        if self._initialized:
            return
        
        try:
            if self.kubeconfig:
                config.load_kube_config(config_file=self.kubeconfig)
            else:
                # Try in-cluster config first
                try:
                    config.load_incluster_config()
                except config.ConfigException:
                    config.load_kube_config()
            
            self._v1 = client.CoreV1Api()
            self._apps_v1 = client.AppsV1Api()
            self._initialized = True
        except Exception as e:
            raise ConnectionError(f"Failed to initialize Kubernetes client: {e}")
    
    @property
    def v1(self) -> client.CoreV1Api:
        self._init_client()
        return self._v1  # type: ignore
    
    @property
    def apps_v1(self) -> client.AppsV1Api:
        self._init_client()
        return self._apps_v1  # type: ignore
    
    async def health_check(self) -> dict[str, Any]:
        """Check Kubernetes connection."""
        self._init_client()
        version = client.VersionApi().get_code()
        return {
            "status": "healthy",
            "details": f"K8s {version.git_version}",
        }
    
    async def get_pods(
        self,
        namespace: str = "default",
        label_selector: str | None = None,
    ) -> list[PodInfo]:
        """Get pods in namespace."""
        try:
            if namespace == "all":
                pods = self.v1.list_pod_for_all_namespaces(label_selector=label_selector)
            else:
                pods = self.v1.list_namespaced_pod(
                    namespace=namespace,
                    label_selector=label_selector,
                )
        except ApiException as e:
            raise RuntimeError(f"Failed to get pods: {e}")
        
        return [self._parse_pod(pod) for pod in pods.items]
    
    async def get_pod(self, name: str, namespace: str = "default") -> PodInfo:
        """Get single pod with details."""
        try:
            pod = self.v1.read_namespaced_pod(name=name, namespace=namespace)
        except ApiException as e:
            raise RuntimeError(f"Pod not found: {e}")
        
        pod_info = self._parse_pod(pod)
        
        # Get events for this pod
        events = await self.get_events(
            namespace=namespace,
            field_selector=f"involvedObject.name={name}",
        )
        pod_info.events = [
            {"type": e.type, "reason": e.reason, "message": e.message}
            for e in events
        ]
        
        return pod_info
    
    async def get_pod_logs(
        self,
        name: str,
        namespace: str = "default",
        container: str | None = None,
        tail_lines: int = 100,
        since_seconds: int | None = None,
    ) -> str:
        """Get pod logs."""
        try:
            logs = self.v1.read_namespaced_pod_log(
                name=name,
                namespace=namespace,
                container=container,
                tail_lines=tail_lines,
                since_seconds=since_seconds,
            )
            return logs
        except ApiException as e:
            raise RuntimeError(f"Failed to get logs: {e}")
    
    async def get_events(
        self,
        namespace: str = "default",
        field_selector: str | None = None,
    ) -> list[EventInfo]:
        """Get events in namespace."""
        try:
            if namespace == "all":
                events = self.v1.list_event_for_all_namespaces(field_selector=field_selector)
            else:
                events = self.v1.list_namespaced_event(
                    namespace=namespace,
                    field_selector=field_selector,
                )
        except ApiException as e:
            raise RuntimeError(f"Failed to get events: {e}")
        
        return [self._parse_event(event) for event in events.items]
    
    async def get_deployment(self, name: str, namespace: str = "default") -> DeploymentInfo:
        """Get deployment info."""
        try:
            deploy = self.apps_v1.read_namespaced_deployment(name=name, namespace=namespace)
        except ApiException as e:
            raise RuntimeError(f"Deployment not found: {e}")
        
        return self._parse_deployment(deploy)
    
    async def get_service_pods(self, service: str, namespace: str = "default") -> list[PodInfo]:
        """Get pods for a service by matching deployment name."""
        return await self.get_pods(
            namespace=namespace,
            label_selector=f"app={service}",
        )
    
    async def describe_resource(self, kind: str, name: str, namespace: str = "default") -> dict[str, Any]:
        """Get detailed description of a resource (like kubectl describe)."""
        result: dict[str, Any] = {"kind": kind, "name": name, "namespace": namespace}
        
        if kind.lower() == "pod":
            pod = await self.get_pod(name, namespace)
            result["status"] = pod.status
            result["ready"] = pod.ready
            result["restarts"] = pod.restarts
            result["containers"] = pod.containers
            result["events"] = pod.events
            
        elif kind.lower() == "deployment":
            deploy = await self.get_deployment(name, namespace)
            result["replicas"] = deploy.replicas
            result["ready_replicas"] = deploy.ready_replicas
            result["available_replicas"] = deploy.available_replicas
            result["conditions"] = deploy.conditions
        
        return result
    
    async def execute_command(
        self,
        command: list[str],
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Execute a kubectl-style command (with safety checks)."""
        # Parse command
        if not command:
            return {"error": "Empty command"}
        
        action = command[0] if command else ""
        
        # Safety: Only allow read operations in dry_run mode
        safe_actions = ["get", "describe", "logs", "top"]
        write_actions = ["delete", "scale", "rollout", "apply", "patch"]
        
        if dry_run and action in write_actions:
            return {
                "dry_run": True,
                "command": " ".join(command),
                "message": "This command would modify resources. Approval required.",
                "approved": False,
            }
        
        if action not in safe_actions and action not in write_actions:
            return {"error": f"Unknown or unsupported action: {action}"}
        
        return {
            "command": " ".join(command),
            "action": action,
            "requires_approval": action in write_actions,
        }
    
    async def rollout_restart(self, deployment: str, namespace: str = "default", dry_run: bool = True) -> dict[str, Any]:
        """Rollout restart a deployment."""
        if dry_run:
            return {
                "dry_run": True,
                "command": f"kubectl rollout restart deployment/{deployment} -n {namespace}",
                "approved": False,
            }
        
        # Patch deployment to trigger rollout
        now = datetime.utcnow().isoformat() + "Z"
        body = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "kubectl.kubernetes.io/restartedAt": now
                        }
                    }
                }
            }
        }
        
        try:
            self.apps_v1.patch_namespaced_deployment(
                name=deployment,
                namespace=namespace,
                body=body,
            )
            return {"success": True, "message": f"Restarted deployment/{deployment}"}
        except ApiException as e:
            return {"success": False, "error": str(e)}
    
    async def scale_deployment(
        self,
        deployment: str,
        replicas: int,
        namespace: str = "default",
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Scale a deployment."""
        if dry_run:
            return {
                "dry_run": True,
                "command": f"kubectl scale deployment/{deployment} --replicas={replicas} -n {namespace}",
                "approved": False,
            }
        
        try:
            self.apps_v1.patch_namespaced_deployment_scale(
                name=deployment,
                namespace=namespace,
                body={"spec": {"replicas": replicas}},
            )
            return {"success": True, "message": f"Scaled deployment/{deployment} to {replicas} replicas"}
        except ApiException as e:
            return {"success": False, "error": str(e)}
    
    def _parse_pod(self, pod) -> PodInfo:
        """Parse K8s pod object to PodInfo."""
        status = pod.status
        
        # Calculate ready status
        ready = False
        if status.conditions:
            for condition in status.conditions:
                if condition.type == "Ready" and condition.status == "True":
                    ready = True
                    break
        
        # Calculate restarts
        restarts = 0
        containers = []
        if status.container_statuses:
            for cs in status.container_statuses:
                restarts += cs.restart_count
                containers.append({
                    "name": cs.name,
                    "ready": cs.ready,
                    "restarts": cs.restart_count,
                    "state": self._get_container_state(cs.state),
                })
        
        # Calculate age
        age = ""
        if pod.metadata.creation_timestamp:
            delta = datetime.now(pod.metadata.creation_timestamp.tzinfo) - pod.metadata.creation_timestamp
            if delta.days > 0:
                age = f"{delta.days}d"
            elif delta.seconds > 3600:
                age = f"{delta.seconds // 3600}h"
            else:
                age = f"{delta.seconds // 60}m"
        
        return PodInfo(
            name=pod.metadata.name,
            namespace=pod.metadata.namespace,
            status=status.phase,
            ready=ready,
            restarts=restarts,
            age=age,
            containers=containers,
            node=pod.spec.node_name,
        )
    
    def _parse_event(self, event) -> EventInfo:
        """Parse K8s event object."""
        return EventInfo(
            type=event.type or "Unknown",
            reason=event.reason or "Unknown",
            message=event.message or "",
            count=event.count or 1,
            first_seen=event.first_timestamp,
            last_seen=event.last_timestamp,
            involved_object=f"{event.involved_object.kind}/{event.involved_object.name}",
        )
    
    def _parse_deployment(self, deploy) -> DeploymentInfo:
        """Parse K8s deployment object."""
        status = deploy.status
        spec = deploy.spec
        
        conditions = []
        if status.conditions:
            for c in status.conditions:
                conditions.append({
                    "type": c.type,
                    "status": c.status,
                    "reason": c.reason,
                    "message": c.message,
                })
        
        return DeploymentInfo(
            name=deploy.metadata.name,
            namespace=deploy.metadata.namespace,
            replicas=spec.replicas or 0,
            ready_replicas=status.ready_replicas or 0,
            available_replicas=status.available_replicas or 0,
            strategy=spec.strategy.type if spec.strategy else "Unknown",
            conditions=conditions,
        )
    
    def _get_container_state(self, state) -> str:
        """Get container state as string."""
        if state.running:
            return "Running"
        elif state.waiting:
            return f"Waiting: {state.waiting.reason}"
        elif state.terminated:
            return f"Terminated: {state.terminated.reason}"
        return "Unknown"
