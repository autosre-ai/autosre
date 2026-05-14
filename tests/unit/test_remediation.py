"""
Unit tests for the remediation framework.

Tests for:
- RemediationEngine
- ActionRegistry
- SafetyChecker
- RollbackManager
- ApprovalWorkflow
"""

from __future__ import annotations

import asyncio
import pytest
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from autosre.remediation import (
    RemediationEngine,
    EngineConfig,
    ActionRegistry,
    ActionNotFoundError,
    ActionValidationError,
    ActionCooldownError,
    SafetyChecker,
    SafetyPolicy,
    RollbackManager,
    ApprovalWorkflow,
    ApprovalPolicy,
)
from autosre.remediation.models import (
    RemediationAction,
    RemediationPlan,
    RemediationResult,
    RemediationStatus,
    ActionDefinition,
    ActionParameter,
    ActionType,
    RiskLevel,
    RollbackStrategy,
    BlastRadius,
    SafetyCheckResult,
    SafetyCheckType,
    ApprovalStatus,
    ApprovalRequest,
)
from autosre.remediation.approval import NotificationChannel


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def registry() -> ActionRegistry:
    """Create a fresh action registry."""
    return ActionRegistry()


@pytest.fixture
def sample_action_definition() -> ActionDefinition:
    """Create a sample action definition."""
    return ActionDefinition(
        name="restart_pod",
        display_name="Restart Pod",
        description="Restarts a Kubernetes pod",
        action_type=ActionType.RESTART,
        risk_level=RiskLevel.LOW,
        is_destructive=False,
        is_reversible=True,
        parameters=[
            ActionParameter(
                name="namespace",
                type="str",
                required=True,
                description="Target namespace",
            ),
            ActionParameter(
                name="pod_name",
                type="str",
                required=True,
                description="Pod name",
            ),
            ActionParameter(
                name="grace_period",
                type="int",
                required=False,
                default=30,
                description="Grace period in seconds",
                min_value=0,
                max_value=300,
            ),
        ],
        target_types=["pod"],
        timeout_seconds=120,
        cooldown_seconds=30,
        tags=["kubernetes", "restart", "pod"],
    )


@pytest.fixture
def safety_policy() -> SafetyPolicy:
    """Create a safety policy."""
    return SafetyPolicy(
        name="test-policy",
        max_risk_level=RiskLevel.HIGH,
        max_blast_radius_pods=10,
        max_blast_radius_nodes=2,
        max_downtime_risk=0.5,
        protected_namespaces=["kube-system", "production"],
        require_approval_for_namespaces=["production"],
    )


@pytest.fixture
def safety_checker(safety_policy: SafetyPolicy) -> SafetyChecker:
    """Create a safety checker."""
    return SafetyChecker(policy=safety_policy)


@pytest.fixture
def rollback_manager() -> RollbackManager:
    """Create a rollback manager."""
    return RollbackManager()


@pytest.fixture
def approval_workflow() -> ApprovalWorkflow:
    """Create an approval workflow."""
    return ApprovalWorkflow()


# ============================================================================
# ActionRegistry Tests
# ============================================================================

