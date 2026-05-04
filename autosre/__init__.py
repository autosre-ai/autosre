"""
AutoSRE v2 — AI-Powered SRE Agent

A world-class open-source SRE agent that investigates production incidents
autonomously using episodic memory, multi-agent investigation, and 
service topology awareness.

Example:
    >>> from autosre import Orchestrator
    >>> orch = Orchestrator()
    >>> result = await orch.investigate("checkout-service 5xx spike")
    >>> print(result.root_cause)
"""

__version__ = "2.0.0-alpha.1"
__author__ = "Sainath + Clawd"

from .config import Settings

__all__ = [
    "Settings",
    "__version__",
]
