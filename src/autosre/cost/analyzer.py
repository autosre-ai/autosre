"""
Cost Analysis for Cloud Infrastructure

Provides comprehensive cost analysis including:
- Cost breakdown by service, team, environment, resource type
- Cost trends over time
- Cost allocation and chargeback
- Multi-cloud cost aggregation
"""

import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CloudProvider(str, Enum):
    """Supported cloud providers."""
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"
    ON_PREM = "on_prem"
    MULTI_CLOUD = "multi_cloud"


class ResourceType(str, Enum):
    """Types of cloud resources."""
    COMPUTE = "compute"          # EC2, GCE, VMs
    KUBERNETES = "kubernetes"    # EKS, GKE, AKS
    DATABASE = "database"        # RDS, CloudSQL, Azure SQL
    STORAGE = "storage"          # S3, GCS, Blob
    NETWORK = "network"          # VPC, Load Balancers, CDN
    SERVERLESS = "serverless"    # Lambda, Cloud Functions
    MONITORING = "monitoring"    # CloudWatch, Stackdriver
    SECURITY = "security"        # WAF, IAM, KMS
    DATA_TRANSFER = "data_transfer"
    OTHER = "other"


@dataclass
class CostMetric:
    """A single cost metric data point."""
    timestamp: datetime
    amount: float
    currency: str = "USD"
    resource_id: Optional[str] = None
    resource_type: ResourceType = ResourceType.OTHER
    service: Optional[str] = None
    team: Optional[str] = None
    environment: Optional[str] = None
    region: Optional[str] = None
    provider: CloudProvider = CloudProvider.AWS
    tags: dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "amount": self.amount,
            "currency": self.currency,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type.value,
            "service": self.service,
            "team": self.team,
            "environment": self.environment,
            "region": self.region,
            "provider": self.provider.value,
            "tags": self.tags,
        }


@dataclass
class CostBreakdown:
    """Breakdown of costs by various dimensions."""
    total_cost: float
    currency: str
    period_start: datetime
    period_end: datetime
    by_service: dict[str, float] = field(default_factory=dict)
    by_team: dict[str, float] = field(default_factory=dict)
    by_environment: dict[str, float] = field(default_factory=dict)
    by_resource_type: dict[str, float] = field(default_factory=dict)
    by_region: dict[str, float] = field(default_factory=dict)
    by_provider: dict[str, float] = field(default_factory=dict)
    top_resources: list[tuple[str, float]] = field(default_factory=list)
    untagged_cost: float = 0.0
    untagged_percentage: float = 0.0
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_cost": self.total_cost,
            "currency": self.currency,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "by_service": self.by_service,
            "by_team": self.by_team,
            "by_environment": self.by_environment,
            "by_resource_type": self.by_resource_type,
            "by_region": self.by_region,
            "by_provider": self.by_provider,
            "top_resources": self.top_resources,
            "untagged_cost": self.untagged_cost,
            "untagged_percentage": self.untagged_percentage,
        }
    
    @property
    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"Total Cost: {self.currency} {self.total_cost:,.2f}",
            f"Period: {self.period_start.date()} to {self.period_end.date()}",
        ]
        
        if self.by_service:
            top_service = max(self.by_service.items(), key=lambda x: x[1])
            lines.append(f"Top Service: {top_service[0]} ({self.currency} {top_service[1]:,.2f})")
        
        if self.by_team:
            top_team = max(self.by_team.items(), key=lambda x: x[1])
            lines.append(f"Top Team: {top_team[0]} ({self.currency} {top_team[1]:,.2f})")
        
        if self.untagged_percentage > 10:
            lines.append(f"Warning: {self.untagged_percentage:.1f}% of costs are untagged")
        
        return "\n".join(lines)


@dataclass
class CostTrend:
    """Cost trend analysis result."""
    metric_name: str
    direction: str  # increasing, decreasing, stable, volatile
    current_daily_rate: float
    previous_daily_rate: float
    percent_change: float
    confidence: float
    projected_monthly: float
    currency: str = "USD"
    period_days: int = 30
    data_points: list[tuple[datetime, float]] = field(default_factory=list)
    anomalies: list[tuple[datetime, float, str]] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "metric_name": self.metric_name,
            "direction": self.direction,
            "current_daily_rate": self.current_daily_rate,
            "previous_daily_rate": self.previous_daily_rate,
            "percent_change": self.percent_change,
            "confidence": self.confidence,
            "projected_monthly": self.projected_monthly,
            "currency": self.currency,
            "period_days": self.period_days,
            "data_points_count": len(self.data_points),
            "anomalies_count": len(self.anomalies),
        }
    
    @property
    def summary(self) -> str:
        """Human-readable summary."""
        direction_emoji = {
            "increasing": "📈",
            "decreasing": "📉",
            "stable": "➡️",
            "volatile": "📊",
        }
        emoji = direction_emoji.get(self.direction, "")
        
        summary = f"{emoji} {self.metric_name}: {self.direction}"
        if self.direction in ("increasing", "decreasing"):
            summary += f" ({self.percent_change:+.1f}%)"
        summary += f"\nProjected monthly: {self.currency} {self.projected_monthly:,.2f}"
        
        if self.anomalies:
            summary += f"\n⚠️ {len(self.anomalies)} cost anomalies detected"
        
        return summary


