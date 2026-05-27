"""
On-Call Schedule Management for AutoSRE.

Provides comprehensive on-call scheduling capabilities including:
- Weekly/daily/custom rotation schedules
- Timezone-aware scheduling
- Override and swap support
- Integration with calendar systems
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, time
from enum import Enum
from typing import Any, Optional, Union

from pydantic import BaseModel, Field


class ScheduleType(str, Enum):
    """Types of on-call schedules."""
    
    WEEKLY = "weekly"           # Traditional weekly rotation
    DAILY = "daily"             # Daily rotation
    FOLLOW_THE_SUN = "follow_the_sun"  # Timezone-based rotation
    CUSTOM = "custom"           # Custom schedule pattern
    BUSINESS_HOURS = "business_hours"  # Business hours only


class DayOfWeek(str, Enum):
    """Days of the week."""
    
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class ScheduleRestrictionType(str, Enum):
    """Types of schedule restrictions."""
    
    TIME_OF_DAY = "time_of_day"     # Specific hours
    DAY_OF_WEEK = "day_of_week"     # Specific days
    HOLIDAY = "holiday"             # Holiday handling
    CUSTOM = "custom"               # Custom restriction


class OverrideReason(str, Enum):
    """Reasons for schedule overrides."""
    
    VACATION = "vacation"
    SICK_LEAVE = "sick_leave"
    SWAP = "swap"
    EMERGENCY = "emergency"
    TRAINING = "training"
    CONFERENCE = "conference"
    OTHER = "other"


@dataclass
class TimeRange:
    """A time range within a day."""
    
    start: time
    end: time
    
    def contains(self, check_time: time) -> bool:
        """Check if a time falls within this range."""
        if self.start <= self.end:
            return self.start <= check_time <= self.end
        else:
            # Handles overnight ranges (e.g., 22:00 - 06:00)
            return check_time >= self.start or check_time <= self.end
    
    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary."""
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "TimeRange":
        """Create from dictionary."""
        return cls(
            start=time.fromisoformat(data["start"]),
            end=time.fromisoformat(data["end"]),
        )


class ScheduleRestriction(BaseModel):
    """Restriction on when a schedule layer applies."""
    
    restriction_type: ScheduleRestrictionType
    time_ranges: list[dict] = Field(default_factory=list)  # TimeRange as dict
    days_of_week: list[DayOfWeek] = Field(default_factory=list)
    holiday_calendar: Optional[str] = None
    description: str = ""
    
    def is_active_at(self, dt: datetime) -> bool:
        """Check if restriction allows coverage at given datetime."""
        # Day of week check
        if self.days_of_week:
            day_name = dt.strftime("%A").lower()
            if not any(d.value == day_name for d in self.days_of_week):
                return False
        
        # Time range check
        if self.time_ranges:
            check_time = dt.time()
            for tr_dict in self.time_ranges:
                tr = TimeRange.from_dict(tr_dict)
                if tr.contains(check_time):
                    return True
            return False
        
        return True


class ScheduleLayer(BaseModel):
    """A layer in an on-call schedule (e.g., primary, secondary)."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    priority: int = Field(default=1, ge=1)  # Lower = higher priority
    users: list[str] = Field(default_factory=list)
    rotation_length_days: int = Field(default=7)
    handoff_time: str = Field(default="09:00")  # When rotation hands off
    handoff_day: DayOfWeek = Field(default=DayOfWeek.MONDAY)
    timezone: str = Field(default="UTC")
    start_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    restrictions: list[ScheduleRestriction] = Field(default_factory=list)
    
    # Current state
    current_user_index: int = Field(default=0)
    
    def get_user_at(self, dt: datetime) -> Optional[str]:
        """Get the user on-call at a specific datetime."""
        if not self.users:
            return None
        
        # Check restrictions
        for restriction in self.restrictions:
            if not restriction.is_active_at(dt):
                return None
        
        # Calculate which user based on rotation
        days_since_start = (dt - self.start_date).days
        rotations = days_since_start // self.rotation_length_days
        user_index = rotations % len(self.users)
        
        return self.users[user_index]
    
    def get_next_user(self) -> Optional[str]:
        """Get the next user in rotation."""
        if not self.users:
            return None
        next_index = (self.current_user_index + 1) % len(self.users)
        return self.users[next_index]


class ScheduleOverride(BaseModel):
    """An override to the regular schedule."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user: str
    start: datetime
    end: datetime
    reason: OverrideReason
    reason_details: str = ""
    replacement_user: Optional[str] = None
    created_by: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    
    def is_active_at(self, dt: datetime) -> bool:
        """Check if override is active at given datetime."""
        return self.start <= dt <= self.end
    
    def duration_hours(self) -> float:
        """Get duration of override in hours."""
        return (self.end - self.start).total_seconds() / 3600


