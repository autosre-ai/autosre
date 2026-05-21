"""
Cypher query templates for Neo4j knowledge graph operations.

Organized by operation type with parameterized queries for safety.
"""

# =============================================================================
# SERVICE QUERIES
# =============================================================================

GET_SERVICE_BY_NAME = """
MATCH (s:Service {name: $name})
OPTIONAL MATCH (s)-[:OWNED_BY]->(t:Team)
OPTIONAL MATCH (s)-[d:DEPENDS_ON]->(dep:Service)
OPTIONAL MATCH (upstream:Service)-[u:DEPENDS_ON]->(s)
RETURN s, t,
       collect(DISTINCT {
           target: dep.name,
           type: d.type,
           protocol: d.protocol,
           criticality: d.criticality,
           port: d.port,
           via: d.via
       }) AS dependencies,
       collect(DISTINCT {
           target: upstream.name,
           type: u.type,
           protocol: u.protocol,
           criticality: u.criticality
       }) AS dependents
"""

# Fallback: also check KubernetesDeployment nodes (OpenSRE compatibility)
GET_SERVICE_BY_NAME_FALLBACK = """
MATCH (d:KubernetesDeployment)
WHERE d.name = $name OR d.name CONTAINS $name
OPTIONAL MATCH (ns:KubernetesNamespace)-[:HAS_DEPLOYMENT]->(d)
OPTIONAL MATCH (ns)-[:HAS_SERVICE]->(svc:KubernetesService)-[:ROUTES_TO]->(d)
OPTIONAL MATCH (d)-[dep:DEPENDS_ON]->(downstream)
OPTIONAL MATCH (upstream)-[u:DEPENDS_ON]->(d)
RETURN d AS service, ns, svc,
       collect(DISTINCT {
           target: downstream.name,
           via: dep.via,
           port: dep.port
       }) AS dependencies,
       collect(DISTINCT {
           target: upstream.name,
           via: u.via,
           port: u.port
       }) AS dependents
LIMIT 1
"""

SEARCH_SERVICES = """
MATCH (s:Service)
WHERE toLower(s.name) CONTAINS toLower($query)
   OR toLower(s.team) CONTAINS toLower($query)
   OR any(label IN keys(s.labels) WHERE toLower(s.labels[label]) CONTAINS toLower($query))
OPTIONAL MATCH (s)-[:OWNED_BY]->(t:Team)
RETURN s.name AS name, s.team AS team, s.tier AS tier, s.namespace AS namespace,
       CASE 
           WHEN toLower(s.name) = toLower($query) THEN 1.0
           WHEN toLower(s.name) STARTS WITH toLower($query) THEN 0.9
           ELSE 0.7
       END AS relevance_score
ORDER BY relevance_score DESC, s.name
LIMIT $limit
"""

# Fallback search for KubernetesDeployment nodes
SEARCH_SERVICES_FALLBACK = """
MATCH (d:KubernetesDeployment)
WHERE toLower(d.name) CONTAINS toLower($query)
   OR toLower(d.language) CONTAINS toLower($query)
RETURN d.name AS name, null AS team, null AS tier, null AS namespace,
       CASE 
           WHEN toLower(d.name) = toLower($query) THEN 1.0
           WHEN toLower(d.name) STARTS WITH toLower($query) THEN 0.9
           ELSE 0.7
       END AS relevance_score
ORDER BY relevance_score DESC, d.name
LIMIT $limit
"""

LIST_ALL_SERVICES = """
MATCH (s:Service)
OPTIONAL MATCH (s)-[:OWNED_BY]->(t:Team)
RETURN s.name AS name, s.team AS team, s.tier AS tier, 
       s.namespace AS namespace, s.cluster AS cluster
ORDER BY s.name
"""

# =============================================================================
# DEPENDENCY QUERIES
# =============================================================================

GET_UPSTREAM_DEPENDENCIES = """
MATCH (s:Service {name: $name})-[d:DEPENDS_ON]->(dep:Service)
RETURN dep.name AS name, dep.team AS team, dep.tier AS tier,
       d.type AS dependency_type, d.protocol AS protocol,
       d.criticality AS criticality, d.port AS port, d.via AS via
"""