@dataclass
class CostAllocation:
    """Cost allocation/chargeback configuration."""
    name: str
    rules: list[dict[str, Any]] = field(default_factory=list)
    shared_cost_distribution: str = "proportional"  # proportional, equal, fixed
    unallocated_bucket: str = "platform"
    
    def allocate(self, costs: list[CostMetric]) -> dict[str, float]:
        """
        Allocate costs based on rules.
        
        Returns dict mapping allocation targets to costs.
        """
        allocations: dict[str, float] = {}
        unallocated = 0.0
        
        for cost in costs:
            allocated = False
            
            for rule in self.rules:
                if self._matches_rule(cost, rule):
                    target = rule.get("target", self.unallocated_bucket)
                    allocations[target] = allocations.get(target, 0) + cost.amount
                    allocated = True
                    break
            
            if not allocated:
                unallocated += cost.amount
        
        # Handle unallocated costs
        if unallocated > 0:
            if self.shared_cost_distribution == "proportional" and allocations:
                # Distribute proportionally
                total_allocated = sum(allocations.values())
                for target in allocations:
                    proportion = allocations[target] / total_allocated
                    allocations[target] += unallocated * proportion
            elif self.shared_cost_distribution == "equal" and allocations:
                # Distribute equally
                per_target = unallocated / len(allocations)
                for target in allocations:
                    allocations[target] += per_target
            else:
                # Add to unallocated bucket
                allocations[self.unallocated_bucket] = (
                    allocations.get(self.unallocated_bucket, 0) + unallocated
                )
        
        return allocations
    
    def _matches_rule(self, cost: CostMetric, rule: dict) -> bool:
        """Check if a cost matches a rule."""
        conditions = rule.get("conditions", {})
        
        for field, value in conditions.items():
            if field == "service" and cost.service != value:
                return False
            if field == "team" and cost.team != value:
                return False
            if field == "environment" and cost.environment != value:
                return False
            if field == "resource_type" and cost.resource_type.value != value:
                return False
            if field == "tags":
                for tag_key, tag_value in value.items():
                    if cost.tags.get(tag_key) != tag_value:
                        return False
        
        return True


