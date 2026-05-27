"""
War Room Coordination

Provides automated war room setup and coordination for incident response.
Integrates with communication platforms (Slack, Teams, Zoom) for
centralized incident management.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Optional
import uuid

from pydantic import BaseModel, Field


class WarRoomState(str, Enum):
    """State of a war room."""
    
    INITIALIZING = "initializing"
    ACTIVE = "active"
    MONITORING = "monitoring"
    RESOLVING = "resolving"
    CLOSED = "closed"
    ARCHIVED = "archived"


class WarRoomRole(str, Enum):
    """Roles in incident war room."""
    
    INCIDENT_COMMANDER = "incident_commander"
    COMMUNICATIONS_LEAD = "communications_lead"
    TECHNICAL_LEAD = "technical_lead"
    OPERATIONS_LEAD = "operations_lead"
    SUBJECT_MATTER_EXPERT = "subject_matter_expert"
    SCRIBE = "scribe"
    OBSERVER = "observer"
    EXECUTIVE_LIAISON = "executive_liaison"
    CUSTOMER_LIAISON = "customer_liaison"


class WarRoomEventType(str, Enum):
    """Types of war room events."""
    
    ROOM_CREATED = "room_created"
    ROOM_CLOSED = "room_closed"
    PARTICIPANT_JOINED = "participant_joined"
    PARTICIPANT_LEFT = "participant_left"
    ROLE_ASSIGNED = "role_assigned"
    STATUS_UPDATE = "status_update"
    HYPOTHESIS_ADDED = "hypothesis_added"
    HYPOTHESIS_VALIDATED = "hypothesis_validated"
    HYPOTHESIS_REJECTED = "hypothesis_rejected"
    ACTION_TAKEN = "action_taken"
    ACTION_COMPLETED = "action_completed"
    DECISION_MADE = "decision_made"
    ESCALATION = "escalation"
    MITIGATION_STARTED = "mitigation_started"
    MITIGATION_COMPLETED = "mitigation_completed"
    ROOT_CAUSE_IDENTIFIED = "root_cause_identified"
    RESOLUTION_CONFIRMED = "resolution_confirmed"
    POSTMORTEM_SCHEDULED = "postmortem_scheduled"
    CHECKLIST_ITEM_COMPLETED = "checklist_item_completed"


class WarRoomConfig(BaseModel):
    """Configuration for war room behavior."""
    
    # Channel/room creation
    create_slack_channel: bool = Field(
        default=True,
        description="Create dedicated Slack channel"
    )
    slack_channel_prefix: str = Field(
        default="inc-",
        description="Prefix for Slack channel names"
    )
    create_video_bridge: bool = Field(
        default=True,
        description="Create video conference bridge"
    )
    video_platform: str = Field(
        default="zoom",
        description="Video platform (zoom, teams, meet)"
    )
    
    # Automatic notifications
    notify_on_call: bool = Field(
        default=True,
        description="Automatically notify on-call engineer"
    )
    notify_stakeholders: bool = Field(
        default=True,
        description="Automatically notify stakeholders"
    )
    escalation_timeout_minutes: int = Field(
        default=15,
        description="Minutes before automatic escalation"
    )
    
    # Timeline and documentation
    auto_timeline: bool = Field(
        default=True,
        description="Automatically capture timeline events"
    )
    reminder_interval_minutes: int = Field(
        default=30,
        description="Minutes between status update reminders"
    )
    
    # Integration settings
    pagerduty_integration: bool = Field(
        default=True,
        description="Integrate with PagerDuty"
    )
    statuspage_integration: bool = Field(
        default=True,
        description="Integrate with Statuspage"
    )
    
    # Checklist templates
    incident_checklist_template: str = Field(
        default="default",
        description="Checklist template to use"
    )


class WarRoomParticipant(BaseModel):
    """A participant in the war room."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Participant ID")
    user_id: str = Field(..., description="User/employee ID")
    name: str = Field(..., description="Display name")
    email: Optional[str] = Field(None, description="Email address")
    role: WarRoomRole = Field(
        default=WarRoomRole.OBSERVER,
        description="Role in the war room"
    )
    joined_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Join timestamp"
    )
    left_at: Optional[datetime] = Field(None, description="Leave timestamp")
    is_active: bool = Field(default=True, description="Currently active in room")
    platform: str = Field(default="slack", description="Communication platform")
    platform_user_id: Optional[str] = Field(
        None,
        description="Platform-specific user ID"
    )


