"""Tests for High Availability module."""

from __future__ import annotations

import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from autosre.ha.leader_election import (
    LeaderElection,
    LeaderState,
    ElectionConfig,
    LeaderInfo,
    InMemoryLeaderBackend,
    create_leader_election,
)
from autosre.ha.state_replication import (
    StateReplicator,
    ReplicationConfig,
    ReplicationState,
    StateEntry,
    ConflictResolution,
    VectorClock,
    InMemoryReplicationBackend,
)
from autosre.ha.health_checker import (
    HealthChecker,
    HealthCheck,
    HealthCheckResult,
    HealthStatus,
    HealthConfig,
    HTTPHealthCheck,
    TCPHealthCheck,
    FunctionHealthCheck,
)
from autosre.ha.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitOpenError,
)
from autosre.ha.retry_policy import (
    RetryPolicy,
    RetryConfig,
    RetryStrategy,
    retry,
    async_retry,
)


class TestLeaderElection:
    """Tests for LeaderElection."""
    
    @pytest.fixture
    def backend(self):
        """Create in-memory backend."""
        return InMemoryLeaderBackend()
    
    @pytest.fixture
    def config(self):
        """Create election config."""
        return ElectionConfig(
            election_key="test/leader",
            lease_ttl_seconds=5.0,
            heartbeat_interval_seconds=1.0,
        )
    
    @pytest.mark.asyncio
    async def test_acquire_leadership(self, backend, config):
        """Test acquiring leadership."""
        election = LeaderElection(backend, config)
        
        # Should start as stopped
        assert election.state == LeaderState.STOPPED
        
        await election.start()
        
        # Wait for election
        await asyncio.sleep(0.1)
        
        assert election.is_leader
        assert election.state == LeaderState.LEADER
        
        await election.stop()
        assert election.state == LeaderState.STOPPED
    
    @pytest.mark.asyncio
    async def test_leadership_callbacks(self, backend, config):
        """Test leadership callbacks are called."""
        election = LeaderElection(backend, config)
        
        gained = asyncio.Event()
        lost = asyncio.Event()
        
        async def on_gain():
            gained.set()
        
        async def on_lose():
            lost.set()
        
        election.on_gain_leadership(on_gain)
        election.on_lose_leadership(on_lose)
        
        await election.start()
        await asyncio.sleep(0.1)
        
        assert gained.is_set()
        
        await election.force_election()
        assert lost.is_set()
        
        await election.stop()
    
    @pytest.mark.asyncio
    async def test_multiple_candidates(self, backend, config):
        """Test multiple candidates competing."""
        election1 = LeaderElection(backend, ElectionConfig(
            election_key="test/leader",
            candidate_id="candidate-1",
            lease_ttl_seconds=5.0,
            heartbeat_interval_seconds=1.0,
        ))
        
        election2 = LeaderElection(backend, ElectionConfig(
            election_key="test/leader",
            candidate_id="candidate-2",
            lease_ttl_seconds=5.0,
            heartbeat_interval_seconds=1.0,
        ))
        
        await election1.start()
        await asyncio.sleep(0.1)
        
        await election2.start()
        await asyncio.sleep(0.1)
        
        # Only one should be leader
        assert election1.is_leader != election2.is_leader
        
        await election1.stop()
        await election2.stop()
    
    def test_create_leader_election(self):
        """Test factory function."""
        election = create_leader_election("memory")
        assert election is not None
        assert isinstance(election.backend, InMemoryLeaderBackend)