GET_UPSTREAM_DEPENDENCIES_FALLBACK = """
MATCH (d:KubernetesDeployment {name: $name})-[r:DEPENDS_ON]->(downstream)
RETURN downstream.name AS name, null AS team, null AS tier,
       'sync' AS dependency_type, 'gRPC' AS protocol,
       'hard' AS criticality, r.port AS port, r.via AS via
"""

GET_DOWNSTREAM_DEPENDENTS = """
MATCH (upstream:Service)-[d:DEPENDS_ON]->(s:Service {name: $name})
RETURN upstream.name AS name, upstream.team AS team, upstream.tier AS tier,
       d.type AS dependency_type, d.protocol AS protocol,
       d.criticality AS criticality
"""

GET_DOWNSTREAM_DEPENDENTS_FALLBACK = """
MATCH (upstream:KubernetesDeployment)-[r:DEPENDS_ON]->(d:KubernetesDeployment {name: $name})
RETURN upstream.name AS name, null AS team, null AS tier,
       'sync' AS dependency_type, 'gRPC' AS protocol,
       'hard' AS criticality
"""

# =============================================================================
# BLAST RADIUS QUERIES
# =============================================================================

GET_BLAST_RADIUS = """
MATCH (s:Service {name: $name})
OPTIONAL MATCH (direct:Service)-[:DEPENDS_ON]->(s)
OPTIONAL MATCH (indirect:Service)-[:DEPENDS_ON*2..]->(s)
WHERE indirect <> direct
RETURN s.name AS service,
       collect(DISTINCT direct.name) AS direct_dependents,
       collect(DISTINCT indirect.name) AS indirect_dependents
"""

GET_BLAST_RADIUS_FALLBACK = """
MATCH (d:KubernetesDeployment {name: $name})
OPTIONAL MATCH (direct:KubernetesDeployment)-[:DEPENDS_ON]->(d)
OPTIONAL MATCH (indirect:KubernetesDeployment)-[:DEPENDS_ON*2..]->(d)
WHERE indirect <> direct
RETURN d.name AS service,
       collect(DISTINCT direct.name) AS direct_dependents,
       collect(DISTINCT indirect.name) AS indirect_dependents
"""

# More comprehensive blast radius with depth
GET_BLAST_RADIUS_WITH_DEPTH = """
MATCH (s:Service {name: $name})
CALL {
    WITH s
    MATCH path = (upstream:Service)-[:DEPENDS_ON*1..]->(s)
    RETURN upstream.name AS dependent, length(path) AS depth
}
RETURN s.name AS service,
       collect({name: dependent, depth: depth}) AS affected_services
ORDER BY depth
"""

# =============================================================================
# TOPOLOGY MANAGEMENT
# =============================================================================

UPSERT_SERVICE = """
MERGE (s:Service {name: $name})
SET s.team = $team,
    s.tier = $tier,
    s.criticality = $criticality,
    s.namespace = $namespace,
    s.cluster = $cluster,
    s.replicas = $replicas,
    s.image = $image,
    s.language = $language,
    s.port = $port,
    s.repo = $repo,
    s.labels = $labels,
    s.updated_at = datetime()
RETURN s
"""

UPSERT_TEAM = """
MERGE (t:Team {name: $name})
SET t.slack_channel = $slack_channel,
    t.oncall_schedule = $oncall_schedule,
    t.email = $email,
    t.updated_at = datetime()
RETURN t
"""

CREATE_DEPENDENCY = """
MATCH (source:Service {name: $source})
MATCH (target:Service {name: $target})
MERGE (source)-[d:DEPENDS_ON]->(target)
SET d.type = $type,
    d.protocol = $protocol,
    d.criticality = $criticality,
    d.port = $port,
    d.via = $via,
    d.updated_at = datetime()
RETURN d
"""

CREATE_OWNERSHIP = """
MATCH (s:Service {name: $service})
MATCH (t:Team {name: $team})
MERGE (s)-[:OWNED_BY]->(t)
RETURN s, t
"""

DELETE_SERVICE = """
MATCH (s:Service {name: $name})
DETACH DELETE s
RETURN count(s) AS deleted
"""

