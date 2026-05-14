"""Shared pytest fixtures for AutoSRE V2 tests.

This module provides fixtures used across all test types:
- Unit tests
- Integration tests
- End-to-end tests
"""

import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ============================================================================
# Configuration Fixtures
# ============================================================================


@pytest.fixture
def test_config() -> dict[str, Any]:
    """Return test configuration."""
    return {
        "version": "2.0",
        "llm": {
            "provider": "openai",
            "model": "gpt-4o",
            "temperature": 0.1,
            "max_tokens": 4096,
        },
        "alerts": {
            "sources": [
                {"type": "prometheus", "url": "http://localhost:9090"},
            ],
        },
        "investigation": {
            "auto_start": False,
            "max_parallel": 3,
            "timeout_minutes": 30,
            "max_iterations": 3,
        },
        "server": {
            "host": "0.0.0.0",
            "port": 8080,
        },
    }


@pytest.fixture
def temp_config_file(tmp_path: Path, test_config: dict[str, Any]) -> Path:
    """Create a temporary config file."""
    import yaml
    
    config_path = tmp_path / ".autosre.yaml"
    with open(config_path, "w") as f:
        yaml.dump(test_config, f)
    return config_path


# ============================================================================
# Alert Fixtures
# ============================================================================


@pytest.fixture
def sample_alert() -> dict[str, Any]:
    """Return a sample alert for testing."""
    return {
        "name": "HighErrorRate",
        "alert_id": "test-alert-001",
        "service": "payment-service",
        "namespace": "production",
        "severity": "critical",
        "status": "firing",
        "description": "Error rate above 5% for 10 minutes",
        "started_at": datetime.utcnow().isoformat(),
        "labels": {
            "alertname": "HighErrorRate",
            "service": "payment-service",
            "severity": "critical",
            "namespace": "production",
        },
        "annotations": {
            "summary": "High error rate in payment service",
            "description": "Error rate is above 5%",
            "runbook_url": "https://runbooks.example.com/high-error-rate",
        },
    }


@pytest.fixture
def prometheus_alert_payload() -> dict[str, Any]:
    """Return a Prometheus/Alertmanager webhook payload."""
    return {
        "status": "firing",
        "labels": {
            "alertname": "HighCPUUsage",
            "service": "api-gateway",
            "severity": "warning",
            "namespace": "production",
            "pod": "api-gateway-abc123",
        },
        "annotations": {
            "summary": "High CPU usage detected",
            "description": "CPU usage is above 80% for 5 minutes",
        },
        "startsAt": "2024-01-15T10:00:00Z",
        "fingerprint": "abc123def456",
    }


@pytest.fixture
def pagerduty_incident_payload() -> dict[str, Any]:
    """Return a PagerDuty incident payload."""
    return {
        "incident": {
            "id": "P12345",
            "title": "High Latency Alert",
            "status": "triggered",
            "urgency": "high",
            "created_at": "2024-01-15T10:00:00Z",
            "service": {
                "name": "checkout-service",
                "summary": "Checkout Service",
            },
            "description": "P99 latency above 1 second",
            "html_url": "https://pagerduty.com/incidents/P12345",
        },
    }


# ============================================================================
# Investigation Fixtures
# ============================================================================


@pytest.fixture
def sample_investigation_state(sample_alert: dict[str, Any]) -> dict[str, Any]:
    """Return a sample investigation state."""
    return {
        "alert": sample_alert,
        "thread_id": "test-thread-001",
        "images": [],
        "memory_context": {},
        "kg_context": {},
        "team_config": {
            "agents": {
                "investigation": {
                    "sub_agents": {
                        "kubernetes": True,
                        "metrics": True,
                        "log_analysis": True,
                        "github": False,
                    },
                },
            },
        },
        "iteration": 0,
        "max_iterations": 3,
        "messages": [],
        "hypotheses": [],
        "selected_agents": [],
        "agent_states": {},
    }


@pytest.fixture
def sample_hypotheses() -> list[dict[str, Any]]:
    """Return sample investigation hypotheses."""
    return [
        {
            "hypothesis": "Memory leak causing OOM kills",
            "priority": "high",
            "agents_to_test": ["kubernetes", "metrics"],
            "confidence": 0.7,
        },
        {
            "hypothesis": "Database connection exhaustion",
            "priority": "medium",
            "agents_to_test": ["metrics", "log_analysis"],
            "confidence": 0.5,
        },
    ]


