"""AutoSRE Subagents — Domain-specific investigation agents."""

from .base import BaseSubagent, SubagentConfig, MockSubagent, run_subagents_parallel
from .kubernetes import KubernetesSubagent, create_kubernetes_subagent
from .metrics import MetricsSubagent, create_metrics_subagent
from .logs import LogsSubagent, create_logs_subagent

__all__ = [
    # Base
    "BaseSubagent",
    "SubagentConfig",
    "MockSubagent",
    "run_subagents_parallel",
    # Kubernetes
    "KubernetesSubagent",
    "create_kubernetes_subagent",
    # Metrics
    "MetricsSubagent",
    "create_metrics_subagent",
    # Logs
    "LogsSubagent",
    "create_logs_subagent",
]


# Registry of available subagents
SUBAGENT_REGISTRY = {
    "kubernetes": KubernetesSubagent,
    "k8s": KubernetesSubagent,  # alias
    "metrics": MetricsSubagent,
    "logs": LogsSubagent,
    "log_analysis": LogsSubagent,  # alias
}


def get_subagent(agent_id: str, **kwargs) -> BaseSubagent:
    """Get a subagent by ID.
    
    Args:
        agent_id: Subagent identifier (kubernetes, metrics, logs, etc.)
        **kwargs: Additional arguments passed to subagent constructor.
        
    Returns:
        Instantiated subagent.
        
    Raises:
        ValueError: If agent_id not found.
    """
    if agent_id not in SUBAGENT_REGISTRY:
        raise ValueError(f"Unknown subagent: {agent_id}. Available: {list(SUBAGENT_REGISTRY.keys())}")
    
    return SUBAGENT_REGISTRY[agent_id](**kwargs)


def list_subagents() -> list[str]:
    """List all available subagent IDs."""
    # Remove aliases, return canonical names
    return ["kubernetes", "metrics", "logs"]
