"""Circuit Breaker for AutoSRE V2 High Availability.

Implements the circuit breaker pattern for fault isolation:
- Prevents cascading failures
- Automatic recovery with half-open state
- Configurable failure thresholds
- Metrics and monitoring
"""

from __future__ import annotations

import asyncio
import functools
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar, Awaitable
from uuid import uuid4

from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class CircuitState(str, Enum):
    """State of a circuit breaker."""
    
    CLOSED = "closed"  # Normal operation, requests pass through
    OPEN = "open"  # Failures exceeded threshold, requests blocked
    HALF_OPEN = "half_open"  # Testing if service has recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for a circuit breaker."""
    
    # Failure thresholds
    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 3  # Successes before closing from half-open
    
    # Timing
    timeout_seconds: float = 30.0  # Time to wait before half-open
    half_open_max_calls: int = 3  # Max calls in half-open state
    
    # Rolling window
    window_size_seconds: float = 60.0  # Window for counting failures
    
    # Exceptions
    excluded_exceptions: tuple = ()  # Exceptions that don't count as failures
    included_exceptions: tuple = (Exception,)  # Exceptions that count as failures
    
    # Recovery
    reset_on_success: bool = False  # Reset failure count on any success


class CircuitBreakerError(Exception):
    """Base exception for circuit breaker errors."""
    
    def __init__(self, message: str, circuit_name: str):
        super().__init__(message)
        self.circuit_name = circuit_name


class CircuitOpenError(CircuitBreakerError):
    """Exception raised when circuit is open."""
    
    def __init__(
        self,
        circuit_name: str,
        retry_after_seconds: float,
    ):
        super().__init__(
            f"Circuit '{circuit_name}' is open, retry after {retry_after_seconds:.1f}s",
            circuit_name,
        )
        self.retry_after_seconds = retry_after_seconds


class CircuitFailure(BaseModel):
    """Record of a circuit failure."""
    
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    exception_type: str
    exception_message: str
    duration_ms: float = 0.0


class CircuitMetrics(BaseModel):
    """Metrics for a circuit breaker."""
    
    name: str
    state: CircuitState
    
    # Counts
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0  # Calls rejected due to open circuit
    
    # Timing
    avg_duration_ms: float = 0.0
    min_duration_ms: float = 0.0
    max_duration_ms: float = 0.0
    
    # State changes
    state_changes: int = 0
    last_state_change: Optional[datetime] = None
    time_in_state_seconds: float = 0.0
    
    # Failures
    current_failure_count: int = 0
    recent_failures: List[CircuitFailure] = Field(default_factory=list)
    
    # Recovery
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    recovery_attempts: int = 0
    
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.successful_calls + self.failed_calls
        if total == 0:
            return 1.0
        return self.successful_calls / total
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "state": self.state.value,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "rejected_calls": self.rejected_calls,
            "success_rate": self.success_rate(),
            "avg_duration_ms": self.avg_duration_ms,
            "current_failure_count": self.current_failure_count,
        }


