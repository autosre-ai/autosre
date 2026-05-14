"""Investigation API schemas for AutoSRE V2.

Defines request/response models for investigation workflows,
observations, hypotheses, and remediation actions.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InvestigationStatus(str, Enum):
    """Investigation lifecycle status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING_FOR_DATA = "waiting_for_data"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ObservationType(str, Enum):
    """Types of observations during investigation."""

    METRIC = "metric"
    LOG = "log"
    TRACE = "trace"
    EVENT = "event"
    RESOURCE = "resource"
    CONFIG = "config"
    COMMAND = "command"
    API_RESPONSE = "api_response"
    DEPENDENCY = "dependency"
    INFERENCE = "inference"


class HypothesisStatus(str, Enum):
    """Hypothesis evaluation status."""

    PROPOSED = "proposed"
    INVESTIGATING = "investigating"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


class ActionType(str, Enum):
    """Types of remediation actions."""

    DIAGNOSTIC = "diagnostic"
    REMEDIATION = "remediation"
    ESCALATION = "escalation"
    NOTIFICATION = "notification"
    ROLLBACK = "rollback"
    SCALE = "scale"
    RESTART = "restart"
    CONFIG_CHANGE = "config_change"
    COMMAND = "command"
    KUBECTL = "kubectl"
    API_CALL = "api_call"
    RUNBOOK = "runbook"


class ActionStatus(str, Enum):
    """Action execution status."""

    PENDING = "pending"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    REQUIRES_APPROVAL = "requires_approval"


class RiskLevel(str, Enum):
    """Risk level for actions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# =============================================================================
# Observation Schemas
# =============================================================================


class ObservationBase(BaseModel):
    """Base observation fields."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "type": "metric",
                "source": "prometheus",
                "description": "CPU usage at 95% for api-gateway pods",
                "query": "rate(process_cpu_seconds_total{job='api-gateway'}[5m])",
                "is_anomalous": True,
                "relevance_score": 0.85,
            }
        },
    )

    type: ObservationType = Field(
        ...,
        description="Type of observation",
        json_schema_extra={"example": "metric"},
    )
    source: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Source system (prometheus, kubernetes, etc.)",
        json_schema_extra={"example": "prometheus"},
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Human-readable description of the observation",
        json_schema_extra={"example": "CPU usage at 95% for api-gateway pods"},
    )
    query: str | None = Field(
        default=None,
        max_length=2000,
        description="Query or command used to gather this observation",
        json_schema_extra={"example": "rate(process_cpu_seconds_total{job='api-gateway'}[5m])"},
    )


class ObservationCreate(ObservationBase):
    """Schema for creating a new observation."""

    data: Any = Field(
        ...,
        description="Raw observation data (metrics, logs, etc.)",
    )
    summary: str | None = Field(
        default=None,
        max_length=1000,
        description="AI-generated summary of the observation",
    )
    is_anomalous: bool = Field(
        default=False,
        alias="isAnomalous",
        description="Whether this observation is anomalous",
    )
    relevance_score: float = Field(
        default=0.5,
        ge=0,
        le=1,
        alias="relevanceScore",
        description="How relevant this observation is to the investigation (0-1)",
    )
    data_timestamp: datetime | None = Field(
        default=None,
        alias="dataTimestamp",
        description="When the underlying data was generated",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )


class ObservationResponse(ObservationBase):
    """Full observation response."""

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "obs_abc123",
                "investigation_id": "inv_xyz789",
                "type": "metric",
                "source": "prometheus",
                "description": "CPU usage at 95% for api-gateway pods",
                "query": "rate(process_cpu_seconds_total[5m])",
                "data": {"value": 0.95, "labels": {"pod": "api-gateway-abc"}},
                "summary": "High CPU utilization detected",
                "is_anomalous": True,
                "relevance_score": 0.85,
                "observed_at": "2024-01-15T10:35:00Z",
                "data_timestamp": "2024-01-15T10:34:00Z",
            }
        },
    )

    id: str = Field(..., description="Observation ID")
    investigation_id: str = Field(
        ...,
        alias="investigationId",
        description="Parent investigation ID",
    )
    data: Any = Field(..., description="Raw observation data")
    summary: str | None = Field(default=None, description="AI-generated summary")
    is_anomalous: bool = Field(
        default=False,
        alias="isAnomalous",
        description="Whether this is anomalous",
    )
    relevance_score: float = Field(
        default=0.5,
        alias="relevanceScore",
        description="Relevance to investigation (0-1)",
    )
    observed_at: datetime = Field(
        ...,
        alias="observedAt",
        description="When the observation was made",
    )
    data_timestamp: datetime | None = Field(
        default=None,
        alias="dataTimestamp",
        description="When the underlying data was generated",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )


