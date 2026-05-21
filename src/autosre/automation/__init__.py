"""Automation evolution for AutoSRE.

Key principles:
- Automation is a force multiplier, not a panacea
- Best: systems that need neither automation NOR manual operation
- "If a human needs to touch during normal ops, you have a bug"
"""

from .maturity import AutomationMaturityModel, MaturityLevel, MaturityAssessment
from .roi import AutomationROICalculator, ROIFactors, ROIAssessment

__all__ = [
    "AutomationMaturityModel",
    "MaturityLevel",
    "MaturityAssessment",
    "AutomationROICalculator",
    "ROIFactors",
    "ROIAssessment",
]
