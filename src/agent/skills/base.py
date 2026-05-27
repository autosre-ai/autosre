"""Base classes and decorators for SRE tools."""

import asyncio
import functools
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, TypeVar, ParamSpec

from langchain_core.tools import BaseTool, tool

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class ToolResult:
    """Structured result from an SRE tool execution."""
    
    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "metadata": self.metadata,
        }
    
    def __str__(self) -> str:
        """Human-readable string representation."""
        if self.success:
            if isinstance(self.data, (list, dict)):
                import json
                return json.dumps(self.data, indent=2, default=str)
            return str(self.data)
        return f"Error: {self.error}"


class SREToolError(Exception):
    """Base exception for SRE tool errors."""
    
    def __init__(self, message: str, recoverable: bool = True):
        super().__init__(message)
        self.message = message
        self.recoverable = recoverable


class TimeoutError(SREToolError):
    """Tool execution timed out."""
    
    def __init__(self, timeout_seconds: float):
        super().__init__(f"Operation timed out after {timeout_seconds}s", recoverable=True)
        self.timeout_seconds = timeout_seconds


class ConnectionError(SREToolError):
    """Failed to connect to external service."""
    
    def __init__(self, service: str, details: str = ""):
        message = f"Failed to connect to {service}"
        if details:
            message += f": {details}"
        super().__init__(message, recoverable=True)
        self.service = service


class AuthenticationError(SREToolError):
    """Authentication failed for external service."""
    
    def __init__(self, service: str):
        super().__init__(f"Authentication failed for {service}", recoverable=False)
        self.service = service


class BaseSRETool(ABC):
    """Abstract base class for all SRE tools.
    
    Provides common functionality like timeout handling, error wrapping,
    and structured result formatting.
    """
    
    name: str = "base_sre_tool"
    description: str = "Base SRE tool"
    default_timeout: float = 30.0
    
    def __init__(self, mock_mode: bool = False):
        """Initialize the tool.
        
        Args:
            mock_mode: If True, return mock data instead of real API calls.
        """
        self.mock_mode = mock_mode
        self._mock_responses: dict[str, Any] = {}
    
    def set_mock_response(self, method_name: str, response: Any) -> None:
        """Set a mock response for a specific method.
        
        Args:
            method_name: Name of the method to mock.
            response: Response to return when method is called.
        """
        self._mock_responses[method_name] = response
    
    def get_mock_response(self, method_name: str, default: Any = None) -> Any:
        """Get a mock response for a method.
        
        Args:
            method_name: Name of the method.
            default: Default value if no mock is set.
            
        Returns:
            Mock response or default.
        """
        return self._mock_responses.get(method_name, default)
    
    @abstractmethod
    def get_tools(self) -> list[BaseTool]:
        """Return list of LangChain tools this class provides.
        
        Each tool should be decorated with @tool or use StructuredTool.
        """
        pass
    
    def _wrap_result(
        self,
        data: Any = None,
        error: Optional[str] = None,
        start_time: Optional[float] = None,
        metadata: Optional[dict] = None,
    ) -> ToolResult:
        """Wrap execution result in ToolResult.
        
        Args:
            data: Successful result data.
            error: Error message if failed.
            start_time: Start timestamp for timing.
            metadata: Additional metadata.
            
        Returns:
            Structured ToolResult.
        """
        execution_time_ms = 0.0
        if start_time:
            execution_time_ms = (time.time() - start_time) * 1000
        
        return ToolResult(
            success=error is None,
            data=data,
            error=error,
            execution_time_ms=execution_time_ms,
            metadata=metadata or {},
        )


def sre_tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    timeout: float = 30.0,
    retries: int = 0,
    retry_delay: float = 1.0,
):
    """Decorator to create an SRE tool with common functionality.
    
    Wraps a function to add:
    - Timeout handling
    - Automatic retries
    - Structured error handling
    - Execution timing
    - LangChain tool compatibility
    
    Args:
        name: Tool name (defaults to function name).
        description: Tool description (defaults to function docstring).
        timeout: Maximum execution time in seconds.
        retries: Number of retry attempts on failure.
        retry_delay: Delay between retries in seconds.
        
    Returns:
        Decorated function as a LangChain tool.
        
    Example:
        @sre_tool(name="list_pods", timeout=30)
        def list_pods(namespace: str = "default") -> ToolResult:
            '''List pods in a Kubernetes namespace.'''
            ...
    """
    def decorator(func: Callable[P, R]) -> Callable[P, str]:
        tool_name = name or func.__name__
        tool_description = description or func.__doc__ or f"SRE tool: {tool_name}"
        
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> str:
            start_time = time.time()
            last_error: Optional[Exception] = None
            
            for attempt in range(retries + 1):
                try:
                    # Handle async functions
                    if asyncio.iscoroutinefunction(func):
                        try:
                            loop = asyncio.get_event_loop()
                        except RuntimeError:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                        
                        result = loop.run_until_complete(
                            asyncio.wait_for(
                                func(*args, **kwargs),
                                timeout=timeout
                            )
                        )
                    else:
                        # For sync functions, we can't easily add timeout
                        # without threading, so we just call directly
                        result = func(*args, **kwargs)
                    
                    # If result is already a ToolResult, return its string form
                    if isinstance(result, ToolResult):
                        return str(result)
                    
                    # Otherwise wrap it
                    wrapped = ToolResult(
                        success=True,
                        data=result,
                        execution_time_ms=(time.time() - start_time) * 1000,
                    )
                    return str(wrapped)
                    
                except asyncio.TimeoutError:
                    last_error = TimeoutError(timeout)
                    logger.warning(f"Tool {tool_name} timed out (attempt {attempt + 1})")
                    
                except SREToolError as e:
                    last_error = e
                    if not e.recoverable:
                        break
                    logger.warning(f"Tool {tool_name} failed (attempt {attempt + 1}): {e}")
                    
                except Exception as e:
                    last_error = e
                    logger.error(f"Tool {tool_name} unexpected error (attempt {attempt + 1}): {e}")
                
                # Retry delay
                if attempt < retries:
                    time.sleep(retry_delay)
            
            # All attempts failed
            error_result = ToolResult(
                success=False,
                error=str(last_error),
                execution_time_ms=(time.time() - start_time) * 1000,
            )
            return str(error_result)
        
        # Apply LangChain tool decorator
        return tool(name=tool_name, description=tool_description)(wrapper)
    
    return decorator


def with_timeout(timeout_seconds: float):
    """Decorator to add timeout to a synchronous function using threading.
    
    Args:
        timeout_seconds: Maximum execution time.
        
    Returns:
        Decorated function.
    """
    import concurrent.futures
    
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func, *args, **kwargs)
                try:
                    return future.result(timeout=timeout_seconds)
                except concurrent.futures.TimeoutError:
                    raise TimeoutError(timeout_seconds)
        return wrapper
    return decorator