# =============================================================================
# Hypothesis Schemas
# =============================================================================


class HypothesisBase(BaseModel):
    """Base hypothesis fields."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "statement": "The API gateway is experiencing high CPU due to increased traffic",
                "reasoning": "Traffic increased 3x in the last hour while replicas remained constant",
            }
        },
    )

    statement: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The hypothesis statement",
        json_schema_extra={"example": "The API gateway is experiencing high CPU due to increased traffic"},
    )
    reasoning: str | None = Field(
        default=None,
        max_length=5000,
        description="Reasoning behind this hypothesis",
        json_schema_extra={"example": "Traffic increased 3x in the last hour while replicas remained constant"},
    )


class HypothesisCreate(HypothesisBase):
    """Schema for creating a new hypothesis."""

    verification_steps: list[str] = Field(
        default_factory=list,
        alias="verificationSteps",
        description="Steps to verify or refute this hypothesis",
    )
    initial_confidence: float = Field(
        default=0.5,
        ge=0,
        le=1,
        alias="initialConfidence",
        description="Initial confidence level (0-1)",
    )


class HypothesisResponse(HypothesisBase):
    """Full hypothesis response."""

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "hyp_abc123",
                "investigation_id": "inv_xyz789",
                "status": "confirmed",
                "statement": "The API gateway is experiencing high CPU due to increased traffic",
                "reasoning": "Traffic increased 3x in the last hour",
                "confidence": 0.92,
                "supporting_observations": ["obs_123", "obs_456"],
                "contradicting_observations": [],
                "verification_steps": ["Check traffic metrics", "Compare with baseline"],
                "verification_result": "Confirmed: traffic is 3x normal levels",
                "proposed_at": "2024-01-15T10:36:00Z",
                "resolved_at": "2024-01-15T10:40:00Z",
            }
        },
    )

    id: str = Field(..., description="Hypothesis ID")
    investigation_id: str = Field(
        ...,
        alias="investigationId",
        description="Parent investigation ID",
    )
    status: HypothesisStatus = Field(
        ...,
        description="Current status of the hypothesis",
    )
    confidence: float = Field(
        ...,
        ge=0,
        le=1,
        description="Confidence level (0-1)",
    )
    supporting_observations: list[str] = Field(
        default_factory=list,
        alias="supportingObservations",
        description="IDs of observations supporting this hypothesis",
    )
    contradicting_observations: list[str] = Field(
        default_factory=list,
        alias="contradictingObservations",
        description="IDs of observations contradicting this hypothesis",
    )
    verification_steps: list[str] = Field(
        default_factory=list,
        alias="verificationSteps",
        description="Steps to verify the hypothesis",
    )
    verification_result: str | None = Field(
        default=None,
        alias="verificationResult",
        description="Result of verification",
    )
    proposed_at: datetime = Field(
        ...,
        alias="proposedAt",
        description="When the hypothesis was proposed",
    )
    resolved_at: datetime | None = Field(
        default=None,
        alias="resolvedAt",
        description="When the hypothesis was confirmed/rejected",
    )


# =============================================================================
# Action Schemas
# =============================================================================


class ActionBase(BaseModel):
    """Base action fields."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "name": "Scale up API gateway",
                "type": "scale",
                "description": "Increase replica count from 3 to 6",
                "is_destructive": False,
                "requires_approval": True,
                "risk_level": "medium",
            }
        },
    )

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Action name",
        json_schema_extra={"example": "Scale up API gateway"},
    )
    type: ActionType = Field(
        ...,
        description="Type of action",
        json_schema_extra={"example": "scale"},
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="What this action does",
        json_schema_extra={"example": "Increase replica count from 3 to 6"},
    )


