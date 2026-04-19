"""
Elasticsearch Skill for OpenSRE

Query logs and metrics from Elasticsearch.
"""

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from opensre_core.skills import ActionResult, Skill

logger = logging.getLogger(__name__)


@dataclass
class Document:
    """Elasticsearch document."""
    id: str
    index: str
    source: dict[str, Any]
    score: float | None = None


@dataclass
class Index:
    """Elasticsearch index."""
    name: str
    health: str
    status: str
    docs_count: int
    size_bytes: int


@dataclass
class ClusterHealth:
    """Elasticsearch cluster health."""
    cluster_name: str
    status: str  # green, yellow, red
    number_of_nodes: int
    number_of_data_nodes: int
    active_primary_shards: int
    active_shards: int
    relocating_shards: int
    initializing_shards: int
    unassigned_shards: int


class ElasticsearchSkill(Skill):
    """Skill for interacting with Elasticsearch."""

    name = "elasticsearch"
    version = "1.0.0"
    description = "Query Elasticsearch for logs and metrics"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.hosts = self.config.get("hosts", ["http://localhost:9200"])
        self.username = self.config.get("username")
        self.password = self.config.get("password")
        self.api_key = self.config.get("api_key")
        self.verify_ssl = self.config.get("verify_ssl", True)
        self.timeout = self.config.get("timeout", 30)
        self._client: httpx.AsyncClient | None = None

        # Register actions
        self.register_action("search", self.search, "Execute Elasticsearch query")
        self.register_action("count", self.count, "Count documents")
        self.register_action("get_indices", self.get_indices, "List indices")
        self.register_action("cluster_health", self.cluster_health, "Get cluster health")

    async def initialize(self) -> None:
        """Initialize HTTP client."""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        auth = None

        if self.api_key:
            headers["Authorization"] = f"ApiKey {self.api_key}"
        elif self.username and self.password:
            auth = (self.username, self.password)

        self._client = httpx.AsyncClient(
            base_url=self.hosts[0],
            headers=headers,
            auth=auth,
            verify=self.verify_ssl,
            timeout=self.timeout,
        )
        self._initialized = True

    async def shutdown(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._initialized = False

    async def health_check(self) -> ActionResult[dict[str, Any]]:
        """Check Elasticsearch connectivity."""
        if not self._client:
            return ActionResult.fail("Client not initialized")
        try:
            response = await self._client.get("/")
            if response.status_code == 200:
                data = response.json()
                return ActionResult.ok({
                    "status": "healthy",
                    "cluster_name": data.get("cluster_name"),
                    "version": data.get("version", {}).get("number"),
                })
            return ActionResult.fail(f"Health check failed: {response.status_code}")
        except Exception as e:
            return ActionResult.fail(f"Health check failed: {e}")

    async def search(
        self,
        index: str,
        query: dict[str, Any],
        size: int = 100,
        sort: list[dict[str, Any]] | None = None,
    ) -> ActionResult[list[Document]]:
        """Execute Elasticsearch search."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            body: dict[str, Any] = {"query": query, "size": size}
            if sort:
                body["sort"] = sort

            response = await self._client.post(f"/{index}/_search", json=body)
            response.raise_for_status()
            data = response.json()

            documents = []
            for hit in data.get("hits", {}).get("hits", []):
                documents.append(Document(
                    id=hit.get("_id", ""),
                    index=hit.get("_index", ""),
                    source=hit.get("_source", {}),
                    score=hit.get("_score"),
                ))
            return ActionResult.ok(documents, total=data.get("hits", {}).get("total", {}).get("value", 0))
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error executing search")
            return ActionResult.fail(str(e))

    async def count(
        self,
        index: str,
        query: dict[str, Any],
    ) -> ActionResult[int]:
        """Count documents matching query."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            response = await self._client.post(
                f"/{index}/_count",
                json={"query": query},
            )
            response.raise_for_status()
            data = response.json()
            return ActionResult.ok(data.get("count", 0))
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error counting documents")
            return ActionResult.fail(str(e))

    async def get_indices(
        self,
        pattern: str = "*",
    ) -> ActionResult[list[Index]]:
        """List Elasticsearch indices."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            response = await self._client.get(
                f"/_cat/indices/{pattern}",
                params={"format": "json"},
            )
            response.raise_for_status()
            data = response.json()

            indices = []
            for idx in data:
                indices.append(Index(
                    name=idx.get("index", ""),
                    health=idx.get("health", ""),
                    status=idx.get("status", ""),
                    docs_count=int(idx.get("docs.count", 0) or 0),
                    size_bytes=0,  # Would need parsing from pri.store.size
                ))
            return ActionResult.ok(indices)
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error listing indices")
            return ActionResult.fail(str(e))

    async def cluster_health(self) -> ActionResult[ClusterHealth]:
        """Get Elasticsearch cluster health."""
        if not self._client:
            return ActionResult.fail("Client not initialized")

        try:
            response = await self._client.get("/_cluster/health")
            response.raise_for_status()
            data = response.json()

            return ActionResult.ok(ClusterHealth(
                cluster_name=data.get("cluster_name", ""),
                status=data.get("status", "unknown"),
                number_of_nodes=data.get("number_of_nodes", 0),
                number_of_data_nodes=data.get("number_of_data_nodes", 0),
                active_primary_shards=data.get("active_primary_shards", 0),
                active_shards=data.get("active_shards", 0),
                relocating_shards=data.get("relocating_shards", 0),
                initializing_shards=data.get("initializing_shards", 0),
                unassigned_shards=data.get("unassigned_shards", 0),
            ))
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Error getting cluster health")
            return ActionResult.fail(str(e))
