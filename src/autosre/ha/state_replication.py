"""State Replication for AutoSRE V2 High Availability.

Provides distributed state replication for consistent state across nodes:
- Multi-node state synchronization
- Conflict resolution strategies
- Change tracking and versioning
- Eventual consistency with ordering guarantees
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, Set, TypeVar, Awaitable
from uuid import uuid4

from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class ConflictResolution(str, Enum):
    """Strategies for resolving conflicting writes."""
    
    LAST_WRITE_WINS = "last_write_wins"  # Most recent timestamp wins
    FIRST_WRITE_WINS = "first_write_wins"  # Earliest timestamp wins
    MERGE = "merge"  # Attempt to merge changes
    CUSTOM = "custom"  # Use custom resolver


class ReplicationState(str, Enum):
    """State of replication."""
    
    IDLE = "idle"  # Not replicating
    SYNCING = "syncing"  # Active synchronization
    SYNCHRONIZED = "synchronized"  # All nodes in sync
    DIVERGED = "diverged"  # Nodes have diverged
    ERROR = "error"  # Replication error


@dataclass
class ReplicationConfig:
    """Configuration for state replication."""
    
    # Node identity
    node_id: str = field(default_factory=lambda: str(uuid4()))
    cluster_name: str = "autosre"
    
    # Replication behavior
    conflict_resolution: ConflictResolution = ConflictResolution.LAST_WRITE_WINS
    sync_interval_seconds: float = 5.0
    batch_size: int = 100
    
    # Versioning
    use_vector_clocks: bool = True
    max_version_history: int = 100
    
    # Reliability
    max_sync_retries: int = 3
    retry_delay_seconds: float = 1.0
    
    # Compression
    compress_large_values: bool = True
    compression_threshold_bytes: int = 1024


class VectorClock(BaseModel):
    """Vector clock for tracking causality."""
    
    clocks: Dict[str, int] = Field(default_factory=dict)
    
    def increment(self, node_id: str) -> "VectorClock":
        """Increment clock for a node."""
        new_clocks = dict(self.clocks)
        new_clocks[node_id] = new_clocks.get(node_id, 0) + 1
        return VectorClock(clocks=new_clocks)
    
    def merge(self, other: "VectorClock") -> "VectorClock":
        """Merge with another vector clock."""
        all_nodes = set(self.clocks.keys()) | set(other.clocks.keys())
        merged = {
            node: max(self.clocks.get(node, 0), other.clocks.get(node, 0))
            for node in all_nodes
        }
        return VectorClock(clocks=merged)
    
    def happens_before(self, other: "VectorClock") -> bool:
        """Check if this clock happens-before another."""
        if not self.clocks:
            return bool(other.clocks)
        
        at_least_one_less = False
        
        for node in set(self.clocks.keys()) | set(other.clocks.keys()):
            my_time = self.clocks.get(node, 0)
            other_time = other.clocks.get(node, 0)
            
            if my_time > other_time:
                return False
            if my_time < other_time:
                at_least_one_less = True
        
        return at_least_one_less
    
    def concurrent_with(self, other: "VectorClock") -> bool:
        """Check if this clock is concurrent with another."""
        return not self.happens_before(other) and not other.happens_before(self)


class StateEntry(BaseModel, Generic[T]):
    """An entry in the replicated state store."""
    
    key: str
    value: Any  # Will be T at runtime
    
    # Versioning
    version: int = 1
    vector_clock: VectorClock = Field(default_factory=VectorClock)
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = ""
    updated_by: str = ""
    
    # Checksum for integrity
    checksum: Optional[str] = None
    
    # TTL
    expires_at: Optional[datetime] = None
    
    # Replication tracking
    replicated_to: Set[str] = Field(default_factory=set)
    pending_replication: bool = True
    
    def compute_checksum(self) -> str:
        """Compute checksum of the value."""
        value_bytes = json.dumps(self.value, sort_keys=True, default=str).encode()
        return hashlib.sha256(value_bytes).hexdigest()
    
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    def mark_replicated(self, node_id: str) -> None:
        """Mark as replicated to a node."""
        self.replicated_to.add(node_id)


class StateChange(BaseModel):
    """A change to be replicated."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    operation: str  # set, delete, update
    key: str
    value: Optional[Any] = None
    previous_version: int = 0
    new_version: int = 1
    vector_clock: VectorClock = Field(default_factory=VectorClock)
    
    source_node: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # For conflict detection
    checksum: Optional[str] = None
    
    def conflicts_with(self, other: "StateChange") -> bool:
        """Check if this change conflicts with another."""
        if self.key != other.key:
            return False
        
        return self.vector_clock.concurrent_with(other.vector_clock)


