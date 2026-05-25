"""
AutoSRE Analytics Module

Advanced analytics, trend analysis, pattern recognition, and predictive
capabilities for incident management and SRE operations.

Features:
- Trend analysis for incidents over time
- Pattern recognition in alerts and incidents
- Predictive analytics for proactive incident prevention
- Automated report generation
- Visualization and charting support
"""

from autosre.analytics.trends import (
    TrendAnalyzer,
    TrendResult,
    TrendDirection,
    SeasonalPattern,
)
from autosre.analytics.patterns import (
    PatternRecognizer,
    AlertPattern,
    IncidentCluster,
    PatternType,
)
from autosre.analytics.predictions import (
    IncidentPredictor,
    PredictionResult,
    RiskLevel,
    PredictiveInsight,
)
from autosre.analytics.reports import (
    ReportGenerator,
    ReportType,
    ReportFormat,
    SREReport,
)
from autosre.analytics.visualizations import (
    ChartGenerator,
    ChartType,
    TimeSeriesChart,
    DistributionChart,
)

__all__ = [
    # Trends
    "TrendAnalyzer",
    "TrendResult",
    "TrendDirection",
    "SeasonalPattern",
    # Patterns
    "PatternRecognizer",
    "AlertPattern",
    "IncidentCluster",
    "PatternType",
    # Predictions
    "IncidentPredictor",
    "PredictionResult",
    "RiskLevel",
    "PredictiveInsight",
    # Reports
    "ReportGenerator",
    "ReportType",
    "ReportFormat",
    "SREReport",
    # Visualizations
    "ChartGenerator",
    "ChartType",
    "TimeSeriesChart",
    "DistributionChart",
]
