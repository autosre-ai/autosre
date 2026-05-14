"""NLP for Operations in AutoSRE.

This module provides NLP capabilities for incident management:
- Incident classification
- Severity estimation
- Similar incident finding
- Summary generation
- Natural language command parsing
"""

from autosre.ml.nlp.classifier import IncidentClassifier, IncidentCategory
from autosre.ml.nlp.severity import SeverityEstimator, SeverityLevel, SeverityEstimate
from autosre.ml.nlp.similarity import SimilarityFinder, SimilarIncident
from autosre.ml.nlp.summarizer import SummaryGenerator, IncidentSummary
from autosre.ml.nlp.command import CommandParser, ParsedCommand, CommandType

__all__ = [
    "IncidentClassifier",
    "IncidentCategory",
    "SeverityEstimator",
    "SeverityLevel",
    "SeverityEstimate",
    "SimilarityFinder",
    "SimilarIncident",
    "SummaryGenerator",
    "IncidentSummary",
    "CommandParser",
    "ParsedCommand",
    "CommandType",
]
