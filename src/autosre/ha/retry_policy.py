"""Retry Policy for AutoSRE V2 High Availability.

Provides configurable retry strategies:
- Exponential backoff
- Linear backoff
- Constant backoff
- Decorrelated jitter
- Custom retry logic
"""

from __future__ import annotations

import asyncio
import functools
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, Tuple, TypeVar, Awaitable, Union

from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class RetryStrategy(str, Enum):
    """Retry backoff strategies."""
    
    CONSTANT = "constant"  # Same delay each time
    LINEAR = "linear"  # Linearly increasing delay
    EXPONENTIAL = "exponential"  # Exponentially increasing delay
    DECORRELATED_JITTER = "decorrelated_jitter"  # AWS-style jitter


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    
    # Retry limits
    max_retries: int = 3
    max_time_seconds: Optional[float] = None  # Total time budget
    
    # Backoff
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    exponential_base: float = 2.0
    
    # Jitter
    jitter: bool = True
    jitter_factor: float = 0.5  # Max jitter as fraction of delay
    
    # Exceptions
    retry_exceptions: Tuple[type, ...] = (Exception,)
    fatal_exceptions: Tuple[type, ...] = ()
    
    # Callbacks
    on_retry: Optional[Callable[[int, Exception, float], None]] = None
    
    def __post_init__(self):
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if self.base_delay_seconds < 0:
            raise ValueError("base_delay_seconds must be >= 0")


class RetryResult(BaseModel, Generic[T]):
    """Result of a retry operation."""
    
    success: bool
    value: Optional[Any] = None  # Will be T at runtime
    
    # Retry info
    attempts: int = 1
    total_time_seconds: float = 0.0
    
    # Errors
    last_exception: Optional[str] = None
    exceptions: List[str] = Field(default_factory=list)
    
    # Timing
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    delays: List[float] = Field(default_factory=list)


class BackoffStrategy(ABC):
    """Abstract backoff strategy."""
    
    @abstractmethod
    def get_delay(
        self,
        attempt: int,
        base_delay: float,
        max_delay: float,
    ) -> float:
        """Calculate delay for an attempt.
        
        Args:
            attempt: Current attempt (1-indexed)
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            
        Returns:
            Delay in seconds
        """
        ...


class ConstantBackoff(BackoffStrategy):
    """Constant delay between retries."""
    
    def get_delay(
        self,
        attempt: int,
        base_delay: float,
        max_delay: float,
    ) -> float:
        return min(base_delay, max_delay)


class LinearBackoff(BackoffStrategy):
    """Linearly increasing delay between retries."""
    
    def __init__(self, increment: float = 1.0):
        """Initialize LinearBackoff.
        
        Args:
            increment: Amount to increase delay each attempt
        """
        self.increment = increment
    
    def get_delay(
        self,
        attempt: int,
        base_delay: float,
        max_delay: float,
    ) -> float:
        delay = base_delay + (attempt - 1) * self.increment
        return min(delay, max_delay)


class ExponentialBackoff(BackoffStrategy):
    """Exponentially increasing delay between retries."""
    
    def __init__(self, exponential_base: float = 2.0):
        """Initialize ExponentialBackoff.
        
        Args:
            exponential_base: Base for exponential calculation
        """
        self.exponential_base = exponential_base
    
    def get_delay(
        self,
        attempt: int,
        base_delay: float,
        max_delay: float,
    ) -> float:
        delay = base_delay * (self.exponential_base ** (attempt - 1))
        return min(delay, max_delay)


class DecorrelatedJitter(BackoffStrategy):
    """AWS-style decorrelated jitter strategy.
    
    Uses sleep = min(max_delay, random(base_delay, sleep * 3))
    This provides good spread while avoiding thundering herd.
    """
    
    def __init__(self):
        self._last_delay = 0.0
    
    def get_delay(
        self,
        attempt: int,
        base_delay: float,
        max_delay: float,
    ) -> float:
        if attempt == 1:
            self._last_delay = base_delay
        else:
            self._last_delay = random.uniform(base_delay, self._last_delay * 3)
        
        return min(self._last_delay, max_delay)


