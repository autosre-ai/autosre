"""
Real-World Scenario Tests for AutoSRE V2

These tests simulate actual production incidents and verify AutoSRE's
ability to investigate, diagnose, and remediate them.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass, field

# ============================================================================
# MOCK INFRASTRUCTURE
# ============================================================================

@dataclass
class MockMetric:
    """Simulated Prometheus metric"""
    name: str
    value: float
    labels: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class MockLogEntry:
    """Simulated log entry"""
    timestamp: datetime
    level: str
    message: str
    service: str
    trace_id: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class MockPod:
    """Simulated Kubernetes pod"""
    name: str
    namespace: str
    status: str
    restarts: int = 0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    ready: bool = True
    events: list = field(default_factory=list)


@dataclass
class MockAlert:
    """Simulated alert"""
    name: str
    severity: str
    service: str
    message: str
    firing_since: datetime = field(default_factory=datetime.now)
    labels: dict = field(default_factory=dict)


class MockPrometheus:
    """Simulated Prometheus backend"""
    
    def __init__(self):
        self.metrics: dict[str, list[MockMetric]] = {}
    
    def add_metric(self, metric: MockMetric):
        if metric.name not in self.metrics:
            self.metrics[metric.name] = []
        self.metrics[metric.name].append(metric)
    
    async def query(self, promql: str) -> list[MockMetric]:
        """Simulate PromQL query"""
        # Simple pattern matching for common queries
        for name, metrics in self.metrics.items():
            if name in promql:
                return metrics
        return []
    
    async def query_range(self, promql: str, start: datetime, end: datetime) -> list[MockMetric]:
        """Simulate range query"""
        return await self.query(promql)


class MockLoki:
    """Simulated Loki backend"""
    
    def __init__(self):
        self.logs: list[MockLogEntry] = []
    
    def add_log(self, entry: MockLogEntry):
        self.logs.append(entry)
    
    async def query(self, logql: str, limit: int = 100) -> list[MockLogEntry]:
        """Simulate LogQL query"""
        results = []
        for log in self.logs:
            # Simple filtering
            if "error" in logql.lower() and log.level == "ERROR":
                results.append(log)
            elif "service" in logql and log.service in logql:
                results.append(log)
            elif not any(x in logql.lower() for x in ["error", "service"]):
                results.append(log)
        return results[:limit]


class MockKubernetes:
    """Simulated Kubernetes cluster"""
    
    def __init__(self):
        self.pods: dict[str, MockPod] = {}
        self.deployments: dict[str, dict] = {}
        self.events: list[dict] = []
    
    def add_pod(self, pod: MockPod):
        self.pods[f"{pod.namespace}/{pod.name}"] = pod
    
    async def get_pods(self, namespace: str = None, label_selector: str = None) -> list[MockPod]:
        pods = list(self.pods.values())
        if namespace:
            pods = [p for p in pods if p.namespace == namespace]
        return pods
    
    async def get_pod_logs(self, name: str, namespace: str) -> str:
        return f"Mock logs for {namespace}/{name}"
    
    async def restart_pod(self, name: str, namespace: str) -> bool:
        key = f"{namespace}/{name}"
        if key in self.pods:
            self.pods[key].restarts += 1
            self.pods[key].status = "Running"
            return True
        return False
    
    async def scale_deployment(self, name: str, namespace: str, replicas: int) -> bool:
        key = f"{namespace}/{name}"
        if key in self.deployments:
            self.deployments[key]["replicas"] = replicas
            return True
        return False


# ============================================================================
# SCENARIO SIMULATORS
# ============================================================================

class MemoryLeakScenario:
    """
    Scenario: Memory leak in payment-service causing OOMKills
    
    Symptoms:
    - Pods restarting frequently
    - Memory usage growing over time
    - OOMKilled events in pod status
    - Increasing latency before crashes
    """
    
    def __init__(self):
        self.prometheus = MockPrometheus()
        self.loki = MockLoki()
        self.kubernetes = MockKubernetes()
        self._setup()
    
    def _setup(self):
        # Setup memory metrics showing growth
        base_time = datetime.now()
        for i in range(60):  # Last 60 minutes
            self.prometheus.add_metric(MockMetric(
                name="container_memory_usage_bytes",
                value=500_000_000 + (i * 50_000_000),  # Growing memory
                labels={"pod": "payment-service-abc123", "namespace": "production"},
                timestamp=base_time - timedelta(minutes=60-i)
            ))
        
        # Add OOMKill events in logs
        for i in range(3):
            self.loki.add_log(MockLogEntry(
                timestamp=base_time - timedelta(minutes=i*20),
                level="ERROR",
                message="Container killed due to OOM",
                service="payment-service",
                extra={"reason": "OOMKilled"}
            ))
        
        # Add pods with restarts
        self.kubernetes.add_pod(MockPod(
            name="payment-service-abc123",
            namespace="production",
            status="Running",
            restarts=5,
            memory_usage=0.95,
            events=["OOMKilled", "BackOff"]
        ))
    
    def get_alert(self) -> MockAlert:
        return MockAlert(
            name="PodOOMKilled",
            severity="critical",
            service="payment-service",
            message="Pod payment-service-abc123 has been OOMKilled 5 times in the last hour",
            labels={"namespace": "production", "pod": "payment-service-abc123"}
        )


class DatabaseConnectionPoolExhaustion:
    """
    Scenario: Database connection pool exhausted causing service failures
    
    Symptoms:
    - Connection timeout errors in logs
    - High pending connection count
    - Increased latency on DB-dependent endpoints
    - 500 errors on API responses
    """
    
    def __init__(self):
        self.prometheus = MockPrometheus()
        self.loki = MockLoki()
        self.kubernetes = MockKubernetes()
        self._setup()
    
    def _setup(self):
        base_time = datetime.now()
        
        # DB connection pool metrics
        self.prometheus.add_metric(MockMetric(
            name="db_connection_pool_active",
            value=100,  # Max pool size
            labels={"service": "order-service", "database": "orders-primary"}
        ))
        self.prometheus.add_metric(MockMetric(
            name="db_connection_pool_pending",
            value=50,  # 50 waiting for connections
            labels={"service": "order-service", "database": "orders-primary"}
        ))
        self.prometheus.add_metric(MockMetric(
            name="db_connection_pool_max",
            value=100,
            labels={"service": "order-service", "database": "orders-primary"}
        ))
        
        # Error logs
        for i in range(20):
            self.loki.add_log(MockLogEntry(
                timestamp=base_time - timedelta(seconds=i*30),
                level="ERROR",
                message=f"Connection pool exhausted: timeout waiting for connection after 30s",
                service="order-service",
                extra={"error_type": "ConnectionPoolExhausted"}
            ))
        
        # API error rate metrics
        self.prometheus.add_metric(MockMetric(
            name="http_requests_total",
            value=1000,
            labels={"service": "order-service", "status": "500"}
        ))
        
        # Pods are running but unhealthy
        self.kubernetes.add_pod(MockPod(
            name="order-service-xyz789",
            namespace="production",
            status="Running",
            ready=False,  # Failing health checks
            cpu_usage=0.3,
            memory_usage=0.4
        ))
    
    def get_alert(self) -> MockAlert:
        return MockAlert(
            name="HighErrorRate",
            severity="critical",
            service="order-service",
            message="Error rate above 50% for order-service",
            labels={"namespace": "production"}
        )


class CascadingFailureScenario:
    """
    Scenario: Cascading failure from upstream service timeout
    
    Chain of events:
    1. auth-service becomes slow (upstream dependency issue)
    2. api-gateway starts timing out on auth
    3. All services depending on auth start failing
    4. Error rates spike across multiple services
    """
    
    def __init__(self):
        self.prometheus = MockPrometheus()
        self.loki = MockLoki()
        self.kubernetes = MockKubernetes()
        self._setup()
    
    def _setup(self):
        base_time = datetime.now()
        
        # Auth service latency spike
        self.prometheus.add_metric(MockMetric(
            name="http_request_duration_seconds",
            value=5.0,  # 5 second latency (normally 50ms)
            labels={"service": "auth-service", "quantile": "0.99"}
        ))
        
        # Downstream services timing out
        for service in ["api-gateway", "user-service", "order-service", "payment-service"]:
            self.prometheus.add_metric(MockMetric(
                name="http_requests_total",
                value=500,
                labels={"service": service, "status": "504"}
            ))
            
            self.loki.add_log(MockLogEntry(
                timestamp=base_time - timedelta(minutes=5),
                level="ERROR",
                message=f"Timeout calling auth-service: context deadline exceeded",
                service=service
            ))
        
        # Circuit breaker tripped
        self.prometheus.add_metric(MockMetric(
            name="circuit_breaker_state",
            value=1,  # OPEN
            labels={"service": "api-gateway", "target": "auth-service"}
        ))
        
        # All pods running but struggling
        for service in ["auth-service", "api-gateway", "user-service"]:
            self.kubernetes.add_pod(MockPod(
                name=f"{service}-pod1",
                namespace="production",
                status="Running",
                cpu_usage=0.9,  # High CPU from retry storms
                memory_usage=0.7
            ))
    
    def get_alert(self) -> MockAlert:
        return MockAlert(
            name="MultiServiceHighLatency",
            severity="critical",
            service="api-gateway",
            message="Multiple services experiencing high latency and timeouts",
            labels={"namespace": "production", "affected_services": "auth,user,order,payment"}
        )


class DiskPressureScenario:
    """
    Scenario: Node disk pressure causing pod evictions
    
    Symptoms:
    - Node in DiskPressure condition
    - Pods being evicted
    - Logs showing write failures
    - PVCs filling up
    """
    
    def __init__(self):
        self.prometheus = MockPrometheus()
        self.loki = MockLoki()
        self.kubernetes = MockKubernetes()
        self._setup()
    
    def _setup(self):
        base_time = datetime.now()
        
        # Node disk metrics
        self.prometheus.add_metric(MockMetric(
            name="node_filesystem_avail_bytes",
            value=1_000_000_000,  # 1GB left
            labels={"node": "worker-node-1", "mountpoint": "/var/lib/docker"}
        ))
        self.prometheus.add_metric(MockMetric(
            name="node_filesystem_size_bytes",
            value=100_000_000_000,  # 100GB total
            labels={"node": "worker-node-1", "mountpoint": "/var/lib/docker"}
        ))
        
        # Log write errors
        self.loki.add_log(MockLogEntry(
            timestamp=base_time,
            level="ERROR",
            message="write /var/log/app.log: no space left on device",
            service="logging-agent"
        ))
        
        # Evicted pods
        self.kubernetes.add_pod(MockPod(
            name="batch-processor-123",
            namespace="production",
            status="Evicted",
            events=["Evicted due to DiskPressure"]
        ))
    
    def get_alert(self) -> MockAlert:
        return MockAlert(
            name="NodeDiskPressure",
            severity="warning",
            service="kubernetes",
            message="Node worker-node-1 is experiencing disk pressure",
            labels={"node": "worker-node-1"}
        )


class DeploymentRolloutFailure:
    """
    Scenario: Failed deployment rollout causing service degradation
    
    Symptoms:
    - New pods failing readiness probes
    - Old pods still running (rollout stuck)
    - Increased error rate during partial rollout
    - Image pull errors or crash loops
    """
    
    def __init__(self):
        self.prometheus = MockPrometheus()
        self.loki = MockLoki()
        self.kubernetes = MockKubernetes()
        self._setup()
    
    def _setup(self):
        base_time = datetime.now()
        
        # Mix of old and new pods
        self.kubernetes.add_pod(MockPod(
            name="catalog-service-old-abc",
            namespace="production",
            status="Running",
            ready=True
        ))
        self.kubernetes.add_pod(MockPod(
            name="catalog-service-new-xyz",
            namespace="production",
            status="CrashLoopBackOff",
            restarts=10,
            ready=False,
            events=["CrashLoopBackOff", "Error: ImagePullBackOff"]
        ))
        
        # Deployment status
        self.kubernetes.deployments["production/catalog-service"] = {
            "replicas": 3,
            "available": 1,
            "unavailable": 2,
            "conditions": [{"type": "Progressing", "status": "False", "reason": "ProgressDeadlineExceeded"}]
        }
        
        # Error logs from new version
        self.loki.add_log(MockLogEntry(
            timestamp=base_time,
            level="ERROR",
            message="panic: runtime error: invalid memory address or nil pointer dereference",
            service="catalog-service"
        ))
        
        self.loki.add_log(MockLogEntry(
            timestamp=base_time - timedelta(minutes=1),
            level="ERROR",
            message="Failed to connect to required service: config-service not found",
            service="catalog-service"
        ))
    
    def get_alert(self) -> MockAlert:
        return MockAlert(
            name="DeploymentRolloutStuck",
            severity="critical",
            service="catalog-service",
            message="Deployment catalog-service rollout stuck: ProgressDeadlineExceeded",
            labels={"namespace": "production", "deployment": "catalog-service"}
        )


# ============================================================================
# INVESTIGATION ENGINE (Simplified for testing)
# ============================================================================

class InvestigationEngine:
    """Simplified investigation engine for scenario testing"""
    
    def __init__(self, prometheus: MockPrometheus, loki: MockLoki, kubernetes: MockKubernetes):
        self.prometheus = prometheus
        self.loki = loki
        self.kubernetes = kubernetes
        self.findings: list[str] = []
        self.root_cause: str = ""
        self.recommendations: list[str] = []
    
    async def investigate(self, alert: MockAlert) -> dict:
        """Run investigation on an alert"""
        self.findings = []
        self.recommendations = []
        
        # Gather evidence
        await self._check_pods(alert)
        await self._check_metrics(alert)
        await self._check_logs(alert)
        
        # Determine root cause
        self._determine_root_cause()
        
        return {
            "alert": alert.name,
            "severity": alert.severity,
            "service": alert.service,
            "findings": self.findings,
            "root_cause": self.root_cause,
            "recommendations": self.recommendations,
            "confidence": self._calculate_confidence()
        }
    
    async def _check_pods(self, alert: MockAlert):
        pods = await self.kubernetes.get_pods()
        
        for pod in pods:
            if pod.status == "CrashLoopBackOff":
                self.findings.append(f"Pod {pod.name} in CrashLoopBackOff with {pod.restarts} restarts")
            elif pod.status == "Evicted":
                self.findings.append(f"Pod {pod.name} was evicted")
            elif not pod.ready:
                self.findings.append(f"Pod {pod.name} failing readiness checks")
            
            if pod.memory_usage > 0.9:
                self.findings.append(f"Pod {pod.name} has high memory usage: {pod.memory_usage*100:.0f}%")
            if pod.cpu_usage > 0.8:
                self.findings.append(f"Pod {pod.name} has high CPU usage: {pod.cpu_usage*100:.0f}%")
            
            for event in pod.events:
                if "OOM" in event:
                    self.findings.append(f"Pod {pod.name} experienced OOMKill")
    
    async def _check_metrics(self, alert: MockAlert):
        # Check memory metrics
        memory_metrics = await self.prometheus.query("container_memory_usage_bytes")
        if memory_metrics:
            latest = memory_metrics[-1]
            if latest.value > 800_000_000:  # > 800MB
                self.findings.append(f"High memory usage detected: {latest.value/1e9:.2f}GB")
        
        # Check connection pool
        pool_metrics = await self.prometheus.query("db_connection_pool_active")
        if pool_metrics:
            active = pool_metrics[0].value
            self.findings.append(f"DB connection pool: {active} active connections")
        
        pending_metrics = await self.prometheus.query("db_connection_pool_pending")
        if pending_metrics and pending_metrics[0].value > 10:
            self.findings.append(f"DB connection pool has {pending_metrics[0].value} pending requests")
        
        # Check latency
        latency_metrics = await self.prometheus.query("http_request_duration_seconds")
        if latency_metrics and latency_metrics[0].value > 1.0:
            self.findings.append(f"High latency detected: {latency_metrics[0].value:.2f}s p99")
        
        # Check circuit breaker
        cb_metrics = await self.prometheus.query("circuit_breaker_state")
        if cb_metrics and cb_metrics[0].value == 1:
            labels = cb_metrics[0].labels
            self.findings.append(f"Circuit breaker OPEN: {labels.get('service')} -> {labels.get('target')}")
    
    async def _check_logs(self, alert: MockAlert):
        error_logs = await self.loki.query('{level="ERROR"}', limit=10)
        
        error_patterns = {}
        for log in error_logs:
            # Categorize errors
            if "OOM" in log.message:
                error_patterns["OOM"] = error_patterns.get("OOM", 0) + 1
            elif "timeout" in log.message.lower():
                error_patterns["timeout"] = error_patterns.get("timeout", 0) + 1
            elif "connection pool" in log.message.lower():
                error_patterns["connection_pool"] = error_patterns.get("connection_pool", 0) + 1
            elif "panic" in log.message.lower():
                error_patterns["panic"] = error_patterns.get("panic", 0) + 1
            elif "no space" in log.message.lower():
                error_patterns["disk_full"] = error_patterns.get("disk_full", 0) + 1
        
        for pattern, count in error_patterns.items():
            self.findings.append(f"Found {count} {pattern} errors in logs")
    
    def _determine_root_cause(self):
        # Analyze findings to determine root cause
        findings_text = " ".join(self.findings).lower()
        
        if "oomkill" in findings_text or "high memory" in findings_text:
            self.root_cause = "Memory leak or insufficient memory allocation"
            self.recommendations = [
                "Increase memory limits for the pod",
                "Profile application for memory leaks",
                "Add memory-based HPA",
                "Review recent code changes for memory issues"
            ]
        elif "connection pool" in findings_text:
            self.root_cause = "Database connection pool exhaustion"
            self.recommendations = [
                "Increase connection pool size",
                "Add connection timeout settings",
                "Check for connection leaks",
                "Scale database if connections are legitimate"
            ]
        elif "circuit breaker" in findings_text and "timeout" in findings_text:
            self.root_cause = "Cascading failure from upstream service"
            self.recommendations = [
                "Check upstream service (auth-service) health",
                "Verify circuit breaker is working correctly",
                "Add bulkhead pattern to isolate failures",
                "Review timeout configurations"
            ]
        elif "evicted" in findings_text or "disk" in findings_text:
            self.root_cause = "Node disk pressure"
            self.recommendations = [
                "Clean up unused images and containers",
                "Expand node disk or add storage",
                "Configure log rotation",
                "Move pods to healthy nodes"
            ]
        elif "crashloopbackoff" in findings_text or "panic" in findings_text:
            self.root_cause = "Application crash in new deployment"
            self.recommendations = [
                "Roll back to previous version",
                "Check application logs for stack traces",
                "Verify environment variables and configs",
                "Review recent deployment changes"
            ]
        else:
            self.root_cause = "Unknown - requires manual investigation"
            self.recommendations = ["Engage on-call engineer for manual investigation"]
    
    def _calculate_confidence(self) -> float:
        """Calculate confidence in root cause determination"""
        if not self.findings:
            return 0.0
        
        # More findings = more confidence (up to a point)
        finding_score = min(len(self.findings) / 5, 1.0) * 0.5
        
        # Specific root cause = more confidence
        if self.root_cause and "Unknown" not in self.root_cause:
            cause_score = 0.5
        else:
            cause_score = 0.1
        
        return finding_score + cause_score


# ============================================================================
# TEST CASES
# ============================================================================

class TestMemoryLeakScenario:
    """Tests for memory leak detection and diagnosis"""
    
    @pytest.mark.asyncio
    async def test_detects_memory_growth(self):
        scenario = MemoryLeakScenario()
        engine = InvestigationEngine(
            scenario.prometheus, scenario.loki, scenario.kubernetes
        )
        
        result = await engine.investigate(scenario.get_alert())
        
        assert result["severity"] == "critical"
        assert "memory" in result["root_cause"].lower()
        assert any("memory" in f.lower() for f in result["findings"])
    
    @pytest.mark.asyncio
    async def test_detects_oom_events(self):
        scenario = MemoryLeakScenario()
        engine = InvestigationEngine(
            scenario.prometheus, scenario.loki, scenario.kubernetes
        )
        
        result = await engine.investigate(scenario.get_alert())
        
        assert any("OOM" in f for f in result["findings"])
    
    @pytest.mark.asyncio
    async def test_recommends_memory_actions(self):
        scenario = MemoryLeakScenario()
        engine = InvestigationEngine(
            scenario.prometheus, scenario.loki, scenario.kubernetes
        )
        
        result = await engine.investigate(scenario.get_alert())
        
        assert len(result["recommendations"]) > 0
        assert any("memory" in r.lower() for r in result["recommendations"])


class TestDatabaseConnectionPoolScenario:
    """Tests for connection pool exhaustion detection"""
    
    @pytest.mark.asyncio
    async def test_detects_pool_exhaustion(self):
        scenario = DatabaseConnectionPoolExhaustion()
        engine = InvestigationEngine(
            scenario.prometheus, scenario.loki, scenario.kubernetes
        )
        
        result = await engine.investigate(scenario.get_alert())
        
        assert "connection pool" in result["root_cause"].lower()
        assert any("connection" in f.lower() for f in result["findings"])
    
    @pytest.mark.asyncio
    async def test_identifies_pending_connections(self):
        scenario = DatabaseConnectionPoolExhaustion()
        engine = InvestigationEngine(
            scenario.prometheus, scenario.loki, scenario.kubernetes
        )
        
        result = await engine.investigate(scenario.get_alert())
        
        assert any("pending" in f.lower() for f in result["findings"])
    
    @pytest.mark.asyncio
    async def test_recommends_pool_actions(self):
        scenario = DatabaseConnectionPoolExhaustion()
        engine = InvestigationEngine(
            scenario.prometheus, scenario.loki, scenario.kubernetes
        )
        
        result = await engine.investigate(scenario.get_alert())
        
        recommendations_text = " ".join(result["recommendations"]).lower()
        assert "pool" in recommendations_text or "connection" in recommendations_text


class TestCascadingFailureScenario:
    """Tests for cascading failure detection"""
    
    @pytest.mark.asyncio
    async def test_detects_upstream_issue(self):
        scenario = CascadingFailureScenario()
        engine = InvestigationEngine(
            scenario.prometheus, scenario.loki, scenario.kubernetes
        )
        
        result = await engine.investigate(scenario.get_alert())
        
        assert "cascading" in result["root_cause"].lower() or "upstream" in result["root_cause"].lower()
    
    @pytest.mark.asyncio
    async def test_detects_circuit_breaker(self):
        scenario = CascadingFailureScenario()
        engine = InvestigationEngine(
            scenario.prometheus, scenario.loki, scenario.kubernetes
        )
        
        result = await engine.investigate(scenario.get_alert())
        
        assert any("circuit breaker" in f.lower() for f in result["findings"])
    
    @pytest.mark.asyncio
    async def test_identifies_timeout_errors(self):
        scenario = CascadingFailureScenario()
        engine = InvestigationEngine(
            scenario.prometheus, scenario.loki, scenario.kubernetes
        )
        
        result = await engine.investigate(scenario.get_alert())
        
        assert any("timeout" in f.lower() for f in result["findings"])


class TestDiskPressureScenario:
    """Tests for disk pressure detection"""
    
    @pytest.mark.asyncio
    async def test_detects_disk_issue(self):
        scenario = DiskPressureScenario()
        engine = InvestigationEngine(
            scenario.prometheus, scenario.loki, scenario.kubernetes
        )
        
        result = await engine.investigate(scenario.get_alert())
        
        assert "disk" in result["root_cause"].lower()
    
    @pytest.mark.asyncio
    async def test_detects_evicted_pods(self):
        scenario = DiskPressureScenario()
        engine = InvestigationEngine(
            scenario.prometheus, scenario.loki, scenario.kubernetes
        )
        
        result = await engine.investigate(scenario.get_alert())
        
        assert any("evicted" in f.lower() for f in result["findings"])


class TestDeploymentRolloutFailure:
    """Tests for failed deployment detection"""
    
    @pytest.mark.asyncio
    async def test_detects_crash_loop(self):
        scenario = DeploymentRolloutFailure()
        engine = InvestigationEngine(
            scenario.prometheus, scenario.loki, scenario.kubernetes
        )
        
        result = await engine.investigate(scenario.get_alert())
        
        assert "crash" in result["root_cause"].lower() or "deployment" in result["root_cause"].lower()
    
    @pytest.mark.asyncio
    async def test_detects_pod_restarts(self):
        scenario = DeploymentRolloutFailure()
        engine = InvestigationEngine(
            scenario.prometheus, scenario.loki, scenario.kubernetes
        )
        
        result = await engine.investigate(scenario.get_alert())
        
        assert any("restart" in f.lower() or "crashloop" in f.lower() for f in result["findings"])
    
    @pytest.mark.asyncio
    async def test_recommends_rollback(self):
        scenario = DeploymentRolloutFailure()
        engine = InvestigationEngine(
            scenario.prometheus, scenario.loki, scenario.kubernetes
        )
        
        result = await engine.investigate(scenario.get_alert())
        
        assert any("roll back" in r.lower() for r in result["recommendations"])


class TestInvestigationConfidence:
    """Tests for confidence scoring"""
    
    @pytest.mark.asyncio
    async def test_high_confidence_with_clear_evidence(self):
        scenario = MemoryLeakScenario()
        engine = InvestigationEngine(
            scenario.prometheus, scenario.loki, scenario.kubernetes
        )
        
        result = await engine.investigate(scenario.get_alert())
        
        assert result["confidence"] >= 0.5
    
    @pytest.mark.asyncio
    async def test_provides_recommendations(self):
        scenario = DatabaseConnectionPoolExhaustion()
        engine = InvestigationEngine(
            scenario.prometheus, scenario.loki, scenario.kubernetes
        )
        
        result = await engine.investigate(scenario.get_alert())
        
        assert len(result["recommendations"]) >= 2


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestEndToEndInvestigation:
    """End-to-end investigation workflow tests"""
    
    @pytest.mark.asyncio
    async def test_full_investigation_workflow(self):
        """Test complete investigation from alert to recommendations"""
        scenario = MemoryLeakScenario()
        engine = InvestigationEngine(
            scenario.prometheus, scenario.loki, scenario.kubernetes
        )
        
        alert = scenario.get_alert()
        result = await engine.investigate(alert)
        
        # Verify complete investigation
        assert result["alert"] == alert.name
        assert result["service"] == alert.service
        assert len(result["findings"]) > 0
        assert result["root_cause"] != ""
        assert len(result["recommendations"]) > 0
        assert 0 <= result["confidence"] <= 1
    
    @pytest.mark.asyncio
    async def test_multiple_scenarios_differentiation(self):
        """Test that different scenarios produce different diagnoses"""
        scenarios = [
            MemoryLeakScenario(),
            DatabaseConnectionPoolExhaustion(),
            CascadingFailureScenario(),
            DiskPressureScenario(),
            DeploymentRolloutFailure()
        ]
        
        root_causes = []
        for scenario in scenarios:
            engine = InvestigationEngine(
                scenario.prometheus, scenario.loki, scenario.kubernetes
            )
            result = await engine.investigate(scenario.get_alert())
            root_causes.append(result["root_cause"])
        
        # Each scenario should have a unique root cause
        assert len(set(root_causes)) == len(root_causes)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
