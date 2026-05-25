"""
Cost Forecasting and Anomaly Detection

Provides cost forecasting capabilities including:
- Time series forecasting for cost projections
- Budget alerts and monitoring
- Cost anomaly detection
- Spending trend analysis
"""

import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ForecastModel(str, Enum):
    """Forecasting model types."""
    LINEAR = "linear"           # Simple linear regression
    EXPONENTIAL = "exponential" # Exponential smoothing
    SEASONAL = "seasonal"       # Seasonal decomposition
    MOVING_AVERAGE = "moving_average"  # Moving average


class BudgetStatus(str, Enum):
    """Budget status levels."""
    ON_TRACK = "on_track"       # Within budget
    WARNING = "warning"         # Approaching budget (>80%)
    CRITICAL = "critical"       # Exceeded or will exceed budget
    OVERSPENT = "overspent"     # Already over budget


class SpendingTrend(str, Enum):
    """Spending trend directions."""
    ACCELERATING = "accelerating"   # Spend growth is accelerating
    STEADY_GROWTH = "steady_growth" # Consistent growth
    STABLE = "stable"               # Relatively flat
    DECLINING = "declining"         # Spend is decreasing
    VOLATILE = "volatile"           # Unpredictable pattern


@dataclass
class CostForecast:
    """Cost forecast result."""
    period_start: datetime
    period_end: datetime
    forecast_days: int
    forecasted_cost: float
    confidence_lower: float  # Lower bound of confidence interval
    confidence_upper: float  # Upper bound of confidence interval
    confidence_level: float  # e.g., 0.95 for 95% CI
    model_used: ForecastModel
    historical_average: float
    growth_rate: float  # Monthly growth rate
    currency: str = "USD"
    breakdown_by_service: dict[str, float] = field(default_factory=dict)
    breakdown_by_team: dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "forecast_days": self.forecast_days,
            "forecasted_cost": self.forecasted_cost,
            "confidence_lower": self.confidence_lower,
            "confidence_upper": self.confidence_upper,
            "confidence_level": self.confidence_level,
            "model_used": self.model_used.value,
            "historical_average": self.historical_average,
            "growth_rate": self.growth_rate,
            "currency": self.currency,
            "breakdown_by_service": self.breakdown_by_service,
            "breakdown_by_team": self.breakdown_by_team,
        }
    
    @property
    def summary(self) -> str:
        """Human-readable summary."""
        return (
            f"Forecast for {self.forecast_days} days: {self.currency} {self.forecasted_cost:,.2f}\n"
            f"Confidence Interval ({self.confidence_level:.0%}): "
            f"{self.currency} {self.confidence_lower:,.2f} - {self.currency} {self.confidence_upper:,.2f}\n"
            f"Monthly Growth Rate: {self.growth_rate:.1%}"
        )


@dataclass
class BudgetAlert:
    """A budget alert."""
    budget_name: str
    budget_amount: float
    current_spend: float
    forecasted_spend: float
    status: BudgetStatus
    percent_used: float
    days_remaining: int
    days_until_exhausted: Optional[int]
    overage_amount: float
    currency: str = "USD"
    owner: Optional[str] = None
    services: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "budget_name": self.budget_name,
            "budget_amount": self.budget_amount,
            "current_spend": self.current_spend,
            "forecasted_spend": self.forecasted_spend,
            "status": self.status.value,
            "percent_used": self.percent_used,
            "days_remaining": self.days_remaining,
            "days_until_exhausted": self.days_until_exhausted,
            "overage_amount": self.overage_amount,
            "currency": self.currency,
            "owner": self.owner,
            "services": self.services,
            "recommendations": self.recommendations,
        }
    
    @property
    def summary(self) -> str:
        """Human-readable summary."""
        status_emoji = {
            BudgetStatus.ON_TRACK: "✅",
            BudgetStatus.WARNING: "⚠️",
            BudgetStatus.CRITICAL: "🔴",
            BudgetStatus.OVERSPENT: "💸",
        }
        emoji = status_emoji.get(self.status, "")
        
        summary = (
            f"{emoji} {self.budget_name}: {self.status.value.upper()}\n"
            f"   Spent: {self.currency} {self.current_spend:,.2f} / {self.currency} {self.budget_amount:,.2f} "
            f"({self.percent_used:.1f}%)\n"
            f"   Forecast: {self.currency} {self.forecasted_spend:,.2f}"
        )
        
        if self.days_until_exhausted:
            summary += f"\n   Budget exhausts in {self.days_until_exhausted} days"
        
        if self.overage_amount > 0:
            summary += f"\n   Overage: {self.currency} {self.overage_amount:,.2f}"
        
        return summary


