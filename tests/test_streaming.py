"""
Tests for real-time streaming functionality.
"""

import pytest
import asyncio
from datetime import datetime, timedelta

from autosre.streaming import (
    StreamEventType,
    StreamEvent,
    InvestigationStream,
    StreamManager,
    get_stream_manager,
)


class TestStreamEventType:
    """Tests for StreamEventType enum."""
    
    def test_event_types_exist(self):
        """Test that all expected event types exist."""
        assert StreamEventType.STARTED.value == "started"
        assert StreamEventType.OBSERVATION.value == "observation"
        assert StreamEventType.ROOT_CAUSE.value == "root_cause"
        assert StreamEventType.COMPLETED.value == "completed"
        assert StreamEventType.ERROR.value == "error"


class TestStreamEvent:
    """Tests for StreamEvent dataclass."""
    
    def test_create_event(self):
        """Test creating a stream event."""
        event = StreamEvent(
            type=StreamEventType.OBSERVATION,
            data={"source": "prometheus", "summary": "CPU high"},
        )
        
        assert event.type == StreamEventType.OBSERVATION
        assert event.data["source"] == "prometheus"
        assert event.timestamp is not None
    
    def test_to_dict(self):
        """Test converting event to dictionary."""
        event = StreamEvent(
            type=StreamEventType.ROOT_CAUSE,
            data={"root_cause": "memory leak", "confidence": 0.85},
        )
        
        result = event.to_dict()
        
        assert result["type"] == "root_cause"
        assert result["data"]["root_cause"] == "memory leak"
        assert "timestamp" in result


class TestInvestigationStream:
    """Tests for InvestigationStream."""
    
    @pytest.fixture
    def stream(self):
        """Create a test stream."""
        return InvestigationStream()
    
    def test_init(self, stream):
        """Test stream initialization."""
        assert stream.subscribers == []
        assert stream.history == []
        assert stream.is_completed is False
    
    @pytest.mark.asyncio
    async def test_emit_event(self, stream):
        """Test emitting an event."""
        await stream.emit(
            StreamEventType.STARTED,
            {"issue": "High CPU", "namespace": "prod"},
        )
        
        assert len(stream.history) == 1
        assert stream.history[0].type == StreamEventType.STARTED
    
    @pytest.mark.asyncio
    async def test_emit_marks_completed(self, stream):
        """Test that completed event marks stream as done."""
        await stream.emit(StreamEventType.COMPLETED, {"result": "success"})
        
        assert stream.is_completed is True
    
    @pytest.mark.asyncio
    async def test_emit_marks_error(self, stream):
        """Test that error event marks stream as done."""
        await stream.emit(StreamEventType.ERROR, {"error": "timeout"})
        
        assert stream.is_completed is True
    
    @pytest.mark.asyncio
    async def test_subscribe_gets_history(self, stream):
        """Test that subscriber gets history replay."""
        # Emit some events first
        await stream.emit(StreamEventType.STARTED, {"issue": "test"})
        await stream.emit(StreamEventType.OBSERVATION, {"source": "k8s"})
        await stream.emit(StreamEventType.COMPLETED, {"done": True})
        
        # Subscribe and collect events
        events = []
        async for event in stream.subscribe():
            events.append(event)
        
        assert len(events) == 3
        assert events[0].type == StreamEventType.STARTED
        assert events[1].type == StreamEventType.OBSERVATION
        assert events[2].type == StreamEventType.COMPLETED
    
    @pytest.mark.asyncio
    async def test_subscribe_streaming(self, stream):
        """Test real-time streaming to subscriber."""
        events = []
        
        async def collector():
            async for event in stream.subscribe():
                events.append(event)
                if event.type == StreamEventType.COMPLETED:
                    break
        
        # Start collector in background
        task = asyncio.create_task(collector())
        
        # Give collector time to start
        await asyncio.sleep(0.01)
        
        # Emit events
        await stream.emit(StreamEventType.STARTED, {"issue": "test"})
        await stream.emit(StreamEventType.COMPLETED, {"done": True})
        
        # Wait for collector
        await asyncio.wait_for(task, timeout=1.0)
        
        assert len(events) == 2
    
    @pytest.mark.asyncio
    async def test_multiple_subscribers(self, stream):
        """Test multiple subscribers receive same events."""
        events1 = []
        events2 = []
        
        async def collector(events_list):
            async for event in stream.subscribe():
                events_list.append(event)
                if event.type == StreamEventType.COMPLETED:
                    break
        
        task1 = asyncio.create_task(collector(events1))
        task2 = asyncio.create_task(collector(events2))
        
        await asyncio.sleep(0.01)
        
        await stream.emit(StreamEventType.STARTED, {"issue": "test"})
        await stream.emit(StreamEventType.COMPLETED, {"done": True})
        
        await asyncio.gather(task1, task2)
        
        assert len(events1) == 2
        assert len(events2) == 2
    
    @pytest.mark.asyncio
    async def test_started_convenience(self, stream):
        """Test started convenience method."""
        await stream.started("High CPU", "production")
        
        event = stream.history[0]
        assert event.type == StreamEventType.STARTED
        assert event.data["issue"] == "High CPU"
        assert event.data["namespace"] == "production"
    
    @pytest.mark.asyncio
    async def test_observation_convenience(self, stream):
        """Test observation convenience method."""
        await stream.observation(
            source="prometheus",
            summary="CPU at 95%",
            severity="critical",
            details={"metric": "cpu_usage"},
        )
        
        event = stream.history[0]
        assert event.type == StreamEventType.OBSERVATION
        assert event.data["source"] == "prometheus"
        assert event.data["severity"] == "critical"
    
    @pytest.mark.asyncio
    async def test_observation_complete_convenience(self, stream):
        """Test observation_complete convenience method."""
        await stream.observation_complete(count=5, services=["api", "web"])
        
        event = stream.history[0]
        assert event.type == StreamEventType.OBSERVATION_COMPLETE
        assert event.data["count"] == 5
    
    @pytest.mark.asyncio
    async def test_thinking_convenience(self, stream):
        """Test thinking convenience method."""
        await stream.thinking("Analyzing CPU patterns...")
        
        event = stream.history[0]
        assert event.type == StreamEventType.THINKING
        assert "CPU" in event.data["thought"]
    
    @pytest.mark.asyncio
    async def test_hypothesis_convenience(self, stream):
        """Test hypothesis convenience method."""
        await stream.hypothesis(
            hypothesis="Memory leak causing OOM",
            confidence=0.75,
            evidence=["Rising memory", "Recent deploy"],
        )
        
        event = stream.history[0]
        assert event.type == StreamEventType.HYPOTHESIS
        assert event.data["confidence"] == 0.75
        assert len(event.data["evidence"]) == 2
    
    @pytest.mark.asyncio
    async def test_root_cause_convenience(self, stream):
        """Test root_cause convenience method."""
        await stream.root_cause("Database connection pool exhausted", 0.9)
        
        event = stream.history[0]
        assert event.type == StreamEventType.ROOT_CAUSE
        assert event.data["confidence"] == 0.9
    
    @pytest.mark.asyncio
    async def test_action_convenience(self, stream):
        """Test action convenience method."""
        await stream.action(
            description="Scale up replicas",
            command="kubectl scale --replicas=5",
            risk="low",
            action_id="act-001",
        )
        
        event = stream.history[0]
        assert event.type == StreamEventType.ACTION
        assert event.data["risk"] == "low"
    
    @pytest.mark.asyncio
    async def test_progress_convenience(self, stream):
        """Test progress convenience method."""
        await stream.progress("Collecting metrics", current=3, total=10)
        
        event = stream.history[0]
        assert event.type == StreamEventType.PROGRESS
        assert event.data["current"] == 3
        assert event.data["total"] == 10
    
    @pytest.mark.asyncio
    async def test_completed_convenience(self, stream):
        """Test completed convenience method."""
        await stream.completed({"root_cause": "Memory leak", "actions": 3})
        
        event = stream.history[0]
        assert event.type == StreamEventType.COMPLETED
        assert stream.is_completed is True
    
    @pytest.mark.asyncio
    async def test_error_convenience(self, stream):
        """Test error convenience method."""
        await stream.error("Connection timeout", {"service": "prometheus"})
        
        event = stream.history[0]
        assert event.type == StreamEventType.ERROR
        assert stream.is_completed is True


