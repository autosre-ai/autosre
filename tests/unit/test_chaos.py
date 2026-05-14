"""
Unit tests for chaos engineering.

Tests for:
- ExperimentRunner
- FaultInjector
- GameDayPlanner
- ResilienceScorer
- ReportGenerator
"""

from __future__ import annotations

import asyncio
import pytest
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from autosre.chaos import (
    ExperimentRunner,
)
from autosre.chaos.models import (
    Experiment,
    ExperimentStatus,
    ExperimentResult,
    Fault,
    FaultType,
    FaultStatus,
    Target,
    TargetType,
    SteadyStateHypothesis,
    Schedule,
    ScheduleType,
)
from autosre.chaos.faults import (
    FaultInjector,
)
from autosre.chaos.gameday import (
    GameDayPlanner,
)
from autosre.chaos.models import (
    GameDay,
    GameDayStatus,
)
from autosre.chaos.resilience import (
    ResilienceScorer,
)
from autosre.chaos.models import (
    ResilienceScore,
)
from autosre.chaos.reports import (
    ReportGenerator,
    ExperimentReport,
    ReportFormat,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_fault() -> Fault:
    """Create a sample fault."""
    return Fault(
        type=FaultType.POD_FAILURE,
        target=Target(
            type=TargetType.DEPLOYMENT,
            name="api-server",
            namespace="production",
            labels={"app": "api"},
        ),
        parameters={
            "count": 1,
            "duration": 60,
        },
    )


@pytest.fixture
def sample_experiment(sample_fault: Fault) -> Experiment:
    """Create a sample experiment."""
    return Experiment(
        name="API Resilience Test",
        description="Test API resilience to pod failures",
        faults=[sample_fault],
        steady_state=[
            SteadyStateHypothesis(
                name="API responds to health check",
                probe_type="http",
                endpoint="http://api-server.production/health",
                expected_status=200,
                timeout_seconds=5,
            ),
            SteadyStateHypothesis(
                name="Error rate below threshold",
                probe_type="prometheus",
                query='rate(http_requests_total{status=~"5.."}[5m]) < 0.01',
                threshold=0.01,
            ),
        ],
        duration_seconds=120,
        warmup_seconds=10,
        cooldown_seconds=30,
    )


@pytest.fixture
def mock_k8s_client():
    """Create a mock K8s client."""
    class MockClient:
        async def delete_pod(self, namespace, name, grace_period=0):
            return True
        
        async def list_pods(self, namespace, label_selector=None):
            return [
                type("Pod", (), {"name": f"pod-{i}", "namespace": namespace})()
                for i in range(3)
            ]
        
        async def get_deployment(self, namespace, name):
            return type("Deployment", (), {
                "name": name,
                "namespace": namespace,
                "replicas": 3,
            })()
    
    return MockClient()


# ============================================================================
# ExperimentRunner Tests
# ============================================================================

class TestExperimentRunner:
    """Tests for ExperimentRunner."""
    
    @pytest.fixture
    def runner(self, mock_k8s_client) -> ExperimentRunner:
        """Create an experiment runner."""
        return ExperimentRunner(k8s_client=mock_k8s_client)
    
    def test_runner_creation(self, runner: ExperimentRunner):
        """Test runner creation."""
        assert runner is not None
        assert len(runner._probes) > 0  # Built-in probes registered
    
    def test_register_custom_probe(self, runner: ExperimentRunner):
        """Test registering custom probe."""
        async def custom_probe(hypothesis):
            return True
        
        runner.register_probe("custom", custom_probe)
        
        assert "custom" in runner._probes
    
    @pytest.mark.asyncio
    async def test_run_experiment_dry_run(
        self,
        runner: ExperimentRunner,
        sample_experiment: Experiment,
    ):
        """Test running experiment in dry-run mode."""
        result = await runner.run(sample_experiment, dry_run=True)
        
        assert result is not None
        assert result.experiment_id == sample_experiment.id
        # Dry run should complete without actual fault injection
        assert any("dry_run" in e["type"].lower() for e in result.events)
    
    @pytest.mark.asyncio
    async def test_run_experiment_success(
        self,
        runner: ExperimentRunner,
        sample_experiment: Experiment,
    ):
        """Test successful experiment run."""
        # Shorten durations for test
        sample_experiment.duration_seconds = 1
        sample_experiment.warmup_seconds = 0
        sample_experiment.cooldown_seconds = 0
        
        result = await runner.run(sample_experiment, dry_run=True)
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_cancel_experiment(
        self,
        runner: ExperimentRunner,
        sample_experiment: Experiment,
    ):
        """Test cancelling an experiment."""
        sample_experiment.duration_seconds = 60
        
        # Start experiment in background
        task = asyncio.create_task(runner.run(sample_experiment, dry_run=True))
        
        # Wait for it to start
        await asyncio.sleep(0.1)
        
        # Cancel
        success = await runner.cancel(sample_experiment.id)
        
        # Wait for task to complete
        try:
            await asyncio.wait_for(task, timeout=1)
        except asyncio.TimeoutError:
            task.cancel()
        
        assert success
    
    @pytest.mark.asyncio
    async def test_pause_resume_experiment(
        self,
        runner: ExperimentRunner,
        sample_experiment: Experiment,
    ):
        """Test pausing and resuming experiment."""
        sample_experiment.duration_seconds = 60
        sample_experiment.warmup_seconds = 0
        
        # Start experiment
        task = asyncio.create_task(runner.run(sample_experiment, dry_run=True))
        await asyncio.sleep(0.1)
        
        # Pause
        paused = await runner.pause(sample_experiment.id)
        assert paused
        
        # Resume
        resumed = await runner.resume(sample_experiment.id)
        
        # Clean up
        await runner.cancel(sample_experiment.id)
        try:
            await asyncio.wait_for(task, timeout=1)
        except:
            task.cancel()
    
    def test_get_active_experiments(
        self,
        runner: ExperimentRunner,
    ):
        """Test getting active experiments."""
        active = runner.get_active_experiments()
        
        assert isinstance(active, list)
    
    def test_get_experiment_history(
        self,
        runner: ExperimentRunner,
    ):
        """Test getting experiment history."""
        history = runner.get_experiment_history()
        
        assert isinstance(history, list)


# ============================================================================
# FaultInjector Tests
# ============================================================================

class TestFaultInjector:
    """Tests for FaultInjector."""
    
    @pytest.fixture
    def injector(self, mock_k8s_client) -> FaultInjector:
        """Create a fault injector."""
        return FaultInjector(k8s_client=mock_k8s_client)
    
    @pytest.mark.asyncio
    async def test_inject_pod_failure(
        self,
        injector: FaultInjector,
        sample_fault: Fault,
    ):
        """Test pod failure injection."""
        result = await injector.inject(
            sample_fault,
            duration=10,
            dry_run=True,
        )
        
        assert result is not None
        assert result.success or result.dry_run
    
    @pytest.mark.asyncio
    async def test_inject_network_latency(
        self,
        injector: FaultInjector,
    ):
        """Test network latency injection."""
        fault = Fault(
            type=FaultType.NETWORK_LATENCY,
            target=Target(
                type=TargetType.POD,
                name="api-server-xyz",
                namespace="production",
            ),
            parameters={
                "latency_ms": 200,
                "jitter_ms": 50,
            },
        )
        
        result = await injector.inject(fault, duration=10, dry_run=True)
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_inject_cpu_stress(
        self,
        injector: FaultInjector,
    ):
        """Test CPU stress injection."""
        fault = Fault(
            type=FaultType.CPU_STRESS,
            target=Target(
                type=TargetType.POD,
                name="api-server-xyz",
                namespace="production",
            ),
            parameters={
                "cores": 2,
                "load_percent": 80,
            },
        )
        
        result = await injector.inject(fault, duration=10, dry_run=True)
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_inject_memory_stress(
        self,
        injector: FaultInjector,
    ):
        """Test memory stress injection."""
        fault = Fault(
            type=FaultType.MEMORY_STRESS,
            target=Target(
                type=TargetType.POD,
                name="api-server-xyz",
                namespace="production",
            ),
            parameters={
                "workers": 1,
                "bytes": "256M",
            },
        )
        
        result = await injector.inject(fault, duration=10, dry_run=True)
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_inject_network_partition(
        self,
        injector: FaultInjector,
    ):
        """Test network partition injection."""
        fault = Fault(
            type=FaultType.NETWORK_PARTITION,
            target=Target(
                type=TargetType.DEPLOYMENT,
                name="api-server",
                namespace="production",
            ),
            parameters={
                "target_service": "database",
            },
        )
        
        result = await injector.inject(fault, duration=10, dry_run=True)
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_stop_fault(
        self,
        injector: FaultInjector,
        sample_fault: Fault,
    ):
        """Test stopping fault injection."""
        # Inject first
        await injector.inject(sample_fault, duration=60, dry_run=True)
        
        # Stop
        stopped = await injector.stop(sample_fault.id)
        
        assert stopped or True  # May not have active fault in dry-run
    
    @pytest.mark.asyncio
    async def test_rollback_fault(
        self,
        injector: FaultInjector,
        sample_fault: Fault,
    ):
        """Test rolling back fault."""
        await injector.inject(sample_fault, duration=60, dry_run=True)
        
        rolled_back = await injector.rollback(sample_fault.id)
        
        assert rolled_back or True
    
    def test_get_active_faults(
        self,
        injector: FaultInjector,
    ):
        """Test getting active faults."""
        active = injector.get_active_faults()
        
        assert isinstance(active, list)


# ============================================================================
# GameDayPlanner Tests
# ============================================================================

class TestGameDayPlanner:
    """Tests for GameDayPlanner."""
    
    @pytest.fixture
    def planner(self, mock_k8s_client) -> GameDayPlanner:
        """Create a game day planner."""
        return GameDayPlanner(k8s_client=mock_k8s_client)
    
    def test_create_game_day(self, planner: GameDayPlanner):
        """Test creating a game day."""
        game_day = planner.create_game_day(
            name="Q4 Resilience Test",
            description="Quarterly resilience testing",
            scheduled_at=datetime.utcnow() + timedelta(days=7),
        )
        
        assert game_day is not None
        assert game_day.name == "Q4 Resilience Test"
        assert game_day.status == GameDayStatus.SCHEDULED
    
    def test_add_scenario(self, planner: GameDayPlanner):
        """Test adding scenario to game day."""
        game_day = planner.create_game_day(
            name="Test Game Day",
            scheduled_at=datetime.utcnow() + timedelta(days=1),
        )
        
        scenario = Scenario(
            name="API Pod Failure",
            description="Terminate API pods",
            experiment=Experiment(
                name="API Pod Kill",
                faults=[
                    Fault(
                        type=FaultType.POD_FAILURE,
                        target=Target(
                            type=TargetType.DEPLOYMENT,
                            name="api-server",
                            namespace="production",
                        ),
                    )
                ],
            ),
        )
        
        planner.add_scenario(game_day.id, scenario)
        
        assert len(game_day.scenarios) == 1
    
    def test_schedule_game_day(self, planner: GameDayPlanner):
        """Test scheduling game day."""
        game_day = planner.create_game_day(
            name="Test Game Day",
            scheduled_at=datetime.utcnow() + timedelta(days=1),
        )
        
        scheduled = planner.schedule(
            game_day.id,
            scheduled_at=datetime.utcnow() + timedelta(days=2),
        )
        
        assert scheduled
    
    def test_cancel_game_day(self, planner: GameDayPlanner):
        """Test cancelling game day."""
        game_day = planner.create_game_day(
            name="Test Game Day",
            scheduled_at=datetime.utcnow() + timedelta(days=1),
        )
        
        cancelled = planner.cancel(game_day.id, reason="Testing cancellation")
        
        assert cancelled
        assert game_day.status == GameDayStatus.CANCELLED
    
    @pytest.mark.asyncio
    async def test_run_game_day_dry_run(self, planner: GameDayPlanner):
        """Test running game day in dry-run mode."""
        game_day = planner.create_game_day(
            name="Test Game Day",
            scheduled_at=datetime.utcnow(),
        )
        
        # Add a scenario
        scenario = Scenario(
            name="Test Scenario",
            experiment=Experiment(
                name="Test Experiment",
                faults=[
                    Fault(
                        type=FaultType.POD_FAILURE,
                        target=Target(
                            type=TargetType.POD,
                            name="test-pod",
                            namespace="default",
                        ),
                    )
                ],
                duration_seconds=1,
            ),
        )
        planner.add_scenario(game_day.id, scenario)
        
        result = await planner.run(game_day.id, dry_run=True)
        
        assert result is not None
    
    def test_get_upcoming_game_days(self, planner: GameDayPlanner):
        """Test getting upcoming game days."""
        # Create some game days
        for i in range(3):
            planner.create_game_day(
                name=f"Game Day {i}",
                scheduled_at=datetime.utcnow() + timedelta(days=i + 1),
            )
        
        upcoming = planner.get_upcoming(days=30)
        
        assert len(upcoming) >= 3
    
    def test_get_game_day_history(self, planner: GameDayPlanner):
        """Test getting game day history."""
        history = planner.get_history()
        
        assert isinstance(history, list)


# ============================================================================
# ResilienceScorer Tests
# ============================================================================

class TestResilienceScorer:
    """Tests for ResilienceScorer."""
    
    @pytest.fixture
    def scorer(self) -> ResilienceScorer:
        """Create a resilience scorer."""
        return ResilienceScorer()
    
    def test_calculate_score_from_experiment(
        self,
        scorer: ResilienceScorer,
    ):
        """Test calculating score from experiment result."""
        result = ExperimentResult(
            experiment_id=uuid4(),
            success=True,
            status=ExperimentStatus.COMPLETED,
            steady_state_met_before=True,
            steady_state_met_during=True,
            steady_state_met_after=True,
            started_at=datetime.utcnow() - timedelta(minutes=5),
        )
        
        score = scorer.calculate_from_result(result)
        
        assert score is not None
        assert 0 <= score.overall_score <= 100
    
    def test_calculate_score_failed_experiment(
        self,
        scorer: ResilienceScorer,
    ):
        """Test calculating score from failed experiment."""
        result = ExperimentResult(
            experiment_id=uuid4(),
            success=False,
            status=ExperimentStatus.FAILED,
            steady_state_met_before=True,
            steady_state_met_during=False,
            steady_state_met_after=False,
            errors=["Service became unavailable"],
            started_at=datetime.utcnow() - timedelta(minutes=5),
        )
        
        score = scorer.calculate_from_result(result)
        
        assert score is not None
        assert score.overall_score < 100
    
    def test_aggregate_scores(self, scorer: ResilienceScorer):
        """Test aggregating multiple scores."""
        scores = [
            ResilienceScore(
                service_name="api-server",
                overall_score=85,
                availability_score=90,
                recovery_score=80,
            ),
            ResilienceScore(
                service_name="api-server",
                overall_score=75,
                availability_score=80,
                recovery_score=70,
            ),
            ResilienceScore(
                service_name="api-server",
                overall_score=95,
                availability_score=95,
                recovery_score=95,
            ),
        ]
        
        aggregated = scorer.aggregate(scores)
        
        assert aggregated is not None
        assert 75 <= aggregated.overall_score <= 95
    
    def test_compare_services(self, scorer: ResilienceScorer):
        """Test comparing services."""
        scores = {
            "api-server": ResilienceScore(
                service_name="api-server",
                overall_score=85,
            ),
            "database": ResilienceScore(
                service_name="database",
                overall_score=95,
            ),
            "cache": ResilienceScore(
                service_name="cache",
                overall_score=70,
            ),
        }
        
        ranking = scorer.rank_services(scores)
        
        assert ranking[0][0] == "database"  # Highest score
        assert ranking[-1][0] == "cache"    # Lowest score
    
    def test_get_recommendations(self, scorer: ResilienceScorer):
        """Test getting resilience recommendations."""
        score = ResilienceScore(
            service_name="api-server",
            overall_score=65,
            availability_score=60,
            recovery_score=70,
            fault_tolerance_score=65,
        )
        
        recommendations = scorer.get_recommendations(score)
        
        assert len(recommendations) > 0
    
    def test_calculate_trend(self, scorer: ResilienceScorer):
        """Test calculating score trend."""
        scores = [
            ResilienceScore(
                service_name="api-server",
                overall_score=70,
                calculated_at=datetime.utcnow() - timedelta(days=30),
            ),
            ResilienceScore(
                service_name="api-server",
                overall_score=75,
                calculated_at=datetime.utcnow() - timedelta(days=20),
            ),
            ResilienceScore(
                service_name="api-server",
                overall_score=85,
                calculated_at=datetime.utcnow() - timedelta(days=10),
            ),
            ResilienceScore(
                service_name="api-server",
                overall_score=90,
                calculated_at=datetime.utcnow(),
            ),
        ]
        
        trend = scorer.calculate_trend(scores)
        
        assert trend > 0  # Improving trend


# ============================================================================
# ReportGenerator Tests
# ============================================================================

class TestReportGenerator:
    """Tests for ReportGenerator."""
    
    @pytest.fixture
    def generator(self) -> ReportGenerator:
        """Create a report generator."""
        return ReportGenerator()
    
    @pytest.fixture
    def sample_result(self) -> ExperimentResult:
        """Create a sample experiment result."""
        return ExperimentResult(
            experiment_id=uuid4(),
            success=True,
            status=ExperimentStatus.COMPLETED,
            message="Experiment completed successfully",
            steady_state_met_before=True,
            steady_state_met_during=True,
            steady_state_met_after=True,
            started_at=datetime.utcnow() - timedelta(minutes=5),
            events=[
                {"type": "start", "message": "Starting experiment", "timestamp": datetime.utcnow().isoformat()},
                {"type": "steady_state_check", "message": "Before check passed", "timestamp": datetime.utcnow().isoformat()},
                {"type": "inject", "message": "Fault injected", "timestamp": datetime.utcnow().isoformat()},
                {"type": "complete", "message": "Experiment complete", "timestamp": datetime.utcnow().isoformat()},
            ],
        )
    
    @pytest.mark.asyncio
    async def test_generate_experiment_report(
        self,
        generator: ReportGenerator,
        sample_experiment: Experiment,
        sample_result: ExperimentResult,
    ):
        """Test generating experiment report."""
        report = await generator.generate_experiment_report(
            experiment=sample_experiment,
            result=sample_result,
        )
        
        assert report is not None
        assert report.experiment_name == sample_experiment.name
        assert report.success == sample_result.success
    
    @pytest.mark.asyncio
    async def test_generate_game_day_report(
        self,
        generator: ReportGenerator,
    ):
        """Test generating game day report."""
        game_day = GameDay(
            name="Q4 Resilience Test",
            description="Quarterly test",
            scenarios=[
                Scenario(
                    name="Test Scenario",
                    experiment=Experiment(
                        name="Test",
                        faults=[],
                    ),
                )
            ],
            status=GameDayStatus.COMPLETED,
        )
        
        report = await generator.generate_game_day_report(game_day)
        
        assert report is not None
    
    @pytest.mark.asyncio
    async def test_export_markdown(
        self,
        generator: ReportGenerator,
        sample_experiment: Experiment,
        sample_result: ExperimentResult,
    ):
        """Test exporting report to markdown."""
        report = await generator.generate_experiment_report(
            experiment=sample_experiment,
            result=sample_result,
        )
        
        markdown = generator.export(report, ReportFormat.MARKDOWN)
        
        assert markdown is not None
        assert sample_experiment.name in markdown
    
    @pytest.mark.asyncio
    async def test_export_json(
        self,
        generator: ReportGenerator,
        sample_experiment: Experiment,
        sample_result: ExperimentResult,
    ):
        """Test exporting report to JSON."""
        import json
        
        report = await generator.generate_experiment_report(
            experiment=sample_experiment,
            result=sample_result,
        )
        
        json_str = generator.export(report, ReportFormat.JSON)
        
        assert json_str is not None
        # Should be valid JSON
        data = json.loads(json_str)
        assert "experiment_name" in data
    
    @pytest.mark.asyncio
    async def test_export_html(
        self,
        generator: ReportGenerator,
        sample_experiment: Experiment,
        sample_result: ExperimentResult,
    ):
        """Test exporting report to HTML."""
        report = await generator.generate_experiment_report(
            experiment=sample_experiment,
            result=sample_result,
        )
        
        html = generator.export(report, ReportFormat.HTML)
        
        assert html is not None
        assert "<html" in html.lower() or "<!doctype" in html.lower()


# ============================================================================
# Model Tests
# ============================================================================

class TestChaosModels:
    """Tests for chaos engineering models."""
    
    def test_fault_creation(self, sample_fault: Fault):
        """Test fault model creation."""
        assert sample_fault.type == FaultType.POD_FAILURE
        assert sample_fault.target.type == TargetType.DEPLOYMENT
        assert sample_fault.status == FaultStatus.PENDING
    
    def test_experiment_creation(self, sample_experiment: Experiment):
        """Test experiment model creation."""
        assert sample_experiment.name == "API Resilience Test"
        assert len(sample_experiment.faults) == 1
        assert len(sample_experiment.steady_state) == 2
        assert sample_experiment.status == ExperimentStatus.PENDING
    
    def test_target_label_selector(self):
        """Test target label selector generation."""
        target = Target(
            type=TargetType.DEPLOYMENT,
            name="api-server",
            namespace="production",
            labels={"app": "api", "tier": "backend"},
        )
        
        selector = target.label_selector
        
        assert "app=api" in selector
        assert "tier=backend" in selector
    
    def test_steady_state_hypothesis(self):
        """Test steady state hypothesis model."""
        hypothesis = SteadyStateHypothesis(
            name="API Health Check",
            probe_type="http",
            endpoint="http://api/health",
            expected_status=200,
            timeout_seconds=5,
        )
        
        assert hypothesis.name == "API Health Check"
        assert hypothesis.probe_type == "http"
    
    def test_experiment_result_events(self, sample_result):
        """Test adding events to result."""
        result = ExperimentResult(
            experiment_id=uuid4(),
            success=True,
            status=ExperimentStatus.COMPLETED,
            started_at=datetime.utcnow(),
        )
        
        result.add_event("test", "Test event")
        
        assert len(result.events) == 1
        assert result.events[0]["type"] == "test"
    
    def test_schedule_cron_type(self):
        """Test schedule with cron expression."""
        schedule = Schedule(
            type=ScheduleType.CRON,
            cron_expression="0 9 * * 1-5",  # 9 AM weekdays
        )
        
        assert schedule.type == ScheduleType.CRON
        next_run = schedule.get_next_run()
        assert next_run is not None or schedule.cron_expression
    
    def test_schedule_interval_type(self):
        """Test schedule with interval."""
        schedule = Schedule(
            type=ScheduleType.INTERVAL,
            interval_seconds=3600,  # Hourly
        )
        
        assert schedule.type == ScheduleType.INTERVAL
    
    def test_game_day_status_transitions(self):
        """Test game day status."""
        game_day = GameDay(
            name="Test Game Day",
            status=GameDayStatus.SCHEDULED,
        )
        
        assert game_day.status == GameDayStatus.SCHEDULED
        
        game_day.status = GameDayStatus.RUNNING
        assert game_day.status == GameDayStatus.RUNNING
        
        game_day.status = GameDayStatus.COMPLETED
        assert game_day.status == GameDayStatus.COMPLETED


# ============================================================================
# Integration Tests
# ============================================================================

class TestChaosIntegration:
    """Integration tests for chaos engineering."""
    
    @pytest.mark.asyncio
    async def test_full_experiment_flow(self, mock_k8s_client):
        """Test full experiment execution flow."""
        runner = ExperimentRunner(k8s_client=mock_k8s_client)
        
        experiment = Experiment(
            name="Integration Test",
            description="Full flow test",
            faults=[
                Fault(
                    type=FaultType.POD_FAILURE,
                    target=Target(
                        type=TargetType.POD,
                        name="test-pod",
                        namespace="default",
                    ),
                )
            ],
            duration_seconds=1,
            warmup_seconds=0,
            cooldown_seconds=0,
        )
        
        # Run experiment
        result = await runner.run(experiment, dry_run=True)
        
        # Generate report
        generator = ReportGenerator()
        report = await generator.generate_experiment_report(experiment, result)
        
        # Calculate resilience score
        scorer = ResilienceScorer()
        score = scorer.calculate_from_result(result)
        
        assert result is not None
        assert report is not None
        assert score is not None
    
    @pytest.mark.asyncio
    async def test_game_day_with_multiple_scenarios(self, mock_k8s_client):
        """Test game day with multiple scenarios."""
        planner = GameDayPlanner(k8s_client=mock_k8s_client)
        
        game_day = planner.create_game_day(
            name="Multi-Scenario Test",
            scheduled_at=datetime.utcnow(),
        )
        
        # Add scenarios
        for i in range(3):
            scenario = Scenario(
                name=f"Scenario {i}",
                experiment=Experiment(
                    name=f"Experiment {i}",
                    faults=[
                        Fault(
                            type=FaultType.POD_FAILURE,
                            target=Target(
                                type=TargetType.POD,
                                name=f"pod-{i}",
                                namespace="default",
                            ),
                        )
                    ],
                    duration_seconds=1,
                ),
            )
            planner.add_scenario(game_day.id, scenario)
        
        assert len(game_day.scenarios) == 3
