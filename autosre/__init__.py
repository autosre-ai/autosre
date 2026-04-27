"""
AutoSRE - Open-source AI SRE Agent

Built foundation-first: context store, evals, sandbox, then agent logic.
"""

__version__ = "0.1.0"
__author__ = "OpenSRE Community"

from autosre.foundation.context_store import ContextStore
from autosre.foundation.models import Service, Ownership, ChangeEvent
from autosre.logging import get_logger, configure_logging
from autosre.exceptions import (
    AutoSREError,
    ConfigurationError,
    ConnectionError,
    ContextError,
    AgentError,
    SandboxError,
    EvalError,
)

__all__ = [
    # Core
    "ContextStore",
    "Service",
    "Ownership", 
    "ChangeEvent",
    # Logging
    "get_logger",
    "configure_logging",
    # Exceptions
    "AutoSREError",
    "ConfigurationError",
    "ConnectionError",
    "ContextError",
    "AgentError",
    "SandboxError",
    "EvalError",
    # Version
    "__version__",
]
