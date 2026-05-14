"""Base classes for ML models in AutoSRE."""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Generic, TypeVar, Optional
from uuid import uuid4

import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from autosre.models.common import utc_now


def generate_model_id() -> str:
    """Generate a unique model ID."""
    return f"model-{uuid4().hex[:12]}"


def generate_version_id() -> str:
    """Generate a unique version ID."""
    return f"v-{uuid4().hex[:8]}"


class ModelStatus(str, Enum):
    """Status of a model."""
    DRAFT = "draft"
    TRAINING = "training"
    TRAINED = "trained"
    VALIDATING = "validating"
    VALIDATED = "validated"
    DEPLOYED = "deployed"
    DEPRECATED = "deprecated"
    FAILED = "failed"


class ModelVersion(BaseModel):
    """Version information for a model."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    version_id: str = Field(default_factory=generate_version_id)
    version_number: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=utc_now)
    description: str = Field(default="")
    
    # Training info
    training_started_at: Optional[datetime] = None
    training_completed_at: Optional[datetime] = None
    training_duration_seconds: Optional[float] = None
    
    # Metrics
    metrics: dict[str, float] = Field(default_factory=dict)
    
    # Artifact location
    artifact_path: Optional[str] = None
    artifact_size_bytes: Optional[int] = None
    
    # Git info
    git_commit: Optional[str] = None
    git_branch: Optional[str] = None


class ModelMetadata(BaseModel):
    """Metadata for a ML model."""
    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        validate_assignment=True,
    )
    
    model_id: str = Field(default_factory=generate_model_id)
    name: str = Field(..., min_length=1)
    description: str = Field(default="")
    model_type: str = Field(..., description="Type of model (e.g., 'capacity_predictor')")
    
    # Status
    status: ModelStatus = Field(default=ModelStatus.DRAFT)
    
    # Versions
    current_version: Optional[ModelVersion] = None
    versions: list[ModelVersion] = Field(default_factory=list)
    
    # Configuration
    hyperparameters: dict[str, Any] = Field(default_factory=dict)
    feature_names: list[str] = Field(default_factory=list)
    target_name: str = Field(default="")
    
    # Timestamps
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    last_trained_at: Optional[datetime] = None
    last_deployed_at: Optional[datetime] = None
    
    # Ownership
    owner: Optional[str] = None
    team: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    
    # Additional metadata
    extra: dict[str, Any] = Field(default_factory=dict)
    
    def add_version(self, version: ModelVersion) -> None:
        """Add a new version."""
        self.versions.append(version)
        self.current_version = version
        self.updated_at = utc_now()
    
    def get_version(self, version_id: str) -> Optional[ModelVersion]:
        """Get a specific version by ID."""
        for v in self.versions:
            if v.version_id == version_id:
                return v
        return None


class TrainingConfig(BaseModel):
    """Configuration for model training."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    # Data configuration
    train_split: float = Field(default=0.8, ge=0.1, le=0.99)
    validation_split: float = Field(default=0.1, ge=0.0, le=0.5)
    test_split: float = Field(default=0.1, ge=0.0, le=0.5)
    
    # Training parameters
    epochs: int = Field(default=100, ge=1)
    batch_size: int = Field(default=32, ge=1)
    learning_rate: float = Field(default=0.001, gt=0)
    early_stopping_patience: int = Field(default=10, ge=0)
    
    # Regularization
    dropout_rate: float = Field(default=0.1, ge=0.0, le=0.9)
    l2_regularization: float = Field(default=0.01, ge=0.0)
    
    # Hardware
    use_gpu: bool = Field(default=True)
    num_workers: int = Field(default=4, ge=1)
    
    # Checkpointing
    checkpoint_dir: Optional[str] = None
    save_best_only: bool = Field(default=True)
    
    # Random seed
    random_seed: int = Field(default=42)


class EvaluationMetrics(BaseModel):
    """Evaluation metrics for a model."""
    model_config = ConfigDict(validate_assignment=True)
    
    # Regression metrics
    mse: Optional[float] = None
    rmse: Optional[float] = None
    mae: Optional[float] = None
    mape: Optional[float] = None
    r2_score: Optional[float] = None
    
    # Classification metrics
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    auc_roc: Optional[float] = None
    
    # Time series metrics
    smape: Optional[float] = None
    mase: Optional[float] = None
    
    # Custom metrics
    custom_metrics: dict[str, float] = Field(default_factory=dict)
    
    # Evaluation context
    dataset_size: int = Field(default=0, ge=0)
    evaluation_time_seconds: float = Field(default=0.0, ge=0.0)
    evaluated_at: datetime = Field(default_factory=utc_now)


# Type variables for generic model classes
InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


