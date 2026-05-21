"""
AutoSRE Knowledge Graph Service.

Neo4j-based service topology component for understanding service dependencies,
calculating blast radius, and enriching incident investigations with context.

Example usage:
    ```python
    from kg import KnowledgeGraphService, KnowledgeGraphTools

    # High-level service usage
    async with KnowledgeGraphService() as kg:
        service = await kg.get_service("payments-service")
        blast_radius = await kg.get_blast_radius("payments-service")

    # Agent integration
    tools = KnowledgeGraphTools()
    context = await tools.get_alert_context(alert_data)
    ```
"""

from .models import (
    # Enums
    DependencyType,
    Protocol,
    ServiceTier,
    Criticality,
    # Core models
    Service,
    Team,
    Dependency,
    ServiceHealth,
    BlastRadius,
    TopologyUpdate,
    ServiceSearchResult,
    AlertContext,
)

from .client import (
    Neo4jClient,
    Neo4jConfig,
    RetryConfig,
    get_client,
    close_client,
)

from .service import (
    KnowledgeGraphService,
    get_service,
)

from .integration import (
    KnowledgeGraphTools,
    get_kg_tools_schema,
    create_kg_tool_executor,
    enrich_alert_with_kg_context,
    kg_context_node,
)

__all__ = [
    # Enums
    "DependencyType",
    "Protocol",
    "ServiceTier",
    "Criticality",
    # Models
    "Service",
    "Team",
    "Dependency",
    "ServiceHealth",
    "BlastRadius",
    "TopologyUpdate",
    "ServiceSearchResult",
    "AlertContext",
    # Client
    "Neo4jClient",
    "Neo4jConfig",
    "RetryConfig",
    "get_client",
    "close_client",
    # Service
    "KnowledgeGraphService",
    "get_service",
    # Integration
    "KnowledgeGraphTools",
    "get_kg_tools_schema",
    "create_kg_tool_executor",
    "enrich_alert_with_kg_context",
    "kg_context_node",
]

__version__ = "1.0.0"
