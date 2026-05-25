"""
Predictive Analytics for Incidents

Provides predictive capabilities for SRE operations:
- Incident probability prediction
- Resource exhaustion forecasting
- SLO burn rate predictions
- Proactive alerting recommendations
- Risk assessment
"""

import logging
import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Risk levels for predictions."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMAL = "minimal"


class PredictionType(str, Enum):
    """Types of predictions."""
    INCIDENT_PROBABILITY = "incident_probability"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    SLO_BREACH = "slo_breach"
    CAPACITY_NEEDED = "capacity_needed"
    FAILURE_LIKELIHOOD = "failure_likelihood"


@dataclass
class PredictionResult:
    """Result of a prediction."""
    prediction_type: PredictionType
    target: str  # What we're predicting for (service, resource, etc.)
    probability: float  # 0-1
    risk_level: RiskLevel
    time_horizon: str  # e.g., "24 hours", "7 days"
    predicted_time: Optional[datetime]  # When the event might occur
    confidence: float  # 0-1
    contributing_factors: list[str]
    recommended_actions: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "prediction_type": self.prediction_type.value,
            "target": self.target,
            "probability": self.probability,
            "risk_level": self.risk_level.value,
            "time_horizon": self.time_horizon,
            "predicted_time": self.predicted_time.isoformat() if self.predicted_time else None,
            "confidence": self.confidence,
            "contributing_factors": self.contributing_factors,
            "recommended_actions": self.recommended_actions,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }
    
    @property
    def summary(self) -> str:
        """Human-readable summary."""
        action_required = self.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH)
        urgency = "ACTION REQUIRED: " if action_required else ""
        
        return (
            f"{urgency}{self.prediction_type.value.replace('_', ' ').title()} for '{self.target}': "
            f"{self.probability:.0%} probability ({self.risk_level.value} risk) "
            f"within {self.time_horizon}"
        )


