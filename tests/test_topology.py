"""
Tests for service topology.
"""

import pytest
import tempfile
import os

from autosre.foundation.context_store import ContextStore
from autosre.foundation.topology import ServiceTopology
from autosre.foundation.models import Service, ServiceStatus


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def store(temp_db):
    """Create a context store with temporary database."""
    return ContextStore(db_path=temp_db)


@pytest.fixture
def topology(store):
    """Create a topology with test services."""
    # Create a service topology:
    # frontend -> api-gateway -> [user-service, order-service] -> database
    
    store.add_service(Service(
        name="frontend",
        dependencies=["api-gateway"],
        status=ServiceStatus.HEALTHY,
    ))
    store.add_service(Service(
        name="api-gateway",
        dependencies=["user-service", "order-service"],
        status=ServiceStatus.HEALTHY,
    ))
    store.add_service(Service(
        name="user-service",
        dependencies=["database"],
        status=ServiceStatus.HEALTHY,
    ))
    store.add_service(Service(
        name="order-service",
        dependencies=["database"],
        status=ServiceStatus.HEALTHY,
    ))
    store.add_service(Service(
        name="database",
        dependencies=[],
        status=ServiceStatus.HEALTHY,
    ))
    
    topo = ServiceTopology(store)
    topo.refresh()
    return topo


class TestServiceTopology:
    """Tests for ServiceTopology."""
    
    def test_get_dependencies(self, topology):
        """Test getting direct dependencies."""
        deps = topology.get_dependencies("api-gateway")
        
        assert "user-service" in deps
        assert "order-service" in deps
        assert len(deps) == 2
    
    def test_get_dependencies_recursive(self, topology):
        """Test getting transitive dependencies."""
        deps = topology.get_dependencies("api-gateway", recursive=True)
        
        assert "user-service" in deps
        assert "order-service" in deps
        assert "database" in deps
        assert len(deps) == 3
    
    def test_get_dependents(self, topology):
        """Test getting direct dependents."""
        deps = topology.get_dependents("database")
        
        assert "user-service" in deps
        assert "order-service" in deps
        assert len(deps) == 2
    
    def test_get_dependents_recursive(self, topology):
        """Test getting transitive dependents."""
        deps = topology.get_dependents("database", recursive=True)
        
        assert "user-service" in deps
        assert "order-service" in deps
        assert "api-gateway" in deps
        assert "frontend" in deps
        assert len(deps) == 4
    
    def test_impact_radius(self, topology):
        """Test impact radius calculation."""
        impact = topology.get_impact_radius("database")
        
        assert impact["service"] == "database"
        assert impact["direct_dependents"] == 2
        assert impact["total_impacted"] == 4  # All services depend on it
    
    def test_find_root_cause_candidates(self, topology):
        """Test finding root cause candidates."""
        # If user-service and order-service are both failing,
        # database should be a root cause candidate
        failing = ["user-service", "order-service"]
        candidates = topology.find_root_cause_candidates(failing)
        
        assert "database" in candidates
    
    def test_critical_path(self, topology):
        """Test finding critical path between services."""
        path = topology.get_critical_path("frontend", "database")
        
        assert path is not None
        assert path[0] == "frontend"
        assert path[-1] == "database"
        assert "api-gateway" in path
    
    def test_no_path(self, topology):
        """Test when no path exists."""
        # Database doesn't depend on anything
        path = topology.get_critical_path("database", "frontend")
        
        assert path is None
    
    def test_health_summary(self, topology, store):
        """Test service health summary."""
        # Make one service unhealthy
        store.add_service(Service(
            name="database",
            dependencies=[],
            status=ServiceStatus.DOWN,
        ))
        topology.refresh()
        
        summary = topology.get_service_health_summary()
        
        assert summary["total"] == 5
        assert summary["down"] == 1
        assert summary["healthy"] == 4
    
    def test_mermaid_diagram(self, topology):
        """Test Mermaid diagram generation."""
        diagram = topology.to_mermaid()
        
        assert "graph TD" in diagram
        assert "frontend" in diagram
        assert "-->" in diagram
