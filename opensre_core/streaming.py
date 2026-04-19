"""
Real-time streaming for investigations.

Provides event-based streaming for investigation progress,
enabling real-time updates via WebSocket and CLI.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator


class StreamEventType(Enum):
    """Types of streaming events during investigation."""
    STARTED = "started"
    OBSERVATION = "observation"
    OBSERVATION_COMPLETE = "observation_complete"
    THINKING = "thinking"
    HYPOTHESIS = "hypothesis"
    ROOT_CAUSE = "root_cause"
    ACTION = "action"
    PROGRESS = "progress"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class StreamEvent:
    """A single streaming event."""
    type: StreamEventType
    data: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }


class InvestigationStream:
    """
    Manages streaming events for an investigation.

    Supports multiple subscribers via async queues.
    Replays history for late joiners.
    """

    def __init__(self):
        self.subscribers: list[asyncio.Queue] = []
        self.history: list[StreamEvent] = []
        self._completed = False

    @property
    def is_completed(self) -> bool:
        """Check if investigation has completed or errored."""
        return self._completed

    async def emit(self, event_type: StreamEventType, data: dict[str, Any]):
        """Emit an event to all subscribers."""
        event = StreamEvent(type=event_type, data=data)
        self.history.append(event)

        # Mark as completed on terminal events
        if event_type in (StreamEventType.COMPLETED, StreamEventType.ERROR):
            self._completed = True

        # Send to all subscribers
        for queue in self.subscribers:
            await queue.put(event)

    async def subscribe(self) -> AsyncIterator[StreamEvent]:
        """
        Subscribe to the event stream.

        Yields:
            StreamEvent: Events as they occur, starting with history replay
        """
        queue: asyncio.Queue = asyncio.Queue()
        self.subscribers.append(queue)

        try:
            # First, replay history
            for event in self.history:
                yield event

            # If already completed, we're done
            if self._completed:
                return

            # Then stream new events
            while True:
                event = await queue.get()
                yield event

                if event.type in (StreamEventType.COMPLETED, StreamEventType.ERROR):
                    break
        finally:
            if queue in self.subscribers:
                self.subscribers.remove(queue)

    # Convenience methods for emitting specific event types

    async def started(self, issue: str, namespace: str):
        """Emit investigation started event."""
        await self.emit(StreamEventType.STARTED, {
            "issue": issue,
            "namespace": namespace,
        })

    async def observation(self, source: str, summary: str, severity: str = "info", details: dict | None = None):
        """Emit observation collected event."""
        await self.emit(StreamEventType.OBSERVATION, {
            "source": source,
            "summary": summary,
            "severity": severity,
            "details": details or {},
        })

    async def observation_complete(self, count: int, services: list[str]):
        """Emit observation phase completed event."""
        await self.emit(StreamEventType.OBSERVATION_COMPLETE, {
            "count": count,
            "services": services,
        })

    async def thinking(self, thought: str):
        """Emit analysis thinking event."""
        await self.emit(StreamEventType.THINKING, {"thought": thought})

    async def hypothesis(self, hypothesis: str, confidence: float, evidence: list[str] | None = None):
        """Emit hypothesis generated event."""
        await self.emit(StreamEventType.HYPOTHESIS, {
            "hypothesis": hypothesis,
            "confidence": confidence,
            "evidence": evidence or [],
        })

    async def root_cause(self, cause: str, confidence: float):
        """Emit root cause identified event."""
        await self.emit(StreamEventType.ROOT_CAUSE, {
            "root_cause": cause,
            "confidence": confidence,
        })

    async def action(self, description: str, command: str, risk: str, action_id: str | None = None):
        """Emit remediation action suggested event."""
        await self.emit(StreamEventType.ACTION, {
            "id": action_id,
            "description": description,
            "command": command,
            "risk": risk,
        })

    async def progress(self, step: str, current: int, total: int):
        """Emit progress update event."""
        await self.emit(StreamEventType.PROGRESS, {
            "step": step,
            "current": current,
            "total": total,
        })

    async def completed(self, result: dict[str, Any]):
        """Emit investigation completed event."""
        await self.emit(StreamEventType.COMPLETED, result)

    async def error(self, message: str, details: dict | None = None):
        """Emit error event."""
        await self.emit(StreamEventType.ERROR, {
            "error": message,
            "details": details or {},
        })


class StreamManager:
    """
    Manages multiple active investigation streams.

    Allows WebSocket endpoints to subscribe to specific investigations.
    """

    def __init__(self):
        self._streams: dict[str, InvestigationStream] = {}
        self._lock = asyncio.Lock()

    async def create_stream(self, investigation_id: str) -> InvestigationStream:
        """Create a new stream for an investigation."""
        async with self._lock:
            stream = InvestigationStream()
            self._streams[investigation_id] = stream
            return stream

    async def get_stream(self, investigation_id: str) -> InvestigationStream | None:
        """Get an existing stream by investigation ID."""
        return self._streams.get(investigation_id)

    async def remove_stream(self, investigation_id: str):
        """Remove a completed stream."""
        async with self._lock:
            self._streams.pop(investigation_id, None)

    async def list_active(self) -> list[str]:
        """List active investigation IDs."""
        return [
            inv_id for inv_id, stream in self._streams.items()
            if not stream.is_completed
        ]

    async def cleanup_completed(self, max_age_seconds: int = 3600):
        """Remove old completed streams."""
        now = datetime.now()
        async with self._lock:
            to_remove = []
            for inv_id, stream in self._streams.items():
                if stream.is_completed and stream.history:
                    last_event = stream.history[-1]
                    age = (now - last_event.timestamp).total_seconds()
                    if age > max_age_seconds:
                        to_remove.append(inv_id)

            for inv_id in to_remove:
                del self._streams[inv_id]


# Global stream manager instance
_stream_manager: StreamManager | None = None


def get_stream_manager() -> StreamManager:
    """Get or create the global stream manager."""
    global _stream_manager
    if _stream_manager is None:
        _stream_manager = StreamManager()
    return _stream_manager
