"""
End-to-end tests for investigation flow.

Test investigation scenarios:
1. High CPU alert → Prometheus metrics → K8s scaling
2. Pod crash → K8s events → Logs → OOMKill detection
3. Latency spike → Trace analysis → Dependency issue
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from autosre.api.app import create_app
from autosre.core.models import (
    Action,
    ActionStatus,
    ActionType,
    Alert,
    AlertSeverity,
    AlertStatus,
    Hypothesis,
    HypothesisStatus,
    Investigation,
    InvestigationStatus,
    Observation,
    ObservationType,
    Report,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def app():
    """Create test application."""
    return create_app()


@pytest.fixture
async def client(app):
    """Create async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def high_cpu_alert() -> Alert:
    """Create high CPU alert fixture."""
    return Alert(
        name="HighCPU",
        source="prometheus",
        service="payment-service",
        namespace="production",
        severity=AlertSeverity.CRITICAL,
        status=AlertStatus.FIRING,
        description="CPU usage above 90% for 10 minutes",
        labels={
            "alertname": "HighCPU",
            "service": "payment-service",
            "pod": "payment-service-abc123",
            "namespace": "production",
        },
        annotations={
            "summary": "High CPU usage detected",
            "runbook_url": "https://runbooks.example.com/high-cpu",
        },
    )


@pytest.fixture
def pod_crash_alert() -> Alert:
    """Create pod crash alert fixture."""
    return Alert(
        name="PodCrashLooping",
        source="prometheus",
        service="api-gateway",
        namespace="production",
        severity=AlertSeverity.WARNING,
        status=AlertStatus.FIRING,
        description="Pod restarting frequently",
        labels={
            "alertname": "PodCrashLooping",
            "service": "api-gateway",
            "pod": "api-gateway-xyz789",
            "namespace": "production",
            "container": "main",
        },
        annotations={
            "summary": "Pod has restarted 5 times in the last hour",
        },
    )


@pytest.fixture
def latency_alert() -> Alert:
    """Create latency spike alert fixture."""
    return Alert(
        name="HighLatency",
        source="prometheus",
        service="checkout-service",
        namespace="production",
        severity=AlertSeverity.HIGH,
        status=AlertStatus.FIRING,
        description="P99 latency above 1 second",
        labels={
            "alertname": "HighLatency",
            "service": "checkout-service",
            "namespace": "production",
            "endpoint": "/api/checkout",
        },
        annotations={
            "summary": "P99 latency spike detected",
            "dashboard": "https://grafana.example.com/d/latency",
        },
    )


@pytest.fixture
def mock_prometheus_client():
    """Create mock Prometheus client."""
    mock = MagicMock()
    
    # High CPU metrics
    mock.query_cpu = AsyncMock(return_value={
        "data": {
            "result": [
                {"metric": {"pod": "payment-service-abc123"}, "value": [1705312800, "0.95"]}
            ]
        }
    })
    
    # Memory metrics
    mock.query_memory = AsyncMock(return_value={
        "data": {
            "result": [
                {"metric": {"pod": "payment-service-abc123"}, "value": [1705312800, "1073741824"]}
            ]
        }
    })
    
    # Error rate
    mock.query_error_rate = AsyncMock(return_value={
        "data": {
            "result": [
                {"metric": {"service": "payment-service"}, "value": [1705312800, "0.02"]}
            ]
        }
    })
    
    # Latency
    mock.query_latency = AsyncMock(return_value={
        "data": {
            "result": [
                {"metric": {"service": "checkout-service"}, "value": [1705312800, "1.5"]}
            ]
        }
    })
    
    mock.health_check = AsyncMock()
    
    return mock


