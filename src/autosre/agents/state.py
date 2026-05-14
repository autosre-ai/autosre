"""Investigation State Machine.

Manages the lifecycle of an incident investigation with:
- State transitions with validation
- State persistence (file-based and SQLite)
- Retry handling with exponential backoff
- Timeout management
- Event emission for UI updates
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Awaitable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional, TypeVar, Generic
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =============================================================================
# State Machine Definitions
# =============================================================================


class InvestigationState(str, Enum):
    """Investigation lifecycle states."""
    
    PENDING = "pending"
    TRIAGING = "triaging"
    INVESTIGATING = "investigating"
    ANALYZING = "analyzing"
    RECOMMENDING = "recommending"
    AWAITING_ACTION = "awaiting_action"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    
    @property
    def is_terminal(self) -> bool:
        """Check if this is a terminal state."""
        return self in (
            InvestigationState.COMPLETED,
            InvestigationState.FAILED,
            InvestigationState.TIMEOUT,
            InvestigationState.CANCELLED,
        )
    
    @property
    def is_active(self) -> bool:
        """Check if this is an active/running state."""
        return self in (
            InvestigationState.TRIAGING,
            InvestigationState.INVESTIGATING,
            InvestigationState.ANALYZING,
            InvestigationState.RECOMMENDING,
            InvestigationState.EXECUTING,
        )


class StateTransition(BaseModel):
    """Defines a valid state transition."""
    
    from_state: InvestigationState
    to_state: InvestigationState
    on_event: str
    condition: Optional[str] = None  # Optional condition name
    
    def __hash__(self) -> int:
        return hash((self.from_state, self.to_state, self.on_event))


class TransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    
    def __init__(self, from_state: InvestigationState, to_state: InvestigationState, event: str):
        self.from_state = from_state
        self.to_state = to_state
        self.event = event
        super().__init__(
            f"Invalid transition: {from_state.value} -> {to_state.value} on event '{event}'"
        )


class InvestigationStateMachine:
    """State machine for investigation lifecycle.
    
    Defines valid state transitions and enforces transition rules.
    
    Example:
        >>> machine = InvestigationStateMachine()
        >>> machine.transition(InvestigationState.PENDING, "start")
        InvestigationState.TRIAGING
    """
    
    # All valid state transitions
    TRANSITIONS: list[StateTransition] = [
        # From PENDING
        StateTransition(from_state=InvestigationState.PENDING, to_state=InvestigationState.TRIAGING, on_event="start"),
        StateTransition(from_state=InvestigationState.PENDING, to_state=InvestigationState.CANCELLED, on_event="cancel"),
        StateTransition(from_state=InvestigationState.PENDING, to_state=InvestigationState.FAILED, on_event="error"),
        
        # From TRIAGING
        StateTransition(from_state=InvestigationState.TRIAGING, to_state=InvestigationState.INVESTIGATING, on_event="triage_complete"),
        StateTransition(from_state=InvestigationState.TRIAGING, to_state=InvestigationState.RECOMMENDING, on_event="skip_investigation"),
        StateTransition(from_state=InvestigationState.TRIAGING, to_state=InvestigationState.FAILED, on_event="error"),
        StateTransition(from_state=InvestigationState.TRIAGING, to_state=InvestigationState.TIMEOUT, on_event="timeout"),
        StateTransition(from_state=InvestigationState.TRIAGING, to_state=InvestigationState.CANCELLED, on_event="cancel"),
        
        # From INVESTIGATING
        StateTransition(from_state=InvestigationState.INVESTIGATING, to_state=InvestigationState.ANALYZING, on_event="observations_collected"),
        StateTransition(from_state=InvestigationState.INVESTIGATING, to_state=InvestigationState.INVESTIGATING, on_event="continue_iteration"),
        StateTransition(from_state=InvestigationState.INVESTIGATING, to_state=InvestigationState.FAILED, on_event="error"),
        StateTransition(from_state=InvestigationState.INVESTIGATING, to_state=InvestigationState.TIMEOUT, on_event="timeout"),
        StateTransition(from_state=InvestigationState.INVESTIGATING, to_state=InvestigationState.CANCELLED, on_event="cancel"),
        
        # From ANALYZING
        StateTransition(from_state=InvestigationState.ANALYZING, to_state=InvestigationState.RECOMMENDING, on_event="analysis_complete"),
        StateTransition(from_state=InvestigationState.ANALYZING, to_state=InvestigationState.INVESTIGATING, on_event="need_more_data"),
        StateTransition(from_state=InvestigationState.ANALYZING, to_state=InvestigationState.FAILED, on_event="error"),
        StateTransition(from_state=InvestigationState.ANALYZING, to_state=InvestigationState.TIMEOUT, on_event="timeout"),
        StateTransition(from_state=InvestigationState.ANALYZING, to_state=InvestigationState.CANCELLED, on_event="cancel"),
        
        # From RECOMMENDING
        StateTransition(from_state=InvestigationState.RECOMMENDING, to_state=InvestigationState.AWAITING_ACTION, on_event="actions_proposed"),
        StateTransition(from_state=InvestigationState.RECOMMENDING, to_state=InvestigationState.COMPLETED, on_event="no_action_needed"),
        StateTransition(from_state=InvestigationState.RECOMMENDING, to_state=InvestigationState.FAILED, on_event="error"),
        StateTransition(from_state=InvestigationState.RECOMMENDING, to_state=InvestigationState.TIMEOUT, on_event="timeout"),
        StateTransition(from_state=InvestigationState.RECOMMENDING, to_state=InvestigationState.CANCELLED, on_event="cancel"),
        
        # From AWAITING_ACTION
        StateTransition(from_state=InvestigationState.AWAITING_ACTION, to_state=InvestigationState.EXECUTING, on_event="action_approved"),
        StateTransition(from_state=InvestigationState.AWAITING_ACTION, to_state=InvestigationState.COMPLETED, on_event="action_rejected"),
        StateTransition(from_state=InvestigationState.AWAITING_ACTION, to_state=InvestigationState.COMPLETED, on_event="skip_action"),
        StateTransition(from_state=InvestigationState.AWAITING_ACTION, to_state=InvestigationState.TIMEOUT, on_event="timeout"),
        StateTransition(from_state=InvestigationState.AWAITING_ACTION, to_state=InvestigationState.CANCELLED, on_event="cancel"),
        
        # From EXECUTING
        StateTransition(from_state=InvestigationState.EXECUTING, to_state=InvestigationState.COMPLETED, on_event="execution_complete"),
        StateTransition(from_state=InvestigationState.EXECUTING, to_state=InvestigationState.FAILED, on_event="execution_failed"),
        StateTransition(from_state=InvestigationState.EXECUTING, to_state=InvestigationState.FAILED, on_event="error"),
        StateTransition(from_state=InvestigationState.EXECUTING, to_state=InvestigationState.TIMEOUT, on_event="timeout"),
        StateTransition(from_state=InvestigationState.EXECUTING, to_state=InvestigationState.CANCELLED, on_event="cancel"),
    ]
    
    def __init__(self):
        # Build transition lookup for O(1) access
        self._transitions: dict[tuple[InvestigationState, str], InvestigationState] = {
            (t.from_state, t.on_event): t.to_state
            for t in self.TRANSITIONS
        }
        
        # Valid events per state
        self._valid_events: dict[InvestigationState, set[str]] = {}
        for t in self.TRANSITIONS:
            if t.from_state not in self._valid_events:
                self._valid_events[t.from_state] = set()
            self._valid_events[t.from_state].add(t.on_event)
    
    def transition(self, current: InvestigationState, event: str) -> InvestigationState:
        """Get next state for an event.
        
        Args:
            current: Current state
            event: Event triggering transition
            
        Returns:
            New state after transition
            
        Raises:
            TransitionError: If transition is invalid
        """
        key = (current, event)
        if key not in self._transitions:
            raise TransitionError(current, InvestigationState.FAILED, event)
        return self._transitions[key]
    
    def can_transition(self, current: InvestigationState, event: str) -> bool:
        """Check if a transition is valid."""
        return (current, event) in self._transitions
    
    def get_valid_events(self, state: InvestigationState) -> set[str]:
        """Get valid events for a state."""
        return self._valid_events.get(state, set())
    
    def get_next_states(self, state: InvestigationState) -> list[InvestigationState]:
        """Get all possible next states from current state."""
        return [
            self._transitions[(state, event)]
            for event in self._valid_events.get(state, set())
        ]


# =============================================================================
# Event System
# =============================================================================


class EventType(str, Enum):
    """Types of events emitted during investigation."""
    
    # State changes
    STATE_CHANGED = "state_changed"
    
    # Phase events
    TRIAGE_STARTED = "triage_started"
    TRIAGE_COMPLETED = "triage_completed"
    INVESTIGATION_STARTED = "investigation_started"
    INVESTIGATION_PROGRESS = "investigation_progress"
    INVESTIGATION_COMPLETED = "investigation_completed"
    ANALYSIS_STARTED = "analysis_started"
    ANALYSIS_COMPLETED = "analysis_completed"
    REMEDIATION_STARTED = "remediation_started"
    REMEDIATION_COMPLETED = "remediation_completed"
    
    # Agent events
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    AGENT_FAILED = "agent_failed"
    AGENT_TIMEOUT = "agent_timeout"
    
    # Finding events
    FINDING_ADDED = "finding_added"
    HYPOTHESIS_UPDATED = "hypothesis_updated"
    
    # Action events
    ACTION_PROPOSED = "action_proposed"
    ACTION_APPROVED = "action_approved"
    ACTION_EXECUTED = "action_executed"
    ACTION_FAILED = "action_failed"
    
    # Error events
    ERROR_OCCURRED = "error_occurred"
    RETRY_ATTEMPTED = "retry_attempted"
    TIMEOUT_WARNING = "timeout_warning"
    
    # Completion events
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Event:
    """An event emitted during investigation."""
    
    type: EventType
    investigation_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    data: dict[str, Any] = field(default_factory=dict)
    source: str = "coordinator"
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "type": self.type.value,
            "investigation_id": self.investigation_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "source": self.source,
        }


# Type alias for event handlers
EventHandler = Callable[[Event], Awaitable[None]]


class EventEmitter:
    """Async event emitter for investigation events.
    
    Supports multiple listeners per event type and broadcasts
    events for UI updates and logging.
    
    Example:
        >>> emitter = EventEmitter()
        >>> async def handler(event): print(event)
        >>> emitter.on(EventType.STATE_CHANGED, handler)
        >>> await emitter.emit(EventType.STATE_CHANGED, "inv-123", {"state": "investigating"})
    """
    
    def __init__(self):
        self._handlers: dict[EventType, list[EventHandler]] = {}
        self._global_handlers: list[EventHandler] = []
        self._event_history: list[Event] = []
        self._max_history: int = 1000
    
    def on(self, event_type: EventType, handler: EventHandler) -> None:
        """Register a handler for an event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    def on_all(self, handler: EventHandler) -> None:
        """Register a handler for all events."""
        self._global_handlers.append(handler)
    
    def off(self, event_type: EventType, handler: EventHandler) -> None:
        """Remove a handler."""
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h != handler
            ]
    
    async def emit(
        self,
        event_type: EventType,
        investigation_id: str,
        data: Optional[dict[str, Any]] = None,
        source: str = "coordinator",
    ) -> None:
        """Emit an event to all registered handlers.
        
        Args:
            event_type: Type of event
            investigation_id: Associated investigation
            data: Event data
            source: Event source component
        """
        event = Event(
            type=event_type,
            investigation_id=investigation_id,
            data=data or {},
            source=source,
        )
        
        # Store in history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]
        
        # Notify handlers
        handlers = self._handlers.get(event_type, []) + self._global_handlers
        
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Event handler error: {e}", exc_info=True)
    
    def get_history(
        self,
        investigation_id: Optional[str] = None,
        event_types: Optional[list[EventType]] = None,
        limit: int = 100,
    ) -> list[Event]:
        """Get event history with optional filters."""
        events = self._event_history
        
        if investigation_id:
            events = [e for e in events if e.investigation_id == investigation_id]
        
        if event_types:
            events = [e for e in events if e.type in event_types]
        
        return events[-limit:]


