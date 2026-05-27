"""
Automated Rollback for Safe Deployments

Provides automated rollback capabilities based on metrics,
health checks, and configurable triggers.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field


class RollbackStatus(str, Enum):
    """Status of a rollback operation."""
    
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RollbackReason(str, Enum):
    """Reason for triggering rollback."""
    
    METRIC_THRESHOLD = "metric_threshold"
    HEALTH_CHECK_FAILURE = "health_check_failure"
    ERROR_RATE = "error_rate"
    LATENCY_DEGRADATION = "latency_degradation"
    CANARY_FAILURE = "canary_failure"
    MANUAL = "manual"
    TIMEOUT = "timeout"
    SLO_VIOLATION = "slo_violation"
    CIRCUIT_BREAKER = "circuit_breaker"


class RollbackStrategy(str, Enum):
    """Strategy for performing rollback."""
    
    IMMEDIATE = "immediate"      # Instant rollback
    GRADUAL = "gradual"          # Gradual traffic shift
    BLUE_GREEN = "blue_green"    # Switch to blue/green
    RECREATE = "recreate"        # Delete and recreate


class TriggerCondition(str, Enum):
    """Condition for rollback trigger evaluation."""
    
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_THAN_OR_EQUAL = ">="
    LESS_THAN_OR_EQUAL = "<="
    EQUALS = "=="
    NOT_EQUALS = "!="


class RollbackConfig(BaseModel):
    """Configuration for rollback behavior."""
    
    # Basic settings
    name: str = "rollback-config"
    namespace: str = "default"
    
    # Strategy
    strategy: RollbackStrategy = RollbackStrategy.IMMEDIATE
    
    # Gradual rollback settings
    gradual_steps: list[int] = Field(default_factory=lambda: [75, 50, 25, 0])
    step_interval_seconds: int = Field(default=30, ge=10)
    
    # Timeout settings
    rollback_timeout_seconds: int = Field(default=300, ge=30)
    health_check_timeout_seconds: int = Field(default=60, ge=10)
    
    # Retry settings
    max_retries: int = Field(default=3, ge=0)
    retry_interval_seconds: int = Field(default=10, ge=1)
    
    # Notification settings
    notify_on_trigger: bool = True
    notify_on_complete: bool = True
    notification_channels: list[str] = Field(default_factory=list)
    
    # Verification settings
    verify_after_rollback: bool = True
    verification_duration_seconds: int = Field(default=60, ge=10)


class RollbackTrigger(BaseModel):
    """A trigger that can initiate automatic rollback."""
    
    id: str
    name: str
    description: str = ""
    enabled: bool = True
    
    # Metric to monitor
    metric_query: str
    
    # Threshold configuration
    condition: TriggerCondition = TriggerCondition.GREATER_THAN
    threshold: float
    
    # Duration requirement
    duration_seconds: int = Field(default=60, ge=10)
    
    # Priority
    priority: int = Field(default=1, ge=1, le=10)
    
    # Action
    strategy: RollbackStrategy = RollbackStrategy.IMMEDIATE
    
    def evaluate(self, value: float) -> bool:
        """Evaluate if trigger condition is met."""
        conditions = {
            TriggerCondition.GREATER_THAN: lambda v, t: v > t,
            TriggerCondition.LESS_THAN: lambda v, t: v < t,
            TriggerCondition.GREATER_THAN_OR_EQUAL: lambda v, t: v >= t,
            TriggerCondition.LESS_THAN_OR_EQUAL: lambda v, t: v <= t,
            TriggerCondition.EQUALS: lambda v, t: v == t,
            TriggerCondition.NOT_EQUALS: lambda v, t: v != t,
        }
        return conditions.get(self.condition, lambda v, t: False)(value, self.threshold)


class AutoRollbackPolicy(BaseModel):
    """Policy for automatic rollback decisions."""
    
    name: str = "auto-rollback-policy"
    enabled: bool = True
    
    # Triggers
    triggers: list[RollbackTrigger] = Field(default_factory=list)
    
    # Default thresholds
    max_error_rate: float = Field(default=0.05, ge=0.0, le=1.0)
    max_latency_p99_ms: float = Field(default=5000.0, ge=0.0)
    min_success_rate: float = Field(default=0.95, ge=0.0, le=1.0)
    max_pod_restart_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    
    # Time windows
    evaluation_window_seconds: int = Field(default=300, ge=60)
    min_evaluation_samples: int = Field(default=100, ge=10)
    
    # Circuit breaker
    enable_circuit_breaker: bool = True
    circuit_breaker_threshold: int = Field(default=3, ge=1)
    circuit_breaker_timeout_seconds: int = Field(default=300, ge=60)
    
    # Approval requirements
    require_approval_for_manual: bool = False
    approvers: list[str] = Field(default_factory=list)


@dataclass
class RollbackAction:
    """An action taken during rollback."""
    
    action_type: str
    description: str
    status: str = "pending"  # pending, completed, failed
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class RollbackSnapshot:
    """Snapshot of deployment state before rollback."""
    
    deployment_name: str
    namespace: str
    
    # Version info
    current_version: str = ""
    target_version: str = ""
    
    # Resource state
    replicas: int = 0
    ready_replicas: int = 0
    
    # Configuration
    image: str = ""
    config_hash: str = ""
    
    # Metadata
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert snapshot to dictionary."""
        return {
            "deployment_name": self.deployment_name,
            "namespace": self.namespace,
            "current_version": self.current_version,
            "target_version": self.target_version,
            "replicas": self.replicas,
            "ready_replicas": self.ready_replicas,
            "image": self.image,
            "config_hash": self.config_hash,
            "captured_at": self.captured_at.isoformat(),
            "labels": self.labels,
            "annotations": self.annotations,
        }