class TestStateReplication:
    """Tests for StateReplication."""
    
    @pytest.fixture
    def backend(self):
        """Create in-memory backend."""
        return InMemoryReplicationBackend()
    
    @pytest.fixture
    def config(self):
        """Create replication config."""
        return ReplicationConfig(
            node_id="test-node",
            sync_interval_seconds=1.0,
        )
    
    @pytest.mark.asyncio
    async def test_set_and_get(self, backend, config):
        """Test basic set and get operations."""
        replicator = StateReplicator(backend, config)
        await replicator.start()
        
        # Set value
        entry = await replicator.set("test-key", {"foo": "bar"})
        
        assert entry.key == "test-key"
        assert entry.value == {"foo": "bar"}
        assert entry.version == 1
        
        # Get value
        value = await replicator.get("test-key")
        assert value == {"foo": "bar"}
        
        await replicator.stop()
    
    @pytest.mark.asyncio
    async def test_version_increment(self, backend, config):
        """Test version increments on update."""
        replicator = StateReplicator(backend, config)
        await replicator.start()
        
        entry1 = await replicator.set("key", "v1")
        assert entry1.version == 1
        
        entry2 = await replicator.set("key", "v2")
        assert entry2.version == 2
        
        await replicator.stop()
    
    @pytest.mark.asyncio
    async def test_delete(self, backend, config):
        """Test delete operation."""
        replicator = StateReplicator(backend, config)
        await replicator.start()
        
        await replicator.set("key", "value")
        
        deleted = await replicator.delete("key")
        assert deleted
        
        value = await replicator.get("key")
        assert value is None
        
        await replicator.stop()
    
    @pytest.mark.asyncio
    async def test_compare_and_set(self, backend, config):
        """Test compare-and-set operation."""
        replicator = StateReplicator(backend, config)
        await replicator.start()
        
        await replicator.set("key", "v1")
        
        # Successful CAS
        success, entry = await replicator.compare_and_set("key", 1, "v2")
        assert success
        assert entry.value == "v2"
        
        # Failed CAS (wrong version)
        success, entry = await replicator.compare_and_set("key", 1, "v3")
        assert not success
        assert entry.value == "v2"
        
        await replicator.stop()
    
    def test_vector_clock_happens_before(self):
        """Test vector clock ordering."""
        vc1 = VectorClock(clocks={"a": 1, "b": 1})
        vc2 = VectorClock(clocks={"a": 2, "b": 1})
        
        assert vc1.happens_before(vc2)
        assert not vc2.happens_before(vc1)
    
    def test_vector_clock_concurrent(self):
        """Test concurrent vector clocks."""
        vc1 = VectorClock(clocks={"a": 2, "b": 1})
        vc2 = VectorClock(clocks={"a": 1, "b": 2})
        
        assert vc1.concurrent_with(vc2)
        assert vc2.concurrent_with(vc1)
    
    def test_vector_clock_merge(self):
        """Test vector clock merge."""
        vc1 = VectorClock(clocks={"a": 2, "b": 1})
        vc2 = VectorClock(clocks={"a": 1, "b": 2, "c": 1})
        
        merged = vc1.merge(vc2)
        
        assert merged.clocks == {"a": 2, "b": 2, "c": 1}


