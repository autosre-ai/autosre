"""
Kubernetes Subagent — Investigates Kubernetes-related issues.

Capabilities:
- Pod logs (kubectl logs)
- Pod descriptions (kubectl describe)
- Events (kubectl get events)
- Resource status (deployments, services, etc.)
"""

import asyncio
import logging
import subprocess
from typing import Any, Optional

from .base import BaseSubagent, SubagentConfig
from .react import Tool, create_tool

logger = logging.getLogger(__name__)


KUBERNETES_CAPABILITIES = """
**Kubernetes Investigation**:
- View pod logs and previous container logs
- Describe pods, deployments, services
- Check Kubernetes events
- Inspect resource status and health
- Check node conditions and capacity

**Common checks**:
1. Pod status and restarts
2. Container logs for errors
3. Recent events in namespace
4. Resource limits and usage
5. Service endpoint health
"""


class KubernetesSubagent(BaseSubagent):
    """Kubernetes domain investigation subagent."""
    
    agent_id = "kubernetes"
    agent_name = "Kubernetes Investigation Agent"
    capabilities_description = KUBERNETES_CAPABILITIES
    
    def __init__(
        self,
        config: Optional[SubagentConfig] = None,
        namespace: str = "default",
        kubeconfig: Optional[str] = None,
        context: Optional[str] = None,
        dry_run: bool = False,
    ):
        super().__init__(config)
        self.namespace = namespace
        self.kubeconfig = kubeconfig
        self.context = context
        self.dry_run = dry_run  # If True, return mock data instead of real kubectl
    
    def _build_kubectl_cmd(self, *args: str) -> list[str]:
        """Build kubectl command with common flags."""
        cmd = ["kubectl"]
        if self.kubeconfig:
            cmd.extend(["--kubeconfig", self.kubeconfig])
        if self.context:
            cmd.extend(["--context", self.context])
        cmd.extend(args)
        return cmd
    
    async def _run_kubectl(self, *args: str, timeout: int = 30) -> str:
        """Run a kubectl command and return output."""
        if self.dry_run:
            return f"[DRY RUN] Would execute: kubectl {' '.join(args)}"
        
        cmd = self._build_kubectl_cmd(*args)
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
            
            if proc.returncode != 0:
                error_msg = stderr.decode().strip()
                return f"Error (exit {proc.returncode}): {error_msg}"
            
            return stdout.decode().strip()
            
        except asyncio.TimeoutError:
            return f"Error: kubectl command timed out after {timeout}s"
        except FileNotFoundError:
            return "Error: kubectl not found. Is it installed and in PATH?"
        except Exception as e:
            return f"Error executing kubectl: {e}"
    
    async def get_tools(self) -> list[Tool]:
        """Return Kubernetes investigation tools."""
        
        # ----- Tool Implementations -----
        
        async def get_pods(
            namespace: Optional[str] = None,
            label_selector: Optional[str] = None,
            all_namespaces: bool = False,
        ) -> str:
            """List pods with status information."""
            args = ["get", "pods", "-o", "wide"]
            if all_namespaces:
                args.append("-A")
            else:
                args.extend(["-n", namespace or self.namespace])
            if label_selector:
                args.extend(["-l", label_selector])
            return await self._run_kubectl(*args)
        
        async def get_pod_logs(
            pod: str,
            namespace: Optional[str] = None,
            container: Optional[str] = None,
            previous: bool = False,
            tail: int = 100,
            since: Optional[str] = None,
        ) -> str:
            """Get logs from a pod."""
            args = ["logs", pod, "-n", namespace or self.namespace]
            if container:
                args.extend(["-c", container])
            if previous:
                args.append("--previous")
            if tail:
                args.extend(["--tail", str(tail)])
            if since:
                args.extend(["--since", since])
            return await self._run_kubectl(*args)
        
        async def describe_pod(
            pod: str,
            namespace: Optional[str] = None,
        ) -> str:
            """Describe a pod with full details."""
            return await self._run_kubectl(
                "describe", "pod", pod,
                "-n", namespace or self.namespace,
            )
        
        async def get_events(
            namespace: Optional[str] = None,
            field_selector: Optional[str] = None,
            all_namespaces: bool = False,
        ) -> str:
            """Get Kubernetes events, sorted by timestamp."""
            args = ["get", "events", "--sort-by=.lastTimestamp"]
            if all_namespaces:
                args.append("-A")
            else:
                args.extend(["-n", namespace or self.namespace])
            if field_selector:
                args.extend(["--field-selector", field_selector])
            return await self._run_kubectl(*args)
        
        async def describe_deployment(
            deployment: str,
            namespace: Optional[str] = None,
        ) -> str:
            """Describe a deployment with full details."""
            return await self._run_kubectl(
                "describe", "deployment", deployment,
                "-n", namespace or self.namespace,
            )
        
        async def get_services(
            namespace: Optional[str] = None,
            label_selector: Optional[str] = None,
        ) -> str:
            """List services in the namespace."""
            args = ["get", "services", "-o", "wide", "-n", namespace or self.namespace]
            if label_selector:
                args.extend(["-l", label_selector])
            return await self._run_kubectl(*args)
        
        async def get_endpoints(
            service: str,
            namespace: Optional[str] = None,
        ) -> str:
            """Get endpoints for a service."""
            return await self._run_kubectl(
                "get", "endpoints", service,
                "-n", namespace or self.namespace,
                "-o", "yaml",
            )
        
        async def top_pods(
            namespace: Optional[str] = None,
            sort_by: str = "memory",
        ) -> str:
            """Get resource usage for pods (requires metrics-server)."""
            args = ["top", "pods", "-n", namespace or self.namespace]
            if sort_by == "memory":
                args.append("--sort-by=memory")
            elif sort_by == "cpu":
                args.append("--sort-by=cpu")
            return await self._run_kubectl(*args)
        
        async def get_nodes() -> str:
            """Get node status and conditions."""
            return await self._run_kubectl("get", "nodes", "-o", "wide")
        
        async def describe_node(node: str) -> str:
            """Describe a node with conditions and capacity."""
            return await self._run_kubectl("describe", "node", node)
        
        # ----- Build Tool Objects -----
        
        return [
            create_tool(
                name="get_pods",
                description="List pods with status. Shows pod name, ready count, status, restarts, age, IP, and node.",
                executor=get_pods,
                parameters={
                    "type": "object",
                    "properties": {
                        "namespace": {"type": "string", "description": "Namespace (default: current)"},
                        "label_selector": {"type": "string", "description": "Label selector (e.g., 'app=myapp')"},
                        "all_namespaces": {"type": "boolean", "description": "List from all namespaces"},
                    },
                },
            ),
            create_tool(
                name="get_pod_logs",
                description="Get container logs from a pod. Essential for finding error messages and stack traces.",
                executor=get_pod_logs,
                parameters={
                    "type": "object",
                    "properties": {
                        "pod": {"type": "string", "description": "Pod name"},
                        "namespace": {"type": "string", "description": "Namespace (default: current)"},
                        "container": {"type": "string", "description": "Container name (for multi-container pods)"},
                        "previous": {"type": "boolean", "description": "Get logs from previous container instance"},
                        "tail": {"type": "integer", "description": "Number of lines from end (default: 100)"},
                        "since": {"type": "string", "description": "Only logs since duration (e.g., '5m', '1h')"},
                    },
                    "required": ["pod"],
                },
            ),
            create_tool(
                name="describe_pod",
                description="Full pod details including events, conditions, resource requests/limits, and container states.",
                executor=describe_pod,
                parameters={
                    "type": "object",
                    "properties": {
                        "pod": {"type": "string", "description": "Pod name"},
                        "namespace": {"type": "string", "description": "Namespace (default: current)"},
                    },
                    "required": ["pod"],
                },
            ),
            create_tool(
                name="get_events",
                description="Kubernetes events sorted by time. Shows warnings, errors, and state changes.",
                executor=get_events,
                parameters={
                    "type": "object",
                    "properties": {
                        "namespace": {"type": "string", "description": "Namespace (default: current)"},
                        "field_selector": {"type": "string", "description": "Field selector (e.g., 'involvedObject.name=mypod')"},
                        "all_namespaces": {"type": "boolean", "description": "Get events from all namespaces"},
                    },
                },
            ),
            create_tool(
                name="describe_deployment",
                description="Full deployment details including replicas, strategy, conditions, and events.",
                executor=describe_deployment,
                parameters={
                    "type": "object",
                    "properties": {
                        "deployment": {"type": "string", "description": "Deployment name"},
                        "namespace": {"type": "string", "description": "Namespace (default: current)"},
                    },
                    "required": ["deployment"],
                },
            ),
            create_tool(
                name="get_services",
                description="List services showing type, cluster IP, external IP, and ports.",
                executor=get_services,
                parameters={
                    "type": "object",
                    "properties": {
                        "namespace": {"type": "string", "description": "Namespace (default: current)"},
                        "label_selector": {"type": "string", "description": "Label selector"},
                    },
                },
            ),
            create_tool(
                name="get_endpoints",
                description="Get endpoints for a service. Shows which pods are backing the service.",
                executor=get_endpoints,
                parameters={
                    "type": "object",
                    "properties": {
                        "service": {"type": "string", "description": "Service name"},
                        "namespace": {"type": "string", "description": "Namespace (default: current)"},
                    },
                    "required": ["service"],
                },
            ),
            create_tool(
                name="top_pods",
                description="Get CPU and memory usage for pods. Requires metrics-server.",
                executor=top_pods,
                parameters={
                    "type": "object",
                    "properties": {
                        "namespace": {"type": "string", "description": "Namespace (default: current)"},
                        "sort_by": {"type": "string", "enum": ["memory", "cpu"], "description": "Sort by resource"},
                    },
                },
            ),
            create_tool(
                name="get_nodes",
                description="List cluster nodes with status, roles, age, version, and IPs.",
                executor=get_nodes,
                parameters={"type": "object", "properties": {}},
            ),
            create_tool(
                name="describe_node",
                description="Full node details including conditions, capacity, allocatable resources, and system info.",
                executor=describe_node,
                parameters={
                    "type": "object",
                    "properties": {
                        "node": {"type": "string", "description": "Node name"},
                    },
                    "required": ["node"],
                },
            ),
        ]
    
    def get_hypothesis(
        self,
        alert: dict[str, Any],
        hypotheses: list[str],
        service_context: str = "",
    ) -> str:
        """Build Kubernetes-focused hypothesis."""
        if hypotheses:
            return f"Kubernetes investigation: {'; '.join(hypotheses)}"
        
        alert_name = alert.get("name", alert.get("alert_name", "Unknown"))
        service = alert.get("service", alert.get("labels", {}).get("service", "unknown"))
        
        return f"""Investigating Kubernetes issues for {service}:
- Check pod status, restarts, and container states
- Look for error events and warnings
- Examine pod logs for errors and stack traces
- Verify service endpoints and connectivity
- Check resource usage (CPU, memory)

Alert: {alert_name}"""


def create_kubernetes_subagent(
    namespace: str = "default",
    config: Optional[SubagentConfig] = None,
    kubeconfig: Optional[str] = None,
    context: Optional[str] = None,
    dry_run: bool = False,
) -> KubernetesSubagent:
    """Factory function to create Kubernetes subagent.
    
    Args:
        namespace: Default Kubernetes namespace
        config: Subagent configuration
        kubeconfig: Path to kubeconfig file
        context: Kubernetes context to use
        dry_run: If True, don't actually run kubectl commands
    """
    return KubernetesSubagent(
        config=config,
        namespace=namespace,
        kubeconfig=kubeconfig,
        context=context,
        dry_run=dry_run,
    )
