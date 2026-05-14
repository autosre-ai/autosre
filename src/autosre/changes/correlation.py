"""
Correlation Engine for linking incidents to changes.

Analyzes incidents and finds related changes that may have caused them.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from autosre.utils.logging import get_logger

from .models import (
    Change,
    ChangeType,
    ChangeStatus,
    IncidentCorrelation,
)
from .tracker import ChangeTracker

logger = get_logger(__name__)


class CorrelationEngine:
    """
    Correlates incidents with recent changes.
    
    Features:
    - Time-based correlation
    - Namespace/service matching
    - Risk-weighted scoring
    - Multi-factor analysis
    
    Example:
        engine = CorrelationEngine(tracker)
        
        correlation = await engine.correlate(
            incident_id="INC-12345",
            incident_started_at=datetime.utcnow(),
            affected_services=["api-server"],
            namespace="production",
        )
        
        suspects = correlation.get_top_suspects(5)
    """
    
    def __init__(
        self,
        change_tracker: ChangeTracker,
    ):
        self._tracker = change_tracker
        
        # Correlation window (default 60 minutes before incident)
        self._default_window_minutes = 60
        
        # Score weights
        self._weights = {
            "time_proximity": 0.25,
            "namespace_match": 0.20,
            "service_match": 0.25,
            "risk_level": 0.15,
            "change_type": 0.15,
        }
        
        # Change type relevance
        self._type_relevance = {
            ChangeType.DEPLOYMENT: 1.0,
            ChangeType.CONFIG_MAP: 0.9,
            ChangeType.SECRET: 0.8,
            ChangeType.SCALING: 0.7,
            ChangeType.RESOURCE_LIMIT: 0.8,
            ChangeType.NETWORK_POLICY: 0.9,
            ChangeType.INGRESS: 0.8,
            ChangeType.DATABASE: 0.9,
            ChangeType.INFRASTRUCTURE: 1.0,
            ChangeType.FEATURE_FLAG: 0.7,
        }
    
    async def correlate(
        self,
        incident_id: str,
        incident_started_at: datetime,
        affected_services: list[str] | None = None,
        namespace: str | None = None,
        cluster: str | None = None,
        error_type: str | None = None,
        window_minutes: int | None = None,
        incident_title: str | None = None,
    ) -> IncidentCorrelation:
        """
        Find changes correlated with an incident.
        
        Args:
            incident_id: Incident identifier
            incident_started_at: When incident started
            affected_services: Services affected by incident
            namespace: Namespace where incident occurred
            cluster: Cluster where incident occurred
            error_type: Type of error (for additional matching)
            window_minutes: Correlation window
            incident_title: Incident title
            
        Returns:
            Correlation analysis result
        """
        window = window_minutes or self._default_window_minutes
        
        correlation = IncidentCorrelation(
            incident_id=incident_id,
            incident_title=incident_title,
            incident_started_at=incident_started_at,
            correlation_window_minutes=window,
        )
        
        # Get changes in correlation window
        start_time = incident_started_at - timedelta(minutes=window)
        changes = await self._tracker.get_changes_in_window(
            start_time=start_time,
            end_time=incident_started_at,
            namespace=namespace,
        )
        
        if not changes:
            correlation.analysis_summary = "No changes found in correlation window"
            return correlation
        
        # Score each change
        scores: dict[str, float] = {}
        
        for change in changes:
            score = self._calculate_correlation_score(
                change=change,
                incident_started_at=incident_started_at,
                affected_services=affected_services or [],
                namespace=namespace,
                error_type=error_type,
            )
            
            scores[str(change.id)] = score
            correlation.correlated_changes.append(change.id)
        
        correlation.correlation_scores = scores
        
        # Find primary suspect
        if scores:
            top_id = max(scores.keys(), key=lambda k: scores[k])
            correlation.primary_suspect = UUID(top_id)
            correlation.primary_suspect_confidence = scores[top_id]
        
        # Generate analysis summary
        correlation.analysis_summary = self._generate_summary(
            changes, scores, namespace
        )
        
        # Link changes to incident
        for change_id in correlation.correlated_changes:
            await self._tracker.link_incident(change_id, incident_id)
        
        logger.info(
            f"Correlated incident {incident_id} with {len(changes)} changes. "
            f"Primary suspect: {correlation.primary_suspect} "
            f"(confidence={correlation.primary_suspect_confidence:.2f})"
        )
        
        return correlation
    
    def _calculate_correlation_score(
        self,
        change: Change,
        incident_started_at: datetime,
        affected_services: list[str],
        namespace: str | None,
        error_type: str | None,
    ) -> float:
        """Calculate correlation score for a change."""
        scores = {}
        
        # Time proximity score (closer = higher)
        change_time = change.completed_at or change.started_at or change.created_at
        time_diff_minutes = (incident_started_at - change_time).total_seconds() / 60
        
        # Exponential decay: changes closer to incident score higher
        time_score = max(0, 1 - (time_diff_minutes / 60) ** 0.5)
        scores["time_proximity"] = time_score
        
        # Namespace match
        if namespace and change.namespace == namespace:
            scores["namespace_match"] = 1.0
        elif namespace and change.namespace:
            scores["namespace_match"] = 0.3  # Different namespace
        else:
            scores["namespace_match"] = 0.5  # Unknown
        
        # Service match
        service_score = 0.5  # Default
        if affected_services:
            if change.resource_name in affected_services:
                service_score = 1.0
            elif any(
                svc in change.resource_name or change.resource_name in svc
                for svc in affected_services
            ):
                service_score = 0.8
            elif change.impact and any(
                svc in change.impact.affected_services
                for svc in affected_services
            ):
                service_score = 0.7
        scores["service_match"] = service_score
        
        # Risk level
        risk_score = {
            "critical": 1.0,
            "high": 0.8,
            "medium": 0.5,
            "low": 0.3,
            "minimal": 0.1,
        }.get(change.risk.value, 0.5)
        scores["risk_level"] = risk_score
        
        # Change type relevance
        type_score = self._type_relevance.get(change.change_type, 0.5)
        scores["change_type"] = type_score
        
        # Additional factors
        
        # Failed changes are more suspicious
        if change.status == ChangeStatus.FAILED:
            scores["risk_level"] *= 1.5
        
        # Rolled back changes are very suspicious
        if change.status == ChangeStatus.ROLLED_BACK:
            scores["risk_level"] = min(1.0, scores["risk_level"] * 2)
        
        # Calculate weighted score
        total_score = sum(
            scores[key] * self._weights[key]
            for key in self._weights
        )
        
        return min(1.0, total_score)
    
    def _generate_summary(
        self,
        changes: list[Change],
        scores: dict[str, float],
        namespace: str | None,
    ) -> str:
        """Generate analysis summary."""
        if not changes:
            return "No changes found in correlation window."
        
        # Count by type
        type_counts = {}
        for change in changes:
            t = change.change_type.value
            type_counts[t] = type_counts.get(t, 0) + 1
        
        # Get top changes
        sorted_changes = sorted(
            changes,
            key=lambda c: scores.get(str(c.id), 0),
            reverse=True,
        )
        
        top_change = sorted_changes[0]
        top_score = scores.get(str(top_change.id), 0)
        
        summary_lines = [
            f"Found {len(changes)} changes in correlation window.",
        ]
        
        if namespace:
            summary_lines.append(f"Namespace: {namespace}")
        
        summary_lines.append(
            f"Change types: {', '.join(f'{t}({c})' for t, c in type_counts.items())}"
        )
        
        summary_lines.append(
            f"\nMost likely cause: {top_change.title or top_change.resource_name} "
            f"(score={top_score:.2f})"
        )
        
        if top_score >= 0.8:
            summary_lines.append("⚠️ HIGH confidence correlation")
        elif top_score >= 0.6:
            summary_lines.append("⚡ Moderate confidence correlation")
        else:
            summary_lines.append("❓ Low confidence - manual review recommended")
        
        return "\n".join(summary_lines)
    
    async def find_similar_incidents(
        self,
        change_id: UUID,
        lookback_days: int = 30,
    ) -> list[str]:
        """
        Find incidents that may be similar based on same change pattern.
        
        Args:
            change_id: Change ID
            lookback_days: Days to look back
            
        Returns:
            List of incident IDs
        """
        change = await self._tracker.get_change(change_id)
        if not change:
            return []
        
        # Find similar changes
        similar_changes = await self._tracker.get_changes_for_resource(
            resource_type=change.resource_type,
            resource_name=change.resource_name,
            namespace=change.namespace,
            limit=100,
        )
        
        # Collect linked incidents
        incident_ids = set()
        for c in similar_changes:
            incident_ids.update(c.incident_ids)
        
        return list(incident_ids)
    
    async def get_change_incident_rate(
        self,
        change_type: ChangeType | None = None,
        namespace: str | None = None,
        days: int = 30,
    ) -> float:
        """
        Calculate rate of changes that led to incidents.
        
        Args:
            change_type: Filter by type
            namespace: Filter by namespace
            days: Lookback period
            
        Returns:
            Incident rate (0-1)
        """
        changes = await self._tracker.get_recent_changes(
            namespace=namespace,
            change_type=change_type,
            minutes=days * 24 * 60,
        )
        
        if not changes:
            return 0.0
        
        with_incidents = sum(1 for c in changes if c.incident_ids)
        
        return with_incidents / len(changes)
    
    def set_weights(self, weights: dict[str, float]) -> None:
        """
        Update correlation weights.
        
        Args:
            weights: New weight configuration
        """
        total = sum(weights.values())
        
        # Normalize weights
        self._weights = {
            k: v / total for k, v in weights.items()
        }
        
        logger.info(f"Updated correlation weights: {self._weights}")
