"""AutoSRE ML Intelligence Layer.

This module provides machine learning capabilities for:
- Predictive Analytics: Forecast capacity, failures, traffic, and costs
- Root Cause Analysis: Automated causal analysis and hypothesis ranking
- Anomaly Detection: Time series, log, and behavior anomaly detection
- NLP for Operations: Incident classification, severity estimation, and summarization
- Reinforcement Learning: Optimal resource allocation, scaling, and remediation
"""

from autosre.ml.common import (
    # Base classes
    BaseMLModel,
    ModelMetadata,
    ModelRegistry,
    PredictionResult,
    # Feature engineering
    FeatureExtractor,
    TimeSeriesFeatures,
    # Utilities
    DataPreprocessor,
    ModelSerializer,
    MetricsTracker,
)

from autosre.ml.prediction import (
    CapacityPredictor,
    FailurePredictor,
    TrafficPredictor,
    CostPredictor,
)

from autosre.ml.rca import (
    CausalGraph,
    RCAEngine,
    SymptomCorrelator,
    HypothesisRanker,
    EvidenceCollector,
)

from autosre.ml.anomaly import (
    TimeSeriesAnomalyDetector,
    LogAnomalyDetector,
    BehaviorAnomalyDetector,
    MultiVariateDetector,
    AnomalyExplainer,
)

from autosre.ml.nlp import (
    IncidentClassifier,
    SeverityEstimator,
    SimilarityFinder,
    SummaryGenerator,
    CommandParser,
)

from autosre.ml.rl import (
    ResourceOptimizer,
    ScalingAgent,
    AlertTuner,
    RemediationLearner,
    RewardTracker,
)

__all__ = [
    # Common
    "BaseMLModel",
    "ModelMetadata",
    "ModelRegistry",
    "PredictionResult",
    "FeatureExtractor",
    "TimeSeriesFeatures",
    "DataPreprocessor",
    "ModelSerializer",
    "MetricsTracker",
    # Prediction
    "CapacityPredictor",
    "FailurePredictor",
    "TrafficPredictor",
    "CostPredictor",
    # RCA
    "CausalGraph",
    "RCAEngine",
    "SymptomCorrelator",
    "HypothesisRanker",
    "EvidenceCollector",
    # Anomaly
    "TimeSeriesAnomalyDetector",
    "LogAnomalyDetector",
    "BehaviorAnomalyDetector",
    "MultiVariateDetector",
    "AnomalyExplainer",
    # NLP
    "IncidentClassifier",
    "SeverityEstimator",
    "SimilarityFinder",
    "SummaryGenerator",
    "CommandParser",
    # RL
    "ResourceOptimizer",
    "ScalingAgent",
    "AlertTuner",
    "RemediationLearner",
    "RewardTracker",
]
