"""Leader Election for AutoSRE V2 High Availability.

Provides distributed leader election using various backends:
- Redis (recommended for most deployments)
- Consul (for service mesh environments)
- etcd (for Kubernetes-native deployments)
- ZooKeeper (for legacy systems)
- In-memory (for testing)

The leader election system ensures:
- Exactly one leader at a time
- Automatic failover on leader failure
- Leader heartbeats for liveness
- Graceful leadership transitions
"""

from __future__ import annotations

import asyncio
import os
import socket
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Awaitable
from uuid import uuid4

from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class LeaderState(str, Enum):
    """State of a participant in leader election."""
    
    FOLLOWER = "follower"  # Not the leader
    CANDIDATE = "candidate"  # Attempting to become leader
    LEADER = "leader"  # Currently the leader
    STOPPED = "stopped"  # Not participating


@dataclass
class ElectionConfig:
    """Configuration for leader election."""
    
    # Election key/path
    election_key: str = "autosre/leader"
    
    # Timing
    lease_ttl_seconds: float = 30.0  # How long lease is valid
    heartbeat_interval_seconds: float = 10.0  # How often to renew
    election_timeout_seconds: float = 5.0  # Max time to wait for election
    
    # Retry behavior
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    
    # Identity
    candidate_id: Optional[str] = None  # Auto-generated if not provided
    candidate_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.candidate_id is None:
            hostname = socket.gethostname()
            pid = os.getpid()
            self.candidate_id = f"{hostname}-{pid}-{uuid4().hex[:8]}"


class LeaderInfo(BaseModel):
    """Information about the current leader."""
    
    id: str
    elected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_heartbeat: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Leader details
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    
    def is_expired(self, ttl_seconds: float) -> bool:
        """Check if leadership has expired."""
        now = datetime.now(timezone.utc)
        elapsed = (now - self.last_heartbeat).total_seconds()
        return elapsed > ttl_seconds


# Type for leadership callbacks
LeadershipCallback = Callable[[], Awaitable[None]]


