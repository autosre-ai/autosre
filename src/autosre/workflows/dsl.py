"""
Workflow DSL Parser

Parses YAML-based workflow definitions into executable workflows.
Supports a declarative DSL similar to Argo/Temporal with SRE-specific extensions.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Union
import yaml
import re

from autosre.workflows.steps import (
    Step,
    ActionStep,
    ConditionStep,
    LoopStep,
    ParallelStep,
    SubWorkflowStep,
)


@dataclass
class WorkflowInput:
    """Input parameter definition for a workflow."""
    name: str
    type: str = "string"
    description: Optional[str] = None
    required: bool = True
    default: Any = None
    enum: Optional[List[Any]] = None


@dataclass
class WorkflowOutput:
    """Output definition for a workflow."""
    name: str
    value: str  # Expression to evaluate for output value
    description: Optional[str] = None


@dataclass
class TriggerDefinition:
    """Trigger definition from DSL."""
    type: str
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowDefinition:
    """
    Parsed workflow definition.
    
    Contains all information needed to execute a workflow:
    - Metadata (name, version, description)
    - Inputs and outputs
    - Triggers
    - Steps
    """
    name: str
    version: str = "1.0.0"
    description: Optional[str] = None
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    inputs: List[WorkflowInput] = field(default_factory=list)
    outputs: List[WorkflowOutput] = field(default_factory=list)
    triggers: List[TriggerDefinition] = field(default_factory=list)
    steps: List[Step] = field(default_factory=list)
    on_success: Optional[List[Step]] = None
    on_failure: Optional[List[Step]] = None
    timeout_seconds: int = 3600
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def id(self) -> str:
        """Generate workflow ID from name and version."""
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', self.name.lower())
        return f"{safe_name}-{self.version}"

    def validate_inputs(self, inputs: Dict[str, Any]) -> List[str]:
        """Validate provided inputs against input definitions."""
        errors = []
        
        for input_def in self.inputs:
            if input_def.required and input_def.name not in inputs:
                if input_def.default is None:
                    errors.append(f"Missing required input: {input_def.name}")
            
            if input_def.name in inputs and input_def.enum:
                if inputs[input_def.name] not in input_def.enum:
                    errors.append(
                        f"Input {input_def.name} must be one of: {input_def.enum}"
                    )
        
        return errors

    def get_default_inputs(self) -> Dict[str, Any]:
        """Get default values for all inputs."""
        return {
            inp.name: inp.default
            for inp in self.inputs
            if inp.default is not None
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary (YAML-compatible)."""
        return {
            "apiVersion": "autosre.io/v1",
            "kind": "Workflow",
            "metadata": {
                "name": self.name,
                "version": self.version,
                "description": self.description,
                "author": self.author,
                "tags": self.tags,
                **self.metadata,
            },
            "spec": {
                "inputs": [
                    {
                        "name": inp.name,
                        "type": inp.type,
                        "description": inp.description,
                        "required": inp.required,
                        "default": inp.default,
                        "enum": inp.enum,
                    }
                    for inp in self.inputs
                ],
                "outputs": [
                    {
                        "name": out.name,
                        "value": out.value,
                        "description": out.description,
                    }
                    for out in self.outputs
                ],
                "triggers": [
                    {"type": t.type, **t.config}
                    for t in self.triggers
                ],
                "steps": [step.to_dict() for step in self.steps],
                "timeout": self.timeout_seconds,
                "retries": self.retry_count,
            },
        }


