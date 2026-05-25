"""
AutoSRE - Open-source AI SRE Agent

Built foundation-first: context store, evals, sandbox, then agent logic.

v2 Architecture:
- Orchestrator: Investigation flow coordination
- Memory: Episodic memory for past incidents
- Topology: Service graph and dependencies
- Agents: Planner, Synthesizer, Writeup
- LLM: Multi-provider routing
- Skills: Kubernetes, Metrics, Logs
"""

__version__ = "0.2.0"
__author__ = "OpenSRE Community"

# Core v2 exports
from autosre.orchestrator import Orchestrator, Investigation
from autosre.memory import EpisodicMemory, Episode, MemoryQuery
from autosre.topology import ServiceGraph, ServiceNode
from autosre.agents import (
    Alert,
    Hypothesis,
    Evidence,
    AgentResult,
    InvestigationState,
    InvestigationPlan,
    Planner,
    AVAILABLE_AGENTS,
    Synthesizer,
    Synthesis,
    WriteupGenerator,
    IncidentReport,
)
from autosre.llm import LLMRouter
from autosre.reporters import TerminalReporter

# On-call and Postmortem (v2.1)
from autosre.alerts.quality import (
    AlertQualityValidator,
    AlertQualityResult,
    REQUIRED_ALERT_FIELDS,
)
from autosre.oncall.load import (
    OnCallLoadTracker,
    ShiftStatus,
    LoadStatus,
    MAX_INCIDENTS_PER_SHIFT,
    SHIFT_HOURS,
)
from autosre.postmortem.generator import (
    PostmortemGenerator,
    PostmortemDraft,
    ActionItem,
    ActionPriority,
    AIPerformanceReview,
)
from autosre.postmortem.policy import (
    PostmortemPolicy,
    PostmortemTrigger,
    TriggerType,
    PolicyConfig,
    load_policy_from_yaml,
)
from autosre.utils.deliberate import (
    DeliberateReasoner,
    DeliberationRecord,
    PAUSE_CHECKLIST_PROMPT,
)

# Multi-Tenancy (v2.2) - Enterprise SaaS support
from autosre.tenancy import (
    Tenant,
    TenantTier,
    TenantStatus,
    Workspace,
    WorkspaceType,
    Team,
    TeamRole,
    TenantContext,
    TenantIsolation,
    get_current_tenant,
    tenant_context,
    QuotaManager,
    QuotaType,
    QuotaExceededError,
    UsageTracker,
    BillingService,
    TenantMiddleware,
)

# Chaos Engineering (v2.3) - Resilience testing
from autosre.chaos import (
    ChaosExperiment,
    ExperimentState,
    ExperimentResult,
    ExperimentConfig,
    ExperimentType,
    TargetSelector,
    ExperimentSchedule,
    ExperimentRunner,
    Fault,
    FaultType,
    FaultInjector,
    PodKillFault,
    NetworkDelayFault,
    CPUStressFault,
    MemoryStressFault,
    GameDay,
    GameDayState,
    GameDayResult,
    GameDayScenario,
    GameDayScheduler,
    GameDayRunner,
    SafetyChecker,
    SafetyRule,
    SafetyViolation,
    BlastRadius,
    BlastRadiusConfig,
    SafetyPolicy,
    SafetyLevel,
    CircuitBreaker,
    ChaosReport,
    ExperimentMetrics,
    ReportGenerator,
    ResilienceScore,
)

# Workflow Automation (v2.3) - Temporal/Argo-inspired workflow engine
from autosre.workflows import (
    # Engine
    WorkflowEngine,
    WorkflowExecution,
    ExecutionStatus,
    StepExecution,
    WorkflowContext,
    # DSL
    WorkflowDefinition,
    WorkflowParser,
    WorkflowValidator,
    parse_workflow,
    parse_workflow_file,
    # Steps
    Step,
    ActionStep,
    ConditionStep,
    LoopStep,
    ParallelStep,
    SubWorkflowStep,
    StepResult,
    StepStatus,
    # Triggers
    Trigger,
    AlertTrigger,
    ScheduleTrigger,
    WebhookTrigger,
    ManualTrigger,
    TriggerEvent,
    TriggerManager,
    # Templates
    WorkflowTemplate,
    TemplateRegistry,
    get_builtin_templates,
)

# Foundation (v1) exports - maintained for compatibility
from autosre.foundation.context_store import ContextStore
from autosre.foundation.models import Service, Ownership, ChangeEvent
from autosre.logging import get_logger, configure_logging
from autosre.exceptions import (
    AutoSREError,
    ConfigurationError,
    ConnectionError,
    ContextError,
    AgentError,
    SandboxError,
    EvalError,
)

__all__ = [
    # Version
    "__version__",
    # Core v2
    "Orchestrator",
    "Investigation",
    "EpisodicMemory",
    "Episode",
    "MemoryQuery",
    "ServiceGraph",
    "ServiceNode",
    "Alert",
    "Hypothesis",
    "Evidence",
    "AgentResult",
    "InvestigationState",
    "InvestigationPlan",
    "Planner",
    "AVAILABLE_AGENTS",
    "Synthesizer",
    "Synthesis",
    "WriteupGenerator",
    "IncidentReport",
    "LLMRouter",
    "TerminalReporter",
    # On-call & Postmortem (v2.1)
    "AlertQualityValidator",
    "AlertQualityResult",
    "REQUIRED_ALERT_FIELDS",
    "OnCallLoadTracker",
    "ShiftStatus",
    "LoadStatus",
    "MAX_INCIDENTS_PER_SHIFT",
    "SHIFT_HOURS",
    "PostmortemGenerator",
    "PostmortemDraft",
    "ActionItem",
    "ActionPriority",
    "AIPerformanceReview",
    "PostmortemPolicy",
    "PostmortemTrigger",
    "TriggerType",
    "PolicyConfig",
    "load_policy_from_yaml",
    "DeliberateReasoner",
    "DeliberationRecord",
    "PAUSE_CHECKLIST_PROMPT",
    # Multi-Tenancy (v2.2)
    "Tenant",
    "TenantTier",
    "TenantStatus",
    "Workspace",
    "WorkspaceType",
    "Team",
    "TeamRole",
    "TenantContext",
    "TenantIsolation",
    "get_current_tenant",
    "tenant_context",
    "QuotaManager",
    "QuotaType",
    "QuotaExceededError",
    "UsageTracker",
    "BillingService",
    "TenantMiddleware",
    # Workflow Automation (v2.3)
    "WorkflowEngine",
    "WorkflowExecution",
    "ExecutionStatus",
    "StepExecution",
    "WorkflowContext",
    "WorkflowDefinition",
    "WorkflowParser",
    "WorkflowValidator",
    "parse_workflow",
    "parse_workflow_file",
    "Step",
    "ActionStep",
    "ConditionStep",
    "LoopStep",
    "ParallelStep",
    "SubWorkflowStep",
    "StepResult",
    "StepStatus",
    "Trigger",
    "AlertTrigger",
    "ScheduleTrigger",
    "WebhookTrigger",
    "ManualTrigger",
    "TriggerEvent",
    "TriggerManager",
    "WorkflowTemplate",
    "TemplateRegistry",
    "get_builtin_templates",
    # Foundation (v1)
    "ContextStore",
    "Service",
    "Ownership",
    "ChangeEvent",
    # Logging
    "get_logger",
    "configure_logging",
    # Exceptions
    "AutoSREError",
    "ConfigurationError",
    "ConnectionError",
    "ContextError",
    "AgentError",
    "SandboxError",
    "EvalError",
]
