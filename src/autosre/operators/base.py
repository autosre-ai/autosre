"""
Base classes for Kubernetes operators.

Provides common functionality for all operators including:
- Configuration management
- Execution tracking
- Health checks
- Metrics collection
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Generic, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class OperatorStatus(str, Enum):
    """Status of an operator operation."""
    
    PENDING = "pending"
    VALIDATING = "validating"
    EXECUTING = "executing"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class OperatorConfig(BaseModel):
    """Base configuration for operators."""
    
    # Timeouts
    operation_timeout_seconds: int = Field(300, description="Timeout for operations")
    health_check_timeout_seconds: int = Field(60, description="Timeout for health checks")
    
    # Retries
    max_retries: int = Field(3, description="Maximum retry attempts")
    retry_delay_seconds: float = Field(5.0, description="Delay between retries")
    
    # Safety
    dry_run: bool = Field(False, description="Dry run mode")
    require_confirmation: bool = Field(False, description="Require confirmation")
    
    # Monitoring
    enable_metrics: bool = Field(True, description="Enable metrics collection")
    
    # Cluster
    cluster_name: str = Field("default", description="Kubernetes cluster name")


class OperatorResult(BaseModel):
    """Result of an operator operation."""
    
    id: UUID = Field(default_factory=uuid4)
    operation: str = Field(..., description="Operation name")
    
    # Target
    resource_type: str
    resource_name: str
    namespace: str | None = None
    
    # Status
    status: OperatorStatus = OperatorStatus.PENDING
    success: bool = False
    message: str = ""
    
    # Details
    result_data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    error_type: str | None = None
    
    # Changes made
    changes: list[dict[str, Any]] = Field(default_factory=list)
    
    # Timing
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    
    # Metrics
    retries: int = 0
    
    @property
    def duration_seconds(self) -> float | None:
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    def add_change(
        self,
        field: str,
        old_value: Any,
        new_value: Any,
        description: str = "",
    ) -> None:
        """Record a change made by the operation."""
        self.changes.append({
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
            "description": description,
            "timestamp": datetime.utcnow().isoformat(),
        })
    
    def complete(
        self,
        success: bool,
        message: str = "",
        result_data: dict[str, Any] | None = None,
    ) -> None:
        """Mark operation as complete."""
        self.success = success
        self.status = OperatorStatus.COMPLETED if success else OperatorStatus.FAILED
        self.message = message
        if result_data:
            self.result_data.update(result_data)
        self.completed_at = datetime.utcnow()
    
    def fail(self, error: str, error_type: str = "OperatorError") -> None:
        """Mark operation as failed."""
        self.success = False
        self.status = OperatorStatus.FAILED
        self.error = error
        self.error_type = error_type
        self.completed_at = datetime.utcnow()
    
    def to_summary(self) -> str:
        """Generate summary string."""
        status_icon = "✅" if self.success else "❌"
        lines = [
            f"{status_icon} {self.operation} - {self.status.value}",
            f"  Target: {self.resource_type}/{self.namespace}/{self.resource_name}",
        ]
        if self.message:
            lines.append(f"  Message: {self.message}")
        if self.error:
            lines.append(f"  Error: {self.error}")
        if self.duration_seconds:
            lines.append(f"  Duration: {self.duration_seconds:.1f}s")
        if self.changes:
            lines.append(f"  Changes: {len(self.changes)}")
        return "\n".join(lines)


T = TypeVar('T', bound=OperatorResult)


class BaseOperator(ABC, Generic[T]):
    """
    Abstract base class for Kubernetes operators.
    
    Provides common functionality:
    - Configuration management
    - Logging
    - Metrics tracking
    - Error handling
    """
    
    def __init__(
        self,
        k8s_client: Any,
        config: OperatorConfig | None = None,
    ):
        """
        Initialize operator.
        
        Args:
            k8s_client: Kubernetes client instance
            config: Operator configuration
        """
        self._k8s = k8s_client
        self._config = config or OperatorConfig()
        
        # Metrics
        self._operations_total = 0
        self._operations_success = 0
        self._operations_failed = 0
        self._total_duration_seconds = 0.0
        
        # History
        self._history: list[T] = []
        self._max_history = 100
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return operator name."""
        ...
    
    @property
    def config(self) -> OperatorConfig:
        return self._config
    
    def set_config(self, config: OperatorConfig) -> None:
        """Update configuration."""
        self._config = config
        logger.info(f"Updated {self.name} config")
    
    def _create_result(
        self,
        operation: str,
        resource_type: str,
        resource_name: str,
        namespace: str | None = None,
    ) -> OperatorResult:
        """Create a new operation result."""
        return OperatorResult(
            operation=operation,
            resource_type=resource_type,
            resource_name=resource_name,
            namespace=namespace,
        )
    
    def _record_operation(self, result: T) -> None:
        """Record operation metrics."""
        self._operations_total += 1
        
        if result.success:
            self._operations_success += 1
        else:
            self._operations_failed += 1
        
        if result.duration_seconds:
            self._total_duration_seconds += result.duration_seconds
        
        # Add to history
        self._history.append(result)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
    
    async def _with_retry(
        self,
        operation: callable,
        result: OperatorResult,
        *args,
        **kwargs,
    ) -> Any:
        """Execute operation with retry logic."""
        last_error = None
        
        for attempt in range(self._config.max_retries + 1):
            try:
                return await operation(*args, **kwargs)
            except Exception as e:
                last_error = e
                result.retries = attempt + 1
                
                if attempt < self._config.max_retries:
                    logger.warning(
                        f"{self.name} retry {attempt + 1}/{self._config.max_retries}: {e}"
                    )
                    import asyncio
                    await asyncio.sleep(self._config.retry_delay_seconds)
                else:
                    logger.error(f"{self.name} failed after {attempt + 1} attempts: {e}")
        
        raise last_error
    
    def get_metrics(self) -> dict[str, Any]:
        """Get operator metrics."""
        return {
            "operator": self.name,
            "operations_total": self._operations_total,
            "operations_success": self._operations_success,
            "operations_failed": self._operations_failed,
            "success_rate": (
                self._operations_success / self._operations_total
                if self._operations_total > 0 else 0
            ),
            "average_duration_seconds": (
                self._total_duration_seconds / self._operations_total
                if self._operations_total > 0 else 0
            ),
            "config": self._config.model_dump(),
        }
    
    def get_history(
        self,
        limit: int = 10,
        success_only: bool = False,
        failed_only: bool = False,
    ) -> list[T]:
        """Get operation history."""
        history = self._history
        
        if success_only:
            history = [r for r in history if r.success]
        elif failed_only:
            history = [r for r in history if not r.success]
        
        return history[-limit:]
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if operator can perform operations."""
        ...
