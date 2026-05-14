"""
Service Graph Builder for AutoSRE V2.

Automatically builds service dependency graphs from distributed traces.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import numpy as np
from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger
from .models import Span, Trace, SpanKind

logger = get_logger(__name__)


class DependencyType(str, Enum):
    """Type of service dependency."""
    
    HTTP = "http"
    GRPC = "grpc"
    DATABASE = "database"
    CACHE = "cache"
    MESSAGING = "messaging"
    INTERNAL = "internal"
    EXTERNAL = "external"
    UNKNOWN = "unknown"


@dataclass
class GraphConfig:
    """Configuration for service graph building."""
    
    # Edge requirements
    min_calls_for_edge: int = 1
    min_confidence_for_edge: float = 0.5
    
    # Node settings
    include_databases: bool = True
    include_caches: bool = True
    include_messaging: bool = True
    include_external: bool = True
    
    # Time-based settings
    time_window_hours: int = 24
    
    # Metrics
    track_latency: bool = True
    track_error_rate: bool = True
    track_throughput: bool = True


@dataclass
class ServiceMetrics:
    """Metrics for a service or edge."""
    
    # Call metrics
    total_calls: int = 0
    error_calls: int = 0
    
    # Latency metrics
    latency_sum_ms: float = 0.0
    latency_min_ms: float = float("inf")
    latency_max_ms: float = 0.0
    latency_samples: list[float] = field(default_factory=list)
    
    # Time range
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    
    @property
    def error_rate(self) -> float:
        """Calculate error rate."""
        if self.total_calls == 0:
            return 0.0
        return self.error_calls / self.total_calls
    
    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency."""
        if self.total_calls == 0:
            return 0.0
        return self.latency_sum_ms / self.total_calls
    
    @property
    def p50_latency_ms(self) -> float:
        """Calculate P50 latency."""
        if not self.latency_samples:
            return 0.0
        sorted_samples = sorted(self.latency_samples)
        return sorted_samples[len(sorted_samples) // 2]
    
    @property
    def p95_latency_ms(self) -> float:
        """Calculate P95 latency."""
        if not self.latency_samples:
            return 0.0
        sorted_samples = sorted(self.latency_samples)
        idx = int(len(sorted_samples) * 0.95)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]
    
    @property
    def p99_latency_ms(self) -> float:
        """Calculate P99 latency."""
        if not self.latency_samples:
            return 0.0
        sorted_samples = sorted(self.latency_samples)
        idx = int(len(sorted_samples) * 0.99)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]
    
    @property
    def throughput_per_minute(self) -> float:
        """Calculate throughput per minute."""
        if not self.first_seen or not self.last_seen:
            return 0.0
        
        duration = (self.last_seen - self.first_seen).total_seconds()
        if duration <= 0:
            return 0.0
        
        return self.total_calls / duration * 60
    
    def record_call(
        self,
        latency_ms: float,
        is_error: bool,
        timestamp: datetime,
    ) -> None:
        """Record a call."""
        self.total_calls += 1
        if is_error:
            self.error_calls += 1
        
        self.latency_sum_ms += latency_ms
        self.latency_min_ms = min(self.latency_min_ms, latency_ms)
        self.latency_max_ms = max(self.latency_max_ms, latency_ms)
        
        # Keep limited samples for percentile calculation
        if len(self.latency_samples) < 10000:
            self.latency_samples.append(latency_ms)
        
        if self.first_seen is None or timestamp < self.first_seen:
            self.first_seen = timestamp
        if self.last_seen is None or timestamp > self.last_seen:
            self.last_seen = timestamp
    
    def merge(self, other: "ServiceMetrics") -> None:
        """Merge another metrics object into this one."""
        self.total_calls += other.total_calls
        self.error_calls += other.error_calls
        self.latency_sum_ms += other.latency_sum_ms
        self.latency_min_ms = min(self.latency_min_ms, other.latency_min_ms)
        self.latency_max_ms = max(self.latency_max_ms, other.latency_max_ms)
        
        # Merge samples (with limit)
        remaining = 10000 - len(self.latency_samples)
        if remaining > 0:
            self.latency_samples.extend(other.latency_samples[:remaining])
        
        if other.first_seen:
            if self.first_seen is None or other.first_seen < self.first_seen:
                self.first_seen = other.first_seen
        if other.last_seen:
            if self.last_seen is None or other.last_seen > self.last_seen:
                self.last_seen = other.last_seen
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "error_calls": self.error_calls,
            "error_rate": self.error_rate,
            "avg_latency_ms": self.avg_latency_ms,
            "min_latency_ms": self.latency_min_ms if self.latency_min_ms != float("inf") else 0,
            "max_latency_ms": self.latency_max_ms,
            "p50_latency_ms": self.p50_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "p99_latency_ms": self.p99_latency_ms,
            "throughput_per_minute": self.throughput_per_minute,
        }