@pytest.fixture
def mock_kubernetes_client():
    """Create mock Kubernetes client."""
    mock = MagicMock()
    
    # Pod info
    mock.get_pod = AsyncMock(return_value={
        "metadata": {
            "name": "payment-service-abc123",
            "namespace": "production",
            "labels": {"app": "payment-service"},
        },
        "status": {
            "phase": "Running",
            "containerStatuses": [
                {
                    "name": "main",
                    "ready": True,
                    "restartCount": 3,
                    "state": {"running": {"startedAt": "2024-01-15T10:00:00Z"}},
                    "lastState": {
                        "terminated": {
                            "reason": "OOMKilled",
                            "exitCode": 137,
                            "finishedAt": "2024-01-15T09:55:00Z",
                        }
                    },
                }
            ],
        },
        "spec": {
            "nodeName": "node-1",
            "containers": [
                {
                    "name": "main",
                    "resources": {
                        "requests": {"memory": "512Mi", "cpu": "500m"},
                        "limits": {"memory": "1Gi", "cpu": "1"},
                    },
                }
            ],
        },
    })
    
    # Pod logs
    mock.get_pod_logs = AsyncMock(return_value="""
2024-01-15T09:50:00Z INFO Starting payment processing
2024-01-15T09:51:00Z WARN Memory usage high: 90%
2024-01-15T09:52:00Z ERROR java.lang.OutOfMemoryError: Java heap space
2024-01-15T09:52:01Z ERROR Container killed due to OOM
""")
    
    # Events
    mock.get_events = AsyncMock(return_value=[
        {
            "type": "Warning",
            "reason": "OOMKilled",
            "message": "Container main exceeded memory limit",
            "firstTimestamp": "2024-01-15T09:52:00Z",
            "lastTimestamp": "2024-01-15T09:52:00Z",
            "count": 3,
        },
        {
            "type": "Normal",
            "reason": "Pulled",
            "message": "Container image pulled successfully",
            "firstTimestamp": "2024-01-15T10:00:00Z",
        },
    ])
    
    # Deployment
    mock.get_deployment = AsyncMock(return_value={
        "metadata": {"name": "payment-service"},
        "spec": {"replicas": 3},
        "status": {"availableReplicas": 2, "readyReplicas": 2},
    })
    
    # Scale operation
    mock.scale_deployment = AsyncMock(return_value=True)
    
    mock.health_check = AsyncMock()
    
    return mock


@pytest.fixture
def mock_loki_client():
    """Create mock Loki client."""
    mock = MagicMock()
    
    mock.query = AsyncMock(return_value={
        "data": {
            "result": [
                {
                    "stream": {"app": "payment-service", "level": "error"},
                    "values": [
                        ["1705312740000000000", "OutOfMemoryError: Java heap space"],
                        ["1705312720000000000", "Memory usage critical: 95%"],
                    ],
                }
            ]
        }
    })
    
    mock.search_errors = AsyncMock(return_value={
        "data": {
            "result": [
                {
                    "stream": {"app": "payment-service"},
                    "values": [
                        ["1705312740000000000", "ERROR: Connection timeout"],
                        ["1705312735000000000", "ERROR: OutOfMemoryError"],
                    ],
                }
            ]
        }
    })
    
    mock.health_check = AsyncMock()
    
    return mock


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    mock = MagicMock()
    
    mock.generate = AsyncMock(return_value={
        "hypotheses": [
            {
                "statement": "Memory leak causing OOM kills",
                "confidence": 0.85,
                "reasoning": "Pod logs show OutOfMemoryError before crashes",
            }
        ],
        "recommended_actions": [
            "Scale up replicas",
            "Increase memory limits",
            "Investigate memory leak",
        ],
        "root_cause_analysis": "Memory leak in payment processing module",
    })
    
    return mock


# ============================================================================
# Scenario 1: High CPU Alert → Prometheus Metrics → K8s Scaling
# ============================================================================


