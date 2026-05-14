"""Multivariate anomaly detection."""

from datetime import datetime
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


class MultiVariateAnomaly(BaseModel):
    """Multivariate anomaly detection result."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    anomaly_id: str = Field(default_factory=generate_id)
    
    # Index and timing
    index: int = Field(default=0, ge=0)
    timestamp: Optional[datetime] = None
    
    # Scores
    anomaly_score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Feature contributions
    feature_scores: dict[str, float] = Field(default_factory=dict)
    top_contributing_features: list[str] = Field(default_factory=list)
    
    # Values
    observed_values: dict[str, float] = Field(default_factory=dict)
    expected_values: dict[str, float] = Field(default_factory=dict)
    deviations: dict[str, float] = Field(default_factory=dict)
    
    # Correlation info
    correlated_features: list[tuple[str, str]] = Field(default_factory=list)
    correlation_anomaly: bool = Field(default=False)
    
    # Metadata
    detected_at: datetime = Field(default_factory=utc_now)


class MultiVariateResult(BaseModel):
    """Result of multivariate anomaly detection."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    anomalies: list[MultiVariateAnomaly] = Field(default_factory=list)
    anomaly_count: int = Field(default=0, ge=0)
    
    # Per-point scores
    anomaly_scores: list[float] = Field(default_factory=list)
    is_anomaly: list[bool] = Field(default_factory=list)
    
    # Feature info
    feature_names: list[str] = Field(default_factory=list)
    feature_importance: dict[str, float] = Field(default_factory=dict)
    
    # Correlation anomalies
    correlation_anomalies: int = Field(default=0, ge=0)
    
    # Statistics
    sample_count: int = Field(default=0, ge=0)
    anomaly_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Model info
    model_id: str = Field(default="")
    threshold: float = Field(default=0.0)
    
    # Timing
    detection_time_ms: float = Field(default=0.0, ge=0.0)
    detected_at: datetime = Field(default_factory=utc_now)


