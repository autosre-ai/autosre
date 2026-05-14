"""
Alert Correlator for AutoSRE V2.

Intelligent alert correlation and grouping to reduce noise:
- Time-window based grouping
- Label similarity matching
- Causal correlation detection
- Alert storm detection
- Alert clustering using ML
"""

from __future__ import annotations

import hashlib
import statistics
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from autosre.core.alert import Alert, AlertSeverity, AlertStatus
from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class CorrelationMethod(str, Enum):
    """Method used for alert correlation."""
    
    TIME_WINDOW = "time_window"  # Group by time proximity
    LABEL_SIMILARITY = "label_similarity"  # Group by shared labels
    CAUSAL = "causal"  # Group by cause-effect relationships
    SERVICE_TOPOLOGY = "service_topology"  # Group by service dependencies
    METRIC_CORRELATION = "metric_correlation"  # Group by correlated metrics
    ML_CLUSTERING = "ml_clustering"  # ML-based clustering
    ENSEMBLE = "ensemble"  # Combination of methods


class SimilarityMetric(str, Enum):
    """Similarity metric for comparing alerts."""
    
    JACCARD = "jaccard"  # Set intersection over union
    COSINE = "cosine"  # Cosine similarity
    EDIT_DISTANCE = "edit_distance"  # Levenshtein distance
    OVERLAP = "overlap"  # Simple overlap coefficient


@dataclass
class TimeWindowConfig:
    """Configuration for time window correlation."""
    
    window_seconds: float = 300.0  # 5 minutes
    min_alerts_for_group: int = 2
    max_group_size: int = 100
    sliding_window: bool = True
    overlap_ratio: float = 0.5


@dataclass
class CorrelatorConfig:
    """Configuration for alert correlation."""
    
    # Time window settings
    time_window: TimeWindowConfig = field(default_factory=TimeWindowConfig)
    
    # Label similarity settings
    label_similarity_threshold: float = 0.5
    important_labels: list[str] = field(
        default_factory=lambda: ["service", "namespace", "cluster", "instance", "job"]
    )
    ignore_labels: list[str] = field(
        default_factory=lambda: ["alertname", "severity"]
    )
    
    # Causal correlation settings
    causal_time_window_seconds: float = 60.0
    causal_confidence_threshold: float = 0.7
    
    # Service topology settings
    use_service_graph: bool = True
    max_hop_distance: int = 2
    
    # Clustering settings
    clustering_eps: float = 0.3
    clustering_min_samples: int = 2
    
    # General settings
    dedup_window_seconds: float = 60.0
    correlation_methods: list[CorrelationMethod] = field(
        default_factory=lambda: [
            CorrelationMethod.TIME_WINDOW,
            CorrelationMethod.LABEL_SIMILARITY,
        ]
    )
    min_correlation_score: float = 0.3


@dataclass
class CorrelationRule:
    """A rule for correlating alerts."""
    
    name: str
    description: str
    conditions: dict[str, Any]  # Conditions that must match
    group_by: list[str]  # Labels to group by
    priority: int = 0
    enabled: bool = True
    
    def matches(self, alert: Alert) -> bool:
        """Check if an alert matches this rule's conditions."""
        for key, value in self.conditions.items():
            if key == "alertname":
                if alert.name != value:
                    return False
            elif key == "alertname_pattern":
                import re
                if not re.match(value, alert.name):
                    return False
            elif key == "severity":
                if alert.severity != AlertSeverity(value):
                    return False
            elif key == "service":
                if alert.service != value:
                    return False
            elif key == "namespace":
                if alert.namespace != value:
                    return False
            elif key == "labels":
                for lk, lv in value.items():
                    if alert.labels.get(lk) != lv:
                        return False
        
        return True
    
    def get_group_key(self, alert: Alert) -> str:
        """Generate a group key for an alert based on this rule."""
        parts = [self.name]
        
        for label in self.group_by:
            if label == "alertname":
                parts.append(alert.name)
            elif label == "service":
                parts.append(alert.service or "unknown")
            elif label == "namespace":
                parts.append(alert.namespace or "default")
            elif label == "severity":
                parts.append(alert.severity.value)
            elif label in alert.labels:
                parts.append(alert.labels[label])
        
        return "|".join(parts)


