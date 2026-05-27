"""
Tests for Cascading Failure and Recovery Modules

Tests cascading failure detection, pattern analysis, and recovery planning.
"""

import pytest
from datetime import datetime, timedelta, timezone

from autosre.skills.cascading_failure import (
    CascadingFailureAnalyzer,
    CascadePattern,
    CascadeDetection,
    FailureStage,
    ServiceMetrics,
)
from autosre.skills.recovery import (
    RecoveryPlanner,
    RecoveryPlan,
    RecoveryAction,
    RecoveryStage,
    LoadProfile,
)


class TestServiceMetrics:
    """Tests for ServiceMetrics."""
    
    def test_accept_reject_ratio(self):
        """Test accept/reject ratio calculation."""
        metrics = ServiceMetrics(
            service="api",
            request_rate=1000,
            accept_rate=800,
            reject_rate=200,
            error_rate=0.05,
        )
        
        assert metrics.accept_reject_ratio == 0.8
    
    def test_accept_reject_ratio_no_rejections(self):
        """Test ratio with no rejections."""
        metrics = ServiceMetrics(
            service="api",
            request_rate=1000,
            accept_rate=1000,
            reject_rate=0,
            error_rate=0.01,
        )
        
        assert metrics.accept_reject_ratio == 1.0
    
    def test_connection_pool_utilization(self):
        """Test connection pool utilization."""
        metrics = ServiceMetrics(
            service="api",
            request_rate=1000,
            accept_rate=1000,
            reject_rate=0,
            error_rate=0.01,
            connection_pool_used=80,
            connection_pool_max=100,
        )
        
        assert metrics.connection_pool_utilization == 0.8


class TestCascadingFailureAnalyzer:
    """Tests for CascadingFailureAnalyzer."""
    
    def test_detect_healthy(self):
        """Test detection with healthy services."""
        analyzer = CascadingFailureAnalyzer()
        
        metrics = [
            ServiceMetrics(
                service="api",
                request_rate=1000,
                accept_rate=990,
                reject_rate=10,
                error_rate=0.01,
                cpu_percent=50,
                memory_percent=60,
            ),
        ]
        
        result = analyzer.analyze(metrics)
        
        assert not result.is_cascading
        assert result.stage == FailureStage.HEALTHY
        assert len(result.patterns) == 0
    
    def test_detect_client_retry_storm(self):
        """Test detection of client retry storm."""
        analyzer = CascadingFailureAnalyzer()
        
        metrics = [
            ServiceMetrics(
                service="api",
                request_rate=1000,
                accept_rate=400,  # Only 40% accepted
                reject_rate=600,
                error_rate=0.30,
            ),
        ]
        
        result = analyzer.analyze(metrics)
        
        assert CascadePattern.CLIENT_RETRY_STORM in result.patterns
        assert result.stage == FailureStage.DEGRADED
    
    def test_detect_queue_saturation(self):
        """Test detection of queue saturation."""
        analyzer = CascadingFailureAnalyzer()
        
        metrics = [
            ServiceMetrics(
                service="api",
                request_rate=1000,
                accept_rate=900,
                reject_rate=100,
                error_rate=0.10,
                queue_depth=500,
                queue_wait_p99_ms=6000,  # 6 second queue wait
                queue_mode="fifo",
            ),
        ]
        
        result = analyzer.analyze(metrics)
        
        assert CascadePattern.QUEUE_SATURATION in result.patterns
        assert any("FIFO" in t.get("note", "") for t in result.triggers)
    
    def test_detect_resource_exhaustion(self):
        """Test detection of resource exhaustion."""
        analyzer = CascadingFailureAnalyzer()
        
        metrics = [
            ServiceMetrics(
                service="api",
                request_rate=1000,
                accept_rate=900,
                reject_rate=100,
                error_rate=0.10,
                cpu_percent=95,  # High CPU
            ),
        ]
        
        result = analyzer.analyze(metrics)
        
        assert CascadePattern.RESOURCE_EXHAUSTION in result.patterns
    
    def test_detect_gc_pressure(self):
        """Test detection of GC pressure."""
        analyzer = CascadingFailureAnalyzer()
        
        metrics = [
            ServiceMetrics(
                service="api",
                request_rate=1000,
                accept_rate=900,
                reject_rate=100,
                error_rate=0.10,
                gc_pause_ms=800,  # Long GC pauses
            ),
        ]
        
        result = analyzer.analyze(metrics)
        
        assert CascadePattern.GC_PRESSURE in result.patterns
    
    def test_detect_connection_pool_exhaustion(self):
        """Test detection of connection pool exhaustion."""
        analyzer = CascadingFailureAnalyzer()
        
        metrics = [
            ServiceMetrics(
                service="api",
                request_rate=1000,
                accept_rate=900,
                reject_rate=100,
                error_rate=0.10,
                connection_pool_used=95,
                connection_pool_max=100,
            ),
        ]
        
        result = analyzer.analyze(metrics)
        
        assert CascadePattern.CONNECTION_POOL_EXHAUSTION in result.patterns
    
    def test_detect_cascading(self):
        """Test detection of cascading failure across services."""
        analyzer = CascadingFailureAnalyzer()
        
        metrics = [
            ServiceMetrics(
                service="api-gateway",
                request_rate=1000,
                accept_rate=400,
                reject_rate=600,
                error_rate=0.35,
                queue_wait_p99_ms=8000,
            ),
            ServiceMetrics(
                service="backend",
                request_rate=800,
                accept_rate=300,
                reject_rate=500,
                error_rate=0.40,
                cpu_percent=95,
            ),
            ServiceMetrics(
                service="database",
                request_rate=500,
                accept_rate=200,
                reject_rate=300,
                error_rate=0.50,
                connection_pool_used=98,
                connection_pool_max=100,
            ),
        ]
        
        result = analyzer.analyze(metrics)
        
        assert result.is_cascading
        assert result.stage == FailureStage.CRITICAL
        assert result.confidence > 0.7
        assert len(result.affected_services) == 3
        assert result.origin_service == "api-gateway"
    
    def test_immediate_actions_generated(self):
        """Test that immediate actions are generated."""
        analyzer = CascadingFailureAnalyzer()
        
        metrics = [
            ServiceMetrics(
                service="api",
                request_rate=1000,
                accept_rate=400,
                reject_rate=600,
                error_rate=0.35,
                queue_wait_p99_ms=8000,
            ),
        ]
        
        result = analyzer.analyze(metrics)
        
        assert len(result.immediate_actions) > 0
    
    def test_recovery_requirements_calculated(self):
        """Test that recovery requirements are calculated."""
        analyzer = CascadingFailureAnalyzer()
        
        metrics = [
            ServiceMetrics(
                service="api",
                request_rate=1000,
                accept_rate=400,
                reject_rate=600,
                error_rate=0.35,
                gc_pause_ms=800,  # GC pressure
            ),
        ]
        
        result = analyzer.analyze(metrics)
        
        assert result.recovery_load_multiplier < 0.5  # Need significant reduction
        assert result.estimated_recovery_minutes > 10  # GC recovery takes time
    
    def test_get_summary(self):
        """Test summary generation."""
        result = CascadeDetection(
            is_cascading=True,
            stage=FailureStage.CRITICAL,
            confidence=0.9,
            patterns=[CascadePattern.CLIENT_RETRY_STORM, CascadePattern.QUEUE_SATURATION],
            origin_service="api",
            affected_services=["api", "backend"],
            immediate_actions=["Reduce load", "Enable circuit breakers"],
        )
        
        summary = result.get_summary()
        
        assert "CASCADING FAILURE" in summary
        assert "CRITICAL" in summary
        assert "api" in summary
        assert "backend" in summary
    
    def test_circuit_breaker_detection(self):
        """Test detection of open circuit breakers."""
        analyzer = CascadingFailureAnalyzer()
        
        metrics = [
            ServiceMetrics(
                service="api",
                request_rate=500,
                accept_rate=500,
                reject_rate=0,
                error_rate=0.05,
                circuit_breaker_open=True,
            ),
        ]
        
        result = analyzer.analyze(metrics)
        
        assert CascadePattern.CIRCUIT_BREAKER_OPEN in result.patterns


