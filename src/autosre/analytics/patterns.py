"""
Pattern Recognition for Alerts and Incidents

Identifies patterns in alert and incident data including:
- Recurring incidents (same alert, similar symptoms)
- Correlated alerts (alerts that fire together)
- Cascade patterns (alert A always precedes alert B)
- Incident clusters (related incidents grouped by similarity)
- Root cause patterns (common underlying causes)
"""

import hashlib
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PatternType(str, Enum):
    """Types of patterns that can be detected."""
    RECURRING = "recurring"          # Same incident repeating
    CORRELATED = "correlated"        # Alerts that fire together
    CASCADE = "cascade"              # Alert A leads to alert B
    TEMPORAL = "temporal"            # Time-based patterns
    INFRASTRUCTURE = "infrastructure"  # Common infrastructure cause
    DEPLOYMENT = "deployment"        # Related to deployments
    CAPACITY = "capacity"            # Resource exhaustion patterns
    CONFIGURATION = "configuration"  # Config-related patterns


@dataclass
class AlertPattern:
    """A detected pattern in alerts."""
    pattern_id: str
    pattern_type: PatternType
    confidence: float  # 0-1
    occurrences: int
    first_seen: datetime
    last_seen: datetime
    affected_services: list[str]
    alert_names: list[str]
    description: str
    root_cause_hypothesis: Optional[str] = None
    recommended_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type.value,
            "confidence": self.confidence,
            "occurrences": self.occurrences,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "affected_services": self.affected_services,
            "alert_names": self.alert_names,
            "description": self.description,
            "root_cause_hypothesis": self.root_cause_hypothesis,
            "recommended_actions": self.recommended_actions,
            "metadata": self.metadata,
        }
    
    @property
    def is_active(self) -> bool:
        """Check if pattern was seen recently (within 7 days)."""
        return self.last_seen > datetime.now(timezone.utc) - timedelta(days=7)


@dataclass
class IncidentCluster:
    """A cluster of related incidents."""
    cluster_id: str
    incidents: list[dict]
    common_services: list[str]
    common_symptoms: list[str]
    pattern_types: list[PatternType]
    similarity_score: float  # 0-1
    suggested_root_cause: Optional[str]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def size(self) -> int:
        return len(self.incidents)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "cluster_id": self.cluster_id,
            "incident_count": len(self.incidents),
            "common_services": self.common_services,
            "common_symptoms": self.common_symptoms,
            "pattern_types": [p.value for p in self.pattern_types],
            "similarity_score": self.similarity_score,
            "suggested_root_cause": self.suggested_root_cause,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class CorrelationResult:
    """Result of alert correlation analysis."""
    alert_a: str
    alert_b: str
    correlation_type: str  # "co-occurrence", "cascade", "inverse"
    correlation_strength: float  # 0-1
    typical_lag_seconds: float  # Time between alerts
    occurrences: int
    
    def to_dict(self) -> dict:
        return {
            "alert_a": self.alert_a,
            "alert_b": self.alert_b,
            "correlation_type": self.correlation_type,
            "correlation_strength": self.correlation_strength,
            "typical_lag_seconds": self.typical_lag_seconds,
            "occurrences": self.occurrences,
        }


