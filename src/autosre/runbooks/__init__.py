"""
AutoSRE V2 Runbook Automation.

This module provides runbook automation capabilities:
- RunbookParser: Parse markdown/YAML runbooks
- StepExecutor: Execute runbook steps
- VariableResolver: Dynamic variable substitution
- ConditionEvaluator: Conditional step execution
- RunbookGenerator: Generate runbooks from incidents

Example:
    from autosre.runbooks import RunbookParser, RunbookExecutor
    
    parser = RunbookParser()
    runbook = await parser.parse_file("runbooks/restart-api.yaml")
    
    executor = RunbookExecutor()
    result = await executor.execute(runbook, context={
        "namespace": "production",
        "deployment": "api-server",
    })
"""

from autosre.runbooks.models import (
    Runbook,
    RunbookStep,
    StepType,
    StepResult,
    RunbookExecution,
    ExecutionStatus,
    RunbookVariable,
    VariableType,
    Condition,
    ConditionOperator,
)

from autosre.runbooks.parser import RunbookParser
from autosre.runbooks.executor import StepExecutor, RunbookExecutor
from autosre.runbooks.variables import VariableResolver
from autosre.runbooks.conditions import ConditionEvaluator
from autosre.runbooks.generator import RunbookGenerator

__all__ = [
    # Models
    "Runbook",
    "RunbookStep",
    "StepType",
    "StepResult",
    "RunbookExecution",
    "ExecutionStatus",
    "RunbookVariable",
    "VariableType",
    "Condition",
    "ConditionOperator",
    # Parser
    "RunbookParser",
    # Executor
    "StepExecutor",
    "RunbookExecutor",
    # Variables
    "VariableResolver",
    # Conditions
    "ConditionEvaluator",
    # Generator
    "RunbookGenerator",
]
