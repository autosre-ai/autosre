"""
Feedback Tracker - Track incident outcomes and feedback.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from enum import Enum

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class FeedbackType(str, Enum):
    """Types of feedback."""
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    CORRECTION = "correction"
    COMMENT = "comment"


class OutcomeType(str, Enum):
    """Types of incident outcomes."""
    RESOLVED_BY_AGENT = "resolved_by_agent"
    RESOLVED_BY_HUMAN = "resolved_by_human"
    AGENT_HELPED = "agent_helped"
    AGENT_WRONG = "agent_wrong"
    FALSE_POSITIVE = "false_positive"
    ONGOING = "ongoing"


class Feedback(BaseModel):
    """Feedback on agent analysis/action."""
    id: str
    incident_id: str
    feedback_type: FeedbackType
    
    # Details
    rating: Optional[int] = Field(None, ge=1, le=5, description="1-5 rating")
    comment: Optional[str] = None
    
    # Correction
    correction: Optional[str] = Field(None, description="What should the agent have said/done")
    
    # Context
    agent_analysis: Optional[str] = None
    agent_action: Optional[str] = None
    
    # Metadata
    submitted_by: str = Field(default="unknown")
    submitted_at: datetime = Field(default_factory=utcnow)


class IncidentOutcome(BaseModel):
    """Outcome of an incident."""
    incident_id: str
    outcome: OutcomeType
    
    # Resolution details
    root_cause_correct: bool = Field(default=False)
    runbook_helpful: bool = Field(default=False)
    action_effective: bool = Field(default=False)
    
    # Timing
    time_to_resolution_seconds: Optional[float] = None
    agent_time_saved_seconds: Optional[float] = None
    
    # Human involvement
    human_override: bool = Field(default=False)
    escalation_needed: bool = Field(default=False)
    
    # Notes
    notes: Optional[str] = None
    lessons_learned: Optional[str] = None
    
    # Metadata
    recorded_at: datetime = Field(default_factory=utcnow)
    recorded_by: str = Field(default="unknown")


class FeedbackTracker:
    """
    Track feedback and outcomes for continuous learning.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize feedback tracker.
        
        Args:
            db_path: Path to feedback database
        """
        if db_path is None:
            db_path = str(Path.home() / ".autosre" / "feedback.db")
        
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize feedback database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    feedback_type TEXT NOT NULL,
                    rating INTEGER,
                    comment TEXT,
                    correction TEXT,
                    agent_analysis TEXT,
                    agent_action TEXT,
                    submitted_by TEXT NOT NULL,
                    submitted_at TEXT NOT NULL
                );
                
                CREATE TABLE IF NOT EXISTS outcomes (
                    incident_id TEXT PRIMARY KEY,
                    outcome TEXT NOT NULL,
                    root_cause_correct INTEGER,
                    runbook_helpful INTEGER,
                    action_effective INTEGER,
                    time_to_resolution_seconds REAL,
                    agent_time_saved_seconds REAL,
                    human_override INTEGER,
                    escalation_needed INTEGER,
                    notes TEXT,
                    lessons_learned TEXT,
                    recorded_at TEXT NOT NULL,
                    recorded_by TEXT NOT NULL
                );
                
                CREATE INDEX IF NOT EXISTS idx_feedback_incident ON feedback(incident_id);
                CREATE INDEX IF NOT EXISTS idx_outcomes_outcome ON outcomes(outcome);
            """)
    
    def submit_feedback(self, feedback: Feedback) -> None:
        """Submit feedback for an incident."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO feedback
                (id, incident_id, feedback_type, rating, comment, correction,
                 agent_analysis, agent_action, submitted_by, submitted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                feedback.id,
                feedback.incident_id,
                feedback.feedback_type.value,
                feedback.rating,
                feedback.comment,
                feedback.correction,
                feedback.agent_analysis,
                feedback.agent_action,
                feedback.submitted_by,
                feedback.submitted_at.isoformat(),
            ))
    
    def record_outcome(self, outcome: IncidentOutcome) -> None:
        """Record the outcome of an incident."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO outcomes
                (incident_id, outcome, root_cause_correct, runbook_helpful,
                 action_effective, time_to_resolution_seconds, agent_time_saved_seconds,
                 human_override, escalation_needed, notes, lessons_learned,
                 recorded_at, recorded_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                outcome.incident_id,
                outcome.outcome.value,
                1 if outcome.root_cause_correct else 0,
                1 if outcome.runbook_helpful else 0,
                1 if outcome.action_effective else 0,
                outcome.time_to_resolution_seconds,
                outcome.agent_time_saved_seconds,
                1 if outcome.human_override else 0,
                1 if outcome.escalation_needed else 0,
                outcome.notes,
                outcome.lessons_learned,
                outcome.recorded_at.isoformat(),
                outcome.recorded_by,
            ))
    
    def get_feedback(self, incident_id: str) -> list[Feedback]:
        """Get all feedback for an incident."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM feedback WHERE incident_id = ?",
                (incident_id,)
            ).fetchall()
            
            return [
                Feedback(
                    id=row["id"],
                    incident_id=row["incident_id"],
                    feedback_type=FeedbackType(row["feedback_type"]),
                    rating=row["rating"],
                    comment=row["comment"],
                    correction=row["correction"],
                    agent_analysis=row["agent_analysis"],
                    agent_action=row["agent_action"],
                    submitted_by=row["submitted_by"],
                    submitted_at=datetime.fromisoformat(row["submitted_at"]),
                )
                for row in rows
            ]
    
    def get_outcome(self, incident_id: str) -> Optional[IncidentOutcome]:
        """Get outcome for an incident."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM outcomes WHERE incident_id = ?",
                (incident_id,)
            ).fetchone()
            
            if not row:
                return None
            
            return IncidentOutcome(
                incident_id=row["incident_id"],
                outcome=OutcomeType(row["outcome"]),
                root_cause_correct=bool(row["root_cause_correct"]),
                runbook_helpful=bool(row["runbook_helpful"]),
                action_effective=bool(row["action_effective"]),
                time_to_resolution_seconds=row["time_to_resolution_seconds"],
                agent_time_saved_seconds=row["agent_time_saved_seconds"],
                human_override=bool(row["human_override"]),
                escalation_needed=bool(row["escalation_needed"]),
                notes=row["notes"],
                lessons_learned=row["lessons_learned"],
                recorded_at=datetime.fromisoformat(row["recorded_at"]),
                recorded_by=row["recorded_by"],
            )
    
    def get_summary(self) -> dict:
        """Get summary statistics."""
        with sqlite3.connect(self.db_path) as conn:
            # Feedback stats
            feedback_count = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
            thumbs_up = conn.execute(
                "SELECT COUNT(*) FROM feedback WHERE feedback_type = ?",
                (FeedbackType.THUMBS_UP.value,)
            ).fetchone()[0]
            thumbs_down = conn.execute(
                "SELECT COUNT(*) FROM feedback WHERE feedback_type = ?",
                (FeedbackType.THUMBS_DOWN.value,)
            ).fetchone()[0]
            corrections = conn.execute(
                "SELECT COUNT(*) FROM feedback WHERE feedback_type = ?",
                (FeedbackType.CORRECTION.value,)
            ).fetchone()[0]
            
            # Outcome stats
            outcomes_count = conn.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0]
            
            root_cause_correct = conn.execute(
                "SELECT COUNT(*) FROM outcomes WHERE root_cause_correct = 1"
            ).fetchone()[0]
            
            agent_helped = conn.execute(
                "SELECT COUNT(*) FROM outcomes WHERE outcome IN (?, ?)",
                (OutcomeType.RESOLVED_BY_AGENT.value, OutcomeType.AGENT_HELPED.value)
            ).fetchone()[0]
            
            human_overrides = conn.execute(
                "SELECT COUNT(*) FROM outcomes WHERE human_override = 1"
            ).fetchone()[0]
            
            avg_time_saved = conn.execute(
                "SELECT AVG(agent_time_saved_seconds) FROM outcomes WHERE agent_time_saved_seconds IS NOT NULL"
            ).fetchone()[0]
        
        return {
            "feedback": {
                "total": feedback_count,
                "thumbs_up": thumbs_up,
                "thumbs_down": thumbs_down,
                "corrections": corrections,
                "approval_rate": thumbs_up / (thumbs_up + thumbs_down) if (thumbs_up + thumbs_down) > 0 else 0,
            },
            "outcomes": {
                "total": outcomes_count,
                "root_cause_accuracy": root_cause_correct / outcomes_count if outcomes_count > 0 else 0,
                "agent_helpful_rate": agent_helped / outcomes_count if outcomes_count > 0 else 0,
                "human_override_rate": human_overrides / outcomes_count if outcomes_count > 0 else 0,
                "avg_time_saved_seconds": avg_time_saved or 0,
            },
        }
