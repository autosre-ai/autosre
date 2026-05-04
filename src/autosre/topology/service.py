"""
Service Graph

Models the service topology and dependencies for blast radius analysis
and impact assessment during incidents.
"""
from typing import Optional, List, Dict, Set
from dataclasses import dataclass, field


@dataclass
class ServiceNode:
    """A service in the topology graph."""
    name: str
    namespace: str = "default"
    tier: str = "unknown"  # critical, standard, best-effort
    team: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)


class ServiceGraph:
    """
    Represents the service topology as a directed graph.
    
    Used for:
    - Blast radius analysis (what's affected by this failure?)
    - Upstream analysis (what could cause this failure?)
    - Impact assessment (how critical is this service?)
    """
    
    def __init__(self):
        self._nodes: Dict[str, ServiceNode] = {}
    
    def add_service(self, node: ServiceNode) -> None:
        """Add a service to the graph."""
        self._nodes[node.name] = node
    
    def get_service(self, name: str) -> Optional[ServiceNode]:
        """Get a service by name."""
        return self._nodes.get(name)
    
    def get_dependencies(self, service: str) -> List[ServiceNode]:
        """Get all services this service depends on."""
        node = self._nodes.get(service)
        if not node:
            return []
        return [
            self._nodes[dep]
            for dep in node.dependencies
            if dep in self._nodes
        ]
    
    def get_dependents(self, service: str) -> List[ServiceNode]:
        """Get all services that depend on this service."""
        node = self._nodes.get(service)
        if not node:
            return []
        return [
            self._nodes[dep]
            for dep in node.dependents
            if dep in self._nodes
        ]
    
    def get_blast_radius(self, service: str, depth: int = 3) -> Set[str]:
        """Get all services affected if this service fails."""
        affected = set()
        to_visit = [service]
        current_depth = 0
        
        while to_visit and current_depth < depth:
            next_visit = []
            for svc in to_visit:
                for dep in self.get_dependents(svc):
                    if dep.name not in affected:
                        affected.add(dep.name)
                        next_visit.append(dep.name)
            to_visit = next_visit
            current_depth += 1
        
        return affected
    
    def get_upstream_path(self, service: str, depth: int = 5) -> List[List[str]]:
        """Get paths to upstream dependencies (potential root causes)."""
        paths = []
        
        def dfs(current: str, path: List[str], d: int):
            if d >= depth:
                return
            node = self._nodes.get(current)
            if not node:
                return
            if not node.dependencies:
                paths.append(path.copy())
                return
            for dep in node.dependencies:
                dfs(dep, path + [dep], d + 1)
        
        dfs(service, [service], 0)
        return paths
    
    def load_from_yaml(self, path: str) -> None:
        """Load topology from a YAML file."""
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        
        for svc_data in data.get("services", []):
            node = ServiceNode(
                name=svc_data["name"],
                namespace=svc_data.get("namespace", "default"),
                tier=svc_data.get("tier", "standard"),
                team=svc_data.get("team"),
                dependencies=svc_data.get("dependencies", []),
                dependents=svc_data.get("dependents", []),
                metadata=svc_data.get("metadata", {}),
            )
            self.add_service(node)
