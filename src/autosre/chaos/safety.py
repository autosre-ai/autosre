"""
Safety Checks and Blast Radius Control

Provides safety mechanisms to prevent chaos experiments
from causing unintended damage.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field


class SafetyLevel(str, Enum):
    """Safety enforcement levels."""
    
    PERMISSIVE = "permissive"  # Log warnings only
    STANDARD = "standard"      # Block dangerous experiments
    STRICT = "strict"          # Require explicit approval


class BlastRadiusConfig(BaseModel):
    """Configuration for blast radius limits."""
    
    # Pod limits
    max_pods_affected: int = Field(default=10, ge=1)
    max_pods_percentage: int = Field(default=50, ge=1, le=100)
    
    # Node limits
    max_nodes_affected: int = Field(default=3, ge=1)
    max_nodes_percentage: int = Field(default=30, ge=1, le=100)
    
    # Service limits
    max_services_affected: int = Field(default=5, ge=1)
    
    # Namespace restrictions
    allowed_namespaces: list[str] = Field(default_factory=list)
    blocked_namespaces: list[str] = Field(
        default_factory=lambda: ["kube-system", "kube-public", "cert-manager", "istio-system"]
    )
    
    # Label restrictions
    protected_labels: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "app.kubernetes.io/part-of": ["infrastructure", "monitoring"],
            "tier": ["critical"],
        }
    )
    
    # Time restrictions
    allowed_hours: tuple[int, int] = Field(
        default=(9, 17), description="Allowed hours (24h format)"
    )
    blocked_days: list[int] = Field(
        default_factory=lambda: [5, 6], description="Blocked days (0=Mon, 6=Sun)"
    )
    
    # Duration limits
    max_experiment_duration_minutes: int = Field(default=60)
    max_total_chaos_duration_minutes: int = Field(default=120)


@dataclass
class BlastRadius:
    """Calculated blast radius for an experiment."""
    
    pods_affected: int = 0
    pods_percentage: float = 0.0
    nodes_affected: int = 0
    nodes_percentage: float = 0.0
    services_affected: int = 0
    namespaces_affected: list[str] = field(default_factory=list)
    
    # Details
    affected_pods: list[str] = field(default_factory=list)
    affected_nodes: list[str] = field(default_factory=list)
    affected_services: list[str] = field(default_factory=list)
    
    # Risk assessment
    risk_level: str = "low"  # low, medium, high, critical
    risk_factors: list[str] = field(default_factory=list)
    
    def calculate_risk(self) -> str:
        """Calculate risk level based on blast radius."""
        if self.pods_affected > 50 or self.nodes_affected > 5:
            self.risk_level = "critical"
        elif self.pods_affected > 20 or self.nodes_affected > 3:
            self.risk_level = "high"
        elif self.pods_affected > 10 or self.services_affected > 3:
            self.risk_level = "medium"
        else:
            self.risk_level = "low"
        return self.risk_level
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pods_affected": self.pods_affected,
            "pods_percentage": self.pods_percentage,
            "nodes_affected": self.nodes_affected,
            "nodes_percentage": self.nodes_percentage,
            "services_affected": self.services_affected,
            "namespaces_affected": self.namespaces_affected,
            "risk_level": self.risk_level,
            "risk_factors": self.risk_factors,
        }


class SafetyRule(BaseModel):
    """A safety rule to check before experiment execution."""
    
    id: str
    name: str
    description: str = ""
    enabled: bool = True
    
    # Rule type
    rule_type: str = Field(
        default="builtin", description="builtin, custom, or approval"
    )
    
    # Conditions
    check_expression: str = Field(
        default="", description="Expression to evaluate for custom rules"
    )
    
    # Actions
    action_on_violation: str = Field(
        default="block", description="block, warn, or require_approval"
    )
    
    # Metadata
    severity: str = Field(default="high", description="low, medium, high, critical")
    category: str = Field(default="general")


@dataclass
class SafetyViolation:
    """A safety rule violation."""
    
    rule_id: str
    rule_name: str
    message: str
    severity: str = "high"
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Resolution
    can_override: bool = False
    override_requires: str = ""  # Role or approval process
    was_overridden: bool = False
    overridden_by: Optional[str] = None


class SafetyPolicy(BaseModel):
    """Overall safety policy configuration."""
    
    name: str = "default"
    level: SafetyLevel = SafetyLevel.STANDARD
    
    # Blast radius
    blast_radius: BlastRadiusConfig = Field(default_factory=BlastRadiusConfig)
    
    # Rules
    rules: list[SafetyRule] = Field(default_factory=list)
    
    # Approvals
    require_approval_for: list[str] = Field(
        default_factory=lambda: ["production", "critical-systems"]
    )
    approvers: list[str] = Field(default_factory=list)
    approval_timeout_minutes: int = Field(default=60)
    
    # Circuit breaker
    enable_circuit_breaker: bool = True
    circuit_breaker_threshold: int = Field(
        default=3, description="Failures before circuit opens"
    )
    circuit_breaker_timeout_minutes: int = Field(default=30)
    
    # Monitoring integration
    alert_on_experiment_start: bool = True
    alert_on_violation: bool = True
    alert_channels: list[str] = Field(default_factory=list)


class CircuitBreaker:
    """Circuit breaker for chaos experiments.
    
    Automatically stops experiments if too many failures occur.
    """
    
    def __init__(
        self,
        threshold: int = 3,
        timeout_minutes: int = 30,
    ):
        self.threshold = threshold
        self.timeout_minutes = timeout_minutes
        
        self._failure_count: int = 0
        self._is_open: bool = False
        self._opened_at: Optional[datetime] = None
        self._failure_timestamps: list[datetime] = []
    
    def record_success(self) -> None:
        """Record a successful experiment."""
        self._failure_count = 0
        self._failure_timestamps.clear()
    
    def record_failure(self) -> bool:
        """Record a failed experiment. Returns True if circuit opens."""
        now = datetime.utcnow()
        self._failure_timestamps.append(now)
        
        # Only count recent failures (within timeout window)
        cutoff = now - timedelta(minutes=self.timeout_minutes)
        self._failure_timestamps = [
            ts for ts in self._failure_timestamps if ts > cutoff
        ]
        
        self._failure_count = len(self._failure_timestamps)
        
        if self._failure_count >= self.threshold:
            self._open()
            return True
        return False
    
    def is_open(self) -> bool:
        """Check if circuit breaker is open."""
        if not self._is_open:
            return False
        
        # Check if timeout has elapsed
        if self._opened_at:
            elapsed = datetime.utcnow() - self._opened_at
            if elapsed > timedelta(minutes=self.timeout_minutes):
                self._close()
                return False
        
        return True
    
    def get_status(self) -> dict[str, Any]:
        """Get circuit breaker status."""
        remaining_minutes = 0
        if self._is_open and self._opened_at:
            elapsed = datetime.utcnow() - self._opened_at
            remaining = timedelta(minutes=self.timeout_minutes) - elapsed
            remaining_minutes = max(0, remaining.total_seconds() / 60)
        
        return {
            "is_open": self._is_open,
            "failure_count": self._failure_count,
            "threshold": self.threshold,
            "remaining_minutes": remaining_minutes,
        }
    
    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        self._close()
        self._failure_count = 0
        self._failure_timestamps.clear()
    
    def _open(self) -> None:
        """Open the circuit breaker."""
        self._is_open = True
        self._opened_at = datetime.utcnow()
    
    def _close(self) -> None:
        """Close the circuit breaker."""
        self._is_open = False
        self._opened_at = None


@dataclass
class RollbackTrigger:
    """Defines conditions for automatic rollback."""
    
    name: str
    description: str = ""
    enabled: bool = True
    
    # Trigger conditions
    metric_query: str = ""  # PromQL or similar
    threshold: float = 0.0
    comparison: str = ">"  # >, <, >=, <=, ==, !=
    duration_seconds: int = 60  # Condition must hold for this duration
    
    # Rollback action
    rollback_type: str = "immediate"  # immediate, graceful
    notify_before_rollback: bool = True
    
    def evaluate(self, metric_value: float) -> bool:
        """Evaluate if trigger condition is met."""
        ops = {
            ">": lambda a, b: a > b,
            "<": lambda a, b: a < b,
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
        }
        return ops.get(self.comparison, lambda a, b: False)(
            metric_value, self.threshold
        )


class SafetyChecker:
    """Validates experiments against safety policies."""
    
    def __init__(
        self,
        policy: Optional[SafetyPolicy] = None,
        kubernetes_client: Optional[Any] = None,
        notify_callback: Optional[Callable[[str, str], None]] = None,
    ):
        self.policy = policy or SafetyPolicy()
        self.kubernetes_client = kubernetes_client
        self.notify_callback = notify_callback
        
        # Circuit breaker
        self.circuit_breaker = CircuitBreaker(
            threshold=self.policy.circuit_breaker_threshold,
            timeout_minutes=self.policy.circuit_breaker_timeout_minutes,
        ) if self.policy.enable_circuit_breaker else None
        
        # Rollback triggers
        self.rollback_triggers: list[RollbackTrigger] = []
        
        # Audit log
        self._audit_log: list[dict[str, Any]] = []
    
    async def validate(
        self,
        experiment: Any,  # ChaosExperiment
        override_user: Optional[str] = None,
    ) -> tuple[bool, list[SafetyViolation]]:
        """Validate an experiment against safety rules.
        
        Returns (is_valid, violations).
        """
        violations: list[SafetyViolation] = []
        
        # Check circuit breaker first
        if self.circuit_breaker and self.circuit_breaker.is_open():
            violations.append(SafetyViolation(
                rule_id="circuit-breaker",
                rule_name="Circuit Breaker Open",
                message="Circuit breaker is open due to recent failures",
                severity="critical",
                can_override=True,
                override_requires="admin",
            ))
            return False, violations
        
        # Check time restrictions
        time_violation = self._check_time_restrictions()
        if time_violation:
            violations.append(time_violation)
        
        # Check namespace restrictions
        ns_violation = self._check_namespace_restrictions(experiment)
        if ns_violation:
            violations.append(ns_violation)
        
        # Calculate and check blast radius
        blast_radius = await self._calculate_blast_radius(experiment)
        br_violations = self._check_blast_radius(blast_radius)
        violations.extend(br_violations)
        
        # Check protected resources
        protected_violations = await self._check_protected_resources(experiment)
        violations.extend(protected_violations)
        
        # Check custom rules
        for rule in self.policy.rules:
            if rule.enabled:
                violation = await self._check_custom_rule(rule, experiment)
                if violation:
                    violations.append(violation)
        
        # Check duration limits
        duration_violation = self._check_duration_limits(experiment)
        if duration_violation:
            violations.append(duration_violation)
        
        # Log audit entry
        self._log_audit(
            experiment=experiment,
            violations=violations,
            override_user=override_user,
        )
        
        # Determine if valid based on policy level
        is_valid = True
        for violation in violations:
            if self.policy.level == SafetyLevel.PERMISSIVE:
                # Log warning but allow
                pass
            elif self.policy.level == SafetyLevel.STANDARD:
                # Block high/critical violations
                if violation.severity in ("high", "critical"):
                    is_valid = False
            else:  # STRICT
                # Block all violations
                is_valid = False
        
        # Handle overrides
        if not is_valid and override_user:
            can_override_all = all(v.can_override for v in violations)
            if can_override_all:
                # Check if user can override
                # In real implementation, verify user permissions
                is_valid = True
                for v in violations:
                    v.was_overridden = True
                    v.overridden_by = override_user
        
        # Notify on violations
        if violations and self.policy.alert_on_violation:
            await self._notify_violations(experiment, violations)
        
        return is_valid, violations
    
    def add_rollback_trigger(self, trigger: RollbackTrigger) -> None:
        """Add a rollback trigger."""
        self.rollback_triggers.append(trigger)
    
    async def check_rollback_triggers(
        self,
        metrics: dict[str, float],
    ) -> Optional[RollbackTrigger]:
        """Check if any rollback trigger is activated."""
        for trigger in self.rollback_triggers:
            if not trigger.enabled:
                continue
            
            metric_value = metrics.get(trigger.metric_query)
            if metric_value is not None and trigger.evaluate(metric_value):
                return trigger
        
        return None
    
    def record_experiment_result(self, success: bool) -> None:
        """Record experiment result for circuit breaker."""
        if self.circuit_breaker:
            if success:
                self.circuit_breaker.record_success()
            else:
                if self.circuit_breaker.record_failure():
                    self._notify_sync(
                        "safety",
                        "🔴 Circuit breaker opened due to repeated failures"
                    )
    
    def get_audit_log(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent audit log entries."""
        return self._audit_log[-limit:]
    
    def _check_time_restrictions(self) -> Optional[SafetyViolation]:
        """Check if current time is within allowed window."""
        now = datetime.utcnow()
        
        # Check day of week
        if now.weekday() in self.policy.blast_radius.blocked_days:
            return SafetyViolation(
                rule_id="time-restriction-day",
                rule_name="Blocked Day",
                message=f"Chaos experiments are not allowed on day {now.weekday()}",
                severity="medium",
                can_override=True,
                override_requires="manager",
            )
        
        # Check hour
        start_hour, end_hour = self.policy.blast_radius.allowed_hours
        if not (start_hour <= now.hour < end_hour):
            return SafetyViolation(
                rule_id="time-restriction-hour",
                rule_name="Outside Allowed Hours",
                message=f"Current hour {now.hour} is outside allowed range {start_hour}-{end_hour}",
                severity="medium",
                can_override=True,
                override_requires="manager",
            )
        
        return None
    
    def _check_namespace_restrictions(self, experiment: Any) -> Optional[SafetyViolation]:
        """Check namespace restrictions."""
        target_namespaces = []
        if hasattr(experiment, "config") and hasattr(experiment.config, "target"):
            target_namespaces = experiment.config.target.namespaces or []
        
        blocked = self.policy.blast_radius.blocked_namespaces
        for ns in target_namespaces:
            if ns in blocked:
                return SafetyViolation(
                    rule_id="namespace-blocked",
                    rule_name="Blocked Namespace",
                    message=f"Namespace '{ns}' is blocked for chaos experiments",
                    severity="critical",
                    details={"namespace": ns, "blocked_list": blocked},
                    can_override=False,
                )
        
        # Check allowed list if specified
        allowed = self.policy.blast_radius.allowed_namespaces
        if allowed:
            for ns in target_namespaces:
                if ns not in allowed:
                    return SafetyViolation(
                        rule_id="namespace-not-allowed",
                        rule_name="Namespace Not Allowed",
                        message=f"Namespace '{ns}' is not in the allowed list",
                        severity="high",
                        can_override=True,
                        override_requires="admin",
                    )
        
        return None
    
    async def _calculate_blast_radius(self, experiment: Any) -> BlastRadius:
        """Calculate the blast radius of an experiment."""
        blast = BlastRadius()
        
        if not hasattr(experiment, "config"):
            return blast
        
        target = getattr(experiment.config, "target", None)
        if not target:
            return blast
        
        # In real implementation, query Kubernetes to get actual counts
        # For now, estimate based on selector
        
        if target.pods:
            blast.affected_pods = target.pods
            blast.pods_affected = len(target.pods)
        elif target.label_selectors:
            # Estimate - would query K8s in real implementation
            blast.pods_affected = 5  # Default estimate
            blast.pods_percentage = 10.0
        
        if target.mode == "all":
            blast.pods_percentage = 100.0
            blast.risk_factors.append("Targets all matching pods")
        elif target.mode == "fixed-percent":
            try:
                blast.pods_percentage = float(target.value)
            except (ValueError, TypeError):
                pass
        
        blast.namespaces_affected = target.namespaces or ["default"]
        blast.calculate_risk()
        
        return blast
    
    def _check_blast_radius(self, blast: BlastRadius) -> list[SafetyViolation]:
        """Check if blast radius exceeds limits."""
        violations = []
        limits = self.policy.blast_radius
        
        if blast.pods_affected > limits.max_pods_affected:
            violations.append(SafetyViolation(
                rule_id="blast-radius-pods",
                rule_name="Pod Limit Exceeded",
                message=f"Affects {blast.pods_affected} pods, limit is {limits.max_pods_affected}",
                severity="high",
                details=blast.to_dict(),
                can_override=True,
                override_requires="admin",
            ))
        
        if blast.pods_percentage > limits.max_pods_percentage:
            violations.append(SafetyViolation(
                rule_id="blast-radius-pods-percent",
                rule_name="Pod Percentage Exceeded",
                message=f"Affects {blast.pods_percentage}% of pods, limit is {limits.max_pods_percentage}%",
                severity="high",
                details=blast.to_dict(),
                can_override=True,
                override_requires="admin",
            ))
        
        if blast.nodes_affected > limits.max_nodes_affected:
            violations.append(SafetyViolation(
                rule_id="blast-radius-nodes",
                rule_name="Node Limit Exceeded",
                message=f"Affects {blast.nodes_affected} nodes, limit is {limits.max_nodes_affected}",
                severity="critical",
                details=blast.to_dict(),
                can_override=False,
            ))
        
        if blast.services_affected > limits.max_services_affected:
            violations.append(SafetyViolation(
                rule_id="blast-radius-services",
                rule_name="Service Limit Exceeded",
                message=f"Affects {blast.services_affected} services, limit is {limits.max_services_affected}",
                severity="high",
                can_override=True,
            ))
        
        return violations
    
    async def _check_protected_resources(self, experiment: Any) -> list[SafetyViolation]:
        """Check if experiment targets protected resources."""
        violations = []
        
        if not hasattr(experiment, "config"):
            return violations
        
        target = getattr(experiment.config, "target", None)
        if not target:
            return violations
        
        protected_labels = self.policy.blast_radius.protected_labels
        target_labels = target.label_selectors or {}
        
        for label_key, protected_values in protected_labels.items():
            if label_key in target_labels:
                target_value = target_labels[label_key]
                if target_value in protected_values:
                    violations.append(SafetyViolation(
                        rule_id=f"protected-label-{label_key}",
                        rule_name="Protected Resource",
                        message=f"Cannot target resources with {label_key}={target_value}",
                        severity="critical",
                        details={"label": label_key, "value": target_value},
                        can_override=False,
                    ))
        
        return violations
    
    async def _check_custom_rule(
        self,
        rule: SafetyRule,
        experiment: Any,
    ) -> Optional[SafetyViolation]:
        """Evaluate a custom safety rule."""
        if rule.rule_type != "custom" or not rule.check_expression:
            return None
        
        # In a real implementation, we would evaluate the expression
        # against the experiment configuration
        # For now, return None (no violation)
        return None
    
    def _check_duration_limits(self, experiment: Any) -> Optional[SafetyViolation]:
        """Check experiment duration limits."""
        if not hasattr(experiment, "config"):
            return None
        
        schedule = getattr(experiment.config, "schedule", None)
        if not schedule:
            return None
        
        max_duration = self.policy.blast_radius.max_experiment_duration_minutes
        
        duration_seconds = schedule.get_duration_seconds()
        duration_minutes = duration_seconds / 60
        
        if duration_minutes > max_duration:
            return SafetyViolation(
                rule_id="duration-limit",
                rule_name="Duration Limit Exceeded",
                message=f"Duration {duration_minutes:.1f}m exceeds limit of {max_duration}m",
                severity="medium",
                can_override=True,
                override_requires="manager",
            )
        
        return None
    
    def _log_audit(
        self,
        experiment: Any,
        violations: list[SafetyViolation],
        override_user: Optional[str],
    ) -> None:
        """Log audit entry."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "experiment_id": getattr(experiment, "id", "unknown"),
            "experiment_name": getattr(experiment, "name", "unknown"),
            "violations_count": len(violations),
            "violations": [
                {
                    "rule_id": v.rule_id,
                    "rule_name": v.rule_name,
                    "severity": v.severity,
                    "overridden": v.was_overridden,
                }
                for v in violations
            ],
            "override_user": override_user,
        }
        self._audit_log.append(entry)
        
        # Keep only last 1000 entries
        if len(self._audit_log) > 1000:
            self._audit_log = self._audit_log[-1000:]
    
    async def _notify_violations(
        self,
        experiment: Any,
        violations: list[SafetyViolation],
    ) -> None:
        """Send notifications about violations."""
        if not self.notify_callback:
            return
        
        severity_emoji = {
            "low": "ℹ️",
            "medium": "⚠️",
            "high": "🔶",
            "critical": "🔴",
        }
        
        message_parts = [
            f"Safety violations for experiment '{getattr(experiment, 'name', 'unknown')}':",
        ]
        
        for v in violations:
            emoji = severity_emoji.get(v.severity, "❓")
            message_parts.append(f"{emoji} [{v.severity}] {v.rule_name}: {v.message}")
        
        message = "\n".join(message_parts)
        self.notify_callback("safety", message)
    
    def _notify_sync(self, channel: str, message: str) -> None:
        """Synchronous notification (for circuit breaker)."""
        if self.notify_callback:
            self.notify_callback(channel, message)


# =============================================================================
# Pre-built Safety Policies
# =============================================================================

def default_safety_policy() -> SafetyPolicy:
    """Create a default safety policy."""
    return SafetyPolicy(
        name="default",
        level=SafetyLevel.STANDARD,
        blast_radius=BlastRadiusConfig(
            max_pods_affected=10,
            max_pods_percentage=50,
            max_nodes_affected=3,
            blocked_namespaces=["kube-system", "kube-public", "monitoring", "istio-system"],
            allowed_hours=(9, 17),
            blocked_days=[5, 6],  # Saturday, Sunday
        ),
        enable_circuit_breaker=True,
        circuit_breaker_threshold=3,
        alert_on_experiment_start=True,
        alert_on_violation=True,
    )


def production_safety_policy() -> SafetyPolicy:
    """Create a strict production safety policy."""
    return SafetyPolicy(
        name="production",
        level=SafetyLevel.STRICT,
        blast_radius=BlastRadiusConfig(
            max_pods_affected=5,
            max_pods_percentage=25,
            max_nodes_affected=1,
            max_nodes_percentage=10,
            max_services_affected=2,
            blocked_namespaces=[
                "kube-system", "kube-public", "monitoring",
                "istio-system", "cert-manager", "production-critical",
            ],
            protected_labels={
                "tier": ["critical", "database"],
                "app.kubernetes.io/part-of": ["infrastructure", "payment"],
            },
            allowed_hours=(10, 16),  # Narrower window
            blocked_days=[4, 5, 6],  # Friday, Saturday, Sunday
            max_experiment_duration_minutes=30,
        ),
        rules=[
            SafetyRule(
                id="require-approval",
                name="Require Approval",
                description="All production experiments require approval",
                rule_type="approval",
                action_on_violation="require_approval",
                severity="high",
            ),
        ],
        require_approval_for=["production", "staging"],
        enable_circuit_breaker=True,
        circuit_breaker_threshold=2,
        circuit_breaker_timeout_minutes=60,
        alert_on_experiment_start=True,
        alert_on_violation=True,
    )


def development_safety_policy() -> SafetyPolicy:
    """Create a permissive development safety policy."""
    return SafetyPolicy(
        name="development",
        level=SafetyLevel.PERMISSIVE,
        blast_radius=BlastRadiusConfig(
            max_pods_affected=50,
            max_pods_percentage=100,
            max_nodes_affected=10,
            blocked_namespaces=["kube-system", "kube-public"],
            allowed_hours=(0, 24),  # All hours
            blocked_days=[],  # No blocked days
            max_experiment_duration_minutes=120,
        ),
        enable_circuit_breaker=False,
        alert_on_experiment_start=False,
        alert_on_violation=False,
    )