class TestLoadProfile:
    """Tests for LoadProfile."""
    
    def test_is_overloaded(self):
        """Test overload detection."""
        profile = LoadProfile(
            current_load_percent=80,
            target_load_percent=50,
            capacity_percent=60,
            normal_load_rps=1000,
            current_load_rps=800,
            safe_load_rps=600 * 0.8,  # 60% capacity with 20% headroom
        )
        
        assert profile.is_overloaded  # 800 > 480
    
    def test_headroom_percent(self):
        """Test headroom calculation."""
        profile = LoadProfile(
            current_load_percent=50,
            target_load_percent=50,
            capacity_percent=100,
            normal_load_rps=1000,
            current_load_rps=500,
            safe_load_rps=800,  # 80% of capacity is safe
        )
        
        # Headroom = (800 - 500) / 800 = 37.5%
        assert 37 < profile.headroom_percent < 38


class TestRecoveryPlanner:
    """Tests for RecoveryPlanner."""
    
    def test_create_plan_basic(self):
        """Test basic plan creation."""
        planner = RecoveryPlanner()
        
        plan = planner.create_plan(
            service="api",
            current_capacity_percent=50,
            normal_load_rps=1000,
            current_load_rps=800,
        )
        
        assert plan.service == "api"
        assert plan.stage == RecoveryStage.NOT_STARTED
        assert len(plan.actions) > 0
        
        # Should start with load reduction
        assert plan.actions[0].action_type == "reduce_load"
    
    def test_plan_includes_stabilization(self):
        """Test that plan includes stabilization wait."""
        planner = RecoveryPlanner()
        
        plan = planner.create_plan(
            service="api",
            current_capacity_percent=50,
            normal_load_rps=1000,
            current_load_rps=800,
        )
        
        wait_actions = [a for a in plan.actions if a.action_type == "wait"]
        assert len(wait_actions) > 0
    
    def test_plan_gradual_increase(self):
        """Test that plan includes gradual load increase."""
        planner = RecoveryPlanner()
        
        plan = planner.create_plan(
            service="api",
            current_capacity_percent=50,
            normal_load_rps=1000,
            current_load_rps=800,
        )
        
        increase_actions = [a for a in plan.actions if a.action_type == "increase_load"]
        
        # Should have multiple increments to reach 100%
        assert len(increase_actions) >= 3
        
        # Each increment should have monitoring after
        monitor_actions = [a for a in plan.actions if a.action_type == "monitor"]
        assert len(monitor_actions) >= len(increase_actions)
    
    def test_plan_has_abort_conditions(self):
        """Test that actions have abort conditions."""
        planner = RecoveryPlanner()
        
        plan = planner.create_plan(
            service="api",
            current_capacity_percent=50,
            normal_load_rps=1000,
            current_load_rps=800,
        )
        
        # Load increase actions should have abort conditions
        increase_actions = [a for a in plan.actions if a.action_type == "increase_load"]
        for action in increase_actions:
            assert len(action.abort_conditions) > 0
    
    def test_plan_estimated_completion(self):
        """Test that estimated completion is calculated."""
        planner = RecoveryPlanner()
        
        plan = planner.create_plan(
            service="api",
            current_capacity_percent=50,
            normal_load_rps=1000,
            current_load_rps=800,
        )
        
        assert plan.estimated_completion is not None
        assert plan.estimated_completion > datetime.now(timezone.utc)
    
    def test_plan_progress_tracking(self):
        """Test progress tracking."""
        planner = RecoveryPlanner()
        
        plan = planner.create_plan(
            service="api",
            current_capacity_percent=50,
            normal_load_rps=1000,
            current_load_rps=800,
        )
        
        assert plan.progress_percent == 0
        
        # Mark some actions complete
        plan.actions[0].status = "complete"
        plan.actions[1].status = "complete"
        
        assert plan.progress_percent > 0
    
    def test_plan_summary(self):
        """Test plan summary generation."""
        planner = RecoveryPlanner()
        
        plan = planner.create_plan(
            service="api",
            current_capacity_percent=50,
            normal_load_rps=1000,
            current_load_rps=800,
        )
        
        summary = plan.get_summary()
        
        assert "api" in summary
        assert "50%" in summary or "50" in summary
        assert "Recovery Plan" in summary
    
    def test_load_reduction_commands(self):
        """Test load reduction command generation."""
        planner = RecoveryPlanner()
        
        commands = planner.get_load_reduction_commands("api", 30)
        
        assert len(commands) > 0
        
        # Should have Kubernetes command
        k8s_commands = [c for c in commands if c["platform"] == "kubernetes"]
        assert len(k8s_commands) > 0
        
        # Should have Istio command
        istio_commands = [c for c in commands if c["platform"] == "istio"]
        assert len(istio_commands) > 0


