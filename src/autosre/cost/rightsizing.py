"""
Resource Rightsizing Analysis

Analyzes resource utilization to provide rightsizing recommendations:
- CPU and memory utilization analysis
- Instance type recommendations
- Container resource optimization
- Database sizing recommendations
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RightsizingAction(str, Enum):
    """Recommended rightsizing actions."""
    DOWNSIZE = "downsize"      # Reduce instance size
    UPSIZE = "upsize"          # Increase instance size
    TERMINATE = "terminate"    # Resource is unused
    MODIFY_TYPE = "modify_type"  # Change instance family
    OPTIMIZE = "optimize"      # Optimize without size change
    NO_ACTION = "no_action"    # Resource is properly sized


@dataclass
class UtilizationThreshold:
    """Thresholds for utilization analysis."""
    idle_cpu: float = 5.0        # Below this = idle (%)
    low_cpu: float = 20.0        # Below this = underutilized (%)
    high_cpu: float = 80.0       # Above this = overutilized (%)
    idle_memory: float = 10.0    # Below this = idle (%)
    low_memory: float = 30.0     # Below this = underutilized (%)
    high_memory: float = 85.0    # Above this = overutilized (%)
    idle_days: int = 7           # Days of low usage = idle
    analysis_days: int = 14      # Days to analyze for recommendations


@dataclass
class InstanceSpec:
    """Specification of a compute instance."""
    instance_type: str
    vcpus: int
    memory_gb: float
    cost_per_hour: float
    provider: str = "aws"
    family: str = ""
    generation: str = ""
    size: str = ""
    network_performance: str = ""
    storage_type: str = ""
    
    @property
    def cost_per_month(self) -> float:
        """Calculate monthly cost (730 hours)."""
        return self.cost_per_hour * 730
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "instance_type": self.instance_type,
            "vcpus": self.vcpus,
            "memory_gb": self.memory_gb,
            "cost_per_hour": self.cost_per_hour,
            "cost_per_month": self.cost_per_month,
            "provider": self.provider,
            "family": self.family,
            "generation": self.generation,
            "size": self.size,
        }


@dataclass
class ResourceUtilization:
    """Utilization metrics for a resource."""
    resource_id: str
    resource_type: str
    current_spec: InstanceSpec
    # CPU metrics
    cpu_avg: float = 0.0
    cpu_max: float = 0.0
    cpu_p95: float = 0.0
    cpu_min: float = 0.0
    # Memory metrics
    memory_avg: float = 0.0
    memory_max: float = 0.0
    memory_p95: float = 0.0
    memory_min: float = 0.0
    # Network metrics
    network_in_avg_mbps: float = 0.0
    network_out_avg_mbps: float = 0.0
    # Disk metrics
    disk_iops_avg: float = 0.0
    disk_throughput_avg_mbps: float = 0.0
    # Metadata
    analysis_period_days: int = 14
    data_points: int = 0
    service: Optional[str] = None
    team: Optional[str] = None
    environment: Optional[str] = None
    tags: dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "current_spec": self.current_spec.to_dict(),
            "cpu_avg": self.cpu_avg,
            "cpu_max": self.cpu_max,
            "cpu_p95": self.cpu_p95,
            "memory_avg": self.memory_avg,
            "memory_max": self.memory_max,
            "memory_p95": self.memory_p95,
            "network_in_avg_mbps": self.network_in_avg_mbps,
            "network_out_avg_mbps": self.network_out_avg_mbps,
            "analysis_period_days": self.analysis_period_days,
            "data_points": self.data_points,
            "service": self.service,
            "team": self.team,
            "environment": self.environment,
        }


@dataclass
class RightsizingRecommendation:
    """A rightsizing recommendation for a resource."""
    resource_id: str
    action: RightsizingAction
    current_spec: InstanceSpec
    recommended_spec: Optional[InstanceSpec]
    utilization: ResourceUtilization
    savings_monthly: float
    savings_percent: float
    confidence: float
    rationale: str
    risks: list[str] = field(default_factory=list)
    implementation_steps: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "resource_id": self.resource_id,
            "action": self.action.value,
            "current_spec": self.current_spec.to_dict(),
            "recommended_spec": self.recommended_spec.to_dict() if self.recommended_spec else None,
            "utilization": self.utilization.to_dict(),
            "savings_monthly": self.savings_monthly,
            "savings_percent": self.savings_percent,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "risks": self.risks,
            "implementation_steps": self.implementation_steps,
            "created_at": self.created_at.isoformat(),
        }
    
    @property
    def summary(self) -> str:
        """Human-readable summary."""
        if self.action == RightsizingAction.NO_ACTION:
            return f"✓ {self.resource_id}: Properly sized"
        
        action_emoji = {
            RightsizingAction.DOWNSIZE: "📉",
            RightsizingAction.UPSIZE: "📈",
            RightsizingAction.TERMINATE: "🗑️",
            RightsizingAction.MODIFY_TYPE: "🔄",
            RightsizingAction.OPTIMIZE: "⚙️",
        }
        emoji = action_emoji.get(self.action, "")
        
        summary = f"{emoji} {self.resource_id}: {self.action.value.title()}"
        
        if self.recommended_spec:
            summary += f"\n   {self.current_spec.instance_type} → {self.recommended_spec.instance_type}"
        
        if self.savings_monthly > 0:
            summary += f"\n   Savings: ${self.savings_monthly:,.2f}/month ({self.savings_percent:.1f}%)"
        
        return summary


class RightsizingAnalyzer:
    """
    Analyzes resources for rightsizing opportunities.
    
    Uses utilization metrics to recommend optimal resource sizes
    that balance cost and performance.
    """
    
    def __init__(
        self,
        thresholds: Optional[UtilizationThreshold] = None,
        instance_catalog: Optional[dict[str, InstanceSpec]] = None,
    ):
        self.thresholds = thresholds or UtilizationThreshold()
        self._instance_catalog = instance_catalog or self._default_instance_catalog()
    
    def _default_instance_catalog(self) -> dict[str, InstanceSpec]:
        """Default AWS instance catalog (simplified)."""
        return {
            # General Purpose
            "t3.nano": InstanceSpec("t3.nano", 2, 0.5, 0.0052, "aws", "t3", "3", "nano"),
            "t3.micro": InstanceSpec("t3.micro", 2, 1, 0.0104, "aws", "t3", "3", "micro"),
            "t3.small": InstanceSpec("t3.small", 2, 2, 0.0208, "aws", "t3", "3", "small"),
            "t3.medium": InstanceSpec("t3.medium", 2, 4, 0.0416, "aws", "t3", "3", "medium"),
            "t3.large": InstanceSpec("t3.large", 2, 8, 0.0832, "aws", "t3", "3", "large"),
            "t3.xlarge": InstanceSpec("t3.xlarge", 4, 16, 0.1664, "aws", "t3", "3", "xlarge"),
            "t3.2xlarge": InstanceSpec("t3.2xlarge", 8, 32, 0.3328, "aws", "t3", "3", "2xlarge"),
            # M5 - General Purpose
            "m5.large": InstanceSpec("m5.large", 2, 8, 0.096, "aws", "m5", "5", "large"),
            "m5.xlarge": InstanceSpec("m5.xlarge", 4, 16, 0.192, "aws", "m5", "5", "xlarge"),
            "m5.2xlarge": InstanceSpec("m5.2xlarge", 8, 32, 0.384, "aws", "m5", "5", "2xlarge"),
            "m5.4xlarge": InstanceSpec("m5.4xlarge", 16, 64, 0.768, "aws", "m5", "5", "4xlarge"),
            "m5.8xlarge": InstanceSpec("m5.8xlarge", 32, 128, 1.536, "aws", "m5", "5", "8xlarge"),
            # C5 - Compute Optimized
            "c5.large": InstanceSpec("c5.large", 2, 4, 0.085, "aws", "c5", "5", "large"),
            "c5.xlarge": InstanceSpec("c5.xlarge", 4, 8, 0.17, "aws", "c5", "5", "xlarge"),
            "c5.2xlarge": InstanceSpec("c5.2xlarge", 8, 16, 0.34, "aws", "c5", "5", "2xlarge"),
            "c5.4xlarge": InstanceSpec("c5.4xlarge", 16, 32, 0.68, "aws", "c5", "5", "4xlarge"),
            # R5 - Memory Optimized
            "r5.large": InstanceSpec("r5.large", 2, 16, 0.126, "aws", "r5", "5", "large"),
            "r5.xlarge": InstanceSpec("r5.xlarge", 4, 32, 0.252, "aws", "r5", "5", "xlarge"),
            "r5.2xlarge": InstanceSpec("r5.2xlarge", 8, 64, 0.504, "aws", "r5", "5", "2xlarge"),
            "r5.4xlarge": InstanceSpec("r5.4xlarge", 16, 128, 1.008, "aws", "r5", "5", "4xlarge"),
        }
    
    def analyze(
        self,
        utilization_data: list[ResourceUtilization],
    ) -> list[RightsizingRecommendation]:
        """
        Analyze resources and generate rightsizing recommendations.
        
        Args:
            utilization_data: List of resource utilization metrics
            
        Returns:
            List of rightsizing recommendations
        """
        recommendations = []
        
        for util in utilization_data:
            rec = self._analyze_resource(util)
            recommendations.append(rec)
        
        # Sort by savings potential
        recommendations.sort(key=lambda r: r.savings_monthly, reverse=True)
        
        logger.info(
            f"Analyzed {len(utilization_data)} resources, "
            f"{sum(1 for r in recommendations if r.action != RightsizingAction.NO_ACTION)} need action"
        )
        
        return recommendations
    
    def _analyze_resource(
        self,
        util: ResourceUtilization,
    ) -> RightsizingRecommendation:
        """Analyze a single resource for rightsizing."""
        
        # Determine action based on utilization
        action, rationale = self._determine_action(util)
        
        if action == RightsizingAction.NO_ACTION:
            return RightsizingRecommendation(
                resource_id=util.resource_id,
                action=action,
                current_spec=util.current_spec,
                recommended_spec=None,
                utilization=util,
                savings_monthly=0,
                savings_percent=0,
                confidence=0.9,
                rationale=rationale,
            )
        
        if action == RightsizingAction.TERMINATE:
            return RightsizingRecommendation(
                resource_id=util.resource_id,
                action=action,
                current_spec=util.current_spec,
                recommended_spec=None,
                utilization=util,
                savings_monthly=util.current_spec.cost_per_month,
                savings_percent=100,
                confidence=0.85,
                rationale=rationale,
                risks=["Verify resource is truly unused", "Check for scheduled jobs"],
                implementation_steps=[
                    "Verify no active workloads",
                    "Create backup/snapshot if needed",
                    "Terminate instance",
                ],
            )
        
        # Find recommended instance
        recommended = self._find_optimal_instance(util, action)
        
        if recommended is None:
            return RightsizingRecommendation(
                resource_id=util.resource_id,
                action=RightsizingAction.NO_ACTION,
                current_spec=util.current_spec,
                recommended_spec=None,
                utilization=util,
                savings_monthly=0,
                savings_percent=0,
                confidence=0.5,
                rationale="No suitable alternative instance found",
            )
        
        # Calculate savings
        current_cost = util.current_spec.cost_per_month
        recommended_cost = recommended.cost_per_month
        savings_monthly = current_cost - recommended_cost
        savings_percent = (savings_monthly / current_cost * 100) if current_cost > 0 else 0
        
        # Determine risks
        risks = self._assess_risks(util, recommended, action)
        
        # Generate implementation steps
        steps = self._generate_implementation_steps(util, recommended, action)
        
        return RightsizingRecommendation(
            resource_id=util.resource_id,
            action=action,
            current_spec=util.current_spec,
            recommended_spec=recommended,
            utilization=util,
            savings_monthly=savings_monthly,
            savings_percent=savings_percent,
            confidence=self._calculate_confidence(util),
            rationale=rationale,
            risks=risks,
            implementation_steps=steps,
        )
    
    def _determine_action(
        self,
        util: ResourceUtilization,
    ) -> tuple[RightsizingAction, str]:
        """Determine the recommended action based on utilization."""
        
        cpu_avg = util.cpu_avg
        cpu_max = util.cpu_max
        memory_avg = util.memory_avg
        memory_max = util.memory_max
        
        # Check for idle resources
        if cpu_avg < self.thresholds.idle_cpu and memory_avg < self.thresholds.idle_memory:
            return (
                RightsizingAction.TERMINATE,
                f"Resource appears idle (CPU: {cpu_avg:.1f}%, Memory: {memory_avg:.1f}%)"
            )
        
        # Check for overutilized resources
        if cpu_avg > self.thresholds.high_cpu or memory_avg > self.thresholds.high_memory:
            return (
                RightsizingAction.UPSIZE,
                f"Resource is overutilized (CPU: {cpu_avg:.1f}%, Memory: {memory_avg:.1f}%)"
            )
        
        # Check for underutilized resources
        if cpu_max < self.thresholds.low_cpu and memory_max < self.thresholds.low_memory:
            return (
                RightsizingAction.DOWNSIZE,
                f"Resource is underutilized (CPU max: {cpu_max:.1f}%, Memory max: {memory_max:.1f}%)"
            )
        
        # Check for moderate underutilization
        if cpu_avg < self.thresholds.low_cpu and memory_avg < self.thresholds.low_memory:
            return (
                RightsizingAction.DOWNSIZE,
                f"Resource is moderately underutilized (CPU: {cpu_avg:.1f}%, Memory: {memory_avg:.1f}%)"
            )
        
        # Check if instance family could be optimized
        if self._can_optimize_family(util):
            return (
                RightsizingAction.MODIFY_TYPE,
                "Instance family may not be optimal for workload characteristics"
            )
        
        return (
            RightsizingAction.NO_ACTION,
            f"Resource is properly sized (CPU: {cpu_avg:.1f}%, Memory: {memory_avg:.1f}%)"
        )
    
    def _can_optimize_family(self, util: ResourceUtilization) -> bool:
        """Check if instance family can be optimized."""
        current_family = util.current_spec.family
        
        # High CPU, low memory -> compute optimized
        if util.cpu_avg > 50 and util.memory_avg < 30:
            if current_family not in ("c5", "c6i", "c6g"):
                return True
        
        # Low CPU, high memory -> memory optimized
        if util.cpu_avg < 30 and util.memory_avg > 50:
            if current_family not in ("r5", "r6i", "r6g"):
                return True
        
        return False
    
    def _find_optimal_instance(
        self,
        util: ResourceUtilization,
        action: RightsizingAction,
    ) -> Optional[InstanceSpec]:
        """Find the optimal instance for the workload."""
        
        current = util.current_spec
        
        # Calculate required resources with headroom
        if action == RightsizingAction.DOWNSIZE:
            # Size based on max utilization + 30% headroom
            required_vcpus = max(1, int(current.vcpus * (util.cpu_max / 100) * 1.3))
            required_memory = max(0.5, current.memory_gb * (util.memory_max / 100) * 1.3)
        elif action == RightsizingAction.UPSIZE:
            # Size based on average + 50% headroom
            required_vcpus = int(current.vcpus * 1.5)
            required_memory = current.memory_gb * 1.5
        else:
            required_vcpus = current.vcpus
            required_memory = current.memory_gb
        
        # Find suitable instances
        candidates = []
        for spec in self._instance_catalog.values():
            if spec.vcpus >= required_vcpus and spec.memory_gb >= required_memory:
                # Prefer same provider
                if spec.provider == current.provider:
                    candidates.append(spec)
        
        if not candidates:
            return None
        
        # Sort by cost and find cheapest that meets requirements
        candidates.sort(key=lambda s: s.cost_per_hour)
        
        # For downsizing, find cheaper option
        if action == RightsizingAction.DOWNSIZE:
            cheaper = [c for c in candidates if c.cost_per_hour < current.cost_per_hour]
            if cheaper:
                return cheaper[0]
            return None
        
        # For upsizing, find larger option
        if action == RightsizingAction.UPSIZE:
            larger = [
                c for c in candidates
                if c.vcpus >= current.vcpus and c.memory_gb >= current.memory_gb
            ]
            if larger:
                # Return cheapest that's actually larger
                for c in larger:
                    if c.vcpus > current.vcpus or c.memory_gb > current.memory_gb:
                        return c
            return None
        
        return candidates[0] if candidates else None
    
    def _calculate_confidence(self, util: ResourceUtilization) -> float:
        """Calculate confidence in the recommendation."""
        confidence = 0.5
        
        # More data points = higher confidence
        if util.data_points > 1000:
            confidence += 0.2
        elif util.data_points > 100:
            confidence += 0.1
        
        # Longer analysis period = higher confidence
        if util.analysis_period_days >= 14:
            confidence += 0.1
        elif util.analysis_period_days >= 7:
            confidence += 0.05
        
        # Consistent utilization = higher confidence
        if util.cpu_max > 0 and util.cpu_avg > 0:
            cpu_variance = (util.cpu_max - util.cpu_avg) / util.cpu_max
            if cpu_variance < 0.3:
                confidence += 0.1
        
        return min(0.95, confidence)
    
    def _assess_risks(
        self,
        util: ResourceUtilization,
        recommended: InstanceSpec,
        action: RightsizingAction,
    ) -> list[str]:
        """Assess risks of the rightsizing action."""
        risks = []
        
        if action == RightsizingAction.DOWNSIZE:
            # Check if peak utilization is close to new capacity
            if util.cpu_max > 80:
                risks.append("Peak CPU utilization is high; may need capacity during bursts")
            if util.memory_max > 80:
                risks.append("Peak memory utilization is high; may experience OOM")
            
            if util.environment == "production":
                risks.append("Production environment; schedule during maintenance window")
        
        elif action == RightsizingAction.UPSIZE:
            risks.append("Higher cost after resize")
        
        if recommended and recommended.family != util.current_spec.family:
            risks.append("Instance family change may affect application compatibility")
        
        if util.analysis_period_days < 7:
            risks.append("Limited historical data; recommendation may not account for weekly patterns")
        
        return risks
    
    def _generate_implementation_steps(
        self,
        util: ResourceUtilization,
        recommended: InstanceSpec,
        action: RightsizingAction,
    ) -> list[str]:
        """Generate implementation steps for the recommendation."""
        steps = []
        
        if action in (RightsizingAction.DOWNSIZE, RightsizingAction.UPSIZE, RightsizingAction.MODIFY_TYPE):
            steps.extend([
                f"Create snapshot/backup of {util.resource_id}",
                f"Schedule maintenance window",
                f"Stop instance {util.resource_id}",
                f"Change instance type from {util.current_spec.instance_type} to {recommended.instance_type}",
                f"Start instance",
                f"Verify application functionality",
                f"Monitor for 24-48 hours",
            ])
        
        elif action == RightsizingAction.TERMINATE:
            steps.extend([
                f"Verify {util.resource_id} is not in use",
                f"Check with service/team owners",
                f"Create final backup if needed",
                f"Terminate instance",
                f"Update documentation/inventory",
            ])
        
        return steps
    
    def analyze_kubernetes_pods(
        self,
        pod_metrics: list[dict],
    ) -> list[dict]:
        """
        Analyze Kubernetes pod resource requests/limits.
        
        Returns recommendations for pod resource optimization.
        """
        recommendations = []
        
        for pod in pod_metrics:
            pod_name = pod.get("name", "")
            namespace = pod.get("namespace", "")
            
            # Current requests
            cpu_request = pod.get("cpu_request_millicores", 0)
            memory_request = pod.get("memory_request_mb", 0)
            
            # Actual usage
            cpu_usage = pod.get("cpu_usage_millicores", 0)
            memory_usage = pod.get("memory_usage_mb", 0)
            
            # Calculate utilization
            cpu_util = (cpu_usage / cpu_request * 100) if cpu_request > 0 else 0
            memory_util = (memory_usage / memory_request * 100) if memory_request > 0 else 0
            
            rec = {
                "pod": pod_name,
                "namespace": namespace,
                "current_cpu_request": cpu_request,
                "current_memory_request": memory_request,
                "cpu_utilization": cpu_util,
                "memory_utilization": memory_util,
            }
            
            # Check if oversized
            if cpu_util < 20 and memory_util < 30:
                rec["action"] = "reduce_requests"
                rec["recommended_cpu_request"] = max(50, int(cpu_usage * 1.5))
                rec["recommended_memory_request"] = max(64, int(memory_usage * 1.5))
                rec["rationale"] = f"Pod is overprovisioned (CPU: {cpu_util:.1f}%, Memory: {memory_util:.1f}%)"
            elif cpu_util > 90 or memory_util > 90:
                rec["action"] = "increase_requests"
                rec["recommended_cpu_request"] = int(cpu_request * 1.5)
                rec["recommended_memory_request"] = int(memory_request * 1.5)
                rec["rationale"] = f"Pod may be resource constrained (CPU: {cpu_util:.1f}%, Memory: {memory_util:.1f}%)"
            else:
                rec["action"] = "no_change"
                rec["rationale"] = "Pod resources are appropriately sized"
            
            recommendations.append(rec)
        
        return recommendations
    
    def get_summary(
        self,
        recommendations: list[RightsizingRecommendation],
    ) -> dict[str, Any]:
        """Get summary of rightsizing analysis."""
        
        total_current_cost = sum(r.current_spec.cost_per_month for r in recommendations)
        total_recommended_cost = sum(
            r.recommended_spec.cost_per_month if r.recommended_spec else r.current_spec.cost_per_month
            for r in recommendations
        )
        total_savings = total_current_cost - total_recommended_cost
        
        action_counts = {}
        for rec in recommendations:
            action = rec.action.value
            action_counts[action] = action_counts.get(action, 0) + 1
        
        return {
            "total_resources": len(recommendations),
            "resources_needing_action": sum(1 for r in recommendations if r.action != RightsizingAction.NO_ACTION),
            "action_breakdown": action_counts,
            "current_monthly_cost": total_current_cost,
            "recommended_monthly_cost": total_recommended_cost,
            "total_monthly_savings": total_savings,
            "total_annual_savings": total_savings * 12,
            "average_savings_percent": (total_savings / total_current_cost * 100) if total_current_cost > 0 else 0,
        }
