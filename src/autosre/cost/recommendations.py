"""
Cost Optimization Recommendations

Provides intelligent cost optimization recommendations including:
- Unused resource detection
- Reserved instance opportunities
- Spot instance candidates
- Storage optimization
- Network cost reduction
- Architecture improvements
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RecommendationType(str, Enum):
    """Types of cost optimization recommendations."""
    UNUSED_RESOURCE = "unused_resource"           # Idle/unused resources
    RIGHTSIZING = "rightsizing"                   # Oversized resources
    RESERVED_INSTANCE = "reserved_instance"       # RI purchase opportunity
    SAVINGS_PLAN = "savings_plan"                 # Savings plan opportunity
    SPOT_INSTANCE = "spot_instance"               # Spot instance candidate
    STORAGE_OPTIMIZATION = "storage_optimization" # Storage tier/cleanup
    NETWORK_OPTIMIZATION = "network_optimization" # NAT/data transfer
    SCHEDULING = "scheduling"                     # Dev/test scheduling
    ARCHITECTURE = "architecture"                 # Architecture changes
    LICENSE_OPTIMIZATION = "license_optimization" # License consolidation
    REGION_OPTIMIZATION = "region_optimization"   # Region arbitrage
    COMMITMENT_DISCOUNT = "commitment_discount"   # Committed use discounts


class RecommendationPriority(str, Enum):
    """Priority levels for recommendations."""
    CRITICAL = "critical"  # >$10k/month savings or urgent
    HIGH = "high"          # $1k-$10k/month savings
    MEDIUM = "medium"      # $100-$1k/month savings
    LOW = "low"            # <$100/month savings


class RecommendationStatus(str, Enum):
    """Status of a recommendation."""
    NEW = "new"
    REVIEWED = "reviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"
    EXPIRED = "expired"


@dataclass
class SavingsEstimate:
    """Estimated savings from implementing a recommendation."""
    monthly_savings: float
    annual_savings: float
    currency: str = "USD"
    confidence: float = 0.8  # 0-1, how confident in estimate
    one_time_cost: float = 0.0  # Implementation cost
    payback_months: float = 0.0  # Time to recoup one_time_cost
    risk_adjusted_savings: float = 0.0  # Savings * confidence
    
    def __post_init__(self):
        """Calculate derived fields."""
        self.risk_adjusted_savings = self.monthly_savings * self.confidence
        if self.monthly_savings > 0 and self.one_time_cost > 0:
            self.payback_months = self.one_time_cost / self.monthly_savings
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "monthly_savings": self.monthly_savings,
            "annual_savings": self.annual_savings,
            "currency": self.currency,
            "confidence": self.confidence,
            "one_time_cost": self.one_time_cost,
            "payback_months": self.payback_months,
            "risk_adjusted_savings": self.risk_adjusted_savings,
        }


@dataclass
class CostRecommendation:
    """A cost optimization recommendation."""
    id: str
    type: RecommendationType
    priority: RecommendationPriority
    title: str
    description: str
    savings: SavingsEstimate
    resource_ids: list[str] = field(default_factory=list)
    service: Optional[str] = None
    team: Optional[str] = None
    environment: Optional[str] = None
    action_items: list[str] = field(default_factory=list)
    implementation_effort: str = "low"  # low, medium, high
    risk_level: str = "low"  # low, medium, high
    status: RecommendationStatus = RecommendationStatus.NEW
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": self.type.value,
            "priority": self.priority.value,
            "title": self.title,
            "description": self.description,
            "savings": self.savings.to_dict(),
            "resource_ids": self.resource_ids,
            "service": self.service,
            "team": self.team,
            "environment": self.environment,
            "action_items": self.action_items,
            "implementation_effort": self.implementation_effort,
            "risk_level": self.risk_level,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.metadata,
        }
    
    @property
    def summary(self) -> str:
        """Human-readable summary."""
        priority_emoji = {
            RecommendationPriority.CRITICAL: "🔴",
            RecommendationPriority.HIGH: "🟠",
            RecommendationPriority.MEDIUM: "🟡",
            RecommendationPriority.LOW: "🟢",
        }
        emoji = priority_emoji.get(self.priority, "")
        
        return (
            f"{emoji} [{self.priority.value.upper()}] {self.title}\n"
            f"   Type: {self.type.value}\n"
            f"   Estimated Savings: ${self.savings.monthly_savings:,.2f}/month "
            f"(${self.savings.annual_savings:,.2f}/year)\n"
            f"   Effort: {self.implementation_effort}, Risk: {self.risk_level}"
        )


class RecommendationEngine:
    """
    Generates cost optimization recommendations.
    
    Analyzes cloud resources and costs to provide actionable
    recommendations for reducing spend.
    """
    
    def __init__(
        self,
        idle_threshold_days: int = 7,
        utilization_threshold: float = 0.2,
        min_savings_threshold: float = 10.0,
    ):
        self.idle_threshold_days = idle_threshold_days
        self.utilization_threshold = utilization_threshold
        self.min_savings_threshold = min_savings_threshold
        self._recommendations: list[CostRecommendation] = []
        self._recommendation_id = 0
    
    def generate_recommendations(
        self,
        resources: list[dict],
        costs: list[dict],
        utilization: Optional[dict[str, dict]] = None,
    ) -> list[CostRecommendation]:
        """
        Generate all recommendations based on resources and costs.
        
        Args:
            resources: List of resource definitions
            costs: List of cost records
            utilization: Optional utilization data per resource
            
        Returns:
            List of CostRecommendation objects
        """
        self._recommendations = []
        
        # Check for unused resources
        unused = self._find_unused_resources(resources, utilization or {})
        self._recommendations.extend(unused)
        
        # Check for rightsizing opportunities
        rightsizing = self._find_rightsizing_opportunities(resources, utilization or {})
        self._recommendations.extend(rightsizing)
        
        # Check for reserved instance opportunities
        ri_opps = self._find_ri_opportunities(resources, costs)
        self._recommendations.extend(ri_opps)
        
        # Check for spot instance candidates
        spot = self._find_spot_candidates(resources)
        self._recommendations.extend(spot)
        
        # Check for storage optimization
        storage = self._find_storage_optimizations(resources, costs)
        self._recommendations.extend(storage)
        
        # Check for scheduling opportunities
        scheduling = self._find_scheduling_opportunities(resources, utilization or {})
        self._recommendations.extend(scheduling)
        
        # Sort by priority and savings
        self._recommendations.sort(
            key=lambda r: (
                list(RecommendationPriority).index(r.priority),
                -r.savings.monthly_savings,
            )
        )
        
        logger.info(f"Generated {len(self._recommendations)} cost recommendations")
        return self._recommendations
    
    def _generate_id(self) -> str:
        """Generate unique recommendation ID."""
        self._recommendation_id += 1
        return f"rec-{self._recommendation_id:04d}"
    
    def _find_unused_resources(
        self,
        resources: list[dict],
        utilization: dict[str, dict],
    ) -> list[CostRecommendation]:
        """Find unused/idle resources."""
        recommendations = []
        
        for resource in resources:
            resource_id = resource.get("id", "")
            resource_type = resource.get("type", "")
            cost_per_month = resource.get("cost_per_month", 0)
            
            # Check utilization
            util_data = utilization.get(resource_id, {})
            cpu_util = util_data.get("cpu_avg", 100)
            last_accessed = util_data.get("last_accessed")
            
            # Check for idle resources
            is_idle = False
            idle_reason = ""
            
            if cpu_util < 1.0:  # Less than 1% CPU
                is_idle = True
                idle_reason = f"CPU utilization < 1% (avg: {cpu_util:.1f}%)"
            
            if last_accessed:
                days_idle = (datetime.now(timezone.utc) - last_accessed).days
                if days_idle > self.idle_threshold_days:
                    is_idle = True
                    idle_reason = f"No access in {days_idle} days"
            
            if is_idle and cost_per_month >= self.min_savings_threshold:
                recommendations.append(
                    CostRecommendation(
                        id=self._generate_id(),
                        type=RecommendationType.UNUSED_RESOURCE,
                        priority=self._calculate_priority(cost_per_month),
                        title=f"Unused {resource_type}: {resource_id}",
                        description=(
                            f"Resource appears to be unused. {idle_reason}. "
                            f"Consider terminating or archiving."
                        ),
                        savings=SavingsEstimate(
                            monthly_savings=cost_per_month,
                            annual_savings=cost_per_month * 12,
                            confidence=0.9,
                        ),
                        resource_ids=[resource_id],
                        service=resource.get("service"),
                        team=resource.get("team"),
                        environment=resource.get("environment"),
                        action_items=[
                            f"Verify {resource_id} is not in use",
                            "Check with service owners",
                            "Create backup if needed",
                            "Terminate or archive resource",
                        ],
                        implementation_effort="low",
                        risk_level="low" if resource.get("environment") == "dev" else "medium",
                        metadata={"idle_reason": idle_reason, "utilization": util_data},
                    )
                )
        
        return recommendations
    
    def _find_rightsizing_opportunities(
        self,
        resources: list[dict],
        utilization: dict[str, dict],
    ) -> list[CostRecommendation]:
        """Find oversized resources that can be rightsized."""
        recommendations = []
        
        for resource in resources:
            resource_id = resource.get("id", "")
            resource_type = resource.get("type", "")
            current_size = resource.get("size", "")
            cost_per_month = resource.get("cost_per_month", 0)
            
            util_data = utilization.get(resource_id, {})
            cpu_util = util_data.get("cpu_avg", 100)
            memory_util = util_data.get("memory_avg", 100)
            
            # Check if oversized
            if cpu_util < self.utilization_threshold * 100 and memory_util < self.utilization_threshold * 100:
                # Estimate savings (assume 50% reduction for one size down)
                estimated_savings = cost_per_month * 0.5
                
                if estimated_savings >= self.min_savings_threshold:
                    recommendations.append(
                        CostRecommendation(
                            id=self._generate_id(),
                            type=RecommendationType.RIGHTSIZING,
                            priority=self._calculate_priority(estimated_savings),
                            title=f"Rightsize {resource_type}: {resource_id}",
                            description=(
                                f"Resource is oversized. CPU: {cpu_util:.1f}%, Memory: {memory_util:.1f}%. "
                                f"Current size: {current_size}. Consider downsizing."
                            ),
                            savings=SavingsEstimate(
                                monthly_savings=estimated_savings,
                                annual_savings=estimated_savings * 12,
                                confidence=0.75,
                            ),
                            resource_ids=[resource_id],
                            service=resource.get("service"),
                            team=resource.get("team"),
                            environment=resource.get("environment"),
                            action_items=[
                                "Review historical utilization patterns",
                                "Identify appropriate target size",
                                "Schedule maintenance window",
                                "Resize resource and monitor",
                            ],
                            implementation_effort="medium",
                            risk_level="medium",
                            metadata={
                                "current_size": current_size,
                                "cpu_utilization": cpu_util,
                                "memory_utilization": memory_util,
                            },
                        )
                    )
        
        return recommendations
    
    def _find_ri_opportunities(
        self,
        resources: list[dict],
        costs: list[dict],
    ) -> list[CostRecommendation]:
        """Find reserved instance purchase opportunities."""
        recommendations = []
        
        # Group resources by type and region
        resource_groups: dict[str, list[dict]] = {}
        for resource in resources:
            key = f"{resource.get('type', '')}:{resource.get('region', '')}"
            if key not in resource_groups:
                resource_groups[key] = []
            resource_groups[key].append(resource)
        
        for key, group in resource_groups.items():
            resource_type, region = key.split(":")
            
            # Only stable resources are RI candidates
            stable_resources = [
                r for r in group
                if r.get("environment") == "production"
                and r.get("age_days", 0) > 30
            ]
            
            if len(stable_resources) >= 3:
                total_on_demand = sum(r.get("cost_per_month", 0) for r in stable_resources)
                
                # RIs typically save 30-40% for 1-year, 50-60% for 3-year
                ri_savings_1yr = total_on_demand * 0.35
                ri_savings_3yr = total_on_demand * 0.55
                
                if ri_savings_1yr >= 100:  # Only if significant savings
                    recommendations.append(
                        CostRecommendation(
                            id=self._generate_id(),
                            type=RecommendationType.RESERVED_INSTANCE,
                            priority=self._calculate_priority(ri_savings_1yr),
                            title=f"Purchase Reserved Instances for {resource_type} in {region}",
                            description=(
                                f"{len(stable_resources)} stable {resource_type} instances identified. "
                                f"1-year RI saves ~35%, 3-year saves ~55%."
                            ),
                            savings=SavingsEstimate(
                                monthly_savings=ri_savings_1yr,
                                annual_savings=ri_savings_1yr * 12,
                                confidence=0.85,
                                one_time_cost=total_on_demand * 12 * 0.3,  # Upfront for 1-yr
                            ),
                            resource_ids=[r.get("id", "") for r in stable_resources],
                            action_items=[
                                f"Review {len(stable_resources)} candidate instances",
                                "Analyze commitment term (1-year vs 3-year)",
                                "Choose payment option (all upfront, partial, no upfront)",
                                "Purchase reserved capacity",
                            ],
                            implementation_effort="medium",
                            risk_level="low",
                            metadata={
                                "resource_count": len(stable_resources),
                                "resource_type": resource_type,
                                "region": region,
                                "ri_savings_1yr": ri_savings_1yr,
                                "ri_savings_3yr": ri_savings_3yr,
                            },
                        )
                    )
        
        return recommendations
    
    def _find_spot_candidates(
        self,
        resources: list[dict],
    ) -> list[CostRecommendation]:
        """Find resources that can use spot instances."""
        recommendations = []
        
        spot_eligible = [
            r for r in resources
            if r.get("type") in ("compute", "kubernetes_node")
            and r.get("environment") in ("dev", "staging", "test")
            and r.get("stateless", True)
        ]
        
        if spot_eligible:
            total_cost = sum(r.get("cost_per_month", 0) for r in spot_eligible)
            spot_savings = total_cost * 0.7  # Spot typically 60-80% cheaper
            
            if spot_savings >= 50:
                recommendations.append(
                    CostRecommendation(
                        id=self._generate_id(),
                        type=RecommendationType.SPOT_INSTANCE,
                        priority=self._calculate_priority(spot_savings),
                        title="Use Spot Instances for non-production workloads",
                        description=(
                            f"{len(spot_eligible)} instances eligible for spot. "
                            f"Spot instances are 60-80% cheaper but can be interrupted."
                        ),
                        savings=SavingsEstimate(
                            monthly_savings=spot_savings,
                            annual_savings=spot_savings * 12,
                            confidence=0.7,
                        ),
                        resource_ids=[r.get("id", "") for r in spot_eligible],
                        action_items=[
                            "Ensure workloads are fault-tolerant",
                            "Implement spot instance interruption handling",
                            "Set up mixed instance groups (spot + on-demand)",
                            "Configure appropriate spot price limits",
                        ],
                        implementation_effort="medium",
                        risk_level="medium",
                        metadata={
                            "eligible_count": len(spot_eligible),
                            "spot_discount_estimate": "60-80%",
                        },
                    )
                )
        
        return recommendations
    
    def _find_storage_optimizations(
        self,
        resources: list[dict],
        costs: list[dict],
    ) -> list[CostRecommendation]:
        """Find storage optimization opportunities."""
        recommendations = []
        
        storage_resources = [
            r for r in resources
            if r.get("type") in ("storage", "ebs", "s3", "gcs", "disk")
        ]
        
        for resource in storage_resources:
            resource_id = resource.get("id", "")
            cost_per_month = resource.get("cost_per_month", 0)
            storage_class = resource.get("storage_class", "standard")
            last_accessed_days = resource.get("last_accessed_days", 0)
            
            # Check for cold storage candidates
            if last_accessed_days > 90 and storage_class == "standard":
                # Moving to cold storage typically saves 50-80%
                savings = cost_per_month * 0.6
                
                if savings >= self.min_savings_threshold:
                    recommendations.append(
                        CostRecommendation(
                            id=self._generate_id(),
                            type=RecommendationType.STORAGE_OPTIMIZATION,
                            priority=self._calculate_priority(savings),
                            title=f"Move {resource_id} to cold storage tier",
                            description=(
                                f"Storage not accessed in {last_accessed_days} days. "
                                f"Move to cold/archive tier for ~60% savings."
                            ),
                            savings=SavingsEstimate(
                                monthly_savings=savings,
                                annual_savings=savings * 12,
                                confidence=0.85,
                            ),
                            resource_ids=[resource_id],
                            service=resource.get("service"),
                            team=resource.get("team"),
                            action_items=[
                                "Verify data access patterns",
                                "Choose appropriate storage tier (infrequent, archive, glacier)",
                                "Set up lifecycle policy",
                                "Monitor retrieval costs if data is accessed",
                            ],
                            implementation_effort="low",
                            risk_level="low",
                            metadata={
                                "current_class": storage_class,
                                "days_since_access": last_accessed_days,
                            },
                        )
                    )
        
        return recommendations
    
    def _find_scheduling_opportunities(
        self,
        resources: list[dict],
        utilization: dict[str, dict],
    ) -> list[CostRecommendation]:
        """Find scheduling/shutdown opportunities for dev/test resources."""
        recommendations = []
        
        dev_resources = [
            r for r in resources
            if r.get("environment") in ("dev", "staging", "test", "sandbox")
            and r.get("type") in ("compute", "kubernetes_node", "database")
        ]
        
        if not dev_resources:
            return recommendations
        
        total_cost = sum(r.get("cost_per_month", 0) for r in dev_resources)
        
        # Assume 12 hours/day, 5 days/week = ~35% of time
        # Savings potential = 65% of cost
        scheduling_savings = total_cost * 0.5  # Conservative estimate
        
        if scheduling_savings >= 100:
            recommendations.append(
                CostRecommendation(
                    id=self._generate_id(),
                    type=RecommendationType.SCHEDULING,
                    priority=self._calculate_priority(scheduling_savings),
                    title="Schedule dev/test environments to shut down after hours",
                    description=(
                        f"{len(dev_resources)} non-production resources can be scheduled. "
                        f"Shut down nights/weekends for ~50% savings."
                    ),
                    savings=SavingsEstimate(
                        monthly_savings=scheduling_savings,
                        annual_savings=scheduling_savings * 12,
                        confidence=0.8,
                    ),
                    resource_ids=[r.get("id", "") for r in dev_resources],
                    action_items=[
                        "Define work hours schedule (e.g., 8am-8pm weekdays)",
                        "Implement automation for start/stop (Lambda, Cloud Scheduler)",
                        "Ensure stateful data is preserved",
                        "Set up manual override for after-hours work",
                    ],
                    implementation_effort="medium",
                    risk_level="low",
                    metadata={
                        "resource_count": len(dev_resources),
                        "environments": list(set(r.get("environment", "") for r in dev_resources)),
                    },
                )
            )
        
        return recommendations
    
    def _calculate_priority(self, monthly_savings: float) -> RecommendationPriority:
        """Calculate recommendation priority based on savings."""
        if monthly_savings >= 10000:
            return RecommendationPriority.CRITICAL
        elif monthly_savings >= 1000:
            return RecommendationPriority.HIGH
        elif monthly_savings >= 100:
            return RecommendationPriority.MEDIUM
        else:
            return RecommendationPriority.LOW
    
    def get_summary(self) -> dict[str, Any]:
        """Get summary of all recommendations."""
        if not self._recommendations:
            return {
                "total_recommendations": 0,
                "total_monthly_savings": 0,
                "total_annual_savings": 0,
                "by_priority": {},
                "by_type": {},
            }
        
        total_monthly = sum(r.savings.monthly_savings for r in self._recommendations)
        total_annual = sum(r.savings.annual_savings for r in self._recommendations)
        
        # Group by priority
        by_priority: dict[str, dict] = {}
        for priority in RecommendationPriority:
            recs = [r for r in self._recommendations if r.priority == priority]
            if recs:
                by_priority[priority.value] = {
                    "count": len(recs),
                    "monthly_savings": sum(r.savings.monthly_savings for r in recs),
                }
        
        # Group by type
        by_type: dict[str, dict] = {}
        for rec_type in RecommendationType:
            recs = [r for r in self._recommendations if r.type == rec_type]
            if recs:
                by_type[rec_type.value] = {
                    "count": len(recs),
                    "monthly_savings": sum(r.savings.monthly_savings for r in recs),
                }
        
        return {
            "total_recommendations": len(self._recommendations),
            "total_monthly_savings": total_monthly,
            "total_annual_savings": total_annual,
            "currency": "USD",
            "by_priority": by_priority,
            "by_type": by_type,
        }
    
    def filter_recommendations(
        self,
        priority: Optional[RecommendationPriority] = None,
        rec_type: Optional[RecommendationType] = None,
        service: Optional[str] = None,
        team: Optional[str] = None,
        min_savings: Optional[float] = None,
    ) -> list[CostRecommendation]:
        """Filter recommendations by criteria."""
        filtered = self._recommendations.copy()
        
        if priority:
            filtered = [r for r in filtered if r.priority == priority]
        
        if rec_type:
            filtered = [r for r in filtered if r.type == rec_type]
        
        if service:
            filtered = [r for r in filtered if r.service == service]
        
        if team:
            filtered = [r for r in filtered if r.team == team]
        
        if min_savings:
            filtered = [r for r in filtered if r.savings.monthly_savings >= min_savings]
        
        return filtered
