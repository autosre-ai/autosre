"""
Knowledge Graph Context Node

Fetches service topology and dependency information from Neo4j
knowledge graph to provide context for the investigation.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def kg_context(state: dict) -> dict:
    """Fetch service topology from knowledge graph.
    
    Queries Neo4j for service information, dependencies, and blast radius
    to provide context for the investigation.
    
    Args:
        state: Current graph state with 'alert' field
        
    Returns:
        State update with 'kg_context' containing service topology
    """
    alert = state.get("alert", {})
    service_name = alert.get("service", "")
    
    if not service_name:
        logger.info("[KG] No service name in alert, skipping KG lookup")
        return {
            "kg_context": {
                "available": False,
                "reason": "No service name provided",
            }
        }
    
    try:
        # Try to get service info from Neo4j
        kg_data = _get_service_topology(service_name)
        
        if kg_data.get("available"):
            logger.info(
                f"[KG] Retrieved topology for {service_name}: "
                f"{len(kg_data.get('upstream_dependents', []))} upstream, "
                f"{len(kg_data.get('downstream_dependencies', []))} downstream"
            )
        else:
            logger.info(f"[KG] No topology data for {service_name}")
        
        return {"kg_context": kg_data}
        
    except Exception as e:
        logger.warning(f"[KG] Lookup failed for {service_name}: {e}")
        return {
            "kg_context": {
                "available": False,
                "error": str(e),
                "service_name": service_name,
            }
        }


def _get_service_topology(service_name: str) -> dict[str, Any]:
    """Query Neo4j for service topology information.
    
    Returns service metadata, upstream dependents (services that call this service),
    downstream dependencies (services this service calls), and blast radius info.
    """
    neo4j_uri = os.getenv("NEO4J_URI", "")
    
    if not neo4j_uri:
        return {
            "available": False,
            "service_name": service_name,
            "reason": "Neo4j not configured",
        }
    
    try:
        from neo4j import GraphDatabase
        
        neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "")
        
        driver = GraphDatabase.driver(
            neo4j_uri,
            auth=(neo4j_user, neo4j_password) if neo4j_password else None,
        )
        
        with driver.session() as session:
            # Get service info
            service_info = _query_service_info(session, service_name)
            if not service_info:
                return {
                    "available": False,
                    "service_name": service_name,
                    "reason": f"Service '{service_name}' not found in knowledge graph",
                }
            
            # Get dependencies
            upstream = _query_upstream_dependents(session, service_name)
            downstream = _query_downstream_dependencies(session, service_name)
            
            # Calculate blast radius
            blast_radius = _calculate_blast_radius(upstream, downstream)
            
            return {
                "available": True,
                "service_name": service_name,
                "resolved_name": service_info.get("name", service_name),
                "service_info": service_info,
                "deployment": service_info.get("deployment", {}),
                "upstream_dependents": upstream,
                "downstream_dependencies": downstream,
                "blast_radius": blast_radius,
            }
            
    except ImportError:
        logger.warning("[KG] neo4j package not installed")
        return {
            "available": False,
            "service_name": service_name,
            "reason": "neo4j package not installed",
        }
    except Exception as e:
        logger.warning(f"[KG] Neo4j query failed: {e}")
        return {
            "available": False,
            "service_name": service_name,
            "error": str(e),
        }


def _query_service_info(session, service_name: str) -> dict[str, Any] | None:
    """Query basic service information from Neo4j."""
    query = """
    MATCH (s:Service)
    WHERE s.name = $name OR s.name CONTAINS $name
    OPTIONAL MATCH (s)-[:DEPLOYED_AS]->(d:Deployment)
    RETURN s, d
    LIMIT 1
    """
    result = session.run(query, name=service_name)
    record = result.single()
    
    if not record:
        return None
    
    service_node = dict(record["s"]) if record["s"] else {}
    deployment_node = dict(record["d"]) if record["d"] else {}
    
    return {
        "name": service_node.get("name", service_name),
        "description": service_node.get("description", ""),
        "team": service_node.get("team", ""),
        "language": service_node.get("language", ""),
        "deployment": {
            "namespace": deployment_node.get("namespace", ""),
            "replicas": deployment_node.get("replicas", 0),
            "image": deployment_node.get("image", ""),
            "port": deployment_node.get("port", ""),
        },
    }


def _query_upstream_dependents(session, service_name: str) -> list[dict[str, str]]:
    """Query services that call this service (upstream dependents)."""
    query = """
    MATCH (upstream:Service)-[r:CALLS|DEPENDS_ON]->(s:Service)
    WHERE s.name = $name OR s.name CONTAINS $name
    RETURN upstream.name AS service, type(r) AS via
    LIMIT 20
    """
    result = session.run(query, name=service_name)
    return [{"service": r["service"], "via": r["via"]} for r in result]


def _query_downstream_dependencies(session, service_name: str) -> list[dict[str, str]]:
    """Query services that this service calls (downstream dependencies)."""
    query = """
    MATCH (s:Service)-[r:CALLS|DEPENDS_ON]->(downstream:Service)
    WHERE s.name = $name OR s.name CONTAINS $name
    RETURN downstream.name AS service, type(r) AS via
    LIMIT 20
    """
    result = session.run(query, name=service_name)
    return [{"service": r["service"], "via": r["via"]} for r in result]


def _calculate_blast_radius(
    upstream: list[dict],
    downstream: list[dict],
) -> dict[str, Any]:
    """Calculate the blast radius for a service failure."""
    return {
        "upstream_count": len(upstream),
        "downstream_count": len(downstream),
        "total_affected": len(upstream) + len(downstream),
        "severity": _estimate_severity(len(upstream)),
    }


def _estimate_severity(upstream_count: int) -> str:
    """Estimate severity based on how many services depend on this one."""
    if upstream_count >= 10:
        return "critical"
    elif upstream_count >= 5:
        return "high"
    elif upstream_count >= 2:
        return "medium"
    return "low"


def format_kg_for_agent(agent_id: str, kg_data: dict) -> str:
    """Format KG context for a specific agent type.
    
    Returns compact markdown tailored to the agent's investigation domain.
    This is used by the subagent executor to include relevant topology info.
    
    Args:
        agent_id: The agent type (kubernetes, metrics, log_analysis, etc.)
        kg_data: The kg_context dict from state
        
    Returns:
        Markdown-formatted string with relevant topology info
    """
    if not kg_data.get("available"):
        return "No service topology available."
    
    service_info = kg_data.get("service_info", {})
    if not service_info:
        return "No service topology available."
    
    deploy = kg_data.get("deployment", {})
    upstream = kg_data.get("upstream_dependents", [])
    downstream = kg_data.get("downstream_dependencies", [])
    blast = kg_data.get("blast_radius", {})
    
    svc_name = kg_data.get("resolved_name", kg_data.get("service_name", "unknown"))
    lines = [f"**Service**: {svc_name}"]
    
    if deploy:
        lines.append(f"**Namespace**: {deploy.get('namespace', '?')}, **Replicas**: {deploy.get('replicas', '?')}")
    
    agent_lower = agent_id.lower()
    
    if agent_lower in ("kubernetes", "k8s", "planner"):
        # Full deployment details for K8s agent and planner
        if deploy:
            lines.append(f"**Image**: {deploy.get('image', '?')}")
            lines.append(f"**Language**: {service_info.get('language', '?')}, **Port**: {deploy.get('port', '?')}")
        
        if upstream:
            lines.append("\n**Upstream (services that CALL this service):**")
            for u in upstream[:8]:
                lines.append(f"  - {u['service']} (via {u.get('via', '?')})")
        
        if downstream:
            lines.append("\n**Downstream (services this service CALLS):**")
            for d in downstream[:8]:
                lines.append(f"  - {d['service']} (via {d.get('via', '?')})")
        
        if blast.get("upstream_count", 0) > 0:
            lines.append(f"\n**Blast radius**: {blast['upstream_count']} upstream services affected if this fails")
        
        lines.append("\n_Use this topology to prioritize dependency checks._")
    
    elif agent_lower in ("metrics", "observability"):
        # Metrics agent: service names for PromQL correlation
        all_related = [u["service"] for u in upstream] + [d["service"] for d in downstream]
        if all_related:
            lines.append(f"\n**Related services for metric correlation**: {', '.join(all_related[:10])}")
        lines.append("\n_Query metrics for these related services to check for correlated error/latency spikes._")
    
    elif agent_lower in ("log_analysis", "logs"):
        # Log agent: service names for log grep patterns
        all_names = [u["service"] for u in upstream] + [d["service"] for d in downstream]
        if all_names:
            lines.append(f"\n**Related service names (search in logs)**: {', '.join(all_names[:10])}")
        lines.append("\n_These service names may appear in error messages or connection logs._")
    
    else:
        # Default: compact summary
        if upstream:
            lines.append(f"**Upstream**: {', '.join(u['service'] for u in upstream[:5])}")
        if downstream:
            lines.append(f"**Downstream**: {', '.join(d['service'] for d in downstream[:5])}")
    
    return "\n".join(lines)
