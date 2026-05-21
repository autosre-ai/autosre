"""
AutoSRE Agent - LangGraph-based SRE Investigation System

This package provides a multi-agent system for automated incident investigation.
The core graph orchestrates:

- **init_context**: Validates alert and loads team config
- **memory_lookup**: Searches past similar incidents
- **kg_context**: Fetches service topology from knowledge graph
- **planner**: Generates hypotheses and selects investigation agents
- **subagent**: Executes domain-specific investigation (k8s, metrics, logs, etc.)
- **synthesizer**: Combines findings and decides to loop or conclude
- **writeup**: Generates structured investigation report
- **memory_store**: Persists investigation for future lookups

Usage:
    from agent.graph import get_graph
    
    graph = get_graph()
    result = graph.invoke({
        "alert": {"name": "HighErrorRate", "service": "api-gateway"},
        "thread_id": "investigation-1",
    })
"""

from .graph import build_graph, get_graph, create_app
from .state import GraphState, Hypothesis, InvestigationPlan, SynthesisDecision, AgentResult
from .config import (
    AgentConfig,
    ModelConfig,
    PromptConfig,
    TeamConfig,
    load_team_config,
    build_llm,
)

__version__ = "0.1.0"

__all__ = [
    # Graph
    "build_graph",
    "get_graph",
    "create_app",
    
    # State
    "GraphState",
    "Hypothesis",
    "InvestigationPlan",
    "SynthesisDecision",
    "AgentResult",
    
    # Config
    "AgentConfig",
    "ModelConfig",
    "PromptConfig",
    "TeamConfig",
    "load_team_config",
    "build_llm",
]
