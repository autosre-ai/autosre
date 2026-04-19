"""
Tests for streaming infrastructure.
"""

import pytest
import asyncio
from datetime import datetime

from opensre_core.streaming import (
    StreamEventType,
    StreamEvent,
    InvestigationStream,
    StreamManager,
    get_stream_manager,
)


class TestStreamEvent:
    """Tests for StreamEvent dataclass."""
    
    def test_stream_event_creation(self):
        """Test creating a stream event."""
        event = StreamEvent(
            type=StreamEventType.STARTED,
            data={"issue": "test issue", "namespace": "default"}
        )
        assert event.type == StreamEventType.STARTED
        assert event.data["issue"] == "test issue"
        assert event.timestamp is not None
    
    def test_stream_event_to_dict(self):
        """Test converting stream event to dictionary."""
        event = StreamEvent(
            type=StreamEventType.OBSERVATION,
            data={"source": "prometheus", "summary": "High CPU"}
        )
        result = event.to_dict()
        
        assert result["type"] == "observation"
        assert result["data"]["source"] == "prometheus"
        assert "timestamp" in result
    
    def test_stream_event_with_custom_timestamp(self):
        """Test creating event with custom timestamp."""
        custom_time = datetime(2025, 1, 1, 12, 0, 0)
        event = StreamEvent(
            type=StreamEventType.COMPLETED,
            data={},
            timestamp=custom_time
        )
        assert event.timestamp == custom_time


class TestInvestigationStream:
    """Tests for InvestigationStream."""
    
    @pytest.mark.asyncio
    async def test_emit_adds_to_history(self):
        """Test that emit adds event to history."""
        stream = InvestigationStream()
        await stream.emit(StreamEventType.STARTED, {"test": True})
        
        assert len(stream.history) == 1
        assert stream.history[0].type == StreamEventType.STARTED
    
    @pytest.mark.asyncio
    async def test_started_convenience_method(self):
        """Test started convenience method."""
        stream = InvestigationStream()
        await stream.started("test issue", "default")
        
        assert len(stream.history) == 1
        assert stream.history[0].data["issue"] == "test issue"
        assert stream.history[0].data["namespace"] == "default"
    
    @pytest.mark.asyncio
    async def test_observation_convenience_method(self):
        """Test observation convenience method."""
        stream = InvestigationStream()
        await stream.observation("prometheus", "High CPU", severity="warning")
        
        event = stream.history[0]
        assert event.type == StreamEventType.OBSERVATION
        assert event.data["source"] == "prometheus"
        assert event.data["severity"] == "warning"
    
    @pytest.mark.asyncio
    async def test_thinking_convenience_method(self):
        """Test thinking convenience method."""
        stream = InvestigationStream()
        await stream.thinking("Analyzing metrics...")
        
        event = stream.history[0]
        assert event.type == StreamEventType.THINKING
        assert event.data["thought"] == "Analyzing metrics..."
    
    @pytest.mark.asyncio
    async def test_hypothesis_convenience_method(self):
        """Test hypothesis convenience method."""
        stream = InvestigationStream()
        await stream.hypothesis(
            "Memory leak in service",
            confidence=0.75,
            evidence=["High memory growth"]
        )
        
        event = stream.history[0]
        assert event.type == StreamEventType.HYPOTHESIS
        assert event.data["confidence"] == 0.75
        assert "High memory growth" in event.data["evidence"]
    
    @pytest.mark.asyncio
    async def test_root_cause_convenience_method(self):
        """Test root_cause convenience method."""
        stream = InvestigationStream()
        await stream.root_cause("Memory leak", confidence=0.85)
        
        event = stream.history[0]
        assert event.type == StreamEventType.ROOT_CAUSE
        assert event.data["root_cause"] == "Memory leak"
        assert event.data["confidence"] == 0.85
    
    @pytest.mark.asyncio
    async def test_action_convenience_method(self):
        """Test action convenience method."""
        stream = InvestigationStream()
        await stream.action(
            description="Restart service",
            command="kubectl rollout restart deployment/api",
            risk="medium",
            action_id="act123"
        )
        
        event = stream.history[0]
        assert event.type == StreamEventType.ACTION
        assert event.data["command"] == "kubectl rollout restart deployment/api"
        assert event.data["risk"] == "medium"
    
    @pytest.mark.asyncio
    async def test_progress_convenience_method(self):
        """Test progress convenience method."""
        stream = InvestigationStream()
        await stream.progress("Collecting observations", 1, 4)
        
        event = stream.history[0]
        assert event.type == StreamEventType.PROGRESS
        assert event.data["step"] == "Collecting observations"
        assert event.data["current"] == 1
        assert event.data["total"] == 4
    
    @pytest.mark.asyncio
    async def test_completed_marks_stream_done(self):
        """Test that completed marks the stream as done."""
        stream = InvestigationStream()
        assert not stream.is_completed
        
        await stream.completed({"result": "success"})
        
        assert stream.is_completed
    
    @pytest.mark.asyncio
    async def test_error_marks_stream_done(self):
        """Test that error marks the stream as done."""
        stream = InvestigationStream()
        assert not stream.is_completed
        
        await stream.error("Something went wrong")
        
        assert stream.is_completed
    
    @pytest.mark.asyncio
    async def test_subscribe_replays_history(self):
        """Test that subscribe replays historical events."""
        stream = InvestigationStream()
        
        # Add some history
        await stream.started("test", "default")
        await stream.observation("k8s", "Pod ready")
        await stream.completed({})
        
        # Subscribe and collect events
        events = []
        async for event in stream.subscribe():
            events.append(event)
        
        assert len(events) == 3
        assert events[0].type == StreamEventType.STARTED
        assert events[1].type == StreamEventType.OBSERVATION
        assert events[2].type == StreamEventType.COMPLETED
    
    @pytest.mark.asyncio
    async def test_subscribe_receives_live_events(self):
        """Test that subscribe receives live events."""
        stream = InvestigationStream()
        received = []
        
        async def subscriber():
            async for event in stream.subscribe():
                received.append(event)
                if event.type == StreamEventType.COMPLETED:
                    break
        
        async def emitter():
            await asyncio.sleep(0.01)
            await stream.started("test", "default")
            await asyncio.sleep(0.01)
            await stream.observation("k8s", "Pod ready")
            await asyncio.sleep(0.01)
            await stream.completed({})
        
        await asyncio.gather(subscriber(), emitter())
        
        assert len(received) == 3
    
    @pytest.mark.asyncio
    async def test_multiple_subscribers(self):
        """Test multiple subscribers receive same events."""
        stream = InvestigationStream()
        received1 = []
        received2 = []
        
        async def subscriber(events_list):
            async for event in stream.subscribe():
                events_list.append(event)
                if event.type == StreamEventType.COMPLETED:
                    break
        
        async def emitter():
            await asyncio.sleep(0.01)
            await stream.started("test", "default")
            await asyncio.sleep(0.01)
            await stream.completed({})
        
        await asyncio.gather(
            subscriber(received1),
            subscriber(received2),
            emitter()
        )
        
        assert len(received1) == 2
        assert len(received2) == 2


