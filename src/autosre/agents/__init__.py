"""Multi-agent system for AutoSRE V2.

This module provides the agent orchestration system for automated
incident investigation and remediation.

Core Components:
- AgentCoordinator: Orchestrates the multi-agent workflow
- TriageAgent: Initial alert assessment and routing
- InvestigationAgent: Domain-specific investigation
- RemediationAgent: Action planning and recommendations

State Management:
- InvestigationStateMachine: State machine for investigation lifecycle
- EventEmitter: Real-time event emission for UI updates
- StatePersister: State persistence for recovery

Example:
    >>> from autosre.agents import create_coordinator
    >>> 
    >>> coordinator = create_coordinator(llm_client)
    >>> 
    >>> # Subscribe to events
    >>> async def on_event(event):
    ...     print(f"{event.type}: {event.data}")
    >>> coordinator.events.on_all(on_event)
    >>> 
    >>> # Run investigation
    >>> result = await coordinator.start_investigation(alert)
"""

# Base agent
from autosre.agents.base import (
    BaseAgent,
    AgentCapability,
    AgentConfig,
    ExecutionContext,
    ExecutionResult,
    Observation,
    LLMClient,
)

# Alternative base (for compatibility)
from autosre.agents.base_agent import (
    BaseAgent as BaseAgentV1,
    AgentResult,
)

# Specialized agents
from autosre.agents.triage import TriageAgent, TriageResult
from autosre.agents.investigator import (
    InvestigationAgent,
    InvestigationOutput,
    KubernetesInvestigator,
    MetricsInvestigator,
    LogsInvestigator,
    TracesInvestigator,
)
from autosre.agents.remediation import (
    RemediationAgent,
    RemediationOutput,
    RemediationAction,
    RiskLevel,
    ActionCategory,
)

# Coordinator
from autosre.agents.coordinator import (
    AgentCoordinator,
    CoordinatorConfig,
    CoordinatorState,
    InvestigationStatus,
    Timeline,
    TimelineEntry,
    create_coordinator,
)

# State management
from autosre.agents.state import (
    # State machine
    InvestigationState,
    InvestigationStateMachine,
    StateTransition,
    TransitionError,
    
    # Events
    EventType,
    Event,
    EventEmitter,
    
    # Retry handling
    RetryConfig,
    RetryManager,
    RetryState,
    
    # Timeout handling
    TimeoutConfig,
    TimeoutManager,
    
    # Persistence
    StatePersister,
    FileStatePersister,
    SQLiteStatePersister,
    InMemoryStatePersister,
    create_persister,
    
    # Context
    InvestigationContext,
)

__all__ = [
    # Base
    "BaseAgent",
    "BaseAgentV1",
    "AgentCapability",
    "AgentConfig",
    "AgentResult",
    "ExecutionContext",
    "ExecutionResult",
    "Observation",
    "LLMClient",
    
    # Specialized agents
    "TriageAgent",
    "TriageResult",
    "InvestigationAgent",
    "InvestigationOutput",
    "KubernetesInvestigator",
    "MetricsInvestigator",
    "LogsInvestigator",
    "TracesInvestigator",
    "RemediationAgent",
    "RemediationOutput",
    "RemediationAction",
    "RiskLevel",
    "ActionCategory",
    
    # Coordinator
    "AgentCoordinator",
    "CoordinatorConfig",
    "CoordinatorState",
    "InvestigationStatus",
    "Timeline",
    "TimelineEntry",
    "create_coordinator",
    
    # State machine
    "InvestigationState",
    "InvestigationStateMachine",
    "StateTransition",
    "TransitionError",
    
    # Events
    "EventType",
    "Event",
    "EventEmitter",
    
    # Retry
    "RetryConfig",
    "RetryManager",
    "RetryState",
    
    # Timeout
    "TimeoutConfig",
    "TimeoutManager",
    
    # Persistence
    "StatePersister",
    "FileStatePersister",
    "SQLiteStatePersister",
    "InMemoryStatePersister",
    "create_persister",
    
    # Context
    "InvestigationContext",
]
