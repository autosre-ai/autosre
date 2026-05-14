"""Hypothesis ranking for root cause analysis."""

from datetime import datetime
from typing import Any, Optional, List, Dict, Tuple
from enum import Enum

import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from autosre.models.common import utc_now, generate_id
from autosre.ml.rca.evidence_collector import Evidence, EvidenceType


class HypothesisType(str, Enum):
    """Type of root cause hypothesis."""
    SERVICE_FAILURE = "service_failure"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    CONFIGURATION_ERROR = "configuration_error"
    DEPLOYMENT_ISSUE = "deployment_issue"
    DEPENDENCY_FAILURE = "dependency_failure"
    NETWORK_ISSUE = "network_issue"
    DATA_ISSUE = "data_issue"
    SECURITY_INCIDENT = "security_incident"
    CAPACITY_ISSUE = "capacity_issue"
    EXTERNAL_ISSUE = "external_issue"


class HypothesisStatus(str, Enum):
    """Status of a hypothesis."""
    PROPOSED = "proposed"
    INVESTIGATING = "investigating"
    SUPPORTED = "supported"
    REFUTED = "refuted"
    CONFIRMED = "confirmed"


class RankedHypothesis(BaseModel):
    """A ranked hypothesis for root cause."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    hypothesis_id: str = Field(default_factory=generate_id)
    
    # What
    title: str = Field(..., min_length=1)
    description: str = Field(default="")
    hypothesis_type: HypothesisType = Field(default=HypothesisType.SERVICE_FAILURE)
    
    # Status
    status: HypothesisStatus = Field(default=HypothesisStatus.PROPOSED)
    
    # Target
    component: str = Field(default="")
    service: str = Field(default="")
    
    # Scoring
    prior_probability: float = Field(default=0.5, ge=0.0, le=1.0)
    posterior_probability: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    rank: int = Field(default=0, ge=0)
    
    # Evidence
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    neutral_evidence: list[str] = Field(default_factory=list)
    
    # Scores breakdown
    evidence_score: float = Field(default=0.0)
    temporal_score: float = Field(default=0.0)
    topological_score: float = Field(default=0.0)
    historical_score: float = Field(default=0.0)
    
    # Tests
    tests_to_validate: list[str] = Field(default_factory=list)
    tests_completed: list[str] = Field(default_factory=list)
    
    # Metadata
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class HypothesisRanker:
    """Rank root cause hypotheses based on evidence.
    
    Uses multiple signals to rank hypotheses:
    - Evidence support/contradiction
    - Temporal proximity
    - Topological distance
    - Historical frequency
    - Bayesian updating
    """
    
    def __init__(
        self,
        prior_weight: float = 0.2,
        evidence_weight: float = 0.4,
        temporal_weight: float = 0.2,
        topological_weight: float = 0.1,
        historical_weight: float = 0.1,
    ):
        """Initialize the hypothesis ranker.
        
        Args:
            prior_weight: Weight for prior probability
            evidence_weight: Weight for evidence score
            temporal_weight: Weight for temporal score
            topological_weight: Weight for topological score
            historical_weight: Weight for historical score
        """
        self.prior_weight = prior_weight
        self.evidence_weight = evidence_weight
        self.temporal_weight = temporal_weight
        self.topological_weight = topological_weight
        self.historical_weight = historical_weight
        
        self._hypotheses: Dict[str, RankedHypothesis] = {}
        self._evidence_store: Dict[str, Evidence] = {}
        
        # Historical data
        self._hypothesis_counts: Dict[HypothesisType, int] = {}
        self._component_counts: Dict[str, int] = {}
    
    def add_hypothesis(
        self,
        title: str,
        hypothesis_type: HypothesisType,
        component: str = "",
        service: str = "",
        description: str = "",
        prior_probability: Optional[float] = None,
    ) -> RankedHypothesis:
        """Add a hypothesis to rank.
        
        Args:
            title: Hypothesis title
            hypothesis_type: Type of hypothesis
            component: Target component
            service: Target service
            description: Description
            prior_probability: Prior probability (if known)
            
        Returns:
            Created hypothesis
        """
        # Calculate prior if not provided
        if prior_probability is None:
            prior_probability = self._calculate_prior(hypothesis_type, component)
        
        hypothesis = RankedHypothesis(
            title=title,
            description=description,
            hypothesis_type=hypothesis_type,
            component=component,
            service=service,
            prior_probability=prior_probability,
            posterior_probability=prior_probability,
        )
        
        self._hypotheses[hypothesis.hypothesis_id] = hypothesis
        return hypothesis
    
    def _calculate_prior(
        self,
        hypothesis_type: HypothesisType,
        component: str,
    ) -> float:
        """Calculate prior probability from historical data.
        
        Args:
            hypothesis_type: Type of hypothesis
            component: Target component
            
        Returns:
            Prior probability
        """
        # Base priors for each type
        base_priors = {
            HypothesisType.SERVICE_FAILURE: 0.2,
            HypothesisType.RESOURCE_EXHAUSTION: 0.15,
            HypothesisType.CONFIGURATION_ERROR: 0.12,
            HypothesisType.DEPLOYMENT_ISSUE: 0.12,
            HypothesisType.DEPENDENCY_FAILURE: 0.1,
            HypothesisType.NETWORK_ISSUE: 0.08,
            HypothesisType.DATA_ISSUE: 0.08,
            HypothesisType.SECURITY_INCIDENT: 0.05,
            HypothesisType.CAPACITY_ISSUE: 0.05,
            HypothesisType.EXTERNAL_ISSUE: 0.05,
        }
        
        base_prior = base_priors.get(hypothesis_type, 0.1)
        
        # Adjust based on historical counts
        total_count = sum(self._hypothesis_counts.values()) + 1
        type_count = self._hypothesis_counts.get(hypothesis_type, 0)
        
        if total_count > 10:
            historical_prior = type_count / total_count
            base_prior = (base_prior + historical_prior) / 2
        
        # Adjust based on component history
        if component and component in self._component_counts:
            component_factor = min(self._component_counts[component] / 10, 1.0)
            base_prior = base_prior * (1 + 0.3 * component_factor)
        
        return min(base_prior, 0.9)  # Cap at 0.9
    
    def add_evidence(
        self,
        hypothesis_id: str,
        evidence: Evidence,
    ) -> None:
        """Add evidence for a hypothesis.
        
        Args:
            hypothesis_id: ID of hypothesis
            evidence: Evidence to add
        """
        if hypothesis_id not in self._hypotheses:
            return
        
        hypothesis = self._hypotheses[hypothesis_id]
        self._evidence_store[evidence.evidence_id] = evidence
        
        if evidence.supports_hypothesis:
            hypothesis.supporting_evidence.append(evidence.evidence_id)
        elif evidence.supports_hypothesis is False:
            hypothesis.contradicting_evidence.append(evidence.evidence_id)
        else:
            hypothesis.neutral_evidence.append(evidence.evidence_id)
        
        hypothesis.updated_at = utc_now()
    
    def add_evidence_batch(
        self,
        hypothesis_id: str,
        evidence_list: List[Evidence],
    ) -> None:
        """Add multiple pieces of evidence.
        
        Args:
            hypothesis_id: ID of hypothesis
            evidence_list: List of evidence
        """
        for evidence in evidence_list:
            self.add_evidence(hypothesis_id, evidence)
    
    def rank(self) -> List[RankedHypothesis]:
        """Rank all hypotheses.
        
        Returns:
            List of hypotheses ranked by probability
        """
        for hypothesis in self._hypotheses.values():
            self._score_hypothesis(hypothesis)
        
        # Sort by posterior probability
        ranked = list(self._hypotheses.values())
        ranked.sort(key=lambda h: h.posterior_probability, reverse=True)
        
        # Update ranks
        for i, hypothesis in enumerate(ranked):
            hypothesis.rank = i + 1
        
        return ranked
    
    def _score_hypothesis(self, hypothesis: RankedHypothesis) -> None:
        """Calculate scores for a hypothesis.
        
        Args:
            hypothesis: Hypothesis to score
        """
        # Evidence score
        hypothesis.evidence_score = self._calculate_evidence_score(hypothesis)
        
        # Temporal score (placeholder - would need incident timeline)
        hypothesis.temporal_score = 0.5  # Neutral if no data
        
        # Topological score (placeholder - would need dependency graph)
        hypothesis.topological_score = 0.5
        
        # Historical score
        hypothesis.historical_score = self._calculate_historical_score(hypothesis)
        
        # Combined posterior using weighted average
        posterior = (
            self.prior_weight * hypothesis.prior_probability +
            self.evidence_weight * hypothesis.evidence_score +
            self.temporal_weight * hypothesis.temporal_score +
            self.topological_weight * hypothesis.topological_score +
            self.historical_weight * hypothesis.historical_score
        )
        
        hypothesis.posterior_probability = min(max(posterior, 0.01), 0.99)
        
        # Confidence based on evidence quantity
        total_evidence = (
            len(hypothesis.supporting_evidence) +
            len(hypothesis.contradicting_evidence)
        )
        hypothesis.confidence = min(total_evidence / 10, 1.0)
        
        # Update status
        if hypothesis.posterior_probability >= 0.8:
            hypothesis.status = HypothesisStatus.SUPPORTED
        elif hypothesis.posterior_probability <= 0.2:
            hypothesis.status = HypothesisStatus.REFUTED
        elif total_evidence > 0:
            hypothesis.status = HypothesisStatus.INVESTIGATING
    
    def _calculate_evidence_score(
        self,
        hypothesis: RankedHypothesis,
    ) -> float:
        """Calculate score based on evidence.
        
        Args:
            hypothesis: Hypothesis to score
            
        Returns:
            Evidence score
        """
        supporting = []
        for eid in hypothesis.supporting_evidence:
            if eid in self._evidence_store:
                supporting.append(self._evidence_store[eid])
        
        contradicting = []
        for eid in hypothesis.contradicting_evidence:
            if eid in self._evidence_store:
                contradicting.append(self._evidence_store[eid])
        
        if not supporting and not contradicting:
            return 0.5  # Neutral
        
        # Weighted sum of evidence
        support_score = sum(e.confidence for e in supporting)
        contradict_score = sum(e.confidence for e in contradicting)
        
        total = support_score + contradict_score
        if total == 0:
            return 0.5
        
        return support_score / total
    
    def _calculate_historical_score(
        self,
        hypothesis: RankedHypothesis,
    ) -> float:
        """Calculate score based on historical data.
        
        Args:
            hypothesis: Hypothesis to score
            
        Returns:
            Historical score
        """
        # Base score
        score = 0.5
        
        # Adjust based on type frequency
        type_count = self._hypothesis_counts.get(hypothesis.hypothesis_type, 0)
        total_count = sum(self._hypothesis_counts.values()) + 1
        
        if total_count > 5:
            type_freq = type_count / total_count
            score = 0.3 + 0.4 * type_freq
        
        # Adjust based on component frequency
        if hypothesis.component:
            comp_count = self._component_counts.get(hypothesis.component, 0)
            if comp_count > 0:
                score = min(score * 1.2, 0.9)
        
        return score
    
    def update_with_test_result(
        self,
        hypothesis_id: str,
        test_name: str,
        passed: bool,
        confidence: float = 0.9,
    ) -> None:
        """Update hypothesis with test result.
        
        Args:
            hypothesis_id: ID of hypothesis
            test_name: Name of test performed
            passed: Whether test supports hypothesis
            confidence: Confidence in test result
        """
        if hypothesis_id not in self._hypotheses:
            return
        
        hypothesis = self._hypotheses[hypothesis_id]
        hypothesis.tests_completed.append(test_name)
        
        # Create evidence from test
        evidence = Evidence(
            evidence_type=EvidenceType.TEST,
            source=f"test:{test_name}",
            description=f"Test '{test_name}' {'passed' if passed else 'failed'}",
            confidence=confidence,
            supports_hypothesis=passed,
        )
        
        self.add_evidence(hypothesis_id, evidence)
        
        # Re-score
        self._score_hypothesis(hypothesis)
    
    def bayesian_update(
        self,
        hypothesis_id: str,
        likelihood_given_true: float,
        likelihood_given_false: float,
    ) -> float:
        """Perform Bayesian update on hypothesis probability.
        
        Args:
            hypothesis_id: ID of hypothesis
            likelihood_given_true: P(evidence | hypothesis true)
            likelihood_given_false: P(evidence | hypothesis false)
            
        Returns:
            Updated posterior probability
        """
        if hypothesis_id not in self._hypotheses:
            return 0.0
        
        hypothesis = self._hypotheses[hypothesis_id]
        prior = hypothesis.posterior_probability
        
        # Bayes theorem
        numerator = likelihood_given_true * prior
        denominator = numerator + likelihood_given_false * (1 - prior)
        
        if denominator == 0:
            return prior
        
        posterior = numerator / denominator
        hypothesis.posterior_probability = min(max(posterior, 0.01), 0.99)
        hypothesis.updated_at = utc_now()
        
        return hypothesis.posterior_probability
    
    def confirm_hypothesis(self, hypothesis_id: str) -> None:
        """Mark a hypothesis as confirmed.
        
        Args:
            hypothesis_id: ID of hypothesis
        """
        if hypothesis_id not in self._hypotheses:
            return
        
        hypothesis = self._hypotheses[hypothesis_id]
        hypothesis.status = HypothesisStatus.CONFIRMED
        hypothesis.posterior_probability = 1.0
        hypothesis.confidence = 1.0
        
        # Update historical counts
        self._hypothesis_counts[hypothesis.hypothesis_type] = (
            self._hypothesis_counts.get(hypothesis.hypothesis_type, 0) + 1
        )
        
        if hypothesis.component:
            self._component_counts[hypothesis.component] = (
                self._component_counts.get(hypothesis.component, 0) + 1
            )
    
    def refute_hypothesis(self, hypothesis_id: str) -> None:
        """Mark a hypothesis as refuted.
        
        Args:
            hypothesis_id: ID of hypothesis
        """
        if hypothesis_id not in self._hypotheses:
            return
        
        hypothesis = self._hypotheses[hypothesis_id]
        hypothesis.status = HypothesisStatus.REFUTED
        hypothesis.posterior_probability = 0.0
    
    def get_top_hypotheses(self, k: int = 3) -> List[RankedHypothesis]:
        """Get top k hypotheses.
        
        Args:
            k: Number of hypotheses to return
            
        Returns:
            Top k hypotheses
        """
        ranked = self.rank()
        return ranked[:k]
    
    def get_tests_needed(self) -> Dict[str, List[str]]:
        """Get tests needed for each hypothesis.
        
        Returns:
            Dictionary of hypothesis_id -> tests needed
        """
        tests_needed = {}
        
        for hypothesis_id, hypothesis in self._hypotheses.items():
            remaining_tests = [
                t for t in hypothesis.tests_to_validate
                if t not in hypothesis.tests_completed
            ]
            
            if remaining_tests:
                tests_needed[hypothesis_id] = remaining_tests
        
        return tests_needed
    
    def suggest_tests(
        self,
        hypothesis_id: str,
    ) -> List[str]:
        """Suggest tests to validate a hypothesis.
        
        Args:
            hypothesis_id: ID of hypothesis
            
        Returns:
            List of suggested tests
        """
        if hypothesis_id not in self._hypotheses:
            return []
        
        hypothesis = self._hypotheses[hypothesis_id]
        tests = []
        
        # Suggest tests based on type
        type_tests = {
            HypothesisType.SERVICE_FAILURE: [
                "Check service health endpoints",
                "Review service logs for errors",
                "Verify service process is running",
            ],
            HypothesisType.RESOURCE_EXHAUSTION: [
                "Check CPU utilization",
                "Check memory usage",
                "Check disk space",
            ],
            HypothesisType.CONFIGURATION_ERROR: [
                "Compare current config with known-good",
                "Check recent config changes",
                "Validate config syntax",
            ],
            HypothesisType.DEPLOYMENT_ISSUE: [
                "Check recent deployments",
                "Compare with previous version",
                "Verify rollback availability",
            ],
            HypothesisType.DEPENDENCY_FAILURE: [
                "Check upstream service health",
                "Verify network connectivity",
                "Test dependency endpoints",
            ],
            HypothesisType.NETWORK_ISSUE: [
                "Run network connectivity tests",
                "Check DNS resolution",
                "Verify firewall rules",
            ],
        }
        
        tests = type_tests.get(hypothesis.hypothesis_type, [
            "Gather additional metrics",
            "Review related logs",
        ])
        
        # Filter out completed tests
        tests = [t for t in tests if t not in hypothesis.tests_completed]
        
        hypothesis.tests_to_validate = list(set(hypothesis.tests_to_validate + tests))
        
        return tests
    
    def get_hypothesis(self, hypothesis_id: str) -> Optional[RankedHypothesis]:
        """Get a hypothesis by ID.
        
        Args:
            hypothesis_id: ID of hypothesis
            
        Returns:
            Hypothesis or None
        """
        return self._hypotheses.get(hypothesis_id)
    
    def summarize(self) -> Dict[str, Any]:
        """Get summary of hypothesis ranking.
        
        Returns:
            Summary dictionary
        """
        ranked = self.rank()
        
        return {
            "total_hypotheses": len(self._hypotheses),
            "top_hypothesis": ranked[0].title if ranked else None,
            "top_probability": ranked[0].posterior_probability if ranked else 0,
            "supported_count": sum(
                1 for h in self._hypotheses.values()
                if h.status == HypothesisStatus.SUPPORTED
            ),
            "refuted_count": sum(
                1 for h in self._hypotheses.values()
                if h.status == HypothesisStatus.REFUTED
            ),
            "total_evidence": sum(
                len(h.supporting_evidence) + len(h.contradicting_evidence)
                for h in self._hypotheses.values()
            ),
        }
    
    def clear(self) -> None:
        """Clear all hypotheses."""
        self._hypotheses.clear()
        self._evidence_store.clear()
