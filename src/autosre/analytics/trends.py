"""
Trend Analysis for AutoSRE V2.

Time series forecasting and trend detection with:
- ARIMA-based analysis
- Prophet-like decomposition
- Holt-Winters exponential smoothing
- Change point detection
- Seasonality identification
"""

from __future__ import annotations

import math
import statistics
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Optional, Sequence, Tuple

import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class TrendDirection(str, Enum):
    """Direction of the trend."""
    
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    UNKNOWN = "unknown"


class SeasonalPeriod(str, Enum):
    """Common seasonality periods."""
    
    HOURLY = "hourly"  # 60 samples at 1-minute resolution
    DAILY = "daily"  # 24 hours
    WEEKLY = "weekly"  # 7 days
    MONTHLY = "monthly"  # ~30 days
    QUARTERLY = "quarterly"  # ~90 days
    YEARLY = "yearly"  # 365 days


@dataclass
class TrendConfig:
    """Configuration for trend analysis."""
    
    # ARIMA settings
    arima_order: Tuple[int, int, int] = (1, 1, 1)  # (p, d, q)
    arima_seasonal_order: Tuple[int, int, int, int] = (0, 0, 0, 0)  # (P, D, Q, m)
    
    # Holt-Winters settings
    hw_alpha: float = 0.2  # Level smoothing
    hw_beta: float = 0.1  # Trend smoothing
    hw_gamma: float = 0.3  # Seasonal smoothing
    hw_seasonal_periods: int = 24  # Default daily seasonality
    hw_damped: bool = True
    
    # Prophet-like settings
    yearly_seasonality: bool = False
    weekly_seasonality: bool = True
    daily_seasonality: bool = True
    
    # General settings
    min_samples: int = 20
    forecast_horizon: int = 24
    confidence_interval: float = 0.95
    trend_sensitivity: float = 0.1  # Slope threshold for trend detection
    
    # Change point detection
    change_point_threshold: float = 2.0
    change_point_min_distance: int = 10
    
    # Moving average settings
    ma_window: int = 12
    ema_alpha: float = 0.3


@dataclass
class SeasonalPattern:
    """Detected seasonal pattern."""
    
    period: int  # Number of samples in one cycle
    period_type: SeasonalPeriod
    strength: float  # 0-1, how strong the pattern is
    phase: float  # Phase offset
    amplitude: float  # Typical amplitude of the pattern
    confidence: float  # Confidence in detection
    
    def __str__(self) -> str:
        return f"{self.period_type.value} (period={self.period}, strength={self.strength:.2f})"


@dataclass
class ChangePoint:
    """A detected change point in the time series."""
    
    index: int
    timestamp: Optional[datetime]
    value: float
    change_magnitude: float
    change_type: str  # "level_shift", "trend_change", "variance_change"
    confidence: float
    details: dict[str, Any] = field(default_factory=dict)
    
    def __str__(self) -> str:
        ts_str = self.timestamp.isoformat() if self.timestamp else f"idx={self.index}"
        return f"ChangePoint at {ts_str}: {self.change_type} (mag={self.change_magnitude:.2f})"


@dataclass
class ForecastResult:
    """Result of a forecast operation."""
    
    values: list[float]
    timestamps: list[datetime]
    lower_bound: list[float]
    upper_bound: list[float]
    confidence_level: float
    method: str
    metrics: dict[str, float] = field(default_factory=dict)  # MAE, RMSE, etc.
    
    def __len__(self) -> int:
        return len(self.values)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "values": self.values,
            "timestamps": [ts.isoformat() for ts in self.timestamps],
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "confidence_level": self.confidence_level,
            "method": self.method,
            "metrics": self.metrics,
        }


@dataclass
class TrendResult:
    """Result of trend analysis."""
    
    direction: TrendDirection
    slope: float  # Rate of change per unit time
    intercept: float
    r_squared: float  # Goodness of fit
    
    # Decomposition
    trend_component: list[float]
    seasonal_component: list[float]
    residual_component: list[float]
    
    # Patterns
    seasonal_patterns: list[SeasonalPattern]
    change_points: list[ChangePoint]
    
    # Statistics
    mean: float
    std: float
    min_value: float
    max_value: float
    
    # Metadata
    method: str
    config: TrendConfig
    details: dict[str, Any] = field(default_factory=dict)
    
    @property
    def trend_strength(self) -> float:
        """Calculate trend strength (0-1)."""
        if not self.residual_component:
            return 0.0
        
        var_residual = statistics.variance(self.residual_component) if len(self.residual_component) > 1 else 0
        var_original = self.std ** 2
        
        if var_original == 0:
            return 0.0
        
        return max(0, 1 - var_residual / var_original)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction.value,
            "slope": self.slope,
            "intercept": self.intercept,
            "r_squared": self.r_squared,
            "trend_strength": self.trend_strength,
            "seasonal_patterns": [
                {"period": sp.period, "type": sp.period_type.value, "strength": sp.strength}
                for sp in self.seasonal_patterns
            ],
            "change_points": [
                {"index": cp.index, "type": cp.change_type, "magnitude": cp.change_magnitude}
                for cp in self.change_points
            ],
            "statistics": {
                "mean": self.mean,
                "std": self.std,
                "min": self.min_value,
                "max": self.max_value,
            },
            "method": self.method,
        }


