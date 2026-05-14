"""Unit tests for RCA (Root Cause Analysis) modules."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

import numpy as np
import pytest

from autosre.ml.rca import (
    CausalGraph,
    RCAEngine,
    SymptomCorrelator,
    HypothesisRanker,
    EvidenceCollector,
)


class TestCausalGraph:
    """Tests for CausalGraph."""
    
    @pytest.fixture
    def graph(self):
        """Create a causal graph."""
        return CausalGraph()
    
    @pytest.fixture
    def sample_topology(self):
        """Create sample service topology."""
        return {
            "services": [
                {"name": "frontend", "dependencies": ["api-gateway"]},
                {"name": "api-gateway", "dependencies": ["auth-service", "user-service", "payment-service"]},
                {"name": "auth-service", "dependencies": ["redis", "database"]},
                {"name": "user-service", "dependencies": ["database"]},
                {"name": "payment-service", "dependencies": ["database", "external-payment-api"]},
                {"name": "redis", "dependencies": []},
                {"name": "database", "dependencies": []},
                {"name": "external-payment-api", "dependencies": []},
            ]
        }
    
    def test_create_graph(self, graph):
        """Test creating a causal graph."""
        assert graph is not None
    
    def test_add_node(self, graph):
        """Test adding nodes to graph."""
        graph.add_node("service-a", node_type="service", metadata={"tier": "frontend"})
        graph.add_node("service-b", node_type="service", metadata={"tier": "backend"})
        
        assert graph.has_node("service-a")
        assert graph.has_node("service-b")
    
    def test_add_edge(self, graph):
        """Test adding edges between nodes."""
        graph.add_node("upstream")
        graph.add_node("downstream")
        graph.add_edge("upstream", "downstream", edge_type="depends_on", weight=0.9)
        
        assert graph.has_edge("upstream", "downstream")
    
    def test_build_from_topology(self, graph, sample_topology):
        """Test building graph from topology."""
        graph.build_from_topology(sample_topology)
        
        assert graph.has_node("frontend")
        assert graph.has_node("database")
        assert graph.has_edge("frontend", "api-gateway")
    
    def test_get_upstream(self, graph, sample_topology):
        """Test getting upstream dependencies."""
        graph.build_from_topology(sample_topology)
        
        upstream = graph.get_upstream("database")
        
        # Database is upstream of: auth, user, payment
        assert len(upstream) >= 3
    
    def test_get_downstream(self, graph, sample_topology):
        """Test getting downstream dependencies."""
        graph.build_from_topology(sample_topology)
        
        downstream = graph.get_downstream("api-gateway")
        
        # API gateway depends on: auth, user, payment
        assert len(downstream) >= 3
    
    def test_find_paths(self, graph, sample_topology):
        """Test finding paths between nodes."""
        graph.build_from_topology(sample_topology)
        
        paths = graph.find_paths("frontend", "database")
        
        assert len(paths) > 0
        # Frontend -> api-gateway -> user-service -> database is one path
    
    def test_get_causal_ancestors(self, graph, sample_topology):
        """Test getting causal ancestors."""
        graph.build_from_topology(sample_topology)
        
        ancestors = graph.get_causal_ancestors("frontend")
        
        # All dependencies and their dependencies
        assert len(ancestors) >= 5


class TestRCAEngine:
    """Tests for RCAEngine."""
    
    @pytest.fixture
    def engine(self):
        """Create an RCA engine."""
        return RCAEngine()
    
    @pytest.fixture
    def sample_symptoms(self):
        """Create sample symptoms."""
        return [
            {
                "type": "high_latency",
                "service": "api-gateway",
                "value": 500,  # ms
                "threshold": 100,
                "started_at": datetime.utcnow() - timedelta(minutes=15),
            },
            {
                "type": "high_error_rate",
                "service": "payment-service",
                "value": 0.1,  # 10%
                "threshold": 0.01,
                "started_at": datetime.utcnow() - timedelta(minutes=10),
            },
            {
                "type": "cpu_high",
                "service": "database",
                "value": 95,
                "threshold": 80,
                "started_at": datetime.utcnow() - timedelta(minutes=20),
            },
        ]
    
    def test_create_engine(self, engine):
        """Test creating RCA engine."""
        assert engine is not None
    
    def test_analyze_basic(self, engine, sample_symptoms):
        """Test basic RCA analysis."""
        result = engine.analyze(sample_symptoms)
        
        assert result is not None
        assert "root_causes" in result or hasattr(result, "root_causes")
    
    def test_rank_hypotheses(self, engine, sample_symptoms):
        """Test ranking hypotheses."""
        hypotheses = [
            {"cause": "database_overload", "probability": 0.8},
            {"cause": "network_issue", "probability": 0.3},
            {"cause": "code_bug", "probability": 0.5},
        ]
        
        ranked = engine.rank_hypotheses(hypotheses, sample_symptoms)
        
        assert len(ranked) == 3
        # Should be sorted by probability/score
    
    def test_identify_impact_chain(self, engine):
        """Test identifying impact chain."""
        chain = engine.identify_impact_chain(
            root_cause="database_cpu_high",
            affected_services=["payment-service", "api-gateway", "frontend"],
        )
        
        assert chain is not None


class TestSymptomCorrelator:
    """Tests for SymptomCorrelator."""
    
    @pytest.fixture
    def correlator(self):
        """Create a symptom correlator."""
        return SymptomCorrelator()
    
    @pytest.fixture
    def sample_symptoms_timeseries(self):
        """Create sample symptom time series."""
        now = datetime.utcnow()
        
        return {
            "database_cpu": [
                (now - timedelta(minutes=25), 50),
                (now - timedelta(minutes=20), 75),
                (now - timedelta(minutes=15), 90),
                (now - timedelta(minutes=10), 95),
                (now - timedelta(minutes=5), 95),
                (now, 95),
            ],
            "payment_latency": [
                (now - timedelta(minutes=25), 50),
                (now - timedelta(minutes=20), 50),
                (now - timedelta(minutes=15), 100),
                (now - timedelta(minutes=10), 300),
                (now - timedelta(minutes=5), 500),
                (now, 500),
            ],
            "api_gateway_latency": [
                (now - timedelta(minutes=25), 30),
                (now - timedelta(minutes=20), 30),
                (now - timedelta(minutes=15), 50),
                (now - timedelta(minutes=10), 150),
                (now - timedelta(minutes=5), 300),
                (now, 400),
            ],
        }
    
    def test_create_correlator(self, correlator):
        """Test creating symptom correlator."""
        assert correlator is not None
    
    def test_correlate_symptoms(self, correlator, sample_symptoms_timeseries):
        """Test correlating symptoms."""
        correlations = correlator.correlate(sample_symptoms_timeseries)
        
        assert correlations is not None
        # Database CPU and payment latency should be highly correlated
    
    def test_find_leading_indicators(self, correlator, sample_symptoms_timeseries):
        """Test finding leading indicators."""
        leaders = correlator.find_leading_indicators(
            sample_symptoms_timeseries,
            target="api_gateway_latency",
        )
        
        assert len(leaders) > 0
        # Database CPU spike happened first
    
    def test_calculate_time_lag(self, correlator, sample_symptoms_timeseries):
        """Test calculating time lag between symptoms."""
        lag = correlator.calculate_time_lag(
            sample_symptoms_timeseries,
            source="database_cpu",
            target="payment_latency",
        )
        
        assert lag is not None
        # Database spike led payment latency by ~5 minutes


class TestHypothesisRanker:
    """Tests for HypothesisRanker."""
    
    @pytest.fixture
    def ranker(self):
        """Create a hypothesis ranker."""
        return HypothesisRanker()
    
    @pytest.fixture
    def sample_hypotheses(self):
        """Create sample hypotheses."""
        return [
            {
                "id": "h1",
                "description": "Database CPU saturation causing slow queries",
                "evidence_for": ["db_cpu_high", "slow_queries", "payment_latency"],
                "evidence_against": [],
                "prior_probability": 0.3,
            },
            {
                "id": "h2",
                "description": "Network partition between payment service and database",
                "evidence_for": ["payment_errors"],
                "evidence_against": ["other_services_ok"],
                "prior_probability": 0.2,
            },
            {
                "id": "h3",
                "description": "Memory leak in payment service",
                "evidence_for": ["payment_memory_high"],
                "evidence_against": ["recent_restart_ok"],
                "prior_probability": 0.1,
            },
        ]
    
    def test_create_ranker(self, ranker):
        """Test creating hypothesis ranker."""
        assert ranker is not None
    
    def test_rank_by_evidence(self, ranker, sample_hypotheses):
        """Test ranking hypotheses by evidence."""
        ranked = ranker.rank(sample_hypotheses)
        
        assert len(ranked) == 3
        # H1 should be ranked highest (most evidence)
    
    def test_compute_posterior(self, ranker, sample_hypotheses):
        """Test computing posterior probability."""
        evidence = ["db_cpu_high", "slow_queries"]
        
        posterior = ranker.compute_posterior(
            sample_hypotheses[0],
            evidence,
        )
        
        assert 0 <= posterior <= 1
        # Should be higher than prior given matching evidence
        assert posterior > sample_hypotheses[0]["prior_probability"]
    
    def test_update_with_new_evidence(self, ranker, sample_hypotheses):
        """Test updating rankings with new evidence."""
        initial_ranking = ranker.rank(sample_hypotheses)
        
        new_evidence = "network_error_logs"
        updated_ranking = ranker.update_with_evidence(
            initial_ranking,
            new_evidence,
            supports_hypothesis="h2",
        )
        
        assert updated_ranking is not None


class TestEvidenceCollector:
    """Tests for EvidenceCollector."""
    
    @pytest.fixture
    def collector(self):
        """Create an evidence collector."""
        return EvidenceCollector()
    
    @pytest.fixture
    def sample_hypothesis(self):
        """Create sample hypothesis to collect evidence for."""
        return {
            "id": "h1",
            "description": "Database CPU saturation",
            "required_evidence": [
                "cpu_metrics",
                "query_performance",
                "connection_pool_stats",
            ],
        }
    
    def test_create_collector(self, collector):
        """Test creating evidence collector."""
        assert collector is not None
    
    def test_collect_for_hypothesis(self, collector, sample_hypothesis):
        """Test collecting evidence for hypothesis."""
        evidence = collector.collect(
            sample_hypothesis,
            time_range=timedelta(hours=1),
        )
        
        assert evidence is not None
    
    def test_prioritize_evidence_sources(self, collector, sample_hypothesis):
        """Test prioritizing evidence sources."""
        sources = collector.prioritize_sources(sample_hypothesis)
        
        assert len(sources) > 0
        # More relevant sources should be first
    
    def test_aggregate_evidence(self, collector):
        """Test aggregating evidence from multiple sources."""
        evidence_pieces = [
            {"source": "prometheus", "metric": "cpu_usage", "value": 95},
            {"source": "logs", "pattern": "slow query", "count": 150},
            {"source": "traces", "operation": "db_query", "p99_latency": 5000},
        ]
        
        aggregated = collector.aggregate(evidence_pieces)
        
        assert aggregated is not None
        assert "summary" in aggregated or hasattr(aggregated, "summary")
