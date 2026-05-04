"""
AutoSRE v2 — AI-Powered SRE Agent

A world-class open-source SRE agent that investigates production incidents
autonomously using episodic memory, multi-agent investigation, and 
service topology awareness.

Example:
    >>> from autosre import Orchestrator, investigate
    >>> 
    >>> # Quick investigation
    >>> report = await investigate("checkout-service 5xx spike")
    >>> print(report.root_cause)
    >>>
    >>> # With custom config
    >>> orch = Orchestrator()
    >>> report = await orch.investigate({
    ...     "name": "HighErrorRate",
    ...     "service": "payment-service",
    ...     "severity": "critical",
    ... })
"""

__version__ = "2.0.0-alpha.1"
__author__ = "Sainath + Clawd"

from .config import Settings, get_settings, configure
from .orchestrator import Orchestrator, investigate

# Re-export commonly used classes
from .agents import (
    InvestigationState,
    InvestigationStatus,
    InvestigationReport,
    Hypothesis,
    Evidence,
)
from .memory import EpisodicMemory, Episode
from .topology import ServiceTopology, load_topology

__all__ = [
    # Version
    "__version__",
    # Config
    "Settings",
    "get_settings",
    "configure",
    # Orchestrator
    "Orchestrator",
    "investigate",
    # State
    "InvestigationState",
    "InvestigationStatus",
    "InvestigationReport",
    "Hypothesis",
    "Evidence",
    # Memory
    "EpisodicMemory",
    "Episode",
    # Topology
    "ServiceTopology",
    "load_topology",
]