DELETE_ALL_DEPENDENCIES_FOR_SERVICE = """
MATCH (s:Service {name: $name})-[d:DEPENDS_ON]->()
DELETE d
RETURN count(d) AS deleted
"""

# =============================================================================
# CONTEXT QUERIES (for agent integration)
# =============================================================================

GET_ALERT_CONTEXT = """
MATCH (s:Service {name: $name})
OPTIONAL MATCH (s)-[:OWNED_BY]->(t:Team)
OPTIONAL MATCH (s)-[d:DEPENDS_ON]->(dep:Service)
OPTIONAL MATCH (upstream:Service)-[u:DEPENDS_ON]->(s)
WITH s, t, 
     collect(DISTINCT dep.name) AS dependencies,
     collect(DISTINCT upstream.name) AS dependents
RETURN {
    service: s.name,
    team: t.name,
    team_slack: t.slack_channel,
    tier: s.tier,
    namespace: s.namespace,
    cluster: s.cluster,
    language: s.language,
    dependencies: dependencies,
    dependents: dependents,
    blast_radius: size(dependents)
} AS context
"""

GET_COMPONENT_RELATIONSHIPS = """
MATCH (source)-[r]->(target)
WHERE source.name = $name OR target.name = $name
RETURN source.name AS source, target.name AS target,
       type(r) AS relationship_type, properties(r) AS properties
"""

# =============================================================================
# KUBERNETES-SPECIFIC QUERIES (OpenSRE compatibility)
# =============================================================================

GET_KUBERNETES_STATUS = """
MATCH (ns:KubernetesNamespace)-[:HAS_DEPLOYMENT]->(d:KubernetesDeployment)
WHERE d.name = $name OR d.name CONTAINS $name
OPTIONAL MATCH (ns)-[:HAS_SERVICE]->(s:KubernetesService)-[:ROUTES_TO]->(d)
RETURN ns.name AS namespace, d.name AS deployment,
       d.replicas AS replicas, d.image AS image, d.language AS language,
       s.name AS service, s.port AS port, s.type AS service_type
"""

GET_CLUSTER_OVERVIEW = """
MATCH (c:KubernetesCluster)-[:HAS_NAMESPACE]->(ns:KubernetesNamespace)
OPTIONAL MATCH (ns)-[:HAS_DEPLOYMENT]->(d:KubernetesDeployment)
RETURN c.name AS cluster, ns.name AS namespace,
       count(d) AS deployment_count
"""

# =============================================================================
# HEALTH & METRICS
# =============================================================================

UPDATE_SERVICE_HEALTH = """
MATCH (s:Service {name: $name})
SET s.health_status = $status,
    s.last_incident = $last_incident,
    s.incident_count = COALESCE(s.incident_count, 0) + $increment_incidents,
    s.health_updated_at = datetime()
RETURN s
"""

RECORD_INCIDENT = """
MATCH (s:Service {name: $name})
SET s.last_incident = datetime(),
    s.incident_count = COALESCE(s.incident_count, 0) + 1
RETURN s
"""

# =============================================================================
# SCHEMA & INDEXES
# =============================================================================

CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS FOR (s:Service) ON (s.name);
CREATE INDEX IF NOT EXISTS FOR (s:Service) ON (s.team);
CREATE INDEX IF NOT EXISTS FOR (s:Service) ON (s.tier);
CREATE INDEX IF NOT EXISTS FOR (t:Team) ON (t.name);
CREATE INDEX IF NOT EXISTS FOR (d:KubernetesDeployment) ON (d.name);
CREATE INDEX IF NOT EXISTS FOR (svc:KubernetesService) ON (svc.name);
CREATE INDEX IF NOT EXISTS FOR (ns:KubernetesNamespace) ON (ns.name);
"""

GET_SCHEMA = """
CALL db.schema.visualization()
"""

# =============================================================================
# UTILITY
# =============================================================================

CHECK_CONNECTION = """
RETURN 1 AS connected
"""

COUNT_NODES = """
MATCH (n)
RETURN labels(n)[0] AS label, count(n) AS count
ORDER BY count DESC
"""