@pytest.fixture
def sample_findings() -> list[dict[str, Any]]:
    """Return sample investigation findings."""
    return [
        {
            "category": "kubernetes",
            "detail": "Pod payment-service-abc123 restarted 5 times in last hour",
            "evidence": "kubectl describe pod payment-service-abc123",
            "severity": "high",
            "confidence": 0.85,
        },
        {
            "category": "metrics",
            "detail": "Memory usage spike to 95% before each restart",
            "evidence": "container_memory_working_set_bytes",
            "severity": "high",
            "confidence": 0.9,
        },
        {
            "category": "log_analysis",
            "detail": "OutOfMemoryError found in logs",
            "evidence": "java.lang.OutOfMemoryError: Java heap space",
            "severity": "critical",
            "confidence": 0.95,
        },
    ]


# ============================================================================
# Mock Fixtures
# ============================================================================


@pytest.fixture
def mock_llm() -> MagicMock:
    """Create a mock LLM that returns configurable responses."""
    mock = MagicMock()
    
    # Default response
    default_response = MagicMock()
    default_response.content = json.dumps({
        "hypotheses": [
            {
                "hypothesis": "Test hypothesis",
                "priority": "high",
                "agents_to_test": ["kubernetes"],
            }
        ],
        "selected_agents": ["kubernetes"],
        "reasoning": "Test reasoning",
    })
    
    mock.invoke.return_value = default_response
    return mock


@pytest.fixture
def mock_llm_planner_response() -> dict[str, Any]:
    """Return mock planner response."""
    return {
        "hypotheses": [
            {
                "hypothesis": "Memory leak in payment pods",
                "priority": "high",
                "agents_to_test": ["kubernetes", "metrics"],
            },
        ],
        "selected_agents": ["kubernetes", "metrics"],
        "reasoning": "Error rate spike suggests resource issue",
    }


@pytest.fixture
def mock_llm_synthesizer_response() -> dict[str, Any]:
    """Return mock synthesizer response."""
    return {
        "sufficient_evidence": True,
        "confidence": 0.85,
        "summary": "Root cause identified: OOMKilled pods",
        "gaps": [],
        "feedback": "",
        "recommended_agents": [],
    }


@pytest.fixture
def mock_k8s_client() -> MagicMock:
    """Create a mock Kubernetes client."""
    mock = MagicMock()
    
    # Mock pod list
    mock_pod = MagicMock()
    mock_pod.metadata.name = "payment-service-abc123"
    mock_pod.metadata.namespace = "production"
    mock_pod.status.phase = "Running"
    mock_pod.status.conditions = []
    mock_pod.status.container_statuses = []
    mock_pod.spec.node_name = "node-1"
    mock_pod.metadata.labels = {"app": "payment-service"}
    mock_pod.metadata.annotations = {}
    
    mock.list_namespaced_pod.return_value.items = [mock_pod]
    mock.read_namespaced_pod_log.return_value = "Sample log output"
    
    return mock


@pytest.fixture
def mock_prometheus_response() -> dict[str, Any]:
    """Return mock Prometheus query response."""
    return {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [
                {
                    "metric": {"service": "payment-service"},
                    "value": [1705312800, "0.05"],
                },
            ],
        },
    }


# ============================================================================
# HTTP Client Fixtures
# ============================================================================


@pytest.fixture
async def async_client() -> AsyncClient:
    """Create an async HTTP client for testing."""
    async with AsyncClient() as client:
        yield client


@pytest.fixture
def app():
    """Create FastAPI test application."""
    from autosre.api.app import create_app
    return create_app(debug=True)


@pytest.fixture
async def api_client(app):
    """Create test client for API tests."""
    from httpx import ASGITransport, AsyncClient
    
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        yield client


# ============================================================================
# Environment Fixtures
# ============================================================================


@pytest.fixture
def clean_env(monkeypatch) -> Generator[None, None, None]:
    """Clear environment variables that might affect tests."""
    vars_to_clear = [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "PROMETHEUS_URL",
        "AUTOSRE_CONFIG_PATH",
    ]
    
    for var in vars_to_clear:
        monkeypatch.delenv(var, raising=False)
    
    yield


@pytest.fixture
def mock_env(monkeypatch) -> dict[str, str]:
    """Set up mock environment variables."""
    env_vars = {
        "OPENAI_API_KEY": "sk-test-key",
        "PROMETHEUS_URL": "http://prometheus:9090",
        "AUTOSRE_DEBUG": "true",
    }
    
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    
    return env_vars