@dataclass
class AlertCluster:
    """A cluster of related alerts."""
    
    id: str
    alerts: list[Alert]
    centroid: dict[str, Any]  # Representative features
    created_at: datetime
    updated_at: datetime
    
    @property
    def size(self) -> int:
        return len(self.alerts)
    
    @property
    def max_severity(self) -> AlertSeverity:
        """Get highest severity in cluster."""
        if not self.alerts:
            return AlertSeverity.INFO
        return min(a.severity for a in self.alerts)
    
    @property
    def active_count(self) -> int:
        """Count of active alerts."""
        return sum(1 for a in self.alerts if a.is_active)
    
    def add_alert(self, alert: Alert) -> None:
        """Add an alert to the cluster."""
        self.alerts.append(alert)
        self.updated_at = datetime.now(timezone.utc)


@dataclass
class CorrelationGroup:
    """A group of correlated alerts."""
    
    id: str
    name: str
    alerts: list[Alert]
    correlation_method: CorrelationMethod
    correlation_score: float
    root_cause_alert: Optional[Alert]
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @property
    def size(self) -> int:
        return len(self.alerts)
    
    @property
    def max_severity(self) -> AlertSeverity:
        """Get highest severity in group."""
        if not self.alerts:
            return AlertSeverity.INFO
        return min(a.severity for a in self.alerts)
    
    @property
    def services(self) -> set[str]:
        """Get unique services in group."""
        return {a.service for a in self.alerts if a.service}
    
    @property
    def duration(self) -> timedelta:
        """Get time span of alerts in group."""
        if not self.alerts:
            return timedelta(0)
        
        starts = [a.started_at for a in self.alerts]
        return max(starts) - min(starts)
    
    @property
    def is_storm(self) -> bool:
        """Check if this group represents an alert storm."""
        return self.size >= 10 and self.duration < timedelta(minutes=5)
    
    def add_alert(self, alert: Alert) -> None:
        """Add an alert to the group."""
        self.alerts.append(alert)
        self.updated_at = datetime.now(timezone.utc)
    
    def merge(self, other: "CorrelationGroup") -> None:
        """Merge another group into this one."""
        for alert in other.alerts:
            if alert not in self.alerts:
                self.alerts.append(alert)
        
        # Update correlation score (average)
        total_alerts = self.size + other.size
        self.correlation_score = (
            self.correlation_score * self.size +
            other.correlation_score * other.size
        ) / total_alerts
        
        self.updated_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "alert_count": self.size,
            "alert_ids": [a.id for a in self.alerts],
            "correlation_method": self.correlation_method.value,
            "correlation_score": self.correlation_score,
            "max_severity": self.max_severity.value,
            "services": list(self.services),
            "is_storm": self.is_storm,
            "root_cause_alert_id": self.root_cause_alert.id if self.root_cause_alert else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class CorrelationResult:
    """Result of alert correlation analysis."""
    
    groups: list[CorrelationGroup]
    uncorrelated_alerts: list[Alert]
    total_alerts: int
    correlation_rate: float
    processing_time_ms: float
    methods_used: list[CorrelationMethod]
    statistics: dict[str, Any] = field(default_factory=dict)
    
    @property
    def noise_reduction(self) -> float:
        """Calculate noise reduction percentage."""
        if self.total_alerts == 0:
            return 0.0
        
        grouped_alerts = sum(g.size for g in self.groups)
        return (1 - len(self.groups) / grouped_alerts) * 100 if grouped_alerts > 0 else 0.0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "groups": [g.to_dict() for g in self.groups],
            "uncorrelated_count": len(self.uncorrelated_alerts),
            "total_alerts": self.total_alerts,
            "correlation_rate": self.correlation_rate,
            "noise_reduction_percent": self.noise_reduction,
            "processing_time_ms": self.processing_time_ms,
            "methods_used": [m.value for m in self.methods_used],
            "statistics": self.statistics,
        }


