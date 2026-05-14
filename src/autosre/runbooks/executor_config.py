"""
Enhanced runbook executor with additional configuration and context support.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from .variables import VariableStore


class ExecutorConfig(BaseModel):
    """Configuration for step executor."""
    
    # Timeouts
    default_timeout_seconds: int = Field(300, description="Default step timeout")
    max_timeout_seconds: int = Field(3600, description="Maximum allowed timeout")
    
    # Retries
    default_max_retries: int = Field(0, description="Default retry count")
    default_retry_delay_seconds: float = Field(5.0, description="Default retry delay")
    
    # Safety
    dry_run: bool = Field(False, description="Global dry run mode")
    allow_scripts: bool = Field(True, description="Allow script execution")
    allow_shell_commands: bool = Field(True, description="Allow shell commands")
    
    # Kubernetes
    kubeconfig_path: str | None = Field(None, description="Path to kubeconfig")
    kubectl_path: str = Field("kubectl", description="Path to kubectl")
    
    # Logging
    log_commands: bool = Field(True, description="Log executed commands")
    log_output: bool = Field(True, description="Log step output")
    max_output_lines: int = Field(100, description="Max output lines to capture")
    
    # Parallelism
    max_parallel_steps: int = Field(10, description="Max parallel step executions")


class ExecutionContext(BaseModel):
    """Context for runbook execution."""
    
    execution_id: UUID = Field(default_factory=uuid4)
    runbook_id: str
    
    # Variables
    variables: VariableStore = Field(default_factory=VariableStore)
    
    # Execution state
    current_step_id: str | None = None
    current_step_index: int = 0
    
    # Options
    dry_run: bool = False
    interactive: bool = False
    
    # Tracking
    started_at: datetime = Field(default_factory=datetime.utcnow)
    step_outputs: dict[str, Any] = Field(default_factory=dict)
    
    # User
    triggered_by: str = "system"
    incident_id: str | None = None
    
    class Config:
        arbitrary_types_allowed = True
    
    def set_step_output(self, step_id: str, output: Any) -> None:
        """Store step output."""
        self.step_outputs[step_id] = output
    
    def get_step_output(self, step_id: str) -> Any | None:
        """Get output from a previous step."""
        return self.step_outputs.get(step_id)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary for variable resolution."""
        result = {
            "execution_id": str(self.execution_id),
            "runbook_id": self.runbook_id,
            "dry_run": self.dry_run,
            "triggered_by": self.triggered_by,
        }
        
        # Add variables
        result.update(self.variables.all())
        
        # Add step outputs
        for step_id, output in self.step_outputs.items():
            result[f"step_{step_id}_output"] = output
        
        return result
