"""
Anomaly Detection for AutoSRE V2.

Statistical and ML-based anomaly detection with:
- Z-Score detector for Gaussian distributions
- IQR (Interquartile Range) for robust detection
- DBSCAN for density-based clustering
- Isolation Forest for outlier detection
- Ensemble methods for combining detectors
"""

from __future__ import annotations

import math
import statistics
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional, Sequence, TypeVar

import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from autosre.utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound="BaseDetector")


class AnomalyType(str, Enum):
    """Type of detected anomaly."""
    
    SPIKE = "spike"  # Sudden increase
    DIP = "dip"  # Sudden decrease
    LEVEL_SHIFT = "level_shift"  # Sustained change
    TREND_CHANGE = "trend_change"  # Change in trend
    SEASONALITY_VIOLATION = "seasonality_violation"
    OUTLIER = "outlier"  # General outlier
    CLUSTER = "cluster"  # Anomalous cluster
    UNKNOWN = "unknown"


class AnomalySeverity(str, Enum):
    """Severity of the anomaly."""
    
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class DetectionMethod(str, Enum):
    """Anomaly detection method used."""
    
    ZSCORE = "zscore"
    IQR = "iqr"
    DBSCAN = "dbscan"
    ISOLATION_FOREST = "isolation_forest"
    MAD = "mad"  # Median Absolute Deviation
    ENSEMBLE = "ensemble"
    PROPHET = "prophet"
    ARIMA = "arima"


@dataclass
class SeasonalityConfig:
    """Configuration for seasonality detection."""
    
    enabled: bool = True
    periods: list[int] = field(default_factory=lambda: [24, 168])  # hourly, weekly
    min_samples_for_detection: int = 100
    fourier_order: int = 3


@dataclass
class AnomalyConfig:
    """Configuration for anomaly detection."""
    
    # Z-Score settings
    zscore_threshold: float = 3.0
    zscore_modified: bool = True  # Use modified z-score (MAD-based)
    
    # IQR settings
    iqr_multiplier: float = 1.5
    iqr_use_log_transform: bool = False
    
    # DBSCAN settings
    dbscan_eps: float = 0.5
    dbscan_min_samples: int = 5
    dbscan_metric: str = "euclidean"
    
    # Isolation Forest settings
    isolation_contamination: float = 0.1
    isolation_n_estimators: int = 100
    isolation_max_samples: int = 256
    
    # General settings
    min_samples: int = 10
    lookback_samples: int = 100
    sensitivity: float = 1.0  # Multiplier for thresholds
    seasonality: SeasonalityConfig = field(default_factory=SeasonalityConfig)
    
    # Ensemble settings
    ensemble_min_votes: int = 2
    ensemble_methods: list[DetectionMethod] = field(
        default_factory=lambda: [
            DetectionMethod.ZSCORE,
            DetectionMethod.IQR,
        ]
    )


@dataclass
class AnomalyResult:
    """Result of anomaly detection for a single point or window."""
    
    # Core detection info
    is_anomaly: bool
    anomaly_score: float  # 0-1 normalized score
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    method: DetectionMethod
    
    # Context
    timestamp: Optional[datetime] = None
    value: Optional[float] = None
    expected_value: Optional[float] = None
    deviation: Optional[float] = None
    
    # Thresholds
    upper_bound: Optional[float] = None
    lower_bound: Optional[float] = None
    
    # Metadata
    metric_name: Optional[str] = None
    labels: dict[str, str] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)
    
    @property
    def deviation_percentage(self) -> Optional[float]:
        """Calculate percentage deviation from expected."""
        if self.expected_value is None or self.value is None:
            return None
        if self.expected_value == 0:
            return None
        return abs(self.value - self.expected_value) / abs(self.expected_value) * 100
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "is_anomaly": self.is_anomaly,
            "anomaly_score": self.anomaly_score,
            "anomaly_type": self.anomaly_type.value,
            "severity": self.severity.value,
            "method": self.method.value,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "value": self.value,
            "expected_value": self.expected_value,
            "deviation": self.deviation,
            "upper_bound": self.upper_bound,
            "lower_bound": self.lower_bound,
            "metric_name": self.metric_name,
            "labels": self.labels,
            "details": self.details,
        }


