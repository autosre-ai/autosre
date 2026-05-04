"""
Ownership Mapping - Who owns what, and how to reach them.

This module manages:
- Service to team mappings
- On-call information
- Escalation paths
"""

from typing import Optional

from autosre.foundation.models import Ownership, Service
from autosre.foundation.context_store import ContextStore


class OwnershipManager:
    """
    Ownership manager for services.
    
    Handles:
    - Who owns a service
    - How to reach the on-call
    - Escalation paths
    """
    
    def __init__(self, context_store: ContextStore):
        """
        Initialize with a context store.
        
        Args:
            context_store: The ContextStore to read/write ownership data
        """
        self.context_store = context_store
    
    def get_owner(self, service_name: str) -> Optional[Ownership]:
        """
        Get ownership info for a service.
        
        Args:
            service_name: Service to look up
            
        Returns:
            Ownership info or None if not found
        """
        return self.context_store.get_ownership(service_name)
    
    def set_owner(self, ownership: Ownership) -> None:
        """
        Set ownership for a service.
        
        Args:
            ownership: Ownership information
        """
        self.context_store.set_ownership(ownership)
    
    def get_team_services(self, team: str) -> list[str]:
        """
        Get all services owned by a team.
        
        Args:
            team: Team name
            
        Returns:
            List of service names
        """
        services = self.context_store.list_services()
        team_services = []
        
        for service in services:
            ownership = self.context_store.get_ownership(service.name)
            if ownership and ownership.team == team:
                team_services.append(service.name)
        
        return team_services
    
    def get_escalation_path(self, service_name: str) -> list[dict]:
        """
        Get the escalation path for a service.
        
        Args:
            service_name: Service to get escalation for
            
        Returns:
            List of escalation levels with contact info
        """
        ownership = self.context_store.get_ownership(service_name)
        
        if not ownership:
            return []
        
        path = []
        
        # Level 1: On-call
        if ownership.oncall_email:
            path.append({
                "level": 1,
                "type": "oncall",
                "contact": ownership.oncall_email,
                "method": "email",
            })
        
        if ownership.slack_channel:
            path.append({
                "level": 1,
                "type": "channel",
                "contact": ownership.slack_channel,
                "method": "slack",
            })
        
        if ownership.pagerduty_service_id:
            path.append({
                "level": 1,
                "type": "pagerduty",
                "contact": ownership.pagerduty_service_id,
                "method": "pagerduty",
            })
        
        # Level 2+: Escalation contacts
        for i, contact in enumerate(ownership.escalation_contacts):
            path.append({
                "level": 2 + i,
                "type": "escalation",
                "contact": contact,
                "method": "email",
            })
        
        return path
    
    def get_critical_services(self, max_tier: int = 1) -> list[str]:
        """
        Get services at or above a criticality tier.
        
        Args:
            max_tier: Maximum tier (1 = most critical)
            
        Returns:
            List of service names
        """
        services = self.context_store.list_services()
        critical = []
        
        for service in services:
            ownership = self.context_store.get_ownership(service.name)
            if ownership and ownership.tier <= max_tier:
                critical.append(service.name)
        
        return critical
    
    def infer_ownership_from_labels(self, service: Service) -> Optional[Ownership]:
        """
        Try to infer ownership from service labels/annotations.
        
        Common patterns:
        - app.kubernetes.io/team
        - team label
        - owner annotation
        
        Args:
            service: Service to infer ownership for
            
        Returns:
            Inferred Ownership or None
        """
        labels = service.labels
        annotations = service.annotations
        
        # Try various common label patterns
        team = (
            labels.get("team") or
            labels.get("app.kubernetes.io/team") or
            labels.get("owner") or
            annotations.get("team") or
            annotations.get("autosre.io/team")
        )
        
        if not team:
            return None
        
        slack_channel = (
            annotations.get("slack-channel") or
            annotations.get("autosre.io/slack-channel")
        )
        
        pagerduty_id = (
            annotations.get("pagerduty-service-id") or
            annotations.get("autosre.io/pagerduty-service-id")
        )
        
        tier_str = annotations.get("autosre.io/tier", "3")
        try:
            tier = int(tier_str)
        except ValueError:
            tier = 3
        
        return Ownership(
            service_name=service.name,
            team=team,
            slack_channel=slack_channel,
            pagerduty_service_id=pagerduty_id,
            tier=tier,
        )
    
    def sync_from_services(self) -> int:
        """
        Infer ownership for all services from their labels.
        
        Returns:
            Number of ownership records created/updated
        """
        services = self.context_store.list_services()
        count = 0
        
        for service in services:
            # Only infer if no existing ownership
            existing = self.context_store.get_ownership(service.name)
            if existing:
                continue
            
            inferred = self.infer_ownership_from_labels(service)
            if inferred:
                self.context_store.set_ownership(inferred)
                count += 1
        
        return count