class TestActionRegistry:
    """Tests for ActionRegistry."""
    
    def test_registry_initialization(self, registry: ActionRegistry):
        """Test registry initializes empty."""
        assert len(registry.action_names) == 0
        assert registry.actions == {}
    
    def test_register_action(
        self,
        registry: ActionRegistry,
        sample_action_definition: ActionDefinition,
    ):
        """Test registering an action."""
        async def handler(namespace: str, pod_name: str, grace_period: int = 30):
            return {"restarted": True}
        
        registry.register_action(sample_action_definition, handler)
        
        assert registry.has_action("restart_pod")
        assert "restart_pod" in registry.action_names
        
        registered = registry.get("restart_pod")
        assert registered.definition.name == "restart_pod"
        assert registered.handler == handler
    
    def test_register_via_decorator(self, registry: ActionRegistry):
        """Test registering via decorator."""
        @registry.register(
            name="scale_deployment",
            display_name="Scale Deployment",
            description="Scales a deployment",
            action_type=ActionType.SCALE,
            risk_level=RiskLevel.MEDIUM,
        )
        async def scale_deployment(namespace: str, name: str, replicas: int):
            return {"replicas": replicas}
        
        assert registry.has_action("scale_deployment")
        definition = registry.get_definition("scale_deployment")
        assert definition.action_type == ActionType.SCALE
    
    def test_unregister_action(
        self,
        registry: ActionRegistry,
        sample_action_definition: ActionDefinition,
    ):
        """Test unregistering an action."""
        async def handler(**kwargs):
            return {}
        
        registry.register_action(sample_action_definition, handler)
        assert registry.has_action("restart_pod")
        
        registry.unregister("restart_pod")
        assert not registry.has_action("restart_pod")
    
    def test_get_nonexistent_action(self, registry: ActionRegistry):
        """Test getting a non-existent action raises error."""
        with pytest.raises(ActionNotFoundError) as exc:
            registry.get("nonexistent")
        
        assert exc.value.action_name == "nonexistent"
    
    def test_validate_parameters_success(
        self,
        registry: ActionRegistry,
        sample_action_definition: ActionDefinition,
    ):
        """Test parameter validation success."""
        async def handler(**kwargs):
            return {}
        
        registry.register_action(sample_action_definition, handler)
        
        errors = registry.validate_parameters("restart_pod", {
            "namespace": "default",
            "pod_name": "api-server-xyz",
            "grace_period": 60,
        })
        
        assert errors == []
    
    def test_validate_parameters_missing_required(
        self,
        registry: ActionRegistry,
        sample_action_definition: ActionDefinition,
    ):
        """Test parameter validation with missing required param."""
        async def handler(**kwargs):
            return {}
        
        registry.register_action(sample_action_definition, handler)
        
        errors = registry.validate_parameters("restart_pod", {
            "namespace": "default",
            # Missing pod_name
        })
        
        assert len(errors) == 1
        assert "pod_name" in errors[0]
    
    def test_validate_parameters_out_of_range(
        self,
        registry: ActionRegistry,
        sample_action_definition: ActionDefinition,
    ):
        """Test parameter validation with out of range value."""
        async def handler(**kwargs):
            return {}
        
        registry.register_action(sample_action_definition, handler)
        
        errors = registry.validate_parameters("restart_pod", {
            "namespace": "default",
            "pod_name": "api-server",
            "grace_period": 500,  # Max is 300
        })
        
        assert len(errors) == 1
        assert "grace_period" in errors[0]
    
    @pytest.mark.asyncio
    async def test_execute_action(
        self,
        registry: ActionRegistry,
        sample_action_definition: ActionDefinition,
    ):
        """Test executing an action."""
        async def handler(namespace: str, pod_name: str, grace_period: int = 30):
            return {"restarted": True, "pod": pod_name}
        
        registry.register_action(sample_action_definition, handler)
        
        result = await registry.execute("restart_pod", {
            "namespace": "default",
            "pod_name": "test-pod",
        })
        
        assert result["restarted"] is True
        assert result["pod"] == "test-pod"
    
    @pytest.mark.asyncio
    async def test_execute_action_cooldown(
        self,
        registry: ActionRegistry,
        sample_action_definition: ActionDefinition,
    ):
        """Test action cooldown enforcement."""
        call_count = 0
        
        async def handler(namespace: str, pod_name: str, grace_period: int = 30):
            nonlocal call_count
            call_count += 1
            return {"count": call_count}
        
        registry.register_action(sample_action_definition, handler)
        
        # First execution
        await registry.execute("restart_pod", {
            "namespace": "default",
            "pod_name": "test-pod",
        })
        
        # Second execution should hit cooldown
        with pytest.raises(ActionCooldownError):
            await registry.execute("restart_pod", {
                "namespace": "default",
                "pod_name": "test-pod",
            })
    
    @pytest.mark.asyncio
    async def test_execute_action_timeout(self, registry: ActionRegistry):
        """Test action timeout."""
        @registry.register(
            name="slow_action",
            display_name="Slow Action",
            description="A slow action",
            action_type=ActionType.DIAGNOSTIC,
            timeout_seconds=1,
        )
        async def slow_action():
            await asyncio.sleep(5)
            return {"done": True}
        
        with pytest.raises(asyncio.TimeoutError):
            await registry.execute("slow_action", {}, timeout=0.5)
    
    def test_find_by_tag(
        self,
        registry: ActionRegistry,
        sample_action_definition: ActionDefinition,
    ):
        """Test finding actions by tag."""
        async def handler(**kwargs):
            return {}
        
        registry.register_action(sample_action_definition, handler)
        
        results = registry.find_by_tag("kubernetes")
        assert len(results) == 1
        assert results[0].name == "restart_pod"
        
        results = registry.find_by_tag("nonexistent")
        assert len(results) == 0
    
    def test_find_by_type(
        self,
        registry: ActionRegistry,
        sample_action_definition: ActionDefinition,
    ):
        """Test finding actions by type."""
        async def handler(**kwargs):
            return {}
        
        registry.register_action(sample_action_definition, handler)
        
        results = registry.find_by_type(ActionType.RESTART)
        assert len(results) == 1
        
        results = registry.find_by_type(ActionType.SCALE)
        assert len(results) == 0
    
    def test_find_by_target_type(
        self,
        registry: ActionRegistry,
        sample_action_definition: ActionDefinition,
    ):
        """Test finding actions by target type."""
        async def handler(**kwargs):
            return {}
        
        registry.register_action(sample_action_definition, handler)
        
        results = registry.find_by_target_type("pod")
        assert len(results) == 1
        
        results = registry.find_by_target_type("deployment")
        assert len(results) == 0
    
    def test_get_metrics(
        self,
        registry: ActionRegistry,
        sample_action_definition: ActionDefinition,
    ):
        """Test getting registry metrics."""
        async def handler(**kwargs):
            return {}
        
        registry.register_action(sample_action_definition, handler)
        
        metrics = registry.get_metrics()
        
        assert metrics["total_actions"] == 1
        assert "restart" in metrics["actions_by_type"]
        assert "low" in metrics["actions_by_risk"]
    
    def test_to_catalog(
        self,
        registry: ActionRegistry,
        sample_action_definition: ActionDefinition,
    ):
        """Test exporting action catalog."""
        async def handler(**kwargs):
            return {}
        
        registry.register_action(sample_action_definition, handler)
        
        catalog = registry.to_catalog()
        
        assert len(catalog) == 1
        assert catalog[0]["name"] == "restart_pod"
        assert catalog[0]["type"] == "restart"
        assert len(catalog[0]["parameters"]) == 3