class PatternRecognizer:
    """
    Recognizes patterns in alert and incident data.
    
    Uses multiple strategies:
    - Text similarity for incident matching
    - Temporal analysis for cascade detection
    - Co-occurrence analysis for correlation
    - Service graph analysis for infrastructure patterns
    """
    
    def __init__(
        self,
        similarity_threshold: float = 0.7,
        correlation_window_minutes: int = 30,
        min_pattern_occurrences: int = 3,
    ):
        self.similarity_threshold = similarity_threshold
        self.correlation_window = timedelta(minutes=correlation_window_minutes)
        self.min_occurrences = min_pattern_occurrences
        
        # Pattern matchers for known issue types
        self.pattern_matchers = self._build_pattern_matchers()
    
    def find_patterns(
        self,
        alerts: list[dict],
        incidents: Optional[list[dict]] = None,
    ) -> list[AlertPattern]:
        """
        Find all patterns in the provided alert data.
        
        Args:
            alerts: List of alert dictionaries
            incidents: Optional list of incident dictionaries
            
        Returns:
            List of detected patterns
        """
        patterns = []
        
        # Find recurring patterns
        recurring = self._find_recurring_patterns(alerts)
        patterns.extend(recurring)
        
        # Find correlation patterns
        correlations = self._find_correlation_patterns(alerts)
        patterns.extend(correlations)
        
        # Find cascade patterns
        cascades = self._find_cascade_patterns(alerts)
        patterns.extend(cascades)
        
        # Find infrastructure patterns
        infra_patterns = self._find_infrastructure_patterns(alerts)
        patterns.extend(infra_patterns)
        
        # Find temporal patterns
        temporal = self._find_temporal_patterns(alerts)
        patterns.extend(temporal)
        
        # Sort by confidence and recency
        patterns.sort(
            key=lambda p: (p.confidence, p.last_seen),
            reverse=True,
        )
        
        return patterns
    
    def cluster_incidents(
        self,
        incidents: list[dict],
        min_cluster_size: int = 2,
    ) -> list[IncidentCluster]:
        """
        Cluster similar incidents together.
        
        Args:
            incidents: List of incident dictionaries
            min_cluster_size: Minimum incidents per cluster
            
        Returns:
            List of incident clusters
        """
        if len(incidents) < min_cluster_size:
            return []
        
        # Calculate similarity matrix
        n = len(incidents)
        similarities = [[0.0] * n for _ in range(n)]
        
        for i in range(n):
            for j in range(i + 1, n):
                sim = self._calculate_incident_similarity(incidents[i], incidents[j])
                similarities[i][j] = sim
                similarities[j][i] = sim
        
        # Simple clustering: group incidents with similarity above threshold
        clusters: list[IncidentCluster] = []
        assigned = set()
        
        for i in range(n):
            if i in assigned:
                continue
            
            # Find all incidents similar to this one
            cluster_indices = [i]
            for j in range(i + 1, n):
                if j not in assigned and similarities[i][j] >= self.similarity_threshold:
                    cluster_indices.append(j)
            
            if len(cluster_indices) >= min_cluster_size:
                cluster_incidents = [incidents[idx] for idx in cluster_indices]
                cluster = self._create_cluster(cluster_incidents)
                clusters.append(cluster)
                assigned.update(cluster_indices)
        
        return clusters
    
    def find_correlations(
        self,
        alerts: list[dict],
    ) -> list[CorrelationResult]:
        """
        Find correlations between different alert types.
        
        Identifies:
        - Co-occurrence: Alerts that fire together
        - Cascade: Alert A typically precedes Alert B
        - Inverse: Alert A and B rarely fire together
        """
        # Group alerts by name
        alert_groups = defaultdict(list)
        for alert in alerts:
            name = alert.get("name") or alert.get("alert_name", "unknown")
            alert_groups[name].append(alert)
        
        correlations = []
        alert_names = list(alert_groups.keys())
        
        for i, name_a in enumerate(alert_names):
            for name_b in alert_names[i + 1:]:
                # Check for correlation
                result = self._check_correlation(
                    name_a, alert_groups[name_a],
                    name_b, alert_groups[name_b],
                )
                if result and result.correlation_strength >= 0.5:
                    correlations.append(result)
        
        # Sort by strength
        correlations.sort(key=lambda c: c.correlation_strength, reverse=True)
        return correlations
    
    def match_known_patterns(
        self,
        alert: dict,
    ) -> list[tuple[PatternType, float, str]]:
        """
        Match an alert against known patterns.
        
        Returns list of (pattern_type, confidence, description) tuples.
        """
        matches = []
        
        alert_text = self._get_alert_text(alert)
        
        for pattern_type, matchers in self.pattern_matchers.items():
            for matcher, description in matchers:
                if matcher.search(alert_text):
                    confidence = 0.8 if matcher.pattern.count("|") == 0 else 0.6
                    matches.append((pattern_type, confidence, description))
        
        return matches
    
    def _find_recurring_patterns(
        self,
        alerts: list[dict],
    ) -> list[AlertPattern]:
        """Find recurring alert patterns."""
        patterns = []
        
        # Group by alert name
        by_name = defaultdict(list)
        for alert in alerts:
            name = alert.get("name") or alert.get("alert_name", "unknown")
            by_name[name].append(alert)
        
        for name, alert_list in by_name.items():
            if len(alert_list) >= self.min_occurrences:
                # Get affected services
                services = list(set(
                    a.get("service") or a.get("labels", {}).get("service", "unknown")
                    for a in alert_list
                ))
                
                # Parse timestamps
                timestamps = []
                for a in alert_list:
                    ts = a.get("timestamp") or a.get("starts_at")
                    if isinstance(ts, str):
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if ts:
                        timestamps.append(ts)
                
                if not timestamps:
                    continue
                
                timestamps.sort()
                
                # Calculate recurrence interval
                intervals = [
                    (timestamps[i + 1] - timestamps[i]).total_seconds()
                    for i in range(len(timestamps) - 1)
                ]
                
                avg_interval = sum(intervals) / len(intervals) if intervals else 0
                interval_str = self._format_interval(avg_interval)
                
                pattern = AlertPattern(
                    pattern_id=self._generate_pattern_id("recurring", name),
                    pattern_type=PatternType.RECURRING,
                    confidence=min(0.9, 0.5 + (len(alert_list) * 0.05)),
                    occurrences=len(alert_list),
                    first_seen=timestamps[0],
                    last_seen=timestamps[-1],
                    affected_services=services,
                    alert_names=[name],
                    description=f"Alert '{name}' recurs approximately every {interval_str}",
                    recommended_actions=[
                        "Investigate recurring root cause",
                        "Consider permanent fix or automation",
                        "Review if alert threshold needs adjustment",
                    ],
                    metadata={"average_interval_seconds": avg_interval},
                )
                patterns.append(pattern)
        
        return patterns
    
    def _find_correlation_patterns(
        self,
        alerts: list[dict],
    ) -> list[AlertPattern]:
        """Find correlated alert patterns."""
        correlations = self.find_correlations(alerts)
        patterns = []
        
        for corr in correlations:
            if corr.correlation_strength < 0.6:
                continue
            
            pattern = AlertPattern(
                pattern_id=self._generate_pattern_id(
                    "correlated", f"{corr.alert_a}_{corr.alert_b}"
                ),
                pattern_type=PatternType.CORRELATED,
                confidence=corr.correlation_strength,
                occurrences=corr.occurrences,
                first_seen=datetime.now(timezone.utc) - timedelta(days=30),
                last_seen=datetime.now(timezone.utc),
                affected_services=[],
                alert_names=[corr.alert_a, corr.alert_b],
                description=(
                    f"Alerts '{corr.alert_a}' and '{corr.alert_b}' "
                    f"are correlated ({corr.correlation_type})"
                ),
                root_cause_hypothesis="These alerts may share a common underlying cause",
                recommended_actions=[
                    "Consider consolidating into a single alert",
                    "Investigate shared root cause",
                    "Set up alert grouping/deduplication",
                ],
                metadata={
                    "correlation_type": corr.correlation_type,
                    "typical_lag_seconds": corr.typical_lag_seconds,
                },
            )
            patterns.append(pattern)
        
        return patterns
    
    def _find_cascade_patterns(
        self,
        alerts: list[dict],
    ) -> list[AlertPattern]:
        """Find cascade patterns (A -> B)."""
        patterns = []
        
        # Group alerts by timestamp
        sorted_alerts = sorted(
            alerts,
            key=lambda a: a.get("timestamp") or a.get("starts_at", ""),
        )
        
        # Look for consistent sequences
        sequences = defaultdict(list)
        
        for i, alert in enumerate(sorted_alerts[:-1]):
            ts_a = alert.get("timestamp") or alert.get("starts_at")
            name_a = alert.get("name") or alert.get("alert_name", "unknown")
            
            for next_alert in sorted_alerts[i + 1:i + 10]:  # Look at next 10 alerts
                ts_b = next_alert.get("timestamp") or next_alert.get("starts_at")
                name_b = next_alert.get("name") or next_alert.get("alert_name", "unknown")
                
                if name_a == name_b:
                    continue
                
                # Parse timestamps
                if isinstance(ts_a, str):
                    ts_a = datetime.fromisoformat(ts_a.replace("Z", "+00:00"))
                if isinstance(ts_b, str):
                    ts_b = datetime.fromisoformat(ts_b.replace("Z", "+00:00"))
                
                if ts_a and ts_b:
                    delta = (ts_b - ts_a).total_seconds()
                    if 0 < delta < self.correlation_window.total_seconds():
                        sequences[(name_a, name_b)].append(delta)
        
        # Find consistent cascades
        for (name_a, name_b), intervals in sequences.items():
            if len(intervals) >= self.min_occurrences:
                avg_interval = sum(intervals) / len(intervals)
                interval_str = self._format_interval(avg_interval)
                
                pattern = AlertPattern(
                    pattern_id=self._generate_pattern_id("cascade", f"{name_a}_{name_b}"),
                    pattern_type=PatternType.CASCADE,
                    confidence=min(0.9, 0.5 + (len(intervals) * 0.05)),
                    occurrences=len(intervals),
                    first_seen=datetime.now(timezone.utc) - timedelta(days=30),
                    last_seen=datetime.now(timezone.utc),
                    affected_services=[],
                    alert_names=[name_a, name_b],
                    description=(
                        f"Alert '{name_a}' typically leads to '{name_b}' "
                        f"after ~{interval_str}"
                    ),
                    root_cause_hypothesis=f"'{name_a}' may be the upstream cause of '{name_b}'",
                    recommended_actions=[
                        f"Focus on resolving '{name_a}' first",
                        "Consider suppressing downstream alert during investigation",
                        "Add automation to prevent cascade",
                    ],
                    metadata={"typical_lag_seconds": avg_interval},
                )
                patterns.append(pattern)
        
        return patterns
    
    def _find_infrastructure_patterns(
        self,
        alerts: list[dict],
    ) -> list[AlertPattern]:
        """Find infrastructure-related patterns."""
        patterns = []
        
        # Group alerts by labels/tags that suggest infrastructure
        infra_groups = defaultdict(list)
        
        infra_labels = ["node", "host", "cluster", "zone", "region", "namespace"]
        
        for alert in alerts:
            labels = alert.get("labels", {})
            for label in infra_labels:
                if label in labels:
                    key = (label, labels[label])
                    infra_groups[key].append(alert)
        
        # Find patterns in infrastructure groups
        for (label, value), alert_list in infra_groups.items():
            if len(alert_list) >= self.min_occurrences:
                alert_names = list(set(
                    a.get("name") or a.get("alert_name", "unknown")
                    for a in alert_list
                ))
                
                pattern = AlertPattern(
                    pattern_id=self._generate_pattern_id("infra", f"{label}_{value}"),
                    pattern_type=PatternType.INFRASTRUCTURE,
                    confidence=min(0.85, 0.5 + (len(alert_list) * 0.03)),
                    occurrences=len(alert_list),
                    first_seen=datetime.now(timezone.utc) - timedelta(days=30),
                    last_seen=datetime.now(timezone.utc),
                    affected_services=[],
                    alert_names=alert_names[:5],
                    description=(
                        f"Multiple alerts ({len(alert_list)}) related to "
                        f"{label}='{value}'"
                    ),
                    root_cause_hypothesis=(
                        f"Infrastructure component '{value}' may have underlying issues"
                    ),
                    recommended_actions=[
                        f"Investigate health of {label} '{value}'",
                        "Check for hardware issues or resource exhaustion",
                        "Consider scaling or replacing infrastructure",
                    ],
                    metadata={"label": label, "value": value},
                )
                patterns.append(pattern)
        
        return patterns
    
    def _find_temporal_patterns(
        self,
        alerts: list[dict],
    ) -> list[AlertPattern]:
        """Find time-based patterns."""
        patterns = []
        
        # Group by hour of day
        hourly_counts = defaultdict(int)
        # Group by day of week
        daily_counts = defaultdict(int)
        
        for alert in alerts:
            ts = alert.get("timestamp") or alert.get("starts_at")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            
            if ts:
                hourly_counts[ts.hour] += 1
                daily_counts[ts.weekday()] += 1
        
        total_alerts = len(alerts)
        if total_alerts < self.min_occurrences:
            return patterns
        
        # Find peak hours
        avg_per_hour = total_alerts / 24
        peak_hours = [
            hour for hour, count in hourly_counts.items()
            if count > avg_per_hour * 2
        ]
        
        if peak_hours:
            pattern = AlertPattern(
                pattern_id=self._generate_pattern_id("temporal", "hourly_peak"),
                pattern_type=PatternType.TEMPORAL,
                confidence=0.7,
                occurrences=sum(hourly_counts[h] for h in peak_hours),
                first_seen=datetime.now(timezone.utc) - timedelta(days=30),
                last_seen=datetime.now(timezone.utc),
                affected_services=[],
                alert_names=[],
                description=(
                    f"Alerts peak during hours: {', '.join(f'{h:02d}:00' for h in peak_hours)}"
                ),
                recommended_actions=[
                    "Align maintenance windows with low-alert periods",
                    "Investigate what causes peak-hour alerts",
                    "Consider time-based alert tuning",
                ],
                metadata={"peak_hours": peak_hours},
            )
            patterns.append(pattern)
        
        # Find peak days
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        avg_per_day = total_alerts / 7
        peak_days = [
            day_names[day] for day, count in daily_counts.items()
            if count > avg_per_day * 1.5
        ]
        
        if peak_days:
            pattern = AlertPattern(
                pattern_id=self._generate_pattern_id("temporal", "daily_peak"),
                pattern_type=PatternType.TEMPORAL,
                confidence=0.7,
                occurrences=total_alerts,
                first_seen=datetime.now(timezone.utc) - timedelta(days=30),
                last_seen=datetime.now(timezone.utc),
                affected_services=[],
                alert_names=[],
                description=f"Alerts peak on: {', '.join(peak_days)}",
                recommended_actions=[
                    "Investigate activities on peak days (deployments, batch jobs)",
                    "Consider adjusting change freeze windows",
                    "Review scheduling of automated tasks",
                ],
                metadata={"peak_days": peak_days},
            )
            patterns.append(pattern)
        
        return patterns
    
    def _calculate_incident_similarity(
        self,
        incident_a: dict,
        incident_b: dict,
    ) -> float:
        """Calculate similarity between two incidents."""
        score = 0.0
        weights_total = 0.0
        
        # Service match (high weight)
        service_a = incident_a.get("service", "")
        service_b = incident_b.get("service", "")
        if service_a and service_b:
            weights_total += 0.3
            if service_a == service_b:
                score += 0.3
        
        # Alert name match
        name_a = incident_a.get("alert_name") or incident_a.get("name", "")
        name_b = incident_b.get("alert_name") or incident_b.get("name", "")
        if name_a and name_b:
            weights_total += 0.25
            if name_a == name_b:
                score += 0.25
            elif self._fuzzy_match(name_a, name_b):
                score += 0.15
        
        # Severity match
        sev_a = incident_a.get("severity", "")
        sev_b = incident_b.get("severity", "")
        if sev_a and sev_b:
            weights_total += 0.15
            if sev_a == sev_b:
                score += 0.15
        
        # Description/summary similarity
        desc_a = incident_a.get("description") or incident_a.get("summary", "")
        desc_b = incident_b.get("description") or incident_b.get("summary", "")
        if desc_a and desc_b:
            weights_total += 0.3
            score += 0.3 * self._text_similarity(desc_a, desc_b)
        
        if weights_total == 0:
            return 0.0
        
        return score / weights_total
    
    def _fuzzy_match(self, a: str, b: str) -> bool:
        """Simple fuzzy matching for alert names."""
        # Normalize
        a = a.lower().replace("_", " ").replace("-", " ")
        b = b.lower().replace("_", " ").replace("-", " ")
        
        # Check if one contains the other
        if a in b or b in a:
            return True
        
        # Check common words
        words_a = set(a.split())
        words_b = set(b.split())
        common = words_a & words_b
        
        return len(common) >= len(words_a) * 0.5
    
    def _text_similarity(self, a: str, b: str) -> float:
        """Calculate text similarity using Jaccard similarity."""
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        
        if not words_a or not words_b:
            return 0.0
        
        intersection = len(words_a & words_b)
        union = len(words_a | words_b)
        
        return intersection / union if union > 0 else 0.0
    
    def _create_cluster(
        self,
        incidents: list[dict],
    ) -> IncidentCluster:
        """Create an incident cluster from related incidents."""
        # Find common services
        services = [i.get("service", "unknown") for i in incidents]
        common_services = list(set(s for s in services if services.count(s) > 1))
        
        # Extract common symptoms from descriptions
        descriptions = [
            i.get("description") or i.get("summary", "")
            for i in incidents
        ]
        common_symptoms = self._extract_common_terms(descriptions)
        
        # Determine pattern types
        pattern_types = []
        alert_names = [i.get("alert_name") or i.get("name", "") for i in incidents]
        if len(set(alert_names)) == 1:
            pattern_types.append(PatternType.RECURRING)
        
        # Calculate average similarity
        n = len(incidents)
        total_sim = 0.0
        count = 0
        for i in range(n):
            for j in range(i + 1, n):
                total_sim += self._calculate_incident_similarity(incidents[i], incidents[j])
                count += 1
        avg_similarity = total_sim / count if count > 0 else 0.0
        
        # Suggest root cause
        root_cause = None
        if common_services:
            root_cause = f"Issue with service(s): {', '.join(common_services[:3])}"
        elif common_symptoms:
            root_cause = f"Related symptoms: {', '.join(common_symptoms[:3])}"
        
        return IncidentCluster(
            cluster_id=self._generate_pattern_id(
                "cluster",
                hashlib.md5("_".join(alert_names).encode()).hexdigest()[:8],
            ),
            incidents=incidents,
            common_services=common_services,
            common_symptoms=common_symptoms,
            pattern_types=pattern_types,
            similarity_score=avg_similarity,
            suggested_root_cause=root_cause,
        )
    
    def _extract_common_terms(
        self,
        texts: list[str],
        min_frequency: float = 0.5,
    ) -> list[str]:
        """Extract terms that appear in at least min_frequency of texts."""
        if not texts:
            return []
        
        # Tokenize and count
        term_counts = defaultdict(int)
        for text in texts:
            words = set(text.lower().split())
            for word in words:
                if len(word) > 3:  # Skip short words
                    term_counts[word] += 1
        
        # Filter by frequency
        min_count = len(texts) * min_frequency
        common = [
            term for term, count in term_counts.items()
            if count >= min_count
        ]
        
        return sorted(common, key=lambda t: term_counts[t], reverse=True)[:10]
    
    def _check_correlation(
        self,
        name_a: str,
        alerts_a: list[dict],
        name_b: str,
        alerts_b: list[dict],
    ) -> Optional[CorrelationResult]:
        """Check for correlation between two alert types."""
        # Get timestamps
        times_a = []
        for a in alerts_a:
            ts = a.get("timestamp") or a.get("starts_at")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if ts:
                times_a.append(ts)
        
        times_b = []
        for b in alerts_b:
            ts = b.get("timestamp") or b.get("starts_at")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if ts:
                times_b.append(ts)
        
        if not times_a or not times_b:
            return None
        
        # Find co-occurrences (within correlation window)
        co_occurrences = 0
        lags = []
        
        for ta in times_a:
            for tb in times_b:
                delta = abs((tb - ta).total_seconds())
                if delta <= self.correlation_window.total_seconds():
                    co_occurrences += 1
                    lags.append((tb - ta).total_seconds())
        
        if co_occurrences < self.min_occurrences:
            return None
        
        # Calculate correlation strength
        expected = len(times_a) * len(times_b) / (30 * 24 * 60)  # Random chance
        strength = min(1.0, co_occurrences / (expected + 1))
        
        # Determine correlation type
        avg_lag = sum(lags) / len(lags) if lags else 0
        if abs(avg_lag) < 60:
            corr_type = "co-occurrence"
        elif avg_lag > 0:
            corr_type = "cascade"  # A -> B
        else:
            corr_type = "cascade"  # B -> A
        
        return CorrelationResult(
            alert_a=name_a,
            alert_b=name_b,
            correlation_type=corr_type,
            correlation_strength=strength,
            typical_lag_seconds=abs(avg_lag),
            occurrences=co_occurrences,
        )
    
    def _get_alert_text(self, alert: dict) -> str:
        """Get searchable text from an alert."""
        parts = [
            alert.get("name", ""),
            alert.get("alert_name", ""),
            alert.get("summary", ""),
            alert.get("description", ""),
        ]
        labels = alert.get("labels", {})
        parts.extend(str(v) for v in labels.values())
        
        return " ".join(parts).lower()
    
    def _build_pattern_matchers(self) -> dict[PatternType, list[tuple[re.Pattern, str]]]:
        """Build regex matchers for known patterns."""
        return {
            PatternType.CAPACITY: [
                (re.compile(r"disk.*(full|space|quota)", re.I), "Disk space exhaustion"),
                (re.compile(r"memory.*(oom|out.of|high|exhaust)", re.I), "Memory exhaustion"),
                (re.compile(r"cpu.*(high|100|saturate)", re.I), "CPU saturation"),
                (re.compile(r"(too many|max|limit).*(connection|request|file)", re.I), "Resource limits hit"),
            ],
            PatternType.DEPLOYMENT: [
                (re.compile(r"(deploy|release|rollout)", re.I), "Deployment-related"),
                (re.compile(r"(version|config).*(change|mismatch)", re.I), "Version/config change"),
                (re.compile(r"crash.loop|image.pull|pod.*(fail|error)", re.I), "Container/pod issues"),
            ],
            PatternType.CONFIGURATION: [
                (re.compile(r"config(uration)?.*(error|invalid|miss)", re.I), "Configuration error"),
                (re.compile(r"(certificate|cert|ssl|tls).*(expir|invalid)", re.I), "Certificate issue"),
                (re.compile(r"(dns|resolve|lookup).*(fail|error)", re.I), "DNS/resolution issue"),
            ],
            PatternType.INFRASTRUCTURE: [
                (re.compile(r"(node|host|instance).*(down|unreachable|fail)", re.I), "Node/host failure"),
                (re.compile(r"(network|connect).*(timeout|refuse|error)", re.I), "Network issue"),
                (re.compile(r"(database|db|mysql|postgres).*(connect|timeout)", re.I), "Database connectivity"),
            ],
        }
    
    def _generate_pattern_id(self, prefix: str, identifier: str) -> str:
        """Generate a unique pattern ID."""
        hash_input = f"{prefix}_{identifier}"
        hash_value = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        return f"{prefix}_{hash_value}"
    
    def _format_interval(self, seconds: float) -> str:
        """Format seconds as human-readable interval."""
        if seconds < 60:
            return f"{int(seconds)} seconds"
        elif seconds < 3600:
            return f"{int(seconds / 60)} minutes"
        elif seconds < 86400:
            return f"{seconds / 3600:.1f} hours"
        else:
            return f"{seconds / 86400:.1f} days"
