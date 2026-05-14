"""High Availability module for AutoSRE V2.

Provides fault-tolerance and distributed systems capabilities:
- Leader election for distributed coordination
- State replication across nodes
- Deep health checks with dependencies
- Circuit breakers for fault isolation
- Configurable retry policies
"""

from autosre.ha.leader_election import (
    LeaderElection,
    LeaderElectionBackend,
    LeaderState,
    ElectionConfig,
    LeaderInfo,
    RedisLeaderBackend,
    ConsulLeaderBackend,
    EtcdLeaderBackend,
    ZookeeperLeaderBackend,
    InMemoryLeaderBackend,
)
from autosre.ha.state_replication import (
    StateReplicator,
    ReplicationConfig,
    ReplicationState,
    StateEntry,
    ConflictResolution,
    ReplicationBackend,
    RedisReplicationBackend,
    PostgresReplicationBackend,
)
from autosre.ha.health_checker import (
    HealthChecker,
    HealthCheck,
    HealthCheckResult,
    HealthStatus,
    DependencyHealth,
    HealthConfig,
    ComponentHealth,
)
from autosre.ha.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitBreakerError,
    CircuitOpenError,
)
from autosre.ha.retry_policy import (
    RetryPolicy,
    RetryConfig,
    RetryStrategy,
    RetryResult,
    ExponentialBackoff,
    LinearBackoff,
    ConstantBackoff,
    DecorrelatedJitter,
    retry,
    async_retry,
)

__all__ = [
    # Leader Election
    "LeaderElection",
    "LeaderElectionBackend",
    "LeaderState",
    "ElectionConfig",
    "LeaderInfo",
    "RedisLeaderBackend",
    "ConsulLeaderBackend",
    "EtcdLeaderBackend",
    "ZookeeperLeaderBackend",
    "InMemoryLeaderBackend",
    # State Replication
    "StateReplicator",
    "ReplicationConfig",
    "ReplicationState",
    "StateEntry",
    "ConflictResolution",
    "ReplicationBackend",
    "RedisReplicationBackend",
    "PostgresReplicationBackend",
    # Health Checker
    "HealthChecker",
    "HealthCheck",
    "HealthCheckResult",
    "HealthStatus",
    "DependencyHealth",
    "HealthConfig",
    "ComponentHealth",
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitState",
    "CircuitBreakerConfig",
    "CircuitBreakerRegistry",
    "CircuitBreakerError",
    "CircuitOpenError",
    # Retry Policy
    "RetryPolicy",
    "RetryConfig",
    "RetryStrategy",
    "RetryResult",
    "ExponentialBackoff",
    "LinearBackoff",
    "ConstantBackoff",
    "DecorrelatedJitter",
    "retry",
    "async_retry",
]