class ActionCreate(ActionBase):
    """Schema for creating a new action."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "name": "Scale up API gateway",
                "type": "scale",
                "description": "Increase replica count from 3 to 6",
                "tool": "kubernetes",
                "command": "kubectl scale deployment api-gateway --replicas=6",
                "parameters": {"replicas": 6},
                "is_destructive": False,
                "requires_approval": True,
                "risk_level": "medium",
            }
        },
    )

    tool: str | None = Field(
        default=None,
        max_length=100,
        description="Tool or plugin to use for execution",
        json_schema_extra={"example": "kubernetes"},
    )
    command: str | None = Field(
        default=None,
        max_length=5000,
        description="Command to execute",
        json_schema_extra={"example": "kubectl scale deployment api-gateway --replicas=6"},
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Action parameters",
        json_schema_extra={"example": {"replicas": 6}},
    )
    is_destructive: bool = Field(
        default=False,
        alias="isDestructive",
        description="Whether this action is destructive",
    )
    requires_approval: bool = Field(
        default=True,
        alias="requiresApproval",
        description="Whether this action requires human approval",
    )
    risk_level: RiskLevel = Field(
        default=RiskLevel.LOW,
        alias="riskLevel",
        description="Risk level of the action",
    )


class ActionResponse(ActionBase):
    """Full action response."""

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "act_abc123",
                "investigation_id": "inv_xyz789",
                "name": "Scale up API gateway",
                "type": "scale",
                "description": "Increase replica count from 3 to 6",
                "status": "completed",
                "tool": "kubernetes",
                "command": "kubectl scale deployment api-gateway --replicas=6",
                "parameters": {"replicas": 6},
                "is_destructive": False,
                "requires_approval": True,
                "risk_level": "medium",
                "result": {"previous_replicas": 3, "new_replicas": 6},
                "error": None,
                "created_at": "2024-01-15T10:41:00Z",
                "started_at": "2024-01-15T10:42:00Z",
                "completed_at": "2024-01-15T10:42:30Z",
                "approved_by": "oncall-engineer",
                "approved_at": "2024-01-15T10:41:30Z",
                "duration_seconds": 30.5,
            }
        },
    )

    id: str = Field(..., description="Action ID")
    investigation_id: str = Field(
        ...,
        alias="investigationId",
        description="Parent investigation ID",
    )
    status: ActionStatus = Field(
        ...,
        description="Current execution status",
    )
    tool: str | None = Field(default=None, description="Tool used")
    command: str | None = Field(default=None, description="Command executed")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Action parameters",
    )
    is_destructive: bool = Field(
        default=False,
        alias="isDestructive",
        description="Whether action is destructive",
    )
    requires_approval: bool = Field(
        default=True,
        alias="requiresApproval",
        description="Whether approval is required",
    )
    risk_level: RiskLevel = Field(
        default=RiskLevel.LOW,
        alias="riskLevel",
        description="Risk level",
    )
    result: Any | None = Field(default=None, description="Action result")
    error: str | None = Field(default=None, description="Error message if failed")
    created_at: datetime = Field(
        ...,
        alias="createdAt",
        description="When the action was created",
    )
    started_at: datetime | None = Field(
        default=None,
        alias="startedAt",
        description="When execution started",
    )
    completed_at: datetime | None = Field(
        default=None,
        alias="completedAt",
        description="When execution completed",
    )
    approved_by: str | None = Field(
        default=None,
        alias="approvedBy",
        description="User who approved the action",
    )
    approved_at: datetime | None = Field(
        default=None,
        alias="approvedAt",
        description="When the action was approved",
    )
    duration_seconds: float | None = Field(
        default=None,
        alias="durationSeconds",
        description="Execution duration in seconds",
    )


class ActionApprove(BaseModel):
    """Request to approve an action."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "approved_by": "oncall-engineer",
                "comment": "Approved - this should help with the CPU issue",
            }
        },
    )

    approved_by: str = Field(
        ...,
        alias="approvedBy",
        min_length=1,
        max_length=100,
        description="User approving the action",
        json_schema_extra={"example": "oncall-engineer"},
    )
    comment: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional approval comment",
    )


class ActionReject(BaseModel):
    """Request to reject an action."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "rejected_by": "oncall-engineer",
                "reason": "Let's wait for more data before scaling",
            }
        },
    )

    rejected_by: str = Field(
        ...,
        alias="rejectedBy",
        min_length=1,
        max_length=100,
        description="User rejecting the action",
    )
    reason: str | None = Field(
        default=None,
        max_length=1000,
        description="Reason for rejection",
    )


# =============================================================================
# Investigation Schemas
# =============================================================================


class InvestigationCreate(BaseModel):
    """Schema for creating a new investigation."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "alert_id": "alert_abc123",
                "title": "High CPU Investigation for api-gateway",
                "objective": "Determine root cause of elevated CPU usage and remediate",
            }
        },
    )

    alert_id: str = Field(
        ...,
        alias="alertId",
        description="ID of the alert triggering this investigation",
        json_schema_extra={"example": "alert_abc123"},
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Investigation title",
        json_schema_extra={"example": "High CPU Investigation for api-gateway"},
    )
    objective: str | None = Field(
        default=None,
        max_length=2000,
        description="Investigation objective",
        json_schema_extra={"example": "Determine root cause of elevated CPU usage and remediate"},
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context for the investigation",
    )


