"""
Feedback Loop - Learn from incident outcomes.

Provides:
- Incident outcome tracking
- Human feedback capture
- Correction logging
- Fine-tuning data export
"""

from autosre.feedback.tracker import FeedbackTracker, Feedback, IncidentOutcome
from autosre.feedback.learning import LearningPipeline

__all__ = [
    "FeedbackTracker",
    "Feedback",
    "IncidentOutcome",
    "LearningPipeline",
]
