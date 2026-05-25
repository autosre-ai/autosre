"""
On-Call Management for AutoSRE.

Comprehensive on-call management capabilities including:
- Load tracking to prevent burnout
- Schedule management with rotations
- Rotation policies and fairness tracking
- Escalation policies
- Shift handoffs

v2.1+ Features:
- OnCallLoadTracker: Track incidents per shift (max 2/shift)
- ScheduleManager: On-call schedules with overrides
- RotationManager: Rotation policies with fairness
- EscalationEngine: Multi-level escalation policies
- HandoffManager: Structured shift handoffs
"""

# Load tracking (original v2.1)
from .load import (
    OnCallLoadTracker,
    ShiftIncident,
    ShiftStatus,
    LoadStatus,
    MAX_INCIDENTS_PER_SHIFT,
    SHIFT_HOURS,
)

# Schedule management
from .schedule import (
    # Core types
    ScheduleType,
    DayOfWeek,
    ScheduleRestrictionType,
    OverrideReason,
    TimeRange,
    # Models
    ScheduleRestriction,
    ScheduleLayer,
    ScheduleOverride,
    OnCallSchedule,
    ScheduleManager,
    # Convenience functions
    create_weekly_schedule,
    create_follow_the_sun_schedule,
)

# Rotation management
from .rotation import (
    # Core types
    RotationType,
    RotationFrequency,
    UserAvailability,
    RotationRole,
    # Models
    UserStats,
    UserAvailabilityWindow,
    RotationConstraint,
    RotationMember,
    Rotation,
    RotationManager,
    # Convenience functions
    create_simple_rotation,
    create_tiered_rotation,
)

# Escalation policies
from .escalation import (
    # Core types
    EscalationTrigger,
    NotificationMethod,
    EscalationStatus,
    TargetType,
    # Models
    NotificationTarget,
    EscalationLevel,
    EscalationPolicy,
    EscalationEvent,
    ActiveEscalation,
    EscalationEngine,
    # Convenience functions
    create_simple_policy,
    create_tiered_policy,
)

# Shift handoffs
from .handoff import (
    # Core types
    HandoffStatus,
    HandoffItemType,
    HandoffItemPriority,
    HandoffItemStatus,
    # Models
    HandoffItem,
    IncidentSummary,
    ShiftSummary,
    Handoff,
    HandoffTemplate,
    HandoffManager,
    # Convenience functions
    create_quick_handoff,
    generate_handoff_checklist,
)

__all__ = [
    # Load tracking
    "OnCallLoadTracker",
    "ShiftIncident",
    "ShiftStatus",
    "LoadStatus",
    "MAX_INCIDENTS_PER_SHIFT",
    "SHIFT_HOURS",
    
    # Schedule management
    "ScheduleType",
    "DayOfWeek",
    "ScheduleRestrictionType",
    "OverrideReason",
    "TimeRange",
    "ScheduleRestriction",
    "ScheduleLayer",
    "ScheduleOverride",
    "OnCallSchedule",
    "ScheduleManager",
    "create_weekly_schedule",
    "create_follow_the_sun_schedule",
    
    # Rotation management
    "RotationType",
    "RotationFrequency",
    "UserAvailability",
    "RotationRole",
    "UserStats",
    "UserAvailabilityWindow",
    "RotationConstraint",
    "RotationMember",
    "Rotation",
    "RotationManager",
    "create_simple_rotation",
    "create_tiered_rotation",
    
    # Escalation policies
    "EscalationTrigger",
    "NotificationMethod",
    "EscalationStatus",
    "TargetType",
    "NotificationTarget",
    "EscalationLevel",
    "EscalationPolicy",
    "EscalationEvent",
    "ActiveEscalation",
    "EscalationEngine",
    "create_simple_policy",
    "create_tiered_policy",
    
    # Shift handoffs
    "HandoffStatus",
    "HandoffItemType",
    "HandoffItemPriority",
    "HandoffItemStatus",
    "HandoffItem",
    "IncidentSummary",
    "ShiftSummary",
    "Handoff",
    "HandoffTemplate",
    "HandoffManager",
    "create_quick_handoff",
    "generate_handoff_checklist",
]
