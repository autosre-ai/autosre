"""
Pytest Configuration and Shared Fixtures for OpenSRE Tests
"""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any
import tempfile
import os


# ============================================================================
# Event Loop Configuration
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Mock Adapters
# ============================================================================

@pytest.fixture
def mock_prometheus():
    """Mock Prometheus adapter for testing without actual Prometheus."""
    mock = AsyncMock()
    mock.health_check.return_value = {"status": "healthy", "details": "Mock Prometheus"}
    mock.query.return_value = []
    mock.query_range.return_value = []
    mock.get_alerts.return_value = []
    mock.get_service_metrics.return_value = {
        "cpu_usage": 0.25,
        "memory_usage": 256 * 1024 * 1024,
        "request_rate": 100.0,
        "error_rate": 0.01,
        "latency_p99": 0.150,
    }
    mock.find_anomalies.return_value = []
    return mock


@pytest.fixture
def mock_kubernetes():
    """Mock Kubernetes adapter for testing without actual cluster."""
    mock = AsyncMock()
    mock.health_check.return_value = {"status": "healthy", "details": "K8s v1.28.0"}
    mock.get_pods.return_value = []
    mock.get_pod.return_value = None
    mock.get_events.return_value = []
    mock.get_pod_logs.return_value = ""
    mock.get_deployment.return_value = None
    mock.get_service_pods.return_value = []
    mock.describe_resource.return_value = {}
    return mock


@pytest.fixture
def mock_llm():
    """Mock LLM adapter for testing without actual LLM calls."""
    mock = AsyncMock()
    mock.health_check.return_value = {"status": "healthy", "details": "Mock LLM"}
    mock.generate.return_value = MagicMock(
        content="Root Cause: Test issue detected\nConfidence: 80%\n\nHypotheses:\n1. Resource exhaustion (80%)\n2. Configuration error (20%)",
        model="mock-model",
        tokens_used=100,
        finish_reason="stop",
    )
    return mock


# ============================================================================
# Sample Data Fixtures
# ============================================================================

@pytest.fixture
def sample_pod_info():
    """Sample PodInfo for testing."""
    from opensre_core.adapters.kubernetes import PodInfo
    return PodInfo(
        name="api-server-abc123",
        namespace="default",
        status="Running",
        ready=True,
        restarts=2,
        age="5h",
        containers=[
            {"name": "api", "ready": True, "restarts": 2, "state": "Running"}
        ],
        node="node-1",
        memory_limit=512 * 1024 * 1024,  # 512MB
        memory_request=256 * 1024 * 1024,  # 256MB
        cpu_limit=0.5,  # 500m
        cpu_request=0.25,  # 250m
    )


@pytest.fixture
def sample_unhealthy_pod():
    """Sample unhealthy PodInfo for testing."""
    from opensre_core.adapters.kubernetes import PodInfo
    return PodInfo(
        name="api-server-def456",
        namespace="default",
        status="CrashLoopBackOff",
        ready=False,
        restarts=15,
        age="2h",
        containers=[
            {"name": "api", "ready": False, "restarts": 15, "state": "Waiting: CrashLoopBackOff"}
        ],
        node="node-1",
        memory_limit=512 * 1024 * 1024,
        memory_request=256 * 1024 * 1024,
        cpu_limit=0.5,
        cpu_request=0.25,
    )


@pytest.fixture
def sample_event_info():
    """Sample Kubernetes event for testing."""
    from opensre_core.adapters.kubernetes import EventInfo
    return EventInfo(
        type="Warning",
        reason="OOMKilled",
        message="Container api was OOM killed",
        count=3,
        first_seen=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
        involved_object="Pod/api-server-abc123",
    )


@pytest.fixture
def sample_metric_result():
    """Sample Prometheus MetricResult for testing."""
    from opensre_core.adapters.prometheus import MetricResult
    return MetricResult(
        metric_name="container_memory_usage_bytes",
        labels={"pod": "api-server-abc123", "namespace": "default"},
        values=[],
        current_value=256 * 1024 * 1024,  # 256MB
    )


