"""
Event Streaming for Dashboard

Provides real-time event streaming for the dashboard including:
- Investigation lifecycle events
- Action events (approval, rejection, execution)
- Alert events
- System events
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Callable

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of dashboard events."""
    # Investigation lifecycle
    INVESTIGATION_STARTED = "investigation_started"
    INVESTIGATION_PROGRESS = "investigation_progress"
    INVESTIGATION_COMPLETED = "investigation_completed"
    INVESTIGATION_FAILED = "investigation_failed"
    
    # Action events
    ACTION_PROPOSED = "action_proposed"
    ACTION_APPROVED = "action_approved"
    ACTION_REJECTED = "action_rejected"
    ACTION_EXECUTED = "action_executed"
    ACTION_FAILED = "action_failed"
    
    # Alert events
    ALERT_TRIGGERED = "alert_triggered"
    ALERT_RESOLVED = "alert_resolved"
    ALERT_ACKNOWLEDGED = "alert_acknowledged"
    
    # System events
    SYSTEM_STARTED = "system_started"
    SYSTEM_SHUTDOWN = "system_shutdown"
    SYSTEM_ERROR = "system_error"
    INTEGRATION_CONNECTED = "integration_connected"
    INTEGRATION_DISCONNECTED = "integration_disconnected"
    
    # User events
    USER_CONNECTED = "user_connected"
    USER_DISCONNECTED = "user_disconnected"


@dataclass
class DashboardEvent:
    """A single dashboard event."""
    event_type: str
    data: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "system"
    severity: str = "info"  # info, warning, error, critical

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "event_type": self.event_type,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "severity": self.severity,
        }