class ReplicationBackend(ABC):
    """Abstract backend for state replication."""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[StateEntry]:
        """Get state entry."""
        ...
    
    @abstractmethod
    async def set(self, entry: StateEntry) -> None:
        """Set state entry."""
        ...
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete state entry."""
        ...
    
    @abstractmethod
    async def list_keys(self, prefix: str = "") -> List[str]:
        """List all keys with optional prefix."""
        ...
    
    @abstractmethod
    async def get_changes_since(
        self,
        version: int,
        limit: int = 100,
    ) -> List[StateChange]:
        """Get changes since a version."""
        ...
    
    @abstractmethod
    async def record_change(self, change: StateChange) -> None:
        """Record a change for replication."""
        ...
    
    @abstractmethod
    async def get_nodes(self) -> List[str]:
        """Get list of peer nodes."""
        ...
    
    @abstractmethod
    async def register_node(self, node_id: str, metadata: Dict[str, Any]) -> None:
        """Register this node with peers."""
        ...
    
    @abstractmethod
    async def close(self) -> None:
        """Close backend connections."""
        ...


class InMemoryReplicationBackend(ReplicationBackend):
    """In-memory backend for testing."""
    
    _state: Dict[str, StateEntry] = {}
    _changes: List[StateChange] = []
    _nodes: Dict[str, Dict[str, Any]] = {}
    _lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[StateEntry]:
        return self._state.get(key)
    
    async def set(self, entry: StateEntry) -> None:
        async with self._lock:
            self._state[entry.key] = entry
    
    async def delete(self, key: str) -> bool:
        async with self._lock:
            if key in self._state:
                del self._state[key]
                return True
            return False
    
    async def list_keys(self, prefix: str = "") -> List[str]:
        return [k for k in self._state.keys() if k.startswith(prefix)]
    
    async def get_changes_since(
        self,
        version: int,
        limit: int = 100,
    ) -> List[StateChange]:
        return [c for c in self._changes if c.new_version > version][:limit]
    
    async def record_change(self, change: StateChange) -> None:
        async with self._lock:
            self._changes.append(change)
    
    async def get_nodes(self) -> List[str]:
        return list(self._nodes.keys())
    
    async def register_node(self, node_id: str, metadata: Dict[str, Any]) -> None:
        async with self._lock:
            self._nodes[node_id] = metadata
    
    async def close(self) -> None:
        pass


class RedisReplicationBackend(ReplicationBackend):
    """Redis-based replication backend using Redis Streams."""
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        key_prefix: str = "autosre:state:",
        stream_key: str = "autosre:changes",
    ):
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self.stream_key = stream_key
        self._redis: Optional[Any] = None
    
    async def _get_redis(self):
        """Get or create Redis connection."""
        if self._redis is None:
            try:
                import redis.asyncio as redis
                self._redis = redis.from_url(self.redis_url)
            except ImportError:
                raise RuntimeError("redis package required")
        return self._redis
    
    async def get(self, key: str) -> Optional[StateEntry]:
        redis = await self._get_redis()
        full_key = f"{self.key_prefix}{key}"
        
        data = await redis.get(full_key)
        if not data:
            return None
        
        return StateEntry.model_validate_json(data)
    
    async def set(self, entry: StateEntry) -> None:
        redis = await self._get_redis()
        full_key = f"{self.key_prefix}{entry.key}"
        
        await redis.set(
            full_key,
            entry.model_dump_json(),
        )
        
        if entry.expires_at:
            ttl = (entry.expires_at - datetime.now(timezone.utc)).total_seconds()
            if ttl > 0:
                await redis.expire(full_key, int(ttl))
    
    async def delete(self, key: str) -> bool:
        redis = await self._get_redis()
        full_key = f"{self.key_prefix}{key}"
        
        result = await redis.delete(full_key)
        return result > 0
    
    async def list_keys(self, prefix: str = "") -> List[str]:
        redis = await self._get_redis()
        pattern = f"{self.key_prefix}{prefix}*"
        
        keys = await redis.keys(pattern)
        prefix_len = len(self.key_prefix)
        return [k.decode()[prefix_len:] for k in keys]
    
    async def get_changes_since(
        self,
        version: int,
        limit: int = 100,
    ) -> List[StateChange]:
        redis = await self._get_redis()
        
        # Read from stream
        entries = await redis.xread(
            {self.stream_key: str(version)},
            count=limit,
            block=0,
        )
        
        changes = []
        for stream, messages in entries:
            for msg_id, fields in messages:
                change = StateChange.model_validate_json(fields[b"data"])
                changes.append(change)
        
        return changes
    
    async def record_change(self, change: StateChange) -> None:
        redis = await self._get_redis()
        
        await redis.xadd(
            self.stream_key,
            {"data": change.model_dump_json()},
        )
    
    async def get_nodes(self) -> List[str]:
        redis = await self._get_redis()
        
        nodes = await redis.smembers(f"{self.key_prefix}nodes")
        return [n.decode() for n in nodes]
    
    async def register_node(self, node_id: str, metadata: Dict[str, Any]) -> None:
        redis = await self._get_redis()
        
        await redis.sadd(f"{self.key_prefix}nodes", node_id)
        await redis.hset(
            f"{self.key_prefix}node:{node_id}",
            mapping={
                "metadata": json.dumps(metadata),
                "last_seen": datetime.now(timezone.utc).isoformat(),
            },
        )
    
    async def close(self) -> None:
        if self._redis:
            await self._redis.close()
            self._redis = None


class PostgresReplicationBackend(ReplicationBackend):
    """PostgreSQL-based replication backend using LISTEN/NOTIFY."""
    
    def __init__(
        self,
        dsn: str = "postgresql://localhost/autosre",
        table_prefix: str = "autosre_",
    ):
        self.dsn = dsn
        self.table_prefix = table_prefix
        self._pool: Optional[Any] = None
    
    async def _get_pool(self):
        """Get or create connection pool."""
        if self._pool is None:
            try:
                import asyncpg
                self._pool = await asyncpg.create_pool(self.dsn)
            except ImportError:
                raise RuntimeError("asyncpg package required")
        return self._pool
    
    async def _ensure_tables(self) -> None:
        """Ensure required tables exist."""
        pool = await self._get_pool()
        
        async with pool.acquire() as conn:
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_prefix}state (
                    key TEXT PRIMARY KEY,
                    value JSONB NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    vector_clock JSONB NOT NULL DEFAULT '{{}}',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    expires_at TIMESTAMPTZ,
                    checksum TEXT
                )
            """)
            
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_prefix}changes (
                    id TEXT PRIMARY KEY,
                    operation TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value JSONB,
                    previous_version INTEGER,
                    new_version INTEGER NOT NULL,
                    vector_clock JSONB NOT NULL,
                    source_node TEXT NOT NULL,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_prefix}nodes (
                    node_id TEXT PRIMARY KEY,
                    metadata JSONB NOT NULL DEFAULT '{{}}',
                    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
    
    async def get(self, key: str) -> Optional[StateEntry]:
        pool = await self._get_pool()
        
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {self.table_prefix}state WHERE key = $1",
                key,
            )
            
            if not row:
                return None
            
            return StateEntry(
                key=row["key"],
                value=row["value"],
                version=row["version"],
                vector_clock=VectorClock(clocks=row["vector_clock"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                expires_at=row["expires_at"],
                checksum=row["checksum"],
            )
    
    async def set(self, entry: StateEntry) -> None:
        pool = await self._get_pool()
        
        async with pool.acquire() as conn:
            await conn.execute(f"""
                INSERT INTO {self.table_prefix}state
                (key, value, version, vector_clock, created_at, updated_at, expires_at, checksum)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (key) DO UPDATE SET
                    value = EXCLUDED.value,
                    version = EXCLUDED.version,
                    vector_clock = EXCLUDED.vector_clock,
                    updated_at = EXCLUDED.updated_at,
                    expires_at = EXCLUDED.expires_at,
                    checksum = EXCLUDED.checksum
            """,
                entry.key,
                json.dumps(entry.value),
                entry.version,
                json.dumps(entry.vector_clock.clocks),
                entry.created_at,
                entry.updated_at,
                entry.expires_at,
                entry.checksum,
            )
    
    async def delete(self, key: str) -> bool:
        pool = await self._get_pool()
        
        async with pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM {self.table_prefix}state WHERE key = $1",
                key,
            )
            return "DELETE 1" in result
    
    async def list_keys(self, prefix: str = "") -> List[str]:
        pool = await self._get_pool()
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT key FROM {self.table_prefix}state WHERE key LIKE $1",
                f"{prefix}%",
            )
            return [row["key"] for row in rows]
    
    async def get_changes_since(
        self,
        version: int,
        limit: int = 100,
    ) -> List[StateChange]:
        pool = await self._get_pool()
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(f"""
                SELECT * FROM {self.table_prefix}changes
                WHERE new_version > $1
                ORDER BY timestamp
                LIMIT $2
            """, version, limit)
            
            return [
                StateChange(
                    id=row["id"],
                    operation=row["operation"],
                    key=row["key"],
                    value=row["value"],
                    previous_version=row["previous_version"],
                    new_version=row["new_version"],
                    vector_clock=VectorClock(clocks=row["vector_clock"]),
                    source_node=row["source_node"],
                    timestamp=row["timestamp"],
                )
                for row in rows
            ]
    
    async def record_change(self, change: StateChange) -> None:
        pool = await self._get_pool()
        
        async with pool.acquire() as conn:
            await conn.execute(f"""
                INSERT INTO {self.table_prefix}changes
                (id, operation, key, value, previous_version, new_version,
                 vector_clock, source_node, timestamp)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
                change.id,
                change.operation,
                change.key,
                json.dumps(change.value) if change.value else None,
                change.previous_version,
                change.new_version,
                json.dumps(change.vector_clock.clocks),
                change.source_node,
                change.timestamp,
            )
            
            # Notify listeners
            await conn.execute(
                f"NOTIFY {self.table_prefix}changes, $1",
                change.id,
            )
    
    async def get_nodes(self) -> List[str]:
        pool = await self._get_pool()
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT node_id FROM {self.table_prefix}nodes"
            )
            return [row["node_id"] for row in rows]
    
    async def register_node(self, node_id: str, metadata: Dict[str, Any]) -> None:
        pool = await self._get_pool()
        
        async with pool.acquire() as conn:
            await conn.execute(f"""
                INSERT INTO {self.table_prefix}nodes (node_id, metadata, last_seen)
                VALUES ($1, $2, NOW())
                ON CONFLICT (node_id) DO UPDATE SET
                    metadata = EXCLUDED.metadata,
                    last_seen = NOW()
            """, node_id, json.dumps(metadata))
    
    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None


# Type for conflict resolvers
ConflictResolver = Callable[[StateEntry, StateEntry], Awaitable[StateEntry]]


class StateReplicator:
    """
    Distributed state replication manager.
    
    Provides multi-node state synchronization with:
    - Automatic conflict detection and resolution
    - Vector clocks for causality tracking
    - Change propagation via pub/sub
    - Configurable consistency guarantees
    
    Example:
        backend = RedisReplicationBackend("redis://localhost:6379")
        config = ReplicationConfig(node_id="node-1")
        
        replicator = StateReplicator(backend, config)
        await replicator.start()
        
        # Set state
        await replicator.set("config:feature_flags", {"new_ui": True})
        
        # Get state
        flags = await replicator.get("config:feature_flags")
        
        await replicator.stop()
    """
    
    def __init__(
        self,
        backend: ReplicationBackend,
        config: Optional[ReplicationConfig] = None,
    ):
        """Initialize StateReplicator.
        
        Args:
            backend: Storage backend for state
            config: Replication configuration
        """
        self.backend = backend
        self.config = config or ReplicationConfig()
        
        self._state = ReplicationState.IDLE
        self._local_clock = VectorClock()
        self._version = 0
        
        self._sync_task: Optional[asyncio.Task] = None
        self._running = False
        
        self._conflict_resolver: Optional[ConflictResolver] = None
        self._change_listeners: List[Callable[[StateChange], Awaitable[None]]] = []
    
    @property
    def node_id(self) -> str:
        """Get this node's ID."""
        return self.config.node_id
    
    @property
    def state(self) -> ReplicationState:
        """Get replication state."""
        return self._state
    
    @property
    def version(self) -> int:
        """Get current version."""
        return self._version
    
    def set_conflict_resolver(self, resolver: ConflictResolver) -> None:
        """Set custom conflict resolver.
        
        Args:
            resolver: Async function that takes two conflicting entries
                     and returns the resolved entry
        """
        self._conflict_resolver = resolver
    
    def on_change(
        self,
        listener: Callable[[StateChange], Awaitable[None]],
    ) -> None:
        """Register change listener.
        
        Args:
            listener: Async function called when state changes
        """
        self._change_listeners.append(listener)
    
    async def start(self) -> None:
        """Start replication."""
        if self._running:
            return
        
        self._running = True
        self._state = ReplicationState.SYNCING
        
        # Register this node
        await self.backend.register_node(
            self.node_id,
            {
                "started_at": datetime.now(timezone.utc).isoformat(),
                "cluster": self.config.cluster_name,
            },
        )
        
        logger.info(
            "Starting state replication",
            node_id=self.node_id,
            cluster=self.config.cluster_name,
        )
        
        # Start sync loop
        self._sync_task = asyncio.create_task(self._sync_loop())
    
    async def stop(self) -> None:
        """Stop replication."""
        if not self._running:
            return
        
        self._running = False
        
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
            self._sync_task = None
        
        self._state = ReplicationState.IDLE
        
        logger.info(
            "Stopped state replication",
            node_id=self.node_id,
        )
    
    async def get(self, key: str) -> Optional[Any]:
        """Get state value.
        
        Args:
            key: State key
            
        Returns:
            Value or None
        """
        entry = await self.backend.get(key)
        
        if not entry:
            return None
        
        if entry.is_expired():
            await self.backend.delete(key)
            return None
        
        return entry.value
    
    async def get_entry(self, key: str) -> Optional[StateEntry]:
        """Get full state entry with metadata.
        
        Args:
            key: State key
            
        Returns:
            StateEntry or None
        """
        entry = await self.backend.get(key)
        
        if entry and entry.is_expired():
            await self.backend.delete(key)
            return None
        
        return entry
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[float] = None,
    ) -> StateEntry:
        """Set state value.
        
        Args:
            key: State key
            value: Value to set
            ttl_seconds: Optional TTL
            
        Returns:
            Created/updated entry
        """
        # Get existing entry for version
        existing = await self.backend.get(key)
        
        # Update vector clock
        self._local_clock = self._local_clock.increment(self.node_id)
        
        # Calculate new version
        if existing:
            version = existing.version + 1
            vector_clock = self._local_clock.merge(existing.vector_clock)
        else:
            version = 1
            vector_clock = self._local_clock
        
        # Create entry
        entry = StateEntry(
            key=key,
            value=value,
            version=version,
            vector_clock=vector_clock,
            created_at=existing.created_at if existing else datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            created_by=existing.created_by if existing else self.node_id,
            updated_by=self.node_id,
            expires_at=(
                datetime.now(timezone.utc) + 
                __import__('datetime').timedelta(seconds=ttl_seconds)
                if ttl_seconds else None
            ),
        )
        entry.checksum = entry.compute_checksum()
        
        # Save entry
        await self.backend.set(entry)
        
        # Record change for replication
        change = StateChange(
            operation="set",
            key=key,
            value=value,
            previous_version=existing.version if existing else 0,
            new_version=version,
            vector_clock=vector_clock,
            source_node=self.node_id,
        )
        await self.backend.record_change(change)
        
        # Update local version
        self._version = max(self._version, version)
        
        # Notify listeners
        await self._notify_change(change)
        
        logger.debug(
            "Set state",
            key=key,
            version=version,
            node_id=self.node_id,
        )
        
        return entry
    
    async def delete(self, key: str) -> bool:
        """Delete state entry.
        
        Args:
            key: State key
            
        Returns:
            True if deleted
        """
        existing = await self.backend.get(key)
        
        if not existing:
            return False
        
        # Update vector clock
        self._local_clock = self._local_clock.increment(self.node_id)
        
        # Delete entry
        await self.backend.delete(key)
        
        # Record change
        change = StateChange(
            operation="delete",
            key=key,
            previous_version=existing.version,
            new_version=existing.version + 1,
            vector_clock=self._local_clock,
            source_node=self.node_id,
        )
        await self.backend.record_change(change)
        
        # Notify listeners
        await self._notify_change(change)
        
        logger.debug(
            "Deleted state",
            key=key,
            node_id=self.node_id,
        )
        
        return True
    
    async def list_keys(self, prefix: str = "") -> List[str]:
        """List state keys.
        
        Args:
            prefix: Optional key prefix
            
        Returns:
            List of keys
        """
        return await self.backend.list_keys(prefix)
    
    async def get_all(self, prefix: str = "") -> Dict[str, Any]:
        """Get all state values.
        
        Args:
            prefix: Optional key prefix
            
        Returns:
            Dict of key -> value
        """
        keys = await self.list_keys(prefix)
        result = {}
        
        for key in keys:
            value = await self.get(key)
            if value is not None:
                result[key] = value
        
        return result
    
    async def compare_and_set(
        self,
        key: str,
        expected_version: int,
        value: Any,
    ) -> tuple[bool, StateEntry]:
        """Atomic compare-and-set operation.
        
        Args:
            key: State key
            expected_version: Expected current version
            value: New value
            
        Returns:
            Tuple of (success, entry)
        """
        existing = await self.backend.get(key)
        
        if existing and existing.version != expected_version:
            return False, existing
        
        if not existing and expected_version != 0:
            return False, None
        
        entry = await self.set(key, value)
        return True, entry
    
    async def sync_with_peer(self, peer_id: str) -> int:
        """Manually sync with a specific peer.
        
        Args:
            peer_id: Peer node ID
            
        Returns:
            Number of changes applied
        """
        # Get changes from peer (would need RPC in real implementation)
        changes = await self.backend.get_changes_since(
            self._version,
            self.config.batch_size,
        )
        
        applied = 0
        for change in changes:
            if change.source_node != self.node_id:
                await self._apply_change(change)
                applied += 1
        
        return applied
    
    async def _sync_loop(self) -> None:
        """Main sync loop."""
        while self._running:
            try:
                # Get changes since our version
                changes = await self.backend.get_changes_since(
                    self._version,
                    self.config.batch_size,
                )
                
                # Apply remote changes
                for change in changes:
                    if change.source_node != self.node_id:
                        await self._apply_change(change)
                
                # Update state
                if not changes:
                    self._state = ReplicationState.SYNCHRONIZED
                else:
                    self._state = ReplicationState.SYNCING
                
                await asyncio.sleep(self.config.sync_interval_seconds)
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self._state = ReplicationState.ERROR
                logger.error(
                    "Sync error",
                    error=str(e),
                    node_id=self.node_id,
                )
                await asyncio.sleep(self.config.retry_delay_seconds)
    
    async def _apply_change(self, change: StateChange) -> None:
        """Apply a change from another node."""
        existing = await self.backend.get(change.key)
        
        # Check for conflicts
        if existing and change.vector_clock.concurrent_with(existing.vector_clock):
            # Resolve conflict
            resolved = await self._resolve_conflict(existing, change)
            
            if resolved:
                await self.backend.set(resolved)
                logger.info(
                    "Resolved conflict",
                    key=change.key,
                    source=change.source_node,
                )
        
        elif change.operation == "delete":
            await self.backend.delete(change.key)
        
        elif change.operation == "set":
            # Create entry from change
            entry = StateEntry(
                key=change.key,
                value=change.value,
                version=change.new_version,
                vector_clock=change.vector_clock,
                updated_by=change.source_node,
            )
            entry.checksum = entry.compute_checksum()
            await self.backend.set(entry)
        
        # Update our version
        self._version = max(self._version, change.new_version)
        self._local_clock = self._local_clock.merge(change.vector_clock)
    
    async def _resolve_conflict(
        self,
        existing: StateEntry,
        change: StateChange,
    ) -> Optional[StateEntry]:
        """Resolve conflicting changes."""
        # Create entry from change for comparison
        incoming = StateEntry(
            key=change.key,
            value=change.value,
            version=change.new_version,
            vector_clock=change.vector_clock,
            updated_at=change.timestamp,
            updated_by=change.source_node,
        )
        
        if self._conflict_resolver:
            return await self._conflict_resolver(existing, incoming)
        
        # Apply default resolution strategy
        if self.config.conflict_resolution == ConflictResolution.LAST_WRITE_WINS:
            if change.timestamp > existing.updated_at:
                return incoming
            return existing
        
        elif self.config.conflict_resolution == ConflictResolution.FIRST_WRITE_WINS:
            if change.timestamp < existing.updated_at:
                return incoming
            return existing
        
        elif self.config.conflict_resolution == ConflictResolution.MERGE:
            # Simple merge for dict values
            if isinstance(existing.value, dict) and isinstance(change.value, dict):
                merged_value = {**existing.value, **change.value}
                return StateEntry(
                    key=existing.key,
                    value=merged_value,
                    version=max(existing.version, change.new_version) + 1,
                    vector_clock=existing.vector_clock.merge(change.vector_clock),
                    updated_at=datetime.now(timezone.utc),
                    updated_by=self.node_id,
                )
            
            # Fall back to last-write-wins
            if change.timestamp > existing.updated_at:
                return incoming
            return existing
        
        return existing
    
    async def _notify_change(self, change: StateChange) -> None:
        """Notify listeners of a change."""
        for listener in self._change_listeners:
            try:
                await listener(change)
            except Exception as e:
                logger.error(
                    "Change listener error",
                    error=str(e),
                )
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()
        await self.backend.close()
