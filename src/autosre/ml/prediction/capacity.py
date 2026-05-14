"""Capacity prediction for infrastructure resources."""

from datetime import datetime, timedelta
from typing import Any, Optional, List, Dict, Tuple
from enum import Enum

import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from autosre.models.common import utc_now
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


class ResourceType(str, Enum):
    """Type of infrastructure resource."""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    GPU = "gpu"
    PODS = "pods"
    REQUESTS = "requests"


class CapacityForecast(BaseModel):
    """Capacity forecast result."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    resource_type: ResourceType
    resource_name: str = Field(default="")
    
    # Forecast
    forecast_values: list[float] = Field(default_factory=list)
    forecast_timestamps: list[datetime] = Field(default_factory=list)
    
    # Confidence intervals
    lower_bound: list[float] = Field(default_factory=list)
    upper_bound: list[float] = Field(default_factory=list)
    confidence_level: float = Field(default=0.95)
    
    # Capacity analysis
    current_capacity: float = Field(default=0.0)
    current_usage: float = Field(default=0.0)
    current_utilization: float = Field(default=0.0)
    
    # Predictions
    days_until_80_pct: Optional[int] = None
    days_until_90_pct: Optional[int] = None
    days_until_100_pct: Optional[int] = None
    
    # Recommendations
    recommended_scale_up: Optional[float] = None
    recommended_scale_date: Optional[datetime] = None
    
    # Metadata
    forecast_horizon_hours: int = Field(default=168)  # 1 week
    generated_at: datetime = Field(default_factory=utc_now)
    model_version: str = Field(default="")


class CapacityPredictor(BaseMLModel[np.ndarray, CapacityForecast]):
    """Predict infrastructure capacity needs.
    
    Uses time series forecasting to predict resource utilization
    and identify when capacity thresholds will be reached.
    
    Supports:
    - CPU, memory, disk, network forecasting
    - Seasonality detection (daily, weekly)
    - Trend analysis
    - Confidence intervals
    """
    
    def __init__(
        self,
        resource_type: ResourceType = ResourceType.CPU,
        forecast_horizon_hours: int = 168,
        seasonality_periods: Optional[list[int]] = None,
        confidence_level: float = 0.95,
        use_external_features: bool = False,
    ):
        """Initialize the capacity predictor.
        
        Args:
            resource_type: Type of resource to predict
            forecast_horizon_hours: Hours to forecast ahead
            seasonality_periods: Seasonal periods in hours (e.g., [24, 168] for daily/weekly)
            confidence_level: Confidence level for intervals
            use_external_features: Include external features (time of day, etc.)
        """
        super().__init__(
            name=f"capacity_predictor_{resource_type.value}",
            model_type="capacity_predictor",
            hyperparameters={
                "resource_type": resource_type.value,
                "forecast_horizon_hours": forecast_horizon_hours,
                "seasonality_periods": seasonality_periods or [24, 168],
                "confidence_level": confidence_level,
                "use_external_features": use_external_features,
            },
        )
        
        self.resource_type = resource_type
        self.forecast_horizon_hours = forecast_horizon_hours
        self.seasonality_periods = seasonality_periods or [24, 168]
        self.confidence_level = confidence_level
        self.use_external_features = use_external_features
        
        # Model components
        self._preprocessor = TimeSeriesPreprocessor(normalize=True, detrend=False)
        self._feature_extractor = TimeSeriesFeatures()
        self._scaler = FeatureScaler()
        
        # Fitted parameters
        self._trend_coeffs: Optional[np.ndarray] = None
        self._seasonal_components: Dict[int, np.ndarray] = {}
        self._residual_std: float = 0.0
        self._last_values: Optional[np.ndarray] = None
        self._timestamps: Optional[np.ndarray] = None
    
    def _extract_trend(self, values: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Extract linear trend from time series.
        
        Args:
            values: Time series values
            
        Returns:
            Tuple of (trend coefficients, detrended values)
        """
        x = np.arange(len(values))
        coeffs = np.polyfit(x, values, 1)
        trend = np.polyval(coeffs, x)
        detrended = values - trend
        return coeffs, detrended
    
    def _extract_seasonality(
        self,
        values: np.ndarray,
        period: int,
    ) -> np.ndarray:
        """Extract seasonal component for a given period.
        
        Args:
            values: Time series values (already detrended)
            period: Seasonal period in samples
            
        Returns:
            Seasonal component
        """
        if len(values) < period:
            return np.zeros(period)
        
        # Calculate average for each position in the cycle
        n_cycles = len(values) // period
        if n_cycles == 0:
            return np.zeros(period)
        
        # Reshape to extract seasonal pattern
        truncated = values[:n_cycles * period]
        reshaped = truncated.reshape(n_cycles, period)
        seasonal = np.mean(reshaped, axis=0)
        
        # Normalize to zero mean
        seasonal = seasonal - np.mean(seasonal)
        
        return seasonal
    
    def _decompose(
        self,
        values: np.ndarray,
    ) -> Dict[str, np.ndarray]:
        """Decompose time series into components.
        
        Args:
            values: Time series values
            
        Returns:
            Dictionary with trend, seasonal, and residual components
        """
        # Extract trend
        trend_coeffs, detrended = self._extract_trend(values)
        self._trend_coeffs = trend_coeffs
        
        # Extract seasonality for each period
        remaining = detrended.copy()
        seasonal_sum = np.zeros_like(values)
        
        for period in sorted(self.seasonality_periods, reverse=True):
            if len(values) >= period * 2:
                seasonal = self._extract_seasonality(remaining, period)
                self._seasonal_components[period] = seasonal
                
                # Create full seasonal series
                n_repeats = (len(values) + period - 1) // period
                full_seasonal = np.tile(seasonal, n_repeats)[:len(values)]
                seasonal_sum += full_seasonal
                remaining = remaining - full_seasonal
        
        # Residual
        residual = remaining
        self._residual_std = np.std(residual)
        
        return {
            "trend_coeffs": trend_coeffs,
            "trend": np.polyval(trend_coeffs, np.arange(len(values))),
            "seasonal": seasonal_sum,
            "residual": residual,
        }
    
    def _forecast_components(
        self,
        n_steps: int,
        start_idx: int,
    ) -> Dict[str, np.ndarray]:
        """Forecast decomposed components.
        
        Args:
            n_steps: Number of steps to forecast
            start_idx: Starting index for forecast
            
        Returns:
            Dictionary with forecasted components
        """
        future_idx = np.arange(start_idx, start_idx + n_steps)
        
        # Trend forecast
        trend = np.polyval(self._trend_coeffs, future_idx)
        
        # Seasonal forecast
        seasonal = np.zeros(n_steps)
        for period, component in self._seasonal_components.items():
            for i in range(n_steps):
                seasonal[i] += component[(start_idx + i) % period]
        
        return {
            "trend": trend,
            "seasonal": seasonal,
        }
    
    def fit(
        self,
        X: np.ndarray,
        y: Optional[np.ndarray] = None,
        timestamps: Optional[np.ndarray] = None,
        config: Optional[TrainingConfig] = None,
    ) -> "CapacityPredictor":
        """Train the capacity predictor.
        
        Args:
            X: Historical time series data (usage values)
            y: Not used (target is future of X)
            timestamps: Timestamps for X (optional)
            config: Training configuration
            
        Returns:
            Self
        """
        X = np.asarray(X).flatten()
        
        if len(X) < 2:
            raise ValueError("Need at least 2 data points to fit")
        
        # Store original values
        self._last_values = X.copy()
        self._timestamps = timestamps
        
        # Decompose time series
        decomposition = self._decompose(X)
        
        # Store for later
        self._is_fitted = True
        self._metadata.status = ModelStatus.TRAINED
        self._metadata.last_trained_at = utc_now()
        
        # Create version
        version = ModelVersion(
            description=f"Trained on {len(X)} samples",
            metrics={
                "residual_std": self._residual_std,
                "trend_slope": float(self._trend_coeffs[0]) if self._trend_coeffs is not None else 0,
                "num_samples": float(len(X)),
            },
        )
        self._metadata.add_version(version)
        
        return self
    
    def predict(
        self,
        X: Optional[np.ndarray] = None,
        current_capacity: float = 100.0,
        resource_name: str = "",
    ) -> PredictionResult[CapacityForecast]:
        """Predict future capacity needs.
        
        Args:
            X: Recent usage data (optional, uses training data if None)
            current_capacity: Current total capacity
            resource_name: Name of the resource
            
        Returns:
            Capacity forecast result
        """
        import time
        start_time = time.time()
        
        if not self._is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        # Use provided data or last values from training
        if X is not None:
            values = np.asarray(X).flatten()
            # Update decomposition with new data
            decomposition = self._decompose(values)
            start_idx = len(values)
        else:
            values = self._last_values
            start_idx = len(values)
        
        # Forecast
        n_steps = self.forecast_horizon_hours
        forecast_components = self._forecast_components(n_steps, start_idx)
        
        # Combine components
        forecast_values = forecast_components["trend"] + forecast_components["seasonal"]
        
        # Add slight randomness for more realistic forecasts (optional)
        # forecast_values += np.random.normal(0, self._residual_std * 0.1, n_steps)
        
        # Clip to reasonable range
        forecast_values = np.clip(forecast_values, 0, current_capacity * 2)
        
        # Calculate confidence intervals
        z_score = 1.96 if self.confidence_level == 0.95 else 1.645  # 95% or 90%
        
        # Uncertainty grows with forecast horizon
        uncertainty = self._residual_std * np.sqrt(np.arange(1, n_steps + 1) / n_steps)
        lower_bound = forecast_values - z_score * uncertainty
        upper_bound = forecast_values + z_score * uncertainty
        
        lower_bound = np.clip(lower_bound, 0, None)
        
        # Generate timestamps
        now = utc_now()
        forecast_timestamps = [
            now + timedelta(hours=i) for i in range(n_steps)
        ]
        
        # Calculate capacity thresholds
        current_usage = float(values[-1]) if len(values) > 0 else 0
        current_utilization = current_usage / current_capacity if current_capacity > 0 else 0
        
        # Find when thresholds are reached
        days_to_80 = None
        days_to_90 = None
        days_to_100 = None
        
        threshold_80 = current_capacity * 0.8
        threshold_90 = current_capacity * 0.9
        threshold_100 = current_capacity
        
        for i, val in enumerate(forecast_values):
            hours = i + 1
            days = hours / 24
            
            if days_to_80 is None and val >= threshold_80:
                days_to_80 = int(np.ceil(days))
            if days_to_90 is None and val >= threshold_90:
                days_to_90 = int(np.ceil(days))
            if days_to_100 is None and val >= threshold_100:
                days_to_100 = int(np.ceil(days))
        
        # Recommendations
        recommended_scale_up = None
        recommended_scale_date = None
        
        if days_to_80 is not None:
            # Recommend scaling before 80% threshold
            scale_buffer_days = max(1, days_to_80 - 1)
            recommended_scale_date = now + timedelta(days=scale_buffer_days)
            
            # Calculate how much to scale
            peak_forecast = float(np.max(forecast_values))
            recommended_scale_up = peak_forecast * 1.25  # 25% buffer above peak
        
        # Create forecast
        forecast = CapacityForecast(
            resource_type=self.resource_type,
            resource_name=resource_name,
            forecast_values=forecast_values.tolist(),
            forecast_timestamps=forecast_timestamps,
            lower_bound=lower_bound.tolist(),
            upper_bound=upper_bound.tolist(),
            confidence_level=self.confidence_level,
            current_capacity=current_capacity,
            current_usage=current_usage,
            current_utilization=current_utilization,
            days_until_80_pct=days_to_80,
            days_until_90_pct=days_to_90,
            days_until_100_pct=days_to_100,
            recommended_scale_up=recommended_scale_up,
            recommended_scale_date=recommended_scale_date,
            forecast_horizon_hours=self.forecast_horizon_hours,
            model_version=self._metadata.current_version.version_id if self._metadata.current_version else "",
        )
        
        latency = (time.time() - start_time) * 1000
        
        return PredictionResult(
            prediction=forecast,
            confidence=self.confidence_level,
            lower_bound=lower_bound[0] if len(lower_bound) > 0 else None,
            upper_bound=upper_bound[0] if len(upper_bound) > 0 else None,
            model_id=self.model_id,
            model_version=self._metadata.current_version.version_id if self._metadata.current_version else "",
            latency_ms=latency,
            explanation=f"Capacity forecast for {self.resource_type.value} over {self.forecast_horizon_hours} hours",
        )
    
    def evaluate(
        self,
        X: np.ndarray,
        y: np.ndarray,
    ) -> EvaluationMetrics:
        """Evaluate the model.
        
        Args:
            X: Historical data used to make predictions
            y: Actual future values to compare against
            
        Returns:
            Evaluation metrics
        """
        import time
        start_time = time.time()
        
        X = np.asarray(X).flatten()
        y = np.asarray(y).flatten()
        
        # Make predictions
        n_steps = len(y)
        original_horizon = self.forecast_horizon_hours
        self.forecast_horizon_hours = n_steps
        
        result = self.predict(X)
        forecast = result.prediction
        
        self.forecast_horizon_hours = original_horizon
        
        # Calculate metrics
        y_pred = np.array(forecast.forecast_values[:len(y)])
        
        ts_metrics = TimeSeriesMetrics.compute(y, y_pred, forecast_horizon=n_steps)
        
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
        """Get feature importance."""
        importance = {}
        
        # Trend importance
        if self._trend_coeffs is not None:
            trend_magnitude = abs(self._trend_coeffs[0])
            importance["trend"] = float(trend_magnitude)
        
        # Seasonal importance
        for period, component in self._seasonal_components.items():
            seasonal_magnitude = np.std(component)
            importance[f"seasonality_{period}h"] = float(seasonal_magnitude)
        
        # Residual (noise) importance
        importance["residual"] = self._residual_std
        
        # Normalize
        total = sum(importance.values())
        if total > 0:
            importance = {k: v / total for k, v in importance.items()}
        
        return importance
    
    def explain_prediction(
        self,
        X: np.ndarray,
        method: str = "decomposition",
    ) -> dict[str, Any]:
        """Explain a capacity prediction.
        
        Args:
            X: Input data
            method: Explanation method
            
        Returns:
            Explanation details
        """
        X = np.asarray(X).flatten()
        
        # Decompose to show contributions
        decomposition = self._decompose(X)
        
        # Recent trend direction
        recent_trend = "increasing" if self._trend_coeffs[0] > 0 else "decreasing"
        trend_rate = abs(self._trend_coeffs[0])
        
        # Dominant seasonal pattern
        dominant_period = None
        max_amplitude = 0
        for period, component in self._seasonal_components.items():
            amplitude = np.std(component)
            if amplitude > max_amplitude:
                max_amplitude = amplitude
                dominant_period = period
        
        return {
            "method": method,
            "decomposition": {
                "trend_direction": recent_trend,
                "trend_rate_per_sample": float(trend_rate),
                "trend_contribution": float(np.std(decomposition["trend"])),
                "seasonal_contribution": float(np.std(decomposition["seasonal"])),
                "residual_contribution": float(np.std(decomposition["residual"])),
            },
            "seasonality": {
                "dominant_period_hours": dominant_period,
                "periods_detected": list(self._seasonal_components.keys()),
            },
            "features": self.get_feature_importance(),
        }


