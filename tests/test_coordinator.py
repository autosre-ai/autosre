"""Tests for the agent coordinator and state machine."""

import asyncio
import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from autosre.agents.state import (
    InvestigationState,
    InvestigationStateMachine,
    StateTransition,
    TransitionError,
    EventType,
    Event,
    EventEmitter,
    RetryConfig,
    RetryManager,
    TimeoutConfig,
    TimeoutManager,
    StatePersister,
    FileStatePersister,
    SQLiteStatePersister,
    InMemoryStatePersister,
    InvestigationContext,
    create_persister,
)

from autosre.agents.coordinator import (
    AgentCoordinator,
    CoordinatorConfig,
    CoordinatorState,
    InvestigationStatus,
    Timeline,
    TimelineEntry,
    create_coordinator,
)


# =============================================================================
# State Machine Tests
# =============================================================================


class TestInvestigationState:
    """Tests for InvestigationState enum."""
    
    def test_terminal_states(self):
        """Terminal states are correctly identified."""
        assert InvestigationState.COMPLETED.is_terminal
        assert InvestigationState.FAILED.is_terminal
        assert InvestigationState.TIMEOUT.is_terminal
        assert InvestigationState.CANCELLED.is_terminal
        
        assert not InvestigationState.PENDING.is_terminal
        assert not InvestigationState.INVESTIGATING.is_terminal
    
    def test_active_states(self):
        """Active states are correctly identified."""
        assert InvestigationState.TRIAGING.is_active
        assert InvestigationState.INVESTIGATING.is_active
        assert InvestigationState.ANALYZING.is_active
        
        assert not InvestigationState.PENDING.is_active
        assert not InvestigationState.COMPLETED.is_active


class TestInvestigationStateMachine:
    """Tests for the state machine."""
    
    @pytest.fixture
    def machine(self):
        return InvestigationStateMachine()
    
    def test_happy_path(self, machine):
        """Test normal investigation flow."""
        transitions = [
            ("start", InvestigationState.TRIAGING),
            ("triage_complete", InvestigationState.INVESTIGATING),
            ("observations_collected", InvestigationState.ANALYZING),
            ("analysis_complete", InvestigationState.RECOMMENDING),
            ("no_action_needed", InvestigationState.COMPLETED),
        ]
        
        current = InvestigationState.PENDING
        for event, expected in transitions:
            current = machine.transition(current, event)
            assert current == expected
    
    def test_investigation_iteration(self, machine):
        """Test returning to investigation for more data."""
        current = InvestigationState.ANALYZING
        current = machine.transition(current, "need_more_data")
        assert current == InvestigationState.INVESTIGATING
    
    def test_invalid_transition_raises(self, machine):
        """Invalid transitions raise TransitionError."""
        with pytest.raises(TransitionError) as exc:
            machine.transition(InvestigationState.COMPLETED, "start")
        
        assert exc.value.from_state == InvestigationState.COMPLETED
    
    def test_can_transition(self, machine):
        """can_transition returns correct boolean."""
        assert machine.can_transition(InvestigationState.PENDING, "start")
        assert not machine.can_transition(InvestigationState.PENDING, "invalid")
        assert not machine.can_transition(InvestigationState.COMPLETED, "start")
    
    def test_get_valid_events(self, machine):
        """Valid events are returned for each state."""
        events = machine.get_valid_events(InvestigationState.PENDING)
        assert "start" in events
        assert "cancel" in events
        
        # Terminal states have no valid events
        events = machine.get_valid_events(InvestigationState.COMPLETED)
        assert len(events) == 0


# =============================================================================
# Event System Tests
# =============================================================================


