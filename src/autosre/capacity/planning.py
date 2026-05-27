"""
Capacity Planning for AutoSRE.

Provides capacity planning capabilities including:
- Resource capacity assessment
- Scaling recommendations
- Budget estimation
- Capacity plans with timelines
"""

import uuid
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ResourceType(str, Enum):
    """Types of resources to plan capacity for."""
    
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    GPU = "gpu"
    DATABASE_CONNECTIONS = "database_connections"
    DATABASE_STORAGE = "database_storage"
    DATABASE_IOPS = "database_iops"
    CACHE = "cache"
    QUEUE = "queue"
    PODS = "pods"
    NODES = "nodes"
    INSTANCES = "instances"
    CONTAINERS = "containers"
    CUSTOM = "custom"


class ScalingStrategy(str, Enum):
    """Scaling strategies for capacity planning."""
    
    HORIZONTAL = "horizontal"    # Add more instances
    VERTICAL = "vertical"        # Upgrade instance size
    HYBRID = "hybrid"            # Combination of both
    NONE = "none"                # No scaling needed
    OPTIMIZE = "optimize"        # Optimize before scaling


class PlanningHorizon(str, Enum):
    """Time horizons for capacity planning."""
    
    IMMEDIATE = "immediate"  # 0-7 days
    SHORT_TERM = "short_term"  # 7-30 days
    MEDIUM_TERM = "medium_term"  # 1-3 months
    LONG_TERM = "long_term"  # 3-12 months
    STRATEGIC = "strategic"  # 1-3 years


class RecommendationType(str, Enum):
    """Types of capacity recommendations."""
    
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    SCALE_OUT = "scale_out"
    SCALE_IN = "scale_in"
    OPTIMIZE = "optimize"
    RESERVE = "reserve"          # Reserve capacity in advance
    SPOT_INSTANCES = "spot_instances"
    RIGHT_SIZE = "right_size"
    NO_ACTION = "no_action"


class RecommendationPriority(str, Enum):
    """Priority levels for recommendations."""
    
    CRITICAL = "critical"    # Act immediately
    HIGH = "high"            # Act within days
    MEDIUM = "medium"        # Act within weeks
    LOW = "low"              # Nice to have
    INFORMATIONAL = "informational"


class CostImpact(str, Enum):
    """Cost impact of a recommendation."""
    
    SAVINGS = "savings"
    INCREASE = "increase"
    NEUTRAL = "neutral"
    VARIABLE = "variable"


@dataclass
class ResourceSpec:
    """Specification for a resource type."""
    
    resource_type: ResourceType
    unit: str  # e.g., "cores", "GB", "IOPS"
    current_allocation: float
    current_usage: float
    max_allocation: float
    min_allocation: float = 0.0
    cost_per_unit_hour: float = 0.0
    
    @property
    def utilization_percent(self) -> float:
        """Get current utilization as a percentage."""
        if self.current_allocation == 0:
            return 0.0
        return (self.current_usage / self.current_allocation) * 100
    
    @property
    def headroom_percent(self) -> float:
        """Get available headroom as a percentage."""
        return 100 - self.utilization_percent
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "resource_type": self.resource_type.value,
            "unit": self.unit,
            "current_allocation": self.current_allocation,
            "current_usage": self.current_usage,
            "max_allocation": self.max_allocation,
            "min_allocation": self.min_allocation,
            "cost_per_unit_hour": self.cost_per_unit_hour,
            "utilization_percent": self.utilization_percent,
            "headroom_percent": self.headroom_percent,
        }