@dataclass
class RollbackExecution:
    """Execution details of a rollback operation."""
    
    id: str
    deployment_name: str
    namespace: str = "default"
    
    # Status
    status: RollbackStatus = RollbackStatus.PENDING
    reason: RollbackReason = RollbackReason.MANUAL
    
    # Strategy
    strategy: RollbackStrategy = RollbackStrategy.IMMEDIATE
    
    # Versions
    from_version: str = ""
    to_version: str = ""
    
    # Timing
    triggered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Progress
    progress_percentage: int = 0
    current_step: str = ""
    
    # Actions taken
    actions: list[RollbackAction] = field(default_factory=list)
    
    # Snapshot
    pre_rollback_snapshot: Optional[RollbackSnapshot] = None
    
    # Results
    success: bool = False
    error_message: str = ""
    
    def duration_seconds(self) -> Optional[float]:
        """Calculate rollback duration."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    def add_action(self, action: RollbackAction) -> None:
        """Add an action to the execution."""
        self.actions.append(action)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert execution to dictionary."""
        return {
            "id": self.id,
            "deployment_name": self.deployment_name,
            "namespace": self.namespace,
            "status": self.status.value,
            "reason": self.reason.value,
            "strategy": self.strategy.value,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "triggered_at": self.triggered_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress_percentage": self.progress_percentage,
            "success": self.success,
            "error_message": self.error_message,
            "duration_seconds": self.duration_seconds(),
        }


@dataclass
class RollbackResult:
    """Result of a rollback operation."""
    
    success: bool = False
    execution: Optional[RollbackExecution] = None
    message: str = ""
    
    # Metrics after rollback
    error_rate_after: Optional[float] = None
    success_rate_after: Optional[float] = None
    latency_p99_after: Optional[float] = None
    
    # Verification
    verified: bool = False
    verification_passed: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "success": self.success,
            "message": self.message,
            "execution": self.execution.to_dict() if self.execution else None,
            "error_rate_after": self.error_rate_after,
            "success_rate_after": self.success_rate_after,
            "latency_p99_after": self.latency_p99_after,
            "verified": self.verified,
            "verification_passed": self.verification_passed,
        }


@dataclass
class RollbackHistoryEntry:
    """Entry in rollback history."""
    
    execution_id: str
    deployment_name: str
    namespace: str
    timestamp: datetime
    reason: RollbackReason
    success: bool
    duration_seconds: float
    from_version: str
    to_version: str


