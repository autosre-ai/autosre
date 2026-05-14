"""Causal graph construction for root cause analysis."""

from datetime import datetime
from typing import Any, Optional, List, Dict, Set, Tuple
from enum import Enum
import json

import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from autosre.models.common import utc_now, generate_id


class NodeType(str, Enum):
    """Type of node in causal graph."""
    SERVICE = "service"
    COMPONENT = "component"
    METRIC = "metric"
    EVENT = "event"
    CONFIG = "config"
    EXTERNAL = "external"


class EdgeType(str, Enum):
    """Type of causal relationship."""
    CAUSES = "causes"
    DEPENDS_ON = "depends_on"
    CORRELATES = "correlates"
    TRIGGERS = "triggers"
    INCREASES = "increases"
    DECREASES = "decreases"


class CausalNode(BaseModel):
    """A node in the causal graph."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    node_id: str = Field(default_factory=generate_id)
    name: str = Field(..., min_length=1)
    node_type: NodeType = Field(default=NodeType.COMPONENT)
    
    # Properties
    properties: dict[str, Any] = Field(default_factory=dict)
    labels: list[str] = Field(default_factory=list)
    
    # State
    is_anomalous: bool = Field(default=False)
    anomaly_score: float = Field(default=0.0, ge=0.0, le=1.0)
    current_value: Optional[float] = None
    baseline_value: Optional[float] = None
    
    # Metadata
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    
    def __hash__(self) -> int:
        return hash(self.node_id)
    
    def __eq__(self, other: object) -> bool:
        if isinstance(other, CausalNode):
            return self.node_id == other.node_id
        return False


class CausalEdge(BaseModel):
    """An edge in the causal graph."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    edge_id: str = Field(default_factory=generate_id)
    source_id: str = Field(...)
    target_id: str = Field(...)
    edge_type: EdgeType = Field(default=EdgeType.CAUSES)
    
    # Strength
    weight: float = Field(default=1.0, ge=0.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    
    # Time
    lag_seconds: float = Field(default=0.0, ge=0.0)
    
    # Properties
    properties: dict[str, Any] = Field(default_factory=dict)
    
    # Metadata
    learned: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utc_now)
    
    def __hash__(self) -> int:
        return hash((self.source_id, self.target_id, self.edge_type))