# ============================================================================
# SafetyChecker Tests
# ============================================================================

class TestSafetyChecker:
    """Tests for SafetyChecker."""
    
    @pytest.mark.asyncio
    async def test_check_action_passes(self, safety_checker: SafetyChecker):
        """Test safety check passes for safe action."""
        action = RemediationAction(
            definition_name="restart_pod",
            target_type="pod",
            target_name="api-server-xyz",
            target_namespace="default",
        )
        
        results = await safety_checker.check_action(action)
        
        assert safety_checker.is_safe(results)
        violations = safety_checker.get_violations(results)
        assert len([v for v in violations if v.is_blocking]) == 0
    
    @pytest.mark.asyncio
    async def test_check_protected_namespace(self, safety_checker: SafetyChecker):
        """Test safety check fails for protected namespace."""
        action = RemediationAction(
            definition_name="delete_pod",
            target_type="pod",
            target_name="coredns-xyz",
            target_namespace="kube-system",
        )
        
        results = await safety_checker.check_action(action)
        
        assert not safety_checker.is_safe(results)
        violations = safety_checker.get_violations(results)
        assert any("kube-system" in v.message for v in violations)
    
    @pytest.mark.asyncio
    async def test_assess_blast_radius_pod(self, safety_checker: SafetyChecker):
        """Test blast radius assessment for pod."""
        action = RemediationAction(
            definition_name="restart_pod",
            target_type="pod",
            target_name="api-server-xyz",
            target_namespace="default",
        )
        
        blast_radius = await safety_checker.assess_blast_radius(action)
        
        assert blast_radius.affected_pods == 1
        assert blast_radius.affected_nodes == 0
        assert "default" in blast_radius.affected_namespaces
    
    @pytest.mark.asyncio
    async def test_assess_blast_radius_node(self, safety_checker: SafetyChecker):
        """Test blast radius assessment for node."""
        action = RemediationAction(
            definition_name="drain_node",
            target_type="node",
            target_name="worker-1",
        )
        
        blast_radius = await safety_checker.assess_blast_radius(action)
        
        assert blast_radius.affected_nodes == 1
        assert blast_radius.affected_pods > 0
    
    @pytest.mark.asyncio
    async def test_requires_approval_production(self, safety_checker: SafetyChecker):
        """Test approval required for production namespace."""
        action = RemediationAction(
            definition_name="restart_pod",
            target_type="pod",
            target_name="api-server-xyz",
            target_namespace="production",
            safety_checks=[],
        )
        
        requires, reason = safety_checker.requires_approval(action, [])
        
        assert requires
        assert "production" in reason
    
    @pytest.mark.asyncio
    async def test_record_action_rate_limiting(self, safety_checker: SafetyChecker):
        """Test rate limiting via action recording."""
        action = RemediationAction(
            definition_name="restart_pod",
            target_type="pod",
            target_name="api-server-xyz",
            target_namespace="default",
        )
        
        # Record many actions
        for _ in range(10):
            await safety_checker.record_action(action)
        
        # Check rate limit - should fail due to per-target limit
        results = await safety_checker.check_action(action)
        
        # Verify rate limit check is working
        rate_limit_result = next(
            r for r in results if r.check_name == "rate_limits"
        )
        # 10 actions should exceed the default 5-per-target limit
        assert not rate_limit_result.passed
        assert "exceeded" in rate_limit_result.message.lower()
    
    def test_register_custom_check(self, safety_checker: SafetyChecker):
        """Test registering custom safety check."""
        async def custom_check(action, policy):
            return SafetyCheckResult(
                check_type=SafetyCheckType.PRE_FLIGHT,
                check_name="custom_check",
                passed=True,
                message="Custom check passed",
            )
        
        safety_checker.register_check("custom", custom_check)
        
        # Verify it's registered
        assert "custom" in safety_checker._custom_checks
    
    def test_get_check_summary(self, safety_checker: SafetyChecker):
        """Test getting check summary."""
        results = [
            SafetyCheckResult(
                check_type=SafetyCheckType.PRE_FLIGHT,
                check_name="check1",
                passed=True,
                message="OK",
            ),
            SafetyCheckResult(
                check_type=SafetyCheckType.PRE_FLIGHT,
                check_name="check2",
                passed=False,
                message="Failed",
                severity=RiskLevel.HIGH,
                is_blocking=True,
            ),
        ]
        
        summary = safety_checker.get_check_summary(results)
        
        assert summary["total_checks"] == 2
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert summary["blocking_failures"] == 1
        assert not summary["is_safe"]