class CostAnalyzer:
    """
    Analyzes cloud infrastructure costs.
    
    Provides comprehensive cost analysis including:
    - Cost breakdowns by service, team, environment
    - Trend analysis
    - Cost allocation and chargeback
    - Multi-cloud aggregation
    """
    
    def __init__(
        self,
        currency: str = "USD",
        cost_providers: Optional[list[str]] = None,
    ):
        self.currency = currency
        self.cost_providers = cost_providers or ["aws"]
        self._cost_data: list[CostMetric] = []
    
    def load_costs(self, costs: list[CostMetric]) -> None:
        """Load cost data for analysis."""
        self._cost_data = sorted(costs, key=lambda x: x.timestamp)
        logger.info(f"Loaded {len(costs)} cost records")
    
    def analyze_breakdown(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        filters: Optional[dict[str, str]] = None,
    ) -> CostBreakdown:
        """
        Analyze cost breakdown by various dimensions.
        
        Args:
            start_date: Start of analysis period
            end_date: End of analysis period
            filters: Optional filters (service, team, environment, etc.)
            
        Returns:
            CostBreakdown with detailed analysis
        """
        # Default to last 30 days
        if end_date is None:
            end_date = datetime.now(timezone.utc)
        if start_date is None:
            start_date = end_date - timedelta(days=30)
        
        # Filter costs
        filtered_costs = self._filter_costs(start_date, end_date, filters)
        
        if not filtered_costs:
            return CostBreakdown(
                total_cost=0.0,
                currency=self.currency,
                period_start=start_date,
                period_end=end_date,
            )
        
        # Calculate breakdowns
        by_service: dict[str, float] = {}
        by_team: dict[str, float] = {}
        by_environment: dict[str, float] = {}
        by_resource_type: dict[str, float] = {}
        by_region: dict[str, float] = {}
        by_provider: dict[str, float] = {}
        resource_costs: dict[str, float] = {}
        untagged_cost = 0.0
        
        for cost in filtered_costs:
            # By service
            service = cost.service or "unknown"
            by_service[service] = by_service.get(service, 0) + cost.amount
            
            # By team
            team = cost.team or "unassigned"
            by_team[team] = by_team.get(team, 0) + cost.amount
            
            # By environment
            env = cost.environment or "unknown"
            by_environment[env] = by_environment.get(env, 0) + cost.amount
            
            # By resource type
            rtype = cost.resource_type.value
            by_resource_type[rtype] = by_resource_type.get(rtype, 0) + cost.amount
            
            # By region
            region = cost.region or "global"
            by_region[region] = by_region.get(region, 0) + cost.amount
            
            # By provider
            provider = cost.provider.value
            by_provider[provider] = by_provider.get(provider, 0) + cost.amount
            
            # Track resource costs
            if cost.resource_id:
                resource_costs[cost.resource_id] = (
                    resource_costs.get(cost.resource_id, 0) + cost.amount
                )
            
            # Track untagged costs
            if not cost.service and not cost.team:
                untagged_cost += cost.amount
        
        total_cost = sum(cost.amount for cost in filtered_costs)
        
        # Sort breakdowns by cost (descending)
        by_service = dict(sorted(by_service.items(), key=lambda x: x[1], reverse=True))
        by_team = dict(sorted(by_team.items(), key=lambda x: x[1], reverse=True))
        by_environment = dict(sorted(by_environment.items(), key=lambda x: x[1], reverse=True))
        by_resource_type = dict(sorted(by_resource_type.items(), key=lambda x: x[1], reverse=True))
        by_region = dict(sorted(by_region.items(), key=lambda x: x[1], reverse=True))
        
        # Top resources
        top_resources = sorted(
            resource_costs.items(), key=lambda x: x[1], reverse=True
        )[:10]
        
        return CostBreakdown(
            total_cost=total_cost,
            currency=self.currency,
            period_start=start_date,
            period_end=end_date,
            by_service=by_service,
            by_team=by_team,
            by_environment=by_environment,
            by_resource_type=by_resource_type,
            by_region=by_region,
            by_provider=by_provider,
            top_resources=top_resources,
            untagged_cost=untagged_cost,
            untagged_percentage=(untagged_cost / total_cost * 100) if total_cost > 0 else 0,
        )
    
    def analyze_trend(
        self,
        metric_name: str = "total_cost",
        period_days: int = 30,
        group_by: Optional[str] = None,
    ) -> CostTrend:
        """
        Analyze cost trends over time.
        
        Args:
            metric_name: Name of the metric being analyzed
            period_days: Number of days to analyze
            group_by: Optional grouping (service, team, environment)
            
        Returns:
            CostTrend with direction and projections
        """
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=period_days)
        
        filtered_costs = self._filter_costs(start_date, end_date, None)
        
        if not filtered_costs:
            return CostTrend(
                metric_name=metric_name,
                direction="stable",
                current_daily_rate=0.0,
                previous_daily_rate=0.0,
                percent_change=0.0,
                confidence=0.0,
                projected_monthly=0.0,
                currency=self.currency,
                period_days=period_days,
            )
        
        # Group costs by day
        daily_costs = self._group_by_day(filtered_costs)
        
        if len(daily_costs) < 3:
            return CostTrend(
                metric_name=metric_name,
                direction="unknown",
                current_daily_rate=statistics.mean(daily_costs.values()) if daily_costs else 0,
                previous_daily_rate=0.0,
                percent_change=0.0,
                confidence=0.0,
                projected_monthly=sum(daily_costs.values()) * 30 / len(daily_costs) if daily_costs else 0,
                currency=self.currency,
                period_days=period_days,
            )
        
        # Calculate trend
        sorted_dates = sorted(daily_costs.keys())
        data_points = [(d, daily_costs[d]) for d in sorted_dates]
        
        # Split into halves for comparison
        mid = len(sorted_dates) // 2
        first_half = [daily_costs[d] for d in sorted_dates[:mid]]
        second_half = [daily_costs[d] for d in sorted_dates[mid:]]
        
        previous_rate = statistics.mean(first_half) if first_half else 0
        current_rate = statistics.mean(second_half) if second_half else 0
        
        if previous_rate > 0:
            percent_change = ((current_rate - previous_rate) / previous_rate) * 100
        else:
            percent_change = 100 if current_rate > 0 else 0
        
        # Determine direction
        if abs(percent_change) < 5:
            direction = "stable"
            confidence = 0.8
        elif percent_change > 20:
            direction = "increasing"
            confidence = min(0.95, 0.6 + abs(percent_change) / 100)
        elif percent_change < -20:
            direction = "decreasing"
            confidence = min(0.95, 0.6 + abs(percent_change) / 100)
        else:
            direction = "increasing" if percent_change > 0 else "decreasing"
            confidence = 0.6
        
        # Check for volatility
        if len(daily_costs) > 7:
            values = list(daily_costs.values())
            cv = statistics.stdev(values) / statistics.mean(values) if statistics.mean(values) > 0 else 0
            if cv > 0.3:
                direction = "volatile"
                confidence = 0.7
        
        # Detect anomalies
        anomalies = self._detect_cost_anomalies(daily_costs)
        
        return CostTrend(
            metric_name=metric_name,
            direction=direction,
            current_daily_rate=current_rate,
            previous_daily_rate=previous_rate,
            percent_change=percent_change,
            confidence=confidence,
            projected_monthly=current_rate * 30,
            currency=self.currency,
            period_days=period_days,
            data_points=data_points,
            anomalies=anomalies,
        )
    
    def compare_periods(
        self,
        period1_start: datetime,
        period1_end: datetime,
        period2_start: datetime,
        period2_end: datetime,
        group_by: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Compare costs between two periods.
        
        Returns comparison with changes per dimension.
        """
        period1_costs = self._filter_costs(period1_start, period1_end, None)
        period2_costs = self._filter_costs(period2_start, period2_end, None)
        
        period1_total = sum(c.amount for c in period1_costs)
        period2_total = sum(c.amount for c in period2_costs)
        
        if period1_total > 0:
            overall_change = ((period2_total - period1_total) / period1_total) * 100
        else:
            overall_change = 100 if period2_total > 0 else 0
        
        # Compare by service
        service_changes = self._compare_by_dimension(
            period1_costs, period2_costs, "service"
        )
        
        # Compare by team
        team_changes = self._compare_by_dimension(
            period1_costs, period2_costs, "team"
        )
        
        return {
            "period1": {
                "start": period1_start.isoformat(),
                "end": period1_end.isoformat(),
                "total": period1_total,
            },
            "period2": {
                "start": period2_start.isoformat(),
                "end": period2_end.isoformat(),
                "total": period2_total,
            },
            "overall_change_percent": overall_change,
            "currency": self.currency,
            "by_service": service_changes,
            "by_team": team_changes,
        }
    
    def calculate_unit_costs(
        self,
        metric_name: str,
        metric_values: dict[str, float],
        period_days: int = 30,
    ) -> dict[str, dict[str, float]]:
        """
        Calculate cost per unit of a metric.
        
        Args:
            metric_name: Name of the metric (requests, users, transactions)
            metric_values: Dict of service -> metric value
            period_days: Period for cost calculation
            
        Returns:
            Dict of service -> {cost, metric_value, unit_cost}
        """
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=period_days)
        
        costs = self._filter_costs(start_date, end_date, None)
        
        # Group costs by service
        service_costs: dict[str, float] = {}
        for cost in costs:
            service = cost.service or "unknown"
            service_costs[service] = service_costs.get(service, 0) + cost.amount
        
        # Calculate unit costs
        unit_costs: dict[str, dict[str, float]] = {}
        
        for service, metric_value in metric_values.items():
            cost = service_costs.get(service, 0)
            unit_cost = cost / metric_value if metric_value > 0 else 0
            
            unit_costs[service] = {
                "total_cost": cost,
                "metric_name": metric_name,
                "metric_value": metric_value,
                "unit_cost": unit_cost,
                "currency": self.currency,
            }
        
        return unit_costs
    
    def get_tagging_compliance(self) -> dict[str, Any]:
        """
        Analyze tagging compliance across resources.
        
        Returns compliance report with recommendations.
        """
        if not self._cost_data:
            return {"compliance_rate": 0, "untagged_cost": 0, "recommendations": []}
        
        required_tags = ["service", "team", "environment"]
        
        total_cost = sum(c.amount for c in self._cost_data)
        
        # Check each required tag
        tag_compliance: dict[str, dict[str, float]] = {}
        
        for tag in required_tags:
            tagged_cost = 0.0
            for cost in self._cost_data:
                if tag == "service" and cost.service:
                    tagged_cost += cost.amount
                elif tag == "team" and cost.team:
                    tagged_cost += cost.amount
                elif tag == "environment" and cost.environment:
                    tagged_cost += cost.amount
            
            tag_compliance[tag] = {
                "tagged_cost": tagged_cost,
                "untagged_cost": total_cost - tagged_cost,
                "compliance_rate": (tagged_cost / total_cost * 100) if total_cost > 0 else 0,
            }
        
        # Overall compliance
        fully_tagged_cost = 0.0
        for cost in self._cost_data:
            if cost.service and cost.team and cost.environment:
                fully_tagged_cost += cost.amount
        
        overall_rate = (fully_tagged_cost / total_cost * 100) if total_cost > 0 else 0
        
        # Generate recommendations
        recommendations = []
        for tag, data in tag_compliance.items():
            if data["compliance_rate"] < 80:
                recommendations.append(
                    f"Improve '{tag}' tagging - currently at {data['compliance_rate']:.1f}% "
                    f"(${data['untagged_cost']:,.2f} untagged)"
                )
        
        return {
            "compliance_rate": overall_rate,
            "total_cost": total_cost,
            "fully_tagged_cost": fully_tagged_cost,
            "untagged_cost": total_cost - fully_tagged_cost,
            "by_tag": tag_compliance,
            "required_tags": required_tags,
            "recommendations": recommendations,
            "currency": self.currency,
        }
    
    def _filter_costs(
        self,
        start_date: datetime,
        end_date: datetime,
        filters: Optional[dict[str, str]],
    ) -> list[CostMetric]:
        """Filter costs by date range and optional filters."""
        filtered = [
            c for c in self._cost_data
            if start_date <= c.timestamp <= end_date
        ]
        
        if filters:
            for key, value in filters.items():
                if key == "service":
                    filtered = [c for c in filtered if c.service == value]
                elif key == "team":
                    filtered = [c for c in filtered if c.team == value]
                elif key == "environment":
                    filtered = [c for c in filtered if c.environment == value]
                elif key == "provider":
                    filtered = [c for c in filtered if c.provider.value == value]
                elif key == "resource_type":
                    filtered = [c for c in filtered if c.resource_type.value == value]
        
        return filtered
    
    def _group_by_day(self, costs: list[CostMetric]) -> dict[datetime, float]:
        """Group costs by day."""
        daily: dict[datetime, float] = {}
        
        for cost in costs:
            day = cost.timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
            daily[day] = daily.get(day, 0) + cost.amount
        
        return daily
    
    def _detect_cost_anomalies(
        self,
        daily_costs: dict[datetime, float],
        threshold: float = 2.0,
    ) -> list[tuple[datetime, float, str]]:
        """Detect cost anomalies using statistical methods."""
        if len(daily_costs) < 7:
            return []
        
        values = list(daily_costs.values())
        mean_cost = statistics.mean(values)
        std_dev = statistics.stdev(values)
        
        anomalies = []
        for day, cost in daily_costs.items():
            if std_dev > 0:
                z_score = (cost - mean_cost) / std_dev
                if abs(z_score) > threshold:
                    anomaly_type = "spike" if z_score > 0 else "drop"
                    anomalies.append((day, cost, anomaly_type))
        
        return anomalies
    
    def _compare_by_dimension(
        self,
        costs1: list[CostMetric],
        costs2: list[CostMetric],
        dimension: str,
    ) -> dict[str, dict[str, float]]:
        """Compare costs by a dimension between two periods."""
        def get_value(cost: CostMetric, dim: str) -> str:
            if dim == "service":
                return cost.service or "unknown"
            elif dim == "team":
                return cost.team or "unassigned"
            elif dim == "environment":
                return cost.environment or "unknown"
            return "unknown"
        
        # Group period 1
        p1: dict[str, float] = {}
        for cost in costs1:
            key = get_value(cost, dimension)
            p1[key] = p1.get(key, 0) + cost.amount
        
        # Group period 2
        p2: dict[str, float] = {}
        for cost in costs2:
            key = get_value(cost, dimension)
            p2[key] = p2.get(key, 0) + cost.amount
        
        # Calculate changes
        all_keys = set(p1.keys()) | set(p2.keys())
        changes: dict[str, dict[str, float]] = {}
        
        for key in all_keys:
            period1_cost = p1.get(key, 0)
            period2_cost = p2.get(key, 0)
            
            if period1_cost > 0:
                change_percent = ((period2_cost - period1_cost) / period1_cost) * 100
            else:
                change_percent = 100 if period2_cost > 0 else 0
            
            changes[key] = {
                "period1": period1_cost,
                "period2": period2_cost,
                "change": period2_cost - period1_cost,
                "change_percent": change_percent,
            }
        
        return dict(sorted(changes.items(), key=lambda x: abs(x[1]["change"]), reverse=True))