class RollbackHistory:
    """Tracks history of rollback operations."""
    
    def __init__(self, max_entries: int = 1000):
        self.max_entries = max_entries
        self._history: list[RollbackHistoryEntry] = []
    
    def add(self, execution: RollbackExecution) -> None:
        """Add a rollback to history."""
        entry = RollbackHistoryEntry(
            execution_id=execution.id,
            deployment_name=execution.deployment_name,
            namespace=execution.namespace,
            timestamp=execution.triggered_at,
            reason=execution.reason,
            success=execution.success,
            duration_seconds=execution.duration_seconds() or 0.0,
            from_version=execution.from_version,
            to_version=execution.to_version,
        )
        self._history.append(entry)
        
        # Trim if needed
        if len(self._history) > self.max_entries:
            self._history = self._history[-self.max_entries:]
    
    def get_recent(
        self,
        limit: int = 10,
        deployment: Optional[str] = None,
        namespace: Optional[str] = None,
    ) -> list[RollbackHistoryEntry]:
        """Get recent rollback history."""
        filtered = self._history
        
        if deployment:
            filtered = [e for e in filtered if e.deployment_name == deployment]
        if namespace:
            filtered = [e for e in filtered if e.namespace == namespace]
        
        return filtered[-limit:]
    
    def get_statistics(
        self,
        deployment: Optional[str] = None,
        time_window: Optional[timedelta] = None,
    ) -> dict[str, Any]:
        """Get rollback statistics."""
        filtered = self._history
        
        if deployment:
            filtered = [e for e in filtered if e.deployment_name == deployment]
        if time_window:
            cutoff = datetime.now(timezone.utc) - time_window
            filtered = [e for e in filtered if e.timestamp > cutoff]
        
        if not filtered:
            return {
                "total_rollbacks": 0,
                "success_rate": 0.0,
                "avg_duration_seconds": 0.0,
                "reasons": {},
            }
        
        success_count = sum(1 for e in filtered if e.success)
        reasons: dict[str, int] = {}
        for entry in filtered:
            reason = entry.reason.value
            reasons[reason] = reasons.get(reason, 0) + 1
        
        return {
            "total_rollbacks": len(filtered),
            "success_rate": success_count / len(filtered),
            "avg_duration_seconds": sum(e.duration_seconds for e in filtered) / len(filtered),
            "reasons": reasons,
        }


class RollbackNotifier:
    """Sends notifications for rollback events."""
    
    def __init__(
        self,
        channels: Optional[list[str]] = None,
        notify_callback: Optional[Callable[[str, str, dict[str, Any]], None]] = None,
    ):
        self.channels = channels or []
        self.notify_callback = notify_callback
    
    async def notify_trigger(
        self,
        execution: RollbackExecution,
        trigger: Optional[RollbackTrigger] = None,
    ) -> None:
        """Notify that rollback has been triggered."""
        message = (
            f"🔄 Rollback triggered for {execution.deployment_name}\n"
            f"Reason: {execution.reason.value}\n"
            f"Strategy: {execution.strategy.value}\n"
            f"From: {execution.from_version} → To: {execution.to_version}"
        )
        
        details = {
            "execution_id": execution.id,
            "deployment": execution.deployment_name,
            "namespace": execution.namespace,
            "reason": execution.reason.value,
        }
        
        if trigger:
            message += f"\nTrigger: {trigger.name}"
            details["trigger"] = trigger.id
        
        await self._send("rollback_triggered", message, details)
    
    async def notify_progress(
        self,
        execution: RollbackExecution,
        step: str,
    ) -> None:
        """Notify rollback progress."""
        message = (
            f"🔄 Rollback progress: {execution.deployment_name}\n"
            f"Step: {step}\n"
            f"Progress: {execution.progress_percentage}%"
        )
        
        await self._send("rollback_progress", message, {
            "execution_id": execution.id,
            "step": step,
            "progress": execution.progress_percentage,
        })
    
    async def notify_complete(
        self,
        result: RollbackResult,
    ) -> None:
        """Notify rollback completion."""
        if result.success:
            emoji = "✅"
            status = "succeeded"
        else:
            emoji = "❌"
            status = "failed"
        
        execution = result.execution
        message = (
            f"{emoji} Rollback {status}\n"
            f"Deployment: {execution.deployment_name if execution else 'unknown'}\n"
            f"Message: {result.message}"
        )
        
        if result.verified:
            message += f"\nVerification: {'passed' if result.verification_passed else 'failed'}"
        
        await self._send("rollback_complete", message, result.to_dict())
    
    async def _send(
        self,
        event_type: str,
        message: str,
        details: dict[str, Any],
    ) -> None:
        """Send notification."""
        if self.notify_callback:
            self.notify_callback(event_type, message, details)