@dataclass
class ServiceNode:
    """A node in the service graph representing a service."""
    
    name: str
    node_type: str = "service"  # service, database, cache, messaging, external
    
    # Metadata
    namespace: Optional[str] = None
    cluster: Optional[str] = None
    version: Optional[str] = None
    
    # Metrics
    metrics: ServiceMetrics = field(default_factory=ServiceMetrics)
    
    # Operations
    operations: set[str] = field(default_factory=set)
    
    # Graph position (for visualization)
    x: float = 0.0
    y: float = 0.0
    
    @property
    def is_database(self) -> bool:
        return self.node_type == "database"
    
    @property
    def is_cache(self) -> bool:
        return self.node_type == "cache"
    
    @property
    def is_messaging(self) -> bool:
        return self.node_type == "messaging"
    
    @property
    def is_external(self) -> bool:
        return self.node_type == "external"
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "node_type": self.node_type,
            "namespace": self.namespace,
            "cluster": self.cluster,
            "version": self.version,
            "metrics": self.metrics.to_dict(),
            "operations": list(self.operations),
            "position": {"x": self.x, "y": self.y},
        }


@dataclass
class ServiceEdge:
    """An edge in the service graph representing a dependency."""
    
    source: str  # Source service name
    target: str  # Target service name
    dependency_type: DependencyType
    
    # Operations on this edge
    operations: set[str] = field(default_factory=set)
    
    # Metrics
    metrics: ServiceMetrics = field(default_factory=ServiceMetrics)
    
    @property
    def edge_id(self) -> str:
        return f"{self.source}->{self.target}"
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "dependency_type": self.dependency_type.value,
            "operations": list(self.operations),
            "metrics": self.metrics.to_dict(),
        }


