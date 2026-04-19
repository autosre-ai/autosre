"""Agent runtime for OpenSRE."""

import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ConfigManager, get_config
from .exceptions import (
    AgentDefinitionError,
    RetryExhaustedError,
    SkillNotFoundError,
    StepExecutionError,
)
from .models import (
    AgentDefinition,
    AgentRunResult,
    StepDefinition,
    StepResult,
    StepStatus,
)
from .skills import SkillRegistry
from .utils import load_yaml, resolve_dict_templates


class ExecutionContext:
    """Context passed between steps during agent execution."""
    
    def __init__(self, initial: dict[str, Any] | None = None):
        self._data: dict[str, Any] = initial or {}
        self._outputs: dict[str, Any] = {}
        self._metadata: dict[str, Any] = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "step_count": 0,
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from context."""
        if key in self._outputs:
            return self._outputs[key]
        return self._data.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set a value in context."""
        self._data[key] = value
    
    def set_output(self, key: str, value: Any) -> None:
        """Set a step output value."""
        self._outputs[key] = value
    
    def all(self) -> dict[str, Any]:
        """Get all context data including outputs."""
        return {**self._data, **self._outputs}
    
    def outputs(self) -> dict[str, Any]:
        """Get only step outputs."""
        return self._outputs.copy()
    
    @property
    def metadata(self) -> dict[str, Any]:
        """Get execution metadata."""
        return self._metadata


