"""
On-Call Rotation Management for AutoSRE.

Provides rotation management capabilities including:
- Rotation policies and rules
- Automatic rotation advancement
- Fairness tracking
- PTO/vacation handling
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional
from collections import defaultdict

from pydantic import BaseModel, Field


class RotationType(str, Enum):
    """Types of rotation patterns."""
    
    ROUND_ROBIN = "round_robin"         # Simple sequential rotation
    WEIGHTED = "weighted"               # Weighted based on experience/preference
    FAIR_DISTRIBUTION = "fair_distribution"  # Balance based on past shifts
    SKILL_BASED = "skill_based"         # Match skills to needs
    RANDOM = "random"                   # Random selection


class RotationFrequency(str, Enum):
    """Frequency of rotation."""
    
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class UserAvailability(str, Enum):
    """User availability status."""
    
    AVAILABLE = "available"
    PARTIAL = "partial"           # Limited availability
    UNAVAILABLE = "unavailable"
    PTO = "pto"
    SICK = "sick"
    BLOCKED = "blocked"           # Blocked from on-call


class RotationRole(str, Enum):
    """Roles within a rotation."""
    
    PRIMARY = "primary"
    SECONDARY = "secondary"
    SHADOW = "shadow"
    ESCALATION = "escalation"


@dataclass
class UserStats:
    """Statistics for a user's on-call participation."""
    
    user_id: str
    total_shifts: int = 0
    total_hours: float = 0.0
    incidents_handled: int = 0
    escalations_received: int = 0
    escalations_made: int = 0
    last_shift_end: Optional[datetime] = None
    consecutive_shifts: int = 0
    current_month_shifts: int = 0
    current_quarter_shifts: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "total_shifts": self.total_shifts,
            "total_hours": self.total_hours,
            "incidents_handled": self.incidents_handled,
            "escalations_received": self.escalations_received,
            "escalations_made": self.escalations_made,
            "last_shift_end": self.last_shift_end.isoformat() if self.last_shift_end else None,
            "consecutive_shifts": self.consecutive_shifts,
            "current_month_shifts": self.current_month_shifts,
            "current_quarter_shifts": self.current_quarter_shifts,
        }


class UserAvailabilityWindow(BaseModel):
    """Time window defining user availability."""
    
    user_id: str
    status: UserAvailability
    start: datetime
    end: datetime
    reason: str = ""
    created_by: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def is_active_at(self, dt: datetime) -> bool:
        """Check if this availability window is active."""
        return self.start <= dt <= self.end


