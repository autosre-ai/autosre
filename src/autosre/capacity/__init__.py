"""
AutoSRE Capacity Planning Module

Comprehensive capacity planning and forecasting capabilities including:
- Capacity forecasting with multiple algorithms
- Resource planning and recommendations
- Capacity reporting and visualization
- Budget estimation and tracking

v2.10 Features:
- CapacityForecaster: Time-series forecasting for resource utilization
- CapacityPlanner: Capacity planning with recommendations
- CapacityReporter: Generate capacity reports and insights
"""

# Forecasting
from .forecast import (
    # Core types
    ForecastAlgorithm,
    SeasonalityType,
    TrendDirection,
    ConfidenceLevel,
    # Models
    DataPoint,
    TimeSeriesData,
    ForecastConfig,
    ForecastResult,
    ForecastMetrics,
    AnomalyDetection,
    CapacityForecaster,
    # Convenience functions
    quick_forecast,
    detect_seasonality,
)

# Planning
from .planning import (
    # Core types
    ResourceType,
    ScalingStrategy,
    PlanningHorizon,
    RecommendationType,
    RecommendationPriority,
    CostImpact,
    # Models
    ResourceSpec,
    CurrentCapacity,
    CapacityRequirement,
    ScalingRecommendation,
    CapacityPlan,
    BudgetEstimate,
    CapacityPlanner,
    # Convenience functions
    quick_capacity_check,
    estimate_scaling_needs,
)

# Reporting
from .reporting import (
    # Core types
    ReportFormat,
    ReportFrequency,
    ReportSection,
    TrendIndicator,
    HealthStatus,
    # Models
    CapacityMetric,
    ResourceUtilization,
    CapacityTrend,
    CapacityAlert,
    CapacityInsight,
    CapacitySummary,
    CapacityReport,
    ReportConfig,
    CapacityReporter,
    # Convenience functions
    generate_quick_report,
    get_capacity_health,
)

__all__ = [
    # Forecasting - types
    "ForecastAlgorithm",
    "SeasonalityType",
    "TrendDirection",
    "ConfidenceLevel",
    # Forecasting - models
    "DataPoint",
    "TimeSeriesData",
    "ForecastConfig",
    "ForecastResult",
    "ForecastMetrics",
    "AnomalyDetection",
    "CapacityForecaster",
    # Forecasting - functions
    "quick_forecast",
    "detect_seasonality",
    
    # Planning - types
    "ResourceType",
    "ScalingStrategy",
    "PlanningHorizon",
    "RecommendationType",
    "RecommendationPriority",
    "CostImpact",
    # Planning - models
    "ResourceSpec",
    "CurrentCapacity",
    "CapacityRequirement",
    "ScalingRecommendation",
    "CapacityPlan",
    "BudgetEstimate",
    "CapacityPlanner",
    # Planning - functions
    "quick_capacity_check",
    "estimate_scaling_needs",
    
    # Reporting - types
    "ReportFormat",
    "ReportFrequency",
    "ReportSection",
    "TrendIndicator",
    "HealthStatus",
    # Reporting - models
    "CapacityMetric",
    "ResourceUtilization",
    "CapacityTrend",
    "CapacityAlert",
    "CapacityInsight",
    "CapacitySummary",
    "CapacityReport",
    "ReportConfig",
    "CapacityReporter",
    # Reporting - functions
    "generate_quick_report",
    "get_capacity_health",
]