@pytest.fixture
def sample_alert_result():
    """Sample Prometheus AlertResult for testing."""
    from opensre_core.adapters.prometheus import AlertResult
    return AlertResult(
        alert_name="HighMemoryUsage",
        state="firing",
        labels={"namespace": "default", "pod": "api-server-abc123", "severity": "warning"},
        annotations={"summary": "Memory usage is high", "description": "Pod using 90% memory"},
        started_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_observations():
    """Sample ObservationResult with observations."""
    from opensre_core.agents.observe import Observation, ObservationResult
    return ObservationResult(
        issue="High memory usage on api-server",
        namespace="default",
        observations=[
            Observation(
                source="prometheus",
                type="metric",
                summary="Memory: 450MB / 512MB (88%)",
                details={"pod": "api-server-abc123", "value": 471859200},
                severity="warning",
            ),
            Observation(
                source="kubernetes",
                type="pod_summary",
                summary="Pods: 2/3 healthy, 5 total restarts",
                details={"total": 3, "healthy": 2, "restarts": 5},
                severity="warning",
            ),
            Observation(
                source="kubernetes",
                type="event",
                summary="OOMKilled: Container was killed due to memory limit",
                details={"object": "Pod/api-server-def456", "count": 2},
                severity="warning",
            ),
        ],
        services_involved=["api-server"],
    )


@pytest.fixture
def sample_analysis_result():
    """Sample AnalysisResult for testing."""
    from opensre_core.agents.reason import AnalysisResult, Hypothesis
    return AnalysisResult(
        root_cause="Memory leak in api-server causing OOM kills",
        confidence=0.85,
        hypotheses=[
            Hypothesis(
                description="Memory leak in api-server",
                confidence=0.85,
                evidence=["OOMKilled events", "High memory usage trend"],
                category="resource",
            ),
            Hypothesis(
                description="Memory limit too low",
                confidence=0.15,
                evidence=["Usage near limit"],
                category="config",
            ),
        ],
        similar_incidents=["INC-2024-001: Similar OOM issue"],
        reasoning="Based on multiple OOMKilled events and memory trending upward...",
    )


@pytest.fixture
def sample_action_plan():
    """Sample ActionPlan for testing."""
    from opensre_core.agents.act import Action, ActionPlan, ActionRisk, ActionStatus
    return ActionPlan(
        actions=[
            Action(
                id="action_1",
                description="Get current pod status",
                command="kubectl get pods -n default -l app=api-server",
                risk=ActionRisk.LOW,
                requires_approval=False,
                rationale="Diagnostic check",
                status=ActionStatus.PENDING,
            ),
            Action(
                id="action_2",
                description="Increase memory limit to 1Gi",
                command="kubectl set resources deployment/api-server -c api --limits=memory=1Gi -n default",
                risk=ActionRisk.HIGH,
                requires_approval=True,
                rationale="Address memory pressure",
                status=ActionStatus.PENDING,
            ),
            Action(
                id="action_3",
                description="Restart deployment to apply changes",
                command="kubectl rollout restart deployment/api-server -n default",
                risk=ActionRisk.MEDIUM,
                requires_approval=True,
                rationale="Apply new resource limits",
                status=ActionStatus.PENDING,
            ),
        ],
        summary="Increase memory limits and restart deployment",
        estimated_impact="Brief service interruption during restart",
    )


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    with patch("opensre_core.config.settings") as mock:
        mock.prometheus_url = "http://localhost:9090"
        mock.llm_provider = "ollama"
        mock.ollama_host = "http://localhost:11434"
        mock.ollama_model = "llama3.1:8b"
        mock.require_approval = True
        mock.auto_approve_low_risk = False
        mock.confidence_threshold = 0.7
        mock.max_iterations = 10
        mock.timeout_seconds = 300
        mock.kubeconfig_path = None
        mock.namespaces = ["default"]
        yield mock


@pytest.fixture
def temp_audit_dir():
    """Temporary directory for audit logs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_audit_logger(temp_audit_dir):
    """Mock audit logger that writes to temp directory."""
    from opensre_core.security.audit import AuditLogger
    return AuditLogger(log_dir=temp_audit_dir)


# ============================================================================
# Agent Fixtures
# ============================================================================

@pytest.fixture
def observer_agent(mock_prometheus, mock_kubernetes):
    """ObserverAgent with mocked adapters."""
    from opensre_core.agents.observe import ObserverAgent
    agent = ObserverAgent()
    agent.prometheus = mock_prometheus
    agent.kubernetes = mock_kubernetes
    return agent


@pytest.fixture
def reasoner_agent(mock_llm):
    """ReasonerAgent with mocked LLM."""
    from opensre_core.agents.reason import ReasonerAgent
    agent = ReasonerAgent()
    agent.llm = mock_llm
    return agent


@pytest.fixture
def actor_agent(mock_kubernetes, mock_audit_logger):
    """ActorAgent with mocked adapters."""
    from opensre_core.agents.act import ActorAgent
    agent = ActorAgent(user="test-user")
    agent.kubernetes = mock_kubernetes
    agent.audit = mock_audit_logger
    return agent


# ============================================================================
# Helper Functions
# ============================================================================

def create_mock_metric_results(data: list[dict[str, Any]]):
    """Helper to create multiple MetricResult objects."""
    from opensre_core.adapters.prometheus import MetricResult
    return [
        MetricResult(
            metric_name=d.get("name", "test_metric"),
            labels=d.get("labels", {}),
            values=d.get("values", []),
            current_value=d.get("value"),
        )
        for d in data
    ]


def create_mock_pods(data: list[dict[str, Any]]):
    """Helper to create multiple PodInfo objects."""
    from opensre_core.adapters.kubernetes import PodInfo
    return [
        PodInfo(
            name=d.get("name", "test-pod"),
            namespace=d.get("namespace", "default"),
            status=d.get("status", "Running"),
            ready=d.get("ready", True),
            restarts=d.get("restarts", 0),
            age=d.get("age", "1h"),
            containers=d.get("containers", []),
            node=d.get("node"),
            memory_limit=d.get("memory_limit"),
            memory_request=d.get("memory_request"),
            cpu_limit=d.get("cpu_limit"),
            cpu_request=d.get("cpu_request"),
        )
        for d in data
    ]