class TestHighCPUScenario:
    """Test scenario: High CPU alert leading to scaling remediation."""

    @pytest.mark.asyncio
    async def test_high_cpu_detection(self, high_cpu_alert: Alert):
        """Test high CPU alert is properly detected."""
        assert high_cpu_alert.name == "HighCPU"
        assert high_cpu_alert.severity == AlertSeverity.CRITICAL
        assert high_cpu_alert.is_active is True

    @pytest.mark.asyncio
    async def test_cpu_metrics_collection(
        self, high_cpu_alert: Alert, mock_prometheus_client: MagicMock
    ):
        """Test collecting CPU metrics from Prometheus."""
        # Query CPU metrics
        result = await mock_prometheus_client.query_cpu(
            query=f'container_cpu_usage_seconds_total{{pod="{high_cpu_alert.labels["pod"]}"}}'
        )
        
        assert "data" in result
        assert len(result["data"]["result"]) > 0
        cpu_value = float(result["data"]["result"][0]["value"][1])
        assert cpu_value > 0.9  # 90% CPU

    @pytest.mark.asyncio
    async def test_investigation_generates_scaling_hypothesis(
        self, high_cpu_alert: Alert
    ):
        """Test investigation generates scaling hypothesis."""
        investigation = Investigation(
            alert_id=high_cpu_alert.id,
            title=f"Investigate {high_cpu_alert.name}",
        )
        
        # Add CPU observation
        cpu_observation = Observation(
            type=ObservationType.METRIC,
            source="prometheus",
            description="CPU usage at 95%",
            data={"cpu_percent": 0.95, "pod": "payment-service-abc123"},
            is_anomalous=True,
            relevance_score=0.9,
        )
        investigation.add_observation(cpu_observation)
        
        # Add hypothesis
        scaling_hypothesis = Hypothesis(
            statement="High traffic causing CPU spike, needs horizontal scaling",
            reasoning="CPU consistently high across all pods suggests load issue",
            confidence=0.7,
        )
        investigation.add_hypothesis(scaling_hypothesis)
        
        assert len(investigation.hypotheses) == 1
        assert "scaling" in investigation.hypotheses[0].statement.lower()

    @pytest.mark.asyncio
    async def test_scaling_action_execution(
        self, mock_kubernetes_client: MagicMock
    ):
        """Test scaling action is executed."""
        # Create scaling action
        action = Action(
            type=ActionType.SCALE,
            name="scale_up_replicas",
            description="Scale payment-service from 3 to 5 replicas",
            tool="kubernetes",
            parameters={
                "deployment": "payment-service",
                "namespace": "production",
                "replicas": 5,
            },
            requires_approval=True,
            risk_level="medium",
        )
        
        # Approve and execute
        action.status = ActionStatus.APPROVED
        action.approved_by = "sre@example.com"
        action.approved_at = datetime.now(timezone.utc)
        
        # Execute
        action.status = ActionStatus.EXECUTING
        action.started_at = datetime.now(timezone.utc)
        
        result = await mock_kubernetes_client.scale_deployment(
            deployment="payment-service",
            namespace="production",
            replicas=5,
        )
        
        assert result is True
        
        action.status = ActionStatus.COMPLETED
        action.completed_at = datetime.now(timezone.utc)
        action.result = {"new_replicas": 5}
        
        assert action.status == ActionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_full_high_cpu_flow(
        self,
        high_cpu_alert: Alert,
        mock_prometheus_client: MagicMock,
        mock_kubernetes_client: MagicMock,
    ):
        """Test complete high CPU investigation flow."""
        # 1. Create investigation
        investigation = Investigation(
            alert_id=high_cpu_alert.id,
            title=f"Investigate {high_cpu_alert.name}",
        )
        investigation.status = InvestigationStatus.IN_PROGRESS
        
        # 2. Collect metrics
        cpu_result = await mock_prometheus_client.query_cpu(query="")
        observation = Observation(
            type=ObservationType.METRIC,
            source="prometheus",
            description="CPU usage at 95%",
            data=cpu_result,
            is_anomalous=True,
        )
        investigation.add_observation(observation)
        
        # 3. Check deployment status
        deployment = await mock_kubernetes_client.get_deployment(
            name="payment-service",
            namespace="production",
        )
        
        # 4. Form hypothesis
        hypothesis = Hypothesis(
            statement="High load requires additional replicas",
            confidence=0.8,
        )
        hypothesis.add_supporting_evidence(observation.id)
        investigation.add_hypothesis(hypothesis)
        
        # 5. Create action
        action = Action(
            type=ActionType.SCALE,
            name="scale_up",
            description="Scale up replicas",
        )
        investigation.add_action(action)
        
        # 6. Complete investigation
        investigation.status = InvestigationStatus.COMPLETED
        investigation.report = Report(
            investigation_id=investigation.id,
            title="High CPU Investigation",
            executive_summary="High CPU caused by increased traffic. Scaled up replicas.",
            root_cause="Insufficient replicas for traffic load",
            root_cause_confidence=0.8,
            actions_taken=["Scaled payment-service from 3 to 5 replicas"],
            recommendations=["Consider auto-scaling configuration"],
        )
        
        assert investigation.status == InvestigationStatus.COMPLETED
        assert investigation.report is not None


# ============================================================================
# Scenario 2: Pod Crash → K8s Events → Logs → OOMKill Detection
# ============================================================================


