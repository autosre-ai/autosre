"""
AI Telemetry Module

Track AI performance, accuracy, and reliability metrics.
Based on the principle: "AI needs reliability targets like any service"
"""

from .ai_metrics import (
    AIMetricsTracker,
    InvestigationRecord,
    get_ai_metrics,
)

from .error_budget import (
    AIErrorBudget,
    ErrorBudgetStatus,
    get_error_budget,
)

__all__ = [
    "AIMetricsTracker",
    "InvestigationRecord",
    "get_ai_metrics",
    "AIErrorBudget",
    "ErrorBudgetStatus",
    "get_error_budget",
]
