"""Time series anomaly detection."""

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
from autosre.ml.common.preprocessing import TimeSeriesPreprocessor


class AnomalyType(str, Enum):
    """Type of time series anomaly."""
    POINT = "point"  # Single point anomaly
    CONTEXTUAL = "contextual"  # Anomaly given context
    COLLECTIVE = "collective"  # Pattern anomaly
    TREND = "trend"  # Trend change
    LEVEL_SHIFT = "level_shift"  # Level shift
    SEASONALITY = "seasonality"  # Seasonality change


class AnomalySeverity(str, Enum):
    """Severity of anomaly."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TimeSeriesAnomaly(BaseModel):
    """Detected time series anomaly."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    anomaly_id: str = Field(default_factory=generate_id)
    
    # Type and severity
    anomaly_type: AnomalyType = Field(default=AnomalyType.POINT)
    severity: AnomalySeverity = Field(default=AnomalySeverity.MEDIUM)
    
    # Timing
    start_index: int = Field(default=0, ge=0)
    end_index: int = Field(default=0, ge=0)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_samples: int = Field(default=1, ge=1)
    
    # Values
    observed_value: float = Field(default=0.0)
    expected_value: float = Field(default=0.0)
    deviation: float = Field(default=0.0)
    
    # Scores
    anomaly_score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Statistical info
    z_score: Optional[float] = None
    percentile: Optional[float] = None
    
    # Context
    metric_name: str = Field(default="")
    component: str = Field(default="")
    labels: dict[str, str] = Field(default_factory=dict)
    
    # Metadata
    detected_at: datetime = Field(default_factory=utc_now)