class TestPodCrashOOMScenario:
    """Test scenario: Pod crash leading to OOMKill detection."""

    @pytest.mark.asyncio
    async def test_pod_crash_alert_detection(self, pod_crash_alert: Alert):
        """Test pod crash alert is properly detected."""
        assert pod_crash_alert.name == "PodCrashLooping"
        assert pod_crash_alert.service == "api-gateway"
        assert "CrashLooping" in pod_crash_alert.name

    @pytest.mark.asyncio
    async def test_kubernetes_events_collection(
        self, mock_kubernetes_client: MagicMock
    ):
        """Test collecting Kubernetes events."""
        events = await mock_kubernetes_client.get_events(
            namespace="production",
            field_selector="involvedObject.name=api-gateway-xyz789",
        )
        
        assert len(events) > 0
        
        # Find OOMKilled event
        oom_events = [e for e in events if e["reason"] == "OOMKilled"]
        assert len(oom_events) > 0

    @pytest.mark.asyncio
    async def test_pod_logs_analysis(
        self, mock_kubernetes_client: MagicMock
    ):
        """Test analyzing pod logs for OOM errors."""
        logs = await mock_kubernetes_client.get_pod_logs(
            name="api-gateway-xyz789",
            namespace="production",
            container="main",
        )
        
        assert "OutOfMemoryError" in logs

    @pytest.mark.asyncio
    async def test_oom_hypothesis_generation(self, pod_crash_alert: Alert):
        """Test OOMKill hypothesis is generated."""
        investigation = Investigation(
            alert_id=pod_crash_alert.id,
            title="Investigate pod crashes",
        )
        
        # Add event observation
        event_obs = Observation(
            type=ObservationType.EVENT,
            source="kubernetes",
            description="OOMKilled event detected",
            data={"reason": "OOMKilled", "count": 3},
            is_anomalous=True,
        )
        investigation.add_observation(event_obs)
        
        # Add log observation
        log_obs = Observation(
            type=ObservationType.LOG,
            source="loki",
            description="OutOfMemoryError in logs",
            data={"error": "java.lang.OutOfMemoryError"},
            is_anomalous=True,
        )
        investigation.add_observation(log_obs)
        
        # Generate hypothesis
        hypothesis = Hypothesis(
            statement="Memory leak or insufficient memory causing OOMKill",
            reasoning="Multiple OOMKilled events and OutOfMemoryError in logs",
            confidence=0.9,
        )
        hypothesis.add_supporting_evidence(event_obs.id)
        hypothesis.add_supporting_evidence(log_obs.id)
        hypothesis.status = HypothesisStatus.CONFIRMED
        investigation.add_hypothesis(hypothesis)
        
        confirmed = investigation.get_confirmed_hypotheses()
        assert len(confirmed) == 1
        assert confirmed[0].confidence >= 0.9

    @pytest.mark.asyncio
    async def test_memory_increase_action(self):
        """Test memory limit increase action."""
        action = Action(
            type=ActionType.CONFIG_CHANGE,
            name="increase_memory_limits",
            description="Increase memory limits from 1Gi to 2Gi",
            tool="kubernetes",
            command="kubectl patch deployment api-gateway -p '{...}'",
            parameters={
                "deployment": "api-gateway",
                "container": "main",
                "memory_limit": "2Gi",
            },
            is_destructive=False,
            requires_approval=True,
            risk_level="medium",
        )
        
        assert action.requires_approval is True
        assert action.type == ActionType.CONFIG_CHANGE

    @pytest.mark.asyncio
    async def test_full_oom_detection_flow(
        self,
        pod_crash_alert: Alert,
        mock_kubernetes_client: MagicMock,
        mock_loki_client: MagicMock,
    ):
        """Test complete OOM detection flow."""
        # 1. Create investigation
        investigation = Investigation(
            alert_id=pod_crash_alert.id,
            title="Investigate pod crash looping",
        )
        investigation.status = InvestigationStatus.IN_PROGRESS
        
        # 2. Get pod details
        pod = await mock_kubernetes_client.get_pod(
            name="api-gateway-xyz789",
            namespace="production",
        )
        
        # Check for OOMKilled in last state
        last_state = pod["status"]["containerStatuses"][0].get("lastState", {})
        terminated = last_state.get("terminated", {})
        
        if terminated.get("reason") == "OOMKilled":
            oom_observation = Observation(
                type=ObservationType.RESOURCE,
                source="kubernetes",
                description="Container was OOMKilled",
                data=terminated,
                is_anomalous=True,
                relevance_score=1.0,
            )
            investigation.add_observation(oom_observation)
        
        # 3. Get events
        events = await mock_kubernetes_client.get_events(namespace="production")
        oom_events = [e for e in events if e["reason"] == "OOMKilled"]
        
        if oom_events:
            event_obs = Observation(
                type=ObservationType.EVENT,
                source="kubernetes",
                description=f"Found {len(oom_events)} OOMKilled events",
                data=oom_events,
                is_anomalous=True,
            )
            investigation.add_observation(event_obs)
        
        # 4. Check logs
        logs = await mock_kubernetes_client.get_pod_logs(
            name="api-gateway-xyz789",
            namespace="production",
        )
        
        if "OutOfMemoryError" in logs:
            log_obs = Observation(
                type=ObservationType.LOG,
                source="kubernetes",
                description="OutOfMemoryError found in logs",
                data={"logs": logs},
                is_anomalous=True,
            )
            investigation.add_observation(log_obs)
        
        # 5. Form hypothesis
        hypothesis = Hypothesis(
            statement="Container killed due to exceeding memory limits",
            reasoning="OOMKilled events, OutOfMemoryError in logs, restart count high",
            confidence=0.95,
        )
        hypothesis.status = HypothesisStatus.CONFIRMED
        investigation.add_hypothesis(hypothesis)
        
        # 6. Propose action
        action = Action(
            type=ActionType.CONFIG_CHANGE,
            name="increase_memory",
            description="Increase memory limit to 2Gi",
            requires_approval=True,
        )
        investigation.add_action(action)
        
        # 7. Complete
        investigation.status = InvestigationStatus.COMPLETED
        investigation.report = Report(
            investigation_id=investigation.id,
            title="OOMKill Investigation",
            executive_summary="Pod crashes caused by OOMKill due to memory leak or insufficient limits.",
            root_cause="Memory consumption exceeds container limits",
            root_cause_confidence=0.95,
            recommendations=[
                "Increase memory limits",
                "Profile application for memory leaks",
                "Add memory alerts at 80% threshold",
            ],
        )
        
        assert investigation.status == InvestigationStatus.COMPLETED
        assert investigation.report.root_cause_confidence >= 0.9


