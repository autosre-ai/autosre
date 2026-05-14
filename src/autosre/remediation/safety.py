"""
Safety Checker for remediation actions.

Performs pre-flight checks, blast radius assessment, and safety validation
before allowing remediation actions to execute.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Awaitable
from uuid import UUID

from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger

from .models import (
    RemediationAction,
    ActionDefinition,
    RiskLevel,
    SafetyCheckResult,
    SafetyCheckType,
    BlastRadius,
)

logger = get_logger(__name__)


class SafetyViolation(BaseModel):
    """A safety violation detected during checks."""
    
    check_name: str
    severity: RiskLevel
    message: str
    is_blocking: bool = True
    recommendation: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class SafetyPolicy(BaseModel):
    """Policy configuration for safety checks."""
    
    name: str
    description: str = ""
    
    # Risk thresholds
    max_risk_level: RiskLevel = RiskLevel.HIGH
    max_blast_radius_pods: int = 50
    max_blast_radius_nodes: int = 5
    max_downtime_risk: float = 0.5
    max_data_loss_risk: float = 0.0
    
    # Time restrictions
    blocked_hours: list[int] = Field(default_factory=list)  # Hours when actions blocked
    blocked_days: list[int] = Field(default_factory=list)   # Days of week (0=Monday)
    
    # Rate limiting
    max_actions_per_hour: int = 100
    max_actions_per_target: int = 5
    cooldown_between_actions_seconds: int = 60
    
    # Approval requirements
    require_approval_above_risk: RiskLevel = RiskLevel.HIGH
    require_approval_for_namespaces: list[str] = Field(
        default_factory=lambda: ["production", "prod", "kube-system"]
    )
    
    # Exclusions
    protected_namespaces: list[str] = Field(
        default_factory=lambda: ["kube-system", "kube-public", "istio-system"]
    )
    protected_deployments: list[str] = Field(default_factory=list)
    protected_services: list[str] = Field(default_factory=list)
    
    # Dry run requirements
    require_dry_run_first: bool = False
    
    def is_namespace_protected(self, namespace: str) -> bool:
        """Check if namespace is protected."""
        return namespace in self.protected_namespaces
    
    def is_deployment_protected(self, deployment: str) -> bool:
        """Check if deployment is protected."""
        return deployment in self.protected_deployments
    
    def is_blocked_time(self) -> tuple[bool, str]:
        """Check if current time is blocked."""
        now = datetime.utcnow()
        
        if now.weekday() in self.blocked_days:
            return True, f"Day of week {now.weekday()} is blocked"
        
        if now.hour in self.blocked_hours:
            return True, f"Hour {now.hour} is blocked"
        
        return False, ""


# Type for custom check functions
SafetyCheckFunc = Callable[[RemediationAction, SafetyPolicy], Awaitable[SafetyCheckResult]]


class SafetyChecker:
    """
    Performs safety checks on remediation actions.
    
    Features:
    - Pre-flight checks before execution
    - Blast radius assessment
    - Protected resource detection
    - Time-based restrictions
    - Rate limiting
    - Custom safety checks
    
    Example:
        checker = SafetyChecker()
        
        # Configure policy
        policy = SafetyPolicy(
            name="production",
            max_risk_level=RiskLevel.MEDIUM,
            protected_namespaces=["production", "kube-system"],
        )
        checker.set_policy(policy)
        
        # Check action
        results = await checker.check_action(action)
        if not checker.is_safe(results):
            violations = checker.get_violations(results)
            ...
    """
    
    def __init__(
        self,
        policy: SafetyPolicy | None = None,
    ):
        self._policy = policy or SafetyPolicy(name="default")
        self._custom_checks: dict[str, SafetyCheckFunc] = {}
        
        # Rate limiting state
        self._action_timestamps: list[datetime] = []
        self._target_action_counts: dict[str, list[datetime]] = {}
        
        # Action history for cooldown
        self._last_action_per_target: dict[str, datetime] = {}
        
        self._lock = asyncio.Lock()
        
        # Register built-in checks
        self._builtin_checks = [
            self._check_risk_level,
            self._check_protected_resources,
            self._check_blast_radius,
            self._check_time_restrictions,
            self._check_rate_limits,
            self._check_cooldown,
            self._check_destructive_action,
            self._check_dry_run_requirement,
        ]
    
    @property
    def policy(self) -> SafetyPolicy:
        """Get current safety policy."""
        return self._policy
    
    def set_policy(self, policy: SafetyPolicy) -> None:
        """Set the safety policy."""
        self._policy = policy
        logger.info(f"Set safety policy: {policy.name}")
    
    def register_check(
        self,
        name: str,
        check_func: SafetyCheckFunc,
    ) -> None:
        """
        Register a custom safety check.
        
        Args:
            name: Check name
            check_func: Async function that performs the check
        """
        self._custom_checks[name] = check_func
        logger.info(f"Registered custom safety check: {name}")
    
    async def check_action(
        self,
        action: RemediationAction,
        definition: ActionDefinition | None = None,
    ) -> list[SafetyCheckResult]:
        """
        Run all safety checks on an action.
        
        Args:
            action: The remediation action to check
            definition: Optional action definition for additional context
            
        Returns:
            List of check results
        """
        results = []
        
        # Run built-in checks
        for check_func in self._builtin_checks:
            try:
                start = datetime.utcnow()
                result = await check_func(action)
                duration_ms = (datetime.utcnow() - start).total_seconds() * 1000
                result.duration_ms = duration_ms
                results.append(result)
            except Exception as e:
                logger.error(f"Safety check failed: {e}", exc_info=True)
                results.append(SafetyCheckResult(
                    check_type=SafetyCheckType.PRE_FLIGHT,
                    check_name=check_func.__name__,
                    passed=False,
                    message=f"Check failed with error: {str(e)}",
                    severity=RiskLevel.HIGH,
                    is_blocking=True,
                ))
        
        # Run custom checks
        for name, check_func in self._custom_checks.items():
            try:
                start = datetime.utcnow()
                result = await check_func(action, self._policy)
                duration_ms = (datetime.utcnow() - start).total_seconds() * 1000
                result.duration_ms = duration_ms
                results.append(result)
            except Exception as e:
                logger.error(f"Custom check {name} failed: {e}", exc_info=True)
                results.append(SafetyCheckResult(
                    check_type=SafetyCheckType.PRE_FLIGHT,
                    check_name=name,
                    passed=False,
                    message=f"Custom check failed: {str(e)}",
                    severity=RiskLevel.MEDIUM,
                    is_blocking=False,
                ))
        
        return results
    
    async def assess_blast_radius(
        self,
        action: RemediationAction,
        k8s_client: Any | None = None,
    ) -> BlastRadius:
        """
        Assess the blast radius of an action.
        
        Args:
            action: The remediation action
            k8s_client: Optional Kubernetes client for live assessment
            
        Returns:
            Blast radius assessment
        """
        blast_radius = BlastRadius()
        
        # Basic assessment based on action type and target
        if action.target_type == "pod":
            blast_radius.affected_pods = 1
        elif action.target_type == "deployment":
            # A deployment might have multiple pods
            blast_radius.affected_pods = 10  # Estimate, should query actual
        elif action.target_type == "node":
            blast_radius.affected_nodes = 1
            blast_radius.affected_pods = 50  # Estimate pods per node
        elif action.target_type == "namespace":
            blast_radius.affected_pods = 100  # Estimate
            blast_radius.affected_namespaces = [action.target_name]
        
        # Add namespace to affected list
        if action.target_namespace:
            if action.target_namespace not in blast_radius.affected_namespaces:
                blast_radius.affected_namespaces.append(action.target_namespace)
        
        # Assess risk levels based on action type
        definition_name = action.definition_name.lower()
        
        if "delete" in definition_name or "drain" in definition_name:
            blast_radius.downtime_risk = 0.6
            blast_radius.cascading_failure_risk = 0.3
        elif "restart" in definition_name:
            blast_radius.downtime_risk = 0.2
        elif "scale" in definition_name:
            if action.parameters.get("replicas", 1) == 0:
                blast_radius.downtime_risk = 1.0
            else:
                blast_radius.downtime_risk = 0.1
        elif "rollback" in definition_name:
            blast_radius.downtime_risk = 0.3
        
        # Production namespace increases risk
        if action.target_namespace in ["production", "prod"]:
            blast_radius.downtime_risk = min(1.0, blast_radius.downtime_risk * 1.5)
            blast_radius.cascading_failure_risk = min(1.0, blast_radius.cascading_failure_risk * 1.5)
        
        return blast_radius
    
    def is_safe(self, results: list[SafetyCheckResult]) -> bool:
        """
        Determine if action is safe based on check results.
        
        Args:
            results: List of check results
            
        Returns:
            True if all blocking checks passed
        """
        return all(
            result.passed or not result.is_blocking
            for result in results
        )
    
    def get_violations(
        self,
        results: list[SafetyCheckResult],
    ) -> list[SafetyViolation]:
        """
        Extract violations from check results.
        
        Args:
            results: List of check results
            
        Returns:
            List of violations
        """
        violations = []
        
        for result in results:
            if not result.passed:
                violations.append(SafetyViolation(
                    check_name=result.check_name,
                    severity=result.severity,
                    message=result.message,
                    is_blocking=result.is_blocking,
                    recommendation=result.recommendations[0] if result.recommendations else None,
                    details=result.details,
                ))
        
        return violations
    
    def requires_approval(
        self,
        action: RemediationAction,
        results: list[SafetyCheckResult],
    ) -> tuple[bool, str]:
        """
        Determine if action requires human approval.
        
        Args:
            action: The remediation action
            results: Check results
            
        Returns:
            Tuple of (requires_approval, reason)
        """
        # Check if namespace requires approval
        if action.target_namespace in self._policy.require_approval_for_namespaces:
            return True, f"Namespace '{action.target_namespace}' requires approval"
        
        # Check blast radius
        if action.blast_radius:
            if action.blast_radius.overall_risk_score > 0.5:
                return True, f"High blast radius (score={action.blast_radius.overall_risk_score:.2f})"
        
        # Check for high-severity violations that aren't blocking
        for result in results:
            if not result.passed and result.severity in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                if not result.is_blocking:
                    return True, f"High-severity warning: {result.check_name}"
        
        return False, ""
    
    async def record_action(
        self,
        action: RemediationAction,
    ) -> None:
        """
        Record an action for rate limiting and cooldown tracking.
        
        Args:
            action: The executed action
        """
        now = datetime.utcnow()
        target_key = f"{action.target_namespace}/{action.target_type}/{action.target_name}"
        
        async with self._lock:
            self._action_timestamps.append(now)
            self._last_action_per_target[target_key] = now
            
            if target_key not in self._target_action_counts:
                self._target_action_counts[target_key] = []
            self._target_action_counts[target_key].append(now)
            
            # Clean up old timestamps
            cutoff = now - timedelta(hours=2)
            self._action_timestamps = [
                ts for ts in self._action_timestamps
                if ts > cutoff
            ]
            
            for key in list(self._target_action_counts.keys()):
                self._target_action_counts[key] = [
                    ts for ts in self._target_action_counts[key]
                    if ts > cutoff
                ]
    
    # Built-in check implementations
    
    async def _check_risk_level(
        self,
        action: RemediationAction,
    ) -> SafetyCheckResult:
        """Check if action risk level is within policy limits."""
        risk_order = [
            RiskLevel.NONE,
            RiskLevel.LOW,
            RiskLevel.MEDIUM,
            RiskLevel.HIGH,
            RiskLevel.CRITICAL,
        ]
        
        # Determine action risk from blast radius
        action_risk = RiskLevel.LOW
        if action.blast_radius:
            score = action.blast_radius.overall_risk_score
            if score > 0.7:
                action_risk = RiskLevel.CRITICAL
            elif score > 0.5:
                action_risk = RiskLevel.HIGH
            elif score > 0.3:
                action_risk = RiskLevel.MEDIUM
        
        max_allowed = risk_order.index(self._policy.max_risk_level)
        action_index = risk_order.index(action_risk)
        
        if action_index > max_allowed:
            return SafetyCheckResult(
                check_type=SafetyCheckType.PRE_FLIGHT,
                check_name="risk_level",
                passed=False,
                message=f"Action risk level ({action_risk.value}) exceeds policy limit ({self._policy.max_risk_level.value})",
                severity=action_risk,
                is_blocking=True,
                recommendations=[
                    "Request approval from SRE team",
                    "Consider alternative lower-risk actions",
                ],
            )
        
        return SafetyCheckResult(
            check_type=SafetyCheckType.PRE_FLIGHT,
            check_name="risk_level",
            passed=True,
            message=f"Risk level {action_risk.value} is within limits",
            severity=RiskLevel.NONE,
        )
    
    async def _check_protected_resources(
        self,
        action: RemediationAction,
    ) -> SafetyCheckResult:
        """Check if action targets protected resources."""
        violations = []
        
        # Check namespace
        if action.target_namespace:
            if self._policy.is_namespace_protected(action.target_namespace):
                violations.append(
                    f"Namespace '{action.target_namespace}' is protected"
                )
        
        # Check deployment
        if action.target_type == "deployment":
            if self._policy.is_deployment_protected(action.target_name):
                violations.append(
                    f"Deployment '{action.target_name}' is protected"
                )
        
        if violations:
            return SafetyCheckResult(
                check_type=SafetyCheckType.PRE_FLIGHT,
                check_name="protected_resources",
                passed=False,
                message="; ".join(violations),
                severity=RiskLevel.CRITICAL,
                is_blocking=True,
                recommendations=[
                    "Remove resource from protected list if intentional",
                    "Request special approval",
                ],
            )
        
        return SafetyCheckResult(
            check_type=SafetyCheckType.PRE_FLIGHT,
            check_name="protected_resources",
            passed=True,
            message="No protected resources targeted",
            severity=RiskLevel.NONE,
        )
    
    async def _check_blast_radius(
        self,
        action: RemediationAction,
    ) -> SafetyCheckResult:
        """Check if blast radius is within limits."""
        if not action.blast_radius:
            # Assess blast radius
            action.blast_radius = await self.assess_blast_radius(action)
        
        br = action.blast_radius
        violations = []
        
        if br.affected_pods > self._policy.max_blast_radius_pods:
            violations.append(
                f"Affected pods ({br.affected_pods}) exceeds limit ({self._policy.max_blast_radius_pods})"
            )
        
        if br.affected_nodes > self._policy.max_blast_radius_nodes:
            violations.append(
                f"Affected nodes ({br.affected_nodes}) exceeds limit ({self._policy.max_blast_radius_nodes})"
            )
        
        if br.downtime_risk > self._policy.max_downtime_risk:
            violations.append(
                f"Downtime risk ({br.downtime_risk:.0%}) exceeds limit ({self._policy.max_downtime_risk:.0%})"
            )
        
        if br.data_loss_risk > self._policy.max_data_loss_risk:
            violations.append(
                f"Data loss risk ({br.data_loss_risk:.0%}) exceeds limit ({self._policy.max_data_loss_risk:.0%})"
            )
        
        if violations:
            return SafetyCheckResult(
                check_type=SafetyCheckType.PRE_FLIGHT,
                check_name="blast_radius",
                passed=False,
                message="; ".join(violations),
                severity=RiskLevel.HIGH,
                is_blocking=True,
                details={
                    "affected_pods": br.affected_pods,
                    "affected_nodes": br.affected_nodes,
                    "downtime_risk": br.downtime_risk,
                    "overall_risk_score": br.overall_risk_score,
                },
                recommendations=[
                    "Reduce scope of action",
                    "Execute in smaller batches",
                    "Request approval for larger scope",
                ],
            )
        
        return SafetyCheckResult(
            check_type=SafetyCheckType.PRE_FLIGHT,
            check_name="blast_radius",
            passed=True,
            message=f"Blast radius within limits (score={br.overall_risk_score:.2f})",
            severity=RiskLevel.NONE,
            details={
                "affected_pods": br.affected_pods,
                "affected_nodes": br.affected_nodes,
                "overall_risk_score": br.overall_risk_score,
            },
        )
    
    async def _check_time_restrictions(
        self,
        action: RemediationAction,
    ) -> SafetyCheckResult:
        """Check if current time allows actions."""
        is_blocked, reason = self._policy.is_blocked_time()
        
        if is_blocked:
            return SafetyCheckResult(
                check_type=SafetyCheckType.PRE_FLIGHT,
                check_name="time_restrictions",
                passed=False,
                message=f"Action blocked due to time restriction: {reason}",
                severity=RiskLevel.MEDIUM,
                is_blocking=True,
                recommendations=[
                    "Wait for allowed time window",
                    "Request emergency override",
                ],
            )
        
        return SafetyCheckResult(
            check_type=SafetyCheckType.PRE_FLIGHT,
            check_name="time_restrictions",
            passed=True,
            message="Time restrictions allow action",
            severity=RiskLevel.NONE,
        )
    
    async def _check_rate_limits(
        self,
        action: RemediationAction,
    ) -> SafetyCheckResult:
        """Check if action would exceed rate limits."""
        now = datetime.utcnow()
        one_hour_ago = now - timedelta(hours=1)
        
        # Check overall rate
        recent_actions = [ts for ts in self._action_timestamps if ts > one_hour_ago]
        if len(recent_actions) >= self._policy.max_actions_per_hour:
            return SafetyCheckResult(
                check_type=SafetyCheckType.PRE_FLIGHT,
                check_name="rate_limits",
                passed=False,
                message=f"Rate limit exceeded ({len(recent_actions)}/{self._policy.max_actions_per_hour} actions per hour)",
                severity=RiskLevel.MEDIUM,
                is_blocking=True,
                recommendations=["Wait before executing more actions"],
            )
        
        # Check per-target rate
        target_key = f"{action.target_namespace}/{action.target_type}/{action.target_name}"
        target_actions = self._target_action_counts.get(target_key, [])
        recent_target_actions = [ts for ts in target_actions if ts > one_hour_ago]
        
        if len(recent_target_actions) >= self._policy.max_actions_per_target:
            return SafetyCheckResult(
                check_type=SafetyCheckType.PRE_FLIGHT,
                check_name="rate_limits",
                passed=False,
                message=f"Per-target rate limit exceeded ({len(recent_target_actions)}/{self._policy.max_actions_per_target} actions)",
                severity=RiskLevel.MEDIUM,
                is_blocking=True,
                details={"target": target_key},
                recommendations=["Wait before targeting this resource again"],
            )
        
        return SafetyCheckResult(
            check_type=SafetyCheckType.PRE_FLIGHT,
            check_name="rate_limits",
            passed=True,
            message="Within rate limits",
            severity=RiskLevel.NONE,
        )
    
    async def _check_cooldown(
        self,
        action: RemediationAction,
    ) -> SafetyCheckResult:
        """Check if target is in cooldown period."""
        target_key = f"{action.target_namespace}/{action.target_type}/{action.target_name}"
        
        last_action = self._last_action_per_target.get(target_key)
        if last_action:
            cooldown = timedelta(seconds=self._policy.cooldown_between_actions_seconds)
            if datetime.utcnow() < last_action + cooldown:
                remaining = (last_action + cooldown - datetime.utcnow()).total_seconds()
                return SafetyCheckResult(
                    check_type=SafetyCheckType.PRE_FLIGHT,
                    check_name="cooldown",
                    passed=False,
                    message=f"Target in cooldown ({remaining:.0f}s remaining)",
                    severity=RiskLevel.LOW,
                    is_blocking=True,
                    details={
                        "target": target_key,
                        "remaining_seconds": remaining,
                    },
                )
        
        return SafetyCheckResult(
            check_type=SafetyCheckType.PRE_FLIGHT,
            check_name="cooldown",
            passed=True,
            message="No cooldown active",
            severity=RiskLevel.NONE,
        )
    
    async def _check_destructive_action(
        self,
        action: RemediationAction,
    ) -> SafetyCheckResult:
        """Check for destructive actions that need extra caution."""
        destructive_patterns = [
            r"delete",
            r"drain",
            r"terminate",
            r"destroy",
            r"remove",
            r"force",
        ]
        
        action_lower = action.definition_name.lower()
        is_destructive = any(
            re.search(pattern, action_lower)
            for pattern in destructive_patterns
        )
        
        if is_destructive and not action.dry_run:
            return SafetyCheckResult(
                check_type=SafetyCheckType.PRE_FLIGHT,
                check_name="destructive_action",
                passed=True,  # Warning only
                message=f"Destructive action detected: {action.definition_name}",
                severity=RiskLevel.HIGH,
                is_blocking=False,  # Not blocking, but requires attention
                recommendations=[
                    "Consider running with dry_run=True first",
                    "Ensure rollback is available",
                    "Verify target is correct",
                ],
            )
        
        return SafetyCheckResult(
            check_type=SafetyCheckType.PRE_FLIGHT,
            check_name="destructive_action",
            passed=True,
            message="Action is not destructive" if not is_destructive else "Dry run mode active",
            severity=RiskLevel.NONE,
        )
    
    async def _check_dry_run_requirement(
        self,
        action: RemediationAction,
    ) -> SafetyCheckResult:
        """Check if dry run is required."""
        if self._policy.require_dry_run_first and not action.dry_run:
            # Check if we've seen a successful dry run for this action type + target
            # For now, just return a warning
            return SafetyCheckResult(
                check_type=SafetyCheckType.PRE_FLIGHT,
                check_name="dry_run_requirement",
                passed=True,  # Warning only
                message="Policy recommends dry run first",
                severity=RiskLevel.LOW,
                is_blocking=False,
                recommendations=["Run with dry_run=True first to verify"],
            )
        
        return SafetyCheckResult(
            check_type=SafetyCheckType.PRE_FLIGHT,
            check_name="dry_run_requirement",
            passed=True,
            message="Dry run not required" if not action.dry_run else "Running in dry run mode",
            severity=RiskLevel.NONE,
        )
    
    def get_check_summary(
        self,
        results: list[SafetyCheckResult],
    ) -> dict[str, Any]:
        """
        Get summary of check results.
        
        Args:
            results: List of check results
            
        Returns:
            Summary dictionary
        """
        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed
        blocking = sum(1 for r in results if not r.passed and r.is_blocking)
        
        return {
            "total_checks": len(results),
            "passed": passed,
            "failed": failed,
            "blocking_failures": blocking,
            "is_safe": self.is_safe(results),
            "highest_severity": max(
                (r.severity for r in results if not r.passed),
                default=RiskLevel.NONE,
                key=lambda x: list(RiskLevel).index(x),
            ).value,
            "checks": [
                {
                    "name": r.check_name,
                    "passed": r.passed,
                    "severity": r.severity.value,
                    "message": r.message,
                    "is_blocking": r.is_blocking,
                    "duration_ms": r.duration_ms,
                }
                for r in results
            ],
        }
