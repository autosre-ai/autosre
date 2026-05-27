"""
Alert Quality Validator for AutoSRE.

Ensures alerts meet quality standards before paging on-call.
Key principle: Pages must be clear failure, actionable, user-visible impact.
"""

from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime, timezone
from enum import Enum


class AlertSeverity(Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# Required fields for a high-quality alert
REQUIRED_ALERT_FIELDS = [
    "failure_mode",      # What specifically is broken?
    "user_impact",       # How are users affected?
    "action_required",   # What should on-call do?
    "severity",          # How urgent is this?
    "runbook_url",       # Where's the documentation?
]

# Field weights for quality score calculation
FIELD_WEIGHTS = {
    "failure_mode": 0.25,      # Most important - what's broken
    "user_impact": 0.25,       # Critical - why we care
    "action_required": 0.20,   # Actionable guidance
    "severity": 0.15,          # Prioritization
    "runbook_url": 0.15,       # Documentation
}

# Minimum fields required to page (4/5)
MIN_FIELDS_TO_PAGE = 4


@dataclass
class AlertQualityResult:
    """Result of alert quality validation."""
    
    is_valid: bool
    quality_score: float  # 0.0 to 1.0
    should_page: bool
    missing_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    field_scores: dict[str, float] = field(default_factory=dict)
    validated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "is_valid": self.is_valid,
            "quality_score": self.quality_score,
            "should_page": self.should_page,
            "missing_fields": self.missing_fields,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
            "field_scores": self.field_scores,
            "validated_at": self.validated_at.isoformat(),
        }


@dataclass
class AlertPayload:
    """Structured alert data for validation."""
    
    name: str
    failure_mode: Optional[str] = None
    user_impact: Optional[str] = None
    action_required: Optional[str] = None
    severity: Optional[str] = None
    runbook_url: Optional[str] = None
    
    # Optional enrichment fields
    service: Optional[str] = None
    environment: Optional[str] = None
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    labels: dict[str, str] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AlertPayload":
        """Create from dictionary."""
        return cls(
            name=data.get("name", data.get("alertname", "unknown")),
            failure_mode=data.get("failure_mode"),
            user_impact=data.get("user_impact"),
            action_required=data.get("action_required"),
            severity=data.get("severity"),
            runbook_url=data.get("runbook_url", data.get("runbook")),
            service=data.get("service"),
            environment=data.get("environment", data.get("env")),
            metric_value=data.get("metric_value", data.get("value")),
            threshold=data.get("threshold"),
            labels=data.get("labels", {}),
        )