class BaseCorrelator(ABC):
    """Abstract base class for alert correlators."""
    
    def __init__(self, config: Optional[CorrelatorConfig] = None):
        self.config = config or CorrelatorConfig()
    
    @property
    @abstractmethod
    def method(self) -> CorrelationMethod:
        """Return the correlation method type."""
        ...
    
    @abstractmethod
    def correlate(
        self,
        alerts: Sequence[Alert],
    ) -> list[CorrelationGroup]:
        """Correlate alerts into groups."""
        ...
    
    def _generate_group_id(self, alerts: Sequence[Alert]) -> str:
        """Generate unique ID for a group."""
        alert_ids = sorted(a.id for a in alerts)
        content = "|".join(alert_ids)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _generate_group_name(self, alerts: Sequence[Alert]) -> str:
        """Generate a descriptive name for the group."""
        if not alerts:
            return "Empty Group"
        
        # Common attributes
        services = {a.service for a in alerts if a.service}
        alert_names = {a.name for a in alerts}
        
        if len(services) == 1:
            service = next(iter(services))
            if len(alert_names) == 1:
                return f"{service}: {next(iter(alert_names))}"
            return f"{service}: {len(alerts)} related alerts"
        elif services:
            return f"Cross-service: {', '.join(sorted(services)[:3])}"
        
        if len(alert_names) == 1:
            return f"{next(iter(alert_names))} ({len(alerts)} instances)"
        
        return f"Alert cluster ({len(alerts)} alerts)"


class TimeWindowCorrelator(BaseCorrelator):
    """
    Time window based alert correlation.
    
    Groups alerts that occur within the same time window.
    """
    
    @property
    def method(self) -> CorrelationMethod:
        return CorrelationMethod.TIME_WINDOW
    
    def correlate(
        self,
        alerts: Sequence[Alert],
    ) -> list[CorrelationGroup]:
        """Group alerts by time window."""
        if len(alerts) < self.config.time_window.min_alerts_for_group:
            return []
        
        # Sort by start time
        sorted_alerts = sorted(alerts, key=lambda a: a.started_at)
        
        groups = []
        current_group: list[Alert] = []
        window_start: Optional[datetime] = None
        
        window_size = timedelta(seconds=self.config.time_window.window_seconds)
        
        for alert in sorted_alerts:
            if window_start is None:
                window_start = alert.started_at
                current_group = [alert]
            elif alert.started_at - window_start <= window_size:
                current_group.append(alert)
            else:
                # Start new window
                if len(current_group) >= self.config.time_window.min_alerts_for_group:
                    groups.append(self._create_group(current_group))
                
                window_start = alert.started_at
                current_group = [alert]
        
        # Don't forget the last group
        if len(current_group) >= self.config.time_window.min_alerts_for_group:
            groups.append(self._create_group(current_group))
        
        return groups
    
    def _create_group(self, alerts: list[Alert]) -> CorrelationGroup:
        """Create a correlation group from alerts."""
        now = datetime.now(timezone.utc)
        
        # Find potential root cause (earliest alert)
        root_cause = min(alerts, key=lambda a: a.started_at)
        
        # Calculate correlation score based on temporal density
        if len(alerts) > 1:
            time_span = (max(a.started_at for a in alerts) - 
                        min(a.started_at for a in alerts)).total_seconds()
            window_seconds = self.config.time_window.window_seconds
            
            # Higher density = higher score
            density = len(alerts) / max(time_span / 60, 1)  # alerts per minute
            score = min(1.0, density / 5)  # 5 alerts/min = score 1.0
        else:
            score = 0.5
        
        return CorrelationGroup(
            id=self._generate_group_id(alerts),
            name=self._generate_group_name(alerts),
            alerts=list(alerts),
            correlation_method=self.method,
            correlation_score=score,
            root_cause_alert=root_cause,
            created_at=now,
            updated_at=now,
            metadata={
                "window_seconds": self.config.time_window.window_seconds,
                "time_span_seconds": (
                    max(a.started_at for a in alerts) - 
                    min(a.started_at for a in alerts)
                ).total_seconds() if len(alerts) > 1 else 0,
            },
        )