@dataclass
class ServiceGraph:
    """A complete service dependency graph."""
    
    nodes: dict[str, ServiceNode] = field(default_factory=dict)
    edges: dict[str, ServiceEdge] = field(default_factory=dict)
    
    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    trace_count: int = 0
    span_count: int = 0
    
    @property
    def node_count(self) -> int:
        return len(self.nodes)
    
    @property
    def edge_count(self) -> int:
        return len(self.edges)
    
    @property
    def services(self) -> list[str]:
        """Get list of service names."""
        return [n.name for n in self.nodes.values() if n.node_type == "service"]
    
    def get_node(self, name: str) -> Optional[ServiceNode]:
        """Get a node by name."""
        return self.nodes.get(name)
    
    def get_edge(self, source: str, target: str) -> Optional[ServiceEdge]:
        """Get an edge by source and target."""
        edge_id = f"{source}->{target}"
        return self.edges.get(edge_id)
    
    def add_node(self, node: ServiceNode) -> None:
        """Add or update a node."""
        if node.name in self.nodes:
            existing = self.nodes[node.name]
            existing.metrics.merge(node.metrics)
            existing.operations.update(node.operations)
        else:
            self.nodes[node.name] = node
        self.updated_at = datetime.now(timezone.utc)
    
    def add_edge(self, edge: ServiceEdge) -> None:
        """Add or update an edge."""
        edge_id = edge.edge_id
        if edge_id in self.edges:
            existing = self.edges[edge_id]
            existing.metrics.merge(edge.metrics)
            existing.operations.update(edge.operations)
        else:
            self.edges[edge_id] = edge
        self.updated_at = datetime.now(timezone.utc)
    
    def get_dependencies(self, service: str) -> list[str]:
        """Get services that this service depends on."""
        deps = []
        for edge in self.edges.values():
            if edge.source == service:
                deps.append(edge.target)
        return deps
    
    def get_dependents(self, service: str) -> list[str]:
        """Get services that depend on this service."""
        deps = []
        for edge in self.edges.values():
            if edge.target == service:
                deps.append(edge.source)
        return deps
    
    def get_upstream_services(self, service: str, max_depth: int = 10) -> set[str]:
        """Get all upstream services (transitive dependencies)."""
        upstream: set[str] = set()
        to_visit = [service]
        depth = 0
        
        while to_visit and depth < max_depth:
            current = to_visit.pop(0)
            deps = self.get_dependencies(current)
            
            for dep in deps:
                if dep not in upstream:
                    upstream.add(dep)
                    to_visit.append(dep)
            
            depth += 1
        
        return upstream
    
    def get_downstream_services(self, service: str, max_depth: int = 10) -> set[str]:
        """Get all downstream services (transitive dependents)."""
        downstream: set[str] = set()
        to_visit = [service]
        depth = 0
        
        while to_visit and depth < max_depth:
            current = to_visit.pop(0)
            deps = self.get_dependents(current)
            
            for dep in deps:
                if dep not in downstream:
                    downstream.add(dep)
                    to_visit.append(dep)
            
            depth += 1
        
        return downstream
    
    def find_critical_paths(self, entry_service: str) -> list[list[str]]:
        """Find critical paths from an entry service."""
        paths: list[list[str]] = []
        
        def dfs(current: str, path: list[str]) -> None:
            deps = self.get_dependencies(current)
            
            if not deps:
                paths.append(path)
                return
            
            for dep in deps:
                if dep not in path:  # Avoid cycles
                    dfs(dep, path + [dep])
        
        dfs(entry_service, [entry_service])
        return paths
    
    def detect_cycles(self) -> list[list[str]]:
        """Detect cycles in the service graph."""
        cycles = []
        visited: set[str] = set()
        rec_stack: set[str] = set()
        
        def dfs(node: str, path: list[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            
            for dep in self.get_dependencies(node):
                if dep not in visited:
                    dfs(dep, path + [dep])
                elif dep in rec_stack:
                    # Found cycle
                    cycle_start = path.index(dep) if dep in path else 0
                    cycles.append(path[cycle_start:] + [dep])
            
            rec_stack.remove(node)
        
        for node in self.nodes:
            if node not in visited:
                dfs(node, [node])
        
        return cycles
    
    def compute_layout(self) -> None:
        """Compute layout positions for visualization."""
        if not self.nodes:
            return
        
        # Simple layered layout
        # Find entry points (no dependents)
        entry_points = [
            name for name in self.nodes
            if not self.get_dependents(name)
        ]
        
        if not entry_points:
            entry_points = list(self.nodes.keys())[:1]
        
        # Assign layers by BFS
        layers: dict[str, int] = {}
        queue = [(ep, 0) for ep in entry_points]
        
        while queue:
            node, layer = queue.pop(0)
            if node in layers:
                continue
            
            layers[node] = layer
            
            for dep in self.get_dependencies(node):
                if dep not in layers:
                    queue.append((dep, layer + 1))
        
        # Position nodes
        nodes_by_layer: dict[int, list[str]] = defaultdict(list)
        for node, layer in layers.items():
            nodes_by_layer[layer].append(node)
        
        for layer, nodes in nodes_by_layer.items():
            for i, node_name in enumerate(nodes):
                node = self.nodes[node_name]
                node.x = layer * 200.0
                node.y = i * 100.0 - (len(nodes) - 1) * 50.0
        
        # Handle unassigned nodes
        max_layer = max(layers.values()) + 1 if layers else 0
        unassigned = [n for n in self.nodes if n not in layers]
        for i, node_name in enumerate(unassigned):
            node = self.nodes[node_name]
            node.x = max_layer * 200.0
            node.y = i * 100.0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "edges": {k: v.to_dict() for k, v in self.edges.items()},
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "services": self.services,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "trace_count": self.trace_count,
            "span_count": self.span_count,
        }
    
    def to_dot(self) -> str:
        """Export to GraphViz DOT format."""
        lines = ["digraph ServiceGraph {"]
        lines.append('  rankdir=LR;')
        lines.append('  node [shape=box, style=rounded];')
        
        # Node definitions
        for node in self.nodes.values():
            label = node.name
            if node.metrics.total_calls > 0:
                label += f"\\n{node.metrics.total_calls} calls"
                if node.metrics.error_rate > 0:
                    label += f"\\n{node.metrics.error_rate*100:.1f}% errors"
            
            color = "black"
            if node.is_database:
                color = "blue"
            elif node.is_cache:
                color = "green"
            elif node.is_messaging:
                color = "orange"
            elif node.is_external:
                color = "gray"
            
            lines.append(f'  "{node.name}" [label="{label}", color={color}];')
        
        # Edge definitions
        for edge in self.edges.values():
            label = f"{edge.metrics.total_calls} calls"
            if edge.metrics.avg_latency_ms > 0:
                label += f"\\n{edge.metrics.avg_latency_ms:.0f}ms avg"
            
            style = "solid"
            if edge.dependency_type == DependencyType.MESSAGING:
                style = "dashed"
            
            lines.append(f'  "{edge.source}" -> "{edge.target}" [label="{label}", style={style}];')
        
        lines.append("}")
        return "\n".join(lines)
    
    def to_mermaid(self) -> str:
        """Export to Mermaid diagram format."""
        lines = ["graph LR"]
        
        for edge in self.edges.values():
            source = edge.source.replace("-", "_")
            target = edge.target.replace("-", "_")
            label = f"{edge.metrics.total_calls}c"
            
            lines.append(f"    {source}[{edge.source}] -->|{label}| {target}[{edge.target}]")
        
        # Add orphan nodes
        connected = set()
        for edge in self.edges.values():
            connected.add(edge.source)
            connected.add(edge.target)
        
        for node in self.nodes.values():
            if node.name not in connected:
                name = node.name.replace("-", "_")
                lines.append(f"    {name}[{node.name}]")
        
        return "\n".join(lines)


class ServiceGraphBuilder:
    """
    Builds service dependency graphs from distributed traces.
    
    Example:
        builder = ServiceGraphBuilder()
        graph = builder.build(traces)
        
        # Get dependencies for a service
        deps = graph.get_dependencies("api-gateway")
        
        # Export to DOT format
        print(graph.to_dot())
    """
    
    def __init__(self, config: Optional[GraphConfig] = None):
        self.config = config or GraphConfig()
    
    def build(
        self,
        traces: Sequence[Trace],
    ) -> ServiceGraph:
        """
        Build a service graph from traces.
        
        Extracts services, operations, and dependencies from span relationships.
        """
        graph = ServiceGraph()
        graph.trace_count = len(traces)
        
        for trace in traces:
            self._process_trace(trace, graph)
        
        # Filter edges by minimum calls
        if self.config.min_calls_for_edge > 1:
            graph.edges = {
                k: v for k, v in graph.edges.items()
                if v.metrics.total_calls >= self.config.min_calls_for_edge
            }
        
        # Compute layout
        graph.compute_layout()
        
        return graph
    
    def _process_trace(self, trace: Trace, graph: ServiceGraph) -> None:
        """Process a single trace."""
        graph.span_count += len(trace.spans)
        
        # Build span lookup
        span_map = {s.span_id: s for s in trace.spans}
        
        for span in trace.spans:
            # Create/update node for this service
            node = self._span_to_node(span)
            graph.add_node(node)
            
            # Record call metrics
            node = graph.get_node(span.service_name)
            if node:
                node.metrics.record_call(
                    span.duration_ms,
                    span.is_error,
                    span.start_time,
                )
                node.operations.add(span.name)
            
            # Create edge from parent
            if span.parent_span_id and span.parent_span_id in span_map:
                parent = span_map[span.parent_span_id]
                
                # Only create edge if different services
                if parent.service_name != span.service_name:
                    edge = self._create_edge(parent, span)
                    if edge:
                        graph.add_edge(edge)
            
            # Check for external dependencies
            if self.config.include_external:
                external_deps = self._extract_external_dependencies(span)
                for ext_node, ext_edge in external_deps:
                    graph.add_node(ext_node)
                    graph.add_edge(ext_edge)
    
    def _span_to_node(self, span: Span) -> ServiceNode:
        """Create a node from a span."""
        node_type = self._determine_node_type(span)
        
        resource = span.resource
        namespace = resource.get("k8s.namespace.name") or resource.get("service.namespace")
        cluster = resource.get("k8s.cluster.name")
        version = resource.get("service.version")
        
        return ServiceNode(
            name=span.service_name,
            node_type=node_type,
            namespace=namespace,
            cluster=cluster,
            version=version,
        )
    
    def _determine_node_type(self, span: Span) -> str:
        """Determine the type of node from span attributes."""
        # Check for database
        if span.db_system:
            return "database"
        
        # Check for cache (Redis, Memcached)
        db_system = span.attributes.get("db.system", "")
        if db_system.lower() in ("redis", "memcached", "elasticache"):
            return "cache"
        
        # Check for messaging
        if span.messaging_system:
            return "messaging"
        
        # Check for external HTTP
        if span.kind == SpanKind.CLIENT:
            peer_service = span.attributes.get("peer.service")
            if peer_service and not self._is_internal_service(peer_service):
                return "external"
        
        return "service"
    
    def _is_internal_service(self, service: str) -> bool:
        """Check if a service is internal (heuristic)."""
        # Simple heuristic: external services often have full domain names
        external_patterns = [
            ".com",
            ".io",
            ".org",
            ".net",
            "googleapis",
            "amazonaws",
            "azure",
        ]
        
        for pattern in external_patterns:
            if pattern in service.lower():
                return False
        
        return True
    
    def _create_edge(self, parent: Span, child: Span) -> Optional[ServiceEdge]:
        """Create an edge between two spans."""
        if parent.service_name == child.service_name:
            return None
        
        dep_type = self._determine_dependency_type(child)
        
        edge = ServiceEdge(
            source=parent.service_name,
            target=child.service_name,
            dependency_type=dep_type,
        )
        
        edge.operations.add(child.name)
        edge.metrics.record_call(
            child.duration_ms,
            child.is_error,
            child.start_time,
        )
        
        return edge
    
    def _determine_dependency_type(self, span: Span) -> DependencyType:
        """Determine the type of dependency from span."""
        if span.db_system:
            return DependencyType.DATABASE
        
        if span.messaging_system:
            return DependencyType.MESSAGING
        
        db_system = span.attributes.get("db.system", "")
        if db_system.lower() in ("redis", "memcached"):
            return DependencyType.CACHE
        
        if span.rpc_service or span.attributes.get("rpc.system") == "grpc":
            return DependencyType.GRPC
        
        if span.http_method or span.http_url:
            return DependencyType.HTTP
        
        if span.kind == SpanKind.INTERNAL:
            return DependencyType.INTERNAL
        
        return DependencyType.UNKNOWN
    
    def _extract_external_dependencies(
        self,
        span: Span,
    ) -> list[tuple[ServiceNode, ServiceEdge]]:
        """Extract external dependencies from a span."""
        deps = []
        
        # Check for database connections
        if self.config.include_databases and span.db_system:
            db_name = span.attributes.get("db.name", span.db_system)
            
            node = ServiceNode(
                name=f"db:{db_name}",
                node_type="database",
            )
            node.metrics.record_call(
                span.duration_ms,
                span.is_error,
                span.start_time,
            )
            node.operations.add(span.name)
            
            edge = ServiceEdge(
                source=span.service_name,
                target=node.name,
                dependency_type=DependencyType.DATABASE,
            )
            edge.operations.add(span.name)
            edge.metrics.record_call(
                span.duration_ms,
                span.is_error,
                span.start_time,
            )
            
            deps.append((node, edge))
        
        # Check for cache connections
        db_system = span.attributes.get("db.system", "")
        if self.config.include_caches and db_system.lower() in ("redis", "memcached"):
            cache_name = f"cache:{db_system}"
            
            node = ServiceNode(
                name=cache_name,
                node_type="cache",
            )
            node.metrics.record_call(
                span.duration_ms,
                span.is_error,
                span.start_time,
            )
            
            edge = ServiceEdge(
                source=span.service_name,
                target=cache_name,
                dependency_type=DependencyType.CACHE,
            )
            edge.metrics.record_call(
                span.duration_ms,
                span.is_error,
                span.start_time,
            )
            
            deps.append((node, edge))
        
        # Check for messaging
        if self.config.include_messaging and span.messaging_system:
            dest = span.messaging_destination or span.messaging_system
            msg_name = f"msg:{dest}"
            
            node = ServiceNode(
                name=msg_name,
                node_type="messaging",
            )
            node.metrics.record_call(
                span.duration_ms,
                span.is_error,
                span.start_time,
            )
            
            edge = ServiceEdge(
                source=span.service_name,
                target=msg_name,
                dependency_type=DependencyType.MESSAGING,
            )
            edge.metrics.record_call(
                span.duration_ms,
                span.is_error,
                span.start_time,
            )
            
            deps.append((node, edge))
        
        return deps
    
    def build_incremental(
        self,
        graph: ServiceGraph,
        traces: Sequence[Trace],
    ) -> ServiceGraph:
        """
        Incrementally update a graph with new traces.
        
        Useful for streaming scenarios.
        """
        graph.trace_count += len(traces)
        
        for trace in traces:
            self._process_trace(trace, graph)
        
        graph.updated_at = datetime.now(timezone.utc)
        return graph
    
    def merge_graphs(
        self,
        *graphs: ServiceGraph,
    ) -> ServiceGraph:
        """Merge multiple service graphs."""
        if not graphs:
            return ServiceGraph()
        
        merged = ServiceGraph()
        
        for graph in graphs:
            merged.trace_count += graph.trace_count
            merged.span_count += graph.span_count
            
            for node in graph.nodes.values():
                merged.add_node(node)
            
            for edge in graph.edges.values():
                merged.add_edge(edge)
        
        merged.compute_layout()
        return merged
