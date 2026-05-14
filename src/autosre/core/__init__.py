"""AutoSRE V2 Core module."""

from autosre.core.config import Settings, get_settings
from autosre.core.alert import (
    Alert,
    AlertSeverity,
    AlertStatus,
    AlertSource,
    AlertGroup,
)
from autosre.core.investigation import (
    Investigation,
    InvestigationStatus,
    Hypothesis,
    HypothesisStatus,
    Evidence,
    EvidenceType,
    Finding,
    InvestigationResult,
)
from autosre.core.models import (
    Observation,
    ObservationType,
    Action,
    ActionType,
    ActionStatus,
    Report,
)
from autosre.core.prompts import PromptTemplates

__all__ = [
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
    # Models (from models.py - legacy)
    "Observation",
    "ObservationType",
    "Action",
    "ActionType",
    "ActionStatus",
    "Report",
    # Prompts
    "PromptTemplates",
]