# ============================================================================
# RollbackManager Tests
# ============================================================================

class TestRollbackManager:
    """Tests for RollbackManager."""
    
    @pytest.mark.asyncio
    async def test_capture_state(self, rollback_manager: RollbackManager):
        """Test state capture."""
        action_id = uuid4()
        
        snapshot = await rollback_manager.capture_state(
            action_id=action_id,
            resource_type="deployment",
            resource_name="api-server",
            resource_namespace="production",
            state_data={"replicas": 3, "image": "api:v1.0"},
        )
        
        assert snapshot.action_id == action_id
        assert snapshot.resource_type == "deployment"
        assert snapshot.state_data["replicas"] == 3
        assert snapshot.state_hash is not None
    
    @pytest.mark.asyncio
    async def test_create_checkpoint(self, rollback_manager: RollbackManager):
        """Test checkpoint creation."""
        action_id = uuid4()
        
        # Capture some state first
        snapshot = await rollback_manager.capture_state(
            action_id=action_id,
            resource_type="deployment",
            resource_name="api-server",
            resource_namespace="production",
            state_data={"replicas": 3},
        )
        
        checkpoint = await rollback_manager.create_checkpoint(
            action_id=action_id,
            name="pre-scale",
            description="State before scaling",
        )
        
        assert checkpoint.action_id == action_id
        assert checkpoint.name == "pre-scale"
        assert len(checkpoint.snapshots) == 1
        assert checkpoint.is_valid
        assert not checkpoint.is_expired
    
    @pytest.mark.asyncio
    async def test_get_latest_checkpoint(self, rollback_manager: RollbackManager):
        """Test getting latest checkpoint."""
        action_id = uuid4()
        
        await rollback_manager.capture_state(
            action_id=action_id,
            resource_type="deployment",
            resource_name="api-server",
            state_data={"step": 1},
        )
        
        await rollback_manager.create_checkpoint(
            action_id=action_id,
            name="checkpoint-1",
        )
        
        await rollback_manager.capture_state(
            action_id=action_id,
            resource_type="deployment",
            resource_name="api-server",
            state_data={"step": 2},
        )
        
        await rollback_manager.create_checkpoint(
            action_id=action_id,
            name="checkpoint-2",
        )
        
        latest = await rollback_manager.get_latest_checkpoint(action_id)
        
        assert latest is not None
        assert latest.name == "checkpoint-2"
    
    @pytest.mark.asyncio
    async def test_create_rollback_plan(self, rollback_manager: RollbackManager):
        """Test rollback plan creation."""
        action = RemediationAction(
            definition_name="scale_deployment",
            target_type="deployment",
            target_name="api-server",
            target_namespace="production",
        )
        
        await rollback_manager.capture_state(
            action_id=action.id,
            resource_type="deployment",
            resource_name="api-server",
            resource_namespace="production",
            state_data={"replicas": 3},
        )
        
        await rollback_manager.create_checkpoint(
            action_id=action.id,
            name="pre-scale",
        )
        
        plan = await rollback_manager.create_rollback_plan(action)
        
        assert plan.action_id == action.id
        assert len(plan.steps) > 0
    
    @pytest.mark.asyncio
    async def test_execute_rollback(self, rollback_manager: RollbackManager):
        """Test rollback execution."""
        action = RemediationAction(
            definition_name="scale_deployment",
            target_type="deployment",
            target_name="api-server",
            target_namespace="production",
            rollback_data={"previous_replicas": 3},
        )
        
        await rollback_manager.capture_state(
            action_id=action.id,
            resource_type="deployment",
            resource_name="api-server",
            resource_namespace="production",
            state_data={"replicas": 3},
        )
        
        await rollback_manager.create_checkpoint(
            action_id=action.id,
            name="pre-scale",
        )
        
        # Register a handler
        async def restore_handler(resource_type, resource_name, namespace, state_data):
            return True
        
        result = await rollback_manager.execute_rollback(
            action,
            restore_handler=restore_handler,
        )
        
        assert result.success
        assert result.steps_completed > 0
    
    @pytest.mark.asyncio
    async def test_invalidate_checkpoints(self, rollback_manager: RollbackManager):
        """Test checkpoint invalidation."""
        action_id = uuid4()
        
        await rollback_manager.capture_state(
            action_id=action_id,
            resource_type="deployment",
            resource_name="api-server",
            state_data={"replicas": 3},
        )
        
        await rollback_manager.create_checkpoint(
            action_id=action_id,
            name="checkpoint-1",
        )
        
        count = await rollback_manager.invalidate_checkpoints(
            action_id,
            reason="Test invalidation",
        )
        
        assert count == 1
        
        # Should not find valid checkpoint
        latest = await rollback_manager.get_latest_checkpoint(action_id)
        assert latest is None
    
    def test_can_rollback_with_checkpoint(self, rollback_manager: RollbackManager):
        """Test can_rollback with checkpoint."""
        action = RemediationAction(
            definition_name="restart_pod",
            target_type="pod",
            target_name="api-server-xyz",
            can_rollback=True,
        )
        
        can_rollback, reason = rollback_manager.can_rollback(action)
        
        # No checkpoints yet
        assert not can_rollback
        assert "No checkpoints" in reason
    
    def test_can_rollback_with_rollback_data(self, rollback_manager: RollbackManager):
        """Test can_rollback with rollback data."""
        action = RemediationAction(
            definition_name="restart_pod",
            target_type="pod",
            target_name="api-server-xyz",
            rollback_data={"original_state": "running"},
        )
        
        # Register a handler
        async def handler(data):
            return True
        
        rollback_manager.register_handler("restart_pod", handler)
        
        can_rollback, reason = rollback_manager.can_rollback(action)
        
        assert can_rollback
        assert "handler available" in reason.lower()
    
    def test_get_stats(self, rollback_manager: RollbackManager):
        """Test getting rollback stats."""
        stats = rollback_manager.get_stats()
        
        assert "total_snapshots" in stats
        assert "total_checkpoints" in stats
        assert "registered_handlers" in stats