class TestRecoveryAction:
    """Tests for RecoveryAction."""
    
    def test_action_creation(self):
        """Test action creation."""
        action = RecoveryAction(
            action_id="action-0",
            action_type="reduce_load",
            description="Reduce load to 30%",
            target_value=300,
            duration_minutes=2,
            success_conditions=["error_rate < 0.05"],
            abort_conditions=["error_rate > 0.5"],
        )
        
        assert action.status == "pending"
        assert action.target_value == 300
    
    def test_action_serialization(self):
        """Test action serialization."""
        action = RecoveryAction(
            action_id="action-0",
            action_type="reduce_load",
            description="Reduce load to 30%",
            target_value=300,
            duration_minutes=2,
        )
        
        d = action.to_dict()
        
        assert d["action_id"] == "action-0"
        assert d["action_type"] == "reduce_load"
        assert d["target_value"] == 300


class TestRecoveryIntegration:
    """Integration tests for cascading failure and recovery."""
    
    def test_cascade_to_recovery_flow(self):
        """Test flow from cascade detection to recovery planning."""
        # Detect cascade - need multiple services for is_cascading=True
        analyzer = CascadingFailureAnalyzer()
        
        metrics = [
            ServiceMetrics(
                service="api",
                request_rate=1000,
                accept_rate=400,
                reject_rate=600,
                error_rate=0.35,
                cpu_percent=95,
            ),
            ServiceMetrics(
                service="backend",
                request_rate=800,
                accept_rate=300,
                reject_rate=500,
                error_rate=0.40,
                cpu_percent=90,
            ),
        ]
        
        detection = analyzer.analyze(metrics)
        
        assert detection.is_cascading  # Now true with multiple affected services
        
        # Create recovery plan based on detection
        planner = RecoveryPlanner()
        
        plan = planner.create_plan(
            service="api",
            current_capacity_percent=40,  # Based on accept rate
            normal_load_rps=1000,
            current_load_rps=metrics[0].request_rate,
        )
        
        # Verify plan uses appropriate recovery multiplier
        assert plan.load_profile.target_load_percent <= 30  # Start low
        
        # First action should reduce load significantly
        first_action = plan.actions[0]
        assert first_action.action_type == "reduce_load"
        assert first_action.target_value < 400  # Below current accept rate
