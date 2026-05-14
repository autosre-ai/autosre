"""
Confidence Scoring System for AutoSRE.

Every AI decision includes:
- confidence_score (0-100%)
- reasoning (why this action)
- evidence (what data supported this)

Scoring is based on:
- Runbook match quality
- Alert pattern recognition
- Historical success rate of similar actions
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class ConfidenceLevel(str, Enum):
    """Confidence level categories."""
    
    VERY_HIGH = "very_high"  # 90-100%
    HIGH = "high"            # 75-89%
    MEDIUM = "medium"        # 50-74%
    LOW = "low"              # 25-49%
    VERY_LOW = "very_low"    # 0-24%
    
    @classmethod
    def from_score(cls, score: float) -> "ConfidenceLevel":
        """Get confidence level from score (0-100)."""
        if score >= 90:
            return cls.VERY_HIGH
        elif score >= 75:
            return cls.HIGH
        elif score >= 50:
            return cls.MEDIUM
        elif score >= 25:
            return cls.LOW
        else:
            return cls.VERY_LOW


class EvidenceType(str, Enum):
    """Types of evidence supporting a decision."""
    
    RUNBOOK_MATCH = "runbook_match"
    ALERT_PATTERN = "alert_pattern"
    METRIC_ANALYSIS = "metric_analysis"
    LOG_ANALYSIS = "log_analysis"
    HISTORICAL_SUCCESS = "historical_success"
    TOPOLOGY_ANALYSIS = "topology_analysis"
    EXPERT_RULE = "expert_rule"
    LLM_REASONING = "llm_reasoning"


class Evidence(BaseModel):
    """A piece of evidence supporting a decision."""
    
    id: UUID = Field(default_factory=uuid4)
    type: EvidenceType
    source: str = Field(..., description="Where this evidence came from")
    summary: str = Field(..., description="Brief description of the evidence")
    data: dict[str, Any] = Field(default_factory=dict)
    
    # Scoring contribution
    weight: float = Field(1.0, ge=0, le=2.0, description="Weight for scoring")
    relevance_score: float = Field(0.5, ge=0, le=1.0, description="How relevant to decision")
    confidence_contribution: float = Field(0.0, ge=0, le=100, description="Contribution to confidence")
    
    # Metadata
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RunbookMatchScore(BaseModel):
    """Score for how well a runbook matches the situation."""
    
    runbook_id: str
    runbook_name: str
    
    # Match scores (0-1 each)
    alert_name_match: float = 0.0
    symptom_match: float = 0.0
    context_match: float = 0.0
    keyword_match: float = 0.0
    
    # Overall
    overall_score: float = 0.0
    
    # Factors
    match_factors: list[str] = Field(default_factory=list)
    mismatch_factors: list[str] = Field(default_factory=list)
    
    def calculate_overall(self) -> float:
        """Calculate overall match score."""
        weights = {
            "alert_name": 0.3,
            "symptom": 0.35,
            "context": 0.2,
            "keyword": 0.15,
        }
        self.overall_score = (
            self.alert_name_match * weights["alert_name"] +
            self.symptom_match * weights["symptom"] +
            self.context_match * weights["context"] +
            self.keyword_match * weights["keyword"]
        )
        return self.overall_score


class HistoricalOutcome(BaseModel):
    """Historical outcome of similar actions."""
    
    action_type: str
    alert_pattern: str
    
    # Statistics
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    
    # Timing
    avg_resolution_time_seconds: float = 0.0
    last_execution: datetime | None = None
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_executions == 0:
            return 0.0
        return self.successful_executions / self.total_executions
    
    @property
    def confidence_boost(self) -> float:
        """Calculate confidence boost from history (0-25 points)."""
        if self.total_executions < 3:
            return 0.0  # Not enough data
        
        base_boost = self.success_rate * 20
        
        # Bonus for recent success
        if self.last_execution:
            days_ago = (datetime.now(timezone.utc) - self.last_execution).days
            if days_ago < 7:
                base_boost += 5
            elif days_ago < 30:
                base_boost += 2
        
        return min(25, base_boost)


class ConfidenceScore(BaseModel):
    """
    Complete confidence assessment for an AI decision.
    
    Every AI decision MUST include this.
    """
    
    id: UUID = Field(default_factory=uuid4)
    
    # Core scores
    score: float = Field(..., ge=0, le=100, description="Overall confidence (0-100%)")
    level: ConfidenceLevel = Field(default=ConfidenceLevel.MEDIUM)
    
    # Reasoning
    reasoning: str = Field(..., description="Why this action is recommended")
    reasoning_steps: list[str] = Field(
        default_factory=list,
        description="Step-by-step reasoning"
    )
    
    # Evidence
    evidence: list[Evidence] = Field(
        default_factory=list,
        description="Data that supports this decision"
    )
    
    # Component scores
    runbook_match_score: float = Field(0.0, ge=0, le=100)
    alert_pattern_score: float = Field(0.0, ge=0, le=100)
    historical_success_score: float = Field(0.0, ge=0, le=100)
    context_relevance_score: float = Field(0.0, ge=0, le=100)
    
    # Factors
    positive_factors: list[str] = Field(default_factory=list)
    negative_factors: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    
    # Metadata
    decision_id: UUID | None = None
    alert_id: UUID | None = None
    model_used: str = ""
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def add_evidence(self, evidence: Evidence) -> None:
        """Add evidence and recalculate score."""
        self.evidence.append(evidence)
        self._recalculate()
    
    def _recalculate(self) -> None:
        """Recalculate overall score from components."""
        weights = {
            "runbook": 0.30,
            "pattern": 0.25,
            "history": 0.25,
            "context": 0.20,
        }
        
        self.score = (
            self.runbook_match_score * weights["runbook"] +
            self.alert_pattern_score * weights["pattern"] +
            self.historical_success_score * weights["history"] +
            self.context_relevance_score * weights["context"]
        )
        
        # Apply evidence boosts/penalties
        for ev in self.evidence:
            self.score += ev.confidence_contribution * 0.1
        
        self.score = max(0, min(100, self.score))
        self.level = ConfidenceLevel.from_score(self.score)
    
    def to_summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"Confidence: {self.score:.1f}% ({self.level.value})",
            "",
            "Reasoning:",
            self.reasoning,
            "",
            "Component Scores:",
            f"  - Runbook Match: {self.runbook_match_score:.1f}%",
            f"  - Alert Pattern: {self.alert_pattern_score:.1f}%",
            f"  - Historical Success: {self.historical_success_score:.1f}%",
            f"  - Context Relevance: {self.context_relevance_score:.1f}%",
        ]
        
        if self.positive_factors:
            lines.extend(["", "Positive Factors:"])
            for f in self.positive_factors:
                lines.append(f"  ✓ {f}")
        
        if self.negative_factors:
            lines.extend(["", "Concerns:"])
            for f in self.negative_factors:
                lines.append(f"  ⚠ {f}")
        
        if self.uncertainties:
            lines.extend(["", "Uncertainties:"])
            for u in self.uncertainties:
                lines.append(f"  ? {u}")
        
        if self.evidence:
            lines.extend(["", f"Evidence ({len(self.evidence)} items):"])
            for ev in self.evidence[:5]:
                lines.append(f"  - [{ev.type.value}] {ev.summary}")
        
        return "\n".join(lines)


class ConfidenceCalculator:
    """
    Calculates confidence scores for AI decisions.
    
    Integrates:
    - Runbook matching
    - Alert pattern recognition
    - Historical success rates
    """
    
    def __init__(
        self,
        history_store_path: Path | None = None,
    ):
        self.history_store_path = history_store_path
        self._history_cache: dict[str, HistoricalOutcome] = {}
        self._load_history()
    
    def _load_history(self) -> None:
        """Load historical outcomes from storage."""
        if self.history_store_path and self.history_store_path.exists():
            try:
                data = json.loads(self.history_store_path.read_text())
                for key, value in data.items():
                    self._history_cache[key] = HistoricalOutcome(**value)
                logger.info(f"Loaded {len(self._history_cache)} historical outcomes")
            except Exception as e:
                logger.warning(f"Failed to load history: {e}")
    
    def _save_history(self) -> None:
        """Save historical outcomes to storage."""
        if self.history_store_path:
            try:
                data = {k: v.model_dump() for k, v in self._history_cache.items()}
                self.history_store_path.parent.mkdir(parents=True, exist_ok=True)
                self.history_store_path.write_text(json.dumps(data, default=str, indent=2))
            except Exception as e:
                logger.warning(f"Failed to save history: {e}")
    
    def _get_history_key(self, action_type: str, alert_name: str) -> str:
        """Generate a consistent key for historical lookups."""
        combined = f"{action_type}:{alert_name}".lower()
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
    
    def calculate_runbook_match(
        self,
        alert_name: str,
        alert_description: str,
        alert_labels: dict[str, str],
        runbook_content: str,
        runbook_metadata: dict[str, Any],
    ) -> RunbookMatchScore:
        """Calculate how well a runbook matches the alert context."""
        score = RunbookMatchScore(
            runbook_id=runbook_metadata.get("id", ""),
            runbook_name=runbook_metadata.get("name", ""),
        )
        
        # Alert name match
        runbook_alerts = runbook_metadata.get("alerts", [])
        if alert_name in runbook_alerts:
            score.alert_name_match = 1.0
            score.match_factors.append(f"Runbook explicitly handles '{alert_name}'")
        elif any(alert_name.lower() in a.lower() for a in runbook_alerts):
            score.alert_name_match = 0.7
            score.match_factors.append("Alert name partially matches runbook")
        
        # Symptom match - check if alert description keywords in runbook
        alert_keywords = set(alert_description.lower().split())
        runbook_lower = runbook_content.lower()
        matched_keywords = [k for k in alert_keywords if k in runbook_lower and len(k) > 4]
        if matched_keywords:
            score.symptom_match = min(1.0, len(matched_keywords) / 5)
            score.match_factors.append(f"Matched symptoms: {', '.join(matched_keywords[:5])}")
        
        # Context match - labels
        runbook_labels = runbook_metadata.get("labels", {})
        label_matches = sum(1 for k, v in alert_labels.items() 
                          if runbook_labels.get(k) == v)
        if label_matches:
            score.context_match = min(1.0, label_matches / 3)
            score.match_factors.append(f"Matched {label_matches} labels")
        
        # Keyword match
        important_keywords = ["restart", "scale", "rollback", "drain", "delete", 
                           "memory", "cpu", "disk", "network", "timeout"]
        content_combined = f"{alert_description} {json.dumps(alert_labels)}".lower()
        for kw in important_keywords:
            if kw in content_combined and kw in runbook_lower:
                score.keyword_match += 0.2
        score.keyword_match = min(1.0, score.keyword_match)
        
        score.calculate_overall()
        return score
    
    def calculate_pattern_score(
        self,
        alert_name: str,
        alert_labels: dict[str, str],
        similar_alerts: list[dict[str, Any]],
    ) -> float:
        """Calculate confidence from alert pattern recognition."""
        if not similar_alerts:
            return 30.0  # Base score with no pattern data
        
        score = 30.0
        
        # Check how many similar alerts were resolved successfully
        resolved = [a for a in similar_alerts if a.get("resolved", False)]
        if resolved:
            resolution_rate = len(resolved) / len(similar_alerts)
            score += resolution_rate * 40  # Up to 40 points
        
        # Check consistency of resolutions
        resolution_types = [a.get("resolution_type") for a in resolved if a.get("resolution_type")]
        if resolution_types:
            most_common = max(set(resolution_types), key=resolution_types.count)
            consistency = resolution_types.count(most_common) / len(resolution_types)
            score += consistency * 20  # Up to 20 points
        
        # Recent patterns more valuable
        recent = [a for a in similar_alerts if a.get("days_ago", 999) < 7]
        if recent:
            score += min(10, len(recent) * 2)  # Up to 10 points
        
        return min(100, score)
    
    def get_historical_score(
        self,
        action_type: str,
        alert_name: str,
    ) -> tuple[float, HistoricalOutcome | None]:
        """Get confidence boost from historical success."""
        key = self._get_history_key(action_type, alert_name)
        outcome = self._history_cache.get(key)
        
        if outcome:
            return outcome.confidence_boost, outcome
        
        return 0.0, None
    
    def record_outcome(
        self,
        action_type: str,
        alert_name: str,
        success: bool,
        resolution_time_seconds: float | None = None,
    ) -> None:
        """Record an action outcome for future confidence calculations."""
        key = self._get_history_key(action_type, alert_name)
        
        if key not in self._history_cache:
            self._history_cache[key] = HistoricalOutcome(
                action_type=action_type,
                alert_pattern=alert_name,
            )
        
        outcome = self._history_cache[key]
        outcome.total_executions += 1
        if success:
            outcome.successful_executions += 1
        else:
            outcome.failed_executions += 1
        
        outcome.last_execution = datetime.now(timezone.utc)
        
        if resolution_time_seconds:
            # Running average
            if outcome.avg_resolution_time_seconds > 0:
                outcome.avg_resolution_time_seconds = (
                    outcome.avg_resolution_time_seconds * 0.8 +
                    resolution_time_seconds * 0.2
                )
            else:
                outcome.avg_resolution_time_seconds = resolution_time_seconds
        
        self._save_history()
        logger.info(f"Recorded outcome for {action_type}:{alert_name} - success={success}")
    
    def calculate(
        self,
        action_type: str,
        alert_name: str,
        alert_description: str,
        alert_labels: dict[str, str],
        reasoning: str,
        runbook_match: RunbookMatchScore | None = None,
        similar_alerts: list[dict[str, Any]] | None = None,
        additional_evidence: list[Evidence] | None = None,
        model_used: str = "",
    ) -> ConfidenceScore:
        """
        Calculate comprehensive confidence score.
        
        Args:
            action_type: Type of action being proposed
            alert_name: Name of the triggering alert
            alert_description: Alert description
            alert_labels: Alert labels
            reasoning: LLM-provided reasoning
            runbook_match: Runbook match score if available
            similar_alerts: Historical similar alerts
            additional_evidence: Extra evidence pieces
            model_used: LLM model used for decision
            
        Returns:
            Complete ConfidenceScore
        """
        confidence = ConfidenceScore(
            score=50.0,  # Base score
            reasoning=reasoning,
            model_used=model_used,
        )
        
        # Runbook match score
        if runbook_match:
            confidence.runbook_match_score = runbook_match.overall_score * 100
            confidence.positive_factors.extend(runbook_match.match_factors)
            confidence.negative_factors.extend(runbook_match.mismatch_factors)
            
            confidence.add_evidence(Evidence(
                type=EvidenceType.RUNBOOK_MATCH,
                source=runbook_match.runbook_name,
                summary=f"Runbook match: {runbook_match.overall_score*100:.0f}%",
                data=runbook_match.model_dump(),
                confidence_contribution=runbook_match.overall_score * 30,
            ))
        else:
            confidence.uncertainties.append("No matching runbook found")
        
        # Pattern score
        if similar_alerts:
            confidence.alert_pattern_score = self.calculate_pattern_score(
                alert_name, alert_labels, similar_alerts
            )
            confidence.add_evidence(Evidence(
                type=EvidenceType.ALERT_PATTERN,
                source="historical_alerts",
                summary=f"Found {len(similar_alerts)} similar historical alerts",
                data={"count": len(similar_alerts)},
                confidence_contribution=min(20, len(similar_alerts) * 2),
            ))
        else:
            confidence.alert_pattern_score = 30.0
            confidence.uncertainties.append("No similar historical alerts found")
        
        # Historical success
        hist_boost, outcome = self.get_historical_score(action_type, alert_name)
        if outcome:
            confidence.historical_success_score = hist_boost * 4  # Scale to 0-100
            confidence.positive_factors.append(
                f"Historical success rate: {outcome.success_rate*100:.0f}% "
                f"({outcome.total_executions} executions)"
            )
            confidence.add_evidence(Evidence(
                type=EvidenceType.HISTORICAL_SUCCESS,
                source="outcome_history",
                summary=f"Success rate: {outcome.success_rate*100:.0f}%",
                data=outcome.model_dump(),
                confidence_contribution=hist_boost,
            ))
        else:
            confidence.historical_success_score = 50.0
            confidence.uncertainties.append("No historical data for this action type")
        
        # Context relevance (basic)
        confidence.context_relevance_score = 60.0  # Default
        if alert_labels.get("severity") in ["critical", "high"]:
            confidence.context_relevance_score += 10
            confidence.positive_factors.append("High severity alert - action urgency justified")
        if alert_labels.get("env") in ["production", "prod"]:
            confidence.context_relevance_score += 10
            confidence.positive_factors.append("Production environment - appropriate attention")
        
        # Add LLM reasoning as evidence
        confidence.add_evidence(Evidence(
            type=EvidenceType.LLM_REASONING,
            source=model_used or "llm",
            summary="AI analysis and reasoning",
            data={"reasoning": reasoning},
            confidence_contribution=10,
        ))
        
        # Add any additional evidence
        if additional_evidence:
            for ev in additional_evidence:
                confidence.add_evidence(ev)
        
        # Recalculate final score
        confidence._recalculate()
        
        # Extract reasoning steps
        confidence.reasoning_steps = [
            f"Analyzed alert: {alert_name}",
            f"Runbook match: {confidence.runbook_match_score:.0f}%",
            f"Pattern recognition: {confidence.alert_pattern_score:.0f}%", 
            f"Historical success: {confidence.historical_success_score:.0f}%",
            f"Final confidence: {confidence.score:.0f}%",
        ]
        
        logger.info(
            f"Calculated confidence for {action_type}: {confidence.score:.1f}% "
            f"({confidence.level.value})"
        )
        
        return confidence


# Singleton calculator instance
_calculator: ConfidenceCalculator | None = None


def get_calculator(history_path: Path | None = None) -> ConfidenceCalculator:
    """Get or create the confidence calculator."""
    global _calculator
    if _calculator is None:
        default_path = Path.home() / ".autosre" / "confidence_history.json"
        _calculator = ConfidenceCalculator(history_path or default_path)
    return _calculator
