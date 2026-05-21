"""
Neo4j async client with connection pooling, retry logic, and health checks.

Provides a robust async interface to Neo4j for the Knowledge Graph service.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncGenerator

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession
from neo4j.exceptions import (
    ServiceUnavailable,
    SessionExpired,
    TransientError,
    AuthError,
    DatabaseError,
)

from .queries import CHECK_CONNECTION

logger = logging.getLogger(__name__)


@dataclass
class Neo4jConfig:
    """Configuration for Neo4j connection."""

    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password: str = ""
    database: str = "neo4j"
    max_connection_pool_size: int = 50
    connection_acquisition_timeout: float = 60.0
    connection_timeout: float = 30.0
    max_transaction_retry_time: float = 30.0
    encrypted: bool = False

    @classmethod
    def from_env(cls) -> "Neo4jConfig":
        """Create config from environment variables."""
        import os

        return cls(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            username=os.getenv("NEO4J_USERNAME", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", ""),
            database=os.getenv("NEO4J_DATABASE", "neo4j"),
            max_connection_pool_size=int(
                os.getenv("NEO4J_MAX_POOL_SIZE", "50")
            ),
            encrypted=os.getenv("NEO4J_ENCRYPTED", "false").lower() == "true",
        )


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 10.0,
        exponential_base: float = 2.0,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt using exponential backoff."""
        delay = self.base_delay * (self.exponential_base ** attempt)
        return min(delay, self.max_delay)


class Neo4jClient:
    """Async Neo4j client with connection pooling and retry logic."""

    def __init__(
        self,
        config: Neo4jConfig | None = None,
        retry_config: RetryConfig | None = None,
    ):
        self.config = config or Neo4jConfig.from_env()
        self.retry_config = retry_config or RetryConfig()
        self._driver: AsyncDriver | None = None
        self._connected = False

    async def connect(self) -> None:
        """Establish connection to Neo4j."""
        if self._driver is not None:
            return

        logger.info(f"Connecting to Neo4j at {self.config.uri}")

        try:
            self._driver = AsyncGraphDatabase.driver(
                self.config.uri,
                auth=(self.config.username, self.config.password),
                max_connection_pool_size=self.config.max_connection_pool_size,
                connection_acquisition_timeout=self.config.connection_acquisition_timeout,
                connection_timeout=self.config.connection_timeout,
                max_transaction_retry_time=self.config.max_transaction_retry_time,
                encrypted=self.config.encrypted,
            )

            # Verify connection
            await self._verify_connection()
            self._connected = True
            logger.info("Successfully connected to Neo4j")

        except AuthError as e:
            logger.error(f"Neo4j authentication failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    async def _verify_connection(self) -> None:
        """Verify connection is working."""
        async with self.session() as session:
            await session.run(CHECK_CONNECTION)

    async def close(self) -> None:
        """Close the Neo4j connection."""
        if self._driver is not None:
            await self._driver.close()
            self._driver = None
            self._connected = False
            logger.info("Neo4j connection closed")

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._connected and self._driver is not None

    @asynccontextmanager
    async def session(
        self, database: str | None = None
    ) -> AsyncGenerator[AsyncSession, None]:
        """Get a session from the connection pool."""
        if self._driver is None:
            await self.connect()

        db = database or self.config.database
        session = self._driver.session(database=db)
        try:
            yield session
        finally:
            await session.close()

    async def execute_query(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
        database: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Execute a Cypher query with retry logic.

        Args:
            query: Cypher query string
            parameters: Query parameters
            database: Database name (optional, uses default)

        Returns:
            List of result records as dictionaries
        """
        parameters = parameters or {}
        last_error: Exception | None = None

        for attempt in range(self.retry_config.max_retries + 1):
            try:
                async with self.session(database) as session:
                    result = await session.run(query, parameters)
                    records = await result.data()
                    return records

            except (ServiceUnavailable, SessionExpired, TransientError) as e:
                last_error = e
                if attempt < self.retry_config.max_retries:
                    delay = self.retry_config.get_delay(attempt)
                    logger.warning(
                        f"Neo4j transient error (attempt {attempt + 1}/"
                        f"{self.retry_config.max_retries + 1}), "
                        f"retrying in {delay:.2f}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Neo4j query failed after {attempt + 1} attempts: {e}"
                    )
                    raise

            except DatabaseError as e:
                # Non-transient database errors should not be retried
                logger.error(f"Neo4j database error: {e}")
                raise

        # Should not reach here, but satisfy type checker
        if last_error:
            raise last_error
        return []

    async def execute_write(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
        database: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Execute a write query within a transaction.

        Args:
            query: Cypher query string
            parameters: Query parameters
            database: Database name (optional)

        Returns:
            List of result records
        """
        parameters = parameters or {}

        async def _write_tx(tx):
            result = await tx.run(query, parameters)
            return await result.data()

        async with self.session(database) as session:
            return await session.execute_write(_write_tx)

    async def execute_batch(
        self,
        queries: list[tuple[str, dict[str, Any] | None]],
        database: str | None = None,
    ) -> list[list[dict[str, Any]]]:
        """
        Execute multiple queries in a single transaction.

        Args:
            queries: List of (query, parameters) tuples
            database: Database name (optional)

        Returns:
            List of results for each query
        """

        async def _batch_tx(tx):
            results = []
            for query, params in queries:
                result = await tx.run(query, params or {})
                records = await result.data()
                results.append(records)
            return results

        async with self.session(database) as session:
            return await session.execute_write(_batch_tx)

    async def health_check(self) -> dict[str, Any]:
        """
        Perform a health check on the Neo4j connection.

        Returns:
            Health status dictionary
        """
        try:
            if not self.is_connected:
                await self.connect()

            start = asyncio.get_event_loop().time()
            await self.execute_query(CHECK_CONNECTION)
            latency_ms = (asyncio.get_event_loop().time() - start) * 1000

            return {
                "status": "healthy",
                "connected": True,
                "uri": self.config.uri,
                "database": self.config.database,
                "latency_ms": round(latency_ms, 2),
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "connected": False,
                "uri": self.config.uri,
                "error": str(e),
            }

    async def get_schema(self) -> dict[str, Any]:
        """
        Get the database schema information.

        Returns:
            Schema information including node labels and relationship types
        """
        try:
            # Get node labels
            labels_result = await self.execute_query("CALL db.labels()")
            labels = [r.get("label") for r in labels_result if r.get("label")]

            # Get relationship types
            rels_result = await self.execute_query("CALL db.relationshipTypes()")
            relationships = [
                r.get("relationshipType")
                for r in rels_result
                if r.get("relationshipType")
            ]

            # Get node counts
            counts_result = await self.execute_query("""
                MATCH (n)
                RETURN labels(n)[0] AS label, count(n) AS count
                ORDER BY count DESC
            """)

            return {
                "labels": labels,
                "relationship_types": relationships,
                "node_counts": {r["label"]: r["count"] for r in counts_result if r.get("label")},
            }

        except Exception as e:
            logger.error(f"Failed to get schema: {e}")
            return {"error": str(e)}

    async def __aenter__(self) -> "Neo4jClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()


# Module-level client instance for singleton pattern
_client: Neo4jClient | None = None


async def get_client(config: Neo4jConfig | None = None) -> Neo4jClient:
    """
    Get or create the singleton Neo4j client.

    Args:
        config: Optional configuration (only used on first call)

    Returns:
        Neo4jClient instance
    """
    global _client
    if _client is None:
        _client = Neo4jClient(config)
        await _client.connect()
    return _client


async def close_client() -> None:
    """Close the singleton client."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None
