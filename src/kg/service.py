"""
High-level Knowledge Graph service for topology operations.

Provides business-logic layer over Neo4j client for service topology
management, dependency analysis, and blast radius calculations.
"""

import logging
from typing import Any

from .client import Neo4jClient, Neo4jConfig, get_client
from .models import (
    Service,
    Team,
    Dependency,
    DependencyType,
    Protocol,
    Criticality,
    ServiceTier,
    BlastRadius,
    TopologyUpdate,
    ServiceSearchResult,
    AlertContext,
    ServiceHealth,
)
from . import queries

logger = logging.getLogger(__name__)


class KnowledgeGraphService:
    """High-level service for topology operations on the knowledge graph."""

    def __init__(self, client: Neo4jClient | None = None):
        """
        Initialize the Knowledge Graph service.

        Args:
            client: Neo4j client instance (optional, will create default if not provided)
        """
        self._client = client
        self._initialized = False

    async def _get_client(self) -> Neo4jClient:
        """Get or initialize the Neo4j client."""
        if self._client is None:
            self._client = await get_client()
        return self._client

    async def initialize(self) -> None:
        """Initialize the service and verify connectivity."""
        client = await self._get_client()
        health = await client.health_check()
        if health["status"] != "healthy":
            raise RuntimeError(f"Neo4j unhealthy: {health.get('error', 'unknown')}")
        self._initialized = True
        logger.info("Knowledge Graph service initialized")

    # =========================================================================
    # SERVICE OPERATIONS
    # =========================================================================

    async def get_service(self, name: str) -> Service | None:
        """
        Get a service by name with its dependencies.

        Args:
            name: Service name (exact or partial match)

        Returns:
            Service with populated dependencies, or None if not found
        """
        client = await self._get_client()

        # Try primary Service node schema first
        results = await client.execute_query(
            queries.GET_SERVICE_BY_NAME,
            {"name": name},
        )

        if results:
            return self._parse_service_result(results[0])

        # Fallback to KubernetesDeployment schema (OpenSRE compatibility)
        results = await client.execute_query(
            queries.GET_SERVICE_BY_NAME_FALLBACK,
            {"name": name},
        )

        if results:
            return self._parse_k8s_service_result(results[0])

        logger.warning(f"Service not found: {name}")
        return None

    def _parse_service_result(self, record: dict[str, Any]) -> Service:
        """Parse a Service node result into a Service model."""
        s = record.get("s", {})
        t = record.get("t", {})
        deps = record.get("dependencies", [])
        dependents = record.get("dependents", [])

        upstream_deps = [
            Dependency(
                target=d.get("target", ""),
                type=DependencyType(d.get("type", "sync")),
                protocol=Protocol(d.get("protocol", "http")),
                criticality=Criticality(d.get("criticality", "hard")),
                port=d.get("port"),
                via=d.get("via"),
            )
            for d in deps
            if d.get("target")
        ]

        downstream_deps = [
            Dependency(
                target=d.get("target", ""),
                type=DependencyType(d.get("type", "sync")),
                protocol=Protocol(d.get("protocol", "http")),
                criticality=Criticality(d.get("criticality", "hard")),
            )
            for d in dependents
            if d.get("target")
        ]

        return Service(
            name=s.get("name", ""),
            team=t.get("name") if t else s.get("team"),
            tier=ServiceTier(s.get("tier", "tier-2")),
            criticality=Criticality(s.get("criticality", "hard")),
            namespace=s.get("namespace"),
            cluster=s.get("cluster"),
            replicas=s.get("replicas"),
            image=s.get("image"),
            language=s.get("language"),
            port=s.get("port"),
            repo=s.get("repo"),
            upstream_dependencies=upstream_deps,
            downstream_dependents=downstream_deps,
            labels=s.get("labels", {}),
        )

    def _parse_k8s_service_result(self, record: dict[str, Any]) -> Service:
        """Parse a KubernetesDeployment result into a Service model."""
        svc = record.get("service", {})
        ns = record.get("ns", {})
        deps = record.get("dependencies", [])
        dependents = record.get("dependents", [])

        upstream_deps = [
            Dependency(
                target=d.get("target", ""),
                type=DependencyType.SYNC,
                protocol=Protocol.GRPC,
                criticality=Criticality.HARD,
                port=d.get("port"),
                via=d.get("via"),
            )
            for d in deps
            if d.get("target")
        ]

        downstream_deps = [
            Dependency(
                target=d.get("target", ""),
                type=DependencyType.SYNC,
                protocol=Protocol.GRPC,
                criticality=Criticality.HARD,
            )
            for d in dependents
            if d.get("target")
        ]

        return Service(
            name=svc.get("name", ""),
            namespace=ns.get("name") if ns else None,
            replicas=svc.get("replicas"),
            image=svc.get("image"),
            language=svc.get("language"),
            port=svc.get("port"),
            upstream_dependencies=upstream_deps,
            downstream_dependents=downstream_deps,
        )

    async def search_services(
        self, query: str, limit: int = 20
    ) -> list[ServiceSearchResult]:
        """
        Search for services by name, team, or labels.

        Args:
            query: Search query string
            limit: Maximum results to return

        Returns:
            List of matching services with relevance scores
        """
        client = await self._get_client()

        # Try primary schema
        results = await client.execute_query(
            queries.SEARCH_SERVICES,
            {"query": query, "limit": limit},
        )

        # If no results, try fallback schema
        if not results:
            results = await client.execute_query(
                queries.SEARCH_SERVICES_FALLBACK,
                {"query": query, "limit": limit},
            )

        return [
            ServiceSearchResult(
                name=r.get("name", ""),
                team=r.get("team"),
                tier=ServiceTier(r.get("tier", "tier-2")) if r.get("tier") else ServiceTier.TIER_2,
                namespace=r.get("namespace"),
                relevance_score=r.get("relevance_score", 0.5),
            )
            for r in results
        ]

    async def list_services(self) -> list[Service]:
        """
        List all services in the topology.

        Returns:
            List of all services (without full dependency details)
        """
        client = await self._get_client()
        results = await client.execute_query(queries.LIST_ALL_SERVICES)

        return [
            Service(
                name=r.get("name", ""),
                team=r.get("team"),
                tier=ServiceTier(r.get("tier", "tier-2")) if r.get("tier") else ServiceTier.TIER_2,
                namespace=r.get("namespace"),
                cluster=r.get("cluster"),
            )
            for r in results
        ]

    # =========================================================================
    # DEPENDENCY OPERATIONS
    # =========================================================================

    async def get_upstream_dependencies(self, service: str) -> list[Dependency]:
        """
        Get all services that a given service depends on.

        Args:
            service: Service name

        Returns:
            List of upstream dependencies
        """
        client = await self._get_client()

        results = await client.execute_query(
            queries.GET_UPSTREAM_DEPENDENCIES,
            {"name": service},
        )

        if not results:
            results = await client.execute_query(
                queries.GET_UPSTREAM_DEPENDENCIES_FALLBACK,
                {"name": service},
            )

        return [
            Dependency(
                target=r.get("name", ""),
                type=DependencyType(r.get("dependency_type", "sync")),
                protocol=Protocol(r.get("protocol", "http")),
                criticality=Criticality(r.get("criticality", "hard")),
                port=r.get("port"),
                via=r.get("via"),
            )
            for r in results
        ]

    async def get_downstream_dependents(self, service: str) -> list[Dependency]:
        """
        Get all services that depend on a given service.

        Args:
            service: Service name

        Returns:
            List of downstream dependents
        """
        client = await self._get_client()

        results = await client.execute_query(
            queries.GET_DOWNSTREAM_DEPENDENTS,
            {"name": service},
        )

        if not results:
            results = await client.execute_query(
                queries.GET_DOWNSTREAM_DEPENDENTS_FALLBACK,
                {"name": service},
            )

        return [
            Dependency(
                target=r.get("name", ""),
                type=DependencyType(r.get("dependency_type", "sync")),
                protocol=Protocol(r.get("protocol", "http")),
                criticality=Criticality(r.get("criticality", "hard")),
            )
            for r in results
        ]

    # =========================================================================
    # BLAST RADIUS ANALYSIS
    # =========================================================================

    async def get_blast_radius(self, service: str) -> BlastRadius:
        """
        Calculate the blast radius for a service failure.

        Args:
            service: Service name

        Returns:
            BlastRadius analysis showing all affected services
        """
        client = await self._get_client()

        results = await client.execute_query(
            queries.GET_BLAST_RADIUS,
            {"name": service},
        )

        if not results:
            results = await client.execute_query(
                queries.GET_BLAST_RADIUS_FALLBACK,
                {"name": service},
            )

        if not results:
            return BlastRadius(
                service=service,
                direct_dependents=[],
                indirect_dependents=[],
                total_affected=0,
                critical_path=False,
            )

        record = results[0]
        direct = record.get("direct_dependents", [])
        indirect = record.get("indirect_dependents", [])

        # Filter out None values
        direct = [d for d in direct if d]
        indirect = [i for i in indirect if i and i not in direct]

        total = len(set(direct + indirect))

        # Critical path if >3 dependents or includes tier-1 services
        critical_path = total >= 3

        return BlastRadius(
            service=service,
            direct_dependents=direct,
            indirect_dependents=indirect,
            total_affected=total,
            critical_path=critical_path,
        )

    # =========================================================================
    # TOPOLOGY MANAGEMENT
    # =========================================================================

    async def update_topology(self, update: TopologyUpdate) -> dict[str, int]:
        """
        Update the service topology with new or modified services.

        Args:
            update: TopologyUpdate containing services and teams to upsert

        Returns:
            Dictionary with counts of created/updated entities
        """
        client = await self._get_client()
        stats = {"teams_updated": 0, "services_updated": 0, "dependencies_created": 0}

        # Upsert teams first
        for team in update.teams:
            await client.execute_write(
                queries.UPSERT_TEAM,
                {
                    "name": team.name,
                    "slack_channel": team.slack_channel,
                    "oncall_schedule": team.oncall_schedule,
                    "email": team.email,
                },
            )
            stats["teams_updated"] += 1

        # Upsert services
        for service in update.services:
            # Create/update service node
            await client.execute_write(
                queries.UPSERT_SERVICE,
                {
                    "name": service.name,
                    "team": service.team,
                    "tier": service.tier.value if service.tier else "tier-2",
                    "criticality": service.criticality.value if service.criticality else "hard",
                    "namespace": service.namespace,
                    "cluster": service.cluster,
                    "replicas": service.replicas,
                    "image": service.image,
                    "language": service.language,
                    "port": service.port,
                    "repo": service.repo,
                    "labels": service.labels,
                },
            )
            stats["services_updated"] += 1

            # Clear existing dependencies
            await client.execute_write(
                queries.DELETE_ALL_DEPENDENCIES_FOR_SERVICE,
                {"name": service.name},
            )

            # Create new dependencies
            for dep in service.upstream_dependencies:
                await client.execute_write(
                    queries.CREATE_DEPENDENCY,
                    {
                        "source": service.name,
                        "target": dep.target,
                        "type": dep.type.value,
                        "protocol": dep.protocol.value,
                        "criticality": dep.criticality.value,
                        "port": dep.port,
                        "via": dep.via,
                    },
                )
                stats["dependencies_created"] += 1

            # Create team ownership
            if service.team:
                await client.execute_write(
                    queries.CREATE_OWNERSHIP,
                    {"service": service.name, "team": service.team},
                )

        logger.info(f"Topology update complete: {stats}")
        return stats

    async def delete_service(self, name: str) -> bool:
        """
        Delete a service from the topology.

        Args:
            name: Service name to delete

        Returns:
            True if service was deleted, False if not found
        """
        client = await self._get_client()
        results = await client.execute_write(
            queries.DELETE_SERVICE,
            {"name": name},
        )
        deleted = results[0].get("deleted", 0) if results else 0
        return deleted > 0

    # =========================================================================
    # ALERT CONTEXT
    # =========================================================================

    async def get_alert_context(self, alert_data: dict[str, Any]) -> AlertContext:
        """
        Get context information for an alert from the knowledge graph.

        Args:
            alert_data: Alert information containing service name

        Returns:
            AlertContext with service info, blast radius, etc.
        """
        # Extract service name from alert
        service_name = self._extract_service_from_alert(alert_data)

        if not service_name:
            logger.warning("Could not extract service name from alert")
            return AlertContext()

        # Get service info
        service = await self.get_service(service_name)
        if not service:
            return AlertContext(service_name=service_name)

        # Get blast radius
        blast_radius = await self.get_blast_radius(service_name)

        # Get connected components
        client = await self._get_client()
        relationships = await client.execute_query(
            queries.GET_COMPONENT_RELATIONSHIPS,
            {"name": service.name},
        )

        connected = set()
        for r in relationships:
            if r.get("source") and r["source"] != service.name:
                connected.add(r["source"])
            if r.get("target") and r["target"] != service.name:
                connected.add(r["target"])

        return AlertContext(
            service_name=service.name,
            service_info=service,
            blast_radius=blast_radius,
            connected_components=list(connected),
        )

    def _extract_service_from_alert(self, alert_data: dict[str, Any]) -> str | None:
        """Extract service name from alert data."""
        # Direct field
        if alert_data.get("service"):
            return alert_data["service"]

        # Labels
        labels = alert_data.get("labels", {})
        if isinstance(labels, dict) and labels.get("service"):
            return labels["service"]

        # Try to extract from name/description
        text = f"{alert_data.get('name', '')} {alert_data.get('description', '')}".lower()

        # Known service patterns (can be expanded)
        service_patterns = [
            "cartservice", "checkoutservice", "currencyservice",
            "emailservice", "paymentservice", "productcatalogservice",
            "recommendationservice", "shippingservice", "adservice",
            "frontend", "kafka", "valkey", "redis", "postgres",
        ]

        for pattern in service_patterns:
            if pattern in text.replace("-", "").replace("_", "").replace(" ", ""):
                return pattern

        return None

    # =========================================================================
    # HEALTH & UTILITIES
    # =========================================================================

    async def health_check(self) -> dict[str, Any]:
        """Perform a health check on the service."""
        client = await self._get_client()
        return await client.health_check()

    async def get_schema(self) -> dict[str, Any]:
        """Get the graph database schema."""
        client = await self._get_client()
        return await client.get_schema()

    async def record_incident(self, service: str) -> None:
        """
        Record that an incident occurred for a service.

        Args:
            service: Service name
        """
        client = await self._get_client()
        await client.execute_write(
            queries.RECORD_INCIDENT,
            {"name": service},
        )
        logger.info(f"Recorded incident for service: {service}")


# Module-level service instance
_service: KnowledgeGraphService | None = None


async def get_service(client: Neo4jClient | None = None) -> KnowledgeGraphService:
    """
    Get or create the singleton KnowledgeGraphService.

    Args:
        client: Optional Neo4j client instance

    Returns:
        KnowledgeGraphService instance
    """
    global _service
    if _service is None:
        _service = KnowledgeGraphService(client)
        await _service.initialize()
    return _service