class TestStreamManager:
    """Tests for StreamManager."""
    
    @pytest.mark.asyncio
    async def test_create_stream(self):
        """Test creating a stream."""
        manager = StreamManager()
        stream = await manager.create_stream("inv123")
        
        assert stream is not None
        assert not stream.is_completed
    
    @pytest.mark.asyncio
    async def test_get_stream(self):
        """Test getting an existing stream."""
        manager = StreamManager()
        await manager.create_stream("inv123")
        
        stream = await manager.get_stream("inv123")
        assert stream is not None
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_stream(self):
        """Test getting a stream that doesn't exist."""
        manager = StreamManager()
        stream = await manager.get_stream("nonexistent")
        assert stream is None
    
    @pytest.mark.asyncio
    async def test_remove_stream(self):
        """Test removing a stream."""
        manager = StreamManager()
        await manager.create_stream("inv123")
        await manager.remove_stream("inv123")
        
        stream = await manager.get_stream("inv123")
        assert stream is None
    
    @pytest.mark.asyncio
    async def test_list_active(self):
        """Test listing active streams."""
        manager = StreamManager()
        stream1 = await manager.create_stream("inv1")
        stream2 = await manager.create_stream("inv2")
        
        # Complete one stream
        await stream1.completed({})
        
        active = await manager.list_active()
        assert "inv2" in active
        assert "inv1" not in active
    
    @pytest.mark.asyncio
    async def test_cleanup_completed(self):
        """Test cleanup of old completed streams."""
        manager = StreamManager()
        stream = await manager.create_stream("old")
        await stream.completed({})
        
        # Force the timestamp to be old
        stream.history[0].timestamp = datetime(2020, 1, 1)
        
        await manager.cleanup_completed(max_age_seconds=1)
        
        assert await manager.get_stream("old") is None


class TestGlobalStreamManager:
    """Tests for global stream manager singleton."""
    
    def test_get_stream_manager_returns_same_instance(self):
        """Test that get_stream_manager returns singleton."""
        manager1 = get_stream_manager()
        manager2 = get_stream_manager()
        
        assert manager1 is manager2