# =============================================================================
# Retry Handling
# =============================================================================


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    
    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple = (Exception,)
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a retry attempt."""
        import random
        
        delay = min(
            self.initial_delay * (self.exponential_base ** attempt),
            self.max_delay,
        )
        
        if self.jitter:
            delay = delay * (0.5 + random.random())
        
        return delay


@dataclass
class RetryState:
    """Tracks retry state for an operation."""
    
    operation: str
    max_retries: int
    attempts: int = 0
    last_error: Optional[str] = None
    last_attempt_at: Optional[datetime] = None
    
    @property
    def can_retry(self) -> bool:
        """Check if more retries are available."""
        return self.attempts < self.max_retries
    
    @property
    def is_exhausted(self) -> bool:
        """Check if all retries are exhausted."""
        return self.attempts >= self.max_retries
    
    def record_attempt(self, error: Optional[str] = None) -> None:
        """Record a retry attempt."""
        self.attempts += 1
        self.last_error = error
        self.last_attempt_at = datetime.now(timezone.utc)


class RetryManager:
    """Manages retries for investigation operations.
    
    Provides exponential backoff with jitter and tracks retry
    state per operation.
    
    Example:
        >>> manager = RetryManager()
        >>> async with manager.retry_context("triage", investigation_id) as retry:
        ...     # Your operation here
        ...     pass
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self._states: dict[str, RetryState] = {}
    
    def get_state(self, operation_id: str) -> Optional[RetryState]:
        """Get retry state for an operation."""
        return self._states.get(operation_id)
    
    def _get_key(self, operation: str, investigation_id: str) -> str:
        """Generate key for operation tracking."""
        return f"{investigation_id}:{operation}"
    
    @asynccontextmanager
    async def retry_context(
        self,
        operation: str,
        investigation_id: str,
        on_retry: Optional[Callable[[int, Exception], Awaitable[None]]] = None,
    ):
        """Context manager for retryable operations.
        
        Args:
            operation: Operation name
            investigation_id: Investigation ID
            on_retry: Optional callback on retry
            
        Yields:
            RetryState for tracking
        """
        key = self._get_key(operation, investigation_id)
        
        if key not in self._states:
            self._states[key] = RetryState(
                operation=operation,
                max_retries=self.config.max_retries,
            )
        
        state = self._states[key]
        
        while True:
            state.record_attempt()
            
            try:
                yield state
                # Success - clear state
                del self._states[key]
                break
                
            except self.config.retryable_exceptions as e:
                state.last_error = str(e)
                
                if not state.can_retry:
                    logger.error(
                        f"Operation {operation} failed after {state.attempts} attempts: {e}"
                    )
                    raise
                
                delay = self.config.get_delay(state.attempts - 1)
                logger.warning(
                    f"Operation {operation} failed (attempt {state.attempts}/"
                    f"{state.max_retries}), retrying in {delay:.1f}s: {e}"
                )
                
                if on_retry:
                    await on_retry(state.attempts, e)
                
                await asyncio.sleep(delay)