class LabelSimilarityCorrelator(BaseCorrelator):
    """
    Label similarity based alert correlation.
    
    Groups alerts with similar labels using configurable similarity metrics.
    """
    
    @property
    def method(self) -> CorrelationMethod:
        return CorrelationMethod.LABEL_SIMILARITY
    
    def correlate(
        self,
        alerts: Sequence[Alert],
    ) -> list[CorrelationGroup]:
        """Group alerts by label similarity."""
        if len(alerts) < 2:
            return []
        
        # Build similarity matrix
        n = len(alerts)
        alert_list = list(alerts)
        similarity_matrix = np.zeros((n, n))
        
        for i in range(n):
            for j in range(i + 1, n):
                sim = self._calculate_similarity(alert_list[i], alert_list[j])
                similarity_matrix[i, j] = sim
                similarity_matrix[j, i] = sim
        
        # Cluster using simple threshold-based grouping
        groups = self._cluster_by_similarity(alert_list, similarity_matrix)
        
        return groups
    
    def _calculate_similarity(self, a1: Alert, a2: Alert) -> float:
        """Calculate label similarity between two alerts."""
        # Extract relevant labels
        labels1 = self._extract_labels(a1)
        labels2 = self._extract_labels(a2)
        
        if not labels1 or not labels2:
            return 0.0
        
        # Jaccard similarity
        intersection = len(labels1 & labels2)
        union = len(labels1 | labels2)
        
        if union == 0:
            return 0.0
        
        jaccard = intersection / union
        
        # Bonus for matching important labels
        important_matches = 0
        for label in self.config.important_labels:
            val1 = a1.labels.get(label) or getattr(a1, label, None)
            val2 = a2.labels.get(label) or getattr(a2, label, None)
            
            if val1 and val2 and val1 == val2:
                important_matches += 1
        
        important_bonus = important_matches * 0.1
        
        return min(1.0, jaccard + important_bonus)
    
    def _extract_labels(self, alert: Alert) -> set[str]:
        """Extract label key-value pairs as set of strings."""
        labels = set()
        
        for key, value in alert.labels.items():
            if key not in self.config.ignore_labels:
                labels.add(f"{key}={value}")
        
        # Add standard fields
        if alert.service:
            labels.add(f"service={alert.service}")
        if alert.namespace:
            labels.add(f"namespace={alert.namespace}")
        
        return labels
    
    def _cluster_by_similarity(
        self,
        alerts: list[Alert],
        similarity_matrix: np.ndarray,
    ) -> list[CorrelationGroup]:
        """Cluster alerts based on similarity matrix."""
        n = len(alerts)
        threshold = self.config.label_similarity_threshold
        
        # Simple agglomerative clustering
        assigned = [False] * n
        groups = []
        
        for i in range(n):
            if assigned[i]:
                continue
            
            # Start new group
            group_alerts = [alerts[i]]
            assigned[i] = True
            
            # Find all alerts similar to this one
            for j in range(i + 1, n):
                if not assigned[j] and similarity_matrix[i, j] >= threshold:
                    group_alerts.append(alerts[j])
                    assigned[j] = True
            
            if len(group_alerts) >= 2:  # Only create groups with 2+ alerts
                now = datetime.now(timezone.utc)
                
                # Average similarity within group
                indices = [alerts.index(a) for a in group_alerts]
                group_similarities = []
                for idx1 in indices:
                    for idx2 in indices:
                        if idx1 < idx2:
                            group_similarities.append(similarity_matrix[idx1, idx2])
                
                avg_similarity = statistics.mean(group_similarities) if group_similarities else 0.5
                
                groups.append(CorrelationGroup(
                    id=self._generate_group_id(group_alerts),
                    name=self._generate_group_name(group_alerts),
                    alerts=group_alerts,
                    correlation_method=self.method,
                    correlation_score=avg_similarity,
                    root_cause_alert=min(group_alerts, key=lambda a: a.started_at),
                    created_at=now,
                    updated_at=now,
                    metadata={"avg_similarity": avg_similarity},
                ))
        
        return groups