class MultiResourceCapacityPredictor:
    """Predict capacity for multiple resources simultaneously."""
    
    def __init__(
        self,
        resources: Optional[list[ResourceType]] = None,
        forecast_horizon_hours: int = 168,
    ):
        """Initialize the multi-resource predictor.
        
        Args:
            resources: List of resource types to predict
            forecast_horizon_hours: Hours to forecast ahead
        """
        self.resources = resources or list(ResourceType)
        self.forecast_horizon_hours = forecast_horizon_hours
        
        self._predictors: dict[ResourceType, CapacityPredictor] = {}
        
        for resource in self.resources:
            self._predictors[resource] = CapacityPredictor(
                resource_type=resource,
                forecast_horizon_hours=forecast_horizon_hours,
            )
    
    def fit(
        self,
        data: dict[ResourceType, np.ndarray],
        config: Optional[TrainingConfig] = None,
    ) -> "MultiResourceCapacityPredictor":
        """Fit predictors for all resources.
        
        Args:
            data: Dictionary mapping resource types to time series
            config: Training configuration
            
        Returns:
            Self
        """
        for resource, values in data.items():
            if resource in self._predictors:
                self._predictors[resource].fit(values, config=config)
        
        return self
    
    def predict(
        self,
        data: Optional[dict[ResourceType, np.ndarray]] = None,
        capacities: Optional[dict[ResourceType, float]] = None,
    ) -> dict[ResourceType, CapacityForecast]:
        """Predict capacity for all resources.
        
        Args:
            data: Recent data for each resource
            capacities: Current capacity for each resource
            
        Returns:
            Dictionary of forecasts
        """
        capacities = capacities or {}
        data = data or {}
        
        forecasts = {}
        
        for resource, predictor in self._predictors.items():
            if not predictor.is_fitted:
                continue
            
            resource_data = data.get(resource)
            capacity = capacities.get(resource, 100.0)
            
            result = predictor.predict(
                X=resource_data,
                current_capacity=capacity,
            )
            forecasts[resource] = result.prediction
        
        return forecasts
    
    def get_critical_resources(
        self,
        forecasts: dict[ResourceType, CapacityForecast],
        threshold_days: int = 7,
    ) -> list[tuple[ResourceType, int]]:
        """Get resources that will reach capacity soon.
        
        Args:
            forecasts: Capacity forecasts
            threshold_days: Days threshold for "soon"
            
        Returns:
            List of (resource, days_until_full) tuples, sorted by urgency
        """
        critical = []
        
        for resource, forecast in forecasts.items():
            if forecast.days_until_90_pct is not None:
                if forecast.days_until_90_pct <= threshold_days:
                    critical.append((resource, forecast.days_until_90_pct))
        
        # Sort by urgency (smallest days first)
        critical.sort(key=lambda x: x[1])
        
        return critical