# =============================================================================
# Timeout Handling
# =============================================================================


@dataclass
class TimeoutConfig:
    """Configuration for operation timeouts."""
    
    total_timeout: float = 600.0  # 10 minutes total
    triage_timeout: float = 30.0
    investigation_timeout: float = 300.0
    analysis_timeout: float = 60.0
    remediation_timeout: float = 60.0
    action_timeout: float = 120.0
    
    warning_threshold: float = 0.8  # Warn at 80% of timeout


class TimeoutManager:
    """Manages timeouts for investigation phases.
    
    Tracks elapsed time and emits warnings when approaching limits.
    
    Example:
        >>> manager = TimeoutManager(config)
        >>> async with manager.timeout_context("triage", inv_id, emitter):
        ...     # Your triage operation
        ...     pass
    """
    
    def __init__(self, config: Optional[TimeoutConfig] = None):
        self.config = config or TimeoutConfig()
        self._start_times: dict[str, datetime] = {}
        self._warnings_sent: set[str] = set()
    
    def get_timeout_for_phase(self, phase: str) -> float:
        """Get timeout duration for a phase."""
        timeouts = {
            "triage": self.config.triage_timeout,
            "triaging": self.config.triage_timeout,
            "investigation": self.config.investigation_timeout,
            "investigating": self.config.investigation_timeout,
            "analysis": self.config.analysis_timeout,
            "analyzing": self.config.analysis_timeout,
            "remediation": self.config.remediation_timeout,
            "recommending": self.config.remediation_timeout,
            "action": self.config.action_timeout,
            "executing": self.config.action_timeout,
        }
        return timeouts.get(phase, self.config.total_timeout)
    
    def start_timer(self, operation_id: str) -> None:
        """Start timing an operation."""
        self._start_times[operation_id] = datetime.now(timezone.utc)
    
    def get_elapsed(self, operation_id: str) -> float:
        """Get elapsed time for an operation."""
        start = self._start_times.get(operation_id)
        if not start:
            return 0.0
        return (datetime.now(timezone.utc) - start).total_seconds()
    
    def get_remaining(self, operation_id: str, timeout: float) -> float:
        """Get remaining time before timeout."""
        elapsed = self.get_elapsed(operation_id)
        return max(0.0, timeout - elapsed)
    
    def is_approaching_timeout(self, operation_id: str, timeout: float) -> bool:
        """Check if approaching timeout threshold."""
        elapsed = self.get_elapsed(operation_id)
        return elapsed >= timeout * self.config.warning_threshold
    
    @asynccontextmanager
    async def timeout_context(
        self,
        phase: str,
        investigation_id: str,
        emitter: Optional[EventEmitter] = None,
    ):
        """Context manager that enforces timeout.
        
        Args:
            phase: Phase name (for timeout lookup)
            investigation_id: Investigation ID
            emitter: Event emitter for warnings
        """
        operation_id = f"{investigation_id}:{phase}"
        timeout = self.get_timeout_for_phase(phase)
        
        self.start_timer(operation_id)
        
        async def check_timeout():
            """Background task to check timeout warnings."""
            warning_time = timeout * self.config.warning_threshold
            await asyncio.sleep(warning_time)
            
            if operation_id not in self._warnings_sent:
                self._warnings_sent.add(operation_id)
                if emitter:
                    await emitter.emit(
                        EventType.TIMEOUT_WARNING,
                        investigation_id,
                        {
                            "phase": phase,
                            "elapsed": self.get_elapsed(operation_id),
                            "timeout": timeout,
                            "remaining": self.get_remaining(operation_id, timeout),
                        },
                    )
        
        # Start warning checker
        warning_task = asyncio.create_task(check_timeout())
        
        try:
            # Run with timeout
            yield
            
        except asyncio.TimeoutError:
            logger.error(f"Phase {phase} timed out after {timeout}s")
            raise
            
        finally:
            warning_task.cancel()
            try:
                await warning_task
            except asyncio.CancelledError:
                pass
            
            # Cleanup
            if operation_id in self._start_times:
                del self._start_times[operation_id]
            self._warnings_sent.discard(operation_id)


