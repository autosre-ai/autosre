"""Pydantic models for OpenSRE."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class StepStatus(str, Enum):
    """Status of a step execution."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


class SkillMetadata(BaseModel):
    """Metadata for a skill from skill.yaml."""
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    dependencies: list[str] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    config_schema: dict[str, Any] = Field(default_factory=dict)
    
    
class SkillInfo(BaseModel):
    """Information about a loaded skill."""
    name: str
    version: str
    description: str
    methods: list[str]
    path: str
    loaded: bool = False
    error: str | None = None


class TriggerDefinition(BaseModel):
    """Definition of a trigger for an agent."""
    type: str  # webhook, schedule, event
    path: str | None = None
    source: str | None = None
    events: list[str] = Field(default_factory=list)
    cron: str | None = None
    timezone: str = "UTC"
    resource: str | None = None
    field_selector: str | None = None
    action: str | None = None  # For event triggers (e.g., slack action)


class StepDefinition(BaseModel):
    """Definition of a single step in an agent.
    
    Supports two formats:
    1. User-friendly: name, action (skill.method), params
    2. Verbose: id, skill, method, args
    """
    # User-friendly format (preferred)
    name: str | None = None
    action: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    
    # Verbose format (for backwards compat)
    id: str | None = None
    skill: str | None = None
    method: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    
    # Common fields
    condition: str | None = None
    retry: int = 0
    retries: int | None = None  # Alias for retry
    retry_delay: float = 1.0
    timeout: float | None = None
    on_error: str = "fail"  # fail, continue, skip
    output: str | None = None  # Variable name to store result
    
    @model_validator(mode='after')
    def normalize_fields(self):
        """Normalize between user-friendly and verbose formats."""
        # Handle retries alias
        if self.retries is not None and self.retry == 0:
            self.retry = self.retries
            
        # If user-friendly format, parse action into skill.method
        if self.action and not self.skill:
            parts = self.action.split('.', 1)
            if len(parts) == 2:
                self.skill = parts[0]
                self.method = parts[1]
            else:
                self.skill = self.action
                self.method = "execute"
        
        # Normalize id/name
        if self.name and not self.id:
            self.id = self.name
        elif self.id and not self.name:
            self.name = self.id
            
        # Normalize args/params
        if self.params and not self.args:
            self.args = self.params
        elif self.args and not self.params:
            self.params = self.args
            
        # Ensure we have required fields
        if not self.id:
            raise ValueError("Step must have 'name' or 'id'")
        if not self.skill:
            raise ValueError(f"Step '{self.id}' must have 'action' (skill.method) or 'skill'")
            
        return self


class AgentDefinition(BaseModel):
    """Definition of an agent from YAML."""
    name: str
    version: str = "1.0.0"
    description: str = ""
    skills: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    variables: dict[str, Any] = Field(default_factory=dict)
    triggers: list[TriggerDefinition] = Field(default_factory=list)
    steps: list[StepDefinition] = Field(default_factory=list)
    

class StepResult(BaseModel):
    """Result of a step execution."""
    step_id: str
    status: StepStatus
    output: Any = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    attempts: int = 1
    duration_ms: float | None = None


class AgentRunResult(BaseModel):
    """Result of an agent run."""
    agent_name: str
    status: StepStatus
    steps: list[StepResult] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: float | None = None
    error: str | None = None


class EnvironmentConfig(BaseModel):
    """Configuration for an environment."""
    name: str
    variables: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, str] = Field(default_factory=dict)  # Secret name -> source
    skills_dir: str = "skills"
    agents_dir: str = "agents"


class OpenSREConfig(BaseModel):
    """Root configuration for OpenSRE project."""
    project_name: str
    version: str = "1.0.0"
    default_environment: str = "dev"
    environments: dict[str, EnvironmentConfig] = Field(default_factory=dict)
    global_config: dict[str, Any] = Field(default_factory=dict)
