"""
Capacity Forecasting for AutoSRE.

Provides time-series forecasting capabilities including:
- Multiple forecasting algorithms (linear, exponential, seasonal)
- Confidence intervals for predictions
- Anomaly detection in capacity data
- Seasonality detection and decomposition
"""

import uuid
import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional, Callable

from pydantic import BaseModel, Field


class ForecastAlgorithm(str, Enum):
    """Forecasting algorithms available."""
    
    LINEAR = "linear"                    # Simple linear regression
    EXPONENTIAL = "exponential"          # Exponential smoothing
    HOLT_WINTERS = "holt_winters"        # Triple exponential smoothing
    ARIMA = "arima"                      # Auto-regressive integrated moving average
    PROPHET = "prophet"                  # Facebook Prophet-style
    ENSEMBLE = "ensemble"                # Ensemble of multiple methods


class SeasonalityType(str, Enum):
    """Types of seasonality patterns."""
    
    NONE = "none"
    HOURLY = "hourly"          # Hourly patterns (e.g., business hours)
    DAILY = "daily"            # Daily patterns (e.g., weekday vs weekend)
    WEEKLY = "weekly"          # Weekly patterns
    MONTHLY = "monthly"        # Monthly patterns
    QUARTERLY = "quarterly"    # Quarterly patterns
    YEARLY = "yearly"          # Yearly patterns
    CUSTOM = "custom"          # Custom period


class TrendDirection(str, Enum):
    """Direction of capacity trend."""
    
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    VOLATILE = "volatile"


class ConfidenceLevel(str, Enum):
    """Confidence levels for predictions."""
    
    LOW = "low"       # 50% confidence
    MEDIUM = "medium" # 80% confidence
    HIGH = "high"     # 95% confidence
    VERY_HIGH = "very_high"  # 99% confidence


