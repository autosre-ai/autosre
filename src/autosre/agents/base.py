"""Base agent interface.

Defines the abstract base class for all investigation agents in the AutoSRE
multi-agent system. Provides common functionality for LLM interaction,
observation collection, state management, and error handling.

Architecture:
    All agents inherit from BaseAgent and implement the execute() method.
    The base class handles:
    - LLM client injection and configuration
    - Observation and finding collection
    - State management and lifecycle hooks
    - Common utilities for evidence gathering
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional, TypeVar, Generic
from uuid import uuid4
import asyncio
import functools
import logging

from pydantic import BaseModel, Field, PrivateAttr

from autosre.models.investigation import (
    AgentState,
    Finding,
    Hypothesis,
    InvestigationStatus,
)
from autosre.models.alert import Alert, AlertSeverity


logger = logging.getLogger(__name__)


# Type variable for generic agent output
T = TypeVar("T", bound=BaseModel)


class AgentCapability(str, Enum):
    """Capabilities that an agent can have."""
    
    TRIAGE = "triage"
    INVESTIGATE = "investigate"
    REMEDIATE = "remediate"
    COORDINATE = "coordinate"
    OBSERVE = "observe"
    ANALYZE = "analyze"


class AgentConfig(BaseModel):
    """Configuration for an agent.
    
    Controls agent behavior, model selection, and operational limits.
    """
    
    name: str = Field(..., description="Agent name")
    enabled: bool = Field(default=True, description="Whether agent is enabled")
    capabilities: list[AgentCapability] = Field(default_factory=list)
    max_iterations: int = Field(default=10, ge=1, le=50)
    timeout_seconds: int = Field(default=300, ge=10, le=3600)
    model: str = Field(default="claude-sonnet-4-20250514")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=100, le=32000)
    system_prompt: str = Field(default="")
    skills: dict[str, bool] = Field(default_factory=dict)


class Observation(BaseModel):
    """An observation collected during agent execution."""
    
    source: str = Field(..., description="Observation source")
    data: Any = Field(..., description="Raw observation data")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionContext(BaseModel):
    """Context provided to agent during execution."""
    
    investigation_id: str = Field(default_factory=lambda: str(uuid4()))
    alert: dict[str, Any] = Field(default_factory=dict)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    previous_findings: list[Finding] = Field(default_factory=list)
    memory_context: dict[str, Any] = Field(default_factory=dict)
    kg_context: dict[str, Any] = Field(default_factory=dict)
    team_config: dict[str, Any] = Field(default_factory=dict)
    iteration: int = Field(default=0)


class ExecutionResult(BaseModel):
    """Result from agent execution."""
    
    state: AgentState = Field(..., description="Final agent state")
    observations: list[Observation] = Field(default_factory=list)
    output: Optional[Any] = Field(default=None)
    next_agents: list[str] = Field(default_factory=list)
    should_continue: bool = Field(default=True)


class LLMClient(ABC):
    """Abstract LLM client interface."""
    
    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[list[Any]] = None,
        structured_output: Optional[type[BaseModel]] = None,
    ) -> Any:
        """Generate a response from the LLM."""
        pass
    
    @abstractmethod
    async def generate_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[Any],
        *,
        max_iterations: int = 10,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Run a ReAct loop with tools."""
        pass


class BaseAgent(ABC):
    """Abstract base class for all investigation agents.
    
    Provides the foundation for building agents that:
    - Execute asynchronously with proper lifecycle management
    - Collect observations and synthesize findings
    - Interact with LLMs for reasoning
    - Handle errors gracefully
    """
    
    _observations: list[Observation] = PrivateAttr(default_factory=list)
    _start_time: Optional[datetime] = PrivateAttr(default=None)
    _llm: Optional[LLMClient] = PrivateAttr(default=None)
    
    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        llm: Optional[LLMClient] = None,
    ):
        self.config = config or AgentConfig(name=self.name)
        self._llm = llm
        self._observations = []
        self._start_time = None
        self._tools: list[Any] = []
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique agent name."""
        pass
    
    @property
    def description(self) -> str:
        """Return a human-readable agent description."""
        return f"{self.name} agent"
    
    @property
    def llm(self) -> Optional[LLMClient]:
        return self._llm
    
    @llm.setter
    def llm(self, client: LLMClient) -> None:
        self._llm = client
    
    @abstractmethod
    async def execute(self, context: ExecutionContext) -> ExecutionResult:
        """Execute the agent's task."""
        pass
    
    async def run(self, context: ExecutionContext) -> ExecutionResult:
        """Run the agent with lifecycle management."""
        self._start_time = datetime.utcnow()
        self._observations = []
        
        logger.info(f"[{self.name}] Starting execution for {context.investigation_id}")
        
        try:
            result = await asyncio.wait_for(
                self.execute(context),
                timeout=self.config.timeout_seconds,
            )
            
            if not result.observations:
                result.observations = self._observations
            
            logger.info(f"[{self.name}] Completed with {len(result.state.findings)} findings")
            return result
            
        except asyncio.TimeoutError:
            logger.error(f"[{self.name}] Timed out after {self.config.timeout_seconds}s")
            return ExecutionResult(
                state=self._create_failed_state(f"Timed out after {self.config.timeout_seconds}s"),
                observations=self._observations,
            )
        except Exception as e:
            logger.exception(f"[{self.name}] Execution failed: {e}")
            return ExecutionResult(
                state=self._create_failed_state(str(e)),
                observations=self._observations,
            )
    
    def add_observation(self, source: str, data: Any, *, confidence: float = 1.0, **metadata: Any) -> Observation:
        """Record an observation during execution."""
        observation = Observation(source=source, data=data, confidence=confidence, metadata=metadata)
        self._observations.append(observation)
        return observation
    
    def create_finding(self, detail: str, evidence: Optional[str] = None, severity: str = "info", confidence: float = 0.7, **metadata: Any) -> Finding:
        """Create a finding from this agent."""
        return Finding(category=self.name, detail=detail, evidence=evidence, severity=severity, confidence=confidence, metadata=metadata)
    
    def _create_completed_state(self, findings: list[Finding], summary: Optional[str] = None) -> AgentState:
        return AgentState(name=self.name, status=InvestigationStatus.COMPLETED, started_at=self._start_time or datetime.utcnow(), completed_at=datetime.utcnow(), findings=findings, summary=summary)
    
    def _create_failed_state(self, error: str) -> AgentState:
        return AgentState(name=self.name, status=InvestigationStatus.FAILED, started_at=self._start_time or datetime.utcnow(), completed_at=datetime.utcnow(), error=error)
    
    async def validate_context(self, context: ExecutionContext) -> bool:
        if not context.alert:
            logger.warning(f"[{self.name}] No alert in context")
            return False
        return True
    
    def format_alert_summary(self, alert: dict[str, Any]) -> str:
        name = alert.get("name", "Unknown")
        service = alert.get("service", "unknown")
        severity = alert.get("severity", "unknown")
        description = alert.get("description", alert.get("summary", ""))
        lines = [f"Alert: {name}", f"Service: {service}", f"Severity: {severity}"]
        if description:
            lines.append(f"Description: {description}")
        return "\n".join(lines)
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name!r})>"


def agent_timeout(seconds: int):
    """Decorator to add timeout to agent methods."""
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
        return wrapper
    return decorator


def retry_on_error(max_retries: int = 3, delay: float = 1.0, exceptions: tuple = (Exception,)):
    """Decorator to retry agent methods on error."""
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        await asyncio.sleep(delay * (attempt + 1))
            raise last_error
        return wrapper
    return decorator
