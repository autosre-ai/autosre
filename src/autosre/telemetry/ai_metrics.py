"""
AI Metrics Tracker

Track every AI investigation for accuracy, reliability, and improvement.
Implements "Build telemetry for AI itself" principle.

Metrics tracked:
- Context documents used per investigation
- Confidence reported vs actual outcome
- Recommendations made vs human acceptance
- Accuracy over time (was AI right?)
"""

import json
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional
from enum import Enum

from prometheus_client import Counter, Gauge, Histogram, Summary


# =============================================================================
# Prometheus Metrics for AI Performance
# =============================================================================

AI_RECOMMENDATIONS_TOTAL = Counter(
    'autosre_ai_recommendation_total',
    'Total AI recommendations made',
    ['confidence_bucket', 'category', 'accepted']
)

AI_ACCURACY_GAUGE = Gauge(
    'autosre_ai_accuracy_rate',
    'Current AI accuracy rate (7-day rolling)',
    ['severity']
)

AI_FALSE_POSITIVE_RATE = Gauge(
    'autosre_ai_false_positive_rate',
    'Current false positive rate',
    ['category']
)

AI_CONFIDENCE_VS_ACCURACY = Histogram(
    'autosre_ai_confidence_calibration',
    'Confidence scores bucketed by actual outcome (1=correct, 0=incorrect)',
    ['outcome'],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

AI_INVESTIGATION_LATENCY = Histogram(
    'autosre_ai_investigation_duration_seconds',
    'Time taken for AI investigation',
    buckets=[1, 5, 10, 30, 60, 120, 300]
)

AI_EVIDENCE_COUNT = Histogram(
    'autosre_ai_evidence_count',
    'Number of evidence pieces gathered per investigation',
    buckets=[1, 2, 3, 5, 8, 13, 21]
)

AI_CONTEXT_DOCUMENTS = Counter(
    'autosre_ai_context_documents_total',
    'Context documents used in investigations',
    ['document_type']
)


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class OutcomeStatus(str, Enum):
    """Outcome of an AI recommendation."""
    PENDING = "pending"       # Not yet determined
    CORRECT = "correct"       # AI was right
    INCORRECT = "incorrect"   # AI was wrong
    PARTIAL = "partial"       # Partially correct
    UNKNOWN = "unknown"       # Cannot determine


@dataclass
class InvestigationRecord:
    """
    Record of a single AI investigation for telemetry.
    """
    # Identity
    investigation_id: str
    alert_name: str
    timestamp: datetime = field(default_factory=utcnow)
    
    # Input context
    context_documents: list[str] = field(default_factory=list)
    evidence_count: int = 0
    
    # AI output
    confidence_reported: float = 0.0
    primary_hypothesis: str = ""
    recommended_action: Optional[str] = None
    category: str = "unknown"
    
    # Human feedback
    accepted_by_human: Optional[bool] = None
    human_feedback: str = ""
    human_override_reason: str = ""
    
    # Outcome
    outcome_correct: Optional[bool] = None
    outcome_status: OutcomeStatus = OutcomeStatus.PENDING
    actual_root_cause: str = ""
    
    # Timing
    duration_seconds: float = 0.0
    
    # Severity
    severity: str = "medium"  # low, medium, high, critical
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "investigation_id": self.investigation_id,
            "alert_name": self.alert_name,
            "timestamp": self.timestamp.isoformat(),
            "context_documents": self.context_documents,
            "evidence_count": self.evidence_count,
            "confidence_reported": self.confidence_reported,
            "primary_hypothesis": self.primary_hypothesis,
            "recommended_action": self.recommended_action,
            "category": self.category,
            "accepted_by_human": self.accepted_by_human,
            "human_feedback": self.human_feedback,
            "human_override_reason": self.human_override_reason,
            "outcome_correct": self.outcome_correct,
            "outcome_status": self.outcome_status.value,
            "actual_root_cause": self.actual_root_cause,
            "duration_seconds": self.duration_seconds,
            "severity": self.severity,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "InvestigationRecord":
        """Create from dictionary."""
        data = data.copy()
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        if isinstance(data.get("outcome_status"), str):
            data["outcome_status"] = OutcomeStatus(data["outcome_status"])
        return cls(**data)


class AIMetricsTracker:
    """
    Track AI investigation metrics for reliability monitoring.
    
    Stores data in SQLite for persistence and fast queries.
    Exposes Prometheus metrics for alerting/dashboarding.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize the metrics tracker."""
        self.db_path = db_path or Path.home() / ".autosre" / "ai_metrics.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()
    
    def _init_db(self):
        """Initialize the SQLite database."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS investigations (
                    investigation_id TEXT PRIMARY KEY,
                    alert_name TEXT,
                    timestamp TEXT,
                    context_documents TEXT,
                    evidence_count INTEGER,
                    confidence_reported REAL,
                    primary_hypothesis TEXT,
                    recommended_action TEXT,
                    category TEXT,
                    accepted_by_human INTEGER,
                    human_feedback TEXT,
                    human_override_reason TEXT,
                    outcome_correct INTEGER,
                    outcome_status TEXT,
                    actual_root_cause TEXT,
                    duration_seconds REAL,
                    severity TEXT
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_investigations_timestamp 
                ON investigations(timestamp)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_investigations_outcome 
                ON investigations(outcome_status)
            """)
            
            conn.commit()
    
    def record_investigation(self, record: InvestigationRecord) -> None:
        """
        Record a completed investigation.
        
        Updates both SQLite (for persistence) and Prometheus (for alerting).
        """
        with self._lock:
            # Store in SQLite
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO investigations 
                    (investigation_id, alert_name, timestamp, context_documents,
                     evidence_count, confidence_reported, primary_hypothesis,
                     recommended_action, category, accepted_by_human, human_feedback,
                     human_override_reason, outcome_correct, outcome_status,
                     actual_root_cause, duration_seconds, severity)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.investigation_id,
                    record.alert_name,
                    record.timestamp.isoformat(),
                    json.dumps(record.context_documents),
                    record.evidence_count,
                    record.confidence_reported,
                    record.primary_hypothesis,
                    record.recommended_action,
                    record.category,
                    1 if record.accepted_by_human else (0 if record.accepted_by_human is False else None),
                    record.human_feedback,
                    record.human_override_reason,
                    1 if record.outcome_correct else (0 if record.outcome_correct is False else None),
                    record.outcome_status.value,
                    record.actual_root_cause,
                    record.duration_seconds,
                    record.severity,
                ))
                conn.commit()
        
        # Update Prometheus metrics
        confidence_bucket = f"{int(record.confidence_reported * 10) / 10:.1f}"
        accepted = "yes" if record.accepted_by_human else ("no" if record.accepted_by_human is False else "pending")
        AI_RECOMMENDATIONS_TOTAL.labels(
            confidence_bucket=confidence_bucket,
            category=record.category,
            accepted=accepted
        ).inc()
        
        AI_INVESTIGATION_LATENCY.observe(record.duration_seconds)
        AI_EVIDENCE_COUNT.observe(record.evidence_count)
        
        for doc in record.context_documents:
            doc_type = doc.split("/")[0] if "/" in doc else "other"
            AI_CONTEXT_DOCUMENTS.labels(document_type=doc_type).inc()
        
        # Update accuracy metrics
        self._update_accuracy_metrics()
    
    def update_outcome(
        self,
        investigation_id: str,
        outcome_correct: bool,
        actual_root_cause: str = "",
    ) -> None:
        """
        Update the outcome of a previous investigation.
        
        Called after we know if the AI was right or wrong.
        """
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                # Get the original record for Prometheus update
                cursor = conn.execute(
                    "SELECT confidence_reported FROM investigations WHERE investigation_id = ?",
                    (investigation_id,)
                )
                row = cursor.fetchone()
                
                if row:
                    confidence = row[0]
                    outcome_status = OutcomeStatus.CORRECT if outcome_correct else OutcomeStatus.INCORRECT
                    
                    conn.execute("""
                        UPDATE investigations 
                        SET outcome_correct = ?, outcome_status = ?, actual_root_cause = ?
                        WHERE investigation_id = ?
                    """, (
                        1 if outcome_correct else 0,
                        outcome_status.value,
                        actual_root_cause,
                        investigation_id,
                    ))
                    conn.commit()
                    
                    # Update Prometheus calibration metric
                    outcome_label = "correct" if outcome_correct else "incorrect"
                    AI_CONFIDENCE_VS_ACCURACY.labels(outcome=outcome_label).observe(confidence)
        
        self._update_accuracy_metrics()
    
    def record_human_feedback(
        self,
        investigation_id: str,
        accepted: bool,
        feedback: str = "",
        override_reason: str = "",
    ) -> None:
        """
        Record human feedback on an investigation.
        """
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("""
                    UPDATE investigations 
                    SET accepted_by_human = ?, human_feedback = ?, human_override_reason = ?
                    WHERE investigation_id = ?
                """, (
                    1 if accepted else 0,
                    feedback,
                    override_reason,
                    investigation_id,
                ))
                conn.commit()
    
    def get_accuracy_rate(self, days: int = 7, severity: Optional[str] = None) -> float:
        """
        Get the accuracy rate over the past N days.
        
        Returns:
            Accuracy as a float from 0.0 to 1.0
        """
        cutoff = (utcnow() - timedelta(days=days)).isoformat()
        
        query = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN outcome_correct = 1 THEN 1 ELSE 0 END) as correct
            FROM investigations
            WHERE timestamp > ? AND outcome_status IN ('correct', 'incorrect')
        """
        params: list = [cutoff]
        
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(query, params)
            row = cursor.fetchone()
            
            if row and row[0] > 0:
                return row[1] / row[0]
            return 0.0
    
    def get_false_positive_rate(self, days: int = 7, category: Optional[str] = None) -> float:
        """
        Get the false positive rate.
        
        A false positive is when AI said there's a problem but there wasn't,
        or AI identified the wrong root cause.
        """
        cutoff = (utcnow() - timedelta(days=days)).isoformat()
        
        query = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN outcome_correct = 0 THEN 1 ELSE 0 END) as false_positives
            FROM investigations
            WHERE timestamp > ? AND outcome_status IN ('correct', 'incorrect')
        """
        params: list = [cutoff]
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(query, params)
            row = cursor.fetchone()
            
            if row and row[0] > 0:
                return row[1] / row[0]
            return 0.0
    
    def get_human_override_rate(self, days: int = 7) -> float:
        """
        Get the rate at which humans override AI recommendations.
        """
        cutoff = (utcnow() - timedelta(days=days)).isoformat()
        
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN accepted_by_human = 0 THEN 1 ELSE 0 END) as overrides
                FROM investigations
                WHERE timestamp > ? AND accepted_by_human IS NOT NULL
            """, (cutoff,))
            row = cursor.fetchone()
            
            if row and row[0] > 0:
                return row[1] / row[0]
            return 0.0
    
    def get_confidence_calibration(self, days: int = 30) -> dict[str, float]:
        """
        Check if confidence scores are well-calibrated.
        
        Returns a dict mapping confidence buckets to actual accuracy.
        E.g., {"0.8-0.9": 0.75} means when AI said 80-90% confident,
        it was actually right 75% of the time.
        """
        cutoff = (utcnow() - timedelta(days=days)).isoformat()
        
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                SELECT 
                    CAST(confidence_reported * 10 AS INTEGER) / 10.0 as bucket,
                    COUNT(*) as total,
                    SUM(CASE WHEN outcome_correct = 1 THEN 1 ELSE 0 END) as correct
                FROM investigations
                WHERE timestamp > ? AND outcome_status IN ('correct', 'incorrect')
                GROUP BY bucket
                ORDER BY bucket
            """, (cutoff,))
            
            calibration = {}
            for row in cursor:
                bucket = row[0]
                total = row[1]
                correct = row[2]
                bucket_label = f"{bucket:.1f}-{bucket + 0.1:.1f}"
                calibration[bucket_label] = correct / total if total > 0 else 0.0
            
            return calibration
    
    def get_statistics(self, days: int = 7) -> dict:
        """
        Get comprehensive statistics.
        """
        cutoff = (utcnow() - timedelta(days=days)).isoformat()
        
        with sqlite3.connect(str(self.db_path)) as conn:
            # Total investigations
            cursor = conn.execute(
                "SELECT COUNT(*) FROM investigations WHERE timestamp > ?",
                (cutoff,)
            )
            total = cursor.fetchone()[0]
            
            # Accuracy
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN outcome_correct = 1 THEN 1 ELSE 0 END) as correct
                FROM investigations
                WHERE timestamp > ? AND outcome_status IN ('correct', 'incorrect')
            """, (cutoff,))
            row = cursor.fetchone()
            determined = row[0]
            correct = row[1]
            
            # Human acceptance
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN accepted_by_human = 1 THEN 1 ELSE 0 END) as accepted
                FROM investigations
                WHERE timestamp > ? AND accepted_by_human IS NOT NULL
            """, (cutoff,))
            row = cursor.fetchone()
            feedback_total = row[0]
            accepted = row[1]
            
            # Average confidence
            cursor = conn.execute(
                "SELECT AVG(confidence_reported) FROM investigations WHERE timestamp > ?",
                (cutoff,)
            )
            avg_confidence = cursor.fetchone()[0] or 0.0
            
            # Average duration
            cursor = conn.execute(
                "SELECT AVG(duration_seconds) FROM investigations WHERE timestamp > ?",
                (cutoff,)
            )
            avg_duration = cursor.fetchone()[0] or 0.0
            
            return {
                "period_days": days,
                "total_investigations": total,
                "determined_outcomes": determined,
                "accuracy_rate": correct / determined if determined > 0 else 0.0,
                "false_positive_rate": (determined - correct) / determined if determined > 0 else 0.0,
                "human_acceptance_rate": accepted / feedback_total if feedback_total > 0 else 0.0,
                "human_override_rate": (feedback_total - accepted) / feedback_total if feedback_total > 0 else 0.0,
                "average_confidence": avg_confidence,
                "average_duration_seconds": avg_duration,
                "calibration": self.get_confidence_calibration(days),
            }
    
    def _update_accuracy_metrics(self):
        """Update Prometheus accuracy gauges."""
        for severity in ["low", "medium", "high", "critical"]:
            accuracy = self.get_accuracy_rate(days=7, severity=severity)
            AI_ACCURACY_GAUGE.labels(severity=severity).set(accuracy)
        
        for category in ["resource", "network", "application", "config", "external", "unknown"]:
            fp_rate = self.get_false_positive_rate(days=7, category=category)
            AI_FALSE_POSITIVE_RATE.labels(category=category).set(fp_rate)


# Singleton instance
_metrics_tracker: Optional[AIMetricsTracker] = None
_metrics_lock = threading.Lock()


def get_ai_metrics(db_path: Optional[Path] = None) -> AIMetricsTracker:
    """Get the global AI metrics tracker instance."""
    global _metrics_tracker
    
    with _metrics_lock:
        if _metrics_tracker is None:
            _metrics_tracker = AIMetricsTracker(db_path)
        return _metrics_tracker