# ============================================================================
# ApprovalWorkflow Tests
# ============================================================================

class TestApprovalWorkflow:
    """Tests for ApprovalWorkflow."""
    
    @pytest.mark.asyncio
    async def test_request_approval(self, approval_workflow: ApprovalWorkflow):
        """Test creating approval request."""
        action = RemediationAction(
            definition_name="scale_deployment",
            target_type="deployment",
            target_name="api-server",
            target_namespace="production",
        )
        
        request = await approval_workflow.request_approval(
            action=action,
            reason="High-risk scaling operation",
            requested_by="autosre",
        )
        
        assert request.action_id == action.id
        assert request.status == ApprovalStatus.PENDING
        assert request.reason == "High-risk scaling operation"
        assert not request.is_expired
    
    @pytest.mark.asyncio
    async def test_approve_request(self, approval_workflow: ApprovalWorkflow):
        """Test approving a request."""
        action = RemediationAction(
            definition_name="restart_pod",
            target_type="pod",
            target_name="api-server-xyz",
        )
        
        request = await approval_workflow.request_approval(
            action=action,
            reason="Test",
        )
        
        success = await approval_workflow.approve(
            request.id,
            approved_by="sre-oncall",
            reason="Looks good",
        )
        
        assert success
        assert await approval_workflow.is_approved(request.id)
        assert not await approval_workflow.is_pending(request.id)
    
    @pytest.mark.asyncio
    async def test_reject_request(self, approval_workflow: ApprovalWorkflow):
        """Test rejecting a request."""
        action = RemediationAction(
            definition_name="drain_node",
            target_type="node",
            target_name="worker-1",
        )
        
        request = await approval_workflow.request_approval(
            action=action,
            reason="Test",
        )
        
        success = await approval_workflow.reject(
            request.id,
            rejected_by="sre-oncall",
            reason="Too risky",
        )
        
        assert success
        assert await approval_workflow.is_rejected(request.id)
    
    @pytest.mark.asyncio
    async def test_get_pending_requests(self, approval_workflow: ApprovalWorkflow):
        """Test getting pending requests."""
        for i in range(3):
            action = RemediationAction(
                definition_name=f"action_{i}",
                target_type="pod",
                target_name=f"pod-{i}",
            )
            
            await approval_workflow.request_approval(
                action=action,
                reason=f"Test {i}",
            )
        
        pending = await approval_workflow.get_pending_requests()
        
        assert len(pending) == 3
    
    @pytest.mark.asyncio
    async def test_decision_callback(self, approval_workflow: ApprovalWorkflow):
        """Test decision callbacks."""
        callback_called = False
        callback_status = None
        
        async def callback(request, status, reason):
            nonlocal callback_called, callback_status
            callback_called = True
            callback_status = status
        
        action = RemediationAction(
            definition_name="restart_pod",
            target_type="pod",
            target_name="api-server-xyz",
        )
        
        request = await approval_workflow.request_approval(
            action=action,
            reason="Test",
        )
        
        approval_workflow.on_decision(request.id, callback)
        
        await approval_workflow.approve(
            request.id,
            approved_by="sre-oncall",
        )
        
        assert callback_called
        assert callback_status == ApprovalStatus.APPROVED
    
    @pytest.mark.asyncio
    async def test_notification_handler(self, approval_workflow: ApprovalWorkflow):
        """Test notification handler."""
        notifications_sent = []
        
        async def handler(request, channel):
            notifications_sent.append((request.id, channel))
            return True
        
        approval_workflow.register_notification_handler(
            NotificationChannel.SLACK,
            handler,
        )
        
        action = RemediationAction(
            definition_name="restart_pod",
            target_type="pod",
            target_name="api-server-xyz",
        )
        
        await approval_workflow.request_approval(
            action=action,
            reason="Test",
            notification_channels=[NotificationChannel.SLACK],
        )
        
        assert len(notifications_sent) == 1
    
    def test_get_stats(self, approval_workflow: ApprovalWorkflow):
        """Test getting workflow stats."""
        stats = approval_workflow.get_stats()
        
        assert "total_requests" in stats
        assert "pending" in stats
        assert "approved" in stats
        assert "rejected" in stats


