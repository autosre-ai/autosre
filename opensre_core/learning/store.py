"""Persistent incident storage for learning."""

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class StoredIncident:
    """Stored incident for learning."""
    id: str
    issue: str
    namespace: str
    root_cause: str
    confidence: float
    observations: list[dict] = field(default_factory=list)
    actions: list[dict] = field(default_factory=list)
    actions_executed: list[str] = field(default_factory=list)
    outcome: Optional[str] = None  # "resolved", "escalated", "false_positive"
    resolution_time_minutes: Optional[int] = None
    user_feedback: Optional[str] = None
    created_at: datetime = None
    resolved_at: datetime = None


class IncidentStore:
    """SQLite-backed incident storage."""

    def __init__(self, db_path: str = "data/incidents.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY,
                    issue TEXT,
                    namespace TEXT,
                    root_cause TEXT,
                    confidence REAL,
                    observations TEXT,
                    actions TEXT,
                    actions_executed TEXT,
                    outcome TEXT,
                    resolution_time_minutes INTEGER,
                    user_feedback TEXT,
                    created_at TEXT,
                    resolved_at TEXT
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_namespace ON incidents(namespace)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_root_cause ON incidents(root_cause)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_outcome ON incidents(outcome)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at ON incidents(created_at)
            """)

    def save(self, incident: StoredIncident):
        """Save an incident."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO incidents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                incident.id,
                incident.issue,
                incident.namespace,
                incident.root_cause,
                incident.confidence,
                json.dumps(incident.observations),
                json.dumps(incident.actions),
                json.dumps(incident.actions_executed),
                incident.outcome,
                incident.resolution_time_minutes,
                incident.user_feedback,
                incident.created_at.isoformat() if incident.created_at else None,
                incident.resolved_at.isoformat() if incident.resolved_at else None,
            ))

    def get(self, incident_id: str) -> Optional[StoredIncident]:
        """Get an incident by ID."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM incidents WHERE id = ?", (incident_id,)
            ).fetchone()

            if row:
                return self._row_to_incident(row)
        return None

    def find_similar(self, issue: str, namespace: str = None, limit: int = 5) -> list[StoredIncident]:
        """Find similar past incidents."""
        # Simple keyword matching - could be enhanced with embeddings
        keywords = issue.lower().split()

        if not keywords:
            return []

        with sqlite3.connect(self.db_path) as conn:
            params = []

            # Build OR conditions for keyword matching
            keyword_conditions = []
            for kw in keywords:
                if len(kw) > 2:  # Skip very short words
                    keyword_conditions.append("(LOWER(issue) LIKE ? OR LOWER(root_cause) LIKE ?)")
                    params.extend([f"%{kw}%", f"%{kw}%"])

            if not keyword_conditions:
                return []

            query = "SELECT * FROM incidents WHERE (" + " OR ".join(keyword_conditions) + ")"

            if namespace:
                query += " AND namespace = ?"
                params.append(namespace)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()
            return [self._row_to_incident(row) for row in rows]

    def find_by_root_cause(self, root_cause: str, limit: int = 10) -> list[StoredIncident]:
        """Find incidents by root cause pattern."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT * FROM incidents
                   WHERE LOWER(root_cause) LIKE ?
                   ORDER BY created_at DESC LIMIT ?""",
                (f"%{root_cause.lower()}%", limit)
            ).fetchall()
            return [self._row_to_incident(row) for row in rows]

    def find_by_namespace(self, namespace: str, limit: int = 20) -> list[StoredIncident]:
        """Find incidents by namespace."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM incidents WHERE namespace = ? ORDER BY created_at DESC LIMIT ?",
                (namespace, limit)
            ).fetchall()
            return [self._row_to_incident(row) for row in rows]

    def find_recent(self, limit: int = 20) -> list[StoredIncident]:
        """Find recent incidents."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM incidents ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [self._row_to_incident(row) for row in rows]

    def get_statistics(self, namespace: str = None) -> dict:
        """Get incident statistics."""
        with sqlite3.connect(self.db_path) as conn:
            base_where = "WHERE namespace = ?" if namespace else "WHERE 1=1"
            base_params = [namespace] if namespace else []

            total = conn.execute(
                f"SELECT COUNT(*) FROM incidents {base_where}",
                base_params
            ).fetchone()[0]

            if total == 0:
                return {
                    "total_incidents": 0,
                    "resolved": 0,
                    "escalated": 0,
                    "false_positives": 0,
                    "resolution_rate": 0,
                    "avg_resolution_time_minutes": 0,
                    "top_root_causes": [],
                    "top_namespaces": [],
                }

            resolved = conn.execute(
                f"SELECT COUNT(*) FROM incidents {base_where} AND outcome = 'resolved'",
                base_params
            ).fetchone()[0]

            escalated = conn.execute(
                f"SELECT COUNT(*) FROM incidents {base_where} AND outcome = 'escalated'",
                base_params
            ).fetchone()[0]

            false_positives = conn.execute(
                f"SELECT COUNT(*) FROM incidents {base_where} AND outcome = 'false_positive'",
                base_params
            ).fetchone()[0]

            avg_time = conn.execute(
                f"""SELECT AVG(resolution_time_minutes) FROM incidents
                    {base_where} AND resolution_time_minutes IS NOT NULL""",
                base_params
            ).fetchone()[0]

            # Top root causes
            top_causes = conn.execute(
                f"""SELECT root_cause, COUNT(*) as cnt FROM incidents {base_where}
                    GROUP BY root_cause ORDER BY cnt DESC LIMIT 10""",
                base_params
            ).fetchall()

            # Top namespaces (only if no namespace filter)
            top_namespaces = []
            if not namespace:
                top_namespaces = conn.execute(
                    """SELECT namespace, COUNT(*) as cnt FROM incidents
                       GROUP BY namespace ORDER BY cnt DESC LIMIT 10"""
                ).fetchall()

            return {
                "total_incidents": total,
                "resolved": resolved,
                "escalated": escalated,
                "false_positives": false_positives,
                "resolution_rate": resolved / total if total > 0 else 0,
                "avg_resolution_time_minutes": avg_time or 0,
                "top_root_causes": [{"cause": c, "count": n} for c, n in top_causes],
                "top_namespaces": [{"namespace": ns, "count": n} for ns, n in top_namespaces],
            }

    def update_outcome(
        self,
        incident_id: str,
        outcome: str,
        feedback: str = None,
        resolved_at: datetime = None,
    ) -> bool:
        """Update incident outcome and feedback."""
        incident = self.get(incident_id)
        if not incident:
            return False

        resolved_at = resolved_at or datetime.now()

        # Calculate resolution time
        resolution_time = None
        if incident.created_at:
            resolution_time = int((resolved_at - incident.created_at).total_seconds() / 60)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE incidents
                SET outcome = ?,
                    user_feedback = ?,
                    resolved_at = ?,
                    resolution_time_minutes = ?
                WHERE id = ?
            """, (
                outcome,
                feedback,
                resolved_at.isoformat(),
                resolution_time,
                incident_id,
            ))

        return True

    def record_action_executed(self, incident_id: str, action: str) -> bool:
        """Record that an action was executed."""
        incident = self.get(incident_id)
        if not incident:
            return False

        actions = incident.actions_executed or []
        actions.append(action)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE incidents SET actions_executed = ? WHERE id = ?",
                (json.dumps(actions), incident_id)
            )

        return True

    def _row_to_incident(self, row) -> StoredIncident:
        return StoredIncident(
            id=row[0],
            issue=row[1],
            namespace=row[2],
            root_cause=row[3],
            confidence=row[4],
            observations=json.loads(row[5]) if row[5] else [],
            actions=json.loads(row[6]) if row[6] else [],
            actions_executed=json.loads(row[7]) if row[7] else [],
            outcome=row[8],
            resolution_time_minutes=row[9],
            user_feedback=row[10],
            created_at=datetime.fromisoformat(row[11]) if row[11] else None,
            resolved_at=datetime.fromisoformat(row[12]) if row[12] else None,
        )