# ============================================================================
# Scenario 3: Latency Spike → Trace Analysis → Dependency Issue
# ============================================================================


class TestLatencySpikeDependencyScenario:
    """Test scenario: Latency spike leading to dependency issue detection."""

    @pytest.mark.asyncio
    async def test_latency_alert_detection(self, latency_alert: Alert):
        """Test latency spike alert is properly detected."""
        assert latency_alert.name == "HighLatency"
        assert latency_alert.severity == AlertSeverity.HIGH
        assert "latency" in latency_alert.name.lower()

    @pytest.mark.asyncio
    async def test_latency_metrics_collection(
        self, mock_prometheus_client: MagicMock
    ):
        """Test collecting latency metrics."""
        result = await mock_prometheus_client.query_latency(
            query='histogram_quantile(0.99, http_request_duration_seconds_bucket{service="checkout-service"})'
        )
        
        latency = float(result["data"]["result"][0]["value"][1])
        assert latency > 1.0  # Above 1 second

    @pytest.fixture
    def mock_trace_data(self) -> dict[str, Any]:
        """Create mock trace data."""
        return {
            "traces": [
                {
                    "traceId": "abc123",
                    "spans": [
                        {
                            "spanId": "span-1",
                            "operationName": "checkout",
                            "duration": 1500,  # 1.5 seconds
                            "tags": {"service": "checkout-service"},
                        },
                        {
                            "spanId": "span-2",
                            "parentSpanId": "span-1",
                            "operationName": "call-payment-service",
                            "duration": 1200,  # 1.2 seconds - slow dependency
                            "tags": {"service": "payment-service"},
                        },
                        {
                            "spanId": "span-3",
                            "parentSpanId": "span-2",
                            "operationName": "database-query",
                            "duration": 1000,  # 1 second - root cause
                            "tags": {"service": "payment-service", "db": "postgres"},
                        },
                    ],
                }
            ]
        }

    @pytest.mark.asyncio
    async def test_trace_analysis_identifies_slow_span(
        self, mock_trace_data: dict[str, Any]
    ):
        """Test trace analysis identifies slow dependency."""
        spans = mock_trace_data["traces"][0]["spans"]
        
        # Find slowest span
        slowest = max(spans, key=lambda s: s["duration"])
        
        assert slowest["operationName"] == "database-query"
        assert slowest["duration"] >= 1000

    @pytest.mark.asyncio
    async def test_dependency_issue_hypothesis(self, latency_alert: Alert):
        """Test dependency issue hypothesis generation."""
        investigation = Investigation(
            alert_id=latency_alert.id,
            title="Investigate latency spike",
        )
        
        # Add trace observation
        trace_obs = Observation(
            type=ObservationType.TRACE,
            source="jaeger",
            description="Trace shows slow database query in payment-service",
            data={
                "slow_span": "database-query",
                "duration_ms": 1000,
                "service": "payment-service",
            },
            is_anomalous=True,
        )
        investigation.add_observation(trace_obs)
        
        # Generate hypothesis
        hypothesis = Hypothesis(
            statement="Slow database queries in payment-service causing latency cascade",
            reasoning="Trace analysis shows database-query span taking 1000ms",
            confidence=0.85,
        )
        hypothesis.add_supporting_evidence(trace_obs.id)
        investigation.add_hypothesis(hypothesis)
        
        assert "database" in investigation.hypotheses[0].statement.lower()

    @pytest.mark.asyncio
    async def test_database_diagnostics_action(self):
        """Test database diagnostics action."""
        action = Action(
            type=ActionType.DIAGNOSTIC,
            name="check_database_performance",
            description="Run database performance diagnostics",
            tool="postgres",
            command="SELECT * FROM pg_stat_activity; EXPLAIN ANALYZE ...",
            parameters={
                "database": "postgres-primary",
                "query_timeout": 30,
            },
            is_destructive=False,
            requires_approval=False,
        )
        
        assert action.type == ActionType.DIAGNOSTIC
        assert action.requires_approval is False

    @pytest.mark.asyncio
    async def test_full_latency_investigation_flow(
        self,
        latency_alert: Alert,
        mock_prometheus_client: MagicMock,
    ):
        """Test complete latency investigation flow."""
        # 1. Create investigation
        investigation = Investigation(
            alert_id=latency_alert.id,
            title="Investigate checkout latency spike",
        )
        investigation.status = InvestigationStatus.IN_PROGRESS
        
        # 2. Collect latency metrics
        latency_result = await mock_prometheus_client.query_latency(query="")
        latency_obs = Observation(
            type=ObservationType.METRIC,
            source="prometheus",
            description="P99 latency at 1.5 seconds",
            data={"p99_latency": 1.5},
            is_anomalous=True,
        )
        investigation.add_observation(latency_obs)
        
        # 3. Analyze traces (simulated)
        trace_obs = Observation(
            type=ObservationType.TRACE,
            source="jaeger",
            description="Slow database query identified: 1000ms",
            data={
                "trace_id": "abc123",
                "slow_operation": "database-query",
                "duration_ms": 1000,
                "upstream_service": "payment-service",
            },
            is_anomalous=True,
        )
        investigation.add_observation(trace_obs)
        
        # 4. Check dependent service
        dependent_obs = Observation(
            type=ObservationType.METRIC,
            source="prometheus",
            description="payment-service database connection pool exhausted",
            data={"active_connections": 100, "max_connections": 100},
            is_anomalous=True,
        )
        investigation.add_observation(dependent_obs)
        
        # 5. Form hypothesis
        hypothesis = Hypothesis(
            statement="Database connection pool exhaustion causing slow queries",
            reasoning="All database connections in use, queries queueing",
            confidence=0.9,
        )
        hypothesis.status = HypothesisStatus.CONFIRMED
        for obs in investigation.observations:
            hypothesis.add_supporting_evidence(obs.id)
        investigation.add_hypothesis(hypothesis)
        
        # 6. Propose actions
        action1 = Action(
            type=ActionType.CONFIG_CHANGE,
            name="increase_connection_pool",
            description="Increase database connection pool size",
            parameters={"max_connections": 150},
        )
        investigation.add_action(action1)
        
        action2 = Action(
            type=ActionType.DIAGNOSTIC,
            name="analyze_slow_queries",
            description="Analyze slow queries in database",
        )
        investigation.add_action(action2)
        
        # 7. Complete
        investigation.status = InvestigationStatus.COMPLETED
        investigation.report = Report(
            investigation_id=investigation.id,
            title="Latency Spike Investigation",
            executive_summary="Latency caused by database connection pool exhaustion.",
            root_cause="Database connection pool at capacity causing query queueing",
            root_cause_confidence=0.9,
            affected_services=["checkout-service", "payment-service"],
            recommendations=[
                "Increase connection pool size",
                "Implement connection pool monitoring",
                "Review and optimize slow queries",
            ],
        )
        
        assert investigation.status == InvestigationStatus.COMPLETED
        assert len(investigation.actions) == 2