# ============================================================================
# RemediationEngine Tests
# ============================================================================

class TestRemediationEngine:
    """Tests for RemediationEngine."""
    
    @pytest.fixture
    def engine(self) -> RemediationEngine:
        """Create a remediation engine with registered actions."""
        config = EngineConfig(
            enable_safety_checks=True,
            enable_approvals=False,  # Disable for most tests
            enable_auto_rollback=True,
            force_dry_run=False,
        )
        
        engine = RemediationEngine(config=config)
        
        # Register a test action
        @engine.registry.register(
            name="test_restart",
            display_name="Test Restart",
            description="Test restart action",
            action_type=ActionType.RESTART,
            risk_level=RiskLevel.LOW,
            target_types=["pod"],
            cooldown_seconds=0,  # No cooldown for tests
        )
        async def test_restart(namespace: str = "default", name: str = "test"):
            return {"restarted": True}
        
        return engine
    
    def test_create_action(self, engine: RemediationEngine):
        """Test creating an action."""
        action = engine.create_action(
            definition_name="test_restart",
            target_type="pod",
            target_name="api-server-xyz",
            target_namespace="default",
        )
        
        assert action.definition_name == "test_restart"
        assert action.target_type == "pod"
        assert action.status == RemediationStatus.PENDING
    
    def test_create_action_dry_run(self, engine: RemediationEngine):
        """Test creating a dry-run action."""
        action = engine.create_action(
            definition_name="test_restart",
            target_type="pod",
            target_name="api-server-xyz",
            dry_run=True,
        )
        
        assert action.dry_run is True
    
    def test_create_action_nonexistent(self, engine: RemediationEngine):
        """Test creating action with non-existent definition."""
        with pytest.raises(ActionNotFoundError):
            engine.create_action(
                definition_name="nonexistent",
                target_type="pod",
                target_name="test",
            )
    
    @pytest.mark.asyncio
    async def test_execute_action_success(self, engine: RemediationEngine):
        """Test successful action execution."""
        action = engine.create_action(
            definition_name="test_restart",
            target_type="pod",
            target_name="api-server-xyz",
            target_namespace="default",
        )
        
        result = await engine.execute(action, skip_safety_checks=True)
        
        assert result.success
        assert result.status == RemediationStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_execute_action_dry_run(self, engine: RemediationEngine):
        """Test dry-run action execution."""
        action = engine.create_action(
            definition_name="test_restart",
            target_type="pod",
            target_name="api-server-xyz",
            dry_run=True,
        )
        
        result = await engine.execute(action, skip_safety_checks=True)
        
        assert result.success
    
    @pytest.mark.asyncio
    async def test_execute_action_safety_check_failure(self, engine: RemediationEngine):
        """Test action fails safety checks."""
        # Create engine with protected namespace
        config = EngineConfig(
            enable_safety_checks=True,
            safety_policy=SafetyPolicy(
                name="strict",
                protected_namespaces=["kube-system"],
            ),
        )
        engine = RemediationEngine(config=config)
        
        @engine.registry.register(
            name="test_action",
            display_name="Test",
            description="Test",
            action_type=ActionType.RESTART,
            cooldown_seconds=0,
        )
        async def test_action():
            return {}
        
        action = engine.create_action(
            definition_name="test_action",
            target_type="pod",
            target_name="coredns-xyz",
            target_namespace="kube-system",
        )
        
        result = await engine.execute(action)
        
        assert not result.success
        assert "safety" in result.message.lower() or "protected" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_execute_plan_sequential(self, engine: RemediationEngine):
        """Test executing a sequential plan."""
        actions = [
            engine.create_action(
                definition_name="test_restart",
                target_type="pod",
                target_name=f"pod-{i}",
                target_namespace="default",
            )
            for i in range(3)
        ]
        
        plan = RemediationPlan(
            name="Test Plan",
            description="Test sequential plan",
            actions=actions,
            parallel=False,
        )
        
        results = await engine.execute_plan(plan, skip_safety_checks=True)
        
        assert len(results) == 3
        assert all(r.success for r in results)
        assert plan.status == RemediationStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_execute_plan_parallel(self, engine: RemediationEngine):
        """Test executing a parallel plan."""
        actions = [
            engine.create_action(
                definition_name="test_restart",
                target_type="pod",
                target_name=f"pod-{i}",
                target_namespace="default",
            )
            for i in range(3)
        ]
        
        plan = RemediationPlan(
            name="Test Plan",
            description="Test parallel plan",
            actions=actions,
            parallel=True,
        )
        
        results = await engine.execute_plan(plan, skip_safety_checks=True)
        
        assert len(results) == 3
        assert all(r.success for r in results)
    
    @pytest.mark.asyncio
    async def test_pre_execution_hook(self, engine: RemediationEngine):
        """Test pre-execution hook."""
        hook_called = False
        
        async def pre_hook(ctx):
            nonlocal hook_called
            hook_called = True
            return True  # Allow execution
        
        engine.add_pre_hook(pre_hook)
        
        action = engine.create_action(
            definition_name="test_restart",
            target_type="pod",
            target_name="api-server-xyz",
        )
        
        await engine.execute(action, skip_safety_checks=True)
        
        assert hook_called
    
    @pytest.mark.asyncio
    async def test_pre_execution_hook_cancel(self, engine: RemediationEngine):
        """Test pre-execution hook cancels execution."""
        async def cancel_hook(ctx):
            return False  # Cancel execution
        
        engine.add_pre_hook(cancel_hook)
        
        action = engine.create_action(
            definition_name="test_restart",
            target_type="pod",
            target_name="api-server-xyz",
        )
        
        result = await engine.execute(action, skip_safety_checks=True)
        
        assert not result.success
        assert result.status == RemediationStatus.CANCELLED
    
    @pytest.mark.asyncio
    async def test_post_execution_hook(self, engine: RemediationEngine):
        """Test post-execution hook."""
        hook_result = None
        
        async def post_hook(ctx, result):
            nonlocal hook_result
            hook_result = result
        
        engine.add_post_hook(post_hook)
        
        action = engine.create_action(
            definition_name="test_restart",
            target_type="pod",
            target_name="api-server-xyz",
        )
        
        await engine.execute(action, skip_safety_checks=True)
        
        assert hook_result is not None
        assert hook_result.success
    
    def test_get_execution_history(self, engine: RemediationEngine):
        """Test getting execution history."""
        history = engine.get_execution_history()
        
        # Initially empty
        assert len(history) == 0
    
    def test_get_stats(self, engine: RemediationEngine):
        """Test getting engine stats."""
        stats = engine.get_stats()
        
        assert "total_executions" in stats
        assert "successful" in stats
        assert "failed" in stats
        assert "registry_stats" in stats