@dataclass
class CostAnomaly:
    """A detected cost anomaly."""
    timestamp: datetime
    service: Optional[str]
    team: Optional[str]
    expected_cost: float
    actual_cost: float
    deviation: float  # How many standard deviations from normal
    anomaly_type: str  # spike, drop
    impact: float  # Dollar impact of the anomaly
    likely_causes: list[str] = field(default_factory=list)
    related_events: list[dict] = field(default_factory=list)
    currency: str = "USD"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "service": self.service,
            "team": self.team,
            "expected_cost": self.expected_cost,
            "actual_cost": self.actual_cost,
            "deviation": self.deviation,
            "anomaly_type": self.anomaly_type,
            "impact": self.impact,
            "likely_causes": self.likely_causes,
            "related_events": self.related_events,
            "currency": self.currency,
        }
    
    @property
    def summary(self) -> str:
        """Human-readable summary."""
        emoji = "📈" if self.anomaly_type == "spike" else "📉"
        
        return (
            f"{emoji} Cost {self.anomaly_type} detected on {self.timestamp.date()}\n"
            f"   Service: {self.service or 'All'}\n"
            f"   Expected: {self.currency} {self.expected_cost:,.2f}, "
            f"Actual: {self.currency} {self.actual_cost:,.2f}\n"
            f"   Deviation: {self.deviation:.1f} standard deviations\n"
            f"   Impact: {self.currency} {abs(self.impact):,.2f}"
        )


class AnomalyDetector:
    """
    Detects cost anomalies using statistical methods.
    """
    
    def __init__(
        self,
        sensitivity: float = 2.0,  # Standard deviations for anomaly
        min_data_points: int = 14,  # Minimum history needed
    ):
        self.sensitivity = sensitivity
        self.min_data_points = min_data_points
    
    def detect(
        self,
        daily_costs: dict[datetime, float],
        service: Optional[str] = None,
        team: Optional[str] = None,
    ) -> list[CostAnomaly]:
        """
        Detect anomalies in daily cost data.
        
        Args:
            daily_costs: Dict mapping dates to costs
            service: Optional service name for context
            team: Optional team name for context
            
        Returns:
            List of detected anomalies
        """
        if len(daily_costs) < self.min_data_points:
            return []
        
        sorted_dates = sorted(daily_costs.keys())
        values = [daily_costs[d] for d in sorted_dates]
        
        # Calculate statistics using rolling window
        anomalies = []
        window_size = min(14, len(values) - 1)
        
        for i in range(window_size, len(values)):
            window = values[i - window_size:i]
            current = values[i]
            
            mean = statistics.mean(window)
            std = statistics.stdev(window) if len(window) > 1 else mean * 0.1
            
            if std == 0:
                std = mean * 0.1 or 1
            
            z_score = (current - mean) / std
            
            if abs(z_score) > self.sensitivity:
                anomaly_type = "spike" if z_score > 0 else "drop"
                
                anomaly = CostAnomaly(
                    timestamp=sorted_dates[i],
                    service=service,
                    team=team,
                    expected_cost=mean,
                    actual_cost=current,
                    deviation=abs(z_score),
                    anomaly_type=anomaly_type,
                    impact=current - mean,
                    likely_causes=self._identify_likely_causes(anomaly_type, z_score),
                )
                anomalies.append(anomaly)
        
        return anomalies
    
    def _identify_likely_causes(
        self,
        anomaly_type: str,
        deviation: float,
    ) -> list[str]:
        """Identify likely causes for an anomaly."""
        causes = []
        
        if anomaly_type == "spike":
            if deviation > 5:
                causes.append("Major infrastructure change or outage")
                causes.append("New high-cost resource provisioned")
            elif deviation > 3:
                causes.append("Significant workload increase")
                causes.append("Auto-scaling triggered")
            else:
                causes.append("Traffic spike")
                causes.append("Data transfer increase")
            
            causes.append("Check for unintended resource creation")
            causes.append("Review recent deployments")
        
        else:  # drop
            if deviation > 5:
                causes.append("Resources terminated or stopped")
                causes.append("Service outage")
            elif deviation > 3:
                causes.append("Reserved instance/savings plan activated")
                causes.append("Significant workload decrease")
            else:
                causes.append("Traffic reduction")
                causes.append("Cost optimization implemented")
            
            causes.append("Verify services are running correctly")
        
        return causes