# =============================================================================
# State Persistence
# =============================================================================


class StatePersister(ABC):
    """Abstract base for state persistence."""
    
    @abstractmethod
    async def save(self, investigation_id: str, state: dict[str, Any]) -> None:
        """Save investigation state."""
        pass
    
    @abstractmethod
    async def load(self, investigation_id: str) -> Optional[dict[str, Any]]:
        """Load investigation state."""
        pass
    
    @abstractmethod
    async def delete(self, investigation_id: str) -> None:
        """Delete investigation state."""
        pass
    
    @abstractmethod
    async def list_active(self) -> list[str]:
        """List active investigation IDs."""
        pass


class FileStatePersister(StatePersister):
    """File-based state persistence.
    
    Stores investigation state as JSON files in a directory.
    Suitable for development and single-instance deployments.
    """
    
    def __init__(self, state_dir: Path):
        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_path(self, investigation_id: str) -> Path:
        """Get file path for investigation state."""
        # Sanitize ID for filename
        safe_id = "".join(c if c.isalnum() or c == "-" else "_" for c in investigation_id)
        return self.state_dir / f"{safe_id}.json"
    
    async def save(self, investigation_id: str, state: dict[str, Any]) -> None:
        """Save state to file."""
        path = self._get_path(investigation_id)
        
        # Add metadata
        state["_saved_at"] = datetime.now(timezone.utc).isoformat()
        
        # Atomic write
        tmp_path = path.with_suffix(".tmp")
        try:
            tmp_path.write_text(json.dumps(state, indent=2, default=str))
            tmp_path.rename(path)
            logger.debug(f"Saved state for {investigation_id}")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
            if tmp_path.exists():
                tmp_path.unlink()
            raise
    
    async def load(self, investigation_id: str) -> Optional[dict[str, Any]]:
        """Load state from file."""
        path = self._get_path(investigation_id)
        
        if not path.exists():
            return None
        
        try:
            return json.loads(path.read_text())
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            return None
    
    async def delete(self, investigation_id: str) -> None:
        """Delete state file."""
        path = self._get_path(investigation_id)
        if path.exists():
            path.unlink()
            logger.debug(f"Deleted state for {investigation_id}")
    
    async def list_active(self) -> list[str]:
        """List investigation IDs with saved state."""
        ids = []
        for path in self.state_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                state = data.get("status", "")
                if not InvestigationState(state).is_terminal:
                    # Extract ID from state data or filename
                    inv_id = data.get("investigation_id", path.stem)
                    ids.append(inv_id)
            except Exception:
                continue
        return ids


