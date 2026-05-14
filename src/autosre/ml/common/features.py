"""Feature extraction and engineering utilities."""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Optional, List, Union
from enum import Enum

import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from autosre.models.common import utc_now


class ScalerType(str, Enum):
    """Type of feature scaling."""
    STANDARD = "standard"
    MINMAX = "minmax"
    ROBUST = "robust"
    MAXABS = "maxabs"


class FeatureImportance(BaseModel):
    """Feature importance information."""
    model_config = ConfigDict(validate_assignment=True)
    
    feature_name: str
    importance_score: float = Field(ge=0.0)
    rank: int = Field(ge=1)
    importance_type: str = Field(default="weight")  # weight, gain, cover, shap
    
    def __lt__(self, other: "FeatureImportance") -> bool:
        return self.importance_score < other.importance_score


class FeatureSet(BaseModel):
    """A set of features with metadata."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )
    
    feature_names: list[str] = Field(default_factory=list)
    feature_values: list[list[float]] = Field(default_factory=list)
    
    # Metadata
    num_samples: int = Field(default=0, ge=0)
    num_features: int = Field(default=0, ge=0)
    
    # Timestamps
    extracted_at: datetime = Field(default_factory=utc_now)
    
    # Statistics
    means: dict[str, float] = Field(default_factory=dict)
    stds: dict[str, float] = Field(default_factory=dict)
    mins: dict[str, float] = Field(default_factory=dict)
    maxs: dict[str, float] = Field(default_factory=dict)
    
    @classmethod
    def from_numpy(
        cls,
        X: np.ndarray,
        feature_names: Optional[list[str]] = None,
    ) -> "FeatureSet":
        """Create FeatureSet from numpy array."""
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        
        num_samples, num_features = X.shape
        
        if feature_names is None:
            feature_names = [f"feature_{i}" for i in range(num_features)]
        
        # Compute statistics
        means = {name: float(np.mean(X[:, i])) for i, name in enumerate(feature_names)}
        stds = {name: float(np.std(X[:, i])) for i, name in enumerate(feature_names)}
        mins = {name: float(np.min(X[:, i])) for i, name in enumerate(feature_names)}
        maxs = {name: float(np.max(X[:, i])) for i, name in enumerate(feature_names)}
        
        return cls(
            feature_names=feature_names,
            feature_values=X.tolist(),
            num_samples=num_samples,
            num_features=num_features,
            means=means,
            stds=stds,
            mins=mins,
            maxs=maxs,
        )
    
    def to_numpy(self) -> np.ndarray:
        """Convert to numpy array."""
        return np.array(self.feature_values)
    
    def select_features(self, names: list[str]) -> "FeatureSet":
        """Select a subset of features."""
        indices = [self.feature_names.index(n) for n in names if n in self.feature_names]
        X = self.to_numpy()
        X_selected = X[:, indices]
        return FeatureSet.from_numpy(X_selected, names)


class FeatureScaler:
    """Scale features using various methods."""
    
    def __init__(
        self,
        method: ScalerType = ScalerType.STANDARD,
        feature_range: tuple[float, float] = (0, 1),
    ):
        """Initialize the scaler.
        
        Args:
            method: Scaling method
            feature_range: Range for MinMax scaling
        """
        self.method = method
        self.feature_range = feature_range
        
        # Fitted parameters
        self._fitted = False
        self._means: Optional[np.ndarray] = None
        self._stds: Optional[np.ndarray] = None
        self._mins: Optional[np.ndarray] = None
        self._maxs: Optional[np.ndarray] = None
        self._medians: Optional[np.ndarray] = None
        self._iqrs: Optional[np.ndarray] = None
    
    def fit(self, X: np.ndarray) -> "FeatureScaler":
        """Fit the scaler to data.
        
        Args:
            X: Data to fit
            
        Returns:
            Self
        """
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        
        if self.method == ScalerType.STANDARD:
            self._means = np.mean(X, axis=0)
            self._stds = np.std(X, axis=0)
            self._stds[self._stds == 0] = 1  # Avoid division by zero
        
        elif self.method == ScalerType.MINMAX:
            self._mins = np.min(X, axis=0)
            self._maxs = np.max(X, axis=0)
            ranges = self._maxs - self._mins
            ranges[ranges == 0] = 1  # Avoid division by zero
        
        elif self.method == ScalerType.ROBUST:
            self._medians = np.median(X, axis=0)
            q75 = np.percentile(X, 75, axis=0)
            q25 = np.percentile(X, 25, axis=0)
            self._iqrs = q75 - q25
            self._iqrs[self._iqrs == 0] = 1  # Avoid division by zero
        
        elif self.method == ScalerType.MAXABS:
            self._maxs = np.max(np.abs(X), axis=0)
            self._maxs[self._maxs == 0] = 1  # Avoid division by zero
        
        self._fitted = True
        return self
    
    def transform(self, X: np.ndarray) -> np.ndarray:
        """Transform data.
        
        Args:
            X: Data to transform
            
        Returns:
            Transformed data
        """
        if not self._fitted:
            raise ValueError("Scaler not fitted. Call fit() first.")
        
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        
        if self.method == ScalerType.STANDARD:
            return (X - self._means) / self._stds
        
        elif self.method == ScalerType.MINMAX:
            X_scaled = (X - self._mins) / (self._maxs - self._mins)
            min_val, max_val = self.feature_range
            return X_scaled * (max_val - min_val) + min_val
        
        elif self.method == ScalerType.ROBUST:
            return (X - self._medians) / self._iqrs
        
        elif self.method == ScalerType.MAXABS:
            return X / self._maxs
        
        return X
    
    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        """Fit and transform in one step."""
        return self.fit(X).transform(X)
    
    def inverse_transform(self, X: np.ndarray) -> np.ndarray:
        """Reverse the transformation.
        
        Args:
            X: Transformed data
            
        Returns:
            Original-scale data
        """
        if not self._fitted:
            raise ValueError("Scaler not fitted. Call fit() first.")
        
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        
        if self.method == ScalerType.STANDARD:
            return X * self._stds + self._means
        
        elif self.method == ScalerType.MINMAX:
            min_val, max_val = self.feature_range
            X_unscaled = (X - min_val) / (max_val - min_val)
            return X_unscaled * (self._maxs - self._mins) + self._mins
        
        elif self.method == ScalerType.ROBUST:
            return X * self._iqrs + self._medians
        
        elif self.method == ScalerType.MAXABS:
            return X * self._maxs
        
        return X


class FeatureSelector:
    """Select features based on various criteria."""
    
    def __init__(
        self,
        method: str = "variance",
        threshold: float = 0.0,
        k: Optional[int] = None,
    ):
        """Initialize the selector.
        
        Args:
            method: Selection method ('variance', 'correlation', 'importance')
            threshold: Threshold for selection
            k: Number of top features to select
        """
        self.method = method
        self.threshold = threshold
        self.k = k
        
        self._fitted = False
        self._selected_indices: list[int] = []
        self._selected_names: list[str] = []
        self._scores: dict[str, float] = {}
    
    def fit(
        self,
        X: np.ndarray,
        y: Optional[np.ndarray] = None,
        feature_names: Optional[list[str]] = None,
    ) -> "FeatureSelector":
        """Fit the selector.
        
        Args:
            X: Feature data
            y: Target data (for supervised methods)
            feature_names: Names of features
            
        Returns:
            Self
        """
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        
        n_features = X.shape[1]
        
        if feature_names is None:
            feature_names = [f"feature_{i}" for i in range(n_features)]
        
        scores = []
        
        if self.method == "variance":
            # Select features with variance above threshold
            variances = np.var(X, axis=0)
            scores = variances.tolist()
        
        elif self.method == "correlation" and y is not None:
            # Select features with high correlation to target
            for i in range(n_features):
                corr = np.corrcoef(X[:, i], y)[0, 1]
                scores.append(abs(corr) if not np.isnan(corr) else 0)
        
        elif self.method == "importance":
            # Placeholder for importance-based selection
            # Would typically use tree-based feature importance
            scores = [1.0] * n_features
        
        else:
            scores = [1.0] * n_features
        
        self._scores = {name: score for name, score in zip(feature_names, scores)}
        
        # Select based on threshold or k
        if self.k is not None:
            # Select top k features
            sorted_indices = np.argsort(scores)[::-1][:self.k]
        else:
            # Select features above threshold
            sorted_indices = [i for i, s in enumerate(scores) if s > self.threshold]
        
        self._selected_indices = sorted(sorted_indices)
        self._selected_names = [feature_names[i] for i in self._selected_indices]
        self._fitted = True
        
        return self
    
    def transform(self, X: np.ndarray) -> np.ndarray:
        """Select features from data.
        
        Args:
            X: Feature data
            
        Returns:
            Selected features
        """
        if not self._fitted:
            raise ValueError("Selector not fitted. Call fit() first.")
        
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        
        return X[:, self._selected_indices]
    
    def fit_transform(
        self,
        X: np.ndarray,
        y: Optional[np.ndarray] = None,
        feature_names: Optional[list[str]] = None,
    ) -> np.ndarray:
        """Fit and transform in one step."""
        return self.fit(X, y, feature_names).transform(X)
    
    @property
    def selected_features(self) -> list[str]:
        """Get selected feature names."""
        return self._selected_names
    
    @property
    def feature_scores(self) -> dict[str, float]:
        """Get feature scores."""
        return self._scores


class TimeSeriesFeatures:
    """Extract features from time series data."""
    
    def __init__(
        self,
        window_sizes: list[int] = [5, 10, 20, 50],
        include_stats: bool = True,
        include_trends: bool = True,
        include_seasonality: bool = False,
    ):
        """Initialize the feature extractor.
        
        Args:
            window_sizes: Rolling window sizes
            include_stats: Include statistical features
            include_trends: Include trend features
            include_seasonality: Include seasonality features
        """
        self.window_sizes = window_sizes
        self.include_stats = include_stats
        self.include_trends = include_trends
        self.include_seasonality = include_seasonality
    
    def extract(
        self,
        values: np.ndarray,
        timestamps: Optional[np.ndarray] = None,
    ) -> dict[str, float]:
        """Extract features from a time series.
        
        Args:
            values: Time series values
            timestamps: Timestamps (optional)
            
        Returns:
            Dictionary of features
        """
        features = {}
        values = np.asarray(values).flatten()
        
        if len(values) == 0:
            return features
        
        # Basic statistics
        if self.include_stats:
            features["mean"] = float(np.mean(values))
            features["std"] = float(np.std(values))
            features["min"] = float(np.min(values))
            features["max"] = float(np.max(values))
            features["median"] = float(np.median(values))
            features["range"] = features["max"] - features["min"]
            
            # Percentiles
            for p in [10, 25, 75, 90]:
                features[f"p{p}"] = float(np.percentile(values, p))
            
            # Higher moments
            if features["std"] > 0:
                features["skewness"] = float(
                    np.mean(((values - features["mean"]) / features["std"]) ** 3)
                )
                features["kurtosis"] = float(
                    np.mean(((values - features["mean"]) / features["std"]) ** 4) - 3
                )
            else:
                features["skewness"] = 0.0
                features["kurtosis"] = 0.0
            
            # Coefficient of variation
            if features["mean"] != 0:
                features["cv"] = features["std"] / abs(features["mean"])
            else:
                features["cv"] = 0.0
        
        # Rolling window features
        for window in self.window_sizes:
            if len(values) >= window:
                rolling_mean = np.convolve(values, np.ones(window)/window, mode='valid')
                rolling_std = np.array([
                    np.std(values[i:i+window]) for i in range(len(values) - window + 1)
                ])
                
                features[f"rolling_mean_{window}"] = float(rolling_mean[-1])
                features[f"rolling_std_{window}"] = float(rolling_std[-1])
                features[f"rolling_mean_diff_{window}"] = float(rolling_mean[-1] - rolling_mean[0])
        
        # Trend features
        if self.include_trends and len(values) > 1:
            # Linear trend
            x = np.arange(len(values))
            coeffs = np.polyfit(x, values, 1)
            features["trend_slope"] = float(coeffs[0])
            features["trend_intercept"] = float(coeffs[1])
            
            # Rate of change
            features["rate_of_change"] = float((values[-1] - values[0]) / len(values))
            
            # First and last values
            features["first_value"] = float(values[0])
            features["last_value"] = float(values[-1])
            
            # Percent change
            if values[0] != 0:
                features["percent_change"] = float((values[-1] - values[0]) / abs(values[0]) * 100)
            else:
                features["percent_change"] = 0.0
        
        # Seasonality features (if timestamps provided)
        if self.include_seasonality and timestamps is not None:
            # Extract hour-of-day if possible
            try:
                hours = np.array([t.hour if hasattr(t, 'hour') else 0 for t in timestamps])
                features["mean_hour"] = float(np.mean(hours))
            except Exception:
                pass
        
        return features
    
    def extract_batch(
        self,
        series_list: list[np.ndarray],
        timestamps_list: Optional[list[np.ndarray]] = None,
    ) -> list[dict[str, float]]:
        """Extract features from multiple time series.
        
        Args:
            series_list: List of time series
            timestamps_list: List of timestamp arrays
            
        Returns:
            List of feature dictionaries
        """
        results = []
        
        for i, series in enumerate(series_list):
            timestamps = timestamps_list[i] if timestamps_list else None
            features = self.extract(series, timestamps)
            results.append(features)
        
        return results


class FeatureExtractor(ABC):
    """Abstract base class for feature extractors."""
    
    @abstractmethod
    def extract(self, data: Any) -> dict[str, float]:
        """Extract features from data.
        
        Args:
            data: Input data
            
        Returns:
            Dictionary of feature names to values
        """
        pass
    
    @abstractmethod
    def get_feature_names(self) -> list[str]:
        """Get list of feature names.
        
        Returns:
            List of feature names
        """
        pass
    
    def extract_to_array(self, data: Any) -> np.ndarray:
        """Extract features as a numpy array.
        
        Args:
            data: Input data
            
        Returns:
            Feature array
        """
        features = self.extract(data)
        return np.array([features[name] for name in self.get_feature_names()])


class MetricFeatureExtractor(FeatureExtractor):
    """Extract features from metric time series."""
    
    def __init__(
        self,
        metric_name: str,
        window_minutes: int = 60,
    ):
        """Initialize the extractor.
        
        Args:
            metric_name: Name of the metric
            window_minutes: Time window for feature extraction
        """
        self.metric_name = metric_name
        self.window_minutes = window_minutes
        self._ts_features = TimeSeriesFeatures()
        self._feature_names: list[str] = []
    
    def extract(self, data: Any) -> dict[str, float]:
        """Extract features from metric data.
        
        Args:
            data: Metric time series (values array or MetricSeries)
            
        Returns:
            Feature dictionary
        """
        if hasattr(data, 'samples'):
            # It's a MetricSeries
            values = np.array([s.value for s in data.samples])
        elif isinstance(data, np.ndarray):
            values = data
        elif isinstance(data, list):
            values = np.array(data)
        else:
            raise ValueError(f"Unsupported data type: {type(data)}")
        
        features = self._ts_features.extract(values)
        
        # Prefix with metric name
        prefixed = {f"{self.metric_name}_{k}": v for k, v in features.items()}
        
        # Update feature names
        self._feature_names = list(prefixed.keys())
        
        return prefixed
    
    def get_feature_names(self) -> list[str]:
        """Get feature names."""
        return self._feature_names


class LogFeatureExtractor(FeatureExtractor):
    """Extract features from log data."""
    
    def __init__(
        self,
        window_minutes: int = 60,
        error_patterns: Optional[list[str]] = None,
    ):
        """Initialize the extractor.
        
        Args:
            window_minutes: Time window for feature extraction
            error_patterns: Patterns to look for in logs
        """
        self.window_minutes = window_minutes
        self.error_patterns = error_patterns or [
            "error", "exception", "fail", "timeout", "refused",
            "crash", "fatal", "critical", "panic", "oom"
        ]
        self._feature_names = [
            "total_logs",
            "error_count",
            "error_rate",
            "unique_messages",
            "avg_message_length",
            *[f"pattern_{p}" for p in self.error_patterns]
        ]
    
    def extract(self, data: Any) -> dict[str, float]:
        """Extract features from log data.
        
        Args:
            data: List of log messages
            
        Returns:
            Feature dictionary
        """
        if not isinstance(data, list):
            data = [data]
        
        logs = [str(log).lower() for log in data]
        
        features = {
            "total_logs": float(len(logs)),
            "error_count": 0.0,
            "error_rate": 0.0,
            "unique_messages": float(len(set(logs))),
            "avg_message_length": float(np.mean([len(log) for log in logs]) if logs else 0),
        }
        
        # Count error patterns
        for pattern in self.error_patterns:
            count = sum(1 for log in logs if pattern in log)
            features[f"pattern_{pattern}"] = float(count)
            features["error_count"] += count
        
        if features["total_logs"] > 0:
            features["error_rate"] = features["error_count"] / features["total_logs"]
        
        return features
    
    def get_feature_names(self) -> list[str]:
        """Get feature names."""
        return self._feature_names
