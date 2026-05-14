"""Root cause analysis engine."""

from datetime import datetime, timedelta
from typing import Any, Optional, List, Dict, Set, Tuple
from enum import Enum

import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from autosre.models.common import utc_now, generate_id
from autosre.ml.rca.causal_graph import CausalGraph, CausalNode, NodeType, EdgeType
from autosre.ml.rca.evidence_collector import EvidenceCollector, Evidence, EvidenceType


class RCAStatus(str, Enum):
    """Status of RCA investigation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    INCONCLUSIVE = "inconclusive"
    FAILED = "failed"


class ConfidenceLevel(str, Enum):
    """Confidence level for findings."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"


class RootCause(BaseModel):
    """Identified root cause."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    cause_id: str = Field(default_factory=generate_id)
    
    # What
    component: str = Field(...)
    component_type: str = Field(default="")
    description: str = Field(...)
    
    # Confidence
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.MEDIUM)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Evidence
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    evidence_count: int = Field(default=0, ge=0)
    
    # Impact
    affected_components: list[str] = Field(default_factory=list)
    impact_score: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Timeline
    probable_start_time: Optional[datetime] = None
    detection_lag_seconds: Optional[float] = None
    
    # Cause chain
    upstream_causes: list[str] = Field(default_factory=list)
    downstream_effects: list[str] = Field(default_factory=list)
    
    # Remediation
    recommended_actions: list[str] = Field(default_factory=list)
    similar_incidents: list[str] = Field(default_factory=list)
    
    # Metadata
    identified_at: datetime = Field(default_factory=utc_now)


class RCAResult(BaseModel):
    """Result of root cause analysis."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    rca_id: str = Field(default_factory=generate_id)
    incident_id: str = Field(default="")
    
    # Status
    status: RCAStatus = Field(default=RCAStatus.PENDING)
    
    # Root causes (ranked)
    root_causes: list[RootCause] = Field(default_factory=list)
    primary_cause: Optional[RootCause] = None
    
    # Investigation details
    symptoms_analyzed: list[str] = Field(default_factory=list)
    components_investigated: list[str] = Field(default_factory=list)
    evidence_collected: int = Field(default=0, ge=0)
    
    # Timeline reconstruction
    event_timeline: list[dict[str, Any]] = Field(default_factory=list)
    incident_start_time: Optional[datetime] = None
    incident_detected_time: Optional[datetime] = None
    
    # Causal chain
    causal_chain: list[str] = Field(default_factory=list)
    
    # Confidence
    overall_confidence: ConfidenceLevel = Field(default=ConfidenceLevel.LOW)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Recommendations
    immediate_actions: list[str] = Field(default_factory=list)
    preventive_measures: list[str] = Field(default_factory=list)
    
    # Timing
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None
    duration_seconds: float = Field(default=0.0, ge=0.0)
    
    # Errors
    errors: list[str] = Field(default_factory=list)


