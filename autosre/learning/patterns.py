"""Pattern recognition from past incidents."""

from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from .store import IncidentStore


@dataclass
class PatternMatch:
    """Result of pattern matching."""
    likely_root_cause: str
    pattern_confidence: float
    similar_incidents: int
    common_actions: list[tuple[str, int]] = field(default_factory=list)
    avg_resolution_time: float = 0.0
    success_rate: float = 0.0


@dataclass
class RunbookSuggestion:
    """Suggested runbook based on past incidents."""
    recommended_actions: list[str]
    success_count: int
    total_similar: int
    avg_resolution_time: float = 0.0


class PatternRecognizer:
    """Recognize patterns in incidents."""

    # Signal keywords for extracting signals from observations
    SIGNAL_PATTERNS = {
        "memory": ["oom", "memory", "oomkilled", "memory_pressure", "out of memory"],
        "crashloop": ["crash", "backoff", "crashloopbackoff", "restart", "terminated"],
        "cpu": ["cpu", "throttl", "processor", "compute"],
        "errors": ["error", "5xx", "500", "502", "503", "504", "exception", "failed"],
        "latency": ["latency", "slow", "timeout", "delay", "p99", "p95"],
        "network": ["network", "connection", "dns", "socket", "unreachable"],
        "disk": ["disk", "storage", "volume", "pvc", "filesystem", "full"],
        "scaling": ["scale", "replica", "hpa", "autoscal", "capacity"],
        "deployment": ["deploy", "rollout", "version", "release", "image"],
        "config": ["config", "configmap", "secret", "env", "environment"],
    }

    def __init__(self, store: IncidentStore):
        self.store = store

    def find_matching_pattern(
        self,
        observations: list[dict],
        namespace: Optional[str] = None,
    ) -> Optional[PatternMatch]:
        """Find if current observations match a known pattern."""
        # Extract key signals from observations
        signals = self._extract_signals(observations)

        if not signals:
            return None

        # Find similar past incidents
        search_query = " ".join(signals)
        similar = self.store.find_similar(search_query, namespace, limit=20)

        if not similar:
            return None

        # Analyze patterns
        root_causes = Counter(inc.root_cause for inc in similar if inc.root_cause)

        if not root_causes:
            return None

        # Count actions from executed actions
        actions: Counter[str] = Counter()
        for inc in similar:
            for action in (inc.actions_executed or []):
                if isinstance(action, str):
                    actions[action] += 1
                elif isinstance(action, dict) and "command" in action:
                    actions[action["command"]] += 1

        # Calculate confidence based on pattern consistency
        most_common_cause, cause_count = root_causes.most_common(1)[0]
        pattern_confidence = cause_count / len(similar)

        # Calculate success rate for resolved incidents
        resolved = [inc for inc in similar if inc.outcome == "resolved"]
        success_rate = len(resolved) / len(similar) if similar else 0

        # Average resolution time
        resolution_times = [
            inc.resolution_time_minutes
            for inc in similar
            if inc.resolution_time_minutes
        ]
        avg_resolution = sum(resolution_times) / len(resolution_times) if resolution_times else 0

        return PatternMatch(
            likely_root_cause=most_common_cause,
            pattern_confidence=pattern_confidence,
            similar_incidents=len(similar),
            common_actions=actions.most_common(5),
            avg_resolution_time=avg_resolution,
            success_rate=success_rate,
        )

    def suggest_runbook(
        self,
        root_cause: str,
        namespace: Optional[str] = None,
    ) -> Optional[RunbookSuggestion]:
        """Suggest runbook based on past success."""
        similar = self.store.find_by_root_cause(root_cause, limit=20)

        if namespace:
            similar = [inc for inc in similar if inc.namespace == namespace]

        # Filter to resolved incidents
        resolved = [inc for inc in similar if inc.outcome == "resolved"]

        if not resolved:
            return None

        # Find most successful action sequences
        action_sequences = Counter()
        for inc in resolved:
            actions = inc.actions_executed or []
            if actions:
                # Convert to tuple for hashing
                sequence = tuple(
                    a if isinstance(a, str) else a.get("command", str(a))
                    for a in actions
                )
                action_sequences[sequence] += 1

        if not action_sequences:
            return None

        best_sequence, count = action_sequences.most_common(1)[0]

        # Average resolution time for resolved incidents
        resolution_times = [
            inc.resolution_time_minutes
            for inc in resolved
            if inc.resolution_time_minutes
        ]
        avg_resolution = sum(resolution_times) / len(resolution_times) if resolution_times else 0

        return RunbookSuggestion(
            recommended_actions=list(best_sequence),
            success_count=count,
            total_similar=len(resolved),
            avg_resolution_time=avg_resolution,
        )

    def get_common_root_causes(self, namespace: Optional[str] = None, limit: int = 10) -> list[dict]:
        """Get most common root causes."""
        stats = self.store.get_statistics(namespace)
        return stats.get("top_root_causes", [])[:limit]

    def predict_resolution_time(
        self,
        root_cause: str,
        namespace: Optional[str] = None,
    ) -> Optional[float]:
        """Predict resolution time based on similar incidents."""
        similar = self.store.find_by_root_cause(root_cause, limit=20)

        if namespace:
            similar = [inc for inc in similar if inc.namespace == namespace]

        # Get resolution times from resolved incidents
        resolution_times = [
            inc.resolution_time_minutes
            for inc in similar
            if inc.outcome == "resolved" and inc.resolution_time_minutes
        ]

        if not resolution_times:
            return None

        return sum(resolution_times) / len(resolution_times)

    def _extract_signals(self, observations: list[dict]) -> list[str]:
        """Extract key signals from observations."""
        signals = set()

        for obs in observations:
            summary = obs.get("summary", "").lower()

            # Check against signal patterns
            for signal_name, keywords in self.SIGNAL_PATTERNS.items():
                if any(kw in summary for kw in keywords):
                    signals.add(signal_name)

        return list(signals)

    def analyze_trends(self, namespace: Optional[str] = None, days: int = 30) -> dict:
        """Analyze incident trends over time."""
        from datetime import datetime, timedelta, timezone

        incidents = self.store.find_recent(limit=1000)

        if namespace:
            incidents = [inc for inc in incidents if inc.namespace == namespace]

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        recent = [inc for inc in incidents if inc.created_at and inc.created_at > cutoff]

        if not recent:
            return {
                "total_incidents": 0,
                "incidents_per_day": 0,
                "most_common_root_cause": None,
                "avg_resolution_time": 0,
                "resolution_rate": 0,
            }

        # Calculate trends
        root_causes = Counter(inc.root_cause for inc in recent if inc.root_cause)
        resolved = [inc for inc in recent if inc.outcome == "resolved"]
        resolution_times = [
            inc.resolution_time_minutes
            for inc in resolved
            if inc.resolution_time_minutes
        ]

        most_common = root_causes.most_common(1)

        return {
            "total_incidents": len(recent),
            "incidents_per_day": len(recent) / days,
            "most_common_root_cause": most_common[0][0] if most_common else None,
            "avg_resolution_time": sum(resolution_times) / len(resolution_times) if resolution_times else 0,
            "resolution_rate": len(resolved) / len(recent) if recent else 0,
            "root_cause_distribution": dict(root_causes.most_common(10)),
        }