class OnCallSchedule(BaseModel):
    """Complete on-call schedule with layers and overrides."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    schedule_type: ScheduleType = ScheduleType.WEEKLY
    timezone: str = Field(default="UTC")
    team_id: str = ""
    
    # Layers (primary, secondary, etc.)
    layers: list[ScheduleLayer] = Field(default_factory=list)
    
    # Overrides
    overrides: list[ScheduleOverride] = Field(default_factory=list)
    
    # Configuration
    notify_before_shift_hours: float = Field(default=24.0)
    auto_escalate: bool = Field(default=True)
    escalation_policy_id: Optional[str] = None
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = ""
    
    def add_layer(
        self,
        name: str,
        users: list[str],
        priority: int = 1,
        rotation_length_days: int = 7,
    ) -> ScheduleLayer:
        """Add a new layer to the schedule."""
        layer = ScheduleLayer(
            name=name,
            users=users,
            priority=priority,
            rotation_length_days=rotation_length_days,
        )
        self.layers.append(layer)
        self.layers.sort(key=lambda l: l.priority)
        self.updated_at = datetime.now(timezone.utc)
        return layer
    
    def add_override(
        self,
        user: str,
        start: datetime,
        end: datetime,
        reason: OverrideReason,
        replacement_user: Optional[str] = None,
        created_by: str = "",
    ) -> ScheduleOverride:
        """Add an override to the schedule."""
        override = ScheduleOverride(
            user=user,
            start=start,
            end=end,
            reason=reason,
            replacement_user=replacement_user,
            created_by=created_by,
        )
        self.overrides.append(override)
        self.updated_at = datetime.now(timezone.utc)
        return override
    
    def get_oncall_at(
        self,
        dt: Optional[datetime] = None,
        include_all_layers: bool = False,
    ) -> Union[str, list[str], None]:
        """
        Get who is on-call at a specific time.
        
        Args:
            dt: Datetime to check (defaults to now)
            include_all_layers: If True, return all on-call users across layers
            
        Returns:
            Single user (highest priority) or list of users
        """
        dt = dt or datetime.now(timezone.utc)
        oncall_users = []
        
        for layer in sorted(self.layers, key=lambda l: l.priority):
            # Check for override first
            override_user = self._check_override(layer, dt)
            if override_user:
                oncall_users.append(override_user)
            else:
                user = layer.get_user_at(dt)
                if user:
                    oncall_users.append(user)
        
        if not oncall_users:
            return [] if include_all_layers else None
        
        return oncall_users if include_all_layers else oncall_users[0]
    
    def _check_override(self, layer: ScheduleLayer, dt: datetime) -> Optional[str]:
        """Check if there's an active override for a layer."""
        for override in self.overrides:
            if override.is_active_at(dt):
                # If the original user is in this layer
                if override.user in layer.users:
                    return override.replacement_user
        return None
    
    def get_upcoming_shifts(
        self,
        user: str,
        days_ahead: int = 30,
    ) -> list[dict[str, Any]]:
        """Get upcoming shifts for a user."""
        shifts = []
        now = datetime.now(timezone.utc)
        
        for day_offset in range(days_ahead):
            check_dt = now + timedelta(days=day_offset)
            oncall = self.get_oncall_at(check_dt, include_all_layers=True)
            
            if user in (oncall if isinstance(oncall, list) else [oncall]):
                # Find which layer
                for layer in self.layers:
                    if layer.get_user_at(check_dt) == user:
                        shifts.append({
                            "date": check_dt.date().isoformat(),
                            "layer": layer.name,
                            "priority": layer.priority,
                        })
                        break
        
        return shifts
    
    def preview_schedule(
        self,
        start: Optional[datetime] = None,
        days: int = 14,
    ) -> list[dict[str, Any]]:
        """Preview schedule for the next N days."""
        start = start or datetime.now(timezone.utc)
        preview = []
        
        for day_offset in range(days):
            check_dt = start + timedelta(days=day_offset)
            oncall = self.get_oncall_at(check_dt, include_all_layers=True)
            
            preview.append({
                "date": check_dt.date().isoformat(),
                "day": check_dt.strftime("%A"),
                "oncall": oncall if isinstance(oncall, list) else [oncall] if oncall else [],
            })
        
        return preview
    
    def validate_coverage(
        self,
        start: Optional[datetime] = None,
        days: int = 30,
    ) -> dict[str, Any]:
        """Validate that schedule has coverage for upcoming period."""
        start = start or datetime.now(timezone.utc)
        gaps = []
        
        for day_offset in range(days):
            check_dt = start + timedelta(days=day_offset)
            oncall = self.get_oncall_at(check_dt)
            
            if not oncall:
                gaps.append(check_dt.date().isoformat())
        
        return {
            "has_full_coverage": len(gaps) == 0,
            "days_checked": days,
            "coverage_gaps": gaps,
            "coverage_percentage": ((days - len(gaps)) / days) * 100,
        }


