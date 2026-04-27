"""
AutoSRE - Open-source AI SRE Agent

Built foundation-first: context store, evals, sandbox, then agent logic.
"""

__version__ = "0.1.0"
__author__ = "OpenSRE Community"

from autosre.foundation.context_store import ContextStore
from autosre.foundation.models import Service, Ownership, ChangeEvent

__all__ = [
    "ContextStore",
    "Service",
    "Ownership", 
    "ChangeEvent",
    "__version__",
]