class SQLiteStatePersister(StatePersister):
    """SQLite-based state persistence.
    
    Uses SQLite for more robust persistence with querying capabilities.
    Suitable for production single-instance deployments.
    """
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS investigation_state (
                    investigation_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status ON investigation_state(status)
            """)
            conn.commit()
    
    async def save(self, investigation_id: str, state: dict[str, Any]) -> None:
        """Save state to SQLite."""
        now = datetime.now(timezone.utc).isoformat()
        status = state.get("status", "pending")
        state_json = json.dumps(state, default=str)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO investigation_state 
                    (investigation_id, status, state_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(investigation_id) DO UPDATE SET
                    status = excluded.status,
                    state_json = excluded.state_json,
                    updated_at = excluded.updated_at
                """,
                (investigation_id, status, state_json, now, now),
            )
            conn.commit()
    
    async def load(self, investigation_id: str) -> Optional[dict[str, Any]]:
        """Load state from SQLite."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT state_json FROM investigation_state WHERE investigation_id = ?",
                (investigation_id,),
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
        return None
    
    async def delete(self, investigation_id: str) -> None:
        """Delete state from SQLite."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM investigation_state WHERE investigation_id = ?",
                (investigation_id,),
            )
            conn.commit()
    
    async def list_active(self) -> list[str]:
        """List active investigations."""
        terminal_states = [s.value for s in InvestigationState if s.is_terminal]
        placeholders = ",".join("?" * len(terminal_states))
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                f"SELECT investigation_id FROM investigation_state WHERE status NOT IN ({placeholders})",
                terminal_states,
            )
            return [row[0] for row in cursor.fetchall()]


