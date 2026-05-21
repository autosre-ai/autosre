"""
SLO (Service Level Objective) Module

Provides error budget calculation, availability tracking, and SLO context
for incident investigation and deployment decisions.
"""

from .error_budget import (
    ErrorBudget,
    ErrorBudgetCalculator,
    ErrorBudgetStatus,
    DeploymentDecision,
)
from .availability import (
    AvailabilityCalculator,
    ServiceAvailability,
    EndpointAvailability,
    AvailabilityTracker,
)
from .context import (
    SLOContextProvider,
    SLOContext,
    IncidentBudgetImpact,
)
from .config import (
    SLOConfig,
    SLODefinition,
    SLOType,
    AlertConfig,
    AlertSeverity,
    LatencyTarget,
    CascadeThresholds,
    RecoveryDefaults,
    generate_example_config,
)

__all__ = [
    # Error Budget
    "ErrorBudget",
    "ErrorBudgetCalculator",
    "ErrorBudgetStatus",
    "DeploymentDecision",
    # Availability
    "AvailabilityCalculator",
    "ServiceAvailability",
    "EndpointAvailability",
    "AvailabilityTracker",
    # Context
    "SLOContextProvider",
    "SLOContext",
    "IncidentBudgetImpact",
    # Config
    "SLOConfig",
    "SLODefinition",
    "SLOType",
    "AlertConfig",
    "AlertSeverity",
    "LatencyTarget",
    "CascadeThresholds",
    "RecoveryDefaults",
    "generate_example_config",
]
