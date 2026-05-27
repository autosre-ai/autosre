"""
Semantic layer for LLM-friendly knowledge graph queries.

Provides natural language interfaces and formatted outputs for agent consumption.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from .client import Neo4jClient
from .topology import TopologyService
from .models import Service, Dependency, ServiceStatus, ServiceTier

logger = logging.getLogger(__name__)


@dataclass
class FormattedTopology:
    """Formatted topology for LLM consumption."""
    
    summary: str
    services: list[dict[str, Any]]
    dependencies: list[dict[str, Any]]
    mermaid_diagram: str
    
    def to_text(self) -> str:
        """Convert to plain text format."""
        lines = [self.summary, "", "Services:", "-" * 40]
        
        for svc in self.services:
            lines.append(
                f"• {svc['name']} ({svc['tier']}) - {svc['status']}"
            )
            if svc.get('description'):
                lines.append(f"  {svc['description']}")
        
        lines.extend(["", "Dependencies:", "-" * 40])
        
        for dep in self.dependencies:
            lines.append(f"• {dep['source']} → {dep['target']} ({dep['type']})")
        
        lines.extend(["", "Diagram:", "```mermaid", self.mermaid_diagram, "```"])
        
        return "\n".join(lines)
    
    def to_json(self) -> str:
        """Convert to JSON format."""
        return json.dumps({
            "summary": self.summary,
            "services": self.services,
            "dependencies": self.dependencies,
            "mermaid_diagram": self.mermaid_diagram,
        }, indent=2)


class SemanticLayer:
    """
    Semantic layer for LLM-friendly knowledge graph access.
    
    Provides:
    - Natural language query translation
    - Formatted outputs for agent consumption
    - Context-aware responses
    """
    
    def __init__(self, client: Neo4jClient):
        self.client = client
        self.topology = TopologyService(client)
    
    # =========================================================================
    # Formatted Outputs
    # =========================================================================
    
    async def format_topology_for_agent(
        self,
        namespace: str | None = None,
        include_diagram: bool = True,
    ) -> FormattedTopology:
        """
        Format the service topology for LLM consumption.
        
        Returns a structured representation with:
        - Plain English summary
        - Service list with key attributes
        - Dependency list
        - Mermaid diagram for visualization
        """
        # Get all services
        services = await self.topology.list_services(namespace=namespace)
        
        # Build dependency map
        all_deps: list[tuple[Service, Service, Dependency]] = []
        
        for service in services:
            deps = await self.topology.get_service_dependencies(service.id)
            for target, dep in deps:
                all_deps.append((service, target, dep))
        
        # Format services
        formatted_services = [
            {
                "name": s.name,
                "namespace": s.namespace,
                "tier": s.tier.value,
                "status": s.status.value,
                "team": s.team,
                "description": s.description,
                "replicas": s.replicas,
            }
            for s in services
        ]
        
        # Format dependencies
        formatted_deps = [
            {
                "source": source.name,
                "target": target.name,
                "type": dep.dependency_type.value,
                "critical": dep.is_critical,
                "has_fallback": dep.has_fallback,
            }
            for source, target, dep in all_deps
        ]
        
        # Generate summary
        tier_counts = {}
        status_counts = {}
        for s in services:
            tier_counts[s.tier.value] = tier_counts.get(s.tier.value, 0) + 1
            status_counts[s.status.value] = status_counts.get(s.status.value, 0) + 1
        
        summary_parts = [
            f"Service topology with {len(services)} services and {len(all_deps)} dependencies."
        ]
        
        if namespace:
            summary_parts.append(f"Namespace: {namespace}.")
        
        summary_parts.append(
            f"Tiers: {', '.join(f'{t}={c}' for t, c in sorted(tier_counts.items()))}."
        )
        
        unhealthy = status_counts.get("unhealthy", 0) + status_counts.get("degraded", 0)
        if unhealthy > 0:
            summary_parts.append(f"⚠️ {unhealthy} services not healthy!")
        
        summary = " ".join(summary_parts)
        
        # Generate Mermaid diagram
        mermaid = self._generate_mermaid_diagram(services, all_deps) if include_diagram else ""
        
        return FormattedTopology(
            summary=summary,
            services=formatted_services,
            dependencies=formatted_deps,
            mermaid_diagram=mermaid,
        )
    
    async def format_blast_radius(
        self,
        service_id: str,
    ) -> str:
        """
        Format blast radius analysis for LLM consumption.
        
        Returns a structured report showing:
        - The failing service
        - Direct impacts (1-hop)
        - Transitive impacts (2+ hops)
        - Impact by tier
        - Recommended actions
        """
        result = await self.topology.get_blast_radius(service_id)
        
        lines = [
            f"# Blast Radius Analysis: {result.failed_service.name}",
            "",
            f"**Service:** {result.failed_service.name}",
            f"**Tier:** {result.failed_service.tier.value}",
            f"**Team:** {result.failed_service.team}",
            "",
            f"## Impact Summary",
            f"- Direct dependents: {len(result.direct_dependents)}",
            f"- Transitive dependents: {len(result.transitive_dependents)}",
            f"- Total affected: {result.total_affected}",
        ]
        
        if result.has_tier0_impact:
            lines.extend([
                "",
                "⚠️ **CRITICAL: Tier-0 services affected!**",
            ])
        
        # Direct impacts
        if result.direct_dependents:
            lines.extend([
                "",
                "## Direct Dependents (will fail immediately)",
            ])
            for svc in result.direct_dependents:
                lines.append(f"- {svc.name} ({svc.tier.value}) - {svc.team}")
        
        # By depth
        if result.by_depth:
            lines.extend([
                "",
                "## Impact by Distance",
            ])
            for depth, services in sorted(result.by_depth.items()):
                lines.append(f"### Depth {depth}")
                for svc in services:
                    lines.append(f"- {svc.name}")
        
        # By tier
        if result.by_tier:
            lines.extend([
                "",
                "## Impact by Tier",
            ])
            for tier in ["tier_0", "tier_1", "tier_2", "tier_3"]:
                if tier in result.by_tier:
                    services = result.by_tier[tier]
                    lines.append(f"### {tier.upper()}: {len(services)} services")
                    for svc in services:
                        lines.append(f"- {svc.name}")
        
        # Recommendations
        lines.extend([
            "",
            "## Recommended Actions",
        ])
        
        if result.has_tier0_impact:
            lines.append("1. **IMMEDIATE:** Page on-call for tier-0 services")
        
        lines.extend([
            f"2. Notify teams: {', '.join(set(s.team for s in result.direct_dependents if s.team))}",
            "3. Check fallback mechanisms for critical paths",
            "4. Monitor downstream services for cascading failures",
        ])
        
        return "\n".join(lines)
    
    async def format_service_details(
        self,
        service_id: str,
    ) -> str:
        """
        Format detailed service information for LLM consumption.
        
        Returns comprehensive service info including:
        - Basic attributes
        - SLOs
        - Dependencies (upstream and downstream)
        - Health status
        """
        subgraph = await self.topology.get_service_details(service_id)
        
        if not subgraph:
            return f"Service not found: {service_id}"
        
        svc = subgraph.service
        
        lines = [
            f"# Service: {svc.name}",
            "",
            "## Overview",
            f"- **Namespace:** {svc.namespace}",
            f"- **Tier:** {svc.tier.value}",
            f"- **Status:** {svc.status.value}",
            f"- **Team:** {svc.team}",
            f"- **Owner:** {svc.owner}",
            f"- **Description:** {svc.description}",
            "",
            "## Technical Details",
            f"- **Language:** {svc.language}",
            f"- **Framework:** {svc.framework}",
            f"- **Version:** {svc.version}",
            f"- **Replicas:** {svc.replicas}",
            f"- **Repository:** {svc.repository}",
            "",
            "## SLOs",
            f"- **Availability:** {svc.slo_availability}%",
            f"- **Latency (p99):** {svc.slo_latency_p99_ms}ms",
        ]
        
        # Upstream (what calls this service)
        if subgraph.downstream:
            lines.extend([
                "",
                "## Upstream Services (what calls this)",
            ])
            for caller, dep in subgraph.downstream:
                critical = " ⚠️ CRITICAL" if dep.is_critical else ""
                lines.append(f"- {caller.name} ({dep.dependency_type.value}){critical}")
        
        # Downstream (what this service calls)
        if subgraph.upstream:
            lines.extend([
                "",
                "## Downstream Services (what this calls)",
            ])
            for target, dep in subgraph.upstream:
                critical = " ⚠️ CRITICAL" if dep.is_critical else ""
                fallback = " (has fallback)" if dep.has_fallback else ""
                lines.append(f"- {target.name} ({dep.dependency_type.value}){critical}{fallback}")
        
        return "\n".join(lines)
    
    # =========================================================================
    # Natural Language Query
    # =========================================================================
    
    async def natural_language_query(
        self,
        query: str,
    ) -> str:
        """
        Process a natural language query about the service topology.
        
        Supports queries like:
        - "What services does X depend on?"
        - "What would happen if X fails?"
        - "Show me unhealthy services"
        - "What's the blast radius of X?"
        - "Who owns service X?"
        
        Returns a formatted response suitable for LLM consumption.
        """
        query_lower = query.lower().strip()
        
        # Parse intent and extract service name
        intent, service_name = self._parse_query_intent(query_lower)
        
        if intent == "dependencies":
            return await self._handle_dependencies_query(service_name)
        
        elif intent == "dependents":
            return await self._handle_dependents_query(service_name)
        
        elif intent == "blast_radius":
            return await self._handle_blast_radius_query(service_name)
        
        elif intent == "service_info":
            return await self._handle_service_info_query(service_name)
        
        elif intent == "unhealthy":
            return await self._handle_unhealthy_query()
        
        elif intent == "topology":
            return await self._handle_topology_query()
        
        elif intent == "critical_services":
            return await self._handle_critical_services_query()
        
        elif intent == "owner":
            return await self._handle_owner_query(service_name)
        
        else:
            return self._help_response()
    
    def _parse_query_intent(self, query: str) -> tuple[str, str | None]:
        """Parse the intent and extract service name from a query."""
        
        # Blast radius patterns
        if any(p in query for p in ["blast radius", "what if", "fails", "goes down", "impact"]):
            service = self._extract_service_name(query)
            return "blast_radius", service
        
        # Dependencies patterns
        if any(p in query for p in ["depends on", "dependencies of", "what does", "downstream"]):
            service = self._extract_service_name(query)
            return "dependencies", service
        
        # Dependents patterns
        if any(p in query for p in ["depends on it", "calls", "upstream", "who uses", "who calls"]):
            service = self._extract_service_name(query)
            return "dependents", service
        
        # Service info patterns
        if any(p in query for p in ["tell me about", "info about", "details for", "describe"]):
            service = self._extract_service_name(query)
            return "service_info", service
        
        # Owner patterns
        if any(p in query for p in ["who owns", "owner of", "team for"]):
            service = self._extract_service_name(query)
            return "owner", service
        
        # Unhealthy services
        if any(p in query for p in ["unhealthy", "degraded", "down", "failing", "problems"]):
            return "unhealthy", None
        
        # Critical services
        if any(p in query for p in ["critical", "tier 0", "tier-0", "most important"]):
            return "critical_services", None
        
        # Full topology
        if any(p in query for p in ["topology", "overview", "all services", "architecture"]):
            return "topology", None
        
        return "unknown", None
    
    def _extract_service_name(self, query: str) -> str | None:
        """Extract service name from query."""
        # Common patterns: "service X", "X service", "'X'", '"X"'
        import re
        
        # Try quoted names first
        quoted = re.findall(r'["\']([^"\']+)["\']', query)
        if quoted:
            return quoted[0]
        
        # Try "service X" pattern
        match = re.search(r'service\s+(\S+)', query)
        if match:
            return match.group(1)
        
        # Try "X service" pattern
        match = re.search(r'(\S+)\s+service', query)
        if match:
            return match.group(1)
        
        # Try common service name patterns (hyphenated names)
        match = re.search(r'([a-z]+-[a-z]+(?:-[a-z]+)*)', query)
        if match:
            return match.group(1)
        
        return None
    
    async def _handle_dependencies_query(self, service_name: str | None) -> str:
        """Handle query about service dependencies."""
        if not service_name:
            return "Please specify which service you want to know the dependencies for."
        
        service = await self.topology.get_service_by_name(service_name)
        if not service:
            return f"Service '{service_name}' not found."
        
        deps = await self.topology.get_service_dependencies(service.id)
        
        if not deps:
            return f"**{service.name}** has no dependencies."
        
        lines = [f"**{service.name}** depends on {len(deps)} services:", ""]
        for target, dep in deps:
            critical = " ⚠️ CRITICAL" if dep.is_critical else ""
            lines.append(f"- **{target.name}** ({dep.dependency_type.value}){critical}")
        
        return "\n".join(lines)
    
    async def _handle_dependents_query(self, service_name: str | None) -> str:
        """Handle query about who depends on a service."""
        if not service_name:
            return "Please specify which service you want to know the dependents for."
        
        service = await self.topology.get_service_by_name(service_name)
        if not service:
            return f"Service '{service_name}' not found."
        
        dependents = await self.topology.get_upstream_services(service.id)
        
        if not dependents:
            return f"No services depend on **{service.name}**."
        
        lines = [f"{len(dependents)} services depend on **{service.name}**:", ""]
        for svc in dependents:
            lines.append(f"- **{svc.name}** ({svc.tier.value})")
        
        return "\n".join(lines)
    
    async def _handle_blast_radius_query(self, service_name: str | None) -> str:
        """Handle blast radius query."""
        if not service_name:
            return "Please specify which service to analyze."
        
        service = await self.topology.get_service_by_name(service_name)
        if not service:
            return f"Service '{service_name}' not found."
        
        return await self.format_blast_radius(service.id)
    
    async def _handle_service_info_query(self, service_name: str | None) -> str:
        """Handle service info query."""
        if not service_name:
            return "Please specify which service you want information about."
        
        service = await self.topology.get_service_by_name(service_name)
        if not service:
            return f"Service '{service_name}' not found."
        
        return await self.format_service_details(service.id)
    
    async def _handle_unhealthy_query(self) -> str:
        """Handle unhealthy services query."""
        unhealthy = await self.topology.get_unhealthy_services()
        
        if not unhealthy:
            return "✅ All services are healthy!"
        
        lines = [f"⚠️ {len(unhealthy)} unhealthy services found:", ""]
        
        for svc, affected in unhealthy:
            lines.append(f"### {svc.name} ({svc.status.value})")
            lines.append(f"- Team: {svc.team}")
            if affected:
                lines.append(f"- Potentially affecting: {', '.join(s.name for s in affected)}")
            lines.append("")
        
        return "\n".join(lines)
    
    async def _handle_topology_query(self) -> str:
        """Handle full topology query."""
        formatted = await self.format_topology_for_agent()
        return formatted.to_text()
    
    async def _handle_critical_services_query(self) -> str:
        """Handle critical services query."""
        services = await self.topology.list_services()
        critical = [s for s in services if s.tier in [ServiceTier.TIER_0, ServiceTier.TIER_1]]
        
        if not critical:
            return "No tier-0 or tier-1 services found."
        
        lines = ["# Critical Services (Tier 0-1)", ""]
        
        tier_0 = [s for s in critical if s.tier == ServiceTier.TIER_0]
        tier_1 = [s for s in critical if s.tier == ServiceTier.TIER_1]
        
        if tier_0:
            lines.append("## Tier 0 (Mission Critical)")
            for svc in tier_0:
                lines.append(f"- **{svc.name}** - {svc.description} (Team: {svc.team})")
            lines.append("")
        
        if tier_1:
            lines.append("## Tier 1 (Business Critical)")
            for svc in tier_1:
                lines.append(f"- **{svc.name}** - {svc.description} (Team: {svc.team})")
        
        return "\n".join(lines)
    
    async def _handle_owner_query(self, service_name: str | None) -> str:
        """Handle service ownership query."""
        if not service_name:
            return "Please specify which service you want to know the owner of."
        
        service = await self.topology.get_service_by_name(service_name)
        if not service:
            return f"Service '{service_name}' not found."
        
        lines = [
            f"**{service.name}** ownership:",
            f"- Team: {service.team or 'Not specified'}",
            f"- Owner: {service.owner or 'Not specified'}",
        ]
        
        return "\n".join(lines)
    
    def _help_response(self) -> str:
        """Return help text for unknown queries."""
        return """I can help with service topology questions. Try asking:

