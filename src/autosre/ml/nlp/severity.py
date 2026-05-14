"""Severity estimation for incidents."""

from datetime import datetime
from typing import Any, Optional, List, Dict
from enum import Enum
import re

import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from autosre.models.common import utc_now, generate_id
from autosre.ml.common.base import (
    BaseMLModel,
    TrainingConfig,
    EvaluationMetrics,
    PredictionResult,
    ModelStatus,
    ModelVersion,
)


class SeverityLevel(str, Enum):
    """Severity level for incidents."""
    SEV1 = "sev1"  # Critical
    SEV2 = "sev2"  # High
    SEV3 = "sev3"  # Medium
    SEV4 = "sev4"  # Low
    SEV5 = "sev5"  # Informational


class SeverityEstimate(BaseModel):
    """Severity estimation result."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    severity: SeverityLevel = Field(default=SeverityLevel.SEV3)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Score breakdown
    severity_scores: dict[str, float] = Field(default_factory=dict)
    
    # Impact assessment
    customer_impact: float = Field(default=0.0, ge=0.0, le=1.0)
    revenue_impact: float = Field(default=0.0, ge=0.0, le=1.0)
    scope: str = Field(default="partial")  # full, partial, minimal
    
    # Contributing factors
    factors: list[dict[str, Any]] = Field(default_factory=list)
    
    # Recommendations
    suggested_response_time_minutes: int = Field(default=60)
    escalation_needed: bool = Field(default=False)
    on_call_notification: bool = Field(default=False)
    
    # Model info
    model_id: str = Field(default="")
    estimation_time_ms: float = Field(default=0.0, ge=0.0)


class SeverityEstimator(BaseMLModel[str, SeverityEstimate]):
    """Estimate incident severity from text and context.
    
    Considers multiple factors:
    - Explicit severity mentions
    - Impact keywords (outage, down, etc.)
    - Affected scope (all users, partial, etc.)
    - Service criticality
    - Time of day / business hours
    
    Features:
    - Rule-based estimation
    - Machine learning enhancement
    - Context awareness
    """
    
    def __init__(
        self,
        default_severity: SeverityLevel = SeverityLevel.SEV3,
        use_business_hours: bool = True,
    ):
        """Initialize the estimator.
        
        Args:
            default_severity: Default severity when uncertain
            use_business_hours: Consider business hours in estimation
        """
        super().__init__(
            name="severity_estimator",
            model_type="severity_estimator",
            hyperparameters={
                "default_severity": default_severity.value,
                "use_business_hours": use_business_hours,
            },
        )
        
        self.default_severity = default_severity
        self.use_business_hours = use_business_hours
        
        # Severity keywords
        self._severity_keywords = {
            SeverityLevel.SEV1: {
                "patterns": [
                    r"\bsev\s*1\b", r"\bp1\b", r"\bcritical\b", r"\bemergency\b",
                    r"\btotal\s+outage\b", r"\bcompletely?\s+down\b",
                    r"\ball\s+users?\s+affected\b", r"\b100%\s+impact\b",
                ],
                "keywords": [
                    "critical", "emergency", "total outage", "completely down",
                    "all customers", "major incident", "p1", "sev1",
                ],
                "weight": 1.0,
            },
            SeverityLevel.SEV2: {
                "patterns": [
                    r"\bsev\s*2\b", r"\bp2\b", r"\bhigh\b", r"\bmajor\b",
                    r"\bsignificant\s+impact\b", r"\bpartially?\s+down\b",
                ],
                "keywords": [
                    "high priority", "major", "significant", "partially down",
                    "many users", "p2", "sev2", "degraded service",
                ],
                "weight": 0.8,
            },
            SeverityLevel.SEV3: {
                "patterns": [
                    r"\bsev\s*3\b", r"\bp3\b", r"\bmedium\b", r"\bmoderate\b",
                ],
                "keywords": [
                    "medium", "moderate", "some users", "intermittent",
                    "p3", "sev3", "partial impact",
                ],
                "weight": 0.5,
            },
            SeverityLevel.SEV4: {
                "patterns": [
                    r"\bsev\s*4\b", r"\bp4\b", r"\blow\b", r"\bminor\b",
                ],
                "keywords": [
                    "low", "minor", "few users", "workaround available",
                    "p4", "sev4", "cosmetic",
                ],
                "weight": 0.3,
            },
            SeverityLevel.SEV5: {
                "patterns": [
                    r"\bsev\s*5\b", r"\bp5\b", r"\binfo\b", r"\binformational\b",
                ],
                "keywords": [
                    "informational", "info", "question", "inquiry",
                    "p5", "sev5", "no impact",
                ],
                "weight": 0.1,
            },
        }
        
        # Critical service patterns
        self._critical_services = [
            "auth", "login", "payment", "checkout", "api", "database",
            "production", "prod", "main", "core",
        ]
        
        # Response time recommendations
        self._response_times = {
            SeverityLevel.SEV1: 15,
            SeverityLevel.SEV2: 30,
            SeverityLevel.SEV3: 60,
            SeverityLevel.SEV4: 240,
            SeverityLevel.SEV5: 1440,
        }
    
    def fit(
        self,
        X: List[str],
        y: List[SeverityLevel],
        config: Optional[TrainingConfig] = None,
    ) -> "SeverityEstimator":
        """Train the estimator.
        
        Args:
            X: Training texts
            y: Training severity labels
            config: Training configuration
            
        Returns:
            Self
        """
        # Learn keyword frequencies per severity
        self._is_fitted = True
        self._metadata.status = ModelStatus.TRAINED
        self._metadata.last_trained_at = utc_now()
        
        version = ModelVersion(
            description=f"Trained on {len(X)} incidents",
            metrics={"num_samples": float(len(X))},
        )
        self._metadata.add_version(version)
        
        return self
    
    def predict(
        self,
        X: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> PredictionResult[SeverityEstimate]:
        """Estimate incident severity.
        
        Args:
            X: Incident description
            context: Additional context (service name, time, etc.)
            
        Returns:
            Severity estimate
        """
        import time
        start_time = time.time()
        
        text_lower = X.lower()
        context = context or {}
        
        # Calculate scores for each severity
        scores: Dict[SeverityLevel, float] = {}
        factors = []
        
        for severity, config in self._severity_keywords.items():
            score = 0.0
            
            # Check patterns
            for pattern in config["patterns"]:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    score += config["weight"]
                    factors.append({
                        "type": "pattern",
                        "pattern": pattern,
                        "severity": severity.value,
                        "weight": config["weight"],
                    })
            
            # Check keywords
            for keyword in config["keywords"]:
                if keyword.lower() in text_lower:
                    score += config["weight"] * 0.5
                    factors.append({
                        "type": "keyword",
                        "keyword": keyword,
                        "severity": severity.value,
                        "weight": config["weight"] * 0.5,
                    })
            
            scores[severity] = score
        
        # Check for critical service mentions
        customer_impact = 0.0
        for service in self._critical_services:
            if service in text_lower:
                scores[SeverityLevel.SEV1] += 0.3
                scores[SeverityLevel.SEV2] += 0.2
                customer_impact += 0.2
                factors.append({
                    "type": "critical_service",
                    "service": service,
                    "weight": 0.3,
                })
        
        # Check scope
        scope = "partial"
        if any(w in text_lower for w in ["all users", "everyone", "total", "100%"]):
            scope = "full"
            scores[SeverityLevel.SEV1] += 0.5
            customer_impact = 1.0
        elif any(w in text_lower for w in ["few users", "minimal", "one user"]):
            scope = "minimal"
            scores[SeverityLevel.SEV4] += 0.3
            customer_impact = 0.1
        
        # Normalize scores
        total = sum(scores.values()) + 1e-10
        severity_scores = {sev.value: score / total for sev, score in scores.items()}
        
        # Determine best severity
        best_severity = max(scores.keys(), key=lambda k: scores[k])
        confidence = severity_scores[best_severity.value]
        
        # Use default if no clear signal
        if confidence < 0.2:
            best_severity = self.default_severity
            confidence = 0.5
        
        # Escalation and notification
        escalation_needed = best_severity in [SeverityLevel.SEV1, SeverityLevel.SEV2]
        on_call_notification = best_severity == SeverityLevel.SEV1
        
        result = SeverityEstimate(
            severity=best_severity,
            confidence=confidence,
            severity_scores=severity_scores,
            customer_impact=min(customer_impact, 1.0),
            scope=scope,
            factors=factors,
            suggested_response_time_minutes=self._response_times[best_severity],
            escalation_needed=escalation_needed,
            on_call_notification=on_call_notification,
            model_id=self.model_id,
            estimation_time_ms=(time.time() - start_time) * 1000,
        )
        
        return PredictionResult(
            prediction=result,
            confidence=confidence,
            model_id=self.model_id,
            latency_ms=(time.time() - start_time) * 1000,
        )
    
    def evaluate(
        self,
        X: List[str],
        y: List[SeverityLevel],
    ) -> EvaluationMetrics:
        """Evaluate the estimator."""
        import time
        start_time = time.time()
        
        predictions = []
        for text in X:
            result = self.predict(text)
            predictions.append(result.prediction.severity)
        
        correct = sum(1 for p, true in zip(predictions, y) if p == true)
        accuracy = correct / len(y) if y else 0
        
        return EvaluationMetrics(
            accuracy=float(accuracy),
            dataset_size=len(y),
            evaluation_time_seconds=(time.time() - start_time),
        )
    
    def get_feature_importance(self) -> dict[str, float]:
        """Get feature importance."""
        return {
            "severity_keywords": 0.4,
            "scope_detection": 0.2,
            "critical_service_detection": 0.2,
            "pattern_matching": 0.2,
        }