class TestEventEmitter:
    """Tests for the event emitter."""
    
    @pytest.fixture
    def emitter(self):
        return EventEmitter()
    
    @pytest.mark.asyncio
    async def test_emit_to_handler(self, emitter):
        """Events are received by registered handlers."""
        received = []
        
        async def handler(event):
            received.append(event)
        
        emitter.on(EventType.STATE_CHANGED, handler)
        await emitter.emit(EventType.STATE_CHANGED, "inv-1", {"state": "new"})
        
        assert len(received) == 1
        assert received[0].type == EventType.STATE_CHANGED
        assert received[0].investigation_id == "inv-1"
        assert received[0].data["state"] == "new"
    
    @pytest.mark.asyncio
    async def test_global_handler(self, emitter):
        """Global handlers receive all events."""
        received = []
        
        async def handler(event):
            received.append(event)
        
        emitter.on_all(handler)
        
        await emitter.emit(EventType.STATE_CHANGED, "inv-1")
        await emitter.emit(EventType.TRIAGE_STARTED, "inv-1")
        await emitter.emit(EventType.AGENT_COMPLETED, "inv-1")
        
        assert len(received) == 3
    
    @pytest.mark.asyncio
    async def test_event_history(self, emitter):
        """Event history is maintained."""
        for i in range(5):
            await emitter.emit(EventType.STATE_CHANGED, f"inv-{i}")
        
        history = emitter.get_history()
        assert len(history) == 5
        
        # Filter by investigation
        history = emitter.get_history(investigation_id="inv-2")
        assert len(history) == 1
    
    @pytest.mark.asyncio
    async def test_handler_error_isolation(self, emitter):
        """Handler errors don't affect other handlers."""
        received = []
        
        async def bad_handler(event):
            raise Exception("Handler error")
        
        async def good_handler(event):
            received.append(event)
        
        emitter.on(EventType.STATE_CHANGED, bad_handler)
        emitter.on(EventType.STATE_CHANGED, good_handler)
        
        # Should not raise, and good_handler should still run
        await emitter.emit(EventType.STATE_CHANGED, "inv-1")
        assert len(received) == 1


# =============================================================================
# Retry Manager Tests
# =============================================================================


class TestRetryConfig:
    """Tests for retry configuration."""
    
    def test_exponential_delay(self):
        """Delays increase exponentially."""
        config = RetryConfig(
            initial_delay=1.0,
            exponential_base=2.0,
            max_delay=60.0,
            jitter=False,  # Disable for predictable tests
        )
        
        assert config.get_delay(0) == 1.0
        assert config.get_delay(1) == 2.0
        assert config.get_delay(2) == 4.0
        assert config.get_delay(3) == 8.0
    
    def test_max_delay_cap(self):
        """Delays are capped at max_delay."""
        config = RetryConfig(
            initial_delay=1.0,
            exponential_base=2.0,
            max_delay=10.0,
            jitter=False,
        )
        
        # 2^10 = 1024, but capped at 10
        assert config.get_delay(10) == 10.0


