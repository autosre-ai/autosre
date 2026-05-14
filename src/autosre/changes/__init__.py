"""
AutoSRE V2 Change Management.

This module provides change management capabilities:
- ChangeTracker: Track all changes (deploys, configs)
- ImpactAnalyzer: Assess change impact
- CorrelationEngine: Link incidents to recent changes
- ChangeWindow: Enforce change windows (via models)

Example:
    from autosre.changes import ChangeTracker, CorrelationEngine
    
    tracker = ChangeTracker()
    
    change = await tracker.record_change(
        change_type="deployment",
        resource="api-server",
        namespace="production",
    )
    
    # Later, when an incident occurs
    correlator = CorrelationEngine(tracker)
    related = await correlator.find_related_changes(incident)
"""

from autosre.changes.models import (
    Change,
    ChangeType,
    ChangeStatus,
    ChangeImpact,
    ChangeRisk,
    ChangeWindow,
    ChangeWindowType,
)

from autosre.changes.tracker import ChangeTracker
from autosre.changes.impact import ImpactAnalyzer
from autosre.changes.correlation import CorrelationEngine

__all__ = [
    # Models
    "Change",
    "ChangeType",
    "ChangeStatus",
    "ChangeImpact",
    "ChangeRisk",
    "ChangeWindow",
    "ChangeWindowType",
    # Tracker
    "ChangeTracker",
    # Impact
    "ImpactAnalyzer",
    # Correlation
    "CorrelationEngine",
]