class RollbackManager:
    """Manages automated rollback operations."""
    
    def __init__(
        self,
        config: Optional[RollbackConfig] = None,
        policy: Optional[AutoRollbackPolicy] = None,
        kubernetes_client: Optional[Any] = None,
        metrics_client: Optional[Any] = None,
        notify_callback: Optional[Callable[[str, str], None]] = None,
    ):
        self.config = config or RollbackConfig()
        self.policy = policy or AutoRollbackPolicy()
        self.kubernetes_client = kubernetes_client
        self.metrics_client = metrics_client
        self.notify_callback = notify_callback
        
        # State
        self._executions: dict[str, RollbackExecution] = {}
        self._history = RollbackHistory()
        self._notifier = RollbackNotifier(
            channels=self.config.notification_channels,
            notify_callback=lambda t, m, d: notify_callback(t, m) if notify_callback else None,
        )
        
        # Trigger monitoring
        self._trigger_states: dict[str, datetime] = {}  # trigger_id -> first_triggered_at
        self._is_monitoring: bool = False
    
    async def rollback(
        self,
        deployment_name: str,
        namespace: str = "default",
        reason: RollbackReason = RollbackReason.MANUAL,
        target_version: Optional[str] = None,
        strategy: Optional[RollbackStrategy] = None,
    ) -> RollbackResult:
        """Perform rollback of a deployment.
        
        Args:
            deployment_name: Name of the deployment to roll back
            namespace: Kubernetes namespace
            reason: Reason for rollback
            target_version: Specific version to roll back to (optional)
            strategy: Rollback strategy to use (optional, uses config default)
        
        Returns:
            RollbackResult with execution details
        """
        import uuid
        
        execution = RollbackExecution(
            id=str(uuid.uuid4()),
            deployment_name=deployment_name,
            namespace=namespace,
            reason=reason,
            strategy=strategy or self.config.strategy,
        )
        
        self._executions[execution.id] = execution
        
        try:
            # Capture pre-rollback snapshot
            execution.pre_rollback_snapshot = await self._capture_snapshot(
                deployment_name, namespace
            )
            execution.from_version = execution.pre_rollback_snapshot.current_version
            execution.to_version = target_version or "previous"
            
            # Notify trigger
            if self.config.notify_on_trigger:
                await self._notifier.notify_trigger(execution)
            
            # Start rollback
            execution.status = RollbackStatus.IN_PROGRESS
            execution.started_at = datetime.now(timezone.utc)
            
            # Execute based on strategy
            if execution.strategy == RollbackStrategy.IMMEDIATE:
                await self._rollback_immediate(execution)
            elif execution.strategy == RollbackStrategy.GRADUAL:
                await self._rollback_gradual(execution)
            elif execution.strategy == RollbackStrategy.BLUE_GREEN:
                await self._rollback_blue_green(execution)
            elif execution.strategy == RollbackStrategy.RECREATE:
                await self._rollback_recreate(execution)
            
            # Verify rollback
            result = RollbackResult(execution=execution)
            
            if self.config.verify_after_rollback:
                result.verified = True
                result.verification_passed = await self._verify_rollback(execution)
            
            # Mark success
            execution.status = RollbackStatus.COMPLETED
            execution.completed_at = datetime.now(timezone.utc)
            execution.success = True
            execution.progress_percentage = 100
            
            result.success = True
            result.message = f"Rollback completed successfully in {execution.duration_seconds():.1f}s"
            
            # Collect post-rollback metrics
            metrics = await self._collect_metrics(deployment_name, namespace)
            result.error_rate_after = metrics.get("error_rate")
            result.success_rate_after = metrics.get("success_rate")
            result.latency_p99_after = metrics.get("latency_p99")
            
        except Exception as e:
            execution.status = RollbackStatus.FAILED
            execution.completed_at = datetime.now(timezone.utc)
            execution.success = False
            execution.error_message = str(e)
            
            result = RollbackResult(
                success=False,
                execution=execution,
                message=f"Rollback failed: {str(e)}",
            )
        finally:
            # Record in history
            self._history.add(execution)
            
            # Notify completion
            if self.config.notify_on_complete:
                await self._notifier.notify_complete(result)
        
        return result
    
    async def _rollback_immediate(self, execution: RollbackExecution) -> None:
        """Perform immediate rollback."""
        action = RollbackAction(
            action_type="rollback_immediate",
            description=f"Rolling back {execution.deployment_name} to {execution.to_version}",
            started_at=datetime.now(timezone.utc),
        )
        execution.add_action(action)
        execution.current_step = "Rolling back deployment"
        
        # In real implementation, use kubectl or Kubernetes API
        # kubectl rollout undo deployment/<name> -n <namespace>
        if self.kubernetes_client:
            await self.kubernetes_client.rollout_undo(
                execution.deployment_name,
                execution.namespace,
                to_revision=execution.to_version if execution.to_version != "previous" else None,
            )
        
        # Wait for rollout to complete
        await self._wait_for_rollout(execution)
        
        action.status = "completed"
        action.completed_at = datetime.now(timezone.utc)
        execution.progress_percentage = 100
    
    async def _rollback_gradual(self, execution: RollbackExecution) -> None:
        """Perform gradual rollback by shifting traffic."""
        steps = self.config.gradual_steps
        total_steps = len(steps)
        
        for i, weight in enumerate(steps):
            step_num = i + 1
            action = RollbackAction(
                action_type="traffic_shift",
                description=f"Shifting traffic to {100 - weight}% stable",
                started_at=datetime.now(timezone.utc),
                details={"canary_weight": weight, "stable_weight": 100 - weight},
            )
            execution.add_action(action)
            execution.current_step = f"Step {step_num}/{total_steps}: Shifting traffic"
            execution.progress_percentage = int((step_num / total_steps) * 100)
            
            # Shift traffic
            if self.kubernetes_client:
                await self.kubernetes_client.set_traffic_split(
                    deployment=execution.deployment_name,
                    namespace=execution.namespace,
                    canary_weight=weight,
                )
            
            action.status = "completed"
            action.completed_at = datetime.now(timezone.utc)
            
            # Wait between steps
            if i < total_steps - 1:
                await asyncio.sleep(self.config.step_interval_seconds)
    
    async def _rollback_blue_green(self, execution: RollbackExecution) -> None:
        """Perform blue-green rollback by switching services."""
        action = RollbackAction(
            action_type="blue_green_switch",
            description="Switching service selector to stable version",
            started_at=datetime.now(timezone.utc),
        )
        execution.add_action(action)
        execution.current_step = "Switching to stable deployment"
        
        if self.kubernetes_client:
            # Update service selector to point to stable deployment
            await self.kubernetes_client.update_service_selector(
                service=execution.deployment_name,
                namespace=execution.namespace,
                selector={"version": "stable"},
            )
        
        action.status = "completed"
        action.completed_at = datetime.now(timezone.utc)
        execution.progress_percentage = 100
    
    async def _rollback_recreate(self, execution: RollbackExecution) -> None:
        """Perform rollback by recreating the deployment."""
        # Delete canary/new deployment
        delete_action = RollbackAction(
            action_type="delete_deployment",
            description="Deleting failed deployment",
            started_at=datetime.now(timezone.utc),
        )
        execution.add_action(delete_action)
        execution.current_step = "Deleting failed deployment"
        execution.progress_percentage = 25
        
        if self.kubernetes_client:
            await self.kubernetes_client.delete_deployment(
                execution.deployment_name,
                execution.namespace,
            )
        
        delete_action.status = "completed"
        delete_action.completed_at = datetime.now(timezone.utc)
        
        # Recreate from snapshot
        recreate_action = RollbackAction(
            action_type="recreate_deployment",
            description="Recreating deployment from snapshot",
            started_at=datetime.now(timezone.utc),
        )
        execution.add_action(recreate_action)
        execution.current_step = "Recreating deployment"
        execution.progress_percentage = 75
        
        if self.kubernetes_client and execution.pre_rollback_snapshot:
            await self.kubernetes_client.create_deployment(
                name=execution.deployment_name,
                namespace=execution.namespace,
                image=execution.pre_rollback_snapshot.image,
                replicas=execution.pre_rollback_snapshot.replicas,
            )
        
        recreate_action.status = "completed"
        recreate_action.completed_at = datetime.now(timezone.utc)
        execution.progress_percentage = 100
    
    async def _capture_snapshot(
        self,
        deployment_name: str,
        namespace: str,
    ) -> RollbackSnapshot:
        """Capture deployment state before rollback."""
        snapshot = RollbackSnapshot(
            deployment_name=deployment_name,
            namespace=namespace,
        )
        
        if self.kubernetes_client:
            deployment = await self.kubernetes_client.get_deployment(
                deployment_name, namespace
            )
            if deployment:
                snapshot.current_version = deployment.get("metadata", {}).get(
                    "labels", {}
                ).get("version", "unknown")
                snapshot.replicas = deployment.get("spec", {}).get("replicas", 0)
                snapshot.ready_replicas = deployment.get("status", {}).get(
                    "readyReplicas", 0
                )
                containers = deployment.get("spec", {}).get("template", {}).get(
                    "spec", {}
                ).get("containers", [])
                if containers:
                    snapshot.image = containers[0].get("image", "")
                snapshot.labels = deployment.get("metadata", {}).get("labels", {})
                snapshot.annotations = deployment.get("metadata", {}).get(
                    "annotations", {}
                )
        
        return snapshot
    
    async def _wait_for_rollout(
        self,
        execution: RollbackExecution,
        timeout_seconds: Optional[int] = None,
    ) -> bool:
        """Wait for rollout to complete."""
        timeout = timeout_seconds or self.config.rollback_timeout_seconds
        deadline = datetime.now(timezone.utc) + timedelta(seconds=timeout)
        
        while datetime.now(timezone.utc) < deadline:
            if self.kubernetes_client:
                status = await self.kubernetes_client.get_rollout_status(
                    execution.deployment_name,
                    execution.namespace,
                )
                if status and status.get("completed"):
                    return True
            
            await asyncio.sleep(5)
        
        return False
    
    async def _verify_rollback(
        self,
        execution: RollbackExecution,
    ) -> bool:
        """Verify rollback was successful."""
        # Wait for verification duration
        await asyncio.sleep(self.config.verification_duration_seconds)
        
        # Check metrics
        metrics = await self._collect_metrics(
            execution.deployment_name,
            execution.namespace,
        )
        
        # Verify against policy thresholds
        error_rate = metrics.get("error_rate", 0.0)
        success_rate = metrics.get("success_rate", 1.0)
        
        return (
            error_rate <= self.policy.max_error_rate and
            success_rate >= self.policy.min_success_rate
        )
    
    async def _collect_metrics(
        self,
        deployment_name: str,
        namespace: str,
    ) -> dict[str, float]:
        """Collect current metrics for deployment."""
        if self.metrics_client:
            return await self.metrics_client.query_deployment_metrics(
                deployment_name, namespace
            )
        return {}
    
    async def start_monitoring(
        self,
        deployment_name: str,
        namespace: str = "default",
        interval_seconds: int = 30,
    ) -> None:
        """Start monitoring deployment for rollback triggers."""
        self._is_monitoring = True
        
        while self._is_monitoring:
            for trigger in self.policy.triggers:
                if not trigger.enabled:
                    continue
                
                # Query metric
                value = await self._query_trigger_metric(
                    trigger, deployment_name, namespace
                )
                
                if value is not None and trigger.evaluate(value):
                    # Check duration requirement
                    trigger_key = f"{trigger.id}:{deployment_name}:{namespace}"
                    if trigger_key not in self._trigger_states:
                        self._trigger_states[trigger_key] = datetime.now(timezone.utc)
                    
                    elapsed = (
                        datetime.now(timezone.utc) - self._trigger_states[trigger_key]
                    ).total_seconds()
                    
                    if elapsed >= trigger.duration_seconds:
                        # Trigger rollback
                        await self.rollback(
                            deployment_name=deployment_name,
                            namespace=namespace,
                            reason=RollbackReason.METRIC_THRESHOLD,
                            strategy=trigger.strategy,
                        )
                        del self._trigger_states[trigger_key]
                        break
                else:
                    # Reset trigger state
                    trigger_key = f"{trigger.id}:{deployment_name}:{namespace}"
                    self._trigger_states.pop(trigger_key, None)
            
            await asyncio.sleep(interval_seconds)
    
    def stop_monitoring(self) -> None:
        """Stop monitoring for rollback triggers."""
        self._is_monitoring = False
    
    async def _query_trigger_metric(
        self,
        trigger: RollbackTrigger,
        deployment_name: str,
        namespace: str,
    ) -> Optional[float]:
        """Query metric value for trigger evaluation."""
        if self.metrics_client:
            return await self.metrics_client.query(
                trigger.metric_query,
                {"deployment": deployment_name, "namespace": namespace},
            )
        return None
    
    def get_execution(self, execution_id: str) -> Optional[RollbackExecution]:
        """Get rollback execution by ID."""
        return self._executions.get(execution_id)
    
    def get_history(
        self,
        deployment: Optional[str] = None,
        namespace: Optional[str] = None,
        limit: int = 10,
    ) -> list[RollbackHistoryEntry]:
        """Get rollback history."""
        return self._history.get_recent(
            limit=limit,
            deployment=deployment,
            namespace=namespace,
        )
    
    def get_statistics(
        self,
        deployment: Optional[str] = None,
        time_window: Optional[timedelta] = None,
    ) -> dict[str, Any]:
        """Get rollback statistics."""
        return self._history.get_statistics(
            deployment=deployment,
            time_window=time_window,
        )