class WarRoomEvent(BaseModel):
    """An event in the war room timeline."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Event ID")
    event_type: WarRoomEventType = Field(..., description="Type of event")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Event timestamp"
    )
    actor: Optional[str] = Field(None, description="User who triggered the event")
    description: str = Field(..., description="Event description")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional event data"
    )
    auto_generated: bool = Field(
        default=False,
        description="Whether this was auto-generated"
    )


class WarRoomAction(BaseModel):
    """An action item in the war room."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Action ID")
    description: str = Field(..., description="Action description")
    assignee: Optional[str] = Field(None, description="Assigned user")
    status: str = Field(default="pending", description="Action status")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp"
    )
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    due_at: Optional[datetime] = Field(None, description="Due timestamp")
    priority: str = Field(default="high", description="Action priority")
    outcome: Optional[str] = Field(None, description="Action outcome")


class ChecklistItem(BaseModel):
    """A checklist item for incident response."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Item ID")
    title: str = Field(..., description="Checklist item title")
    description: Optional[str] = Field(None, description="Detailed description")
    phase: str = Field(default="triage", description="Incident phase")
    is_required: bool = Field(default=True, description="Whether item is required")
    is_completed: bool = Field(default=False, description="Completion status")
    completed_by: Optional[str] = Field(None, description="User who completed")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    order: int = Field(default=0, description="Display order")


class WarRoomTimeline(BaseModel):
    """Timeline of war room events."""
    
    events: list[WarRoomEvent] = Field(
        default_factory=list,
        description="Timeline events"
    )
    
    def add_event(
        self,
        event_type: WarRoomEventType,
        description: str,
        actor: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        auto_generated: bool = False,
    ) -> WarRoomEvent:
        """Add an event to the timeline."""
        event = WarRoomEvent(
            event_type=event_type,
            description=description,
            actor=actor,
            metadata=metadata or {},
            auto_generated=auto_generated,
        )
        self.events.append(event)
        return event
    
    def get_events_by_type(self, event_type: WarRoomEventType) -> list[WarRoomEvent]:
        """Get all events of a specific type."""
        return [e for e in self.events if e.event_type == event_type]
    
    def get_events_since(self, since: datetime) -> list[WarRoomEvent]:
        """Get events since a specific time."""
        return [e for e in self.events if e.timestamp >= since]
    
    def to_markdown(self) -> str:
        """Export timeline as markdown."""
        lines = ["# Incident Timeline\n"]
        for event in sorted(self.events, key=lambda e: e.timestamp):
            ts = event.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
            actor = f" ({event.actor})" if event.actor else ""
            lines.append(f"- **{ts}**{actor}: {event.description}")
        return "\n".join(lines)


class IncidentBridge(BaseModel):
    """Video/voice conference bridge for incident."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Bridge ID")
    platform: str = Field(default="zoom", description="Video platform")
    url: str = Field(..., description="Join URL")
    meeting_id: Optional[str] = Field(None, description="Meeting ID")
    passcode: Optional[str] = Field(None, description="Meeting passcode")
    phone_numbers: list[str] = Field(
        default_factory=list,
        description="Dial-in phone numbers"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp"
    )