class TestHealthChecker:
    """Tests for HealthChecker."""
    
    @pytest.mark.asyncio
    async def test_basic_health_check(self):
        """Test basic health check."""
        checker = HealthChecker()
        
        # Add a simple function check
        async def always_healthy():
            return HealthCheckResult(
                name="test",
                check_type=HealthCheck.check_type,
                status=HealthStatus.HEALTHY,
            )
        
        checker.add_function_check("test", always_healthy)
        
        await checker.start()
        
        health = await checker.get_health()
        assert health.status == HealthStatus.HEALTHY
        
        await checker.stop()
    
    @pytest.mark.asyncio
    async def test_unhealthy_critical_dependency(self):
        """Test that critical dependency failure affects overall health."""
        checker = HealthChecker(HealthConfig(
            critical_dependencies={"critical-service"},
        ))
        
        async def unhealthy_check():
            return HealthCheckResult(
                name="critical-service",
                check_type=HealthCheck.check_type,
                status=HealthStatus.UNHEALTHY,
            )
        
        checker.add_function_check("critical-service", unhealthy_check, critical=True)
        
        await checker.start()
        
        health = await checker.get_health()
        assert health.status in (HealthStatus.UNHEALTHY, HealthStatus.DEGRADED)
        
        await checker.stop()
    
    @pytest.mark.asyncio
    async def test_liveness_check(self):
        """Test liveness check."""
        checker = HealthChecker()
        
        result = await checker.check_liveness()
        assert result.status == HealthStatus.HEALTHY
    
    @pytest.mark.asyncio
    async def test_health_statistics(self):
        """Test health statistics tracking."""
        checker = HealthChecker()
        
        call_count = 0
        
        async def counting_check():
            nonlocal call_count
            call_count += 1
            return HealthCheckResult(
                name="counter",
                check_type=HealthCheck.check_type,
                status=HealthStatus.HEALTHY,
            )
        
        checker.add_function_check("counter", counting_check)
        
        # Run checks manually
        await checker._run_checks()
        await checker._run_checks()
        
        stats = checker.get_stats("counter")
        assert stats["total_checks"] == 2
        assert stats["healthy_count"] == 2


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""
    
    @pytest.mark.asyncio
    async def test_successful_calls(self):
        """Test successful calls pass through."""
        circuit = CircuitBreaker("test")
        
        async def success():
            return "ok"
        
        result = await circuit.call(success)
        assert result == "ok"
        assert circuit.is_closed
    
    @pytest.mark.asyncio
    async def test_circuit_opens_on_failures(self):
        """Test circuit opens after failure threshold."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            timeout_seconds=10.0,
        )
        circuit = CircuitBreaker("test", config)
        
        async def failing():
            raise ValueError("fail")
        
        # First failure
        with pytest.raises(ValueError):
            await circuit.call(failing)
        
        # Second failure - should open circuit
        with pytest.raises(ValueError):
            await circuit.call(failing)
        
        assert circuit.is_open
        
        # Next call should be rejected
        with pytest.raises(CircuitOpenError):
            await circuit.call(failing)
    
    @pytest.mark.asyncio
    async def test_circuit_half_open_recovery(self):
        """Test circuit recovers through half-open state."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            success_threshold=1,
            timeout_seconds=0.1,  # Short timeout for test
        )
        circuit = CircuitBreaker("test", config)
        
        call_count = 0
        
        async def recovers():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("fail")
            return "ok"
        
        # First call fails, opens circuit
        with pytest.raises(ValueError):
            await circuit.call(recovers)
        
        assert circuit.is_open
        
        # Wait for timeout
        await asyncio.sleep(0.2)
        
        # Check state transition - need to trigger it
        async with circuit._lock:
            await circuit._check_state_transition()
        
        assert circuit.is_half_open
        
        # Successful call should close circuit
        result = await circuit.call(recovers)
        assert result == "ok"
        assert circuit.is_closed
    
    @pytest.mark.asyncio
    async def test_decorator(self):
        """Test circuit breaker decorator."""
        circuit = CircuitBreaker("test")
        
        @circuit.protect
        async def protected():
            return "protected"
        
        result = await protected()
        assert result == "protected"
    
    @pytest.mark.asyncio
    async def test_registry(self):
        """Test circuit breaker registry."""
        registry = CircuitBreakerRegistry()
        
        circuit1 = registry.get_or_create("service-a")
        circuit2 = registry.get_or_create("service-a")
        
        assert circuit1 is circuit2
        
        assert "service-a" in registry.list_names()
        
        metrics = registry.get_all_metrics()
        assert "service-a" in metrics


