"""Common ML utilities and base classes."""

from autosre.ml.common.base import (
    BaseMLModel,
    ModelMetadata,
    ModelVersion,
    PredictionResult,
    BatchPredictionResult,
    ModelStatus,
    TrainingConfig,
    EvaluationMetrics,
)

from autosre.ml.common.registry import (
    ModelRegistry,
    ModelEntry,
    ModelFilter,
)

from autosre.ml.common.features import (
    FeatureExtractor,
    TimeSeriesFeatures,
    FeatureSet,
    FeatureImportance,
    FeatureScaler,
    FeatureSelector,
)

from autosre.ml.common.preprocessing import (
    DataPreprocessor,
    TimeSeriesPreprocessor,
    TextPreprocessor,
    MissingValueHandler,
    OutlierHandler,
)

from autosre.ml.common.serialization import (
    ModelSerializer,
    SerializationFormat,
    ModelArtifact,
)

from autosre.ml.common.metrics import (
    MetricsTracker,
    ModelMetrics,
    ConfusionMatrix,
    RegressionMetrics,
    ClassificationMetrics,
    TimeSeriesMetrics,
)

from autosre.ml.common.pipeline import (
    Pipeline,
    PipelineStep,
    PipelineResult,
    PipelineConfig,
)

__all__ = [
    # Base
    "BaseMLModel",
    "ModelMetadata",
    "ModelVersion",
    "PredictionResult",
    "BatchPredictionResult",
    "ModelStatus",
    "TrainingConfig",
    "EvaluationMetrics",
    # Registry
    "ModelRegistry",
    "ModelEntry",
    "ModelFilter",
    # Features
    "FeatureExtractor",
    "TimeSeriesFeatures",
    "FeatureSet",
    "FeatureImportance",
    "FeatureScaler",
    "FeatureSelector",
    # Preprocessing
    "DataPreprocessor",
    "TimeSeriesPreprocessor",
    "TextPreprocessor",
    "MissingValueHandler",
    "OutlierHandler",
    # Serialization
    "ModelSerializer",
    "SerializationFormat",
    "ModelArtifact",
    # Metrics
    "MetricsTracker",
    "ModelMetrics",
    "ConfusionMatrix",
    "RegressionMetrics",
    "ClassificationMetrics",
    "TimeSeriesMetrics",
    # Pipeline
    "Pipeline",
    "PipelineStep",
    "PipelineResult",
    "PipelineConfig",
]
