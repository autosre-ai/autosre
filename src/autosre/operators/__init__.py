"""
AutoSRE Kubernetes Operators Package

Provides Kopf-based Kubernetes operators for managing AutoSRE custom resources:
- Investigation Controller: Manages Investigation CRDs
- Alert Controller: Manages Alert CRDs and triggers investigations
- Runbook Controller: Manages Runbook CRDs and executions

Usage:
    kopf run -m autosre.operators --standalone
    
Or with the CLI:
    autosre operator run --all
"""

from typing import TYPE_CHECKING

# Lazy imports for optional kopf dependency
if TYPE_CHECKING:
    from autosre.operators.investigation_controller import (
        InvestigationController,
        investigation_create_handler,
        investigation_update_handler,
        investigation_delete_handler,
    )
    from autosre.operators.alert_controller import (
        AlertController,
        alert_create_handler,
        alert_update_handler,
        alert_delete_handler,
    )

__all__ = [
    "InvestigationController",
    "AlertController",
    "investigation_create_handler",
    "investigation_update_handler",
    "investigation_delete_handler",
    "alert_create_handler",
    "alert_update_handler",
    "alert_delete_handler",
]

# CRD Group and versions
CRD_GROUP = "autosre.io"
CRD_VERSION = "v1alpha1"

# Resource kinds
INVESTIGATION_KIND = "Investigation"
ALERT_KIND = "Alert"
RUNBOOK_KIND = "Runbook"

# Status phases
class InvestigationPhase:
    """Investigation lifecycle phases."""
    PENDING = "Pending"
    RUNNING = "Running"
    ANALYZING = "Analyzing"
    WAITING_FOR_APPROVAL = "WaitingForApproval"
    REMEDIATING = "Remediating"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


class AlertState:
    """Alert states."""
    FIRING = "Firing"
    ACKNOWLEDGED = "Acknowledged"
    INVESTIGATING = "Investigating"
    RESOLVED = "Resolved"
    SILENCED = "Silenced"
    EXPIRED = "Expired"


class RunbookState:
    """Runbook states."""
    READY = "Ready"
    DISABLED = "Disabled"
    ERROR = "Error"
    DEPRECATED = "Deprecated"


def check_kopf_installed() -> bool:
    """Check if kopf is installed."""
    try:
        import kopf
        return True
    except ImportError:
        return False


def run_operators(
    namespaces: list[str] | None = None,
    standalone: bool = True,
    verbose: bool = False,
):
    """
    Run all AutoSRE operators.
    
    Args:
        namespaces: List of namespaces to watch (None = all namespaces)
        standalone: Run in standalone mode
        verbose: Enable verbose logging
    """
    if not check_kopf_installed():
        raise ImportError(
            "Kopf is required to run operators. "
            "Install with: pip install kopf"
        )
    
    import kopf
    import asyncio
    import logging
    
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    # Import handlers to register them with kopf
    from autosre.operators import investigation_controller
    from autosre.operators import alert_controller
    
    # Run kopf
    kwargs = {}
    if namespaces:
        kwargs['namespaces'] = namespaces
    if standalone:
        kwargs['standalone'] = standalone
    
    kopf.run(**kwargs)
