"""AutoSRE Subagents — Domain-specific investigation agents with ReAct loop."""

from .base import (
    BaseSubagent,
    SubagentConfig,
    MockSubagent,
    run_subagents_parallel,
)
from .react import (
    Tool,
    ToolCall,
    ToolResult,
    ReactConfig,
    ReactDecision,
    Message,
    react_loop,
    create_tool,
    hash_tool_call,
    trim_old_messages,
)
from .kubernetes import KubernetesSubagent, create_kubernetes_subagent
from .metrics import MetricsSubagent, create_metrics_subagent
from .logs import LogsSubagent, create_logs_subagent
from .changes import ChangesSubagent, create_changes_subagent

__all__ = [
    # Base
    "BaseSubagent",
    "SubagentConfig",
    "MockSubagent",
    "run_subagents_parallel",
    # ReAct loop
    "Tool",
    "ToolCall",
    "ToolResult",
    "ReactConfig",
    "ReactDecision",
    "Message",
    "react_loop",
    "create_tool",
    "hash_tool_call",
    "trim_old_messages",
    # Kubernetes
    "KubernetesSubagent",
    "create_kubernetes_subagent",
    # Metrics
    "MetricsSubagent",
    "create_metrics_subagent",
    # Logs
    "LogsSubagent",
    "create_logs_subagent",
    # Changes
    "ChangesSubagent",
    "create_changes_subagent",
]


# Registry of available subagents
SUBAGENT_REGISTRY = {
    "kubernetes": KubernetesSubagent,
    "k8s": KubernetesSubagent,  # alias
    "metrics": MetricsSubagent,
    "logs": LogsSubagent,
    "log_analysis": LogsSubagent,  # alias
    "changes": ChangesSubagent,
    "recent_changes": ChangesSubagent,  # alias
}


def get_subagent(agent_id: str, **kwargs) -> BaseSubagent:
    """Get a subagent by ID.
    
    Args:
        agent_id: Subagent identifier (kubernetes, metrics, logs, changes, etc.)
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
    return ["kubernetes", "metrics", "logs", "changes"]