- "What services does api-gateway depend on?"
- "What's the blast radius of payment-service?"
- "Show me unhealthy services"
- "Tell me about order-service"
- "Who owns auth-service?"
- "What are the critical services?"
- "Show me the topology overview"
"""
    
    # =========================================================================
    # Diagram Generation
    # =========================================================================
    
    def _generate_mermaid_diagram(
        self,
        services: list[Service],
        dependencies: list[tuple[Service, Service, Dependency]],
    ) -> str:
        """Generate a Mermaid flowchart diagram of the topology."""
        lines = ["flowchart LR"]
        
        # Define node styles by tier
        lines.extend([
            "    classDef tier0 fill:#ff6b6b,stroke:#c92a2a,color:#fff",
            "    classDef tier1 fill:#ffd43b,stroke:#f59f00,color:#000",
            "    classDef tier2 fill:#69db7c,stroke:#37b24d,color:#000",
            "    classDef tier3 fill:#74c0fc,stroke:#339af0,color:#000",
            "    classDef unhealthy stroke:#ff0000,stroke-width:3px",
        ])
        
        # Add nodes
        for svc in services:
            node_id = svc.name.replace("-", "_")
            shape_start, shape_end = self._get_shape_for_tier(svc.tier)
            lines.append(f"    {node_id}{shape_start}{svc.name}{shape_end}")
        
        # Add edges
        for source, target, dep in dependencies:
            source_id = source.name.replace("-", "_")
            target_id = target.name.replace("-", "_")
            
            if dep.is_critical:
                lines.append(f"    {source_id} ==>|critical| {target_id}")
            elif dep.dependency_type.value == "async":
                lines.append(f"    {source_id} -.->|async| {target_id}")
            else:
                lines.append(f"    {source_id} --> {target_id}")
        
        # Apply styles
        for svc in services:
            node_id = svc.name.replace("-", "_")
            tier_class = svc.tier.value.replace("_", "")
            lines.append(f"    class {node_id} {tier_class}")
            
            if svc.status in [ServiceStatus.UNHEALTHY, ServiceStatus.DEGRADED]:
                lines.append(f"    class {node_id} unhealthy")
        
        return "\n".join(lines)
    
    def _get_shape_for_tier(self, tier: ServiceTier) -> tuple[str, str]:
        """Get Mermaid node shape based on service tier."""
        if tier == ServiceTier.TIER_0:
            return "[[", "]]"  # Stadium shape for critical
        elif tier == ServiceTier.TIER_1:
            return "{{", "}}"  # Hexagon for business critical
        elif tier == ServiceTier.TIER_2:
            return "(", ")"  # Rounded
        else:
            return "[", "]"  # Rectangle
