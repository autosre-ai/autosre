"""OpenSRE tools for ADK agents.

This module wraps OpenSRE adapters as ADK-compatible tools
that can be used by LLM agents for incident investigation.
"""

import asyncio

from google.adk.tools import FunctionTool


def _run_async(coro):
    """Run async coroutine in sync context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're in an async context, create a new event loop in a thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)


def create_prometheus_tools() -> list[FunctionTool]:
    """Create Prometheus query tools for ADK agents.

    Returns:
        List of FunctionTool objects for Prometheus operations
    """

    def query_prometheus(query: str) -> str:
        """Execute a PromQL query against Prometheus.

        Args:
            query: The PromQL query to execute (e.g., 'up', 'rate(http_requests_total[5m])')

        Returns:
            Query results formatted as a string with metric names and values
        """
        from opensre_core.adapters.prometheus import PrometheusAdapter

        adapter = PrometheusAdapter()
        results = _run_async(adapter.query(query))

        if not results:
            return "No results found for query"

        output = []
        for metric in results:
            labels_str = ", ".join(f"{k}={v}" for k, v in metric.labels.items())
            value_str = f"{metric.current_value:.4f}" if metric.current_value is not None else "N/A"
            output.append(f"- {metric.metric_name}{{{labels_str}}}: {value_str}")

        return "\n".join(output) if output else "No metrics returned"

    def get_firing_alerts() -> str:
        """Get all currently firing Prometheus alerts.

        Returns:
            List of firing alerts with name, severity, and summary
        """
        from opensre_core.adapters.prometheus import PrometheusAdapter

        adapter = PrometheusAdapter()
        alerts = _run_async(adapter.get_alerts(state="firing"))

        if not alerts:
            return "No firing alerts"

        output = []
        for alert in alerts:
            severity = alert.labels.get("severity", "unknown")
            summary = alert.annotations.get("summary", alert.annotations.get("description", "No description"))
            output.append(f"- {alert.alert_name} ({severity}): {summary}")

        return "\n".join(output)

    def get_service_metrics(service: str, namespace: str = "default") -> str:
        """Get common SRE metrics for a service (CPU, memory, request rate, errors, latency).

        Args:
            service: Name of the service to query
            namespace: Kubernetes namespace (default: "default")

        Returns:
            Formatted metrics including CPU usage, memory, request rate, error rate, and P99 latency
        """
        from opensre_core.adapters.prometheus import PrometheusAdapter

        adapter = PrometheusAdapter()
        metrics = _run_async(adapter.get_service_metrics(service, namespace))

        output = [f"Service Metrics for {service} in {namespace}:"]
        for name, value in metrics.items():
            if value is not None:
                if "rate" in name:
                    output.append(f"  {name}: {value:.2%}")
                elif "latency" in name:
                    output.append(f"  {name}: {value:.3f}s")
                else:
                    output.append(f"  {name}: {value:.4f}")
            else:
                output.append(f"  {name}: N/A")

        return "\n".join(output)

    return [
        FunctionTool(query_prometheus),
        FunctionTool(get_firing_alerts),
        FunctionTool(get_service_metrics),
    ]


def create_kubernetes_tools() -> list[FunctionTool]:
    """Create Kubernetes tools for ADK agents.

    Returns:
        List of FunctionTool objects for Kubernetes operations
    """

    def get_pods(namespace: str = "default") -> str:
        """Get pods in a Kubernetes namespace with their status.

        Args:
            namespace: The Kubernetes namespace (default: "default", use "all" for all namespaces)

        Returns:
            List of pods with name, status, restarts, and age
        """
        from opensre_core.adapters.kubernetes import KubernetesAdapter

        adapter = KubernetesAdapter()
        pods = _run_async(adapter.get_pods(namespace))

        if not pods:
            return f"No pods found in namespace {namespace}"

        output = [f"Pods in {namespace}:"]
        for pod in pods:
            status_icon = "✓" if pod.ready else "✗"
            output.append(f"  {status_icon} {pod.name}: {pod.status} (restarts: {pod.restarts}, age: {pod.age})")

        return "\n".join(output)

    def get_pod_logs(pod_name: str, namespace: str = "default", lines: int = 100) -> str:
        """Get logs from a Kubernetes pod.

        Args:
            pod_name: Name of the pod
            namespace: Kubernetes namespace (default: "default")
            lines: Number of log lines to return (default: 100)

        Returns:
            Pod logs as a string
        """
        from opensre_core.adapters.kubernetes import KubernetesAdapter

        adapter = KubernetesAdapter()
        logs = _run_async(adapter.get_pod_logs(pod_name, namespace, tail_lines=lines))

        if not logs:
            return f"No logs available for pod {pod_name}"

        return f"Logs for {pod_name} (last {lines} lines):\n{logs}"

    def get_events(namespace: str = "default", minutes: int = 15) -> str:
        """Get recent warning events in a Kubernetes namespace.

        Args:
            namespace: Kubernetes namespace (default: "default", use "all" for all namespaces)
            minutes: Only show events from the last N minutes (default: 15)

        Returns:
            List of warning events with type, reason, and message
        """
        from opensre_core.adapters.kubernetes import KubernetesAdapter

        adapter = KubernetesAdapter()
        events = _run_async(adapter.get_events(namespace, minutes=minutes))

        # Filter to warnings
        warnings = [e for e in events if e.type == "Warning"]

        if not warnings:
            return f"No warning events in the last {minutes} minutes"

        output = [f"Warning events in {namespace} (last {minutes} min):"]
        for event in warnings:
            output.append(f"  - [{event.reason}] {event.involved_object}: {event.message}")

        return "\n".join(output)

    def describe_pod(pod_name: str, namespace: str = "default") -> str:
        """Get detailed information about a specific pod.

        Args:
            pod_name: Name of the pod to describe
            namespace: Kubernetes namespace (default: "default")

        Returns:
            Detailed pod information including containers, status, and events
        """
        from opensre_core.adapters.kubernetes import KubernetesAdapter

        adapter = KubernetesAdapter()
        pod = _run_async(adapter.get_pod(pod_name, namespace))

        output = [
            f"Pod: {pod.name}",
            f"  Namespace: {pod.namespace}",
            f"  Status: {pod.status}",
            f"  Ready: {pod.ready}",
            f"  Node: {pod.node}",
            f"  Restarts: {pod.restarts}",
            f"  Age: {pod.age}",
            "",
            "Containers:",
        ]

        for container in pod.containers:
            output.append(f"  - {container['name']}: {container['state']} (restarts: {container['restarts']})")

        if pod.events:
            output.append("")
            output.append("Recent Events:")
            for event in pod.events[:5]:
                output.append(f"  - [{event['type']}] {event['reason']}: {event['message']}")

        return "\n".join(output)

    def get_deployment(name: str, namespace: str = "default") -> str:
        """Get deployment status and replica information.

        Args:
            name: Deployment name
            namespace: Kubernetes namespace (default: "default")

        Returns:
            Deployment status including replica counts and conditions
        """
        from opensre_core.adapters.kubernetes import KubernetesAdapter

        adapter = KubernetesAdapter()
        deploy = _run_async(adapter.get_deployment(name, namespace))

        output = [
            f"Deployment: {deploy.name}",
            f"  Namespace: {deploy.namespace}",
            f"  Replicas: {deploy.ready_replicas}/{deploy.replicas} ready, {deploy.available_replicas} available",
            f"  Strategy: {deploy.strategy}",
            "",
            "Conditions:",
        ]

        for condition in deploy.conditions:
            output.append(f"  - {condition['type']}: {condition['status']} ({condition.get('reason', 'N/A')})")

        return "\n".join(output)

    return [
        FunctionTool(get_pods),
        FunctionTool(get_pod_logs),
        FunctionTool(get_events),
        FunctionTool(describe_pod),
        FunctionTool(get_deployment),
    ]


def create_action_tools() -> list[FunctionTool]:
    """Create remediation action tools for ADK agents.

    These tools can modify cluster state and should be used cautiously.

    Returns:
        List of FunctionTool objects for remediation actions
    """

    def restart_pod(pod_name: str, namespace: str = "default") -> str:
        """Restart a pod by deleting it (will be recreated by its controller).

        WARNING: This is a destructive action. The pod will be terminated and recreated.
        Only use this if the pod is unhealthy and needs to be restarted.

        Args:
            pod_name: Name of the pod to restart
            namespace: Kubernetes namespace (default: "default")

        Returns:
            Result of the operation
        """
        from kubernetes import client, config
        from kubernetes.client.exceptions import ApiException

        try:
            config.load_kube_config()
        except config.ConfigException:
            config.load_incluster_config()

        v1 = client.CoreV1Api()

        try:
            v1.delete_namespaced_pod(name=pod_name, namespace=namespace)
            return f"✓ Pod {pod_name} deleted. Controller will recreate it."
        except ApiException as e:
            return f"✗ Failed to delete pod: {e.reason}"

    def scale_deployment(name: str, replicas: int, namespace: str = "default") -> str:
        """Scale a deployment to a specific number of replicas.

        Args:
            name: Deployment name
            replicas: Target replica count (must be >= 0)
            namespace: Kubernetes namespace (default: "default")

        Returns:
            Result of the scale operation
        """
        from opensre_core.adapters.kubernetes import KubernetesAdapter

        if replicas < 0:
            return "✗ Replica count must be >= 0"

        adapter = KubernetesAdapter()
        result = _run_async(adapter.scale_deployment(name, replicas, namespace, dry_run=False))

        if result.get("success"):
            return f"✓ Deployment {name} scaled to {replicas} replicas."
        else:
            return f"✗ Failed to scale: {result.get('error', 'Unknown error')}"

    def rollout_restart(deployment: str, namespace: str = "default") -> str:
        """Perform a rolling restart of a deployment.

        This triggers a rolling update that restarts all pods in the deployment
        without downtime (respects PodDisruptionBudget).

        Args:
            deployment: Name of the deployment to restart
            namespace: Kubernetes namespace (default: "default")

        Returns:
            Result of the rollout restart
        """
        from opensre_core.adapters.kubernetes import KubernetesAdapter

        adapter = KubernetesAdapter()
        result = _run_async(adapter.rollout_restart(deployment, namespace, dry_run=False))

        if result.get("success"):
            return f"✓ Rollout restart initiated for deployment/{deployment}"
        else:
            return f"✗ Failed: {result.get('error', 'Unknown error')}"

    return [
        FunctionTool(restart_pod),
        FunctionTool(scale_deployment),
        FunctionTool(rollout_restart),
    ]
