"""
Tests for Prometheus metrics exporter.
"""

import pytest
from prometheus_client import REGISTRY

from autosre.metrics import (
    # Metrics
    INVESTIGATIONS_TOTAL,
    INVESTIGATION_DURATION,
    INVESTIGATION_CONFIDENCE,
    ACTIVE_INVESTIGATIONS,
    ACTIONS_TOTAL,
    LLM_REQUESTS,
    ADAPTER_HEALTH,
    # Helper functions
    get_metrics,
    get_content_type,
    record_investigation_start,
    record_investigation_end,
    record_action_suggested,
    record_action_approved,
    record_action_rejected,
    record_action_executed,
    record_llm_request,
    record_llm_error,
    record_adapter_health,
    record_adapter_error,
    record_observation,
    record_observation_duration,
    record_api_request,
    set_version_info,
)


class TestMetricsExport:
    """Tests for metrics export functions."""
    
    def test_get_metrics_returns_bytes(self):
        """Test that get_metrics returns bytes."""
        result = get_metrics()
        assert isinstance(result, bytes)
    
    def test_get_metrics_contains_metric_names(self):
        """Test that exported metrics contain expected names."""
        result = get_metrics().decode('utf-8')
        # Should contain at least some metric definitions
        assert 'opensre_' in result or 'python_' in result or 'process_' in result
    
    def test_get_content_type(self):
        """Test content type for Prometheus."""
        content_type = get_content_type()
        assert 'text/plain' in content_type or 'text/openmetrics' in content_type


class TestInvestigationMetrics:
    """Tests for investigation metrics."""
    
    def test_record_investigation_start(self):
        """Test recording investigation start."""
        initial = ACTIVE_INVESTIGATIONS._value.get()
        
        record_investigation_start()
        
        assert ACTIVE_INVESTIGATIONS._value.get() == initial + 1
        
        # Clean up
        ACTIVE_INVESTIGATIONS.dec()
    
    def test_record_investigation_end(self):
        """Test recording investigation completion."""
        # Start first to avoid negative gauge
        record_investigation_start()
        
        record_investigation_end(
            namespace="production",
            status="completed",
            duration=30.5,
            confidence=0.85,
            iterations=3,
        )
        
        # Check that metrics were recorded
        # We can verify by checking the metric output
        metrics_output = get_metrics().decode('utf-8')
        assert 'opensre_investigations_total' in metrics_output
    
    def test_record_investigation_failed(self):
        """Test recording failed investigation."""
        record_investigation_start()
        
        record_investigation_end(
            namespace="staging",
            status="failed",
            duration=120.0,
            confidence=0.3,
            iterations=5,
        )
        
        metrics_output = get_metrics().decode('utf-8')
        assert 'opensre_investigations_total' in metrics_output


class TestActionMetrics:
    """Tests for action metrics."""
    
    def test_record_action_suggested(self):
        """Test recording suggested action."""
        record_action_suggested(risk="low")
        
        metrics_output = get_metrics().decode('utf-8')
        assert 'opensre_actions_total' in metrics_output
    
    def test_record_action_approved(self):
        """Test recording approved action."""
        record_action_approved(risk="medium")
        
        metrics_output = get_metrics().decode('utf-8')
        assert 'opensre_actions_approved_total' in metrics_output
    
    def test_record_action_rejected(self):
        """Test recording rejected action."""
        record_action_rejected(risk="high")
        
        metrics_output = get_metrics().decode('utf-8')
        assert 'opensre_actions_rejected_total' in metrics_output
    
    def test_record_action_executed_success(self):
        """Test recording successful action execution."""
        record_action_executed(risk="low", success=True, duration=2.5)
        
        metrics_output = get_metrics().decode('utf-8')
        assert 'opensre_actions_executed_total' in metrics_output
    
    def test_record_action_executed_failure(self):
        """Test recording failed action execution."""
        record_action_executed(risk="medium", success=False, duration=10.0)
        
        metrics_output = get_metrics().decode('utf-8')
        assert 'opensre_action_execution_duration_seconds' in metrics_output


