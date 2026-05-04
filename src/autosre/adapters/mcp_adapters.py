"""MCP-backed adapters for Kubernetes and Prometheus.

These adapters use MCP tool servers instead of direct API calls,
enabling pluggable infrastructure backends.

Usage:
    # With MCP
    adapter = MCPKubernetesAdapter(mcp_manager)
    pods = await adapter.get_pods("default")

    # Falls back to native adapter if MCP unavailable
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

from opensre_core.mcp_client import MCPClientManager

logger = logging.getLogger(__name__)


@dataclass
class PodInfo:
    """Simplified pod info from MCP or native."""
    name: str
    namespace: str
    status: str
    ready: bool
    restarts: int
    age: str = ""
    containers: list[str] = None

    def __post_init__(self):
        if self.containers is None:
            self.containers = []


@dataclass
class EventInfo:
    """Kubernetes event info."""
    reason: str
    message: str
    involved_object: str
    type: str = "Warning"
    count: int = 1
    timestamp: str = ""


class MCPKubernetesAdapter:
    """Kubernetes adapter using MCP kubernetes-mcp server.

    This adapter uses the kubernetes-mcp server for all operations,
    enabling centralized tool management and consistent interfaces.

    Supported tools from kubernetes-mcp:
    - get_pods: List pods in a namespace
    - get_pod_logs: Get logs from a pod
    - describe_pod: Get detailed pod info
    - get_events: Get cluster events
    - get_deployments: List deployments
    - scale_deployment: Scale a deployment
    - delete_pod: Delete a pod
    - apply_manifest: Apply a YAML manifest
    """

    SERVER_NAME = "kubernetes"

    def __init__(self, mcp_manager: MCPClientManager):
        self.mcp = mcp_manager
        self._connected = False

    async def ensure_connected(self) -> bool:
        """Ensure kubernetes MCP server is connected."""
        if self._connected and self.SERVER_NAME in self.mcp.connections:
            return True

        try:
            from opensre_core.mcp_client import connect_preset
            await connect_preset(self.mcp, self.SERVER_NAME)
            self._connected = True
            return True
        except Exception as e:
            logger.warning(f"Failed to connect to kubernetes MCP: {e}")
            return False

    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool is available."""
        if self.SERVER_NAME not in self.mcp.connections:
            return False
        tools = [t.name for t in self.mcp.connections[self.SERVER_NAME].tools]
        return tool_name in tools

    async def get_pods(self, namespace: str = "default") -> list[PodInfo]:
        """Get pods in a namespace."""
        if not await self.ensure_connected():
            raise RuntimeError("Kubernetes MCP not connected")

        result = await self.mcp.call_tool(
            self.SERVER_NAME,
            "get_pods",
            {"namespace": namespace}
        )

        # Parse result (format depends on MCP server implementation)
        pods = []
        if isinstance(result, str):
            # Try to parse as JSON
            try:
                data = json.loads(result)
                if isinstance(data, list):
                    for item in data:
                        pods.append(PodInfo(
                            name=item.get("name", ""),
                            namespace=item.get("namespace", namespace),
                            status=item.get("status", "Unknown"),
                            ready=item.get("ready", False),
                            restarts=item.get("restarts", 0),
                            age=item.get("age", ""),
                        ))
            except json.JSONDecodeError:
                # Parse text output
                for line in result.split("\n"):
                    if line and not line.startswith("NAME"):
                        parts = line.split()
                        if len(parts) >= 3:
                            pods.append(PodInfo(
                                name=parts[0],
                                namespace=namespace,
                                status=parts[2] if len(parts) > 2 else "Unknown",
                                ready="/" in parts[1] and parts[1].split("/")[0] == parts[1].split("/")[1],
                                restarts=int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0,
                            ))

        return pods

    async def get_pod_logs(
        self,
        pod_name: str,
        namespace: str = "default",
        lines: int = 100,
        container: Optional[str] = None,
    ) -> str:
        """Get logs from a pod."""
        if not await self.ensure_connected():
            raise RuntimeError("Kubernetes MCP not connected")

        args = {
            "pod": pod_name,
            "namespace": namespace,
            "tail": lines,
        }
        if container:
            args["container"] = container

        return await self.mcp.call_tool(self.SERVER_NAME, "get_pod_logs", args)

    async def describe_pod(self, pod_name: str, namespace: str = "default") -> str:
        """Get detailed pod description."""
        if not await self.ensure_connected():
            raise RuntimeError("Kubernetes MCP not connected")

        return await self.mcp.call_tool(
            self.SERVER_NAME,
            "describe_pod",
            {"pod": pod_name, "namespace": namespace}
        )

    async def get_events(
        self,
        namespace: str = "default",
        minutes: int = 15,
    ) -> list[EventInfo]:
        """Get recent events in a namespace."""
        if not await self.ensure_connected():
            raise RuntimeError("Kubernetes MCP not connected")

        result = await self.mcp.call_tool(
            self.SERVER_NAME,
            "get_events",
            {"namespace": namespace, "since_minutes": minutes}
        )

        events = []
        if isinstance(result, str):
            try:
                data = json.loads(result)
                if isinstance(data, list):
                    for item in data:
                        events.append(EventInfo(
                            reason=item.get("reason", ""),
                            message=item.get("message", ""),
                            involved_object=item.get("object", ""),
                            type=item.get("type", "Warning"),
                            count=item.get("count", 1),
                        ))
            except json.JSONDecodeError:
                # Parse text output
                for line in result.split("\n"):
                    if "Warning" in line or "Error" in line:
                        events.append(EventInfo(
                            reason="Unknown",
                            message=line,
                            involved_object="",
                        ))

        return events

    async def get_deployments(self, namespace: str = "default") -> list[dict]:
        """Get deployments in a namespace."""
        if not await self.ensure_connected():
            raise RuntimeError("Kubernetes MCP not connected")

        result = await self.mcp.call_tool(
            self.SERVER_NAME,
            "get_deployments",
            {"namespace": namespace}
        )

        if isinstance(result, str):
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                return [{"raw": result}]
        return result if isinstance(result, list) else []

    async def scale_deployment(
        self,
        name: str,
        replicas: int,
        namespace: str = "default",
    ) -> str:
        """Scale a deployment."""
        if not await self.ensure_connected():
            raise RuntimeError("Kubernetes MCP not connected")

        return await self.mcp.call_tool(
            self.SERVER_NAME,
            "scale_deployment",
            {"deployment": name, "replicas": replicas, "namespace": namespace}
        )

    async def delete_pod(self, pod_name: str, namespace: str = "default") -> str:
        """Delete a pod."""
        if not await self.ensure_connected():
            raise RuntimeError("Kubernetes MCP not connected")

        return await self.mcp.call_tool(
            self.SERVER_NAME,
            "delete_pod",
            {"pod": pod_name, "namespace": namespace}
        )

    async def apply_manifest(self, manifest: str, namespace: str = "default") -> str:
        """Apply a YAML manifest."""
        if not await self.ensure_connected():
            raise RuntimeError("Kubernetes MCP not connected")

        return await self.mcp.call_tool(
            self.SERVER_NAME,
            "apply_manifest",
            {"manifest": manifest, "namespace": namespace}
        )

    async def execute_command(self, command: str) -> str:
        """Execute a kubectl command via MCP."""
        if not await self.ensure_connected():
            raise RuntimeError("Kubernetes MCP not connected")

        # Check if there's a raw command tool
        if self.has_tool("kubectl"):
            return await self.mcp.call_tool(
                self.SERVER_NAME,
                "kubectl",
                {"command": command}
            )

        # Otherwise parse and route to specific tools
        # This is a simplified parser
        if "get pods" in command:
            ns = "default"
            if "-n" in command:
                parts = command.split()
                ns_idx = parts.index("-n") + 1
                if ns_idx < len(parts):
                    ns = parts[ns_idx]
            pods = await self.get_pods(ns)
            return "\n".join([f"{p.name}\t{p.status}\t{p.restarts}" for p in pods])

        return f"Command routing not implemented for: {command}"


