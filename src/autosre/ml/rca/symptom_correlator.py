"""Symptom correlation for root cause analysis."""

from datetime import datetime, timedelta
from typing import Any, Optional, List, Dict, Tuple
from enum import Enum
import hashlib

import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from autosre.models.common import utc_now, generate_id


class SymptomType(str, Enum):
    """Type of symptom."""
    METRIC_ANOMALY = "metric_anomaly"
    LOG_ERROR = "log_error"
    LATENCY_SPIKE = "latency_spike"
    ERROR_RATE = "error_rate"
    TIMEOUT = "timeout"
    AVAILABILITY = "availability"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    CONFIGURATION = "configuration"
    DEPLOYMENT = "deployment"
    EXTERNAL = "external"


class CorrelationType(str, Enum):
    """Type of correlation."""
    TEMPORAL = "temporal"
    CAUSAL = "causal"
    STATISTICAL = "statistical"
    TOPOLOGICAL = "topological"


class Symptom(BaseModel):
    """A symptom observed during an incident."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    symptom_id: str = Field(default_factory=generate_id)
    
    # What
    name: str = Field(..., min_length=1)
    symptom_type: SymptomType = Field(default=SymptomType.METRIC_ANOMALY)
    description: str = Field(default="")
    
    # Where
    component: str = Field(default="")
    service: str = Field(default="")
    
    # When
    first_seen: datetime = Field(default_factory=utc_now)
    last_seen: datetime = Field(default_factory=utc_now)
    
    # Severity
    severity: float = Field(default=0.5, ge=0.0, le=1.0)
    
    # Values
    current_value: Optional[float] = None
    baseline_value: Optional[float] = None
    deviation: Optional[float] = None
    
    # Metadata
    labels: dict[str, str] = Field(default_factory=dict)
    raw_data: dict[str, Any] = Field(default_factory=dict)
    
    def signature(self) -> str:
        """Generate a unique signature for deduplication."""
        sig = f"{self.symptom_type}:{self.component}:{self.name}"
        return hashlib.md5(sig.encode()).hexdigest()[:12]


class SymptomCorrelation(BaseModel):
    """Correlation between two symptoms."""
    model_config = ConfigDict(validate_assignment=True)
    
    symptom_a_id: str
    symptom_b_id: str
    
    correlation_type: CorrelationType
    correlation_coefficient: float = Field(default=0.0, ge=-1.0, le=1.0)
    
    # Timing
    time_lag_seconds: float = Field(default=0.0)
    
    # Confidence
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Statistical significance
    p_value: Optional[float] = None
    sample_size: int = Field(default=0, ge=0)


class SymptomCluster(BaseModel):
    """A cluster of correlated symptoms."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    cluster_id: str = Field(default_factory=generate_id)
    
    # Members
    symptom_ids: list[str] = Field(default_factory=list)
    symptom_names: list[str] = Field(default_factory=list)
    
    # Cluster properties
    size: int = Field(default=0, ge=0)
    cohesion: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Representative
    centroid_symptom_id: Optional[str] = None
    common_component: Optional[str] = None
    
    # Time
    earliest_symptom: Optional[datetime] = None
    cluster_duration_seconds: Optional[float] = None
    
    # Potential root cause
    likely_root_symptom_id: Optional[str] = None
    root_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class SymptomCorrelator:
    """Correlate symptoms to identify patterns and root causes.
    
    Analyzes relationships between symptoms:
    - Temporal correlation (timing)
    - Statistical correlation (co-occurrence)
    - Topological correlation (component proximity)
    
    Groups related symptoms into clusters for investigation.
    """
    
    def __init__(
        self,
        correlation_threshold: float = 0.5,
        time_window_seconds: float = 300.0,
        min_cluster_size: int = 2,
    ):
        """Initialize the symptom correlator.
        
        Args:
            correlation_threshold: Minimum correlation to consider
            time_window_seconds: Time window for temporal correlation
            min_cluster_size: Minimum symptoms per cluster
        """
        self.correlation_threshold = correlation_threshold
        self.time_window_seconds = time_window_seconds
        self.min_cluster_size = min_cluster_size
        
        self._symptoms: Dict[str, Symptom] = {}
        self._correlations: List[SymptomCorrelation] = []
        self._clusters: List[SymptomCluster] = []
    
    def add_symptom(self, symptom: Symptom) -> None:
        """Add a symptom for correlation.
        
        Args:
            symptom: Symptom to add
        """
        self._symptoms[symptom.symptom_id] = symptom
    
    def add_symptoms(self, symptoms: List[Symptom]) -> None:
        """Add multiple symptoms.
        
        Args:
            symptoms: List of symptoms
        """
        for symptom in symptoms:
            self.add_symptom(symptom)
    
    def correlate(self) -> List[SymptomCorrelation]:
        """Find correlations between all symptoms.
        
        Returns:
            List of correlations
        """
        self._correlations = []
        symptoms = list(self._symptoms.values())
        
        for i, symptom_a in enumerate(symptoms):
            for symptom_b in symptoms[i+1:]:
                correlation = self._compute_correlation(symptom_a, symptom_b)
                if correlation and abs(correlation.correlation_coefficient) >= self.correlation_threshold:
                    self._correlations.append(correlation)
        
        return self._correlations
    
    def _compute_correlation(
        self,
        symptom_a: Symptom,
        symptom_b: Symptom,
    ) -> Optional[SymptomCorrelation]:
        """Compute correlation between two symptoms.
        
        Args:
            symptom_a: First symptom
            symptom_b: Second symptom
            
        Returns:
            Correlation or None
        """
        # Temporal correlation
        temporal_corr = self._compute_temporal_correlation(symptom_a, symptom_b)
        
        # Topological correlation (same component/service)
        topo_corr = self._compute_topological_correlation(symptom_a, symptom_b)
        
        # Type correlation (similar symptoms)
        type_corr = self._compute_type_correlation(symptom_a, symptom_b)
        
        # Combined correlation
        combined = (temporal_corr + topo_corr + type_corr) / 3
        
        if abs(combined) < 0.1:
            return None
        
        # Determine type
        if temporal_corr > topo_corr and temporal_corr > type_corr:
            corr_type = CorrelationType.TEMPORAL
        elif topo_corr > type_corr:
            corr_type = CorrelationType.TOPOLOGICAL
        else:
            corr_type = CorrelationType.STATISTICAL
        
        # Calculate time lag
        time_lag = (symptom_b.first_seen - symptom_a.first_seen).total_seconds()
        
        return SymptomCorrelation(
            symptom_a_id=symptom_a.symptom_id,
            symptom_b_id=symptom_b.symptom_id,
            correlation_type=corr_type,
            correlation_coefficient=combined,
            time_lag_seconds=time_lag,
            confidence=abs(combined),
        )
    
    def _compute_temporal_correlation(
        self,
        symptom_a: Symptom,
        symptom_b: Symptom,
    ) -> float:
        """Compute temporal correlation.
        
        Args:
            symptom_a: First symptom
            symptom_b: Second symptom
            
        Returns:
            Correlation score
        """
        # Time difference in seconds
        time_diff = abs((symptom_a.first_seen - symptom_b.first_seen).total_seconds())
        
        # If within time window, they're correlated
        if time_diff <= self.time_window_seconds:
            # Closer in time = higher correlation
            return 1.0 - (time_diff / self.time_window_seconds)
        
        return 0.0
    
    def _compute_topological_correlation(
        self,
        symptom_a: Symptom,
        symptom_b: Symptom,
    ) -> float:
        """Compute topological correlation.
        
        Args:
            symptom_a: First symptom
            symptom_b: Second symptom
            
        Returns:
            Correlation score
        """
        score = 0.0
        
        # Same component = high correlation
        if symptom_a.component and symptom_b.component:
            if symptom_a.component == symptom_b.component:
                score += 0.8
            elif symptom_a.service == symptom_b.service:
                score += 0.5
        
        # Same service = medium correlation
        if symptom_a.service and symptom_b.service:
            if symptom_a.service == symptom_b.service and score < 0.5:
                score = 0.5
        
        return min(score, 1.0)
    
    def _compute_type_correlation(
        self,
        symptom_a: Symptom,
        symptom_b: Symptom,
    ) -> float:
        """Compute symptom type correlation.
        
        Args:
            symptom_a: First symptom
            symptom_b: Second symptom
            
        Returns:
            Correlation score
        """
        # Same type = some correlation
        if symptom_a.symptom_type == symptom_b.symptom_type:
            return 0.6
        
        # Related types
        related_types = {
            (SymptomType.LATENCY_SPIKE, SymptomType.TIMEOUT): 0.7,
            (SymptomType.ERROR_RATE, SymptomType.AVAILABILITY): 0.7,
            (SymptomType.RESOURCE_EXHAUSTION, SymptomType.LATENCY_SPIKE): 0.6,
            (SymptomType.DEPLOYMENT, SymptomType.ERROR_RATE): 0.5,
            (SymptomType.CONFIGURATION, SymptomType.ERROR_RATE): 0.5,
        }
        
        type_pair = (symptom_a.symptom_type, symptom_b.symptom_type)
        if type_pair in related_types:
            return related_types[type_pair]
        
        # Check reverse
        type_pair = (symptom_b.symptom_type, symptom_a.symptom_type)
        if type_pair in related_types:
            return related_types[type_pair]
        
        return 0.0
    
    def cluster(self) -> List[SymptomCluster]:
        """Group symptoms into clusters.
        
        Returns:
            List of symptom clusters
        """
        if not self._correlations:
            self.correlate()
        
        # Build adjacency list
        adjacency: Dict[str, Set[str]] = {
            sid: set() for sid in self._symptoms.keys()
        }
        
        for corr in self._correlations:
            adjacency[corr.symptom_a_id].add(corr.symptom_b_id)
            adjacency[corr.symptom_b_id].add(corr.symptom_a_id)
        
        # Find connected components
        visited = set()
        self._clusters = []
        
        for symptom_id in self._symptoms.keys():
            if symptom_id in visited:
                continue
            
            # BFS to find cluster
            cluster_ids = []
            queue = [symptom_id]
            
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                
                visited.add(current)
                cluster_ids.append(current)
                
                for neighbor in adjacency.get(current, set()):
                    if neighbor not in visited:
                        queue.append(neighbor)
            
            # Create cluster if large enough
            if len(cluster_ids) >= self.min_cluster_size:
                cluster = self._create_cluster(cluster_ids)
                self._clusters.append(cluster)
        
        return self._clusters
    
    def _create_cluster(self, symptom_ids: List[str]) -> SymptomCluster:
        """Create a cluster from symptom IDs.
        
        Args:
            symptom_ids: IDs of symptoms in cluster
            
        Returns:
            Created cluster
        """
        symptoms = [self._symptoms[sid] for sid in symptom_ids if sid in self._symptoms]
        
        # Find earliest symptom
        earliest = min(symptoms, key=lambda s: s.first_seen)
        latest = max(symptoms, key=lambda s: s.last_seen)
        
        # Find common component
        components = [s.component for s in symptoms if s.component]
        from collections import Counter
        common_component = None
        if components:
            most_common = Counter(components).most_common(1)
            if most_common:
                common_component = most_common[0][0]
        
        # Calculate cohesion (average correlation within cluster)
        internal_correlations = [
            c for c in self._correlations
            if c.symptom_a_id in symptom_ids and c.symptom_b_id in symptom_ids
        ]
        
        if internal_correlations:
            cohesion = np.mean([abs(c.correlation_coefficient) for c in internal_correlations])
        else:
            cohesion = 0.0
        
        # Find likely root (earliest and most connected)
        likely_root = self._find_cluster_root(symptom_ids)
        
        return SymptomCluster(
            symptom_ids=symptom_ids,
            symptom_names=[self._symptoms[sid].name for sid in symptom_ids if sid in self._symptoms],
            size=len(symptom_ids),
            cohesion=float(cohesion),
            centroid_symptom_id=earliest.symptom_id,
            common_component=common_component,
            earliest_symptom=earliest.first_seen,
            cluster_duration_seconds=(latest.last_seen - earliest.first_seen).total_seconds(),
            likely_root_symptom_id=likely_root,
            root_confidence=0.6 if likely_root else 0.0,
        )
    
    def _find_cluster_root(self, symptom_ids: List[str]) -> Optional[str]:
        """Find the likely root symptom in a cluster.
        
        Args:
            symptom_ids: IDs of symptoms in cluster
            
        Returns:
            ID of likely root symptom
        """
        if not symptom_ids:
            return None
        
        # Score each symptom
        scores: Dict[str, float] = {}
        
        for sid in symptom_ids:
            symptom = self._symptoms.get(sid)
            if not symptom:
                continue
            
            score = 0.0
            
            # Earlier symptoms are more likely root
            all_first_seen = [
                self._symptoms[s].first_seen
                for s in symptom_ids
                if s in self._symptoms
            ]
            if all_first_seen:
                min_time = min(all_first_seen)
                max_time = max(all_first_seen)
                time_range = (max_time - min_time).total_seconds()
                
                if time_range > 0:
                    symptom_time = (symptom.first_seen - min_time).total_seconds()
                    score += (1.0 - symptom_time / time_range) * 0.5
            
            # More connections = more likely root
            connections = sum(
                1 for c in self._correlations
                if (c.symptom_a_id == sid or c.symptom_b_id == sid)
                and c.symptom_a_id in symptom_ids
                and c.symptom_b_id in symptom_ids
            )
            score += min(connections / len(symptom_ids), 1.0) * 0.3
            
            # Higher severity = more likely root
            score += symptom.severity * 0.2
            
            scores[sid] = score
        
        if scores:
            return max(scores.keys(), key=lambda k: scores[k])
        
        return None
    
    def find_related_symptoms(
        self,
        symptom: Symptom,
        top_k: int = 5,
    ) -> List[Tuple[Symptom, float]]:
        """Find symptoms most related to a given symptom.
        
        Args:
            symptom: Reference symptom
            top_k: Number of related symptoms to return
            
        Returns:
            List of (symptom, correlation_score) tuples
        """
        if symptom.symptom_id not in self._symptoms:
            self.add_symptom(symptom)
        
        related = []
        
        for other_id, other in self._symptoms.items():
            if other_id == symptom.symptom_id:
                continue
            
            correlation = self._compute_correlation(symptom, other)
            if correlation:
                related.append((other, correlation.correlation_coefficient))
        
        # Sort by correlation
        related.sort(key=lambda x: abs(x[1]), reverse=True)
        
        return related[:top_k]
    
    def get_symptom_timeline(self) -> List[Tuple[datetime, Symptom]]:
        """Get symptoms ordered by time.
        
        Returns:
            List of (timestamp, symptom) tuples
        """
        timeline = [
            (s.first_seen, s)
            for s in self._symptoms.values()
        ]
        timeline.sort(key=lambda x: x[0])
        return timeline
    
    def get_clusters(self) -> List[SymptomCluster]:
        """Get computed clusters.
        
        Returns:
            List of clusters
        """
        if not self._clusters:
            self.cluster()
        return self._clusters
    
    def summarize(self) -> Dict[str, Any]:
        """Get summary of symptom analysis.
        
        Returns:
            Summary dictionary
        """
        if not self._clusters:
            self.cluster()
        
        return {
            "total_symptoms": len(self._symptoms),
            "total_correlations": len(self._correlations),
            "total_clusters": len(self._clusters),
            "cluster_sizes": [c.size for c in self._clusters],
            "symptom_types": dict(Counter(
                s.symptom_type.value for s in self._symptoms.values()
            )),
            "affected_components": list(set(
                s.component for s in self._symptoms.values() if s.component
            )),
        }
    
    def clear(self) -> None:
        """Clear all symptoms and correlations."""
        self._symptoms.clear()
        self._correlations.clear()
        self._clusters.clear()


# Import Counter for summarize
from collections import Counter