# ============================================================================
# Model Tests
# ============================================================================

class TestRemediationModels:
    """Tests for remediation models."""
    
    def test_blast_radius_risk_score(self):
        """Test blast radius risk score calculation."""
        br = BlastRadius(
            affected_pods=5,
            affected_nodes=0,
            downtime_risk=0.2,
            data_loss_risk=0.0,
            cascading_failure_risk=0.1,
        )
        
        score = br.overall_risk_score
        
        assert 0 <= score <= 1
        assert score < 0.5  # Low risk
    
    def test_blast_radius_high_risk(self):
        """Test high-risk blast radius."""
        br = BlastRadius(
            affected_pods=100,
            affected_nodes=5,
            downtime_risk=0.8,
            data_loss_risk=0.3,
            cascading_failure_risk=0.5,
        )
        
        assert not br.is_safe
        assert br.overall_risk_score > 0.5
    
    def test_action_duration_calculation(self):
        """Test action duration calculation."""
        action = RemediationAction(
            definition_name="test",
            target_type="pod",
            target_name="test",
            started_at=datetime.utcnow() - timedelta(seconds=30),
            completed_at=datetime.utcnow(),
        )
        
        assert action.duration_seconds is not None
        assert 29 <= action.duration_seconds <= 31
    
    def test_action_is_terminal(self):
        """Test action terminal state check."""
        action = RemediationAction(
            definition_name="test",
            target_type="pod",
            target_name="test",
            status=RemediationStatus.PENDING,
        )
        
        assert not action.is_terminal
        
        action.status = RemediationStatus.COMPLETED
        assert action.is_terminal
        
        action.status = RemediationStatus.FAILED
        assert action.is_terminal
    
    def test_plan_get_next_action(self):
        """Test plan next action retrieval."""
        actions = [
            RemediationAction(
                definition_name="action1",
                target_type="pod",
                target_name="pod-1",
                status=RemediationStatus.COMPLETED,
            ),
            RemediationAction(
                definition_name="action2",
                target_type="pod",
                target_name="pod-2",
                status=RemediationStatus.PENDING,
            ),
            RemediationAction(
                definition_name="action3",
                target_type="pod",
                target_name="pod-3",
                status=RemediationStatus.PENDING,
            ),
        ]
        
        plan = RemediationPlan(
            name="Test",
            description="Test plan",
            actions=actions,
        )
        
        next_action = plan.get_next_action()
        
        assert next_action is not None
        assert next_action.definition_name == "action2"
    
    def test_result_to_summary(self):
        """Test result summary generation."""
        result = RemediationResult(
            action_id=uuid4(),
            success=True,
            status=RemediationStatus.COMPLETED,
            message="Pod restarted successfully",
            started_at=datetime.utcnow() - timedelta(seconds=5),
            resources_modified=["default/pod/api-server-xyz"],
        )
        
        summary = result.to_summary()
        
        assert "SUCCESS" in summary
        assert "Pod restarted" in summary
        assert "Duration" in summary
    
    def test_approval_request_expiry(self):
        """Test approval request expiry."""
        request = ApprovalRequest(
            action_id=uuid4(),
            action_name="test",
            reason="Test",
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )
        
        assert request.is_expired
        assert request.time_remaining_seconds == 0
    
    def test_action_parameter_validation(self):
        """Test action parameter validation."""
        param = ActionParameter(
            name="replicas",
            type="int",
            required=True,
            min_value=1,
            max_value=100,
        )
        
        # Valid
        is_valid, error = param.validate_value(5)
        assert is_valid
        assert error is None
        
        # Too low
        is_valid, error = param.validate_value(0)
        assert not is_valid
        
        # Too high
        is_valid, error = param.validate_value(200)
        assert not is_valid
        
        # Wrong type
        is_valid, error = param.validate_value("five")
        assert not is_valid
    
    def test_action_parameter_allowed_values(self):
        """Test action parameter allowed values validation."""
        param = ActionParameter(
            name="strategy",
            type="str",
            required=True,
            allowed_values=["rolling", "recreate", "blue-green"],
        )
        
        # Valid
        is_valid, error = param.validate_value("rolling")
        assert is_valid
        
        # Invalid
        is_valid, error = param.validate_value("canary")
        assert not is_valid
