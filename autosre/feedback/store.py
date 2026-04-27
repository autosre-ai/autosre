"""
Feedback Store - Simple feedback storage for CLI.
"""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class Feedback(BaseModel):
    """Simple feedback entry."""
    incident_id: str
    rating: str = Field(..., description="correct, incorrect, or partial")
    actual_root_cause: Optional[str] = None
    notes: Optional[str] = None
    submitted_at: datetime = Field(default_factory=utcnow)


class FeedbackStore:
    """
    Simple SQLite-backed feedback store for CLI use.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize the store."""
        if db_path is None:
            db_path = str(Path.home() / ".autosre" / "feedback.db")
        
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS simple_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id TEXT NOT NULL,
                    rating TEXT NOT NULL,
                    actual_root_cause TEXT,
                    notes TEXT,
                    submitted_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_simple_feedback_incident 
                ON simple_feedback(incident_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_simple_feedback_rating 
                ON simple_feedback(rating)
            """)
    
    def save(self, feedback: Feedback) -> None:
        """Save a feedback entry."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO simple_feedback
                (incident_id, rating, actual_root_cause, notes, submitted_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                feedback.incident_id,
                feedback.rating,
                feedback.actual_root_cause,
                feedback.notes,
                feedback.submitted_at.isoformat(),
            ))
    
    def list_feedback(
        self,
        limit: int = 20,
        rating: Optional[str] = None
    ) -> list[Feedback]:
        """List feedback entries."""
        query = "SELECT * FROM simple_feedback"
        params = []
        
        if rating:
            query += " WHERE rating = ?"
            params.append(rating)
        
        query += " ORDER BY submitted_at DESC LIMIT ?"
        params.append(limit)
        
        entries = []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            for row in conn.execute(query, params):
                entries.append(Feedback(
                    incident_id=row["incident_id"],
                    rating=row["rating"],
                    actual_root_cause=row["actual_root_cause"],
                    notes=row["notes"],
                    submitted_at=datetime.fromisoformat(row["submitted_at"]),
                ))
        
        return entries
    
    def get_stats(self, days: int = 30) -> dict:
        """Get feedback statistics."""
        cutoff = (utcnow() - timedelta(days=days)).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM simple_feedback WHERE submitted_at > ?",
                (cutoff,)
            ).fetchone()[0]
            
            correct = conn.execute(
                "SELECT COUNT(*) FROM simple_feedback WHERE submitted_at > ? AND rating = 'correct'",
                (cutoff,)
            ).fetchone()[0]
            
            incorrect = conn.execute(
                "SELECT COUNT(*) FROM simple_feedback WHERE submitted_at > ? AND rating = 'incorrect'",
                (cutoff,)
            ).fetchone()[0]
            
            partial = conn.execute(
                "SELECT COUNT(*) FROM simple_feedback WHERE submitted_at > ? AND rating = 'partial'",
                (cutoff,)
            ).fetchone()[0]
            
            # Previous period for trend
            prev_cutoff = (utcnow() - timedelta(days=days * 2)).isoformat()
            prev_total = conn.execute(
                "SELECT COUNT(*) FROM simple_feedback WHERE submitted_at > ? AND submitted_at <= ?",
                (prev_cutoff, cutoff)
            ).fetchone()[0]
            
            prev_correct = conn.execute(
                "SELECT COUNT(*) FROM simple_feedback WHERE submitted_at > ? AND submitted_at <= ? AND rating = 'correct'",
                (prev_cutoff, cutoff)
            ).fetchone()[0]
        
        current_accuracy = (correct + partial * 0.5) / total if total > 0 else 0
        prev_accuracy = (prev_correct + 0) / prev_total if prev_total > 0 else 0
        trend = (current_accuracy - prev_accuracy) * 100 if prev_total > 0 else None
        
        return {
            "total": total,
            "correct": correct,
            "incorrect": incorrect,
            "partial": partial,
            "accuracy": current_accuracy,
            "trend": trend,
        }