class MCPPrometheusAdapter:
    """Prometheus adapter using MCP prometheus-mcp server.

    Supported tools:
    - query: Execute a PromQL query
    - query_range: Execute a range query
    - get_alerts: Get firing alerts
    - get_targets: Get scrape targets
    - get_rules: Get alerting/recording rules
    """

    SERVER_NAME = "prometheus"

    def __init__(self, mcp_manager: MCPClientManager):
        self.mcp = mcp_manager
        self._connected = False

    async def ensure_connected(self) -> bool:
        """Ensure prometheus MCP server is connected."""
        if self._connected and self.SERVER_NAME in self.mcp.connections:
            return True

        try:
            from opensre_core.mcp_client import connect_preset
            await connect_preset(self.mcp, self.SERVER_NAME)
            self._connected = True
            return True
        except Exception as e:
            logger.warning(f"Failed to connect to prometheus MCP: {e}")
            return False

    async def query(self, promql: str) -> Any:
        """Execute a PromQL instant query."""
        if not await self.ensure_connected():
            raise RuntimeError("Prometheus MCP not connected")

        result = await self.mcp.call_tool(
            self.SERVER_NAME,
            "query",
            {"query": promql}
        )

        if isinstance(result, str):
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                return result
        return result

    async def query_range(
        self,
        promql: str,
        start: str,
        end: str,
        step: str = "1m",
    ) -> Any:
        """Execute a PromQL range query."""
        if not await self.ensure_connected():
            raise RuntimeError("Prometheus MCP not connected")

        return await self.mcp.call_tool(
            self.SERVER_NAME,
            "query_range",
            {"query": promql, "start": start, "end": end, "step": step}
        )

    async def get_alerts(self) -> list[dict]:
        """Get currently firing alerts."""
        if not await self.ensure_connected():
            raise RuntimeError("Prometheus MCP not connected")

        result = await self.mcp.call_tool(
            self.SERVER_NAME,
            "get_alerts",
            {}
        )

        if isinstance(result, str):
            try:
                data = json.loads(result)
                return data if isinstance(data, list) else data.get("alerts", [])
            except json.JSONDecodeError:
                return []
        return result if isinstance(result, list) else []

    async def get_targets(self) -> list[dict]:
        """Get scrape targets."""
        if not await self.ensure_connected():
            raise RuntimeError("Prometheus MCP not connected")

        result = await self.mcp.call_tool(
            self.SERVER_NAME,
            "get_targets",
            {}
        )

        if isinstance(result, str):
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                return []
        return result if isinstance(result, list) else []

    async def health_check(self) -> dict:
        """Check Prometheus connectivity."""
        try:
            await self.query("up")
            return {"status": "ok", "details": "Connected via MCP"}
        except Exception as e:
            return {"status": "error", "details": str(e)}