class Agent:
    """Agent that executes steps using skills."""
    
    def __init__(
        self,
        definition: AgentDefinition,
        skill_registry: SkillRegistry,
        config_manager: ConfigManager | None = None
    ):
        self.definition = definition
        self.skills = skill_registry
        self.config = config_manager or get_config()
        self._loaded_skills: set[str] = set()
    
    @classmethod
    def from_yaml(
        cls,
        path: Path | str,
        skill_registry: SkillRegistry | None = None,
        config_manager: ConfigManager | None = None
    ) -> "Agent":
        """Load an agent from a YAML file."""
        path = Path(path)
        if not path.exists():
            raise AgentDefinitionError(str(path), "File not found")
        
        try:
            raw = load_yaml(path)
        except Exception as e:
            raise AgentDefinitionError(str(path), f"Failed to parse YAML: {e}")
        
        # Parse steps
        steps: list[StepDefinition] = []
        for i, step_data in enumerate(raw.get("steps", [])):
            step_id = step_data.get("id", f"step_{i}")
            steps.append(StepDefinition(id=step_id, **{
                k: v for k, v in step_data.items() if k != "id"
            }))
        
        definition = AgentDefinition(
            name=raw.get("name", path.stem),
            version=raw.get("version", "1.0.0"),
            description=raw.get("description", ""),
            skills=raw.get("skills", []),
            config=raw.get("config", {}),
            steps=steps
        )
        
        config_manager = config_manager or get_config()
        registry = skill_registry or SkillRegistry(config_manager.get_skills_dir())
        
        return cls(definition, registry, config_manager)
    
    def load_skills(self) -> None:
        """Load all skills required by the agent."""
        for skill_name in self.definition.skills:
            if skill_name not in self._loaded_skills:
                skill_config = self.definition.config.get(skill_name, {})
                self.skills.load(skill_name, skill_config)
                self._loaded_skills.add(skill_name)
    
    def run(
        self,
        initial_context: dict[str, Any] | None = None,
        dry_run: bool = False
    ) -> AgentRunResult:
        """Run the agent synchronously."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        
        if loop and loop.is_running():
            # We're in an async context, create a new loop in a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    self.run_async(initial_context, dry_run)
                )
                return future.result()
        else:
            return asyncio.run(self.run_async(initial_context, dry_run))
    
    async def run_async(
        self,
        initial_context: dict[str, Any] | None = None,
        dry_run: bool = False
    ) -> AgentRunResult:
        """Run the agent asynchronously."""
        started_at = datetime.now(timezone.utc)
        context = ExecutionContext(initial_context)
        step_results: list[StepResult] = []
        overall_status = StepStatus.SUCCESS
        error_message: str | None = None
        
        # Load required skills
        try:
            self.load_skills()
        except SkillNotFoundError as e:
            return AgentRunResult(
                agent_name=self.definition.name,
                status=StepStatus.FAILED,
                error=str(e),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc)
            )
        
        # Execute steps
        for step in self.definition.steps:
            result = await self._execute_step(step, context, dry_run)
            step_results.append(result)
            context.metadata["step_count"] += 1
            
            # Handle step result
            if result.status == StepStatus.FAILED:
                if step.on_error == "fail":
                    overall_status = StepStatus.FAILED
                    error_message = result.error
                    break
                elif step.on_error == "skip":
                    # Mark as skipped and continue
                    result.status = StepStatus.SKIPPED
                # "continue" just moves on
            
            # Store output if specified
            if step.output and result.output is not None:
                context.set_output(step.output, result.output)
        
        completed_at = datetime.now(timezone.utc)
        duration_ms = (completed_at - started_at).total_seconds() * 1000
        
        return AgentRunResult(
            agent_name=self.definition.name,
            status=overall_status,
            steps=step_results,
            context=context.all(),
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            error=error_message
        )
    
    async def _execute_step(
        self,
        step: StepDefinition,
        context: ExecutionContext,
        dry_run: bool = False
    ) -> StepResult:
        """Execute a single step."""
        started_at = datetime.now(timezone.utc)
        
        # Check condition
        if step.condition:
            if not self._evaluate_condition(step.condition, context):
                return StepResult(
                    step_id=step.id,
                    status=StepStatus.SKIPPED,
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc)
                )
        
        # Resolve templates in args
        resolved_args = resolve_dict_templates(step.args, context.all())
        
        if dry_run:
            return StepResult(
                step_id=step.id,
                status=StepStatus.SUCCESS,
                output={"dry_run": True, "args": resolved_args},
                started_at=started_at,
                completed_at=datetime.now(timezone.utc)
            )
        
        # Execute with retries
        last_error: Exception | None = None
        for attempt in range(step.retry + 1):
            try:
                skill = self.skills.get(step.skill)
                if not skill:
                    raise SkillNotFoundError(step.skill)
                
                # Execute the method
                if step.timeout:
                    output = await asyncio.wait_for(
                        asyncio.to_thread(
                            skill.call, step.method, context.all(), **resolved_args
                        ),
                        timeout=step.timeout
                    )
                else:
                    output = await asyncio.to_thread(
                        skill.call, step.method, context.all(), **resolved_args
                    )
                
                completed_at = datetime.now(timezone.utc)
                return StepResult(
                    step_id=step.id,
                    status=StepStatus.SUCCESS,
                    output=output,
                    started_at=started_at,
                    completed_at=completed_at,
                    attempts=attempt + 1,
                    duration_ms=(completed_at - started_at).total_seconds() * 1000
                )
                
            except asyncio.TimeoutError:
                last_error = StepExecutionError(
                    step.id, f"Timeout after {step.timeout}s", retryable=True
                )
            except Exception as e:
                last_error = e
            
            # Retry delay
            if attempt < step.retry:
                await asyncio.sleep(step.retry_delay)
        
        # All retries exhausted
        completed_at = datetime.now(timezone.utc)
        return StepResult(
            step_id=step.id,
            status=StepStatus.FAILED,
            error=str(last_error) if last_error else "Unknown error",
            started_at=started_at,
            completed_at=completed_at,
            attempts=step.retry + 1,
            duration_ms=(completed_at - started_at).total_seconds() * 1000
        )
    
    def _evaluate_condition(self, condition: str, context: ExecutionContext) -> bool:
        """Evaluate a condition expression.
        
        Simple conditions like "output.success == true" or "status == 'ok'".
        """
        # Very basic evaluation - in production would use a safe expression parser
        try:
            # Replace context references
            expr = condition
            for key, value in context.all().items():
                if isinstance(value, str):
                    expr = expr.replace(f"{key}", f"'{value}'")
                elif isinstance(value, bool):
                    expr = expr.replace(f"{key}", str(value).lower())
                elif isinstance(value, (int, float)):
                    expr = expr.replace(f"{key}", str(value))
            
            # Evaluate (note: in production, use a safe evaluator)
            return bool(eval(expr, {"__builtins__": {}}, {}))
        except Exception:
            return False


class AgentRunner:
    """High-level runner for agents."""
    
    def __init__(
        self,
        config_manager: ConfigManager | None = None,
        skill_registry: SkillRegistry | None = None
    ):
        self.config = config_manager or get_config()
        self.skills = skill_registry or SkillRegistry(self.config.get_skills_dir())
    
    def run(
        self,
        agent_path: Path | str,
        context: dict[str, Any] | None = None,
        dry_run: bool = False
    ) -> AgentRunResult:
        """Run an agent from a YAML file."""
        agent = Agent.from_yaml(agent_path, self.skills, self.config)
        return agent.run(context, dry_run)
    
    async def run_async(
        self,
        agent_path: Path | str,
        context: dict[str, Any] | None = None,
        dry_run: bool = False
    ) -> AgentRunResult:
        """Run an agent asynchronously."""
        agent = Agent.from_yaml(agent_path, self.skills, self.config)
        return await agent.run_async(context, dry_run)
    
    def discover_agents(self) -> list[dict[str, Any]]:
        """Discover all agents in the agents directory.
        
        Searches for agent.yaml files in subdirectories and *.yaml files
        directly in the agents directory.
        """
        agents_dir = self.config.get_agents_dir()
        if not agents_dir.exists():
            return []
        
        discovered = []
        
        # Find agent.yaml files in subdirectories
        for agent_yaml in agents_dir.glob("*/agent.yaml"):
            try:
                raw = load_yaml(agent_yaml)
                discovered.append({
                    "name": raw.get("name", agent_yaml.parent.name),
                    "version": raw.get("version", "1.0.0"),
                    "description": raw.get("description", ""),
                    "path": str(agent_yaml),
                    "skills": raw.get("skills", []),
                    "steps": len(raw.get("steps", []))
                })
            except Exception as e:
                discovered.append({
                    "name": agent_yaml.parent.name,
                    "path": str(agent_yaml),
                    "error": str(e)
                })
        
        # Also check for *.yaml files directly in agents directory
        for item in agents_dir.glob("*.yaml"):
            if item.name.lower() in ("catalog.md", "readme.md"):
                continue  # Skip non-agent files
            try:
                raw = load_yaml(item)
                # Only include if it looks like an agent definition
                if "steps" in raw or "skills" in raw:
                    discovered.append({
                        "name": raw.get("name", item.stem),
                        "version": raw.get("version", "1.0.0"),
                        "description": raw.get("description", ""),
                        "path": str(item),
                        "skills": raw.get("skills", []),
                        "steps": len(raw.get("steps", []))
                    })
            except Exception as e:
                discovered.append({
                    "name": item.stem,
                    "path": str(item),
                    "error": str(e)
                })
        
        return discovered
