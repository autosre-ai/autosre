"""
Tests for Investigation Quality features.

Based on Google SRE book learnings:
- Triage-first enforcement
- Golden Signals skill
- Changes subagent
- Latency percentiles (no avg!)
- Investigation phase flow
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================================
# Triage Node Tests
# ============================================================================

class TestTriageNode:
    """Tests for the mandatory triage phase."""
    
    @pytest.fixture
    def mock_llm(self):
        """Mock LLM client."""
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value=MagicMock(
            content='''```json
            {
                "is_service_impaired": true,
                "impact": {
                    "severity": "high",
                    "users_affected": "50% of users in us-east",
                    "sla_violation": true,
                    "data_loss_risk": false,
                    "description": "API returning 5xx errors"
                },
                "mitigation_options": [
                    {
                        "action": "rollback_deployment",
                        "description": "Revert to previous version",
                        "estimated_impact": "Should restore service in 2-3 min",
                        "risk_level": "low",
                        "requires_approval": false
                    }
                ],
                "recommended_focus_areas": ["recent_changes", "error_logs"],
                "reasoning": "Recent deployment correlates with issue start"
            }
            ```'''
        ))
        return llm
    
    @pytest.mark.asyncio
    async def test_triage_creates_result(self, mock_llm):
        """Triage node should create a complete TriageResult."""
        from src.autosre.agents.nodes.triage import TriageNode, TriageStatus
        
        node = TriageNode(llm_client=mock_llm)
        
        alert = {
            "name": "HighErrorRate",
            "service": "api-gateway",
            "severity": "critical",
        }
        
        result = await node.run(alert)
        
        assert result.is_service_impaired is True
        assert result.impact.severity.value == "high"
        assert result.mitigation_considered is True
        assert len(result.mitigation_options) > 0
        assert result.triage_completed_at is not None
    
    @pytest.mark.asyncio
    async def test_triage_blocks_investigation_without_completion(self):
        """Investigation should be blocked if triage not complete."""
        from src.autosre.agents.nodes.triage import block_investigation_without_triage
        
        # No triage result
        with pytest.raises(RuntimeError, match="Triage phase must run first"):
            block_investigation_without_triage(None)
    
    @pytest.mark.asyncio
    async def test_triage_blocks_without_mitigation_consideration(self):
        """Investigation blocked if mitigation not considered."""
        from src.autosre.agents.nodes.triage import (
            TriageResult, TriageStatus, ImpactAssessment, ImpactSeverity,
            block_investigation_without_triage,
        )
        
        # Triage result without mitigation consideration
        result = TriageResult(
            status=TriageStatus.IN_PROGRESS,
            is_service_impaired=True,
            impact=ImpactAssessment(severity=ImpactSeverity.HIGH),
            mitigation_considered=False,
        )
        
        with pytest.raises(RuntimeError, match="Triage not complete"):
            block_investigation_without_triage(result)
    
    @pytest.mark.asyncio
    async def test_triage_tracks_time_to_mitigation(self, mock_llm):
        """Triage should track time-to-mitigation metric."""
        from src.autosre.agents.nodes.triage import TriageNode, MitigationOption
        
        node = TriageNode(llm_client=mock_llm)
        
        alert = {"name": "Test", "service": "test-svc"}
        result = await node.run(alert)
        
        # Mark mitigation applied
        option = MitigationOption(
            action="rollback_deployment",
            description="Rollback",
            estimated_impact="Fix in 2 min",
        )
        result = node.mark_mitigation_applied(result, option)
        
        assert result.mitigation_completed_at is not None
        assert result.time_to_mitigation_seconds is not None
        assert result.time_to_mitigation_seconds >= 0


# ============================================================================
# Golden Signals Tests
# ============================================================================

class TestGoldenSignals:
    """Tests for the Golden Signals skill."""
    
    @pytest.fixture
    def mock_prometheus(self):
        """Mock Prometheus responses."""
        async def mock_query(query):
            # Return realistic data based on query
            if "histogram_quantile(0.99" in query:
                return {
                    "status": "success",
                    "data": {
                        "resultType": "vector",
                        "result": [{"metric": {}, "value": [0, "0.150"]}]
                    }
                }
            elif "histogram_quantile(0.50" in query:
                return {
                    "status": "success",
                    "data": {
                        "resultType": "vector",
                        "result": [{"metric": {}, "value": [0, "0.050"]}]
                    }
                }
            elif "rate" in query.lower() and "error" not in query.lower():
                return {
                    "status": "success",
                    "data": {
                        "resultType": "vector",
                        "result": [{"metric": {}, "value": [0, "100"]}]  # 100 req/s
                    }
                }
            elif "5.." in query:  # Error rate
                return {
                    "status": "success",
                    "data": {
                        "resultType": "vector",
                        "result": [{"metric": {}, "value": [0, "0.02"]}]  # 2% errors
                    }
                }
            elif "cpu" in query.lower() or "memory" in query.lower():
                return {
                    "status": "success",
                    "data": {
                        "resultType": "vector",
                        "result": [{"metric": {}, "value": [0, "0.65"]}]  # 65% saturation
                    }
                }
            return {"status": "success", "data": {"result": []}}
        
        return mock_query
    
    @pytest.mark.asyncio
    async def test_golden_signals_checks_all_four(self, mock_prometheus):
        """Golden signals should check latency, traffic, errors, saturation."""
        from src.autosre.skills.golden_signals import GoldenSignalsSkill, PrometheusBackend
        
        backend = MagicMock(spec=PrometheusBackend)
        backend.query_instant = AsyncMock(side_effect=mock_prometheus)
        
        skill = GoldenSignalsSkill(backend=backend)
        result = await skill.check_all_signals("my-service")
        
        # All four signals should be present
        assert result.latency is not None
        assert result.traffic is not None
        assert result.errors is not None
        assert result.saturation is not None
    
    @pytest.mark.asyncio
    async def test_golden_signals_uses_percentiles(self, mock_prometheus):
        """Latency should use percentiles, not averages."""
        from src.autosre.skills.golden_signals import GoldenSignalsSkill, PrometheusBackend
        
        backend = MagicMock(spec=PrometheusBackend)
        backend.query_instant = AsyncMock(side_effect=mock_prometheus)
        
        skill = GoldenSignalsSkill(backend=backend)
        result = await skill.check_all_signals("my-service")
        
        # Should have percentile details
        assert result.latency.details is not None
        # Should include p99
        assert "p99" in result.latency.details or result.latency.value is not None
    
    @pytest.mark.asyncio
    async def test_golden_signals_flags_missing_metrics(self):
        """Should flag services missing golden signal metrics."""
        from src.autosre.skills.golden_signals import GoldenSignalsSkill, PrometheusBackend, SignalStatus
        
        # Backend that returns no data
        backend = MagicMock(spec=PrometheusBackend)
        backend.query_instant = AsyncMock(return_value={
            "status": "success",
            "data": {"result": []}
        })
        
        skill = GoldenSignalsSkill(backend=backend)
        result = await skill.check_all_signals("missing-metrics-service")
        
        # Should report missing signals
        assert result.has_missing_signals()
        assert len(result.missing_signals) > 0
        assert len(result.warnings) > 0


# ============================================================================
# Changes Subagent Tests
# ============================================================================

class TestChangesSubagent:
    """Tests for the changes investigation subagent."""
    
    @pytest.mark.asyncio
    async def test_changes_correlates_with_incident(self):
        """Changes should correlate with incident timing."""
        from src.autosre.agents.subagents.changes import (
            ChangesSubagent, Change, ChangeType, ChangeSource
        )
        
        subagent = ChangesSubagent(dry_run=True)
        
        # Manually add test changes
        now = datetime.utcnow()
        test_changes = [
            Change(
                id="1",
                type=ChangeType.DEPLOYMENT,
                source=ChangeSource.KUBERNETES,
                timestamp=now - timedelta(minutes=10),
                service="api-gateway",
                description="Deploy v1.2.3",
            ),
            Change(
                id="2",
                type=ChangeType.CONFIG,
                source=ChangeSource.CONFIGMAP,
                timestamp=now - timedelta(hours=2),
                service="api-gateway",
                description="Update config",
            ),
        ]
        
        # Mock the k8s client
        subagent.k8s.get_deployment_events = AsyncMock(return_value=test_changes)
        
        result = await subagent.get_recent_changes(
            service="api-gateway",
            incident_time=now,
        )
        
        # Should identify the deployment as suspicious
        assert result.most_suspicious is not None
        assert result.most_suspicious.type == ChangeType.DEPLOYMENT
        assert result.correlation_score > 0.5
    
    @pytest.mark.asyncio
    async def test_changes_always_runs_first(self):
        """Changes subagent should be first in investigation."""
        from src.autosre.agents.planner import Planner, InvestigationPhase
        from src.autosre.agents.state import InvestigationState, Alert
        
        planner = Planner(llm_router=AsyncMock())
        planner._current_phase = InvestigationPhase.INVESTIGATE
        
        # Default agents should include changes first
        default = planner._default_agents({"name": "Test"})
        assert default[0] == "changes"


# ============================================================================
# Latency Metrics Tests (NO AVG!)
# ============================================================================

class TestLatencyMetrics:
    """Tests for proper latency measurement (percentiles, not averages)."""
    
    def test_validate_latency_query_rejects_avg(self):
        """Should reject queries using avg() for latency."""
        from src.autosre.skills.metrics.latency import validate_latency_query
        
        bad_queries = [
            "avg(http_request_duration_seconds)",
            "avg_over_time(latency[5m])",
            "avg by (service) (request_duration)",
            "avg without (instance) (http_latency)",
        ]
        
        for query in bad_queries:
            is_valid, error = validate_latency_query(query)
            assert is_valid is False, f"Should reject: {query}"
            assert "avg()" in error.lower()
    
    def test_validate_latency_query_accepts_histogram_quantile(self):
        """Should accept proper histogram_quantile queries."""
        from src.autosre.skills.metrics.latency import validate_latency_query
        
        good_queries = [
            "histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))",
            "histogram_quantile(0.95, rate(latency_bucket[5m]))",
        ]
        
        for query in good_queries:
            is_valid, error = validate_latency_query(query)
            assert is_valid is True, f"Should accept: {query}"
            assert error is None
    
    @pytest.mark.asyncio
    async def test_latency_skill_returns_all_percentiles(self):
        """Latency skill should return p50, p90, p95, p99, p999."""
        from src.autosre.skills.metrics.latency import LatencyMetricsSkill
        
        skill = LatencyMetricsSkill(prometheus_url="http://mock:9090")
        
        # Mock the prometheus query
        async def mock_query(query):
            return {
                "status": "success",
                "data": {"result": [{"value": [0, "0.100"]}]}
            }
        
        skill._query_prometheus = mock_query
        skill._detect_histogram_metric = AsyncMock(return_value="http_request_duration_seconds")
        
        result = await skill.get_latency("test-service")
        
        # Should have all percentiles
        pcts = result.percentiles.to_dict()
        assert "p50" in pcts
        assert "p90" in pcts
        assert "p95" in pcts
        assert "p99" in pcts
        assert "p999" in pcts
    
    @pytest.mark.asyncio
    async def test_latency_skill_flags_missing_histogram(self):
        """Should flag services without histogram metrics."""
        from src.autosre.skills.metrics.latency import LatencyMetricsSkill, LatencyStatus
        
        skill = LatencyMetricsSkill(prometheus_url="http://mock:9090")
        
        # No histogram metric found
        skill._detect_histogram_metric = AsyncMock(return_value=None)
        
        result = await skill.get_latency("no-histogram-service")
        
        assert result.status == LatencyStatus.MISSING
        assert result.has_histogram is False
        assert len(result.warnings) > 0


# ============================================================================
# Investigation Flow Tests
# ============================================================================

class TestInvestigationFlow:
    """Tests for the investigation phase flow."""
    
    def test_investigation_phases_order(self):
        """Phases should be in correct order."""
        from src.autosre.agents.planner import InvestigationPhase
        
        phases = list(InvestigationPhase)
        
        # Triage must be first
        assert phases[0] == InvestigationPhase.TRIAGE
        
        # Mitigate before investigate
        assert phases.index(InvestigationPhase.MITIGATE) < phases.index(InvestigationPhase.INVESTIGATE)
        
        # Document is last
        assert phases[-1] == InvestigationPhase.DOCUMENT
    
    def test_planner_enforces_triage_first(self):
        """Planner should enforce triage completion."""
        from src.autosre.agents.planner import require_triage_complete, InvestigationPhase
        
        # Try to start investigation without triage
        with pytest.raises(RuntimeError, match="Triage phase not complete"):
            require_triage_complete(None, InvestigationPhase.INVESTIGATE)
    
    def test_planner_enforces_mitigation_consideration(self):
        """Planner should require mitigation to be considered."""
        from src.autosre.agents.planner import require_triage_complete, InvestigationPhase
        
        # Triage result without mitigation consideration
        triage_result = {
            "status": "completed",
            "mitigation_considered": False,
        }
        
        with pytest.raises(RuntimeError, match="Mitigation not considered"):
            require_triage_complete(triage_result, InvestigationPhase.INVESTIGATE)
    
    @pytest.mark.asyncio
    async def test_orchestrator_runs_triage_first(self):
        """Orchestrator should run triage before investigation."""
        from src.autosre.orchestrator import Orchestrator, InvestigationStatus
        
        orchestrator = Orchestrator()
        
        # Start investigation
        inv = await orchestrator.start_investigation("alert-123", {})
        
        # State should start at pending
        assert inv.state == InvestigationStatus.PENDING
        
        # Mock the triage node to avoid actual execution
        mock_triage = AsyncMock()
        mock_triage.run = AsyncMock(return_value=MagicMock(
            is_service_impaired=True,
            impact=MagicMock(severity=MagicMock(value="high")),
            mitigation_considered=True,
            mitigation_options=[],
            model_dump=MagicMock(return_value={
                "is_service_impaired": True,
                "mitigation_considered": True,
            })
        ))
        orchestrator._triage_node = mock_triage
        
        # Run triage phase
        await orchestrator._run_triage_phase(inv)
        
        # Triage should be complete
        assert inv.triage_result is not None
        assert inv.metrics.triage_completed_at is not None


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for the full investigation quality flow."""
    
    @pytest.mark.asyncio
    async def test_full_triage_to_investigation_flow(self):
        """Test complete flow from triage to investigation."""
        from src.autosre.agents.nodes.triage import TriageNode, TriageStatus
        from src.autosre.agents.planner import Planner, InvestigationPhase, require_triage_complete
        
        # Create components with mocks
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value=MagicMock(
            content='{"is_service_impaired": true, "impact": {"severity": "high"}, "mitigation_options": [], "mitigation_considered": true}'
        ))
        
        # Run triage
        triage_node = TriageNode(llm_client=mock_llm)
        triage_result = await triage_node.run({"name": "Test", "service": "test"})
        
        # Skip mitigation (documented)
        triage_result = triage_node.skip_mitigation(triage_result, "No safe mitigation available")
        
        # Now investigation can proceed
        assert triage_result.can_proceed_to_investigation()
        
        # Planner accepts it
        triage_dict = {
            "status": triage_result.status.value,
            "mitigation_considered": triage_result.mitigation_considered,
        }
        
        # Should not raise
        require_triage_complete(triage_dict, InvestigationPhase.INVESTIGATE)


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
