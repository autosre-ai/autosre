"""Memory and episode models."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EpisodeOutcome(str, Enum):
    """Outcome of an investigation episode."""
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    FALSE_POSITIVE = "false_positive"
    UNRESOLVED = "unresolved"
    AUTO_RECOVERED = "auto_recovered"


class Episode(BaseModel):
    """A complete investigation episode stored in memory."""
    episode_id: str = Field(..., description="Unique episode identifier")
    investigation_id: str = Field(..., description="Original investigation ID")
    service: str = Field(..., description="Service that was investigated")
    alert_type: str = Field(..., description="Type of alert that triggered investigation")
    symptoms: list[str] = Field(..., description="Observed symptoms")
    root_cause: str | None = Field(default=None, description="Identified root cause")
    resolution: str | None = Field(default=None, description="How it was resolved")
    outcome: EpisodeOutcome = Field(..., description="Episode outcome")
    duration_seconds: int = Field(..., description="Total investigation duration")
    created_at: datetime = Field(..., description="Episode creation time")
    feedback_rating: int | None = Field(
        default=None,
        ge=1,
        le=5,
        description="Human feedback rating"
    )
    tags: list[str] = Field(default_factory=list, description="Categorization tags")
    embedding_id: str | None = Field(
        default=None,
        description="Vector embedding reference for similarity search"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "episode_id": "ep-123",
                "investigation_id": "inv-abc123",
                "service": "api-gateway",
                "alert_type": "high_error_rate",
                "symptoms": [
                    "Error rate > 5%",
                    "Latency p99 increased 200%",
                    "Recent deployment detected"
                ],
                "root_cause": "Memory leak in new feature flag code",
                "resolution": "Rolled back deployment, memory leak fix pending",
                "outcome": "resolved",
                "duration_seconds": 847,
                "created_at": "2024-01-15T10:40:00Z",
                "feedback_rating": 4,
                "tags": ["deployment", "memory-leak", "rollback"]
            }
        }
    }


class EpisodeList(BaseModel):
    """List of episodes with pagination."""
    episodes: list[Episode] = Field(..., description="List of episodes")
    total: int = Field(..., description="Total number of episodes", ge=0)
    page: int = Field(..., description="Current page", ge=1)
    page_size: int = Field(..., description="Items per page", ge=1, le=100)
    has_more: bool = Field(..., description="Whether more pages exist")


class EpisodeSearch(BaseModel):
    """Search request for similar episodes."""
    query: str = Field(..., min_length=3, max_length=500, description="Search query text")
    service: str | None = Field(default=None, description="Filter by service")
    alert_type: str | None = Field(default=None, description="Filter by alert type")
    outcome: EpisodeOutcome | None = Field(default=None, description="Filter by outcome")
    min_rating: int | None = Field(default=None, ge=1, le=5, description="Minimum feedback rating")
    date_from: datetime | None = Field(default=None, description="Start date filter")
    date_to: datetime | None = Field(default=None, description="End date filter")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum results")
    use_semantic: bool = Field(
        default=True,
        description="Use semantic (vector) search vs keyword"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "memory leak causing high error rates after deployment",
                "service": "api-gateway",
                "min_rating": 3,
                "limit": 5,
                "use_semantic": True
            }
        }
    }


class EpisodeMatch(BaseModel):
    """A search result with similarity score."""
    episode: Episode = Field(..., description="Matched episode")
    score: float = Field(..., ge=0.0, le=1.0, description="Similarity score")
    matched_on: list[str] = Field(
        default_factory=list,
        description="Fields that contributed to match"
    )


class EpisodeSearchResults(BaseModel):
    """Search results response."""
    results: list[EpisodeMatch] = Field(..., description="Matched episodes with scores")
    query: str = Field(..., description="Original search query")
    search_type: str = Field(..., description="Search type used (semantic/keyword)")
    total_matches: int = Field(..., description="Total number of matches", ge=0)


class StrategyType(str, Enum):
    """Types of investigation strategies."""
    DIAGNOSTIC = "diagnostic"
    REMEDIATION = "remediation"
    ESCALATION = "escalation"
    MONITORING = "monitoring"


class Strategy(BaseModel):
    """An investigation strategy learned from experience."""
    strategy_id: str = Field(..., description="Unique strategy identifier")
    name: str = Field(..., description="Strategy name")
    description: str = Field(..., description="What this strategy does")
    strategy_type: StrategyType = Field(..., description="Strategy category")
    applicable_to: list[str] = Field(
        ...,
        description="Alert types/services this applies to"
    )
    conditions: dict[str, Any] = Field(
        ...,
        description="Conditions when to apply this strategy"
    )
    steps: list[str] = Field(..., description="Steps to execute")
    success_rate: float = Field(..., ge=0.0, le=1.0, description="Historical success rate")
    avg_resolution_time: int | None = Field(
        default=None,
        description="Average resolution time in seconds"
    )
    learned_from: list[str] = Field(
        default_factory=list,
        description="Episode IDs this was learned from"
    )
    created_at: datetime = Field(..., description="Strategy creation time")
    updated_at: datetime = Field(..., description="Last update time")
    usage_count: int = Field(default=0, ge=0, description="Times this strategy was used")

    model_config = {
        "json_schema_extra": {
            "example": {
                "strategy_id": "strat-001",
                "name": "Post-Deployment Error Spike",
                "description": "Handle error rate increases following deployments",
                "strategy_type": "diagnostic",
                "applicable_to": ["high_error_rate", "latency_spike"],
                "conditions": {
                    "recent_deployment": True,
                    "error_rate_increase": "> 100%"
                },
                "steps": [
                    "Check deployment timeline",
                    "Compare metrics before/after deploy",
                    "Review changed services",
                    "Check rollback feasibility"
                ],
                "success_rate": 0.87,
                "avg_resolution_time": 600,
                "learned_from": ["ep-100", "ep-142", "ep-189"],
                "created_at": "2024-01-10T08:00:00Z",
                "updated_at": "2024-01-14T16:30:00Z",
                "usage_count": 23
            }
        }
    }


class StrategyList(BaseModel):
    """List of strategies."""
    strategies: list[Strategy] = Field(..., description="List of strategies")
    total: int = Field(..., description="Total strategies", ge=0)


class MemoryStats(BaseModel):
    """Memory system statistics."""
    total_episodes: int = Field(..., ge=0, description="Total episodes stored")
    total_strategies: int = Field(..., ge=0, description="Total strategies learned")
    episodes_last_7_days: int = Field(..., ge=0, description="Episodes in last week")
    avg_resolution_time: float = Field(..., ge=0, description="Average resolution time (seconds)")
    success_rate: float = Field(..., ge=0.0, le=1.0, description="Overall success rate")
    top_services: list[dict[str, Any]] = Field(
        ...,
        description="Services with most incidents"
    )
    top_alert_types: list[dict[str, Any]] = Field(
        ...,
        description="Most common alert types"
    )
    feedback_summary: dict[str, int] = Field(
        ...,
        description="Feedback rating distribution"
    )
    storage_size_mb: float = Field(..., ge=0, description="Memory storage size in MB")

    model_config = {
        "json_schema_extra": {
            "example": {
                "total_episodes": 1542,
                "total_strategies": 47,
                "episodes_last_7_days": 89,
                "avg_resolution_time": 723.5,
                "success_rate": 0.82,
                "top_services": [
                    {"service": "api-gateway", "count": 234},
                    {"service": "auth-service", "count": 156}
                ],
                "top_alert_types": [
                    {"type": "high_error_rate", "count": 412},
                    {"type": "latency_spike", "count": 298}
                ],
                "feedback_summary": {
                    "1": 23,
                    "2": 45,
                    "3": 189,
                    "4": 456,
                    "5": 312
                },
                "storage_size_mb": 156.7
            }
        }
    }
