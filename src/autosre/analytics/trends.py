"""
Trend Analysis for Incidents

Analyzes incident data to identify trends over time including:
- Incident frequency trends (increasing, decreasing, stable)
- Seasonal patterns (time-of-day, day-of-week, monthly)
- Service-specific trends
- MTTR/MTTD trends
- Alert fatigue indicators
"""

import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TrendDirection(str, Enum):
    """Direction of a trend."""
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"


class SeasonalPattern(str, Enum):
    """Type of seasonal pattern detected."""
    HOURLY = "hourly"          # Peaks at certain hours
    DAILY = "daily"            # Peaks on certain days
    WEEKLY = "weekly"          # Weekly cycles
    MONTHLY = "monthly"        # Monthly cycles
    NONE = "none"              # No seasonal pattern


@dataclass
class TrendDataPoint:
    """A single data point in a trend series."""
    timestamp: datetime
    value: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TrendResult:
    """Result of a trend analysis."""
    metric_name: str
    direction: TrendDirection
    slope: float  # Rate of change per day
    confidence: float  # 0-1, how confident we are in the trend
    period_start: datetime
    period_end: datetime
    data_points: list[TrendDataPoint]
    baseline: float  # Average value at start of period
    current: float  # Average value at end of period
    percent_change: float
    seasonal_pattern: SeasonalPattern = SeasonalPattern.NONE
    seasonal_peaks: list[str] = field(default_factory=list)
    anomalies: list[TrendDataPoint] = field(default_factory=list)
    forecast_next_week: Optional[float] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "metric_name": self.metric_name,
            "direction": self.direction.value,
            "slope": self.slope,
            "confidence": self.confidence,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "data_points_count": len(self.data_points),
            "baseline": self.baseline,
            "current": self.current,
            "percent_change": self.percent_change,
            "seasonal_pattern": self.seasonal_pattern.value,
            "seasonal_peaks": self.seasonal_peaks,
            "anomalies_count": len(self.anomalies),
            "forecast_next_week": self.forecast_next_week,
        }
    
    @property
    def summary(self) -> str:
        """Human-readable summary of the trend."""
        direction_text = {
            TrendDirection.INCREASING: "increasing",
            TrendDirection.DECREASING: "decreasing",
            TrendDirection.STABLE: "stable",
            TrendDirection.VOLATILE: "volatile",
            TrendDirection.UNKNOWN: "unclear",
        }
        
        summary = f"{self.metric_name} is {direction_text[self.direction]}"
        
        if self.direction in (TrendDirection.INCREASING, TrendDirection.DECREASING):
            summary += f" ({self.percent_change:+.1f}% over period)"
        
        if self.seasonal_pattern != SeasonalPattern.NONE:
            summary += f", with {self.seasonal_pattern.value} seasonality"
            if self.seasonal_peaks:
                summary += f" (peaks: {', '.join(self.seasonal_peaks[:3])})"
        
        if self.anomalies:
            summary += f", {len(self.anomalies)} anomalies detected"
        
        return summary


@dataclass
class IncidentTrendSummary:
    """Summary of incident trends across multiple dimensions."""
    period: str  # e.g., "7 days", "30 days"
    total_incidents: int
    incident_trend: TrendResult
    mttr_trend: TrendResult
    mttd_trend: TrendResult
    severity_breakdown: dict[str, int]
    top_services: list[tuple[str, int]]
    alert_fatigue_score: float  # 0-1, higher = more fatigue
    recommendations: list[str]
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "period": self.period,
            "total_incidents": self.total_incidents,
            "incident_trend": self.incident_trend.to_dict(),
            "mttr_trend": self.mttr_trend.to_dict(),
            "mttd_trend": self.mttd_trend.to_dict(),
            "severity_breakdown": self.severity_breakdown,
            "top_services": self.top_services,
            "alert_fatigue_score": self.alert_fatigue_score,
            "recommendations": self.recommendations,
        }