def _get_backoff_strategy(config: RetryConfig) -> BackoffStrategy:
    """Get backoff strategy from config."""
    if config.strategy == RetryStrategy.CONSTANT:
        return ConstantBackoff()
    elif config.strategy == RetryStrategy.LINEAR:
        return LinearBackoff()
    elif config.strategy == RetryStrategy.EXPONENTIAL:
        return ExponentialBackoff(config.exponential_base)
    elif config.strategy == RetryStrategy.DECORRELATED_JITTER:
        return DecorrelatedJitter()
    else:
        raise ValueError(f"Unknown strategy: {config.strategy}")


def _add_jitter(delay: float, jitter_factor: float) -> float:
    """Add jitter to delay."""
    if jitter_factor <= 0:
        return delay
    
    jitter = delay * jitter_factor
    return delay + random.uniform(-jitter, jitter)


class RetryPolicy:
    """
    Configurable retry policy with multiple strategies.
    
    Provides flexible retry behavior with:
    - Multiple backoff strategies
    - Configurable jitter
    - Exception filtering
    - Time budgets
    - Callbacks
    
    Example:
        # Basic usage
        policy = RetryPolicy(RetryConfig(max_retries=3))
        
        result = await policy.execute(
            async lambda: await http_client.get("/api/data")
        )
        
        if result.success:
            print(result.value)
        else:
            print(f"Failed after {result.attempts} attempts")
        
        # With decorator
        @policy.wrap
        async def get_data():
            return await http_client.get("/api/data")
    """
    
    def __init__(
        self,
        config: Optional[RetryConfig] = None,
    ):
        """Initialize RetryPolicy.
        
        Args:
            config: Retry configuration
        """
        self.config = config or RetryConfig()
        self._backoff = _get_backoff_strategy(self.config)
    
    async def execute(
        self,
        func: Callable[..., Awaitable[T]],
        *args,
        **kwargs,
    ) -> RetryResult[T]:
        """Execute function with retry policy.
        
        Args:
            func: Async function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            RetryResult
        """
        start_time = time.time()
        started_at = datetime.now(timezone.utc)
        
        attempt = 0
        exceptions: List[str] = []
        delays: List[float] = []
        last_exception: Optional[Exception] = None
        
        while True:
            attempt += 1
            
            try:
                result = await func(*args, **kwargs)
                
                return RetryResult(
                    success=True,
                    value=result,
                    attempts=attempt,
                    total_time_seconds=time.time() - start_time,
                    started_at=started_at,
                    finished_at=datetime.now(timezone.utc),
                    delays=delays,
                    exceptions=exceptions,
                )
            
            except Exception as e:
                last_exception = e
                exceptions.append(f"{type(e).__name__}: {str(e)}")
                
                # Check for fatal exceptions
                if isinstance(e, self.config.fatal_exceptions):
                    logger.warning(
                        "Retry aborted: fatal exception",
                        exception=type(e).__name__,
                    )
                    break
                
                # Check if exception is retryable
                if not isinstance(e, self.config.retry_exceptions):
                    logger.warning(
                        "Retry aborted: non-retryable exception",
                        exception=type(e).__name__,
                    )
                    break
                
                # Check retry limit
                if attempt >= self.config.max_retries + 1:
                    logger.warning(
                        "Retry limit reached",
                        attempts=attempt,
                        max_retries=self.config.max_retries,
                    )
                    break
                
                # Check time budget
                elapsed = time.time() - start_time
                if self.config.max_time_seconds and elapsed >= self.config.max_time_seconds:
                    logger.warning(
                        "Retry time budget exceeded",
                        elapsed_seconds=elapsed,
                        max_seconds=self.config.max_time_seconds,
                    )
                    break
                
                # Calculate delay
                delay = self._backoff.get_delay(
                    attempt,
                    self.config.base_delay_seconds,
                    self.config.max_delay_seconds,
                )
                
                if self.config.jitter:
                    delay = _add_jitter(delay, self.config.jitter_factor)
                
                delays.append(delay)
                
                # Call retry callback
                if self.config.on_retry:
                    try:
                        self.config.on_retry(attempt, e, delay)
                    except Exception:
                        pass
                
                logger.info(
                    "Retrying",
                    attempt=attempt,
                    delay_seconds=delay,
                    exception=type(e).__name__,
                )
                
                await asyncio.sleep(delay)
        
        return RetryResult(
            success=False,
            attempts=attempt,
            total_time_seconds=time.time() - start_time,
            last_exception=str(last_exception) if last_exception else None,
            exceptions=exceptions,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            delays=delays,
        )
    
    def wrap(
        self,
        func: Optional[Callable[..., Awaitable[T]]] = None,
    ):
        """Decorator to wrap function with retry policy.
        
        Args:
            func: Function to wrap
            
        Returns:
            Decorated function
        
        Example:
            policy = RetryPolicy()
            
            @policy.wrap
            async def get_data():
                return await http_client.get("/api/data")
        """
        def decorator(f: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
            @functools.wraps(f)
            async def wrapper(*args, **kwargs) -> T:
                result = await self.execute(f, *args, **kwargs)
                
                if result.success:
                    return result.value
                
                # Re-raise the last exception
                raise RuntimeError(
                    f"Retry failed after {result.attempts} attempts: {result.last_exception}"
                )
            
            return wrapper
        
        if func is not None:
            return decorator(func)
        
        return decorator
    
    def wrap_with_result(
        self,
        func: Optional[Callable[..., Awaitable[T]]] = None,
    ):
        """Decorator that returns RetryResult instead of value.
        
        Args:
            func: Function to wrap
            
        Returns:
            Decorated function returning RetryResult
        """
        def decorator(f: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[RetryResult[T]]]:
            @functools.wraps(f)
            async def wrapper(*args, **kwargs) -> RetryResult[T]:
                return await self.execute(f, *args, **kwargs)
            
            return wrapper
        
        if func is not None:
            return decorator(func)
        
        return decorator


# Convenience decorators

def retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
    jitter: bool = True,
    retry_exceptions: Tuple[type, ...] = (Exception,),
    fatal_exceptions: Tuple[type, ...] = (),
):
    """Decorator for retrying async functions.
    
    Args:
        max_retries: Maximum retry attempts
        base_delay: Base delay between retries
        max_delay: Maximum delay between retries
        strategy: Backoff strategy
        jitter: Whether to add jitter
        retry_exceptions: Exceptions to retry on
        fatal_exceptions: Exceptions that stop retrying
        
    Returns:
        Decorator
    
    Example:
        @retry(max_retries=3, base_delay=1.0)
        async def fetch_data():
            return await http_client.get("/api/data")
    """
    config = RetryConfig(
        max_retries=max_retries,
        base_delay_seconds=base_delay,
        max_delay_seconds=max_delay,
        strategy=strategy,
        jitter=jitter,
        retry_exceptions=retry_exceptions,
        fatal_exceptions=fatal_exceptions,
    )
    policy = RetryPolicy(config)
    return policy.wrap


