"""
K8sAgent — Specialized Kubernetes troubleshooting agent.

This agent provides deep Kubernetes expertise with methods for:
- Pod diagnosis (restarts, crashes, resource issues)
- Deployment checks (rollout status, replicas, conditions)
- Event analysis (warnings, errors, state changes)
- Resource checks (limits, requests, usage)

Uses kubectl tools under the hood.
"""

import asyncio
import logging
import subprocess
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class K8sAgentConfig:
    """Configuration for the Kubernetes agent."""
    
    namespace: str = "default"
    kubeconfig: Optional[str] = None
    context: Optional[str] = None
    timeout_seconds: int = 30
    dry_run: bool = False


@dataclass
class DiagnosisResult:
    """Result of a pod diagnosis."""
    
    pod_name: str
    namespace: str
    status: str
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)
    
    @property
    def has_issues(self) -> bool:
        return len(self.issues) > 0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "pod_name": self.pod_name,
            "namespace": self.namespace,
            "status": self.status,
            "issues": self.issues,
            "recommendations": self.recommendations,
            "raw_data": self.raw_data,
        }


@dataclass
class DeploymentCheckResult:
    """Result of a deployment health check."""
    
    deployment_name: str
    namespace: str
    healthy: bool
    replicas_desired: int = 0
    replicas_ready: int = 0
    replicas_available: int = 0
    conditions: list[dict[str, Any]] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "deployment_name": self.deployment_name,
            "namespace": self.namespace,
            "healthy": self.healthy,
            "replicas_desired": self.replicas_desired,
            "replicas_ready": self.replicas_ready,
            "replicas_available": self.replicas_available,
            "conditions": self.conditions,
            "issues": self.issues,
            "raw_data": self.raw_data,
        }


@dataclass
class EventAnalysisResult:
    """Result of Kubernetes event analysis."""
    
    namespace: str
    total_events: int = 0
    warnings: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    recent_events: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "total_events": self.total_events,
            "warnings": self.warnings,
            "errors": self.errors,
            "recent_events": self.recent_events,
            "summary": self.summary,
        }


@dataclass
class ResourceCheckResult:
    """Result of resource utilization check."""
    
    namespace: str
    pods: list[dict[str, Any]] = field(default_factory=list)
    nodes: list[dict[str, Any]] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    summary: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "pods": self.pods,
            "nodes": self.nodes,
            "issues": self.issues,
            "summary": self.summary,
        }