class InvestigationResponse(BaseModel):
    """Full investigation response with all related data."""

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "inv_xyz789",
                "alert_id": "alert_abc123",
                "status": "completed",
                "title": "High CPU Investigation for api-gateway",
                "objective": "Determine root cause of elevated CPU usage",
                "started_at": "2024-01-15T10:35:00Z",
                "completed_at": "2024-01-15T11:00:00Z",
                "observations": [],
                "hypotheses": [],
                "actions": [],
                "root_cause": "Increased traffic without autoscaling",
                "confidence": 0.92,
                "llm_calls": 15,
                "total_tokens": 25000,
                "duration_seconds": 1500.0,
            }
        },
    )

    id: str = Field(..., description="Investigation ID")
    alert_id: str = Field(
        ...,
        alias="alertId",
        description="Associated alert ID",
    )
    status: InvestigationStatus = Field(
        ...,
        description="Current investigation status",
    )
    title: str = Field(..., description="Investigation title")
    objective: str | None = Field(default=None, description="Investigation objective")
    
    # Timing
    started_at: datetime = Field(
        ...,
        alias="startedAt",
        description="When the investigation started",
    )
    completed_at: datetime | None = Field(
        default=None,
        alias="completedAt",
        description="When the investigation completed",
    )
    
    # Related entities
    observations: list[ObservationResponse] = Field(
        default_factory=list,
        description="Observations gathered during investigation",
    )
    hypotheses: list[HypothesisResponse] = Field(
        default_factory=list,
        description="Hypotheses proposed and evaluated",
    )
    actions: list[ActionResponse] = Field(
        default_factory=list,
        description="Actions taken or proposed",
    )
    
    # Results
    root_cause: str | None = Field(
        default=None,
        alias="rootCause",
        description="Identified root cause",
    )
    confidence: float = Field(
        default=0.0,
        ge=0,
        le=1,
        description="Confidence in root cause determination",
    )
    
    # Context and findings
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Investigation context",
    )
    findings: dict[str, Any] = Field(
        default_factory=dict,
        description="Investigation findings",
    )
    
    # LLM usage tracking
    llm_calls: int = Field(
        default=0,
        alias="llmCalls",
        description="Number of LLM API calls made",
    )
    total_tokens: int = Field(
        default=0,
        alias="totalTokens",
        description="Total tokens used",
    )
    
    # Computed
    duration_seconds: float | None = Field(
        default=None,
        alias="durationSeconds",
        description="Investigation duration in seconds",
    )


class InvestigationSummary(BaseModel):
    """Condensed investigation view for lists."""

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "inv_xyz789",
                "alert_id": "alert_abc123",
                "status": "completed",
                "title": "High CPU Investigation",
                "started_at": "2024-01-15T10:35:00Z",
                "completed_at": "2024-01-15T11:00:00Z",
                "root_cause": "Increased traffic",
                "confidence": 0.92,
                "observation_count": 12,
                "action_count": 3,
            }
        },
    )

    id: str = Field(..., description="Investigation ID")
    alert_id: str = Field(..., alias="alertId", description="Associated alert ID")
    status: InvestigationStatus = Field(..., description="Current status")
    title: str = Field(..., description="Investigation title")
    started_at: datetime = Field(..., alias="startedAt", description="Start time")
    completed_at: datetime | None = Field(
        default=None,
        alias="completedAt",
        description="Completion time",
    )
    root_cause: str | None = Field(
        default=None,
        alias="rootCause",
        description="Identified root cause",
    )
    confidence: float = Field(default=0.0, description="Confidence level")
    observation_count: int = Field(
        default=0,
        alias="observationCount",
        description="Number of observations",
    )
    action_count: int = Field(
        default=0,
        alias="actionCount",
        description="Number of actions",
    )


