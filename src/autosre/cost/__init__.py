"""
AutoSRE Cost Optimization Module

FinOps for SRE - comprehensive cost analysis, recommendations, rightsizing,
and forecasting capabilities for cloud infrastructure optimization.

Features:
- Cost analysis and breakdown by service, team, environment
- Intelligent cost optimization recommendations
- Resource rightsizing based on usage patterns
- Cost forecasting and budget alerts
- Multi-cloud support (AWS, GCP, Azure)
"""

from autosre.cost.analyzer import (
    CostAnalyzer,
    CostBreakdown,
    CostTrend,
    CostAllocation,
    CostMetric,
    CloudProvider,
    ResourceType,
)
from autosre.cost.recommendations import (
    CostRecommendation,
    RecommendationType,
    RecommendationPriority,
    RecommendationEngine,
    SavingsEstimate,
    RecommendationStatus,
)
from autosre.cost.rightsizing import (
    RightsizingAnalyzer,
    RightsizingRecommendation,
    ResourceUtilization,
    InstanceSpec,
    RightsizingAction,
    UtilizationThreshold,
)
from autosre.cost.forecasting import (
    CostForecaster,
    CostForecast,
    BudgetAlert,
    BudgetStatus,
    ForecastModel,
    SpendingTrend,
    AnomalyDetector,
    CostAnomaly,
)

__all__ = [
    # Analyzer
    "CostAnalyzer",
    "CostBreakdown",
    "CostTrend",
    "CostAllocation",
    "CostMetric",
    "CloudProvider",
    "ResourceType",
    # Recommendations
    "CostRecommendation",
    "RecommendationType",
    "RecommendationPriority",
    "RecommendationEngine",
    "SavingsEstimate",
    "RecommendationStatus",
    # Rightsizing
    "RightsizingAnalyzer",
    "RightsizingRecommendation",
    "ResourceUtilization",
    "InstanceSpec",
    "RightsizingAction",
    "UtilizationThreshold",
    # Forecasting
    "CostForecaster",
    "CostForecast",
    "BudgetAlert",
    "BudgetStatus",
    "ForecastModel",
    "SpendingTrend",
    "AnomalyDetector",
    "CostAnomaly",
]
