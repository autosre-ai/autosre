"""
Runbook Parser.

Parses runbooks from YAML and Markdown formats.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from autosre.utils.logging import get_logger

from .models import (
    Runbook,
    RunbookStep,
    RunbookVariable,
    StepType,
    VariableType,
    Condition,
    ConditionOperator,
)

logger = get_logger(__name__)


class ParseError(Exception):
    """Error parsing runbook."""
    
    def __init__(self, message: str, line: int | None = None):
        super().__init__(message)
        self.line = line


class RunbookParser:
    """
    Parser for runbook definitions.
    
    Supports:
    - YAML format
    - Markdown format with special sections
    
    Example YAML:
        name: Restart API Server
        description: Safely restart the API server
        variables:
          - name: namespace
            type: string
            default: production
        steps:
          - id: check-health
            name: Check current health
            type: command
            command: kubectl get pods -n {{ namespace }}
    
    Example Markdown:
        # Restart API Server
        
        ## Variables
        - namespace: production
        - deployment: api-server
        
        ## Steps
        
        ### 1. Check current health
        ```command
        kubectl get pods -n {{ namespace }}
        ```
        
        ### 2. Restart deployment
        ```kubernetes
        action: restart_deployment
        namespace: {{ namespace }}
        deployment: {{ deployment }}
        ```
    """
    
    def __init__(self):
        self._step_counter = 0
    
    async def parse_file(self, path: str | Path) -> Runbook:
        """
        Parse a runbook from a file.
        
        Args:
            path: Path to runbook file
            
        Returns:
            Parsed runbook
        """
        path = Path(path)
        
        if not path.exists():
            raise ParseError(f"File not found: {path}")
        
        content = path.read_text()
        
        if path.suffix in [".yaml", ".yml"]:
            return self.parse_yaml(content)
        elif path.suffix in [".md", ".markdown"]:
            return self.parse_markdown(content)
        else:
            # Try to detect format
            if content.strip().startswith("#"):
                return self.parse_markdown(content)
            else:
                return self.parse_yaml(content)
    
    def parse_yaml(self, content: str) -> Runbook:
        """
        Parse a YAML runbook.
        
        Args:
            content: YAML content
            
        Returns:
            Parsed runbook
        """
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise ParseError(f"Invalid YAML: {e}")
        
        if not isinstance(data, dict):
            raise ParseError("Runbook must be a YAML object")
        
        return self._parse_runbook_dict(data)
    
    def parse_markdown(self, content: str) -> Runbook:
        """
        Parse a Markdown runbook.
        
        Args:
            content: Markdown content
            
        Returns:
            Parsed runbook
        """
        lines = content.split("\n")
        
        # Extract title
        name = "Untitled Runbook"
        description = ""
        for i, line in enumerate(lines):
            if line.startswith("# "):
                name = line[2:].strip()
                # Get description from following paragraph
                desc_lines = []
                for j in range(i + 1, len(lines)):
                    if lines[j].strip() == "" and desc_lines:
                        break
                    if lines[j].startswith("#"):
                        break
                    if lines[j].strip():
                        desc_lines.append(lines[j].strip())
                description = " ".join(desc_lines)
                break
        
        # Parse sections
        sections = self._split_markdown_sections(lines)
        
        # Parse variables
        variables = []
        if "variables" in sections:
            variables = self._parse_markdown_variables(sections["variables"])
        
        # Parse steps
        steps = []
        if "steps" in sections:
            steps = self._parse_markdown_steps(sections["steps"])
        
        return Runbook(
            name=name,
            description=description,
            variables=variables,
            steps=steps,
        )
    
    def _parse_runbook_dict(self, data: dict[str, Any]) -> Runbook:
        """Parse runbook from dictionary."""
        # Parse variables
        variables = []
        for var_data in data.get("variables", []):
            variables.append(self._parse_variable(var_data))
        
        # Parse steps
        steps = []
        for step_data in data.get("steps", []):
            steps.append(self._parse_step(step_data))
        
        # Parse triggers
        triggers = data.get("triggers", [])
        
        return Runbook(
            id=data.get("id", str(hash(data.get("name", "")))),
            name=data.get("name", "Untitled"),
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            variables=variables,
            steps=steps,
            triggers=triggers,
            requires_approval=data.get("requires_approval", False),
            dry_run_by_default=data.get("dry_run_by_default", False),
            max_concurrent_executions=data.get("max_concurrent_executions", 1),
            target_services=data.get("target_services", []),
            target_namespaces=data.get("target_namespaces", []),
            author=data.get("author"),
            tags=data.get("tags", []),
            documentation_url=data.get("documentation_url"),
            default_timeout_seconds=data.get("default_timeout_seconds", 3600),
        )
    
    def _parse_variable(self, data: dict[str, Any] | str) -> RunbookVariable:
        """Parse a variable definition."""
        if isinstance(data, str):
            # Simple format: "name: default_value"
            if ":" in data:
                name, default = data.split(":", 1)
                return RunbookVariable(
                    name=name.strip(),
                    default=default.strip(),
                )
            return RunbookVariable(name=data.strip())
        
        var_type = VariableType(data.get("type", "string"))
        
        return RunbookVariable(
            name=data.get("name", "unnamed"),
            type=var_type,
            default=data.get("default"),
            value=data.get("value"),
            required=data.get("required", False),
            description=data.get("description", ""),
            validation_pattern=data.get("validation_pattern"),
            allowed_values=data.get("allowed_values"),
            from_secret=data.get("from_secret"),
            from_env=data.get("from_env"),
        )
    
    def _parse_step(self, data: dict[str, Any]) -> RunbookStep:
        """Parse a step definition."""
        self._step_counter += 1
        step_id = data.get("id", f"step-{self._step_counter}")
        
        step_type = StepType(data.get("type", "command"))
        
        # Parse condition
        condition = None
        if "condition" in data:
            condition = self._parse_condition(data["condition"])
        
        # Parse nested steps
        nested_steps = []
        for nested in data.get("steps", []):
            nested_steps.append(self._parse_step(nested))
        
        return RunbookStep(
            id=step_id,
            name=data.get("name", f"Step {self._step_counter}"),
            description=data.get("description", ""),
            type=step_type,
            command=data.get("command"),
            script=data.get("script"),
            parameters=data.get("parameters", {}),
            condition=condition,
            on_failure=data.get("on_failure"),
            on_success=data.get("on_success"),
            continue_on_failure=data.get("continue_on_failure", False),
            timeout_seconds=data.get("timeout_seconds", 300),
            delay_seconds=data.get("delay_seconds", 0),
            max_retries=data.get("max_retries", 0),
            retry_delay_seconds=data.get("retry_delay_seconds", 5),
            output_variable=data.get("output_variable"),
            expected_output=data.get("expected_output"),
            approvers=data.get("approvers", []),
            approval_timeout_minutes=data.get("approval_timeout_minutes", 60),
            steps=nested_steps,
            instructions=data.get("instructions"),
            verification_steps=data.get("verification_steps", []),
            tags=data.get("tags", []),
            annotations=data.get("annotations", {}),
        )
    
    def _parse_condition(self, data: dict[str, Any] | str) -> Condition:
        """Parse a condition."""
        if isinstance(data, str):
            # Simple format: "variable == value"
            return self._parse_condition_string(data)
        
        operator = ConditionOperator(data.get("operator", "equals"))
        
        # Parse nested conditions for AND/OR
        nested_conditions = []
        for nested in data.get("conditions", []):
            nested_conditions.append(self._parse_condition(nested))
        
        return Condition(
            left=data.get("left", ""),
            operator=operator,
            right=data.get("right"),
            conditions=nested_conditions,
        )
    
    def _parse_condition_string(self, condition: str) -> Condition:
        """Parse a condition from string format."""
        # Patterns: "var == value", "var != value", "var > value", etc.
        operators = {
            "==": ConditionOperator.EQUALS,
            "!=": ConditionOperator.NOT_EQUALS,
            ">": ConditionOperator.GREATER_THAN,
            "<": ConditionOperator.LESS_THAN,
            "contains": ConditionOperator.CONTAINS,
            "matches": ConditionOperator.MATCHES,
        }
        
        for op_str, op_enum in operators.items():
            if op_str in condition:
                parts = condition.split(op_str, 1)
                if len(parts) == 2:
                    return Condition(
                        left=parts[0].strip(),
                        operator=op_enum,
                        right=parts[1].strip().strip('"\''),
                    )
        
        # Default: check if truthy
        return Condition(
            left=condition.strip(),
            operator=ConditionOperator.EXISTS,
            right=True,
        )
    
    def _split_markdown_sections(
        self,
        lines: list[str],
    ) -> dict[str, list[str]]:
        """Split markdown into sections by headers."""
        sections: dict[str, list[str]] = {}
        current_section = "intro"
        current_lines: list[str] = []
        
        for line in lines:
            # H2 headers mark sections
            if line.startswith("## "):
                if current_lines:
                    sections[current_section] = current_lines
                current_section = line[3:].strip().lower()
                current_lines = []
            else:
                current_lines.append(line)
        
        if current_lines:
            sections[current_section] = current_lines
        
        return sections
    
    def _parse_markdown_variables(
        self,
        lines: list[str],
    ) -> list[RunbookVariable]:
        """Parse variables from markdown section."""
        variables = []
        
        for line in lines:
            line = line.strip()
            
            # List item format: - name: default
            if line.startswith("- "):
                var_text = line[2:].strip()
                
                if ":" in var_text:
                    name, default = var_text.split(":", 1)
                    variables.append(RunbookVariable(
                        name=name.strip(),
                        default=default.strip(),
                    ))
                else:
                    variables.append(RunbookVariable(name=var_text))
        
        return variables
    
    def _parse_markdown_steps(
        self,
        lines: list[str],
    ) -> list[RunbookStep]:
        """Parse steps from markdown section."""
        steps = []
        current_step: dict[str, Any] | None = None
        in_code_block = False
        code_type = ""
        code_lines: list[str] = []
        
        for line in lines:
            # H3 headers mark steps
            if line.startswith("### "):
                if current_step:
                    steps.append(self._parse_step(current_step))
                
                step_title = line[4:].strip()
                # Extract step number if present
                match = re.match(r"^(\d+)\.\s*(.+)$", step_title)
                if match:
                    step_num = match.group(1)
                    step_name = match.group(2)
                else:
                    step_num = str(len(steps) + 1)
                    step_name = step_title
                
                current_step = {
                    "id": f"step-{step_num}",
                    "name": step_name,
                    "type": "command",
                }
                continue
            
            if not current_step:
                continue
            
            # Code blocks
            if line.strip().startswith("```"):
                if in_code_block:
                    # End code block
                    in_code_block = False
                    
                    # Set step type and content based on code type
                    if code_type in ["command", "bash", "sh", "shell"]:
                        current_step["type"] = "command"
                        current_step["command"] = "\n".join(code_lines)
                    elif code_type in ["kubernetes", "k8s"]:
                        current_step["type"] = "kubernetes"
                        try:
                            current_step["parameters"] = yaml.safe_load("\n".join(code_lines))
                        except:
                            current_step["command"] = "\n".join(code_lines)
                    elif code_type in ["python"]:
                        current_step["type"] = "script"
                        current_step["script"] = "\n".join(code_lines)
                    elif code_type in ["yaml", "json"]:
                        try:
                            current_step["parameters"] = yaml.safe_load("\n".join(code_lines))
                        except:
                            pass
                    else:
                        current_step["command"] = "\n".join(code_lines)
                    
                    code_lines = []
                else:
                    # Start code block
                    in_code_block = True
                    code_type = line.strip()[3:].strip()
                continue
            
            if in_code_block:
                code_lines.append(line)
            else:
                # Regular text - add to description
                if line.strip():
                    current_step["description"] = current_step.get("description", "") + line.strip() + " "
        
        if current_step:
            steps.append(self._parse_step(current_step))
        
        return steps
    
    def validate_runbook(self, runbook: Runbook) -> list[str]:
        """
        Validate a runbook.
        
        Args:
            runbook: Runbook to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Check required fields
        if not runbook.name:
            errors.append("Runbook must have a name")
        
        if not runbook.steps:
            errors.append("Runbook must have at least one step")
        
        # Check step IDs are unique
        step_ids = set()
        for step in runbook.steps:
            if step.id in step_ids:
                errors.append(f"Duplicate step ID: {step.id}")
            step_ids.add(step.id)
            
            # Check nested steps
            for nested in step.steps:
                if nested.id in step_ids:
                    errors.append(f"Duplicate step ID: {nested.id}")
                step_ids.add(nested.id)
        
        # Check variable references in steps
        var_names = {v.name for v in runbook.variables}
        for step in runbook.steps:
            refs = self._extract_variable_refs(step)
            for ref in refs:
                if ref not in var_names:
                    errors.append(f"Step '{step.id}' references undefined variable: {ref}")
        
        # Check step references
        for step in runbook.steps:
            if step.on_failure and step.on_failure not in step_ids:
                errors.append(f"Step '{step.id}' references unknown step: {step.on_failure}")
            if step.on_success and step.on_success not in step_ids:
                errors.append(f"Step '{step.id}' references unknown step: {step.on_success}")
        
        return errors
    
    def _extract_variable_refs(self, step: RunbookStep) -> set[str]:
        """Extract variable references from a step."""
        refs = set()
        
        # Pattern: {{ variable }}
        pattern = r"\{\{\s*(\w+)\s*\}\}"
        
        # Check command
        if step.command:
            for match in re.finditer(pattern, step.command):
                refs.add(match.group(1))
        
        # Check script
        if step.script:
            for match in re.finditer(pattern, step.script):
                refs.add(match.group(1))
        
        # Check parameters
        for key, value in step.parameters.items():
            if isinstance(value, str):
                for match in re.finditer(pattern, value):
                    refs.add(match.group(1))
        
        return refs
