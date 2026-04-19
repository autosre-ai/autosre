"""
OpenSRE — AI-Powered Incident Response
"""

__version__ = "0.1.0"

from opensre_core.learning import IncidentStore, PatternRecognizer, StoredIncident

__all__ = [
    "__version__",
    "IncidentStore",
    "StoredIncident",
    "PatternRecognizer",
]