class BaseDetector(ABC):
    """Abstract base class for anomaly detectors."""
    
    def __init__(self, config: Optional[AnomalyConfig] = None):
        self.config = config or AnomalyConfig()
    
    @property
    @abstractmethod
    def method(self) -> DetectionMethod:
        """Return the detection method type."""
        ...
    
    @abstractmethod
    def fit(self, values: Sequence[float]) -> None:
        """Fit the detector to historical data."""
        ...
    
    @abstractmethod
    def detect(
        self,
        value: float,
        timestamp: Optional[datetime] = None,
    ) -> AnomalyResult:
        """Detect if a single value is anomalous."""
        ...
    
    @abstractmethod
    def detect_batch(
        self,
        values: Sequence[float],
        timestamps: Optional[Sequence[datetime]] = None,
    ) -> list[AnomalyResult]:
        """Detect anomalies in a batch of values."""
        ...
    
    def _determine_anomaly_type(
        self,
        value: float,
        expected: float,
    ) -> AnomalyType:
        """Determine the type of anomaly based on direction."""
        if value > expected:
            return AnomalyType.SPIKE
        elif value < expected:
            return AnomalyType.DIP
        return AnomalyType.OUTLIER
    
    def _calculate_severity(
        self,
        anomaly_score: float,
    ) -> AnomalySeverity:
        """Calculate severity from anomaly score."""
        if anomaly_score >= 0.9:
            return AnomalySeverity.CRITICAL
        elif anomaly_score >= 0.7:
            return AnomalySeverity.HIGH
        elif anomaly_score >= 0.5:
            return AnomalySeverity.MEDIUM
        elif anomaly_score >= 0.3:
            return AnomalySeverity.LOW
        return AnomalySeverity.INFO


class ZScoreDetector(BaseDetector):
    """
    Z-Score based anomaly detection.
    
    Standard z-score: z = (x - μ) / σ
    Modified z-score: z = 0.6745 * (x - median) / MAD
    
    The modified z-score is more robust to outliers.
    """
    
    def __init__(self, config: Optional[AnomalyConfig] = None):
        super().__init__(config)
        self._mean: Optional[float] = None
        self._std: Optional[float] = None
        self._median: Optional[float] = None
        self._mad: Optional[float] = None
        self._values: list[float] = []
    
    @property
    def method(self) -> DetectionMethod:
        return DetectionMethod.ZSCORE
    
    def fit(self, values: Sequence[float]) -> None:
        """Fit the detector to historical data."""
        if len(values) < self.config.min_samples:
            logger.warning(
                f"Insufficient samples for ZScore fitting: {len(values)} < {self.config.min_samples}"
            )
            return
        
        values_list = list(values)
        self._values = values_list[-self.config.lookback_samples:]
        
        # Calculate standard statistics
        self._mean = statistics.mean(values_list)
        self._std = statistics.stdev(values_list) if len(values_list) > 1 else 0.0
        
        # Calculate robust statistics for modified z-score
        self._median = statistics.median(values_list)
        deviations = [abs(x - self._median) for x in values_list]
        self._mad = statistics.median(deviations) if deviations else 0.0
        
        logger.debug(
            f"ZScore fitted: mean={self._mean:.3f}, std={self._std:.3f}, "
            f"median={self._median:.3f}, MAD={self._mad:.3f}"
        )
    
    def _calculate_zscore(self, value: float) -> float:
        """Calculate z-score for a value."""
        if self.config.zscore_modified:
            # Modified z-score using MAD
            if self._mad is None or self._mad == 0:
                return 0.0
            return 0.6745 * (value - (self._median or 0)) / self._mad
        else:
            # Standard z-score
            if self._std is None or self._std == 0:
                return 0.0
            return (value - (self._mean or 0)) / self._std
    
    def detect(
        self,
        value: float,
        timestamp: Optional[datetime] = None,
    ) -> AnomalyResult:
        """Detect if a single value is anomalous."""
        if self._mean is None:
            # Not fitted, can't detect
            return AnomalyResult(
                is_anomaly=False,
                anomaly_score=0.0,
                anomaly_type=AnomalyType.UNKNOWN,
                severity=AnomalySeverity.INFO,
                method=self.method,
                timestamp=timestamp,
                value=value,
                details={"error": "Detector not fitted"},
            )
        
        zscore = self._calculate_zscore(value)
        threshold = self.config.zscore_threshold * self.config.sensitivity
        
        is_anomaly = abs(zscore) > threshold
        
        # Normalize score to 0-1 range
        # Using sigmoid-like transformation
        anomaly_score = min(1.0, abs(zscore) / (2 * threshold))
        
        expected = self._median if self.config.zscore_modified else self._mean
        deviation = value - (expected or 0)
        
        # Calculate bounds
        if self.config.zscore_modified:
            bound_width = threshold * (self._mad or 0) / 0.6745
        else:
            bound_width = threshold * (self._std or 0)
        
        upper_bound = (expected or 0) + bound_width
        lower_bound = (expected or 0) - bound_width
        
        return AnomalyResult(
            is_anomaly=is_anomaly,
            anomaly_score=anomaly_score,
            anomaly_type=self._determine_anomaly_type(value, expected or 0),
            severity=self._calculate_severity(anomaly_score),
            method=self.method,
            timestamp=timestamp,
            value=value,
            expected_value=expected,
            deviation=deviation,
            upper_bound=upper_bound,
            lower_bound=lower_bound,
            details={
                "zscore": zscore,
                "threshold": threshold,
                "modified": self.config.zscore_modified,
            },
        )
    
    def detect_batch(
        self,
        values: Sequence[float],
        timestamps: Optional[Sequence[datetime]] = None,
    ) -> list[AnomalyResult]:
        """Detect anomalies in a batch of values."""
        results = []
        ts_list = list(timestamps) if timestamps else [None] * len(values)
        
        for value, ts in zip(values, ts_list):
            results.append(self.detect(value, ts))
            
            # Online update: add value to rolling window
            self._values.append(value)
            if len(self._values) > self.config.lookback_samples:
                self._values = self._values[-self.config.lookback_samples:]
            
            # Recompute statistics periodically
            if len(results) % 10 == 0:
                self.fit(self._values)
        
        return results