class AlertQualityValidator:
    """
    Validates alert quality before allowing pages.
    
    Key principles:
    - Pages must have clear failure mode
    - Pages must be actionable
    - Pages must show user-visible impact
    - Reject alerts missing required fields
    """
    
    def __init__(
        self,
        min_quality_score: float = 0.6,
        require_runbook_for_critical: bool = True,
        strict_mode: bool = False,
    ):
        """
        Initialize validator.
        
        Args:
            min_quality_score: Minimum score to accept alert (0-1)
            require_runbook_for_critical: Require runbook for critical alerts
            strict_mode: Reject all alerts missing any required field
        """
        self.min_quality_score = min_quality_score
        self.require_runbook_for_critical = require_runbook_for_critical
        self.strict_mode = strict_mode
    
    def validate(self, alert: AlertPayload | dict[str, Any]) -> AlertQualityResult:
        """
        Validate an alert's quality.
        
        Args:
            alert: Alert payload (dict or AlertPayload)
            
        Returns:
            AlertQualityResult with validation details
        """
        if isinstance(alert, dict):
            alert = AlertPayload.from_dict(alert)
        
        missing_fields: list[str] = []
        warnings: list[str] = []
        suggestions: list[str] = []
        field_scores: dict[str, float] = {}
        
        # Check each required field
        for field_name in REQUIRED_ALERT_FIELDS:
            value = getattr(alert, field_name, None)
            
            if not value:
                missing_fields.append(field_name)
                field_scores[field_name] = 0.0
            else:
                # Score field quality based on content
                score = self._score_field(field_name, value)
                field_scores[field_name] = score
        
        # Calculate overall quality score
        quality_score = sum(
            field_scores.get(f, 0.0) * FIELD_WEIGHTS[f]
            for f in REQUIRED_ALERT_FIELDS
        )
        
        # Determine if alert should page
        fields_present = len(REQUIRED_ALERT_FIELDS) - len(missing_fields)
        should_page = (
            fields_present >= MIN_FIELDS_TO_PAGE and
            quality_score >= self.min_quality_score
        )
        
        # Additional validation rules
        if alert.severity == AlertSeverity.CRITICAL.value:
            if self.require_runbook_for_critical and not alert.runbook_url:
                warnings.append("Critical alerts should have runbook URLs")
                should_page = False
        
        # Generate suggestions for missing fields
        for field_name in missing_fields:
            suggestions.append(self._suggest_for_field(field_name, alert))
        
        # Low quality warnings
        for field_name, score in field_scores.items():
            if 0 < score < 0.5:
                warnings.append(f"Low quality {field_name}: consider more detail")
        
        # Strict mode rejects any missing required fields
        is_valid = (
            len(missing_fields) == 0 if self.strict_mode
            else quality_score >= self.min_quality_score
        )
        
        return AlertQualityResult(
            is_valid=is_valid,
            quality_score=quality_score,
            should_page=should_page,
            missing_fields=missing_fields,
            warnings=warnings,
            suggestions=suggestions,
            field_scores=field_scores,
        )
    
    def _score_field(self, field_name: str, value: str) -> float:
        """Score a field based on content quality (0-1)."""
        if not value:
            return 0.0
        
        value = str(value).strip()
        
        # Empty or placeholder values
        if not value or value.lower() in ("n/a", "none", "unknown", "-", "tbd"):
            return 0.0
        
        # Very short values are low quality
        if len(value) < 10:
            return 0.3
        
        # Field-specific scoring
        if field_name == "failure_mode":
            # Good failure modes are specific
            if any(word in value.lower() for word in ["increase", "decrease", "timeout", "error", "failed", "unavailable"]):
                return 1.0
            return 0.6
        
        elif field_name == "user_impact":
            # Good impact statements mention users or business
            if any(word in value.lower() for word in ["users", "customers", "revenue", "cannot", "unable", "degraded"]):
                return 1.0
            return 0.6
        
        elif field_name == "action_required":
            # Good actions are imperative
            if any(word in value.lower() for word in ["check", "restart", "scale", "investigate", "rollback", "contact"]):
                return 1.0
            return 0.6
        
        elif field_name == "severity":
            # Valid severity values
            valid_severities = [s.value for s in AlertSeverity]
            if value.lower() in valid_severities:
                return 1.0
            return 0.3
        
        elif field_name == "runbook_url":
            # Valid URLs
            if value.startswith(("http://", "https://", "runbook://")):
                return 1.0
            return 0.3
        
        return 0.5
    
    def _suggest_for_field(self, field_name: str, alert: AlertPayload) -> str:
        """Generate improvement suggestion for a missing field."""
        suggestions = {
            "failure_mode": f"Add failure_mode: What specifically is broken in '{alert.name}'?",
            "user_impact": "Add user_impact: How are end users affected by this issue?",
            "action_required": "Add action_required: What should on-call do first?",
            "severity": "Add severity: critical/high/medium/low based on user impact",
            "runbook_url": "Add runbook_url: Link to troubleshooting documentation",
        }
        return suggestions.get(field_name, f"Add missing field: {field_name}")
    
    def reject_reason(self, result: AlertQualityResult) -> Optional[str]:
        """
        Get human-readable rejection reason if alert is invalid.
        
        Args:
            result: Validation result
            
        Returns:
            Rejection reason or None if valid
        """
        if result.is_valid:
            return None
        
        reasons = []
        
        if result.missing_fields:
            reasons.append(f"Missing required fields: {', '.join(result.missing_fields)}")
        
        if result.quality_score < self.min_quality_score:
            reasons.append(
                f"Quality score {result.quality_score:.2f} below minimum {self.min_quality_score}"
            )
        
        return "; ".join(reasons) if reasons else "Alert quality validation failed"


def validate_alert(alert: dict[str, Any], strict: bool = False) -> AlertQualityResult:
    """
    Convenience function to validate an alert.
    
    Args:
        alert: Alert dictionary
        strict: Use strict mode
        
    Returns:
        Validation result
    """
    validator = AlertQualityValidator(strict_mode=strict)
    return validator.validate(alert)
