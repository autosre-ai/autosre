"""
AutoSRE Incident Communications Module

Enterprise-grade incident communication capabilities providing:
- Statuspage.io integration for public status updates
- War room coordination for incident response
- Stakeholder notifications and escalation
- Message templates for consistent communication

Automate incident communications to ensure timely, consistent,
and accurate updates to all stakeholders during incidents.

Usage:
    from autosre.comms import (
        StatusPageClient, StatusPageIncident, ComponentStatus,
        WarRoom, WarRoomRole, WarRoomEvent, WarRoomCoordinator,
        StakeholderNotifier, Stakeholder, StakeholderGroup, NotificationChannel,
        MessageTemplate, TemplateEngine, get_builtin_templates,
    )
"""

from autosre.comms.statuspage import (
    StatusPageClient,
    StatusPageIncident,
    StatusPageUpdate,
    ComponentStatus,
    IncidentStatus,
    IncidentImpact,
    Component,
    ComponentGroup,
    Subscriber,
    StatusPageConfig,
)
from autosre.comms.war_room import (
    WarRoom,
    WarRoomState,
    WarRoomRole,
    WarRoomParticipant,
    WarRoomEvent,
    WarRoomEventType,
    WarRoomCoordinator,
    WarRoomConfig,
    WarRoomAction,
    WarRoomTimeline,
    ChecklistItem,
    IncidentBridge,
)
from autosre.comms.stakeholders import (
    Stakeholder,
    StakeholderGroup,
    StakeholderPriority,
    NotificationChannel,
    NotificationStatus,
    NotificationResult,
    StakeholderNotifier,
    EscalationPolicy,
    EscalationLevel,
    EscalationRule,
    NotificationPreferences,
)
from autosre.comms.templates import (
    MessageTemplate,
    TemplateContext,
    TemplateEngine,
    TemplateRegistry,
    get_builtin_templates,
    INITIAL_NOTIFICATION_TEMPLATE,
    UPDATE_TEMPLATE,
    RESOLUTION_TEMPLATE,
    POSTMORTEM_SUMMARY_TEMPLATE,
    EXECUTIVE_BRIEF_TEMPLATE,
)

__all__ = [
    # Statuspage
    "StatusPageClient",
    "StatusPageIncident",
    "StatusPageUpdate",
    "ComponentStatus",
    "IncidentStatus",
    "IncidentImpact",
    "Component",
    "ComponentGroup",
    "Subscriber",
    "StatusPageConfig",
    # War Room
    "WarRoom",
    "WarRoomState",
    "WarRoomRole",
    "WarRoomParticipant",
    "WarRoomEvent",
    "WarRoomEventType",
    "WarRoomCoordinator",
    "WarRoomConfig",
    "WarRoomAction",
    "WarRoomTimeline",
    "ChecklistItem",
    "IncidentBridge",
    # Stakeholders
    "Stakeholder",
    "StakeholderGroup",
    "StakeholderPriority",
    "NotificationChannel",
    "NotificationStatus",
    "NotificationResult",
    "StakeholderNotifier",
    "EscalationPolicy",
    "EscalationLevel",
    "EscalationRule",
    "NotificationPreferences",
    # Templates
    "MessageTemplate",
    "TemplateContext",
    "TemplateEngine",
    "TemplateRegistry",
    "get_builtin_templates",
    "INITIAL_NOTIFICATION_TEMPLATE",
    "UPDATE_TEMPLATE",
    "RESOLUTION_TEMPLATE",
    "POSTMORTEM_SUMMARY_TEMPLATE",
    "EXECUTIVE_BRIEF_TEMPLATE",
]