class CausalGraph:
    """Graph structure for causal relationships.
    
    Represents dependencies and causal relationships between:
    - Services
    - Components
    - Metrics
    - Events
    - Configurations
    
    Used for:
    - Impact analysis
    - Root cause localization
    - Dependency visualization
    """
    
    def __init__(self, name: str = "causal_graph"):
        """Initialize the causal graph.
        
        Args:
            name: Name of the graph
        """
        self.name = name
        self.graph_id = generate_id()
        
        self._nodes: Dict[str, CausalNode] = {}
        self._edges: Dict[str, CausalEdge] = {}
        
        # Adjacency lists for efficient traversal
        self._outgoing: Dict[str, Set[str]] = {}  # node_id -> set of edge_ids
        self._incoming: Dict[str, Set[str]] = {}  # node_id -> set of edge_ids
        
        # Index by node name for quick lookup
        self._name_index: Dict[str, str] = {}  # name -> node_id
        
        # Metadata
        self.created_at = utc_now()
        self.updated_at = utc_now()
    
    def add_node(
        self,
        name: str,
        node_type: NodeType = NodeType.COMPONENT,
        properties: Optional[dict[str, Any]] = None,
        labels: Optional[list[str]] = None,
        node_id: Optional[str] = None,
    ) -> CausalNode:
        """Add a node to the graph.
        
        Args:
            name: Node name
            node_type: Type of node
            properties: Node properties
            labels: Node labels
            node_id: Optional custom ID
            
        Returns:
            Created node
        """
        # Check if node already exists
        if name in self._name_index:
            return self._nodes[self._name_index[name]]
        
        node = CausalNode(
            node_id=node_id or generate_id(),
            name=name,
            node_type=node_type,
            properties=properties or {},
            labels=labels or [],
        )
        
        self._nodes[node.node_id] = node
        self._name_index[name] = node.node_id
        self._outgoing[node.node_id] = set()
        self._incoming[node.node_id] = set()
        
        self.updated_at = utc_now()
        
        return node
    
    def add_edge(
        self,
        source: str,
        target: str,
        edge_type: EdgeType = EdgeType.CAUSES,
        weight: float = 1.0,
        confidence: float = 1.0,
        lag_seconds: float = 0.0,
        properties: Optional[dict[str, Any]] = None,
        learned: bool = False,
    ) -> CausalEdge:
        """Add an edge to the graph.
        
        Args:
            source: Source node name or ID
            target: Target node name or ID
            edge_type: Type of relationship
            weight: Edge weight
            confidence: Confidence in relationship
            lag_seconds: Time lag in seconds
            properties: Edge properties
            learned: Whether edge was learned from data
            
        Returns:
            Created edge
        """
        # Resolve node IDs
        source_id = self._resolve_node_id(source)
        target_id = self._resolve_node_id(target)
        
        if source_id is None:
            raise ValueError(f"Source node not found: {source}")
        if target_id is None:
            raise ValueError(f"Target node not found: {target}")
        
        # Check for existing edge
        for edge_id in self._outgoing.get(source_id, set()):
            edge = self._edges[edge_id]
            if edge.target_id == target_id and edge.edge_type == edge_type:
                # Update existing edge
                edge.weight = weight
                edge.confidence = confidence
                return edge
        
        edge = CausalEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            weight=weight,
            confidence=confidence,
            lag_seconds=lag_seconds,
            properties=properties or {},
            learned=learned,
        )
        
        self._edges[edge.edge_id] = edge
        self._outgoing[source_id].add(edge.edge_id)
        self._incoming[target_id].add(edge.edge_id)
        
        self.updated_at = utc_now()
        
        return edge
    
    def _resolve_node_id(self, name_or_id: str) -> Optional[str]:
        """Resolve node name to ID.
        
        Args:
            name_or_id: Node name or ID
            
        Returns:
            Node ID or None
        """
        if name_or_id in self._nodes:
            return name_or_id
        if name_or_id in self._name_index:
            return self._name_index[name_or_id]
        return None
    
    def get_node(self, name_or_id: str) -> Optional[CausalNode]:
        """Get a node by name or ID.
        
        Args:
            name_or_id: Node name or ID
            
        Returns:
            Node or None
        """
        node_id = self._resolve_node_id(name_or_id)
        if node_id:
            return self._nodes.get(node_id)
        return None
    
    def get_edge(self, source: str, target: str) -> Optional[CausalEdge]:
        """Get edge between two nodes.
        
        Args:
            source: Source node
            target: Target node
            
        Returns:
            Edge or None
        """
        source_id = self._resolve_node_id(source)
        target_id = self._resolve_node_id(target)
        
        if source_id and target_id:
            for edge_id in self._outgoing.get(source_id, set()):
                edge = self._edges[edge_id]
                if edge.target_id == target_id:
                    return edge
        return None
    
    def get_parents(self, node: str) -> List[CausalNode]:
        """Get parent nodes (nodes that cause this node).
        
        Args:
            node: Node name or ID
            
        Returns:
            List of parent nodes
        """
        node_id = self._resolve_node_id(node)
        if not node_id:
            return []
        
        parents = []
        for edge_id in self._incoming.get(node_id, set()):
            edge = self._edges[edge_id]
            parent = self._nodes.get(edge.source_id)
            if parent:
                parents.append(parent)
        
        return parents
    
    def get_children(self, node: str) -> List[CausalNode]:
        """Get child nodes (nodes caused by this node).
        
        Args:
            node: Node name or ID
            
        Returns:
            List of child nodes
        """
        node_id = self._resolve_node_id(node)
        if not node_id:
            return []
        
        children = []
        for edge_id in self._outgoing.get(node_id, set()):
            edge = self._edges[edge_id]
            child = self._nodes.get(edge.target_id)
            if child:
                children.append(child)
        
        return children
    
    def get_ancestors(
        self,
        node: str,
        max_depth: int = 10,
    ) -> List[Tuple[CausalNode, int]]:
        """Get all ancestor nodes with depth.
        
        Args:
            node: Node name or ID
            max_depth: Maximum traversal depth
            
        Returns:
            List of (node, depth) tuples
        """
        node_id = self._resolve_node_id(node)
        if not node_id:
            return []
        
        ancestors = []
        visited = {node_id}
        queue = [(node_id, 0)]
        
        while queue:
            current_id, depth = queue.pop(0)
            
            if depth >= max_depth:
                continue
            
            for edge_id in self._incoming.get(current_id, set()):
                edge = self._edges[edge_id]
                parent_id = edge.source_id
                
                if parent_id not in visited:
                    visited.add(parent_id)
                    parent = self._nodes.get(parent_id)
                    if parent:
                        ancestors.append((parent, depth + 1))
                        queue.append((parent_id, depth + 1))
        
        return ancestors
    
    def get_descendants(
        self,
        node: str,
        max_depth: int = 10,
    ) -> List[Tuple[CausalNode, int]]:
        """Get all descendant nodes with depth.
        
        Args:
            node: Node name or ID
            max_depth: Maximum traversal depth
            
        Returns:
            List of (node, depth) tuples
        """
        node_id = self._resolve_node_id(node)
        if not node_id:
            return []
        
        descendants = []
        visited = {node_id}
        queue = [(node_id, 0)]
        
        while queue:
            current_id, depth = queue.pop(0)
            
            if depth >= max_depth:
                continue
            
            for edge_id in self._outgoing.get(current_id, set()):
                edge = self._edges[edge_id]
                child_id = edge.target_id
                
                if child_id not in visited:
                    visited.add(child_id)
                    child = self._nodes.get(child_id)
                    if child:
                        descendants.append((child, depth + 1))
                        queue.append((child_id, depth + 1))
        
        return descendants
    
    def find_paths(
        self,
        source: str,
        target: str,
        max_paths: int = 5,
        max_length: int = 10,
    ) -> List[List[CausalNode]]:
        """Find paths between two nodes.
        
        Args:
            source: Source node
            target: Target node
            max_paths: Maximum number of paths to find
            max_length: Maximum path length
            
        Returns:
            List of paths (each path is a list of nodes)
        """
        source_id = self._resolve_node_id(source)
        target_id = self._resolve_node_id(target)
        
        if not source_id or not target_id:
            return []
        
        paths = []
        
        def dfs(current: str, path: List[str], visited: Set[str]) -> None:
            if len(paths) >= max_paths or len(path) > max_length:
                return
            
            if current == target_id:
                node_path = [self._nodes[nid] for nid in path]
                paths.append(node_path)
                return
            
            for edge_id in self._outgoing.get(current, set()):
                edge = self._edges[edge_id]
                next_id = edge.target_id
                
                if next_id not in visited:
                    visited.add(next_id)
                    path.append(next_id)
                    dfs(next_id, path, visited)
                    path.pop()
                    visited.remove(next_id)
        
        dfs(source_id, [source_id], {source_id})
        
        return paths
    
    def get_anomalous_nodes(self) -> List[CausalNode]:
        """Get all nodes marked as anomalous.
        
        Returns:
            List of anomalous nodes
        """
        return [n for n in self._nodes.values() if n.is_anomalous]
    
    def set_node_anomalous(
        self,
        node: str,
        is_anomalous: bool = True,
        score: float = 1.0,
    ) -> None:
        """Mark a node as anomalous.
        
        Args:
            node: Node name or ID
            is_anomalous: Whether node is anomalous
            score: Anomaly score
        """
        node_obj = self.get_node(node)
        if node_obj:
            node_obj.is_anomalous = is_anomalous
            node_obj.anomaly_score = score
            node_obj.updated_at = utc_now()
    
    def propagate_impact(
        self,
        start_node: str,
        decay: float = 0.8,
    ) -> Dict[str, float]:
        """Propagate impact from a starting node.
        
        Args:
            start_node: Node where impact starts
            decay: Impact decay per hop
            
        Returns:
            Dictionary of node_id -> impact_score
        """
        node_id = self._resolve_node_id(start_node)
        if not node_id:
            return {}
        
        impacts = {node_id: 1.0}
        queue = [(node_id, 1.0)]
        
        while queue:
            current, impact = queue.pop(0)
            
            for edge_id in self._outgoing.get(current, set()):
                edge = self._edges[edge_id]
                child_id = edge.target_id
                
                propagated_impact = impact * decay * edge.weight * edge.confidence
                
                if propagated_impact > 0.01:  # Threshold
                    if child_id not in impacts or impacts[child_id] < propagated_impact:
                        impacts[child_id] = propagated_impact
                        queue.append((child_id, propagated_impact))
        
        return impacts
    
    def find_root_causes(
        self,
        affected_nodes: List[str],
        max_depth: int = 5,
    ) -> List[Tuple[CausalNode, float]]:
        """Find potential root causes for affected nodes.
        
        Args:
            affected_nodes: Nodes that are affected
            max_depth: Maximum search depth
            
        Returns:
            List of (node, score) tuples ranked by likelihood
        """
        # Find common ancestors
        ancestor_counts: Dict[str, int] = {}
        ancestor_depths: Dict[str, int] = {}
        
        for node in affected_nodes:
            ancestors = self.get_ancestors(node, max_depth=max_depth)
            
            for ancestor, depth in ancestors:
                ancestor_counts[ancestor.node_id] = ancestor_counts.get(ancestor.node_id, 0) + 1
                
                if ancestor.node_id not in ancestor_depths:
                    ancestor_depths[ancestor.node_id] = depth
                else:
                    ancestor_depths[ancestor.node_id] = min(ancestor_depths[ancestor.node_id], depth)
        
        # Score ancestors
        root_causes = []
        n_affected = len(affected_nodes)
        
        for node_id, count in ancestor_counts.items():
            node = self._nodes[node_id]
            depth = ancestor_depths[node_id]
            
            # Score based on:
            # 1. How many affected nodes it's an ancestor of
            # 2. How close it is (shallower depth = better)
            # 3. Whether it's anomalous
            coverage = count / n_affected
            depth_score = 1.0 / (depth + 1)
            anomaly_boost = 1.5 if node.is_anomalous else 1.0
            
            score = coverage * depth_score * anomaly_boost
            root_causes.append((node, score))
        
        # Sort by score
        root_causes.sort(key=lambda x: x[1], reverse=True)
        
        return root_causes
    
    def learn_from_correlation(
        self,
        node_a: str,
        node_b: str,
        correlation: float,
        lag_seconds: float = 0.0,
    ) -> Optional[CausalEdge]:
        """Learn an edge from correlation data.
        
        Args:
            node_a: First node
            node_b: Second node
            correlation: Correlation coefficient
            lag_seconds: Time lag (positive = A before B)
            
        Returns:
            Created edge or None
        """
        if abs(correlation) < 0.5:
            return None  # Too weak
        
        # Determine direction based on lag
        if lag_seconds > 0:
            source, target = node_a, node_b
        elif lag_seconds < 0:
            source, target = node_b, node_a
            lag_seconds = abs(lag_seconds)
        else:
            # No clear direction, use correlation sign
            if correlation > 0:
                source, target = node_a, node_b
            else:
                source, target = node_b, node_a
        
        # Determine edge type
        if correlation > 0:
            edge_type = EdgeType.INCREASES
        else:
            edge_type = EdgeType.DECREASES
        
        return self.add_edge(
            source=source,
            target=target,
            edge_type=edge_type,
            weight=abs(correlation),
            confidence=0.8,  # Learned relationships have lower confidence
            lag_seconds=lag_seconds,
            learned=True,
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert graph to dictionary.
        
        Returns:
            Dictionary representation
        """
        return {
            "name": self.name,
            "graph_id": self.graph_id,
            "nodes": [n.model_dump() for n in self._nodes.values()],
            "edges": [e.model_dump() for e in self._edges.values()],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CausalGraph":
        """Create graph from dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            CausalGraph instance
        """
        graph = cls(name=data.get("name", "causal_graph"))
        graph.graph_id = data.get("graph_id", generate_id())
        
        # Add nodes
        for node_data in data.get("nodes", []):
            node = CausalNode(**node_data)
            graph._nodes[node.node_id] = node
            graph._name_index[node.name] = node.node_id
            graph._outgoing[node.node_id] = set()
            graph._incoming[node.node_id] = set()
        
        # Add edges
        for edge_data in data.get("edges", []):
            edge = CausalEdge(**edge_data)
            graph._edges[edge.edge_id] = edge
            graph._outgoing[edge.source_id].add(edge.edge_id)
            graph._incoming[edge.target_id].add(edge.edge_id)
        
        return graph
    
    def to_json(self) -> str:
        """Convert graph to JSON string.
        
        Returns:
            JSON string
        """
        return json.dumps(self.to_dict(), default=str)
    
    @classmethod
    def from_json(cls, json_str: str) -> "CausalGraph":
        """Create graph from JSON string.
        
        Args:
            json_str: JSON string
            
        Returns:
            CausalGraph instance
        """
        return cls.from_dict(json.loads(json_str))
    
    def __len__(self) -> int:
        return len(self._nodes)
    
    def __repr__(self) -> str:
        return f"CausalGraph(name='{self.name}', nodes={len(self._nodes)}, edges={len(self._edges)})"
