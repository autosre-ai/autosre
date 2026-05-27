"""
Shift Handoff Management for AutoSRE.

Provides shift handoff capabilities including:
- Structured handoff documentation
- Incident summaries
- Pending items tracking
- Knowledge transfer
"""

import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional
from collections import defaultdict

from pydantic import BaseModel, Field


class HandoffStatus(str, Enum):
    """Status of a handoff."""
    
    DRAFT = "draft"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    MISSED = "missed"


class HandoffItemType(str, Enum):
    """Types of items in a handoff."""
    
    INCIDENT = "incident"
    TASK = "task"
    MONITORING = "monitoring"
    CHANGE = "change"
    INVESTIGATION = "investigation"
    FOLLOWUP = "followup"


class HandoffItemPriority(str, Enum):
    """Priority levels for handoff items."""
    
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class HandoffItemStatus(str, Enum):
    """Status of a handoff item."""
    
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    DEFERRED = "deferred"


class HandoffItem(BaseModel):
    """An item to be handed off."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    item_type: HandoffItemType
    title: str
    description: str = ""
    priority: HandoffItemPriority = HandoffItemPriority.MEDIUM
    status: HandoffItemStatus = HandoffItemStatus.OPEN
    
    # Context
    related_incident_id: Optional[str] = None
    related_change_id: Optional[str] = None
    service_affected: str = ""
    
    # Tracking
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = ""
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Action items
    action_required: str = ""
    next_steps: list[str] = Field(default_factory=list)
    notes: str = ""
    
    # Links
    links: list[str] = Field(default_factory=list)
    
    def add_note(self, note: str, by: str = "") -> None:
        """Add a note to the item."""
        timestamp = datetime.now(timezone.utc).isoformat()
        prefix = f"[{timestamp}]"
        if by:
            prefix = f"[{timestamp} - {by}]"
        self.notes = f"{self.notes}\n{prefix} {note}".strip()
        self.updated_at = datetime.now(timezone.utc)


class IncidentSummary(BaseModel):
    """Summary of an incident for handoff."""
    
    incident_id: str
    title: str
    severity: str
    status: str
    
    # Timeline
    started_at: datetime
    detected_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    
    # Details
    description: str = ""
    root_cause: str = ""
    resolution: str = ""
    impact: str = ""
    
    # Metrics
    time_to_detect_minutes: Optional[int] = None
    time_to_acknowledge_minutes: Optional[int] = None
    time_to_resolve_minutes: Optional[int] = None
    
    # Services
    services_affected: list[str] = Field(default_factory=list)
    
    # Actions
    followup_actions: list[str] = Field(default_factory=list)
    escalated: bool = False
    escalation_reason: str = ""
    
    def is_ongoing(self) -> bool:
        """Check if incident is still ongoing."""
        return self.resolved_at is None


class ShiftSummary(BaseModel):
    """Summary of a shift for handoff."""
    
    # Shift info
    on_call_user: str
    shift_start: datetime
    shift_end: datetime
    
    # Incident stats
    total_incidents: int = 0
    critical_incidents: int = 0
    high_incidents: int = 0
    resolved_incidents: int = 0
    ongoing_incidents: int = 0
    
    # Performance
    average_response_time_minutes: Optional[float] = None
    average_resolution_time_minutes: Optional[float] = None
    
    # Escalations
    escalations_made: int = 0
    escalations_received: int = 0
    
    # Notes
    shift_notes: str = ""
    highlights: list[str] = Field(default_factory=list)
    lowlights: list[str] = Field(default_factory=list)


class Handoff(BaseModel):
    """A complete shift handoff."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # Participants
    outgoing_user: str
    incoming_user: str
    
    # Timing
    scheduled_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Status
    status: HandoffStatus = HandoffStatus.DRAFT
    
    # Content
    shift_summary: Optional[ShiftSummary] = None
    incidents: list[IncidentSummary] = Field(default_factory=list)
    handoff_items: list[HandoffItem] = Field(default_factory=list)
    
    # Additional context
    system_status: str = ""  # Overall system health
    upcoming_changes: list[str] = Field(default_factory=list)
    important_contacts: dict[str, str] = Field(default_factory=dict)
    
    # Communication
    notes: str = ""
    outgoing_notes: str = ""
    incoming_notes: str = ""
    
    # Tracking
    acknowledged_by_incoming: bool = False
    acknowledgment_time: Optional[datetime] = None
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def add_incident(self, incident: IncidentSummary) -> None:
        """Add an incident to the handoff."""
        self.incidents.append(incident)
        self.updated_at = datetime.now(timezone.utc)
    
    def add_item(
        self,
        item_type: HandoffItemType,
        title: str,
        description: str = "",
        priority: HandoffItemPriority = HandoffItemPriority.MEDIUM,
        **kwargs: Any,
    ) -> HandoffItem:
        """Add an item to the handoff."""
        item = HandoffItem(
            item_type=item_type,
            title=title,
            description=description,
            priority=priority,
            created_by=self.outgoing_user,
            **kwargs,
        )
        self.handoff_items.append(item)
        self.updated_at = datetime.now(timezone.utc)
        return item
    
    def acknowledge(self, by: str) -> bool:
        """Acknowledge the handoff."""
        if by != self.incoming_user:
            return False
        
        self.acknowledged_by_incoming = True
        self.acknowledgment_time = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        return True
    
    def start(self) -> None:
        """Start the handoff process."""
        self.status = HandoffStatus.IN_PROGRESS
        self.started_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
    
    def complete(self) -> None:
        """Complete the handoff."""
        self.status = HandoffStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
    
    def get_critical_items(self) -> list[HandoffItem]:
        """Get critical priority items."""
        return [
            item for item in self.handoff_items
            if item.priority == HandoffItemPriority.CRITICAL
        ]
    
    def get_open_items(self) -> list[HandoffItem]:
        """Get items that are still open."""
        return [
            item for item in self.handoff_items
            if item.status in (HandoffItemStatus.OPEN, HandoffItemStatus.IN_PROGRESS)
        ]
    
    def get_ongoing_incidents(self) -> list[IncidentSummary]:
        """Get incidents that are still ongoing."""
        return [inc for inc in self.incidents if inc.is_ongoing()]
    
    def generate_summary(self) -> str:
        """Generate a text summary of the handoff."""
        lines = [
            f"# Shift Handoff: {self.outgoing_user} -> {self.incoming_user}",
            f"Scheduled: {self.scheduled_at.isoformat()}",
            "",
        ]
        
        # Shift summary
        if self.shift_summary:
            lines.extend([
                "## Shift Summary",
                f"- Total Incidents: {self.shift_summary.total_incidents}",
                f"- Critical: {self.shift_summary.critical_incidents}",
                f"- Resolved: {self.shift_summary.resolved_incidents}",
                f"- Ongoing: {self.shift_summary.ongoing_incidents}",
                "",
            ])
        
        # Ongoing incidents
        ongoing = self.get_ongoing_incidents()
        if ongoing:
            lines.extend([
                "## ⚠️ Ongoing Incidents",
            ])
            for inc in ongoing:
                lines.append(
                    f"- [{inc.severity.upper()}] {inc.title} (ID: {inc.incident_id})"
                )
            lines.append("")
        
        # Critical items
        critical = self.get_critical_items()
        if critical:
            lines.extend([
                "## 🔴 Critical Items",
            ])
            for item in critical:
                lines.append(f"- {item.title}: {item.action_required}")
            lines.append("")
        
        # Open items
        open_items = [i for i in self.get_open_items() if i not in critical]
        if open_items:
            lines.extend([
                "## Open Items",
            ])
            for item in open_items:
                lines.append(f"- [{item.priority.value}] {item.title}")
            lines.append("")
        
        # Notes
        if self.notes:
            lines.extend([
                "## Notes",
                self.notes,
                "",
            ])
        
        # System status
        if self.system_status:
            lines.extend([
                "## System Status",
                self.system_status,
                "",
            ])
        
        return "\n".join(lines)


