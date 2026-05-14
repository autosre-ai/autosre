"""AutoSRE V2 - LLM-powered incident investigation and remediation."""

from autosre.core import (
    # Config
    Settings,
    get_settings,
    # Alert
    Alert,
    AlertSeverity,
    AlertStatus,
    AlertSource,
    AlertGroup,
    # Investigation
    Investigation,
    InvestigationStatus,
    Hypothesis,
    HypothesisStatus,
    Evidence,
    EvidenceType,
    Finding,
    InvestigationResult,
    # Models (from models.py - legacy compatibility)
    Observation,
    ObservationType,
    Action,
    ActionType,
    ActionStatus,
    Report,
    # Prompts
    PromptTemplates,
)

__version__ = "2.0.0"

__all__ = [
    "__version__",
    # Config
    "Settings",
    "get_settings",
    # Alert
    "Alert",
    "AlertSeverity",
    "AlertStatus",
    "AlertSource",
    "AlertGroup",
    # Investigation
    "Investigation",
    "InvestigationStatus",
    "Hypothesis",
    "HypothesisStatus",
    "Evidence",
    "EvidenceType",
    "Finding",
    "InvestigationResult",
    # Models
    "Observation",
    "ObservationType",
    "Action",
    "ActionType",
    "ActionStatus",
    "Report",
    # Prompts
    "PromptTemplates",
]