class CausalCorrelator(BaseCorrelator):
    """
    Causal relationship based alert correlation.
    
    Identifies cause-effect relationships between alerts based on
    timing and service dependencies.
    """
    
    def __init__(
        self,
        config: Optional[CorrelatorConfig] = None,
        service_dependencies: Optional[dict[str, list[str]]] = None,
    ):
        super().__init__(config)
        # service -> list of services it depends on
        self._dependencies = service_dependencies or {}
    
    @property
    def method(self) -> CorrelationMethod:
        return CorrelationMethod.CAUSAL
    
    def set_dependencies(self, dependencies: dict[str, list[str]]) -> None:
        """Set service dependency graph."""
        self._dependencies = dependencies
    
    def correlate(
        self,
        alerts: Sequence[Alert],
    ) -> list[CorrelationGroup]:
        """Group alerts by causal relationships."""
        if len(alerts) < 2:
            return []
        
        # Sort by time
        sorted_alerts = sorted(alerts, key=lambda a: a.started_at)
        
        # Build causal relationships
        causal_pairs: list[tuple[Alert, Alert, float]] = []
        
        for i, earlier in enumerate(sorted_alerts):
            for later in sorted_alerts[i + 1:]:
                confidence = self._calculate_causal_confidence(earlier, later)
                
                if confidence >= self.config.causal_confidence_threshold:
                    causal_pairs.append((earlier, later, confidence))
        
        # Build groups from causal chains
        groups = self._build_causal_groups(causal_pairs)
        
        return groups
    
    def _calculate_causal_confidence(
        self,
        earlier: Alert,
        later: Alert,
    ) -> float:
        """Calculate confidence that earlier alert caused later alert."""
        confidence = 0.0
        
        # Time proximity (alerts close in time more likely related)
        time_diff = (later.started_at - earlier.started_at).total_seconds()
        window = self.config.causal_time_window_seconds
        
        if time_diff > window:
            return 0.0
        
        time_factor = 1 - (time_diff / window)
        confidence += time_factor * 0.3
        
        # Check service dependencies
        if earlier.service and later.service:
            if later.service in self._dependencies.get(earlier.service, []):
                # Upstream failure -> downstream alert
                confidence += 0.4
            elif earlier.service == later.service:
                # Same service, likely related
                confidence += 0.2
        
        # Same namespace is a weak indicator
        if earlier.namespace and later.namespace == earlier.namespace:
            confidence += 0.1
        
        # Same cluster
        if earlier.cluster and later.cluster == earlier.cluster:
            confidence += 0.1
        
        # Severity escalation pattern
        if earlier.severity.numeric_priority > later.severity.numeric_priority:
            # Lower severity led to higher severity (warning -> critical)
            confidence += 0.1
        
        return min(1.0, confidence)
    
    def _build_causal_groups(
        self,
        causal_pairs: list[tuple[Alert, Alert, float]],
    ) -> list[CorrelationGroup]:
        """Build correlation groups from causal relationships."""
        if not causal_pairs:
            return []
        
        # Build adjacency list
        adjacency: dict[str, set[str]] = defaultdict(set)
        alert_by_id: dict[str, Alert] = {}
        confidence_map: dict[tuple[str, str], float] = {}
        
        for earlier, later, conf in causal_pairs:
            adjacency[earlier.id].add(later.id)
            alert_by_id[earlier.id] = earlier
            alert_by_id[later.id] = later
            confidence_map[(earlier.id, later.id)] = conf
        
        # Find connected components (groups)
        visited: set[str] = set()
        groups = []
        
        for start_id in alert_by_id:
            if start_id in visited:
                continue
            
            # BFS to find all connected alerts
            component: list[str] = []
            queue = [start_id]
            
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                
                visited.add(current)
                component.append(current)
                
                # Add both directions (cause and effect)
                for neighbor in adjacency[current]:
                    if neighbor not in visited:
                        queue.append(neighbor)
                
                # Check reverse direction too
                for aid, neighbors in adjacency.items():
                    if current in neighbors and aid not in visited:
                        queue.append(aid)
            
            if len(component) >= 2:
                group_alerts = [alert_by_id[aid] for aid in component]
                
                # Calculate average confidence
                confidences = []
                for c1 in component:
                    for c2 in component:
                        if (c1, c2) in confidence_map:
                            confidences.append(confidence_map[(c1, c2)])
                
                avg_conf = statistics.mean(confidences) if confidences else 0.5
                
                # Root cause is the earliest alert
                root_cause = min(group_alerts, key=lambda a: a.started_at)
                
                now = datetime.now(timezone.utc)
                groups.append(CorrelationGroup(
                    id=self._generate_group_id(group_alerts),
                    name=f"Causal chain from {root_cause.name}",
                    alerts=group_alerts,
                    correlation_method=self.method,
                    correlation_score=avg_conf,
                    root_cause_alert=root_cause,
                    created_at=now,
                    updated_at=now,
                    metadata={
                        "causal_pairs": len([p for p in causal_pairs 
                                            if p[0].id in component and p[1].id in component]),
                    },
                ))
        
        return groups


