"""
Agent Core - The AI SRE reasoning engine.

The agent follows the Observer-Reasoner-Actor pattern:
1. Observer: Watch for alerts and anomalies
2. Reasoner: Analyze context and determine root cause
3. Actor: Execute remediation with guardrails
"""

from autosre.agent.observer import AlertWatcher, MetricAnalyzer, LogCorrelator, ChangeDetector
from autosre.agent.reasoner import Reasoner, ReasonerConfig
from autosre.agent.actor import Actor, ActionResult
from autosre.agent.guardrails import Guardrails, ApprovalRequest

__all__ = [
    "AlertWatcher",
    "MetricAnalyzer",
    "LogCorrelator",
    "ChangeDetector",
    "Reasoner",
    "ReasonerConfig",
    "Actor",
    "ActionResult",
    "Guardrails",
    "ApprovalRequest",
]
