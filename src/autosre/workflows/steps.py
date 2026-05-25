"""
Workflow Step Types

Defines the building blocks of workflows:
- ActionStep: Execute a single action (tool call, API request, etc.)
- ConditionStep: Branch based on conditions
- LoopStep: Iterate over collections or until conditions
- ParallelStep: Execute multiple steps concurrently
- SubWorkflowStep: Invoke another workflow
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
import asyncio
import re


class StepStatus(str, Enum):
    """Status of a workflow step execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


@dataclass
class StepResult:
    """Result of executing a workflow step."""
    status: StepStatus
    output: Any = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retries: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate execution duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def is_success(self) -> bool:
        """Check if step completed successfully."""
        return self.status == StepStatus.COMPLETED


class Step(ABC):
    """Base class for all workflow steps."""

    def __init__(
        self,
        name: str,
        id: Optional[str] = None,
        description: Optional[str] = None,
        timeout_seconds: int = 300,
        retry_count: int = 0,
        retry_delay_seconds: int = 5,
        continue_on_error: bool = False,
        condition: Optional[str] = None,
        on_success: Optional[str] = None,
        on_failure: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.id = id or name.lower().replace(" ", "_")
        self.description = description
        self.timeout_seconds = timeout_seconds
        self.retry_count = retry_count
        self.retry_delay_seconds = retry_delay_seconds
        self.continue_on_error = continue_on_error
        self.condition = condition
        self.on_success = on_success
        self.on_failure = on_failure
        self.metadata = metadata or {}

    @abstractmethod
    async def execute(self, context: "WorkflowContext") -> StepResult:
        """Execute the step with the given context."""
        pass

    def should_run(self, context: "WorkflowContext") -> bool:
        """Check if step should run based on condition."""
        if not self.condition:
            return True
        return context.evaluate_condition(self.condition)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize step to dictionary."""
        return {
            "type": self.__class__.__name__,
            "name": self.name,
            "id": self.id,
            "description": self.description,
            "timeout_seconds": self.timeout_seconds,
            "retry_count": self.retry_count,
            "retry_delay_seconds": self.retry_delay_seconds,
            "continue_on_error": self.continue_on_error,
            "condition": self.condition,
            "on_success": self.on_success,
            "on_failure": self.on_failure,
            "metadata": self.metadata,
        }


class WorkflowContext:
    """
    Context passed between workflow steps.
    Stores variables, results, and provides evaluation utilities.
    """

    def __init__(
        self,
        variables: Optional[Dict[str, Any]] = None,
        trigger_data: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
        execution_id: Optional[str] = None,
    ):
        self.variables: Dict[str, Any] = variables or {}
        self.trigger_data: Dict[str, Any] = trigger_data or {}
        self.step_results: Dict[str, StepResult] = {}
        self.tenant_id = tenant_id
        self.execution_id = execution_id
        self._action_handlers: Dict[str, Callable] = {}

    def set(self, key: str, value: Any) -> None:
        """Set a variable in the context."""
        self.variables[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get a variable from the context."""
        return self.variables.get(key, default)

    def update(self, values: Dict[str, Any]) -> None:
        """Update multiple variables."""
        self.variables.update(values)

    def record_result(self, step_id: str, result: StepResult) -> None:
        """Record the result of a step execution."""
        self.step_results[step_id] = result

    def get_result(self, step_id: str) -> Optional[StepResult]:
        """Get the result of a previously executed step."""
        return self.step_results.get(step_id)

    def register_action_handler(self, action_type: str, handler: Callable) -> None:
        """Register a handler for an action type."""
        self._action_handlers[action_type] = handler

    def get_action_handler(self, action_type: str) -> Optional[Callable]:
        """Get the handler for an action type."""
        return self._action_handlers.get(action_type)

    def evaluate_expression(self, expression: str) -> Any:
        """
        Evaluate an expression with variable substitution.
        Supports: ${{ variable }}, ${{ steps.step_id.output }}
        """
        # Replace variable references
        pattern = r'\$\{\{\s*([^}]+)\s*\}\}'
        
        def replace_ref(match):
            ref = match.group(1).strip()
            
            # Handle steps.step_id.output references
            if ref.startswith("steps."):
                parts = ref.split(".")
                if len(parts) >= 3:
                    step_id = parts[1]
                    field = parts[2]
                    result = self.step_results.get(step_id)
                    if result:
                        if field == "output":
                            return str(result.output) if result.output else ""
                        elif field == "status":
                            return result.status.value
                        elif field == "error":
                            return result.error or ""
                return ""
            
            # Handle trigger data references
            if ref.startswith("trigger."):
                key = ref[8:]  # Remove "trigger."
                value = self.trigger_data.get(key)
                return str(value) if value is not None else ""
            
            # Handle simple variable references
            value = self.variables.get(ref)
            return str(value) if value is not None else ""
        
        result = re.sub(pattern, replace_ref, str(expression))
        return result

    def evaluate_condition(self, condition: str) -> bool:
        """
        Evaluate a boolean condition.
        Supports: ==, !=, >, <, >=, <=, and, or, not, in
        """
        # First, expand any variable references
        expanded = self.evaluate_expression(condition)
        
        # Create a safe evaluation context
        safe_context = {
            "variables": self.variables,
            "trigger": self.trigger_data,
            "steps": {
                step_id: {
                    "output": result.output,
                    "status": result.status.value,
                    "is_success": result.is_success,
                    "error": result.error,
                }
                for step_id, result in self.step_results.items()
            },
            # Safe built-ins
            "True": True,
            "False": False,
            "None": None,
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
        }
        
        try:
            # Simple eval with restricted context
            # In production, use a proper expression parser
            return bool(eval(expanded, {"__builtins__": {}}, safe_context))
        except Exception:
            return False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize context to dictionary."""
        return {
            "variables": self.variables,
            "trigger_data": self.trigger_data,
            "step_results": {
                step_id: {
                    "status": result.status.value,
                    "output": result.output,
                    "error": result.error,
                }
                for step_id, result in self.step_results.items()
            },
            "tenant_id": self.tenant_id,
            "execution_id": self.execution_id,
        }


class ActionStep(Step):
    """
    Execute a single action.
    
    Actions can be:
    - Tool calls (kubernetes, prometheus, etc.)
    - API requests
    - Script execution
    - Custom handlers
    """

    def __init__(
        self,
        name: str,
        action: str,
        inputs: Optional[Dict[str, Any]] = None,
        outputs: Optional[List[str]] = None,
        **kwargs,
    ):
        super().__init__(name, **kwargs)
        self.action = action
        self.inputs = inputs or {}
        self.outputs = outputs or []

    async def execute(self, context: WorkflowContext) -> StepResult:
        """Execute the action."""
        started_at = datetime.utcnow()
        
        try:
            # Resolve input expressions
            resolved_inputs = {}
            for key, value in self.inputs.items():
                if isinstance(value, str):
                    resolved_inputs[key] = context.evaluate_expression(value)
                else:
                    resolved_inputs[key] = value

            # Get the action handler
            handler = context.get_action_handler(self.action)
            if not handler:
                return StepResult(
                    status=StepStatus.FAILED,
                    error=f"No handler registered for action: {self.action}",
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                )

            # Execute with timeout
            try:
                output = await asyncio.wait_for(
                    handler(resolved_inputs, context),
                    timeout=self.timeout_seconds,
                )
            except asyncio.TimeoutError:
                return StepResult(
                    status=StepStatus.TIMED_OUT,
                    error=f"Action timed out after {self.timeout_seconds}s",
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                )

            # Store outputs in context
            if isinstance(output, dict):
                for output_key in self.outputs:
                    if output_key in output:
                        context.set(output_key, output[output_key])

            return StepResult(
                status=StepStatus.COMPLETED,
                output=output,
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

        except Exception as e:
            return StepResult(
                status=StepStatus.FAILED,
                error=str(e),
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        data = super().to_dict()
        data.update({
            "action": self.action,
            "inputs": self.inputs,
            "outputs": self.outputs,
        })
        return data


class ConditionStep(Step):
    """
    Branch execution based on conditions.
    
    Similar to if/elif/else in programming:
    - if_condition: Primary condition
    - then_steps: Steps to execute if condition is true
    - elif_branches: Additional condition/step pairs
    - else_steps: Steps to execute if no conditions match
    """

    def __init__(
        self,
        name: str,
        if_condition: str,
        then_steps: Optional[List[Step]] = None,
        elif_branches: Optional[List[Dict[str, Any]]] = None,
        else_steps: Optional[List[Step]] = None,
        **kwargs,
    ):
        super().__init__(name, **kwargs)
        self.if_condition = if_condition
        self.then_steps = then_steps or []
        self.elif_branches = elif_branches or []
        self.else_steps = else_steps or []

    async def execute(self, context: WorkflowContext) -> StepResult:
        """Execute the appropriate branch based on conditions."""
        started_at = datetime.utcnow()
        
        try:
            # Check primary condition
            if context.evaluate_condition(self.if_condition):
                steps_to_run = self.then_steps
                branch_taken = "then"
            else:
                # Check elif branches
                steps_to_run = None
                branch_taken = None
                
                for branch in self.elif_branches:
                    condition = branch.get("condition")
                    if condition and context.evaluate_condition(condition):
                        steps_to_run = branch.get("steps", [])
                        branch_taken = f"elif:{condition}"
                        break
                
                # Fall back to else
                if steps_to_run is None:
                    steps_to_run = self.else_steps
                    branch_taken = "else"

            # Execute the selected steps
            results = []
            for step in steps_to_run:
                if step.should_run(context):
                    result = await step.execute(context)
                    context.record_result(step.id, result)
                    results.append(result)
                    
                    if not result.is_success and not step.continue_on_error:
                        return StepResult(
                            status=StepStatus.FAILED,
                            output={"branch": branch_taken, "results": results},
                            error=f"Step {step.name} failed: {result.error}",
                            started_at=started_at,
                            completed_at=datetime.utcnow(),
                        )

            return StepResult(
                status=StepStatus.COMPLETED,
                output={"branch": branch_taken, "step_count": len(results)},
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

        except Exception as e:
            return StepResult(
                status=StepStatus.FAILED,
                error=str(e),
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        data = super().to_dict()
        data.update({
            "if_condition": self.if_condition,
            "then_steps": [s.to_dict() for s in self.then_steps],
            "elif_branches": [
                {
                    "condition": b.get("condition"),
                    "steps": [s.to_dict() for s in b.get("steps", [])],
                }
                for b in self.elif_branches
            ],
            "else_steps": [s.to_dict() for s in self.else_steps],
        })
        return data


class LoopStep(Step):
    """
    Iterate over a collection or until a condition is met.
    
    Supports:
    - for_each: Iterate over a list
    - while_condition: Loop while condition is true
    - until_condition: Loop until condition becomes true
    - max_iterations: Safety limit
    """

    def __init__(
        self,
        name: str,
        steps: Optional[List[Step]] = None,
        for_each: Optional[str] = None,
        item_variable: str = "item",
        index_variable: str = "index",
        while_condition: Optional[str] = None,
        until_condition: Optional[str] = None,
        max_iterations: int = 100,
        delay_between_iterations: float = 0,
        **kwargs,
    ):
        super().__init__(name, **kwargs)
        self.steps = steps or []
        self.for_each = for_each
        self.item_variable = item_variable
        self.index_variable = index_variable
        self.while_condition = while_condition
        self.until_condition = until_condition
        self.max_iterations = max_iterations
        self.delay_between_iterations = delay_between_iterations

    async def execute(self, context: WorkflowContext) -> StepResult:
        """Execute the loop."""
        started_at = datetime.utcnow()
        iteration_results = []
        
        try:
            if self.for_each:
                # For-each loop
                collection = context.evaluate_expression(self.for_each)
                if isinstance(collection, str):
                    # Try to get from variables
                    collection = context.get(collection, [])
                
                if not isinstance(collection, (list, tuple)):
                    collection = [collection]

                for index, item in enumerate(collection):
                    if index >= self.max_iterations:
                        break
                    
                    context.set(self.item_variable, item)
                    context.set(self.index_variable, index)
                    
                    iter_result = await self._run_iteration(context, index)
                    iteration_results.append(iter_result)
                    
                    if not iter_result.is_success:
                        break
                    
                    if self.delay_between_iterations > 0:
                        await asyncio.sleep(self.delay_between_iterations)

            elif self.while_condition:
                # While loop
                iteration = 0
                while (
                    context.evaluate_condition(self.while_condition)
                    and iteration < self.max_iterations
                ):
                    context.set(self.index_variable, iteration)
                    
                    iter_result = await self._run_iteration(context, iteration)
                    iteration_results.append(iter_result)
                    
                    if not iter_result.is_success:
                        break
                    
                    iteration += 1
                    if self.delay_between_iterations > 0:
                        await asyncio.sleep(self.delay_between_iterations)

            elif self.until_condition:
                # Until loop
                iteration = 0
                while iteration < self.max_iterations:
                    context.set(self.index_variable, iteration)
                    
                    iter_result = await self._run_iteration(context, iteration)
                    iteration_results.append(iter_result)
                    
                    if not iter_result.is_success:
                        break
                    
                    if context.evaluate_condition(self.until_condition):
                        break
                    
                    iteration += 1
                    if self.delay_between_iterations > 0:
                        await asyncio.sleep(self.delay_between_iterations)

            # Determine overall status
            failed_iterations = [r for r in iteration_results if not r.is_success]
            if failed_iterations:
                return StepResult(
                    status=StepStatus.FAILED,
                    output={"iterations": len(iteration_results), "failed": len(failed_iterations)},
                    error=f"Loop failed at iteration {len(iteration_results) - 1}",
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                )

            return StepResult(
                status=StepStatus.COMPLETED,
                output={"iterations": len(iteration_results)},
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

        except Exception as e:
            return StepResult(
                status=StepStatus.FAILED,
                error=str(e),
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

    async def _run_iteration(self, context: WorkflowContext, iteration: int) -> StepResult:
        """Run a single iteration of the loop."""
        for step in self.steps:
            if step.should_run(context):
                result = await step.execute(context)
                context.record_result(f"{step.id}_iter_{iteration}", result)
                
                if not result.is_success and not step.continue_on_error:
                    return result
        
        return StepResult(status=StepStatus.COMPLETED, output={"iteration": iteration})

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        data = super().to_dict()
        data.update({
            "steps": [s.to_dict() for s in self.steps],
            "for_each": self.for_each,
            "item_variable": self.item_variable,
            "index_variable": self.index_variable,
            "while_condition": self.while_condition,
            "until_condition": self.until_condition,
            "max_iterations": self.max_iterations,
            "delay_between_iterations": self.delay_between_iterations,
        })
        return data


class ParallelStep(Step):
    """
    Execute multiple steps concurrently.
    
    Supports:
    - max_concurrency: Limit parallel executions
    - fail_fast: Stop all on first failure
    - wait_for: Wait for specific steps to complete
    """

    def __init__(
        self,
        name: str,
        steps: Optional[List[Step]] = None,
        max_concurrency: int = 10,
        fail_fast: bool = False,
        **kwargs,
    ):
        super().__init__(name, **kwargs)
        self.steps = steps or []
        self.max_concurrency = max_concurrency
        self.fail_fast = fail_fast

    async def execute(self, context: WorkflowContext) -> StepResult:
        """Execute steps in parallel."""
        started_at = datetime.utcnow()
        
        try:
            # Filter steps that should run
            steps_to_run = [s for s in self.steps if s.should_run(context)]
            
            if not steps_to_run:
                return StepResult(
                    status=StepStatus.COMPLETED,
                    output={"executed": 0},
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                )

            # Create semaphore for concurrency control
            semaphore = asyncio.Semaphore(self.max_concurrency)
            results: Dict[str, StepResult] = {}
            failed = False

            async def run_with_semaphore(step: Step) -> None:
                nonlocal failed
                if self.fail_fast and failed:
                    results[step.id] = StepResult(
                        status=StepStatus.CANCELLED,
                        error="Cancelled due to fail_fast",
                    )
                    return
                
                async with semaphore:
                    if self.fail_fast and failed:
                        results[step.id] = StepResult(
                            status=StepStatus.CANCELLED,
                            error="Cancelled due to fail_fast",
                        )
                        return
                    
                    result = await step.execute(context)
                    results[step.id] = result
                    context.record_result(step.id, result)
                    
                    if not result.is_success and self.fail_fast:
                        failed = True

            # Run all steps concurrently
            await asyncio.gather(*[run_with_semaphore(s) for s in steps_to_run])

            # Determine overall status
            failed_results = [r for r in results.values() if not r.is_success]
            if failed_results:
                # If not continue_on_error, report failure
                if not self.continue_on_error:
                    return StepResult(
                        status=StepStatus.FAILED,
                        output={
                            "executed": len(results),
                            "failed": len(failed_results),
                            "results": {k: v.status.value for k, v in results.items()},
                        },
                        error=f"{len(failed_results)} parallel steps failed",
                        started_at=started_at,
                        completed_at=datetime.utcnow(),
                    )

            return StepResult(
                status=StepStatus.COMPLETED,
                output={
                    "executed": len(results),
                    "results": {k: v.status.value for k, v in results.items()},
                },
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

        except Exception as e:
            return StepResult(
                status=StepStatus.FAILED,
                error=str(e),
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        data = super().to_dict()
        data.update({
            "steps": [s.to_dict() for s in self.steps],
            "max_concurrency": self.max_concurrency,
            "fail_fast": self.fail_fast,
        })
        return data


class SubWorkflowStep(Step):
    """
    Invoke another workflow as a sub-workflow.
    
    Supports:
    - workflow_id: ID of workflow to invoke
    - inputs: Input parameters to pass
    - wait: Whether to wait for completion
    """

    def __init__(
        self,
        name: str,
        workflow_id: str,
        inputs: Optional[Dict[str, Any]] = None,
        wait: bool = True,
        **kwargs,
    ):
        super().__init__(name, **kwargs)
        self.workflow_id = workflow_id
        self.inputs = inputs or {}
        self.wait = wait

    async def execute(self, context: WorkflowContext) -> StepResult:
        """Execute the sub-workflow."""
        started_at = datetime.utcnow()
        
        try:
            # Resolve input expressions
            resolved_inputs = {}
            for key, value in self.inputs.items():
                if isinstance(value, str):
                    resolved_inputs[key] = context.evaluate_expression(value)
                else:
                    resolved_inputs[key] = value

            # Get sub-workflow executor from context
            executor = context.get_action_handler("execute_workflow")
            if not executor:
                return StepResult(
                    status=StepStatus.FAILED,
                    error="No workflow executor registered",
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                )

            # Execute sub-workflow
            result = await executor({
                "workflow_id": self.workflow_id,
                "inputs": resolved_inputs,
                "wait": self.wait,
                "parent_execution_id": context.execution_id,
            }, context)

            return StepResult(
                status=StepStatus.COMPLETED if result.get("success") else StepStatus.FAILED,
                output=result,
                error=result.get("error"),
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

        except Exception as e:
            return StepResult(
                status=StepStatus.FAILED,
                error=str(e),
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        data = super().to_dict()
        data.update({
            "workflow_id": self.workflow_id,
            "inputs": self.inputs,
            "wait": self.wait,
        })
        return data
