"""
Neo4j client wrapper with connection pooling and async support.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, TypeVar

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession, AsyncTransaction
from neo4j.exceptions import ServiceUnavailable, AuthError, Neo4jError

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Global client singleton
_client: Neo4jClient | None = None


@dataclass
class Neo4jConfig:
    """Neo4j connection configuration."""
    
    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password: str = "password"
    database: str = "neo4j"
    max_connection_pool_size: int = 50
    connection_acquisition_timeout: float = 60.0
    max_transaction_retry_time: float = 30.0
    connection_timeout: float = 30.0
    encrypted: bool = False
    trust: str = "TRUST_ALL_CERTIFICATES"
    
    @classmethod
    def from_env(cls) -> Neo4jConfig:
        """Load configuration from environment variables."""
        import os
        return cls(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            username=os.getenv("NEO4J_USERNAME", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password"),
            database=os.getenv("NEO4J_DATABASE", "neo4j"),
            max_connection_pool_size=int(os.getenv("NEO4J_POOL_SIZE", "50")),
            encrypted=os.getenv("NEO4J_ENCRYPTED", "false").lower() == "true",
        )


@dataclass
class QueryResult:
    """Result from a Neo4j query."""
    
    records: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    
    @property
    def single(self) -> dict[str, Any] | None:
        """Get single record or None."""
        return self.records[0] if self.records else None
    
    @property
    def values(self) -> list[Any]:
        """Get first value from each record."""
        return [list(r.values())[0] for r in self.records if r]
    
    def __len__(self) -> int:
        return len(self.records)
    
    def __iter__(self):
        return iter(self.records)
    
    def __bool__(self) -> bool:
        return len(self.records) > 0


class Neo4jClient:
    """
    Async Neo4j client with connection pooling.
    
    Usage:
        async with Neo4jClient.create(config) as client:
            result = await client.execute_query("MATCH (n) RETURN n LIMIT 10")
            
        # Or manual lifecycle:
        client = Neo4jClient(config)
        await client.connect()
        try:
            result = await client.execute_query("...")
        finally:
            await client.close()
    """
    
    def __init__(self, config: Neo4jConfig | None = None):
        self.config = config or Neo4jConfig.from_env()
        self._driver: AsyncDriver | None = None
        self._connected = False
        self._lock = asyncio.Lock()
    
    @classmethod
    async def create(cls, config: Neo4jConfig | None = None) -> Neo4jClient:
        """Create and connect a new client."""
        client = cls(config)
        await client.connect()
        return client
    
    async def connect(self) -> None:
        """Establish connection to Neo4j."""
        async with self._lock:
            if self._connected:
                return
            
            try:
                self._driver = AsyncGraphDatabase.driver(
                    self.config.uri,
                    auth=(self.config.username, self.config.password),
                    max_connection_pool_size=self.config.max_connection_pool_size,
                    connection_acquisition_timeout=self.config.connection_acquisition_timeout,
                    max_transaction_retry_time=self.config.max_transaction_retry_time,
                    connection_timeout=self.config.connection_timeout,
                    encrypted=self.config.encrypted,
                )
                
                # Verify connectivity
                await self._driver.verify_connectivity()
                self._connected = True
                logger.info(f"Connected to Neo4j at {self.config.uri}")
                
            except AuthError as e:
                logger.error(f"Neo4j authentication failed: {e}")
                raise
            except ServiceUnavailable as e:
                logger.error(f"Neo4j service unavailable: {e}")
                raise
            except Exception as e:
                logger.error(f"Failed to connect to Neo4j: {e}")
                raise
    
    async def close(self) -> None:
        """Close the connection."""
        async with self._lock:
            if self._driver:
                await self._driver.close()
                self._driver = None
                self._connected = False
                logger.info("Neo4j connection closed")
    
    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected and self._driver is not None
    
    async def verify_connectivity(self) -> bool:
        """Verify the connection is alive."""
        if not self._driver:
            return False
        try:
            await self._driver.verify_connectivity()
            return True
        except Exception:
            return False
    
    @asynccontextmanager
    async def session(self, database: str | None = None) -> AsyncIterator[AsyncSession]:
        """Get a session from the pool."""
        if not self._driver:
            raise RuntimeError("Client not connected. Call connect() first.")
        
        db = database or self.config.database
        session = self._driver.session(database=db)
        try:
            yield session
        finally:
            await session.close()
    
    @asynccontextmanager
    async def transaction(
        self, 
        database: str | None = None
    ) -> AsyncIterator[AsyncTransaction]:
        """Get a transaction for explicit transaction control."""
        async with self.session(database) as session:
            tx = await session.begin_transaction()
            try:
                yield tx
                await tx.commit()
            except Exception:
                await tx.rollback()
                raise
    
    async def execute_query(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
        database: str | None = None,
    ) -> QueryResult:
        """
        Execute a Cypher query and return results.
        
        Args:
            query: Cypher query string
            parameters: Query parameters
            database: Optional database name override
            
        Returns:
            QueryResult with records and summary
        """
        if not self._driver:
            raise RuntimeError("Client not connected. Call connect() first.")
        
        params = parameters or {}
        db = database or self.config.database
        
        try:
            async with self.session(db) as session:
                result = await session.run(query, params)
                records = [dict(record) for record in await result.data()]
                summary = await result.consume()
                
                return QueryResult(
                    records=records,
                    summary={
                        "counters": summary.counters.__dict__ if hasattr(summary, 'counters') else {},
                        "query_type": summary.query_type if hasattr(summary, 'query_type') else None,
                        "result_available_after": summary.result_available_after if hasattr(summary, 'result_available_after') else None,
                        "result_consumed_after": summary.result_consumed_after if hasattr(summary, 'result_consumed_after') else None,
                    }
                )
        except Neo4jError as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    async def execute_write(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
        database: str | None = None,
    ) -> QueryResult:
        """Execute a write query with automatic retry on transient errors."""
        if not self._driver:
            raise RuntimeError("Client not connected. Call connect() first.")
        
        params = parameters or {}
        db = database or self.config.database
        
        async def _work(tx: AsyncTransaction) -> list[dict]:
            result = await tx.run(query, params)
            return [dict(record) for record in await result.data()]
        
        async with self.session(db) as session:
            records = await session.execute_write(_work)
            return QueryResult(records=records)
    
    async def execute_read(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
        database: str | None = None,
    ) -> QueryResult:
        """Execute a read query with automatic retry on transient errors."""
        if not self._driver:
            raise RuntimeError("Client not connected. Call connect() first.")
        
        params = parameters or {}
        db = database or self.config.database
        
        async def _work(tx: AsyncTransaction) -> list[dict]:
            result = await tx.run(query, params)
            return [dict(record) for record in await result.data()]
        
        async with self.session(db) as session:
            records = await session.execute_read(_work)
            return QueryResult(records=records)
    
    async def __aenter__(self) -> Neo4jClient:
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()


async def get_client(config: Neo4jConfig | None = None) -> Neo4jClient:
    """
    Get or create the global Neo4j client singleton.
    
    Thread-safe initialization with connection pooling.
    """
    global _client
    
    if _client is None or not _client.is_connected:
        _client = await Neo4jClient.create(config)
    
    return _client


async def close_client() -> None:
    """Close the global client if it exists."""
    global _client
    
    if _client:
        await _client.close()
        _client = None