class RotationConstraint(BaseModel):
    """Constraint for rotation scheduling."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    
    # Constraints
    max_consecutive_shifts: int = Field(default=2)
    min_days_between_shifts: int = Field(default=7)
    max_shifts_per_month: int = Field(default=5)
    max_shifts_per_quarter: int = Field(default=15)
    
    # Preferences
    prefer_same_day_of_week: bool = False
    balance_weekend_shifts: bool = True
    respect_timezone_preferences: bool = True
    
    def check_user_eligibility(
        self,
        user_stats: UserStats,
        proposed_shift_start: datetime,
    ) -> tuple[bool, list[str]]:
        """
        Check if a user is eligible for a shift based on constraints.
        
        Returns:
            Tuple of (is_eligible, list of violation reasons)
        """
        violations = []
        
        # Check consecutive shifts
        if user_stats.consecutive_shifts >= self.max_consecutive_shifts:
            violations.append(
                f"Exceeds max consecutive shifts ({self.max_consecutive_shifts})"
            )
        
        # Check minimum days between shifts
        if user_stats.last_shift_end:
            days_since = (proposed_shift_start - user_stats.last_shift_end).days
            if days_since < self.min_days_between_shifts:
                violations.append(
                    f"Only {days_since} days since last shift "
                    f"(min: {self.min_days_between_shifts})"
                )
        
        # Check monthly limit
        if user_stats.current_month_shifts >= self.max_shifts_per_month:
            violations.append(
                f"Reached monthly limit ({self.max_shifts_per_month})"
            )
        
        # Check quarterly limit
        if user_stats.current_quarter_shifts >= self.max_shifts_per_quarter:
            violations.append(
                f"Reached quarterly limit ({self.max_shifts_per_quarter})"
            )
        
        return len(violations) == 0, violations


class RotationMember(BaseModel):
    """A member of a rotation."""
    
    user_id: str
    name: str
    email: str = ""
    role: RotationRole = RotationRole.PRIMARY
    weight: float = Field(default=1.0, ge=0.0)  # For weighted rotation
    skills: list[str] = Field(default_factory=list)
    timezone: str = Field(default="UTC")
    
    # Status
    is_active: bool = True
    availability: UserAvailability = UserAvailability.AVAILABLE
    
    # Stats
    stats: Optional[dict] = None  # UserStats as dict


class Rotation(BaseModel):
    """An on-call rotation configuration."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    team_id: str = ""
    
    # Rotation config
    rotation_type: RotationType = RotationType.ROUND_ROBIN
    frequency: RotationFrequency = RotationFrequency.WEEKLY
    custom_frequency_days: Optional[int] = None
    
    # Members
    members: list[RotationMember] = Field(default_factory=list)
    
    # State
    current_index: int = Field(default=0)
    current_oncall: Optional[str] = None
    rotation_start: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_rotation: Optional[datetime] = None
    
    # Constraints
    constraints: Optional[RotationConstraint] = None
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def add_member(
        self,
        user_id: str,
        name: str,
        email: str = "",
        role: RotationRole = RotationRole.PRIMARY,
    ) -> RotationMember:
        """Add a member to the rotation."""
        member = RotationMember(
            user_id=user_id,
            name=name,
            email=email,
            role=role,
        )
        self.members.append(member)
        self.updated_at = datetime.now(timezone.utc)
        return member
    
    def remove_member(self, user_id: str) -> bool:
        """Remove a member from the rotation."""
        original_count = len(self.members)
        self.members = [m for m in self.members if m.user_id != user_id]
        
        if len(self.members) < original_count:
            # Adjust index if needed
            if self.current_index >= len(self.members):
                self.current_index = 0
            self.updated_at = datetime.now(timezone.utc)
            return True
        return False
    
    def get_active_members(self, role: Optional[RotationRole] = None) -> list[RotationMember]:
        """Get active members, optionally filtered by role."""
        members = [m for m in self.members if m.is_active]
        if role:
            members = [m for m in members if m.role == role]
        return members
    
    def get_available_members(self, at_time: Optional[datetime] = None) -> list[RotationMember]:
        """Get members currently available for on-call."""
        return [
            m for m in self.get_active_members()
            if m.availability == UserAvailability.AVAILABLE
        ]
    
    def advance_rotation(self) -> Optional[RotationMember]:
        """Advance to the next person in rotation."""
        available = self.get_available_members()
        if not available:
            return None
        
        if self.rotation_type == RotationType.ROUND_ROBIN:
            return self._advance_round_robin(available)
        elif self.rotation_type == RotationType.WEIGHTED:
            return self._advance_weighted(available)
        elif self.rotation_type == RotationType.FAIR_DISTRIBUTION:
            return self._advance_fair(available)
        else:
            return self._advance_round_robin(available)
    
    def _advance_round_robin(self, available: list[RotationMember]) -> RotationMember:
        """Simple round-robin advancement."""
        self.current_index = (self.current_index + 1) % len(available)
        selected = available[self.current_index]
        self.current_oncall = selected.user_id
        self.last_rotation = datetime.now(timezone.utc)
        return selected
    
    def _advance_weighted(self, available: list[RotationMember]) -> RotationMember:
        """Weighted selection based on member weights."""
        import random
        
        total_weight = sum(m.weight for m in available)
        if total_weight == 0:
            return self._advance_round_robin(available)
        
        rand_val = random.uniform(0, total_weight)
        cumulative = 0.0
        
        for member in available:
            cumulative += member.weight
            if rand_val <= cumulative:
                self.current_oncall = member.user_id
                self.last_rotation = datetime.now(timezone.utc)
                return member
        
        # Fallback
        return available[0]
    
    def _advance_fair(self, available: list[RotationMember]) -> RotationMember:
        """Select member with fewest recent shifts."""
        # Sort by total shifts (ascending)
        sorted_members = sorted(
            available,
            key=lambda m: (m.stats or {}).get("total_shifts", 0)
        )
        selected = sorted_members[0]
        self.current_oncall = selected.user_id
        self.last_rotation = datetime.now(timezone.utc)
        return selected
    
    def get_rotation_schedule(self, days: int = 30) -> list[dict[str, Any]]:
        """
        Preview the rotation schedule for upcoming days.
        
        Args:
            days: Number of days to preview
            
        Returns:
            List of scheduled on-call assignments
        """
        schedule = []
        available = self.get_available_members()
        
        if not available:
            return schedule
        
        frequency_days = self._get_frequency_days()
        current_dt = datetime.now(timezone.utc)
        temp_index = self.current_index
        
        for day_offset in range(0, days, frequency_days):
            date = current_dt + timedelta(days=day_offset)
            member = available[temp_index % len(available)]
            
            schedule.append({
                "start": date.isoformat(),
                "end": (date + timedelta(days=frequency_days)).isoformat(),
                "user_id": member.user_id,
                "user_name": member.name,
                "role": member.role.value,
            })
            
            temp_index += 1
        
        return schedule
    
    def _get_frequency_days(self) -> int:
        """Get rotation frequency in days."""
        if self.frequency == RotationFrequency.DAILY:
            return 1
        elif self.frequency == RotationFrequency.WEEKLY:
            return 7
        elif self.frequency == RotationFrequency.BIWEEKLY:
            return 14
        elif self.frequency == RotationFrequency.MONTHLY:
            return 30
        elif self.frequency == RotationFrequency.CUSTOM and self.custom_frequency_days:
            return self.custom_frequency_days
        return 7