class IQRDetector(BaseDetector):
    """
    Interquartile Range (IQR) based anomaly detection.
    
    A value is anomalous if it falls outside:
    [Q1 - k*IQR, Q3 + k*IQR]
    
    Where k is typically 1.5 (mild outlier) or 3.0 (extreme outlier).
    """
    
    def __init__(self, config: Optional[AnomalyConfig] = None):
        super().__init__(config)
        self._q1: Optional[float] = None
        self._q3: Optional[float] = None
        self._iqr: Optional[float] = None
        self._median: Optional[float] = None
        self._values: list[float] = []
    
    @property
    def method(self) -> DetectionMethod:
        return DetectionMethod.IQR
    
    def fit(self, values: Sequence[float]) -> None:
        """Fit the detector to historical data."""
        if len(values) < self.config.min_samples:
            logger.warning(
                f"Insufficient samples for IQR fitting: {len(values)} < {self.config.min_samples}"
            )
            return
        
        values_list = list(values)
        self._values = values_list[-self.config.lookback_samples:]
        
        # Optionally apply log transform for skewed data
        if self.config.iqr_use_log_transform:
            transformed = [math.log1p(max(0, v)) for v in values_list]
        else:
            transformed = values_list
        
        sorted_vals = sorted(transformed)
        n = len(sorted_vals)
        
        # Calculate quartiles
        self._q1 = sorted_vals[n // 4]
        self._q3 = sorted_vals[3 * n // 4]
        self._iqr = self._q3 - self._q1
        self._median = statistics.median(transformed)
        
        logger.debug(
            f"IQR fitted: Q1={self._q1:.3f}, Q3={self._q3:.3f}, "
            f"IQR={self._iqr:.3f}, median={self._median:.3f}"
        )
    
    def detect(
        self,
        value: float,
        timestamp: Optional[datetime] = None,
    ) -> AnomalyResult:
        """Detect if a single value is anomalous."""
        if self._q1 is None or self._iqr is None:
            return AnomalyResult(
                is_anomaly=False,
                anomaly_score=0.0,
                anomaly_type=AnomalyType.UNKNOWN,
                severity=AnomalySeverity.INFO,
                method=self.method,
                timestamp=timestamp,
                value=value,
                details={"error": "Detector not fitted"},
            )
        
        # Apply same transform if enabled
        if self.config.iqr_use_log_transform:
            test_value = math.log1p(max(0, value))
        else:
            test_value = value
        
        multiplier = self.config.iqr_multiplier * self.config.sensitivity
        
        lower_bound = self._q1 - multiplier * self._iqr
        upper_bound = self._q3 + multiplier * self._iqr
        
        is_anomaly = test_value < lower_bound or test_value > upper_bound
        
        # Calculate anomaly score based on distance from bounds
        if test_value < lower_bound:
            distance = lower_bound - test_value
        elif test_value > upper_bound:
            distance = test_value - upper_bound
        else:
            distance = 0.0
        
        # Normalize by IQR
        if self._iqr > 0:
            anomaly_score = min(1.0, distance / (2 * self._iqr))
        else:
            anomaly_score = 0.0
        
        # Transform bounds back if needed
        if self.config.iqr_use_log_transform:
            lower_bound = math.expm1(lower_bound)
            upper_bound = math.expm1(upper_bound)
        
        return AnomalyResult(
            is_anomaly=is_anomaly,
            anomaly_score=anomaly_score,
            anomaly_type=self._determine_anomaly_type(value, self._median or 0),
            severity=self._calculate_severity(anomaly_score),
            method=self.method,
            timestamp=timestamp,
            value=value,
            expected_value=self._median,
            deviation=value - (self._median or 0),
            upper_bound=upper_bound,
            lower_bound=lower_bound,
            details={
                "q1": self._q1,
                "q3": self._q3,
                "iqr": self._iqr,
                "multiplier": multiplier,
            },
        )
    
    def detect_batch(
        self,
        values: Sequence[float],
        timestamps: Optional[Sequence[datetime]] = None,
    ) -> list[AnomalyResult]:
        """Detect anomalies in a batch of values."""
        results = []
        ts_list = list(timestamps) if timestamps else [None] * len(values)
        
        for value, ts in zip(values, ts_list):
            results.append(self.detect(value, ts))
        
        return results


class DBSCANDetector(BaseDetector):
    """
    DBSCAN-based anomaly detection.
    
    Points that don't belong to any cluster are considered anomalies.
    Good for detecting outliers in multivariate data or unusual patterns.
    """
    
    def __init__(self, config: Optional[AnomalyConfig] = None):
        super().__init__(config)
        self._fitted = False
        self._cluster_centers: list[np.ndarray] = []
        self._cluster_sizes: list[int] = []
        self._values: list[float] = []
    
    @property
    def method(self) -> DetectionMethod:
        return DetectionMethod.DBSCAN
    
    def _create_features(self, values: Sequence[float]) -> np.ndarray:
        """Create feature matrix from values (using sliding windows)."""
        arr = np.array(values)
        n = len(arr)
        
        # Create sliding window features
        window_size = min(5, n // 2)
        if window_size < 2:
            # Not enough data, return simple 2D features
            return np.column_stack([arr, np.gradient(arr) if len(arr) > 1 else np.zeros_like(arr)])
        
        features = []
        for i in range(n):
            start = max(0, i - window_size + 1)
            window = arr[start:i + 1]
            
            # Features: value, rolling mean, rolling std, trend
            feat = [
                arr[i],
                np.mean(window),
                np.std(window) if len(window) > 1 else 0,
                np.gradient(window)[-1] if len(window) > 1 else 0,
            ]
            features.append(feat)
        
        return np.array(features)
    
    def fit(self, values: Sequence[float]) -> None:
        """Fit the detector to historical data."""
        if len(values) < self.config.min_samples:
            logger.warning(
                f"Insufficient samples for DBSCAN fitting: {len(values)} < {self.config.min_samples}"
            )
            return
        
        self._values = list(values)[-self.config.lookback_samples:]
        
        # Create feature matrix
        X = self._create_features(self._values)
        
        # Normalize features
        X_mean = np.mean(X, axis=0)
        X_std = np.std(X, axis=0) + 1e-8
        X_normalized = (X - X_mean) / X_std
        
        # Simple DBSCAN implementation
        labels = self._dbscan(
            X_normalized,
            eps=self.config.dbscan_eps,
            min_samples=self.config.dbscan_min_samples,
        )
        
        # Calculate cluster centers (excluding noise points labeled -1)
        unique_labels = set(labels) - {-1}
        self._cluster_centers = []
        self._cluster_sizes = []
        
        for label in unique_labels:
            mask = labels == label
            cluster_points = X[mask]
            self._cluster_centers.append(np.mean(cluster_points, axis=0))
            self._cluster_sizes.append(np.sum(mask))
        
        self._fitted = True
        logger.debug(f"DBSCAN fitted: {len(self._cluster_centers)} clusters found")
    
    def _dbscan(
        self,
        X: np.ndarray,
        eps: float,
        min_samples: int,
    ) -> np.ndarray:
        """
        Simple DBSCAN implementation.
        
        Returns array of cluster labels (-1 for noise).
        """
        n_samples = X.shape[0]
        labels = np.full(n_samples, -1)
        cluster_id = 0
        
        for i in range(n_samples):
            if labels[i] != -1:
                continue
            
            # Find neighbors
            distances = np.linalg.norm(X - X[i], axis=1)
            neighbors = np.where(distances <= eps)[0]
            
            if len(neighbors) < min_samples:
                # Mark as noise (for now)
                continue
            
            # Start new cluster
            labels[i] = cluster_id
            seeds = list(neighbors)
            seeds.remove(i)
            
            while seeds:
                q = seeds.pop(0)
                if labels[q] == -1:
                    labels[q] = cluster_id
                elif labels[q] != cluster_id:
                    continue
                
                # Find neighbors of q
                q_distances = np.linalg.norm(X - X[q], axis=1)
                q_neighbors = np.where(q_distances <= eps)[0]
                
                if len(q_neighbors) >= min_samples:
                    for neighbor in q_neighbors:
                        if labels[neighbor] == -1:
                            seeds.append(neighbor)
                            labels[neighbor] = cluster_id
            
            cluster_id += 1
        
        return labels
    
    def detect(
        self,
        value: float,
        timestamp: Optional[datetime] = None,
    ) -> AnomalyResult:
        """Detect if a single value is anomalous."""
        if not self._fitted or not self._cluster_centers:
            return AnomalyResult(
                is_anomaly=False,
                anomaly_score=0.0,
                anomaly_type=AnomalyType.UNKNOWN,
                severity=AnomalySeverity.INFO,
                method=self.method,
                timestamp=timestamp,
                value=value,
                details={"error": "Detector not fitted"},
            )
        
        # Add value to recent window and create features
        test_values = self._values[-10:] + [value]
        X = self._create_features(test_values)
        point = X[-1]  # Feature vector for the new value
        
        # Find minimum distance to any cluster center
        min_distance = float("inf")
        nearest_cluster = -1
        
        for idx, center in enumerate(self._cluster_centers):
            if len(center) != len(point):
                continue
            dist = np.linalg.norm(point - center)
            if dist < min_distance:
                min_distance = dist
                nearest_cluster = idx
        
        # Determine if point is anomalous based on distance
        eps = self.config.dbscan_eps * self.config.sensitivity
        is_anomaly = min_distance > eps * 2  # Point far from any cluster
        
        # Calculate anomaly score
        anomaly_score = min(1.0, min_distance / (eps * 4))
        
        # Estimate expected value from nearest cluster
        if nearest_cluster >= 0 and len(self._cluster_centers[nearest_cluster]) > 0:
            expected = float(self._cluster_centers[nearest_cluster][0])
        else:
            expected = statistics.mean(self._values) if self._values else value
        
        return AnomalyResult(
            is_anomaly=is_anomaly,
            anomaly_score=anomaly_score,
            anomaly_type=AnomalyType.CLUSTER if is_anomaly else AnomalyType.UNKNOWN,
            severity=self._calculate_severity(anomaly_score),
            method=self.method,
            timestamp=timestamp,
            value=value,
            expected_value=expected,
            deviation=value - expected,
            details={
                "min_distance": min_distance,
                "eps": eps,
                "nearest_cluster": nearest_cluster,
                "num_clusters": len(self._cluster_centers),
            },
        )
    
    def detect_batch(
        self,
        values: Sequence[float],
        timestamps: Optional[Sequence[datetime]] = None,
    ) -> list[AnomalyResult]:
        """Detect anomalies in a batch of values."""
        results = []
        ts_list = list(timestamps) if timestamps else [None] * len(values)
        
        for value, ts in zip(values, ts_list):
            results.append(self.detect(value, ts))
        
        return results


class IsolationForestDetector(BaseDetector):
    """
    Isolation Forest based anomaly detection.
    
    Anomalies are isolated faster than normal points
    because they are "few and different".
    """
    
    def __init__(self, config: Optional[AnomalyConfig] = None):
        super().__init__(config)
        self._trees: list[dict] = []
        self._fitted = False
        self._values: list[float] = []
        self._mean: Optional[float] = None
        self._std: Optional[float] = None
    
    @property
    def method(self) -> DetectionMethod:
        return DetectionMethod.ISOLATION_FOREST
    
    def fit(self, values: Sequence[float]) -> None:
        """Fit the detector by building isolation trees."""
        if len(values) < self.config.min_samples:
            logger.warning(
                f"Insufficient samples for Isolation Forest: {len(values)} < {self.config.min_samples}"
            )
            return
        
        values_list = list(values)
        self._values = values_list[-self.config.lookback_samples:]
        self._mean = statistics.mean(values_list)
        self._std = statistics.stdev(values_list) if len(values_list) > 1 else 1.0
        
        # Sample data points
        sample_size = min(self.config.isolation_max_samples, len(self._values))
        
        # Build trees
        self._trees = []
        for _ in range(self.config.isolation_n_estimators):
            # Random sample with replacement
            indices = np.random.choice(len(self._values), sample_size, replace=True)
            sample = [self._values[i] for i in indices]
            tree = self._build_tree(sample, depth=0, max_depth=int(np.ceil(np.log2(sample_size))))
            self._trees.append(tree)
        
        self._fitted = True
        logger.debug(f"Isolation Forest fitted: {len(self._trees)} trees built")
    
    def _build_tree(
        self,
        data: list[float],
        depth: int,
        max_depth: int,
    ) -> dict:
        """Build a single isolation tree."""
        if depth >= max_depth or len(data) <= 1:
            return {"type": "leaf", "size": len(data)}
        
        # Random split
        min_val, max_val = min(data), max(data)
        if min_val == max_val:
            return {"type": "leaf", "size": len(data)}
        
        split_value = np.random.uniform(min_val, max_val)
        
        left_data = [x for x in data if x < split_value]
        right_data = [x for x in data if x >= split_value]
        
        # Avoid empty splits
        if not left_data or not right_data:
            return {"type": "leaf", "size": len(data)}
        
        return {
            "type": "split",
            "split_value": split_value,
            "left": self._build_tree(left_data, depth + 1, max_depth),
            "right": self._build_tree(right_data, depth + 1, max_depth),
        }
    
    def _path_length(self, value: float, tree: dict, depth: int = 0) -> float:
        """Calculate path length for a value in a tree."""
        if tree["type"] == "leaf":
            # Add correction factor for unbuilt subtrees
            n = tree["size"]
            if n <= 1:
                return depth
            return depth + self._c(n)
        
        if value < tree["split_value"]:
            return self._path_length(value, tree["left"], depth + 1)
        return self._path_length(value, tree["right"], depth + 1)
    
    def _c(self, n: int) -> float:
        """Average path length of unsuccessful search in BST."""
        if n <= 1:
            return 0
        return 2 * (np.log(n - 1) + 0.5772156649) - 2 * (n - 1) / n
    
    def detect(
        self,
        value: float,
        timestamp: Optional[datetime] = None,
    ) -> AnomalyResult:
        """Detect if a single value is anomalous."""
        if not self._fitted or not self._trees:
            return AnomalyResult(
                is_anomaly=False,
                anomaly_score=0.0,
                anomaly_type=AnomalyType.UNKNOWN,
                severity=AnomalySeverity.INFO,
                method=self.method,
                timestamp=timestamp,
                value=value,
                details={"error": "Detector not fitted"},
            )
        
        # Calculate average path length
        path_lengths = [self._path_length(value, tree) for tree in self._trees]
        avg_path_length = np.mean(path_lengths)
        
        # Calculate anomaly score
        n = len(self._values)
        c_n = self._c(n)
        
        if c_n == 0:
            anomaly_score = 0.5
        else:
            anomaly_score = 2 ** (-avg_path_length / c_n)
        
        # Threshold based on contamination parameter
        threshold = 1 - self.config.isolation_contamination * self.config.sensitivity
        is_anomaly = anomaly_score > threshold
        
        return AnomalyResult(
            is_anomaly=is_anomaly,
            anomaly_score=anomaly_score,
            anomaly_type=AnomalyType.OUTLIER if is_anomaly else AnomalyType.UNKNOWN,
            severity=self._calculate_severity(anomaly_score),
            method=self.method,
            timestamp=timestamp,
            value=value,
            expected_value=self._mean,
            deviation=value - (self._mean or 0),
            details={
                "avg_path_length": avg_path_length,
                "threshold": threshold,
                "num_trees": len(self._trees),
            },
        )
    
    def detect_batch(
        self,
        values: Sequence[float],
        timestamps: Optional[Sequence[datetime]] = None,
    ) -> list[AnomalyResult]:
        """Detect anomalies in a batch of values."""
        results = []
        ts_list = list(timestamps) if timestamps else [None] * len(values)
        
        for value, ts in zip(values, ts_list):
            results.append(self.detect(value, ts))
        
        return results


class EnsembleDetector(BaseDetector):
    """
    Ensemble anomaly detector combining multiple methods.
    
    Uses voting or score averaging to combine detections.
    """
    
    def __init__(
        self,
        config: Optional[AnomalyConfig] = None,
        detectors: Optional[list[BaseDetector]] = None,
    ):
        super().__init__(config)
        
        if detectors:
            self._detectors = detectors
        else:
            # Default ensemble
            self._detectors = [
                ZScoreDetector(config),
                IQRDetector(config),
            ]
            
            # Add more sophisticated detectors if configured
            if DetectionMethod.DBSCAN in self.config.ensemble_methods:
                self._detectors.append(DBSCANDetector(config))
            if DetectionMethod.ISOLATION_FOREST in self.config.ensemble_methods:
                self._detectors.append(IsolationForestDetector(config))
    
    @property
    def method(self) -> DetectionMethod:
        return DetectionMethod.ENSEMBLE
    
    def fit(self, values: Sequence[float]) -> None:
        """Fit all detectors."""
        for detector in self._detectors:
            detector.fit(values)
    
    def detect(
        self,
        value: float,
        timestamp: Optional[datetime] = None,
    ) -> AnomalyResult:
        """
        Detect using ensemble voting.
        
        A point is anomalous if at least min_votes detectors agree.
        """
        results = [d.detect(value, timestamp) for d in self._detectors]
        
        # Count votes
        votes = sum(1 for r in results if r.is_anomaly)
        is_anomaly = votes >= self.config.ensemble_min_votes
        
        # Average scores
        anomaly_score = statistics.mean(r.anomaly_score for r in results)
        
        # Use most severe type from voting detectors
        anomaly_types = [r.anomaly_type for r in results if r.is_anomaly]
        if anomaly_types:
            # Priority order
            type_priority = {
                AnomalyType.CRITICAL: 0,
                AnomalyType.SPIKE: 1,
                AnomalyType.DIP: 2,
                AnomalyType.LEVEL_SHIFT: 3,
                AnomalyType.TREND_CHANGE: 4,
                AnomalyType.OUTLIER: 5,
            }
            anomaly_type = min(anomaly_types, key=lambda t: type_priority.get(t, 10))
        else:
            anomaly_type = AnomalyType.UNKNOWN
        
        # Aggregate bounds
        valid_uppers = [r.upper_bound for r in results if r.upper_bound is not None]
        valid_lowers = [r.lower_bound for r in results if r.lower_bound is not None]
        valid_expected = [r.expected_value for r in results if r.expected_value is not None]
        
        return AnomalyResult(
            is_anomaly=is_anomaly,
            anomaly_score=anomaly_score,
            anomaly_type=anomaly_type,
            severity=self._calculate_severity(anomaly_score),
            method=self.method,
            timestamp=timestamp,
            value=value,
            expected_value=statistics.mean(valid_expected) if valid_expected else None,
            deviation=value - statistics.mean(valid_expected) if valid_expected else None,
            upper_bound=statistics.mean(valid_uppers) if valid_uppers else None,
            lower_bound=statistics.mean(valid_lowers) if valid_lowers else None,
            details={
                "votes": votes,
                "min_votes_required": self.config.ensemble_min_votes,
                "methods": [d.method.value for d in self._detectors],
                "individual_results": [r.to_dict() for r in results],
            },
        )
    
    def detect_batch(
        self,
        values: Sequence[float],
        timestamps: Optional[Sequence[datetime]] = None,
    ) -> list[AnomalyResult]:
        """Detect anomalies in a batch of values."""
        results = []
        ts_list = list(timestamps) if timestamps else [None] * len(values)
        
        for value, ts in zip(values, ts_list):
            results.append(self.detect(value, ts))
        
        return results


class AnomalyDetector:
    """
    High-level anomaly detector for AutoSRE.
    
    Provides a unified interface for multiple detection methods
    with automatic method selection and parameter tuning.
    
    Example:
        detector = AnomalyDetector()
        detector.fit(historical_values)
        
        result = detector.detect(new_value)
        if result.is_anomaly:
            print(f"Anomaly detected: {result.anomaly_type}")
    """
    
    def __init__(
        self,
        config: Optional[AnomalyConfig] = None,
        method: DetectionMethod = DetectionMethod.ENSEMBLE,
    ):
        self.config = config or AnomalyConfig()
        self._method = method
        self._detector = self._create_detector(method)
        self._fitted = False
    
    def _create_detector(self, method: DetectionMethod) -> BaseDetector:
        """Create detector instance for the given method."""
        if method == DetectionMethod.ZSCORE:
            return ZScoreDetector(self.config)
        elif method == DetectionMethod.IQR:
            return IQRDetector(self.config)
        elif method == DetectionMethod.DBSCAN:
            return DBSCANDetector(self.config)
        elif method == DetectionMethod.ISOLATION_FOREST:
            return IsolationForestDetector(self.config)
        elif method == DetectionMethod.ENSEMBLE:
            return EnsembleDetector(self.config)
        else:
            return EnsembleDetector(self.config)
    
    def fit(
        self,
        values: Sequence[float],
        timestamps: Optional[Sequence[datetime]] = None,
    ) -> "AnomalyDetector":
        """Fit the detector to historical data."""
        if len(values) < self.config.min_samples:
            logger.warning(
                f"Insufficient samples for fitting: {len(values)} < {self.config.min_samples}"
            )
            return self
        
        self._detector.fit(values)
        self._fitted = True
        return self
    
    def detect(
        self,
        value: float,
        timestamp: Optional[datetime] = None,
        metric_name: Optional[str] = None,
        labels: Optional[dict[str, str]] = None,
    ) -> AnomalyResult:
        """Detect if a value is anomalous."""
        result = self._detector.detect(value, timestamp)
        
        # Add metadata
        if metric_name:
            result.metric_name = metric_name
        if labels:
            result.labels = labels
        
        return result
    
    def detect_batch(
        self,
        values: Sequence[float],
        timestamps: Optional[Sequence[datetime]] = None,
        metric_name: Optional[str] = None,
        labels: Optional[dict[str, str]] = None,
    ) -> list[AnomalyResult]:
        """Detect anomalies in a batch of values."""
        results = self._detector.detect_batch(values, timestamps)
        
        # Add metadata to all results
        for result in results:
            if metric_name:
                result.metric_name = metric_name
            if labels:
                result.labels = labels
        
        return results
    
    def set_method(self, method: DetectionMethod) -> "AnomalyDetector":
        """Change the detection method."""
        self._method = method
        self._detector = self._create_detector(method)
        self._fitted = False
        return self
    
    @property
    def method(self) -> DetectionMethod:
        """Get current detection method."""
        return self._method
    
    @property
    def is_fitted(self) -> bool:
        """Check if detector is fitted."""
        return self._fitted
