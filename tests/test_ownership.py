"""
Tests for ownership management.
"""

import pytest
from autosre.foundation.ownership import OwnershipManager
from autosre.foundation.models import Ownership, Service, ServiceStatus


class TestOwnershipManager:
    """Tests for OwnershipManager."""
    
    def test_init(self, context_store):
        """Test initialization with context store."""
        manager = OwnershipManager(context_store)
        assert manager.context_store is context_store
    
    def test_get_owner_not_found(self, context_store):
        """Test getting owner for nonexistent service."""
        manager = OwnershipManager(context_store)
        result = manager.get_owner("nonexistent-service")
        assert result is None
    
    def test_set_and_get_owner(self, context_store):
        """Test setting and retrieving ownership."""
        manager = OwnershipManager(context_store)
        
        ownership = Ownership(
            service_name="payment-service",
            team="payments-team",
            slack_channel="#payments-oncall",
            pagerduty_service_id="PD123",
            oncall_email="oncall@payments.example.com",
            tier=1,
        )
        
        manager.set_owner(ownership)
        result = manager.get_owner("payment-service")
        
        assert result is not None
        assert result.service_name == "payment-service"
        assert result.team == "payments-team"
        assert result.slack_channel == "#payments-oncall"
        assert result.pagerduty_service_id == "PD123"
        assert result.tier == 1
    
    def test_get_team_services(self, context_store):
        """Test getting all services owned by a team."""
        manager = OwnershipManager(context_store)
        
        # Add some services
        service1 = Service(name="api-gateway", namespace="default")
        service2 = Service(name="user-service", namespace="default")
        service3 = Service(name="billing-service", namespace="default")
        
        context_store.add_service(service1)
        context_store.add_service(service2)
        context_store.add_service(service3)
        
        # Set ownership
        manager.set_owner(Ownership(service_name="api-gateway", team="platform"))
        manager.set_owner(Ownership(service_name="user-service", team="platform"))
        manager.set_owner(Ownership(service_name="billing-service", team="billing"))
        
        platform_services = manager.get_team_services("platform")
        assert len(platform_services) == 2
        assert "api-gateway" in platform_services
        assert "user-service" in platform_services
        
        billing_services = manager.get_team_services("billing")
        assert len(billing_services) == 1
        assert "billing-service" in billing_services
    
    def test_get_team_services_no_services(self, context_store):
        """Test getting services for a team with no services."""
        manager = OwnershipManager(context_store)
        result = manager.get_team_services("nonexistent-team")
        assert result == []
    
    def test_get_escalation_path_full(self, context_store):
        """Test full escalation path."""
        manager = OwnershipManager(context_store)
        
        ownership = Ownership(
            service_name="critical-service",
            team="sre",
            slack_channel="#sre-oncall",
            pagerduty_service_id="PD456",
            oncall_email="sre-oncall@example.com",
            escalation_contacts=["manager@example.com", "director@example.com"],
            tier=1,
        )
        
        manager.set_owner(ownership)
        path = manager.get_escalation_path("critical-service")
        
        # Should have 5 levels: 3 at level 1 + 2 escalations
        assert len(path) == 5
        
        # Check level 1 contacts
        level_1 = [p for p in path if p["level"] == 1]
        assert len(level_1) == 3
        
        contact_types = {p["type"] for p in level_1}
        assert "oncall" in contact_types
        assert "channel" in contact_types
        assert "pagerduty" in contact_types
        
        # Check escalation levels
        level_2 = [p for p in path if p["level"] == 2]
        assert len(level_2) == 1
        assert level_2[0]["contact"] == "manager@example.com"
        
        level_3 = [p for p in path if p["level"] == 3]
        assert len(level_3) == 1
        assert level_3[0]["contact"] == "director@example.com"
    
    def test_get_escalation_path_minimal(self, context_store):
        """Test escalation path with minimal info."""
        manager = OwnershipManager(context_store)
        
        ownership = Ownership(
            service_name="basic-service",
            team="dev",
            slack_channel="#dev-alerts",
        )
        
        manager.set_owner(ownership)
        path = manager.get_escalation_path("basic-service")
        
        assert len(path) == 1
        assert path[0]["type"] == "channel"
        assert path[0]["contact"] == "#dev-alerts"
    
    def test_get_escalation_path_not_found(self, context_store):
        """Test escalation path for unknown service."""
        manager = OwnershipManager(context_store)
        path = manager.get_escalation_path("unknown-service")
        assert path == []
    
    def test_get_critical_services(self, context_store):
        """Test getting critical services by tier."""
        manager = OwnershipManager(context_store)
        
        # Add services with different tiers
        for svc, tier in [("payment", 1), ("auth", 1), ("api", 2), ("frontend", 3)]:
            context_store.add_service(Service(name=svc, namespace="default"))
            manager.set_owner(Ownership(service_name=svc, team="eng", tier=tier))
        
        # Tier 1 only
        tier1 = manager.get_critical_services(max_tier=1)
        assert len(tier1) == 2
        assert "payment" in tier1
        assert "auth" in tier1
        
        # Tier 1 and 2
        tier2 = manager.get_critical_services(max_tier=2)
        assert len(tier2) == 3
        assert "api" in tier2
    
    def test_infer_ownership_from_labels_team_label(self, context_store):
        """Test inferring ownership from team label."""
        manager = OwnershipManager(context_store)
        
        service = Service(
            name="my-service",
            namespace="default",
            labels={"team": "backend"},
        )
        
        ownership = manager.infer_ownership_from_labels(service)
        
        assert ownership is not None
        assert ownership.service_name == "my-service"
        assert ownership.team == "backend"
    
    def test_infer_ownership_from_k8s_label(self, context_store):
        """Test inferring ownership from Kubernetes standard label."""
        manager = OwnershipManager(context_store)
        
        service = Service(
            name="k8s-service",
            namespace="default",
            labels={"app.kubernetes.io/team": "infrastructure"},
        )
        
        ownership = manager.infer_ownership_from_labels(service)
        
        assert ownership is not None
        assert ownership.team == "infrastructure"
    
    def test_infer_ownership_from_annotations(self, context_store):
        """Test inferring ownership with full annotations."""
        manager = OwnershipManager(context_store)
        
        service = Service(
            name="annotated-service",
            namespace="default",
            labels={},
            annotations={
                "autosre.io/team": "data-team",
                "autosre.io/slack-channel": "#data-alerts",
                "autosre.io/pagerduty-service-id": "PDDATA",
                "autosre.io/tier": "2",
            },
        )
        
        ownership = manager.infer_ownership_from_labels(service)
        
        assert ownership is not None
        assert ownership.team == "data-team"
        assert ownership.slack_channel == "#data-alerts"
        assert ownership.pagerduty_service_id == "PDDATA"
        assert ownership.tier == 2
    
    def test_infer_ownership_no_team_info(self, context_store):
        """Test inferring ownership when no team info exists."""
        manager = OwnershipManager(context_store)
        
        service = Service(
            name="unlabeled-service",
            namespace="default",
            labels={"app": "myapp"},
        )
        
        ownership = manager.infer_ownership_from_labels(service)
        assert ownership is None
    
    def test_infer_ownership_invalid_tier(self, context_store):
        """Test inferring ownership with invalid tier defaults to 3."""
        manager = OwnershipManager(context_store)
        
        service = Service(
            name="bad-tier-service",
            namespace="default",
            labels={"team": "test"},
            annotations={"autosre.io/tier": "invalid"},
        )
        
        ownership = manager.infer_ownership_from_labels(service)
        
        assert ownership is not None
        assert ownership.tier == 3  # Default
    
    def test_sync_from_services(self, context_store):
        """Test syncing ownership from service labels."""
        manager = OwnershipManager(context_store)
        
        # Add services with labels
        context_store.add_service(Service(
            name="svc-a",
            namespace="default",
            labels={"team": "team-a"},
        ))
        context_store.add_service(Service(
            name="svc-b",
            namespace="default",
            labels={"team": "team-b"},
        ))
        context_store.add_service(Service(
            name="svc-no-label",
            namespace="default",
            labels={},
        ))
        
        count = manager.sync_from_services()
        
        assert count == 2  # Only 2 had team labels
        
        assert manager.get_owner("svc-a") is not None
        assert manager.get_owner("svc-a").team == "team-a"
        assert manager.get_owner("svc-b") is not None
        assert manager.get_owner("svc-no-label") is None
    
    def test_sync_from_services_skips_existing(self, context_store):
        """Test that sync doesn't overwrite existing ownership."""
        manager = OwnershipManager(context_store)
        
        # Set existing ownership
        manager.set_owner(Ownership(
            service_name="existing-svc",
            team="original-team",
            slack_channel="#original",
        ))
        
        # Add service with different label
        context_store.add_service(Service(
            name="existing-svc",
            namespace="default",
            labels={"team": "new-team"},  # Different team in labels
        ))
        
        count = manager.sync_from_services()
        
        # Should not have synced (skipped because ownership exists)
        assert count == 0
        
        # Original ownership should be preserved
        ownership = manager.get_owner("existing-svc")
        assert ownership.team == "original-team"
        assert ownership.slack_channel == "#original"


class TestOwnershipEdgeCases:
    """Edge case tests for ownership."""
    
    def test_owner_label_priority(self, context_store):
        """Test that team label takes priority over owner label."""
        manager = OwnershipManager(context_store)
        
        service = Service(
            name="priority-test",
            namespace="default",
            labels={
                "team": "primary-team",
                "owner": "secondary-owner",
            },
        )
        
        ownership = manager.infer_ownership_from_labels(service)
        
        assert ownership is not None
        # team should take priority
        assert ownership.team == "primary-team"
    
    def test_escalation_path_only_pagerduty(self, context_store):
        """Test escalation with only PagerDuty configured."""
        manager = OwnershipManager(context_store)
        
        ownership = Ownership(
            service_name="pd-only-service",
            team="ops",
            pagerduty_service_id="PD789",
        )
        
        manager.set_owner(ownership)
        path = manager.get_escalation_path("pd-only-service")
        
        assert len(path) == 1
        assert path[0]["type"] == "pagerduty"
        assert path[0]["method"] == "pagerduty"