class BaseTrendAnalyzer(ABC):
    """Abstract base class for trend analyzers."""
    
    def __init__(self, config: Optional[TrendConfig] = None):
        self.config = config or TrendConfig()
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return analyzer name."""
        ...
    
    @abstractmethod
    def analyze(
        self,
        values: Sequence[float],
        timestamps: Optional[Sequence[datetime]] = None,
    ) -> TrendResult:
        """Analyze trend in the data."""
        ...
    
    @abstractmethod
    def forecast(
        self,
        values: Sequence[float],
        timestamps: Optional[Sequence[datetime]] = None,
        horizon: Optional[int] = None,
    ) -> ForecastResult:
        """Forecast future values."""
        ...
    
    def _detect_trend_direction(
        self,
        slope: float,
        r_squared: float,
    ) -> TrendDirection:
        """Determine trend direction from slope."""
        threshold = self.config.trend_sensitivity
        
        if r_squared < 0.1:  # Weak fit
            return TrendDirection.UNKNOWN
        
        if slope > threshold:
            return TrendDirection.INCREASING
        elif slope < -threshold:
            return TrendDirection.DECREASING
        return TrendDirection.STABLE
    
    def _linear_regression(
        self,
        x: Sequence[float],
        y: Sequence[float],
    ) -> Tuple[float, float, float]:
        """
        Simple linear regression.
        
        Returns: (slope, intercept, r_squared)
        """
        n = len(x)
        if n < 2:
            return 0.0, y[0] if y else 0.0, 0.0
        
        x_arr = np.array(x)
        y_arr = np.array(y)
        
        x_mean = np.mean(x_arr)
        y_mean = np.mean(y_arr)
        
        numerator = np.sum((x_arr - x_mean) * (y_arr - y_mean))
        denominator = np.sum((x_arr - x_mean) ** 2)
        
        if denominator == 0:
            return 0.0, y_mean, 0.0
        
        slope = numerator / denominator
        intercept = y_mean - slope * x_mean
        
        # R-squared
        y_pred = slope * x_arr + intercept
        ss_res = np.sum((y_arr - y_pred) ** 2)
        ss_tot = np.sum((y_arr - y_mean) ** 2)
        
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        
        return float(slope), float(intercept), float(r_squared)
    
    def _detect_change_points(
        self,
        values: Sequence[float],
        timestamps: Optional[Sequence[datetime]] = None,
    ) -> list[ChangePoint]:
        """
        Detect change points using CUSUM-like algorithm.
        """
        if len(values) < self.config.change_point_min_distance * 2:
            return []
        
        arr = np.array(values)
        n = len(arr)
        change_points = []
        
        # Calculate cumulative sum of deviations from mean
        mean = np.mean(arr)
        cusum = np.cumsum(arr - mean)
        
        # Find peaks in CUSUM (potential change points)
        for i in range(self.config.change_point_min_distance, n - self.config.change_point_min_distance):
            # Calculate local mean before and after
            before = np.mean(arr[max(0, i - self.config.change_point_min_distance):i])
            after = np.mean(arr[i:min(n, i + self.config.change_point_min_distance)])
            
            change_magnitude = abs(after - before)
            
            # Also check variance change
            var_before = np.var(arr[max(0, i - self.config.change_point_min_distance):i])
            var_after = np.var(arr[i:min(n, i + self.config.change_point_min_distance)])
            var_ratio = var_after / (var_before + 1e-10)
            
            # Determine change type
            std = np.std(arr)
            if std > 0 and change_magnitude / std > self.config.change_point_threshold:
                change_type = "level_shift"
                confidence = min(1.0, change_magnitude / (std * 2))
                
                ts = timestamps[i] if timestamps else None
                change_points.append(ChangePoint(
                    index=i,
                    timestamp=ts,
                    value=float(arr[i]),
                    change_magnitude=float(change_magnitude),
                    change_type=change_type,
                    confidence=confidence,
                    details={
                        "mean_before": float(before),
                        "mean_after": float(after),
                    },
                ))
            elif var_ratio > 2 or var_ratio < 0.5:
                change_type = "variance_change"
                confidence = min(1.0, abs(np.log(var_ratio)) / 2)
                
                ts = timestamps[i] if timestamps else None
                change_points.append(ChangePoint(
                    index=i,
                    timestamp=ts,
                    value=float(arr[i]),
                    change_magnitude=float(abs(np.log(var_ratio))),
                    change_type=change_type,
                    confidence=confidence,
                    details={
                        "var_before": float(var_before),
                        "var_after": float(var_after),
                        "var_ratio": float(var_ratio),
                    },
                ))
        
        # Filter to keep only significant, well-separated change points
        if not change_points:
            return []
        
        # Sort by confidence and remove close duplicates
        change_points.sort(key=lambda cp: -cp.confidence)
        filtered = [change_points[0]]
        
        for cp in change_points[1:]:
            if all(abs(cp.index - f.index) >= self.config.change_point_min_distance for f in filtered):
                filtered.append(cp)
        
        return sorted(filtered, key=lambda cp: cp.index)
    
    def _detect_seasonality(
        self,
        values: Sequence[float],
        periods_to_check: list[int] = None,
    ) -> list[SeasonalPattern]:
        """
        Detect seasonal patterns using autocorrelation.
        """
        if len(values) < self.config.min_samples:
            return []
        
        if periods_to_check is None:
            periods_to_check = [6, 12, 24, 168]  # 6h, 12h, daily, weekly at hourly resolution
        
        arr = np.array(values)
        n = len(arr)
        patterns = []
        
        # Compute autocorrelation for each period
        for period in periods_to_check:
            if period >= n // 2:
                continue
            
            # Calculate autocorrelation at this lag
            autocorr = self._autocorrelation(arr, period)
            
            if autocorr > 0.3:  # Significant correlation
                # Estimate amplitude from the variation at this period
                chunks = [arr[i:i + period] for i in range(0, n - period + 1, period)]
                if chunks:
                    chunk_means = [np.mean(c) for c in chunks if len(c) == period]
                    amplitude = np.std(chunk_means) if len(chunk_means) > 1 else 0.0
                else:
                    amplitude = 0.0
                
                # Determine period type
                period_type = self._classify_period(period)
                
                patterns.append(SeasonalPattern(
                    period=period,
                    period_type=period_type,
                    strength=float(autocorr),
                    phase=0.0,  # Would need FFT for accurate phase
                    amplitude=float(amplitude),
                    confidence=float(min(1.0, autocorr * 1.5)),
                ))
        
        # Sort by strength
        patterns.sort(key=lambda p: -p.strength)
        return patterns
    
    def _autocorrelation(self, values: np.ndarray, lag: int) -> float:
        """Calculate autocorrelation at a specific lag."""
        n = len(values)
        if lag >= n:
            return 0.0
        
        mean = np.mean(values)
        var = np.var(values)
        if var == 0:
            return 0.0
        
        covariance = np.mean((values[:-lag] - mean) * (values[lag:] - mean))
        return covariance / var
    
    def _classify_period(self, period: int) -> SeasonalPeriod:
        """Classify period length into semantic type."""
        # Assuming hourly data resolution
        if period <= 6:
            return SeasonalPeriod.HOURLY
        elif 20 <= period <= 28:
            return SeasonalPeriod.DAILY
        elif 160 <= period <= 180:
            return SeasonalPeriod.WEEKLY
        elif 700 <= period <= 750:
            return SeasonalPeriod.MONTHLY
        return SeasonalPeriod.DAILY  # Default


class MovingAverageAnalyzer(BaseTrendAnalyzer):
    """
    Moving average based trend analyzer.
    
    Simple but effective for noise reduction and basic trend extraction.
    """
    
    @property
    def name(self) -> str:
        return "moving_average"
    
    def analyze(
        self,
        values: Sequence[float],
        timestamps: Optional[Sequence[datetime]] = None,
    ) -> TrendResult:
        """Analyze using moving average decomposition."""
        if len(values) < self.config.min_samples:
            raise ValueError(f"Need at least {self.config.min_samples} samples")
        
        arr = np.array(values)
        n = len(arr)
        
        # Calculate moving average (trend)
        window = min(self.config.ma_window, n // 3)
        trend = self._moving_average(arr, window)
        
        # Seasonal = original - trend (simplified)
        seasonal = arr - trend
        
        # Residual = original - trend - seasonal (which is 0 in this simple case)
        residual = np.zeros_like(arr)
        
        # Linear regression on trend
        x = np.arange(n)
        slope, intercept, r_squared = self._linear_regression(x, trend)
        
        # Detect patterns
        change_points = self._detect_change_points(values, timestamps)
        seasonal_patterns = self._detect_seasonality(values)
        
        direction = self._detect_trend_direction(slope, r_squared)
        
        return TrendResult(
            direction=direction,
            slope=slope,
            intercept=intercept,
            r_squared=r_squared,
            trend_component=trend.tolist(),
            seasonal_component=seasonal.tolist(),
            residual_component=residual.tolist(),
            seasonal_patterns=seasonal_patterns,
            change_points=change_points,
            mean=float(np.mean(arr)),
            std=float(np.std(arr)),
            min_value=float(np.min(arr)),
            max_value=float(np.max(arr)),
            method=self.name,
            config=self.config,
        )
    
    def _moving_average(self, values: np.ndarray, window: int) -> np.ndarray:
        """Calculate simple moving average."""
        n = len(values)
        result = np.zeros(n)
        
        for i in range(n):
            start = max(0, i - window // 2)
            end = min(n, i + window // 2 + 1)
            result[i] = np.mean(values[start:end])
        
        return result
    
    def forecast(
        self,
        values: Sequence[float],
        timestamps: Optional[Sequence[datetime]] = None,
        horizon: Optional[int] = None,
    ) -> ForecastResult:
        """Forecast using exponential moving average extrapolation."""
        horizon = horizon or self.config.forecast_horizon
        arr = np.array(values)
        
        # Calculate EMA
        ema = self._exponential_moving_average(arr, self.config.ema_alpha)
        
        # Calculate trend from EMA
        recent_trend = np.gradient(ema[-min(10, len(ema)):]).mean()
        
        # Generate forecasts
        forecast_values = []
        last_value = ema[-1]
        
        for i in range(horizon):
            forecast_values.append(last_value + recent_trend * (i + 1))
        
        # Generate timestamps
        if timestamps:
            last_ts = timestamps[-1]
            if len(timestamps) > 1:
                interval = (timestamps[-1] - timestamps[-2])
            else:
                interval = timedelta(hours=1)
            
            forecast_ts = [last_ts + interval * (i + 1) for i in range(horizon)]
        else:
            forecast_ts = [datetime.now(timezone.utc) + timedelta(hours=i + 1) for i in range(horizon)]
        
        # Confidence bounds based on historical std
        std = float(np.std(arr))
        z_value = 1.96  # 95% confidence
        
        lower = [v - z_value * std for v in forecast_values]
        upper = [v + z_value * std for v in forecast_values]
        
        return ForecastResult(
            values=forecast_values,
            timestamps=forecast_ts,
            lower_bound=lower,
            upper_bound=upper,
            confidence_level=self.config.confidence_interval,
            method=self.name,
        )
    
    def _exponential_moving_average(
        self,
        values: np.ndarray,
        alpha: float,
    ) -> np.ndarray:
        """Calculate exponential moving average."""
        n = len(values)
        result = np.zeros(n)
        result[0] = values[0]
        
        for i in range(1, n):
            result[i] = alpha * values[i] + (1 - alpha) * result[i - 1]
        
        return result


class HoltWintersAnalyzer(BaseTrendAnalyzer):
    """
    Holt-Winters exponential smoothing.
    
    Handles level, trend, and seasonal components.
    """
    
    @property
    def name(self) -> str:
        return "holt_winters"
    
    def analyze(
        self,
        values: Sequence[float],
        timestamps: Optional[Sequence[datetime]] = None,
    ) -> TrendResult:
        """Analyze using Holt-Winters decomposition."""
        if len(values) < self.config.min_samples:
            raise ValueError(f"Need at least {self.config.min_samples} samples")
        
        arr = np.array(values)
        n = len(arr)
        m = min(self.config.hw_seasonal_periods, n // 2)
        
        # Initialize components
        level, trend, seasonal, fitted = self._fit_hw(arr, m)
        
        # Calculate residuals
        residual = arr - fitted
        
        # Linear regression on level for overall trend
        x = np.arange(n)
        slope, intercept, r_squared = self._linear_regression(x, level)
        
        # Detect patterns
        change_points = self._detect_change_points(values, timestamps)
        seasonal_patterns = self._detect_seasonality(values)
        
        direction = self._detect_trend_direction(slope, r_squared)
        
        return TrendResult(
            direction=direction,
            slope=slope,
            intercept=intercept,
            r_squared=r_squared,
            trend_component=level.tolist(),
            seasonal_component=seasonal.tolist(),
            residual_component=residual.tolist(),
            seasonal_patterns=seasonal_patterns,
            change_points=change_points,
            mean=float(np.mean(arr)),
            std=float(np.std(arr)),
            min_value=float(np.min(arr)),
            max_value=float(np.max(arr)),
            method=self.name,
            config=self.config,
            details={
                "alpha": self.config.hw_alpha,
                "beta": self.config.hw_beta,
                "gamma": self.config.hw_gamma,
                "seasonal_periods": m,
            },
        )
    
    def _fit_hw(
        self,
        values: np.ndarray,
        m: int,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Fit Holt-Winters additive model.
        
        Returns: (level, trend, seasonal, fitted_values)
        """
        n = len(values)
        alpha = self.config.hw_alpha
        beta = self.config.hw_beta
        gamma = self.config.hw_gamma
        damped = self.config.hw_damped
        phi = 0.9 if damped else 1.0
        
        # Initialize
        level = np.zeros(n)
        trend = np.zeros(n)
        seasonal = np.zeros(n)
        fitted = np.zeros(n)
        
        # Initial values
        level[0] = values[0]
        trend[0] = (values[min(m, n-1)] - values[0]) / m if m < n else 0
        
        # Initialize seasonal component from first complete cycle
        for i in range(min(m, n)):
            seasonal[i] = values[i] - level[0]
        
        # Smooth
        for t in range(1, n):
            # Seasonal index
            s_idx = (t - m) % m if t >= m else t
            
            # Level
            level[t] = alpha * (values[t] - seasonal[s_idx]) + (1 - alpha) * (level[t-1] + phi * trend[t-1])
            
            # Trend
            trend[t] = beta * (level[t] - level[t-1]) + (1 - beta) * phi * trend[t-1]
            
            # Seasonal
            seasonal[t] = gamma * (values[t] - level[t]) + (1 - gamma) * seasonal[s_idx]
            
            # Fitted value
            fitted[t] = level[t] + seasonal[s_idx]
        
        return level, trend, seasonal, fitted
    
    def forecast(
        self,
        values: Sequence[float],
        timestamps: Optional[Sequence[datetime]] = None,
        horizon: Optional[int] = None,
    ) -> ForecastResult:
        """Forecast using Holt-Winters."""
        horizon = horizon or self.config.forecast_horizon
        arr = np.array(values)
        n = len(arr)
        m = min(self.config.hw_seasonal_periods, n // 2)
        
        phi = 0.9 if self.config.hw_damped else 1.0
        
        # Fit model
        level, trend, seasonal, fitted = self._fit_hw(arr, m)
        
        # Generate forecasts
        forecast_values = []
        last_level = level[-1]
        last_trend = trend[-1]
        
        for h in range(1, horizon + 1):
            # Damping factor accumulation
            phi_sum = sum(phi ** i for i in range(1, h + 1))
            
            # Seasonal index
            s_idx = ((n - m) + h - 1) % m
            
            forecast = last_level + phi_sum * last_trend + seasonal[s_idx]
            forecast_values.append(float(forecast))
        
        # Generate timestamps
        if timestamps:
            last_ts = timestamps[-1]
            if len(timestamps) > 1:
                interval = (timestamps[-1] - timestamps[-2])
            else:
                interval = timedelta(hours=1)
            forecast_ts = [last_ts + interval * (i + 1) for i in range(horizon)]
        else:
            forecast_ts = [datetime.now(timezone.utc) + timedelta(hours=i + 1) for i in range(horizon)]
        
        # Confidence bounds
        residuals = arr - fitted
        rmse = float(np.sqrt(np.mean(residuals ** 2)))
        z_value = 1.96
        
        lower = [v - z_value * rmse * math.sqrt(1 + h * 0.1) for h, v in enumerate(forecast_values, 1)]
        upper = [v + z_value * rmse * math.sqrt(1 + h * 0.1) for h, v in enumerate(forecast_values, 1)]
        
        return ForecastResult(
            values=forecast_values,
            timestamps=forecast_ts,
            lower_bound=lower,
            upper_bound=upper,
            confidence_level=self.config.confidence_interval,
            method=self.name,
            metrics={
                "rmse": rmse,
                "mae": float(np.mean(np.abs(residuals))),
            },
        )


class ARIMAAnalyzer(BaseTrendAnalyzer):
    """
    ARIMA (AutoRegressive Integrated Moving Average) analyzer.
    
    Simplified implementation for trend analysis.
    """
    
    @property
    def name(self) -> str:
        return "arima"
    
    def analyze(
        self,
        values: Sequence[float],
        timestamps: Optional[Sequence[datetime]] = None,
    ) -> TrendResult:
        """Analyze using ARIMA decomposition."""
        if len(values) < self.config.min_samples:
            raise ValueError(f"Need at least {self.config.min_samples} samples")
        
        arr = np.array(values)
        n = len(arr)
        p, d, q = self.config.arima_order
        
        # Differencing for stationarity
        diff_values = self._difference(arr, d)
        
        # Estimate AR coefficients using Yule-Walker
        ar_coeffs = self._estimate_ar(diff_values, p) if p > 0 else []
        
        # Fit and get components
        fitted = self._fit_arima(arr, ar_coeffs, d)
        
        # Trend is the fitted values
        trend = fitted
        
        # Residual
        residual = arr - fitted
        
        # Use moving average for seasonal approximation
        window = min(24, n // 3)
        seasonal = arr - self._moving_average(arr, window)
        
        # Linear regression for trend direction
        x = np.arange(n)
        slope, intercept, r_squared = self._linear_regression(x, trend)
        
        # Detect patterns
        change_points = self._detect_change_points(values, timestamps)
        seasonal_patterns = self._detect_seasonality(values)
        
        direction = self._detect_trend_direction(slope, r_squared)
        
        return TrendResult(
            direction=direction,
            slope=slope,
            intercept=intercept,
            r_squared=r_squared,
            trend_component=trend.tolist(),
            seasonal_component=seasonal.tolist(),
            residual_component=residual.tolist(),
            seasonal_patterns=seasonal_patterns,
            change_points=change_points,
            mean=float(np.mean(arr)),
            std=float(np.std(arr)),
            min_value=float(np.min(arr)),
            max_value=float(np.max(arr)),
            method=self.name,
            config=self.config,
            details={
                "order": self.config.arima_order,
                "ar_coefficients": ar_coeffs,
            },
        )
    
    def _difference(self, values: np.ndarray, d: int) -> np.ndarray:
        """Apply differencing d times."""
        result = values.copy()
        for _ in range(d):
            result = np.diff(result)
        return result
    
    def _moving_average(self, values: np.ndarray, window: int) -> np.ndarray:
        """Calculate simple moving average."""
        n = len(values)
        result = np.zeros(n)
        for i in range(n):
            start = max(0, i - window // 2)
            end = min(n, i + window // 2 + 1)
            result[i] = np.mean(values[start:end])
        return result
    
    def _estimate_ar(self, values: np.ndarray, p: int) -> list[float]:
        """Estimate AR coefficients using Yule-Walker equations."""
        if len(values) < p + 1:
            return [0.0] * p
        
        # Compute autocorrelations
        r = np.zeros(p + 1)
        n = len(values)
        mean = np.mean(values)
        
        for k in range(p + 1):
            r[k] = np.sum((values[:n-k] - mean) * (values[k:] - mean)) / n
        
        if r[0] == 0:
            return [0.0] * p
        
        r = r / r[0]  # Normalize
        
        # Solve Yule-Walker using Levinson-Durbin
        coeffs = self._levinson_durbin(r[1:], p)
        return coeffs.tolist()
    
    def _levinson_durbin(self, r: np.ndarray, order: int) -> np.ndarray:
        """Levinson-Durbin algorithm for AR coefficient estimation."""
        a = np.zeros(order)
        e = 1.0
        
        for i in range(order):
            # Reflection coefficient
            sum_term = np.sum(a[:i] * r[i-1::-1]) if i > 0 else 0
            k = (r[i] - sum_term) / e if e != 0 else 0
            
            # Update coefficients
            a_new = np.zeros(order)
            a_new[i] = k
            for j in range(i):
                a_new[j] = a[j] - k * a[i-1-j]
            a = a_new
            
            # Update error
            e = e * (1 - k * k)
        
        return a
    
    def _fit_arima(
        self,
        values: np.ndarray,
        ar_coeffs: list[float],
        d: int,
    ) -> np.ndarray:
        """Generate fitted values from ARIMA model."""
        n = len(values)
        p = len(ar_coeffs)
        
        # Apply differencing
        diff_values = self._difference(values, d)
        
        # AR prediction
        if p > 0:
            fitted_diff = np.zeros(len(diff_values))
            for t in range(p, len(diff_values)):
                fitted_diff[t] = np.sum(np.array(ar_coeffs) * diff_values[t-p:t][::-1])
        else:
            fitted_diff = diff_values.copy()
        
        # Integrate back
        fitted = self._integrate(fitted_diff, values[:d], d)
        
        return fitted
    
    def _integrate(
        self,
        diff_values: np.ndarray,
        initial: np.ndarray,
        d: int,
    ) -> np.ndarray:
        """Reverse differencing."""
        result = diff_values.copy()
        
        for i in range(d):
            initial_val = initial[d - 1 - i] if i < len(initial) else 0
            new_result = np.zeros(len(result) + 1)
            new_result[0] = initial_val
            new_result[1:] = initial_val + np.cumsum(result)
            result = new_result
        
        return result
    
    def forecast(
        self,
        values: Sequence[float],
        timestamps: Optional[Sequence[datetime]] = None,
        horizon: Optional[int] = None,
    ) -> ForecastResult:
        """Forecast using ARIMA."""
        horizon = horizon or self.config.forecast_horizon
        arr = np.array(values)
        p, d, q = self.config.arima_order
        
        # Difference the series
        diff_values = self._difference(arr, d)
        
        # Estimate coefficients
        ar_coeffs = self._estimate_ar(diff_values, p) if p > 0 else []
        
        # Generate forecasts on differenced series
        forecast_diff = []
        history = list(diff_values[-p:]) if p > 0 else []
        
        for _ in range(horizon):
            if p > 0 and len(history) >= p:
                pred = sum(c * h for c, h in zip(ar_coeffs, history[-p:]))
            else:
                pred = 0.0
            forecast_diff.append(pred)
            history.append(pred)
        
        # Integrate forecasts
        forecast_values = []
        last_value = arr[-1]
        
        for i, fd in enumerate(forecast_diff):
            last_value = last_value + fd
            forecast_values.append(float(last_value))
        
        # Generate timestamps
        if timestamps:
            last_ts = timestamps[-1]
            if len(timestamps) > 1:
                interval = (timestamps[-1] - timestamps[-2])
            else:
                interval = timedelta(hours=1)
            forecast_ts = [last_ts + interval * (i + 1) for i in range(horizon)]
        else:
            forecast_ts = [datetime.now(timezone.utc) + timedelta(hours=i + 1) for i in range(horizon)]
        
        # Confidence bounds
        residuals = self._difference(arr - self._fit_arima(arr, ar_coeffs, d), 0)
        std = float(np.std(residuals)) if len(residuals) > 0 else float(np.std(arr))
        z_value = 1.96
        
        lower = [v - z_value * std * math.sqrt(h) for h, v in enumerate(forecast_values, 1)]
        upper = [v + z_value * std * math.sqrt(h) for h, v in enumerate(forecast_values, 1)]
        
        return ForecastResult(
            values=forecast_values,
            timestamps=forecast_ts,
            lower_bound=lower,
            upper_bound=upper,
            confidence_level=self.config.confidence_interval,
            method=self.name,
            metrics={"std": std},
        )


class ProphetAnalyzer(BaseTrendAnalyzer):
    """
    Prophet-like decomposition analyzer.
    
    Additive model: y = trend + seasonality + residuals
    """
    
    @property
    def name(self) -> str:
        return "prophet"
    
    def analyze(
        self,
        values: Sequence[float],
        timestamps: Optional[Sequence[datetime]] = None,
    ) -> TrendResult:
        """Analyze using Prophet-like decomposition."""
        if len(values) < self.config.min_samples:
            raise ValueError(f"Need at least {self.config.min_samples} samples")
        
        arr = np.array(values)
        n = len(arr)
        
        # Extract trend using robust LOESS-like smoothing
        trend = self._loess_trend(arr)
        
        # Extract seasonality using Fourier decomposition
        detrended = arr - trend
        seasonal = self._fourier_seasonal(detrended, timestamps)
        
        # Residuals
        residual = arr - trend - seasonal
        
        # Linear regression for direction
        x = np.arange(n)
        slope, intercept, r_squared = self._linear_regression(x, trend)
        
        # Detect patterns
        change_points = self._detect_change_points(values, timestamps)
        seasonal_patterns = self._detect_seasonality(values)
        
        direction = self._detect_trend_direction(slope, r_squared)
        
        return TrendResult(
            direction=direction,
            slope=slope,
            intercept=intercept,
            r_squared=r_squared,
            trend_component=trend.tolist(),
            seasonal_component=seasonal.tolist(),
            residual_component=residual.tolist(),
            seasonal_patterns=seasonal_patterns,
            change_points=change_points,
            mean=float(np.mean(arr)),
            std=float(np.std(arr)),
            min_value=float(np.min(arr)),
            max_value=float(np.max(arr)),
            method=self.name,
            config=self.config,
        )
    
    def _loess_trend(
        self,
        values: np.ndarray,
        frac: float = 0.3,
    ) -> np.ndarray:
        """
        LOESS-like smoothing for trend extraction.
        Simplified weighted local regression.
        """
        n = len(values)
        window = max(3, int(n * frac))
        trend = np.zeros(n)
        
        for i in range(n):
            # Define local window
            start = max(0, i - window // 2)
            end = min(n, i + window // 2 + 1)
            
            x_local = np.arange(end - start)
            y_local = values[start:end]
            
            # Weights (tricube function)
            center = i - start
            distances = np.abs(x_local - center)
            max_dist = max(distances.max(), 1)
            weights = (1 - (distances / max_dist) ** 3) ** 3
            
            # Weighted linear regression
            w_sum = np.sum(weights)
            if w_sum == 0:
                trend[i] = values[i]
                continue
            
            x_w_mean = np.sum(weights * x_local) / w_sum
            y_w_mean = np.sum(weights * y_local) / w_sum
            
            numerator = np.sum(weights * (x_local - x_w_mean) * (y_local - y_w_mean))
            denominator = np.sum(weights * (x_local - x_w_mean) ** 2)
            
            if denominator == 0:
                trend[i] = y_w_mean
            else:
                slope = numerator / denominator
                intercept = y_w_mean - slope * x_w_mean
                trend[i] = slope * center + intercept
        
        return trend
    
    def _fourier_seasonal(
        self,
        detrended: np.ndarray,
        timestamps: Optional[Sequence[datetime]] = None,
    ) -> np.ndarray:
        """
        Extract seasonality using Fourier components.
        """
        n = len(detrended)
        seasonal = np.zeros(n)
        
        # Check for daily seasonality (assume hourly data)
        if self.config.daily_seasonality and n >= 48:
            period = 24
            for k in range(1, 4):  # First 3 harmonics
                freq = 2 * np.pi * k / period
                t = np.arange(n)
                
                # Fit sin and cos components
                sin_comp = np.sin(freq * t)
                cos_comp = np.cos(freq * t)
                
                # Least squares fit
                A = np.column_stack([sin_comp, cos_comp])
                coeffs, _, _, _ = np.linalg.lstsq(A, detrended, rcond=None)
                
                seasonal += coeffs[0] * sin_comp + coeffs[1] * cos_comp
        
        # Check for weekly seasonality
        if self.config.weekly_seasonality and n >= 168 * 2:
            period = 168  # 7 * 24
            for k in range(1, 3):
                freq = 2 * np.pi * k / period
                t = np.arange(n)
                
                sin_comp = np.sin(freq * t)
                cos_comp = np.cos(freq * t)
                
                A = np.column_stack([sin_comp, cos_comp])
                coeffs, _, _, _ = np.linalg.lstsq(A, detrended - seasonal, rcond=None)
                
                seasonal += coeffs[0] * sin_comp + coeffs[1] * cos_comp
        
        return seasonal
    
    def forecast(
        self,
        values: Sequence[float],
        timestamps: Optional[Sequence[datetime]] = None,
        horizon: Optional[int] = None,
    ) -> ForecastResult:
        """Forecast using Prophet-like extrapolation."""
        horizon = horizon or self.config.forecast_horizon
        arr = np.array(values)
        n = len(arr)
        
        # Decompose
        trend = self._loess_trend(arr)
        detrended = arr - trend
        seasonal = self._fourier_seasonal(detrended, timestamps)
        residual = arr - trend - seasonal
        
        # Extrapolate trend (linear)
        x = np.arange(n)
        slope, intercept, _ = self._linear_regression(x, trend)
        
        # Generate forecasts
        forecast_values = []
        
        for h in range(1, horizon + 1):
            # Trend extrapolation
            trend_pred = slope * (n + h - 1) + intercept
            
            # Seasonal component (repeating)
            seasonal_idx = (n + h - 1) % n
            seasonal_pred = seasonal[seasonal_idx] if n > 0 else 0
            
            forecast_values.append(float(trend_pred + seasonal_pred))
        
        # Generate timestamps
        if timestamps:
            last_ts = timestamps[-1]
            if len(timestamps) > 1:
                interval = (timestamps[-1] - timestamps[-2])
            else:
                interval = timedelta(hours=1)
            forecast_ts = [last_ts + interval * (i + 1) for i in range(horizon)]
        else:
            forecast_ts = [datetime.now(timezone.utc) + timedelta(hours=i + 1) for i in range(horizon)]
        
        # Confidence bounds
        std = float(np.std(residual))
        z_value = 1.96
        
        lower = [v - z_value * std for v in forecast_values]
        upper = [v + z_value * std for v in forecast_values]
        
        return ForecastResult(
            values=forecast_values,
            timestamps=forecast_ts,
            lower_bound=lower,
            upper_bound=upper,
            confidence_level=self.config.confidence_interval,
            method=self.name,
            metrics={"residual_std": std},
        )


class TrendAnalyzer:
    """
    High-level trend analyzer for AutoSRE.
    
    Provides unified interface for multiple analysis methods
    with automatic method selection.
    
    Example:
        analyzer = TrendAnalyzer()
        result = analyzer.analyze(historical_values)
        
        forecast = analyzer.forecast(values, horizon=24)
    """
    
    def __init__(
        self,
        config: Optional[TrendConfig] = None,
        method: str = "auto",
    ):
        self.config = config or TrendConfig()
        self._method = method
        
        # Initialize analyzers
        self._analyzers: dict[str, BaseTrendAnalyzer] = {
            "moving_average": MovingAverageAnalyzer(self.config),
            "holt_winters": HoltWintersAnalyzer(self.config),
            "arima": ARIMAAnalyzer(self.config),
            "prophet": ProphetAnalyzer(self.config),
        }
    
    def _select_method(self, values: Sequence[float]) -> str:
        """Auto-select best method based on data characteristics."""
        n = len(values)
        
        # Check for seasonality
        seasonal_patterns = self._analyzers["moving_average"]._detect_seasonality(values)
        has_seasonality = len(seasonal_patterns) > 0
        
        if n < 50:
            return "moving_average"
        elif has_seasonality and n >= 100:
            return "prophet"
        elif n >= 100:
            return "holt_winters"
        else:
            return "arima"
    
    def analyze(
        self,
        values: Sequence[float],
        timestamps: Optional[Sequence[datetime]] = None,
        method: Optional[str] = None,
    ) -> TrendResult:
        """
        Analyze trend in the data.
        
        Args:
            values: Time series values
            timestamps: Optional timestamps
            method: Analysis method ("moving_average", "holt_winters", "arima", "prophet", "auto")
        
        Returns:
            TrendResult with decomposition and patterns
        """
        if len(values) < self.config.min_samples:
            raise ValueError(f"Need at least {self.config.min_samples} samples")
        
        method = method or self._method
        if method == "auto":
            method = self._select_method(values)
        
        analyzer = self._analyzers.get(method)
        if not analyzer:
            analyzer = self._analyzers["moving_average"]
        
        return analyzer.analyze(values, timestamps)
    
    def forecast(
        self,
        values: Sequence[float],
        timestamps: Optional[Sequence[datetime]] = None,
        horizon: Optional[int] = None,
        method: Optional[str] = None,
    ) -> ForecastResult:
        """
        Forecast future values.
        
        Args:
            values: Historical time series values
            timestamps: Optional timestamps
            horizon: Number of steps to forecast
            method: Forecasting method
        
        Returns:
            ForecastResult with predictions and confidence bounds
        """
        if len(values) < self.config.min_samples:
            raise ValueError(f"Need at least {self.config.min_samples} samples")
        
        method = method or self._method
        if method == "auto":
            method = self._select_method(values)
        
        analyzer = self._analyzers.get(method)
        if not analyzer:
            analyzer = self._analyzers["moving_average"]
        
        return analyzer.forecast(values, timestamps, horizon)
    
    def detect_change_points(
        self,
        values: Sequence[float],
        timestamps: Optional[Sequence[datetime]] = None,
    ) -> list[ChangePoint]:
        """Detect change points in the time series."""
        return self._analyzers["moving_average"]._detect_change_points(values, timestamps)
    
    def detect_seasonality(
        self,
        values: Sequence[float],
        periods_to_check: Optional[list[int]] = None,
    ) -> list[SeasonalPattern]:
        """Detect seasonal patterns in the time series."""
        return self._analyzers["moving_average"]._detect_seasonality(values, periods_to_check)
    
    @property
    def available_methods(self) -> list[str]:
        """Get list of available analysis methods."""
        return list(self._analyzers.keys())
