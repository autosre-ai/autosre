"""
AutoSRE - Open-source AI SRE Agent

Built foundation-first: context store, evals, sandbox, then agent logic.

v2 Architecture:
- Orchestrator: Investigation flow coordination
- Memory: Episodic memory for past incidents
- Topology: Service graph and dependencies
- Agents: Planner, Synthesizer, Writeup
- LLM: Multi-provider routing
- Skills: Kubernetes, Metrics, Logs
"""

__version__ = "0.2.0"
__author__ = "OpenSRE Community"

# Core v2 exports
from autosre.orchestrator import Orchestrator, Investigation
from autosre.memory import EpisodicMemory, Episode, MemoryQuery
from autosre.topology import ServiceGraph, ServiceNode
from autosre.agents import (
    Alert,
    Hypothesis,
    Evidence,
    AgentResult,
    InvestigationState,
    InvestigationPlan,
    Planner,
    AVAILABLE_AGENTS,
    Synthesizer,
    Synthesis,
    WriteupGenerator,
    IncidentReport,
)
from autosre.llm import LLMRouter
from autosre.reporters import TerminalReporter

# Foundation (v1) exports - maintained for compatibility
from autosre.foundation.context_store import ContextStore
from autosre.foundation.models import Service, Ownership, ChangeEvent
from autosre.logging import get_logger, configure_logging
from autosre.exceptions import (
    AutoSREError,
    ConfigurationError,
    ConnectionError,
    ContextError,
    AgentError,
    SandboxError,
    EvalError,
)

__all__ = [
    # Version
    "__version__",
    # Core v2
    "Orchestrator",
    "Investigation",
    "EpisodicMemory",
    "Episode",
    "MemoryQuery",
    "ServiceGraph",
    "ServiceNode",
    "Alert",
    "Hypothesis",
    "Evidence",
    "AgentResult",
    "InvestigationState",
    "InvestigationPlan",
    "Planner",
    "AVAILABLE_AGENTS",
    "Synthesizer",
    "Synthesis",
    "WriteupGenerator",
    "IncidentReport",
    "LLMRouter",
    "TerminalReporter",
    # Foundation (v1)
    "ContextStore",
    "Service",
    "Ownership",
    "ChangeEvent",
    # Logging
    "get_logger",
    "configure_logging",
    # Exceptions
    "AutoSREError",
    "ConfigurationError",
    "ConnectionError",
    "ContextError",
    "AgentError",
    "SandboxError",
    "EvalError",
]