class WorkflowParser:
    """
    Parser for workflow YAML definitions.
    
    Supports the AutoSRE workflow DSL format:
    
    ```yaml
    apiVersion: autosre.io/v1
    kind: Workflow
    metadata:
      name: incident-response
      version: 1.0.0
    spec:
      inputs:
        - name: alert_id
          type: string
          required: true
      triggers:
        - type: alert
          severity: [critical, high]
      steps:
        - name: Gather Context
          action: kubernetes.get_pods
          inputs:
            namespace: ${{ trigger.namespace }}
    ```
    """

    # Mapping of step types to classes
    STEP_TYPES: Dict[str, Type[Step]] = {
        "action": ActionStep,
        "condition": ConditionStep,
        "loop": LoopStep,
        "parallel": ParallelStep,
        "subworkflow": SubWorkflowStep,
        "workflow": SubWorkflowStep,
    }

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def parse(self, yaml_content: str) -> WorkflowDefinition:
        """Parse YAML content into a WorkflowDefinition."""
        self.errors = []
        self.warnings = []
        
        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise WorkflowParseError(f"Invalid YAML: {e}")
        
        return self._parse_workflow(data)

    def parse_file(self, path: Union[str, Path]) -> WorkflowDefinition:
        """Parse a workflow file."""
        path = Path(path)
        if not path.exists():
            raise WorkflowParseError(f"File not found: {path}")
        
        with open(path, 'r') as f:
            content = f.read()
        
        return self.parse(content)

    def _parse_workflow(self, data: Dict[str, Any]) -> WorkflowDefinition:
        """Parse workflow from dictionary."""
        # Validate structure
        api_version = data.get("apiVersion", "autosre.io/v1")
        kind = data.get("kind", "Workflow")
        
        if kind != "Workflow":
            raise WorkflowParseError(f"Invalid kind: {kind}, expected 'Workflow'")
        
        metadata = data.get("metadata", {})
        spec = data.get("spec", {})
        
        # Parse metadata
        name = metadata.get("name")
        if not name:
            raise WorkflowParseError("Workflow must have a name")
        
        version = metadata.get("version", "1.0.0")
        description = metadata.get("description")
        author = metadata.get("author")
        tags = metadata.get("tags", [])
        
        # Parse inputs
        inputs = [
            self._parse_input(inp)
            for inp in spec.get("inputs", [])
        ]
        
        # Parse outputs
        outputs = [
            self._parse_output(out)
            for out in spec.get("outputs", [])
        ]
        
        # Parse triggers
        triggers = [
            self._parse_trigger(trig)
            for trig in spec.get("triggers", [])
        ]
        
        # Parse steps
        steps = [
            self._parse_step(step)
            for step in spec.get("steps", [])
        ]
        
        # Parse on_success/on_failure handlers
        on_success = None
        on_failure = None
        
        if "onSuccess" in spec:
            on_success = [self._parse_step(s) for s in spec["onSuccess"]]
        if "onFailure" in spec:
            on_failure = [self._parse_step(s) for s in spec["onFailure"]]
        
        # Parse other options
        timeout = spec.get("timeout", spec.get("timeoutSeconds", 3600))
        retries = spec.get("retries", spec.get("retryCount", 0))
        
        # Build custom metadata
        custom_metadata = {
            k: v for k, v in metadata.items()
            if k not in ["name", "version", "description", "author", "tags"]
        }
        
        return WorkflowDefinition(
            name=name,
            version=version,
            description=description,
            author=author,
            tags=tags,
            inputs=inputs,
            outputs=outputs,
            triggers=triggers,
            steps=steps,
            on_success=on_success,
            on_failure=on_failure,
            timeout_seconds=timeout,
            retry_count=retries,
            metadata=custom_metadata,
        )

    def _parse_input(self, data: Dict[str, Any]) -> WorkflowInput:
        """Parse an input definition."""
        return WorkflowInput(
            name=data.get("name", ""),
            type=data.get("type", "string"),
            description=data.get("description"),
            required=data.get("required", True),
            default=data.get("default"),
            enum=data.get("enum"),
        )

    def _parse_output(self, data: Dict[str, Any]) -> WorkflowOutput:
        """Parse an output definition."""
        return WorkflowOutput(
            name=data.get("name", ""),
            value=data.get("value", ""),
            description=data.get("description"),
        )

    def _parse_trigger(self, data: Dict[str, Any]) -> TriggerDefinition:
        """Parse a trigger definition."""
        trigger_type = data.get("type", "manual")
        config = {k: v for k, v in data.items() if k != "type"}
        return TriggerDefinition(type=trigger_type, config=config)

    def _parse_step(self, data: Dict[str, Any]) -> Step:
        """Parse a step definition."""
        # Determine step type
        step_type = self._infer_step_type(data)
        
        # Common step properties
        common_props = {
            "name": data.get("name", "Unnamed Step"),
            "id": data.get("id"),
            "description": data.get("description"),
            "timeout_seconds": data.get("timeout", data.get("timeoutSeconds", 300)),
            "retry_count": data.get("retries", data.get("retryCount", 0)),
            "retry_delay_seconds": data.get("retryDelay", 5),
            "continue_on_error": data.get("continueOnError", False),
            "condition": data.get("if", data.get("condition")),
            "on_success": data.get("onSuccess"),
            "on_failure": data.get("onFailure"),
            "metadata": data.get("metadata", {}),
        }
        
        if step_type == "action":
            return ActionStep(
                action=data.get("action", ""),
                inputs=data.get("inputs", data.get("with", {})),
                outputs=data.get("outputs", []),
                **common_props,
            )
        
        elif step_type == "condition":
            return ConditionStep(
                if_condition=data.get("if", "true"),
                then_steps=[self._parse_step(s) for s in data.get("then", [])],
                elif_branches=[
                    {
                        "condition": b.get("if", b.get("condition")),
                        "steps": [self._parse_step(s) for s in b.get("then", b.get("steps", []))],
                    }
                    for b in data.get("elif", [])
                ],
                else_steps=[self._parse_step(s) for s in data.get("else", [])],
                **common_props,
            )
        
        elif step_type == "loop":
            return LoopStep(
                steps=[self._parse_step(s) for s in data.get("steps", data.get("do", []))],
                for_each=data.get("forEach", data.get("for_each")),
                item_variable=data.get("itemVar", data.get("item_variable", "item")),
                index_variable=data.get("indexVar", data.get("index_variable", "index")),
                while_condition=data.get("while"),
                until_condition=data.get("until"),
                max_iterations=data.get("maxIterations", data.get("max_iterations", 100)),
                delay_between_iterations=data.get("delay", 0),
                **common_props,
            )
        
        elif step_type == "parallel":
            return ParallelStep(
                steps=[self._parse_step(s) for s in data.get("steps", data.get("branches", []))],
                max_concurrency=data.get("maxConcurrency", data.get("max_concurrency", 10)),
                fail_fast=data.get("failFast", data.get("fail_fast", False)),
                **common_props,
            )
        
        elif step_type == "subworkflow":
            return SubWorkflowStep(
                workflow_id=data.get("workflow", data.get("workflowId", "")),
                inputs=data.get("inputs", data.get("with", {})),
                wait=data.get("wait", True),
                **common_props,
            )
        
        else:
            raise WorkflowParseError(f"Unknown step type: {step_type}")

    def _infer_step_type(self, data: Dict[str, Any]) -> str:
        """Infer the step type from its structure."""
        # Explicit type
        if "type" in data:
            return data["type"].lower()
        
        # Infer from structure
        if "action" in data:
            return "action"
        if "then" in data or "else" in data:
            return "condition"
        if "forEach" in data or "for_each" in data or "while" in data or "until" in data:
            return "loop"
        if "parallel" in data or "branches" in data:
            return "parallel"
        if "workflow" in data or "workflowId" in data:
            return "subworkflow"
        
        # Check for nested steps
        if "steps" in data:
            # Could be loop or parallel, default to parallel if no loop indicators
            return "parallel"
        
        # Default to action
        return "action"


