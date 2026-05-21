"""
AutoSRE Knowledge Graph Service

Neo4j-based knowledge graph for service topology, dependencies, and infrastructure.
"""

from .client import Neo4jClient, get_client
from .models import (
    Service,
    Dependency,
    Endpoint,
    Pod,
    Node,
    Namespace,
    Database,
    Cache,
    MessageQueue,
    LoadBalancer,
    DependencyType,
    ServiceStatus,
    HealthStatus,
)
from .topology import TopologyService
from .ingestion import IngestionService
from .queries import CypherQueries
from .semantic import SemanticLayer

__all__ = [
    # Client
    "Neo4jClient",
    "get_client",
    # Models
    "Service",
    "Dependency",
    "Endpoint",
    "Pod",
    "Node",
    "Namespace",
    "Database",
    "Cache",
    "MessageQueue",
    "LoadBalancer",
    "DependencyType",
    "ServiceStatus",
    "HealthStatus",
    # Services
    "TopologyService",
    "IngestionService",
    "CypherQueries",
    "SemanticLayer",
]

__version__ = "0.1.0"
