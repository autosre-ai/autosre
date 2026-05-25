"""
SLO Management for AutoSRE.

Comprehensive Service Level Objective management capabilities including:
- SLO/SLI definitions with multiple indicator types
- Error budget tracking and burn rate calculation
- Multi-window multi-burn-rate alerting
- SLO reporting and trend analysis

v2.10 Features:
- SLODefinition: Define SLOs with targets and SLIs
- ErrorBudget: Track budget consumption and burn rates
- SLOReport: Generate compliance and trend reports
- SLODashboard: Real-time SLO monitoring

Example:
    from autosre.slo import (
        SLOManager,
        create_availability_slo,
        ErrorBudgetTracker,
        ReportGenerator,
    )
    
    # Create an availability SLO
    slo = create_availability_slo(
        name="API Availability",
        service_id="api-gateway",
        target=0.999,  # 99.9%
    )
    
    # Track error budget
    tracker = ErrorBudgetTracker()
    budget = tracker.create_budget(slo)
    
    # Record events
    budget.record_events(good_events=9990, total_events=10000)
    
    # Get status
    status = budget.get_status()
    print(f"Budget remaining: {status.remaining_percentage:.2f}%")
"""

# Definition module
from .definition import (
    # Core types
    SLIType,
    SLOPeriod,
    AlertSeverity,
    ComplianceStatus,
    # Models
    LatencyThreshold,
    SLIMetric,
    BurnRateWindow,
    AlertPolicy,
    SLODefinition,
    SLOGroup,
    SLOManager,
    # Convenience functions
    create_availability_slo,
    create_latency_slo,
    create_error_rate_slo,
)

# Budget module
from .budget import (
    # Core types
    BudgetConsumptionRate,
    BudgetAction,
    # Models
    BudgetDataPoint,
    BurnRateCalculation,
    ErrorBudgetStatus,
    BudgetPolicy,
    ErrorBudget,
    ErrorBudgetTracker,
    # Convenience functions
    calculate_burn_rate,
    calculate_time_to_exhaustion,
    budget_allows_deployment,
)

# Reporting module
from .reporting import (
    # Core types
    ReportPeriod,
    ReportFormat,
    TrendDirection,
    # Models
    SLOComplianceRecord,
    SLOTrend,
    ServiceSLOSummary,
    SLOReport,
    ReportGenerator,
    SLODashboard,
    # Convenience functions
    generate_weekly_report,
    generate_monthly_report,
    format_report,
)


__all__ = [
    # Definition - Core types
    "SLIType",
    "SLOPeriod",
    "AlertSeverity",
    "ComplianceStatus",
    
    # Definition - Models
    "LatencyThreshold",
    "SLIMetric",
    "BurnRateWindow",
    "AlertPolicy",
    "SLODefinition",
    "SLOGroup",
    "SLOManager",
    
    # Definition - Convenience
    "create_availability_slo",
    "create_latency_slo",
    "create_error_rate_slo",
    
    # Budget - Core types
    "BudgetConsumptionRate",
    "BudgetAction",
    
    # Budget - Models
    "BudgetDataPoint",
    "BurnRateCalculation",
    "ErrorBudgetStatus",
    "BudgetPolicy",
    "ErrorBudget",
    "ErrorBudgetTracker",
    
    # Budget - Convenience
    "calculate_burn_rate",
    "calculate_time_to_exhaustion",
    "budget_allows_deployment",
    
    # Reporting - Core types
    "ReportPeriod",
    "ReportFormat",
    "TrendDirection",
    
    # Reporting - Models
    "SLOComplianceRecord",
    "SLOTrend",
    "ServiceSLOSummary",
    "SLOReport",
    "ReportGenerator",
    "SLODashboard",
    
    # Reporting - Convenience
    "generate_weekly_report",
    "generate_monthly_report",
    "format_report",
]