class TestLLMMetrics:
    """Tests for LLM metrics."""
    
    def test_record_llm_request_success(self):
        """Test recording successful LLM request."""
        record_llm_request(
            provider="ollama",
            model="llama3",
            success=True,
            latency=5.2,
            input_tokens=500,
            output_tokens=200,
        )
        
        metrics_output = get_metrics().decode('utf-8')
        assert 'opensre_llm_requests_total' in metrics_output
        assert 'opensre_llm_latency_seconds' in metrics_output
        assert 'opensre_llm_tokens_total' in metrics_output
    
    def test_record_llm_request_failure(self):
        """Test recording failed LLM request."""
        record_llm_request(
            provider="openai",
            model="gpt-4",
            success=False,
            latency=1.0,
        )
        
        metrics_output = get_metrics().decode('utf-8')
        assert 'opensre_llm_requests_total' in metrics_output
    
    def test_record_llm_request_with_total_tokens(self):
        """Test recording LLM request with total tokens only."""
        record_llm_request(
            provider="anthropic",
            model="claude-3",
            success=True,
            latency=3.5,
            tokens=1000,
        )
        
        metrics_output = get_metrics().decode('utf-8')
        assert 'opensre_llm_tokens_total' in metrics_output
    
    def test_record_llm_error(self):
        """Test recording LLM error."""
        record_llm_error(
            provider="openai",
            model="gpt-4",
            error_type="rate_limit",
        )
        
        metrics_output = get_metrics().decode('utf-8')
        assert 'opensre_llm_errors_total' in metrics_output


class TestAdapterMetrics:
    """Tests for adapter health metrics."""
    
    def test_record_adapter_health_healthy(self):
        """Test recording healthy adapter."""
        record_adapter_health(adapter="prometheus", healthy=True, latency=0.1)
        
        metrics_output = get_metrics().decode('utf-8')
        assert 'opensre_adapter_health' in metrics_output
        assert 'opensre_adapter_latency_seconds' in metrics_output
    
    def test_record_adapter_health_unhealthy(self):
        """Test recording unhealthy adapter."""
        record_adapter_health(adapter="kubernetes", healthy=False, latency=5.0)
        
        metrics_output = get_metrics().decode('utf-8')
        assert 'opensre_adapter_health' in metrics_output
    
    def test_record_adapter_error(self):
        """Test recording adapter error."""
        record_adapter_error(adapter="slack", error_type="connection_timeout")
        
        metrics_output = get_metrics().decode('utf-8')
        assert 'opensre_adapter_errors_total' in metrics_output


class TestObservationMetrics:
    """Tests for observation metrics."""
    
    def test_record_observation(self):
        """Test recording observations."""
        record_observation(source="prometheus", observation_type="metric", count=10)
        
        metrics_output = get_metrics().decode('utf-8')
        assert 'opensre_observations_collected_total' in metrics_output
    
    def test_record_observation_duration(self):
        """Test recording observation collection duration."""
        record_observation_duration(source="kubernetes", duration=2.5)
        
        metrics_output = get_metrics().decode('utf-8')
        assert 'opensre_observation_duration_seconds' in metrics_output


class TestAPIMetrics:
    """Tests for API metrics."""
    
    def test_record_api_request(self):
        """Test recording API request."""
        record_api_request(
            method="POST",
            endpoint="/investigate",
            status_code=200,
            latency=0.5,
        )
        
        metrics_output = get_metrics().decode('utf-8')
        assert 'opensre_api_requests_total' in metrics_output
        assert 'opensre_api_latency_seconds' in metrics_output
    
    def test_record_api_request_error(self):
        """Test recording API error response."""
        record_api_request(
            method="GET",
            endpoint="/status",
            status_code=500,
            latency=0.1,
        )
        
        metrics_output = get_metrics().decode('utf-8')
        assert 'opensre_api_requests_total' in metrics_output


class TestSystemMetrics:
    """Tests for system info metrics."""
    
    def test_set_version_info(self):
        """Test setting version info."""
        set_version_info(version="0.1.0", llm_provider="ollama")
        
        metrics_output = get_metrics().decode('utf-8')
        assert 'opensre_info' in metrics_output
