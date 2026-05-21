"""
On-Call Load Tracker for AutoSRE.

Tracks incident load per on-call shift to prevent burnout and ensure quality response.
Key principle: Max 2 incidents per 12-hour shift.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Any
from enum import Enum
import json


# Configuration constants
MAX_INCIDENTS_PER_SHIFT = 2
SHIFT_HOURS = 12
WARNING_THRESHOLD = 1  # Alert when this many incidents in shift


class LoadStatus(Enum):
    """On-call load status levels."""
    NORMAL = "normal"           # Under threshold
    ELEVATED = "elevated"       # At warning threshold
    OVERLOADED = "overloaded"   # At or above max


@dataclass
class ShiftIncident:
    """Record of an incident during a shift."""
    
    incident_id: str
    title: str
    severity: str
    started_at: datetime
    resolved_at: Optional[datetime] = None
    time_to_resolve_minutes: Optional[int] = None
    required_escalation: bool = False
    notes: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "incident_id": self.incident_id,
            "title": self.title,
            "severity": self.severity,
            "started_at": self.started_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "time_to_resolve_minutes": self.time_to_resolve_minutes,
            "required_escalation": self.required_escalation,
            "notes": self.notes,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ShiftIncident":
        """Create from dictionary."""
        return cls(
            incident_id=data["incident_id"],
            title=data["title"],
            severity=data["severity"],
            started_at=datetime.fromisoformat(data["started_at"]),
            resolved_at=datetime.fromisoformat(data["resolved_at"]) if data.get("resolved_at") else None,
            time_to_resolve_minutes=data.get("time_to_resolve_minutes"),
            required_escalation=data.get("required_escalation", False),
            notes=data.get("notes", ""),
        )


@dataclass
class ShiftStatus:
    """Status of the current on-call shift."""
    
    on_call_user: str
    shift_start: datetime
    shift_end: datetime
    incidents: list[ShiftIncident] = field(default_factory=list)
    load_status: LoadStatus = LoadStatus.NORMAL
    escalation_suggested: bool = False
    escalation_reason: Optional[str] = None
    
    @property
    def incident_count(self) -> int:
        """Number of incidents in this shift."""
        return len(self.incidents)
    
    @property
    def remaining_capacity(self) -> int:
        """How many more incidents can be handled."""
        return max(0, MAX_INCIDENTS_PER_SHIFT - self.incident_count)
    
    @property
    def hours_remaining(self) -> float:
        """Hours remaining in shift."""
        remaining = (self.shift_end - datetime.utcnow()).total_seconds() / 3600
        return max(0, remaining)
    
    @property
    def is_overloaded(self) -> bool:
        """Check if shift is overloaded."""
        return self.incident_count >= MAX_INCIDENTS_PER_SHIFT
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "on_call_user": self.on_call_user,
            "shift_start": self.shift_start.isoformat(),
            "shift_end": self.shift_end.isoformat(),
            "incidents": [i.to_dict() for i in self.incidents],
            "incident_count": self.incident_count,
            "remaining_capacity": self.remaining_capacity,
            "hours_remaining": self.hours_remaining,
            "load_status": self.load_status.value,
            "is_overloaded": self.is_overloaded,
            "escalation_suggested": self.escalation_suggested,
            "escalation_reason": self.escalation_reason,
        }


class OnCallLoadTracker:
    """
    Tracks on-call load to prevent burnout and ensure quality response.
    
    Key principles:
    - Max 2 incidents per 12-hour shift
    - Alert when approaching overload
    - Suggest escalation when overloaded
    """
    
    def __init__(
        self,
        max_incidents: int = MAX_INCIDENTS_PER_SHIFT,
        shift_hours: int = SHIFT_HOURS,
        warning_threshold: int = WARNING_THRESHOLD,
    ):
        """
        Initialize tracker.
        
        Args:
            max_incidents: Maximum incidents per shift
            shift_hours: Length of a shift in hours
            warning_threshold: Alert when this many incidents
        """
        self.max_incidents = max_incidents
        self.shift_hours = shift_hours
        self.warning_threshold = warning_threshold
        
        # Active shifts by user
        self._shifts: dict[str, ShiftStatus] = {}
    
    def start_shift(
        self,
        user: str,
        start_time: Optional[datetime] = None,
    ) -> ShiftStatus:
        """
        Start a new on-call shift.
        
        Args:
            user: On-call user identifier
            start_time: Shift start time (defaults to now)
            
        Returns:
            New shift status
        """
        start = start_time or datetime.utcnow()
        end = start + timedelta(hours=self.shift_hours)
        
        shift = ShiftStatus(
            on_call_user=user,
            shift_start=start,
            shift_end=end,
        )
        
        self._shifts[user] = shift
        return shift
    
    def get_shift(self, user: str) -> Optional[ShiftStatus]:
        """
        Get current shift for a user.
        
        Args:
            user: On-call user identifier
            
        Returns:
            Shift status or None
        """
        shift = self._shifts.get(user)
        
        if shift and datetime.utcnow() > shift.shift_end:
            # Shift has ended
            del self._shifts[user]
            return None
        
        return shift
    
    def record_incident(
        self,
        user: str,
        incident_id: str,
        title: str,
        severity: str,
        started_at: Optional[datetime] = None,
    ) -> tuple[ShiftStatus, bool]:
        """
        Record an incident for an on-call user.
        
        Args:
            user: On-call user
            incident_id: Unique incident identifier
            title: Incident title
            severity: Incident severity
            started_at: When incident started
            
        Returns:
            Tuple of (updated shift status, should escalate)
        """
        # Get or create shift
        shift = self.get_shift(user)
        if not shift:
            shift = self.start_shift(user, started_at)
        
        # Record incident
        incident = ShiftIncident(
            incident_id=incident_id,
            title=title,
            severity=severity,
            started_at=started_at or datetime.utcnow(),
        )
        shift.incidents.append(incident)
        
        # Update load status
        self._update_load_status(shift)
        
        return shift, shift.escalation_suggested
    
    def resolve_incident(
        self,
        user: str,
        incident_id: str,
        notes: str = "",
    ) -> Optional[ShiftStatus]:
        """
        Mark an incident as resolved.
        
        Args:
            user: On-call user
            incident_id: Incident to resolve
            notes: Resolution notes
            
        Returns:
            Updated shift status or None
        """
        shift = self.get_shift(user)
        if not shift:
            return None
        
        for incident in shift.incidents:
            if incident.incident_id == incident_id:
                incident.resolved_at = datetime.utcnow()
                incident.notes = notes
                
                # Calculate TTR
                if incident.started_at:
                    delta = incident.resolved_at - incident.started_at
                    incident.time_to_resolve_minutes = int(delta.total_seconds() / 60)
                
                break
        
        return shift
    
    def check_capacity(self, user: str) -> dict[str, Any]:
        """
        Check if user has capacity for more incidents.
        
        Args:
            user: On-call user
            
        Returns:
            Capacity assessment
        """
        shift = self.get_shift(user)
        
        if not shift:
            return {
                "has_capacity": True,
                "reason": "No active shift",
                "remaining": self.max_incidents,
            }
        
        return {
            "has_capacity": shift.remaining_capacity > 0,
            "reason": self._capacity_reason(shift),
            "remaining": shift.remaining_capacity,
            "load_status": shift.load_status.value,
            "escalation_suggested": shift.escalation_suggested,
        }
    
    def suggest_escalation(self, user: str) -> Optional[dict[str, Any]]:
        """
        Get escalation suggestion if needed.
        
        Args:
            user: On-call user
            
        Returns:
            Escalation suggestion or None
        """
        shift = self.get_shift(user)
        if not shift or not shift.escalation_suggested:
            return None
        
        return {
            "should_escalate": True,
            "reason": shift.escalation_reason,
            "current_incidents": shift.incident_count,
            "max_incidents": self.max_incidents,
            "hours_remaining": shift.hours_remaining,
            "suggested_actions": self._escalation_actions(shift),
        }
    
    def _update_load_status(self, shift: ShiftStatus) -> None:
        """Update load status based on incident count."""
        count = shift.incident_count
        
        if count >= self.max_incidents:
            shift.load_status = LoadStatus.OVERLOADED
            shift.escalation_suggested = True
            shift.escalation_reason = (
                f"Shift has {count} incidents (max {self.max_incidents}). "
                "Quality of response may be degraded. Consider escalation."
            )
        elif count >= self.warning_threshold:
            shift.load_status = LoadStatus.ELEVATED
            shift.escalation_suggested = False
            shift.escalation_reason = None
        else:
            shift.load_status = LoadStatus.NORMAL
            shift.escalation_suggested = False
            shift.escalation_reason = None
    
    def _capacity_reason(self, shift: ShiftStatus) -> str:
        """Generate capacity reason message."""
        if shift.is_overloaded:
            return (
                f"Overloaded: {shift.incident_count} incidents in shift "
                f"(max {self.max_incidents}). Escalation recommended."
            )
        elif shift.load_status == LoadStatus.ELEVATED:
            return (
                f"Elevated load: {shift.incident_count}/{self.max_incidents} incidents. "
                f"{shift.remaining_capacity} more can be handled."
            )
        else:
            return f"Normal: {shift.remaining_capacity} incidents can be handled."
    
    def _escalation_actions(self, shift: ShiftStatus) -> list[str]:
        """Get suggested escalation actions."""
        actions = []
        
        if shift.is_overloaded:
            actions.append("Page secondary on-call for assistance")
            actions.append("Notify team lead of high incident volume")
            
            # Check for unresolved incidents
            unresolved = [i for i in shift.incidents if not i.resolved_at]
            if len(unresolved) > 1:
                actions.append(
                    f"Prioritize {len(unresolved)} active incidents by severity"
                )
            
            # Check for long-running incidents
            for incident in unresolved:
                age = (datetime.utcnow() - incident.started_at).total_seconds() / 60
                if age > 30:
                    actions.append(
                        f"Incident '{incident.incident_id}' open for {int(age)}min - "
                        "consider bringing in specialist"
                    )
        
        return actions
    
    def get_shift_summary(self, user: str) -> Optional[dict[str, Any]]:
        """
        Get summary of a user's shift.
        
        Args:
            user: On-call user
            
        Returns:
            Shift summary or None
        """
        shift = self.get_shift(user)
        if not shift:
            return None
        
        resolved = [i for i in shift.incidents if i.resolved_at]
        unresolved = [i for i in shift.incidents if not i.resolved_at]
        
        avg_ttr = None
        if resolved:
            ttrs = [i.time_to_resolve_minutes for i in resolved if i.time_to_resolve_minutes]
            if ttrs:
                avg_ttr = sum(ttrs) / len(ttrs)
        
        return {
            "user": user,
            "shift_start": shift.shift_start.isoformat(),
            "shift_end": shift.shift_end.isoformat(),
            "hours_remaining": shift.hours_remaining,
            "total_incidents": shift.incident_count,
            "resolved_incidents": len(resolved),
            "active_incidents": len(unresolved),
            "average_ttr_minutes": avg_ttr,
            "load_status": shift.load_status.value,
            "remaining_capacity": shift.remaining_capacity,
            "escalation_suggested": shift.escalation_suggested,
        }
    
    def export_shift(self, user: str) -> Optional[str]:
        """Export shift data as JSON."""
        shift = self.get_shift(user)
        if not shift:
            return None
        return json.dumps(shift.to_dict(), indent=2)