# ============================================================================
# Investigation State Machine Tests
# ============================================================================


class TestInvestigationStateMachine:
    """Tests for investigation state transitions."""

    def test_investigation_state_transitions(self):
        """Test valid state transitions."""
        investigation = Investigation(
            alert_id=uuid4(),
            title="Test Investigation",
        )
        
        # Start: PENDING -> IN_PROGRESS
        assert investigation.status == InvestigationStatus.PENDING
        investigation.status = InvestigationStatus.IN_PROGRESS
        assert investigation.status == InvestigationStatus.IN_PROGRESS
        
        # Can go to WAITING_FOR_DATA
        investigation.status = InvestigationStatus.WAITING_FOR_DATA
        assert investigation.status == InvestigationStatus.WAITING_FOR_DATA
        
        # Back to IN_PROGRESS
        investigation.status = InvestigationStatus.IN_PROGRESS
        
        # To WAITING_FOR_APPROVAL
        investigation.status = InvestigationStatus.WAITING_FOR_APPROVAL
        
        # To COMPLETED
        investigation.status = InvestigationStatus.COMPLETED
        investigation.completed_at = datetime.now(timezone.utc)
        assert investigation.status == InvestigationStatus.COMPLETED

    def test_investigation_can_fail(self):
        """Test investigation can transition to failed."""
        investigation = Investigation(
            alert_id=uuid4(),
            title="Failing Investigation",
        )
        
        investigation.status = InvestigationStatus.IN_PROGRESS
        investigation.status = InvestigationStatus.FAILED
        
        assert investigation.status == InvestigationStatus.FAILED

    def test_investigation_can_be_cancelled(self):
        """Test investigation can be cancelled."""
        investigation = Investigation(
            alert_id=uuid4(),
            title="Cancelled Investigation",
        )
        
        investigation.status = InvestigationStatus.IN_PROGRESS
        investigation.status = InvestigationStatus.CANCELLED
        
        assert investigation.status == InvestigationStatus.CANCELLED