class InMemoryStatePersister(StatePersister):
    """In-memory state persistence for testing."""
    
    def __init__(self):
        self._states: dict[str, dict[str, Any]] = {}
    
    async def save(self, investigation_id: str, state: dict[str, Any]) -> None:
        self._states[investigation_id] = state.copy()
    
    async def load(self, investigation_id: str) -> Optional[dict[str, Any]]:
        return self._states.get(investigation_id)
    
    async def delete(self, investigation_id: str) -> None:
        self._states.pop(investigation_id, None)
    
    async def list_active(self) -> list[str]:
        return [
            inv_id for inv_id, state in self._states.items()
            if not InvestigationState(state.get("status", "pending")).is_terminal
        ]


# =============================================================================
# Stateful Investigation Context
# =============================================================================


class InvestigationContext(BaseModel):
    """Full investigation context with state management.
    
    Combines all state components into a single manageable unit
    that can be persisted and restored.
    """
    
    investigation_id: str = Field(default_factory=lambda: str(uuid4()))
    status: InvestigationState = InvestigationState.PENDING
    
    # Timing
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Phase tracking
    current_phase: str = "pending"
    phase_history: list[dict[str, Any]] = Field(default_factory=list)
    
    # Iteration tracking  
    iteration: int = 0
    max_iterations: int = 3
    
    # Agent tracking
    pending_agents: list[str] = Field(default_factory=list)
    completed_agents: list[str] = Field(default_factory=list)
    failed_agents: list[str] = Field(default_factory=list)
    
    # Retry tracking
    retry_counts: dict[str, int] = Field(default_factory=dict)
    
    # Error tracking
    errors: list[dict[str, Any]] = Field(default_factory=list)
    
    # Result data (stored separately for size)
    has_result: bool = False
    
    def get_status(self) -> InvestigationState:
        """Get status as enum (handles string conversion from Pydantic)."""
        if isinstance(self.status, InvestigationState):
            return self.status
        return InvestigationState(self.status)
    
    def record_phase_transition(
        self,
        from_phase: str,
        to_phase: str,
        event: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Record a phase transition."""
        self.phase_history.append({
            "from": from_phase,
            "to": to_phase,
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details or {},
        })
        self.current_phase = to_phase
    
    def record_error(self, error: str, phase: str, recoverable: bool = True) -> None:
        """Record an error."""
        self.errors.append({
            "error": error,
            "phase": phase,
            "recoverable": recoverable,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    
    def increment_retry(self, operation: str) -> int:
        """Increment retry count and return new value."""
        self.retry_counts[operation] = self.retry_counts.get(operation, 0) + 1
        return self.retry_counts[operation]
    
    def to_persist_dict(self) -> dict[str, Any]:
        """Convert to dictionary for persistence."""
        status_value = self.status.value if isinstance(self.status, InvestigationState) else self.status
        return {
            "investigation_id": self.investigation_id,
            "status": status_value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "current_phase": self.current_phase,
            "phase_history": self.phase_history,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "pending_agents": self.pending_agents,
            "completed_agents": self.completed_agents,
            "failed_agents": self.failed_agents,
            "retry_counts": self.retry_counts,
            "errors": self.errors,
            "has_result": self.has_result,
        }
    
    @classmethod
    def from_persist_dict(cls, data: dict[str, Any]) -> "InvestigationContext":
        """Restore from persistence dictionary."""
        return cls(
            investigation_id=data.get("investigation_id", str(uuid4())),
            status=InvestigationState(data.get("status", "pending")),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(timezone.utc),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            current_phase=data.get("current_phase", "pending"),
            phase_history=data.get("phase_history", []),
            iteration=data.get("iteration", 0),
            max_iterations=data.get("max_iterations", 3),
            pending_agents=data.get("pending_agents", []),
            completed_agents=data.get("completed_agents", []),
            failed_agents=data.get("failed_agents", []),
            retry_counts=data.get("retry_counts", {}),
            errors=data.get("errors", []),
            has_result=data.get("has_result", False),
        )


# =============================================================================
# Factory Functions
# =============================================================================


def create_persister(
    backend: str = "memory",
    path: Optional[Path] = None,
) -> StatePersister:
    """Create a state persister.
    
    Args:
        backend: "memory", "file", or "sqlite"
        path: Path for file/sqlite backends
        
    Returns:
        StatePersister instance
    """
    if backend == "memory":
        return InMemoryStatePersister()
    elif backend == "file":
        if not path:
            path = Path.home() / ".autosre" / "state"
        return FileStatePersister(path)
    elif backend == "sqlite":
        if not path:
            path = Path.home() / ".autosre" / "state.db"
        return SQLiteStatePersister(path)
    else:
        raise ValueError(f"Unknown backend: {backend}")