class RotationManager:
    """Manager for on-call rotations."""
    
    def __init__(self):
        """Initialize the rotation manager."""
        self._rotations: dict[str, Rotation] = {}
        self._user_stats: dict[str, UserStats] = {}
        self._availability: dict[str, list[UserAvailabilityWindow]] = defaultdict(list)
    
    def create_rotation(
        self,
        name: str,
        rotation_type: RotationType = RotationType.ROUND_ROBIN,
        frequency: RotationFrequency = RotationFrequency.WEEKLY,
        team_id: str = "",
    ) -> Rotation:
        """Create a new rotation."""
        rotation = Rotation(
            name=name,
            rotation_type=rotation_type,
            frequency=frequency,
            team_id=team_id,
        )
        self._rotations[rotation.id] = rotation
        return rotation
    
    def get_rotation(self, rotation_id: str) -> Optional[Rotation]:
        """Get a rotation by ID."""
        return self._rotations.get(rotation_id)
    
    def get_rotations_for_team(self, team_id: str) -> list[Rotation]:
        """Get all rotations for a team."""
        return [r for r in self._rotations.values() if r.team_id == team_id]
    
    def get_rotations_for_user(self, user_id: str) -> list[Rotation]:
        """Get all rotations a user is part of."""
        return [
            r for r in self._rotations.values()
            if any(m.user_id == user_id for m in r.members)
        ]
    
    def set_user_availability(
        self,
        user_id: str,
        status: UserAvailability,
        start: datetime,
        end: datetime,
        reason: str = "",
    ) -> UserAvailabilityWindow:
        """Set user availability for a time period."""
        window = UserAvailabilityWindow(
            user_id=user_id,
            status=status,
            start=start,
            end=end,
            reason=reason,
        )
        self._availability[user_id].append(window)
        
        # Update member status in all rotations
        for rotation in self.get_rotations_for_user(user_id):
            for member in rotation.members:
                if member.user_id == user_id:
                    member.availability = status
        
        return window
    
    def get_user_availability(
        self,
        user_id: str,
        at_time: Optional[datetime] = None,
    ) -> UserAvailability:
        """Get user's availability at a specific time."""
        at_time = at_time or datetime.now(timezone.utc)
        
        for window in self._availability.get(user_id, []):
            if window.is_active_at(at_time):
                return window.status
        
        return UserAvailability.AVAILABLE
    
    def request_pto(
        self,
        user_id: str,
        start: datetime,
        end: datetime,
        reason: str = "",
    ) -> dict[str, Any]:
        """
        Request PTO for a user, checking for coverage.
        
        Args:
            user_id: User requesting PTO
            start: PTO start
            end: PTO end
            reason: Reason for PTO
            
        Returns:
            PTO request status with coverage check
        """
        # Check if user is on-call during this period
        conflicts = []
        
        for rotation in self.get_rotations_for_user(user_id):
            schedule = rotation.get_rotation_schedule(
                days=max(1, (end - start).days + 14)
            )
            
            for shift in schedule:
                shift_start = datetime.fromisoformat(shift["start"])
                shift_end = datetime.fromisoformat(shift["end"])
                
                if shift["user_id"] == user_id:
                    if shift_start <= end and shift_end >= start:
                        conflicts.append({
                            "rotation_id": rotation.id,
                            "rotation_name": rotation.name,
                            "shift_start": shift_start.isoformat(),
                            "shift_end": shift_end.isoformat(),
                        })
        
        # Set availability window
        self.set_user_availability(
            user_id=user_id,
            status=UserAvailability.PTO,
            start=start,
            end=end,
            reason=reason,
        )
        
        return {
            "user_id": user_id,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "status": "approved" if not conflicts else "needs_coverage",
            "conflicts": conflicts,
            "coverage_needed": len(conflicts) > 0,
        }
    
    def find_coverage(
        self,
        rotation_id: str,
        shift_start: datetime,
        shift_end: datetime,
        exclude_users: list[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Find available users who can cover a shift.
        
        Args:
            rotation_id: Rotation to find coverage for
            shift_start: Shift start time
            shift_end: Shift end time
            exclude_users: Users to exclude
            
        Returns:
            List of available users with fairness scores
        """
        rotation = self.get_rotation(rotation_id)
        if not rotation:
            return []
        
        exclude = set(exclude_users or [])
        candidates = []
        
        for member in rotation.members:
            if member.user_id in exclude:
                continue
            
            if not member.is_active:
                continue
            
            # Check availability
            availability = self.get_user_availability(member.user_id, shift_start)
            if availability != UserAvailability.AVAILABLE:
                continue
            
            # Check constraints
            stats = self._get_or_create_stats(member.user_id)
            is_eligible, violations = (
                rotation.constraints.check_user_eligibility(stats, shift_start)
                if rotation.constraints else (True, [])
            )
            
            candidates.append({
                "user_id": member.user_id,
                "user_name": member.name,
                "is_eligible": is_eligible,
                "violations": violations,
                "fairness_score": self._calculate_fairness_score(stats),
                "stats": stats.to_dict(),
            })
        
        # Sort by fairness score (lower = more fair to assign)
        candidates.sort(key=lambda c: c["fairness_score"])
        
        return candidates
    
    def _get_or_create_stats(self, user_id: str) -> UserStats:
        """Get or create stats for a user."""
        if user_id not in self._user_stats:
            self._user_stats[user_id] = UserStats(user_id=user_id)
        return self._user_stats[user_id]
    
    def _calculate_fairness_score(self, stats: UserStats) -> float:
        """
        Calculate fairness score for a user.
        Lower score = more fair to assign next.
        """
        score = 0.0
        
        # Weight total shifts
        score += stats.total_shifts * 2.0
        
        # Weight recent shifts more heavily
        score += stats.current_month_shifts * 5.0
        
        # Consecutive shifts penalty
        score += stats.consecutive_shifts * 10.0
        
        # Recent shift recency
        if stats.last_shift_end:
            days_since = (datetime.now(timezone.utc) - stats.last_shift_end).days
            # Inverse: more recent = higher score = less likely to assign
            if days_since < 7:
                score += (7 - days_since) * 3.0
        
        return score
    
    def record_shift_completion(
        self,
        user_id: str,
        rotation_id: str,
        shift_end: datetime,
        incidents_handled: int = 0,
        escalations_made: int = 0,
        escalations_received: int = 0,
    ) -> UserStats:
        """Record completion of a shift for fairness tracking."""
        stats = self._get_or_create_stats(user_id)
        
        stats.total_shifts += 1
        stats.last_shift_end = shift_end
        stats.incidents_handled += incidents_handled
        stats.escalations_made += escalations_made
        stats.escalations_received += escalations_received
        
        # Update monthly/quarterly counts
        now = datetime.now(timezone.utc)
        if shift_end.month == now.month and shift_end.year == now.year:
            stats.current_month_shifts += 1
        
        # Simplified quarter calculation
        shift_quarter = (shift_end.month - 1) // 3 + 1
        current_quarter = (now.month - 1) // 3 + 1
        if shift_quarter == current_quarter and shift_end.year == now.year:
            stats.current_quarter_shifts += 1
        
        return stats
    
    def get_fairness_report(self, rotation_id: str) -> dict[str, Any]:
        """Generate a fairness report for a rotation."""
        rotation = self.get_rotation(rotation_id)
        if not rotation:
            return {"error": "Rotation not found"}
        
        report = {
            "rotation_id": rotation_id,
            "rotation_name": rotation.name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "members": [],
            "summary": {},
        }
        
        total_shifts = 0
        shifts_list = []
        
        for member in rotation.members:
            stats = self._get_or_create_stats(member.user_id)
            total_shifts += stats.total_shifts
            shifts_list.append(stats.total_shifts)
            
            report["members"].append({
                "user_id": member.user_id,
                "name": member.name,
                **stats.to_dict(),
            })
        
        # Calculate fairness metrics
        if shifts_list and len(shifts_list) > 1:
            avg_shifts = sum(shifts_list) / len(shifts_list)
            variance = sum((x - avg_shifts) ** 2 for x in shifts_list) / len(shifts_list)
            
            report["summary"] = {
                "total_members": len(rotation.members),
                "total_shifts": total_shifts,
                "average_shifts_per_member": round(avg_shifts, 2),
                "variance": round(variance, 2),
                "is_fair": variance < (avg_shifts * 0.25) if avg_shifts > 0 else True,
            }
        
        return report


# Convenience functions
def create_simple_rotation(
    name: str,
    members: list[dict[str, str]],
    frequency: RotationFrequency = RotationFrequency.WEEKLY,
) -> Rotation:
    """
    Create a simple round-robin rotation.
    
    Args:
        name: Rotation name
        members: List of dicts with user_id, name, email
        frequency: How often to rotate
        
    Returns:
        Configured rotation
    """
    rotation = Rotation(
        name=name,
        rotation_type=RotationType.ROUND_ROBIN,
        frequency=frequency,
    )
    
    for member in members:
        rotation.add_member(
            user_id=member["user_id"],
            name=member["name"],
            email=member.get("email", ""),
        )
    
    return rotation


def create_tiered_rotation(
    name: str,
    primary_members: list[dict[str, str]],
    secondary_members: list[dict[str, str]],
    frequency: RotationFrequency = RotationFrequency.WEEKLY,
) -> Rotation:
    """
    Create a tiered rotation with primary and secondary members.
    
    Args:
        name: Rotation name
        primary_members: Primary on-call members
        secondary_members: Secondary/backup members
        frequency: How often to rotate
        
    Returns:
        Configured rotation
    """
    rotation = Rotation(
        name=name,
        rotation_type=RotationType.ROUND_ROBIN,
        frequency=frequency,
    )
    
    for member in primary_members:
        rotation.add_member(
            user_id=member["user_id"],
            name=member["name"],
            email=member.get("email", ""),
            role=RotationRole.PRIMARY,
        )
    
    for member in secondary_members:
        rotation.add_member(
            user_id=member["user_id"],
            name=member["name"],
            email=member.get("email", ""),
            role=RotationRole.SECONDARY,
        )
    
    return rotation
