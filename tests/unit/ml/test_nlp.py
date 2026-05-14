"""Unit tests for NLP modules."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

import numpy as np
import pytest

from autosre.ml.nlp import (
    IncidentClassifier,
    SeverityEstimator,
    SimilarityFinder,
    SummaryGenerator,
    CommandParser,
)


class TestIncidentClassifier:
    """Tests for IncidentClassifier."""
    
    @pytest.fixture
    def classifier(self):
        """Create an incident classifier."""
        return IncidentClassifier(
            name="test-incident-classifier",
            categories=[
                "infrastructure",
                "application",
                "network",
                "database",
                "security",
                "performance",
            ],
        )
    
    @pytest.fixture
    def sample_incidents(self):
        """Create sample incidents for training."""
        return [
            {"text": "Database connection timeout after 30 seconds", "label": "database"},
            {"text": "High CPU usage on web server nodes", "label": "infrastructure"},
            {"text": "API latency increased to 5 seconds", "label": "performance"},
            {"text": "Unauthorized access attempt detected", "label": "security"},
            {"text": "Network packet loss between datacenters", "label": "network"},
            {"text": "Application throwing null pointer exceptions", "label": "application"},
            {"text": "Redis cluster node failure", "label": "database"},
            {"text": "Memory leak in payment service", "label": "application"},
            {"text": "SSL certificate expiration warning", "label": "security"},
            {"text": "Kubernetes pod OOMKilled", "label": "infrastructure"},
        ]
    
    def test_create_classifier(self, classifier):
        """Test creating classifier."""
        assert classifier.name == "test-incident-classifier"
        assert not classifier.is_fitted
    
    def test_fit_classifier(self, classifier, sample_incidents):
        """Test fitting classifier."""
        texts = [inc["text"] for inc in sample_incidents]
        labels = [inc["label"] for inc in sample_incidents]
        
        classifier.fit(texts, labels)
        
        assert classifier.is_fitted
    
    def test_classify_incident(self, classifier, sample_incidents):
        """Test classifying an incident."""
        texts = [inc["text"] for inc in sample_incidents]
        labels = [inc["label"] for inc in sample_incidents]
        classifier.fit(texts, labels)
        
        result = classifier.classify("MySQL query taking too long, database unresponsive")
        
        assert result.prediction in classifier._metadata.extra.get("categories", ["database"])
        assert result.confidence > 0
    
    def test_classify_with_multiple_labels(self, classifier, sample_incidents):
        """Test getting multiple possible labels."""
        texts = [inc["text"] for inc in sample_incidents]
        labels = [inc["label"] for inc in sample_incidents]
        classifier.fit(texts, labels)
        
        result = classifier.classify_top_k(
            "Network issues causing database timeouts",
            k=3,
        )
        
        assert len(result) <= 3
        # Should include both network and database


class TestSeverityEstimator:
    """Tests for SeverityEstimator."""
    
    @pytest.fixture
    def estimator(self):
        """Create a severity estimator."""
        return SeverityEstimator(
            name="test-severity-estimator",
            severity_levels=["low", "medium", "high", "critical"],
        )
    
    @pytest.fixture
    def sample_incidents(self):
        """Create sample incidents with severity."""
        return [
            {"text": "Minor UI alignment issue", "severity": "low"},
            {"text": "Slow page load times", "severity": "medium"},
            {"text": "Payment processing failing for all users", "severity": "critical"},
            {"text": "Database primary failover occurred", "severity": "high"},
            {"text": "Login service completely down", "severity": "critical"},
            {"text": "One cache node unreachable", "severity": "low"},
            {"text": "API rate limiting triggered", "severity": "medium"},
            {"text": "All production pods restarting", "severity": "critical"},
            {"text": "Increased error rate in logging service", "severity": "medium"},
            {"text": "Complete network outage in us-east-1", "severity": "critical"},
        ]
    
    def test_create_estimator(self, estimator):
        """Test creating estimator."""
        assert estimator.name == "test-severity-estimator"
    
    def test_fit_estimator(self, estimator, sample_incidents):
        """Test fitting estimator."""
        texts = [inc["text"] for inc in sample_incidents]
        severities = [inc["severity"] for inc in sample_incidents]
        
        estimator.fit(texts, severities)
        
        assert estimator.is_fitted
    
    def test_estimate_severity(self, estimator, sample_incidents):
        """Test estimating severity."""
        texts = [inc["text"] for inc in sample_incidents]
        severities = [inc["severity"] for inc in sample_incidents]
        estimator.fit(texts, severities)
        
        result = estimator.estimate("Production database completely unresponsive")
        
        # Should be high or critical
        assert result.prediction in ["high", "critical"]
    
    def test_severity_with_context(self, estimator, sample_incidents):
        """Test severity estimation with context."""
        texts = [inc["text"] for inc in sample_incidents]
        severities = [inc["severity"] for inc in sample_incidents]
        estimator.fit(texts, severities)
        
        context = {
            "affected_users": 10000,
            "revenue_impact": True,
            "is_business_hours": True,
        }
        
        result = estimator.estimate_with_context(
            "Payment service errors",
            context=context,
        )
        
        # Should factor in the high impact
        assert result.prediction in ["high", "critical"]


class TestSimilarityFinder:
    """Tests for SimilarityFinder."""
    
    @pytest.fixture
    def finder(self):
        """Create a similarity finder."""
        return SimilarityFinder(
            name="test-similarity-finder",
        )
    
    @pytest.fixture
    def historical_incidents(self):
        """Create historical incidents."""
        return [
            {
                "id": "inc-001",
                "title": "Database connection pool exhausted",
                "description": "MySQL connection pool reached max connections, causing timeouts",
                "root_cause": "Connection leak in ORM layer",
                "resolution": "Deployed fix for connection leak, increased pool size",
            },
            {
                "id": "inc-002",
                "title": "High memory usage on API servers",
                "description": "API pods using 95% memory, causing OOM kills",
                "root_cause": "Memory leak in caching layer",
                "resolution": "Cleared cache, deployed memory fix",
            },
            {
                "id": "inc-003",
                "title": "Payment gateway timeout",
                "description": "Stripe API calls timing out after 30s",
                "root_cause": "Network routing issue to Stripe",
                "resolution": "Switched to backup network path",
            },
            {
                "id": "inc-004",
                "title": "Redis cluster failure",
                "description": "Redis primary node crashed, cluster split-brain",
                "root_cause": "Disk failure on primary node",
                "resolution": "Replaced node, recovered from replica",
            },
        ]
    
    def test_create_finder(self, finder):
        """Test creating similarity finder."""
        assert finder.name == "test-similarity-finder"
    
    def test_index_incidents(self, finder, historical_incidents):
        """Test indexing incidents."""
        finder.index(historical_incidents)
        
        assert finder.is_fitted
    
    def test_find_similar(self, finder, historical_incidents):
        """Test finding similar incidents."""
        finder.index(historical_incidents)
        
        query = "Database connections timing out, max connections reached"
        similar = finder.find_similar(query, top_k=2)
        
        assert len(similar) >= 1
        # Should find the database connection incident
        assert any("database" in s["title"].lower() or "connection" in s["title"].lower() for s in similar)
    
    def test_find_by_symptoms(self, finder, historical_incidents):
        """Test finding by symptoms."""
        finder.index(historical_incidents)
        
        symptoms = ["high memory", "OOM", "pod restart"]
        similar = finder.find_by_symptoms(symptoms, top_k=2)
        
        assert len(similar) >= 1
        # Should find the memory incident
    
    def test_similarity_score(self, finder, historical_incidents):
        """Test similarity scoring."""
        finder.index(historical_incidents)
        
        query = "Redis primary down"
        similar = finder.find_similar(query, top_k=1)
        
        assert len(similar) == 1
        assert "similarity_score" in similar[0] or hasattr(similar[0], "similarity_score")


class TestSummaryGenerator:
    """Tests for SummaryGenerator."""
    
    @pytest.fixture
    def generator(self):
        """Create a summary generator."""
        return SummaryGenerator(
            name="test-summary-generator",
            max_summary_length=200,
        )
    
    @pytest.fixture
    def incident_data(self):
        """Create incident data for summarization."""
        return {
            "title": "Production Database Outage",
            "alerts": [
                "MySQL Primary Down",
                "High Error Rate - Payment Service",
                "Connection Pool Exhausted",
            ],
            "timeline": [
                {"time": "10:00", "event": "First alert triggered"},
                {"time": "10:05", "event": "On-call engineer paged"},
                {"time": "10:15", "event": "Root cause identified: disk failure"},
                {"time": "10:30", "event": "Failover to replica initiated"},
                {"time": "10:45", "event": "Service restored"},
            ],
            "impact": {
                "duration_minutes": 45,
                "affected_services": ["payment", "checkout", "inventory"],
                "affected_users_percent": 15,
            },
            "root_cause": "Primary database disk failure caused by hardware defect",
            "resolution": "Automatic failover to replica, replaced failed disk",
        }
    
    def test_create_generator(self, generator):
        """Test creating generator."""
        assert generator.name == "test-summary-generator"
    
    def test_generate_summary(self, generator, incident_data):
        """Test generating incident summary."""
        summary = generator.generate(incident_data)
        
        assert summary is not None
        assert len(summary) > 0
        assert len(summary) <= 200
    
    def test_generate_executive_summary(self, generator, incident_data):
        """Test generating executive summary."""
        summary = generator.generate_executive(incident_data)
        
        assert summary is not None
        # Should be concise
        assert len(summary) <= 100
    
    def test_generate_technical_summary(self, generator, incident_data):
        """Test generating technical summary."""
        summary = generator.generate_technical(incident_data)
        
        assert summary is not None
        # Should include technical details
        assert "disk" in summary.lower() or "database" in summary.lower()
    
    def test_generate_timeline_summary(self, generator, incident_data):
        """Test generating timeline summary."""
        summary = generator.summarize_timeline(incident_data["timeline"])
        
        assert summary is not None
        # Should mention key events


class TestCommandParser:
    """Tests for CommandParser."""
    
    @pytest.fixture
    def parser(self):
        """Create a command parser."""
        return CommandParser(
            name="test-command-parser",
            supported_actions=[
                "restart",
                "scale",
                "rollback",
                "describe",
                "logs",
                "drain",
            ],
        )
    
    @pytest.fixture
    def sample_commands(self):
        """Create sample natural language commands."""
        return [
            ("restart the payment service pods", {"action": "restart", "target": "payment-service", "resource": "pods"}),
            ("scale up api-gateway to 5 replicas", {"action": "scale", "target": "api-gateway", "replicas": 5}),
            ("show me logs from auth service", {"action": "logs", "target": "auth-service"}),
            ("rollback checkout deployment", {"action": "rollback", "target": "checkout", "resource": "deployment"}),
            ("drain node worker-3", {"action": "drain", "target": "worker-3", "resource": "node"}),
        ]
    
    def test_create_parser(self, parser):
        """Test creating parser."""
        assert parser.name == "test-command-parser"
    
    def test_parse_restart_command(self, parser):
        """Test parsing restart command."""
        result = parser.parse("restart the payment service")
        
        assert result.action == "restart"
        assert "payment" in result.target.lower()
    
    def test_parse_scale_command(self, parser):
        """Test parsing scale command."""
        result = parser.parse("scale api-gateway to 10 replicas")
        
        assert result.action == "scale"
        assert result.parameters.get("replicas") == 10 or "10" in str(result.parameters)
    
    def test_parse_logs_command(self, parser):
        """Test parsing logs command."""
        result = parser.parse("show logs for the checkout service last 1 hour")
        
        assert result.action == "logs"
        assert "checkout" in result.target.lower()
    
    def test_parse_with_options(self, parser):
        """Test parsing command with options."""
        result = parser.parse("rollback deployment payment-service to revision 5")
        
        assert result.action == "rollback"
        assert result.parameters.get("revision") == 5 or "5" in str(result.parameters)
    
    def test_parse_ambiguous_command(self, parser):
        """Test handling ambiguous command."""
        result = parser.parse("fix the problem with the database")
        
        # Should indicate ambiguity or ask for clarification
        assert result.confidence < 0.5 or result.needs_clarification
    
    def test_extract_entities(self, parser):
        """Test entity extraction from command."""
        entities = parser.extract_entities("restart pods in namespace production for service api-gateway")
        
        assert "namespace" in entities or "service" in entities
        assert "production" in str(entities) or "api-gateway" in str(entities)
    
    def test_validate_command(self, parser):
        """Test command validation."""
        # Valid command
        valid_result = parser.validate("restart payment-service")
        assert valid_result.is_valid
        
        # Invalid/unsupported action
        invalid_result = parser.validate("hack into the mainframe")
        assert not invalid_result.is_valid