class WorkflowValidator:
    """Validate workflow definitions for correctness and best practices."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate(self, workflow: WorkflowDefinition) -> bool:
        """
        Validate a workflow definition.
        
        Returns True if valid, False otherwise.
        Errors and warnings are stored in self.errors and self.warnings.
        """
        self.errors = []
        self.warnings = []
        
        # Required fields
        if not workflow.name:
            self.errors.append("Workflow must have a name")
        
        if not workflow.steps:
            self.errors.append("Workflow must have at least one step")
        
        # Validate steps
        step_ids = set()
        for step in workflow.steps:
            self._validate_step(step, step_ids)
        
        # Validate inputs
        for inp in workflow.inputs:
            if not inp.name:
                self.errors.append("Input must have a name")
            if inp.required and inp.default is not None:
                self.warnings.append(
                    f"Input '{inp.name}' is required but has default value"
                )
        
        # Validate triggers
        for trigger in workflow.triggers:
            if trigger.type not in ["alert", "schedule", "webhook", "manual"]:
                self.warnings.append(f"Unknown trigger type: {trigger.type}")
        
        # Check for best practices
        if workflow.timeout_seconds > 86400:
            self.warnings.append(
                f"Workflow timeout ({workflow.timeout_seconds}s) exceeds 24 hours"
            )
        
        if not workflow.description:
            self.warnings.append("Workflow should have a description")
        
        return len(self.errors) == 0

    def _validate_step(self, step: Step, step_ids: set) -> None:
        """Validate a single step."""
        # Check for duplicate IDs
        if step.id in step_ids:
            self.errors.append(f"Duplicate step ID: {step.id}")
        step_ids.add(step.id)
        
        # Validate specific step types
        if isinstance(step, ActionStep):
            if not step.action:
                self.errors.append(f"Step '{step.name}' must have an action")
        
        elif isinstance(step, ConditionStep):
            if not step.then_steps and not step.else_steps:
                self.warnings.append(
                    f"Condition step '{step.name}' has no branches"
                )
            for s in step.then_steps + step.else_steps:
                self._validate_step(s, step_ids)
        
        elif isinstance(step, LoopStep):
            if not step.for_each and not step.while_condition and not step.until_condition:
                self.errors.append(
                    f"Loop step '{step.name}' must have forEach, while, or until"
                )
            for s in step.steps:
                self._validate_step(s, step_ids)
        
        elif isinstance(step, ParallelStep):
            if not step.steps:
                self.warnings.append(
                    f"Parallel step '{step.name}' has no sub-steps"
                )
            for s in step.steps:
                self._validate_step(s, step_ids)
        
        elif isinstance(step, SubWorkflowStep):
            if not step.workflow_id:
                self.errors.append(
                    f"SubWorkflow step '{step.name}' must have workflow_id"
                )


class WorkflowParseError(Exception):
    """Exception raised when workflow parsing fails."""
    pass


# Convenience functions
def parse_workflow(yaml_content: str) -> WorkflowDefinition:
    """Parse YAML content into a WorkflowDefinition."""
    parser = WorkflowParser()
    return parser.parse(yaml_content)


def parse_workflow_file(path: Union[str, Path]) -> WorkflowDefinition:
    """Parse a workflow file."""
    parser = WorkflowParser()
    return parser.parse_file(path)