class HandoffTemplate(BaseModel):
    """Template for handoffs."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    team_id: str = ""
    
    # Template sections
    include_incident_summary: bool = True
    include_system_status: bool = True
    include_upcoming_changes: bool = True
    
    # Required fields
    required_fields: list[str] = Field(
        default_factory=lambda: [
            "shift_notes",
            "system_status",
        ]
    )
    
    # Custom sections
    custom_sections: list[dict[str, str]] = Field(default_factory=list)
    
    # Auto-population
    auto_populate_incidents: bool = True
    auto_populate_changes: bool = True
    
    # Reminders
    reminder_before_minutes: int = Field(default=30)


class HandoffManager:
    """Manager for shift handoffs."""
    
    def __init__(self):
        """Initialize the handoff manager."""
        self._handoffs: dict[str, Handoff] = {}
        self._templates: dict[str, HandoffTemplate] = {}
        self._history: dict[str, list[Handoff]] = defaultdict(list)  # user -> handoffs
    
    def create_handoff(
        self,
        outgoing_user: str,
        incoming_user: str,
        scheduled_at: datetime,
        template_id: Optional[str] = None,
    ) -> Handoff:
        """
        Create a new handoff.
        
        Args:
            outgoing_user: User ending shift
            incoming_user: User starting shift
            scheduled_at: When handoff is scheduled
            template_id: Optional template to use
            
        Returns:
            New handoff object
        """
        handoff = Handoff(
            outgoing_user=outgoing_user,
            incoming_user=incoming_user,
            scheduled_at=scheduled_at,
        )
        
        # Apply template if specified
        if template_id and template_id in self._templates:
            template = self._templates[template_id]
            # Template customization would be applied here
        
        self._handoffs[handoff.id] = handoff
        self._history[outgoing_user].append(handoff)
        self._history[incoming_user].append(handoff)
        
        return handoff
    
    def get_handoff(self, handoff_id: str) -> Optional[Handoff]:
        """Get a handoff by ID."""
        return self._handoffs.get(handoff_id)
    
    def get_pending_handoffs(
        self,
        user: Optional[str] = None,
    ) -> list[Handoff]:
        """Get pending handoffs, optionally filtered by user."""
        handoffs = [
            h for h in self._handoffs.values()
            if h.status in (HandoffStatus.DRAFT, HandoffStatus.READY, HandoffStatus.IN_PROGRESS)
        ]
        
        if user:
            handoffs = [
                h for h in handoffs
                if h.outgoing_user == user or h.incoming_user == user
            ]
        
        return sorted(handoffs, key=lambda h: h.scheduled_at)
    
    def get_user_handoff_history(
        self,
        user: str,
        limit: int = 10,
    ) -> list[Handoff]:
        """Get a user's handoff history."""
        handoffs = self._history.get(user, [])
        completed = [h for h in handoffs if h.status == HandoffStatus.COMPLETED]
        return sorted(completed, key=lambda h: h.completed_at or h.scheduled_at, reverse=True)[:limit]
    
    def create_template(
        self,
        name: str,
        team_id: str = "",
        **kwargs: Any,
    ) -> HandoffTemplate:
        """Create a handoff template."""
        template = HandoffTemplate(
            name=name,
            team_id=team_id,
            **kwargs,
        )
        self._templates[template.id] = template
        return template
    
    def get_template(self, template_id: str) -> Optional[HandoffTemplate]:
        """Get a template by ID."""
        return self._templates.get(template_id)
    
    def auto_populate_handoff(
        self,
        handoff_id: str,
        incidents: list[dict[str, Any]],
        shift_stats: Optional[dict[str, Any]] = None,
    ) -> Handoff:
        """
        Auto-populate a handoff with incident data.
        
        Args:
            handoff_id: Handoff to populate
            incidents: List of incident data dicts
            shift_stats: Optional shift statistics
            
        Returns:
            Updated handoff
        """
        handoff = self.get_handoff(handoff_id)
        if not handoff:
            raise ValueError(f"Handoff {handoff_id} not found")
        
        # Add incident summaries
        for inc_data in incidents:
            summary = IncidentSummary(
                incident_id=inc_data.get("id", ""),
                title=inc_data.get("title", ""),
                severity=inc_data.get("severity", "medium"),
                status=inc_data.get("status", "open"),
                started_at=datetime.fromisoformat(inc_data["started_at"]) if "started_at" in inc_data else datetime.now(timezone.utc),
                description=inc_data.get("description", ""),
                resolution=inc_data.get("resolution", ""),
                services_affected=inc_data.get("services", []),
            )
            
            if inc_data.get("resolved_at"):
                summary.resolved_at = datetime.fromisoformat(inc_data["resolved_at"])
            
            handoff.add_incident(summary)
            
            # Create handoff items for ongoing incidents
            if summary.is_ongoing():
                handoff.add_item(
                    item_type=HandoffItemType.INCIDENT,
                    title=f"Ongoing: {summary.title}",
                    description=summary.description,
                    priority=HandoffItemPriority.HIGH if summary.severity in ("critical", "high") else HandoffItemPriority.MEDIUM,
                    related_incident_id=summary.incident_id,
                    action_required="Continue monitoring and resolution",
                )
        
        # Add shift summary
        if shift_stats:
            handoff.shift_summary = ShiftSummary(
                on_call_user=handoff.outgoing_user,
                shift_start=datetime.fromisoformat(shift_stats.get("start", datetime.now(timezone.utc).isoformat())),
                shift_end=datetime.fromisoformat(shift_stats.get("end", datetime.now(timezone.utc).isoformat())),
                total_incidents=shift_stats.get("total_incidents", len(incidents)),
                critical_incidents=shift_stats.get("critical_incidents", 0),
                high_incidents=shift_stats.get("high_incidents", 0),
                resolved_incidents=shift_stats.get("resolved_incidents", 0),
                ongoing_incidents=shift_stats.get("ongoing_incidents", len(handoff.get_ongoing_incidents())),
            )
        
        handoff.status = HandoffStatus.READY
        handoff.updated_at = datetime.now(timezone.utc)
        
        return handoff
    
    def conduct_handoff(
        self,
        handoff_id: str,
        outgoing_notes: str = "",
        incoming_notes: str = "",
    ) -> Handoff:
        """
        Conduct the handoff meeting.
        
        Args:
            handoff_id: Handoff to conduct
            outgoing_notes: Notes from outgoing user
            incoming_notes: Notes from incoming user
            
        Returns:
            Updated handoff
        """
        handoff = self.get_handoff(handoff_id)
        if not handoff:
            raise ValueError(f"Handoff {handoff_id} not found")
        
        handoff.start()
        handoff.outgoing_notes = outgoing_notes
        handoff.incoming_notes = incoming_notes
        
        return handoff
    
    def complete_handoff(
        self,
        handoff_id: str,
        acknowledged_by: str,
    ) -> Handoff:
        """
        Complete a handoff.
        
        Args:
            handoff_id: Handoff to complete
            acknowledged_by: User acknowledging completion
            
        Returns:
            Completed handoff
        """
        handoff = self.get_handoff(handoff_id)
        if not handoff:
            raise ValueError(f"Handoff {handoff_id} not found")
        
        if acknowledged_by == handoff.incoming_user:
            handoff.acknowledge(acknowledged_by)
        
        handoff.complete()
        
        return handoff
    
    def generate_handoff_report(
        self,
        handoff_id: str,
        format: str = "markdown",
    ) -> str:
        """
        Generate a handoff report.
        
        Args:
            handoff_id: Handoff to report on
            format: Output format (markdown, json, html)
            
        Returns:
            Formatted report
        """
        handoff = self.get_handoff(handoff_id)
        if not handoff:
            return ""
        
        if format == "markdown":
            return handoff.generate_summary()
        elif format == "json":
            return handoff.model_dump_json(indent=2)
        elif format == "html":
            return self._to_html(handoff)
        
        return handoff.generate_summary()
    
    def _to_html(self, handoff: Handoff) -> str:
        """Convert handoff to HTML format."""
        markdown = handoff.generate_summary()
        
        # Simple markdown to HTML conversion
        html_lines = ["<html><body>"]
        
        for line in markdown.split("\n"):
            if line.startswith("# "):
                html_lines.append(f"<h1>{line[2:]}</h1>")
            elif line.startswith("## "):
                html_lines.append(f"<h2>{line[3:]}</h2>")
            elif line.startswith("- "):
                html_lines.append(f"<li>{line[2:]}</li>")
            elif line:
                html_lines.append(f"<p>{line}</p>")
        
        html_lines.append("</body></html>")
        return "\n".join(html_lines)
    
    def get_handoff_metrics(
        self,
        since: Optional[datetime] = None,
        team_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Get handoff metrics.
        
        Args:
            since: Only include handoffs since this time
            team_id: Filter by team
            
        Returns:
            Metrics summary
        """
        since = since or datetime.now(timezone.utc) - timedelta(days=30)
        
        handoffs = [
            h for h in self._handoffs.values()
            if h.completed_at and h.completed_at >= since
        ]
        
        if not handoffs:
            return {
                "total_handoffs": 0,
                "completed": 0,
                "missed": 0,
            }
        
        completed = [h for h in handoffs if h.status == HandoffStatus.COMPLETED]
        missed = [h for h in handoffs if h.status == HandoffStatus.MISSED]
        
        # Calculate average duration
        durations = []
        for h in completed:
            if h.started_at and h.completed_at:
                duration = (h.completed_at - h.started_at).total_seconds() / 60
                durations.append(duration)
        
        avg_duration = sum(durations) / len(durations) if durations else None
        
        # Count acknowledgments
        acknowledged = len([h for h in completed if h.acknowledged_by_incoming])
        
        return {
            "total_handoffs": len(handoffs),
            "completed": len(completed),
            "missed": len(missed),
            "acknowledgment_rate": (acknowledged / len(completed) * 100) if completed else 0,
            "average_duration_minutes": round(avg_duration, 2) if avg_duration else None,
            "since": since.isoformat(),
        }


# Convenience functions
def create_quick_handoff(
    outgoing: str,
    incoming: str,
    incidents: list[dict[str, Any]] = None,
    notes: str = "",
) -> Handoff:
    """
    Create a quick handoff with minimal setup.
    
    Args:
        outgoing: Outgoing user
        incoming: Incoming user
        incidents: Optional list of incident dicts
        notes: Optional notes
        
    Returns:
        Configured handoff
    """
    handoff = Handoff(
        outgoing_user=outgoing,
        incoming_user=incoming,
        scheduled_at=datetime.now(timezone.utc),
        notes=notes,
        status=HandoffStatus.READY,
    )
    
    if incidents:
        for inc in incidents:
            summary = IncidentSummary(
                incident_id=inc.get("id", str(uuid.uuid4())),
                title=inc.get("title", ""),
                severity=inc.get("severity", "medium"),
                status=inc.get("status", "open"),
                started_at=datetime.now(timezone.utc),
                description=inc.get("description", ""),
            )
            handoff.add_incident(summary)
    
    return handoff


def generate_handoff_checklist() -> list[str]:
    """Generate a standard handoff checklist."""
    return [
        "Review ongoing incidents and their current status",
        "Discuss any escalated issues",
        "Review pending changes and maintenance windows",
        "Check system health dashboards",
        "Review alert queue and recent alerts",
        "Discuss any customer-facing issues",
        "Share relevant context about system behavior",
        "Confirm contact information for specialists",
        "Review upcoming on-call schedule",
        "Acknowledge handoff completion",
    ]