class CurrentCapacity(BaseModel):
    """Current capacity state of a system."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    service: str = ""
    environment: str = ""  # e.g., "production", "staging"
    region: str = ""
    
    # Resources
    resources: list[dict] = Field(default_factory=list)  # ResourceSpec as dicts
    
    # Metadata
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data_source: str = ""
    tags: dict[str, str] = Field(default_factory=dict)
    
    def add_resource(self, resource: ResourceSpec) -> None:
        """Add a resource to the capacity."""
        self.resources.append(resource.to_dict())
    
    def get_resource(self, resource_type: ResourceType) -> Optional[dict]:
        """Get a specific resource by type."""
        for r in self.resources:
            if r["resource_type"] == resource_type.value:
                return r
        return None
    
    def get_critical_resources(self, threshold: float = 80.0) -> list[dict]:
        """Get resources above utilization threshold."""
        return [r for r in self.resources if r.get("utilization_percent", 0) >= threshold]
    
    def get_underutilized_resources(self, threshold: float = 30.0) -> list[dict]:
        """Get resources below utilization threshold."""
        return [r for r in self.resources if r.get("utilization_percent", 0) < threshold]


class CapacityRequirement(BaseModel):
    """Capacity requirement specification."""
    
    resource_type: ResourceType
    required_capacity: float
    unit: str
    
    # Timing
    needed_by: datetime
    duration_days: int = Field(default=30)
    
    # Constraints
    min_headroom_percent: float = Field(default=20.0, ge=0, le=100)
    max_utilization_percent: float = Field(default=80.0, ge=0, le=100)
    
    # Context
    reason: str = ""
    confidence: float = Field(default=0.8, ge=0, le=1)  # How confident in the requirement
    based_on: str = ""  # e.g., "forecast", "growth_plan", "event"
    
    def get_with_headroom(self) -> float:
        """Get required capacity including headroom."""
        headroom_factor = 1 + (self.min_headroom_percent / 100)
        return self.required_capacity * headroom_factor


class ScalingRecommendation(BaseModel):
    """A scaling recommendation."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_type: ResourceType
    recommendation_type: RecommendationType
    priority: RecommendationPriority
    
    # Details
    current_value: float
    recommended_value: float
    unit: str
    
    # Impact
    cost_impact: CostImpact
    monthly_cost_change: float = 0.0  # Positive = increase, negative = savings
    
    # Timing
    recommended_by: datetime
    implementation_hours: float = 1.0  # Estimated time to implement
    
    # Reasoning
    reason: str
    details: str = ""
    supporting_data: dict[str, Any] = Field(default_factory=dict)
    
    # Risk
    risk_level: str = "low"
    risk_details: str = ""
    rollback_plan: str = ""
    
    def get_change_percent(self) -> float:
        """Get the percentage change."""
        if self.current_value == 0:
            return 100.0
        return ((self.recommended_value - self.current_value) / self.current_value) * 100


class BudgetEstimate(BaseModel):
    """Budget estimate for capacity plan."""
    
    horizon: PlanningHorizon
    start_date: datetime
    end_date: datetime
    
    # Current costs
    current_monthly_cost: float
    
    # Projected costs
    projected_monthly_cost: float
    total_cost_change: float
    
    # Breakdown
    scaling_costs: float = 0.0
    optimization_savings: float = 0.0
    reserved_instance_savings: float = 0.0
    
    # Details
    cost_breakdown: dict[str, float] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    
    @property
    def net_change_percent(self) -> float:
        """Get net cost change as percentage."""
        if self.current_monthly_cost == 0:
            return 0.0
        return ((self.projected_monthly_cost - self.current_monthly_cost) / 
                self.current_monthly_cost) * 100


class CapacityPlan(BaseModel):
    """A complete capacity plan."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    horizon: PlanningHorizon
    
    # Context
    service: str = ""
    environment: str = ""
    region: str = ""
    team: str = ""
    
    # Current state
    current_capacity: Optional[CurrentCapacity] = None
    
    # Requirements
    requirements: list[CapacityRequirement] = Field(default_factory=list)
    
    # Recommendations
    recommendations: list[ScalingRecommendation] = Field(default_factory=list)
    
    # Budget
    budget_estimate: Optional[BudgetEstimate] = None
    
    # Timeline
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    start_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    end_date: Optional[datetime] = None
    
    # Status
    status: str = "draft"  # draft, approved, in_progress, completed
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    
    # Metadata
    created_by: str = ""
    tags: dict[str, str] = Field(default_factory=dict)
    
    def add_requirement(self, requirement: CapacityRequirement) -> None:
        """Add a capacity requirement."""
        self.requirements.append(requirement)
    
    def add_recommendation(self, recommendation: ScalingRecommendation) -> None:
        """Add a scaling recommendation."""
        self.recommendations.append(recommendation)
    
    def get_critical_recommendations(self) -> list[ScalingRecommendation]:
        """Get critical priority recommendations."""
        return [r for r in self.recommendations 
                if r.priority == RecommendationPriority.CRITICAL]
    
    def get_total_cost_impact(self) -> float:
        """Get total monthly cost impact of all recommendations."""
        return sum(r.monthly_cost_change for r in self.recommendations)
    
    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the plan."""
        return {
            "id": self.id,
            "name": self.name,
            "horizon": self.horizon.value,
            "status": self.status,
            "requirements_count": len(self.requirements),
            "recommendations_count": len(self.recommendations),
            "critical_recommendations": len(self.get_critical_recommendations()),
            "monthly_cost_impact": self.get_total_cost_impact(),
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
        }