class K8sAgent:
    """Specialized Kubernetes troubleshooting agent.
    
    Provides high-level troubleshooting methods that combine multiple
    kubectl operations with intelligent analysis.
    
    Example:
        agent = K8sAgent(namespace="production")
        result = await agent.diagnose_pod("my-pod-abc123")
        if result.has_issues:
            print("Found issues:", result.issues)
    """
    
    def __init__(
        self,
        namespace: str = "default",
        kubeconfig: Optional[str] = None,
        context: Optional[str] = None,
        timeout_seconds: int = 30,
        dry_run: bool = False,
        config: Optional[K8sAgentConfig] = None,
    ):
        """Initialize the Kubernetes agent.
        
        Args:
            namespace: Default Kubernetes namespace
            kubeconfig: Path to kubeconfig file
            context: Kubernetes context to use
            timeout_seconds: Timeout for kubectl commands
            dry_run: If True, return mock data instead of real kubectl calls
            config: Full config object (overrides other params if provided)
        """
        if config:
            self.config = config
        else:
            self.config = K8sAgentConfig(
                namespace=namespace,
                kubeconfig=kubeconfig,
                context=context,
                timeout_seconds=timeout_seconds,
                dry_run=dry_run,
            )
    
    def _build_kubectl_cmd(self, *args: str) -> list[str]:
        """Build kubectl command with common flags."""
        cmd = ["kubectl"]
        if self.config.kubeconfig:
            cmd.extend(["--kubeconfig", self.config.kubeconfig])
        if self.config.context:
            cmd.extend(["--context", self.config.context])
        cmd.extend(args)
        return cmd
    
    async def _run_kubectl(
        self,
        *args: str,
        timeout: Optional[int] = None,
    ) -> tuple[bool, str]:
        """Run a kubectl command and return (success, output).
        
        Returns:
            Tuple of (success: bool, output: str)
        """
        if self.config.dry_run:
            return True, f"[DRY RUN] Would execute: kubectl {' '.join(args)}"
        
        cmd = self._build_kubectl_cmd(*args)
        timeout = timeout or self.config.timeout_seconds
        
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
                return False, f"Error (exit {proc.returncode}): {error_msg}"
            
            return True, stdout.decode().strip()
            
        except asyncio.TimeoutError:
            return False, f"Timeout: kubectl command timed out after {timeout}s"
        except FileNotFoundError:
            return False, "Error: kubectl not found. Is it installed and in PATH?"
        except Exception as e:
            return False, f"Error executing kubectl: {e}"
    
    async def _run_kubectl_json(
        self,
        *args: str,
        timeout: Optional[int] = None,
    ) -> tuple[bool, Any]:
        """Run kubectl with -o json and parse the result.
        
        Returns:
            Tuple of (success: bool, parsed_json or error_string)
        """
        import json
        
        full_args = list(args) + ["-o", "json"]
        success, output = await self._run_kubectl(*full_args, timeout=timeout)
        
        if not success:
            return False, output
        
        try:
            return True, json.loads(output)
        except json.JSONDecodeError as e:
            return False, f"Failed to parse JSON: {e}"
    
    # ----- Main troubleshooting methods -----
    
    async def diagnose_pod(
        self,
        pod_name: str,
        namespace: Optional[str] = None,
    ) -> DiagnosisResult:
        """Diagnose issues with a specific pod.
        
        Performs comprehensive analysis including:
        - Pod status and phase
        - Container states and restarts
        - Resource limits and requests
        - Recent events
        - Exit codes and termination reasons
        
        Args:
            pod_name: Name of the pod to diagnose
            namespace: Namespace (defaults to agent's namespace)
            
        Returns:
            DiagnosisResult with findings and recommendations
        """
        ns = namespace or self.config.namespace
        issues: list[str] = []
        recommendations: list[str] = []
        raw_data: dict[str, Any] = {}
        
        # Get pod details
        success, pod_data = await self._run_kubectl_json(
            "get", "pod", pod_name, "-n", ns,
        )
        
        if not success:
            return DiagnosisResult(
                pod_name=pod_name,
                namespace=ns,
                status="error",
                issues=[f"Failed to get pod: {pod_data}"],
                recommendations=["Check if pod exists and you have access"],
            )
        
        raw_data["pod"] = pod_data
        
        # Analyze pod status
        status = pod_data.get("status", {})
        phase = status.get("phase", "Unknown")
        
        # Check container statuses
        container_statuses = status.get("containerStatuses", [])
        for cs in container_statuses:
            container_name = cs.get("name", "unknown")
            restart_count = cs.get("restartCount", 0)
            
            if restart_count > 0:
                issues.append(f"Container '{container_name}' has restarted {restart_count} times")
                recommendations.append(f"Check logs: kubectl logs {pod_name} -c {container_name} --previous")
            
            # Check waiting state
            waiting = cs.get("state", {}).get("waiting", {})
            if waiting:
                reason = waiting.get("reason", "Unknown")
                message = waiting.get("message", "")
                issues.append(f"Container '{container_name}' waiting: {reason} - {message}")
                
                if reason == "ImagePullBackOff":
                    recommendations.append("Check image name and registry credentials")
                elif reason == "CrashLoopBackOff":
                    recommendations.append("Check container logs for crash reason")
                elif reason == "CreateContainerConfigError":
                    recommendations.append("Check ConfigMaps and Secrets referenced by the pod")
            
            # Check terminated state
            terminated = cs.get("state", {}).get("terminated", {})
            if terminated:
                exit_code = terminated.get("exitCode", 0)
                reason = terminated.get("reason", "Unknown")
                if exit_code != 0:
                    issues.append(f"Container '{container_name}' exited with code {exit_code}: {reason}")
        
        # Check conditions
        conditions = status.get("conditions", [])
        for condition in conditions:
            if condition.get("status") != "True":
                cond_type = condition.get("type", "Unknown")
                reason = condition.get("reason", "")
                message = condition.get("message", "")
                if cond_type in ("Ready", "ContainersReady"):
                    issues.append(f"Condition {cond_type} is False: {reason} - {message}")
        
        # Check resource limits
        spec = pod_data.get("spec", {})
        containers = spec.get("containers", [])
        for container in containers:
            resources = container.get("resources", {})
            if not resources.get("limits"):
                issues.append(f"Container '{container.get('name')}' has no resource limits")
                recommendations.append("Set CPU and memory limits to prevent resource exhaustion")
        
        # Get recent events for this pod
        success, events_output = await self._run_kubectl(
            "get", "events", "-n", ns,
            "--field-selector", f"involvedObject.name={pod_name}",
            "--sort-by=.lastTimestamp",
        )
        
        if success:
            raw_data["events"] = events_output
            # Look for warning events
            for line in events_output.split("\n"):
                if "Warning" in line:
                    issues.append(f"Warning event: {line.strip()}")
        
        return DiagnosisResult(
            pod_name=pod_name,
            namespace=ns,
            status=phase,
            issues=issues,
            recommendations=recommendations,
            raw_data=raw_data,
        )
    
    async def check_deployment(
        self,
        deployment_name: str,
        namespace: Optional[str] = None,
    ) -> DeploymentCheckResult:
        """Check health and status of a deployment.
        
        Analyzes:
        - Replica counts (desired vs ready vs available)
        - Deployment conditions
        - Rollout status
        - Recent changes
        
        Args:
            deployment_name: Name of the deployment
            namespace: Namespace (defaults to agent's namespace)
            
        Returns:
            DeploymentCheckResult with health status and issues
        """
        ns = namespace or self.config.namespace
        issues: list[str] = []
        raw_data: dict[str, Any] = {}
        
        # Get deployment details
        success, deploy_data = await self._run_kubectl_json(
            "get", "deployment", deployment_name, "-n", ns,
        )
        
        if not success:
            return DeploymentCheckResult(
                deployment_name=deployment_name,
                namespace=ns,
                healthy=False,
                issues=[f"Failed to get deployment: {deploy_data}"],
            )
        
        raw_data["deployment"] = deploy_data
        
        # Parse replica counts
        spec = deploy_data.get("spec", {})
        status = deploy_data.get("status", {})
        
        replicas_desired = spec.get("replicas", 0)
        replicas_ready = status.get("readyReplicas", 0)
        replicas_available = status.get("availableReplicas", 0)
        replicas_updated = status.get("updatedReplicas", 0)
        
        # Check for replica mismatches
        if replicas_ready < replicas_desired:
            issues.append(f"Only {replicas_ready}/{replicas_desired} replicas ready")
        
        if replicas_available < replicas_desired:
            issues.append(f"Only {replicas_available}/{replicas_desired} replicas available")
        
        if replicas_updated < replicas_desired:
            issues.append(f"Rollout in progress: {replicas_updated}/{replicas_desired} updated")
        
        # Parse conditions
        conditions = status.get("conditions", [])
        parsed_conditions = []
        for cond in conditions:
            parsed_cond = {
                "type": cond.get("type"),
                "status": cond.get("status"),
                "reason": cond.get("reason"),
                "message": cond.get("message"),
            }
            parsed_conditions.append(parsed_cond)
            
            # Check for problematic conditions
            if cond.get("type") == "Available" and cond.get("status") != "True":
                issues.append(f"Deployment not available: {cond.get('reason')}")
            elif cond.get("type") == "Progressing":
                if cond.get("reason") == "ProgressDeadlineExceeded":
                    issues.append("Deployment progress deadline exceeded")
        
        # Check rollout status
        success, rollout_status = await self._run_kubectl(
            "rollout", "status", "deployment", deployment_name,
            "-n", ns, "--timeout=5s",
        )
        raw_data["rollout_status"] = rollout_status
        
        if not success and "successfully rolled out" not in rollout_status.lower():
            issues.append(f"Rollout issue: {rollout_status}")
        
        healthy = len(issues) == 0 and replicas_ready >= replicas_desired
        
        return DeploymentCheckResult(
            deployment_name=deployment_name,
            namespace=ns,
            healthy=healthy,
            replicas_desired=replicas_desired,
            replicas_ready=replicas_ready,
            replicas_available=replicas_available,
            conditions=parsed_conditions,
            issues=issues,
            raw_data=raw_data,
        )
    
    async def analyze_events(
        self,
        namespace: Optional[str] = None,
        involved_object: Optional[str] = None,
        event_types: Optional[list[str]] = None,
        since_minutes: int = 30,
    ) -> EventAnalysisResult:
        """Analyze Kubernetes events in a namespace.
        
        Filters and categorizes events to identify problems:
        - Warning events
        - Error-related events
        - Recent state changes
        
        Args:
            namespace: Namespace to analyze (defaults to agent's namespace)
            involved_object: Filter by object name
            event_types: Filter by event types (e.g., ["Warning"])
            since_minutes: Only include events from last N minutes
            
        Returns:
            EventAnalysisResult with categorized events
        """
        ns = namespace or self.config.namespace
        warnings: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        recent_events: list[dict[str, Any]] = []
        
        # Build kubectl command
        args = ["get", "events", "-n", ns, "--sort-by=.lastTimestamp"]
        
        if involved_object:
            args.extend(["--field-selector", f"involvedObject.name={involved_object}"])
        
        success, events_data = await self._run_kubectl_json(*args)
        
        if not success:
            return EventAnalysisResult(
                namespace=ns,
                summary=f"Failed to get events: {events_data}",
            )
        
        items = events_data.get("items", [])
        total_events = len(items)
        
        # Categorize events
        for event in items:
            event_type = event.get("type", "Normal")
            reason = event.get("reason", "")
            message = event.get("message", "")
            involved = event.get("involvedObject", {})
            
            event_summary = {
                "type": event_type,
                "reason": reason,
                "message": message,
                "object_kind": involved.get("kind"),
                "object_name": involved.get("name"),
                "count": event.get("count", 1),
                "last_timestamp": event.get("lastTimestamp"),
            }
            
            recent_events.append(event_summary)
            
            if event_type == "Warning":
                warnings.append(event_summary)
                
                # Identify error-like warnings
                error_reasons = [
                    "Failed", "Error", "BackOff", "Unhealthy",
                    "FailedScheduling", "FailedMount", "FailedAttach",
                ]
                if any(err in reason for err in error_reasons):
                    errors.append(event_summary)
        
        # Generate summary
        summary_parts = []
        if warnings:
            summary_parts.append(f"{len(warnings)} warning events")
        if errors:
            summary_parts.append(f"{len(errors)} error-related events")
        if not summary_parts:
            summary_parts.append("No warnings or errors found")
        
        summary = f"Analyzed {total_events} events: " + ", ".join(summary_parts)
        
        return EventAnalysisResult(
            namespace=ns,
            total_events=total_events,
            warnings=warnings,
            errors=errors,
            recent_events=recent_events[:20],  # Limit to 20 most recent
            summary=summary,
        )
    
    async def check_resources(
        self,
        namespace: Optional[str] = None,
        pod_selector: Optional[str] = None,
        include_nodes: bool = False,
    ) -> ResourceCheckResult:
        """Check resource utilization for pods and nodes.
        
        Requires metrics-server to be installed in the cluster.
        
        Args:
            namespace: Namespace to check (defaults to agent's namespace)
            pod_selector: Label selector for pods
            include_nodes: Also check node resources
            
        Returns:
            ResourceCheckResult with utilization data and issues
        """
        ns = namespace or self.config.namespace
        pods: list[dict[str, Any]] = []
        nodes: list[dict[str, Any]] = []
        issues: list[str] = []
        
        # Get pod resource usage
        args = ["top", "pods", "-n", ns, "--no-headers"]
        if pod_selector:
            args.extend(["-l", pod_selector])
        
        success, pod_output = await self._run_kubectl(*args)
        
        if not success:
            if "Metrics API not available" in pod_output or "metrics" in pod_output.lower():
                issues.append("Metrics server not available - cannot get resource usage")
            else:
                issues.append(f"Failed to get pod metrics: {pod_output}")
        else:
            # Parse pod metrics output
            # Format: NAME CPU(cores) MEMORY(bytes)
            for line in pod_output.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) >= 3:
                    pods.append({
                        "name": parts[0],
                        "cpu": parts[1],
                        "memory": parts[2],
                    })
        
        # Get pod resource limits for comparison
        success, pods_data = await self._run_kubectl_json(
            "get", "pods", "-n", ns,
            "-o", "jsonpath={range .items[*]}{.metadata.name},{.spec.containers[*].resources}{\"\\n\"}{end}",
        )
        
        # Get node resource usage if requested
        if include_nodes:
            success, node_output = await self._run_kubectl("top", "nodes", "--no-headers")
            
            if success:
                for line in node_output.strip().split("\n"):
                    if not line.strip():
                        continue
                    parts = line.split()
                    if len(parts) >= 5:
                        cpu_percent = parts[2].rstrip("%")
                        mem_percent = parts[4].rstrip("%")
                        
                        nodes.append({
                            "name": parts[0],
                            "cpu": parts[1],
                            "cpu_percent": cpu_percent,
                            "memory": parts[3],
                            "memory_percent": mem_percent,
                        })
                        
                        # Check for high utilization
                        try:
                            if int(cpu_percent) > 80:
                                issues.append(f"Node {parts[0]} CPU utilization high: {cpu_percent}%")
                            if int(mem_percent) > 85:
                                issues.append(f"Node {parts[0]} memory utilization high: {mem_percent}%")
                        except ValueError:
                            pass
        
        # Generate summary
        summary_parts = []
        if pods:
            summary_parts.append(f"{len(pods)} pods checked")
        if nodes:
            summary_parts.append(f"{len(nodes)} nodes checked")
        if issues:
            summary_parts.append(f"{len(issues)} issues found")
        
        summary = ", ".join(summary_parts) if summary_parts else "No data available"
        
        return ResourceCheckResult(
            namespace=ns,
            pods=pods,
            nodes=nodes,
            issues=issues,
            summary=summary,
        )
    
    # ----- Convenience methods -----
    
    async def get_pod_logs(
        self,
        pod_name: str,
        namespace: Optional[str] = None,
        container: Optional[str] = None,
        tail: int = 100,
        previous: bool = False,
    ) -> str:
        """Get logs from a pod.
        
        Args:
            pod_name: Name of the pod
            namespace: Namespace (defaults to agent's namespace)
            container: Container name (for multi-container pods)
            tail: Number of lines from end
            previous: Get logs from previous container instance
            
        Returns:
            Log output as string
        """
        ns = namespace or self.config.namespace
        args = ["logs", pod_name, "-n", ns, f"--tail={tail}"]
        
        if container:
            args.extend(["-c", container])
        if previous:
            args.append("--previous")
        
        success, output = await self._run_kubectl(*args)
        return output
    
    async def list_pods(
        self,
        namespace: Optional[str] = None,
        label_selector: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """List pods in a namespace.
        
        Args:
            namespace: Namespace (defaults to agent's namespace)
            label_selector: Label selector to filter pods
            
        Returns:
            List of pod dictionaries with name, status, restarts, etc.
        """
        ns = namespace or self.config.namespace
        args = ["get", "pods", "-n", ns]
        
        if label_selector:
            args.extend(["-l", label_selector])
        
        success, data = await self._run_kubectl_json(*args)
        
        if not success:
            return []
        
        pods = []
        for item in data.get("items", []):
            status = item.get("status", {})
            container_statuses = status.get("containerStatuses", [])
            
            total_restarts = sum(cs.get("restartCount", 0) for cs in container_statuses)
            
            pods.append({
                "name": item.get("metadata", {}).get("name"),
                "namespace": item.get("metadata", {}).get("namespace"),
                "phase": status.get("phase"),
                "restarts": total_restarts,
                "node": item.get("spec", {}).get("nodeName"),
                "ip": status.get("podIP"),
            })
        
        return pods


def create_k8s_agent(
    namespace: str = "default",
    kubeconfig: Optional[str] = None,
    context: Optional[str] = None,
    timeout_seconds: int = 30,
    dry_run: bool = False,
) -> K8sAgent:
    """Factory function to create a Kubernetes agent.
    
    Args:
        namespace: Default Kubernetes namespace
        kubeconfig: Path to kubeconfig file
        context: Kubernetes context to use
        timeout_seconds: Timeout for kubectl commands
        dry_run: If True, return mock data instead of real kubectl calls
        
    Returns:
        Configured K8sAgent instance
    """
    return K8sAgent(
        namespace=namespace,
        kubeconfig=kubeconfig,
        context=context,
        timeout_seconds=timeout_seconds,
        dry_run=dry_run,
    )