class TestRetryPolicy:
    """Tests for RetryPolicy."""
    
    @pytest.mark.asyncio
    async def test_successful_no_retry(self):
        """Test successful call doesn't retry."""
        policy = RetryPolicy(RetryConfig(max_retries=3))
        
        call_count = 0
        
        async def success():
            nonlocal call_count
            call_count += 1
            return "ok"
        
        result = await policy.execute(success)
        
        assert result.success
        assert result.value == "ok"
        assert result.attempts == 1
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Test retry on transient failure."""
        policy = RetryPolicy(RetryConfig(
            max_retries=3,
            base_delay_seconds=0.01,
        ))
        
        call_count = 0
        
        async def recovers():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("fail")
            return "ok"
        
        result = await policy.execute(recovers)
        
        assert result.success
        assert result.value == "ok"
        assert result.attempts == 3
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test failure after max retries."""
        policy = RetryPolicy(RetryConfig(
            max_retries=2,
            base_delay_seconds=0.01,
        ))
        
        async def always_fails():
            raise ValueError("always fail")
        
        result = await policy.execute(always_fails)
        
        assert not result.success
        assert result.attempts == 3  # Initial + 2 retries
        assert "always fail" in result.last_exception
    
    @pytest.mark.asyncio
    async def test_fatal_exception_no_retry(self):
        """Test fatal exception stops retrying."""
        policy = RetryPolicy(RetryConfig(
            max_retries=5,
            fatal_exceptions=(KeyError,),
        ))
        
        call_count = 0
        
        async def fatal_error():
            nonlocal call_count
            call_count += 1
            raise KeyError("fatal")
        
        result = await policy.execute(fatal_error)
        
        assert not result.success
        assert call_count == 1  # No retry
    
    @pytest.mark.asyncio
    async def test_retry_decorator(self):
        """Test retry decorator."""
        call_count = 0
        
        @retry(max_retries=2, base_delay=0.01)
        async def recovers():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("fail")
            return "ok"
        
        result = await recovers()
        assert result == "ok"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Test exponential backoff delays."""
        policy = RetryPolicy(RetryConfig(
            max_retries=3,
            strategy=RetryStrategy.EXPONENTIAL,
            base_delay_seconds=0.01,
            exponential_base=2.0,
            jitter=False,
        ))
        
        async def always_fails():
            raise ValueError("fail")
        
        result = await policy.execute(always_fails)
        
        # Delays should be: 0.01, 0.02, 0.04
        assert len(result.delays) == 3
        assert abs(result.delays[0] - 0.01) < 0.001
        assert abs(result.delays[1] - 0.02) < 0.001
        assert abs(result.delays[2] - 0.04) < 0.001


class TestIntegration:
    """Integration tests for HA module."""
    
    @pytest.mark.asyncio
    async def test_leader_with_circuit_breaker(self):
        """Test leader election with circuit breaker protection."""
        backend = InMemoryLeaderBackend()
        config = ElectionConfig(
            lease_ttl_seconds=5.0,
            heartbeat_interval_seconds=0.5,
        )
        
        election = LeaderElection(backend, config)
        circuit = CircuitBreaker("leader-ops")
        
        # Protect election operations
        @circuit.protect
        async def leader_operation():
            if election.is_leader:
                return "leader action"
            return "follower"
        
        await election.start()
        await asyncio.sleep(0.1)
        
        result = await leader_operation()
        assert result == "leader action"
        
        await election.stop()
    
    @pytest.mark.asyncio
    async def test_replication_with_health_checks(self):
        """Test state replication with health monitoring."""
        backend = InMemoryReplicationBackend()
        replicator = StateReplicator(backend)
        
        checker = HealthChecker()
        
        async def replicator_health():
            if replicator.state == ReplicationState.ERROR:
                return HealthCheckResult(
                    name="replicator",
                    check_type=HealthCheck.check_type,
                    status=HealthStatus.UNHEALTHY,
                )
            return HealthCheckResult(
                name="replicator",
                check_type=HealthCheck.check_type,
                status=HealthStatus.HEALTHY,
            )
        
        checker.add_function_check("replicator", replicator_health)
        
        await replicator.start()
        
        # Set some state
        await replicator.set("key", "value")
        
        # Check health
        result = await checker.check_specific("replicator")
        assert result.status == HealthStatus.HEALTHY
        
        await replicator.stop()