class TestStreamManager:
    """Tests for StreamManager."""
    
    @pytest.fixture
    def manager(self):
        """Create a test manager."""
        return StreamManager()
    
    @pytest.mark.asyncio
    async def test_create_stream(self, manager):
        """Test creating a stream."""
        stream = await manager.create_stream("inv-001")
        
        assert stream is not None
        assert isinstance(stream, InvestigationStream)
    
    @pytest.mark.asyncio
    async def test_get_stream(self, manager):
        """Test getting an existing stream."""
        created = await manager.create_stream("inv-002")
        retrieved = await manager.get_stream("inv-002")
        
        assert retrieved is created
    
    @pytest.mark.asyncio
    async def test_get_stream_not_found(self, manager):
        """Test getting nonexistent stream."""
        result = await manager.get_stream("nonexistent")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_remove_stream(self, manager):
        """Test removing a stream."""
        await manager.create_stream("inv-003")
        await manager.remove_stream("inv-003")
        
        result = await manager.get_stream("inv-003")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_list_active(self, manager):
        """Test listing active streams."""
        stream1 = await manager.create_stream("inv-active")
        stream2 = await manager.create_stream("inv-completed")
        
        # Complete one stream
        await stream2.completed({})
        
        active = await manager.list_active()
        
        assert "inv-active" in active
        assert "inv-completed" not in active
    
    @pytest.mark.asyncio
    async def test_cleanup_completed(self, manager):
        """Test cleaning up old completed streams."""
        stream = await manager.create_stream("inv-old")
        
        # Manually set old timestamp
        await stream.completed({})
        stream.history[-1].timestamp = datetime.now() - timedelta(hours=2)
        
        # Cleanup with 1 hour max age
        await manager.cleanup_completed(max_age_seconds=3600)
        
        result = await manager.get_stream("inv-old")
        assert result is None


class TestGetStreamManager:
    """Tests for global stream manager."""
    
    def test_get_stream_manager(self):
        """Test getting global stream manager."""
        manager = get_stream_manager()
        
        assert manager is not None
        assert isinstance(manager, StreamManager)
    
    def test_get_stream_manager_singleton(self):
        """Test that manager is singleton."""
        manager1 = get_stream_manager()
        manager2 = get_stream_manager()
        
        assert manager1 is manager2