class ScheduleManager:
    """Manager for on-call schedules."""
    
    def __init__(self):
        """Initialize the schedule manager."""
        self._schedules: dict[str, OnCallSchedule] = {}
        self._user_schedules: dict[str, list[str]] = {}  # user -> schedule_ids
    
    def create_schedule(
        self,
        name: str,
        schedule_type: ScheduleType = ScheduleType.WEEKLY,
        team_id: str = "",
        **kwargs: Any,
    ) -> OnCallSchedule:
        """Create a new on-call schedule."""
        schedule = OnCallSchedule(
            name=name,
            schedule_type=schedule_type,
            team_id=team_id,
            **kwargs,
        )
        self._schedules[schedule.id] = schedule
        return schedule
    
    def get_schedule(self, schedule_id: str) -> Optional[OnCallSchedule]:
        """Get a schedule by ID."""
        return self._schedules.get(schedule_id)
    
    def get_schedules_for_team(self, team_id: str) -> list[OnCallSchedule]:
        """Get all schedules for a team."""
        return [s for s in self._schedules.values() if s.team_id == team_id]
    
    def get_schedules_for_user(self, user: str) -> list[OnCallSchedule]:
        """Get all schedules containing a user."""
        results = []
        for schedule in self._schedules.values():
            for layer in schedule.layers:
                if user in layer.users:
                    results.append(schedule)
                    break
        return results
    
    def who_is_oncall(
        self,
        schedule_id: Optional[str] = None,
        team_id: Optional[str] = None,
        dt: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """
        Get who is on-call right now.
        
        Args:
            schedule_id: Specific schedule to check
            team_id: Team to check all schedules for
            dt: Time to check (defaults to now)
            
        Returns:
            On-call information
        """
        dt = dt or datetime.now(timezone.utc)
        result = {
            "timestamp": dt.isoformat(),
            "oncall": [],
        }
        
        schedules = []
        if schedule_id:
            schedule = self.get_schedule(schedule_id)
            if schedule:
                schedules = [schedule]
        elif team_id:
            schedules = self.get_schedules_for_team(team_id)
        else:
            schedules = list(self._schedules.values())
        
        for schedule in schedules:
            oncall = schedule.get_oncall_at(dt, include_all_layers=True)
            result["oncall"].append({
                "schedule_id": schedule.id,
                "schedule_name": schedule.name,
                "team_id": schedule.team_id,
                "users": oncall if isinstance(oncall, list) else [oncall] if oncall else [],
            })
        
        return result
    
    def request_swap(
        self,
        schedule_id: str,
        requester: str,
        target_user: str,
        start: datetime,
        end: datetime,
        reason: str = "",
    ) -> Optional[dict[str, Any]]:
        """
        Request a swap with another user.
        
        Args:
            schedule_id: Schedule to swap in
            requester: User requesting swap
            target_user: User to swap with
            start: Swap start time
            end: Swap end time
            reason: Reason for swap
            
        Returns:
            Swap request details
        """
        schedule = self.get_schedule(schedule_id)
        if not schedule:
            return None
        
        # Create pending swap request
        swap_request = {
            "id": str(uuid.uuid4()),
            "schedule_id": schedule_id,
            "requester": requester,
            "target_user": target_user,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "reason": reason,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        return swap_request
    
    def approve_swap(
        self,
        schedule_id: str,
        swap_request: dict[str, Any],
        approved_by: str,
    ) -> Optional[ScheduleOverride]:
        """Approve a swap request and create overrides."""
        schedule = self.get_schedule(schedule_id)
        if not schedule:
            return None
        
        # Create override for the swap
        override = schedule.add_override(
            user=swap_request["requester"],
            start=datetime.fromisoformat(swap_request["start"]),
            end=datetime.fromisoformat(swap_request["end"]),
            reason=OverrideReason.SWAP,
            replacement_user=swap_request["target_user"],
            created_by=swap_request["requester"],
        )
        override.approved_by = approved_by
        override.approved_at = datetime.now(timezone.utc)
        
        return override
    
    def export_schedule(
        self,
        schedule_id: str,
        format: str = "json",
    ) -> Optional[str]:
        """Export schedule to JSON or ICS format."""
        schedule = self.get_schedule(schedule_id)
        if not schedule:
            return None
        
        if format == "json":
            return schedule.model_dump_json(indent=2)
        elif format == "ics":
            return self._to_ics(schedule)
        
        return None
    
    def _to_ics(self, schedule: OnCallSchedule) -> str:
        """Convert schedule to ICS format."""
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//AutoSRE//OnCall Schedule//EN",
            f"X-WR-CALNAME:{schedule.name}",
        ]
        
        # Add events for next 90 days
        preview = schedule.preview_schedule(days=90)
        for day_info in preview:
            if day_info["oncall"]:
                dt = datetime.fromisoformat(day_info["date"])
                for user in day_info["oncall"]:
                    lines.extend([
                        "BEGIN:VEVENT",
                        f"UID:{uuid.uuid4()}@autosre",
                        f"DTSTART;VALUE=DATE:{dt.strftime('%Y%m%d')}",
                        f"DTEND;VALUE=DATE:{(dt + timedelta(days=1)).strftime('%Y%m%d')}",
                        f"SUMMARY:On-Call: {user}",
                        f"DESCRIPTION:{schedule.name}",
                        "END:VEVENT",
                    ])
        
        lines.append("END:VCALENDAR")
        return "\n".join(lines)


# Convenience functions
def create_weekly_schedule(
    name: str,
    users: list[str],
    handoff_day: DayOfWeek = DayOfWeek.MONDAY,
    handoff_time: str = "09:00",
    timezone: str = "UTC",
) -> OnCallSchedule:
    """Create a simple weekly rotation schedule."""
    schedule = OnCallSchedule(
        name=name,
        schedule_type=ScheduleType.WEEKLY,
        timezone=timezone,
    )
    
    schedule.add_layer(
        name="Primary",
        users=users,
        priority=1,
        rotation_length_days=7,
    )
    
    return schedule


def create_follow_the_sun_schedule(
    name: str,
    regions: dict[str, list[str]],  # timezone -> users
) -> OnCallSchedule:
    """
    Create a follow-the-sun schedule.
    
    Args:
        name: Schedule name
        regions: Dict mapping timezone to list of users
        
    Returns:
        Configured schedule
    """
    schedule = OnCallSchedule(
        name=name,
        schedule_type=ScheduleType.FOLLOW_THE_SUN,
    )
    
    priority = 1
    for tz, users in regions.items():
        # Create layer for each region with time restrictions
        layer = ScheduleLayer(
            name=f"Region: {tz}",
            users=users,
            priority=priority,
            timezone=tz,
            restrictions=[
                ScheduleRestriction(
                    restriction_type=ScheduleRestrictionType.TIME_OF_DAY,
                    time_ranges=[
                        {"start": "08:00", "end": "20:00"}
                    ],
                )
            ],
        )
        schedule.layers.append(layer)
        priority += 1
    
    return schedule
