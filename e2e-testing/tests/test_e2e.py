"""
AutoSRE End-to-End Test Suite

Tests AutoSRE's ability to detect and diagnose various failure scenarios
in the bookstore application running on a Kind cluster.

Scenarios:
1. High Error Rate - 5xx errors from API
2. OOM Kill - Memory exhaustion causing pod kills
3. CPU Throttling - High CPU usage degrading performance
4. Database Connection Pool Exhaustion
5. Network Partition - Service connectivity issues
6. Cascading Failure - Multiple services affected
"""

import pytest
import os
import subprocess
import time
from pathlib import Path
from typing import Generator

from test_harness import (
    AutoSRETestHarness,
    InvestigationResult,
    ExpectedResult,
    VerificationResult
)


# Test configuration
CONFIG_PATH = os.environ.get("AUTOSRE_CONFIG", "../autosre-config.yaml")
CHAOS_DIR = os.environ.get("CHAOS_DIR", "../chaos/scenarios")
RESET_SCRIPT = os.environ.get("RESET_SCRIPT", "../chaos/reset-all.sh")
METRICS_WAIT_SECONDS = int(os.environ.get("METRICS_WAIT", "30"))


@pytest.fixture(scope="session")
def harness() -> AutoSRETestHarness:
    """Create test harness for the session."""
    return AutoSRETestHarness(
        config_path=CONFIG_PATH,
        timeout_seconds=300,
        working_dir=str(Path(__file__).parent.parent)
    )


