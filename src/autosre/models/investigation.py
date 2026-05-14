"""Investigation models for incident analysis."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator

from .common import generate_id, utc_now, ExecutionStatus
from .alert import Alert


class InvestigationStatus(str, Enum):
    """Status of an investigation."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    RESOLVED = "resolved"
    CLOSED = "closed"


class ObservationType(str, Enum):
    """Type of observation made during investigation."""
    METRIC = "metric"
    LOG = "log"
    TRACE = "trace"
    EVENT = "event"
    CONFIGURATION = "configuration"
    EXTERNAL = "external"
    MANUAL = "manual"


class Confidence(str, Enum):
    """Confidence level for hypotheses and findings."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class Observation(BaseModel):
    """An observation made during an investigation."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    id: str = Field(default_factory=generate_id)
    type: ObservationType = Field(..., description="Type of observation")
    source: str = Field(..., min_length=1, description="Source of the observation")
    summary: str = Field(..., min_length=1, description="Brief summary of what was observed")
    details: dict[str, Any] = Field(default_factory=dict, description="Detailed observation data")
    timestamp: datetime = Field(default_factory=utc_now, description="When the observation was made")
    relevance_score: float = Field(default=0.5, ge=0.0, le=1.0, description="How relevant this observation is")
    
    @field_validator("source", "summary")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class Hypothesis(BaseModel):
    """A hypothesis about the root cause."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    id: str = Field(default_factory=generate_id)
    description: str = Field(..., min_length=1, description="Description of the hypothesis")
    confidence: Confidence = Field(default=Confidence.UNKNOWN, description="Confidence level")
    supporting_observations: list[str] = Field(default_factory=list, description="IDs of supporting observations")
    contradicting_observations: list[str] = Field(default_factory=list, description="IDs of contradicting observations")
    tests_to_validate: list[str] = Field(default_factory=list, description="Tests that could validate/invalidate this hypothesis")
    created_at: datetime = Field(default_factory=utc_now)
    validated: Optional[bool] = Field(default=None, description="True if validated, False if disproven, None if untested")
    
    @field_validator("description")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()
    
    def score(self) -> float:
        """Calculate a score based on evidence."""
        supporting = len(self.supporting_observations)
        contradicting = len(self.contradicting_observations)
        total = supporting + contradicting
        if total == 0:
            return 0.5
        return supporting / total


class Finding(BaseModel):
    """A confirmed finding from the investigation."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    id: str = Field(default_factory=generate_id)
    title: str = Field(..., min_length=1, description="Brief title of the finding")
    description: str = Field(..., min_length=1, description="Detailed description")
    is_root_cause: bool = Field(default=False, description="Whether this is the root cause")
    impact: str = Field(default="", description="Impact of this finding")
    evidence: list[str] = Field(default_factory=list, description="IDs of observations that support this finding")
    hypothesis_id: Optional[str] = Field(default=None, description="ID of the hypothesis this confirms")
    confidence: Confidence = Field(default=Confidence.MEDIUM)
    created_at: datetime = Field(default_factory=utc_now)
    
    @field_validator("title", "description")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class Investigation(BaseModel):
    """A full investigation into an incident."""
    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        validate_assignment=True,
    )
    
    id: str = Field(default_factory=generate_id)
    title: str = Field(..., min_length=1, description="Investigation title")
    summary: str = Field(default="", description="Summary of the investigation")
    status: InvestigationStatus = Field(default=InvestigationStatus.OPEN)
    
    # Related alerts
    alert_ids: list[str] = Field(default_factory=list, description="IDs of related alerts")
    primary_alert: Optional[Alert] = Field(default=None, description="Primary alert that triggered investigation")
    
    # Investigation artifacts
    observations: list[Observation] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    
    # Timeline
    started_at: datetime = Field(default_factory=utc_now)
    resolved_at: Optional[datetime] = Field(default=None)
    
    # Metadata
    owner: Optional[str] = Field(default=None, description="Owner/assignee of the investigation")
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    @field_validator("title")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()
    
    def root_cause(self) -> Optional[Finding]:
        """Get the root cause finding, if identified."""
        for finding in self.findings:
            if finding.is_root_cause:
                return finding
        return None
    
    def duration_seconds(self) -> float | None:
        """Get investigation duration in seconds."""
        if self.resolved_at is None:
            return None
        return (self.resolved_at - self.started_at).total_seconds()
    
    def add_observation(self, observation: Observation) -> None:
        """Add an observation to the investigation."""
        self.observations.append(observation)
    
    def add_hypothesis(self, hypothesis: Hypothesis) -> None:
        """Add a hypothesis to the investigation."""
        self.hypotheses.append(hypothesis)
    
    def add_finding(self, finding: Finding) -> None:
        """Add a finding to the investigation."""
        self.findings.append(finding)