def async_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
    jitter: bool = True,
    retry_exceptions: Tuple[type, ...] = (Exception,),
    fatal_exceptions: Tuple[type, ...] = (),
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
):
    """Decorator for retrying async functions with more options.
    
    Args:
        max_retries: Maximum retry attempts
        base_delay: Base delay between retries
        max_delay: Maximum delay between retries
        strategy: Backoff strategy
        jitter: Whether to add jitter
        retry_exceptions: Exceptions to retry on
        fatal_exceptions: Exceptions that stop retrying
        on_retry: Callback called before each retry
        
    Returns:
        Decorator
    
    Example:
        @async_retry(
            max_retries=5,
            strategy=RetryStrategy.DECORRELATED_JITTER,
            on_retry=lambda n, e, d: print(f"Retry {n}: {e}"),
        )
        async def fetch_data():
            return await http_client.get("/api/data")
    """
    config = RetryConfig(
        max_retries=max_retries,
        base_delay_seconds=base_delay,
        max_delay_seconds=max_delay,
        strategy=strategy,
        jitter=jitter,
        retry_exceptions=retry_exceptions,
        fatal_exceptions=fatal_exceptions,
        on_retry=on_retry,
    )
    policy = RetryPolicy(config)
    return policy.wrap


# Utility functions

