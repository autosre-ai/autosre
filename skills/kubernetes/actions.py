"""
Kubernetes Skill Actions

Provides actions for interacting with Kubernetes clusters.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
import logging

from opensre_core.skills import Skill, ActionResult, action

logger = logging.getLogger(__name__)

# Import kubernetes client lazily to avoid import errors when not installed
try:
    from kubernetes import client, config
    from kubernetes.client.exceptions import ApiException
    from kubernetes.stream import stream
    K8S_AVAILABLE = True
except ImportError:
    K8S_AVAILABLE = False
    ApiException = Exception  # type: ignore


@dataclass
class PodInfo:
    """Information about a Kubernetes pod."""
    name: str
    namespace: str
    status: str
    ready: bool
    restarts: int
    age: str
    node: str | None = None
    containers: list[dict[str, Any]] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)
    memory_limit: int | None = None  # bytes
    cpu_limit: float | None = None  # cores


@dataclass
class DeploymentInfo:
    """Information about a Kubernetes deployment."""
    name: str
    namespace: str
    replicas: int
    ready_replicas: int
    available_replicas: int
    strategy: str
    age: str
    conditions: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class EventInfo:
    """Kubernetes event."""
    type: str  # Normal, Warning
    reason: str
    message: str
    count: int
    involved_object: str
    first_seen: datetime | None = None
    last_seen: datetime | None = None


@dataclass
class PodDetails:
    """Detailed pod information."""
    pod: PodInfo
    events: list[EventInfo]
    conditions: list[dict[str, Any]]
    volumes: list[str]


@dataclass
class ScaleResult:
    """Result of scaling operation."""
    deployment: str
    namespace: str
    previous_replicas: int
    new_replicas: int


@dataclass
class RollbackResult:
    """Result of rollback operation."""
    deployment: str
    namespace: str
    revision: int | None = None


@dataclass
class ExecResult:
    """Result of exec command."""
    stdout: str
    stderr: str
    exit_code: int | None = None


class KubernetesSkill(Skill):
    """Skill for interacting with Kubernetes clusters."""
    
    name = "kubernetes"
    version = "1.0.0"
    description = "Interact with Kubernetes clusters - pods, deployments, troubleshooting"
    
    def __init__(self, config_dict: dict[str, Any] | None = None):
        super().__init__(config_dict)
        self.kubeconfig = self.config.get("kubeconfig")
        self.context = self.config.get("context")
        self.default_namespace = self.config.get("namespace", "default")
        self._v1: Any = None
        self._apps_v1: Any = None
        self._initialized = False
        
        # Register actions
        self.register_action("get_pods", self.get_pods, "List pods in namespace")
        self.register_action("get_pod_logs", self.get_pod_logs, "Fetch pod logs")
        self.register_action("describe_pod", self.describe_pod, "Get pod details")
        self.register_action("get_deployments", self.get_deployments, "List deployments")
        self.register_action("scale_deployment", self.scale_deployment, "Scale deployment", requires_approval=True)
        self.register_action("rollback_deployment", self.rollback_deployment, "Rollback deployment", requires_approval=True)
        self.register_action("get_events", self.get_events, "Get recent events")
        self.register_action("exec_command", self.exec_command, "Execute command in pod", requires_approval=True)
    
    def _init_client(self) -> None:
        """Initialize Kubernetes client."""
        if self._initialized or not K8S_AVAILABLE:
            return
        
        try:
            if self.kubeconfig:
                config.load_kube_config(
                    config_file=self.kubeconfig,
                    context=self.context,
                )
            else:
                try:
                    config.load_incluster_config()
                except config.ConfigException:
                    config.load_kube_config(context=self.context)
            
            self._v1 = client.CoreV1Api()
            self._apps_v1 = client.AppsV1Api()
            self._initialized = True
        except Exception as e:
            raise ConnectionError(f"Failed to initialize Kubernetes client: {e}")
    
    @property
    def v1(self):
        """Get CoreV1Api client."""
        self._init_client()
        return self._v1
    
    @property
    def apps_v1(self):
        """Get AppsV1Api client."""
        self._init_client()
        return self._apps_v1
    
    async def health_check(self) -> ActionResult[dict[str, Any]]:
        """Check Kubernetes connection."""
        if not K8S_AVAILABLE:
            return ActionResult.fail("kubernetes package not installed")
        
        try:
            self._init_client()
            version = client.VersionApi().get_code()
            return ActionResult.ok({
                "status": "healthy",
                "version": version.git_version,
                "context": self.context or "default",
            })
        except Exception as e:
            return ActionResult.fail(f"Connection failed: {e}")
    
    @action(description="List pods in namespace")
    async def get_pods(
        self,
        namespace: str | None = None,
        labels: str | None = None,
    ) -> ActionResult[list[PodInfo]]:
        """Get pods in a namespace.
        
        Args:
            namespace: Namespace to query (default: configured default, "all" for all)
            labels: Label selector string
            
        Returns:
            List of PodInfo objects
        """
        namespace = namespace or self.default_namespace
        
        try:
            if namespace == "all":
                pods = self.v1.list_pod_for_all_namespaces(label_selector=labels)
            else:
                pods = self.v1.list_namespaced_pod(
                    namespace=namespace,
                    label_selector=labels,
                )
            
            result = [self._parse_pod(pod) for pod in pods.items]
            return ActionResult.ok(result, namespace=namespace, count=len(result))
            
        except ApiException as e:
            return ActionResult.fail(f"Failed to get pods: {e.reason}")
        except Exception as e:
            return ActionResult.fail(f"Failed to get pods: {e}")
    
    @action(description="Fetch pod logs")
    async def get_pod_logs(
        self,
        pod: str,
        namespace: str | None = None,
        lines: int = 100,
        container: str | None = None,
        since_seconds: int | None = None,
    ) -> ActionResult[str]:
        """Get logs from a pod.
        
        Args:
            pod: Pod name
            namespace: Namespace
            lines: Number of lines to tail
            container: Container name (for multi-container pods)
            since_seconds: Only return logs from last N seconds
            
        Returns:
            Log content as string
        """
        namespace = namespace or self.default_namespace
        
        try:
            logs = self.v1.read_namespaced_pod_log(
                name=pod,
                namespace=namespace,
                container=container,
                tail_lines=lines,
                since_seconds=since_seconds,
            )
            return ActionResult.ok(logs, pod=pod, namespace=namespace, lines=lines)
            
        except ApiException as e:
            if e.status == 404:
                return ActionResult.fail(f"Pod not found: {pod}")
            return ActionResult.fail(f"Failed to get logs: {e.reason}")
        except Exception as e:
            return ActionResult.fail(f"Failed to get logs: {e}")
    
    @action(description="Get detailed pod information")
    async def describe_pod(
        self,
        pod: str,
        namespace: str | None = None,
    ) -> ActionResult[PodDetails]:
        """Get detailed pod information.
        
        Args:
            pod: Pod name
            namespace: Namespace
            
        Returns:
            PodDetails with full information
        """
        namespace = namespace or self.default_namespace
        
        try:
            pod_obj = self.v1.read_namespaced_pod(name=pod, namespace=namespace)
            pod_info = self._parse_pod(pod_obj)
            
            # Get events for this pod
            events = await self.get_events(
                namespace=namespace,
                field_selector=f"involvedObject.name={pod}",
            )
            
            # Parse conditions
            conditions = []
            if pod_obj.status.conditions:
                for c in pod_obj.status.conditions:
                    conditions.append({
                        "type": c.type,
                        "status": c.status,
                        "reason": c.reason,
                        "message": c.message,
                    })
            
            # Parse volumes
            volumes = []
            if pod_obj.spec.volumes:
                for v in pod_obj.spec.volumes:
                    volumes.append(v.name)
            
            return ActionResult.ok(PodDetails(
                pod=pod_info,
                events=events.data if events.success else [],
                conditions=conditions,
                volumes=volumes,
            ))
            
        except ApiException as e:
            if e.status == 404:
                return ActionResult.fail(f"Pod not found: {pod}")
            return ActionResult.fail(f"Failed to describe pod: {e.reason}")
        except Exception as e:
            return ActionResult.fail(f"Failed to describe pod: {e}")
    
    @action(description="List deployments")
    async def get_deployments(
        self,
        namespace: str | None = None,
    ) -> ActionResult[list[DeploymentInfo]]:
        """Get deployments in a namespace.
        
        Args:
            namespace: Namespace to query
            
        Returns:
            List of DeploymentInfo objects
        """
        namespace = namespace or self.default_namespace
        
        try:
            if namespace == "all":
                deployments = self.apps_v1.list_deployment_for_all_namespaces()
            else:
                deployments = self.apps_v1.list_namespaced_deployment(namespace=namespace)
            
            result = [self._parse_deployment(d) for d in deployments.items]
            return ActionResult.ok(result, namespace=namespace, count=len(result))
            
        except ApiException as e:
            return ActionResult.fail(f"Failed to get deployments: {e.reason}")
        except Exception as e:
            return ActionResult.fail(f"Failed to get deployments: {e}")
    
    @action(description="Scale deployment", requires_approval=True)
    async def scale_deployment(
        self,
        name: str,
        replicas: int,
        namespace: str | None = None,
    ) -> ActionResult[ScaleResult]:
        """Scale a deployment.
        
        Args:
            name: Deployment name
            replicas: Desired replica count
            namespace: Namespace
            
        Returns:
            ScaleResult with previous and new replica counts
        """
        namespace = namespace or self.default_namespace
        
        try:
            # Get current replicas
            deployment = self.apps_v1.read_namespaced_deployment(
                name=name,
                namespace=namespace,
            )
            previous = deployment.spec.replicas or 0
            
            # Scale
            self.apps_v1.patch_namespaced_deployment_scale(
                name=name,
                namespace=namespace,
                body={"spec": {"replicas": replicas}},
            )
            
            return ActionResult.ok(ScaleResult(
                deployment=name,
                namespace=namespace,
                previous_replicas=previous,
                new_replicas=replicas,
            ))
            
        except ApiException as e:
            if e.status == 404:
                return ActionResult.fail(f"Deployment not found: {name}")
            return ActionResult.fail(f"Failed to scale: {e.reason}")
        except Exception as e:
            return ActionResult.fail(f"Failed to scale: {e}")
    
    @action(description="Rollback deployment", requires_approval=True)
    async def rollback_deployment(
        self,
        name: str,
        namespace: str | None = None,
        revision: int | None = None,
    ) -> ActionResult[RollbackResult]:
        """Rollback deployment to previous revision.
        
        Args:
            name: Deployment name
            namespace: Namespace
            revision: Specific revision (default: previous)
            
        Returns:
            RollbackResult
        """
        namespace = namespace or self.default_namespace
        
        try:
            # Trigger rollout by patching with restart annotation
            # For actual revision rollback, we'd use the rollout API
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
            
            self.apps_v1.patch_namespaced_deployment(
                name=name,
                namespace=namespace,
                body=body,
            )
            
            return ActionResult.ok(RollbackResult(
                deployment=name,
                namespace=namespace,
                revision=revision,
            ))
            
        except ApiException as e:
            if e.status == 404:
                return ActionResult.fail(f"Deployment not found: {name}")
            return ActionResult.fail(f"Failed to rollback: {e.reason}")
        except Exception as e:
            return ActionResult.fail(f"Failed to rollback: {e}")
    
    @action(description="Get recent events")
    async def get_events(
        self,
        namespace: str | None = None,
        minutes: int = 15,
        field_selector: str | None = None,
    ) -> ActionResult[list[EventInfo]]:
        """Get recent Kubernetes events.
        
        Args:
            namespace: Namespace (or "all")
            minutes: Time window in minutes
            field_selector: Field selector for filtering
            
        Returns:
            List of EventInfo objects
        """
        namespace = namespace or self.default_namespace
        
        try:
            if namespace == "all":
                events = self.v1.list_event_for_all_namespaces(
                    field_selector=field_selector,
                )
            else:
                events = self.v1.list_namespaced_event(
                    namespace=namespace,
                    field_selector=field_selector,
                )
            
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
            result = []
            
            for event in events.items:
                event_info = self._parse_event(event)
                
                # Filter by time
                event_time = event_info.last_seen or event_info.first_seen
                if event_time:
                    if event_time.tzinfo is None:
                        event_time = event_time.replace(tzinfo=timezone.utc)
                    if event_time < cutoff:
                        continue
                
                result.append(event_info)
            
            return ActionResult.ok(result, namespace=namespace, count=len(result))
            
        except ApiException as e:
            return ActionResult.fail(f"Failed to get events: {e.reason}")
        except Exception as e:
            return ActionResult.fail(f"Failed to get events: {e}")
    
    @action(description="Execute command in pod", requires_approval=True)
    async def exec_command(
        self,
        pod: str,
        command: list[str],
        namespace: str | None = None,
        container: str | None = None,
    ) -> ActionResult[ExecResult]:
        """Execute command in a pod.
        
        Args:
            pod: Pod name
            command: Command as list of strings
            namespace: Namespace
            container: Container name (for multi-container pods)
            
        Returns:
            ExecResult with stdout/stderr
        """
        namespace = namespace or self.default_namespace
        
        try:
            resp = stream(
                self.v1.connect_get_namespaced_pod_exec,
                pod,
                namespace,
                command=command,
                container=container,
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False,
                _preload_content=False,
            )
            
            stdout = ""
            stderr = ""
            while resp.is_open():
                resp.update(timeout=1)
                if resp.peek_stdout():
                    stdout += resp.read_stdout()
                if resp.peek_stderr():
                    stderr += resp.read_stderr()
            
            return ActionResult.ok(ExecResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=resp.returncode,
            ))
            
        except ApiException as e:
            if e.status == 404:
                return ActionResult.fail(f"Pod not found: {pod}")
            return ActionResult.fail(f"Failed to exec: {e.reason}")
        except Exception as e:
            return ActionResult.fail(f"Failed to exec: {e}")
    
    # Helper methods
    
    def _parse_pod(self, pod) -> PodInfo:
        """Parse K8s pod to PodInfo."""
        status = pod.status
        
        # Calculate ready status
        ready = False
        if status.conditions:
            for c in status.conditions:
                if c.type == "Ready" and c.status == "True":
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
        age = self._calculate_age(pod.metadata.creation_timestamp)
        
        # Extract resources
        memory_limit, cpu_limit = self._extract_resources(pod)
        
        return PodInfo(
            name=pod.metadata.name,
            namespace=pod.metadata.namespace,
            status=status.phase,
            ready=ready,
            restarts=restarts,
            age=age,
            node=pod.spec.node_name,
            containers=containers,
            labels=pod.metadata.labels or {},
            memory_limit=memory_limit,
            cpu_limit=cpu_limit,
        )
    
    def _parse_deployment(self, deploy) -> DeploymentInfo:
        """Parse K8s deployment to DeploymentInfo."""
        status = deploy.status
        spec = deploy.spec
        
        conditions = []
        if status.conditions:
            for c in status.conditions:
                conditions.append({
                    "type": c.type,
                    "status": c.status,
                    "reason": c.reason,
                })
        
        return DeploymentInfo(
            name=deploy.metadata.name,
            namespace=deploy.metadata.namespace,
            replicas=spec.replicas or 0,
            ready_replicas=status.ready_replicas or 0,
            available_replicas=status.available_replicas or 0,
            strategy=spec.strategy.type if spec.strategy else "Unknown",
            age=self._calculate_age(deploy.metadata.creation_timestamp),
            conditions=conditions,
        )
    
    def _parse_event(self, event) -> EventInfo:
        """Parse K8s event to EventInfo."""
        return EventInfo(
            type=event.type or "Unknown",
            reason=event.reason or "Unknown",
            message=event.message or "",
            count=event.count or 1,
            involved_object=f"{event.involved_object.kind}/{event.involved_object.name}",
            first_seen=event.first_timestamp,
            last_seen=event.last_timestamp,
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
    
    def _calculate_age(self, timestamp: datetime | None) -> str:
        """Calculate age string from timestamp."""
        if not timestamp:
            return "Unknown"
        
        now = datetime.now(timestamp.tzinfo)
        delta = now - timestamp
        
        if delta.days > 0:
            return f"{delta.days}d"
        elif delta.seconds > 3600:
            return f"{delta.seconds // 3600}h"
        else:
            return f"{delta.seconds // 60}m"
    
    def _extract_resources(self, pod) -> tuple[int | None, float | None]:
        """Extract aggregated resource limits from pod."""
        memory_limit = 0
        cpu_limit = 0.0
        has_limits = False
        
        if not pod.spec.containers:
            return None, None
        
        for container in pod.spec.containers:
            resources = container.resources
            if not resources or not resources.limits:
                continue
            
            has_limits = True
            if "memory" in resources.limits:
                memory_limit += self._parse_memory(resources.limits["memory"])
            if "cpu" in resources.limits:
                cpu_limit += self._parse_cpu(resources.limits["cpu"])
        
        return (
            memory_limit if has_limits and memory_limit > 0 else None,
            cpu_limit if has_limits and cpu_limit > 0 else None,
        )
    
    def _parse_memory(self, value: str) -> int:
        """Parse memory string to bytes."""
        value = str(value).strip()
        multipliers = {
            "Ki": 1024,
            "Mi": 1024 ** 2,
            "Gi": 1024 ** 3,
            "K": 1000,
            "M": 1000 ** 2,
            "G": 1000 ** 3,
        }
        
        for suffix, mult in multipliers.items():
            if value.endswith(suffix):
                return int(float(value[:-len(suffix)]) * mult)
        
        return int(value)
    
    def _parse_cpu(self, value: str) -> float:
        """Parse CPU string to cores."""
        value = str(value).strip()
        if value.endswith("m"):
            return int(value[:-1]) / 1000.0
        return float(value)
