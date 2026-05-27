"""
Agent integration helpers for the Knowledge Graph service.

Provides utilities for integrating with LangGraph agents and SRE workflows,
including tool definitions and context enrichment functions.
"""

import logging
from typing import Any

from .service import KnowledgeGraphService, get_service

logger = logging.getLogger(__name__)


class KnowledgeGraphTools:
    """
    Tool wrapper for agent integration.

    Provides methods that can be used as LangGraph tools for querying
    the knowledge graph during incident investigation.
    """

    def __init__(self, service: KnowledgeGraphService | None = None):
        self._service = service
        self._available = True

    async def _get_service(self) -> KnowledgeGraphService | None:
        """Get the KG service, handling unavailability gracefully."""
        if self._service is not None:
            return self._service

        try:
            self._service = await get_service()
            return self._service
        except Exception as e:
            logger.warning(f"Knowledge graph unavailable: {e}")
            self._available = False
            return None

    @property
    def is_available(self) -> bool:
        """Check if the knowledge graph is available."""
        return self._available

    async def get_service_info(self, service_name: str) -> dict[str, Any]:
        """
        Get information about a service including dependencies and blast radius.

        This is a primary tool for agents investigating incidents.

        Args:
            service_name: Name of the service to query

        Returns:
            Dictionary containing service info, dependencies, and blast radius
        """
        kg = await self._get_service()
        if not kg:
            return {"available": False, "error": "Knowledge graph unavailable"}

        try:
            service = await kg.get_service(service_name)
            if not service:
                return {
                    "available": True,
                    "found": False,
                    "service_name": service_name,
                    "message": f"Service '{service_name}' not found in topology",
                }

            blast_radius = await kg.get_blast_radius(service_name)

            return {
                "available": True,
                "found": True,
                "service_name": service.name,
                "team": service.team,
                "tier": service.tier.value if service.tier else None,
                "namespace": service.namespace,
                "cluster": service.cluster,
                "language": service.language,
                "port": service.port,
                "replicas": service.replicas,
                "upstream_dependencies": [
                    {
                        "target": d.target,
                        "type": d.type.value,
                        "protocol": d.protocol.value,
                        "criticality": d.criticality.value,
                    }
                    for d in service.upstream_dependencies
                ],
                "downstream_dependents": [
                    {"target": d.target} for d in service.downstream_dependents
                ],
                "blast_radius": {
                    "direct_dependents": blast_radius.direct_dependents,
                    "indirect_dependents": blast_radius.indirect_dependents,
                    "total_affected": blast_radius.total_affected,
                    "critical_path": blast_radius.critical_path,
                },
            }

        except Exception as e:
            logger.error(f"Error getting service info: {e}")
            return {"available": True, "error": str(e)}

    async def get_blast_radius(self, service_name: str) -> dict[str, Any]:
        """
        Calculate the blast radius for a service.

        Useful for understanding the impact of an outage.

        Args:
            service_name: Name of the service

        Returns:
            Blast radius analysis
        """
        kg = await self._get_service()
        if not kg:
            return {"available": False, "error": "Knowledge graph unavailable"}

        try:
            blast_radius = await kg.get_blast_radius(service_name)
            return {
                "available": True,
                "service": service_name,
                "direct_dependents": blast_radius.direct_dependents,
                "indirect_dependents": blast_radius.indirect_dependents,
                "total_affected": blast_radius.total_affected,
                "critical_path": blast_radius.critical_path,
            }
        except Exception as e:
            logger.error(f"Error calculating blast radius: {e}")
            return {"available": True, "error": str(e)}

    async def get_dependencies(
        self, service_name: str, direction: str = "both"
    ) -> dict[str, Any]:
        """
        Get dependencies for a service.

        Args:
            service_name: Name of the service
            direction: "upstream" (what it depends on), "downstream" (what depends on it),
                      or "both"

        Returns:
            Dictionary containing dependency information
        """
        kg = await self._get_service()
        if not kg:
            return {"available": False, "error": "Knowledge graph unavailable"}

        try:
            result: dict[str, Any] = {
                "available": True,
                "service": service_name,
            }

            if direction in ("upstream", "both"):
                upstream = await kg.get_upstream_dependencies(service_name)
                result["upstream"] = [
                    {
                        "target": d.target,
                        "type": d.type.value,
                        "protocol": d.protocol.value,
                        "criticality": d.criticality.value,
                    }
                    for d in upstream
                ]

            if direction in ("downstream", "both"):
                downstream = await kg.get_downstream_dependents(service_name)
                result["downstream"] = [
                    {
                        "target": d.target,
                        "type": d.type.value,
                    }
                    for d in downstream
                ]

            return result

        except Exception as e:
            logger.error(f"Error getting dependencies: {e}")
            return {"available": True, "error": str(e)}

    async def search_services(
        self, query: str, limit: int = 10
    ) -> dict[str, Any]:
        """
        Search for services in the topology.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching services
        """
        kg = await self._get_service()
        if not kg:
            return {"available": False, "error": "Knowledge graph unavailable"}

        try:
            results = await kg.search_services(query, limit)
            return {
                "available": True,
                "query": query,
                "results": [
                    {
                        "name": r.name,
                        "team": r.team,
                        "tier": r.tier.value if r.tier else None,
                        "namespace": r.namespace,
                        "relevance_score": r.relevance_score,
                    }
                    for r in results
                ],
            }
        except Exception as e:
            logger.error(f"Error searching services: {e}")
            return {"available": True, "error": str(e)}

    async def get_alert_context(self, alert_data: dict[str, Any]) -> dict[str, Any]:
        """
        Get full context for an alert from the knowledge graph.

        This is the primary method for enriching alerts with topology context.

        Args:
            alert_data: Alert information

        Returns:
            Rich context including service info and blast radius
        """
        kg = await self._get_service()
        if not kg:
            return {"available": False, "error": "Knowledge graph unavailable"}

        try:
            context = await kg.get_alert_context(alert_data)

            result: dict[str, Any] = {
                "available": True,
                "service_name": context.service_name,
            }

            if context.service_info:
                result["service_info"] = {
                    "name": context.service_info.name,
                    "team": context.service_info.team,
                    "tier": context.service_info.tier.value if context.service_info.tier else None,
                    "namespace": context.service_info.namespace,
                    "language": context.service_info.language,
                }

            if context.blast_radius:
                result["blast_radius"] = {
                    "direct_dependents": context.blast_radius.direct_dependents,
                    "indirect_dependents": context.blast_radius.indirect_dependents,
                    "total_affected": context.blast_radius.total_affected,
                    "critical_path": context.blast_radius.critical_path,
                }

            result["connected_components"] = context.connected_components

            return result

        except Exception as e:
            logger.error(f"Error getting alert context: {e}")
            return {"available": True, "error": str(e)}


