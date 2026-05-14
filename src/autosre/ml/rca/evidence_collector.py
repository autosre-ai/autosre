"""Evidence collection for root cause analysis."""

from datetime import datetime, timedelta
from typing import Any, Optional, List, Dict, Tuple
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict

from autosre.models.common import utc_now, generate_id


class EvidenceType(str, Enum):
    """Type of evidence."""
    METRIC = "metric"
    LOG = "log"
    TRACE = "trace"
    EVENT = "event"
    CONFIGURATION = "configuration"
    DEPLOYMENT = "deployment"
    ALERT = "alert"
    CORRELATION = "correlation"
    TEST = "test"
    MANUAL = "manual"


class EvidenceStrength(str, Enum):
    """Strength of evidence."""
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    CIRCUMSTANTIAL = "circumstantial"


class Evidence(BaseModel):
    """A piece of evidence for root cause analysis."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    evidence_id: str = Field(default_factory=generate_id)
    
    # Type and source
    evidence_type: EvidenceType = Field(default=EvidenceType.METRIC)
    source: str = Field(default="")
    
    # Content
    description: str = Field(default="")
    raw_data: dict[str, Any] = Field(default_factory=dict)
    
    # Support
    supports_hypothesis: Optional[bool] = None  # True = supports, False = contradicts, None = neutral
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    strength: EvidenceStrength = Field(default=EvidenceStrength.MODERATE)
    
    # Relevance
    relevance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    
    # Timing
    timestamp: datetime = Field(default_factory=utc_now)
    time_range_start: Optional[datetime] = None
    time_range_end: Optional[datetime] = None
    
    # Context
    component: str = Field(default="")
    service: str = Field(default="")
    labels: dict[str, str] = Field(default_factory=dict)
    
    # Metadata
    collected_at: datetime = Field(default_factory=utc_now)
    collection_method: str = Field(default="automatic")


class EvidenceQuery(BaseModel):
    """Query parameters for evidence collection."""
    model_config = ConfigDict(validate_assignment=True)
    
    component: str = Field(default="")
    service: str = Field(default="")
    
    evidence_types: list[EvidenceType] = Field(default_factory=list)
    
    time_range_start: Optional[datetime] = None
    time_range_end: Optional[datetime] = None
    
    keywords: list[str] = Field(default_factory=list)
    
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    limit: int = Field(default=100, ge=1, le=1000)


class EvidenceCollector:
    """Collect evidence for root cause analysis.
    
    Gathers evidence from multiple sources:
    - Metrics
    - Logs
    - Traces
    - Events
    - Configurations
    - Deployments
    - Alerts
    
    Evaluates evidence relevance and support for hypotheses.
    """
    
    def __init__(
        self,
        default_time_window_seconds: float = 3600.0,
        min_relevance: float = 0.3,
    ):
        """Initialize the evidence collector.
        
        Args:
            default_time_window_seconds: Default time window for evidence collection
            min_relevance: Minimum relevance to include evidence
        """
        self.default_time_window_seconds = default_time_window_seconds
        self.min_relevance = min_relevance
        
        self._evidence_store: Dict[str, Evidence] = {}
        
        # Collectors for different evidence types
        self._metric_patterns: List[Dict[str, Any]] = []
        self._log_patterns: List[Dict[str, Any]] = []
        self._known_events: List[Dict[str, Any]] = []
    
    def collect(
        self,
        component: str,
        symptoms: Optional[List[str]] = None,
        time_range: Optional[Tuple[datetime, datetime]] = None,
        evidence_types: Optional[List[EvidenceType]] = None,
    ) -> List[Evidence]:
        """Collect evidence related to a component and symptoms.
        
        Args:
            component: Component to investigate
            symptoms: Related symptoms
            time_range: Time range to search
            evidence_types: Types of evidence to collect
            
        Returns:
            List of collected evidence
        """
        symptoms = symptoms or []
        evidence_types = evidence_types or list(EvidenceType)
        
        # Default time range
        if time_range is None:
            end = utc_now()
            start = end - timedelta(seconds=self.default_time_window_seconds)
            time_range = (start, end)
        
        evidence = []
        
        # Collect from different sources
        if EvidenceType.METRIC in evidence_types:
            evidence.extend(self._collect_metric_evidence(component, symptoms, time_range))
        
        if EvidenceType.LOG in evidence_types:
            evidence.extend(self._collect_log_evidence(component, symptoms, time_range))
        
        if EvidenceType.EVENT in evidence_types:
            evidence.extend(self._collect_event_evidence(component, symptoms, time_range))
        
        if EvidenceType.DEPLOYMENT in evidence_types:
            evidence.extend(self._collect_deployment_evidence(component, time_range))
        
        if EvidenceType.CONFIGURATION in evidence_types:
            evidence.extend(self._collect_config_evidence(component, time_range))
        
        if EvidenceType.ALERT in evidence_types:
            evidence.extend(self._collect_alert_evidence(component, time_range))
        
        # Filter by relevance
        evidence = [e for e in evidence if e.relevance_score >= self.min_relevance]
        
        # Store evidence
        for e in evidence:
            self._evidence_store[e.evidence_id] = e
        
        return evidence
    
    def _collect_metric_evidence(
        self,
        component: str,
        symptoms: List[str],
        time_range: Tuple[datetime, datetime],
    ) -> List[Evidence]:
        """Collect metric-based evidence.
        
        Args:
            component: Component name
            symptoms: Symptoms to look for
            time_range: Time range
            
        Returns:
            List of evidence
        """
        evidence = []
        
        # Check for known metric patterns
        for pattern in self._metric_patterns:
            if pattern.get("component") == component or not pattern.get("component"):
                # Check if pattern matches symptoms
                pattern_symptoms = pattern.get("symptoms", [])
                if any(s in symptoms for s in pattern_symptoms) or not pattern_symptoms:
                    evidence.append(Evidence(
                        evidence_type=EvidenceType.METRIC,
                        source=f"metric:{pattern.get('metric_name', 'unknown')}",
                        description=pattern.get("description", "Metric anomaly detected"),
                        confidence=pattern.get("confidence", 0.7),
                        strength=EvidenceStrength.MODERATE,
                        relevance_score=0.7,
                        component=component,
                        supports_hypothesis=pattern.get("supports", True),
                        time_range_start=time_range[0],
                        time_range_end=time_range[1],
                    ))
        
        # Generate generic evidence based on symptoms
        symptom_metrics = {
            "high_cpu": ("CPU utilization above threshold", 0.8),
            "high_memory": ("Memory usage above threshold", 0.8),
            "high_latency": ("Latency spike detected", 0.7),
            "error_rate": ("Error rate increase detected", 0.9),
            "timeout": ("Request timeouts detected", 0.8),
        }
        
        for symptom in symptoms:
            for keyword, (desc, conf) in symptom_metrics.items():
                if keyword in symptom.lower():
                    evidence.append(Evidence(
                        evidence_type=EvidenceType.METRIC,
                        source=f"metric:{keyword}",
                        description=desc,
                        confidence=conf,
                        strength=EvidenceStrength.MODERATE,
                        relevance_score=0.8,
                        component=component,
                        supports_hypothesis=True,
                        time_range_start=time_range[0],
                        time_range_end=time_range[1],
                    ))
        
        return evidence
    
    def _collect_log_evidence(
        self,
        component: str,
        symptoms: List[str],
        time_range: Tuple[datetime, datetime],
    ) -> List[Evidence]:
        """Collect log-based evidence.
        
        Args:
            component: Component name
            symptoms: Symptoms to look for
            time_range: Time range
            
        Returns:
            List of evidence
        """
        evidence = []
        
        # Check for known log patterns
        for pattern in self._log_patterns:
            if pattern.get("component") == component or not pattern.get("component"):
                evidence.append(Evidence(
                    evidence_type=EvidenceType.LOG,
                    source=f"log:{pattern.get('pattern', 'unknown')}",
                    description=pattern.get("description", "Log pattern matched"),
                    confidence=pattern.get("confidence", 0.6),
                    strength=EvidenceStrength.MODERATE,
                    relevance_score=0.6,
                    component=component,
                    supports_hypothesis=pattern.get("supports", True),
                    time_range_start=time_range[0],
                    time_range_end=time_range[1],
                ))
        
        # Generate generic log evidence for symptoms
        if "error" in " ".join(symptoms).lower():
            evidence.append(Evidence(
                evidence_type=EvidenceType.LOG,
                source=f"log:{component}",
                description="Error messages found in logs",
                confidence=0.7,
                strength=EvidenceStrength.MODERATE,
                relevance_score=0.7,
                component=component,
                supports_hypothesis=True,
                time_range_start=time_range[0],
                time_range_end=time_range[1],
            ))
        
        return evidence
    
    def _collect_event_evidence(
        self,
        component: str,
        symptoms: List[str],
        time_range: Tuple[datetime, datetime],
    ) -> List[Evidence]:
        """Collect event-based evidence.
        
        Args:
            component: Component name
            symptoms: Symptoms to look for
            time_range: Time range
            
        Returns:
            List of evidence
        """
        evidence = []
        
        # Check known events
        for event in self._known_events:
            event_time = event.get("timestamp")
            if event_time and time_range[0] <= event_time <= time_range[1]:
                if event.get("component") == component or event.get("affects", []):
                    evidence.append(Evidence(
                        evidence_type=EvidenceType.EVENT,
                        source=f"event:{event.get('type', 'unknown')}",
                        description=event.get("description", "Event detected"),
                        confidence=event.get("confidence", 0.7),
                        strength=EvidenceStrength.STRONG,
                        relevance_score=0.8,
                        component=component,
                        supports_hypothesis=True,
                        timestamp=event_time,
                        time_range_start=time_range[0],
                        time_range_end=time_range[1],
                    ))
        
        return evidence
    
    def _collect_deployment_evidence(
        self,
        component: str,
        time_range: Tuple[datetime, datetime],
    ) -> List[Evidence]:
        """Collect deployment-related evidence.
        
        Args:
            component: Component name
            time_range: Time range
            
        Returns:
            List of evidence
        """
        evidence = []
        
        # Placeholder - would integrate with deployment tracking
        # For now, return empty if no deployment data registered
        
        return evidence
    
    def _collect_config_evidence(
        self,
        component: str,
        time_range: Tuple[datetime, datetime],
    ) -> List[Evidence]:
        """Collect configuration-related evidence.
        
        Args:
            component: Component name
            time_range: Time range
            
        Returns:
            List of evidence
        """
        evidence = []
        
        # Placeholder - would integrate with config management
        
        return evidence
    
    def _collect_alert_evidence(
        self,
        component: str,
        time_range: Tuple[datetime, datetime],
    ) -> List[Evidence]:
        """Collect alert-related evidence.
        
        Args:
            component: Component name
            time_range: Time range
            
        Returns:
            List of evidence
        """
        evidence = []
        
        # Placeholder - would integrate with alerting system
        
        return evidence
    
    def register_metric_pattern(
        self,
        metric_name: str,
        component: Optional[str] = None,
        description: str = "",
        symptoms: Optional[List[str]] = None,
        confidence: float = 0.7,
        supports: bool = True,
    ) -> None:
        """Register a metric pattern to look for.
        
        Args:
            metric_name: Name of metric
            component: Component (or None for any)
            description: Description of what it indicates
            symptoms: Related symptoms
            confidence: Confidence when pattern matches
            supports: Whether pattern supports hypothesis
        """
        self._metric_patterns.append({
            "metric_name": metric_name,
            "component": component,
            "description": description,
            "symptoms": symptoms or [],
            "confidence": confidence,
            "supports": supports,
        })
    
    def register_log_pattern(
        self,
        pattern: str,
        component: Optional[str] = None,
        description: str = "",
        confidence: float = 0.6,
        supports: bool = True,
    ) -> None:
        """Register a log pattern to look for.
        
        Args:
            pattern: Log pattern (regex or keyword)
            component: Component (or None for any)
            description: Description of what it indicates
            confidence: Confidence when pattern matches
            supports: Whether pattern supports hypothesis
        """
        self._log_patterns.append({
            "pattern": pattern,
            "component": component,
            "description": description,
            "confidence": confidence,
            "supports": supports,
        })
    
    def register_event(
        self,
        event_type: str,
        timestamp: datetime,
        component: Optional[str] = None,
        description: str = "",
        affects: Optional[List[str]] = None,
        confidence: float = 0.7,
    ) -> None:
        """Register a known event.
        
        Args:
            event_type: Type of event
            timestamp: When event occurred
            component: Component involved
            description: Description
            affects: Components affected
            confidence: Confidence level
        """
        self._known_events.append({
            "type": event_type,
            "timestamp": timestamp,
            "component": component,
            "description": description,
            "affects": affects or [],
            "confidence": confidence,
        })
    
    def add_manual_evidence(
        self,
        description: str,
        component: str,
        supports_hypothesis: bool,
        confidence: float = 0.8,
        strength: EvidenceStrength = EvidenceStrength.STRONG,
    ) -> Evidence:
        """Add manually gathered evidence.
        
        Args:
            description: Evidence description
            component: Related component
            supports_hypothesis: Whether it supports the hypothesis
            confidence: Confidence level
            strength: Evidence strength
            
        Returns:
            Created evidence
        """
        evidence = Evidence(
            evidence_type=EvidenceType.MANUAL,
            source="manual",
            description=description,
            confidence=confidence,
            strength=strength,
            relevance_score=0.9,  # Manual evidence is highly relevant
            component=component,
            supports_hypothesis=supports_hypothesis,
            collection_method="manual",
        )
        
        self._evidence_store[evidence.evidence_id] = evidence
        return evidence
    
    def evaluate_evidence(
        self,
        evidence: Evidence,
        hypothesis_component: str,
        hypothesis_type: str,
    ) -> float:
        """Evaluate how relevant evidence is to a hypothesis.
        
        Args:
            evidence: Evidence to evaluate
            hypothesis_component: Component in hypothesis
            hypothesis_type: Type of hypothesis
            
        Returns:
            Relevance score
        """
        score = evidence.relevance_score
        
        # Same component = more relevant
        if evidence.component == hypothesis_component:
            score *= 1.3
        
        # Evidence type matches hypothesis type
        type_relevance = {
            "service_failure": [EvidenceType.METRIC, EvidenceType.LOG, EvidenceType.ALERT],
            "resource_exhaustion": [EvidenceType.METRIC],
            "configuration_error": [EvidenceType.CONFIGURATION, EvidenceType.EVENT],
            "deployment_issue": [EvidenceType.DEPLOYMENT, EvidenceType.EVENT],
        }
        
        relevant_types = type_relevance.get(hypothesis_type, [])
        if evidence.evidence_type in relevant_types:
            score *= 1.2
        
        # Strength multiplier
        strength_mult = {
            EvidenceStrength.STRONG: 1.2,
            EvidenceStrength.MODERATE: 1.0,
            EvidenceStrength.WEAK: 0.8,
            EvidenceStrength.CIRCUMSTANTIAL: 0.6,
        }
        score *= strength_mult.get(evidence.strength, 1.0)
        
        # Confidence adjustment
        score *= evidence.confidence
        
        return min(score, 1.0)
    
    def get_evidence(self, evidence_id: str) -> Optional[Evidence]:
        """Get evidence by ID.
        
        Args:
            evidence_id: Evidence ID
            
        Returns:
            Evidence or None
        """
        return self._evidence_store.get(evidence_id)
    
    def get_all_evidence(self) -> List[Evidence]:
        """Get all collected evidence.
        
        Returns:
            List of all evidence
        """
        return list(self._evidence_store.values())
    
    def summarize(self) -> Dict[str, Any]:
        """Get summary of collected evidence.
        
        Returns:
            Summary dictionary
        """
        all_evidence = list(self._evidence_store.values())
        
        by_type = {}
        for e in all_evidence:
            etype = e.evidence_type.value
            by_type[etype] = by_type.get(etype, 0) + 1
        
        supporting = [e for e in all_evidence if e.supports_hypothesis is True]
        contradicting = [e for e in all_evidence if e.supports_hypothesis is False]
        
        return {
            "total_evidence": len(all_evidence),
            "by_type": by_type,
            "supporting_count": len(supporting),
            "contradicting_count": len(contradicting),
            "avg_confidence": sum(e.confidence for e in all_evidence) / len(all_evidence) if all_evidence else 0,
            "components": list(set(e.component for e in all_evidence if e.component)),
        }
    
    def clear(self) -> None:
        """Clear all evidence."""
        self._evidence_store.clear()
        self._metric_patterns.clear()
        self._log_patterns.clear()
        self._known_events.clear()
