"""
Runbook Generator.

Generates runbooks from incidents, investigations, and templates.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from autosre.utils.logging import get_logger

from .models import (
    Runbook,
    RunbookStep,
    RunbookVariable,
    StepType,
    VariableType,
)

logger = get_logger(__name__)


class RunbookTemplate:
    """Template for generating runbooks."""
    
    def __init__(
        self,
        name: str,
        description: str,
        steps: list[dict[str, Any]],
        variables: list[dict[str, Any]] | None = None,
    ):
        self.name = name
        self.description = description
        self.steps = steps
        self.variables = variables or []


# Built-in templates
BUILTIN_TEMPLATES = {
    "restart_deployment": RunbookTemplate(
        name="Restart Deployment",
        description="Safely restart a Kubernetes deployment",
        variables=[
            {"name": "namespace", "type": "string", "required": True},
            {"name": "deployment", "type": "string", "required": True},
        ],
        steps=[
            {
                "id": "check-health",
                "name": "Check current health",
                "type": "kubernetes",
                "parameters": {
                    "action": "get_pods",
                    "namespace": "{{ namespace }}",
                    "label_selector": "app={{ deployment }}",
                },
            },
            {
                "id": "restart",
                "name": "Restart deployment",
                "type": "kubernetes",
                "parameters": {
                    "action": "restart_deployment",
                    "namespace": "{{ namespace }}",
                    "deployment": "{{ deployment }}",
                },
            },
            {
                "id": "verify",
                "name": "Verify pods are healthy",
                "type": "wait",
                "parameters": {"seconds": 30},
            },
            {
                "id": "final-check",
                "name": "Final health check",
                "type": "kubernetes",
                "parameters": {
                    "action": "get_pods",
                    "namespace": "{{ namespace }}",
                    "label_selector": "app={{ deployment }}",
                },
            },
        ],
    ),
    "scale_deployment": RunbookTemplate(
        name="Scale Deployment",
        description="Scale a Kubernetes deployment",
        variables=[
            {"name": "namespace", "type": "string", "required": True},
            {"name": "deployment", "type": "string", "required": True},
            {"name": "replicas", "type": "number", "required": True},
        ],
        steps=[
            {
                "id": "current-state",
                "name": "Get current state",
                "type": "kubernetes",
                "parameters": {
                    "action": "get_deployment",
                    "namespace": "{{ namespace }}",
                    "deployment": "{{ deployment }}",
                },
            },
            {
                "id": "scale",
                "name": "Scale deployment",
                "type": "kubernetes",
                "parameters": {
                    "action": "scale",
                    "namespace": "{{ namespace }}",
                    "deployment": "{{ deployment }}",
                    "replicas": "{{ replicas }}",
                },
            },
            {
                "id": "verify",
                "name": "Wait for scale",
                "type": "wait",
                "parameters": {"seconds": 60},
            },
        ],
    ),
    "investigate_high_latency": RunbookTemplate(
        name="Investigate High Latency",
        description="Investigate high latency in a service",
        variables=[
            {"name": "service", "type": "string", "required": True},
            {"name": "namespace", "type": "string", "default": "production"},
        ],
        steps=[
            {
                "id": "check-pods",
                "name": "Check pod status",
                "type": "kubernetes",
                "parameters": {
                    "action": "get_pods",
                    "namespace": "{{ namespace }}",
                    "label_selector": "app={{ service }}",
                },
            },
            {
                "id": "check-latency",
                "name": "Query latency metrics",
                "type": "prometheus",
                "parameters": {
                    "query": 'histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{service="{{ service }}"}[5m]))',
                },
            },
            {
                "id": "check-cpu",
                "name": "Check CPU usage",
                "type": "prometheus",
                "parameters": {
                    "query": 'sum(rate(container_cpu_usage_seconds_total{pod=~"{{ service }}.*"}[5m])) by (pod)',
                },
            },
            {
                "id": "check-memory",
                "name": "Check memory usage",
                "type": "prometheus",
                "parameters": {
                    "query": 'sum(container_memory_usage_bytes{pod=~"{{ service }}.*"}) by (pod)',
                },
            },
            {
                "id": "check-logs",
                "name": "Check recent errors",
                "type": "command",
                "command": 'kubectl logs -n {{ namespace }} -l app={{ service }} --tail=100 | grep -i error || true',
            },
        ],
    ),
}


class RunbookGenerator:
    """
    Generates runbooks from various sources.
    
    Features:
    - Generate from templates
    - Generate from incidents
    - Generate from investigations
    - AI-assisted generation
    
    Example:
        generator = RunbookGenerator()
        
        # From template
        runbook = generator.from_template(
            "restart_deployment",
            variables={"namespace": "prod", "deployment": "api"}
        )
        
        # From incident actions
        runbook = generator.from_incident_actions(incident)
    """
    
    def __init__(self):
        self._templates: dict[str, RunbookTemplate] = dict(BUILTIN_TEMPLATES)
    
    def register_template(
        self,
        template_id: str,
        template: RunbookTemplate,
    ) -> None:
        """Register a custom template."""
        self._templates[template_id] = template
        logger.info(f"Registered template: {template_id}")
    
    def list_templates(self) -> list[str]:
        """List available template IDs."""
        return list(self._templates.keys())
    
    def get_template(self, template_id: str) -> RunbookTemplate | None:
        """Get a template by ID."""
        return self._templates.get(template_id)
    
    def from_template(
        self,
        template_id: str,
        variables: dict[str, Any] | None = None,
        name_override: str | None = None,
    ) -> Runbook:
        """
        Generate a runbook from a template.
        
        Args:
            template_id: Template ID
            variables: Variable values
            name_override: Override runbook name
            
        Returns:
            Generated runbook
        """
        template = self._templates.get(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")
        
        # Create variables
        runbook_vars = []
        for var_def in template.variables:
            var = RunbookVariable(
                name=var_def["name"],
                type=VariableType(var_def.get("type", "string")),
                required=var_def.get("required", False),
                default=var_def.get("default"),
                description=var_def.get("description", ""),
            )
            
            # Set value if provided
            if variables and var.name in variables:
                var.value = variables[var.name]
            
            runbook_vars.append(var)
        
        # Create steps
        steps = []
        for i, step_def in enumerate(template.steps):
            step = RunbookStep(
                id=step_def.get("id", f"step-{i+1}"),
                name=step_def.get("name", f"Step {i+1}"),
                description=step_def.get("description", ""),
                type=StepType(step_def.get("type", "command")),
                command=step_def.get("command"),
                script=step_def.get("script"),
                parameters=step_def.get("parameters", {}),
                timeout_seconds=step_def.get("timeout_seconds", 300),
            )
            steps.append(step)
        
        return Runbook(
            name=name_override or template.name,
            description=template.description,
            variables=runbook_vars,
            steps=steps,
        )
    
    def from_incident_actions(
        self,
        actions: list[dict[str, Any]],
        incident_id: str | None = None,
        name: str | None = None,
    ) -> Runbook:
        """
        Generate a runbook from incident remediation actions.
        
        Args:
            actions: List of actions taken during incident
            incident_id: Related incident ID
            name: Runbook name
            
        Returns:
            Generated runbook
        """
        # Extract unique variables from actions
        variables: dict[str, RunbookVariable] = {}
        steps = []
        
        for i, action in enumerate(actions):
            action_type = action.get("type", "command")
            
            # Create step
            step = RunbookStep(
                id=f"step-{i+1}",
                name=action.get("name", f"Step {i+1}"),
                description=action.get("description", ""),
                type=StepType(action_type),
                command=action.get("command"),
                parameters=action.get("parameters", {}),
            )
            steps.append(step)
            
            # Extract variables from parameters
            for key, value in action.get("parameters", {}).items():
                if key not in variables:
                    var_type = self._infer_type(value)
                    variables[key] = RunbookVariable(
                        name=key,
                        type=var_type,
                        default=value,
                    )
        
        return Runbook(
            name=name or f"Incident {incident_id or 'Unknown'} Remediation",
            description=f"Generated from incident {incident_id or 'Unknown'}",
            variables=list(variables.values()),
            steps=steps,
        )
    
    def from_investigation(
        self,
        investigation: Any,
        name: str | None = None,
    ) -> Runbook:
        """
        Generate a runbook from an investigation.
        
        Args:
            investigation: Investigation object
            name: Runbook name
            
        Returns:
            Generated runbook
        """
        steps = []
        variables: dict[str, RunbookVariable] = {}
        
        # Generate diagnostic steps from observations
        for i, obs in enumerate(getattr(investigation, "observations", [])):
            if obs.type.value == "metric":
                steps.append(RunbookStep(
                    id=f"check-metric-{i+1}",
                    name=f"Check {obs.description}",
                    type=StepType.PROMETHEUS,
                    parameters={"query": obs.query or ""},
                ))
            elif obs.type.value == "log":
                steps.append(RunbookStep(
                    id=f"check-logs-{i+1}",
                    name=f"Check logs: {obs.description}",
                    type=StepType.COMMAND,
                    command=obs.query or "",
                ))
        
        # Generate remediation steps from actions
        for i, action in enumerate(getattr(investigation, "actions", [])):
            step_type = StepType.COMMAND
            if "kubernetes" in action.tool.lower() if action.tool else "":
                step_type = StepType.KUBERNETES
            
            steps.append(RunbookStep(
                id=f"remediate-{i+1}",
                name=action.name,
                description=action.description,
                type=step_type,
                command=action.command,
                parameters=action.parameters,
            ))
        
        # Add verification steps
        steps.append(RunbookStep(
            id="verify",
            name="Verify remediation",
            type=StepType.MANUAL,
            instructions="Verify the issue is resolved by checking metrics and logs",
        ))
        
        return Runbook(
            name=name or f"Investigation {investigation.id}",
            description=f"Generated from investigation: {investigation.title}",
            variables=list(variables.values()),
            steps=steps,
        )
    
    def generate_from_description(
        self,
        description: str,
        context: dict[str, Any] | None = None,
    ) -> Runbook:
        """
        Generate a runbook from a natural language description.
        
        This would integrate with an LLM for more sophisticated generation.
        For now, it uses simple pattern matching.
        
        Args:
            description: Natural language description
            context: Additional context
            
        Returns:
            Generated runbook
        """
        description_lower = description.lower()
        
        # Match to templates
        if "restart" in description_lower and "deployment" in description_lower:
            return self.from_template("restart_deployment", context)
        
        if "scale" in description_lower and "deployment" in description_lower:
            return self.from_template("scale_deployment", context)
        
        if "latency" in description_lower or "slow" in description_lower:
            return self.from_template("investigate_high_latency", context)
        
        # Generate basic runbook
        return Runbook(
            name=f"Runbook: {description[:50]}",
            description=description,
            steps=[
                RunbookStep(
                    id="manual-1",
                    name="Manual investigation required",
                    type=StepType.MANUAL,
                    instructions=description,
                ),
            ],
        )
    
    def merge_runbooks(
        self,
        runbooks: list[Runbook],
        name: str,
    ) -> Runbook:
        """
        Merge multiple runbooks into one.
        
        Args:
            runbooks: List of runbooks to merge
            name: Name for merged runbook
            
        Returns:
            Merged runbook
        """
        # Collect all variables
        variables: dict[str, RunbookVariable] = {}
        for rb in runbooks:
            for var in rb.variables:
                if var.name not in variables:
                    variables[var.name] = var
        
        # Collect all steps with unique IDs
        steps = []
        step_counter = 0
        
        for rb in runbooks:
            for step in rb.steps:
                step_counter += 1
                # Create new step with unique ID
                new_step = step.model_copy()
                new_step.id = f"step-{step_counter}"
                steps.append(new_step)
        
        return Runbook(
            name=name,
            description=f"Merged from: {', '.join(rb.name for rb in runbooks)}",
            variables=list(variables.values()),
            steps=steps,
        )
    
    def _infer_type(self, value: Any) -> VariableType:
        """Infer variable type from value."""
        if isinstance(value, bool):
            return VariableType.BOOLEAN
        elif isinstance(value, (int, float)):
            return VariableType.NUMBER
        elif isinstance(value, list):
            return VariableType.LIST
        else:
            return VariableType.STRING
    
    def export_as_yaml(self, runbook: Runbook) -> str:
        """
        Export runbook as YAML.
        
        Args:
            runbook: Runbook to export
            
        Returns:
            YAML string
        """
        import yaml
        
        data = {
            "name": runbook.name,
            "description": runbook.description,
            "version": runbook.version,
            "variables": [
                {
                    "name": v.name,
                    "type": v.type.value,
                    "required": v.required,
                    "default": v.default,
                    "description": v.description,
                }
                for v in runbook.variables
            ],
            "steps": [
                {
                    "id": s.id,
                    "name": s.name,
                    "type": s.type.value,
                    **({"command": s.command} if s.command else {}),
                    **({"parameters": s.parameters} if s.parameters else {}),
                    **({"description": s.description} if s.description else {}),
                }
                for s in runbook.steps
            ],
        }
        
        return yaml.dump(data, default_flow_style=False, sort_keys=False)
    
    def export_as_markdown(self, runbook: Runbook) -> str:
        """
        Export runbook as Markdown.
        
        Args:
            runbook: Runbook to export
            
        Returns:
            Markdown string
        """
        lines = [
            f"# {runbook.name}",
            "",
            runbook.description,
            "",
        ]
        
        # Variables section
        if runbook.variables:
            lines.extend([
                "## Variables",
                "",
            ])
            for var in runbook.variables:
                required = " (required)" if var.required else ""
                default = f" = {var.default}" if var.default else ""
                lines.append(f"- **{var.name}**{required}{default}")
            lines.append("")
        
        # Steps section
        lines.extend([
            "## Steps",
            "",
        ])
        
        for i, step in enumerate(runbook.steps):
            lines.extend([
                f"### {i+1}. {step.name}",
                "",
            ])
            
            if step.description:
                lines.append(step.description)
                lines.append("")
            
            if step.command:
                lines.extend([
                    f"```{step.type.value}",
                    step.command,
                    "```",
                    "",
                ])
            elif step.parameters:
                import yaml
                lines.extend([
                    f"```yaml",
                    yaml.dump(step.parameters, default_flow_style=False),
                    "```",
                    "",
                ])
            elif step.instructions:
                lines.extend([
                    step.instructions,
                    "",
                ])
        
        return "\n".join(lines)
