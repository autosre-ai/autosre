"""Traffic prediction for infrastructure planning."""

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
from autosre.ml.common.features import TimeSeriesFeatures, FeatureScaler
from autosre.ml.common.preprocessing import TimeSeriesPreprocessor
from autosre.ml.common.metrics import TimeSeriesMetrics


class TrafficPattern(str, Enum):
    """Type of traffic pattern."""
    STEADY = "steady"
    GROWING = "growing"
    DECLINING = "declining"
    SEASONAL = "seasonal"
    SPIKY = "spiky"
    BURSTY = "bursty"


class TrafficForecast(BaseModel):
    """Traffic forecast result."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    forecast_id: str = Field(default_factory=generate_id)
    
    # Target
    service_name: str = Field(default="")
    endpoint: str = Field(default="")
    
    # Forecast
    forecast_values: list[float] = Field(default_factory=list)
    forecast_timestamps: list[datetime] = Field(default_factory=list)
    
    # Confidence intervals
    lower_bound: list[float] = Field(default_factory=list)
    upper_bound: list[float] = Field(default_factory=list)
    confidence_level: float = Field(default=0.95)
    
    # Pattern analysis
    pattern_type: TrafficPattern = Field(default=TrafficPattern.STEADY)
    trend_direction: str = Field(default="stable")  # increasing, decreasing, stable
    trend_slope_per_hour: float = Field(default=0.0)
    
    # Seasonality
    daily_pattern: list[float] = Field(default_factory=list)  # 24 values
    weekly_pattern: list[float] = Field(default_factory=list)  # 7 values
    peak_hours: list[int] = Field(default_factory=list)
    trough_hours: list[int] = Field(default_factory=list)
    
    # Statistics
    predicted_peak: float = Field(default=0.0)
    predicted_peak_time: Optional[datetime] = None
    predicted_average: float = Field(default=0.0)
    predicted_min: float = Field(default=0.0)
    
    # Anomaly risk
    anomaly_risk_hours: list[int] = Field(default_factory=list)
    
    # Capacity implications
    required_replicas: Optional[int] = None
    scaling_recommendations: list[dict[str, Any]] = Field(default_factory=list)
    
    # Metadata
    forecast_horizon_hours: int = Field(default=168)
    generated_at: datetime = Field(default_factory=utc_now)
    model_version: str = Field(default="")


class TrafficPredictor(BaseMLModel[np.ndarray, TrafficForecast]):
    """Predict traffic patterns for capacity planning.
    
    Uses time series forecasting with seasonality detection to predict:
    - Request rates
    - Bandwidth usage
    - User activity patterns
    
    Supports:
    - Multiple seasonality (hourly, daily, weekly)
    - Trend detection
    - Anomaly detection
    - Capacity recommendations
    """
    
    def __init__(
        self,
        forecast_horizon_hours: int = 168,
        detect_daily_seasonality: bool = True,
        detect_weekly_seasonality: bool = True,
        confidence_level: float = 0.95,
        requests_per_replica: float = 100.0,
    ):
        """Initialize the traffic predictor.
        
        Args:
            forecast_horizon_hours: Hours to forecast ahead
            detect_daily_seasonality: Detect daily patterns
            detect_weekly_seasonality: Detect weekly patterns
            confidence_level: Confidence level for intervals
            requests_per_replica: Requests per second each replica can handle
        """
        super().__init__(
            name="traffic_predictor",
            model_type="traffic_predictor",
            hyperparameters={
                "forecast_horizon_hours": forecast_horizon_hours,
                "detect_daily_seasonality": detect_daily_seasonality,
                "detect_weekly_seasonality": detect_weekly_seasonality,
                "confidence_level": confidence_level,
                "requests_per_replica": requests_per_replica,
            },
        )
        
        self.forecast_horizon_hours = forecast_horizon_hours
        self.detect_daily_seasonality = detect_daily_seasonality
        self.detect_weekly_seasonality = detect_weekly_seasonality
        self.confidence_level = confidence_level
        self.requests_per_replica = requests_per_replica
        
        # Model components
        self._preprocessor = TimeSeriesPreprocessor(normalize=False, detrend=False)
        self._feature_extractor = TimeSeriesFeatures()
        
        # Learned parameters
        self._trend_coeffs: Optional[np.ndarray] = None
        self._daily_pattern: Optional[np.ndarray] = None
        self._weekly_pattern: Optional[np.ndarray] = None
        self._residual_std: float = 0.0
        self._base_level: float = 0.0
        
        # Training data statistics
        self._data_mean: float = 0.0
        self._data_std: float = 0.0
        self._last_values: Optional[np.ndarray] = None
    
    def _decompose_additive(
        self,
        values: np.ndarray,
        timestamps: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        """Decompose time series into additive components.
        
        Args:
            values: Time series values
            timestamps: Timestamps (optional)
            
        Returns:
            Dictionary with trend, seasonal, and residual
        """
        values = values.copy()
        n = len(values)
        
        # Base level (mean)
        self._base_level = np.mean(values)
        
        # Extract trend
        x = np.arange(n)
        self._trend_coeffs = np.polyfit(x, values, 1)
        trend = np.polyval(self._trend_coeffs, x)
        detrended = values - trend
        
        # Extract daily seasonality (24-hour period)
        seasonal_sum = np.zeros(n)
        
        if self.detect_daily_seasonality and n >= 48:
            daily = self._extract_seasonal_pattern(detrended, 24)
            self._daily_pattern = daily
            
            # Create full daily series
            daily_full = np.tile(daily, (n + 23) // 24)[:n]
            seasonal_sum += daily_full
            detrended = detrended - daily_full
        
        # Extract weekly seasonality (168-hour period)
        if self.detect_weekly_seasonality and n >= 336:
            weekly = self._extract_seasonal_pattern(detrended, 168)
            self._weekly_pattern = weekly
            
            # Create full weekly series
            weekly_full = np.tile(weekly, (n + 167) // 168)[:n]
            seasonal_sum += weekly_full
            detrended = detrended - weekly_full
        
        # Residual
        residual = values - trend - seasonal_sum
        self._residual_std = np.std(residual)
        
        return {
            "trend": trend,
            "seasonal": seasonal_sum,
            "residual": residual,
            "trend_coeffs": self._trend_coeffs,
        }
    
    def _extract_seasonal_pattern(
        self,
        values: np.ndarray,
        period: int,
    ) -> np.ndarray:
        """Extract seasonal pattern for a given period.
        
        Args:
            values: Detrended values
            period: Period length
            
        Returns:
            Seasonal pattern array
        """
        n = len(values)
        n_cycles = n // period
        
        if n_cycles == 0:
            return np.zeros(period)
        
        # Calculate mean for each position in cycle
        pattern = np.zeros(period)
        counts = np.zeros(period)
        
        for i in range(n):
            pos = i % period
            pattern[pos] += values[i]
            counts[pos] += 1
        
        pattern = pattern / np.maximum(counts, 1)
        
        # Normalize to zero mean
        pattern = pattern - np.mean(pattern)
        
        return pattern
    
    def fit(
        self,
        X: np.ndarray,
        y: Optional[np.ndarray] = None,
        timestamps: Optional[np.ndarray] = None,
        config: Optional[TrainingConfig] = None,
    ) -> "TrafficPredictor":
        """Train the traffic predictor.
        
        Args:
            X: Historical traffic data (requests per second, etc.)
            y: Not used
            timestamps: Timestamps for data
            config: Training configuration
            
        Returns:
            Self
        """
        X = np.asarray(X).flatten()
        
        if len(X) < 2:
            raise ValueError("Need at least 2 data points")
        
        # Store training statistics
        self._data_mean = float(np.mean(X))
        self._data_std = float(np.std(X))
        self._last_values = X.copy()
        
        # Decompose time series
        decomposition = self._decompose_additive(X, timestamps)
        
        self._is_fitted = True
        self._metadata.status = ModelStatus.TRAINED
        self._metadata.last_trained_at = utc_now()
        
        # Calculate metrics
        metrics = {
            "mean": self._data_mean,
            "std": self._data_std,
            "trend_slope": float(self._trend_coeffs[0]) if self._trend_coeffs is not None else 0,
            "residual_std": self._residual_std,
            "num_samples": float(len(X)),
        }
        
        version = ModelVersion(
            description=f"Trained on {len(X)} samples",
            metrics=metrics,
        )
        self._metadata.add_version(version)
        
        return self
    
    def predict(
        self,
        X: Optional[np.ndarray] = None,
        service_name: str = "",
        endpoint: str = "",
    ) -> PredictionResult[TrafficForecast]:
        """Predict future traffic.
        
        Args:
            X: Recent traffic data (optional)
            service_name: Name of the service
            endpoint: Endpoint being predicted
            
        Returns:
            Traffic forecast
        """
        import time
        start_time = time.time()
        
        if not self._is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        # Use provided data or training data
        if X is not None:
            values = np.asarray(X).flatten()
            self._decompose_additive(values)
            start_idx = len(values)
        else:
            values = self._last_values
            start_idx = len(values)
        
        # Generate forecast
        n_steps = self.forecast_horizon_hours
        future_idx = np.arange(start_idx, start_idx + n_steps)
        
        # Trend component
        trend_forecast = np.polyval(self._trend_coeffs, future_idx)
        
        # Daily seasonality
        daily_forecast = np.zeros(n_steps)
        if self._daily_pattern is not None:
            for i in range(n_steps):
                daily_forecast[i] = self._daily_pattern[(start_idx + i) % 24]
        
        # Weekly seasonality
        weekly_forecast = np.zeros(n_steps)
        if self._weekly_pattern is not None:
            for i in range(n_steps):
                weekly_forecast[i] = self._weekly_pattern[(start_idx + i) % 168]
        
        # Combine components
        forecast_values = trend_forecast + daily_forecast + weekly_forecast
        
        # Ensure non-negative
        forecast_values = np.maximum(forecast_values, 0)
        
        # Confidence intervals
        z = 1.96 if self.confidence_level == 0.95 else 1.645
        uncertainty = self._residual_std * np.sqrt(1 + np.arange(1, n_steps + 1) / n_steps)
        
        lower_bound = np.maximum(forecast_values - z * uncertainty, 0)
        upper_bound = forecast_values + z * uncertainty
        
        # Generate timestamps
        now = utc_now()
        forecast_timestamps = [now + timedelta(hours=i) for i in range(n_steps)]
        
        # Analyze pattern
        pattern_type = self._detect_pattern_type(values, forecast_values)
        
        # Trend analysis
        if self._trend_coeffs is not None:
            trend_slope = self._trend_coeffs[0]
            if trend_slope > 0.1:
                trend_direction = "increasing"
            elif trend_slope < -0.1:
                trend_direction = "decreasing"
            else:
                trend_direction = "stable"
        else:
            trend_direction = "stable"
            trend_slope = 0.0
        
        # Peak hours
        peak_hours = []
        trough_hours = []
        if self._daily_pattern is not None:
            sorted_hours = np.argsort(self._daily_pattern)
            peak_hours = sorted_hours[-3:].tolist()[::-1]  # Top 3
            trough_hours = sorted_hours[:3].tolist()  # Bottom 3
        
        # Statistics
        predicted_peak = float(np.max(forecast_values))
        peak_idx = int(np.argmax(forecast_values))
        predicted_peak_time = forecast_timestamps[peak_idx]
        predicted_average = float(np.mean(forecast_values))
        predicted_min = float(np.min(forecast_values))
        
        # Capacity recommendations
        scaling_recommendations = self._generate_scaling_recommendations(
            forecast_values, forecast_timestamps
        )
        
        # Required replicas based on peak
        required_replicas = int(np.ceil(predicted_peak / self.requests_per_replica))
        
        # Create forecast
        forecast = TrafficForecast(
            service_name=service_name,
            endpoint=endpoint,
            forecast_values=forecast_values.tolist(),
            forecast_timestamps=forecast_timestamps,
            lower_bound=lower_bound.tolist(),
            upper_bound=upper_bound.tolist(),
            confidence_level=self.confidence_level,
            pattern_type=pattern_type,
            trend_direction=trend_direction,
            trend_slope_per_hour=float(trend_slope),
            daily_pattern=self._daily_pattern.tolist() if self._daily_pattern is not None else [],
            weekly_pattern=self._weekly_pattern.tolist() if self._weekly_pattern is not None else [],
            peak_hours=peak_hours,
            trough_hours=trough_hours,
            predicted_peak=predicted_peak,
            predicted_peak_time=predicted_peak_time,
            predicted_average=predicted_average,
            predicted_min=predicted_min,
            required_replicas=required_replicas,
            scaling_recommendations=scaling_recommendations,
            forecast_horizon_hours=self.forecast_horizon_hours,
            model_version=self._metadata.current_version.version_id if self._metadata.current_version else "",
        )
        
        latency = (time.time() - start_time) * 1000
        
        return PredictionResult(
            prediction=forecast,
            confidence=self.confidence_level,
            model_id=self.model_id,
            model_version=self._metadata.current_version.version_id if self._metadata.current_version else "",
            latency_ms=latency,
        )
    
    def _detect_pattern_type(
        self,
        historical: np.ndarray,
        forecast: np.ndarray,
    ) -> TrafficPattern:
        """Detect the type of traffic pattern.
        
        Args:
            historical: Historical values
            forecast: Forecasted values
            
        Returns:
            Pattern type
        """
        # Check trend
        if self._trend_coeffs is not None:
            slope = self._trend_coeffs[0]
            relative_slope = slope / (self._data_mean + 1e-10)
            
            if relative_slope > 0.01:
                return TrafficPattern.GROWING
            elif relative_slope < -0.01:
                return TrafficPattern.DECLINING
        
        # Check for spikiness
        if self._data_std > self._data_mean * 0.5:
            return TrafficPattern.SPIKY
        
        # Check for strong seasonality
        if self._daily_pattern is not None:
            seasonal_amplitude = np.std(self._daily_pattern)
            if seasonal_amplitude > self._data_mean * 0.2:
                return TrafficPattern.SEASONAL
        
        # Check for bursts
        if len(historical) > 10:
            diffs = np.diff(historical)
            if np.max(np.abs(diffs)) > self._data_mean * 2:
                return TrafficPattern.BURSTY
        
        return TrafficPattern.STEADY
    
    def _generate_scaling_recommendations(
        self,
        forecast: np.ndarray,
        timestamps: list[datetime],
    ) -> list[dict[str, Any]]:
        """Generate scaling recommendations based on forecast.
        
        Args:
            forecast: Traffic forecast
            timestamps: Forecast timestamps
            
        Returns:
            List of scaling recommendations
        """
        recommendations = []
        
        # Find periods that need scaling
        for i in range(0, len(forecast), 24):  # Check daily
            window = forecast[i:min(i+24, len(forecast))]
            window_peak = np.max(window)
            window_avg = np.mean(window)
            
            peak_replicas = int(np.ceil(window_peak / self.requests_per_replica))
            avg_replicas = int(np.ceil(window_avg / self.requests_per_replica))
            
            if peak_replicas > avg_replicas * 1.5:
                # Significant variation, recommend HPA
                recommendations.append({
                    "type": "hpa",
                    "start_time": timestamps[i].isoformat() if i < len(timestamps) else None,
                    "min_replicas": avg_replicas,
                    "max_replicas": peak_replicas,
                    "reason": "High traffic variance during this period",
                })
            elif peak_replicas > 1:
                # Steady traffic, recommend static scaling
                recommendations.append({
                    "type": "scale",
                    "start_time": timestamps[i].isoformat() if i < len(timestamps) else None,
                    "replicas": peak_replicas,
                    "reason": "Predicted traffic requires additional capacity",
                })
        
        return recommendations[:10]  # Limit recommendations
    
    def evaluate(
        self,
        X: np.ndarray,
        y: np.ndarray,
    ) -> EvaluationMetrics:
        """Evaluate the model.
        
        Args:
            X: Historical data for prediction
            y: Actual future values
            
        Returns:
            Evaluation metrics
        """
        import time
        start_time = time.time()
        
        X = np.asarray(X).flatten()
        y = np.asarray(y).flatten()
        
        # Make prediction
        original_horizon = self.forecast_horizon_hours
        self.forecast_horizon_hours = len(y)
        
        result = self.predict(X)
        forecast = result.prediction
        
        self.forecast_horizon_hours = original_horizon
        
        # Calculate metrics
        y_pred = np.array(forecast.forecast_values[:len(y)])
        
        ts_metrics = TimeSeriesMetrics.compute(y, y_pred)
        
        return EvaluationMetrics(
            mse=ts_metrics.mse,
            rmse=ts_metrics.rmse,
            mae=ts_metrics.mae,
            mape=ts_metrics.mape,
            smape=ts_metrics.smape,
            custom_metrics={
                "directional_accuracy": ts_metrics.directional_accuracy,
            },
            dataset_size=len(y),
            evaluation_time_seconds=(time.time() - start_time),
        )
    
    def get_feature_importance(self) -> dict[str, float]:
        """Get importance of different components."""
        importance = {}
        
        total_variance = self._data_std ** 2 if self._data_std > 0 else 1
        
        # Trend importance
        if self._trend_coeffs is not None:
            trend_var = (self._trend_coeffs[0] * 100) ** 2  # Rough estimate
            importance["trend"] = min(float(trend_var / total_variance), 1.0)
        
        # Daily seasonality importance
        if self._daily_pattern is not None:
            daily_var = np.var(self._daily_pattern)
            importance["daily_seasonality"] = float(daily_var / total_variance)
        
        # Weekly seasonality importance
        if self._weekly_pattern is not None:
            weekly_var = np.var(self._weekly_pattern)
            importance["weekly_seasonality"] = float(weekly_var / total_variance)
        
        # Residual importance
        residual_var = self._residual_std ** 2
        importance["residual"] = float(residual_var / total_variance)
        
        # Normalize
        total = sum(importance.values())
        if total > 0:
            importance = {k: v / total for k, v in importance.items()}
        
        return importance
