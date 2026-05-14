"""
AutoSRE V2 Analytics Module.

Real-time metrics pipeline with:
- MetricsCollector: Prometheus scraping with adaptive sampling
- AnomalyDetector: Statistical anomaly detection (z-score, IQR, DBSCAN)
- TrendAnalyzer: Time series forecasting (Prophet, ARIMA patterns)
- AlertCorrelator: Group related alerts, reduce noise

Example:
    from autosre.analytics import MetricsCollector, AnomalyDetector

    collector = MetricsCollector(prometheus_url="http://prometheus:9090")
    metrics = await collector.collect_metrics(queries=[...])

    detector = AnomalyDetector()
    anomalies = detector.detect(metrics)
"""

from .collector import (
    MetricsCollector,
    CollectorConfig,
    SamplingStrategy,
    AdaptiveSampler,
    MetricBuffer,
    CollectionResult,
    CollectionStats,
)

from .anomaly import (
    AnomalyDetector,
    AnomalyResult,
    AnomalyType,
    AnomalySeverity,
    DetectionMethod,
    ZScoreDetector,
    IQRDetector,
    DBSCANDetector,
    IsolationForestDetector,
    EnsembleDetector,
    AnomalyConfig,
    SeasonalityConfig,
)

from .trends import (
    TrendAnalyzer,
    TrendResult,
    TrendDirection,
    ForecastResult,
    SeasonalPattern,
    ChangePoint,
    TrendConfig,
    ARIMAAnalyzer,
    ProphetAnalyzer,
    HoltWintersAnalyzer,
    MovingAverageAnalyzer,
)

from .correlator import (
    AlertCorrelator,
    CorrelationGroup,
    CorrelationRule,
    CorrelationMethod,
    CorrelationResult,
    AlertCluster,
    CorrelatorConfig,
    TimeWindowConfig,
    SimilarityMetric,
)

__all__ = [
    # Collector
    "MetricsCollector",
    "CollectorConfig",
    "SamplingStrategy",
    "AdaptiveSampler",
    "MetricBuffer",
    "CollectionResult",
    "CollectionStats",
    # Anomaly Detection
    "AnomalyDetector",
    "AnomalyResult",
    "AnomalyType",
    "AnomalySeverity",
    "DetectionMethod",
    "ZScoreDetector",
    "IQRDetector",
    "DBSCANDetector",
    "IsolationForestDetector",
    "EnsembleDetector",
    "AnomalyConfig",
    "SeasonalityConfig",
    # Trend Analysis
    "TrendAnalyzer",
    "TrendResult",
    "TrendDirection",
    "ForecastResult",
    "SeasonalPattern",
    "ChangePoint",
    "TrendConfig",
    "ARIMAAnalyzer",
    "ProphetAnalyzer",
    "HoltWintersAnalyzer",
    "MovingAverageAnalyzer",
    # Alert Correlation
    "AlertCorrelator",
    "CorrelationGroup",
    "CorrelationRule",
    "CorrelationMethod",
    "CorrelationResult",
    "AlertCluster",
    "CorrelatorConfig",
    "TimeWindowConfig",
    "SimilarityMetric",
]
