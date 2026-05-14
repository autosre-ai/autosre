"""
Resilience Scorer for chaos engineering.

Calculates resilience scores based on chaos experiment results.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from autosre.utils.logging import get_logger

from .models import (
    Experiment,
    ExperimentResult,
    ExperimentStatus,
    ResilienceScore,
    FaultType,
)

logger = get_logger(__name__)


class ResilienceScorer:
    """
    Calculates resilience scores for services.
    
    Features:
    - Component-based scoring
    - Trend analysis
    - Recommendations
    - Historical tracking
    
    Example:
        scorer = ResilienceScorer()
        
        # Calculate score from experiments
        score = scorer.calculate_score(
            service="api-server",
            namespace="production",
            experiments=recent_experiments,
        )
        
        print(f"Resilience Grade: {score.get_grade()}")
    """
    
    def __init__(self):
        # Score history
        self._history: dict[str, list[ResilienceScore]] = {}
        
        # Weight configuration
        self._weights = {
            "availability": 0.3,
            "recovery": 0.3,
            "degradation": 0.2,
            "blast_radius": 0.2,
        }
        
        # Fault type impact weights
        self._fault_weights = {
            FaultType.POD_KILL: 1.2,
            FaultType.NODE_FAILURE: 1.5,
            FaultType.NETWORK_PARTITION: 1.3,
            FaultType.CPU_STRESS: 0.8,
            FaultType.MEMORY_STRESS: 0.9,
            FaultType.NETWORK_LATENCY: 0.7,
        }
    
    def calculate_score(
        self,
        service: str,
        namespace: str,
        experiments: list[Experiment],
        lookback_days: int = 30,
    ) -> ResilienceScore:
        """
        Calculate resilience score from experiments.
        
        Args:
            service: Service name
            namespace: Kubernetes namespace
            experiments: List of experiments
            lookback_days: Days to consider
            
        Returns:
            Resilience score
        """
        # Filter recent experiments
        cutoff = datetime.utcnow() - timedelta(days=lookback_days)
        recent = [
            e for e in experiments
            if e.completed_at and e.completed_at > cutoff
        ]
        
        if not recent:
            return ResilienceScore(
                service=service,
                namespace=namespace,
                overall_score=50.0,  # Neutral if no data
                recommendations=["Run chaos experiments to establish baseline"],
            )
        
        # Calculate component scores
        availability_score = self._calculate_availability(recent)
        recovery_score = self._calculate_recovery(recent)
        degradation_score = self._calculate_degradation(recent)
        blast_radius_score = self._calculate_blast_radius(recent)
        
        # Calculate overall
        overall = (
            availability_score * self._weights["availability"] +
            recovery_score * self._weights["recovery"] +
            degradation_score * self._weights["degradation"] +
            blast_radius_score * self._weights["blast_radius"]
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            availability_score,
            recovery_score,
            degradation_score,
            blast_radius_score,
            recent,
        )
        
        # Determine trend
        trend = self._calculate_trend(service, namespace, overall)
        
        score = ResilienceScore(
            service=service,
            namespace=namespace,
            overall_score=overall,
            availability_score=availability_score,
            recovery_score=recovery_score,
            degradation_score=degradation_score,
            blast_radius_score=blast_radius_score,
            experiments_run=len(recent),
            experiments_passed=sum(1 for e in recent if e.result and e.result.success),
            last_experiment_at=max(e.completed_at for e in recent if e.completed_at),
            recommendations=recommendations,
            score_trend=trend,
        )
        
        # Store in history
        self._store_score(service, namespace, score)
        
        return score
    
    def _calculate_availability(
        self,
        experiments: list[Experiment],
    ) -> float:
        """Calculate availability score."""
        if not experiments:
            return 50.0
        
        # Based on steady state maintenance during experiments
        total_weight = 0
        weighted_score = 0
        
        for exp in experiments:
            if not exp.result:
                continue
            
            weight = self._get_experiment_weight(exp)
            total_weight += weight
            
            # Score based on steady state
            if exp.result.steady_state_met_during:
                weighted_score += weight * 100
            elif exp.result.steady_state_met_after:
                weighted_score += weight * 50  # Recovered
            else:
                weighted_score += weight * 0  # Failed
        
        return weighted_score / total_weight if total_weight > 0 else 50.0
    
    def _calculate_recovery(
        self,
        experiments: list[Experiment],
    ) -> float:
        """Calculate recovery score."""
        if not experiments:
            return 50.0
        
        total_weight = 0
        weighted_score = 0
        
        for exp in experiments:
            if not exp.result:
                continue
            
            weight = self._get_experiment_weight(exp)
            total_weight += weight
            
            # Score based on recovery
            if exp.result.steady_state_met_after:
                # Calculate recovery time factor
                recovery_time = exp.cooldown_seconds
                if recovery_time <= 30:
                    weighted_score += weight * 100
                elif recovery_time <= 60:
                    weighted_score += weight * 80
                elif recovery_time <= 120:
                    weighted_score += weight * 60
                else:
                    weighted_score += weight * 40
            else:
                weighted_score += weight * 0
        
        return weighted_score / total_weight if total_weight > 0 else 50.0
    
    def _calculate_degradation(
        self,
        experiments: list[Experiment],
    ) -> float:
        """Calculate graceful degradation score."""
        if not experiments:
            return 50.0
        
        total_weight = 0
        weighted_score = 0
        
        for exp in experiments:
            if not exp.result:
                continue
            
            weight = self._get_experiment_weight(exp)
            total_weight += weight
            
            # Score based on how well system degraded
            # Check if there were partial failures vs complete failures
            if exp.result.success:
                weighted_score += weight * 100
            elif exp.result.steady_state_met_before and not exp.result.steady_state_met_during:
                # Degraded but in a controlled way
                if exp.result.steady_state_met_after:
                    weighted_score += weight * 70
                else:
                    weighted_score += weight * 30
            else:
                weighted_score += weight * 0
        
        return weighted_score / total_weight if total_weight > 0 else 50.0
    
    def _calculate_blast_radius(
        self,
        experiments: list[Experiment],
    ) -> float:
        """Calculate blast radius containment score."""
        if not experiments:
            return 50.0
        
        total_weight = 0
        weighted_score = 0
        
        for exp in experiments:
            if not exp.result:
                continue
            
            weight = self._get_experiment_weight(exp)
            total_weight += weight
            
            # Check if failure was contained
            impact = exp.result.impact_metrics
            
            # Default to good if no impact data
            if not impact:
                if exp.result.success:
                    weighted_score += weight * 100
                else:
                    weighted_score += weight * 50
                continue
            
            # Score based on impact scope
            affected_services = impact.get("affected_services", 0)
            cascade_detected = impact.get("cascade_detected", False)
            
            if not cascade_detected and affected_services <= 1:
                weighted_score += weight * 100
            elif not cascade_detected:
                weighted_score += weight * 70
            else:
                weighted_score += weight * 30
        
        return weighted_score / total_weight if total_weight > 0 else 50.0
    
    def _get_experiment_weight(self, experiment: Experiment) -> float:
        """Get weight for an experiment based on fault types."""
        if not experiment.faults:
            return 1.0
        
        # Average weight of fault types
        weights = [
            self._fault_weights.get(f.type, 1.0)
            for f in experiment.faults
        ]
        
        return sum(weights) / len(weights)
    
    def _generate_recommendations(
        self,
        availability: float,
        recovery: float,
        degradation: float,
        blast_radius: float,
        experiments: list[Experiment],
    ) -> list[str]:
        """Generate recommendations based on scores."""
        recommendations = []
        
        if availability < 70:
            recommendations.append(
                "🔴 Availability needs improvement. Consider:"
                "\n  - Adding health checks"
                "\n  - Implementing circuit breakers"
                "\n  - Increasing pod disruption budgets"
            )
        
        if recovery < 70:
            recommendations.append(
                "🟡 Recovery time is slow. Consider:"
                "\n  - Optimizing startup time"
                "\n  - Adding readiness probes"
                "\n  - Pre-warming caches"
            )
        
        if degradation < 70:
            recommendations.append(
                "🟡 Graceful degradation needs work. Consider:"
                "\n  - Implementing fallback mechanisms"
                "\n  - Adding feature flags"
                "\n  - Configuring load shedding"
            )
        
        if blast_radius < 70:
            recommendations.append(
                "🔴 Blast radius containment is poor. Consider:"
                "\n  - Adding bulkheads"
                "\n  - Implementing retry budgets"
                "\n  - Reviewing service dependencies"
            )
        
        # Check fault type coverage
        tested_faults = set()
        for exp in experiments:
            for fault in exp.faults:
                tested_faults.add(fault.type)
        
        important_faults = {
            FaultType.POD_KILL,
            FaultType.NETWORK_LATENCY,
            FaultType.CPU_STRESS,
        }
        
        untested = important_faults - tested_faults
        if untested:
            recommendations.append(
                f"📊 Consider testing these fault types: "
                f"{', '.join(f.value for f in untested)}"
            )
        
        if not recommendations:
            recommendations.append("✅ Resilience is good! Continue regular testing.")
        
        return recommendations
    
    def _calculate_trend(
        self,
        service: str,
        namespace: str,
        current_score: float,
    ) -> str:
        """Calculate score trend."""
        key = f"{namespace}/{service}"
        history = self._history.get(key, [])
        
        if len(history) < 2:
            return "stable"
        
        # Compare to average of recent scores
        recent_avg = sum(s.overall_score for s in history[-5:]) / min(5, len(history))
        
        if current_score > recent_avg + 5:
            return "improving"
        elif current_score < recent_avg - 5:
            return "declining"
        else:
            return "stable"
    
    def _store_score(
        self,
        service: str,
        namespace: str,
        score: ResilienceScore,
    ) -> None:
        """Store score in history."""
        key = f"{namespace}/{service}"
        
        if key not in self._history:
            self._history[key] = []
        
        self._history[key].append(score)
        
        # Keep last 100 scores
        if len(self._history[key]) > 100:
            self._history[key] = self._history[key][-100:]
    
    def get_score_history(
        self,
        service: str,
        namespace: str,
        limit: int = 30,
    ) -> list[ResilienceScore]:
        """Get score history for a service."""
        key = f"{namespace}/{service}"
        return self._history.get(key, [])[-limit:]
    
    def compare_services(
        self,
        services: list[tuple[str, str]],
        experiments_map: dict[str, list[Experiment]],
    ) -> list[ResilienceScore]:
        """
        Compare resilience scores across services.
        
        Args:
            services: List of (service, namespace) tuples
            experiments_map: Map of service key to experiments
            
        Returns:
            List of scores sorted by overall score
        """
        scores = []
        
        for service, namespace in services:
            key = f"{namespace}/{service}"
            experiments = experiments_map.get(key, [])
            
            score = self.calculate_score(service, namespace, experiments)
            scores.append(score)
        
        # Sort by overall score (descending)
        scores.sort(key=lambda s: s.overall_score, reverse=True)
        
        return scores
    
    def generate_report(
        self,
        score: ResilienceScore,
    ) -> str:
        """Generate a resilience report."""
        grade = score.get_grade()
        
        lines = [
            f"# Resilience Report: {score.service}",
            "",
            f"**Namespace:** {score.namespace}",
            f"**Overall Grade:** {grade} ({score.overall_score:.0f}/100)",
            f"**Trend:** {score.score_trend.upper()}",
            f"**Last Tested:** {score.last_experiment_at or 'Never'}",
            "",
            "## Component Scores",
            "",
            f"| Component | Score | Grade |",
            f"|-----------|-------|-------|",
            f"| Availability | {score.availability_score:.0f} | {self._grade(score.availability_score)} |",
            f"| Recovery | {score.recovery_score:.0f} | {self._grade(score.recovery_score)} |",
            f"| Degradation | {score.degradation_score:.0f} | {self._grade(score.degradation_score)} |",
            f"| Blast Radius | {score.blast_radius_score:.0f} | {self._grade(score.blast_radius_score)} |",
            "",
            "## Experiments",
            "",
            f"- Total Run: {score.experiments_run}",
            f"- Passed: {score.experiments_passed}",
            f"- Pass Rate: {score.pass_rate:.0%}",
            "",
            "## Recommendations",
            "",
        ]
        
        for rec in score.recommendations:
            lines.append(rec)
            lines.append("")
        
        return "\n".join(lines)
    
    def _grade(self, score: float) -> str:
        """Convert score to letter grade."""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"
