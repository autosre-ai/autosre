"""Failure prediction for infrastructure components."""

from datetime import datetime, timedelta
from typing import Any, Optional, List, Dict, Tuple
from enum import Enum

import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from autosre.models.common import utc_now, generate_id
from autosre.ml.common.base import (
    BaseMLModel,
    TrainingConfig,
    EvaluationMetrics,
    PredictionResult,
    ModelStatus,
    ModelVersion,
)
from autosre.ml.common.features import TimeSeriesFeatures, FeatureScaler, MetricFeatureExtractor
from autosre.ml.common.preprocessing import DataPreprocessor
from autosre.ml.common.metrics import ClassificationMetrics


class FailureType(str, Enum):
    """Type of infrastructure failure."""
    CRASH = "crash"
    DEGRADATION = "degradation"
    TIMEOUT = "timeout"
    OOM = "oom"
    DISK_FULL = "disk_full"
    NETWORK = "network"
    DEPENDENCY = "dependency"
    UNKNOWN = "unknown"


class FailureRisk(str, Enum):
    """Risk level for failure prediction."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FailurePrediction(BaseModel):
    """Failure prediction result."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    prediction_id: str = Field(default_factory=generate_id)
    
    # Target
    component_name: str = Field(default="")
    component_type: str = Field(default="")
    
    # Prediction
    failure_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    risk_level: FailureRisk = Field(default=FailureRisk.LOW)
    predicted_failure_type: Optional[FailureType] = None
    
    # Time estimation
    predicted_time_to_failure_hours: Optional[float] = None
    confidence_interval: tuple[float, float] = Field(default=(0, 0))
    
    # Contributing factors
    risk_factors: list[dict[str, Any]] = Field(default_factory=list)
    top_indicators: list[str] = Field(default_factory=list)
    
    # Historical context
    similar_failures: list[str] = Field(default_factory=list)
    mtbf_hours: Optional[float] = None  # Mean time between failures
    
    # Recommendations
    preventive_actions: list[str] = Field(default_factory=list)
    
    # Metadata
    prediction_horizon_hours: int = Field(default=24)
    generated_at: datetime = Field(default_factory=utc_now)
    model_version: str = Field(default="")


class ComponentHealth(BaseModel):
    """Health metrics for a component."""
    model_config = ConfigDict(validate_assignment=True)
    
    component_name: str
    
    # Resource metrics
    cpu_usage: float = Field(default=0.0, ge=0.0, le=100.0)
    memory_usage: float = Field(default=0.0, ge=0.0, le=100.0)
    disk_usage: float = Field(default=0.0, ge=0.0, le=100.0)
    
    # Performance metrics
    latency_p99_ms: float = Field(default=0.0, ge=0.0)
    error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    request_rate: float = Field(default=0.0, ge=0.0)
    
    # Health indicators
    restart_count: int = Field(default=0, ge=0)
    uptime_hours: float = Field(default=0.0, ge=0.0)
    oom_count: int = Field(default=0, ge=0)
    
    # Time series (last N samples)
    cpu_history: list[float] = Field(default_factory=list)
    memory_history: list[float] = Field(default_factory=list)
    latency_history: list[float] = Field(default_factory=list)
    error_history: list[float] = Field(default_factory=list)