class TrendAnalyzer:
    """
    Analyzes trends in incident and alert data.
    
    Uses statistical methods to identify:
    - Directional trends (increasing/decreasing)
    - Seasonal patterns
    - Anomalies and outliers
    - Forecasts
    """
    
    def __init__(
        self,
        min_data_points: int = 7,
        anomaly_threshold: float = 2.0,  # Standard deviations
    ):
        self.min_data_points = min_data_points
        self.anomaly_threshold = anomaly_threshold
    
    def analyze_time_series(
        self,
        data: list[TrendDataPoint],
        metric_name: str = "metric",
    ) -> TrendResult:
        """
        Analyze a time series for trends.
        
        Args:
            data: List of data points with timestamps and values
            metric_name: Name of the metric being analyzed
            
        Returns:
            TrendResult with direction, confidence, and other insights
        """
        if len(data) < self.min_data_points:
            return self._insufficient_data_result(data, metric_name)
        
        # Sort by timestamp
        sorted_data = sorted(data, key=lambda x: x.timestamp)
        
        # Extract values
        values = [d.value for d in sorted_data]
        timestamps = [d.timestamp for d in sorted_data]
        
        # Calculate basic statistics
        mean_value = statistics.mean(values)
        std_dev = statistics.stdev(values) if len(values) > 1 else 0
        
        # Split into first and last thirds for trend detection
        third = max(1, len(values) // 3)
        first_third = values[:third]
        last_third = values[-third:]
        
        baseline = statistics.mean(first_third)
        current = statistics.mean(last_third)
        
        # Calculate percent change
        if baseline > 0:
            percent_change = ((current - baseline) / baseline) * 100
        else:
            percent_change = 100 if current > 0 else 0
        
        # Calculate slope using linear regression
        slope = self._calculate_slope(sorted_data)
        
        # Determine direction and confidence
        direction, confidence = self._determine_direction(
            values, slope, std_dev, percent_change
        )
        
        # Detect seasonal patterns
        seasonal_pattern, seasonal_peaks = self._detect_seasonality(sorted_data)
        
        # Detect anomalies
        anomalies = self._detect_anomalies(sorted_data, mean_value, std_dev)
        
        # Forecast
        forecast = self._simple_forecast(values, slope)
        
        return TrendResult(
            metric_name=metric_name,
            direction=direction,
            slope=slope,
            confidence=confidence,
            period_start=timestamps[0],
            period_end=timestamps[-1],
            data_points=sorted_data,
            baseline=baseline,
            current=current,
            percent_change=percent_change,
            seasonal_pattern=seasonal_pattern,
            seasonal_peaks=seasonal_peaks,
            anomalies=anomalies,
            forecast_next_week=forecast,
        )
    
    def analyze_incidents(
        self,
        incidents: list[dict],
        period_days: int = 30,
    ) -> IncidentTrendSummary:
        """
        Analyze incident trends comprehensively.
        
        Args:
            incidents: List of incident dictionaries with at minimum:
                       - timestamp (or created_at)
                       - severity
                       - service (optional)
                       - ttd (time to detect, optional)
                       - ttr (time to resolve, optional)
            period_days: Number of days to analyze
            
        Returns:
            IncidentTrendSummary with comprehensive analysis
        """
        if not incidents:
            return self._empty_incident_summary(period_days)
        
        # Group incidents by day
        daily_counts = self._group_by_day(incidents, period_days)
        
        # Create data points for incident count trend
        incident_data = [
            TrendDataPoint(timestamp=day, value=count)
            for day, count in daily_counts.items()
        ]
        incident_trend = self.analyze_time_series(
            incident_data, "incident_count"
        )
        
        # Analyze MTTR trend
        mttr_data = self._extract_mttr_data(incidents, period_days)
        mttr_trend = self.analyze_time_series(mttr_data, "mttr_minutes")
        
        # Analyze MTTD trend
        mttd_data = self._extract_mttd_data(incidents, period_days)
        mttd_trend = self.analyze_time_series(mttd_data, "mttd_minutes")
        
        # Calculate severity breakdown
        severity_breakdown = self._severity_breakdown(incidents)
        
        # Get top services
        top_services = self._top_services(incidents, limit=5)
        
        # Calculate alert fatigue score
        alert_fatigue = self._calculate_alert_fatigue(incidents)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            incident_trend, mttr_trend, mttd_trend, alert_fatigue
        )
        
        return IncidentTrendSummary(
            period=f"{period_days} days",
            total_incidents=len(incidents),
            incident_trend=incident_trend,
            mttr_trend=mttr_trend,
            mttd_trend=mttd_trend,
            severity_breakdown=severity_breakdown,
            top_services=top_services,
            alert_fatigue_score=alert_fatigue,
            recommendations=recommendations,
        )
    
    def detect_change_points(
        self,
        data: list[TrendDataPoint],
        sensitivity: float = 0.1,
    ) -> list[datetime]:
        """
        Detect significant change points in the data.
        
        Returns timestamps where significant changes occurred.
        """
        if len(data) < 5:
            return []
        
        sorted_data = sorted(data, key=lambda x: x.timestamp)
        values = [d.value for d in sorted_data]
        
        change_points = []
        window_size = max(3, len(values) // 10)
        
        for i in range(window_size, len(values) - window_size):
            before = values[i - window_size:i]
            after = values[i:i + window_size]
            
            before_mean = statistics.mean(before)
            after_mean = statistics.mean(after)
            
            # Check for significant change
            if before_mean > 0:
                change_ratio = abs(after_mean - before_mean) / before_mean
                if change_ratio > sensitivity:
                    change_points.append(sorted_data[i].timestamp)
        
        return change_points
    
    def compare_periods(
        self,
        current_data: list[TrendDataPoint],
        previous_data: list[TrendDataPoint],
        metric_name: str = "metric",
    ) -> dict[str, Any]:
        """
        Compare two time periods (e.g., this week vs last week).
        """
        current_values = [d.value for d in current_data]
        previous_values = [d.value for d in previous_data]
        
        current_avg = statistics.mean(current_values) if current_values else 0
        previous_avg = statistics.mean(previous_values) if previous_values else 0
        
        if previous_avg > 0:
            percent_change = ((current_avg - previous_avg) / previous_avg) * 100
        else:
            percent_change = 100 if current_avg > 0 else 0
        
        return {
            "metric_name": metric_name,
            "current_period": {
                "count": len(current_data),
                "average": current_avg,
                "total": sum(current_values),
                "min": min(current_values) if current_values else 0,
                "max": max(current_values) if current_values else 0,
            },
            "previous_period": {
                "count": len(previous_data),
                "average": previous_avg,
                "total": sum(previous_values),
                "min": min(previous_values) if previous_values else 0,
                "max": max(previous_values) if previous_values else 0,
            },
            "percent_change": percent_change,
            "improved": percent_change < 0 if metric_name in ["incidents", "errors", "mttr"] else percent_change > 0,
        }
    
    def _calculate_slope(self, data: list[TrendDataPoint]) -> float:
        """Calculate slope using simple linear regression."""
        if len(data) < 2:
            return 0.0
        
        n = len(data)
        # Use day indices as x values
        x_values = list(range(n))
        y_values = [d.value for d in data]
        
        x_mean = statistics.mean(x_values)
        y_mean = statistics.mean(y_values)
        
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values))
        denominator = sum((x - x_mean) ** 2 for x in x_values)
        
        if denominator == 0:
            return 0.0
        
        return numerator / denominator
    
    def _determine_direction(
        self,
        values: list[float],
        slope: float,
        std_dev: float,
        percent_change: float,
    ) -> tuple[TrendDirection, float]:
        """Determine trend direction and confidence."""
        if not values or std_dev == 0:
            return TrendDirection.STABLE, 0.5
        
        # Calculate coefficient of variation (volatility)
        mean_value = statistics.mean(values)
        cv = std_dev / mean_value if mean_value > 0 else 0
        
        # High volatility = volatile trend
        if cv > 0.5:
            return TrendDirection.VOLATILE, 0.7
        
        # Determine direction based on slope and percent change
        slope_threshold = std_dev * 0.1  # Slope needs to be significant
        
        if abs(slope) < slope_threshold and abs(percent_change) < 10:
            confidence = 1 - (abs(percent_change) / 10)
            return TrendDirection.STABLE, max(0.5, confidence)
        
        if slope > slope_threshold or percent_change > 10:
            confidence = min(1.0, abs(percent_change) / 50 + 0.5)
            return TrendDirection.INCREASING, confidence
        
        if slope < -slope_threshold or percent_change < -10:
            confidence = min(1.0, abs(percent_change) / 50 + 0.5)
            return TrendDirection.DECREASING, confidence
        
        return TrendDirection.STABLE, 0.6
    
    def _detect_seasonality(
        self,
        data: list[TrendDataPoint],
    ) -> tuple[SeasonalPattern, list[str]]:
        """Detect seasonal patterns in the data."""
        if len(data) < 14:  # Need at least 2 weeks
            return SeasonalPattern.NONE, []
        
        # Group by day of week
        dow_values: dict[int, list[float]] = {i: [] for i in range(7)}
        for point in data:
            dow = point.timestamp.weekday()
            dow_values[dow].append(point.value)
        
        # Calculate average per day of week
        dow_avg = {
            dow: statistics.mean(vals) if vals else 0
            for dow, vals in dow_values.items()
        }
        
        overall_avg = statistics.mean([v for vals in dow_values.values() for v in vals])
        
        # Check for weekly pattern
        if overall_avg > 0:
            max_deviation = max(abs(avg - overall_avg) / overall_avg for avg in dow_avg.values())
            if max_deviation > 0.3:  # 30% deviation indicates pattern
                # Find peak days
                day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                peaks = [
                    day_names[dow] for dow, avg in dow_avg.items()
                    if avg > overall_avg * 1.2
                ]
                return SeasonalPattern.WEEKLY, peaks
        
        # Group by hour (if we have hourly data)
        hour_values: dict[int, list[float]] = {i: [] for i in range(24)}
        for point in data:
            hour = point.timestamp.hour
            hour_values[hour].append(point.value)
        
        # Check for hourly pattern
        hour_avg = {
            hour: statistics.mean(vals) if vals else 0
            for hour, vals in hour_values.items()
        }
        
        if overall_avg > 0:
            max_deviation = max(abs(avg - overall_avg) / overall_avg for avg in hour_avg.values() if hour_values)
            if max_deviation > 0.5:  # 50% deviation indicates pattern
                peaks = [
                    f"{hour:02d}:00" for hour, avg in hour_avg.items()
                    if avg > overall_avg * 1.3
                ]
                return SeasonalPattern.HOURLY, peaks[:5]  # Top 5 peak hours
        
        return SeasonalPattern.NONE, []
    
    def _detect_anomalies(
        self,
        data: list[TrendDataPoint],
        mean_value: float,
        std_dev: float,
    ) -> list[TrendDataPoint]:
        """Detect anomalies (outliers) in the data."""
        if std_dev == 0:
            return []
        
        threshold = self.anomaly_threshold * std_dev
        anomalies = [
            point for point in data
            if abs(point.value - mean_value) > threshold
        ]
        return anomalies
    
    def _simple_forecast(
        self,
        values: list[float],
        slope: float,
        days_ahead: int = 7,
    ) -> Optional[float]:
        """Simple linear forecast."""
        if not values:
            return None
        
        current = values[-1]
        forecast = current + (slope * days_ahead)
        return max(0, forecast)  # Don't forecast negative values
    
    def _insufficient_data_result(
        self,
        data: list[TrendDataPoint],
        metric_name: str,
    ) -> TrendResult:
        """Return result when insufficient data."""
        now = datetime.now(timezone.utc)
        return TrendResult(
            metric_name=metric_name,
            direction=TrendDirection.UNKNOWN,
            slope=0,
            confidence=0,
            period_start=now - timedelta(days=7),
            period_end=now,
            data_points=data,
            baseline=0,
            current=0,
            percent_change=0,
        )
    
    def _group_by_day(
        self,
        incidents: list[dict],
        period_days: int,
    ) -> dict[datetime, int]:
        """Group incidents by day."""
        end_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = end_date - timedelta(days=period_days)
        
        # Initialize all days with 0
        daily_counts = {
            start_date + timedelta(days=i): 0
            for i in range(period_days + 1)
        }
        
        for incident in incidents:
            timestamp = incident.get("timestamp") or incident.get("created_at")
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            
            if timestamp:
                day = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
                if day in daily_counts:
                    daily_counts[day] += 1
        
        return daily_counts
    
    def _extract_mttr_data(
        self,
        incidents: list[dict],
        period_days: int,
    ) -> list[TrendDataPoint]:
        """Extract MTTR data points from incidents."""
        data = []
        for incident in incidents:
            ttr = incident.get("ttr") or incident.get("time_to_resolve")
            timestamp = incident.get("timestamp") or incident.get("created_at")
            
            if ttr is not None and timestamp:
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                data.append(TrendDataPoint(timestamp=timestamp, value=float(ttr)))
        
        return data
    
    def _extract_mttd_data(
        self,
        incidents: list[dict],
        period_days: int,
    ) -> list[TrendDataPoint]:
        """Extract MTTD data points from incidents."""
        data = []
        for incident in incidents:
            ttd = incident.get("ttd") or incident.get("time_to_detect")
            timestamp = incident.get("timestamp") or incident.get("created_at")
            
            if ttd is not None and timestamp:
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                data.append(TrendDataPoint(timestamp=timestamp, value=float(ttd)))
        
        return data
    
    def _severity_breakdown(self, incidents: list[dict]) -> dict[str, int]:
        """Get breakdown by severity."""
        breakdown: dict[str, int] = {}
        for incident in incidents:
            severity = incident.get("severity", "unknown")
            breakdown[severity] = breakdown.get(severity, 0) + 1
        return breakdown
    
    def _top_services(
        self,
        incidents: list[dict],
        limit: int = 5,
    ) -> list[tuple[str, int]]:
        """Get top services by incident count."""
        service_counts: dict[str, int] = {}
        for incident in incidents:
            service = incident.get("service", "unknown")
            service_counts[service] = service_counts.get(service, 0) + 1
        
        sorted_services = sorted(
            service_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return sorted_services[:limit]
    
    def _calculate_alert_fatigue(self, incidents: list[dict]) -> float:
        """
        Calculate alert fatigue score.
        
        Higher score (closer to 1.0) indicates more fatigue.
        """
        if not incidents:
            return 0.0
        
        # Factors contributing to alert fatigue:
        # 1. High volume of low-severity incidents
        # 2. Repeated incidents for same service
        # 3. Short interval between incidents
        
        severity_weights = {
            "critical": 0.1,
            "high": 0.3,
            "medium": 0.6,
            "low": 0.9,
            "info": 1.0,
        }
        
        fatigue_score = 0.0
        
        # Volume component
        daily_rate = len(incidents) / 30  # Assuming 30 days
        volume_fatigue = min(1.0, daily_rate / 20)  # 20+ incidents/day = max fatigue
        
        # Severity component
        severity_scores = [
            severity_weights.get(i.get("severity", "medium"), 0.6)
            for i in incidents
        ]
        severity_fatigue = statistics.mean(severity_scores) if severity_scores else 0.5
        
        # Repetition component
        services = [i.get("service", "unknown") for i in incidents]
        unique_ratio = len(set(services)) / len(services) if services else 1
        repetition_fatigue = 1 - unique_ratio
        
        # Combine factors
        fatigue_score = (
            volume_fatigue * 0.4 +
            severity_fatigue * 0.3 +
            repetition_fatigue * 0.3
        )
        
        return round(min(1.0, fatigue_score), 3)
    
    def _generate_recommendations(
        self,
        incident_trend: TrendResult,
        mttr_trend: TrendResult,
        mttd_trend: TrendResult,
        alert_fatigue: float,
    ) -> list[str]:
        """Generate recommendations based on trends."""
        recommendations = []
        
        # Incident volume recommendations
        if incident_trend.direction == TrendDirection.INCREASING:
            recommendations.append(
                f"Incident volume is increasing ({incident_trend.percent_change:+.1f}%). "
                "Consider reviewing recent changes and identifying root causes."
            )
        
        # MTTR recommendations
        if mttr_trend.direction == TrendDirection.INCREASING:
            recommendations.append(
                "Time to resolve is increasing. Consider improving runbooks, "
                "adding automation, or conducting incident response training."
            )
        elif mttr_trend.direction == TrendDirection.DECREASING:
            recommendations.append(
                "MTTR is improving. Document what's working well and share best practices."
            )
        
        # MTTD recommendations
        if mttd_trend.direction == TrendDirection.INCREASING:
            recommendations.append(
                "Time to detect is increasing. Review alerting thresholds "
                "and monitoring coverage."
            )
        
        # Alert fatigue recommendations
        if alert_fatigue > 0.7:
            recommendations.append(
                f"Alert fatigue score is high ({alert_fatigue:.0%}). "
                "Consider tuning alert thresholds, consolidating alerts, "
                "or implementing alert grouping."
            )
        elif alert_fatigue > 0.5:
            recommendations.append(
                "Moderate alert fatigue detected. Review low-severity alerts "
                "for potential noise reduction."
            )
        
        # Seasonal recommendations
        if incident_trend.seasonal_pattern != SeasonalPattern.NONE:
            peaks = ", ".join(incident_trend.seasonal_peaks[:3])
            recommendations.append(
                f"Incidents show {incident_trend.seasonal_pattern.value} patterns "
                f"(peaks: {peaks}). Consider adjusting staffing or change freeze windows."
            )
        
        return recommendations
    
    def _empty_incident_summary(self, period_days: int) -> IncidentTrendSummary:
        """Return empty summary when no incidents."""
        now = datetime.now(timezone.utc)
        empty_trend = TrendResult(
            metric_name="empty",
            direction=TrendDirection.STABLE,
            slope=0,
            confidence=0,
            period_start=now - timedelta(days=period_days),
            period_end=now,
            data_points=[],
            baseline=0,
            current=0,
            percent_change=0,
        )
        
        return IncidentTrendSummary(
            period=f"{period_days} days",
            total_incidents=0,
            incident_trend=empty_trend,
            mttr_trend=empty_trend,
            mttd_trend=empty_trend,
            severity_breakdown={},
            top_services=[],
            alert_fatigue_score=0,
            recommendations=["No incidents in the period - maintain current practices."],
        )
