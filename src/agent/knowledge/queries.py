"""
Cypher query templates for the knowledge graph.

Provides parameterized queries for common operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CypherQueries:
    """
    Collection of Cypher query templates.
    
    All queries are parameterized for safety and efficiency.
    """
    
    # =========================================================================
    # Service Queries
    # =========================================================================
    
    CREATE_SERVICE = """
        MERGE (s:Service {id: $id})
        SET s += $properties
        SET s.updated_at = datetime()
        RETURN s
    """
    
    GET_SERVICE = """
        MATCH (s:Service {id: $service_id})
        RETURN s
    """
    
    GET_SERVICE_BY_NAME = """
        MATCH (s:Service {name: $name})
        OPTIONAL MATCH (s)-[:IN_NAMESPACE]->(ns:Namespace)
        WHERE ns.name = $namespace OR $namespace IS NULL
        RETURN s
    """
    
    LIST_SERVICES = """
        MATCH (s:Service)
        WHERE s.namespace = $namespace OR $namespace IS NULL
        RETURN s
        ORDER BY s.name
        SKIP $skip
        LIMIT $limit
    """
    
    DELETE_SERVICE = """
        MATCH (s:Service {id: $service_id})
        DETACH DELETE s
        RETURN count(s) as deleted
    """
    
    # =========================================================================
    # Dependency Queries
    # =========================================================================
    
    CREATE_DEPENDENCY = """
        MATCH (source:Service {id: $source_id})
        MATCH (target:Service {id: $target_id})
        MERGE (source)-[d:DEPENDS_ON]->(target)
        SET d += $properties
        SET d.updated_at = datetime()
        RETURN source, d, target
    """
    
    GET_DEPENDENCIES = """
        MATCH (s:Service {id: $service_id})-[d:DEPENDS_ON]->(dep:Service)
        RETURN dep as service, d as dependency
        ORDER BY dep.name
    """
    
    GET_DEPENDENTS = """
        MATCH (dep:Service)-[d:DEPENDS_ON]->(s:Service {id: $service_id})
        RETURN dep as service, d as dependency
        ORDER BY dep.name
    """
    
    GET_ALL_DEPENDENCIES = """
        MATCH (s:Service {id: $service_id})-[d:DEPENDS_ON*1..]->(dep:Service)
        RETURN DISTINCT dep as service, length(d) as depth
        ORDER BY depth, dep.name
    """
    
    GET_CRITICAL_PATH = """
        MATCH path = (s:Service {id: $service_id})-[:DEPENDS_ON*]->(dep:Service)
        WHERE ALL(r IN relationships(path) WHERE r.is_critical = true)
        RETURN path
        ORDER BY length(path) DESC
        LIMIT $limit
    """
    
    # =========================================================================
    # Blast Radius Queries
    # =========================================================================
    
    GET_BLAST_RADIUS = """
        // Find all services that would be affected if this service fails
        MATCH (failed:Service {id: $service_id})
        
        // Get direct dependents (services that call this one)
        OPTIONAL MATCH (direct:Service)-[:DEPENDS_ON]->(failed)
        
        // Get transitive dependents
        OPTIONAL MATCH (transitive:Service)-[:DEPENDS_ON*2..]->(failed)
        
        WITH failed, 
             collect(DISTINCT direct) as direct_deps,
             collect(DISTINCT transitive) as transitive_deps
        
        RETURN failed,
               direct_deps,
               transitive_deps,
               size(direct_deps) as direct_count,
               size(transitive_deps) as transitive_count
    """
    
    GET_BLAST_RADIUS_WITH_DEPTH = """
        MATCH (failed:Service {id: $service_id})
        MATCH path = (affected:Service)-[:DEPENDS_ON*1..]->(failed)
        WITH affected, min(length(path)) as depth
        RETURN affected, depth
        ORDER BY depth, affected.name
    """
    
    GET_BLAST_RADIUS_BY_TIER = """
        MATCH (failed:Service {id: $service_id})
        MATCH (affected:Service)-[:DEPENDS_ON*1..]->(failed)
        WITH affected.tier as tier, collect(affected) as services
        RETURN tier, services, size(services) as count
        ORDER BY tier
    """
    
    # =========================================================================
    # Topology Queries
    # =========================================================================
    
    GET_FULL_TOPOLOGY = """
        MATCH (s:Service)
        OPTIONAL MATCH (s)-[d:DEPENDS_ON]->(dep:Service)
        RETURN s as service, collect({target: dep, rel: d}) as dependencies
    """
    
    GET_NAMESPACE_TOPOLOGY = """
        MATCH (s:Service)
        WHERE s.namespace = $namespace
        OPTIONAL MATCH (s)-[d:DEPENDS_ON]->(dep:Service)
        RETURN s as service, collect({target: dep, rel: d}) as dependencies
    """
    
    GET_SERVICE_SUBGRAPH = """
        // Get the service and its immediate neighborhood
        MATCH (center:Service {id: $service_id})
        
        // Upstream (what it depends on)
        OPTIONAL MATCH (center)-[up:DEPENDS_ON]->(upstream:Service)
        
        // Downstream (what depends on it)
        OPTIONAL MATCH (downstream:Service)-[down:DEPENDS_ON]->(center)
        
        RETURN center,
               collect(DISTINCT {service: upstream, rel: up}) as upstream,
               collect(DISTINCT {service: downstream, rel: down}) as downstream
    """
    
    FIND_PATHS = """
        MATCH path = shortestPath(
            (source:Service {id: $source_id})-[:DEPENDS_ON*1..10]->(target:Service {id: $target_id})
        )
        RETURN path
    """
    
    FIND_ALL_PATHS = """
        MATCH path = (source:Service {id: $source_id})-[:DEPENDS_ON*1..]->(target:Service {id: $target_id})
        WHERE length(path) <= $max_depth
        RETURN path
        ORDER BY length(path)
        LIMIT $limit
    """
    
    # =========================================================================
    # Infrastructure Queries
    # =========================================================================
    
    CREATE_POD = """
        MERGE (p:Pod {id: $id})
        SET p += $properties
        SET p.updated_at = datetime()
        WITH p
        MATCH (s:Service {id: $service_id})
        MERGE (p)-[:BELONGS_TO]->(s)
        WITH p
        MATCH (n:Node {id: $node_id})
        MERGE (p)-[:RUNS_ON]->(n)
        RETURN p
    """
    
    GET_SERVICE_PODS = """
        MATCH (p:Pod)-[:BELONGS_TO]->(s:Service {id: $service_id})
        RETURN p
        ORDER BY p.name
    """
    
    GET_NODE_PODS = """
        MATCH (p:Pod)-[:RUNS_ON]->(n:Node {id: $node_id})
        RETURN p
        ORDER BY p.name
    """
    
    CREATE_NODE = """
        MERGE (n:Node {id: $id})
        SET n += $properties
        SET n.updated_at = datetime()
        RETURN n
    """
    
    GET_NODES = """
        MATCH (n:Node)
        WHERE n.cluster = $cluster OR $cluster IS NULL
        RETURN n
        ORDER BY n.name
    """
    
    # =========================================================================
    # Database / Cache / Queue Queries
    # =========================================================================
    
    CREATE_DATABASE = """
        MERGE (db:Database {id: $id})
        SET db += $properties
        SET db.updated_at = datetime()
        RETURN db
    """
    
    LINK_SERVICE_TO_DATABASE = """
        MATCH (s:Service {id: $service_id})
        MATCH (db:Database {id: $database_id})
        MERGE (s)-[r:USES_DATABASE]->(db)
        SET r.connection_pool_size = $connection_pool_size
        SET r.read_only = $read_only
        RETURN s, r, db
    """
    
    CREATE_CACHE = """
        MERGE (c:Cache {id: $id})
        SET c += $properties
        SET c.updated_at = datetime()
        RETURN c
    """
    
    LINK_SERVICE_TO_CACHE = """
        MATCH (s:Service {id: $service_id})
        MATCH (c:Cache {id: $cache_id})
        MERGE (s)-[r:USES_CACHE]->(c)
        RETURN s, r, c
    """
    
    CREATE_QUEUE = """
        MERGE (q:MessageQueue {id: $id})
        SET q += $properties
        SET q.updated_at = datetime()
        RETURN q
    """
    
    LINK_SERVICE_TO_QUEUE = """
        MATCH (s:Service {id: $service_id})
        MATCH (q:MessageQueue {id: $queue_id})
        MERGE (s)-[r:$relationship_type]->(q)
        SET r.topics = $topics
        RETURN s, r, q
    """
    
    # =========================================================================
    # Analytics Queries
    # =========================================================================
    
    GET_MOST_DEPENDED_ON = """
        MATCH (s:Service)<-[d:DEPENDS_ON]-()
        WITH s, count(d) as dependent_count
        RETURN s, dependent_count
        ORDER BY dependent_count DESC
        LIMIT $limit
    """
    
    GET_MOST_DEPENDENCIES = """
        MATCH (s:Service)-[d:DEPENDS_ON]->()
        WITH s, count(d) as dependency_count
        RETURN s, dependency_count
        ORDER BY dependency_count DESC
        LIMIT $limit
    """
    
    GET_ORPHAN_SERVICES = """
        // Services with no dependencies and no dependents
        MATCH (s:Service)
        WHERE NOT (s)-[:DEPENDS_ON]->() AND NOT ()-[:DEPENDS_ON]->(s)
        RETURN s
        ORDER BY s.name
    """
    
    GET_CIRCULAR_DEPENDENCIES = """
        MATCH path = (s:Service)-[:DEPENDS_ON*2..10]->(s)
        RETURN path, length(path) as cycle_length
        ORDER BY cycle_length
        LIMIT $limit
    """
    
    GET_TIER_SUMMARY = """
        MATCH (s:Service)
        WITH s.tier as tier, count(s) as count
        RETURN tier, count
        ORDER BY tier
    """
    
    GET_NAMESPACE_SUMMARY = """
        MATCH (s:Service)
        WITH s.namespace as namespace, count(s) as service_count
        OPTIONAL MATCH (s:Service)-[d:DEPENDS_ON]->()
        WHERE s.namespace = namespace
        WITH namespace, service_count, count(d) as dependency_count
        RETURN namespace, service_count, dependency_count
        ORDER BY service_count DESC
    """
    
    # =========================================================================
    # Health & Alerts Queries
    # =========================================================================
    
    GET_UNHEALTHY_SERVICES = """
        MATCH (s:Service)
        WHERE s.status IN ['degraded', 'unhealthy']
        OPTIONAL MATCH (affected:Service)-[:DEPENDS_ON*1..3]->(s)
        RETURN s, collect(DISTINCT affected) as potentially_affected
        ORDER BY 
            CASE s.status 
                WHEN 'unhealthy' THEN 0 
                WHEN 'degraded' THEN 1 
            END
    """
    
    CREATE_ALERT = """
        MERGE (a:Alert {id: $id})
        SET a += $properties
        WITH a
        MATCH (s:Service {id: $service_id})
        MERGE (a)-[:AFFECTS]->(s)
        RETURN a
    """
    
    GET_ACTIVE_ALERTS = """
        MATCH (a:Alert)-[:AFFECTS]->(s:Service)
        WHERE a.status = 'firing'
        RETURN a, s
        ORDER BY 
            CASE a.severity 
                WHEN 'critical' THEN 0 
                WHEN 'warning' THEN 1 
                ELSE 2 
            END,
            a.started_at DESC
    """
    
    # =========================================================================
    # Schema Management
    # =========================================================================
    
    CREATE_CONSTRAINTS = """
        CREATE CONSTRAINT service_id IF NOT EXISTS FOR (s:Service) REQUIRE s.id IS UNIQUE;
        CREATE CONSTRAINT service_name IF NOT EXISTS FOR (s:Service) REQUIRE s.name IS UNIQUE;
        CREATE CONSTRAINT pod_id IF NOT EXISTS FOR (p:Pod) REQUIRE p.id IS UNIQUE;
        CREATE CONSTRAINT node_id IF NOT EXISTS FOR (n:Node) REQUIRE n.id IS UNIQUE;
        CREATE CONSTRAINT database_id IF NOT EXISTS FOR (d:Database) REQUIRE d.id IS UNIQUE;
        CREATE CONSTRAINT cache_id IF NOT EXISTS FOR (c:Cache) REQUIRE c.id IS UNIQUE;
        CREATE CONSTRAINT queue_id IF NOT EXISTS FOR (q:MessageQueue) REQUIRE q.id IS UNIQUE;
        CREATE CONSTRAINT namespace_id IF NOT EXISTS FOR (ns:Namespace) REQUIRE ns.id IS UNIQUE;
        CREATE CONSTRAINT alert_id IF NOT EXISTS FOR (a:Alert) REQUIRE a.id IS UNIQUE;
    """
    
    CREATE_INDEXES = """
        CREATE INDEX service_namespace IF NOT EXISTS FOR (s:Service) ON (s.namespace);
        CREATE INDEX service_tier IF NOT EXISTS FOR (s:Service) ON (s.tier);
        CREATE INDEX service_status IF NOT EXISTS FOR (s:Service) ON (s.status);
        CREATE INDEX service_team IF NOT EXISTS FOR (s:Service) ON (s.team);
        CREATE INDEX pod_namespace IF NOT EXISTS FOR (p:Pod) ON (p.namespace);
        CREATE INDEX pod_status IF NOT EXISTS FOR (p:Pod) ON (p.status);
        CREATE INDEX node_cluster IF NOT EXISTS FOR (n:Node) ON (n.cluster);
        CREATE INDEX alert_status IF NOT EXISTS FOR (a:Alert) ON (a.status);
        CREATE INDEX alert_severity IF NOT EXISTS FOR (a:Alert) ON (a.severity);
    """
    
    @classmethod
    def get_query(cls, name: str) -> str:
        """Get a query by name."""
        query = getattr(cls, name.upper(), None)
        if query is None:
            raise ValueError(f"Unknown query: {name}")
        return query
    
    @classmethod
    def format_query(cls, name: str, **params: Any) -> tuple[str, dict]:
        """Get a query with formatted parameters."""
        query = cls.get_query(name)
        return query, params