class LeaderElectionBackend(ABC):
    """Abstract backend for leader election."""
    
    @abstractmethod
    async def try_acquire(
        self,
        key: str,
        candidate_id: str,
        ttl_seconds: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Try to acquire leadership.
        
        Args:
            key: Election key
            candidate_id: This candidate's ID
            ttl_seconds: Lease TTL
            metadata: Leader metadata
            
        Returns:
            True if leadership acquired
        """
        ...
    
    @abstractmethod
    async def renew(
        self,
        key: str,
        candidate_id: str,
        ttl_seconds: float,
    ) -> bool:
        """Renew leadership lease.
        
        Args:
            key: Election key
            candidate_id: Current leader ID
            ttl_seconds: New TTL
            
        Returns:
            True if renewed successfully
        """
        ...
    
    @abstractmethod
    async def release(
        self,
        key: str,
        candidate_id: str,
    ) -> bool:
        """Release leadership.
        
        Args:
            key: Election key
            candidate_id: Current leader ID
            
        Returns:
            True if released successfully
        """
        ...
    
    @abstractmethod
    async def get_leader(
        self,
        key: str,
    ) -> Optional[LeaderInfo]:
        """Get current leader info.
        
        Args:
            key: Election key
            
        Returns:
            Leader info or None
        """
        ...
    
    @abstractmethod
    async def close(self) -> None:
        """Close backend connections."""
        ...


class InMemoryLeaderBackend(LeaderElectionBackend):
    """In-memory backend for testing."""
    
    # Class-level storage for simulating distributed state
    _leaders: Dict[str, tuple[LeaderInfo, float]] = {}  # key -> (info, expiry_timestamp)
    _lock = asyncio.Lock()
    
    async def try_acquire(
        self,
        key: str,
        candidate_id: str,
        ttl_seconds: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        async with self._lock:
            now = time.time()
            
            # Check if there's an existing valid leader
            if key in self._leaders:
                info, expiry = self._leaders[key]
                if expiry > now and info.id != candidate_id:
                    return False
            
            # Acquire leadership
            self._leaders[key] = (
                LeaderInfo(
                    id=candidate_id,
                    hostname=socket.gethostname(),
                    metadata=metadata or {},
                ),
                now + ttl_seconds,
            )
            return True
    
    async def renew(
        self,
        key: str,
        candidate_id: str,
        ttl_seconds: float,
    ) -> bool:
        async with self._lock:
            if key not in self._leaders:
                return False
            
            info, _ = self._leaders[key]
            if info.id != candidate_id:
                return False
            
            info.last_heartbeat = datetime.now(timezone.utc)
            self._leaders[key] = (info, time.time() + ttl_seconds)
            return True
    
    async def release(
        self,
        key: str,
        candidate_id: str,
    ) -> bool:
        async with self._lock:
            if key not in self._leaders:
                return True
            
            info, _ = self._leaders[key]
            if info.id != candidate_id:
                return False
            
            del self._leaders[key]
            return True
    
    async def get_leader(
        self,
        key: str,
    ) -> Optional[LeaderInfo]:
        async with self._lock:
            if key not in self._leaders:
                return None
            
            info, expiry = self._leaders[key]
            if expiry <= time.time():
                del self._leaders[key]
                return None
            
            return info
    
    async def close(self) -> None:
        pass


class RedisLeaderBackend(LeaderElectionBackend):
    """Redis-based leader election using distributed locks."""
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        key_prefix: str = "autosre:election:",
    ):
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self._redis: Optional[Any] = None
    
    async def _get_redis(self):
        """Get or create Redis connection."""
        if self._redis is None:
            try:
                import redis.asyncio as redis
                self._redis = redis.from_url(self.redis_url)
            except ImportError:
                raise RuntimeError("redis package required for RedisLeaderBackend")
        return self._redis
    
    def _make_key(self, key: str) -> str:
        return f"{self.key_prefix}{key}"
    
    async def try_acquire(
        self,
        key: str,
        candidate_id: str,
        ttl_seconds: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        redis = await self._get_redis()
        full_key = self._make_key(key)
        
        import json
        
        info = LeaderInfo(
            id=candidate_id,
            hostname=socket.gethostname(),
            metadata=metadata or {},
        )
        
        # Use SET NX (set if not exists) with expiry
        acquired = await redis.set(
            full_key,
            json.dumps(info.model_dump(), default=str),
            nx=True,
            ex=int(ttl_seconds),
        )
        
        if acquired:
            return True
        
        # Check if we already own it
        existing = await redis.get(full_key)
        if existing:
            existing_info = LeaderInfo.model_validate_json(existing)
            if existing_info.id == candidate_id:
                return True
        
        return False
    
    async def renew(
        self,
        key: str,
        candidate_id: str,
        ttl_seconds: float,
    ) -> bool:
        redis = await self._get_redis()
        full_key = self._make_key(key)
        
        import json
        
        # Get current leader
        existing = await redis.get(full_key)
        if not existing:
            return False
        
        info = LeaderInfo.model_validate_json(existing)
        if info.id != candidate_id:
            return False
        
        # Update heartbeat and reset TTL
        info.last_heartbeat = datetime.now(timezone.utc)
        await redis.setex(
            full_key,
            int(ttl_seconds),
            json.dumps(info.model_dump(), default=str),
        )
        
        return True
    
    async def release(
        self,
        key: str,
        candidate_id: str,
    ) -> bool:
        redis = await self._get_redis()
        full_key = self._make_key(key)
        
        # Use Lua script for atomic check-and-delete
        script = """
        local value = redis.call('GET', KEYS[1])
        if not value then
            return 1
        end
        local info = cjson.decode(value)
        if info.id == ARGV[1] then
            redis.call('DEL', KEYS[1])
            return 1
        end
        return 0
        """
        
        result = await redis.eval(script, 1, full_key, candidate_id)
        return result == 1
    
    async def get_leader(
        self,
        key: str,
    ) -> Optional[LeaderInfo]:
        redis = await self._get_redis()
        full_key = self._make_key(key)
        
        value = await redis.get(full_key)
        if not value:
            return None
        
        return LeaderInfo.model_validate_json(value)
    
    async def close(self) -> None:
        if self._redis:
            await self._redis.close()
            self._redis = None


class ConsulLeaderBackend(LeaderElectionBackend):
    """Consul-based leader election using sessions and locks."""
    
    def __init__(
        self,
        consul_url: str = "http://localhost:8500",
        key_prefix: str = "autosre/election/",
    ):
        self.consul_url = consul_url
        self.key_prefix = key_prefix
        self._session_id: Optional[str] = None
        self._client: Optional[Any] = None
    
    async def _get_client(self):
        """Get HTTP client for Consul."""
        if self._client is None:
            import httpx
            self._client = httpx.AsyncClient(base_url=self.consul_url)
        return self._client
    
    async def _create_session(self, ttl_seconds: float) -> str:
        """Create Consul session."""
        client = await self._get_client()
        
        response = await client.put(
            "/v1/session/create",
            json={
                "TTL": f"{int(ttl_seconds)}s",
                "Behavior": "delete",
            },
        )
        response.raise_for_status()
        return response.json()["ID"]
    
    async def _renew_session(self, session_id: str) -> bool:
        """Renew Consul session."""
        client = await self._get_client()
        
        try:
            response = await client.put(f"/v1/session/renew/{session_id}")
            return response.status_code == 200
        except Exception:
            return False
    
    async def try_acquire(
        self,
        key: str,
        candidate_id: str,
        ttl_seconds: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        client = await self._get_client()
        
        # Create session if needed
        if not self._session_id:
            self._session_id = await self._create_session(ttl_seconds)
        
        import json
        
        info = LeaderInfo(
            id=candidate_id,
            hostname=socket.gethostname(),
            metadata=metadata or {},
        )
        
        # Try to acquire lock
        response = await client.put(
            f"/v1/kv/{self.key_prefix}{key}",
            params={"acquire": self._session_id},
            content=json.dumps(info.model_dump(), default=str),
        )
        
        return response.json() is True
    
    async def renew(
        self,
        key: str,
        candidate_id: str,
        ttl_seconds: float,
    ) -> bool:
        if not self._session_id:
            return False
        
        return await self._renew_session(self._session_id)
    
    async def release(
        self,
        key: str,
        candidate_id: str,
    ) -> bool:
        if not self._session_id:
            return True
        
        client = await self._get_client()
        
        response = await client.put(
            f"/v1/kv/{self.key_prefix}{key}",
            params={"release": self._session_id},
        )
        
        if response.json() is True:
            # Destroy session
            await client.put(f"/v1/session/destroy/{self._session_id}")
            self._session_id = None
            return True
        
        return False
    
    async def get_leader(
        self,
        key: str,
    ) -> Optional[LeaderInfo]:
        client = await self._get_client()
        
        response = await client.get(f"/v1/kv/{self.key_prefix}{key}")
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        if not data:
            return None
        
        import base64
        
        value = base64.b64decode(data[0]["Value"]).decode()
        return LeaderInfo.model_validate_json(value)
    
    async def close(self) -> None:
        if self._session_id:
            try:
                client = await self._get_client()
                await client.put(f"/v1/session/destroy/{self._session_id}")
            except Exception:
                pass
            self._session_id = None
        
        if self._client:
            await self._client.aclose()
            self._client = None


class EtcdLeaderBackend(LeaderElectionBackend):
    """etcd-based leader election using leases."""
    
    def __init__(
        self,
        etcd_endpoints: List[str] = None,
        key_prefix: str = "/autosre/election/",
    ):
        self.etcd_endpoints = etcd_endpoints or ["localhost:2379"]
        self.key_prefix = key_prefix
        self._client: Optional[Any] = None
        self._lease_id: Optional[int] = None
    
    async def _get_client(self):
        """Get etcd client."""
        if self._client is None:
            try:
                import etcd3
                self._client = etcd3.client(
                    host=self.etcd_endpoints[0].split(":")[0],
                    port=int(self.etcd_endpoints[0].split(":")[1]),
                )
            except ImportError:
                raise RuntimeError("etcd3 package required for EtcdLeaderBackend")
        return self._client
    
    async def try_acquire(
        self,
        key: str,
        candidate_id: str,
        ttl_seconds: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        client = await self._get_client()
        
        import json
        
        info = LeaderInfo(
            id=candidate_id,
            hostname=socket.gethostname(),
            metadata=metadata or {},
        )
        
        # Create lease
        lease = client.lease(int(ttl_seconds))
        self._lease_id = lease.id
        
        # Try to put with lease (etcd handles atomicity)
        full_key = f"{self.key_prefix}{key}"
        
        # Use transaction for atomic operation
        success, _ = client.transaction(
            compare=[
                client.transactions.version(full_key) == 0,  # Key doesn't exist
            ],
            success=[
                client.transactions.put(
                    full_key,
                    json.dumps(info.model_dump(), default=str),
                    lease=lease,
                ),
            ],
            failure=[],
        )
        
        return success
    
    async def renew(
        self,
        key: str,
        candidate_id: str,
        ttl_seconds: float,
    ) -> bool:
        if not self._lease_id:
            return False
        
        client = await self._get_client()
        
        try:
            client.refresh_lease(self._lease_id)
            return True
        except Exception:
            return False
    
    async def release(
        self,
        key: str,
        candidate_id: str,
    ) -> bool:
        if not self._lease_id:
            return True
        
        client = await self._get_client()
        
        try:
            client.revoke_lease(self._lease_id)
            self._lease_id = None
            return True
        except Exception:
            return False
    
    async def get_leader(
        self,
        key: str,
    ) -> Optional[LeaderInfo]:
        client = await self._get_client()
        
        full_key = f"{self.key_prefix}{key}"
        value, _ = client.get(full_key)
        
        if not value:
            return None
        
        return LeaderInfo.model_validate_json(value.decode())
    
    async def close(self) -> None:
        if self._lease_id:
            try:
                client = await self._get_client()
                client.revoke_lease(self._lease_id)
            except Exception:
                pass
            self._lease_id = None
        
        if self._client:
            self._client.close()
            self._client = None


class ZookeeperLeaderBackend(LeaderElectionBackend):
    """ZooKeeper-based leader election using ephemeral sequential nodes."""
    
    def __init__(
        self,
        zk_hosts: str = "localhost:2181",
        base_path: str = "/autosre/election",
    ):
        self.zk_hosts = zk_hosts
        self.base_path = base_path
        self._client: Optional[Any] = None
        self._node_path: Optional[str] = None
    
    async def _get_client(self):
        """Get ZooKeeper client."""
        if self._client is None:
            try:
                from kazoo.client import KazooClient
                self._client = KazooClient(hosts=self.zk_hosts)
                self._client.start()
            except ImportError:
                raise RuntimeError("kazoo package required for ZookeeperLeaderBackend")
        return self._client
    
    async def try_acquire(
        self,
        key: str,
        candidate_id: str,
        ttl_seconds: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        client = await self._get_client()
        
        import json
        
        election_path = f"{self.base_path}/{key}"
        
        # Ensure base path exists
        client.ensure_path(election_path)
        
        info = LeaderInfo(
            id=candidate_id,
            hostname=socket.gethostname(),
            metadata=metadata or {},
        )
        
        # Create ephemeral sequential node
        self._node_path = client.create(
            f"{election_path}/candidate_",
            value=json.dumps(info.model_dump(), default=str).encode(),
            ephemeral=True,
            sequence=True,
        )
        
        # Check if we're the leader (lowest sequence number)
        children = client.get_children(election_path)
        children.sort()
        
        node_name = self._node_path.split("/")[-1]
        return children[0] == node_name
    
    async def renew(
        self,
        key: str,
        candidate_id: str,
        ttl_seconds: float,
    ) -> bool:
        # ZooKeeper ephemeral nodes don't need renewal
        # as long as the session is alive
        client = await self._get_client()
        return client.connected
    
    async def release(
        self,
        key: str,
        candidate_id: str,
    ) -> bool:
        if not self._node_path:
            return True
        
        client = await self._get_client()
        
        try:
            client.delete(self._node_path)
            self._node_path = None
            return True
        except Exception:
            return False
    
    async def get_leader(
        self,
        key: str,
    ) -> Optional[LeaderInfo]:
        client = await self._get_client()
        
        election_path = f"{self.base_path}/{key}"
        
        try:
            children = client.get_children(election_path)
            if not children:
                return None
            
            children.sort()
            leader_path = f"{election_path}/{children[0]}"
            
            data, _ = client.get(leader_path)
            return LeaderInfo.model_validate_json(data.decode())
        except Exception:
            return None
    
    async def close(self) -> None:
        if self._node_path:
            try:
                client = await self._get_client()
                client.delete(self._node_path)
            except Exception:
                pass
            self._node_path = None
        
        if self._client:
            self._client.stop()
            self._client = None


class LeaderElection:
    """
    Distributed leader election coordinator.
    
    Provides single-leader election across distributed nodes using
    pluggable backends (Redis, Consul, etcd, ZooKeeper, or in-memory).
    
    Features:
    - Automatic leader election and failover
    - Heartbeat-based liveness checking
    - Leadership callbacks (on gain/loss)
    - Graceful leadership transitions
    
    Example:
        # Create election with Redis backend
        backend = RedisLeaderBackend("redis://localhost:6379")
        config = ElectionConfig(election_key="my-service/leader")
        
        election = LeaderElection(backend, config)
        
        # Register callbacks
        election.on_gain_leadership(async def: print("I'm the leader!"))
        election.on_lose_leadership(async def: print("Lost leadership"))
        
        # Start participating
        await election.start()
        
        # Check leadership
        if election.is_leader:
            await do_leader_work()
        
        # Stop when done
        await election.stop()
    """
    
    def __init__(
        self,
        backend: LeaderElectionBackend,
        config: Optional[ElectionConfig] = None,
    ):
        """Initialize LeaderElection.
        
        Args:
            backend: Storage backend for election coordination
            config: Election configuration
        """
        self.backend = backend
        self.config = config or ElectionConfig()
        
        self._state = LeaderState.STOPPED
        self._leader_info: Optional[LeaderInfo] = None
        
        self._gain_callbacks: List[LeadershipCallback] = []
        self._lose_callbacks: List[LeadershipCallback] = []
        
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False
    
    @property
    def state(self) -> LeaderState:
        """Get current election state."""
        return self._state
    
    @property
    def is_leader(self) -> bool:
        """Check if this instance is currently the leader."""
        return self._state == LeaderState.LEADER
    
    @property
    def candidate_id(self) -> str:
        """Get this candidate's ID."""
        return self.config.candidate_id
    
    @property
    def leader_info(self) -> Optional[LeaderInfo]:
        """Get current leader information."""
        return self._leader_info
    
    def on_gain_leadership(self, callback: LeadershipCallback) -> None:
        """Register callback for when leadership is gained.
        
        Args:
            callback: Async function to call
        """
        self._gain_callbacks.append(callback)
    
    def on_lose_leadership(self, callback: LeadershipCallback) -> None:
        """Register callback for when leadership is lost.
        
        Args:
            callback: Async function to call
        """
        self._lose_callbacks.append(callback)
    
    async def start(self) -> None:
        """Start participating in leader election."""
        if self._running:
            return
        
        self._running = True
        self._state = LeaderState.FOLLOWER
        
        logger.info(
            "Starting leader election",
            candidate_id=self.candidate_id,
            election_key=self.config.election_key,
        )
        
        # Start heartbeat/election loop
        self._heartbeat_task = asyncio.create_task(self._election_loop())
    
    async def stop(self) -> None:
        """Stop participating in leader election."""
        if not self._running:
            return
        
        self._running = False
        
        # Cancel heartbeat task
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None
        
        # Release leadership if we have it
        if self._state == LeaderState.LEADER:
            await self._release_leadership()
        
        self._state = LeaderState.STOPPED
        
        logger.info(
            "Stopped leader election",
            candidate_id=self.candidate_id,
        )
    
    async def get_current_leader(self) -> Optional[LeaderInfo]:
        """Get the current leader's information.
        
        Returns:
            LeaderInfo or None if no leader
        """
        return await self.backend.get_leader(self.config.election_key)
    
    async def force_election(self) -> bool:
        """Force a new election (only if current leader).
        
        This can be used for graceful handoff.
        
        Returns:
            True if election was forced
        """
        if not self.is_leader:
            return False
        
        await self._release_leadership()
        return True
    
    async def _election_loop(self) -> None:
        """Main election and heartbeat loop."""
        while self._running:
            try:
                if self._state == LeaderState.LEADER:
                    # Renew leadership
                    renewed = await self.backend.renew(
                        self.config.election_key,
                        self.candidate_id,
                        self.config.lease_ttl_seconds,
                    )
                    
                    if not renewed:
                        logger.warning(
                            "Lost leadership lease",
                            candidate_id=self.candidate_id,
                        )
                        await self._handle_leadership_lost()
                
                else:
                    # Try to acquire leadership
                    self._state = LeaderState.CANDIDATE
                    
                    acquired = await self.backend.try_acquire(
                        self.config.election_key,
                        self.candidate_id,
                        self.config.lease_ttl_seconds,
                        self.config.candidate_metadata,
                    )
                    
                    if acquired:
                        await self._handle_leadership_gained()
                    else:
                        self._state = LeaderState.FOLLOWER
                        
                        # Update our view of the leader
                        self._leader_info = await self.backend.get_leader(
                            self.config.election_key
                        )
                
                await asyncio.sleep(self.config.heartbeat_interval_seconds)
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(
                    "Error in election loop",
                    error=str(e),
                    candidate_id=self.candidate_id,
                )
                await asyncio.sleep(self.config.retry_delay_seconds)
    
    async def _handle_leadership_gained(self) -> None:
        """Handle gaining leadership."""
        self._state = LeaderState.LEADER
        self._leader_info = LeaderInfo(
            id=self.candidate_id,
            hostname=socket.gethostname(),
            metadata=self.config.candidate_metadata,
        )
        
        logger.info(
            "Gained leadership",
            candidate_id=self.candidate_id,
            election_key=self.config.election_key,
        )
        
        # Call callbacks
        for callback in self._gain_callbacks:
            try:
                await callback()
            except Exception as e:
                logger.error(
                    "Leadership gain callback failed",
                    error=str(e),
                )
    
    async def _handle_leadership_lost(self) -> None:
        """Handle losing leadership."""
        self._state = LeaderState.FOLLOWER
        
        logger.info(
            "Lost leadership",
            candidate_id=self.candidate_id,
            election_key=self.config.election_key,
        )
        
        # Call callbacks
        for callback in self._lose_callbacks:
            try:
                await callback()
            except Exception as e:
                logger.error(
                    "Leadership loss callback failed",
                    error=str(e),
                )
        
        # Get new leader info
        self._leader_info = await self.backend.get_leader(
            self.config.election_key
        )
    
    async def _release_leadership(self) -> None:
        """Release leadership."""
        await self.backend.release(
            self.config.election_key,
            self.candidate_id,
        )
        
        await self._handle_leadership_lost()
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()
        await self.backend.close()


# Convenience factory functions
def create_leader_election(
    backend_type: str = "memory",
    config: Optional[ElectionConfig] = None,
    **backend_kwargs,
) -> LeaderElection:
    """Create a LeaderElection with the specified backend.
    
    Args:
        backend_type: One of 'memory', 'redis', 'consul', 'etcd', 'zookeeper'
        config: Election configuration
        **backend_kwargs: Backend-specific arguments
        
    Returns:
        LeaderElection instance
    """
    backends = {
        "memory": InMemoryLeaderBackend,
        "redis": RedisLeaderBackend,
        "consul": ConsulLeaderBackend,
        "etcd": EtcdLeaderBackend,
        "zookeeper": ZookeeperLeaderBackend,
    }
    
    if backend_type not in backends:
        raise ValueError(f"Unknown backend type: {backend_type}")
    
    backend = backends[backend_type](**backend_kwargs)
    return LeaderElection(backend, config)
