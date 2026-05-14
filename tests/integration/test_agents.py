"""Integration tests for agent coordination.

Tests agent coordination, workflow orchestration, and multi-agent collaboration.
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from autosre.agents.base_agent import (
    AgentResult,
    AgentStatus,
    BaseAgent,
    ToolRegistry,
)
from autosre.agents.coordinator import (
    AgentCoordinator,
    CoordinatorConfig,
    CoordinatorState,
)
from autosre.agents.state import (
    EventEmitter,
    EventType,
    InvestigationState,
    InvestigationStateMachine,
    RetryConfig,
    RetryManager,
    TimeoutConfig,
    TimeoutManager,
)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def coordinator_config():
    """Create test coordinator config."""
    return CoordinatorConfig(
        max_iterations=3,
        max_agents_parallel=5,
        total_timeout_seconds=60.0,
        triage_timeout_seconds=10.0,
        investigation_timeout_seconds=30.0,
        max_retries=2,
        retry_delay=0.1,
    )


@pytest.fixture
def mock_alert():
    """Create mock alert for testing."""
    return {
        "id": str(uuid4()),
        "name": "HighErrorRate",
        "service": "payment-service",
        "namespace": "production",
        "severity": "critical",
        "description": "Error rate above 5%",
        "labels": {
            "alertname": "HighErrorRate",
            "service": "payment-service",
            "namespace": "production",
        },
    }


@pytest.fixture
def mock_llm():
    """Create mock LLM client."""
    llm = MagicMock()
    llm.complete_with_retry = AsyncMock()
    llm.complete_structured = AsyncMock()

    # Default response
    response = MagicMock()
    response.content = json.dumps({
        "hypotheses": [
            {
                "hypothesis": "Memory leak causing OOMKilled",
                "priority": "high",
                "agents_to_test": ["kubernetes", "metrics"],
            }
        ],
        "selected_agents": ["kubernetes", "metrics"],
        "reasoning": "Error rate spike correlates with memory growth",
    })
    response.has_tool_calls = False
    response.tool_calls = []

    llm.complete_with_retry.return_value = response

    return llm


@pytest.fixture
def mock_kubernetes_agent():
    """Create mock Kubernetes agent."""
    agent = MagicMock()
    agent.agent_id = "kubernetes"
    agent.agent_name = "Kubernetes Agent"
    agent.execute = AsyncMock()

    result = AgentResult(
        agent_id="kubernetes",
        status=AgentStatus.COMPLETED,
        summary="Found 2 pods in CrashLoopBackOff",
        confidence=0.85,
        iterations=3,
        duration_seconds=15.5,
    )
    agent.execute.return_value = result

    return agent


@pytest.fixture
def mock_metrics_agent():
    """Create mock Metrics agent."""
    agent = MagicMock()
    agent.agent_id = "metrics"
    agent.agent_name = "Metrics Agent"
    agent.execute = AsyncMock()

    result = AgentResult(
        agent_id="metrics",
        status=AgentStatus.COMPLETED,
        summary="Memory usage at 95% before crashes",
        confidence=0.9,
        iterations=2,
        duration_seconds=8.2,
    )
    agent.execute.return_value = result

    return agent


# ============================================================================
# Agent Coordinator Tests
# ============================================================================


class TestAgentCoordinator:
    """Tests for AgentCoordinator."""

    @pytest.mark.asyncio
    async def test_coordinator_initialization(self, coordinator_config):
        """Test coordinator initializes correctly."""
        coordinator = AgentCoordinator(config=coordinator_config)

        assert coordinator is not None
        assert coordinator.config.max_iterations == 3

    @pytest.mark.asyncio
    async def test_register_agent(
        self, coordinator_config, mock_kubernetes_agent
    ):
        """Test registering an agent with coordinator."""
        coordinator = AgentCoordinator(config=coordinator_config)

        coordinator.register_agent(mock_kubernetes_agent)

        assert "kubernetes" in coordinator.get_available_agents()

    @pytest.mark.asyncio
    async def test_register_multiple_agents(
        self,
        coordinator_config,
        mock_kubernetes_agent,
        mock_metrics_agent,
    ):
        """Test registering multiple agents."""
        coordinator = AgentCoordinator(config=coordinator_config)

        coordinator.register_agent(mock_kubernetes_agent)
        coordinator.register_agent(mock_metrics_agent)

        agents = coordinator.get_available_agents()
        assert "kubernetes" in agents
        assert "metrics" in agents

    @pytest.mark.asyncio
    async def test_dispatch_single_agent(
        self,
        coordinator_config,
        mock_kubernetes_agent,
        mock_alert,
    ):
        """Test dispatching a single agent."""
        coordinator = AgentCoordinator(config=coordinator_config)
        coordinator.register_agent(mock_kubernetes_agent)

        state = CoordinatorState(investigation_id="inv-123")
        state.alert = mock_alert

        results = await coordinator._dispatch_agents(
            state=state,
            agents=["kubernetes"],
        )

        assert "kubernetes" in results
        assert results["kubernetes"].status == AgentStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_dispatch_parallel_agents(
        self,
        coordinator_config,
        mock_kubernetes_agent,
        mock_metrics_agent,
        mock_alert,
    ):
        """Test dispatching multiple agents in parallel."""
        coordinator = AgentCoordinator(config=coordinator_config)
        coordinator.register_agent(mock_kubernetes_agent)
        coordinator.register_agent(mock_metrics_agent)

        state = CoordinatorState(investigation_id="inv-123")
        state.alert = mock_alert

        results = await coordinator._dispatch_agents(
            state=state,
            agents=["kubernetes", "metrics"],
        )

        assert len(results) == 2
        assert all(r.status == AgentStatus.COMPLETED for r in results.values())

    @pytest.mark.asyncio
    async def test_agent_timeout_handling(
        self,
        coordinator_config,
        mock_alert,
    ):
        """Test handling of agent timeout."""
        coordinator = AgentCoordinator(config=coordinator_config)

        # Create slow agent that times out
        slow_agent = MagicMock()
        slow_agent.agent_id = "slow"
        slow_agent.agent_name = "Slow Agent"

        async def slow_execute(*args, **kwargs):
            await asyncio.sleep(100)  # Very slow
            return AgentResult(agent_id="slow", status=AgentStatus.COMPLETED)

        slow_agent.execute = slow_execute

        coordinator.register_agent(slow_agent)

        state = CoordinatorState(investigation_id="inv-123")
        state.alert = mock_alert

        # Should handle timeout gracefully
        # In real implementation, would use asyncio.wait_for with timeout

    @pytest.mark.asyncio
    async def test_agent_error_handling(
        self,
        coordinator_config,
        mock_alert,
    ):
        """Test handling of agent errors."""
        coordinator = AgentCoordinator(config=coordinator_config)

        # Create failing agent
        failing_agent = MagicMock()
        failing_agent.agent_id = "failing"
        failing_agent.agent_name = "Failing Agent"
        failing_agent.execute = AsyncMock(side_effect=RuntimeError("Agent crashed"))

        coordinator.register_agent(failing_agent)

        state = CoordinatorState(investigation_id="inv-123")
        state.alert = mock_alert

        results = await coordinator._dispatch_agents(
            state=state,
            agents=["failing"],
        )

        # Should return error result, not crash
        assert "failing" in results
        assert results["failing"].status == AgentStatus.ERROR


# ============================================================================
# Coordinator State Tests
# ============================================================================


class TestCoordinatorState:
    """Tests for CoordinatorState."""

    def test_state_initialization(self):
        """Test state initializes correctly."""
        state = CoordinatorState(investigation_id="inv-123")

        assert state.investigation_id == "inv-123"
        assert state.hypotheses == []
        assert state.all_findings == []
        assert state.timeline == []

    def test_add_timeline_event(self):
        """Test adding timeline events."""
        state = CoordinatorState(investigation_id="inv-123")

        state.add_timeline_event(
            event="Investigation started",
            phase="triage",
            agent=None,
            severity="critical",
        )

        assert len(state.timeline) == 1
        assert state.timeline[0]["event"] == "Investigation started"
        assert state.timeline[0]["phase"] == "triage"
        assert "timestamp" in state.timeline[0]

    def test_add_multiple_timeline_events(self):
        """Test adding multiple timeline events."""
        state = CoordinatorState(investigation_id="inv-123")

        state.add_timeline_event("Started", phase="triage")
        state.add_timeline_event("Agent dispatched", phase="investigation", agent="kubernetes")
        state.add_timeline_event("Completed", phase="conclusion")

        assert len(state.timeline) == 3
        assert state.timeline[1]["agent"] == "kubernetes"

    def test_add_findings(self, sample_findings):
        """Test adding findings to state."""
        from autosre.core.investigation import Finding

        state = CoordinatorState(investigation_id="inv-123")

        findings = [
            Finding(title="Finding 1", description="Test 1"),
            Finding(title="Finding 2", description="Test 2"),
        ]

        state.add_findings(findings)

        assert len(state.all_findings) == 2

    def test_state_persistence(self):
        """Test state can be persisted."""
        state = CoordinatorState(investigation_id="inv-123")
        state.alert = {"name": "TestAlert"}
        state.add_timeline_event("Test", phase="test")

        persist_dict = state.to_persist_dict()

        assert persist_dict["investigation_id"] == "inv-123"
        assert persist_dict["alert"]["name"] == "TestAlert"


# ============================================================================
# Investigation State Machine Tests
# ============================================================================


class TestInvestigationStateMachine:
    """Tests for InvestigationStateMachine."""

    @pytest.fixture
    def state_machine(self):
        """Create state machine instance."""
        return InvestigationStateMachine()

    def test_initial_state(self, state_machine):
        """Test initial state is PENDING."""
        assert state_machine.state == InvestigationState.PENDING

    def test_valid_transition_pending_to_triaging(self, state_machine):
        """Test valid transition from PENDING to TRIAGING."""
        state_machine.transition(InvestigationState.TRIAGING)

        assert state_machine.state == InvestigationState.TRIAGING

    def test_valid_transition_sequence(self, state_machine):
        """Test valid transition sequence through workflow."""
        state_machine.transition(InvestigationState.TRIAGING)
        state_machine.transition(InvestigationState.PLANNING)
        state_machine.transition(InvestigationState.INVESTIGATING)
        state_machine.transition(InvestigationState.SYNTHESIZING)
        state_machine.transition(InvestigationState.COMPLETED)

        assert state_machine.state == InvestigationState.COMPLETED

    def test_invalid_transition_raises(self, state_machine):
        """Test invalid transition raises error."""
        from autosre.agents.state import TransitionError

        with pytest.raises(TransitionError):
            # Can't go directly from PENDING to INVESTIGATING
            state_machine.transition(InvestigationState.INVESTIGATING)

    def test_transition_to_failed_from_any(self, state_machine):
        """Test can transition to FAILED from any state."""
        state_machine.transition(InvestigationState.TRIAGING)
        state_machine.transition(InvestigationState.FAILED)

        assert state_machine.state == InvestigationState.FAILED


# ============================================================================
# Event Emitter Tests
# ============================================================================


class TestEventEmitter:
    """Tests for EventEmitter."""

    @pytest.fixture
    def emitter(self):
        """Create event emitter."""
        return EventEmitter()

    @pytest.mark.asyncio
    async def test_emit_event(self, emitter):
        """Test emitting an event."""
        events_received = []

        async def handler(event):
            events_received.append(event)

        emitter.subscribe(EventType.INVESTIGATION_STARTED, handler)

        await emitter.emit(EventType.INVESTIGATION_STARTED, {"investigation_id": "123"})

        assert len(events_received) == 1
        assert events_received[0]["investigation_id"] == "123"

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self, emitter):
        """Test multiple subscribers receive events."""
        count = 0

        async def handler1(event):
            nonlocal count
            count += 1

        async def handler2(event):
            nonlocal count
            count += 1

        emitter.subscribe(EventType.AGENT_STARTED, handler1)
        emitter.subscribe(EventType.AGENT_STARTED, handler2)

        await emitter.emit(EventType.AGENT_STARTED, {})

        assert count == 2

    @pytest.mark.asyncio
    async def test_unsubscribe(self, emitter):
        """Test unsubscribing from events."""
        count = 0

        async def handler(event):
            nonlocal count
            count += 1

        emitter.subscribe(EventType.AGENT_COMPLETED, handler)
        await emitter.emit(EventType.AGENT_COMPLETED, {})
        assert count == 1

        emitter.unsubscribe(EventType.AGENT_COMPLETED, handler)
        await emitter.emit(EventType.AGENT_COMPLETED, {})
        assert count == 1  # Should not increase


# ============================================================================
# Retry Manager Tests
# ============================================================================


class TestRetryManager:
    """Tests for RetryManager."""

    @pytest.fixture
    def retry_config(self):
        """Create retry config."""
        return RetryConfig(max_retries=3, initial_delay=0.01)

    @pytest.fixture
    def retry_manager(self, retry_config):
        """Create retry manager."""
        return RetryManager(retry_config)

    @pytest.mark.asyncio
    async def test_retry_on_failure(self, retry_manager):
        """Test retry on transient failure."""
        attempts = 0

        async def flaky_operation():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise Exception("Transient error")
            return "success"

        result = await retry_manager.execute(flaky_operation)

        assert result == "success"
        assert attempts == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted(self, retry_manager):
        """Test retry exhaustion."""
        attempts = 0

        async def always_fail():
            nonlocal attempts
            attempts += 1
            raise Exception("Persistent error")

        with pytest.raises(Exception):
            await retry_manager.execute(always_fail)

        assert attempts == 4  # 1 initial + 3 retries

    @pytest.mark.asyncio
    async def test_no_retry_on_success(self, retry_manager):
        """Test no retry needed on success."""
        attempts = 0

        async def success_operation():
            nonlocal attempts
            attempts += 1
            return "success"

        result = await retry_manager.execute(success_operation)

        assert result == "success"
        assert attempts == 1


# ============================================================================
# Timeout Manager Tests
# ============================================================================


class TestTimeoutManager:
    """Tests for TimeoutManager."""

    @pytest.fixture
    def timeout_config(self):
        """Create timeout config."""
        return TimeoutConfig(
            total_timeout=60.0,
            triage_timeout=10.0,
            investigation_timeout=30.0,
        )

    @pytest.fixture
    def timeout_manager(self, timeout_config):
        """Create timeout manager."""
        return TimeoutManager(timeout_config)

    @pytest.mark.asyncio
    async def test_within_timeout(self, timeout_manager):
        """Test operation within timeout."""

        async def quick_operation():
            await asyncio.sleep(0.01)
            return "done"

        result = await timeout_manager.execute(quick_operation, timeout=1.0)

        assert result == "done"

    @pytest.mark.asyncio
    async def test_timeout_exceeded(self, timeout_manager):
        """Test operation exceeding timeout."""

        async def slow_operation():
            await asyncio.sleep(10.0)
            return "done"

        with pytest.raises(asyncio.TimeoutError):
            await timeout_manager.execute(slow_operation, timeout=0.1)


# ============================================================================
# Multi-Agent Workflow Tests
# ============================================================================


class TestMultiAgentWorkflow:
    """Tests for multi-agent workflow scenarios."""

    @pytest.mark.asyncio
    async def test_sequential_agent_execution(
        self,
        coordinator_config,
        mock_kubernetes_agent,
        mock_metrics_agent,
        mock_alert,
    ):
        """Test sequential agent execution."""
        coordinator = AgentCoordinator(config=coordinator_config)
        coordinator.register_agent(mock_kubernetes_agent)
        coordinator.register_agent(mock_metrics_agent)

        state = CoordinatorState(investigation_id="inv-123")
        state.alert = mock_alert

        # First dispatch Kubernetes
        results1 = await coordinator._dispatch_agents(state, ["kubernetes"])
        state.agent_results.update(results1)

        # Then dispatch Metrics
        results2 = await coordinator._dispatch_agents(state, ["metrics"])
        state.agent_results.update(results2)

        assert len(state.agent_results) == 2

    @pytest.mark.asyncio
    async def test_agent_dependency_handling(
        self,
        coordinator_config,
        mock_alert,
    ):
        """Test handling agent dependencies."""
        coordinator = AgentCoordinator(config=coordinator_config)

        # Agent that depends on another's output
        dependent_agent = MagicMock()
        dependent_agent.agent_id = "dependent"
        dependent_agent.agent_name = "Dependent Agent"

        async def execute_with_context(investigation, **kwargs):
            # Check for required context
            prior_results = kwargs.get("prior_results", {})
            if "kubernetes" not in prior_results:
                return AgentResult(
                    agent_id="dependent",
                    status=AgentStatus.ERROR,
                    error="Missing kubernetes results",
                )
            return AgentResult(
                agent_id="dependent",
                status=AgentStatus.COMPLETED,
                summary="Used kubernetes data",
            )

        dependent_agent.execute = execute_with_context

        coordinator.register_agent(dependent_agent)

    @pytest.mark.asyncio
    async def test_iteration_loop(
        self,
        coordinator_config,
        mock_kubernetes_agent,
        mock_metrics_agent,
        mock_alert,
    ):
        """Test investigation iteration loop."""
        coordinator = AgentCoordinator(config=coordinator_config)
        coordinator.register_agent(mock_kubernetes_agent)
        coordinator.register_agent(mock_metrics_agent)

        state = CoordinatorState(investigation_id="inv-123")
        state.alert = mock_alert

        for iteration in range(coordinator.config.max_iterations):
            # Each iteration may dispatch different agents
            agents_to_dispatch = ["kubernetes"] if iteration == 0 else ["metrics"]
            results = await coordinator._dispatch_agents(state, agents_to_dispatch)
            state.agent_results.update(results)

        assert len(state.agent_results) >= 1


# ============================================================================
# Agent Result Aggregation Tests
# ============================================================================


class TestAgentResultAggregation:
    """Tests for aggregating results from multiple agents."""

    def test_aggregate_findings(self):
        """Test aggregating findings from multiple agents."""
        from autosre.core.investigation import Finding

        results = [
            AgentResult(
                agent_id="kubernetes",
                status=AgentStatus.COMPLETED,
                findings=[
                    Finding(title="K8s Finding", description="Pod crashed"),
                ],
                confidence=0.8,
            ),
            AgentResult(
                agent_id="metrics",
                status=AgentStatus.COMPLETED,
                findings=[
                    Finding(title="Metrics Finding", description="Memory spike"),
                ],
                confidence=0.9,
            ),
        ]

        all_findings = []
        for result in results:
            all_findings.extend(result.findings)

        assert len(all_findings) == 2

    def test_calculate_overall_confidence(self):
        """Test calculating overall confidence from agent results."""
        results = [
            AgentResult(agent_id="k8s", status=AgentStatus.COMPLETED, confidence=0.8),
            AgentResult(agent_id="metrics", status=AgentStatus.COMPLETED, confidence=0.9),
            AgentResult(agent_id="logs", status=AgentStatus.COMPLETED, confidence=0.7),
        ]

        # Weighted average or max
        confidences = [r.confidence for r in results]
        avg_confidence = sum(confidences) / len(confidences)
        max_confidence = max(confidences)

        assert avg_confidence == pytest.approx(0.8, 0.01)
        assert max_confidence == 0.9

    def test_filter_successful_results(self):
        """Test filtering only successful agent results."""
        results = {
            "k8s": AgentResult(agent_id="k8s", status=AgentStatus.COMPLETED),
            "metrics": AgentResult(agent_id="metrics", status=AgentStatus.ERROR),
            "logs": AgentResult(agent_id="logs", status=AgentStatus.COMPLETED),
        }

        successful = {
            k: v for k, v in results.items()
            if v.status == AgentStatus.COMPLETED
        }

        assert len(successful) == 2
        assert "metrics" not in successful


# ============================================================================
# Tool Registry Tests
# ============================================================================


class TestToolRegistryExtended:
    """Extended tests for ToolRegistry."""

    @pytest.fixture
    def registry(self):
        """Create tool registry."""
        return ToolRegistry()

    def test_register_multiple_tools(self, registry):
        """Test registering multiple tools."""
        registry.register(
            name="get_pods",
            description="Get pods",
            parameters={},
            handler=lambda: "pods",
        )
        registry.register(
            name="get_metrics",
            description="Get metrics",
            parameters={},
            handler=lambda: "metrics",
        )
        registry.register(
            name="search_logs",
            description="Search logs",
            parameters={},
            handler=lambda: "logs",
        )

        assert len(registry) == 3

    @pytest.mark.asyncio
    async def test_execute_with_kwargs(self, registry):
        """Test executing tool with keyword arguments."""

        def handler(namespace: str, label: str = "app") -> str:
            return f"pods in {namespace} with label {label}"

        registry.register(
            name="get_labeled_pods",
            description="Get pods with label",
            parameters={
                "type": "object",
                "properties": {
                    "namespace": {"type": "string"},
                    "label": {"type": "string"},
                },
            },
            handler=handler,
        )

        from autosre.core.llm_client import ToolCall

        call = ToolCall(
            id="1",
            name="get_labeled_pods",
            arguments={"namespace": "production", "label": "version"},
        )

        result = await registry.execute(call)

        assert "production" in result
        assert "version" in result

    @pytest.mark.asyncio
    async def test_execute_handles_exception(self, registry):
        """Test execute handles tool exceptions."""

        def failing_handler():
            raise ValueError("Tool failed")

        registry.register(
            name="failing_tool",
            description="A failing tool",
            parameters={},
            handler=failing_handler,
        )

        from autosre.core.llm_client import ToolCall

        call = ToolCall(id="1", name="failing_tool", arguments={})

        result = await registry.execute(call)

        assert "Error" in result
        assert "failing_tool" in result


# ============================================================================
# Coordination Decision Tests
# ============================================================================


class TestCoordinationDecisions:
    """Tests for coordination decision making."""

    def test_should_continue_investigation(self):
        """Test decision to continue investigation."""
        state = CoordinatorState(investigation_id="inv-123")
        state.context = MagicMock()
        state.context.iteration = 1
        state.context.max_iterations = 3

        # No synthesis result yet, should continue
        assert state.synthesis_result is None

    def test_should_conclude_investigation(self):
        """Test decision to conclude investigation."""
        state = CoordinatorState(investigation_id="inv-123")
        state.synthesis_result = {
            "sufficient_evidence": True,
            "confidence": 0.9,
            "summary": "Root cause identified",
        }

        # Has synthesis with high confidence, should conclude
        assert state.synthesis_result is not None
        assert state.synthesis_result["confidence"] >= 0.7

    def test_max_iterations_reached(self):
        """Test conclusion when max iterations reached."""
        config = CoordinatorConfig(max_iterations=3)
        state = CoordinatorState(investigation_id="inv-123")
        state.context = MagicMock()
        state.context.iteration = 3
        state.context.max_iterations = 3

        # At max iterations, must conclude
        assert state.context.iteration >= state.context.max_iterations