@dataclass
class PredictiveInsight:
    """A predictive insight with context and recommendations."""
    insight_id: str
    title: str
    description: str
    severity: RiskLevel
    predictions: list[PredictionResult]
    evidence: list[str]
    impact: str
    recommendations: list[str]
    estimated_cost_of_inaction: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict:
        return {
            "insight_id": self.insight_id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "predictions": [p.to_dict() for p in self.predictions],
            "evidence": self.evidence,
            "impact": self.impact,
            "recommendations": self.recommendations,
            "estimated_cost_of_inaction": self.estimated_cost_of_inaction,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class CapacityForecast:
    """Forecast for resource capacity."""
    resource: str
    current_usage: float
    current_limit: float
    usage_trend: float  # Change per day
    exhaustion_date: Optional[datetime]
    days_until_exhaustion: Optional[float]
    confidence: float
    recommendations: list[str]
    
    def to_dict(self) -> dict:
        return {
            "resource": self.resource,
            "current_usage": self.current_usage,
            "current_limit": self.current_limit,
            "usage_trend": self.usage_trend,
            "exhaustion_date": self.exhaustion_date.isoformat() if self.exhaustion_date else None,
            "days_until_exhaustion": self.days_until_exhaustion,
            "confidence": self.confidence,
            "recommendations": self.recommendations,
        }


@dataclass
class SLOBurnRateAnalysis:
    """SLO burn rate analysis and prediction."""
    slo_name: str
    current_error_budget_remaining: float  # 0-1
    burn_rate: float  # Multiplier vs sustainable rate
    time_to_exhaustion: Optional[timedelta]
    risk_level: RiskLevel
    trend: str  # "increasing", "decreasing", "stable"
    recommendations: list[str]
    
    def to_dict(self) -> dict:
        return {
            "slo_name": self.slo_name,
            "current_error_budget_remaining": self.current_error_budget_remaining,
            "burn_rate": self.burn_rate,
            "time_to_exhaustion_hours": (
                self.time_to_exhaustion.total_seconds() / 3600 
                if self.time_to_exhaustion else None
            ),
            "risk_level": self.risk_level.value,
            "trend": self.trend,
            "recommendations": self.recommendations,
        }


class IncidentPredictor:
    """
    Predicts incidents and provides proactive recommendations.
    
    Uses historical data and patterns to:
    - Estimate incident probability
    - Forecast resource exhaustion
    - Predict SLO breaches
    - Identify emerging risks
    """
    
    def __init__(
        self,
        lookback_days: int = 90,
        confidence_threshold: float = 0.6,
    ):
        self.lookback_days = lookback_days
        self.confidence_threshold = confidence_threshold
    
    def predict_incidents(
        self,
        service: str,
        historical_incidents: list[dict],
        current_metrics: Optional[dict] = None,
        time_horizon_hours: int = 24,
    ) -> PredictionResult:
        """
        Predict probability of incidents for a service.
        
        Args:
            service: Service name
            historical_incidents: Past incidents for this service
            current_metrics: Current metric values (optional)
            time_horizon_hours: Prediction window in hours
            
        Returns:
            PredictionResult with probability and recommendations
        """
        # Calculate base probability from historical data
        base_probability = self._calculate_base_probability(
            historical_incidents, time_horizon_hours
        )
        
        # Adjust based on current metrics
        metric_factor = 1.0
        contributing_factors = []
        
        if current_metrics:
            metric_factor, factors = self._assess_metric_risk(current_metrics)
            contributing_factors.extend(factors)
        
        # Adjust based on recent incident patterns
        pattern_factor, pattern_factors = self._assess_pattern_risk(
            historical_incidents
        )
        contributing_factors.extend(pattern_factors)
        
        # Calculate final probability
        probability = min(1.0, base_probability * metric_factor * pattern_factor)
        
        # Determine risk level
        risk_level = self._probability_to_risk(probability)
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            len(historical_incidents), metric_factor, pattern_factor
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            service, probability, contributing_factors, current_metrics
        )
        
        return PredictionResult(
            prediction_type=PredictionType.INCIDENT_PROBABILITY,
            target=service,
            probability=probability,
            risk_level=risk_level,
            time_horizon=f"{time_horizon_hours} hours",
            predicted_time=None,
            confidence=confidence,
            contributing_factors=contributing_factors,
            recommended_actions=recommendations,
            metadata={
                "base_probability": base_probability,
                "metric_factor": metric_factor,
                "pattern_factor": pattern_factor,
                "incident_count": len(historical_incidents),
            },
        )
    
    def forecast_capacity(
        self,
        resource_name: str,
        usage_history: list[tuple[datetime, float]],
        limit: float,
        forecast_days: int = 30,
    ) -> CapacityForecast:
        """
        Forecast when a resource will be exhausted.
        
        Args:
            resource_name: Name of the resource
            usage_history: List of (timestamp, usage_value) tuples
            limit: Resource limit/capacity
            forecast_days: Days to forecast ahead
            
        Returns:
            CapacityForecast with exhaustion prediction
        """
        if len(usage_history) < 3:
            return CapacityForecast(
                resource=resource_name,
                current_usage=usage_history[-1][1] if usage_history else 0,
                current_limit=limit,
                usage_trend=0,
                exhaustion_date=None,
                days_until_exhaustion=None,
                confidence=0.0,
                recommendations=["Insufficient data for forecast"],
            )
        
        # Sort by timestamp
        sorted_history = sorted(usage_history, key=lambda x: x[0])
        
        # Calculate trend (usage change per day)
        values = [v for _, v in sorted_history]
        timestamps = [ts for ts, _ in sorted_history]
        
        # Simple linear regression
        n = len(values)
        days = [(ts - timestamps[0]).total_seconds() / 86400 for ts in timestamps]
        
        x_mean = sum(days) / n
        y_mean = sum(values) / n
        
        numerator = sum((d - x_mean) * (v - y_mean) for d, v in zip(days, values))
        denominator = sum((d - x_mean) ** 2 for d in days)
        
        trend = numerator / denominator if denominator > 0 else 0
        
        current_usage = values[-1]
        
        # Calculate days until exhaustion
        if trend > 0 and current_usage < limit:
            days_until = (limit - current_usage) / trend
            exhaustion_date = datetime.now(timezone.utc) + timedelta(days=days_until)
        else:
            days_until = None
            exhaustion_date = None
        
        # Calculate confidence based on data quality
        confidence = self._calculate_forecast_confidence(values, trend)
        
        # Generate recommendations
        recommendations = self._generate_capacity_recommendations(
            resource_name, current_usage, limit, trend, days_until
        )
        
        return CapacityForecast(
            resource=resource_name,
            current_usage=current_usage,
            current_limit=limit,
            usage_trend=trend,
            exhaustion_date=exhaustion_date,
            days_until_exhaustion=days_until,
            confidence=confidence,
            recommendations=recommendations,
        )
    
    def analyze_slo_burn_rate(
        self,
        slo_name: str,
        error_budget_total: float,
        error_budget_consumed: float,
        window_hours: float = 24,
        recent_errors: Optional[list[dict]] = None,
    ) -> SLOBurnRateAnalysis:
        """
        Analyze SLO burn rate and predict budget exhaustion.
        
        Args:
            slo_name: Name of the SLO
            error_budget_total: Total error budget for the period
            error_budget_consumed: Error budget consumed so far
            window_hours: Time window for analysis
            recent_errors: Recent error events
            
        Returns:
            SLOBurnRateAnalysis with predictions
        """
        remaining = max(0, error_budget_total - error_budget_consumed)
        remaining_pct = remaining / error_budget_total if error_budget_total > 0 else 0
        
        # Calculate burn rate
        # Sustainable rate = consuming 100% over full period (30 days typically)
        period_hours = 30 * 24  # Assume 30-day period
        sustainable_rate = 1.0  # 1x = consuming exactly budget over period
        
        elapsed_pct = window_hours / period_hours
        consumed_pct = error_budget_consumed / error_budget_total if error_budget_total > 0 else 0
        
        if elapsed_pct > 0:
            burn_rate = consumed_pct / elapsed_pct
        else:
            burn_rate = 0
        
        # Estimate time to exhaustion
        if burn_rate > 0 and remaining > 0:
            hours_to_exhaustion = (remaining / error_budget_total) * period_hours / burn_rate
            time_to_exhaustion = timedelta(hours=hours_to_exhaustion)
        else:
            time_to_exhaustion = None
        
        # Determine risk level
        if burn_rate > 10:
            risk_level = RiskLevel.CRITICAL
        elif burn_rate > 5:
            risk_level = RiskLevel.HIGH
        elif burn_rate > 2:
            risk_level = RiskLevel.MEDIUM
        elif burn_rate > 1:
            risk_level = RiskLevel.LOW
        else:
            risk_level = RiskLevel.MINIMAL
        
        # Determine trend
        if recent_errors:
            # Compare recent error rate to earlier
            half = len(recent_errors) // 2
            earlier = len(recent_errors[:half])
            later = len(recent_errors[half:])
            if later > earlier * 1.2:
                trend = "increasing"
            elif later < earlier * 0.8:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "unknown"
        
        # Generate recommendations
        recommendations = self._generate_slo_recommendations(
            slo_name, burn_rate, remaining_pct, trend
        )
        
        return SLOBurnRateAnalysis(
            slo_name=slo_name,
            current_error_budget_remaining=remaining_pct,
            burn_rate=burn_rate,
            time_to_exhaustion=time_to_exhaustion,
            risk_level=risk_level,
            trend=trend,
            recommendations=recommendations,
        )
    
    def generate_insights(
        self,
        services: list[str],
        incidents: list[dict],
        metrics: dict[str, dict],
        slo_data: Optional[dict] = None,
    ) -> list[PredictiveInsight]:
        """
        Generate comprehensive predictive insights.
        
        Args:
            services: List of services to analyze
            incidents: Historical incidents
            metrics: Current metrics per service
            slo_data: SLO configuration and data
            
        Returns:
            List of PredictiveInsight objects
        """
        insights = []
        
        # Analyze each service
        for service in services:
            service_incidents = [
                i for i in incidents
                if i.get("service") == service
            ]
            service_metrics = metrics.get(service, {})
            
            # Predict incidents
            prediction = self.predict_incidents(
                service, service_incidents, service_metrics
            )
            
            if prediction.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH):
                insight = PredictiveInsight(
                    insight_id=f"incident_risk_{service}",
                    title=f"High Incident Risk: {service}",
                    description=(
                        f"Service '{service}' has a {prediction.probability:.0%} probability "
                        f"of experiencing an incident in the next {prediction.time_horizon}."
                    ),
                    severity=prediction.risk_level,
                    predictions=[prediction],
                    evidence=prediction.contributing_factors,
                    impact=f"Potential service degradation or outage for {service}",
                    recommendations=prediction.recommended_actions,
                    estimated_cost_of_inaction=self._estimate_incident_cost(
                        service, prediction.probability
                    ),
                )
                insights.append(insight)
        
        # Analyze SLOs if provided
        if slo_data:
            for slo_name, data in slo_data.items():
                analysis = self.analyze_slo_burn_rate(
                    slo_name,
                    data.get("budget_total", 1.0),
                    data.get("budget_consumed", 0),
                    data.get("window_hours", 24),
                )
                
                if analysis.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH):
                    insight = PredictiveInsight(
                        insight_id=f"slo_risk_{slo_name}",
                        title=f"SLO at Risk: {slo_name}",
                        description=(
                            f"SLO '{slo_name}' is burning error budget at {analysis.burn_rate:.1f}x "
                            f"sustainable rate. {analysis.current_error_budget_remaining:.0%} budget remaining."
                        ),
                        severity=analysis.risk_level,
                        predictions=[],
                        evidence=[
                            f"Burn rate: {analysis.burn_rate:.1f}x",
                            f"Trend: {analysis.trend}",
                            f"Budget remaining: {analysis.current_error_budget_remaining:.0%}",
                        ],
                        impact="SLO breach could affect customer commitments",
                        recommendations=analysis.recommendations,
                    )
                    insights.append(insight)
        
        # Sort by severity
        severity_order = {
            RiskLevel.CRITICAL: 0,
            RiskLevel.HIGH: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.LOW: 3,
            RiskLevel.MINIMAL: 4,
        }
        insights.sort(key=lambda i: severity_order.get(i.severity, 5))
        
        return insights
    
    def _calculate_base_probability(
        self,
        incidents: list[dict],
        time_horizon_hours: int,
    ) -> float:
        """Calculate base probability from historical incident rate."""
        if not incidents:
            return 0.05  # Low default probability
        
        # Get timestamps
        timestamps = []
        for incident in incidents:
            ts = incident.get("timestamp") or incident.get("created_at")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if ts:
                timestamps.append(ts)
        
        if not timestamps:
            return 0.05
        
        # Calculate incident rate
        timestamps.sort()
        span_hours = max(1, (timestamps[-1] - timestamps[0]).total_seconds() / 3600)
        incident_rate = len(timestamps) / span_hours  # Incidents per hour
        
        # Probability of at least one incident in time horizon
        # Using Poisson: P(X >= 1) = 1 - e^(-lambda)
        expected_incidents = incident_rate * time_horizon_hours
        probability = 1 - math.exp(-expected_incidents)
        
        return min(0.95, probability)  # Cap at 95%
    
    def _assess_metric_risk(
        self,
        metrics: dict,
    ) -> tuple[float, list[str]]:
        """Assess risk from current metrics."""
        factor = 1.0
        factors = []
        
        # CPU risk
        cpu = metrics.get("cpu_percent") or metrics.get("cpu")
        if cpu and cpu > 80:
            factor *= 1.5
            factors.append(f"High CPU usage ({cpu:.1f}%)")
        elif cpu and cpu > 60:
            factor *= 1.2
            factors.append(f"Elevated CPU usage ({cpu:.1f}%)")
        
        # Memory risk
        memory = metrics.get("memory_percent") or metrics.get("memory")
        if memory and memory > 85:
            factor *= 1.6
            factors.append(f"High memory usage ({memory:.1f}%)")
        elif memory and memory > 70:
            factor *= 1.2
            factors.append(f"Elevated memory usage ({memory:.1f}%)")
        
        # Error rate risk
        error_rate = metrics.get("error_rate")
        if error_rate and error_rate > 0.05:
            factor *= 2.0
            factors.append(f"Elevated error rate ({error_rate:.1%})")
        elif error_rate and error_rate > 0.01:
            factor *= 1.3
            factors.append(f"Slightly elevated error rate ({error_rate:.1%})")
        
        # Latency risk
        latency_p99 = metrics.get("latency_p99") or metrics.get("latency")
        latency_threshold = metrics.get("latency_threshold", 1000)  # Default 1s
        if latency_p99 and latency_p99 > latency_threshold:
            factor *= 1.5
            factors.append(f"High latency ({latency_p99:.0f}ms)")
        
        # Recent deployments
        recent_deploy = metrics.get("recent_deployment") or metrics.get("deployed_recently")
        if recent_deploy:
            factor *= 1.4
            factors.append("Recent deployment increases risk")
        
        return factor, factors
    
    def _assess_pattern_risk(
        self,
        incidents: list[dict],
    ) -> tuple[float, list[str]]:
        """Assess risk from incident patterns."""
        factor = 1.0
        factors = []
        
        if not incidents:
            return factor, factors
        
        # Recent incident acceleration
        now = datetime.now(timezone.utc)
        last_7_days = [
            i for i in incidents
            if self._parse_timestamp(i) and (now - self._parse_timestamp(i)).days <= 7
        ]
        prev_7_days = [
            i for i in incidents
            if self._parse_timestamp(i) and 7 < (now - self._parse_timestamp(i)).days <= 14
        ]
        
        if len(last_7_days) > len(prev_7_days) * 1.5 and last_7_days:
            factor *= 1.4
            factors.append("Incident rate is accelerating")
        
        # Recurring incidents
        alert_names = [
            i.get("alert_name") or i.get("name", "")
            for i in last_7_days
        ]
        for name in set(alert_names):
            if alert_names.count(name) >= 3:
                factor *= 1.3
                factors.append(f"Recurring incident pattern: {name}")
                break
        
        return factor, factors
    
    def _parse_timestamp(self, incident: dict) -> Optional[datetime]:
        """Parse timestamp from incident."""
        ts = incident.get("timestamp") or incident.get("created_at")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return ts
    
    def _probability_to_risk(self, probability: float) -> RiskLevel:
        """Convert probability to risk level."""
        if probability >= 0.8:
            return RiskLevel.CRITICAL
        elif probability >= 0.6:
            return RiskLevel.HIGH
        elif probability >= 0.4:
            return RiskLevel.MEDIUM
        elif probability >= 0.2:
            return RiskLevel.LOW
        else:
            return RiskLevel.MINIMAL
    
    def _calculate_confidence(
        self,
        incident_count: int,
        metric_factor: float,
        pattern_factor: float,
    ) -> float:
        """Calculate confidence in prediction."""
        # More data = higher confidence
        data_confidence = min(0.4, incident_count * 0.02)
        
        # Factor adjustments indicate clear signals
        factor_confidence = 0.3 if metric_factor != 1.0 or pattern_factor != 1.0 else 0.2
        
        # Base confidence
        base = 0.3
        
        return min(0.95, base + data_confidence + factor_confidence)
    
    def _generate_recommendations(
        self,
        service: str,
        probability: float,
        factors: list[str],
        metrics: Optional[dict],
    ) -> list[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        if probability >= 0.6:
            recommendations.append(
                f"Consider proactive investigation of {service}"
            )
        
        if any("CPU" in f for f in factors):
            recommendations.append("Review CPU-intensive operations and consider scaling")
        
        if any("memory" in f.lower() for f in factors):
            recommendations.append("Check for memory leaks and optimize memory usage")
        
        if any("error rate" in f.lower() for f in factors):
            recommendations.append("Investigate recent error patterns in logs")
        
        if any("latency" in f.lower() for f in factors):
            recommendations.append("Review slow queries and optimize hot paths")
        
        if any("deployment" in f.lower() for f in factors):
            recommendations.append("Ensure rollback procedure is ready")
        
        if any("recurring" in f.lower() for f in factors):
            recommendations.append("Address root cause of recurring incidents")
        
        if not recommendations:
            recommendations.append("Continue monitoring and maintain current practices")
        
        return recommendations
    
    def _calculate_forecast_confidence(
        self,
        values: list[float],
        trend: float,
    ) -> float:
        """Calculate confidence in capacity forecast."""
        if len(values) < 5:
            return 0.3
        
        # Calculate R-squared of trend
        mean_value = statistics.mean(values)
        ss_tot = sum((v - mean_value) ** 2 for v in values)
        
        if ss_tot == 0:
            return 0.5
        
        # Estimate residuals
        predicted = [mean_value + trend * i for i in range(len(values))]
        ss_res = sum((v - p) ** 2 for v, p in zip(values, predicted))
        
        r_squared = 1 - (ss_res / ss_tot)
        
        # Combine with data quantity factor
        data_factor = min(0.3, len(values) * 0.01)
        
        return min(0.9, max(0.3, r_squared * 0.7 + data_factor))
    
    def _generate_capacity_recommendations(
        self,
        resource: str,
        current: float,
        limit: float,
        trend: float,
        days_until: Optional[float],
    ) -> list[str]:
        """Generate capacity recommendations."""
        recommendations = []
        utilization = current / limit if limit > 0 else 0
        
        if days_until is not None and days_until < 7:
            recommendations.append(
                f"URGENT: {resource} will be exhausted in ~{days_until:.1f} days"
            )
            recommendations.append("Immediately provision additional capacity")
        elif days_until is not None and days_until < 30:
            recommendations.append(
                f"Plan capacity expansion for {resource} within {days_until:.0f} days"
            )
        
        if utilization > 0.8:
            recommendations.append(f"Current {resource} utilization is high ({utilization:.0%})")
        
        if trend > 0:
            recommendations.append(
                f"{resource} usage is growing at {trend:.2f}/day"
            )
        elif trend < 0:
            recommendations.append(
                f"{resource} usage is decreasing - review for optimization opportunities"
            )
        
        if not recommendations:
            recommendations.append(f"{resource} capacity is healthy")
        
        return recommendations
    
    def _generate_slo_recommendations(
        self,
        slo_name: str,
        burn_rate: float,
        remaining_pct: float,
        trend: str,
    ) -> list[str]:
        """Generate SLO-specific recommendations."""
        recommendations = []
        
        if burn_rate > 10:
            recommendations.append(
                f"CRITICAL: {slo_name} is burning budget at {burn_rate:.0f}x rate"
            )
            recommendations.append("Immediately investigate and mitigate errors")
            recommendations.append("Consider feature flags or traffic reduction")
        elif burn_rate > 5:
            recommendations.append(
                f"HIGH PRIORITY: {slo_name} burn rate of {burn_rate:.1f}x needs attention"
            )
            recommendations.append("Identify top error contributors")
        elif burn_rate > 2:
            recommendations.append(
                f"Monitor {slo_name} closely - burn rate is {burn_rate:.1f}x"
            )
        
        if remaining_pct < 0.1:
            recommendations.append("Less than 10% error budget remaining")
            recommendations.append("Consider freezing non-critical changes")
        
        if trend == "increasing":
            recommendations.append("Error rate is increasing - investigate recent changes")
        elif trend == "decreasing":
            recommendations.append("Error rate is improving - current mitigations working")
        
        return recommendations
    
    def _estimate_incident_cost(
        self,
        service: str,
        probability: float,
    ) -> str:
        """Estimate cost of not acting on prediction."""
        # This is a simplified estimation
        # In practice, this would use business metrics
        
        base_cost = "Unknown"
        
        if probability >= 0.8:
            base_cost = "High - likely outage with customer impact"
        elif probability >= 0.6:
            base_cost = "Medium - potential service degradation"
        elif probability >= 0.4:
            base_cost = "Low to Medium - possible minor issues"
        else:
            base_cost = "Low - minimal expected impact"
        
        return base_cost
