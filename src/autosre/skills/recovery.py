"""
Recovery Planner

Plans and monitors recovery from incidents and cascading failures.

Key insight: You can't recover at normal load when capacity is degraded.
Recovery requires:
1. Reduce load significantly below current capacity
2. Wait for service to stabilize
3. Gradually increase load while monitoring
4. Watch for GC pressure and CPU saturation

Think of it like a traffic jam - you can't fix it by adding more cars.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


class RecoveryStage(Enum):
    """Stages of recovery process."""
    NOT_STARTED = "not_started"
    LOAD_REDUCTION = "load_reduction"
    STABILIZATION = "stabilization"
    GRADUAL_INCREASE = "gradual_increase"
    MONITORING = "monitoring"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class LoadProfile:
    """Current and target load profile."""
    current_load_percent: float      # Current load as % of normal
    target_load_percent: float       # Target load for this stage
    capacity_percent: float          # Current capacity as % of normal
    normal_load_rps: float           # Normal request rate
    current_load_rps: float          # Current request rate
    safe_load_rps: float             # Safe load at current capacity
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "current_load_percent": round(self.current_load_percent, 1),
            "target_load_percent": round(self.target_load_percent, 1),
            "capacity_percent": round(self.capacity_percent, 1),
            "normal_load_rps": round(self.normal_load_rps, 1),
            "current_load_rps": round(self.current_load_rps, 1),
            "safe_load_rps": round(self.safe_load_rps, 1),
        }
    
    @property
    def is_overloaded(self) -> bool:
        """Check if current load exceeds safe capacity."""
        return self.current_load_rps > self.safe_load_rps
    
    @property
    def headroom_percent(self) -> float:
        """Percentage headroom below capacity."""
        if self.safe_load_rps == 0:
            return 0
        return ((self.safe_load_rps - self.current_load_rps) / self.safe_load_rps) * 100


@dataclass
class RecoveryAction:
    """A specific recovery action to take."""
    action_id: str
    action_type: str  # reduce_load, scale_up, wait, increase_load, monitor
    description: str
    
    # Parameters
    target_value: Optional[float] = None
    duration_minutes: Optional[float] = None
    
    # Status
    status: str = "pending"  # pending, in_progress, complete, skipped
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Conditions
    prerequisite_actions: list[str] = field(default_factory=list)
    success_conditions: list[str] = field(default_factory=list)
    abort_conditions: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "description": self.description,
            "target_value": self.target_value,
            "duration_minutes": self.duration_minutes,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "success_conditions": self.success_conditions,
            "abort_conditions": self.abort_conditions,
        }


@dataclass
class RecoveryPlan:
    """Complete recovery plan for a service."""
    plan_id: str
    service: str
    
    # Current state
    stage: RecoveryStage
    load_profile: LoadProfile
    
    # Actions
    actions: list[RecoveryAction] = field(default_factory=list)
    current_action_index: int = 0
    
    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Health checks
    health_checks: list[dict[str, Any]] = field(default_factory=list)
    
    # Results
    success: Optional[bool] = None
    failure_reason: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "service": self.service,
            "stage": self.stage.value,
            "load_profile": self.load_profile.to_dict(),
            "actions": [a.to_dict() for a in self.actions],
            "current_action_index": self.current_action_index,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "estimated_completion": self.estimated_completion.isoformat() if self.estimated_completion else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "success": self.success,
            "failure_reason": self.failure_reason,
        }
    
    @property
    def current_action(self) -> Optional[RecoveryAction]:
        """Get current action being executed."""
        if 0 <= self.current_action_index < len(self.actions):
            return self.actions[self.current_action_index]
        return None
    
    @property
    def progress_percent(self) -> float:
        """Progress through the recovery plan."""
        if not self.actions:
            return 0
        completed = sum(1 for a in self.actions if a.status == "complete")
        return (completed / len(self.actions)) * 100
    
    def get_summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"Recovery Plan: {self.plan_id}",
            f"Service: {self.service}",
            f"Stage: {self.stage.value}",
            f"Progress: {self.progress_percent:.0f}%",
            f"",
            f"Load Profile:",
            f"  Current Load: {self.load_profile.current_load_percent:.0f}% of normal",
            f"  Current Capacity: {self.load_profile.capacity_percent:.0f}% of normal",
            f"  Safe Load: {self.load_profile.safe_load_rps:.0f} RPS",
        ]
        
        if self.current_action:
            lines.extend([
                f"",
                f"Current Action: {self.current_action.description}",
            ])
        
        if self.estimated_completion:
            remaining = self.estimated_completion - datetime.utcnow()
            if remaining.total_seconds() > 0:
                lines.append(f"Estimated Time Remaining: {remaining.total_seconds() / 60:.0f} minutes")
        
        return "\n".join(lines)


class RecoveryPlanner:
    """
    Plans recovery from incidents and cascading failures.
    
    Recovery principles:
    1. Can't recover at normal load when capacity is degraded
    2. Must reduce load significantly below current capacity
    3. Wait for stabilization (queue drain, GC settle)
    4. Gradually increase load (10-20% increments)
    5. Monitor for signs of re-cascade
    """
    
    # Recovery parameters
    DEFAULTS = {
        "initial_load_reduction": 0.3,    # Start at 30% of normal load
        "stabilization_minutes": 5,        # Wait 5 min for stabilization
        "load_increment": 0.1,             # Increase 10% at a time
        "increment_wait_minutes": 2,       # Wait 2 min between increments
        "safe_headroom": 0.2,              # Keep 20% headroom during recovery
    }
    
    # Health check thresholds
    HEALTH_THRESHOLDS = {
        "error_rate_healthy": 0.01,       # <1% errors is healthy
        "cpu_healthy": 70,                 # <70% CPU is healthy
        "gc_pause_healthy_ms": 100,        # <100ms GC pause is healthy
        "queue_wait_healthy_ms": 100,      # <100ms queue wait is healthy
    }
    
    def __init__(self, prometheus_client: Any = None):
        self.prometheus = prometheus_client
    
    def create_plan(
        self,
        service: str,
        current_capacity_percent: float,
        normal_load_rps: float,
        current_load_rps: float,
        plan_id: Optional[str] = None,
    ) -> RecoveryPlan:
        """
        Create a recovery plan for a service.
        
        Args:
            service: Service name
            current_capacity_percent: Current capacity as % of normal (e.g., 50 = half capacity)
            normal_load_rps: Normal request rate in RPS
            current_load_rps: Current request rate
            plan_id: Optional plan ID
        
        Returns:
            RecoveryPlan with staged recovery actions
        """
        plan_id = plan_id or f"recovery-{service}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        # Calculate safe load at current capacity
        # With 20% headroom to avoid re-overload
        safe_capacity = current_capacity_percent * (1 - self.DEFAULTS["safe_headroom"])
        safe_load_rps = normal_load_rps * (safe_capacity / 100)
        
        # Initial target: reduce to 30% of normal (or current capacity - 20%, whichever is lower)
        initial_target_percent = min(
            self.DEFAULTS["initial_load_reduction"] * 100,
            safe_capacity
        )
        
        load_profile = LoadProfile(
            current_load_percent=(current_load_rps / normal_load_rps) * 100 if normal_load_rps > 0 else 0,
            target_load_percent=initial_target_percent,
            capacity_percent=current_capacity_percent,
            normal_load_rps=normal_load_rps,
            current_load_rps=current_load_rps,
            safe_load_rps=safe_load_rps,
        )
        
        # Generate recovery actions
        actions = self._generate_actions(
            service=service,
            load_profile=load_profile,
            target_capacity=100,  # Full recovery
        )
        
        # Estimate completion time
        total_minutes = sum(
            a.duration_minutes or 0 for a in actions
        )
        estimated_completion = datetime.utcnow() + timedelta(minutes=total_minutes)
        
        return RecoveryPlan(
            plan_id=plan_id,
            service=service,
            stage=RecoveryStage.NOT_STARTED,
            load_profile=load_profile,
            actions=actions,
            estimated_completion=estimated_completion,
        )
    
    def _generate_actions(
        self,
        service: str,
        load_profile: LoadProfile,
        target_capacity: float,
    ) -> list[RecoveryAction]:
        """Generate recovery actions based on current state."""
        actions = []
        action_idx = 0
        
        # Action 1: Reduce load
        target_rps = load_profile.normal_load_rps * (load_profile.target_load_percent / 100)
        actions.append(RecoveryAction(
            action_id=f"action-{action_idx}",
            action_type="reduce_load",
            description=f"Reduce load to {load_profile.target_load_percent:.0f}% ({target_rps:.0f} RPS)",
            target_value=target_rps,
            duration_minutes=2,
            success_conditions=[
                f"request_rate < {target_rps * 1.1}",  # Within 10%
                "error_rate < 0.05",
            ],
            abort_conditions=[
                "error_rate > 0.5",
            ],
        ))
        action_idx += 1
        
        # Action 2: Wait for stabilization
        actions.append(RecoveryAction(
            action_id=f"action-{action_idx}",
            action_type="wait",
            description=f"Wait {self.DEFAULTS['stabilization_minutes']} minutes for stabilization",
            duration_minutes=self.DEFAULTS["stabilization_minutes"],
            prerequisite_actions=[f"action-{action_idx - 1}"],
            success_conditions=[
                f"queue_depth < 10",
                f"gc_pause_ms < {self.HEALTH_THRESHOLDS['gc_pause_healthy_ms']}",
                f"error_rate < {self.HEALTH_THRESHOLDS['error_rate_healthy']}",
            ],
            abort_conditions=[
                "error_rate > 0.25",
                "cpu_percent > 90",
            ],
        ))
        action_idx += 1
        
        # Actions 3-N: Gradual load increase
        current_percent = load_profile.target_load_percent
        increment = self.DEFAULTS["load_increment"] * 100
        
        while current_percent < 100:
            next_percent = min(current_percent + increment, 100)
            next_rps = load_profile.normal_load_rps * (next_percent / 100)
            
            # Increase load
            actions.append(RecoveryAction(
                action_id=f"action-{action_idx}",
                action_type="increase_load",
                description=f"Increase load to {next_percent:.0f}% ({next_rps:.0f} RPS)",
                target_value=next_rps,
                duration_minutes=1,
                prerequisite_actions=[f"action-{action_idx - 1}"],
                success_conditions=[
                    f"request_rate >= {next_rps * 0.9}",  # Within 10%
                    f"error_rate < {self.HEALTH_THRESHOLDS['error_rate_healthy']}",
                ],
                abort_conditions=[
                    "error_rate > 0.1",
                    "cpu_percent > 85",
                    f"gc_pause_ms > {self.HEALTH_THRESHOLDS['gc_pause_healthy_ms'] * 2}",
                ],
            ))
            action_idx += 1
            
            # Monitor after increase
            actions.append(RecoveryAction(
                action_id=f"action-{action_idx}",
                action_type="monitor",
                description=f"Monitor at {next_percent:.0f}% load for {self.DEFAULTS['increment_wait_minutes']} minutes",
                duration_minutes=self.DEFAULTS["increment_wait_minutes"],
                prerequisite_actions=[f"action-{action_idx - 1}"],
                success_conditions=[
                    f"error_rate < {self.HEALTH_THRESHOLDS['error_rate_healthy']}",
                    f"cpu_percent < {self.HEALTH_THRESHOLDS['cpu_healthy']}",
                ],
                abort_conditions=[
                    "error_rate > 0.05",
                    "cpu_percent > 85",
                ],
            ))
            action_idx += 1
            
            current_percent = next_percent
        
        # Final action: Confirm recovery
        actions.append(RecoveryAction(
            action_id=f"action-{action_idx}",
            action_type="monitor",
            description="Final health check - confirm recovery complete",
            duration_minutes=5,
            prerequisite_actions=[f"action-{action_idx - 1}"],
            success_conditions=[
                f"error_rate < {self.HEALTH_THRESHOLDS['error_rate_healthy']}",
                f"cpu_percent < {self.HEALTH_THRESHOLDS['cpu_healthy']}",
                f"queue_wait_ms < {self.HEALTH_THRESHOLDS['queue_wait_healthy_ms']}",
            ],
        ))
        
        return actions
    
    async def execute_action(
        self,
        plan: RecoveryPlan,
        action: RecoveryAction,
        load_controller: Any = None,
    ) -> bool:
        """
        Execute a recovery action.
        
        Args:
            plan: The recovery plan
            action: Action to execute
            load_controller: Optional controller for load adjustment
        
        Returns:
            True if action succeeded
        """
        action.status = "in_progress"
        action.started_at = datetime.utcnow()
        
        logger.info(f"Executing recovery action: {action.description}")
        
        try:
            if action.action_type == "reduce_load":
                if load_controller:
                    await load_controller.set_target_rps(action.target_value)
                plan.stage = RecoveryStage.LOAD_REDUCTION
                
            elif action.action_type == "wait":
                plan.stage = RecoveryStage.STABILIZATION
                # Just wait - monitoring happens in check_action_status
                
            elif action.action_type == "increase_load":
                if load_controller:
                    await load_controller.set_target_rps(action.target_value)
                plan.stage = RecoveryStage.GRADUAL_INCREASE
                
            elif action.action_type == "monitor":
                plan.stage = RecoveryStage.MONITORING
            
            # Wait for duration
            if action.duration_minutes:
                import asyncio
                await asyncio.sleep(action.duration_minutes * 60)
            
            # Check success conditions
            success = await self._check_conditions(
                action.success_conditions, plan.service
            )
            
            if success:
                action.status = "complete"
                action.completed_at = datetime.utcnow()
                plan.current_action_index += 1
                return True
            else:
                action.status = "failed"
                return False
                
        except Exception as e:
            logger.error(f"Action failed: {e}")
            action.status = "failed"
            return False
    
    async def check_health(
        self,
        service: str,
    ) -> dict[str, Any]:
        """
        Check service health during recovery.
        
        Returns health status and metrics.
        """
        if not self.prometheus:
            return {"healthy": True, "reason": "No Prometheus client"}
        
        try:
            # Query key metrics
            error_query = f'sum(rate(http_requests_total{{service="{service}",status=~"5.."}}[5m])) / sum(rate(http_requests_total{{service="{service}"}}[5m]))'
            cpu_query = f'avg(rate(container_cpu_usage_seconds_total{{service="{service}"}}[5m])) * 100'
            gc_query = f'rate(jvm_gc_pause_seconds_sum{{service="{service}"}}[5m]) * 1000'
            queue_query = f'histogram_quantile(0.99, rate(request_queue_wait_seconds_bucket{{service="{service}"}}[5m])) * 1000'
            
            error_rate = await self._query_metric(error_query, 0)
            cpu_percent = await self._query_metric(cpu_query, 0)
            gc_pause_ms = await self._query_metric(gc_query, 0)
            queue_wait_ms = await self._query_metric(queue_query, 0)
            
            # Evaluate health
            issues = []
            
            if error_rate > self.HEALTH_THRESHOLDS["error_rate_healthy"]:
                issues.append(f"High error rate: {error_rate * 100:.1f}%")
            
            if cpu_percent > self.HEALTH_THRESHOLDS["cpu_healthy"]:
                issues.append(f"High CPU: {cpu_percent:.0f}%")
            
            if gc_pause_ms > self.HEALTH_THRESHOLDS["gc_pause_healthy_ms"]:
                issues.append(f"GC pressure: {gc_pause_ms:.0f}ms pauses")
            
            if queue_wait_ms > self.HEALTH_THRESHOLDS["queue_wait_healthy_ms"]:
                issues.append(f"Queue backlog: {queue_wait_ms:.0f}ms wait")
            
            return {
                "healthy": len(issues) == 0,
                "issues": issues,
                "metrics": {
                    "error_rate": error_rate,
                    "cpu_percent": cpu_percent,
                    "gc_pause_ms": gc_pause_ms,
                    "queue_wait_ms": queue_wait_ms,
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "healthy": False,
                "issues": [f"Health check error: {e}"],
                "metrics": {},
                "timestamp": datetime.utcnow().isoformat(),
            }
    
    async def should_abort(
        self,
        plan: RecoveryPlan,
    ) -> tuple[bool, str]:
        """
        Check if recovery should be aborted.
        
        Returns (should_abort, reason).
        """
        if not plan.current_action:
            return False, ""
        
        action = plan.current_action
        
        # Check abort conditions
        for condition in action.abort_conditions:
            triggered = await self._check_condition(condition, plan.service)
            if triggered:
                return True, f"Abort condition triggered: {condition}"
        
        return False, ""
    
    async def _check_conditions(
        self,
        conditions: list[str],
        service: str,
    ) -> bool:
        """Check if all conditions are met."""
        for condition in conditions:
            met = await self._check_condition(condition, service)
            if not met:
                return False
        return True
    
    async def _check_condition(
        self,
        condition: str,
        service: str,
    ) -> bool:
        """
        Check a single condition.
        
        Condition format: "metric_name < threshold" or "metric_name > threshold"
        """
        import re
        
        match = re.match(r'(\w+)\s*([<>]=?)\s*([\d.]+)', condition)
        if not match:
            logger.warning(f"Invalid condition format: {condition}")
            return True  # Skip invalid conditions
        
        metric_name, operator, threshold = match.groups()
        threshold = float(threshold)
        
        # Get metric value
        value = await self._get_metric_value(metric_name, service)
        if value is None:
            return True  # Skip if metric unavailable
        
        # Evaluate condition
        if operator == "<":
            return value < threshold
        elif operator == "<=":
            return value <= threshold
        elif operator == ">":
            return value > threshold
        elif operator == ">=":
            return value >= threshold
        
        return True
    
    async def _get_metric_value(
        self,
        metric_name: str,
        service: str,
    ) -> Optional[float]:
        """Get current value of a metric."""
        if not self.prometheus:
            return None
        
        query_map = {
            "error_rate": f'sum(rate(http_requests_total{{service="{service}",status=~"5.."}}[5m])) / sum(rate(http_requests_total{{service="{service}"}}[5m]))',
            "cpu_percent": f'avg(rate(container_cpu_usage_seconds_total{{service="{service}"}}[5m])) * 100',
            "gc_pause_ms": f'rate(jvm_gc_pause_seconds_sum{{service="{service}"}}[5m]) * 1000',
            "queue_depth": f'sum(request_queue_depth{{service="{service}"}})',
            "queue_wait_ms": f'histogram_quantile(0.99, rate(request_queue_wait_seconds_bucket{{service="{service}"}}[5m])) * 1000',
            "request_rate": f'sum(rate(http_requests_total{{service="{service}"}}[5m]))',
        }
        
        query = query_map.get(metric_name)
        if not query:
            logger.warning(f"Unknown metric: {metric_name}")
            return None
        
        return await self._query_metric(query, None)
    
    async def _query_metric(
        self,
        query: str,
        default: Any,
    ) -> Any:
        """Query Prometheus for a metric value."""
        try:
            result = await self.prometheus.query(query)
            return self._extract_value(result, default)
        except Exception as e:
            logger.warning(f"Query failed: {e}")
            return default
    
    def _extract_value(self, result: Any, default: Any) -> Any:
        """Extract scalar value from Prometheus result."""
        try:
            if isinstance(result, dict):
                if "data" in result and "result" in result["data"]:
                    data = result["data"]["result"]
                    if data and len(data) > 0:
                        return float(data[0]["value"][1])
            elif isinstance(result, (int, float)):
                return float(result)
        except (KeyError, IndexError, TypeError, ValueError):
            pass
        return default
    
    def get_load_reduction_commands(
        self,
        service: str,
        target_percent: float,
    ) -> list[dict[str, Any]]:
        """
        Generate commands for reducing load.
        
        Returns platform-specific commands (Kubernetes, etc.)
        """
        return [
            {
                "platform": "kubernetes",
                "type": "hpa_scale",
                "command": f"kubectl patch hpa {service} -p '{{\"spec\":{{\"minReplicas\":1,\"maxReplicas\":1}}}}'",
                "description": "Disable autoscaling to prevent scale-up during recovery",
            },
            {
                "platform": "istio",
                "type": "traffic_shift",
                "command": f"istioctl traffic --service {service} --percentage {target_percent}",
                "description": f"Reduce traffic to {target_percent}% using Istio",
            },
            {
                "platform": "envoy",
                "type": "rate_limit",
                "description": f"Configure rate limiting to {target_percent}% of normal capacity",
            },
            {
                "platform": "nginx",
                "type": "upstream_weight",
                "description": f"Reduce upstream weight to achieve {target_percent}% traffic",
            },
        ]