class CostForecaster:
    """
    Forecasts future cloud costs.
    
    Uses historical cost data to predict future spending
    and provide budget alerts.
    """
    
    def __init__(
        self,
        default_model: ForecastModel = ForecastModel.LINEAR,
        confidence_level: float = 0.95,
    ):
        self.default_model = default_model
        self.confidence_level = confidence_level
        self._anomaly_detector = AnomalyDetector()
    
    def forecast(
        self,
        daily_costs: dict[datetime, float],
        forecast_days: int = 30,
        model: Optional[ForecastModel] = None,
    ) -> CostForecast:
        """
        Forecast costs for the next N days.
        
        Args:
            daily_costs: Historical daily costs
            forecast_days: Number of days to forecast
            model: Forecasting model to use
            
        Returns:
            CostForecast with predictions
        """
        model = model or self.default_model
        
        if not daily_costs:
            return self._empty_forecast(forecast_days)
        
        sorted_dates = sorted(daily_costs.keys())
        values = [daily_costs[d] for d in sorted_dates]
        
        # Calculate historical statistics
        historical_avg = statistics.mean(values)
        std_dev = statistics.stdev(values) if len(values) > 1 else historical_avg * 0.1
        
        # Calculate growth rate
        if len(values) >= 7:
            first_week_avg = statistics.mean(values[:7])
            last_week_avg = statistics.mean(values[-7:])
            if first_week_avg > 0:
                total_growth = (last_week_avg - first_week_avg) / first_week_avg
                weeks = len(values) / 7
                weekly_growth = total_growth / weeks if weeks > 0 else 0
                monthly_growth = weekly_growth * 4
            else:
                monthly_growth = 0
        else:
            monthly_growth = 0
        
        # Generate forecast based on model
        if model == ForecastModel.LINEAR:
            forecasted_daily = self._linear_forecast(values)
        elif model == ForecastModel.MOVING_AVERAGE:
            forecasted_daily = self._moving_average_forecast(values)
        elif model == ForecastModel.EXPONENTIAL:
            forecasted_daily = self._exponential_forecast(values)
        else:
            forecasted_daily = historical_avg
        
        # Apply growth rate to daily forecast
        days_from_end = forecast_days / 2  # Average position in forecast period
        growth_factor = 1 + (monthly_growth * days_from_end / 30)
        forecasted_daily *= max(0.5, min(2.0, growth_factor))  # Cap growth factor
        
        forecasted_total = forecasted_daily * forecast_days
        
        # Calculate confidence interval
        # Using simplified approach: ± 2 standard deviations
        margin = std_dev * 2 * (forecast_days ** 0.5)  # Error grows with sqrt of time
        
        period_start = sorted_dates[-1] + timedelta(days=1)
        period_end = period_start + timedelta(days=forecast_days)
        
        return CostForecast(
            period_start=period_start,
            period_end=period_end,
            forecast_days=forecast_days,
            forecasted_cost=forecasted_total,
            confidence_lower=max(0, forecasted_total - margin),
            confidence_upper=forecasted_total + margin,
            confidence_level=self.confidence_level,
            model_used=model,
            historical_average=historical_avg * forecast_days,
            growth_rate=monthly_growth,
        )
    
    def forecast_by_dimension(
        self,
        costs_by_dimension: dict[str, dict[datetime, float]],
        dimension_name: str,
        forecast_days: int = 30,
    ) -> dict[str, CostForecast]:
        """
        Forecast costs for each value in a dimension.
        
        Args:
            costs_by_dimension: Dict of dimension_value -> daily_costs
            dimension_name: Name of the dimension (service, team, etc.)
            forecast_days: Number of days to forecast
            
        Returns:
            Dict of dimension_value -> CostForecast
        """
        forecasts = {}
        
        for dim_value, daily_costs in costs_by_dimension.items():
            forecast = self.forecast(daily_costs, forecast_days)
            forecasts[dim_value] = forecast
        
        return forecasts
    
    def check_budgets(
        self,
        budgets: list[dict],
        current_costs: dict[str, float],
        daily_costs: dict[datetime, float],
    ) -> list[BudgetAlert]:
        """
        Check budgets and generate alerts.
        
        Args:
            budgets: List of budget configurations
            current_costs: Current month spend by budget
            daily_costs: Daily cost history for forecasting
            
        Returns:
            List of budget alerts
        """
        alerts = []
        
        # Calculate days remaining in period
        now = datetime.now(timezone.utc)
        days_in_month = 30  # Simplified
        day_of_month = now.day
        days_remaining = days_in_month - day_of_month
        
        for budget in budgets:
            budget_name = budget.get("name", "Unknown")
            budget_amount = budget.get("amount", 0)
            owner = budget.get("owner")
            services = budget.get("services", [])
            
            # Get current spend for this budget
            current_spend = current_costs.get(budget_name, 0)
            
            # Forecast remaining spend
            forecast = self.forecast(daily_costs, days_remaining)
            forecasted_total = current_spend + forecast.forecasted_cost
            
            # Calculate metrics
            percent_used = (current_spend / budget_amount * 100) if budget_amount > 0 else 0
            
            # Determine status
            if current_spend >= budget_amount:
                status = BudgetStatus.OVERSPENT
                overage = current_spend - budget_amount
            elif forecasted_total >= budget_amount:
                if percent_used >= 80:
                    status = BudgetStatus.CRITICAL
                else:
                    status = BudgetStatus.WARNING
                overage = max(0, forecasted_total - budget_amount)
            elif percent_used >= 80:
                status = BudgetStatus.WARNING
                overage = 0
            else:
                status = BudgetStatus.ON_TRACK
                overage = 0
            
            # Calculate days until budget exhausted
            daily_rate = current_spend / day_of_month if day_of_month > 0 else 0
            if daily_rate > 0:
                remaining_budget = budget_amount - current_spend
                days_until_exhausted = int(remaining_budget / daily_rate) if remaining_budget > 0 else 0
            else:
                days_until_exhausted = None
            
            # Generate recommendations
            recommendations = self._generate_budget_recommendations(
                status, percent_used, days_remaining, services
            )
            
            alert = BudgetAlert(
                budget_name=budget_name,
                budget_amount=budget_amount,
                current_spend=current_spend,
                forecasted_spend=forecasted_total,
                status=status,
                percent_used=percent_used,
                days_remaining=days_remaining,
                days_until_exhausted=days_until_exhausted,
                overage_amount=overage,
                owner=owner,
                services=services,
                recommendations=recommendations,
            )
            alerts.append(alert)
        
        # Sort by severity
        status_order = {
            BudgetStatus.OVERSPENT: 0,
            BudgetStatus.CRITICAL: 1,
            BudgetStatus.WARNING: 2,
            BudgetStatus.ON_TRACK: 3,
        }
        alerts.sort(key=lambda a: status_order.get(a.status, 4))
        
        return alerts
    
    def analyze_spending_trend(
        self,
        daily_costs: dict[datetime, float],
    ) -> tuple[SpendingTrend, dict[str, Any]]:
        """
        Analyze overall spending trend.
        
        Returns:
            Tuple of (trend_type, analysis_details)
        """
        if len(daily_costs) < 14:
            return SpendingTrend.STABLE, {"reason": "Insufficient data"}
        
        sorted_dates = sorted(daily_costs.keys())
        values = [daily_costs[d] for d in sorted_dates]
        
        # Calculate weekly averages
        week_size = 7
        num_weeks = len(values) // week_size
        weekly_avgs = []
        
        for i in range(num_weeks):
            week_data = values[i * week_size:(i + 1) * week_size]
            weekly_avgs.append(statistics.mean(week_data))
        
        if len(weekly_avgs) < 2:
            return SpendingTrend.STABLE, {"reason": "Insufficient weekly data"}
        
        # Calculate week-over-week changes
        wow_changes = []
        for i in range(1, len(weekly_avgs)):
            if weekly_avgs[i - 1] > 0:
                change = (weekly_avgs[i] - weekly_avgs[i - 1]) / weekly_avgs[i - 1]
                wow_changes.append(change)
        
        if not wow_changes:
            return SpendingTrend.STABLE, {"reason": "Unable to calculate changes"}
        
        avg_change = statistics.mean(wow_changes)
        change_variance = statistics.variance(wow_changes) if len(wow_changes) > 1 else 0
        
        # Determine trend
        details = {
            "weekly_averages": weekly_avgs,
            "week_over_week_changes": wow_changes,
            "average_weekly_change": avg_change,
            "change_variance": change_variance,
        }
        
        # High variance = volatile
        if change_variance > 0.1:
            return SpendingTrend.VOLATILE, details
        
        # Check for acceleration (increasing rate of change)
        if len(wow_changes) >= 3:
            first_half = statistics.mean(wow_changes[:len(wow_changes) // 2])
            second_half = statistics.mean(wow_changes[len(wow_changes) // 2:])
            
            if second_half > first_half + 0.05 and avg_change > 0.05:
                return SpendingTrend.ACCELERATING, details
        
        # Determine direction
        if avg_change > 0.05:
            return SpendingTrend.STEADY_GROWTH, details
        elif avg_change < -0.05:
            return SpendingTrend.DECLINING, details
        else:
            return SpendingTrend.STABLE, details
    
    def detect_anomalies(
        self,
        daily_costs: dict[datetime, float],
        service: Optional[str] = None,
        team: Optional[str] = None,
    ) -> list[CostAnomaly]:
        """
        Detect cost anomalies in historical data.
        
        Args:
            daily_costs: Historical daily costs
            service: Optional service filter
            team: Optional team filter
            
        Returns:
            List of detected cost anomalies
        """
        return self._anomaly_detector.detect(daily_costs, service, team)
    
    def _empty_forecast(self, forecast_days: int) -> CostForecast:
        """Create empty forecast when no data available."""
        now = datetime.now(timezone.utc)
        return CostForecast(
            period_start=now,
            period_end=now + timedelta(days=forecast_days),
            forecast_days=forecast_days,
            forecasted_cost=0,
            confidence_lower=0,
            confidence_upper=0,
            confidence_level=self.confidence_level,
            model_used=self.default_model,
            historical_average=0,
            growth_rate=0,
        )
    
    def _linear_forecast(self, values: list[float]) -> float:
        """Simple linear regression forecast."""
        n = len(values)
        if n < 2:
            return values[0] if values else 0
        
        x = list(range(n))
        x_mean = statistics.mean(x)
        y_mean = statistics.mean(values)
        
        numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, values))
        denominator = sum((xi - x_mean) ** 2 for xi in x)
        
        if denominator == 0:
            return y_mean
        
        slope = numerator / denominator
        intercept = y_mean - slope * x_mean
        
        # Forecast next day
        return intercept + slope * n
    
    def _moving_average_forecast(self, values: list[float], window: int = 7) -> float:
        """Moving average forecast."""
        if not values:
            return 0
        
        window = min(window, len(values))
        return statistics.mean(values[-window:])
    
    def _exponential_forecast(self, values: list[float], alpha: float = 0.3) -> float:
        """Exponential smoothing forecast."""
        if not values:
            return 0
        
        smoothed = values[0]
        for value in values[1:]:
            smoothed = alpha * value + (1 - alpha) * smoothed
        
        return smoothed
    
    def _generate_budget_recommendations(
        self,
        status: BudgetStatus,
        percent_used: float,
        days_remaining: int,
        services: list[str],
    ) -> list[str]:
        """Generate recommendations based on budget status."""
        recommendations = []
        
        if status == BudgetStatus.OVERSPENT:
            recommendations.extend([
                "Review and terminate unused resources immediately",
                "Contact finance to discuss budget increase if spend is justified",
                "Implement cost controls to prevent further overage",
            ])
        elif status == BudgetStatus.CRITICAL:
            recommendations.extend([
                "Review high-cost resources and optimize",
                "Consider implementing spend limits/alerts",
                "Evaluate if current spending rate is sustainable",
            ])
        elif status == BudgetStatus.WARNING:
            recommendations.extend([
                "Monitor spending closely for remainder of period",
                "Review recent cost increases",
                "Plan optimization efforts for next period",
            ])
        else:
            recommendations.extend([
                "Continue monitoring for any unexpected changes",
                "Consider if budget can be reduced",
            ])
        
        if services:
            recommendations.append(f"Focus on services: {', '.join(services[:3])}")
        
        return recommendations
    
    def get_insights(
        self,
        daily_costs: dict[datetime, float],
        budgets: Optional[list[dict]] = None,
    ) -> dict[str, Any]:
        """
        Get comprehensive cost insights.
        
        Returns summary of forecasts, trends, anomalies, and recommendations.
        """
        # Forecast next month
        forecast = self.forecast(daily_costs, 30)
        
        # Analyze trend
        trend, trend_details = self.analyze_spending_trend(daily_costs)
        
        # Detect anomalies
        anomalies = self.detect_anomalies(daily_costs)
        
        insights = {
            "forecast": forecast.to_dict(),
            "trend": {
                "direction": trend.value,
                "details": trend_details,
            },
            "anomalies": [a.to_dict() for a in anomalies],
            "anomaly_count": len(anomalies),
            "recommendations": [],
        }
        
        # Generate recommendations based on insights
        if trend == SpendingTrend.ACCELERATING:
            insights["recommendations"].append(
                "Cost growth is accelerating - review for runaway resources"
            )
        
        if len(anomalies) > 3:
            insights["recommendations"].append(
                f"{len(anomalies)} cost anomalies detected - investigate unusual spending"
            )
        
        if forecast.growth_rate > 0.1:
            insights["recommendations"].append(
                f"Projected {forecast.growth_rate:.0%} monthly growth - plan for budget increase or optimization"
            )
        
        return insights