class HybridAdapter:
    """Hybrid adapter that uses MCP when available, falls back to native.

    This provides seamless integration where MCP tools are used when
    connected, but native adapters work as fallback.

    Example:
        adapter = HybridAdapter(mcp_manager)

        # Uses MCP if kubernetes-mcp is connected, else native kubernetes
        pods = await adapter.kubernetes.get_pods("default")
    """

    def __init__(self, mcp_manager: Optional[MCPClientManager] = None):
        self.mcp_manager = mcp_manager
        self._mcp_k8s: Optional[MCPKubernetesAdapter] = None
        self._mcp_prom: Optional[MCPPrometheusAdapter] = None
        self._native_k8s = None
        self._native_prom = None

    @property
    def kubernetes(self):
        """Get Kubernetes adapter (MCP or native)."""
        if self.mcp_manager and "kubernetes" in self.mcp_manager.connections:
            if not self._mcp_k8s:
                self._mcp_k8s = MCPKubernetesAdapter(self.mcp_manager)
            return self._mcp_k8s

        # Fallback to native
        if not self._native_k8s:
            from opensre_core.adapters.kubernetes import KubernetesAdapter
            self._native_k8s = KubernetesAdapter()
        return self._native_k8s

    @property
    def prometheus(self):
        """Get Prometheus adapter (MCP or native)."""
        if self.mcp_manager and "prometheus" in self.mcp_manager.connections:
            if not self._mcp_prom:
                self._mcp_prom = MCPPrometheusAdapter(self.mcp_manager)
            return self._mcp_prom

        # Fallback to native
        if not self._native_prom:
            from opensre_core.adapters.prometheus import PrometheusAdapter
            self._native_prom = PrometheusAdapter()
        return self._native_prom

    def using_mcp(self, adapter_type: str) -> bool:
        """Check if using MCP for a given adapter type."""
        if not self.mcp_manager:
            return False
        return adapter_type in self.mcp_manager.connections