# ============================================================================
# Async Event Loop
# ============================================================================


@pytest.fixture(scope="session")
def event_loop_policy():
    """Set event loop policy for tests."""
    return asyncio.DefaultEventLoopPolicy()


# ============================================================================
# Factory Fixtures
# ============================================================================


@pytest.fixture
def alert_factory():
    """Factory for creating test alerts."""
    from autosre.models.alert import Alert, AlertSeverity, AlertStatus
    
    def _create_alert(
        name: str = "TestAlert",
        service: str = "test-service",
        severity: AlertSeverity = AlertSeverity.WARNING,
        status: AlertStatus = AlertStatus.FIRING,
        **kwargs,
    ) -> Alert:
        return Alert(
            name=name,
            service=service,
            severity=severity,
            status=status,
            **kwargs,
        )
    
    return _create_alert


@pytest.fixture
def finding_factory():
    """Factory for creating test findings."""
    from autosre.models.investigation import Finding
    
    def _create_finding(
        category: str = "test",
        detail: str = "Test finding",
        severity: str = "info",
        confidence: float = 0.5,
        **kwargs,
    ) -> Finding:
        return Finding(
            category=category,
            detail=detail,
            severity=severity,
            confidence=confidence,
            **kwargs,
        )
    
    return _create_finding


@pytest.fixture
def hypothesis_factory():
    """Factory for creating test hypotheses."""
    from autosre.models.investigation import Hypothesis
    
    def _create_hypothesis(
        hypothesis: str = "Test hypothesis",
        priority: str = "medium",
        agents_to_test: list[str] = None,
        confidence: float = 0.5,
    ) -> Hypothesis:
        return Hypothesis(
            hypothesis=hypothesis,
            priority=priority,
            agents_to_test=agents_to_test or ["kubernetes"],
            confidence=confidence,
        )
    
    return _create_hypothesis


