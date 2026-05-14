"""
Impact Analyzer for changes.

Assesses the potential impact of changes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from autosre.utils.logging import get_logger

from .models import (
    Change,
    ChangeType,
    ChangeRisk,
    ChangeImpact,
)

logger = get_logger(__name__)


class ImpactAnalyzer:
    """
    Analyzes the potential impact of changes.
    
    Features:
    - Dependency analysis
    - Risk scoring
    - User impact estimation
    - Rollback time estimation
    
    Example:
        analyzer = ImpactAnalyzer(k8s_client)
        
        impact = await analyzer.analyze(change)
        print(f"Risk: {impact.overall_risk_score}")
    """
    
    def __init__(
        self,
        k8s_client: Any | None = None,
        service_graph: dict[str, list[str]] | None = None,
    ):
        self._k8s = k8s_client
        self._service_graph = service_graph or {}
        
        # Risk weights by change type
        self._type_risk_weights = {
            ChangeType.DEPLOYMENT: 0.6,
            ChangeType.CONFIG_MAP: 0.4,
            ChangeType.SECRET: 0.5,
            ChangeType.SCALING: 0.3,
            ChangeType.RESOURCE_LIMIT: 0.4,
            ChangeType.NETWORK_POLICY: 0.7,
            ChangeType.INGRESS: 0.6,
            ChangeType.DATABASE: 0.8,
            ChangeType.INFRASTRUCTURE: 0.9,
            ChangeType.FEATURE_FLAG: 0.3,
        }
        
        # High-risk namespaces
        self._high_risk_namespaces = {"production", "prod", "kube-system"}
        
        # Critical services
        self._critical_services: set[str] = set()
    
    def set_critical_services(self, services: list[str]) -> None:
        """Set list of critical services."""
        self._critical_services = set(services)
    
    def set_service_graph(self, graph: dict[str, list[str]]) -> None:
        """Set service dependency graph."""
        self._service_graph = graph
    
    async def analyze(self, change: Change) -> ChangeImpact:
        """
        Analyze the impact of a change.
        
        Args:
            change: Change to analyze
            
        Returns:
            Impact assessment
        """
        impact = ChangeImpact()
        
        # Get affected services
        affected_services = await self._get_affected_services(change)
        impact.affected_services = affected_services
        
        if change.namespace:
            impact.affected_namespaces = [change.namespace]
        
        # Estimate affected pods
        impact.affected_pods_estimate = await self._estimate_affected_pods(change)
        
        # Check if user-facing
        impact.user_facing = self._is_user_facing(change, affected_services)
        
        # Estimate user impact
        if impact.user_facing:
            impact.estimated_user_impact_percentage = (
                self._estimate_user_impact(change, affected_services)
            )
        
        # Calculate risk scores
        impact.downtime_risk = self._calculate_downtime_risk(change)
        impact.data_loss_risk = self._calculate_data_loss_risk(change)
        impact.performance_impact_risk = self._calculate_performance_risk(change)
        
        # Get dependencies
        impact.upstream_dependencies = self._get_upstream_dependencies(
            change.resource_name
        )
        impact.downstream_dependencies = self._get_downstream_dependencies(
            change.resource_name
        )
        
        # Estimate rollback time
        impact.rollback_time_minutes = self._estimate_rollback_time(change)
        impact.is_reversible = self._is_reversible(change)
        
        logger.info(
            f"Impact analysis for {change.id}: "
            f"risk={impact.overall_risk_score:.2f}, "
            f"affected_services={len(affected_services)}"
        )
        
        return impact
    
    async def analyze_batch(
        self,
        changes: list[Change],
    ) -> ChangeImpact:
        """
        Analyze combined impact of multiple changes.
        
        Args:
            changes: List of changes
            
        Returns:
            Combined impact assessment
        """
        individual_impacts = []
        
        for change in changes:
            impact = await self.analyze(change)
            individual_impacts.append(impact)
        
        # Combine impacts
        combined = ChangeImpact()
        
        all_services = set()
        all_namespaces = set()
        
        for imp in individual_impacts:
            all_services.update(imp.affected_services)
            all_namespaces.update(imp.affected_namespaces)
        
        combined.affected_services = list(all_services)
        combined.affected_namespaces = list(all_namespaces)
        combined.affected_pods_estimate = sum(
            imp.affected_pods_estimate for imp in individual_impacts
        )
        
        # Max risk scores
        combined.downtime_risk = max(
            imp.downtime_risk for imp in individual_impacts
        ) if individual_impacts else 0
        combined.data_loss_risk = max(
            imp.data_loss_risk for imp in individual_impacts
        ) if individual_impacts else 0
        combined.performance_impact_risk = max(
            imp.performance_impact_risk for imp in individual_impacts
        ) if individual_impacts else 0
        
        combined.user_facing = any(imp.user_facing for imp in individual_impacts)
        combined.estimated_user_impact_percentage = max(
            imp.estimated_user_impact_percentage for imp in individual_impacts
        ) if individual_impacts else 0
        
        # Combine dependencies
        all_upstream = set()
        all_downstream = set()
        for imp in individual_impacts:
            all_upstream.update(imp.upstream_dependencies)
            all_downstream.update(imp.downstream_dependencies)
        
        combined.upstream_dependencies = list(all_upstream)
        combined.downstream_dependencies = list(all_downstream)
        
        # Worst case rollback
        combined.rollback_time_minutes = max(
            imp.rollback_time_minutes for imp in individual_impacts
        ) if individual_impacts else 5
        combined.is_reversible = all(imp.is_reversible for imp in individual_impacts)
        
        return combined
    
    def suggest_risk_level(self, impact: ChangeImpact) -> ChangeRisk:
        """
        Suggest a risk level based on impact analysis.
        
        Args:
            impact: Impact assessment
            
        Returns:
            Suggested risk level
        """
        score = impact.overall_risk_score
        
        if score >= 0.8:
            return ChangeRisk.CRITICAL
        elif score >= 0.6:
            return ChangeRisk.HIGH
        elif score >= 0.4:
            return ChangeRisk.MEDIUM
        elif score >= 0.2:
            return ChangeRisk.LOW
        else:
            return ChangeRisk.MINIMAL
    
    async def _get_affected_services(self, change: Change) -> list[str]:
        """Get services affected by change."""
        affected = [change.resource_name]
        
        # Add downstream dependencies
        downstream = self._get_downstream_dependencies(change.resource_name)
        affected.extend(downstream)
        
        return list(set(affected))
    
    async def _estimate_affected_pods(self, change: Change) -> int:
        """Estimate number of pods affected."""
        if not self._k8s or not change.namespace:
            return 1
        
        try:
            if change.change_type == ChangeType.DEPLOYMENT:
                deployment = await self._k8s.get_deployment(
                    change.namespace,
                    change.resource_name,
                )
                return deployment.replicas
            
            elif change.change_type == ChangeType.SCALING:
                # Could affect all pods
                replicas = change.after_state.get("replicas", 1)
                return replicas
            
            else:
                # Generic estimate
                return 1
                
        except Exception as e:
            logger.debug(f"Could not estimate pods: {e}")
            return 1
    
    def _is_user_facing(
        self,
        change: Change,
        affected_services: list[str],
    ) -> bool:
        """Determine if change affects user-facing services."""
        # Check if any affected service is critical
        for service in affected_services:
            if service in self._critical_services:
                return True
        
        # Check change type
        if change.change_type in [ChangeType.INGRESS, ChangeType.SERVICE]:
            return True
        
        # Check namespace
        if change.namespace in ["frontend", "api", "gateway"]:
            return True
        
        return False
    
    def _estimate_user_impact(
        self,
        change: Change,
        affected_services: list[str],
    ) -> float:
        """Estimate percentage of users affected."""
        # Simple heuristic based on service criticality
        critical_count = sum(
            1 for s in affected_services if s in self._critical_services
        )
        
        if critical_count > 0:
            return min(100.0, critical_count * 25.0)
        
        # Change type heuristics
        if change.change_type == ChangeType.INGRESS:
            return 50.0
        elif change.change_type in [ChangeType.DEPLOYMENT, ChangeType.SERVICE]:
            return 25.0
        
        return 10.0
    
    def _calculate_downtime_risk(self, change: Change) -> float:
        """Calculate downtime risk (0-1)."""
        base_risk = self._type_risk_weights.get(change.change_type, 0.5)
        
        # Adjust for namespace
        if change.namespace in self._high_risk_namespaces:
            base_risk *= 1.3
        
        # Adjust for existing risk assessment
        if change.risk == ChangeRisk.CRITICAL:
            base_risk *= 1.5
        elif change.risk == ChangeRisk.HIGH:
            base_risk *= 1.2
        
        return min(1.0, base_risk)
    
    def _calculate_data_loss_risk(self, change: Change) -> float:
        """Calculate data loss risk (0-1)."""
        if change.change_type == ChangeType.DATABASE:
            return 0.5
        elif change.change_type == ChangeType.SECRET:
            return 0.3
        elif change.change_type in [ChangeType.CONFIG_MAP, ChangeType.PDB]:
            return 0.1
        
        return 0.0
    
    def _calculate_performance_risk(self, change: Change) -> float:
        """Calculate performance impact risk (0-1)."""
        if change.change_type == ChangeType.RESOURCE_LIMIT:
            return 0.6
        elif change.change_type == ChangeType.SCALING:
            return 0.4
        elif change.change_type == ChangeType.NETWORK_POLICY:
            return 0.5
        elif change.change_type == ChangeType.HPA:
            return 0.3
        
        return 0.2
    
    def _get_upstream_dependencies(self, service: str) -> list[str]:
        """Get services that this service depends on."""
        # Reverse lookup in service graph
        upstream = []
        for svc, deps in self._service_graph.items():
            if service in deps:
                upstream.append(svc)
        return upstream
    
    def _get_downstream_dependencies(self, service: str) -> list[str]:
        """Get services that depend on this service."""
        return self._service_graph.get(service, [])
    
    def _estimate_rollback_time(self, change: Change) -> int:
        """Estimate rollback time in minutes."""
        base_time = {
            ChangeType.DEPLOYMENT: 5,
            ChangeType.CONFIG_MAP: 2,
            ChangeType.SECRET: 2,
            ChangeType.SCALING: 3,
            ChangeType.DATABASE: 30,
            ChangeType.INFRASTRUCTURE: 60,
            ChangeType.FEATURE_FLAG: 1,
        }.get(change.change_type, 10)
        
        return base_time
    
    def _is_reversible(self, change: Change) -> bool:
        """Determine if change is easily reversible."""
        # Most Kubernetes changes are reversible
        if change.change_type == ChangeType.DATABASE:
            # Database changes may not be easily reversible
            return False
        
        if change.change_type == ChangeType.INFRASTRUCTURE:
            # Infrastructure changes may be complex to rollback
            return False
        
        # Check if before state is available
        if not change.before_state:
            return False
        
        return True