@pytest.fixture(scope="session")
def cluster_ready() -> bool:
    """Verify Kind cluster is ready before tests."""
    try:
        result = subprocess.run(
            ["kubectl", "cluster-info", "--context", "kind-autosre-e2e"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            pytest.skip("Kind cluster not ready")
        return True
    except Exception as e:
        pytest.skip(f"Cannot connect to cluster: {e}")


@pytest.fixture(scope="session")
def prometheus_ready() -> bool:
    """Verify Prometheus is accessible."""
    try:
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
             "http://localhost:30090/-/healthy"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.stdout.strip() != "200":
            pytest.skip("Prometheus not healthy")
        return True
    except Exception as e:
        pytest.skip(f"Cannot connect to Prometheus: {e}")


@pytest.fixture(autouse=True)
def reset_after_test(harness: AutoSRETestHarness) -> Generator:
    """Reset chaos after each test."""
    yield
    harness.reset_chaos(RESET_SCRIPT)
    time.sleep(10)  # Allow system to stabilize


class TestAutoSREE2E:
    """End-to-end tests for AutoSRE investigation capabilities."""
    
    def test_scenario_1_high_error_rate(
        self,
        harness: AutoSRETestHarness,
        cluster_ready: bool,
        prometheus_ready: bool
    ):
        """
        Scenario 1: High Error Rate
        
        Injects 5xx errors into the bookstore-api service.
        AutoSRE should detect elevated error rates and identify the API
        as the source of errors.
        """
        # Inject chaos
        scenario_script = f"{CHAOS_DIR}/scenario-1.sh"
        assert harness.run_chaos_scenario(scenario_script, METRICS_WAIT_SECONDS), \
            "Failed to inject high error rate chaos"
        
        # Run investigation
        result = harness.run_investigation(
            "High error rate detected in bookstore-api - 5xx responses increased"
        )
        
        # Verify detection
        expected = ExpectedResult(
            root_cause_keywords=["error", "5xx", "http", "status", "failure", "api"],
            evidence_types=["metrics", "logs"],
            min_confidence=0.7,
            expected_recommendations=["rollback", "restart", "scale"]
        )
        
        verification = harness.verify_detection(result, expected)
        
        assert result.success, f"Investigation failed: {result.error}"
        assert verification.root_cause_match, \
            f"Root cause not detected. Got: {result.root_cause}"
        assert verification.confidence_sufficient, \
            f"Confidence too low: {result.confidence} < {expected.min_confidence}"
    
    def test_scenario_2_oom_kill(
        self,
        harness: AutoSRETestHarness,
        cluster_ready: bool,
        prometheus_ready: bool
    ):
        """
        Scenario 2: OOM Kill
        
        Causes memory exhaustion leading to pod OOM kills.
        AutoSRE should detect memory pressure and OOMKilled pods.
        """
        scenario_script = f"{CHAOS_DIR}/scenario-2.sh"
        assert harness.run_chaos_scenario(scenario_script, METRICS_WAIT_SECONDS), \
            "Failed to inject OOM chaos"
        
        result = harness.run_investigation(
            "Pod restarts detected in bookstore namespace - possible OOM"
        )
        
        expected = ExpectedResult(
            root_cause_keywords=["oom", "memory", "kill", "restart", "limit"],
            evidence_types=["metrics", "events"],
            min_confidence=0.6,
            expected_recommendations=["memory", "limit", "request"]
        )
        
        verification = harness.verify_detection(result, expected)
        
        assert result.success, f"Investigation failed: {result.error}"
        assert verification.root_cause_match, \
            f"OOM not detected. Got: {result.root_cause}"
        assert verification.evidence_collected, \
            f"Missing evidence types. Found: {verification.details.get('evidence_types_found')}"
    
    def test_scenario_3_cpu_throttling(
        self,
        harness: AutoSRETestHarness,
        cluster_ready: bool,
        prometheus_ready: bool
    ):
        """
        Scenario 3: CPU Throttling
        
        Injects CPU stress causing throttling and latency increases.
        AutoSRE should detect CPU saturation and its impact on latency.
        """
        scenario_script = f"{CHAOS_DIR}/scenario-3.sh"
        assert harness.run_chaos_scenario(scenario_script, METRICS_WAIT_SECONDS), \
            "Failed to inject CPU throttling chaos"
        
        result = harness.run_investigation(
            "Increased latency in bookstore-api - p99 latency above SLO"
        )
        
        expected = ExpectedResult(
            root_cause_keywords=["cpu", "throttl", "latency", "saturat", "limit"],
            evidence_types=["metrics"],
            min_confidence=0.6,
            expected_recommendations=["cpu", "limit", "scale"]
        )
        
        verification = harness.verify_detection(result, expected)
        
        assert result.success, f"Investigation failed: {result.error}"
        assert verification.root_cause_match, \
            f"CPU throttling not detected. Got: {result.root_cause}"
    
    def test_scenario_4_db_connection_pool(
        self,
        harness: AutoSRETestHarness,
        cluster_ready: bool,
        prometheus_ready: bool
    ):
        """
        Scenario 4: Database Connection Pool Exhaustion
        
        Exhausts database connection pool causing request failures.
        AutoSRE should identify database connectivity as the root cause.
        """
        scenario_script = f"{CHAOS_DIR}/scenario-4.sh"
        assert harness.run_chaos_scenario(scenario_script, METRICS_WAIT_SECONDS), \
            "Failed to inject DB connection pool chaos"
        
        result = harness.run_investigation(
            "Database errors in bookstore-api - connection timeouts"
        )
        
        expected = ExpectedResult(
            root_cause_keywords=["database", "connection", "pool", "timeout", "db", "postgres"],
            evidence_types=["metrics", "logs"],
            min_confidence=0.6,
            expected_recommendations=["connection", "pool", "timeout"]
        )
        
        verification = harness.verify_detection(result, expected)
        
        assert result.success, f"Investigation failed: {result.error}"
        assert verification.root_cause_match, \
            f"DB connection issues not detected. Got: {result.root_cause}"
    
    def test_scenario_5_network_partition(
        self,
        harness: AutoSRETestHarness,
        cluster_ready: bool,
        prometheus_ready: bool
    ):
        """
        Scenario 5: Network Partition
        
        Creates network partitions between services.
        AutoSRE should detect network issues and affected service communication.
        """
        scenario_script = f"{CHAOS_DIR}/scenario-5.sh"
        assert harness.run_chaos_scenario(scenario_script, METRICS_WAIT_SECONDS), \
            "Failed to inject network partition chaos"
        
        result = harness.run_investigation(
            "Service connectivity issues in bookstore namespace"
        )
        
        expected = ExpectedResult(
            root_cause_keywords=["network", "partition", "connect", "timeout", "unreachable"],
            evidence_types=["metrics", "events"],
            min_confidence=0.5,
            expected_recommendations=["network", "connectivity"]
        )
        
        verification = harness.verify_detection(result, expected)
        
        assert result.success, f"Investigation failed: {result.error}"
        assert verification.root_cause_match, \
            f"Network partition not detected. Got: {result.root_cause}"
    
    def test_scenario_6_cascading_failure(
        self,
        harness: AutoSRETestHarness,
        cluster_ready: bool,
        prometheus_ready: bool
    ):
        """
        Scenario 6: Cascading Failure
        
        Causes a failure that cascades across multiple services.
        AutoSRE should identify the root cause and affected services.
        """
        scenario_script = f"{CHAOS_DIR}/scenario-6.sh"
        assert harness.run_chaos_scenario(scenario_script, METRICS_WAIT_SECONDS), \
            "Failed to inject cascading failure chaos"
        
        result = harness.run_investigation(
            "Multiple services degraded in bookstore namespace"
        )
        
        expected = ExpectedResult(
            root_cause_keywords=["cascade", "multiple", "depend", "failure", "propagat"],
            evidence_types=["metrics", "logs", "events"],
            min_confidence=0.5,
            expected_recommendations=["circuit", "breaker", "retry", "fallback"]
        )
        
        verification = harness.verify_detection(result, expected)
        
        assert result.success, f"Investigation failed: {result.error}"
        # For cascading failures, check that multiple evidence types are collected
        assert len(result.evidence) >= 2, \
            f"Expected multiple evidence sources for cascading failure, got {len(result.evidence)}"


class TestAutoSREPerformance:
    """Performance tests for AutoSRE investigations."""
    
    def test_investigation_completes_within_timeout(
        self,
        harness: AutoSRETestHarness,
        cluster_ready: bool
    ):
        """Verify investigations complete within acceptable time."""
        result = harness.run_investigation(
            "Performance test - basic investigation"
        )
        
        # Investigation should complete within 60 seconds for basic case
        assert result.duration_seconds < 60, \
            f"Investigation took too long: {result.duration_seconds}s"
    
    def test_rapid_sequential_investigations(
        self,
        harness: AutoSRETestHarness,
        cluster_ready: bool
    ):
        """Test running multiple investigations in sequence."""
        alerts = [
            "Test alert 1",
            "Test alert 2",
            "Test alert 3"
        ]
        
        results = []
        for alert in alerts:
            result = harness.run_investigation(alert)
            results.append(result)
        
        # All should complete (success or fail gracefully)
        for i, result in enumerate(results):
            assert result.error is None or "not found" not in result.error.lower(), \
                f"Investigation {i+1} had unexpected error: {result.error}"


class TestAutoSREEdgeCases:
    """Edge case tests for AutoSRE."""
    
    def test_empty_alert_description(self, harness: AutoSRETestHarness):
        """Test handling of empty alert description."""
        result = harness.run_investigation("")
        # Should handle gracefully - either work or return meaningful error
        assert result.error is None or "alert" in result.error.lower()
    
    def test_very_long_alert_description(self, harness: AutoSRETestHarness):
        """Test handling of very long alert description."""
        long_alert = "Alert: " + "x" * 10000
        result = harness.run_investigation(long_alert)
        # Should handle gracefully
        assert result.duration_seconds < 120  # Shouldn't hang


# Pytest configuration
def pytest_configure(config):
    """Add custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