class RCAEngine:
    """Automated root cause analysis engine.
    
    Combines multiple analysis techniques:
    - Causal graph traversal
    - Symptom correlation
    - Evidence collection
    - Hypothesis ranking
    
    To identify the most likely root cause of an incident.
    """
    
    def __init__(
        self,
        causal_graph: Optional[CausalGraph] = None,
        evidence_collector: Optional[EvidenceCollector] = None,
        max_depth: int = 10,
        min_confidence: float = 0.3,
    ):
        """Initialize the RCA engine.
        
        Args:
            causal_graph: Pre-built causal graph
            evidence_collector: Evidence collection component
            max_depth: Maximum depth for graph traversal
            min_confidence: Minimum confidence to report
        """
        self.causal_graph = causal_graph or CausalGraph()
        self.evidence_collector = evidence_collector or EvidenceCollector()
        self.max_depth = max_depth
        self.min_confidence = min_confidence
    
    def analyze(
        self,
        incident_id: str,
        symptoms: list[str],
        affected_components: Optional[list[str]] = None,
        time_range: Optional[Tuple[datetime, datetime]] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> RCAResult:
        """Perform root cause analysis.
        
        Args:
            incident_id: Incident identifier
            symptoms: List of observed symptoms
            affected_components: Known affected components
            time_range: Time range of incident
            context: Additional context
            
        Returns:
            RCA result
        """
        import time
        start_time = time.time()
        
        result = RCAResult(
            incident_id=incident_id,
            status=RCAStatus.IN_PROGRESS,
            symptoms_analyzed=symptoms,
            components_investigated=affected_components or [],
        )
        
        try:
            # Step 1: Identify affected nodes in causal graph
            affected_nodes = self._identify_affected_nodes(
                symptoms, affected_components or []
            )
            
            # Step 2: Find potential root causes using graph
            candidates = self._find_root_cause_candidates(affected_nodes)
            
            # Step 3: Collect evidence for each candidate
            evidence_by_candidate = {}
            for candidate, score in candidates:
                evidence = self._collect_evidence(
                    candidate, symptoms, time_range
                )
                evidence_by_candidate[candidate.node_id] = evidence
                result.evidence_collected += len(evidence)
            
            # Step 4: Score and rank candidates
            root_causes = self._rank_candidates(
                candidates, evidence_by_candidate, symptoms
            )
            
            # Step 5: Build causal chain
            if root_causes:
                result.primary_cause = root_causes[0]
                result.causal_chain = self._build_causal_chain(
                    root_causes[0], affected_nodes
                )
            
            result.root_causes = root_causes
            
            # Step 6: Reconstruct timeline
            result.event_timeline = self._reconstruct_timeline(
                root_causes, time_range
            )
            
            if result.event_timeline:
                result.incident_start_time = result.event_timeline[0].get("timestamp")
            
            # Step 7: Generate recommendations
            result.immediate_actions, result.preventive_measures = self._generate_recommendations(
                root_causes
            )
            
            # Step 8: Calculate overall confidence
            if root_causes:
                result.confidence_score = float(np.mean([
                    rc.confidence_score for rc in root_causes[:3]
                ]))
                
                if result.confidence_score >= 0.8:
                    result.overall_confidence = ConfidenceLevel.HIGH
                elif result.confidence_score >= 0.5:
                    result.overall_confidence = ConfidenceLevel.MEDIUM
                elif result.confidence_score >= 0.3:
                    result.overall_confidence = ConfidenceLevel.LOW
                else:
                    result.overall_confidence = ConfidenceLevel.VERY_LOW
            
            result.status = RCAStatus.COMPLETED if root_causes else RCAStatus.INCONCLUSIVE
            
        except Exception as e:
            result.status = RCAStatus.FAILED
            result.errors.append(str(e))
        
        result.completed_at = utc_now()
        result.duration_seconds = time.time() - start_time
        
        return result
    
    def _identify_affected_nodes(
        self,
        symptoms: list[str],
        components: list[str],
    ) -> list[CausalNode]:
        """Identify affected nodes in causal graph.
        
        Args:
            symptoms: Observed symptoms
            components: Affected component names
            
        Returns:
            List of affected nodes
        """
        affected = []
        
        # Mark symptom-related nodes as anomalous
        for symptom in symptoms:
            # Try to match symptom to node
            node = self.causal_graph.get_node(symptom)
            if node:
                self.causal_graph.set_node_anomalous(symptom, True, 1.0)
                affected.append(node)
        
        # Mark affected components
        for component in components:
            node = self.causal_graph.get_node(component)
            if node:
                self.causal_graph.set_node_anomalous(component, True, 1.0)
                if node not in affected:
                    affected.append(node)
        
        # Also get nodes already marked as anomalous
        for node in self.causal_graph.get_anomalous_nodes():
            if node not in affected:
                affected.append(node)
        
        return affected
    
    def _find_root_cause_candidates(
        self,
        affected_nodes: list[CausalNode],
    ) -> list[Tuple[CausalNode, float]]:
        """Find potential root cause candidates.
        
        Args:
            affected_nodes: Nodes affected by the incident
            
        Returns:
            List of (node, initial_score) tuples
        """
        if not affected_nodes:
            return []
        
        # Use causal graph to find common ancestors
        candidates = self.causal_graph.find_root_causes(
            [n.name for n in affected_nodes],
            max_depth=self.max_depth,
        )
        
        # Also consider affected nodes themselves as potential root causes
        for node in affected_nodes:
            # Check if this node has no parents (could be root)
            parents = self.causal_graph.get_parents(node.name)
            if not parents and (node, 0.5) not in candidates:
                candidates.append((node, 0.5))
        
        return candidates
    
    def _collect_evidence(
        self,
        candidate: CausalNode,
        symptoms: list[str],
        time_range: Optional[Tuple[datetime, datetime]],
    ) -> list[Evidence]:
        """Collect evidence for a root cause candidate.
        
        Args:
            candidate: Candidate node
            symptoms: Observed symptoms
            time_range: Time range to search
            
        Returns:
            List of evidence items
        """
        evidence = []
        
        # Check if candidate is anomalous
        if candidate.is_anomalous:
            evidence.append(Evidence(
                evidence_type=EvidenceType.METRIC,
                source=candidate.name,
                description=f"{candidate.name} is showing anomalous behavior",
                confidence=candidate.anomaly_score,
                supports_hypothesis=True,
            ))
        
        # Check for correlated timing
        children = self.causal_graph.get_children(candidate.name)
        for child in children:
            if child.is_anomalous:
                evidence.append(Evidence(
                    evidence_type=EvidenceType.CORRELATION,
                    source=f"{candidate.name} -> {child.name}",
                    description=f"Downstream component {child.name} is also anomalous",
                    confidence=0.7,
                    supports_hypothesis=True,
                ))
        
        # Use evidence collector for more evidence
        additional = self.evidence_collector.collect(
            component=candidate.name,
            symptoms=symptoms,
            time_range=time_range,
        )
        evidence.extend(additional)
        
        return evidence
    
    def _rank_candidates(
        self,
        candidates: list[Tuple[CausalNode, float]],
        evidence: dict[str, list[Evidence]],
        symptoms: list[str],
    ) -> list[RootCause]:
        """Rank root cause candidates.
        
        Args:
            candidates: Candidate nodes with initial scores
            evidence: Evidence for each candidate
            symptoms: Observed symptoms
            
        Returns:
            Ranked list of root causes
        """
        root_causes = []
        
        for node, initial_score in candidates:
            node_evidence = evidence.get(node.node_id, [])
            
            # Calculate confidence score
            supporting = [e for e in node_evidence if e.supports_hypothesis]
            contradicting = [e for e in node_evidence if not e.supports_hypothesis]
            
            if supporting:
                support_score = np.mean([e.confidence for e in supporting])
            else:
                support_score = 0.0
            
            if contradicting:
                contradict_score = np.mean([e.confidence for e in contradicting])
            else:
                contradict_score = 0.0
            
            # Combined score
            evidence_score = support_score - 0.5 * contradict_score
            confidence_score = (initial_score + evidence_score) / 2
            confidence_score = max(0, min(1, confidence_score))
            
            if confidence_score < self.min_confidence:
                continue
            
            # Determine confidence level
            if confidence_score >= 0.8:
                confidence = ConfidenceLevel.HIGH
            elif confidence_score >= 0.5:
                confidence = ConfidenceLevel.MEDIUM
            else:
                confidence = ConfidenceLevel.LOW
            
            # Get affected components
            descendants = self.causal_graph.get_descendants(node.name, max_depth=3)
            affected = [d.name for d, _ in descendants if d.is_anomalous]
            
            # Generate description
            description = self._generate_cause_description(node, symptoms)
            
            # Get upstream causes
            ancestors = self.causal_graph.get_ancestors(node.name, max_depth=2)
            upstream = [a.name for a, _ in ancestors if a.is_anomalous]
            
            # Generate recommendations
            recommendations = self._generate_remediation_actions(node)
            
            root_cause = RootCause(
                component=node.name,
                component_type=node.node_type.value,
                description=description,
                confidence=confidence,
                confidence_score=confidence_score,
                supporting_evidence=[e.evidence_id for e in supporting],
                contradicting_evidence=[e.evidence_id for e in contradicting],
                evidence_count=len(node_evidence),
                affected_components=affected,
                impact_score=len(affected) / (len(self.causal_graph._nodes) + 1),
                upstream_causes=upstream,
                downstream_effects=affected,
                recommended_actions=recommendations,
            )
            
            root_causes.append(root_cause)
        
        # Sort by confidence
        root_causes.sort(key=lambda rc: rc.confidence_score, reverse=True)
        
        return root_causes
    
    def _build_causal_chain(
        self,
        primary_cause: RootCause,
        affected_nodes: list[CausalNode],
    ) -> list[str]:
        """Build the causal chain from root cause to effects.
        
        Args:
            primary_cause: Primary root cause
            affected_nodes: Affected nodes
            
        Returns:
            List of component names in causal order
        """
        chain = [primary_cause.component]
        
        # Find path to each affected node
        for node in affected_nodes[:3]:  # Limit for performance
            if node.name == primary_cause.component:
                continue
            
            paths = self.causal_graph.find_paths(
                primary_cause.component,
                node.name,
                max_paths=1,
                max_length=5,
            )
            
            if paths:
                for path_node in paths[0]:
                    if path_node.name not in chain:
                        chain.append(path_node.name)
        
        return chain
    
    def _reconstruct_timeline(
        self,
        root_causes: list[RootCause],
        time_range: Optional[Tuple[datetime, datetime]],
    ) -> list[dict[str, Any]]:
        """Reconstruct timeline of events.
        
        Args:
            root_causes: Identified root causes
            time_range: Time range
            
        Returns:
            List of timeline events
        """
        events = []
        
        now = utc_now()
        
        if root_causes:
            # Root cause event
            primary = root_causes[0]
            events.append({
                "timestamp": primary.probable_start_time or (now - timedelta(minutes=30)),
                "event_type": "root_cause",
                "component": primary.component,
                "description": primary.description,
            })
            
            # Propagation events
            for i, affected in enumerate(primary.affected_components[:5]):
                events.append({
                    "timestamp": (primary.probable_start_time or now) + timedelta(minutes=i+1),
                    "event_type": "propagation",
                    "component": affected,
                    "description": f"Impact propagated to {affected}",
                })
        
        # Sort by time
        events.sort(key=lambda e: e["timestamp"])
        
        return events
    
    def _generate_recommendations(
        self,
        root_causes: list[RootCause],
    ) -> Tuple[list[str], list[str]]:
        """Generate remediation recommendations.
        
        Args:
            root_causes: Identified root causes
            
        Returns:
            Tuple of (immediate_actions, preventive_measures)
        """
        immediate = []
        preventive = []
        
        for cause in root_causes[:3]:
            immediate.extend(cause.recommended_actions)
            
            # Add generic preventive measures based on component type
            if cause.component_type == "service":
                preventive.append(f"Add health checks for {cause.component}")
                preventive.append(f"Implement circuit breaker for {cause.component}")
            elif cause.component_type == "metric":
                preventive.append(f"Set up alerting for {cause.component}")
                preventive.append(f"Add anomaly detection for {cause.component}")
        
        # Deduplicate
        immediate = list(set(immediate))
        preventive = list(set(preventive))
        
        return immediate, preventive
    
    def _generate_cause_description(
        self,
        node: CausalNode,
        symptoms: list[str],
    ) -> str:
        """Generate human-readable cause description.
        
        Args:
            node: Root cause node
            symptoms: Observed symptoms
            
        Returns:
            Description string
        """
        symptoms_str = ", ".join(symptoms[:3])
        
        if node.node_type == NodeType.SERVICE:
            return f"Service {node.name} failure caused {symptoms_str}"
        elif node.node_type == NodeType.CONFIG:
            return f"Configuration change in {node.name} led to {symptoms_str}"
        elif node.node_type == NodeType.METRIC:
            return f"Abnormal {node.name} values triggered {symptoms_str}"
        elif node.node_type == NodeType.EXTERNAL:
            return f"External dependency {node.name} issue caused {symptoms_str}"
        else:
            return f"Issue with {node.name} resulted in {symptoms_str}"
    
    def _generate_remediation_actions(
        self,
        node: CausalNode,
    ) -> list[str]:
        """Generate remediation actions for a root cause.
        
        Args:
            node: Root cause node
            
        Returns:
            List of actions
        """
        actions = []
        
        if node.node_type == NodeType.SERVICE:
            actions.extend([
                f"Restart {node.name} service",
                f"Check {node.name} logs for errors",
                f"Verify {node.name} resource utilization",
            ])
        elif node.node_type == NodeType.CONFIG:
            actions.extend([
                f"Review recent changes to {node.name}",
                f"Consider rolling back {node.name} configuration",
            ])
        elif node.node_type == NodeType.METRIC:
            actions.extend([
                f"Investigate {node.name} anomaly",
                f"Check thresholds for {node.name}",
            ])
        elif node.node_type == NodeType.EXTERNAL:
            actions.extend([
                f"Check {node.name} status page",
                f"Consider failover to backup for {node.name}",
            ])
        
        return actions
    
    def add_component(
        self,
        name: str,
        node_type: NodeType = NodeType.COMPONENT,
        properties: Optional[dict[str, Any]] = None,
    ) -> CausalNode:
        """Add a component to the causal graph.
        
        Args:
            name: Component name
            node_type: Type of node
            properties: Node properties
            
        Returns:
            Created node
        """
        return self.causal_graph.add_node(name, node_type, properties)
    
    def add_dependency(
        self,
        source: str,
        target: str,
        edge_type: EdgeType = EdgeType.DEPENDS_ON,
    ) -> None:
        """Add a dependency between components.
        
        Args:
            source: Source component
            target: Target component
            edge_type: Type of relationship
        """
        self.causal_graph.add_edge(source, target, edge_type)