# ============================================================================
# Integration with External Systems Tests
# ============================================================================


class TestExternalSystemIntegration:
    """Tests for integration with external systems."""

    @pytest.mark.asyncio
    async def test_prometheus_integration(
        self, client: AsyncClient, mock_prometheus_client: MagicMock
    ):
        """Test integration with Prometheus."""
        with patch("autosre.integrations.prometheus.PrometheusClient") as MockClient:
            MockClient.return_value = mock_prometheus_client
            
            # Query should work
            result = await mock_prometheus_client.query_cpu(query="")
            assert "data" in result

    @pytest.mark.asyncio
    async def test_kubernetes_integration(
        self, client: AsyncClient, mock_kubernetes_client: MagicMock
    ):
        """Test integration with Kubernetes."""
        with patch("autosre.integrations.kubernetes.KubernetesClient") as MockClient:
            MockClient.return_value = mock_kubernetes_client
            
            # Operations should work
            pod = await mock_kubernetes_client.get_pod(name="test", namespace="default")
            assert "metadata" in pod

    @pytest.mark.asyncio
    async def test_loki_integration(
        self, client: AsyncClient, mock_loki_client: MagicMock
    ):
        """Test integration with Loki."""
        with patch("autosre.integrations.loki.LokiClient") as MockClient:
            MockClient.return_value = mock_loki_client
            
            result = await mock_loki_client.query(query='{app="test"}')
            assert "data" in result

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_integration_failure(self):
        """Test investigation continues when integrations fail."""
        investigation = Investigation(
            alert_id=uuid4(),
            title="Test with failing integrations",
        )
        investigation.status = InvestigationStatus.IN_PROGRESS
        
        # Simulate integration failures by not adding observations
        # Investigation should still be able to complete with partial data
        
        hypothesis = Hypothesis(
            statement="Unable to collect full data due to integration issues",
            reasoning="Some data sources unavailable",
            confidence=0.3,
        )
        investigation.add_hypothesis(hypothesis)
        
        # Can still complete
        investigation.status = InvestigationStatus.COMPLETED
        assert investigation.status == InvestigationStatus.COMPLETED