class MLClusteringCorrelator(BaseCorrelator):
    """
    Machine learning based alert clustering.
    
    Uses DBSCAN-like clustering on alert features.
    """
    
    @property
    def method(self) -> CorrelationMethod:
        return CorrelationMethod.ML_CLUSTERING
    
    def correlate(
        self,
        alerts: Sequence[Alert],
    ) -> list[CorrelationGroup]:
        """Cluster alerts using ML."""
        if len(alerts) < self.config.clustering_min_samples:
            return []
        
        # Extract features
        features = self._extract_features(alerts)
        
        # Normalize features
        features_normalized = self._normalize_features(features)
        
        # Cluster using DBSCAN
        labels = self._dbscan(
            features_normalized,
            eps=self.config.clustering_eps,
            min_samples=self.config.clustering_min_samples,
        )
        
        # Build groups from clusters
        groups = self._build_groups_from_labels(list(alerts), labels)
        
        return groups
    
    def _extract_features(self, alerts: Sequence[Alert]) -> np.ndarray:
        """Extract numerical features from alerts."""
        features = []
        
        for alert in alerts:
            feat = []
            
            # Time features (normalized to 0-1)
            ts = alert.started_at.timestamp()
            feat.append(ts / 1e10)  # Rough normalization
            
            # Severity (0-4)
            feat.append(alert.severity.numeric_priority / 5)
            
            # Hash-based features for categorical data
            service_hash = hash(alert.service or "") % 1000 / 1000
            namespace_hash = hash(alert.namespace or "") % 1000 / 1000
            name_hash = hash(alert.name) % 1000 / 1000
            
            feat.extend([service_hash, namespace_hash, name_hash])
            
            # Label count
            feat.append(len(alert.labels) / 20)  # Normalize
            
            features.append(feat)
        
        return np.array(features)
    
    def _normalize_features(self, features: np.ndarray) -> np.ndarray:
        """Normalize features to zero mean and unit variance."""
        mean = np.mean(features, axis=0)
        std = np.std(features, axis=0) + 1e-8
        return (features - mean) / std
    
    def _dbscan(
        self,
        X: np.ndarray,
        eps: float,
        min_samples: int,
    ) -> np.ndarray:
        """DBSCAN clustering."""
        n = X.shape[0]
        labels = np.full(n, -1)
        cluster_id = 0
        
        for i in range(n):
            if labels[i] != -1:
                continue
            
            # Find neighbors
            distances = np.linalg.norm(X - X[i], axis=1)
            neighbors = np.where(distances <= eps)[0]
            
            if len(neighbors) < min_samples:
                continue
            
            # Start new cluster
            labels[i] = cluster_id
            seeds = list(neighbors)
            seeds.remove(i)
            
            while seeds:
                q = seeds.pop(0)
                if labels[q] == -1:
                    labels[q] = cluster_id
                elif labels[q] != cluster_id:
                    continue
                
                q_distances = np.linalg.norm(X - X[q], axis=1)
                q_neighbors = np.where(q_distances <= eps)[0]
                
                if len(q_neighbors) >= min_samples:
                    for neighbor in q_neighbors:
                        if labels[neighbor] == -1:
                            seeds.append(neighbor)
                            labels[neighbor] = cluster_id
            
            cluster_id += 1
        
        return labels
    
    def _build_groups_from_labels(
        self,
        alerts: list[Alert],
        labels: np.ndarray,
    ) -> list[CorrelationGroup]:
        """Build correlation groups from cluster labels."""
        groups = []
        unique_labels = set(labels) - {-1}  # Exclude noise
        
        for label in unique_labels:
            indices = np.where(labels == label)[0]
            group_alerts = [alerts[i] for i in indices]
            
            if len(group_alerts) < 2:
                continue
            
            now = datetime.now(timezone.utc)
            groups.append(CorrelationGroup(
                id=self._generate_group_id(group_alerts),
                name=self._generate_group_name(group_alerts),
                alerts=group_alerts,
                correlation_method=self.method,
                correlation_score=0.7,  # Default for ML clustering
                root_cause_alert=min(group_alerts, key=lambda a: a.started_at),
                created_at=now,
                updated_at=now,
                metadata={"cluster_id": int(label), "cluster_size": len(group_alerts)},
            ))
        
        return groups