class PredictionResult(BaseModel, Generic[OutputT]):
    """Result of a model prediction."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )
    
    # Prediction
    prediction: Any = Field(...)  # Generic type in BaseModel is complex
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    
    # Uncertainty
    lower_bound: Optional[Any] = None
    upper_bound: Optional[Any] = None
    std_dev: Optional[float] = None
    
    # Metadata
    model_id: str = Field(default="")
    model_version: str = Field(default="")
    predicted_at: datetime = Field(default_factory=utc_now)
    latency_ms: float = Field(default=0.0, ge=0.0)
    
    # Feature importance for this prediction
    feature_contributions: dict[str, float] = Field(default_factory=dict)
    
    # Explanation
    explanation: Optional[str] = None


class BatchPredictionResult(BaseModel):
    """Result of batch predictions."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )
    
    predictions: list[PredictionResult] = Field(default_factory=list)
    
    # Batch metadata
    batch_size: int = Field(default=0, ge=0)
    total_latency_ms: float = Field(default=0.0, ge=0.0)
    avg_latency_ms: float = Field(default=0.0, ge=0.0)
    
    # Model info
    model_id: str = Field(default="")
    model_version: str = Field(default="")
    
    # Errors
    num_failures: int = Field(default=0, ge=0)
    failure_indices: list[int] = Field(default_factory=list)
    
    def success_rate(self) -> float:
        """Calculate prediction success rate."""
        if self.batch_size == 0:
            return 0.0
        return (self.batch_size - self.num_failures) / self.batch_size


class BaseMLModel(ABC, Generic[InputT, OutputT]):
    """Abstract base class for all ML models in AutoSRE.
    
    This provides a consistent interface for:
    - Training and evaluation
    - Prediction (single and batch)
    - Serialization and deserialization
    - Metadata management
    """
    
    def __init__(
        self,
        name: str,
        model_type: str,
        hyperparameters: Optional[dict[str, Any]] = None,
    ):
        """Initialize the base model.
        
        Args:
            name: Human-readable model name
            model_type: Type identifier for the model
            hyperparameters: Model hyperparameters
        """
        self._metadata = ModelMetadata(
            name=name,
            model_type=model_type,
            hyperparameters=hyperparameters or {},
        )
        self._is_fitted = False
        self._model: Any = None
    
    @property
    def metadata(self) -> ModelMetadata:
        """Get model metadata."""
        return self._metadata
    
    @property
    def model_id(self) -> str:
        """Get model ID."""
        return self._metadata.model_id
    
    @property
    def name(self) -> str:
        """Get model name."""
        return self._metadata.name
    
    @property
    def is_fitted(self) -> bool:
        """Check if model has been trained."""
        return self._is_fitted
    
    @abstractmethod
    def fit(
        self,
        X: InputT,
        y: Optional[Any] = None,
        config: Optional[TrainingConfig] = None,
    ) -> "BaseMLModel":
        """Train the model.
        
        Args:
            X: Training features
            y: Training targets (optional for unsupervised)
            config: Training configuration
            
        Returns:
            Self for chaining
        """
        pass
    
    @abstractmethod
    def predict(self, X: InputT) -> PredictionResult[OutputT]:
        """Make a prediction.
        
        Args:
            X: Input features
            
        Returns:
            Prediction result
        """
        pass
    
    def predict_batch(
        self,
        X: list[InputT],
    ) -> BatchPredictionResult:
        """Make batch predictions.
        
        Default implementation calls predict() for each input.
        Override for optimized batch processing.
        
        Args:
            X: List of input features
            
        Returns:
            Batch prediction results
        """
        import time
        
        start_time = time.time()
        predictions = []
        failures = []
        
        for i, x in enumerate(X):
            try:
                result = self.predict(x)
                predictions.append(result)
            except Exception:
                failures.append(i)
        
        total_time = (time.time() - start_time) * 1000
        
        return BatchPredictionResult(
            predictions=predictions,
            batch_size=len(X),
            total_latency_ms=total_time,
            avg_latency_ms=total_time / len(X) if X else 0,
            model_id=self.model_id,
            model_version=self._metadata.current_version.version_id if self._metadata.current_version else "",
            num_failures=len(failures),
            failure_indices=failures,
        )
    
    @abstractmethod
    def evaluate(
        self,
        X: InputT,
        y: Any,
    ) -> EvaluationMetrics:
        """Evaluate the model.
        
        Args:
            X: Test features
            y: True targets
            
        Returns:
            Evaluation metrics
        """
        pass
    
    def save(self, path: str) -> str:
        """Save model to disk.
        
        Args:
            path: Directory to save to
            
        Returns:
            Path to saved model
        """
        from autosre.ml.common.serialization import ModelSerializer
        
        serializer = ModelSerializer()
        return serializer.save(self, path)
    
    @classmethod
    def load(cls, path: str) -> "BaseMLModel":
        """Load model from disk.
        
        Args:
            path: Path to saved model
            
        Returns:
            Loaded model instance
        """
        from autosre.ml.common.serialization import ModelSerializer
        
        serializer = ModelSerializer()
        return serializer.load(path)
    
    def get_feature_importance(self) -> dict[str, float]:
        """Get feature importance scores.
        
        Returns:
            Dictionary mapping feature names to importance scores
        """
        return {}
    
    def explain_prediction(
        self,
        X: InputT,
        method: str = "shap",
    ) -> dict[str, Any]:
        """Explain a prediction.
        
        Args:
            X: Input features
            method: Explanation method ('shap', 'lime', 'integrated_gradients')
            
        Returns:
            Explanation details
        """
        return {"method": method, "features": {}, "explanation": "Not implemented"}
    
    def update_metadata(self, **kwargs: Any) -> None:
        """Update model metadata.
        
        Args:
            **kwargs: Fields to update
        """
        for key, value in kwargs.items():
            if hasattr(self._metadata, key):
                setattr(self._metadata, key, value)
        self._metadata.updated_at = utc_now()
    
    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"name='{self.name}', "
            f"model_id='{self.model_id}', "
            f"is_fitted={self.is_fitted})"
        )
