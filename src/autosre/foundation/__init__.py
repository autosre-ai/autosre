"""
Foundation Layer - The bedrock of AutoSRE

This layer provides context that the agent needs to reason about incidents:
- Service topology (what services exist, how they connect)
- Ownership mapping (who owns what)
- Change history (what changed recently)
- Runbooks (documented remediation procedures)
"""

from autosre.foundation.context_store import ContextStore
from autosre.foundation.models import (
    Service,
    Ownership,
    ChangeEvent,
    Runbook,
    Alert,
    Incident,
)

__all__ = [
    "ContextStore",
    "Service",
    "Ownership",
    "ChangeEvent",
    "Runbook",
    "Alert",
    "Incident",
]