class CapacityPlanner:
    """Planner for capacity management."""
    
    # Default thresholds
    DEFAULT_HIGH_UTILIZATION = 80.0
    DEFAULT_LOW_UTILIZATION = 30.0
    DEFAULT_TARGET_UTILIZATION = 70.0
    DEFAULT_HEADROOM_PERCENT = 20.0
    
    def __init__(
        self,
        high_utilization_threshold: float = DEFAULT_HIGH_UTILIZATION,
        low_utilization_threshold: float = DEFAULT_LOW_UTILIZATION,
        target_utilization: float = DEFAULT_TARGET_UTILIZATION,
    ):
        """Initialize the capacity planner."""
        self.high_utilization_threshold = high_utilization_threshold
        self.low_utilization_threshold = low_utilization_threshold
        self.target_utilization = target_utilization
        self._plans: dict[str, CapacityPlan] = {}
    
    def assess_capacity(
        self,
        current: CurrentCapacity,
    ) -> dict[str, Any]:
        """
        Assess current capacity state.
        
        Args:
            current: Current capacity state
            
        Returns:
            Assessment results
        """
        critical = current.get_critical_resources(self.high_utilization_threshold)
        underutilized = current.get_underutilized_resources(self.low_utilization_threshold)
        
        # Calculate overall health
        utilizations = [r.get("utilization_percent", 0) for r in current.resources]
        avg_utilization = statistics.mean(utilizations) if utilizations else 0
        
        if any(u >= 90 for u in utilizations):
            health = "critical"
        elif any(u >= self.high_utilization_threshold for u in utilizations):
            health = "warning"
        elif avg_utilization < 20:
            health = "over_provisioned"
        else:
            health = "healthy"
        
        return {
            "health": health,
            "average_utilization": avg_utilization,
            "critical_resources": len(critical),
            "underutilized_resources": len(underutilized),
            "total_resources": len(current.resources),
            "critical_details": critical,
            "underutilized_details": underutilized,
            "assessment_time": datetime.now(timezone.utc).isoformat(),
        }
    
    def create_plan(
        self,
        name: str,
        current: CurrentCapacity,
        horizon: PlanningHorizon = PlanningHorizon.SHORT_TERM,
        requirements: Optional[list[CapacityRequirement]] = None,
        include_optimization: bool = True,
        **kwargs: Any,
    ) -> CapacityPlan:
        """
        Create a capacity plan.
        
        Args:
            name: Plan name
            current: Current capacity state
            horizon: Planning horizon
            requirements: Capacity requirements (optional)
            include_optimization: Include optimization recommendations
            **kwargs: Additional plan attributes
            
        Returns:
            CapacityPlan with recommendations
        """
        # Create plan
        plan = CapacityPlan(
            name=name,
            horizon=horizon,
            current_capacity=current,
            service=current.service,
            environment=current.environment,
            region=current.region,
            **kwargs,
        )
        
        # Set end date based on horizon
        horizon_days = {
            PlanningHorizon.IMMEDIATE: 7,
            PlanningHorizon.SHORT_TERM: 30,
            PlanningHorizon.MEDIUM_TERM: 90,
            PlanningHorizon.LONG_TERM: 365,
            PlanningHorizon.STRATEGIC: 1095,
        }
        plan.end_date = plan.start_date + timedelta(days=horizon_days.get(horizon, 30))
        
        # Add requirements if provided
        if requirements:
            for req in requirements:
                plan.add_requirement(req)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            current, requirements or [], include_optimization
        )
        for rec in recommendations:
            plan.add_recommendation(rec)
        
        # Generate budget estimate
        plan.budget_estimate = self._estimate_budget(plan)
        
        self._plans[plan.id] = plan
        return plan
    
    def _generate_recommendations(
        self,
        current: CurrentCapacity,
        requirements: list[CapacityRequirement],
        include_optimization: bool,
    ) -> list[ScalingRecommendation]:
        """Generate scaling recommendations."""
        recommendations = []
        now = datetime.now(timezone.utc)
        
        # Check for overutilized resources
        for resource in current.resources:
            utilization = resource.get("utilization_percent", 0)
            resource_type = ResourceType(resource["resource_type"])
            
            if utilization >= self.high_utilization_threshold:
                # Scale up recommendation
                target_allocation = resource["current_usage"] / (self.target_utilization / 100)
                
                rec = ScalingRecommendation(
                    resource_type=resource_type,
                    recommendation_type=RecommendationType.SCALE_UP,
                    priority=RecommendationPriority.HIGH if utilization >= 90 else RecommendationPriority.MEDIUM,
                    current_value=resource["current_allocation"],
                    recommended_value=target_allocation,
                    unit=resource["unit"],
                    cost_impact=CostImpact.INCREASE,
                    monthly_cost_change=self._estimate_cost_change(
                        resource, target_allocation
                    ),
                    recommended_by=now + timedelta(days=7),
                    reason=f"{resource_type.value} utilization at {utilization:.1f}% exceeds threshold",
                    details=f"Current allocation: {resource['current_allocation']} {resource['unit']}, "
                            f"Usage: {resource['current_usage']} {resource['unit']}",
                )
                recommendations.append(rec)
            
            elif include_optimization and utilization < self.low_utilization_threshold:
                # Scale down recommendation
                target_allocation = max(
                    resource["min_allocation"],
                    resource["current_usage"] / (self.target_utilization / 100)
                )
                
                if target_allocation < resource["current_allocation"] * 0.8:
                    rec = ScalingRecommendation(
                        resource_type=resource_type,
                        recommendation_type=RecommendationType.SCALE_DOWN,
                        priority=RecommendationPriority.LOW,
                        current_value=resource["current_allocation"],
                        recommended_value=target_allocation,
                        unit=resource["unit"],
                        cost_impact=CostImpact.SAVINGS,
                        monthly_cost_change=-self._estimate_cost_change(
                            resource, resource["current_allocation"] - target_allocation
                        ),
                        recommended_by=now + timedelta(days=30),
                        reason=f"{resource_type.value} underutilized at {utilization:.1f}%",
                        details=f"Potential to reduce allocation and save costs",
                    )
                    recommendations.append(rec)
        
        # Check requirements
        for req in requirements:
            resource = current.get_resource(req.resource_type)
            if resource:
                current_allocation = resource["current_allocation"]
                required_with_headroom = req.get_with_headroom()
                
                if required_with_headroom > current_allocation:
                    gap = required_with_headroom - current_allocation
                    rec = ScalingRecommendation(
                        resource_type=req.resource_type,
                        recommendation_type=RecommendationType.SCALE_UP,
                        priority=self._calculate_priority(req.needed_by, now),
                        current_value=current_allocation,
                        recommended_value=required_with_headroom,
                        unit=req.unit,
                        cost_impact=CostImpact.INCREASE,
                        monthly_cost_change=self._estimate_cost_change(resource, gap),
                        recommended_by=req.needed_by - timedelta(days=7),
                        reason=f"Capacity requirement: {req.reason}",
                        details=f"Required: {req.required_capacity} {req.unit} "
                                f"(+{req.min_headroom_percent}% headroom) by {req.needed_by.date()}",
                        supporting_data={"confidence": req.confidence, "based_on": req.based_on},
                    )
                    recommendations.append(rec)
        
        # Sort by priority
        priority_order = {
            RecommendationPriority.CRITICAL: 0,
            RecommendationPriority.HIGH: 1,
            RecommendationPriority.MEDIUM: 2,
            RecommendationPriority.LOW: 3,
            RecommendationPriority.INFORMATIONAL: 4,
        }
        recommendations.sort(key=lambda r: priority_order.get(r.priority, 5))
        
        return recommendations
    
    def _calculate_priority(
        self,
        needed_by: datetime,
        now: datetime,
    ) -> RecommendationPriority:
        """Calculate recommendation priority based on timing."""
        days_until = (needed_by - now).days
        
        if days_until <= 7:
            return RecommendationPriority.CRITICAL
        elif days_until <= 30:
            return RecommendationPriority.HIGH
        elif days_until <= 90:
            return RecommendationPriority.MEDIUM
        else:
            return RecommendationPriority.LOW
    
    def _estimate_cost_change(
        self,
        resource: dict,
        capacity_change: float,
    ) -> float:
        """Estimate monthly cost change for a capacity change."""
        cost_per_unit_hour = resource.get("cost_per_unit_hour", 0)
        hours_per_month = 730  # Average hours in a month
        return capacity_change * cost_per_unit_hour * hours_per_month
    
    def _estimate_budget(self, plan: CapacityPlan) -> BudgetEstimate:
        """Estimate budget for a capacity plan."""
        current_monthly = 0.0
        projected_monthly = 0.0
        scaling_costs = 0.0
        optimization_savings = 0.0
        
        if plan.current_capacity:
            for resource in plan.current_capacity.resources:
                current_monthly += self._estimate_cost_change(
                    resource, resource["current_allocation"]
                )
        
        for rec in plan.recommendations:
            if rec.monthly_cost_change > 0:
                scaling_costs += rec.monthly_cost_change
            else:
                optimization_savings += abs(rec.monthly_cost_change)
        
        projected_monthly = current_monthly + scaling_costs - optimization_savings
        
        return BudgetEstimate(
            horizon=plan.horizon,
            start_date=plan.start_date,
            end_date=plan.end_date or (plan.start_date + timedelta(days=30)),
            current_monthly_cost=current_monthly,
            projected_monthly_cost=projected_monthly,
            total_cost_change=projected_monthly - current_monthly,
            scaling_costs=scaling_costs,
            optimization_savings=optimization_savings,
            cost_breakdown={
                "scaling": scaling_costs,
                "optimization_savings": optimization_savings,
            },
            assumptions=[
                "Cost estimates based on current pricing",
                "Assumes linear scaling of costs with capacity",
                "Does not include potential reserved instance discounts",
            ],
        )
    
    def get_plan(self, plan_id: str) -> Optional[CapacityPlan]:
        """Get a plan by ID."""
        return self._plans.get(plan_id)
    
    def approve_plan(
        self,
        plan_id: str,
        approved_by: str,
    ) -> Optional[CapacityPlan]:
        """Approve a capacity plan."""
        plan = self.get_plan(plan_id)
        if plan:
            plan.status = "approved"
            plan.approved_by = approved_by
            plan.approved_at = datetime.now(timezone.utc)
        return plan
    
    def get_quick_recommendations(
        self,
        current: CurrentCapacity,
    ) -> list[ScalingRecommendation]:
        """Get quick recommendations without creating a full plan."""
        return self._generate_recommendations(current, [], include_optimization=True)