# =============================================================================
# LangGraph Tool Definitions
# =============================================================================


def get_kg_tools_schema() -> list[dict[str, Any]]:
    """
    Get JSON schema for KG tools compatible with LLM function calling.

    Returns:
        List of tool definitions in OpenAI function calling format
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "kg_get_service_info",
                "description": "Get information about a service from the knowledge graph, including its dependencies, team ownership, and blast radius. Use this to understand service topology during incident investigation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "service_name": {
                            "type": "string",
                            "description": "Name of the service to query (e.g., 'payments-service', 'otel-demo-checkoutservice')",
                        },
                    },
                    "required": ["service_name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "kg_get_blast_radius",
                "description": "Calculate which services would be affected if a given service fails. Returns direct and indirect dependents.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "service_name": {
                            "type": "string",
                            "description": "Name of the service to analyze",
                        },
                    },
                    "required": ["service_name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "kg_get_dependencies",
                "description": "Get upstream and/or downstream dependencies for a service. Upstream = services this depends on; Downstream = services depending on this.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "service_name": {
                            "type": "string",
                            "description": "Name of the service",
                        },
                        "direction": {
                            "type": "string",
                            "enum": ["upstream", "downstream", "both"],
                            "description": "Which dependencies to return",
                            "default": "both",
                        },
                    },
                    "required": ["service_name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "kg_search_services",
                "description": "Search for services in the topology by name, team, or labels.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query string",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results to return",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
            },
        },
    ]


async def create_kg_tool_executor() -> dict[str, Any]:
    """
    Create an executor for KG tools.

    Returns:
        Dictionary mapping tool names to async functions
    """
    tools = KnowledgeGraphTools()

    return {
        "kg_get_service_info": tools.get_service_info,
        "kg_get_blast_radius": tools.get_blast_radius,
        "kg_get_dependencies": tools.get_dependencies,
        "kg_search_services": tools.search_services,
    }


# =============================================================================
# Context Enrichment for LangGraph Nodes
# =============================================================================


async def enrich_alert_with_kg_context(
    alert_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Enrich an alert with knowledge graph context.

    This is intended to be called from a LangGraph node to add
    topology information to the investigation state.

    Args:
        alert_data: Raw alert data

    Returns:
        Dictionary with KG context to merge into graph state
    """
    tools = KnowledgeGraphTools()

    try:
        context = await tools.get_alert_context(alert_data)
        return {"kg_context": context}
    except Exception as e:
        logger.warning(f"Failed to enrich alert with KG context: {e}")
        return {"kg_context": {"available": False, "error": str(e)}}


async def kg_context_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    LangGraph node for enriching investigation state with KG context.

    This is a drop-in replacement for the kg_context node in the
    OpenSRE reference implementation.

    Args:
        state: Current graph state (must contain 'alert' key)

    Returns:
        State update with kg_context
    """
    alert = state.get("alert", {})

    if not alert:
        logger.warning("[KG] No alert in state, skipping context enrichment")
        return {"kg_context": {"available": False, "error": "No alert data"}}

    try:
        tools = KnowledgeGraphTools()

        if not tools.is_available:
            logger.warning("[KG] Knowledge graph not available")
            return {"kg_context": {"available": False}}

        context = await tools.get_alert_context(alert)
        logger.info(
            f"[KG] Retrieved context for service: "
            f"{context.get('service_name', 'unknown')}"
        )

        return {"kg_context": context}

    except Exception as e:
        logger.warning(f"[KG] Failed to query knowledge graph: {e}")
        return {"kg_context": {"available": False, "error": str(e)}}
