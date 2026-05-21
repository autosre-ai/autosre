"""Kubernetes investigation tools for SRE agents.

Provides tools for investigating Kubernetes clusters:
- Pod operations (list, describe, logs)
- Deployment and service inspection
- Event monitoring
- Node status checks
"""

import json
import logging
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Optional

from langchain_core.tools import BaseTool, tool

from .base import BaseSRETool, ToolResult, SREToolError, sre_tool, with_timeout

logger = logging.getLogger(__name__)


@dataclass
class KubernetesConfig:
    """Configuration for Kubernetes client."""
    
    kubeconfig: Optional[str] = None
    context: Optional[str] = None
    namespace: str = "default"
    timeout_seconds: int = 30
    
    @classmethod
    def from_env(cls) -> "KubernetesConfig":
        """Create config from environment variables."""
        return cls(
            kubeconfig=os.getenv("KUBECONFIG"),
            context=os.getenv("KUBE_CONTEXT"),
            namespace=os.getenv("KUBE_NAMESPACE", "default"),
            timeout_seconds=int(os.getenv("KUBE_TIMEOUT", "30")),
        )


class KubernetesTools(BaseSRETool):
    """Kubernetes investigation tools.
    
    Uses kubectl CLI for maximum compatibility across environments.
    Can also use kubernetes-client library if available.
    """
    
    name = "kubernetes"
    description = "Kubernetes cluster investigation tools"
    
    def __init__(
        self,
        config: Optional[KubernetesConfig] = None,
        mock_mode: bool = False,
    ):
        """Initialize Kubernetes tools.
        
        Args:
            config: Kubernetes configuration. Uses env vars if not provided.
            mock_mode: If True, return mock data.
        """
        super().__init__(mock_mode=mock_mode)
        self.config = config or KubernetesConfig.from_env()
        self._kubectl_available: Optional[bool] = None
    
    def _check_kubectl(self) -> bool:
        """Check if kubectl is available."""
        if self._kubectl_available is None:
            try:
                subprocess.run(
                    ["kubectl", "version", "--client", "--short"],
                    capture_output=True,
                    timeout=5,
                )
                self._kubectl_available = True
            except (subprocess.SubprocessError, FileNotFoundError):
                self._kubectl_available = False
        return self._kubectl_available
    
    def _build_kubectl_cmd(
        self,
        *args: str,
        namespace: Optional[str] = None,
        all_namespaces: bool = False,
    ) -> list[str]:
        """Build kubectl command with common flags."""
        cmd = ["kubectl"]
        
        if self.config.kubeconfig:
            cmd.extend(["--kubeconfig", self.config.kubeconfig])
        
        if self.config.context:
            cmd.extend(["--context", self.config.context])
        
        if all_namespaces:
            cmd.append("--all-namespaces")
        elif namespace:
            cmd.extend(["-n", namespace])
        elif self.config.namespace:
            cmd.extend(["-n", self.config.namespace])
        
        cmd.extend(args)
        return cmd
    
    def _run_kubectl(
        self,
        *args: str,
        namespace: Optional[str] = None,
        all_namespaces: bool = False,
        output_format: str = "json",
    ) -> dict[str, Any]:
        """Run kubectl command and return parsed output.
        
        Args:
            *args: kubectl arguments.
            namespace: Target namespace.
            all_namespaces: Query all namespaces.
            output_format: Output format (json, yaml, wide).
            
        Returns:
            Parsed command output.
            
        Raises:
            SREToolError: On command failure.
        """
        if not self._check_kubectl():
            raise SREToolError("kubectl is not available", recoverable=False)
        
        full_args = list(args)
        if output_format and "-o" not in args:
            full_args.extend(["-o", output_format])
        
        cmd = self._build_kubectl_cmd(
            *full_args,
            namespace=namespace,
            all_namespaces=all_namespaces,
        )
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout_seconds,
            )
            
            if result.returncode != 0:
                raise SREToolError(
                    f"kubectl failed: {result.stderr.strip() or result.stdout.strip()}"
                )
            
            if output_format == "json" and result.stdout.strip():
                return json.loads(result.stdout)
            
            return {"output": result.stdout}
            
        except subprocess.TimeoutExpired:
            raise SREToolError(
                f"kubectl timed out after {self.config.timeout_seconds}s"
            )
        except json.JSONDecodeError as e:
            raise SREToolError(f"Failed to parse kubectl output: {e}")
    
    def _format_pod_info(self, pod: dict) -> dict:
        """Extract key information from a pod resource."""
        metadata = pod.get("metadata", {})
        status = pod.get("status", {})
        spec = pod.get("spec", {})
        
        containers = []
        for c in spec.get("containers", []):
            container_status = next(
                (cs for cs in status.get("containerStatuses", [])
                 if cs.get("name") == c.get("name")),
                {}
            )
            containers.append({
                "name": c.get("name"),
                "image": c.get("image"),
                "ready": container_status.get("ready", False),
                "restartCount": container_status.get("restartCount", 0),
                "state": list(container_status.get("state", {}).keys())[0]
                if container_status.get("state") else "unknown",
            })
        
        return {
            "name": metadata.get("name"),
            "namespace": metadata.get("namespace"),
            "phase": status.get("phase"),
            "hostIP": status.get("hostIP"),
            "podIP": status.get("podIP"),
            "startTime": status.get("startTime"),
            "containers": containers,
            "labels": metadata.get("labels", {}),
            "nodeName": spec.get("nodeName"),
        }
    
    def get_tools(self) -> list[BaseTool]:
        """Return list of Kubernetes tools."""
        return [
            self._make_list_pods_tool(),
            self._make_get_pod_logs_tool(),
            self._make_describe_pod_tool(),
            self._make_get_deployments_tool(),
            self._make_get_services_tool(),
            self._make_get_events_tool(),
            self._make_get_node_status_tool(),
        ]
    
    def _make_list_pods_tool(self) -> BaseTool:
        """Create list_pods tool."""
        parent = self
        
        @tool
        def list_pods(
            namespace: str = "",
            all_namespaces: bool = False,
            label_selector: str = "",
            field_selector: str = "",
        ) -> str:
            """List pods in a Kubernetes namespace.
            
            Args:
                namespace: Target namespace (empty uses default from config).
                all_namespaces: If True, list pods across all namespaces.
                label_selector: Filter by labels (e.g., 'app=nginx,env=prod').
                field_selector: Filter by fields (e.g., 'status.phase=Running').
                
            Returns:
                JSON list of pods with key information.
            """
            if parent.mock_mode:
                mock_data = parent.get_mock_response("list_pods", {
                    "pods": [
                        {
                            "name": "nginx-pod-1",
                            "namespace": namespace or "default",
                            "phase": "Running",
                            "containers": [{"name": "nginx", "ready": True}],
                        }
                    ]
                })
                return json.dumps(mock_data, indent=2)
            
            args = ["get", "pods"]
            if label_selector:
                args.extend(["-l", label_selector])
            if field_selector:
                args.extend(["--field-selector", field_selector])
            
            try:
                result = parent._run_kubectl(
                    *args,
                    namespace=namespace or None,
                    all_namespaces=all_namespaces,
                )
                
                pods = []
                for item in result.get("items", []):
                    pods.append(parent._format_pod_info(item))
                
                return json.dumps({"pods": pods, "count": len(pods)}, indent=2)
                
            except SREToolError as e:
                return json.dumps({"error": str(e)})
        
        return list_pods
    
    def _make_get_pod_logs_tool(self) -> BaseTool:
        """Create get_pod_logs tool."""
        parent = self
        
        @tool
        def get_pod_logs(
            pod_name: str,
            namespace: str = "",
            container: str = "",
            tail_lines: int = 100,
            since: str = "",
            previous: bool = False,
        ) -> str:
            """Get logs from a Kubernetes pod.
            
            Args:
                pod_name: Name of the pod.
                namespace: Target namespace (empty uses default).
                container: Specific container name (required for multi-container pods).
                tail_lines: Number of recent lines to return (default 100).
                since: Return logs newer than duration (e.g., '1h', '30m').
                previous: Get logs from previous container instance.
                
            Returns:
                Pod logs as text, or error message.
            """
            if parent.mock_mode:
                mock_data = parent.get_mock_response(
                    "get_pod_logs",
                    f"[INFO] Mock log line 1\n[INFO] Mock log line 2\n"
                )
                return mock_data
            
            args = ["logs", pod_name]
            
            if container:
                args.extend(["-c", container])
            if tail_lines:
                args.extend(["--tail", str(tail_lines)])
            if since:
                args.extend(["--since", since])
            if previous:
                args.append("--previous")
            
            try:
                result = parent._run_kubectl(
                    *args,
                    namespace=namespace or None,
                    output_format="",  # Logs don't use JSON output
                )
                return result.get("output", "No logs available")
                
            except SREToolError as e:
                return f"Error getting logs: {e}"
        
        return get_pod_logs
    
    def _make_describe_pod_tool(self) -> BaseTool:
        """Create describe_pod tool."""
        parent = self
        
        @tool
        def describe_pod(
            pod_name: str,
            namespace: str = "",
        ) -> str:
            """Get detailed information about a Kubernetes pod.
            
            Includes conditions, events, container states, volumes, and more.
            
            Args:
                pod_name: Name of the pod.
                namespace: Target namespace (empty uses default).
                
            Returns:
                Detailed pod description in JSON format.
            """
            if parent.mock_mode:
                mock_data = parent.get_mock_response("describe_pod", {
                    "name": pod_name,
                    "namespace": namespace or "default",
                    "phase": "Running",
                    "conditions": [{"type": "Ready", "status": "True"}],
                })
                return json.dumps(mock_data, indent=2)
            
            try:
                result = parent._run_kubectl(
                    "get", "pod", pod_name,
                    namespace=namespace or None,
                )
                
                pod_info = parent._format_pod_info(result)
                
                # Add conditions
                status = result.get("status", {})
                pod_info["conditions"] = status.get("conditions", [])
                
                # Add volumes
                spec = result.get("spec", {})
                pod_info["volumes"] = [
                    {"name": v.get("name"), "type": list(v.keys())[1] if len(v) > 1 else "unknown"}
                    for v in spec.get("volumes", [])
                ]
                
                # Get recent events for this pod
                try:
                    events_result = parent._run_kubectl(
                        "get", "events",
                        "--field-selector", f"involvedObject.name={pod_name}",
                        "--sort-by", ".lastTimestamp",
                        namespace=namespace or None,
                    )
                    pod_info["events"] = [
                        {
                            "type": e.get("type"),
                            "reason": e.get("reason"),
                            "message": e.get("message"),
                            "lastTimestamp": e.get("lastTimestamp"),
                        }
                        for e in events_result.get("items", [])[-5:]  # Last 5 events
                    ]
                except SREToolError:
                    pod_info["events"] = []
                
                return json.dumps(pod_info, indent=2)
                
            except SREToolError as e:
                return json.dumps({"error": str(e)})
        
        return describe_pod
    
    def _make_get_deployments_tool(self) -> BaseTool:
        """Create get_deployments tool."""
        parent = self
        
        @tool
        def get_deployments(
            namespace: str = "",
            all_namespaces: bool = False,
            label_selector: str = "",
        ) -> str:
            """List deployments in a Kubernetes namespace.
            
            Args:
                namespace: Target namespace (empty uses default).
                all_namespaces: If True, list across all namespaces.
                label_selector: Filter by labels (e.g., 'app=nginx').
                
            Returns:
                JSON list of deployments with replica status.
            """
            if parent.mock_mode:
                mock_data = parent.get_mock_response("get_deployments", {
                    "deployments": [
                        {
                            "name": "nginx-deployment",
                            "namespace": namespace or "default",
                            "replicas": {"desired": 3, "ready": 3, "available": 3},
                        }
                    ]
                })
                return json.dumps(mock_data, indent=2)
            
            args = ["get", "deployments"]
            if label_selector:
                args.extend(["-l", label_selector])
            
            try:
                result = parent._run_kubectl(
                    *args,
                    namespace=namespace or None,
                    all_namespaces=all_namespaces,
                )
                
                deployments = []
                for item in result.get("items", []):
                    metadata = item.get("metadata", {})
                    status = item.get("status", {})
                    spec = item.get("spec", {})
                    
                    deployments.append({
                        "name": metadata.get("name"),
                        "namespace": metadata.get("namespace"),
                        "replicas": {
                            "desired": spec.get("replicas", 0),
                            "ready": status.get("readyReplicas", 0),
                            "available": status.get("availableReplicas", 0),
                            "unavailable": status.get("unavailableReplicas", 0),
                        },
                        "strategy": spec.get("strategy", {}).get("type"),
                        "labels": metadata.get("labels", {}),
                        "conditions": [
                            {
                                "type": c.get("type"),
                                "status": c.get("status"),
                                "reason": c.get("reason"),
                            }
                            for c in status.get("conditions", [])
                        ],
                    })
                
                return json.dumps({"deployments": deployments, "count": len(deployments)}, indent=2)
                
            except SREToolError as e:
                return json.dumps({"error": str(e)})
        
        return get_deployments
    
    def _make_get_services_tool(self) -> BaseTool:
        """Create get_services tool."""
        parent = self
        
        @tool
        def get_services(
            namespace: str = "",
            all_namespaces: bool = False,
            label_selector: str = "",
        ) -> str:
            """List services in a Kubernetes namespace.
            
            Args:
                namespace: Target namespace (empty uses default).
                all_namespaces: If True, list across all namespaces.
                label_selector: Filter by labels.
                
            Returns:
                JSON list of services with type, ports, and endpoints.
            """
            if parent.mock_mode:
                mock_data = parent.get_mock_response("get_services", {
                    "services": [
                        {
                            "name": "nginx-service",
                            "namespace": namespace or "default",
                            "type": "ClusterIP",
                            "clusterIP": "10.0.0.100",
                            "ports": [{"port": 80, "targetPort": 8080}],
                        }
                    ]
                })
                return json.dumps(mock_data, indent=2)
            
            args = ["get", "services"]
            if label_selector:
                args.extend(["-l", label_selector])
            
            try:
                result = parent._run_kubectl(
                    *args,
                    namespace=namespace or None,
                    all_namespaces=all_namespaces,
                )
                
                services = []
                for item in result.get("items", []):
                    metadata = item.get("metadata", {})
                    spec = item.get("spec", {})
                    
                    services.append({
                        "name": metadata.get("name"),
                        "namespace": metadata.get("namespace"),
                        "type": spec.get("type"),
                        "clusterIP": spec.get("clusterIP"),
                        "externalIP": spec.get("externalIPs", []),
                        "ports": [
                            {
                                "name": p.get("name"),
                                "port": p.get("port"),
                                "targetPort": p.get("targetPort"),
                                "protocol": p.get("protocol"),
                                "nodePort": p.get("nodePort"),
                            }
                            for p in spec.get("ports", [])
                        ],
                        "selector": spec.get("selector", {}),
                        "labels": metadata.get("labels", {}),
                    })
                
                return json.dumps({"services": services, "count": len(services)}, indent=2)
                
            except SREToolError as e:
                return json.dumps({"error": str(e)})
        
        return get_services
    
    def _make_get_events_tool(self) -> BaseTool:
        """Create get_events tool."""
        parent = self
        
        @tool
        def get_events(
            namespace: str = "",
            all_namespaces: bool = False,
            field_selector: str = "",
            event_type: str = "",
        ) -> str:
            """Get Kubernetes cluster events.
            
            Events show what's happening in the cluster - pod scheduling,
            container starts/stops, errors, warnings, etc.
            
            Args:
                namespace: Target namespace (empty uses default).
                all_namespaces: If True, get events across all namespaces.
                field_selector: Filter by fields (e.g., 'involvedObject.kind=Pod').
                event_type: Filter by type ('Normal' or 'Warning').
                
            Returns:
                JSON list of recent events sorted by time.
            """
            if parent.mock_mode:
                mock_data = parent.get_mock_response("get_events", {
                    "events": [
                        {
                            "type": "Normal",
                            "reason": "Scheduled",
                            "message": "Successfully assigned pod",
                            "object": "pod/nginx-pod-1",
                            "lastTimestamp": "2024-01-15T10:30:00Z",
                        }
                    ]
                })
                return json.dumps(mock_data, indent=2)
            
            args = ["get", "events", "--sort-by", ".lastTimestamp"]
            
            selectors = []
            if field_selector:
                selectors.append(field_selector)
            if event_type:
                selectors.append(f"type={event_type}")
            if selectors:
                args.extend(["--field-selector", ",".join(selectors)])
            
            try:
                result = parent._run_kubectl(
                    *args,
                    namespace=namespace or None,
                    all_namespaces=all_namespaces,
                )
                
                events = []
                for item in result.get("items", [])[-50:]:  # Last 50 events
                    involved = item.get("involvedObject", {})
                    events.append({
                        "type": item.get("type"),
                        "reason": item.get("reason"),
                        "message": item.get("message"),
                        "object": f"{involved.get('kind', '').lower()}/{involved.get('name', '')}",
                        "namespace": involved.get("namespace"),
                        "count": item.get("count", 1),
                        "firstTimestamp": item.get("firstTimestamp"),
                        "lastTimestamp": item.get("lastTimestamp"),
                        "source": item.get("source", {}).get("component"),
                    })
                
                # Sort by timestamp descending
                events.sort(
                    key=lambda e: e.get("lastTimestamp") or "",
                    reverse=True
                )
                
                return json.dumps({"events": events, "count": len(events)}, indent=2)
                
            except SREToolError as e:
                return json.dumps({"error": str(e)})
        
        return get_events
    
    def _make_get_node_status_tool(self) -> BaseTool:
        """Create get_node_status tool."""
        parent = self
        
        @tool
        def get_node_status(
            node_name: str = "",
            label_selector: str = "",
        ) -> str:
            """Get status of Kubernetes nodes.
            
            Shows node health, capacity, allocatable resources, and conditions.
            
            Args:
                node_name: Specific node name (empty for all nodes).
                label_selector: Filter nodes by labels.
                
            Returns:
                JSON with node status and resource information.
            """
            if parent.mock_mode:
                mock_data = parent.get_mock_response("get_node_status", {
                    "nodes": [
                        {
                            "name": "node-1",
                            "ready": True,
                            "capacity": {"cpu": "4", "memory": "16Gi"},
                            "allocatable": {"cpu": "3800m", "memory": "14Gi"},
                        }
                    ]
                })
                return json.dumps(mock_data, indent=2)
            
            args = ["get", "nodes"]
            if node_name:
                args.append(node_name)
            if label_selector:
                args.extend(["-l", label_selector])
            
            try:
                result = parent._run_kubectl(*args)
                
                nodes = []
                items = result.get("items", [result]) if "items" in result else [result]
                
                for item in items:
                    if not item.get("metadata"):
                        continue
                        
                    metadata = item.get("metadata", {})
                    status = item.get("status", {})
                    spec = item.get("spec", {})
                    
                    # Get ready condition
                    conditions = status.get("conditions", [])
                    ready_condition = next(
                        (c for c in conditions if c.get("type") == "Ready"),
                        {}
                    )
                    
                    nodes.append({
                        "name": metadata.get("name"),
                        "ready": ready_condition.get("status") == "True",
                        "conditions": [
                            {
                                "type": c.get("type"),
                                "status": c.get("status"),
                                "reason": c.get("reason"),
                                "message": c.get("message"),
                            }
                            for c in conditions
                        ],
                        "capacity": status.get("capacity", {}),
                        "allocatable": status.get("allocatable", {}),
                        "nodeInfo": {
                            "kubeletVersion": status.get("nodeInfo", {}).get("kubeletVersion"),
                            "osImage": status.get("nodeInfo", {}).get("osImage"),
                            "containerRuntimeVersion": status.get("nodeInfo", {}).get("containerRuntimeVersion"),
                        },
                        "labels": metadata.get("labels", {}),
                        "taints": spec.get("taints", []),
                        "unschedulable": spec.get("unschedulable", False),
                    })
                
                return json.dumps({"nodes": nodes, "count": len(nodes)}, indent=2)
                
            except SREToolError as e:
                return json.dumps({"error": str(e)})
        
        return get_node_status


# Convenience function to get all K8s tools
def get_kubernetes_tools(
    config: Optional[KubernetesConfig] = None,
    mock_mode: bool = False,
) -> list[BaseTool]:
    """Get all Kubernetes investigation tools.
    
    Args:
        config: Kubernetes configuration.
        mock_mode: If True, return mock data.
        
    Returns:
        List of LangChain tools.
    """
    k8s = KubernetesTools(config=config, mock_mode=mock_mode)
    return k8s.get_tools()