class AlertCorrelator:
    """
    High-level alert correlator for AutoSRE.
    
    Combines multiple correlation methods to reduce alert noise
    and identify related alerts.
    
    Example:
        correlator = AlertCorrelator()
        result = correlator.correlate(alerts)
        
        for group in result.groups:
            print(f"Group: {group.name} ({group.size} alerts)")
    """
    
    def __init__(
        self,
        config: Optional[CorrelatorConfig] = None,
        service_dependencies: Optional[dict[str, list[str]]] = None,
    ):
        self.config = config or CorrelatorConfig()
        
        # Initialize correlators
        self._correlators: dict[CorrelationMethod, BaseCorrelator] = {
            CorrelationMethod.TIME_WINDOW: TimeWindowCorrelator(self.config),
            CorrelationMethod.LABEL_SIMILARITY: LabelSimilarityCorrelator(self.config),
            CorrelationMethod.CAUSAL: CausalCorrelator(self.config, service_dependencies),
            CorrelationMethod.ML_CLUSTERING: MLClusteringCorrelator(self.config),
        }
        
        # Custom correlation rules
        self._rules: list[CorrelationRule] = []
        
        # Alert deduplication cache
        self._seen_fingerprints: dict[str, datetime] = {}
    
    def add_rule(self, rule: CorrelationRule) -> None:
        """Add a custom correlation rule."""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: -r.priority)
    
    def set_service_dependencies(self, dependencies: dict[str, list[str]]) -> None:
        """Set service dependency graph for causal correlation."""
        causal = self._correlators.get(CorrelationMethod.CAUSAL)
        if isinstance(causal, CausalCorrelator):
            causal.set_dependencies(dependencies)
    
    def correlate(
        self,
        alerts: Sequence[Alert],
        methods: Optional[list[CorrelationMethod]] = None,
    ) -> CorrelationResult:
        """
        Correlate alerts using configured methods.
        
        Args:
            alerts: List of alerts to correlate
            methods: Specific methods to use (default: config.correlation_methods)
        
        Returns:
            CorrelationResult with groups and statistics
        """
        import time
        start_time = time.time()
        
        methods = methods or self.config.correlation_methods
        
        # Deduplicate alerts first
        deduped_alerts = self._deduplicate(list(alerts))
        
        # Apply custom rules first
        rule_groups = self._apply_rules(deduped_alerts)
        
        # Track which alerts are already grouped by rules
        rule_grouped_ids = {a.id for g in rule_groups for a in g.alerts}
        remaining_alerts = [a for a in deduped_alerts if a.id not in rule_grouped_ids]
        
        # Run each correlation method
        all_groups: list[CorrelationGroup] = list(rule_groups)
        
        for method in methods:
            correlator = self._correlators.get(method)
            if not correlator:
                continue
            
            try:
                method_groups = correlator.correlate(remaining_alerts)
                
                # Remove alerts that are now grouped
                grouped_ids = {a.id for g in method_groups for a in g.alerts}
                remaining_alerts = [a for a in remaining_alerts if a.id not in grouped_ids]
                
                all_groups.extend(method_groups)
            except Exception as e:
                logger.error(f"Correlation method {method} failed: {e}")
        
        # Merge overlapping groups
        merged_groups = self._merge_overlapping_groups(all_groups)
        
        # Filter by minimum correlation score
        filtered_groups = [
            g for g in merged_groups 
            if g.correlation_score >= self.config.min_correlation_score
        ]
        
        # Calculate statistics
        processing_time = (time.time() - start_time) * 1000
        total_alerts = len(alerts)
        grouped_alerts = sum(g.size for g in filtered_groups)
        
        return CorrelationResult(
            groups=filtered_groups,
            uncorrelated_alerts=remaining_alerts,
            total_alerts=total_alerts,
            correlation_rate=grouped_alerts / total_alerts if total_alerts > 0 else 0.0,
            processing_time_ms=processing_time,
            methods_used=methods,
            statistics={
                "deduplicated_alerts": len(deduped_alerts),
                "rule_groups": len(rule_groups),
                "final_groups": len(filtered_groups),
                "uncorrelated": len(remaining_alerts),
                "noise_reduction_percent": (
                    (1 - len(filtered_groups) / grouped_alerts) * 100 
                    if grouped_alerts > 0 else 0
                ),
            },
        )
    
    def _deduplicate(self, alerts: list[Alert]) -> list[Alert]:
        """Remove duplicate alerts within dedup window."""
        deduped = []
        now = datetime.now(timezone.utc)
        window = timedelta(seconds=self.config.dedup_window_seconds)
        
        for alert in alerts:
            fp = alert.fingerprint
            if fp:
                last_seen = self._seen_fingerprints.get(fp)
                if last_seen and (now - last_seen) < window:
                    continue
                self._seen_fingerprints[fp] = now
            
            deduped.append(alert)
        
        # Clean old entries from cache
        cutoff = now - window * 10
        self._seen_fingerprints = {
            fp: ts for fp, ts in self._seen_fingerprints.items()
            if ts > cutoff
        }
        
        return deduped
    
    def _apply_rules(self, alerts: list[Alert]) -> list[CorrelationGroup]:
        """Apply custom correlation rules."""
        if not self._rules:
            return []
        
        # Group alerts by matching rules
        rule_groups: dict[str, list[Alert]] = defaultdict(list)
        
        for alert in alerts:
            for rule in self._rules:
                if not rule.enabled:
                    continue
                
                if rule.matches(alert):
                    group_key = rule.get_group_key(alert)
                    rule_groups[group_key].append(alert)
                    break  # First matching rule wins
        
        # Convert to CorrelationGroups
        groups = []
        now = datetime.now(timezone.utc)
        
        for group_key, group_alerts in rule_groups.items():
            if len(group_alerts) < 2:
                continue
            
            # Find the rule that created this group
            rule_name = group_key.split("|")[0]
            
            groups.append(CorrelationGroup(
                id=hashlib.sha256(group_key.encode()).hexdigest()[:16],
                name=f"Rule: {rule_name}",
                alerts=group_alerts,
                correlation_method=CorrelationMethod.ENSEMBLE,  # Rules are a form of ensemble
                correlation_score=1.0,  # Rules are explicit matches
                root_cause_alert=min(group_alerts, key=lambda a: a.started_at),
                created_at=now,
                updated_at=now,
                metadata={"rule_name": rule_name, "group_key": group_key},
            ))
        
        return groups
    
    def _merge_overlapping_groups(
        self,
        groups: list[CorrelationGroup],
    ) -> list[CorrelationGroup]:
        """Merge groups that share alerts."""
        if len(groups) <= 1:
            return groups
        
        # Build alert -> groups mapping
        alert_to_groups: dict[str, list[int]] = defaultdict(list)
        for i, group in enumerate(groups):
            for alert in group.alerts:
                alert_to_groups[alert.id].append(i)
        
        # Find groups to merge (share alerts)
        merged_indices: set[int] = set()
        result = []
        
        for i, group in enumerate(groups):
            if i in merged_indices:
                continue
            
            # Find all groups that overlap with this one
            overlapping = set()
            for alert in group.alerts:
                overlapping.update(alert_to_groups[alert.id])
            
            if len(overlapping) > 1:
                # Merge all overlapping groups
                merged_group = group
                for j in overlapping:
                    if j != i and j not in merged_indices:
                        merged_group.merge(groups[j])
                        merged_indices.add(j)
                
                result.append(merged_group)
                merged_indices.add(i)
            else:
                result.append(group)
        
        return result
    
    def detect_alert_storm(
        self,
        alerts: Sequence[Alert],
        threshold: int = 10,
        window_seconds: float = 300.0,
    ) -> bool:
        """
        Detect if there's an alert storm.
        
        An alert storm is a sudden burst of alerts that may indicate
        a systemic issue or monitoring misconfiguration.
        """
        if len(alerts) < threshold:
            return False
        
        # Count alerts in time windows
        sorted_alerts = sorted(alerts, key=lambda a: a.started_at)
        window = timedelta(seconds=window_seconds)
        
        for i, alert in enumerate(sorted_alerts):
            window_end = alert.started_at + window
            count = sum(
                1 for a in sorted_alerts[i:]
                if a.started_at <= window_end
            )
            
            if count >= threshold:
                return True
        
        return False
    
    def get_statistics(self) -> dict[str, Any]:
        """Get correlation statistics."""
        return {
            "rules_count": len(self._rules),
            "dedup_cache_size": len(self._seen_fingerprints),
            "available_methods": [m.value for m in self._correlators.keys()],
            "config": {
                "time_window_seconds": self.config.time_window.window_seconds,
                "similarity_threshold": self.config.label_similarity_threshold,
                "min_correlation_score": self.config.min_correlation_score,
            },
        }
