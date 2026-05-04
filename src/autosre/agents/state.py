"""Investigation state models."""

from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class Alert(BaseModel):
    """Input alert to investigate."""
    name: str
    service: Optional[str] = None
    severity: Literal["critical", "warning", "info"] = "warning"
    description: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    labels: Dict[str, str] = {}


class Hypothesis(BaseModel):
    """A potential root cause hypothesis."""
    hypothesis: str
    priority: Literal["high", "medium", "low"] = "medium"
    agents_to_test: List[str] = []
    confidence: float = 0.5


class Evidence(BaseModel):
    """Evidence gathered by a subagent."""
    source: str  # Which agent found this
    skill: str   # Which skill was used
    finding: str
    confidence: float = 0.5
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    raw_data: Optional[Dict] = None


class AgentResult(BaseModel):
    """Result from a subagent investigation."""
    agent_id: str
    status: Literal["completed", "failed", "timeout"] = "completed"
    evidence: List[Evidence] = []
    summary: str = ""
    duration_seconds: float = 0.0


class InvestigationState(BaseModel):
    """Complete state of an investigation."""
    # Input
    investigation_id: str
    alert: Alert
    
    # Context
    memory_context: Dict = {}
    topology_context: Dict = {}
    
    # Planning
    hypotheses: List[Hypothesis] = []
    selected_agents: List[str] = []
    
    # Results
    agent_results: Dict[str, AgentResult] = {}
    
    # Synthesis
    conclusion: str = ""
    root_cause: Optional[str] = None
    confidence: float = 0.0
    
    # Control
    iteration: int = 0
    max_iterations: int = 3
    status: Literal["running", "completed", "failed"] = "running"
    
    # Timing
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class InvestigationPlan(BaseModel):
    """Output from the planner."""
    hypotheses: List[Hypothesis]
    selected_agents: List[str]
    reasoning: str