async def retry_call(
    func: Callable[..., Awaitable[T]],
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    **kwargs,
) -> T:
    """Retry an async function call.
    
    Args:
        func: Async function to call
        *args: Positional arguments
        max_retries: Maximum retries
        base_delay: Base delay
        **kwargs: Keyword arguments
        
    Returns:
        Function result
        
    Raises:
        RuntimeError: If all retries fail
    """
    policy = RetryPolicy(RetryConfig(
        max_retries=max_retries,
        base_delay_seconds=base_delay,
    ))
    
    result = await policy.execute(func, *args, **kwargs)
    
    if result.success:
        return result.value
    
    raise RuntimeError(
        f"Retry failed after {result.attempts} attempts: {result.last_exception}"
    )


class RetryContext:
    """Context manager for retry logic with more control.
    
    Example:
        async with RetryContext(max_retries=3) as ctx:
            while ctx.should_retry():
                try:
                    result = await risky_operation()
                    ctx.success(result)
                    break
                except Exception as e:
                    await ctx.handle_error(e)
    """
    
    def __init__(
        self,
        config: Optional[RetryConfig] = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ):
        """Initialize RetryContext.
        
        Args:
            config: Full retry config
            max_retries: Max retries (if config not provided)
            base_delay: Base delay (if config not provided)
        """
        self.config = config or RetryConfig(
            max_retries=max_retries,
            base_delay_seconds=base_delay,
        )
        self._backoff = _get_backoff_strategy(self.config)
        
        self._attempt = 0
        self._result: Optional[RetryResult] = None
        self._start_time: Optional[float] = None
        self._exceptions: List[str] = []
        self._delays: List[float] = []
        self._succeeded = False
    
    async def __aenter__(self) -> "RetryContext":
        self._start_time = time.time()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    def should_retry(self) -> bool:
        """Check if should attempt (another) retry.
        
        Returns:
            True if should retry
        """
        if self._succeeded:
            return False
        
        if self._attempt >= self.config.max_retries + 1:
            return False
        
        if self.config.max_time_seconds and self._start_time:
            elapsed = time.time() - self._start_time
            if elapsed >= self.config.max_time_seconds:
                return False
        
        return True
    
    async def handle_error(self, exc: Exception) -> None:
        """Handle an error and prepare for retry.
        
        Args:
            exc: Exception that occurred
        """
        self._attempt += 1
        self._exceptions.append(f"{type(exc).__name__}: {str(exc)}")
        
        if not self.should_retry():
            return
        
        # Calculate delay
        delay = self._backoff.get_delay(
            self._attempt,
            self.config.base_delay_seconds,
            self.config.max_delay_seconds,
        )
        
        if self.config.jitter:
            delay = _add_jitter(delay, self.config.jitter_factor)
        
        self._delays.append(delay)
        
        await asyncio.sleep(delay)
    
    def success(self, value: T) -> None:
        """Mark operation as successful.
        
        Args:
            value: Result value
        """
        self._succeeded = True
        self._result = RetryResult(
            success=True,
            value=value,
            attempts=self._attempt + 1,
            total_time_seconds=time.time() - (self._start_time or time.time()),
            exceptions=self._exceptions,
            delays=self._delays,
        )
    
    @property
    def attempt(self) -> int:
        """Get current attempt number (1-indexed)."""
        return self._attempt + 1
    
    @property
    def result(self) -> Optional[RetryResult]:
        """Get result if successful."""
        return self._result
    
    def get_result(self) -> RetryResult:
        """Get result (success or failure).
        
        Returns:
            RetryResult
        """
        if self._result:
            return self._result
        
        return RetryResult(
            success=False,
            attempts=self._attempt,
            total_time_seconds=time.time() - (self._start_time or time.time()),
            last_exception=self._exceptions[-1] if self._exceptions else None,
            exceptions=self._exceptions,
            delays=self._delays,
        )
