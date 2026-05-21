"""Toil tracking and elimination for AutoSRE.

Based on SRE principles:
- Toil is manual, repetitive, automatable work with no enduring value
- Keep toil under 50% to maintain engineering capacity
- "If a human needs to touch during normal ops, you have a bug"
"""

from .classifier import ToilClassifier, ToilAssessment, TOIL_CRITERIA
from .budget import ToilBudgetTracker, TOIL_CAP
from .dashboard import ToilDashboard

__all__ = [
    "ToilClassifier",
    "ToilAssessment", 
    "TOIL_CRITERIA",
    "ToilBudgetTracker",
    "TOIL_CAP",
    "ToilDashboard",
]