# ============================================================================
# Mock LLM Client Fixtures
# ============================================================================


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client for testing agents."""
    mock = MagicMock()
    
    # Mock async methods
    mock.complete_with_retry = AsyncMock()
    mock.complete_structured = AsyncMock()
    mock.generate = AsyncMock()
    
    # Default response for complete_with_retry
    default_response = MagicMock()
    default_response.content = "Test response content"
    default_response.tool_calls = []
    default_response.has_tool_calls = False
    mock.complete_with_retry.return_value = default_response
    
    return mock


@pytest.fixture
def mock_llm_with_tools():
    """Create a mock LLM that simulates tool calls."""
    mock = MagicMock()
    mock.complete_with_retry = AsyncMock()
    
    # First response - tool call
    tool_response = MagicMock()
    tool_response.content = ""
    tool_response.has_tool_calls = True
    tool_response.tool_calls = [
        MagicMock(
            id="call_1",
            name="get_pod_status",
            arguments={"service": "test-service", "namespace": "default"},
        )
    ]
    
    # Second response - final answer
    final_response = MagicMock()
    final_response.content = "Investigation complete. Found memory issue."
    final_response.has_tool_calls = False
    final_response.tool_calls = []
    
    mock.complete_with_retry.side_effect = [tool_response, final_response]
    
    return mock


# ============================================================================
# Mock Integrations Fixtures
# ============================================================================


@pytest.fixture
def mock_prometheus_client():
    """Create a mock Prometheus client."""
    mock = MagicMock()
    
    mock.query = AsyncMock(return_value=[
        MagicMock(
            name="test_metric",
            value=0.5,
            labels={"pod": "test-pod"},
        )
    ])
    mock.query_range = AsyncMock()
    mock.get_error_rate = AsyncMock(return_value=0.05)
    mock.get_latency_percentile = AsyncMock(return_value=0.250)
    mock.get_resource_usage = AsyncMock(return_value={
        "cpu": {"test-pod": 0.5},
        "memory": {"test-pod": 1024 * 1024 * 512},
    })
    mock.check_connection = AsyncMock(return_value=True)
    mock.health_check = AsyncMock()
    
    return mock


@pytest.fixture
def mock_kubernetes_client():
    """Create a mock Kubernetes client."""
    from autosre.integrations.kubernetes import Pod, PodPhase, ContainerStatus, ContainerState
    
    mock = MagicMock()
    
    # Mock pods
    mock_pod = Pod(
        name="test-pod-abc123",
        namespace="default",
        phase=PodPhase.RUNNING,
        node_name="node-1",
        pod_ip="10.0.0.1",
        host_ip="192.168.1.1",
        start_time=datetime.now(timezone.utc),
        labels={"app": "test-service"},
        conditions=[{"type": "Ready", "status": "True"}],
        containers=[
            ContainerStatus(
                name="main",
                state=ContainerState.RUNNING,
                ready=True,
                restart_count=0,
                image="test:latest",
            )
        ],
    )
    
    mock.list_pods = AsyncMock(return_value=[mock_pod])
    mock.get_pod = AsyncMock(return_value=mock_pod)
    mock.get_pod_logs = AsyncMock(return_value="Sample log line\nAnother log line")
    mock.get_pod_events = AsyncMock(return_value=[])
    mock.get_deployment = AsyncMock()
    mock.get_events = AsyncMock(return_value=[])
    mock.health_check = AsyncMock()
    
    return mock


@pytest.fixture
def mock_loki_client():
    """Create a mock Loki client."""
    mock = MagicMock()
    
    mock.query = AsyncMock()
    mock.search_errors = AsyncMock()
    mock.query_service = AsyncMock()
    mock.health_check = AsyncMock()
    
    # Configure query result
    query_result = MagicMock()
    query_result.is_empty = False
    query_result.all_entries = MagicMock(return_value=[
        MagicMock(timestamp=datetime.now(timezone.utc), line="Error: Connection refused"),
    ])
    query_result.get_unique_error_messages = MagicMock(return_value=[
        "Error: Connection refused",
    ])
    mock.query.return_value = query_result
    mock.search_errors.return_value = query_result
    
    return mock


# ============================================================================
# Database Fixtures
# ============================================================================


@pytest.fixture
def temp_db_path(tmp_path):
    """Create temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create temporary config directory with files."""
    import yaml
    
    config = {
        "version": "2.0",
        "llm": {
            "provider": "openai",
            "model": "gpt-4o",
        },
        "alerts": {
            "sources": [
                {"type": "prometheus", "url": "http://localhost:9090"},
            ],
        },
    }
    
    config_path = tmp_path / ".autosre.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    
    # Create runbooks dir
    runbooks_dir = tmp_path / "runbooks"
    runbooks_dir.mkdir()
    
    return tmp_path


# ============================================================================
# Investigation State Fixtures
# ============================================================================


@pytest.fixture
def investigation_factory(alert_factory):
    """Factory for creating test investigations."""
    from autosre.models.investigation import Investigation
    
    def _create_investigation(
        alert=None,
        status=None,
        **kwargs,
    ):
        if alert is None:
            alert = alert_factory()
        
        return Investigation(
            alert=alert,
            status=status,
            **kwargs,
        )
    
    return _create_investigation


@pytest.fixture
def agent_result_factory():
    """Factory for creating agent results."""
    from autosre.agents.base_agent import AgentResult, AgentStatus
    
    def _create_result(
        agent_id: str = "test",
        status: AgentStatus = AgentStatus.COMPLETED,
        summary: str = "Test summary",
        confidence: float = 0.8,
        **kwargs,
    ) -> AgentResult:
        return AgentResult(
            agent_id=agent_id,
            status=status,
            summary=summary,
            confidence=confidence,
            **kwargs,
        )
    
    return _create_result


# ============================================================================
# CLI Test Fixtures
# ============================================================================


@pytest.fixture
def cli_runner():
    """Create CLI test runner."""
    from typer.testing import CliRunner
    return CliRunner()


@pytest.fixture
def cli_env(tmp_path, monkeypatch):
    """Set up CLI test environment."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AUTOSRE_CONFIG_PATH", str(tmp_path / ".autosre.yaml"))
    return tmp_path


# ============================================================================
# Fixture Data Loaders
# ============================================================================


@pytest.fixture
def load_fixture():
    """Load fixture data from JSON file."""
    fixtures_dir = Path(__file__).parent / "fixtures"
    
    def _load(filename: str) -> Any:
        path = fixtures_dir / filename
        with open(path) as f:
            return json.load(f)
    
    return _load


@pytest.fixture
def alerts_fixture(load_fixture):
    """Load alerts fixture data."""
    return load_fixture("alerts.json")


@pytest.fixture
def prometheus_fixture(load_fixture):
    """Load Prometheus fixture data."""
    return load_fixture("prometheus_responses.json")


@pytest.fixture
def k8s_fixture(load_fixture):
    """Load Kubernetes fixture data."""
    return load_fixture("k8s_resources.json")
