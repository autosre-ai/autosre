"""
AutoSRE Workflow Automation Engine

A Temporal/Argo-inspired workflow engine for SRE automation.
Supports declarative YAML workflows with:
- Action, condition, loop, and parallel step types
- Event triggers (alerts, schedules, webhooks)
- Pre-built templates for common SRE patterns
- Execution history and state management
"""

from autosre.workflows.engine import (
    WorkflowEngine,
    WorkflowExecution,
    ExecutionStatus,
    StepExecution,
    WorkflowContext,
)
from autosre.workflows.dsl import (
    WorkflowDefinition,
    WorkflowParser,
    WorkflowValidator,
    parse_workflow,
    parse_workflow_file,
)
from autosre.workflows.steps import (
    Step,
    ActionStep,
    ConditionStep,
    LoopStep,
    ParallelStep,
    SubWorkflowStep,
    StepResult,
    StepStatus,
)
from autosre.workflows.triggers import (
    Trigger,
    AlertTrigger,
    ScheduleTrigger,
    WebhookTrigger,
    ManualTrigger,
    TriggerEvent,
    TriggerManager,
)
from autosre.workflows.templates import (
    WorkflowTemplate,
    TemplateRegistry,
    get_builtin_templates,
    INCIDENT_RESPONSE_TEMPLATE,
    SCALING_TEMPLATE,
    DEPLOYMENT_ROLLBACK_TEMPLATE,
    HEALTH_CHECK_TEMPLATE,
    CHAOS_ENGINEERING_TEMPLATE,
)

__all__ = [
    # Engine
    "WorkflowEngine",
    "WorkflowExecution",
    "ExecutionStatus",
    "StepExecution",
    "WorkflowContext",
    # DSL
    "WorkflowDefinition",
    "WorkflowParser",
    "WorkflowValidator",
    "parse_workflow",
    "parse_workflow_file",
    # Steps
    "Step",
    "ActionStep",
    "ConditionStep",
    "LoopStep",
    "ParallelStep",
    "SubWorkflowStep",
    "StepResult",
    "StepStatus",
    # Triggers
    "Trigger",
    "AlertTrigger",
    "ScheduleTrigger",
    "WebhookTrigger",
    "ManualTrigger",
    "TriggerEvent",
    "TriggerManager",
    # Templates
    "WorkflowTemplate",
    "TemplateRegistry",
    "get_builtin_templates",
    "INCIDENT_RESPONSE_TEMPLATE",
    "SCALING_TEMPLATE",
    "DEPLOYMENT_ROLLBACK_TEMPLATE",
    "HEALTH_CHECK_TEMPLATE",
    "CHAOS_ENGINEERING_TEMPLATE",
]