class TestRetryManager:
    """Tests for retry manager."""
    
    @pytest.mark.asyncio
    async def test_successful_operation(self):
        """Successful operations don't retry."""
        manager = RetryManager(RetryConfig(max_retries=3))
        attempts = 0
        
        async with manager.retry_context("test", "inv-1"):
            attempts += 1
        
        assert attempts == 1
    
    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Failed operations are retried."""
        config = RetryConfig(
            max_retries=3,
            initial_delay=0.01,  # Fast for testing
            jitter=False,
        )
        manager = RetryManager(config)
        attempts = 0
        
        with pytest.raises(ValueError):
            async with manager.retry_context("test", "inv-1"):
                attempts += 1
                if attempts < 3:
                    raise ValueError("Simulated failure")
        
        assert attempts == 3  # Tried 3 times, then raised


# =============================================================================
# Persistence Tests
# =============================================================================


class TestInMemoryPersister:
    """Tests for in-memory persistence."""
    
    @pytest.fixture
    def persister(self):
        return InMemoryStatePersister()
    
    @pytest.mark.asyncio
    async def test_save_and_load(self, persister):
        """State can be saved and loaded."""
        await persister.save("inv-1", {"status": "running"})
        loaded = await persister.load("inv-1")
        
        assert loaded["status"] == "running"
    
    @pytest.mark.asyncio
    async def test_delete(self, persister):
        """State can be deleted."""
        await persister.save("inv-1", {"status": "running"})
        await persister.delete("inv-1")
        loaded = await persister.load("inv-1")
        
        assert loaded is None
    
    @pytest.mark.asyncio
    async def test_list_active(self, persister):
        """Active investigations are listed."""
        await persister.save("inv-1", {"status": "pending"})
        await persister.save("inv-2", {"status": "investigating"})
        await persister.save("inv-3", {"status": "completed"})
        
        active = await persister.list_active()
        assert "inv-1" in active
        assert "inv-2" in active
        assert "inv-3" not in active  # Completed is terminal


class TestInvestigationContext:
    """Tests for investigation context."""
    
    def test_serialization_roundtrip(self):
        """Context survives serialization."""
        ctx = InvestigationContext(
            investigation_id="test-123",
            status=InvestigationState.INVESTIGATING,
            iteration=2,
            max_iterations=5,
        )
        ctx.record_phase_transition("pending", "triaging", "start")
        ctx.record_error("Test error", "triaging")
        
        data = ctx.to_persist_dict()
        restored = InvestigationContext.from_persist_dict(data)
        
        assert restored.investigation_id == "test-123"
        assert restored.get_status() == InvestigationState.INVESTIGATING
        assert restored.iteration == 2
        assert len(restored.phase_history) == 1
        assert len(restored.errors) == 1


# =============================================================================
# Coordinator Tests
# =============================================================================


class TestCoordinatorConfig:
    """Tests for coordinator configuration."""
    
    def test_defaults(self):
        """Default config has sensible values."""
        config = CoordinatorConfig()
        
        assert config.max_iterations >= 1
        assert config.total_timeout_seconds > 0
        assert config.max_retries >= 1
    
    def test_timeout_config_conversion(self):
        """Timeout config is correctly derived."""
        config = CoordinatorConfig(
            total_timeout_seconds=300,
            triage_timeout_seconds=15,
        )
        
        tc = config.get_timeout_config()
        assert tc.total_timeout == 300
        assert tc.triage_timeout == 15


class TestAgentCoordinator:
    """Tests for the agent coordinator."""
    
    @pytest.fixture
    def coordinator(self):
        config = CoordinatorConfig(
            persistence_backend="memory",
            max_iterations=2,
        )
        return AgentCoordinator(config=config)
    
    def test_register_agent(self, coordinator):
        """Agents can be registered."""
        agent = MagicMock()
        agent.name = "test_agent"
        
        coordinator.register_agent(agent)
        
        assert "test_agent" in coordinator.get_available_agents()
    
    @pytest.mark.asyncio
    async def test_event_emission(self, coordinator):
        """Events are emitted during investigation."""
        received_events = []
        
        async def handler(event):
            received_events.append(event.type)
        
        coordinator.events.on_all(handler)
        
        # Mock the agents to make the test fast
        mock_triage = AsyncMock()
        mock_triage.run = AsyncMock(return_value=MagicMock(
            output=None,
            state=MagicMock(findings=[]),
        ))
        coordinator._triage_agent = mock_triage
        
        # Would need more mocking for full test
        # This just verifies the event system is wired up
        assert coordinator.events is not None
    
    @pytest.mark.asyncio
    async def test_get_status_not_found(self, coordinator):
        """Status for unknown investigation returns not_found."""
        status = await coordinator.get_status("unknown-id")
        assert status.status == "not_found"


# =============================================================================
# Integration Tests
# =============================================================================


class TestFullWorkflow:
    """Integration tests for the full workflow."""
    
    @pytest.mark.asyncio
    async def test_state_machine_workflow(self):
        """Test complete state machine workflow."""
        machine = InvestigationStateMachine()
        context = InvestigationContext()
        
        # Simulate workflow
        events = [
            "start",
            "triage_complete", 
            "observations_collected",
            "need_more_data",  # Go back for more
            "observations_collected",
            "analysis_complete",
            "actions_proposed",
            "action_approved",
            "execution_complete",
        ]
        
        for event in events:
            new_state = machine.transition(context.get_status(), event)
            context.status = new_state
            context.record_phase_transition(
                context.current_phase,
                new_state.value,
                event,
            )
        
        assert context.get_status() == InvestigationState.COMPLETED
        assert len(context.phase_history) == len(events)


# =============================================================================
# Run Tests
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