class WarRoom(BaseModel):
    """An incident war room."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="War room ID")
    incident_id: str = Field(..., description="Associated incident ID")
    name: str = Field(..., description="War room name")
    state: WarRoomState = Field(
        default=WarRoomState.INITIALIZING,
        description="Current state"
    )
    
    # Incident details
    severity: str = Field(default="unknown", description="Incident severity")
    title: str = Field(..., description="Incident title")
    summary: Optional[str] = Field(None, description="Current summary")
    root_cause: Optional[str] = Field(None, description="Identified root cause")
    impact: Optional[str] = Field(None, description="Business impact")
    affected_services: list[str] = Field(
        default_factory=list,
        description="Affected services"
    )
    
    # Communication channels
    slack_channel_id: Optional[str] = Field(
        None,
        description="Slack channel ID"
    )
    slack_channel_name: Optional[str] = Field(
        None,
        description="Slack channel name"
    )
    bridge: Optional[IncidentBridge] = Field(
        None,
        description="Video conference bridge"
    )
    
    # Participants
    participants: list[WarRoomParticipant] = Field(
        default_factory=list,
        description="War room participants"
    )
    
    # Timeline and actions
    timeline: WarRoomTimeline = Field(
        default_factory=WarRoomTimeline,
        description="Event timeline"
    )
    actions: list[WarRoomAction] = Field(
        default_factory=list,
        description="Action items"
    )
    checklist: list[ChecklistItem] = Field(
        default_factory=list,
        description="Incident checklist"
    )
    
    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp"
    )
    activated_at: Optional[datetime] = Field(
        None,
        description="Activation timestamp"
    )
    resolved_at: Optional[datetime] = Field(
        None,
        description="Resolution timestamp"
    )
    closed_at: Optional[datetime] = Field(
        None,
        description="Close timestamp"
    )
    
    # External references
    statuspage_incident_id: Optional[str] = Field(
        None,
        description="Statuspage incident ID"
    )
    pagerduty_incident_id: Optional[str] = Field(
        None,
        description="PagerDuty incident ID"
    )
    investigation_id: Optional[str] = Field(
        None,
        description="AutoSRE investigation ID"
    )
    
    def get_incident_commander(self) -> Optional[WarRoomParticipant]:
        """Get the incident commander."""
        for p in self.participants:
            if p.role == WarRoomRole.INCIDENT_COMMANDER and p.is_active:
                return p
        return None
    
    def get_participants_by_role(self, role: WarRoomRole) -> list[WarRoomParticipant]:
        """Get all participants with a specific role."""
        return [p for p in self.participants if p.role == role and p.is_active]
    
    def get_active_participants(self) -> list[WarRoomParticipant]:
        """Get all active participants."""
        return [p for p in self.participants if p.is_active]
    
    def get_pending_actions(self) -> list[WarRoomAction]:
        """Get all pending action items."""
        return [a for a in self.actions if a.status == "pending"]
    
    def get_incomplete_checklist_items(self) -> list[ChecklistItem]:
        """Get incomplete checklist items."""
        return [c for c in self.checklist if not c.is_completed]
    
    def get_time_to_resolution(self) -> Optional[timedelta]:
        """Calculate time from creation to resolution."""
        if self.resolved_at:
            return self.resolved_at - self.created_at
        return None
    
    def get_current_duration(self) -> timedelta:
        """Get current incident duration."""
        end = self.resolved_at or datetime.now(timezone.utc)
        return end - self.created_at


# Default incident response checklist
DEFAULT_CHECKLIST = [
    ChecklistItem(
        title="Acknowledge incident",
        description="Confirm incident has been acknowledged and response initiated",
        phase="triage",
        order=1,
    ),
    ChecklistItem(
        title="Assign Incident Commander",
        description="Designate IC to coordinate response",
        phase="triage",
        order=2,
    ),
    ChecklistItem(
        title="Create communication channels",
        description="Set up Slack channel and video bridge",
        phase="triage",
        order=3,
    ),
    ChecklistItem(
        title="Assess severity and impact",
        description="Determine severity level and business impact",
        phase="triage",
        order=4,
    ),
    ChecklistItem(
        title="Notify stakeholders",
        description="Send initial notification to appropriate stakeholders",
        phase="triage",
        order=5,
    ),
    ChecklistItem(
        title="Update status page",
        description="Create or update public status page incident",
        phase="communication",
        order=6,
    ),
    ChecklistItem(
        title="Identify affected services",
        description="List all services impacted by the incident",
        phase="investigation",
        order=7,
    ),
    ChecklistItem(
        title="Form hypotheses",
        description="Generate initial hypotheses for root cause",
        phase="investigation",
        order=8,
    ),
    ChecklistItem(
        title="Gather evidence",
        description="Collect logs, metrics, and traces for analysis",
        phase="investigation",
        order=9,
    ),
    ChecklistItem(
        title="Identify root cause",
        description="Determine the root cause of the incident",
        phase="investigation",
        order=10,
    ),
    ChecklistItem(
        title="Implement mitigation",
        description="Take action to mitigate the incident",
        phase="mitigation",
        order=11,
    ),
    ChecklistItem(
        title="Verify resolution",
        description="Confirm the issue has been resolved",
        phase="resolution",
        order=12,
    ),
    ChecklistItem(
        title="Post resolution update",
        description="Update status page and notify stakeholders of resolution",
        phase="resolution",
        order=13,
    ),
    ChecklistItem(
        title="Schedule postmortem",
        description="Set up postmortem review meeting",
        phase="closure",
        order=14,
    ),
    ChecklistItem(
        title="Close war room",
        description="Archive war room and close communication channels",
        phase="closure",
        order=15,
    ),
]


class WarRoomCoordinator:
    """Coordinates war room operations.
    
    Manages war room lifecycle, participant coordination, and
    integration with external platforms.
    
    Example:
        config = WarRoomConfig(
            create_slack_channel=True,
            create_video_bridge=True,
            notify_on_call=True,
        )
        coordinator = WarRoomCoordinator(config)
        
        # Create war room for incident
        war_room = await coordinator.create_war_room(
            incident_id="inc-123",
            title="Payment API Latency",
            severity="high",
            affected_services=["payment-api", "checkout"],
        )
        
        # Add participants
        await coordinator.add_participant(
            war_room_id=war_room.id,
            user_id="user-456",
            name="Jane Engineer",
            role=WarRoomRole.INCIDENT_COMMANDER,
        )
        
        # Log events
        await coordinator.log_event(
            war_room_id=war_room.id,
            event_type=WarRoomEventType.HYPOTHESIS_ADDED,
            description="Database connection pool exhaustion",
            actor="Jane Engineer",
        )
        
        # Update status
        await coordinator.update_status(
            war_room_id=war_room.id,
            summary="Identified root cause: DB connection leak",
            root_cause="Connection leak in payment service v2.3.1",
        )
        
        # Close war room
        await coordinator.close_war_room(war_room.id)
    """
    
    def __init__(
        self,
        config: Optional[WarRoomConfig] = None,
        slack_client: Optional[Any] = None,
        video_client: Optional[Any] = None,
    ) -> None:
        """Initialize the war room coordinator.
        
        Args:
            config: War room configuration
            slack_client: Slack client for channel operations
            video_client: Video platform client for bridge creation
        """
        self.config = config or WarRoomConfig()
        self.slack_client = slack_client
        self.video_client = video_client
        self._war_rooms: dict[str, WarRoom] = {}
        self._event_handlers: list[Callable[[WarRoom, WarRoomEvent], None]] = []
    
    def register_event_handler(
        self,
        handler: Callable[[WarRoom, WarRoomEvent], None]
    ) -> None:
        """Register a handler for war room events.
        
        Args:
            handler: Callback function for events
        """
        self._event_handlers.append(handler)
    
    async def _notify_event_handlers(
        self,
        war_room: WarRoom,
        event: WarRoomEvent
    ) -> None:
        """Notify all registered event handlers."""
        for handler in self._event_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(war_room, event)
                else:
                    handler(war_room, event)
            except Exception:
                pass  # Don't let handler errors disrupt operations
    
    async def create_war_room(
        self,
        incident_id: str,
        title: str,
        severity: str = "unknown",
        affected_services: Optional[list[str]] = None,
        summary: Optional[str] = None,
        investigation_id: Optional[str] = None,
    ) -> WarRoom:
        """Create a new war room for an incident.
        
        Args:
            incident_id: Incident identifier
            title: Incident title
            severity: Incident severity
            affected_services: List of affected services
            summary: Initial incident summary
            investigation_id: Correlated AutoSRE investigation ID
            
        Returns:
            Created war room
        """
        # Generate war room name
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
        name = f"inc-{timestamp}-{incident_id[:8]}"
        
        # Create war room
        war_room = WarRoom(
            incident_id=incident_id,
            name=name,
            title=title,
            severity=severity,
            affected_services=affected_services or [],
            summary=summary,
            investigation_id=investigation_id,
        )
        
        # Add default checklist
        war_room.checklist = [
            item.model_copy() for item in DEFAULT_CHECKLIST
        ]
        
        # Create Slack channel if configured
        if self.config.create_slack_channel and self.slack_client:
            channel = await self._create_slack_channel(name, title)
            if channel:
                war_room.slack_channel_id = channel.get("id")
                war_room.slack_channel_name = channel.get("name")
        
        # Create video bridge if configured
        if self.config.create_video_bridge and self.video_client:
            bridge = await self._create_video_bridge(title)
            if bridge:
                war_room.bridge = bridge
        
        # Log creation event
        event = war_room.timeline.add_event(
            event_type=WarRoomEventType.ROOM_CREATED,
            description=f"War room created for incident: {title}",
            auto_generated=True,
            metadata={
                "severity": severity,
                "affected_services": affected_services or [],
            }
        )
        
        # Activate war room
        war_room.state = WarRoomState.ACTIVE
        war_room.activated_at = datetime.now(timezone.utc)
        
        # Store war room
        self._war_rooms[war_room.id] = war_room
        
        # Notify event handlers
        await self._notify_event_handlers(war_room, event)
        
        return war_room
    
    async def _create_slack_channel(
        self,
        name: str,
        topic: str
    ) -> Optional[dict[str, Any]]:
        """Create a Slack channel for the incident."""
        if not self.slack_client:
            return None
        
        try:
            # This would use actual Slack API
            channel_name = f"{self.config.slack_channel_prefix}{name}"
            return {
                "id": f"C{uuid.uuid4().hex[:10].upper()}",
                "name": channel_name,
            }
        except Exception:
            return None
    
    async def _create_video_bridge(self, title: str) -> Optional[IncidentBridge]:
        """Create a video conference bridge."""
        if not self.video_client:
            return None
        
        try:
            # This would use actual video platform API
            return IncidentBridge(
                platform=self.config.video_platform,
                url=f"https://{self.config.video_platform}.us/j/{uuid.uuid4().hex[:10]}",
                meeting_id=uuid.uuid4().hex[:10],
            )
        except Exception:
            return None
    
    async def add_participant(
        self,
        war_room_id: str,
        user_id: str,
        name: str,
        role: WarRoomRole = WarRoomRole.OBSERVER,
        email: Optional[str] = None,
        platform_user_id: Optional[str] = None,
    ) -> WarRoomParticipant:
        """Add a participant to the war room.
        
        Args:
            war_room_id: War room ID
            user_id: User identifier
            name: Display name
            role: Role in war room
            email: Email address
            platform_user_id: Platform-specific user ID
            
        Returns:
            Added participant
        """
        war_room = self._war_rooms.get(war_room_id)
        if not war_room:
            raise ValueError(f"War room not found: {war_room_id}")
        
        participant = WarRoomParticipant(
            user_id=user_id,
            name=name,
            email=email,
            role=role,
            platform_user_id=platform_user_id,
        )
        
        war_room.participants.append(participant)
        
        # Log join event
        event = war_room.timeline.add_event(
            event_type=WarRoomEventType.PARTICIPANT_JOINED,
            description=f"{name} joined as {role.value}",
            actor=name,
            auto_generated=True,
            metadata={"role": role.value},
        )
        
        await self._notify_event_handlers(war_room, event)
        
        return participant
    
    async def assign_role(
        self,
        war_room_id: str,
        participant_id: str,
        role: WarRoomRole,
        assigned_by: Optional[str] = None,
    ) -> None:
        """Assign a role to a participant.
        
        Args:
            war_room_id: War room ID
            participant_id: Participant ID
            role: New role
            assigned_by: User who assigned the role
        """
        war_room = self._war_rooms.get(war_room_id)
        if not war_room:
            raise ValueError(f"War room not found: {war_room_id}")
        
        for participant in war_room.participants:
            if participant.id == participant_id:
                old_role = participant.role
                participant.role = role
                
                event = war_room.timeline.add_event(
                    event_type=WarRoomEventType.ROLE_ASSIGNED,
                    description=f"{participant.name} role changed from {old_role.value} to {role.value}",
                    actor=assigned_by,
                    metadata={"old_role": old_role.value, "new_role": role.value},
                )
                
                await self._notify_event_handlers(war_room, event)
                return
        
        raise ValueError(f"Participant not found: {participant_id}")
    
    async def log_event(
        self,
        war_room_id: str,
        event_type: WarRoomEventType,
        description: str,
        actor: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> WarRoomEvent:
        """Log an event to the war room timeline.
        
        Args:
            war_room_id: War room ID
            event_type: Type of event
            description: Event description
            actor: User who triggered the event
            metadata: Additional event data
            
        Returns:
            Created event
        """
        war_room = self._war_rooms.get(war_room_id)
        if not war_room:
            raise ValueError(f"War room not found: {war_room_id}")
        
        event = war_room.timeline.add_event(
            event_type=event_type,
            description=description,
            actor=actor,
            metadata=metadata,
        )
        
        await self._notify_event_handlers(war_room, event)
        
        return event
    
    async def add_action(
        self,
        war_room_id: str,
        description: str,
        assignee: Optional[str] = None,
        priority: str = "high",
        due_at: Optional[datetime] = None,
    ) -> WarRoomAction:
        """Add an action item to the war room.
        
        Args:
            war_room_id: War room ID
            description: Action description
            assignee: Assigned user
            priority: Action priority
            due_at: Due timestamp
            
        Returns:
            Created action
        """
        war_room = self._war_rooms.get(war_room_id)
        if not war_room:
            raise ValueError(f"War room not found: {war_room_id}")
        
        action = WarRoomAction(
            description=description,
            assignee=assignee,
            priority=priority,
            due_at=due_at,
        )
        
        war_room.actions.append(action)
        
        event = war_room.timeline.add_event(
            event_type=WarRoomEventType.ACTION_TAKEN,
            description=f"Action added: {description}",
            actor=assignee,
            auto_generated=True,
            metadata={"action_id": action.id, "assignee": assignee},
        )
        
        await self._notify_event_handlers(war_room, event)
        
        return action
    
    async def complete_action(
        self,
        war_room_id: str,
        action_id: str,
        outcome: Optional[str] = None,
        completed_by: Optional[str] = None,
    ) -> None:
        """Mark an action as completed.
        
        Args:
            war_room_id: War room ID
            action_id: Action ID
            outcome: Action outcome
            completed_by: User who completed the action
        """
        war_room = self._war_rooms.get(war_room_id)
        if not war_room:
            raise ValueError(f"War room not found: {war_room_id}")
        
        for action in war_room.actions:
            if action.id == action_id:
                action.status = "completed"
                action.completed_at = datetime.now(timezone.utc)
                action.outcome = outcome
                
                event = war_room.timeline.add_event(
                    event_type=WarRoomEventType.ACTION_COMPLETED,
                    description=f"Action completed: {action.description}",
                    actor=completed_by,
                    metadata={"action_id": action_id, "outcome": outcome},
                )
                
                await self._notify_event_handlers(war_room, event)
                return
        
        raise ValueError(f"Action not found: {action_id}")
    
    async def complete_checklist_item(
        self,
        war_room_id: str,
        item_id: str,
        completed_by: Optional[str] = None,
    ) -> None:
        """Mark a checklist item as completed.
        
        Args:
            war_room_id: War room ID
            item_id: Checklist item ID
            completed_by: User who completed the item
        """
        war_room = self._war_rooms.get(war_room_id)
        if not war_room:
            raise ValueError(f"War room not found: {war_room_id}")
        
        for item in war_room.checklist:
            if item.id == item_id:
                item.is_completed = True
                item.completed_by = completed_by
                item.completed_at = datetime.now(timezone.utc)
                
                event = war_room.timeline.add_event(
                    event_type=WarRoomEventType.CHECKLIST_ITEM_COMPLETED,
                    description=f"Checklist item completed: {item.title}",
                    actor=completed_by,
                    auto_generated=True,
                    metadata={"item_id": item_id, "phase": item.phase},
                )
                
                await self._notify_event_handlers(war_room, event)
                return
        
        raise ValueError(f"Checklist item not found: {item_id}")
    
    async def update_status(
        self,
        war_room_id: str,
        summary: Optional[str] = None,
        root_cause: Optional[str] = None,
        impact: Optional[str] = None,
        state: Optional[WarRoomState] = None,
        updated_by: Optional[str] = None,
    ) -> None:
        """Update war room status.
        
        Args:
            war_room_id: War room ID
            summary: Updated summary
            root_cause: Identified root cause
            impact: Business impact
            state: New war room state
            updated_by: User who made the update
        """
        war_room = self._war_rooms.get(war_room_id)
        if not war_room:
            raise ValueError(f"War room not found: {war_room_id}")
        
        changes = []
        
        if summary is not None:
            war_room.summary = summary
            changes.append("summary")
        
        if root_cause is not None:
            war_room.root_cause = root_cause
            changes.append("root_cause")
            
            # Log root cause event
            event = war_room.timeline.add_event(
                event_type=WarRoomEventType.ROOT_CAUSE_IDENTIFIED,
                description=f"Root cause identified: {root_cause}",
                actor=updated_by,
                metadata={"root_cause": root_cause},
            )
            await self._notify_event_handlers(war_room, event)
        
        if impact is not None:
            war_room.impact = impact
            changes.append("impact")
        
        if state is not None:
            old_state = war_room.state
            war_room.state = state
            changes.append("state")
            
            if state == WarRoomState.RESOLVING:
                war_room.resolved_at = datetime.now(timezone.utc)
                event = war_room.timeline.add_event(
                    event_type=WarRoomEventType.RESOLUTION_CONFIRMED,
                    description="Incident resolution confirmed",
                    actor=updated_by,
                    auto_generated=True,
                )
                await self._notify_event_handlers(war_room, event)
        
        if changes:
            event = war_room.timeline.add_event(
                event_type=WarRoomEventType.STATUS_UPDATE,
                description=f"Status updated: {', '.join(changes)}",
                actor=updated_by,
                metadata={change: getattr(war_room, change, None) for change in changes},
            )
            await self._notify_event_handlers(war_room, event)
    
    async def close_war_room(
        self,
        war_room_id: str,
        closed_by: Optional[str] = None,
        schedule_postmortem: bool = True,
    ) -> None:
        """Close a war room.
        
        Args:
            war_room_id: War room ID
            closed_by: User who closed the room
            schedule_postmortem: Whether to schedule postmortem
        """
        war_room = self._war_rooms.get(war_room_id)
        if not war_room:
            raise ValueError(f"War room not found: {war_room_id}")
        
        war_room.state = WarRoomState.CLOSED
        war_room.closed_at = datetime.now(timezone.utc)
        
        if schedule_postmortem:
            event = war_room.timeline.add_event(
                event_type=WarRoomEventType.POSTMORTEM_SCHEDULED,
                description="Postmortem scheduled",
                actor=closed_by,
                auto_generated=True,
            )
            await self._notify_event_handlers(war_room, event)
        
        event = war_room.timeline.add_event(
            event_type=WarRoomEventType.ROOM_CLOSED,
            description="War room closed",
            actor=closed_by,
            auto_generated=True,
            metadata={
                "duration_minutes": int(war_room.get_current_duration().total_seconds() / 60),
                "actions_completed": len([a for a in war_room.actions if a.status == "completed"]),
                "checklist_completed": len([c for c in war_room.checklist if c.is_completed]),
            },
        )
        
        await self._notify_event_handlers(war_room, event)
    
    def get_war_room(self, war_room_id: str) -> Optional[WarRoom]:
        """Get a war room by ID.
        
        Args:
            war_room_id: War room ID
            
        Returns:
            War room if found
        """
        return self._war_rooms.get(war_room_id)
    
    def get_active_war_rooms(self) -> list[WarRoom]:
        """Get all active war rooms.
        
        Returns:
            List of active war rooms
        """
        return [
            wr for wr in self._war_rooms.values()
            if wr.state in [WarRoomState.ACTIVE, WarRoomState.MONITORING, WarRoomState.RESOLVING]
        ]
    
    def get_war_room_by_incident(self, incident_id: str) -> Optional[WarRoom]:
        """Get war room by incident ID.
        
        Args:
            incident_id: Incident ID
            
        Returns:
            War room if found
        """
        for wr in self._war_rooms.values():
            if wr.incident_id == incident_id:
                return wr
        return None