class EventStream:
    """
    Manages event streaming for the dashboard.
    
    Features:
    - Pub/sub pattern with async queues
    - Event history with configurable retention
    - Event filtering
    - Event handlers for side effects
    """

    def __init__(self, max_history: int = 1000):
        self._subscribers: list[asyncio.Queue] = []
        self._history: list[DashboardEvent] = []
        self._max_history = max_history
        self._lock = asyncio.Lock()
        self._handlers: dict[str, list[Callable]] = {}

    async def emit(
        self,
        event_type: str | EventType,
        data: dict[str, Any],
        source: str = "system",
        severity: str = "info",
    ):
        """
        Emit an event to all subscribers.
        
        Args:
            event_type: Type of event (string or EventType enum)
            data: Event payload
            source: Event source identifier
            severity: Event severity level
        """
        if isinstance(event_type, EventType):
            event_type = event_type.value
        
        event = DashboardEvent(
            event_type=event_type,
            data=data,
            source=source,
            severity=severity,
        )
        
        async with self._lock:
            # Add to history
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
            
            # Send to all subscribers
            for queue in self._subscribers:
                try:
                    await queue.put(event)
                except Exception as e:
                    logger.warning(f"Failed to emit event to subscriber: {e}")
        
        # Call registered handlers
        await self._call_handlers(event)
        
        logger.debug(f"Event emitted: {event_type}")

    async def subscribe(
        self,
        filter_types: set[str] | None = None,
        replay_history: bool = False,
    ) -> AsyncIterator[DashboardEvent]:
        """
        Subscribe to the event stream.
        
        Args:
            filter_types: Optional set of event types to receive
            replay_history: Whether to replay historical events first
            
        Yields:
            DashboardEvent: Events as they occur
        """
        queue: asyncio.Queue = asyncio.Queue()
        
        async with self._lock:
            self._subscribers.append(queue)
        
        try:
            # Replay history if requested
            if replay_history:
                for event in self._history:
                    if filter_types and event.event_type not in filter_types:
                        continue
                    yield event
            
            # Stream new events
            while True:
                event = await queue.get()
                if filter_types and event.event_type not in filter_types:
                    continue
                yield event
                
        finally:
            async with self._lock:
                if queue in self._subscribers:
                    self._subscribers.remove(queue)

    def register_handler(self, event_type: str | EventType, handler: Callable):
        """
        Register a handler to be called when an event type is emitted.
        
        Args:
            event_type: Type of event to handle
            handler: Async callable to handle the event
        """
        if isinstance(event_type, EventType):
            event_type = event_type.value
        
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    async def _call_handlers(self, event: DashboardEvent):
        """Call all registered handlers for an event."""
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Event handler error for {event.event_type}: {e}")

    def get_history(
        self,
        event_types: set[str] | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[DashboardEvent]:
        """
        Get historical events.
        
        Args:
            event_types: Filter by event types
            since: Only events after this timestamp
            limit: Maximum number of events to return
            
        Returns:
            List of matching events (most recent last)
        """
        events = self._history
        
        if event_types:
            events = [e for e in events if e.event_type in event_types]
        
        if since:
            events = [e for e in events if e.timestamp > since]
        
        if limit:
            events = events[-limit:]
        
        return events

    @property
    def subscriber_count(self) -> int:
        """Number of active subscribers."""
        return len(self._subscribers)


# Global event stream instance
_event_stream: EventStream | None = None


def get_event_stream() -> EventStream:
    """Get or create the global event stream."""
    global _event_stream
    if _event_stream is None:
        _event_stream = EventStream()
    return _event_stream


# Convenience functions for common events

async def emit_investigation_started(
    investigation_id: str,
    issue: str,
    namespace: str = "default",
):
    """Emit investigation started event."""
    stream = get_event_stream()
    await stream.emit(
        EventType.INVESTIGATION_STARTED,
        {
            "investigation_id": investigation_id,
            "issue": issue,
            "namespace": namespace,
        },
    )


async def emit_investigation_completed(
    investigation_id: str,
    result: dict[str, Any],
    duration_seconds: float,
):
    """Emit investigation completed event."""
    stream = get_event_stream()
    await stream.emit(
        EventType.INVESTIGATION_COMPLETED,
        {
            "investigation_id": investigation_id,
            "result": result,
            "duration_seconds": duration_seconds,
        },
    )


async def emit_action_proposed(
    investigation_id: str,
    action_id: str,
    description: str,
    risk: str,
):
    """Emit action proposed event."""
    stream = get_event_stream()
    await stream.emit(
        EventType.ACTION_PROPOSED,
        {
            "investigation_id": investigation_id,
            "action_id": action_id,
            "description": description,
            "risk": risk,
        },
    )


async def emit_action_approved(
    investigation_id: str,
    action_id: str,
    approved_by: str,
):
    """Emit action approved event."""
    stream = get_event_stream()
    await stream.emit(
        EventType.ACTION_APPROVED,
        {
            "investigation_id": investigation_id,
            "action_id": action_id,
            "approved_by": approved_by,
        },
    )


async def emit_action_executed(
    investigation_id: str,
    action_id: str,
    result: dict[str, Any],
    success: bool,
):
    """Emit action executed event."""
    stream = get_event_stream()
    await stream.emit(
        EventType.ACTION_EXECUTED,
        {
            "investigation_id": investigation_id,
            "action_id": action_id,
            "result": result,
            "success": success,
        },
        severity="info" if success else "warning",
    )


async def emit_alert_triggered(
    alert_id: str,
    alert_name: str,
    severity: str,
    source: str,
    labels: dict[str, str] | None = None,
):
    """Emit alert triggered event."""
    stream = get_event_stream()
    await stream.emit(
        EventType.ALERT_TRIGGERED,
        {
            "alert_id": alert_id,
            "alert_name": alert_name,
            "severity": severity,
            "source": source,
            "labels": labels or {},
        },
        severity="warning" if severity in ("warning", "info") else "error",
    )


async def emit_system_error(error: str, details: dict[str, Any] | None = None):
    """Emit system error event."""
    stream = get_event_stream()
    await stream.emit(
        EventType.SYSTEM_ERROR,
        {
            "error": error,
            "details": details or {},
        },
        severity="error",
    )
