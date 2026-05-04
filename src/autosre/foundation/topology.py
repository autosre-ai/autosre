"""
Service Topology - Build and query the service dependency graph.

The topology layer understands:
- What services exist
- How they depend on each other
- Impact analysis (what breaks if X goes down)
"""

from typing import Optional
from collections import defaultdict

from autosre.foundation.models import Service, ServiceStatus
from autosre.foundation.context_store import ContextStore


class ServiceTopology:
    """
    Service topology manager.
    
    Builds and maintains a dependency graph of services for:
    - Impact analysis
    - Root cause correlation
    - Blast radius estimation
    """
    
    def __init__(self, context_store: ContextStore):
        """
        Initialize topology with a context store.
        
        Args:
            context_store: The ContextStore to read services from
        """
        self.context_store = context_store
        self._dependency_graph: dict[str, set[str]] = defaultdict(set)  # service -> dependencies
        self._dependent_graph: dict[str, set[str]] = defaultdict(set)   # service -> dependents
        self._services: dict[str, Service] = {}
    
    def refresh(self) -> None:
        """Refresh the topology from the context store."""
        self._dependency_graph.clear()
        self._dependent_graph.clear()
        self._services.clear()
        
        services = self.context_store.list_services()
        
        for service in services:
            self._services[service.name] = service
            
            for dep in service.dependencies:
                self._dependency_graph[service.name].add(dep)
                self._dependent_graph[dep].add(service.name)
    
    def get_dependencies(self, service_name: str, recursive: bool = False) -> set[str]:
        """
        Get services that a service depends on.
        
        Args:
            service_name: Service to check
            recursive: If True, get transitive dependencies
            
        Returns:
            Set of service names
        """
        if not recursive:
            return self._dependency_graph.get(service_name, set()).copy()
        
        # BFS for transitive dependencies
        visited = set()
        queue = list(self._dependency_graph.get(service_name, set()))
        
        while queue:
            dep = queue.pop(0)
            if dep not in visited:
                visited.add(dep)
                queue.extend(self._dependency_graph.get(dep, set()) - visited)
        
        return visited
    
    def get_dependents(self, service_name: str, recursive: bool = False) -> set[str]:
        """
        Get services that depend on a service.
        
        Args:
            service_name: Service to check
            recursive: If True, get transitive dependents
            
        Returns:
            Set of service names
        """
        if not recursive:
            return self._dependent_graph.get(service_name, set()).copy()
        
        # BFS for transitive dependents
        visited = set()
        queue = list(self._dependent_graph.get(service_name, set()))
        
        while queue:
            dep = queue.pop(0)
            if dep not in visited:
                visited.add(dep)
                queue.extend(self._dependent_graph.get(dep, set()) - visited)
        
        return visited
    
    def get_impact_radius(self, service_name: str) -> dict:
        """
        Calculate the impact radius if a service goes down.
        
        Returns:
            Dict with direct/transitive impact counts and service lists
        """
        direct = self.get_dependents(service_name, recursive=False)
        transitive = self.get_dependents(service_name, recursive=True)
        
        return {
            "service": service_name,
            "direct_dependents": len(direct),
            "total_impacted": len(transitive),
            "direct_services": list(direct),
            "all_impacted_services": list(transitive),
        }
    
    def find_root_cause_candidates(self, failing_services: list[str]) -> list[str]:
        """
        Given a list of failing services, find common dependencies.
        
        These common dependencies are root cause candidates.
        
        Args:
            failing_services: List of service names currently failing
            
        Returns:
            List of service names that could be root cause (most likely first)
        """
        if not failing_services:
            return []
        
        # Get dependencies for each failing service
        dependency_sets = [
            self.get_dependencies(svc, recursive=True)
            for svc in failing_services
        ]
        
        # Find intersection (common dependencies)
        common = set.intersection(*dependency_sets) if dependency_sets else set()
        
        # Score by how many failing services depend on each
        scores = {}
        for candidate in common | set(failing_services):
            dependents = self.get_dependents(candidate, recursive=True)
            overlap = len(set(failing_services) & (dependents | {candidate}))
            scores[candidate] = overlap
        
        # Sort by score (most failing services impacted)
        sorted_candidates = sorted(scores.items(), key=lambda x: -x[1])
        
        return [c[0] for c in sorted_candidates if c[1] > 1]
    
    def get_critical_path(self, from_service: str, to_service: str) -> Optional[list[str]]:
        """
        Find the dependency path between two services.
        
        Args:
            from_service: Starting service
            to_service: Target service
            
        Returns:
            List of services in the path, or None if no path exists
        """
        if from_service == to_service:
            return [from_service]
        
        # BFS to find path
        visited = {from_service}
        queue = [(from_service, [from_service])]
        
        while queue:
            current, path = queue.pop(0)
            
            for neighbor in self._dependency_graph.get(current, set()):
                if neighbor == to_service:
                    return path + [neighbor]
                
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        
        return None
    
    def get_unhealthy_services(self) -> list[Service]:
        """Get all services that are not healthy."""
        return [
            svc for svc in self._services.values()
            if svc.status != ServiceStatus.HEALTHY
        ]
    
    def get_service_health_summary(self) -> dict:
        """Get a summary of service health."""
        summary = {
            "total": len(self._services),
            "healthy": 0,
            "degraded": 0,
            "down": 0,
            "unknown": 0,
        }
        
        for service in self._services.values():
            if service.status == ServiceStatus.HEALTHY:
                summary["healthy"] += 1
            elif service.status == ServiceStatus.DEGRADED:
                summary["degraded"] += 1
            elif service.status == ServiceStatus.DOWN:
                summary["down"] += 1
            else:
                summary["unknown"] += 1
        
        return summary
    
    def to_mermaid(self) -> str:
        """Generate a Mermaid diagram of the topology."""
        lines = ["graph TD"]
        
        for service, deps in self._dependency_graph.items():
            for dep in deps:
                # Add status styling
                svc = self._services.get(service)
                status_class = ""
                if svc:
                    if svc.status == ServiceStatus.DOWN:
                        status_class = ":::red"
                    elif svc.status == ServiceStatus.DEGRADED:
                        status_class = ":::orange"
                    elif svc.status == ServiceStatus.HEALTHY:
                        status_class = ":::green"
                
                lines.append(f"    {service}{status_class} --> {dep}")
        
        # Add styling
        lines.extend([
            "    classDef red fill:#f88,stroke:#f00",
            "    classDef orange fill:#fa0,stroke:#f80",
            "    classDef green fill:#8f8,stroke:#0f0",
        ])
        
        return "\n".join(lines)