class InvestigationList(BaseModel):
    """Paginated list of investigations."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "items": [],
                "total": 50,
                "page": 1,
                "per_page": 20,
                "pages": 3,
                "has_next": True,
                "has_prev": False,
            }
        },
    )

    items: list[InvestigationSummary] = Field(..., description="List of investigations")
    total: int = Field(..., ge=0, description="Total number of investigations")
    page: int = Field(..., ge=1, description="Current page")
    per_page: int = Field(..., ge=1, alias="perPage", description="Items per page")
    pages: int = Field(..., ge=0, description="Total pages")
    has_next: bool = Field(..., alias="hasNext", description="Has next page")
    has_prev: bool = Field(..., alias="hasPrev", description="Has previous page")

    @classmethod
    def create(
        cls,
        items: list[InvestigationSummary],
        total: int,
        page: int,
        per_page: int,
    ) -> InvestigationList:
        """Create paginated response with computed fields."""
        pages = (total + per_page - 1) // per_page if per_page > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            pages=pages,
            has_next=page < pages,
            has_prev=page > 1,
        )


class InvestigationFilter(BaseModel):
    """Investigation filtering parameters."""

    model_config = ConfigDict(populate_by_name=True)

    status: list[InvestigationStatus] | None = Field(
        default=None,
        description="Filter by status values",
    )
    alert_id: str | None = Field(
        default=None,
        alias="alertId",
        description="Filter by alert ID",
    )
    has_root_cause: bool | None = Field(
        default=None,
        alias="hasRootCause",
        description="Filter by whether root cause was identified",
    )
    started_after: datetime | None = Field(
        default=None,
        alias="startedAfter",
        description="Filter by start time",
    )
    started_before: datetime | None = Field(
        default=None,
        alias="startedBefore",
        description="Filter by start time",
    )
    search: str | None = Field(
        default=None,
        max_length=200,
        description="Full-text search in title and root cause",
    )


# =============================================================================
# Report Schemas
# =============================================================================


class ReportResponse(BaseModel):
    """Investigation report response."""

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "rpt_abc123",
                "investigation_id": "inv_xyz789",
                "title": "High CPU Incident Report",
                "executive_summary": "API gateway experienced high CPU due to traffic spike",
                "root_cause": "3x traffic increase without autoscaling",
                "root_cause_confidence": 0.92,
                "timeline": [
                    {"timestamp": "2024-01-15T10:30:00Z", "description": "Alert triggered"},
                    {"timestamp": "2024-01-15T10:35:00Z", "description": "Investigation started"},
                ],
                "impact_summary": "Elevated latency for 25 minutes",
                "affected_services": ["api-gateway", "user-service"],
                "downtime_seconds": 1500.0,
                "resolution_summary": "Scaled up replicas and enabled autoscaling",
                "actions_taken": ["Scaled replicas to 6", "Enabled HPA"],
                "recommendations": ["Review autoscaling thresholds"],
                "preventive_measures": ["Add CPU-based autoscaling alerts"],
                "generated_at": "2024-01-15T11:05:00Z",
            }
        },
    )

    id: str = Field(..., description="Report ID")
    investigation_id: str = Field(
        ...,
        alias="investigationId",
        description="Associated investigation ID",
    )
    title: str = Field(..., description="Report title")
    executive_summary: str = Field(
        ...,
        alias="executiveSummary",
        description="Brief summary for stakeholders",
    )
    
    # Root cause
    root_cause: str | None = Field(
        default=None,
        alias="rootCause",
        description="Identified root cause",
    )
    root_cause_confidence: float = Field(
        default=0.0,
        ge=0,
        le=1,
        alias="rootCauseConfidence",
        description="Confidence in root cause",
    )
    
    # Timeline
    timeline: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Incident timeline",
    )
    
    # Impact
    impact_summary: str | None = Field(
        default=None,
        alias="impactSummary",
        description="Impact summary",
    )
    affected_services: list[str] = Field(
        default_factory=list,
        alias="affectedServices",
        description="List of affected services",
    )
    affected_users: int | None = Field(
        default=None,
        alias="affectedUsers",
        description="Number of affected users",
    )
    downtime_seconds: float | None = Field(
        default=None,
        alias="downtimeSeconds",
        description="Total downtime in seconds",
    )
    
    # Resolution
    resolution_summary: str | None = Field(
        default=None,
        alias="resolutionSummary",
        description="Resolution summary",
    )
    actions_taken: list[str] = Field(
        default_factory=list,
        alias="actionsTaken",
        description="Actions taken to resolve",
    )
    
    # Recommendations
    recommendations: list[str] = Field(
        default_factory=list,
        description="Recommendations",
    )
    preventive_measures: list[str] = Field(
        default_factory=list,
        alias="preventiveMeasures",
        description="Preventive measures",
    )
    
    # Metadata
    generated_at: datetime = Field(
        ...,
        alias="generatedAt",
        description="When the report was generated",
    )
    generated_by: str = Field(
        default="autosre",
        alias="generatedBy",
        description="Who/what generated the report",
    )