class CircuitBreaker:
    """
    Circuit breaker for fault isolation.
    
    Implements the circuit breaker pattern to prevent cascading failures.
    When failures exceed a threshold, the circuit opens and blocks calls,
    allowing downstream services to recover.
    
    States:
    - CLOSED: Normal operation, calls pass through
    - OPEN: Too many failures, calls are rejected
    - HALF_OPEN: Testing if service recovered
    
    Example:
        # Create circuit breaker
        circuit = CircuitBreaker("database", CircuitBreakerConfig(
            failure_threshold=5,
            timeout_seconds=30,
        ))
        
        # Use with async function
        try:
            result = await circuit.call(database.query, "SELECT 1")
        except CircuitOpenError:
            # Circuit is open, use fallback
            result = cache.get("cached_result")
        
        # Or use as decorator
        @circuit.protect
        async def get_data():
            return await database.query("SELECT * FROM data")
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ):
        """Initialize circuit breaker.
        
        Args:
            name: Circuit name
            config: Circuit configuration
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        
        self._last_failure_time: Optional[float] = None
        self._state_change_time = time.time()
        
        self._failures: List[CircuitFailure] = []
        self._durations: List[float] = []
        
        self._metrics = CircuitMetrics(
            name=name,
            state=CircuitState.CLOSED,
        )
        
        self._lock = asyncio.Lock()
        
        self._state_listeners: List[Callable[[CircuitState, CircuitState], Awaitable[None]]] = []
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state
    
    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed."""
        return self._state == CircuitState.CLOSED
    
    @property
    def is_open(self) -> bool:
        """Check if circuit is open."""
        return self._state == CircuitState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open."""
        return self._state == CircuitState.HALF_OPEN
    
    @property
    def metrics(self) -> CircuitMetrics:
        """Get circuit metrics."""
        self._update_metrics()
        return self._metrics
    
    def on_state_change(
        self,
        listener: Callable[[CircuitState, CircuitState], Awaitable[None]],
    ) -> None:
        """Register state change listener.
        
        Args:
            listener: Async function called with (old_state, new_state)
        """
        self._state_listeners.append(listener)
    
    async def call(
        self,
        func: Callable[..., Awaitable[T]],
        *args,
        **kwargs,
    ) -> T:
        """Execute function through circuit breaker.
        
        Args:
            func: Async function to call
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitOpenError: If circuit is open
        """
        async with self._lock:
            # Check if we should transition state
            await self._check_state_transition()
            
            # Check if call is allowed
            if not self._can_execute():
                self._metrics.rejected_calls += 1
                raise CircuitOpenError(
                    self.name,
                    self._time_until_half_open(),
                )
            
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
        
        # Execute call
        start_time = time.time()
        
        try:
            result = await func(*args, **kwargs)
            
            duration_ms = (time.time() - start_time) * 1000
            await self._record_success(duration_ms)
            
            return result
        
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            if self._is_failure_exception(e):
                await self._record_failure(e, duration_ms)
            
            raise
    
    def protect(
        self,
        func: Optional[Callable[..., Awaitable[T]]] = None,
        fallback: Optional[Callable[..., Awaitable[T]]] = None,
    ):
        """Decorator to protect a function with circuit breaker.
        
        Args:
            func: Function to protect
            fallback: Optional fallback function
            
        Returns:
            Decorated function
        
        Example:
            @circuit.protect
            async def call_service():
                return await http_client.get("/api/data")
            
            @circuit.protect(fallback=get_cached_data)
            async def call_service_with_fallback():
                return await http_client.get("/api/data")
        """
        def decorator(f: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
            @functools.wraps(f)
            async def wrapper(*args, **kwargs) -> T:
                try:
                    return await self.call(f, *args, **kwargs)
                except CircuitOpenError:
                    if fallback:
                        return await fallback(*args, **kwargs)
                    raise
            
            return wrapper
        
        if func is not None:
            return decorator(func)
        
        return decorator
    
    async def reset(self) -> None:
        """Manually reset circuit to closed state."""
        async with self._lock:
            old_state = self._state
            
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
            self._last_failure_time = None
            self._state_change_time = time.time()
            
            if old_state != CircuitState.CLOSED:
                await self._notify_state_change(old_state, CircuitState.CLOSED)
        
        logger.info(
            "Circuit breaker reset",
            circuit=self.name,
        )
    
    async def force_open(self) -> None:
        """Manually force circuit to open state."""
        async with self._lock:
            old_state = self._state
            
            self._state = CircuitState.OPEN
            self._last_failure_time = time.time()
            self._state_change_time = time.time()
            
            if old_state != CircuitState.OPEN:
                await self._notify_state_change(old_state, CircuitState.OPEN)
        
        logger.info(
            "Circuit breaker forced open",
            circuit=self.name,
        )
    
    def _can_execute(self) -> bool:
        """Check if a call can be executed."""
        if self._state == CircuitState.CLOSED:
            return True
        
        if self._state == CircuitState.HALF_OPEN:
            return self._half_open_calls < self.config.half_open_max_calls
        
        # OPEN state
        return False
    
    async def _check_state_transition(self) -> None:
        """Check and perform state transitions."""
        if self._state == CircuitState.OPEN:
            # Check if timeout has passed
            if self._time_until_half_open() <= 0:
                old_state = self._state
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                self._success_count = 0
                self._state_change_time = time.time()
                self._metrics.recovery_attempts += 1
                
                await self._notify_state_change(old_state, CircuitState.HALF_OPEN)
                
                logger.info(
                    "Circuit breaker half-open",
                    circuit=self.name,
                )
    
    def _time_until_half_open(self) -> float:
        """Get time until circuit transitions to half-open."""
        if self._last_failure_time is None:
            return 0.0
        
        elapsed = time.time() - self._last_failure_time
        return max(0.0, self.config.timeout_seconds - elapsed)
    
    def _is_failure_exception(self, exc: Exception) -> bool:
        """Check if exception counts as a failure."""
        # Check excluded exceptions first
        if isinstance(exc, self.config.excluded_exceptions):
            return False
        
        # Check included exceptions
        return isinstance(exc, self.config.included_exceptions)
    
    async def _record_success(self, duration_ms: float) -> None:
        """Record a successful call."""
        async with self._lock:
            self._metrics.total_calls += 1
            self._metrics.successful_calls += 1
            self._metrics.last_success = datetime.now(timezone.utc)
            
            self._durations.append(duration_ms)
            if len(self._durations) > 100:
                self._durations = self._durations[-100:]
            
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                
                if self._success_count >= self.config.success_threshold:
                    old_state = self._state
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._state_change_time = time.time()
                    
                    await self._notify_state_change(old_state, CircuitState.CLOSED)
                    
                    logger.info(
                        "Circuit breaker closed (recovered)",
                        circuit=self.name,
                    )
            
            elif self._state == CircuitState.CLOSED and self.config.reset_on_success:
                self._failure_count = 0
    
    async def _record_failure(
        self,
        exc: Exception,
        duration_ms: float,
    ) -> None:
        """Record a failed call."""
        async with self._lock:
            self._metrics.total_calls += 1
            self._metrics.failed_calls += 1
            self._metrics.last_failure = datetime.now(timezone.utc)
            self._metrics.current_failure_count = self._failure_count + 1
            
            self._durations.append(duration_ms)
            if len(self._durations) > 100:
                self._durations = self._durations[-100:]
            
            # Record failure
            failure = CircuitFailure(
                exception_type=type(exc).__name__,
                exception_message=str(exc),
                duration_ms=duration_ms,
            )
            self._failures.append(failure)
            
            # Clean old failures outside window
            cutoff = datetime.now(timezone.utc).timestamp() - self.config.window_size_seconds
            self._failures = [
                f for f in self._failures
                if f.timestamp.timestamp() > cutoff
            ]
            
            self._failure_count = len(self._failures)
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    old_state = self._state
                    self._state = CircuitState.OPEN
                    self._state_change_time = time.time()
                    
                    await self._notify_state_change(old_state, CircuitState.OPEN)
                    
                    logger.warning(
                        "Circuit breaker opened",
                        circuit=self.name,
                        failure_count=self._failure_count,
                    )
            
            elif self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open state reopens circuit
                old_state = self._state
                self._state = CircuitState.OPEN
                self._half_open_calls = 0
                self._state_change_time = time.time()
                
                await self._notify_state_change(old_state, CircuitState.OPEN)
                
                logger.warning(
                    "Circuit breaker reopened from half-open",
                    circuit=self.name,
                )
    
    def _update_metrics(self) -> None:
        """Update metrics with current state."""
        self._metrics.state = self._state
        self._metrics.current_failure_count = self._failure_count
        self._metrics.recent_failures = self._failures[-10:]
        self._metrics.time_in_state_seconds = time.time() - self._state_change_time
        
        if self._durations:
            self._metrics.avg_duration_ms = sum(self._durations) / len(self._durations)
            self._metrics.min_duration_ms = min(self._durations)
            self._metrics.max_duration_ms = max(self._durations)
    
    async def _notify_state_change(
        self,
        old_state: CircuitState,
        new_state: CircuitState,
    ) -> None:
        """Notify listeners of state change."""
        self._metrics.state_changes += 1
        self._metrics.last_state_change = datetime.now(timezone.utc)
        
        for listener in self._state_listeners:
            try:
                await listener(old_state, new_state)
            except Exception as e:
                logger.error(
                    "State change listener error",
                    error=str(e),
                )


class CircuitBreakerRegistry:
    """
    Registry for managing multiple circuit breakers.
    
    Provides centralized management and monitoring of circuit breakers.
    
    Example:
        registry = CircuitBreakerRegistry()
        
        # Get or create circuit breaker
        db_circuit = registry.get_or_create("database")
        api_circuit = registry.get_or_create("external-api", CircuitBreakerConfig(
            failure_threshold=3,
        ))
        
        # Get all metrics
        metrics = registry.get_all_metrics()
        
        # Reset all circuits
        await registry.reset_all()
    """
    
    def __init__(
        self,
        default_config: Optional[CircuitBreakerConfig] = None,
    ):
        """Initialize registry.
        
        Args:
            default_config: Default configuration for new circuits
        """
        self.default_config = default_config or CircuitBreakerConfig()
        self._circuits: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name.
        
        Args:
            name: Circuit name
            
        Returns:
            CircuitBreaker or None
        """
        return self._circuits.get(name)
    
    def get_or_create(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> CircuitBreaker:
        """Get existing or create new circuit breaker.
        
        Args:
            name: Circuit name
            config: Optional configuration (ignored if circuit exists)
            
        Returns:
            CircuitBreaker
        """
        if name not in self._circuits:
            self._circuits[name] = CircuitBreaker(
                name,
                config or self.default_config,
            )
        
        return self._circuits[name]
    
    def create(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> CircuitBreaker:
        """Create new circuit breaker (replaces existing).
        
        Args:
            name: Circuit name
            config: Configuration
            
        Returns:
            CircuitBreaker
        """
        self._circuits[name] = CircuitBreaker(
            name,
            config or self.default_config,
        )
        return self._circuits[name]
    
    def remove(self, name: str) -> bool:
        """Remove circuit breaker.
        
        Args:
            name: Circuit name
            
        Returns:
            True if removed
        """
        if name in self._circuits:
            del self._circuits[name]
            return True
        return False
    
    def list_names(self) -> List[str]:
        """List all circuit names.
        
        Returns:
            List of names
        """
        return list(self._circuits.keys())
    
    def get_all_metrics(self) -> Dict[str, CircuitMetrics]:
        """Get metrics for all circuits.
        
        Returns:
            Dict of name -> metrics
        """
        return {
            name: circuit.metrics
            for name, circuit in self._circuits.items()
        }
    
    def get_open_circuits(self) -> List[str]:
        """Get names of all open circuits.
        
        Returns:
            List of circuit names
        """
        return [
            name for name, circuit in self._circuits.items()
            if circuit.is_open
        ]
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all circuits.
        
        Returns:
            Summary dict
        """
        total = len(self._circuits)
        closed = sum(1 for c in self._circuits.values() if c.is_closed)
        open_ = sum(1 for c in self._circuits.values() if c.is_open)
        half_open = sum(1 for c in self._circuits.values() if c.is_half_open)
        
        return {
            "total": total,
            "closed": closed,
            "open": open_,
            "half_open": half_open,
            "healthy_percentage": (closed / total * 100) if total > 0 else 100.0,
        }
    
    async def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for circuit in self._circuits.values():
            await circuit.reset()
    
    async def reset(self, name: str) -> bool:
        """Reset specific circuit breaker.
        
        Args:
            name: Circuit name
            
        Returns:
            True if reset
        """
        circuit = self._circuits.get(name)
        if circuit:
            await circuit.reset()
            return True
        return False
    
    def protect(
        self,
        circuit_name: str,
        config: Optional[CircuitBreakerConfig] = None,
        fallback: Optional[Callable[..., Awaitable[T]]] = None,
    ):
        """Decorator to protect function with named circuit.
        
        Args:
            circuit_name: Circuit name
            config: Circuit configuration
            fallback: Fallback function
            
        Returns:
            Decorator
        
        Example:
            @registry.protect("database")
            async def query_db():
                return await db.query("SELECT 1")
        """
        circuit = self.get_or_create(circuit_name, config)
        return circuit.protect(fallback=fallback)


# Global registry instance
_default_registry = CircuitBreakerRegistry()


def get_circuit(
    name: str,
    config: Optional[CircuitBreakerConfig] = None,
) -> CircuitBreaker:
    """Get circuit breaker from global registry.
    
    Args:
        name: Circuit name
        config: Optional configuration
        
    Returns:
        CircuitBreaker
    """
    return _default_registry.get_or_create(name, config)


def circuit_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None,
    fallback: Optional[Callable[..., Awaitable[T]]] = None,
):
    """Decorator to protect function with circuit breaker.
    
    Args:
        name: Circuit name
        config: Circuit configuration
        fallback: Fallback function
        
    Returns:
        Decorator
    
    Example:
        @circuit_breaker("api-service")
        async def call_api():
            return await http_client.get("/api/data")
    """
    return _default_registry.protect(name, config, fallback)