@dataclass
class DataPoint:
    """A single data point in a time series."""
    
    timestamp: datetime
    value: float
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "value": self.value,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DataPoint":
        """Create from dictionary."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            value=data["value"],
            metadata=data.get("metadata", {}),
        )


class TimeSeriesData(BaseModel):
    """Time series data for forecasting."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    resource_type: str = ""  # e.g., "cpu", "memory", "disk", "network"
    unit: str = ""  # e.g., "percent", "GB", "requests/sec"
    points: list[dict] = Field(default_factory=list)  # DataPoint as dicts
    
    # Metadata
    source: str = ""
    region: str = ""
    service: str = ""
    tags: dict[str, str] = Field(default_factory=dict)
    
    def add_point(self, timestamp: datetime, value: float, **metadata: Any) -> None:
        """Add a data point to the series."""
        self.points.append(DataPoint(timestamp, value, metadata).to_dict())
    
    def get_values(self) -> list[float]:
        """Get all values as a list."""
        return [p["value"] for p in self.points]
    
    def get_timestamps(self) -> list[datetime]:
        """Get all timestamps as a list."""
        return [datetime.fromisoformat(p["timestamp"]) for p in self.points]
    
    def get_latest(self) -> Optional[dict]:
        """Get the latest data point."""
        if not self.points:
            return None
        return max(self.points, key=lambda p: p["timestamp"])
    
    def get_stats(self) -> dict[str, float]:
        """Get basic statistics for the series."""
        values = self.get_values()
        if not values:
            return {}
        return {
            "min": min(values),
            "max": max(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "std_dev": statistics.stdev(values) if len(values) > 1 else 0,
            "count": len(values),
        }


class ForecastConfig(BaseModel):
    """Configuration for forecasting."""
    
    algorithm: ForecastAlgorithm = ForecastAlgorithm.LINEAR
    horizon_hours: int = Field(default=168, ge=1)  # Default 7 days
    confidence_level: ConfidenceLevel = ConfidenceLevel.MEDIUM
    seasonality: SeasonalityType = SeasonalityType.DAILY
    custom_seasonality_hours: Optional[int] = None
    
    # Algorithm-specific parameters
    smoothing_factor: float = Field(default=0.3, ge=0, le=1)
    trend_smoothing: float = Field(default=0.1, ge=0, le=1)
    seasonal_smoothing: float = Field(default=0.1, ge=0, le=1)
    
    # Anomaly detection
    detect_anomalies: bool = True
    anomaly_threshold_std: float = Field(default=3.0, ge=1)
    
    # Output options
    include_components: bool = False  # Include trend/seasonal components
    resolution_hours: int = Field(default=1, ge=1)  # Forecast resolution


class ForecastMetrics(BaseModel):
    """Metrics about a forecast."""
    
    algorithm_used: ForecastAlgorithm
    data_points_used: int
    time_range_hours: float
    
    # Accuracy metrics (from validation)
    mape: Optional[float] = None  # Mean Absolute Percentage Error
    rmse: Optional[float] = None  # Root Mean Square Error
    mae: Optional[float] = None   # Mean Absolute Error
    
    # Trend analysis
    trend_direction: TrendDirection = TrendDirection.STABLE
    trend_slope: float = 0.0
    trend_strength: float = 0.0  # 0-1, how strong the trend is
    
    # Seasonality
    seasonality_detected: bool = False
    seasonality_type: SeasonalityType = SeasonalityType.NONE
    seasonality_strength: float = 0.0
    
    # Data quality
    missing_data_percent: float = 0.0
    outliers_detected: int = 0


class AnomalyDetection(BaseModel):
    """Anomaly detection results."""
    
    anomalies_found: int = 0
    anomaly_points: list[dict] = Field(default_factory=list)  # DataPoints
    threshold_used: float = 3.0
    mean_value: float = 0.0
    std_dev: float = 0.0
    
    def is_anomaly(self, value: float) -> bool:
        """Check if a value is an anomaly."""
        if self.std_dev == 0:
            return False
        z_score = abs(value - self.mean_value) / self.std_dev
        return z_score > self.threshold_used


class ForecastResult(BaseModel):
    """Result of a capacity forecast."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    series_id: str
    series_name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Configuration used
    config: ForecastConfig
    
    # Forecast data
    forecast_points: list[dict] = Field(default_factory=list)  # DataPoints
    upper_bound: list[dict] = Field(default_factory=list)  # Confidence upper
    lower_bound: list[dict] = Field(default_factory=list)  # Confidence lower
    
    # Components (if requested)
    trend_component: list[dict] = Field(default_factory=list)
    seasonal_component: list[dict] = Field(default_factory=list)
    residual_component: list[dict] = Field(default_factory=list)
    
    # Metrics
    metrics: ForecastMetrics
    anomaly_detection: Optional[AnomalyDetection] = None
    
    # Key predictions
    peak_predicted: Optional[dict] = None  # When capacity will peak
    threshold_breach: Optional[dict] = None  # When threshold will be breached
    
    def get_forecast_at(self, dt: datetime) -> Optional[dict[str, float]]:
        """Get forecast value at a specific time."""
        for i, point in enumerate(self.forecast_points):
            pt = datetime.fromisoformat(point["timestamp"])
            if pt >= dt:
                return {
                    "value": point["value"],
                    "upper": self.upper_bound[i]["value"] if self.upper_bound else None,
                    "lower": self.lower_bound[i]["value"] if self.lower_bound else None,
                }
        return None
    
    def will_breach_threshold(self, threshold: float, within_hours: int = 168) -> Optional[datetime]:
        """Check when the forecast will breach a threshold."""
        cutoff = self.created_at + timedelta(hours=within_hours)
        for point in self.forecast_points:
            pt = datetime.fromisoformat(point["timestamp"])
            if pt > cutoff:
                break
            if point["value"] >= threshold:
                return pt
        return None
    
    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the forecast."""
        if not self.forecast_points:
            return {"error": "No forecast data"}
        
        values = [p["value"] for p in self.forecast_points]
        return {
            "series_name": self.series_name,
            "horizon_hours": self.config.horizon_hours,
            "algorithm": self.config.algorithm.value,
            "trend": self.metrics.trend_direction.value,
            "min_forecast": min(values),
            "max_forecast": max(values),
            "avg_forecast": statistics.mean(values),
            "peak_time": self.peak_predicted,
            "threshold_breach": self.threshold_breach,
            "anomalies_detected": self.anomaly_detection.anomalies_found if self.anomaly_detection else 0,
        }


class CapacityForecaster:
    """Forecaster for capacity planning."""
    
    def __init__(self, default_config: Optional[ForecastConfig] = None):
        """Initialize the forecaster."""
        self.default_config = default_config or ForecastConfig()
        self._forecasts: dict[str, ForecastResult] = {}
    
    def forecast(
        self,
        data: TimeSeriesData,
        config: Optional[ForecastConfig] = None,
        threshold: Optional[float] = None,
    ) -> ForecastResult:
        """
        Generate a capacity forecast.
        
        Args:
            data: Time series data to forecast
            config: Forecast configuration (uses default if not provided)
            threshold: Optional threshold to check for breach
            
        Returns:
            ForecastResult with predictions
        """
        config = config or self.default_config
        values = data.get_values()
        timestamps = data.get_timestamps()
        
        if len(values) < 3:
            raise ValueError("Need at least 3 data points for forecasting")
        
        # Detect anomalies
        anomaly_detection = None
        if config.detect_anomalies:
            anomaly_detection = self._detect_anomalies(data, config.anomaly_threshold_std)
        
        # Calculate metrics
        metrics = self._calculate_metrics(data, config)
        
        # Generate forecast based on algorithm
        forecast_points = self._generate_forecast(values, timestamps, config)
        
        # Calculate confidence bounds
        upper_bound, lower_bound = self._calculate_confidence_bounds(
            forecast_points, values, config.confidence_level
        )
        
        # Find peak
        peak_idx = max(range(len(forecast_points)), key=lambda i: forecast_points[i]["value"])
        peak_predicted = forecast_points[peak_idx]
        
        # Check threshold breach
        threshold_breach = None
        if threshold:
            for point in forecast_points:
                if point["value"] >= threshold:
                    threshold_breach = point
                    break
        
        result = ForecastResult(
            series_id=data.id,
            series_name=data.name,
            config=config,
            forecast_points=forecast_points,
            upper_bound=upper_bound,
            lower_bound=lower_bound,
            metrics=metrics,
            anomaly_detection=anomaly_detection,
            peak_predicted=peak_predicted,
            threshold_breach=threshold_breach,
        )
        
        self._forecasts[result.id] = result
        return result
    
    def _generate_forecast(
        self,
        values: list[float],
        timestamps: list[datetime],
        config: ForecastConfig,
    ) -> list[dict]:
        """Generate forecast points using specified algorithm."""
        algorithm = config.algorithm
        
        if algorithm == ForecastAlgorithm.LINEAR:
            return self._linear_forecast(values, timestamps, config)
        elif algorithm == ForecastAlgorithm.EXPONENTIAL:
            return self._exponential_forecast(values, timestamps, config)
        elif algorithm == ForecastAlgorithm.HOLT_WINTERS:
            return self._holt_winters_forecast(values, timestamps, config)
        else:
            # Default to linear for unsupported algorithms
            return self._linear_forecast(values, timestamps, config)
    
    def _linear_forecast(
        self,
        values: list[float],
        timestamps: list[datetime],
        config: ForecastConfig,
    ) -> list[dict]:
        """Simple linear regression forecast."""
        n = len(values)
        x = list(range(n))
        
        # Calculate slope and intercept
        x_mean = statistics.mean(x)
        y_mean = statistics.mean(values)
        
        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        slope = numerator / denominator if denominator != 0 else 0
        intercept = y_mean - slope * x_mean
        
        # Generate forecast points
        last_timestamp = timestamps[-1]
        forecast_points = []
        
        num_points = config.horizon_hours // config.resolution_hours
        for i in range(1, num_points + 1):
            forecast_x = n + i - 1
            forecast_value = slope * forecast_x + intercept
            forecast_value = max(0, forecast_value)  # Ensure non-negative
            
            forecast_timestamp = last_timestamp + timedelta(hours=i * config.resolution_hours)
            forecast_points.append({
                "timestamp": forecast_timestamp.isoformat(),
                "value": forecast_value,
            })
        
        return forecast_points
    
    def _exponential_forecast(
        self,
        values: list[float],
        timestamps: list[datetime],
        config: ForecastConfig,
    ) -> list[dict]:
        """Exponential smoothing forecast."""
        alpha = config.smoothing_factor
        
        # Calculate smoothed values
        smoothed = [values[0]]
        for i in range(1, len(values)):
            smoothed.append(alpha * values[i] + (1 - alpha) * smoothed[-1])
        
        # Project forward
        last_timestamp = timestamps[-1]
        last_smoothed = smoothed[-1]
        trend = (smoothed[-1] - smoothed[0]) / len(smoothed) if len(smoothed) > 1 else 0
        
        forecast_points = []
        num_points = config.horizon_hours // config.resolution_hours
        
        for i in range(1, num_points + 1):
            forecast_value = last_smoothed + trend * i
            forecast_value = max(0, forecast_value)
            
            forecast_timestamp = last_timestamp + timedelta(hours=i * config.resolution_hours)
            forecast_points.append({
                "timestamp": forecast_timestamp.isoformat(),
                "value": forecast_value,
            })
        
        return forecast_points
    
    def _holt_winters_forecast(
        self,
        values: list[float],
        timestamps: list[datetime],
        config: ForecastConfig,
    ) -> list[dict]:
        """Holt-Winters (triple exponential smoothing) forecast."""
        alpha = config.smoothing_factor
        beta = config.trend_smoothing
        
        # Initialize level and trend
        level = values[0]
        trend = (values[-1] - values[0]) / len(values) if len(values) > 1 else 0
        
        # Apply smoothing
        for i in range(1, len(values)):
            new_level = alpha * values[i] + (1 - alpha) * (level + trend)
            new_trend = beta * (new_level - level) + (1 - beta) * trend
            level = new_level
            trend = new_trend
        
        # Generate forecast
        last_timestamp = timestamps[-1]
        forecast_points = []
        num_points = config.horizon_hours // config.resolution_hours
        
        for i in range(1, num_points + 1):
            forecast_value = level + trend * i
            forecast_value = max(0, forecast_value)
            
            forecast_timestamp = last_timestamp + timedelta(hours=i * config.resolution_hours)
            forecast_points.append({
                "timestamp": forecast_timestamp.isoformat(),
                "value": forecast_value,
            })
        
        return forecast_points
    
    def _calculate_confidence_bounds(
        self,
        forecast_points: list[dict],
        historical_values: list[float],
        confidence_level: ConfidenceLevel,
    ) -> tuple[list[dict], list[dict]]:
        """Calculate confidence intervals for forecast."""
        # Z-scores for confidence levels
        z_scores = {
            ConfidenceLevel.LOW: 0.674,        # 50%
            ConfidenceLevel.MEDIUM: 1.282,     # 80%
            ConfidenceLevel.HIGH: 1.960,       # 95%
            ConfidenceLevel.VERY_HIGH: 2.576,  # 99%
        }
        
        z = z_scores.get(confidence_level, 1.96)
        std_dev = statistics.stdev(historical_values) if len(historical_values) > 1 else 0
        
        upper_bound = []
        lower_bound = []
        
        for i, point in enumerate(forecast_points):
            # Widen confidence interval further into the future
            uncertainty_factor = 1 + (i * 0.01)
            margin = z * std_dev * uncertainty_factor
            
            upper_bound.append({
                "timestamp": point["timestamp"],
                "value": point["value"] + margin,
            })
            lower_bound.append({
                "timestamp": point["timestamp"],
                "value": max(0, point["value"] - margin),
            })
        
        return upper_bound, lower_bound
    
    def _detect_anomalies(
        self,
        data: TimeSeriesData,
        threshold_std: float,
    ) -> AnomalyDetection:
        """Detect anomalies in the time series."""
        values = data.get_values()
        if len(values) < 2:
            return AnomalyDetection()
        
        mean_value = statistics.mean(values)
        std_dev = statistics.stdev(values)
        
        anomaly_points = []
        for point in data.points:
            if std_dev > 0:
                z_score = abs(point["value"] - mean_value) / std_dev
                if z_score > threshold_std:
                    anomaly_points.append(point)
        
        return AnomalyDetection(
            anomalies_found=len(anomaly_points),
            anomaly_points=anomaly_points,
            threshold_used=threshold_std,
            mean_value=mean_value,
            std_dev=std_dev,
        )
    
    def _calculate_metrics(
        self,
        data: TimeSeriesData,
        config: ForecastConfig,
    ) -> ForecastMetrics:
        """Calculate forecast metrics."""
        values = data.get_values()
        timestamps = data.get_timestamps()
        
        if len(values) < 2:
            return ForecastMetrics(
                algorithm_used=config.algorithm,
                data_points_used=len(values),
                time_range_hours=0,
            )
        
        # Time range
        time_range = (timestamps[-1] - timestamps[0]).total_seconds() / 3600
        
        # Trend analysis
        trend_direction, trend_slope = self._analyze_trend(values)
        trend_strength = min(1.0, abs(trend_slope) / (statistics.stdev(values) + 0.001))
        
        # Seasonality detection
        seasonality_type, seasonality_strength = self._detect_seasonality_pattern(values, config)
        
        return ForecastMetrics(
            algorithm_used=config.algorithm,
            data_points_used=len(values),
            time_range_hours=time_range,
            trend_direction=trend_direction,
            trend_slope=trend_slope,
            trend_strength=trend_strength,
            seasonality_detected=seasonality_strength > 0.3,
            seasonality_type=seasonality_type,
            seasonality_strength=seasonality_strength,
        )
    
    def _analyze_trend(self, values: list[float]) -> tuple[TrendDirection, float]:
        """Analyze the trend in the data."""
        n = len(values)
        x = list(range(n))
        
        x_mean = statistics.mean(x)
        y_mean = statistics.mean(values)
        
        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        slope = numerator / denominator if denominator != 0 else 0
        
        # Determine trend direction
        std_dev = statistics.stdev(values) if len(values) > 1 else 0
        relative_slope = abs(slope) / (std_dev + 0.001)
        
        if relative_slope < 0.1:
            direction = TrendDirection.STABLE
        elif slope > 0:
            direction = TrendDirection.INCREASING
        else:
            direction = TrendDirection.DECREASING
        
        # Check for volatility
        cv = std_dev / (statistics.mean(values) + 0.001)
        if cv > 0.5:
            direction = TrendDirection.VOLATILE
        
        return direction, slope
    
    def _detect_seasonality_pattern(
        self,
        values: list[float],
        config: ForecastConfig,
    ) -> tuple[SeasonalityType, float]:
        """Detect seasonality patterns in the data."""
        if len(values) < 24:
            return SeasonalityType.NONE, 0.0
        
        # Simple autocorrelation check for daily pattern (assuming hourly data)
        if len(values) >= 48:
            # Check correlation with 24-hour lag
            lag_24 = values[:-24]
            current = values[24:]
            
            if len(lag_24) > 1:
                try:
                    # Calculate correlation coefficient
                    n = len(lag_24)
                    mean1 = statistics.mean(lag_24)
                    mean2 = statistics.mean(current)
                    
                    numerator = sum((lag_24[i] - mean1) * (current[i] - mean2) for i in range(n))
                    denom1 = sum((lag_24[i] - mean1) ** 2 for i in range(n))
                    denom2 = sum((current[i] - mean2) ** 2 for i in range(n))
                    
                    if denom1 > 0 and denom2 > 0:
                        correlation = numerator / math.sqrt(denom1 * denom2)
                        if correlation > 0.3:
                            return SeasonalityType.DAILY, correlation
                except Exception:
                    pass
        
        return config.seasonality, 0.0
    
    def get_forecast(self, forecast_id: str) -> Optional[ForecastResult]:
        """Get a forecast by ID."""
        return self._forecasts.get(forecast_id)
    
    def compare_algorithms(
        self,
        data: TimeSeriesData,
        algorithms: Optional[list[ForecastAlgorithm]] = None,
    ) -> dict[str, ForecastResult]:
        """Compare multiple forecasting algorithms on the same data."""
        algorithms = algorithms or [
            ForecastAlgorithm.LINEAR,
            ForecastAlgorithm.EXPONENTIAL,
            ForecastAlgorithm.HOLT_WINTERS,
        ]
        
        results = {}
        for algo in algorithms:
            config = ForecastConfig(algorithm=algo)
            try:
                result = self.forecast(data, config)
                results[algo.value] = result
            except Exception as e:
                results[algo.value] = {"error": str(e)}
        
        return results


def quick_forecast(
    values: list[float],
    horizon_hours: int = 168,
    algorithm: ForecastAlgorithm = ForecastAlgorithm.LINEAR,
) -> list[dict]:
    """
    Quick forecast from a list of values.
    
    Args:
        values: Historical values (assumed hourly)
        horizon_hours: Hours to forecast ahead
        algorithm: Algorithm to use
        
    Returns:
        List of forecast points
    """
    if len(values) < 3:
        raise ValueError("Need at least 3 data points")
    
    # Create time series data
    now = datetime.now(timezone.utc)
    data = TimeSeriesData(name="quick_forecast")
    
    for i, value in enumerate(values):
        timestamp = now - timedelta(hours=len(values) - i)
        data.add_point(timestamp, value)
    
    forecaster = CapacityForecaster()
    config = ForecastConfig(algorithm=algorithm, horizon_hours=horizon_hours)
    result = forecaster.forecast(data, config)
    
    return result.forecast_points


def detect_seasonality(values: list[float]) -> dict[str, Any]:
    """
    Detect seasonality in a time series.
    
    Args:
        values: Historical values (assumed hourly)
        
    Returns:
        Seasonality detection results
    """
    if len(values) < 48:
        return {
            "detected": False,
            "type": SeasonalityType.NONE.value,
            "strength": 0.0,
            "error": "Need at least 48 data points for seasonality detection",
        }
    
    # Create time series data
    now = datetime.now(timezone.utc)
    data = TimeSeriesData(name="seasonality_check")
    
    for i, value in enumerate(values):
        timestamp = now - timedelta(hours=len(values) - i)
        data.add_point(timestamp, value)
    
    forecaster = CapacityForecaster()
    config = ForecastConfig()
    metrics = forecaster._calculate_metrics(data, config)
    
    return {
        "detected": metrics.seasonality_detected,
        "type": metrics.seasonality_type.value,
        "strength": metrics.seasonality_strength,
    }
