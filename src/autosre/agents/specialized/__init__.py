"""
AutoSRE Specialized Agents — Domain-specific expert agents for SRE tasks.

These agents provide deeper expertise in specific domains compared to
the general investigation subagents. They're designed to be used directly
or composed into larger workflows.
"""

from .kubernetes_agent import K8sAgent, create_k8s_agent
from .database_agent import DatabaseAgent, create_database_agent

__all__ = [
    # Kubernetes
    "K8sAgent",
    "create_k8s_agent",
    # Database
    "DatabaseAgent",
    "create_database_agent",
]


# Registry of available specialized agents
SPECIALIZED_AGENT_REGISTRY = {
    "kubernetes": K8sAgent,
    "k8s": K8sAgent,  # alias
    "database": DatabaseAgent,
    "db": DatabaseAgent,  # alias
}


def get_specialized_agent(agent_id: str, **kwargs):
    """Get a specialized agent by ID.
    
    Args:
        agent_id: Agent identifier (kubernetes, k8s, database, db)
        **kwargs: Additional arguments passed to agent constructor.
        
    Returns:
        Instantiated specialized agent.
        
    Raises:
        ValueError: If agent_id not found.
    """
    if agent_id not in SPECIALIZED_AGENT_REGISTRY:
        available = list(SPECIALIZED_AGENT_REGISTRY.keys())
        raise ValueError(f"Unknown specialized agent: {agent_id}. Available: {available}")
    
    return SPECIALIZED_AGENT_REGISTRY[agent_id](**kwargs)


def list_specialized_agents() -> list[str]:
    """List all available specialized agent IDs (canonical names only)."""
    return ["kubernetes", "database"]
