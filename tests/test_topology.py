"""Tests for Service Topology."""

import pytest
from pathlib import Path
import tempfile

from autosre.topology import ServiceTopology, ServiceInfo


class TestServiceTopology:
    """Test topology loading and queries."""
    
    @pytest.fixture
    def sample_topology(self) -> ServiceTopology:
        """Create a sample topology for testing."""
        return ServiceTopology.from_dict({
            "services": {
                "checkout-service": {
                    "description": "Main checkout flow",
                    "dependencies": ["payment-service", "inventory-service"],
                    "owners": ["team-checkout"],
                    "alerts": ["checkout-5xx", "checkout-latency"],
                    "tier": "critical",
                },
                "payment-service": {
                    "description": "Payment processing",
                    "dependencies": ["stripe-gateway", "payment-db"],
                    "owners": ["team-payments"],
                    "alerts": ["payment-failures"],
                    "tier": "critical",
                },
                "inventory-service": {
                    "description": "Inventory management",
                    "dependencies": ["inventory-db"],
                    "owners": ["team-inventory"],
                    "tier": "high",
                },
                "stripe-gateway": {
                    "description": "Stripe API",
                    "external": True,
                },
                "payment-db": {
                    "type": "database",
                },
                "inventory-db": {
                    "type": "database",
                },
            },
            "alert_mappings": {
                "checkout-5xx": "checkout-service",
                "payment-timeout": "payment-service",
            },
            "tiers": {
                "critical": {
                    "sla_minutes": 15,
                    "notify_slack": "#incidents-critical",
                },
                "high": {
                    "sla_minutes": 60,
                },
            },
        })
    
    def test_load_services(self, sample_topology: ServiceTopology):
        """Test that services are loaded correctly."""
        assert len(sample_topology) == 6
        assert "checkout-service" in sample_topology
        assert "payment-service" in sample_topology
    
    def test_get_service(self, sample_topology: ServiceTopology):
        """Test getting service info."""
        svc = sample_topology.get_service("checkout-service")
        assert svc is not None
        assert svc.description == "Main checkout flow"
        assert svc.tier == "critical"
        assert "payment-service" in svc.dependencies
    
    def test_get_dependencies_direct(self, sample_topology: ServiceTopology):
        """Test getting direct dependencies."""
        deps = sample_topology.get_dependencies("checkout-service")
        assert set(deps) == {"payment-service", "inventory-service"}
    
    def test_get_dependencies_recursive(self, sample_topology: ServiceTopology):
        """Test getting transitive dependencies."""
        deps = sample_topology.get_dependencies("checkout-service", recursive=True)
        assert "payment-service" in deps
        assert "stripe-gateway" in deps  # transitive
        assert "payment-db" in deps  # transitive
        assert "inventory-service" in deps
        assert "inventory-db" in deps  # transitive
    
    def test_get_dependents_direct(self, sample_topology: ServiceTopology):
        """Test getting direct dependents."""
        dependents = sample_topology.get_dependents("payment-service")
        assert dependents == ["checkout-service"]
    
    def test_get_blast_radius(self, sample_topology: ServiceTopology):
        """Test blast radius calculation."""
        # If payment-db fails, payment-service fails, then checkout fails
        blast = sample_topology.get_blast_radius("payment-db")
        assert "payment-service" in blast
        assert "checkout-service" in blast
    
    def test_get_service_for_alert(self, sample_topology: ServiceTopology):
        """Test alert to service mapping."""
        # From explicit mapping
        assert sample_topology.get_service_for_alert("checkout-5xx") == "checkout-service"
        assert sample_topology.get_service_for_alert("payment-timeout") == "payment-service"
        
        # From service alerts list
        assert sample_topology.get_service_for_alert("payment-failures") == "payment-service"
        
        # Unknown
        assert sample_topology.get_service_for_alert("unknown-alert") is None
    
    def test_get_owners(self, sample_topology: ServiceTopology):
        """Test getting service owners."""
        owners = sample_topology.get_owners("checkout-service")
        assert owners == ["team-checkout"]
    
    def test_get_tier(self, sample_topology: ServiceTopology):
        """Test tier configuration retrieval."""
        tier = sample_topology.get_tier("checkout-service")
        assert tier is not None
        assert tier.sla_minutes == 15
        assert tier.notify_slack == "#incidents-critical"
    
    def test_get_critical_services(self, sample_topology: ServiceTopology):
        """Test filtering critical services."""
        critical = sample_topology.get_critical_services()
        assert set(critical) == {"checkout-service", "payment-service"}
    
    def test_to_context(self, sample_topology: ServiceTopology):
        """Test context generation for prompts."""
        ctx = sample_topology.to_context("checkout-service")
        
        assert ctx["available"] is True
        assert ctx["service"] == "checkout-service"
        assert ctx["tier"] == "critical"
        assert "payment-service" in ctx["dependencies"]
        assert ctx["blast_radius_size"] == 0  # checkout is top-level
    
    def test_format_for_prompt(self, sample_topology: ServiceTopology):
        """Test prompt formatting."""
        text = sample_topology.format_for_prompt("checkout-service")
        
        assert "checkout-service" in text
        assert "critical" in text
        assert "payment-service" in text
        assert "team-checkout" in text
    
    def test_load_from_yaml(self, tmp_path: Path):
        """Test loading from YAML file."""
        yaml_content = """
services:
  test-service:
    description: "Test service"
    dependencies:
      - dep-a
      - dep-b
    tier: high
  dep-a:
    description: "Dependency A"
  dep-b:
    description: "Dependency B"
"""
        yaml_file = tmp_path / "topology.yaml"
        yaml_file.write_text(yaml_content)
        
        topology = ServiceTopology.from_yaml(yaml_file)
        
        assert len(topology) == 3
        assert topology.get_service("test-service") is not None
        assert topology.get_dependencies("test-service") == ["dep-a", "dep-b"]
    
    def test_external_service(self, sample_topology: ServiceTopology):
        """Test external service flag."""
        svc = sample_topology.get_service("stripe-gateway")
        assert svc is not None
        assert svc.external is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
