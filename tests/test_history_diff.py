"""
Tests for the history diff command.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

from autosre.memory.models import Episode
from autosre.cli.commands.history import _build_diff_analysis, diff_investigations


# Test fixtures
@pytest.fixture
def episode1():
    """Sample episode 1 for comparison."""
    return Episode(
        id="test-001",
        alert_type="high_error_rate",
        service_name="checkout-service",
        severity="high",
        root_cause="Database connection pool exhaustion due to slow queries",
        summary="Checkout service experienced high error rates due to database issues",
        resolved=True,
        effectiveness_score=0.85,
        skills_used=["prometheus_query", "log_analysis", "database_check"],
        key_findings=[
            {"finding": "Error rate spiked to 45%", "confidence": 0.9},
            {"finding": "Database queries taking >5s", "confidence": 0.95},
        ],
        duration_seconds=1800,  # 30 minutes
        steps_taken=[
            "Checked error rate metrics",
            "Analyzed application logs",
            "Reviewed database performance",
        ],
        created_at=datetime.now(timezone.utc) - timedelta(days=7),
    )


@pytest.fixture
def episode2():
    """Sample episode 2 for comparison."""
    return Episode(
        id="test-002",
        alert_type="high_error_rate",
        service_name="checkout-service",
        severity="critical",
        root_cause="Database connection pool exhaustion caused by memory leak",
        summary="Recurring database issues with additional memory leak identified",
        resolved=True,
        effectiveness_score=0.92,
        skills_used=["prometheus_query", "log_analysis", "memory_profiler"],
        key_findings=[
            {"finding": "Error rate spiked to 60%", "confidence": 0.95},
            {"finding": "Memory leak in connection pooling", "confidence": 0.88},
        ],
        duration_seconds=1200,  # 20 minutes
        steps_taken=[
            "Checked error rate metrics",
            "Analyzed application logs",
            "Profiled memory usage",
            "Reviewed recent deployments",
        ],
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def episode_different_service():
    """Episode from a different service."""
    return Episode(
        id="test-003",
        alert_type="latency_spike",
        service_name="api-gateway",
        severity="medium",
        root_cause="Upstream timeout from payment service",
        summary="API gateway latency caused by payment service issues",
        resolved=True,
        effectiveness_score=0.75,
        skills_used=["trace_analysis", "log_analysis"],
        key_findings=[
            {"finding": "P99 latency exceeded 2s", "confidence": 0.85},
        ],
        duration_seconds=2400,  # 40 minutes
        created_at=datetime.now(timezone.utc) - timedelta(days=1),
    )


class TestBuildDiffAnalysis:
    """Tests for _build_diff_analysis function."""
    
    def test_same_service_same_alert_type(self, episode1, episode2):
        """Test comparison of episodes with same service and alert type."""
        diff = _build_diff_analysis(episode1, episode2)
        
        assert diff["same_service"] is True
        assert diff["same_alert_type"] is True
        assert diff["root_cause_similarity"] > 0.3  # Should have some overlap
    
    def test_different_service_different_alert(self, episode1, episode_different_service):
        """Test comparison of episodes with different service and alert type."""
        diff = _build_diff_analysis(episode1, episode_different_service)
        
        assert diff["same_service"] is False
        assert diff["same_alert_type"] is False
    
    def test_field_changes_detected(self, episode1, episode2):
        """Test that field changes are properly detected."""
        diff = _build_diff_analysis(episode1, episode2)
        
        # Severity changed from high to critical
        assert "severity" in diff["field_changes"]
        assert diff["field_changes"]["severity"]["old"] == "high"
        assert diff["field_changes"]["severity"]["new"] == "critical"
    
    def test_skills_comparison(self, episode1, episode2):
        """Test skills added/removed/common comparison."""
        diff = _build_diff_analysis(episode1, episode2)
        
        skills = diff["skills"]
        assert "prometheus_query" in skills["common"]
        assert "log_analysis" in skills["common"]
        assert "memory_profiler" in skills["added"]
        assert "database_check" in skills["removed"]
    
    def test_steps_comparison(self, episode1, episode2):
        """Test steps added/removed comparison."""
        diff = _build_diff_analysis(episode1, episode2)
        
        steps = diff["steps"]
        assert "Profiled memory usage" in steps["added"]
        assert "Reviewed recent deployments" in steps["added"]
        assert "Reviewed database performance" in steps["removed"]
    
    def test_timeline_analysis(self, episode1, episode2):
        """Test timeline difference calculation."""
        diff = _build_diff_analysis(episode1, episode2)
        
        timeline = diff["timeline"]
        assert timeline is not None
        assert timeline["direction"] == "later"
        assert timeline["days"] >= 6  # ~7 days difference
    
    def test_duration_comparison(self, episode1, episode2):
        """Test duration difference calculation."""
        diff = _build_diff_analysis(episode1, episode2)
        
        duration = diff["duration"]
        assert duration is not None
        assert duration["direction"] == "shorter"
        assert duration["diff_seconds"] == -600  # 10 minutes shorter
    
    def test_effectiveness_comparison(self, episode1, episode2):
        """Test effectiveness score comparison."""
        diff = _build_diff_analysis(episode1, episode2)
        
        effectiveness = diff["effectiveness"]
        assert effectiveness is not None
        assert effectiveness["direction"] == "improved"
        assert effectiveness["diff"] == pytest.approx(0.07, abs=0.01)
    
    def test_root_cause_similarity_high(self, episode1, episode2):
        """Test that similar root causes have high similarity."""
        diff = _build_diff_analysis(episode1, episode2)
        
        # Both mention database connection pool
        assert diff["root_cause_similarity"] > 0.3
    
    def test_root_cause_similarity_low(self, episode1, episode_different_service):
        """Test that different root causes have low similarity."""
        diff = _build_diff_analysis(episode1, episode_different_service)
        
        # Different root causes
        assert diff["root_cause_similarity"] < 0.3


class TestDiffCommand:
    """Integration tests for the diff command."""
    
    def test_diff_command_not_found(self, capsys):
        """Test that diff command handles missing episodes."""
        from click.exceptions import Exit
        with patch('autosre.cli.commands.history._get_memory') as mock_memory:
            memory = AsyncMock()
            memory.get = AsyncMock(return_value=None)
            memory.retrieve = AsyncMock(return_value=[])
            mock_memory.return_value = memory
            
            with pytest.raises((SystemExit, Exit)):
                diff_investigations(
                    id1="nonexistent",
                    id2="alsonotfound",
                    json_output=False,
                    fields_only=False,
                )
    
    def test_diff_command_json_output(self, episode1, episode2, capsys):
        """Test diff command with JSON output."""
        with patch('autosre.cli.commands.history._get_memory') as mock_memory:
            memory = AsyncMock()
            
            async def mock_get(id):
                if id == "test-001":
                    return episode1
                elif id == "test-002":
                    return episode2
                return None
            
            memory.get = mock_get
            memory.retrieve = AsyncMock(return_value=[episode1, episode2])
            mock_memory.return_value = memory
            
            diff_investigations(
                id1="test-001",
                id2="test-002",
                json_output=True,
                fields_only=False,
            )
            
            captured = capsys.readouterr()
            assert "root_cause_similarity" in captured.out
            assert "same_service" in captured.out


class TestTextSimilarity:
    """Tests for the text similarity calculation."""
    
    def test_identical_text(self):
        """Test similarity of identical texts."""
        from autosre.cli.commands.history import _build_diff_analysis
        
        ep1 = Episode(
            id="a",
            alert_type="test",
            root_cause="Database connection timeout",
        )
        ep2 = Episode(
            id="b",
            alert_type="test",
            root_cause="Database connection timeout",
        )
        
        diff = _build_diff_analysis(ep1, ep2)
        assert diff["root_cause_similarity"] == 1.0
    
    def test_no_text(self):
        """Test similarity when one or both texts are None."""
        from autosre.cli.commands.history import _build_diff_analysis
        
        ep1 = Episode(id="a", alert_type="test", root_cause=None)
        ep2 = Episode(id="b", alert_type="test", root_cause="Some cause")
        
        diff = _build_diff_analysis(ep1, ep2)
        assert diff["root_cause_similarity"] == 0.0
    
    def test_partial_overlap(self):
        """Test similarity with partial text overlap."""
        from autosre.cli.commands.history import _build_diff_analysis
        
        ep1 = Episode(
            id="a",
            alert_type="test",
            root_cause="Database slow queries causing timeout",
        )
        ep2 = Episode(
            id="b",
            alert_type="test",
            root_cause="Database connection pool causing timeout",
        )
        
        diff = _build_diff_analysis(ep1, ep2)
        # Should have some overlap (database, causing, timeout)
        assert 0.3 < diff["root_cause_similarity"] < 0.9