class MultiVariateDetector(BaseMLModel[np.ndarray, MultiVariateResult]):
    """Detect multivariate anomalies.
    
    Analyzes multiple features together to detect:
    - Joint anomalies
    - Correlation anomalies
    - Collective anomalies
    
    Methods:
    - Mahalanobis distance
    - PCA reconstruction error
    - Isolation Forest
    - Correlation-based detection
    """
    
    def __init__(
        self,
        method: str = "mahalanobis",
        threshold: float = 3.0,
        contamination: float = 0.1,
        detect_correlation_anomalies: bool = True,
    ):
        """Initialize the detector.
        
        Args:
            method: Detection method
            threshold: Anomaly threshold
            contamination: Expected proportion of anomalies
            detect_correlation_anomalies: Detect correlation changes
        """
        super().__init__(
            name="multivariate_anomaly_detector",
            model_type="multivariate_anomaly_detector",
            hyperparameters={
                "method": method,
                "threshold": threshold,
                "contamination": contamination,
                "detect_correlation_anomalies": detect_correlation_anomalies,
            },
        )
        
        self.method = method
        self.threshold = threshold
        self.contamination = contamination
        self.detect_correlation_anomalies = detect_correlation_anomalies
        
        # Fitted parameters
        self._mean: Optional[np.ndarray] = None
        self._cov: Optional[np.ndarray] = None
        self._cov_inv: Optional[np.ndarray] = None
        self._feature_names: List[str] = []
        self._n_features: int = 0
        
        # Correlation matrix
        self._correlation_matrix: Optional[np.ndarray] = None
        
        # PCA components (for reconstruction method)
        self._pca_components: Optional[np.ndarray] = None
        self._pca_explained_variance: Optional[np.ndarray] = None
        
        # Per-feature statistics
        self._feature_means: Optional[np.ndarray] = None
        self._feature_stds: Optional[np.ndarray] = None
    
    def fit(
        self,
        X: np.ndarray,
        y: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None,
        config: Optional[TrainingConfig] = None,
    ) -> "MultiVariateDetector":
        """Fit the detector to training data.
        
        Args:
            X: Training data (n_samples, n_features)
            y: Not used
            feature_names: Names of features
            config: Training configuration
            
        Returns:
            Self
        """
        X = np.asarray(X)
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        
        n_samples, n_features = X.shape
        self._n_features = n_features
        
        # Set feature names
        if feature_names is not None:
            self._feature_names = feature_names
        else:
            self._feature_names = [f"feature_{i}" for i in range(n_features)]
        
        # Calculate mean and covariance
        self._mean = np.mean(X, axis=0)
        self._cov = np.cov(X, rowvar=False)
        
        # Ensure covariance matrix is invertible
        if n_features == 1:
            self._cov = np.array([[self._cov]])
        
        # Add small regularization for numerical stability
        self._cov = self._cov + np.eye(n_features) * 1e-6
        
        try:
            self._cov_inv = np.linalg.inv(self._cov)
        except np.linalg.LinAlgError:
            # Use pseudo-inverse if singular
            self._cov_inv = np.linalg.pinv(self._cov)
        
        # Per-feature statistics
        self._feature_means = np.mean(X, axis=0)
        self._feature_stds = np.std(X, axis=0)
        self._feature_stds[self._feature_stds == 0] = 1.0
        
        # Correlation matrix
        self._correlation_matrix = np.corrcoef(X, rowvar=False)
        if self._correlation_matrix.ndim == 0:
            self._correlation_matrix = np.array([[1.0]])
        
        # PCA for reconstruction method
        if self.method == "pca" and n_features > 1:
            self._fit_pca(X)
        
        self._is_fitted = True
        self._metadata.status = ModelStatus.TRAINED
        self._metadata.last_trained_at = utc_now()
        
        version = ModelVersion(
            description=f"Trained on {n_samples} samples with {n_features} features",
            metrics={
                "n_samples": float(n_samples),
                "n_features": float(n_features),
            },
        )
        self._metadata.add_version(version)
        
        return self
    
    def _fit_pca(self, X: np.ndarray) -> None:
        """Fit PCA for reconstruction-based detection.
        
        Args:
            X: Training data
        """
        # Center data
        X_centered = X - self._mean
        
        # Compute SVD
        U, S, Vt = np.linalg.svd(X_centered, full_matrices=False)
        
        # Store components
        self._pca_components = Vt
        self._pca_explained_variance = (S ** 2) / (len(X) - 1)
    
    def predict(
        self,
        X: np.ndarray,
        timestamps: Optional[np.ndarray] = None,
    ) -> PredictionResult[MultiVariateResult]:
        """Detect multivariate anomalies.
        
        Args:
            X: Data to analyze
            timestamps: Timestamps (optional)
            
        Returns:
            Detection result
        """
        import time
        start_time = time.time()
        
        if not self._is_fitted:
            self.fit(X)
        
        X = np.asarray(X)
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        
        n_samples = len(X)
        
        # Calculate anomaly scores
        if self.method == "mahalanobis":
            scores = self._mahalanobis_scores(X)
        elif self.method == "pca":
            scores = self._pca_reconstruction_scores(X)
        else:
            scores = self._mahalanobis_scores(X)
        
        # Determine threshold
        if self.contamination > 0:
            # Use contamination-based threshold
            threshold = np.percentile(scores, (1 - self.contamination) * 100)
        else:
            threshold = self.threshold
        
        is_anomaly = scores > threshold
        
        # Extract anomalies with details
        anomalies = []
        for i in np.where(is_anomaly)[0]:
            anomaly = self._create_anomaly(
                i, X[i], scores[i], timestamps[i] if timestamps is not None and i < len(timestamps) else None
            )
            anomalies.append(anomaly)
        
        # Detect correlation anomalies
        correlation_anomalies = 0
        if self.detect_correlation_anomalies and n_samples >= 10:
            correlation_anomalies = self._detect_correlation_anomalies(X)
        
        # Feature importance (based on variance contribution)
        feature_importance = {}
        if self._feature_stds is not None:
            total_var = np.sum(self._feature_stds ** 2)
            for i, name in enumerate(self._feature_names):
                feature_importance[name] = float(self._feature_stds[i] ** 2 / total_var)
        
        result = MultiVariateResult(
            anomalies=anomalies,
            anomaly_count=len(anomalies),
            anomaly_scores=scores.tolist(),
            is_anomaly=is_anomaly.tolist(),
            feature_names=self._feature_names,
            feature_importance=feature_importance,
            correlation_anomalies=correlation_anomalies,
            sample_count=n_samples,
            anomaly_ratio=float(np.sum(is_anomaly) / n_samples),
            model_id=self.model_id,
            threshold=float(threshold),
            detection_time_ms=(time.time() - start_time) * 1000,
        )
        
        return PredictionResult(
            prediction=result,
            confidence=0.8,
            model_id=self.model_id,
            latency_ms=(time.time() - start_time) * 1000,
        )
    
    def _mahalanobis_scores(self, X: np.ndarray) -> np.ndarray:
        """Calculate Mahalanobis distance scores.
        
        Args:
            X: Data
            
        Returns:
            Anomaly scores
        """
        diff = X - self._mean
        
        # Mahalanobis distance
        left = np.dot(diff, self._cov_inv)
        mahal = np.sqrt(np.sum(left * diff, axis=1))
        
        return mahal
    
    def _pca_reconstruction_scores(self, X: np.ndarray) -> np.ndarray:
        """Calculate PCA reconstruction error scores.
        
        Args:
            X: Data
            
        Returns:
            Anomaly scores
        """
        if self._pca_components is None:
            return self._mahalanobis_scores(X)
        
        # Center data
        X_centered = X - self._mean
        
        # Project and reconstruct
        projected = np.dot(X_centered, self._pca_components.T)
        reconstructed = np.dot(projected, self._pca_components)
        
        # Reconstruction error
        error = np.sqrt(np.sum((X_centered - reconstructed) ** 2, axis=1))
        
        return error
    
    def _create_anomaly(
        self,
        index: int,
        values: np.ndarray,
        score: float,
        timestamp: Optional[datetime],
    ) -> MultiVariateAnomaly:
        """Create anomaly object with details.
        
        Args:
            index: Sample index
            values: Feature values
            score: Anomaly score
            timestamp: Timestamp
            
        Returns:
            Anomaly object
        """
        # Calculate per-feature scores
        feature_scores = {}
        observed = {}
        expected = {}
        deviations = {}
        
        for i, name in enumerate(self._feature_names):
            if i < len(values):
                z = (values[i] - self._feature_means[i]) / self._feature_stds[i]
                feature_scores[name] = float(abs(z))
                observed[name] = float(values[i])
                expected[name] = float(self._feature_means[i])
                deviations[name] = float(z)
        
        # Top contributing features
        top_features = sorted(
            feature_scores.keys(),
            key=lambda k: feature_scores[k],
            reverse=True
        )[:5]
        
        return MultiVariateAnomaly(
            index=index,
            timestamp=timestamp,
            anomaly_score=min(score / self.threshold, 1.0) if self.threshold > 0 else 1.0,
            confidence=0.8,
            feature_scores=feature_scores,
            top_contributing_features=top_features,
            observed_values=observed,
            expected_values=expected,
            deviations=deviations,
        )
    
    def _detect_correlation_anomalies(self, X: np.ndarray) -> int:
        """Detect anomalies in feature correlations.
        
        Args:
            X: Data
            
        Returns:
            Number of correlation anomalies
        """
        if X.shape[1] < 2:
            return 0
        
        # Calculate correlation for new data
        new_corr = np.corrcoef(X, rowvar=False)
        
        if new_corr.ndim == 0:
            return 0
        
        # Compare with baseline
        corr_diff = np.abs(new_corr - self._correlation_matrix)
        
        # Count significant changes
        anomalies = np.sum(corr_diff > 0.3)  # Threshold for correlation change
        
        return int(anomalies)
    
    def evaluate(
        self,
        X: np.ndarray,
        y: np.ndarray,
    ) -> EvaluationMetrics:
        """Evaluate the detector."""
        import time
        start_time = time.time()
        
        result = self.predict(X)
        predictions = np.array(result.prediction.is_anomaly)
        y = np.asarray(y).flatten()
        
        min_len = min(len(predictions), len(y))
        predictions = predictions[:min_len]
        y = y[:min_len]
        
        tp = np.sum((predictions == 1) & (y == 1))
        tn = np.sum((predictions == 0) & (y == 0))
        fp = np.sum((predictions == 1) & (y == 0))
        fn = np.sum((predictions == 0) & (y == 1))
        
        accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        return EvaluationMetrics(
            accuracy=float(accuracy),
            precision=float(precision),
            recall=float(recall),
            f1_score=float(f1),
            dataset_size=len(y),
            evaluation_time_seconds=(time.time() - start_time),
        )
    
    def get_feature_importance(self) -> dict[str, float]:
        """Get feature importance."""
        if self._feature_stds is None:
            return {}
        
        total_var = np.sum(self._feature_stds ** 2)
        return {
            name: float(self._feature_stds[i] ** 2 / total_var)
            for i, name in enumerate(self._feature_names)
        }
