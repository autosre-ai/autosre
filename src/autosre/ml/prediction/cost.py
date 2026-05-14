"""Cost prediction for infrastructure spending."""

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
from autosre.ml.common.metrics import RegressionMetrics


class CostCategory(str, Enum):
    """Category of infrastructure cost."""
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    DATABASE = "database"
    CACHE = "cache"
    CDN = "cdn"
    MONITORING = "monitoring"
    OTHER = "other"


class CostTrend(str, Enum):
    """Trend direction for costs."""
    INCREASING = "increasing"
    STABLE = "stable"
    DECREASING = "decreasing"


class CostDriver(BaseModel):
    """A factor driving costs."""
    model_config = ConfigDict(validate_assignment=True)
    
    name: str
    category: CostCategory
    current_cost: float = Field(default=0.0, ge=0.0)
    predicted_cost: float = Field(default=0.0, ge=0.0)
    growth_rate_percent: float = Field(default=0.0)
    contribution_percent: float = Field(default=0.0)
    
    # Optimization potential
    optimization_potential: float = Field(default=0.0, ge=0.0)
    optimization_actions: list[str] = Field(default_factory=list)


class CostForecast(BaseModel):
    """Cost forecast result."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    forecast_id: str = Field(default_factory=generate_id)
    
    # Scope
    account_id: str = Field(default="")
    environment: str = Field(default="")  # production, staging, etc.
    
    # Forecast
    forecast_values: list[float] = Field(default_factory=list)
    forecast_timestamps: list[datetime] = Field(default_factory=list)
    currency: str = Field(default="USD")
    
    # Confidence intervals
    lower_bound: list[float] = Field(default_factory=list)
    upper_bound: list[float] = Field(default_factory=list)
    confidence_level: float = Field(default=0.95)
    
    # By category
    category_forecasts: dict[str, list[float]] = Field(default_factory=dict)
    category_current: dict[str, float] = Field(default_factory=dict)
    
    # Summary statistics
    current_monthly_cost: float = Field(default=0.0, ge=0.0)
    predicted_monthly_cost: float = Field(default=0.0, ge=0.0)
    predicted_total_cost: float = Field(default=0.0, ge=0.0)
    
    # Trend analysis
    trend: CostTrend = Field(default=CostTrend.STABLE)
    monthly_growth_rate: float = Field(default=0.0)
    year_over_year_growth: Optional[float] = None
    
    # Cost drivers
    top_drivers: list[CostDriver] = Field(default_factory=list)
    
    # Anomalies
    cost_anomalies: list[dict[str, Any]] = Field(default_factory=list)
    
    # Optimization
    total_optimization_potential: float = Field(default=0.0, ge=0.0)
    optimization_recommendations: list[dict[str, Any]] = Field(default_factory=list)
    
    # Budget analysis
    budget: Optional[float] = None
    budget_utilization: Optional[float] = None
    days_until_budget_exceeded: Optional[int] = None
    
    # Metadata
    forecast_horizon_days: int = Field(default=30)
    generated_at: datetime = Field(default_factory=utc_now)
    model_version: str = Field(default="")


class CostDataPoint(BaseModel):
    """A single cost data point."""
    model_config = ConfigDict(validate_assignment=True)
    
    timestamp: datetime
    total_cost: float = Field(ge=0.0)
    
    # By category
    compute_cost: float = Field(default=0.0, ge=0.0)
    storage_cost: float = Field(default=0.0, ge=0.0)
    network_cost: float = Field(default=0.0, ge=0.0)
    database_cost: float = Field(default=0.0, ge=0.0)
    other_cost: float = Field(default=0.0, ge=0.0)
    
    # Context
    resource_count: int = Field(default=0, ge=0)
    request_count: int = Field(default=0, ge=0)


class CostPredictor(BaseMLModel[List[CostDataPoint], CostForecast]):
    """Predict infrastructure costs.
    
    Uses historical cost data to forecast:
    - Total costs
    - Cost by category
    - Growth trends
    - Budget utilization
    
    Supports:
    - Multi-category forecasting
    - Trend analysis
    - Cost optimization recommendations
    - Budget monitoring
    """
    
    def __init__(
        self,
        forecast_horizon_days: int = 30,
        confidence_level: float = 0.95,
        detect_anomalies: bool = True,
        include_recommendations: bool = True,
    ):
        """Initialize the cost predictor.
        
        Args:
            forecast_horizon_days: Days to forecast ahead
            confidence_level: Confidence level for intervals
            detect_anomalies: Detect cost anomalies
            include_recommendations: Include optimization recommendations
        """
        super().__init__(
            name="cost_predictor",
            model_type="cost_predictor",
            hyperparameters={
                "forecast_horizon_days": forecast_horizon_days,
                "confidence_level": confidence_level,
                "detect_anomalies": detect_anomalies,
                "include_recommendations": include_recommendations,
            },
        )
        
        self.forecast_horizon_days = forecast_horizon_days
        self.confidence_level = confidence_level
        self.detect_anomalies = detect_anomalies
        self.include_recommendations = include_recommendations
        
        # Model components
        self._ts_features = TimeSeriesFeatures()
        self._scaler = FeatureScaler()
        
        # Learned parameters (per category)
        self._trend_coeffs: dict[str, np.ndarray] = {}
        self._seasonal_patterns: dict[str, np.ndarray] = {}
        self._residual_stds: dict[str, float] = {}
        
        # Training statistics
        self._category_means: dict[str, float] = {}
        self._total_mean: float = 0.0
        self._last_data: Optional[List[CostDataPoint]] = None
    
    def _prepare_category_data(
        self,
        data: List[CostDataPoint],
    ) -> dict[str, np.ndarray]:
        """Prepare time series for each cost category.
        
        Args:
            data: Cost data points
            
        Returns:
            Dictionary of category time series
        """
        categories = {
            "compute": [],
            "storage": [],
            "network": [],
            "database": [],
            "other": [],
            "total": [],
        }
        
        for point in data:
            categories["compute"].append(point.compute_cost)
            categories["storage"].append(point.storage_cost)
            categories["network"].append(point.network_cost)
            categories["database"].append(point.database_cost)
            categories["other"].append(point.other_cost)
            categories["total"].append(point.total_cost)
        
        return {k: np.array(v) for k, v in categories.items()}
    
    def _fit_category(
        self,
        values: np.ndarray,
        category: str,
    ) -> None:
        """Fit model for a single category.
        
        Args:
            values: Time series values
            category: Category name
        """
        if len(values) < 2:
            return
        
        # Store mean
        self._category_means[category] = float(np.mean(values))
        
        # Fit trend
        x = np.arange(len(values))
        self._trend_coeffs[category] = np.polyfit(x, values, 1)
        
        # Detrend
        trend = np.polyval(self._trend_coeffs[category], x)
        detrended = values - trend
        
        # Monthly seasonality (if enough data)
        if len(values) >= 60:  # ~2 months daily data
            pattern = self._extract_pattern(detrended, 30)
            self._seasonal_patterns[category] = pattern
            
            # Create full seasonal series
            seasonal_full = np.tile(pattern, (len(values) + 29) // 30)[:len(values)]
            detrended = detrended - seasonal_full
        
        # Residual std
        self._residual_stds[category] = float(np.std(detrended))
    
    def _extract_pattern(
        self,
        values: np.ndarray,
        period: int,
    ) -> np.ndarray:
        """Extract seasonal pattern.
        
        Args:
            values: Time series
            period: Pattern period
            
        Returns:
            Pattern array
        """
        n = len(values)
        pattern = np.zeros(period)
        counts = np.zeros(period)
        
        for i in range(n):
            pos = i % period
            pattern[pos] += values[i]
            counts[pos] += 1
        
        pattern = pattern / np.maximum(counts, 1)
        pattern = pattern - np.mean(pattern)
        
        return pattern
    
    def _forecast_category(
        self,
        category: str,
        start_idx: int,
        n_steps: int,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Forecast a single category.
        
        Args:
            category: Category name
            start_idx: Start index
            n_steps: Steps to forecast
            
        Returns:
            Tuple of (forecast, lower, upper)
        """
        future_idx = np.arange(start_idx, start_idx + n_steps)
        
        # Trend
        if category in self._trend_coeffs:
            forecast = np.polyval(self._trend_coeffs[category], future_idx)
        else:
            forecast = np.ones(n_steps) * self._category_means.get(category, 0)
        
        # Seasonality
        if category in self._seasonal_patterns:
            pattern = self._seasonal_patterns[category]
            for i in range(n_steps):
                forecast[i] += pattern[(start_idx + i) % len(pattern)]
        
        # Ensure non-negative
        forecast = np.maximum(forecast, 0)
        
        # Confidence intervals
        z = 1.96 if self.confidence_level == 0.95 else 1.645
        std = self._residual_stds.get(category, 1.0)
        uncertainty = std * np.sqrt(1 + np.arange(1, n_steps + 1) / n_steps)
        
        lower = np.maximum(forecast - z * uncertainty, 0)
        upper = forecast + z * uncertainty
        
        return forecast, lower, upper
    
    def fit(
        self,
        X: List[CostDataPoint],
        y: Optional[np.ndarray] = None,
        config: Optional[TrainingConfig] = None,
    ) -> "CostPredictor":
        """Train the cost predictor.
        
        Args:
            X: Historical cost data
            y: Not used
            config: Training configuration
            
        Returns:
            Self
        """
        if len(X) < 2:
            raise ValueError("Need at least 2 data points")
        
        # Store data
        self._last_data = X
        
        # Prepare category data
        category_data = self._prepare_category_data(X)
        
        # Fit each category
        for category, values in category_data.items():
            self._fit_category(values, category)
        
        self._total_mean = float(np.mean(category_data["total"]))
        
        self._is_fitted = True
        self._metadata.status = ModelStatus.TRAINED
        self._metadata.last_trained_at = utc_now()
        
        # Create version
        version = ModelVersion(
            description=f"Trained on {len(X)} days of data",
            metrics={
                "total_mean": self._total_mean,
                "compute_mean": self._category_means.get("compute", 0),
                "storage_mean": self._category_means.get("storage", 0),
                "num_samples": float(len(X)),
            },
        )
        self._metadata.add_version(version)
        
        return self
    
    def predict(
        self,
        X: Optional[List[CostDataPoint]] = None,
        budget: Optional[float] = None,
        account_id: str = "",
        environment: str = "",
    ) -> PredictionResult[CostForecast]:
        """Predict future costs.
        
        Args:
            X: Recent cost data (optional)
            budget: Monthly budget (for utilization)
            account_id: Account identifier
            environment: Environment name
            
        Returns:
            Cost forecast
        """
        import time
        start_time = time.time()
        
        if not self._is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        # Use provided or training data
        data = X if X is not None else self._last_data
        if data:
            start_idx = len(data)
        else:
            start_idx = 0
        
        n_steps = self.forecast_horizon_days
        
        # Forecast each category
        forecasts: dict[str, np.ndarray] = {}
        lowers: dict[str, np.ndarray] = {}
        uppers: dict[str, np.ndarray] = {}
        
        for category in ["compute", "storage", "network", "database", "other", "total"]:
            f, l, u = self._forecast_category(category, start_idx, n_steps)
            forecasts[category] = f
            lowers[category] = l
            uppers[category] = u
        
        # Generate timestamps
        now = utc_now()
        forecast_timestamps = [now + timedelta(days=i) for i in range(n_steps)]
        
        # Current costs
        current_costs = {}
        if data:
            last_point = data[-1]
            current_costs = {
                "compute": last_point.compute_cost,
                "storage": last_point.storage_cost,
                "network": last_point.network_cost,
                "database": last_point.database_cost,
                "other": last_point.other_cost,
            }
            current_monthly = last_point.total_cost * 30
        else:
            current_monthly = self._total_mean * 30
        
        # Summary statistics
        total_forecast = forecasts["total"]
        predicted_monthly = float(np.mean(total_forecast)) * 30
        predicted_total = float(np.sum(total_forecast))
        
        # Trend analysis
        if "total" in self._trend_coeffs:
            slope = self._trend_coeffs["total"][0]
            daily_growth_rate = slope / (self._total_mean + 1e-10)
            monthly_growth_rate = daily_growth_rate * 30 * 100  # Percentage
            
            if monthly_growth_rate > 5:
                trend = CostTrend.INCREASING
            elif monthly_growth_rate < -5:
                trend = CostTrend.DECREASING
            else:
                trend = CostTrend.STABLE
        else:
            monthly_growth_rate = 0.0
            trend = CostTrend.STABLE
        
        # Top cost drivers
        top_drivers = self._identify_cost_drivers(data, forecasts, current_costs)
        
        # Detect anomalies
        cost_anomalies = []
        if self.detect_anomalies and data:
            cost_anomalies = self._detect_cost_anomalies(data)
        
        # Budget analysis
        budget_utilization = None
        days_until_exceeded = None
        
        if budget is not None and budget > 0:
            budget_utilization = predicted_monthly / budget * 100
            
            # Find when budget is exceeded
            cumsum = np.cumsum(total_forecast)
            exceeded_idx = np.where(cumsum > budget)[0]
            if len(exceeded_idx) > 0:
                days_until_exceeded = int(exceeded_idx[0]) + 1
        
        # Optimization recommendations
        recommendations = []
        total_optimization = 0.0
        
        if self.include_recommendations:
            recommendations, total_optimization = self._generate_recommendations(
                current_costs, forecasts, top_drivers
            )
        
        # Create forecast
        forecast = CostForecast(
            account_id=account_id,
            environment=environment,
            forecast_values=total_forecast.tolist(),
            forecast_timestamps=forecast_timestamps,
            lower_bound=lowers["total"].tolist(),
            upper_bound=uppers["total"].tolist(),
            confidence_level=self.confidence_level,
            category_forecasts={
                k: v.tolist() for k, v in forecasts.items() if k != "total"
            },
            category_current=current_costs,
            current_monthly_cost=current_monthly,
            predicted_monthly_cost=predicted_monthly,
            predicted_total_cost=predicted_total,
            trend=trend,
            monthly_growth_rate=monthly_growth_rate,
            top_drivers=top_drivers,
            cost_anomalies=cost_anomalies,
            total_optimization_potential=total_optimization,
            optimization_recommendations=recommendations,
            budget=budget,
            budget_utilization=budget_utilization,
            days_until_budget_exceeded=days_until_exceeded,
            forecast_horizon_days=self.forecast_horizon_days,
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
    
    def _identify_cost_drivers(
        self,
        data: Optional[List[CostDataPoint]],
        forecasts: dict[str, np.ndarray],
        current_costs: dict[str, float],
    ) -> list[CostDriver]:
        """Identify top cost drivers.
        
        Args:
            data: Historical data
            forecasts: Category forecasts
            current_costs: Current costs by category
            
        Returns:
            List of cost drivers
        """
        drivers = []
        
        category_map = {
            "compute": CostCategory.COMPUTE,
            "storage": CostCategory.STORAGE,
            "network": CostCategory.NETWORK,
            "database": CostCategory.DATABASE,
            "other": CostCategory.OTHER,
        }
        
        total_current = sum(current_costs.values())
        
        for cat_name, cat_enum in category_map.items():
            current = current_costs.get(cat_name, 0)
            predicted = float(np.mean(forecasts.get(cat_name, [0])))
            
            if current > 0:
                growth_rate = (predicted - current) / current * 100
            else:
                growth_rate = 0.0
            
            contribution = (current / total_current * 100) if total_current > 0 else 0
            
            # Estimate optimization potential
            optimization = 0.0
            actions = []
            
            if cat_name == "compute" and current > 100:
                optimization = current * 0.2  # 20% potential savings
                actions = [
                    "Consider reserved instances for predictable workloads",
                    "Review oversized instances",
                    "Use spot instances for batch jobs",
                ]
            elif cat_name == "storage" and current > 50:
                optimization = current * 0.15
                actions = [
                    "Implement lifecycle policies for old data",
                    "Consider cheaper storage tiers",
                    "Remove unused snapshots and volumes",
                ]
            
            driver = CostDriver(
                name=cat_name.capitalize(),
                category=cat_enum,
                current_cost=current,
                predicted_cost=predicted,
                growth_rate_percent=growth_rate,
                contribution_percent=contribution,
                optimization_potential=optimization,
                optimization_actions=actions,
            )
            drivers.append(driver)
        
        # Sort by contribution
        drivers.sort(key=lambda d: d.contribution_percent, reverse=True)
        
        return drivers
    
    def _detect_cost_anomalies(
        self,
        data: List[CostDataPoint],
    ) -> list[dict[str, Any]]:
        """Detect cost anomalies in historical data.
        
        Args:
            data: Cost data points
            
        Returns:
            List of anomalies
        """
        anomalies = []
        
        costs = [p.total_cost for p in data]
        if len(costs) < 7:
            return anomalies
        
        # Calculate rolling statistics
        arr = np.array(costs)
        mean = np.mean(arr)
        std = np.std(arr)
        
        for i, point in enumerate(data):
            z_score = (point.total_cost - mean) / (std + 1e-10)
            
            if abs(z_score) > 2.5:
                anomalies.append({
                    "date": point.timestamp.isoformat(),
                    "cost": point.total_cost,
                    "expected": float(mean),
                    "z_score": float(z_score),
                    "type": "spike" if z_score > 0 else "dip",
                })
        
        return anomalies[:10]  # Limit results
    
    def _generate_recommendations(
        self,
        current_costs: dict[str, float],
        forecasts: dict[str, np.ndarray],
        drivers: list[CostDriver],
    ) -> Tuple[list[dict[str, Any]], float]:
        """Generate cost optimization recommendations.
        
        Args:
            current_costs: Current costs
            forecasts: Forecasted costs
            drivers: Cost drivers
            
        Returns:
            Tuple of (recommendations, total potential)
        """
        recommendations = []
        total_potential = 0.0
        
        for driver in drivers:
            if driver.optimization_potential > 0:
                total_potential += driver.optimization_potential
                
                recommendations.append({
                    "category": driver.category.value,
                    "potential_savings": driver.optimization_potential,
                    "actions": driver.optimization_actions,
                    "priority": "high" if driver.optimization_potential > 100 else "medium",
                })
        
        # Add general recommendations
        total_forecast = np.mean(forecasts.get("total", [0]))
        
        if total_forecast > 1000:
            recommendations.append({
                "category": "general",
                "potential_savings": total_forecast * 0.1,
                "actions": [
                    "Implement cost allocation tags for better visibility",
                    "Set up cost alerts and budgets",
                    "Review and consolidate accounts",
                ],
                "priority": "medium",
            })
        
        return recommendations, total_potential
    
    def evaluate(
        self,
        X: List[CostDataPoint],
        y: np.ndarray,
    ) -> EvaluationMetrics:
        """Evaluate the model.
        
        Args:
            X: Historical cost data
            y: Actual future costs
            
        Returns:
            Evaluation metrics
        """
        import time
        start_time = time.time()
        
        y = np.asarray(y).flatten()
        
        # Predict
        original_horizon = self.forecast_horizon_days
        self.forecast_horizon_days = len(y)
        
        result = self.predict(X)
        forecast = result.prediction
        
        self.forecast_horizon_days = original_horizon
        
        # Calculate metrics
        y_pred = np.array(forecast.forecast_values[:len(y)])
        
        reg_metrics = RegressionMetrics.compute(y, y_pred)
        
        return EvaluationMetrics(
            mse=reg_metrics.mse,
            rmse=reg_metrics.rmse,
            mae=reg_metrics.mae,
            mape=reg_metrics.mape,
            r2_score=reg_metrics.r2_score,
            dataset_size=len(y),
            evaluation_time_seconds=(time.time() - start_time),
        )
    
    def get_feature_importance(self) -> dict[str, float]:
        """Get importance of different cost categories."""
        total = sum(self._category_means.values())
        
        if total == 0:
            return {}
        
        return {
            category: mean / total
            for category, mean in self._category_means.items()
            if category != "total"
        }
