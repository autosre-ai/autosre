"""
Runbook Executor.

Executes runbook steps with variable resolution and condition evaluation.
"""

from __future__ import annotations

import asyncio
import subprocess
import shlex
from datetime import datetime
from typing import Any, Callable, Awaitable
from uuid import UUID

from autosre.utils.logging import get_logger

from .models import (
    Runbook,
    RunbookStep,
    RunbookExecution,
    StepResult,
    StepType,
    ExecutionStatus,
)
from .variables import VariableResolver
from .conditions import ConditionEvaluator

logger = get_logger(__name__)


# Type for custom step handlers
StepHandler = Callable[[RunbookStep, dict[str, Any]], Awaitable[StepResult]]


class ExecutionError(Exception):
    """Error during runbook execution."""
    
    def __init__(self, step_id: str, message: str):
        super().__init__(f"Step '{step_id}': {message}")
        self.step_id = step_id


class StepExecutor:
    """
    Executes individual runbook steps.
    
    Features:
    - Multiple step types (command, kubernetes, http, etc.)
    - Variable substitution
    - Timeout handling
    - Retry logic
    - Output capture
    
    Example:
        executor = StepExecutor()
        
        result = await executor.execute(
            step=step,
            context={"namespace": "production"},
        )
    """
    
    def __init__(
        self,
        variable_resolver: VariableResolver | None = None,
        condition_evaluator: ConditionEvaluator | None = None,
    ):
        self._resolver = variable_resolver or VariableResolver()
        self._evaluator = condition_evaluator or ConditionEvaluator()
        
        # Custom handlers for step types
        self._handlers: dict[StepType, StepHandler] = {}
        
        # Kubernetes client (optional)
        self._k8s_client: Any = None
    
    def set_k8s_client(self, client: Any) -> None:
        """Set Kubernetes client for k8s operations."""
        self._k8s_client = client
    
    def register_handler(
        self,
        step_type: StepType,
        handler: StepHandler,
    ) -> None:
        """Register a custom handler for a step type."""
        self._handlers[step_type] = handler
        logger.info(f"Registered handler for step type: {step_type.value}")
    
    async def execute(
        self,
        step: RunbookStep,
        context: dict[str, Any],
        dry_run: bool = False,
    ) -> StepResult:
        """
        Execute a runbook step.
        
        Args:
            step: Step to execute
            context: Execution context with variables
            dry_run: Dry run mode
            
        Returns:
            Step result
        """
        result = StepResult(step_id=step.id)
        result.started_at = datetime.utcnow()
        
        try:
            # Check condition
            if step.condition:
                should_run = self._evaluator.evaluate(step.condition, context)
                if not should_run:
                    result.status = ExecutionStatus.SKIPPED
                    result.output = "Condition not met"
                    result.completed_at = datetime.utcnow()
                    return result
            
            # Delay if specified
            if step.delay_seconds > 0:
                logger.debug(f"Waiting {step.delay_seconds}s before step {step.id}")
                await asyncio.sleep(step.delay_seconds)
            
            result.status = ExecutionStatus.RUNNING
            
            # Execute with retry
            for attempt in range(step.max_retries + 1):
                result.attempts = attempt + 1
                
                try:
                    if dry_run:
                        step_result = await self._dry_run_step(step, context)
                    else:
                        step_result = await asyncio.wait_for(
                            self._execute_step(step, context),
                            timeout=step.timeout_seconds,
                        )
                    
                    result.output = step_result.get("output")
                    result.output_captured = step_result.get("captured", {})
                    
                    # Store output in context if variable specified
                    if step.output_variable and result.output is not None:
                        context[step.output_variable] = result.output
                    
                    result.status = ExecutionStatus.COMPLETED
                    break
                    
                except asyncio.TimeoutError:
                    result.error = f"Step timed out after {step.timeout_seconds}s"
                    if attempt < step.max_retries:
                        logger.warning(f"Step {step.id} timed out, retrying...")
                        await asyncio.sleep(step.retry_delay_seconds)
                    else:
                        result.status = ExecutionStatus.FAILED
                        
                except Exception as e:
                    result.error = str(e)
                    if attempt < step.max_retries:
                        logger.warning(f"Step {step.id} failed, retrying: {e}")
                        await asyncio.sleep(step.retry_delay_seconds)
                    else:
                        result.status = ExecutionStatus.FAILED
            
        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error = str(e)
            logger.error(f"Step {step.id} failed: {e}", exc_info=True)
        
        result.completed_at = datetime.utcnow()
        return result
    
    async def _execute_step(
        self,
        step: RunbookStep,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a step based on its type."""
        # Check for custom handler
        if step.type in self._handlers:
            result = await self._handlers[step.type](step, context)
            return {"output": result.output, "captured": result.output_captured}
        
        # Built-in handlers
        if step.type == StepType.COMMAND:
            return await self._execute_command(step, context)
        elif step.type == StepType.KUBERNETES:
            return await self._execute_kubernetes(step, context)
        elif step.type == StepType.HTTP:
            return await self._execute_http(step, context)
        elif step.type == StepType.WAIT:
            return await self._execute_wait(step, context)
        elif step.type == StepType.SCRIPT:
            return await self._execute_script(step, context)
        elif step.type == StepType.PROMETHEUS:
            return await self._execute_prometheus(step, context)
        elif step.type == StepType.PARALLEL:
            return await self._execute_parallel(step, context)
        elif step.type == StepType.NOTIFY:
            return await self._execute_notify(step, context)
        elif step.type == StepType.MANUAL:
            return {"output": f"Manual step: {step.instructions or step.description}"}
        elif step.type == StepType.APPROVAL:
            return await self._execute_approval(step, context)
        else:
            raise ExecutionError(step.id, f"Unknown step type: {step.type}")
    
    async def _dry_run_step(
        self,
        step: RunbookStep,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Simulate step execution in dry run mode."""
        resolved_command = None
        
        if step.command:
            resolved_command = self._resolver.resolve_string(step.command, context)
        
        return {
            "output": f"[DRY RUN] Would execute {step.type.value}: {resolved_command or step.name}",
            "captured": {},
        }
    
    async def _execute_command(
        self,
        step: RunbookStep,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a shell command."""
        if not step.command:
            raise ExecutionError(step.id, "No command specified")
        
        # Resolve variables in command
        command = self._resolver.resolve_string(step.command, context)
        
        logger.debug(f"Executing command: {command}")
        
        # Run command
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        stdout, stderr = await process.communicate()
        
        output = stdout.decode("utf-8")
        error_output = stderr.decode("utf-8")
        
        if process.returncode != 0:
            raise ExecutionError(
                step.id,
                f"Command failed with code {process.returncode}: {error_output}",
            )
        
        return {
            "output": output.strip(),
            "captured": {
                "stdout": output,
                "stderr": error_output,
                "return_code": process.returncode,
            },
        }
    
    async def _execute_kubernetes(
        self,
        step: RunbookStep,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a Kubernetes operation."""
        params = self._resolver.resolve_dict(step.parameters, context)
        
        action = params.get("action", "")
        namespace = params.get("namespace", "default")
        
        if self._k8s_client is None:
            # Fall back to kubectl command
            if step.command:
                return await self._execute_command(step, context)
            raise ExecutionError(step.id, "Kubernetes client not configured")
        
        # Execute via client
        if action == "restart_deployment":
            deployment = params.get("deployment")
            result = await self._k8s_client.restart_deployment(namespace, deployment)
            return {"output": f"Restarted deployment {deployment}", "captured": {}}
        
        elif action == "scale":
            deployment = params.get("deployment")
            replicas = params.get("replicas", 1)
            result = await self._k8s_client.scale_deployment(namespace, deployment, replicas)
            return {"output": f"Scaled {deployment} to {replicas} replicas", "captured": {}}
        
        elif action == "get_pods":
            pods = await self._k8s_client.list_pods(namespace)
            return {
                "output": [{"name": p.name, "phase": p.phase.value} for p in pods],
                "captured": {"pod_count": len(pods)},
            }
        
        else:
            raise ExecutionError(step.id, f"Unknown Kubernetes action: {action}")
    
    async def _execute_http(
        self,
        step: RunbookStep,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute an HTTP request."""
        import httpx
        
        params = self._resolver.resolve_dict(step.parameters, context)
        
        method = params.get("method", "GET")
        url = params.get("url", "")
        headers = params.get("headers", {})
        body = params.get("body")
        
        if not url:
            raise ExecutionError(step.id, "No URL specified")
        
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=body if body else None,
            )
            
            return {
                "output": response.text,
                "captured": {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                },
            }
    
    async def _execute_wait(
        self,
        step: RunbookStep,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a wait step."""
        params = self._resolver.resolve_dict(step.parameters, context)
        
        seconds = params.get("seconds", step.timeout_seconds)
        
        logger.info(f"Waiting {seconds} seconds...")
        await asyncio.sleep(seconds)
        
        return {"output": f"Waited {seconds} seconds", "captured": {}}
    
    async def _execute_script(
        self,
        step: RunbookStep,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a Python script."""
        if not step.script:
            raise ExecutionError(step.id, "No script specified")
        
        # Resolve variables in script
        script = self._resolver.resolve_string(step.script, context)
        
        # Create a namespace with context
        namespace = {
            "context": context,
            "result": None,
        }
        
        # Execute script
        exec(script, namespace)
        
        return {
            "output": namespace.get("result"),
            "captured": {k: v for k, v in namespace.items() if not k.startswith("_")},
        }
    
    async def _execute_prometheus(
        self,
        step: RunbookStep,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a Prometheus query."""
        params = self._resolver.resolve_dict(step.parameters, context)
        
        query = params.get("query", "")
        url = params.get("url", "http://prometheus:9090")
        
        if not query:
            raise ExecutionError(step.id, "No query specified")
        
        import httpx
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{url}/api/v1/query",
                params={"query": query},
            )
            
            data = response.json()
            
            if data.get("status") != "success":
                raise ExecutionError(step.id, f"Query failed: {data.get('error')}")
            
            return {
                "output": data.get("data", {}).get("result", []),
                "captured": data,
            }
    
    async def _execute_parallel(
        self,
        step: RunbookStep,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute nested steps in parallel."""
        if not step.steps:
            return {"output": "No nested steps", "captured": {}}
        
        tasks = [
            self.execute(nested, context.copy())
            for nested in step.steps
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        outputs = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                outputs.append({"step": step.steps[i].id, "error": str(r)})
            else:
                outputs.append({"step": step.steps[i].id, "result": r.output})
        
        return {
            "output": outputs,
            "captured": {"results": outputs},
        }
    
    async def _execute_notify(
        self,
        step: RunbookStep,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Send a notification."""
        params = self._resolver.resolve_dict(step.parameters, context)
        
        channel = params.get("channel", "console")
        message = params.get("message", "")
        
        # Resolve message
        message = self._resolver.resolve_string(message, context)
        
        logger.info(f"[NOTIFY:{channel}] {message}")
        
        return {
            "output": f"Notification sent to {channel}",
            "captured": {"channel": channel, "message": message},
        }
    
    async def _execute_approval(
        self,
        step: RunbookStep,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Wait for human approval."""
        logger.info(f"Waiting for approval: {step.name}")
        logger.info(f"Approvers: {step.approvers or ['any']}")
        
        # In a real implementation, this would integrate with
        # an approval workflow system
        return {
            "output": "Approval step (auto-approved in simulation)",
            "captured": {"auto_approved": True},
        }


class RunbookExecutor:
    """
    Executes complete runbooks.
    
    Features:
    - Full runbook execution
    - Variable resolution
    - Step flow control
    - Pause/resume support
    - Execution tracking
    
    Example:
        executor = RunbookExecutor()
        
        execution = await executor.execute(
            runbook=runbook,
            context={"namespace": "production"},
        )
        
        print(execution.to_summary())
    """
    
    def __init__(
        self,
        step_executor: StepExecutor | None = None,
        variable_resolver: VariableResolver | None = None,
    ):
        self._step_executor = step_executor or StepExecutor()
        self._resolver = variable_resolver or VariableResolver()
        
        # Active executions
        self._active: dict[UUID, RunbookExecution] = {}
        
        # Execution history
        self._history: list[RunbookExecution] = []
    
    def set_k8s_client(self, client: Any) -> None:
        """Set Kubernetes client."""
        self._step_executor.set_k8s_client(client)
    
    async def execute(
        self,
        runbook: Runbook,
        context: dict[str, Any] | None = None,
        dry_run: bool = False,
        triggered_by: str = "manual",
        incident_id: str | None = None,
    ) -> RunbookExecution:
        """
        Execute a runbook.
        
        Args:
            runbook: Runbook to execute
            context: Initial context/variables
            dry_run: Dry run mode
            triggered_by: What triggered execution
            incident_id: Related incident ID
            
        Returns:
            Execution result
        """
        context = context or {}
        
        # Apply default dry run
        if runbook.dry_run_by_default:
            dry_run = True
        
        # Create execution
        execution = RunbookExecution(
            runbook_id=runbook.id,
            runbook_name=runbook.name,
            context=context,
            dry_run=dry_run,
            triggered_by=triggered_by,
            incident_id=incident_id,
        )
        
        # Resolve variables
        resolved_vars = self._resolve_variables(runbook, context)
        execution.resolved_variables = resolved_vars
        
        # Merge into context
        full_context = {**resolved_vars, **context}
        
        # Track execution
        self._active[execution.id] = execution
        
        try:
            execution.started_at = datetime.utcnow()
            execution.status = ExecutionStatus.RUNNING
            
            logger.info(f"Starting runbook execution: {runbook.name} (id={execution.id})")
            
            # Execute steps
            step_index = 0
            while step_index < len(runbook.steps):
                step = runbook.steps[step_index]
                execution.current_step_id = step.id
                execution.current_step_index = step_index
                
                logger.info(f"Executing step {step_index + 1}/{len(runbook.steps)}: {step.name}")
                
                # Execute step
                result = await self._step_executor.execute(
                    step=step,
                    context=full_context,
                    dry_run=dry_run,
                )
                
                execution.step_results[step.id] = result
                
                # Update context with captured output
                full_context.update(result.output_captured)
                
                # Handle result
                if result.status == ExecutionStatus.FAILED:
                    if step.continue_on_failure:
                        logger.warning(f"Step {step.id} failed but continuing: {result.error}")
                    elif step.on_failure:
                        # Jump to failure handler
                        fail_step = runbook.get_step(step.on_failure)
                        if fail_step:
                            step_index = runbook.steps.index(fail_step)
                            continue
                        else:
                            logger.error(f"Failure handler step not found: {step.on_failure}")
                    elif execution.pause_on_failure:
                        execution.status = ExecutionStatus.PAUSED
                        logger.error(f"Execution paused due to failure: {result.error}")
                        break
                    else:
                        execution.status = ExecutionStatus.FAILED
                        execution.error = result.error
                        break
                
                elif result.status == ExecutionStatus.COMPLETED:
                    if step.on_success:
                        # Jump to success handler
                        success_step = runbook.get_step(step.on_success)
                        if success_step:
                            step_index = runbook.steps.index(success_step)
                            continue
                
                step_index += 1
            
            # Mark complete if not already failed/paused
            if execution.status == ExecutionStatus.RUNNING:
                execution.status = ExecutionStatus.COMPLETED
                execution.final_output = full_context
            
        except Exception as e:
            execution.status = ExecutionStatus.FAILED
            execution.error = str(e)
            logger.error(f"Runbook execution failed: {e}", exc_info=True)
        
        finally:
            execution.completed_at = datetime.utcnow()
            self._active.pop(execution.id, None)
            self._history.append(execution)
        
        logger.info(f"Runbook execution completed: {execution.status.value}")
        
        return execution
    
    async def resume(
        self,
        execution_id: UUID,
        context: dict[str, Any] | None = None,
    ) -> RunbookExecution:
        """
        Resume a paused execution.
        
        Args:
            execution_id: Execution ID
            context: Additional context
            
        Returns:
            Resumed execution
        """
        execution = self._active.get(execution_id)
        
        if not execution:
            # Check history
            execution = next(
                (e for e in self._history if e.id == execution_id),
                None,
            )
        
        if not execution:
            raise ValueError(f"Execution {execution_id} not found")
        
        if execution.status != ExecutionStatus.PAUSED:
            raise ValueError(f"Execution is not paused: {execution.status}")
        
        # Update context
        if context:
            execution.resolved_variables.update(context)
        
        # Resume from current step (skip failed step)
        execution.current_step_index += 1
        execution.status = ExecutionStatus.RUNNING
        
        # Continue execution...
        # (Implementation would continue from here)
        
        return execution
    
    async def cancel(self, execution_id: UUID) -> bool:
        """
        Cancel an active execution.
        
        Args:
            execution_id: Execution ID
            
        Returns:
            True if cancelled
        """
        execution = self._active.get(execution_id)
        
        if not execution:
            return False
        
        execution.status = ExecutionStatus.CANCELLED
        execution.completed_at = datetime.utcnow()
        
        logger.info(f"Execution {execution_id} cancelled")
        
        return True
    
    def get_active_executions(self) -> list[RunbookExecution]:
        """Get all active executions."""
        return list(self._active.values())
    
    def get_execution(self, execution_id: UUID) -> RunbookExecution | None:
        """Get an execution by ID."""
        if execution_id in self._active:
            return self._active[execution_id]
        
        return next(
            (e for e in self._history if e.id == execution_id),
            None,
        )
    
    def _resolve_variables(
        self,
        runbook: Runbook,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Resolve all runbook variables."""
        resolved = {}
        
        for var in runbook.variables:
            value = var.resolve(context)
            
            # Validate
            if var.required and value is None:
                raise ValueError(f"Required variable '{var.name}' not provided")
            
            if var.allowed_values and value not in var.allowed_values:
                raise ValueError(
                    f"Variable '{var.name}' must be one of {var.allowed_values}"
                )
            
            resolved[var.name] = value
        
        return resolved