class FailurePredictor(BaseMLModel[ComponentHealth, FailurePrediction]):
    """Predict component failures before they occur.
    
    Uses machine learning to identify patterns that precede failures:
    - Resource exhaustion patterns (memory leaks, disk filling)
    - Performance degradation trends
    - Error rate spikes
    - Unusual behavior patterns
    
    Supports:
    - Binary failure prediction
    - Time-to-failure estimation
    - Failure type classification
    - Risk factor analysis
    """
    
    def __init__(
        self,
        prediction_horizon_hours: int = 24,
        failure_threshold: float = 0.5,
        include_time_features: bool = True,
        use_ensemble: bool = True,
    ):
        """Initialize the failure predictor.
        
        Args:
            prediction_horizon_hours: Hours ahead to predict failures
            failure_threshold: Probability threshold for failure prediction
            include_time_features: Include time-based features
            use_ensemble: Use ensemble of models
        """
        super().__init__(
            name="failure_predictor",
            model_type="failure_predictor",
            hyperparameters={
                "prediction_horizon_hours": prediction_horizon_hours,
                "failure_threshold": failure_threshold,
                "include_time_features": include_time_features,
                "use_ensemble": use_ensemble,
            },
        )
        
        self.prediction_horizon_hours = prediction_horizon_hours
        self.failure_threshold = failure_threshold
        self.include_time_features = include_time_features
        self.use_ensemble = use_ensemble
        
        # Feature extraction
        self._ts_features = TimeSeriesFeatures()
        self._scaler = FeatureScaler()
        self._preprocessor = DataPreprocessor()
        
        # Model parameters (learned)
        self._weights: Optional[np.ndarray] = None
        self._bias: float = 0.0
        self._feature_means: Optional[np.ndarray] = None
        self._feature_stds: Optional[np.ndarray] = None
        
        # Thresholds learned from training
        self._failure_patterns: list[dict[str, Any]] = []
        self._risk_thresholds: dict[str, tuple[float, float, float]] = {}
        
        # Feature names
        self._feature_names: list[str] = []
    
    def _extract_features(self, health: ComponentHealth) -> np.ndarray:
        """Extract features from component health data.
        
        Args:
            health: Component health metrics
            
        Returns:
            Feature vector
        """
        features = []
        self._feature_names = []
        
        # Current resource utilization
        features.extend([
            health.cpu_usage,
            health.memory_usage,
            health.disk_usage,
        ])
        self._feature_names.extend(["cpu_usage", "memory_usage", "disk_usage"])
        
        # Performance metrics
        features.extend([
            health.latency_p99_ms,
            health.error_rate,
            health.request_rate,
        ])
        self._feature_names.extend(["latency_p99", "error_rate", "request_rate"])
        
        # Health indicators
        features.extend([
            float(health.restart_count),
            health.uptime_hours,
            float(health.oom_count),
        ])
        self._feature_names.extend(["restart_count", "uptime_hours", "oom_count"])
        
        # Time series features
        if health.cpu_history:
            cpu_features = self._ts_features.extract(np.array(health.cpu_history))
            for name, value in cpu_features.items():
                features.append(value)
                self._feature_names.append(f"cpu_{name}")
        
        if health.memory_history:
            mem_features = self._ts_features.extract(np.array(health.memory_history))
            for name, value in mem_features.items():
                features.append(value)
                self._feature_names.append(f"memory_{name}")
        
        if health.latency_history:
            lat_features = self._ts_features.extract(np.array(health.latency_history))
            for name, value in lat_features.items():
                features.append(value)
                self._feature_names.append(f"latency_{name}")
        
        if health.error_history:
            err_features = self._ts_features.extract(np.array(health.error_history))
            for name, value in err_features.items():
                features.append(value)
                self._feature_names.append(f"error_{name}")
        
        return np.array(features, dtype=np.float64)
    
    def _sigmoid(self, x: np.ndarray) -> np.ndarray:
        """Sigmoid activation function."""
        return 1 / (1 + np.exp(-np.clip(x, -500, 500)))
    
    def fit(
        self,
        X: list[ComponentHealth],
        y: np.ndarray,
        config: Optional[TrainingConfig] = None,
    ) -> "FailurePredictor":
        """Train the failure predictor.
        
        Args:
            X: List of component health snapshots
            y: Binary labels (1 = failure occurred, 0 = no failure)
            config: Training configuration
            
        Returns:
            Self
        """
        config = config or TrainingConfig()
        
        # Extract features
        feature_vectors = []
        for health in X:
            features = self._extract_features(health)
            feature_vectors.append(features)
        
        # Pad to same length
        max_len = max(len(f) for f in feature_vectors)
        X_matrix = np.zeros((len(feature_vectors), max_len))
        for i, f in enumerate(feature_vectors):
            X_matrix[i, :len(f)] = f
        
        y = np.asarray(y).flatten()
        
        # Normalize features
        self._feature_means = np.mean(X_matrix, axis=0)
        self._feature_stds = np.std(X_matrix, axis=0)
        self._feature_stds[self._feature_stds == 0] = 1  # Avoid division by zero
        
        X_normalized = (X_matrix - self._feature_means) / self._feature_stds
        
        # Simple logistic regression training
        n_features = X_normalized.shape[1]
        self._weights = np.zeros(n_features)
        self._bias = 0.0
        
        lr = config.learning_rate
        
        for epoch in range(config.epochs):
            # Forward pass
            z = np.dot(X_normalized, self._weights) + self._bias
            predictions = self._sigmoid(z)
            
            # Compute gradients
            error = predictions - y
            grad_w = np.dot(X_normalized.T, error) / len(y)
            grad_b = np.mean(error)
            
            # L2 regularization
            grad_w += config.l2_regularization * self._weights
            
            # Update weights
            self._weights -= lr * grad_w
            self._bias -= lr * grad_b
            
            # Check convergence
            loss = -np.mean(y * np.log(predictions + 1e-10) + (1 - y) * np.log(1 - predictions + 1e-10))
            
            if epoch % 100 == 0 and config.learning_rate > 0.0001:
                lr *= 0.99  # Learning rate decay
        
        # Learn risk thresholds from data
        self._learn_risk_thresholds(X)
        
        # Learn failure patterns
        failure_indices = np.where(y == 1)[0]
        if len(failure_indices) > 0:
            self._learn_failure_patterns(X, failure_indices)
        
        # Mark as fitted
        self._is_fitted = True
        self._metadata.status = ModelStatus.TRAINED
        self._metadata.last_trained_at = utc_now()
        
        # Calculate training metrics
        final_predictions = self._sigmoid(np.dot(X_normalized, self._weights) + self._bias)
        final_accuracy = np.mean((final_predictions >= 0.5) == y)
        
        version = ModelVersion(
            description=f"Trained on {len(X)} samples",
            metrics={
                "accuracy": float(final_accuracy),
                "num_samples": float(len(X)),
                "num_failures": float(np.sum(y)),
            },
        )
        self._metadata.add_version(version)
        
        return self
    
    def _learn_risk_thresholds(self, X: list[ComponentHealth]) -> None:
        """Learn risk thresholds from data.
        
        Args:
            X: Component health data
        """
        # Collect metric values
        cpu_values = [h.cpu_usage for h in X]
        memory_values = [h.memory_usage for h in X]
        disk_values = [h.disk_usage for h in X]
        error_values = [h.error_rate for h in X]
        
        # Set thresholds at percentiles
        for name, values in [
            ("cpu", cpu_values),
            ("memory", memory_values),
            ("disk", disk_values),
            ("error_rate", error_values),
        ]:
            if values:
                arr = np.array(values)
                self._risk_thresholds[name] = (
                    float(np.percentile(arr, 70)),  # Medium
                    float(np.percentile(arr, 85)),  # High
                    float(np.percentile(arr, 95)),  # Critical
                )
    
    def _learn_failure_patterns(
        self,
        X: list[ComponentHealth],
        failure_indices: np.ndarray,
    ) -> None:
        """Learn patterns that precede failures.
        
        Args:
            X: Component health data
            failure_indices: Indices of failure cases
        """
        patterns = []
        
        for idx in failure_indices:
            health = X[idx]
            pattern = {
                "cpu_usage": health.cpu_usage,
                "memory_usage": health.memory_usage,
                "disk_usage": health.disk_usage,
                "error_rate": health.error_rate,
                "restart_count": health.restart_count,
            }
            
            # Detect pattern type
            if health.memory_usage > 90:
                pattern["type"] = FailureType.OOM
            elif health.disk_usage > 95:
                pattern["type"] = FailureType.DISK_FULL
            elif health.error_rate > 0.5:
                pattern["type"] = FailureType.CRASH
            elif health.latency_p99_ms > 5000:
                pattern["type"] = FailureType.TIMEOUT
            else:
                pattern["type"] = FailureType.UNKNOWN
            
            patterns.append(pattern)
        
        self._failure_patterns = patterns
    
    def predict(
        self,
        X: ComponentHealth,
    ) -> PredictionResult[FailurePrediction]:
        """Predict failure risk for a component.
        
        Args:
            X: Component health metrics
            
        Returns:
            Failure prediction result
        """
        import time
        start_time = time.time()
        
        if not self._is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        # Extract features
        features = self._extract_features(X)
        
        # Pad to expected length
        if len(features) < len(self._feature_means):
            features = np.pad(features, (0, len(self._feature_means) - len(features)))
        elif len(features) > len(self._feature_means):
            features = features[:len(self._feature_means)]
        
        # Normalize
        features_normalized = (features - self._feature_means) / self._feature_stds
        
        # Predict probability
        z = np.dot(features_normalized, self._weights) + self._bias
        failure_probability = float(self._sigmoid(np.array([z]))[0])
        
        # Determine risk level
        if failure_probability >= 0.8:
            risk_level = FailureRisk.CRITICAL
        elif failure_probability >= 0.6:
            risk_level = FailureRisk.HIGH
        elif failure_probability >= 0.3:
            risk_level = FailureRisk.MEDIUM
        else:
            risk_level = FailureRisk.LOW
        
        # Predict failure type
        predicted_type = self._predict_failure_type(X)
        
        # Estimate time to failure
        ttf = self._estimate_time_to_failure(X, failure_probability)
        
        # Identify risk factors
        risk_factors = self._identify_risk_factors(X, features_normalized)
        
        # Get top indicators
        top_indicators = self._get_top_indicators(features_normalized)
        
        # Generate preventive actions
        preventive_actions = self._generate_preventive_actions(
            X, predicted_type, risk_factors
        )
        
        # Create prediction
        prediction = FailurePrediction(
            component_name=X.component_name,
            failure_probability=failure_probability,
            risk_level=risk_level,
            predicted_failure_type=predicted_type,
            predicted_time_to_failure_hours=ttf,
            risk_factors=risk_factors,
            top_indicators=top_indicators,
            preventive_actions=preventive_actions,
            prediction_horizon_hours=self.prediction_horizon_hours,
            model_version=self._metadata.current_version.version_id if self._metadata.current_version else "",
        )
        
        latency = (time.time() - start_time) * 1000
        
        return PredictionResult(
            prediction=prediction,
            confidence=1.0 - abs(0.5 - failure_probability) * 2,  # Confidence is higher near 0 or 1
            model_id=self.model_id,
            model_version=self._metadata.current_version.version_id if self._metadata.current_version else "",
            latency_ms=latency,
        )
    
    def _predict_failure_type(self, health: ComponentHealth) -> Optional[FailureType]:
        """Predict the most likely failure type.
        
        Args:
            health: Component health metrics
            
        Returns:
            Predicted failure type
        """
        # Rule-based prediction based on current state
        if health.memory_usage > 90:
            return FailureType.OOM
        elif health.disk_usage > 95:
            return FailureType.DISK_FULL
        elif health.error_rate > 0.5:
            return FailureType.CRASH
        elif health.latency_p99_ms > 5000:
            return FailureType.TIMEOUT
        elif health.cpu_usage > 95:
            return FailureType.DEGRADATION
        
        # Check learned patterns
        if self._failure_patterns:
            # Find most similar pattern
            min_dist = float("inf")
            best_type = None
            
            for pattern in self._failure_patterns:
                dist = (
                    abs(health.cpu_usage - pattern["cpu_usage"]) +
                    abs(health.memory_usage - pattern["memory_usage"]) +
                    abs(health.error_rate - pattern["error_rate"])
                )
                if dist < min_dist:
                    min_dist = dist
                    best_type = pattern.get("type")
            
            return best_type
        
        return None
    
    def _estimate_time_to_failure(
        self,
        health: ComponentHealth,
        failure_probability: float,
    ) -> Optional[float]:
        """Estimate time to failure based on trends.
        
        Args:
            health: Component health metrics
            failure_probability: Predicted failure probability
            
        Returns:
            Estimated hours until failure
        """
        if failure_probability < 0.3:
            return None  # Low probability, no estimate
        
        # Check memory trend
        if health.memory_history and len(health.memory_history) > 2:
            mem_array = np.array(health.memory_history)
            if len(mem_array) > 1:
                # Calculate trend
                x = np.arange(len(mem_array))
                slope, _ = np.polyfit(x, mem_array, 1)
                
                if slope > 0:
                    # Memory is increasing
                    current = mem_array[-1]
                    remaining = 100 - current
                    if slope > 0.01:  # Significant increase
                        hours_to_full = remaining / (slope * len(mem_array))  # Rough estimate
                        return max(0.1, min(hours_to_full, self.prediction_horizon_hours))
        
        # Default estimate based on probability
        if failure_probability >= 0.8:
            return 2.0
        elif failure_probability >= 0.6:
            return 8.0
        elif failure_probability >= 0.4:
            return 24.0
        else:
            return None
    
    def _identify_risk_factors(
        self,
        health: ComponentHealth,
        features_normalized: np.ndarray,
    ) -> list[dict[str, Any]]:
        """Identify contributing risk factors.
        
        Args:
            health: Component health metrics
            features_normalized: Normalized feature vector
            
        Returns:
            List of risk factors
        """
        risk_factors = []
        
        # Check resource thresholds
        if health.cpu_usage > 80:
            risk_factors.append({
                "factor": "high_cpu_usage",
                "value": health.cpu_usage,
                "threshold": 80,
                "severity": "high" if health.cpu_usage > 90 else "medium",
            })
        
        if health.memory_usage > 80:
            risk_factors.append({
                "factor": "high_memory_usage",
                "value": health.memory_usage,
                "threshold": 80,
                "severity": "critical" if health.memory_usage > 95 else "high",
            })
        
        if health.disk_usage > 85:
            risk_factors.append({
                "factor": "high_disk_usage",
                "value": health.disk_usage,
                "threshold": 85,
                "severity": "critical" if health.disk_usage > 95 else "high",
            })
        
        if health.error_rate > 0.1:
            risk_factors.append({
                "factor": "elevated_error_rate",
                "value": health.error_rate,
                "threshold": 0.1,
                "severity": "critical" if health.error_rate > 0.5 else "high",
            })
        
        if health.restart_count > 2:
            risk_factors.append({
                "factor": "frequent_restarts",
                "value": health.restart_count,
                "threshold": 2,
                "severity": "high",
            })
        
        if health.oom_count > 0:
            risk_factors.append({
                "factor": "oom_events",
                "value": health.oom_count,
                "threshold": 0,
                "severity": "critical",
            })
        
        return risk_factors
    
    def _get_top_indicators(
        self,
        features_normalized: np.ndarray,
        top_k: int = 5,
    ) -> list[str]:
        """Get top contributing indicators.
        
        Args:
            features_normalized: Normalized features
            top_k: Number of top indicators to return
            
        Returns:
            List of indicator names
        """
        if self._weights is None or len(self._feature_names) == 0:
            return []
        
        # Calculate feature contributions
        contributions = features_normalized * self._weights[:len(features_normalized)]
        
        # Get top contributors
        top_indices = np.argsort(np.abs(contributions))[::-1][:top_k]
        
        indicators = []
        for idx in top_indices:
            if idx < len(self._feature_names):
                indicators.append(self._feature_names[idx])
        
        return indicators
    
    def _generate_preventive_actions(
        self,
        health: ComponentHealth,
        failure_type: Optional[FailureType],
        risk_factors: list[dict[str, Any]],
    ) -> list[str]:
        """Generate recommended preventive actions.
        
        Args:
            health: Component health metrics
            failure_type: Predicted failure type
            risk_factors: Identified risk factors
            
        Returns:
            List of recommended actions
        """
        actions = []
        
        if failure_type == FailureType.OOM:
            actions.append("Increase memory limits for the component")
            actions.append("Review application for memory leaks")
            actions.append("Consider adding memory caching eviction")
        
        elif failure_type == FailureType.DISK_FULL:
            actions.append("Clean up unused data and logs")
            actions.append("Increase disk allocation")
            actions.append("Implement log rotation")
        
        elif failure_type == FailureType.TIMEOUT:
            actions.append("Review slow database queries")
            actions.append("Check downstream service health")
            actions.append("Consider increasing timeout limits")
        
        elif failure_type == FailureType.CRASH:
            actions.append("Review recent code changes")
            actions.append("Check application logs for errors")
            actions.append("Consider rolling back recent deployments")
        
        # Add generic actions based on risk factors
        for factor in risk_factors:
            if factor["factor"] == "high_cpu_usage":
                actions.append("Scale up CPU resources or add replicas")
            elif factor["factor"] == "frequent_restarts":
                actions.append("Investigate crash loop causes")
                actions.append("Check resource limits and health probes")
        
        return list(set(actions))  # Remove duplicates
    
    def evaluate(
        self,
        X: list[ComponentHealth],
        y: np.ndarray,
    ) -> EvaluationMetrics:
        """Evaluate the model.
        
        Args:
            X: Component health data
            y: True failure labels
            
        Returns:
            Evaluation metrics
        """
        import time
        start_time = time.time()
        
        y = np.asarray(y).flatten()
        
        # Make predictions
        predictions = []
        probabilities = []
        
        for health in X:
            result = self.predict(health)
            prob = result.prediction.failure_probability
            probabilities.append(prob)
            predictions.append(1 if prob >= self.failure_threshold else 0)
        
        predictions = np.array(predictions)
        probabilities = np.array(probabilities)
        
        # Calculate metrics
        cls_metrics = ClassificationMetrics.compute(y, predictions, probabilities)
        
        return EvaluationMetrics(
            accuracy=cls_metrics.accuracy,
            precision=cls_metrics.precision,
            recall=cls_metrics.recall,
            f1_score=cls_metrics.f1_score,
            auc_roc=cls_metrics.auc_roc,
            dataset_size=len(y),
            evaluation_time_seconds=(time.time() - start_time),
        )
    
    def get_feature_importance(self) -> dict[str, float]:
        """Get feature importance based on weights."""
        if self._weights is None:
            return {}
        
        importance = {}
        weights_abs = np.abs(self._weights)
        total = np.sum(weights_abs)
        
        if total > 0:
            for i, name in enumerate(self._feature_names):
                if i < len(self._weights):
                    importance[name] = float(weights_abs[i] / total)
        
        return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))