class AnomalyDetectionResult(BaseModel):
    """Result of anomaly detection on a time series."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    # Anomalies found
    anomalies: list[TimeSeriesAnomaly] = Field(default_factory=list)
    anomaly_count: int = Field(default=0, ge=0)
    
    # Series info
    series_length: int = Field(default=0, ge=0)
    anomaly_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Per-point scores
    anomaly_scores: list[float] = Field(default_factory=list)
    is_anomaly: list[bool] = Field(default_factory=list)
    
    # Thresholds used
    threshold: float = Field(default=0.0)
    adaptive_threshold: bool = Field(default=False)
    
    # Model info
    model_id: str = Field(default="")
    model_version: str = Field(default="")
    
    # Timing
    detection_time_ms: float = Field(default=0.0, ge=0.0)
    detected_at: datetime = Field(default_factory=utc_now)


class TimeSeriesAnomalyDetector(BaseMLModel[np.ndarray, AnomalyDetectionResult]):
    """Detect anomalies in time series data.
    
    Supports multiple detection methods:
    - Statistical (z-score, IQR, MAD)
    - Moving average based
    - Exponential smoothing
    - Seasonal decomposition
    
    Features:
    - Adaptive thresholds
    - Multiple anomaly types
    - Seasonality awareness
    - Online detection
    """
    
    def __init__(
        self,
        method: str = "zscore",
        threshold: float = 3.0,
        window_size: int = 24,
        min_periods: int = 10,
        adaptive_threshold: bool = True,
        seasonality_period: Optional[int] = None,
    ):
        """Initialize the detector.
        
        Args:
            method: Detection method ('zscore', 'iqr', 'mad', 'isolation_forest')
            threshold: Anomaly threshold (meaning depends on method)
            window_size: Window size for rolling statistics
            min_periods: Minimum periods for statistics
            adaptive_threshold: Use adaptive thresholds
            seasonality_period: Period for seasonality (e.g., 24 for hourly)
        """
        super().__init__(
            name="timeseries_anomaly_detector",
            model_type="anomaly_detector",
            hyperparameters={
                "method": method,
                "threshold": threshold,
                "window_size": window_size,
                "min_periods": min_periods,
                "adaptive_threshold": adaptive_threshold,
                "seasonality_period": seasonality_period,
            },
        )
        
        self.method = method
        self.threshold = threshold
        self.window_size = window_size
        self.min_periods = min_periods
        self.adaptive_threshold = adaptive_threshold
        self.seasonality_period = seasonality_period
        
        # Preprocessing
        self._preprocessor = TimeSeriesPreprocessor(normalize=False)
        
        # Fitted parameters
        self._mean: float = 0.0
        self._std: float = 1.0
        self._median: float = 0.0
        self._mad: float = 1.0
        self._q1: float = 0.0
        self._q3: float = 1.0
        self._iqr: float = 1.0
        
        # Seasonal baselines
        self._seasonal_baseline: Optional[np.ndarray] = None
        self._seasonal_std: Optional[np.ndarray] = None
        
        # History for online detection
        self._history: list[float] = []
        self._max_history: int = 1000
    
    def fit(
        self,
        X: np.ndarray,
        y: Optional[np.ndarray] = None,
        timestamps: Optional[np.ndarray] = None,
        config: Optional[TrainingConfig] = None,
    ) -> "TimeSeriesAnomalyDetector":
        """Fit the detector to training data.
        
        Args:
            X: Training time series (should be normal data)
            y: Not used
            timestamps: Timestamps (optional)
            config: Training configuration
            
        Returns:
            Self
        """
        X = np.asarray(X).flatten()
        
        # Basic statistics
        self._mean = float(np.mean(X))
        self._std = float(np.std(X))
        if self._std == 0:
            self._std = 1.0
        
        self._median = float(np.median(X))
        self._mad = float(np.median(np.abs(X - self._median)))
        if self._mad == 0:
            self._mad = 1.0
        
        self._q1 = float(np.percentile(X, 25))
        self._q3 = float(np.percentile(X, 75))
        self._iqr = self._q3 - self._q1
        if self._iqr == 0:
            self._iqr = 1.0
        
        # Seasonal baseline if period specified
        if self.seasonality_period and len(X) >= self.seasonality_period * 2:
            self._fit_seasonal_baseline(X)
        
        # Store history
        self._history = list(X[-self._max_history:])
        
        self._is_fitted = True
        self._metadata.status = ModelStatus.TRAINED
        self._metadata.last_trained_at = utc_now()
        
        version = ModelVersion(
            description=f"Trained on {len(X)} samples using {self.method}",
            metrics={
                "mean": self._mean,
                "std": self._std,
                "median": self._median,
            },
        )
        self._metadata.add_version(version)
        
        return self
    
    def _fit_seasonal_baseline(self, X: np.ndarray) -> None:
        """Fit seasonal baseline from data.
        
        Args:
            X: Training data
        """
        period = self.seasonality_period
        n = len(X)
        n_cycles = n // period
        
        if n_cycles < 2:
            return
        
        # Calculate mean and std for each position in cycle
        baseline = np.zeros(period)
        baseline_std = np.zeros(period)
        
        for i in range(period):
            values_at_position = X[i::period]
            baseline[i] = np.mean(values_at_position)
            baseline_std[i] = np.std(values_at_position)
        
        self._seasonal_baseline = baseline
        self._seasonal_std = baseline_std
    
    def predict(
        self,
        X: np.ndarray,
        timestamps: Optional[np.ndarray] = None,
        metric_name: str = "",
        component: str = "",
    ) -> PredictionResult[AnomalyDetectionResult]:
        """Detect anomalies in time series.
        
        Args:
            X: Time series to analyze
            timestamps: Timestamps (optional)
            metric_name: Name of metric
            component: Component name
            
        Returns:
            Anomaly detection result
        """
        import time
        start_time = time.time()
        
        if not self._is_fitted:
            # Auto-fit on first window
            if len(X) >= self.min_periods:
                self.fit(X[:self.min_periods])
            else:
                raise ValueError("Model not fitted and not enough data to auto-fit")
        
        X = np.asarray(X).flatten()
        n = len(X)
        
        # Calculate anomaly scores
        anomaly_scores = self._calculate_anomaly_scores(X)
        
        # Determine threshold
        if self.adaptive_threshold:
            effective_threshold = self._calculate_adaptive_threshold(anomaly_scores)
        else:
            effective_threshold = self.threshold
        
        # Identify anomalies
        is_anomaly = anomaly_scores > effective_threshold
        
        # Group consecutive anomalies and create anomaly objects
        anomalies = self._extract_anomalies(
            X, anomaly_scores, is_anomaly, timestamps, metric_name, component
        )
        
        # Create result
        result = AnomalyDetectionResult(
            anomalies=anomalies,
            anomaly_count=len(anomalies),
            series_length=n,
            anomaly_ratio=np.sum(is_anomaly) / n if n > 0 else 0,
            anomaly_scores=anomaly_scores.tolist(),
            is_anomaly=is_anomaly.tolist(),
            threshold=effective_threshold,
            adaptive_threshold=self.adaptive_threshold,
            model_id=self.model_id,
            model_version=self._metadata.current_version.version_id if self._metadata.current_version else "",
            detection_time_ms=(time.time() - start_time) * 1000,
        )
        
        latency = (time.time() - start_time) * 1000
        
        return PredictionResult(
            prediction=result,
            confidence=0.9 if anomalies else 1.0,
            model_id=self.model_id,
            model_version=self._metadata.current_version.version_id if self._metadata.current_version else "",
            latency_ms=latency,
        )
    
    def _calculate_anomaly_scores(self, X: np.ndarray) -> np.ndarray:
        """Calculate anomaly scores for each point.
        
        Args:
            X: Time series values
            
        Returns:
            Anomaly scores
        """
        n = len(X)
        scores = np.zeros(n)
        
        if self.method == "zscore":
            # Z-score method
            if self._seasonal_baseline is not None:
                # Use seasonal baseline
                for i in range(n):
                    pos = i % len(self._seasonal_baseline)
                    baseline = self._seasonal_baseline[pos]
                    std = max(self._seasonal_std[pos], 0.001)
                    scores[i] = abs(X[i] - baseline) / std
            else:
                scores = np.abs(X - self._mean) / self._std
        
        elif self.method == "iqr":
            # IQR method
            lower = self._q1 - self.threshold * self._iqr
            upper = self._q3 + self.threshold * self._iqr
            
            for i in range(n):
                if X[i] < lower:
                    scores[i] = (lower - X[i]) / self._iqr
                elif X[i] > upper:
                    scores[i] = (X[i] - upper) / self._iqr
                else:
                    scores[i] = 0
        
        elif self.method == "mad":
            # Median Absolute Deviation method
            scores = np.abs(X - self._median) / (self._mad * 1.4826)
        
        elif self.method == "rolling":
            # Rolling statistics method
            for i in range(n):
                start = max(0, i - self.window_size)
                window = X[start:i] if i > start else X[:i+1]
                
                if len(window) >= self.min_periods:
                    window_mean = np.mean(window)
                    window_std = np.std(window)
                    if window_std > 0:
                        scores[i] = abs(X[i] - window_mean) / window_std
                    else:
                        scores[i] = 0
                else:
                    scores[i] = 0
        
        else:
            # Default to z-score
            scores = np.abs(X - self._mean) / self._std
        
        return scores
    
    def _calculate_adaptive_threshold(self, scores: np.ndarray) -> float:
        """Calculate adaptive threshold based on score distribution.
        
        Args:
            scores: Anomaly scores
            
        Returns:
            Adaptive threshold
        """
        # Use percentile-based threshold
        base_threshold = self.threshold
        
        # Adjust based on score distribution
        score_mean = np.mean(scores)
        score_std = np.std(scores)
        
        if score_std > 0:
            adaptive = score_mean + base_threshold * score_std
        else:
            adaptive = base_threshold
        
        # Don't go below base threshold
        return max(adaptive, base_threshold * 0.5)
    
    def _extract_anomalies(
        self,
        X: np.ndarray,
        scores: np.ndarray,
        is_anomaly: np.ndarray,
        timestamps: Optional[np.ndarray],
        metric_name: str,
        component: str,
    ) -> List[TimeSeriesAnomaly]:
        """Extract anomaly objects from detection results.
        
        Args:
            X: Time series values
            scores: Anomaly scores
            is_anomaly: Boolean anomaly flags
            timestamps: Timestamps
            metric_name: Metric name
            component: Component name
            
        Returns:
            List of anomaly objects
        """
        anomalies = []
        n = len(X)
        
        # Find contiguous anomaly regions
        i = 0
        while i < n:
            if not is_anomaly[i]:
                i += 1
                continue
            
            # Start of anomaly region
            start = i
            while i < n and is_anomaly[i]:
                i += 1
            end = i - 1
            
            # Calculate anomaly properties
            region_values = X[start:end+1]
            region_scores = scores[start:end+1]
            
            max_score_idx = np.argmax(region_scores)
            max_score = float(region_scores[max_score_idx])
            observed = float(region_values[max_score_idx])
            
            # Expected value
            if self._seasonal_baseline is not None:
                pos = (start + max_score_idx) % len(self._seasonal_baseline)
                expected = float(self._seasonal_baseline[pos])
            else:
                expected = self._mean
            
            # Determine type
            anomaly_type = self._determine_anomaly_type(
                X, start, end, region_scores
            )
            
            # Determine severity
            severity = self._determine_severity(max_score)
            
            # Calculate z-score and percentile
            z_score = (observed - self._mean) / self._std if self._std > 0 else 0
            
            # Get timestamps if available
            start_time = timestamps[start] if timestamps is not None and start < len(timestamps) else None
            end_time = timestamps[end] if timestamps is not None and end < len(timestamps) else None
            
            anomaly = TimeSeriesAnomaly(
                anomaly_type=anomaly_type,
                severity=severity,
                start_index=start,
                end_index=end,
                start_time=start_time,
                end_time=end_time,
                duration_samples=end - start + 1,
                observed_value=observed,
                expected_value=expected,
                deviation=observed - expected,
                anomaly_score=max_score,
                confidence=min(max_score / self.threshold, 1.0) if self.threshold > 0 else 1.0,
                z_score=float(z_score),
                metric_name=metric_name,
                component=component,
            )
            
            anomalies.append(anomaly)
        
        return anomalies
    
    def _determine_anomaly_type(
        self,
        X: np.ndarray,
        start: int,
        end: int,
        region_scores: np.ndarray,
    ) -> AnomalyType:
        """Determine the type of anomaly.
        
        Args:
            X: Full time series
            start: Start index
            end: End index
            region_scores: Scores in anomaly region
            
        Returns:
            Anomaly type
        """
        duration = end - start + 1
        
        # Point anomaly
        if duration == 1:
            return AnomalyType.POINT
        
        # Check for level shift
        if duration >= 5 and end < len(X) - 1:
            before_mean = np.mean(X[max(0, start-10):start])
            region_mean = np.mean(X[start:end+1])
            after_mean = np.mean(X[end+1:min(len(X), end+11)])
            
            if abs(region_mean - before_mean) > 2 * self._std and abs(after_mean - region_mean) < self._std:
                return AnomalyType.LEVEL_SHIFT
        
        # Check for trend change
        if duration >= 3:
            region_values = X[start:end+1]
            diffs = np.diff(region_values)
            if np.all(diffs > 0) or np.all(diffs < 0):
                return AnomalyType.TREND
        
        # Collective anomaly
        if duration > 3:
            return AnomalyType.COLLECTIVE
        
        return AnomalyType.CONTEXTUAL
    
    def _determine_severity(self, score: float) -> AnomalySeverity:
        """Determine anomaly severity based on score.
        
        Args:
            score: Anomaly score
            
        Returns:
            Severity level
        """
        if score >= self.threshold * 3:
            return AnomalySeverity.CRITICAL
        elif score >= self.threshold * 2:
            return AnomalySeverity.HIGH
        elif score >= self.threshold * 1.5:
            return AnomalySeverity.MEDIUM
        else:
            return AnomalySeverity.LOW
    
    def detect_online(
        self,
        value: float,
        timestamp: Optional[datetime] = None,
    ) -> Optional[TimeSeriesAnomaly]:
        """Detect anomaly for a single new value (online detection).
        
        Args:
            value: New value
            timestamp: Timestamp
            
        Returns:
            Anomaly if detected, None otherwise
        """
        if not self._is_fitted:
            raise ValueError("Model not fitted")
        
        # Calculate score
        if self._seasonal_baseline is not None:
            pos = len(self._history) % len(self._seasonal_baseline)
            baseline = self._seasonal_baseline[pos]
            std = max(self._seasonal_std[pos], 0.001)
            score = abs(value - baseline) / std
            expected = baseline
        else:
            score = abs(value - self._mean) / self._std
            expected = self._mean
        
        # Update history
        self._history.append(value)
        if len(self._history) > self._max_history:
            self._history.pop(0)
        
        # Check if anomaly
        if score > self.threshold:
            return TimeSeriesAnomaly(
                anomaly_type=AnomalyType.POINT,
                severity=self._determine_severity(score),
                start_index=len(self._history) - 1,
                end_index=len(self._history) - 1,
                start_time=timestamp,
                end_time=timestamp,
                duration_samples=1,
                observed_value=value,
                expected_value=expected,
                deviation=value - expected,
                anomaly_score=score,
                confidence=min(score / self.threshold, 1.0),
            )
        
        return None
    
    def evaluate(
        self,
        X: np.ndarray,
        y: np.ndarray,
    ) -> EvaluationMetrics:
        """Evaluate the detector.
        
        Args:
            X: Time series
            y: True anomaly labels (1 = anomaly, 0 = normal)
            
        Returns:
            Evaluation metrics
        """
        import time
        start_time = time.time()
        
        result = self.predict(X)
        predictions = np.array(result.prediction.is_anomaly)
        y = np.asarray(y).flatten()
        
        # Ensure same length
        min_len = min(len(predictions), len(y))
        predictions = predictions[:min_len]
        y = y[:min_len]
        
        # Calculate metrics
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
            custom_metrics={
                "true_positives": float(tp),
                "false_positives": float(fp),
                "false_negatives": float(fn),
            },
            dataset_size=len(y),
            evaluation_time_seconds=(time.time() - start_time),
        )
    
    def get_feature_importance(self) -> dict[str, float]:
        """Get importance of detection features."""
        return {
            "mean": 0.3,
            "std": 0.3,
            "seasonality": 0.2 if self._seasonal_baseline is not None else 0.0,
            "iqr": 0.2 if self.method == "iqr" else 0.0,
        }
