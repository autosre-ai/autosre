"""
Service Topology — YAML-based service graph for dependency awareness.

Simpler than OpenSRE's Neo4j approach:
- Single YAML file defines all services and dependencies
- No external database required
- Supports blast radius calculation
"""

import logging
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ServiceInfo(BaseModel):
    """Information about a service in the topology."""
    
    name: str
    description: str = ""
    dependencies: list[str] = Field(default_factory=list)
    owners: list[str] = Field(default_factory=list)
    alerts: list[str] = Field(default_factory=list)
    runbooks: list[str] = Field(default_factory=list)
    tier: str = "medium"  # critical, high, medium, low
    type: str = "service"  # service, database, external
    external: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class TierInfo(BaseModel):
    """Tier configuration for SLA prioritization."""
    
    name: str
    sla_minutes: int = 60
    notify_slack: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ServiceTopology:
    """Service topology graph loaded from YAML.
    
    Example topology.yaml:
    
        services:
          checkout-service:
            description: "Main checkout flow"
            dependencies:
              - payment-service
              - inventory-service
            owners:
              - team-checkout
            alerts:
              - checkout-5xx
            tier: critical
            
          payment-service:
            dependencies:
              - stripe-gateway
            external: false
            
        alert_mappings:
          checkout-5xx: checkout-service
          payment-failure: payment-service
          
        tiers:
          critical:
            sla_minutes: 15
            notify_slack: "#incidents-critical"
    """
    
    def __init__(
        self,
        services: dict[str, ServiceInfo] | None = None,
        alert_mappings: dict[str, str] | None = None,
        tiers: dict[str, TierInfo] | None = None,
    ):
        self.services = services or {}
        self.alert_mappings = alert_mappings or {}
        self.tiers = tiers or {}
        
        # Build reverse dependency graph (dependents)
        self._dependents: dict[str, set[str]] = {}
        self._build_reverse_graph()
    
    def _build_reverse_graph(self) -> None:
        """Build reverse dependency graph for blast radius."""
        self._dependents = {name: set() for name in self.services}
        
        for name, service in self.services.items():
            for dep in service.dependencies:
                if dep not in self._dependents:
                    self._dependents[dep] = set()
                self._dependents[dep].add(name)
    
    @classmethod
    def from_yaml(cls, path: Path | str) -> "ServiceTopology":
        """Load topology from YAML file.
        
        Args:
            path: Path to topology.yaml file.
            
        Returns:
            ServiceTopology instance.
            
        Raises:
            FileNotFoundError: If file doesn't exist.
            ValueError: If YAML is invalid.
        """
        path = Path(path)
        
        if not path.exists():
            raise FileNotFoundError(f"Topology file not found: {path}")
        
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        
        return cls.from_dict(data)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ServiceTopology":
        """Load topology from dictionary."""
        services: dict[str, ServiceInfo] = {}
        
        for name, svc_data in data.get("services", {}).items():
            if isinstance(svc_data, dict):
                services[name] = ServiceInfo(name=name, **svc_data)
            else:
                services[name] = ServiceInfo(name=name)
        
        alert_mappings = data.get("alert_mappings", {})
        
        tiers: dict[str, TierInfo] = {}
        for name, tier_data in data.get("tiers", {}).items():
            if isinstance(tier_data, dict):
                tiers[name] = TierInfo(name=name, **tier_data)
            else:
                tiers[name] = TierInfo(name=name)
        
        return cls(services=services, alert_mappings=alert_mappings, tiers=tiers)
    
    @classmethod
    def empty(cls) -> "ServiceTopology":
        """Create an empty topology."""
        return cls()
    
    def get_service(self, name: str) -> Optional[ServiceInfo]:
        """Get service by name."""
        return self.services.get(name)
    
    def get_dependencies(self, service: str, recursive: bool = False) -> list[str]:
        """Get services that this service depends on.
        
        Args:
            service: Service name.
            recursive: If True, include transitive dependencies.
            
        Returns:
            List of dependency service names.
        """
        svc = self.services.get(service)
        if not svc:
            return []
        
        if not recursive:
            return list(svc.dependencies)
        
        # BFS for transitive dependencies
        result: list[str] = []
        visited: set[str] = set()
        queue = list(svc.dependencies)
        
        while queue:
            dep = queue.pop(0)
            if dep in visited:
                continue
            visited.add(dep)
            result.append(dep)
            
            dep_svc = self.services.get(dep)
            if dep_svc:
                queue.extend(d for d in dep_svc.dependencies if d not in visited)
        
        return result
    
    def get_dependents(self, service: str, recursive: bool = False) -> list[str]:
        """Get services that depend on this service (blast radius).
        
        Args:
            service: Service name.
            recursive: If True, include transitive dependents.
            
        Returns:
            List of dependent service names.
        """
        direct = list(self._dependents.get(service, set()))
        
        if not recursive:
            return direct
        
        # BFS for transitive dependents
        result: list[str] = []
        visited: set[str] = set()
        queue = direct.copy()
        
        while queue:
            dep = queue.pop(0)
            if dep in visited:
                continue
            visited.add(dep)
            result.append(dep)
            
            queue.extend(d for d in self._dependents.get(dep, set()) if d not in visited)
        
        return result
    
    def get_blast_radius(self, service: str) -> list[str]:
        """Get full blast radius (all services affected if this fails).
        
        Alias for get_dependents(recursive=True).
        """
        return self.get_dependents(service, recursive=True)
    
    def get_owners(self, service: str) -> list[str]:
        """Get owners for a service."""
        svc = self.services.get(service)
        return list(svc.owners) if svc else []
    
    def get_runbooks(self, service: str) -> list[str]:
        """Get runbooks for a service."""
        svc = self.services.get(service)
        return list(svc.runbooks) if svc else []
    
    def get_service_for_alert(self, alert_name: str) -> Optional[str]:
        """Get service name for an alert.
        
        First checks alert_mappings, then searches service alerts.
        """
        # Check explicit mapping
        if alert_name in self.alert_mappings:
            return self.alert_mappings[alert_name]
        
        # Search service alerts
        for name, svc in self.services.items():
            if alert_name in svc.alerts:
                return name
        
        return None
    
    def get_tier(self, service: str) -> Optional[TierInfo]:
        """Get tier configuration for a service."""
        svc = self.services.get(service)
        if not svc:
            return None
        
        return self.tiers.get(svc.tier)
    
    def get_critical_services(self) -> list[str]:
        """Get all services marked as critical tier."""
        return [
            name for name, svc in self.services.items()
            if svc.tier == "critical"
        ]
    
    def list_services(self) -> list[str]:
        """Get list of all service names."""
        return list(self.services.keys())
    
    def to_context(self, service: str) -> dict[str, Any]:
        """Generate context dict for investigation prompts.
        
        Returns information useful for LLM investigation.
        """
        svc = self.services.get(service)
        if not svc:
            return {"available": False, "service": service}
        
        dependencies = self.get_dependencies(service)
        dependents = self.get_dependents(service)
        blast_radius = self.get_blast_radius(service)
        
        return {
            "available": True,
            "service": service,
            "description": svc.description,
            "tier": svc.tier,
            "type": svc.type,
            "external": svc.external,
            "dependencies": dependencies,
            "dependents": dependents,
            "blast_radius_size": len(blast_radius),
            "blast_radius": blast_radius[:10],  # Limit for prompt size
            "owners": svc.owners,
            "runbooks": svc.runbooks,
            "alerts": svc.alerts,
        }
    
    def format_for_prompt(self, service: str) -> str:
        """Format topology context as text for LLM prompts."""
        ctx = self.to_context(service)
        
        if not ctx["available"]:
            return f"No topology information for service: {service}"
        
        lines = [
            f"### Service: {service}",
            f"- Description: {ctx['description'] or 'N/A'}",
            f"- Tier: {ctx['tier']}",
            f"- Type: {ctx['type']}",
        ]
        
        if ctx["dependencies"]:
            lines.append(f"- Dependencies: {', '.join(ctx['dependencies'])}")
        
        if ctx["dependents"]:
            lines.append(f"- Dependents: {', '.join(ctx['dependents'])}")
        
        if ctx["blast_radius_size"] > 0:
            lines.append(f"- Blast radius: {ctx['blast_radius_size']} services")
        
        if ctx["owners"]:
            lines.append(f"- Owners: {', '.join(ctx['owners'])}")
        
        if ctx["runbooks"]:
            lines.append(f"- Runbooks: {', '.join(ctx['runbooks'])}")
        
        return "\n".join(lines)
    
    def __len__(self) -> int:
        return len(self.services)
    
    def __contains__(self, service: str) -> bool:
        return service in self.services


# Global topology instance
_topology: Optional[ServiceTopology] = None


def get_topology() -> ServiceTopology:
    """Get global topology instance."""
    global _topology
    if _topology is None:
        _topology = ServiceTopology.empty()
    return _topology


def load_topology(path: Path | str) -> ServiceTopology:
    """Load topology from file and set as global."""
    global _topology
    _topology = ServiceTopology.from_yaml(path)
    logger.info(f"[TOPOLOGY] Loaded {len(_topology)} services from {path}")
    return _topology
