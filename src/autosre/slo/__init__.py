"""
AutoSRE V2 SLO Module.

SLO management with:
- SLODefinition: Define SLIs and objectives
- ErrorBudgetTracker: Track burn rate, remaining budget
- SLOReporter: Generate SLO reports
- AlertRules: Auto-generate Prometheus alerting rules

Example:
    from autosre.slo import SLODefinition, ErrorBudgetTracker

    slo = SLODefinition(
        name="api-availability",
        service="api-gateway",
        sli_type="availability",
        target=0.999,
    )

    tracker = ErrorBudgetTracker()
    status = tracker.evaluate(slo, metrics)
"""

from .definition import (
    SLODefinition,
    SLIType,
    SLIConfig,
    SLOWindow,
    SLOTarget,
    ServiceLevelObjective,
)

from .budget import (
    ErrorBudgetTracker,
    BudgetStatus,
    BudgetBurnRate,
    BudgetForecast,
    TrackerConfig,
)

from .reporter import (
    SLOReporter,
    SLOReport,
    ReportFormat,
    ReportConfig,
    WeeklyReport,
    MonthlyReport,
)

from .alerts import (
    AlertRuleGenerator,
    AlertRule,
    AlertSeverity,
    BurnRateAlert,
    ErrorBudgetAlert,
    MultiWindowAlert,
    RuleConfig,
)

__all__ = [
    # Definition
    "SLODefinition",
    "SLIType",
    "SLIConfig",
    "SLOWindow",
    "SLOTarget",
    "ServiceLevelObjective",
    # Budget
    "ErrorBudgetTracker",
    "BudgetStatus",
    "BudgetBurnRate",
    "BudgetForecast",
    "TrackerConfig",
    # Reporter
    "SLOReporter",
    "SLOReport",
    "ReportFormat",
    "ReportConfig",
    "WeeklyReport",
    "MonthlyReport",
    # Alerts
    "AlertRuleGenerator",
    "AlertRule",
    "AlertSeverity",
    "BurnRateAlert",
    "ErrorBudgetAlert",
    "MultiWindowAlert",
    "RuleConfig",
]
