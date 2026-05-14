"""Data preprocessing utilities for ML models."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional, List, Union
from enum import Enum
import re

import numpy as np
from pydantic import BaseModel, Field, ConfigDict


class ImputationStrategy(str, Enum):
    """Strategy for handling missing values."""
    MEAN = "mean"
    MEDIAN = "median"
    MODE = "mode"
    ZERO = "zero"
    FORWARD_FILL = "forward_fill"
    BACKWARD_FILL = "backward_fill"
    INTERPOLATE = "interpolate"
    DROP = "drop"


class OutlierStrategy(str, Enum):
    """Strategy for handling outliers."""
    CLIP = "clip"
    REMOVE = "remove"
    REPLACE_MEAN = "replace_mean"
    REPLACE_MEDIAN = "replace_median"
    LOG_TRANSFORM = "log_transform"


class MissingValueHandler:
    """Handle missing values in data."""
    
    def __init__(
        self,
        strategy: ImputationStrategy = ImputationStrategy.MEAN,
        fill_value: Optional[float] = None,
    ):
        """Initialize the handler.
        
        Args:
            strategy: Imputation strategy
            fill_value: Value for constant imputation
        """
        self.strategy = strategy
        self.fill_value = fill_value
        
        self._fitted = False
        self._fill_values: dict[int, float] = {}
    
    def fit(self, X: np.ndarray) -> "MissingValueHandler":
        """Fit the handler to data.
        
        Args:
            X: Data with possible missing values
            
        Returns:
            Self
        """
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        
        for col in range(X.shape[1]):
            col_data = X[:, col]
            valid_data = col_data[~np.isnan(col_data)]
            
            if len(valid_data) == 0:
                self._fill_values[col] = 0.0
                continue
            
            if self.strategy == ImputationStrategy.MEAN:
                self._fill_values[col] = float(np.mean(valid_data))
            elif self.strategy == ImputationStrategy.MEDIAN:
                self._fill_values[col] = float(np.median(valid_data))
            elif self.strategy == ImputationStrategy.MODE:
                values, counts = np.unique(valid_data, return_counts=True)
                self._fill_values[col] = float(values[np.argmax(counts)])
            elif self.strategy == ImputationStrategy.ZERO:
                self._fill_values[col] = 0.0
            else:
                self._fill_values[col] = self.fill_value or 0.0
        
        self._fitted = True
        return self
    
    def transform(self, X: np.ndarray) -> np.ndarray:
        """Transform data by handling missing values.
        
        Args:
            X: Data with possible missing values
            
        Returns:
            Data with missing values handled
        """
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        
        X_transformed = X.copy()
        
        if self.strategy == ImputationStrategy.DROP:
            # Drop rows with any missing values
            mask = ~np.any(np.isnan(X_transformed), axis=1)
            return X_transformed[mask]
        
        if self.strategy == ImputationStrategy.FORWARD_FILL:
            for col in range(X.shape[1]):
                mask = np.isnan(X_transformed[:, col])
                idx = np.where(~mask, np.arange(len(mask)), 0)
                np.maximum.accumulate(idx, out=idx)
                X_transformed[:, col] = X_transformed[idx, col]
            return X_transformed
        
        if self.strategy == ImputationStrategy.BACKWARD_FILL:
            for col in range(X.shape[1]):
                mask = np.isnan(X_transformed[:, col])
                idx = np.where(~mask, np.arange(len(mask)), len(mask) - 1)
                idx = np.minimum.accumulate(idx[::-1])[::-1]
                X_transformed[:, col] = X_transformed[idx, col]
            return X_transformed
        
        if self.strategy == ImputationStrategy.INTERPOLATE:
            for col in range(X.shape[1]):
                mask = np.isnan(X_transformed[:, col])
                if np.any(mask):
                    indices = np.arange(len(X_transformed))
                    valid_indices = indices[~mask]
                    valid_values = X_transformed[~mask, col]
                    X_transformed[mask, col] = np.interp(
                        indices[mask], valid_indices, valid_values
                    )
            return X_transformed
        
        # Use fitted fill values
        if not self._fitted:
            self.fit(X)
        
        for col in range(X.shape[1]):
            mask = np.isnan(X_transformed[:, col])
            X_transformed[mask, col] = self._fill_values.get(col, 0.0)
        
        return X_transformed
    
    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        """Fit and transform in one step."""
        return self.fit(X).transform(X)


class OutlierHandler:
    """Handle outliers in data."""
    
    def __init__(
        self,
        strategy: OutlierStrategy = OutlierStrategy.CLIP,
        method: str = "iqr",
        threshold: float = 1.5,
    ):
        """Initialize the handler.
        
        Args:
            strategy: Outlier handling strategy
            method: Detection method ('iqr', 'zscore', 'percentile')
            threshold: Threshold for outlier detection
        """
        self.strategy = strategy
        self.method = method
        self.threshold = threshold
        
        self._fitted = False
        self._lower_bounds: dict[int, float] = {}
        self._upper_bounds: dict[int, float] = {}
        self._means: dict[int, float] = {}
        self._medians: dict[int, float] = {}
    
    def fit(self, X: np.ndarray) -> "OutlierHandler":
        """Fit the handler to data.
        
        Args:
            X: Data
            
        Returns:
            Self
        """
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        
        for col in range(X.shape[1]):
            col_data = X[:, col]
            valid_data = col_data[~np.isnan(col_data)]
            
            self._means[col] = float(np.mean(valid_data))
            self._medians[col] = float(np.median(valid_data))
            
            if self.method == "iqr":
                q1 = np.percentile(valid_data, 25)
                q3 = np.percentile(valid_data, 75)
                iqr = q3 - q1
                self._lower_bounds[col] = q1 - self.threshold * iqr
                self._upper_bounds[col] = q3 + self.threshold * iqr
            
            elif self.method == "zscore":
                mean = np.mean(valid_data)
                std = np.std(valid_data)
                self._lower_bounds[col] = mean - self.threshold * std
                self._upper_bounds[col] = mean + self.threshold * std
            
            elif self.method == "percentile":
                self._lower_bounds[col] = np.percentile(valid_data, self.threshold)
                self._upper_bounds[col] = np.percentile(valid_data, 100 - self.threshold)
        
        self._fitted = True
        return self
    
    def transform(self, X: np.ndarray) -> np.ndarray:
        """Transform data by handling outliers.
        
        Args:
            X: Data
            
        Returns:
            Data with outliers handled
        """
        if not self._fitted:
            self.fit(X)
        
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        
        X_transformed = X.copy()
        
        if self.strategy == OutlierStrategy.LOG_TRANSFORM:
            # Apply log transform (handle negatives)
            X_transformed = np.sign(X_transformed) * np.log1p(np.abs(X_transformed))
            return X_transformed
        
        for col in range(X.shape[1]):
            lower = self._lower_bounds[col]
            upper = self._upper_bounds[col]
            
            if self.strategy == OutlierStrategy.CLIP:
                X_transformed[:, col] = np.clip(X_transformed[:, col], lower, upper)
            
            elif self.strategy == OutlierStrategy.REMOVE:
                # Mark outliers as NaN (to be handled separately)
                mask = (X_transformed[:, col] < lower) | (X_transformed[:, col] > upper)
                X_transformed[mask, col] = np.nan
            
            elif self.strategy == OutlierStrategy.REPLACE_MEAN:
                mask = (X_transformed[:, col] < lower) | (X_transformed[:, col] > upper)
                X_transformed[mask, col] = self._means[col]
            
            elif self.strategy == OutlierStrategy.REPLACE_MEDIAN:
                mask = (X_transformed[:, col] < lower) | (X_transformed[:, col] > upper)
                X_transformed[mask, col] = self._medians[col]
        
        return X_transformed
    
    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        """Fit and transform in one step."""
        return self.fit(X).transform(X)
    
    def detect_outliers(self, X: np.ndarray) -> np.ndarray:
        """Detect outliers in data.
        
        Args:
            X: Data
            
        Returns:
            Boolean mask where True indicates outlier
        """
        if not self._fitted:
            self.fit(X)
        
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        
        mask = np.zeros(X.shape, dtype=bool)
        
        for col in range(X.shape[1]):
            lower = self._lower_bounds[col]
            upper = self._upper_bounds[col]
            mask[:, col] = (X[:, col] < lower) | (X[:, col] > upper)
        
        return mask


class DataPreprocessor:
    """Comprehensive data preprocessing pipeline."""
    
    def __init__(
        self,
        handle_missing: bool = True,
        handle_outliers: bool = True,
        missing_strategy: ImputationStrategy = ImputationStrategy.MEAN,
        outlier_strategy: OutlierStrategy = OutlierStrategy.CLIP,
    ):
        """Initialize the preprocessor.
        
        Args:
            handle_missing: Whether to handle missing values
            handle_outliers: Whether to handle outliers
            missing_strategy: Strategy for missing values
            outlier_strategy: Strategy for outliers
        """
        self.handle_missing = handle_missing
        self.handle_outliers = handle_outliers
        
        self._missing_handler = MissingValueHandler(strategy=missing_strategy) if handle_missing else None
        self._outlier_handler = OutlierHandler(strategy=outlier_strategy) if handle_outliers else None
        
        self._fitted = False
    
    def fit(self, X: np.ndarray) -> "DataPreprocessor":
        """Fit the preprocessor.
        
        Args:
            X: Data
            
        Returns:
            Self
        """
        if self._missing_handler:
            self._missing_handler.fit(X)
        if self._outlier_handler:
            # Fit on data with missing values handled
            X_no_missing = self._missing_handler.transform(X) if self._missing_handler else X
            self._outlier_handler.fit(X_no_missing)
        
        self._fitted = True
        return self
    
    def transform(self, X: np.ndarray) -> np.ndarray:
        """Transform data.
        
        Args:
            X: Data
            
        Returns:
            Preprocessed data
        """
        X_transformed = X.copy()
        
        if self._missing_handler:
            X_transformed = self._missing_handler.transform(X_transformed)
        
        if self._outlier_handler:
            X_transformed = self._outlier_handler.transform(X_transformed)
        
        return X_transformed
    
    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        """Fit and transform in one step."""
        return self.fit(X).transform(X)


class TimeSeriesPreprocessor:
    """Preprocessing specifically for time series data."""
    
    def __init__(
        self,
        resample_interval: Optional[str] = None,
        fill_gaps: bool = True,
        normalize: bool = True,
        detrend: bool = False,
        remove_seasonality: bool = False,
    ):
        """Initialize the preprocessor.
        
        Args:
            resample_interval: Resample interval (e.g., '1min', '5min')
            fill_gaps: Fill gaps in time series
            normalize: Normalize values
            detrend: Remove trend
            remove_seasonality: Remove seasonal component
        """
        self.resample_interval = resample_interval
        self.fill_gaps = fill_gaps
        self.normalize = normalize
        self.detrend = detrend
        self.remove_seasonality = remove_seasonality
        
        self._fitted = False
        self._mean: Optional[float] = None
        self._std: Optional[float] = None
        self._trend_coeffs: Optional[np.ndarray] = None
    
    def fit(
        self,
        values: np.ndarray,
        timestamps: Optional[np.ndarray] = None,
    ) -> "TimeSeriesPreprocessor":
        """Fit the preprocessor.
        
        Args:
            values: Time series values
            timestamps: Timestamps
            
        Returns:
            Self
        """
        values = np.asarray(values).flatten()
        
        # Remove NaNs for fitting
        valid_mask = ~np.isnan(values)
        valid_values = values[valid_mask]
        
        if len(valid_values) == 0:
            self._mean = 0.0
            self._std = 1.0
            self._fitted = True
            return self
        
        # Compute normalization parameters
        if self.normalize:
            self._mean = float(np.mean(valid_values))
            self._std = float(np.std(valid_values))
            if self._std == 0:
                self._std = 1.0
        
        # Compute trend parameters
        if self.detrend:
            x = np.arange(len(values))
            valid_x = x[valid_mask]
            self._trend_coeffs = np.polyfit(valid_x, valid_values, 1)
        
        self._fitted = True
        return self
    
    def transform(
        self,
        values: np.ndarray,
        timestamps: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """Transform time series data.
        
        Args:
            values: Time series values
            timestamps: Timestamps
            
        Returns:
            Transformed values
        """
        values = np.asarray(values).flatten().copy()
        
        # Fill gaps
        if self.fill_gaps:
            mask = np.isnan(values)
            if np.any(mask) and np.any(~mask):
                indices = np.arange(len(values))
                valid_indices = indices[~mask]
                valid_values = values[~mask]
                values[mask] = np.interp(indices[mask], valid_indices, valid_values)
        
        # Detrend
        if self.detrend and self._trend_coeffs is not None:
            x = np.arange(len(values))
            trend = np.polyval(self._trend_coeffs, x)
            values = values - trend
        
        # Normalize
        if self.normalize and self._mean is not None:
            values = (values - self._mean) / self._std
        
        return values
    
    def inverse_transform(self, values: np.ndarray) -> np.ndarray:
        """Reverse the transformation.
        
        Args:
            values: Transformed values
            
        Returns:
            Original-scale values
        """
        values = np.asarray(values).flatten().copy()
        
        # Denormalize
        if self.normalize and self._mean is not None:
            values = values * self._std + self._mean
        
        # Add trend back (note: this is an approximation)
        if self.detrend and self._trend_coeffs is not None:
            x = np.arange(len(values))
            trend = np.polyval(self._trend_coeffs, x)
            values = values + trend
        
        return values
    
    def fit_transform(
        self,
        values: np.ndarray,
        timestamps: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """Fit and transform in one step."""
        return self.fit(values, timestamps).transform(values, timestamps)


class TextPreprocessor:
    """Preprocessing for text data."""
    
    def __init__(
        self,
        lowercase: bool = True,
        remove_punctuation: bool = True,
        remove_numbers: bool = False,
        remove_stopwords: bool = True,
        stem: bool = False,
        lemmatize: bool = False,
        min_length: int = 2,
        max_length: Optional[int] = None,
    ):
        """Initialize the preprocessor.
        
        Args:
            lowercase: Convert to lowercase
            remove_punctuation: Remove punctuation
            remove_numbers: Remove numbers
            remove_stopwords: Remove common stopwords
            stem: Apply stemming
            lemmatize: Apply lemmatization
            min_length: Minimum word length
            max_length: Maximum word length
        """
        self.lowercase = lowercase
        self.remove_punctuation = remove_punctuation
        self.remove_numbers = remove_numbers
        self.remove_stopwords = remove_stopwords
        self.stem = stem
        self.lemmatize = lemmatize
        self.min_length = min_length
        self.max_length = max_length
        
        # Common English stopwords
        self._stopwords = {
            "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "shall", "can", "need",
            "dare", "ought", "used", "this", "that", "these", "those", "i", "you",
            "he", "she", "it", "we", "they", "what", "which", "who", "whom",
            "whose", "where", "when", "why", "how", "all", "each", "every", "both",
            "few", "more", "most", "other", "some", "such", "no", "nor", "not",
            "only", "own", "same", "so", "than", "too", "very", "just", "also",
        }
    
    def preprocess(self, text: str) -> str:
        """Preprocess a single text.
        
        Args:
            text: Input text
            
        Returns:
            Preprocessed text
        """
        if not text:
            return ""
        
        # Lowercase
        if self.lowercase:
            text = text.lower()
        
        # Remove punctuation
        if self.remove_punctuation:
            text = re.sub(r'[^\w\s]', ' ', text)
        
        # Remove numbers
        if self.remove_numbers:
            text = re.sub(r'\d+', '', text)
        
        # Tokenize
        words = text.split()
        
        # Remove stopwords
        if self.remove_stopwords:
            words = [w for w in words if w not in self._stopwords]
        
        # Filter by length
        words = [w for w in words if len(w) >= self.min_length]
        if self.max_length:
            words = [w for w in words if len(w) <= self.max_length]
        
        return " ".join(words)
    
    def preprocess_batch(self, texts: list[str]) -> list[str]:
        """Preprocess multiple texts.
        
        Args:
            texts: List of texts
            
        Returns:
            List of preprocessed texts
        """
        return [self.preprocess(text) for text in texts]
    
    def tokenize(self, text: str) -> list[str]:
        """Tokenize preprocessed text.
        
        Args:
            text: Preprocessed text
            
        Returns:
            List of tokens
        """
        preprocessed = self.preprocess(text)
        return preprocessed.split()
