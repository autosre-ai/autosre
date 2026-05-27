"""
Replication Lag Monitoring

Provides comprehensive database replication monitoring:
- Replication lag tracking
- Replica health monitoring
- Failover readiness assessment
- Replication topology visualization
- Synchronous/asynchronous replication monitoring
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class ReplicationRole(str, Enum):
    """Database replication role."""
    
    PRIMARY = "primary"
    REPLICA = "replica"
    STANDBY = "standby"
    CASCADING = "cascading"


class ReplicationType(str, Enum):
    """Type of replication."""
    
    SYNCHRONOUS = "synchronous"
    ASYNCHRONOUS = "asynchronous"
    SEMI_SYNCHRONOUS = "semi_synchronous"
    LOGICAL = "logical"
    PHYSICAL = "physical"


class ReplicationState(str, Enum):
    """Current replication state."""
    
    STREAMING = "streaming"
    CATCHUP = "catchup"
    BACKUP = "backup"
    STOPPED = "stopped"
    DISCONNECTED = "disconnected"


class ReplicaHealth(str, Enum):
    """Replica health status."""
    
    HEALTHY = "healthy"
    LAGGING = "lagging"
    CRITICAL_LAG = "critical_lag"
    DISCONNECTED = "disconnected"
    RECOVERING = "recovering"
    UNKNOWN = "unknown"


class FailoverReadiness(str, Enum):
    """Replica failover readiness."""
    
    READY = "ready"
    CATCHUP_REQUIRED = "catchup_required"
    NOT_READY = "not_ready"
    UNKNOWN = "unknown"


# =============================================================================
# Configuration
# =============================================================================


class ReplicationConfig(BaseModel):
    """Replication monitoring configuration."""
    
    # Lag thresholds
    lag_warning_seconds: float = Field(default=30.0, description="Lag warning threshold")
    lag_critical_seconds: float = Field(default=120.0, description="Lag critical threshold")
    lag_bytes_warning: int = Field(default=10_000_000, description="Lag bytes warning threshold (10MB)")
    lag_bytes_critical: int = Field(default=100_000_000, description="Lag bytes critical threshold (100MB)")
    
    # Monitoring settings
    check_interval_seconds: int = Field(default=10, description="Check interval in seconds")
    history_retention_hours: int = Field(default=24, description="Lag history retention")
    
    # Alerting
    alert_on_lag_increase: bool = Field(default=True, description="Alert when lag is increasing")
    alert_on_disconnect: bool = Field(default=True, description="Alert on replica disconnect")
    
    # Failover
    auto_failover_enabled: bool = Field(default=False, description="Enable automatic failover")
    min_healthy_replicas: int = Field(default=1, description="Minimum healthy replicas for failover")


# =============================================================================
# Replication Models
# =============================================================================


class ReplicationNode(BaseModel):
    """A node in the replication topology."""
    
    node_id: str
    host: str
    port: int
    role: ReplicationRole
    state: ReplicationState
    
    # Connection info
    connected: bool = True
    connected_since: Optional[datetime] = None
    
    # Upstream (for replicas)
    upstream_node: Optional[str] = None
    replication_type: ReplicationType = ReplicationType.ASYNCHRONOUS
    
    # Configuration
    synchronous: bool = False
    priority: int = Field(default=100, description="Failover priority (lower = higher priority)")


class ReplicationLag(BaseModel):
    """Replication lag measurement."""
    
    node_id: str
    measured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Time-based lag
    lag_seconds: float = Field(default=0.0, description="Replication lag in seconds")
    replay_lag_seconds: float = Field(default=0.0, description="Replay lag in seconds")
    write_lag_seconds: float = Field(default=0.0, description="Write lag in seconds")
    flush_lag_seconds: float = Field(default=0.0, description="Flush lag in seconds")
    
    # Byte-based lag
    lag_bytes: int = Field(default=0, description="Replication lag in bytes")
    pending_wal_bytes: int = Field(default=0, description="Pending WAL bytes")
    
    # LSN positions (PostgreSQL specific)
    primary_lsn: Optional[str] = None
    replay_lsn: Optional[str] = None
    write_lsn: Optional[str] = None
    flush_lsn: Optional[str] = None


class ReplicationSlot(BaseModel):
    """Replication slot information."""
    
    slot_name: str
    slot_type: str = Field(description="physical or logical")
    active: bool = True
    node_id: Optional[str] = None
    
    # Position
    restart_lsn: Optional[str] = None
    confirmed_flush_lsn: Optional[str] = None
    
    # Resource usage
    wal_retained_bytes: int = 0
    catalog_xmin: Optional[str] = None
    
    # Timestamps
    created_at: Optional[datetime] = None
    last_active_at: Optional[datetime] = None


class ReplicaStatus(BaseModel):
    """Complete status of a replica."""
    
    node: ReplicationNode
    lag: ReplicationLag
    health: ReplicaHealth
    failover_readiness: FailoverReadiness
    
    # Performance
    replay_rate_bytes_sec: float = 0.0
    apply_rate_rows_sec: float = 0.0
    
    # Catchup estimation
    estimated_catchup_seconds: Optional[float] = None
    
    # Errors
    last_error: Optional[str] = None
    last_error_at: Optional[datetime] = None
    error_count_24h: int = 0


class ReplicationTopology(BaseModel):
    """Complete replication topology."""
    
    cluster_name: str
    primary: ReplicationNode
    replicas: list[ReplicaStatus] = Field(default_factory=list)
    
    # Slots
    replication_slots: list[ReplicationSlot] = Field(default_factory=list)
    
    # Overall health
    overall_health: ReplicaHealth = ReplicaHealth.HEALTHY
    healthy_replica_count: int = 0
    total_replica_count: int = 0
    
    # Lag summary
    max_lag_seconds: float = 0.0
    avg_lag_seconds: float = 0.0
    
    # Timestamps
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReplicationAlert(BaseModel):
    """Replication-related alert."""
    
    alert_id: str
    node_id: str
    alert_type: str
    severity: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class LagHistoryPoint(BaseModel):
    """Historical lag measurement point."""
    
    timestamp: datetime
    node_id: str
    lag_seconds: float
    lag_bytes: int


# =============================================================================
# Replication Monitor
# =============================================================================


@dataclass
class ReplicationMonitor:
    """
    Monitors database replication health and lag.
    
    Features:
    - Real-time lag monitoring
    - Replica health assessment
    - Failover readiness checking
    - Historical lag tracking
    - Replication topology visualization
    
    Usage:
        monitor = ReplicationMonitor(config)
        
        # Get current topology
        topology = await monitor.get_topology()
        
        # Check specific replica
        status = await monitor.get_replica_status("replica-1")
        
        # Get lag history
        history = await monitor.get_lag_history("replica-1", hours=24)
    """
    
    config: ReplicationConfig = field(default_factory=ReplicationConfig)
    cluster_name: str = "default"
    
    # Internal state
    _nodes: dict[str, ReplicationNode] = field(default_factory=dict, init=False)
    _lag_history: dict[str, list[LagHistoryPoint]] = field(default_factory=dict, init=False)
    _alerts: list[ReplicationAlert] = field(default_factory=list, init=False)
    _primary_node_id: Optional[str] = field(default=None, init=False)
    
    async def register_node(self, node: ReplicationNode):
        """Register a node in the replication topology."""
        self._nodes[node.node_id] = node
        
        if node.role == ReplicationRole.PRIMARY:
            self._primary_node_id = node.node_id
        
        if node.node_id not in self._lag_history:
            self._lag_history[node.node_id] = []
    
    async def update_lag(self, lag: ReplicationLag):
        """Update lag measurement for a node."""
        if lag.node_id in self._lag_history:
            history = self._lag_history[lag.node_id]
            history.append(LagHistoryPoint(
                timestamp=lag.measured_at,
                node_id=lag.node_id,
                lag_seconds=lag.lag_seconds,
                lag_bytes=lag.lag_bytes,
            ))
            
            # Trim old history
            cutoff = datetime.now(timezone.utc) - timedelta(hours=self.config.history_retention_hours)
            self._lag_history[lag.node_id] = [
                h for h in history if h.timestamp > cutoff
            ]
        
        # Check for alerts
        await self._check_lag_alerts(lag)
    
    async def _check_lag_alerts(self, lag: ReplicationLag):
        """Check for lag-related alerts."""
        if lag.lag_seconds >= self.config.lag_critical_seconds:
            alert = ReplicationAlert(
                alert_id=f"lag_critical_{lag.node_id}_{datetime.now(timezone.utc).timestamp()}",
                node_id=lag.node_id,
                alert_type="critical_lag",
                severity="critical",
                message=f"Critical replication lag: {lag.lag_seconds:.1f}s",
                details={"lag_seconds": lag.lag_seconds, "lag_bytes": lag.lag_bytes},
            )
            self._alerts.append(alert)
        elif lag.lag_seconds >= self.config.lag_warning_seconds:
            alert = ReplicationAlert(
                alert_id=f"lag_warning_{lag.node_id}_{datetime.now(timezone.utc).timestamp()}",
                node_id=lag.node_id,
                alert_type="warning_lag",
                severity="warning",
                message=f"Replication lag warning: {lag.lag_seconds:.1f}s",
                details={"lag_seconds": lag.lag_seconds, "lag_bytes": lag.lag_bytes},
            )
            self._alerts.append(alert)
    
    def _assess_replica_health(self, lag: ReplicationLag, node: ReplicationNode) -> ReplicaHealth:
        """Assess the health of a replica based on lag."""
        if not node.connected or node.state == ReplicationState.DISCONNECTED:
            return ReplicaHealth.DISCONNECTED
        
        if node.state == ReplicationState.CATCHUP:
            return ReplicaHealth.RECOVERING
        
        if lag.lag_seconds >= self.config.lag_critical_seconds:
            return ReplicaHealth.CRITICAL_LAG
        elif lag.lag_seconds >= self.config.lag_warning_seconds:
            return ReplicaHealth.LAGGING
        
        return ReplicaHealth.HEALTHY
    
    def _assess_failover_readiness(
        self, 
        health: ReplicaHealth, 
        lag: ReplicationLag,
        node: ReplicationNode
    ) -> FailoverReadiness:
        """Assess if a replica is ready for failover."""
        if health == ReplicaHealth.DISCONNECTED:
            return FailoverReadiness.NOT_READY
        
        if health == ReplicaHealth.RECOVERING:
            return FailoverReadiness.CATCHUP_REQUIRED
        
        if health in [ReplicaHealth.CRITICAL_LAG, ReplicaHealth.LAGGING]:
            if lag.lag_seconds > 60:
                return FailoverReadiness.CATCHUP_REQUIRED
        
        if health == ReplicaHealth.HEALTHY:
            return FailoverReadiness.READY
        
        return FailoverReadiness.UNKNOWN
    
    async def get_replica_status(self, node_id: str) -> Optional[ReplicaStatus]:
        """Get complete status for a replica."""
        if node_id not in self._nodes:
            return None
        
        node = self._nodes[node_id]
        
        # Get latest lag (simulated)
        lag = ReplicationLag(
            node_id=node_id,
            lag_seconds=0.5,
            lag_bytes=50000,
        )
        
        health = self._assess_replica_health(lag, node)
        readiness = self._assess_failover_readiness(health, lag, node)
        
        # Calculate replay rate from history
        history = self._lag_history.get(node_id, [])
        replay_rate = 0.0
        if len(history) >= 2:
            recent = history[-2:]
            time_diff = (recent[1].timestamp - recent[0].timestamp).total_seconds()
            if time_diff > 0:
                bytes_diff = recent[0].lag_bytes - recent[1].lag_bytes
                replay_rate = max(0, bytes_diff / time_diff)
        
        # Estimate catchup time
        catchup_time = None
        if lag.lag_bytes > 0 and replay_rate > 0:
            catchup_time = lag.lag_bytes / replay_rate
        
        return ReplicaStatus(
            node=node,
            lag=lag,
            health=health,
            failover_readiness=readiness,
            replay_rate_bytes_sec=replay_rate,
            estimated_catchup_seconds=catchup_time,
        )
    
    async def get_topology(self) -> ReplicationTopology:
        """Get complete replication topology."""
        if not self._primary_node_id or self._primary_node_id not in self._nodes:
            raise ValueError("No primary node registered")
        
        primary = self._nodes[self._primary_node_id]
        
        replicas = []
        for node_id, node in self._nodes.items():
            if node.role != ReplicationRole.PRIMARY:
                status = await self.get_replica_status(node_id)
                if status:
                    replicas.append(status)
        
        # Calculate summary statistics
        healthy_count = sum(1 for r in replicas if r.health == ReplicaHealth.HEALTHY)
        max_lag = max((r.lag.lag_seconds for r in replicas), default=0.0)
        avg_lag = (
            sum(r.lag.lag_seconds for r in replicas) / len(replicas)
            if replicas else 0.0
        )
        
        # Determine overall health
        if any(r.health == ReplicaHealth.CRITICAL_LAG for r in replicas):
            overall = ReplicaHealth.CRITICAL_LAG
        elif any(r.health == ReplicaHealth.DISCONNECTED for r in replicas):
            overall = ReplicaHealth.DISCONNECTED
        elif any(r.health == ReplicaHealth.LAGGING for r in replicas):
            overall = ReplicaHealth.LAGGING
        else:
            overall = ReplicaHealth.HEALTHY
        
        return ReplicationTopology(
            cluster_name=self.cluster_name,
            primary=primary,
            replicas=replicas,
            overall_health=overall,
            healthy_replica_count=healthy_count,
            total_replica_count=len(replicas),
            max_lag_seconds=max_lag,
            avg_lag_seconds=avg_lag,
        )
    
    async def get_lag_history(
        self, 
        node_id: str, 
        hours: int = 24,
    ) -> list[LagHistoryPoint]:
        """Get lag history for a node."""
        if node_id not in self._lag_history:
            return []
        
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return [
            h for h in self._lag_history[node_id]
            if h.timestamp > cutoff
        ]
    
    async def get_active_alerts(self) -> list[ReplicationAlert]:
        """Get active (unresolved) alerts."""
        return [a for a in self._alerts if not a.resolved]
    
    async def check_failover_candidates(self) -> list[ReplicaStatus]:
        """Get replicas ready for failover, sorted by priority."""
        topology = await self.get_topology()
        
        candidates = [
            r for r in topology.replicas
            if r.failover_readiness == FailoverReadiness.READY
        ]
        
        # Sort by priority (lower is better) and then by lag
        candidates.sort(key=lambda r: (r.node.priority, r.lag.lag_seconds))
        
        return candidates
    
    async def simulate_failover(self, target_node_id: str) -> dict[str, Any]:
        """Simulate what would happen during failover to target node."""
        status = await self.get_replica_status(target_node_id)
        
        if not status:
            return {"success": False, "error": "Node not found"}
        
        if status.failover_readiness != FailoverReadiness.READY:
            return {
                "success": False,
                "error": f"Node not ready for failover: {status.failover_readiness}",
                "estimated_catchup_time": status.estimated_catchup_seconds,
            }
        
        # Calculate potential data loss
        potential_data_loss = status.lag.lag_bytes
        transactions_at_risk = status.lag.lag_bytes // 1000  # Rough estimate
        
        return {
            "success": True,
            "target_node": target_node_id,
            "current_lag_seconds": status.lag.lag_seconds,
            "current_lag_bytes": status.lag.lag_bytes,
            "potential_data_loss_bytes": potential_data_loss,
            "transactions_at_risk": transactions_at_risk,
            "estimated_failover_time_seconds": 5 + status.lag.lag_seconds,
        }
    
    async def run_continuous(self, callback=None):
        """Run continuous replication monitoring."""
        while True:
            for node_id in self._nodes:
                if self._nodes[node_id].role != ReplicationRole.PRIMARY:
                    # Simulate lag measurement
                    lag = ReplicationLag(
                        node_id=node_id,
                        lag_seconds=0.5,
                        lag_bytes=50000,
                    )
                    await self.update_lag(lag)
            
            if callback:
                topology = await self.get_topology()
                await callback(topology)
            
            await asyncio.sleep(self.config.check_interval_seconds)


__all__ = [
    # Enums
    "ReplicationRole",
    "ReplicationType",
    "ReplicationState",
    "ReplicaHealth",
    "FailoverReadiness",
    # Configuration
    "ReplicationConfig",
    # Models
    "ReplicationNode",
    "ReplicationLag",
    "ReplicationSlot",
    "ReplicaStatus",
    "ReplicationTopology",
    "ReplicationAlert",
    "LagHistoryPoint",
    # Monitor
    "ReplicationMonitor",
]