def quick_capacity_check(
    resources: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Quick capacity check from resource data.
    
    Args:
        resources: List of resource dicts with keys:
            - type: Resource type (e.g., "cpu", "memory")
            - allocation: Current allocation
            - usage: Current usage
            - unit: Unit of measurement
            
    Returns:
        Capacity assessment results
    """
    current = CurrentCapacity(name="quick_check")
    
    for r in resources:
        resource_type = ResourceType(r.get("type", "custom"))
        spec = ResourceSpec(
            resource_type=resource_type,
            unit=r.get("unit", "units"),
            current_allocation=r.get("allocation", 0),
            current_usage=r.get("usage", 0),
            max_allocation=r.get("max_allocation", r.get("allocation", 0) * 2),
        )
        current.add_resource(spec)
    
    planner = CapacityPlanner()
    return planner.assess_capacity(current)


def estimate_scaling_needs(
    current_usage: float,
    growth_rate_percent: float,
    months_ahead: int = 3,
    target_utilization: float = 70.0,
) -> dict[str, Any]:
    """
    Estimate scaling needs based on growth rate.
    
    Args:
        current_usage: Current resource usage
        growth_rate_percent: Monthly growth rate as percentage
        months_ahead: Months to project
        target_utilization: Target utilization percentage
        
    Returns:
        Scaling estimate
    """
    # Project usage
    monthly_growth = 1 + (growth_rate_percent / 100)
    projections = []
    
    current = current_usage
    for month in range(1, months_ahead + 1):
        projected = current * (monthly_growth ** month)
        required_capacity = projected / (target_utilization / 100)
        projections.append({
            "month": month,
            "projected_usage": projected,
            "required_capacity": required_capacity,
        })
    
    final_projection = projections[-1] if projections else {}
    
    return {
        "current_usage": current_usage,
        "growth_rate_percent": growth_rate_percent,
        "months_projected": months_ahead,
        "target_utilization_percent": target_utilization,
        "final_projected_usage": final_projection.get("projected_usage", current_usage),
        "final_required_capacity": final_projection.get("required_capacity", current_usage),
        "growth_factor": monthly_growth ** months_ahead,
        "projections": projections,
    }
