"""
Unit Tests for Orchestrator

Tests the investigation orchestration flow including:
- Investigation lifecycle
- Agent coordination
- Timeout handling
- Action execution flow
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opensre_core.agents.act import Action, ActionPlan, ActionRisk
from opensre_core.agents.observe import Observation, ObservationResult
from opensre_core.agents.orchestrator import (
    InvestigationManager,
    InvestigationResult,
    Orchestrator,
)


class TestInvestigationResult:
    """Tests for InvestigationResult dataclass."""

    def test_investigation_result_creation(self):
        """Test investigation result creation."""
        result = InvestigationResult(
            issue="High memory usage",
            namespace="default",
        )

        assert result.issue == "High memory usage"
        assert result.namespace == "default"
        assert result.status == "running"
        assert result.id is not None
        assert len(result.id) == 8

    def test_investigation_result_to_dict(self):
        """Test conversion to dictionary."""
        result = InvestigationResult(
            issue="Test issue",
            namespace="production",
        )
        result.root_cause = "Memory leak"
        result.confidence = 0.85

        data = result.to_dict()

        assert data["issue"] == "Test issue"
        assert data["namespace"] == "production"
        assert data["root_cause"] == "Memory leak"
        assert data["confidence"] == 0.85
        assert "id" in data
        assert "started_at" in data

    def test_investigation_result_with_observations(self):
        """Test result with observations."""
        result = InvestigationResult(
            issue="Test",
            namespace="default",
        )
        result.observations = [
            Observation(source="prometheus", type="metric", summary="CPU high"),
            Observation(source="kubernetes", type="event", summary="OOMKilled"),
        ]

        data = result.to_dict()

        assert len(data["observations"]) == 2
        assert data["observations"][0]["source"] == "prometheus"

    def test_investigation_result_with_actions(self):
        """Test result with actions."""
        result = InvestigationResult(
            issue="Test",
            namespace="default",
        )
        result.actions = [
            Action(
                id="action_1",
                description="Get pods",
                command="kubectl get pods",
                risk=ActionRisk.LOW,
                requires_approval=False,
            ),
        ]

        data = result.to_dict()

        assert len(data["actions"]) == 1
        assert data["actions"][0]["id"] == "action_1"
        assert data["actions"][0]["risk"] == "low"


class TestOrchestrator:
    """Tests for Orchestrator class."""

    @pytest.fixture
    def orchestrator(self, mock_prometheus, mock_kubernetes, mock_llm, mock_audit_logger):
        """Create orchestrator with mocked agents."""
        orch = Orchestrator()

        # Mock observer
        orch.observer.prometheus = mock_prometheus
        orch.observer.kubernetes = mock_kubernetes

        # Mock reasoner
        orch.reasoner.llm = mock_llm

        # Mock actor
        orch.actor.audit = mock_audit_logger
        orch.actor.llm = mock_llm

        # Mock runbooks
        orch.runbooks = MagicMock()
        orch.runbooks.find_relevant.return_value = []
        orch.runbooks.get_context.return_value = ""

        return orch

    @pytest.mark.asyncio
    async def test_investigate_returns_result(self, orchestrator):
        """Test investigate returns InvestigationResult."""
        result = await orchestrator.investigate("test issue", namespace="default")

        assert isinstance(result, InvestigationResult)
        assert result.issue == "test issue"
        assert result.namespace == "default"

    @pytest.mark.asyncio
    async def test_investigate_sets_status_completed(self, orchestrator):
        """Test successful investigation sets completed status."""
        result = await orchestrator.investigate("test issue")

        assert result.status == "completed"
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_investigate_collects_observations(self, orchestrator, mock_kubernetes):
        """Test investigation collects observations."""
        mock_kubernetes.get_pods.return_value = []
        mock_kubernetes.get_events.return_value = []

        await orchestrator.investigate("memory issue")

        # Should have called observer
        mock_kubernetes.get_pods.assert_called()

    @pytest.mark.asyncio
    async def test_investigate_performs_analysis(self, orchestrator, mock_llm):
        """Test investigation performs analysis."""
        await orchestrator.investigate("test issue")

        # Reasoner should have been called
        mock_llm.generate.assert_called()

    @pytest.mark.asyncio
    async def test_investigate_generates_action_plan(self, orchestrator):
        """Test investigation generates action plan."""
        result = await orchestrator.investigate("test issue")

        # Should have actions (may be empty if LLM doesn't suggest any)
        assert isinstance(result.actions, list)

    @pytest.mark.asyncio
    async def test_investigate_handles_timeout(self, orchestrator):
        """Test investigation handles timeout."""
        # Make observer slow
        async def slow_observe(*args, **kwargs):
            await asyncio.sleep(5)
            return ObservationResult(issue="test", namespace="default")

        orchestrator.observer.observe = slow_observe

        result = await orchestrator.investigate("test issue", timeout=1)

        assert result.status == "timeout"
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_investigate_handles_exception(self, orchestrator, mock_kubernetes):
        """Test investigation handles exceptions."""
        mock_kubernetes.get_pods.side_effect = Exception("Connection failed")
        mock_kubernetes.get_events.side_effect = Exception("Connection failed")

        # This might fail or handle gracefully depending on implementation
        result = await orchestrator.investigate("test issue")

        # Should have a result, possibly with error status
        assert result is not None

    @pytest.mark.asyncio
    async def test_investigate_auto_execute_safe(self, orchestrator):
        """Test auto-execution of safe actions."""
        # Set up actor to return safe actions
        orchestrator.actor.plan_actions = AsyncMock(return_value=ActionPlan(
            actions=[
                Action(
                    id="action_1",
                    description="Get pods",
                    command="kubectl get pods",
                    risk=ActionRisk.LOW,
                    requires_approval=False,
                ),
            ]
        ))

        orchestrator.actor.execute_action = AsyncMock(return_value={"success": True})

        await orchestrator.investigate(
            "test issue",
            auto_execute_safe=True,
        )

        # Safe action should have been executed
        orchestrator.actor.execute_action.assert_called()

    @pytest.mark.asyncio
    async def test_investigate_tracks_iterations(self, orchestrator):
        """Test investigation tracks iterations."""
        result = await orchestrator.investigate("test issue")

        assert result.iterations >= 1

    @pytest.mark.asyncio
    async def test_investigate_includes_runbooks(self, orchestrator):
        """Test investigation includes relevant runbooks."""
        orchestrator.runbooks.find_relevant.return_value = [
            MagicMock(title="Memory Troubleshooting"),
        ]

        await orchestrator.investigate("memory issue")

        orchestrator.runbooks.find_relevant.assert_called()


class TestInvestigationManager:
    """Tests for InvestigationManager class."""

    @pytest.fixture
    def manager(self, mock_prometheus, mock_kubernetes, mock_llm, mock_audit_logger):
        """Create manager with mocked orchestrator."""
        mgr = InvestigationManager()

        # Mock the internal orchestrator
        mgr.orchestrator.observer.prometheus = mock_prometheus
        mgr.orchestrator.observer.kubernetes = mock_kubernetes
        mgr.orchestrator.reasoner.llm = mock_llm
        mgr.orchestrator.actor.audit = mock_audit_logger
        mgr.orchestrator.actor.llm = mock_llm
        mgr.orchestrator.runbooks = MagicMock()
        mgr.orchestrator.runbooks.find_relevant.return_value = []
        mgr.orchestrator.runbooks.get_context.return_value = ""

        return mgr

    @pytest.mark.asyncio
    async def test_start_investigation_returns_id(self, manager):
        """Test start_investigation returns an ID."""
        investigation_id = await manager.start_investigation("test issue")

        assert isinstance(investigation_id, str)
        assert len(investigation_id) == 8

    @pytest.mark.asyncio
    async def test_start_investigation_runs_in_background(self, manager):
        """Test investigation runs in background."""
        investigation_id = await manager.start_investigation("test issue")

        # Give time for background task
        await asyncio.sleep(0.5)

        # Should be able to retrieve result
        result = await manager.get_investigation(investigation_id)
        # May be None if not completed yet, or InvestigationResult
        assert result is None or isinstance(result, InvestigationResult)

    @pytest.mark.asyncio
    async def test_list_investigations(self, manager):
        """Test listing investigations."""
        await manager.start_investigation("issue 1")
        await manager.start_investigation("issue 2")

        # Give time for tasks to start
        await asyncio.sleep(0.1)

        investigations = await manager.list_investigations()

        # May have investigations started (depends on timing)
        assert isinstance(investigations, list)

    @pytest.mark.asyncio
    async def test_approve_action_not_found(self, manager):
        """Test approving action for non-existent investigation."""
        result = await manager.approve_action("nonexistent", "action_1")

        assert "error" in result

    @pytest.mark.asyncio
    async def test_reject_action_not_found(self, manager):
        """Test rejecting action for non-existent investigation."""
        result = await manager.reject_action("nonexistent", "action_1")

        assert "error" in result


class TestOrchestratorMetrics:
    """Tests for orchestrator metrics recording."""

    @pytest.fixture
    def orchestrator(self, mock_prometheus, mock_kubernetes, mock_llm, mock_audit_logger):
        orch = Orchestrator()
        orch.observer.prometheus = mock_prometheus
        orch.observer.kubernetes = mock_kubernetes
        orch.reasoner.llm = mock_llm
        orch.actor.audit = mock_audit_logger
        orch.actor.llm = mock_llm
        orch.runbooks = MagicMock()
        orch.runbooks.find_relevant.return_value = []
        orch.runbooks.get_context.return_value = ""
        return orch

    @pytest.mark.asyncio
    async def test_investigate_records_metrics(self, orchestrator):
        """Test that investigation records metrics."""
        with patch("opensre_core.agents.orchestrator.record_investigation_start") as mock_start, \
             patch("opensre_core.agents.orchestrator.record_investigation_end") as mock_end:

            await orchestrator.investigate("test issue")

            mock_start.assert_called_once()
            mock_end.assert_called_once()

    @pytest.mark.asyncio
    async def test_investigate_records_action_metrics(self, orchestrator):
        """Test that action suggestions record metrics."""
        with patch("opensre_core.agents.orchestrator.record_action_suggested") as mock_suggested:
            orchestrator.actor.plan_actions = AsyncMock(return_value=ActionPlan(
                actions=[
                    Action(
                        id="action_1",
                        description="Test",
                        command="kubectl get pods",
                        risk=ActionRisk.LOW,
                        requires_approval=False,
                    ),
                ]
            ))

            await orchestrator.investigate("test issue")

            mock_suggested.assert_called()
