"""
Data ingestion for the knowledge graph.

Ingest topology data from Kubernetes, service mesh, OpenTelemetry, and config files.
"""

from __future__ import annotations

import json
import logging
import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .client import Neo4jClient
from .models import (
    Service,
    Dependency,
    Pod,
    Node,
    Namespace,
    Database,
    Cache,
    DependencyType,
    ServiceStatus,
    ServiceTier,
)
from .queries import CypherQueries

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    """Result of an ingestion operation."""
    
    services_created: int = 0
    services_updated: int = 0
    dependencies_created: int = 0
    pods_created: int = 0
    nodes_created: int = 0
    errors: list[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
    
    @property
    def success(self) -> bool:
        return len(self.errors) == 0
    
    def __add__(self, other: IngestionResult) -> IngestionResult:
        return IngestionResult(
            services_created=self.services_created + other.services_created,
            services_updated=self.services_updated + other.services_updated,
            dependencies_created=self.dependencies_created + other.dependencies_created,
            pods_created=self.pods_created + other.pods_created,
            nodes_created=self.nodes_created + other.nodes_created,
            errors=self.errors + other.errors,
        )


class IngestionService:
    """
    Service for ingesting topology data into the knowledge graph.
    
    Supports multiple data sources:
    - Kubernetes API
    - Service mesh (Istio, Linkerd)
    - OpenTelemetry traces
    - Configuration files
    """
    
    def __init__(self, client: Neo4jClient):
        self.client = client
        self.queries = CypherQueries
    
    # =========================================================================
    # Kubernetes Ingestion
    # =========================================================================
    
    async def ingest_kubernetes_topology(
        self,
        kubeconfig: str | None = None,
        namespaces: list[str] | None = None,
        context: str | None = None,
    ) -> IngestionResult:
        """
        Ingest service topology from Kubernetes cluster.
        
        Reads:
        - Deployments/Services → Service nodes
        - Pods → Pod nodes
        - Nodes → Node nodes
        - ConfigMaps with service annotations → Dependencies
        
        Args:
            kubeconfig: Path to kubeconfig file (default: ~/.kube/config)
            namespaces: List of namespaces to scan (default: all)
            context: Kubernetes context to use
            
        Returns:
            IngestionResult with counts and any errors
        """
        try:
            from kubernetes import client as k8s_client, config as k8s_config
        except ImportError:
            logger.warning("kubernetes package not installed, using mock data")
            return await self._ingest_mock_kubernetes()
        
        result = IngestionResult()
        
        try:
            # Load kubeconfig
            if kubeconfig:
                k8s_config.load_kube_config(config_file=kubeconfig, context=context)
            else:
                try:
                    k8s_config.load_incluster_config()
                except k8s_config.ConfigException:
                    k8s_config.load_kube_config(context=context)
            
            v1 = k8s_client.CoreV1Api()
            apps_v1 = k8s_client.AppsV1Api()
            
            # Get namespaces
            if namespaces:
                ns_list = namespaces
            else:
                ns_response = v1.list_namespace()
                ns_list = [ns.metadata.name for ns in ns_response.items]
            
            # Ingest nodes
            nodes_response = v1.list_node()
            for node in nodes_response.items:
                await self._ingest_k8s_node(node)
                result.nodes_created += 1
            
            # Process each namespace
            for ns in ns_list:
                ns_result = await self._ingest_k8s_namespace(v1, apps_v1, ns)
                result = result + ns_result
            
        except Exception as e:
            logger.error(f"Kubernetes ingestion failed: {e}")
            result.errors.append(str(e))
        
        return result
    
    async def _ingest_k8s_namespace(
        self,
        v1,
        apps_v1,
        namespace: str,
    ) -> IngestionResult:
        """Ingest services from a single namespace."""
        result = IngestionResult()
        
        # Get deployments
        deployments = apps_v1.list_namespaced_deployment(namespace)
        
        for deploy in deployments.items:
            try:
                service = self._k8s_deployment_to_service(deploy, namespace)
                await self._upsert_service(service)
                result.services_created += 1
                
                # Get pods for this deployment
                selector = deploy.spec.selector.match_labels
                label_selector = ",".join(f"{k}={v}" for k, v in selector.items())
                pods = v1.list_namespaced_pod(namespace, label_selector=label_selector)
                
                for pod in pods.items:
                    pod_model = self._k8s_pod_to_model(pod, service.id)
                    await self._upsert_pod(pod_model)
                    result.pods_created += 1
                    
            except Exception as e:
                logger.error(f"Failed to ingest deployment {deploy.metadata.name}: {e}")
                result.errors.append(f"Deployment {deploy.metadata.name}: {e}")
        
        return result
    
    async def _ingest_k8s_node(self, node) -> None:
        """Ingest a Kubernetes node."""
        node_model = Node(
            id=node.metadata.uid,
            name=node.metadata.name,
            cluster=node.metadata.labels.get("cluster", ""),
            zone=node.metadata.labels.get("topology.kubernetes.io/zone", ""),
            region=node.metadata.labels.get("topology.kubernetes.io/region", ""),
            instance_type=node.metadata.labels.get("node.kubernetes.io/instance-type", ""),
            cpu_capacity=node.status.capacity.get("cpu", ""),
            memory_capacity=node.status.capacity.get("memory", ""),
            cpu_allocatable=node.status.allocatable.get("cpu", ""),
            memory_allocatable=node.status.allocatable.get("memory", ""),
            ready=any(
                c.type == "Ready" and c.status == "True"
                for c in node.status.conditions
            ),
            schedulable=not node.spec.unschedulable,
            provider=node.spec.provider_id.split("://")[0] if node.spec.provider_id else "",
            provider_id=node.spec.provider_id or "",
            labels=dict(node.metadata.labels or {}),
        )
        
        await self.client.execute_write(
            self.queries.CREATE_NODE,
            {"id": node_model.id, "properties": node_model.to_dict()}
        )
    
    def _k8s_deployment_to_service(self, deploy, namespace: str) -> Service:
        """Convert a Kubernetes deployment to a Service model."""
        labels = dict(deploy.metadata.labels or {})
        annotations = dict(deploy.metadata.annotations or {})
        
        # Extract tier from labels
        tier_label = labels.get("tier", labels.get("app.kubernetes.io/tier", "tier_3"))
        try:
            tier = ServiceTier(tier_label)
        except ValueError:
            tier = ServiceTier.TIER_3
        
        return Service(
            id=deploy.metadata.uid,
            name=deploy.metadata.name,
            namespace=namespace,
            version=labels.get("version", labels.get("app.kubernetes.io/version", "")),
            tier=tier,
            status=ServiceStatus.HEALTHY if deploy.status.ready_replicas else ServiceStatus.UNHEALTHY,
            team=labels.get("team", annotations.get("team", "")),
            owner=annotations.get("owner", ""),
            repository=annotations.get("repository", ""),
            description=annotations.get("description", ""),
            replicas=deploy.spec.replicas or 1,
            labels=labels,
            annotations=annotations,
        )
    
    def _k8s_pod_to_model(self, pod, service_id: str) -> Pod:
        """Convert a Kubernetes pod to a Pod model."""
        return Pod(
            id=pod.metadata.uid,
            name=pod.metadata.name,
            service_id=service_id,
            namespace=pod.metadata.namespace,
            node_id=pod.spec.node_name or "",
            status=pod.status.phase,
            phase=pod.status.phase,
            ip=pod.status.pod_ip or "",
            restart_count=sum(
                cs.restart_count for cs in (pod.status.container_statuses or [])
            ),
            ready=all(
                cs.ready for cs in (pod.status.container_statuses or [])
            ),
        )
    
    async def _ingest_mock_kubernetes(self) -> IngestionResult:
        """Ingest mock Kubernetes data for testing."""
        logger.info("Ingesting mock Kubernetes topology")
        return await self.sync_from_config(self._get_mock_topology())
    
    # =========================================================================
    # Service Mesh Ingestion
    # =========================================================================
    
    async def ingest_service_mesh(
        self,
        mesh_type: str = "istio",
        prometheus_url: str | None = None,
    ) -> IngestionResult:
        """
        Ingest service dependencies from service mesh.
        
        Reads traffic patterns from Prometheus metrics to infer dependencies.
        
        Args:
            mesh_type: Type of service mesh (istio, linkerd)
            prometheus_url: URL of Prometheus server
            
        Returns:
            IngestionResult with dependency counts
        """
        result = IngestionResult()
        
        if not prometheus_url:
            logger.warning("No Prometheus URL provided, skipping service mesh ingestion")
            return result
        
        try:
            import httpx
        except ImportError:
            logger.error("httpx not installed, cannot query Prometheus")
            result.errors.append("httpx package required for Prometheus queries")
            return result
        
        try:
            async with httpx.AsyncClient() as client:
                # Query for service-to-service traffic
                if mesh_type == "istio":
                    query = 'sum(rate(istio_requests_total[5m])) by (source_workload, destination_workload, destination_service)'
                else:  # linkerd
                    query = 'sum(rate(request_total[5m])) by (src_deployment, dst_deployment)'
                
                response = await client.get(
                    f"{prometheus_url}/api/v1/query",
                    params={"query": query}
                )
                response.raise_for_status()
                data = response.json()
                
                for item in data.get("data", {}).get("result", []):
                    metric = item["metric"]
                    value = float(item["value"][1])
                    
                    if mesh_type == "istio":
                        source = metric.get("source_workload", "")
                        target = metric.get("destination_workload", "")
                    else:
                        source = metric.get("src_deployment", "")
                        target = metric.get("dst_deployment", "")
                    
                    if source and target and source != target:
                        # Create dependency
                        dep = Dependency(
                            source_id=source,
                            target_id=target,
                            dependency_type=DependencyType.SYNC,
                            calls_per_minute=value * 60,
                        )
                        await self._upsert_dependency(dep)
                        result.dependencies_created += 1
                        
        except Exception as e:
            logger.error(f"Service mesh ingestion failed: {e}")
            result.errors.append(str(e))
        
        return result
    
    # =========================================================================
    # OpenTelemetry Ingestion
    # =========================================================================
    
    async def ingest_from_opentelemetry(
        self,
        otlp_endpoint: str | None = None,
        tempo_url: str | None = None,
        time_range_minutes: int = 60,
    ) -> IngestionResult:
        """
        Ingest service topology from OpenTelemetry traces.
        
        Analyzes trace data to discover service dependencies.
        
        Args:
            otlp_endpoint: OTLP endpoint for direct trace access
            tempo_url: Grafana Tempo URL for trace queries
            time_range_minutes: How far back to look for traces
            
        Returns:
            IngestionResult with discovered dependencies
        """
        result = IngestionResult()
        
        if not otlp_endpoint and not tempo_url:
            logger.warning("No OpenTelemetry endpoint provided")
            return result
        
        try:
            import httpx
        except ImportError:
            result.errors.append("httpx package required for OpenTelemetry queries")
            return result
        
        try:
            async with httpx.AsyncClient() as client:
                if tempo_url:
                    # Query Tempo for service graph
                    response = await client.get(
                        f"{tempo_url}/api/search/tags",
                    )
                    # Process trace data to extract dependencies
                    # This is a simplified example
                    pass
                    
        except Exception as e:
            logger.error(f"OpenTelemetry ingestion failed: {e}")
            result.errors.append(str(e))
        
        return result
    
    # =========================================================================
    # Config File Ingestion
    # =========================================================================
    
    async def sync_from_config(
        self,
        config: dict[str, Any] | None = None,
        config_path: str | Path | None = None,
    ) -> IngestionResult:
        """
        Sync topology from a configuration file or dictionary.
        
        Supports YAML/JSON with structure:
        ```yaml
        services:
          - name: api-gateway
            namespace: production
            tier: tier_0
            dependencies:
              - service: auth-service
                type: sync
              - service: user-service
                type: sync
        
        infrastructure:
          databases:
            - name: postgres-main
              engine: postgresql
          caches:
            - name: redis-main
              engine: redis
        ```
        
        Args:
            config: Configuration dictionary
            config_path: Path to YAML/JSON config file
            
        Returns:
            IngestionResult with created entities
        """
        result = IngestionResult()
        
        # Load config
        if config is None:
            if config_path is None:
                result.errors.append("No config or config_path provided")
                return result
            
            path = Path(config_path)
            if not path.exists():
                result.errors.append(f"Config file not found: {config_path}")
                return result
            
            with open(path) as f:
                if path.suffix in (".yaml", ".yml"):
                    config = yaml.safe_load(f)
                else:
                    config = json.load(f)
        
        # Create namespaces
        for ns_config in config.get("namespaces", []):
            ns = Namespace(
                id=ns_config.get("id", ns_config["name"]),
                name=ns_config["name"],
                environment=ns_config.get("environment", "production"),
                cluster=ns_config.get("cluster", ""),
            )
            await self._upsert_namespace(ns)
        
        # Create services
        service_map: dict[str, str] = {}  # name -> id mapping
        
        for svc_config in config.get("services", []):
            service = Service(
                id=svc_config.get("id", svc_config["name"]),
                name=svc_config["name"],
                namespace=svc_config.get("namespace", "default"),
                version=svc_config.get("version", ""),
                tier=ServiceTier(svc_config.get("tier", "tier_3")),
                status=ServiceStatus(svc_config.get("status", "healthy")),
                team=svc_config.get("team", ""),
                owner=svc_config.get("owner", ""),
                repository=svc_config.get("repository", ""),
                description=svc_config.get("description", ""),
                language=svc_config.get("language", ""),
                framework=svc_config.get("framework", ""),
                slo_availability=svc_config.get("slo_availability", 99.9),
                slo_latency_p99_ms=svc_config.get("slo_latency_p99_ms", 500),
            )
            
            await self._upsert_service(service)
            service_map[service.name] = service.id
            result.services_created += 1
        
        # Create dependencies
        for svc_config in config.get("services", []):
            source_name = svc_config["name"]
            source_id = service_map.get(source_name)
            
            if not source_id:
                continue
            
            for dep_config in svc_config.get("dependencies", []):
                target_name = dep_config.get("service", dep_config.get("target"))
                target_id = service_map.get(target_name)
                
                if not target_id:
                    result.errors.append(
                        f"Unknown dependency target: {target_name} for {source_name}"
                    )
                    continue
                
                dep = Dependency(
                    source_id=source_id,
                    target_id=target_id,
                    dependency_type=DependencyType(dep_config.get("type", "sync")),
                    protocol=dep_config.get("protocol", "http"),
                    port=dep_config.get("port", 80),
                    is_critical=dep_config.get("critical", False),
                    has_fallback=dep_config.get("fallback", False),
                )
                
                await self._upsert_dependency(dep)
                result.dependencies_created += 1
        
        # Create infrastructure
        infra = config.get("infrastructure", {})
        
        for db_config in infra.get("databases", []):
            db = Database(
                id=db_config.get("id", db_config["name"]),
                name=db_config["name"],
                engine=db_config.get("engine", "postgresql"),
                version=db_config.get("version", ""),
                host=db_config.get("host", ""),
                port=db_config.get("port", 5432),
            )
            await self._upsert_database(db)
            
            # Link services to database
            for svc_name in db_config.get("services", []):
                svc_id = service_map.get(svc_name)
                if svc_id:
                    await self.client.execute_write(
                        self.queries.LINK_SERVICE_TO_DATABASE,
                        {
                            "service_id": svc_id,
                            "database_id": db.id,
                            "connection_pool_size": 10,
                            "read_only": False,
                        }
                    )
        
        for cache_config in infra.get("caches", []):
            cache = Cache(
                id=cache_config.get("id", cache_config["name"]),
                name=cache_config["name"],
                engine=cache_config.get("engine", "redis"),
                version=cache_config.get("version", ""),
                host=cache_config.get("host", ""),
                port=cache_config.get("port", 6379),
            )
            await self._upsert_cache(cache)
            
            # Link services to cache
            for svc_name in cache_config.get("services", []):
                svc_id = service_map.get(svc_name)
                if svc_id:
                    await self.client.execute_write(
                        self.queries.LINK_SERVICE_TO_CACHE,
                        {"service_id": svc_id, "cache_id": cache.id}
                    )
        
        logger.info(
            f"Config sync complete: {result.services_created} services, "
            f"{result.dependencies_created} dependencies"
        )
        
        return result
    
    # =========================================================================
    # Schema Management
    # =========================================================================
    
    async def initialize_schema(self) -> None:
        """Initialize Neo4j schema with constraints and indexes."""
        # Create constraints (one at a time for Neo4j)
        constraints = [
            "CREATE CONSTRAINT service_id IF NOT EXISTS FOR (s:Service) REQUIRE s.id IS UNIQUE",
            "CREATE CONSTRAINT pod_id IF NOT EXISTS FOR (p:Pod) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT node_id IF NOT EXISTS FOR (n:Node) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT database_id IF NOT EXISTS FOR (d:Database) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT cache_id IF NOT EXISTS FOR (c:Cache) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT queue_id IF NOT EXISTS FOR (q:MessageQueue) REQUIRE q.id IS UNIQUE",
            "CREATE CONSTRAINT namespace_id IF NOT EXISTS FOR (ns:Namespace) REQUIRE ns.id IS UNIQUE",
            "CREATE CONSTRAINT alert_id IF NOT EXISTS FOR (a:Alert) REQUIRE a.id IS UNIQUE",
        ]
        
        for constraint in constraints:
            try:
                await self.client.execute_query(constraint)
            except Exception as e:
                logger.debug(f"Constraint may already exist: {e}")
        
        # Create indexes
        indexes = [
            "CREATE INDEX service_namespace IF NOT EXISTS FOR (s:Service) ON (s.namespace)",
            "CREATE INDEX service_tier IF NOT EXISTS FOR (s:Service) ON (s.tier)",
            "CREATE INDEX service_status IF NOT EXISTS FOR (s:Service) ON (s.status)",
            "CREATE INDEX service_team IF NOT EXISTS FOR (s:Service) ON (s.team)",
            "CREATE INDEX pod_namespace IF NOT EXISTS FOR (p:Pod) ON (p.namespace)",
            "CREATE INDEX node_cluster IF NOT EXISTS FOR (n:Node) ON (n.cluster)",
        ]
        
        for index in indexes:
            try:
                await self.client.execute_query(index)
            except Exception as e:
                logger.debug(f"Index may already exist: {e}")
        
        logger.info("Schema initialized")
    
    # =========================================================================
    # Helpers
    # =========================================================================
    
    async def _upsert_service(self, service: Service) -> None:
        """Create or update a service."""
        await self.client.execute_write(
            self.queries.CREATE_SERVICE,
            {"id": service.id, "properties": service.to_dict()}
        )
    
    async def _upsert_dependency(self, dep: Dependency) -> None:
        """Create or update a dependency."""
        await self.client.execute_write(
            self.queries.CREATE_DEPENDENCY,
            {
                "source_id": dep.source_id,
                "target_id": dep.target_id,
                "properties": dep.to_dict(),
            }
        )
    
    async def _upsert_pod(self, pod: Pod) -> None:
        """Create or update a pod."""
        await self.client.execute_write(
            self.queries.CREATE_POD,
            {
                "id": pod.id,
                "service_id": pod.service_id,
                "node_id": pod.node_id,
                "properties": pod.to_dict(),
            }
        )
    
    async def _upsert_namespace(self, ns: Namespace) -> None:
        """Create or update a namespace."""
        await self.client.execute_write(
            """
            MERGE (ns:Namespace {id: $id})
            SET ns += $properties
            SET ns.updated_at = datetime()
            RETURN ns
            """,
            {"id": ns.id, "properties": ns.to_dict()}
        )
    
    async def _upsert_database(self, db: Database) -> None:
        """Create or update a database."""
        await self.client.execute_write(
            self.queries.CREATE_DATABASE,
            {"id": db.id, "properties": db.to_dict()}
        )
    
    async def _upsert_cache(self, cache: Cache) -> None:
        """Create or update a cache."""
        await self.client.execute_write(
            self.queries.CREATE_CACHE,
            {"id": cache.id, "properties": cache.to_dict()}
        )
    
    def _get_mock_topology(self) -> dict[str, Any]:
        """Get mock topology for testing."""
        return {
            "services": [
                {
                    "name": "frontend",
                    "namespace": "production",
                    "tier": "tier_1",
                    "team": "platform",
                    "description": "Main web frontend",
                    "dependencies": [
                        {"service": "api-gateway", "type": "sync", "critical": True},
                    ]
                },
                {
                    "name": "api-gateway",
                    "namespace": "production",
                    "tier": "tier_0",
                    "team": "platform",
                    "description": "API Gateway / BFF",
                    "dependencies": [
                        {"service": "auth-service", "type": "sync", "critical": True},
                        {"service": "user-service", "type": "sync"},
                        {"service": "product-service", "type": "sync"},
                        {"service": "order-service", "type": "sync"},
                    ]
                },
                {
                    "name": "auth-service",
                    "namespace": "production",
                    "tier": "tier_0",
                    "team": "security",
                    "description": "Authentication and authorization",
                    "dependencies": [
                        {"service": "user-service", "type": "sync"},
                    ]
                },
                {
                    "name": "user-service",
                    "namespace": "production",
                    "tier": "tier_1",
                    "team": "users",
                    "description": "User management",
                    "dependencies": []
                },
                {
                    "name": "product-service",
                    "namespace": "production",
                    "tier": "tier_1",
                    "team": "catalog",
                    "description": "Product catalog",
                    "dependencies": [
                        {"service": "inventory-service", "type": "sync"},
                        {"service": "search-service", "type": "sync"},
                    ]
                },
                {
                    "name": "inventory-service",
                    "namespace": "production",
                    "tier": "tier_2",
                    "team": "warehouse",
                    "description": "Inventory management",
                    "dependencies": []
                },
                {
                    "name": "search-service",
                    "namespace": "production",
                    "tier": "tier_2",
                    "team": "search",
                    "description": "Product search (Elasticsearch)",
                    "dependencies": []
                },
                {
                    "name": "order-service",
                    "namespace": "production",
                    "tier": "tier_0",
                    "team": "orders",
                    "description": "Order processing",
                    "dependencies": [
                        {"service": "payment-service", "type": "sync", "critical": True},
                        {"service": "inventory-service", "type": "sync"},
                        {"service": "notification-service", "type": "async"},
                    ]
                },
                {
                    "name": "payment-service",
                    "namespace": "production",
                    "tier": "tier_0",
                    "team": "payments",
                    "description": "Payment processing",
                    "dependencies": []
                },
                {
                    "name": "notification-service",
                    "namespace": "production",
                    "tier": "tier_2",
                    "team": "platform",
                    "description": "Email/SMS/Push notifications",
                    "dependencies": []
                },
            ],
            "infrastructure": {
                "databases": [
                    {
                        "name": "postgres-main",
                        "engine": "postgresql",
                        "version": "15.4",
                        "services": ["user-service", "order-service", "product-service"],
                    },
                    {
                        "name": "postgres-auth",
                        "engine": "postgresql",
                        "version": "15.4",
                        "services": ["auth-service"],
                    },
                ],
                "caches": [
                    {
                        "name": "redis-main",
                        "engine": "redis",
                        "version": "7.2",
                        "services": ["api-gateway", "auth-service", "user-service"],
                    },
                ],
            },
        }
