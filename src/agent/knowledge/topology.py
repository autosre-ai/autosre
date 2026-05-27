"""
Service topology operations.

High-level operations for querying and manipulating the service graph.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .client import Neo4jClient
from .models import Service, Dependency, DependencyType
from .queries import CypherQueries

logger = logging.getLogger(__name__)


@dataclass
class BlastRadiusResult:
    """Result of a blast radius calculation."""
    
    failed_service: Service
    direct_dependents: list[Service] = field(default_factory=list)
    transitive_dependents: list[Service] = field(default_factory=list)
    by_depth: dict[int, list[Service]] = field(default_factory=dict)
    by_tier: dict[str, list[Service]] = field(default_factory=dict)
    
    @property
    def total_affected(self) -> int:
        """Total number of affected services."""
        return len(self.direct_dependents) + len(self.transitive_dependents)
    
    @property
    def has_tier0_impact(self) -> bool:
        """Check if tier 0 services are affected."""
        return "tier_0" in self.by_tier and len(self.by_tier["tier_0"]) > 0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "failed_service": self.failed_service.to_dict(),
            "direct_dependents": [s.to_dict() for s in self.direct_dependents],
            "transitive_dependents": [s.to_dict() for s in self.transitive_dependents],
            "total_affected": self.total_affected,
            "has_tier0_impact": self.has_tier0_impact,
            "by_depth": {
                depth: [s.to_dict() for s in services]
                for depth, services in self.by_depth.items()
            },
            "by_tier": {
                tier: [s.to_dict() for s in services]
                for tier, services in self.by_tier.items()
            },
        }


@dataclass
class ServiceSubgraph:
    """A service and its immediate neighborhood."""
    
    service: Service
    upstream: list[tuple[Service, Dependency]] = field(default_factory=list)
    downstream: list[tuple[Service, Dependency]] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "service": self.service.to_dict(),
            "upstream": [
                {"service": s.to_dict(), "dependency": d.to_dict()}
                for s, d in self.upstream
            ],
            "downstream": [
                {"service": s.to_dict(), "dependency": d.to_dict()}
                for s, d in self.downstream
            ],
        }


class TopologyService:
    """
    Service for querying and manipulating service topology.
    
    Provides high-level operations on the service graph.
    """
    
    def __init__(self, client: Neo4jClient):
        self.client = client
        self.queries = CypherQueries
    
    # =========================================================================
    # Service CRUD
    # =========================================================================
    
    async def create_service(self, service: Service) -> Service:
        """Create or update a service in the graph."""
        result = await self.client.execute_write(
            self.queries.CREATE_SERVICE,
            {"id": service.id, "properties": service.to_dict()}
        )
        logger.info(f"Created/updated service: {service.name}")
        return service
    
    async def get_service(self, service_id: str) -> Service | None:
        """Get a service by ID."""
        result = await self.client.execute_read(
            self.queries.GET_SERVICE,
            {"service_id": service_id}
        )
        if not result:
            return None
        return self._record_to_service(result.single["s"])
    
    async def get_service_by_name(
        self, 
        name: str, 
        namespace: str | None = None
    ) -> Service | None:
        """Get a service by name, optionally filtered by namespace."""
        result = await self.client.execute_read(
            self.queries.GET_SERVICE_BY_NAME,
            {"name": name, "namespace": namespace}
        )
        if not result:
            return None
        return self._record_to_service(result.single["s"])
    
    async def list_services(
        self,
        namespace: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Service]:
        """List all services, optionally filtered by namespace."""
        result = await self.client.execute_read(
            self.queries.LIST_SERVICES,
            {"namespace": namespace, "skip": skip, "limit": limit}
        )
        return [self._record_to_service(r["s"]) for r in result]
    
    async def delete_service(self, service_id: str) -> bool:
        """Delete a service and all its relationships."""
        result = await self.client.execute_write(
            self.queries.DELETE_SERVICE,
            {"service_id": service_id}
        )
        deleted = result.single["deleted"] if result else 0
        if deleted:
            logger.info(f"Deleted service: {service_id}")
        return deleted > 0
    
    # =========================================================================
    # Dependencies
    # =========================================================================
    
    async def create_dependency(self, dependency: Dependency) -> Dependency:
        """Create a dependency relationship between services."""
        result = await self.client.execute_write(
            self.queries.CREATE_DEPENDENCY,
            {
                "source_id": dependency.source_id,
                "target_id": dependency.target_id,
                "properties": dependency.to_dict(),
            }
        )
        logger.info(
            f"Created dependency: {dependency.source_id} -> {dependency.target_id}"
        )
        return dependency
    
    async def get_service_dependencies(
        self, 
        service_id: str
    ) -> list[tuple[Service, Dependency]]:
        """
        Get all services this service depends on (downstream).
        
        Returns tuples of (dependency_service, dependency_relationship).
        """
        result = await self.client.execute_read(
            self.queries.GET_DEPENDENCIES,
            {"service_id": service_id}
        )
        return [
            (
                self._record_to_service(r["service"]),
                self._record_to_dependency(r["dependency"], service_id, r["service"]["id"])
            )
            for r in result
        ]
    
    async def get_downstream_services(
        self, 
        service_id: str
    ) -> list[Service]:
        """
        Get all services this service calls (its dependencies).
        
        "Downstream" = what this service depends on.
        """
        deps = await self.get_service_dependencies(service_id)
        return [service for service, _ in deps]
    
    async def get_upstream_services(
        self, 
        service_id: str
    ) -> list[Service]:
        """
        Get all services that depend on this service.
        
        "Upstream" = what calls this service.
        """
        result = await self.client.execute_read(
            self.queries.GET_DEPENDENTS,
            {"service_id": service_id}
        )
        return [self._record_to_service(r["service"]) for r in result]
    
    async def get_all_dependencies(
        self, 
        service_id: str,
        max_depth: int | None = None,
    ) -> list[tuple[Service, int]]:
        """
        Get all transitive dependencies (what this service ultimately depends on).
        
        Returns list of (service, depth) tuples.
        """
        result = await self.client.execute_read(
            self.queries.GET_ALL_DEPENDENCIES,
            {"service_id": service_id}
        )
        deps = [
            (self._record_to_service(r["service"]), r["depth"])
            for r in result
        ]
        if max_depth:
            deps = [(s, d) for s, d in deps if d <= max_depth]
        return deps
    
    # =========================================================================
    # Blast Radius
    # =========================================================================
    
    async def get_blast_radius(self, service_id: str) -> BlastRadiusResult:
        """
        Calculate the blast radius if a service fails.
        
        Returns all services that would be affected, categorized by:
        - Direct vs transitive impact
        - Depth of impact
        - Service tier
        """
        # Get the failed service
        service = await self.get_service(service_id)
        if not service:
            raise ValueError(f"Service not found: {service_id}")
        
        # Get basic blast radius
        result = await self.client.execute_read(
            self.queries.GET_BLAST_RADIUS,
            {"service_id": service_id}
        )
        
        if not result:
            return BlastRadiusResult(failed_service=service)
        
        record = result.single
        direct = [self._record_to_service(s) for s in (record.get("direct_deps") or [])]
        transitive = [self._record_to_service(s) for s in (record.get("transitive_deps") or [])]
        
        # Get depth information
        depth_result = await self.client.execute_read(
            self.queries.GET_BLAST_RADIUS_WITH_DEPTH,
            {"service_id": service_id}
        )
        
        by_depth: dict[int, list[Service]] = {}
        for r in depth_result:
            depth = r["depth"]
            svc = self._record_to_service(r["affected"])
            if depth not in by_depth:
                by_depth[depth] = []
            by_depth[depth].append(svc)
        
        # Get tier information
        tier_result = await self.client.execute_read(
            self.queries.GET_BLAST_RADIUS_BY_TIER,
            {"service_id": service_id}
        )
        
        by_tier: dict[str, list[Service]] = {}
        for r in tier_result:
            tier = r["tier"]
            services = [self._record_to_service(s) for s in r["services"]]
            by_tier[tier] = services
        
        return BlastRadiusResult(
            failed_service=service,
            direct_dependents=direct,
            transitive_dependents=transitive,
            by_depth=by_depth,
            by_tier=by_tier,
        )
    
    # =========================================================================
    # Topology Queries
    # =========================================================================
    
    async def get_service_details(self, service_id: str) -> ServiceSubgraph | None:
        """
        Get detailed information about a service and its immediate neighborhood.
        
        Returns the service with its upstream and downstream dependencies.
        """
        result = await self.client.execute_read(
            self.queries.GET_SERVICE_SUBGRAPH,
            {"service_id": service_id}
        )
        
        if not result:
            return None
        
        record = result.single
        center = self._record_to_service(record["center"])
        
        upstream = []
        for item in record.get("upstream") or []:
            if item.get("service"):
                svc = self._record_to_service(item["service"])
                dep = self._record_to_dependency(
                    item["rel"], 
                    service_id, 
                    item["service"]["id"]
                )
                upstream.append((svc, dep))
        
        downstream = []
        for item in record.get("downstream") or []:
            if item.get("service"):
                svc = self._record_to_service(item["service"])
                dep = self._record_to_dependency(
                    item["rel"],
                    item["service"]["id"],
                    service_id
                )
                downstream.append((svc, dep))
        
        return ServiceSubgraph(
            service=center,
            upstream=upstream,
            downstream=downstream,
        )
    
    async def find_path(
        self, 
        source_id: str, 
        target_id: str
    ) -> list[Service] | None:
        """Find the shortest dependency path between two services."""
        result = await self.client.execute_read(
            self.queries.FIND_PATHS,
            {"source_id": source_id, "target_id": target_id}
        )
        
        if not result:
            return None
        
        path_record = result.single.get("path")
        if not path_record:
            return None
        
        # Extract nodes from path
        return [self._record_to_service(node) for node in path_record.nodes]
    
    async def find_all_paths(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5,
        limit: int = 10,
    ) -> list[list[Service]]:
        """Find all dependency paths between two services."""
        result = await self.client.execute_read(
            self.queries.FIND_ALL_PATHS,
            {
                "source_id": source_id,
                "target_id": target_id,
                "max_depth": max_depth,
                "limit": limit,
            }
        )
        
        paths = []
        for record in result:
            path_record = record.get("path")
            if path_record:
                path = [self._record_to_service(node) for node in path_record.nodes]
                paths.append(path)
        
        return paths
    
    async def get_critical_path(
        self, 
        service_id: str, 
        limit: int = 10
    ) -> list[list[Service]]:
        """
        Get critical dependency paths (all critical=true relationships).
        
        These are paths where failure of any service would cascade.
        """
        result = await self.client.execute_read(
            self.queries.GET_CRITICAL_PATH,
            {"service_id": service_id, "limit": limit}
        )
        
        paths = []
        for record in result:
            path_record = record.get("path")
            if path_record:
                path = [self._record_to_service(node) for node in path_record.nodes]
                paths.append(path)
        
        return paths
    
    # =========================================================================
    # Analytics
    # =========================================================================
    
    async def get_most_depended_on(self, limit: int = 10) -> list[tuple[Service, int]]:
        """Get services with the most dependents (potential impact points)."""
        result = await self.client.execute_read(
            self.queries.GET_MOST_DEPENDED_ON,
            {"limit": limit}
        )
        return [
            (self._record_to_service(r["s"]), r["dependent_count"])
            for r in result
        ]
    
    async def get_most_dependencies(self, limit: int = 10) -> list[tuple[Service, int]]:
        """Get services with the most dependencies (potential fragility points)."""
        result = await self.client.execute_read(
            self.queries.GET_MOST_DEPENDENCIES,
            {"limit": limit}
        )
        return [
            (self._record_to_service(r["s"]), r["dependency_count"])
            for r in result
        ]
    
    async def get_orphan_services(self) -> list[Service]:
        """Get services with no dependencies and no dependents."""
        result = await self.client.execute_read(
            self.queries.GET_ORPHAN_SERVICES,
            {}
        )
        return [self._record_to_service(r["s"]) for r in result]
    
    async def find_circular_dependencies(
        self, 
        limit: int = 10
    ) -> list[list[Service]]:
        """Find circular dependency chains."""
        result = await self.client.execute_read(
            self.queries.GET_CIRCULAR_DEPENDENCIES,
            {"limit": limit}
        )
        
        cycles = []
        for record in result:
            path_record = record.get("path")
            if path_record:
                cycle = [self._record_to_service(node) for node in path_record.nodes]
                cycles.append(cycle)
        
        return cycles
    
    async def get_unhealthy_services(self) -> list[tuple[Service, list[Service]]]:
        """
        Get unhealthy services and the services that might be affected.
        
        Returns tuples of (unhealthy_service, potentially_affected_services).
        """
        result = await self.client.execute_read(
            self.queries.GET_UNHEALTHY_SERVICES,
            {}
        )
        return [
            (
                self._record_to_service(r["s"]),
                [self._record_to_service(s) for s in r.get("potentially_affected") or []]
            )
            for r in result
        ]
    
    # =========================================================================
    # Helpers
    # =========================================================================
    
    def _record_to_service(self, record: dict[str, Any]) -> Service:
        """Convert a Neo4j record to a Service model."""
        from .models import ServiceStatus, ServiceTier
        
        # Handle Neo4j node wrapper
        if hasattr(record, '__iter__') and not isinstance(record, dict):
            record = dict(record)
        
        return Service(
            id=record.get("id", ""),
            name=record.get("name", ""),
            namespace=record.get("namespace", "default"),
            version=record.get("version", ""),
            tier=ServiceTier(record.get("tier", "tier_3")),
            status=ServiceStatus(record.get("status", "unknown")),
            team=record.get("team", ""),
            owner=record.get("owner", ""),
            repository=record.get("repository", ""),
            description=record.get("description", ""),
            language=record.get("language", ""),
            framework=record.get("framework", ""),
            runtime=record.get("runtime", ""),
            slo_availability=record.get("slo_availability", 99.9),
            slo_latency_p99_ms=record.get("slo_latency_p99_ms", 500),
            endpoints=record.get("endpoints", []),
            replicas=record.get("replicas", 1),
            cpu_request=record.get("cpu_request", ""),
            memory_request=record.get("memory_request", ""),
            labels=record.get("labels", {}),
            annotations=record.get("annotations", {}),
        )
    
    def _record_to_dependency(
        self,
        record: dict[str, Any],
        source_id: str,
        target_id: str,
    ) -> Dependency:
        """Convert a Neo4j relationship record to a Dependency model."""
        if hasattr(record, '__iter__') and not isinstance(record, dict):
            record = dict(record)
        
        return Dependency(
            source_id=source_id,
            target_id=target_id,
            dependency_type=DependencyType(
                record.get("dependency_type", "sync")
            ),
            protocol=record.get("protocol", "http"),
            port=record.get("port", 80),
            path=record.get("path", ""),
            calls_per_minute=record.get("calls_per_minute", 0.0),
            latency_p50_ms=record.get("latency_p50_ms", 0.0),
            latency_p99_ms=record.get("latency_p99_ms", 0.0),
            error_rate=record.get("error_rate", 0.0),
            is_critical=record.get("is_critical", False),
            has_fallback=record.get("has_fallback", False),
            timeout_ms=record.get("timeout_ms", 30000),
            retry_count=record.get("retry_count", 3),
            circuit_breaker=record.get("circuit_breaker", False),
        )
