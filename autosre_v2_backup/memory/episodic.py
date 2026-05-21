"""
Episodic Memory — SQLite-based storage for investigation episodes.

Based on OpenSRE's memory/integration.py but simplified:
- SQLite instead of PostgreSQL
- Local-first, no HTTP API
- Full-text search via FTS5
"""

import json
import logging
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Episode(BaseModel):
    """A stored investigation episode."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Alert classification
    alert_type: str = ""
    alert_description: str = ""
    severity: str = "info"  # critical, warning, info
    
    # Service context
    service_name: str = ""
    services: list[str] = Field(default_factory=list)
    
    # Investigation outcome
    resolved: bool = False
    root_cause: Optional[str] = None
    summary: Optional[str] = None
    
    # Metadata
    skills_used: list[str] = Field(default_factory=list)
    key_findings: list[dict[str, Any]] = Field(default_factory=list)
    duration_seconds: Optional[float] = None
    effectiveness_score: float = 0.5  # 0.0-1.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for SQLite storage."""
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "alert_type": self.alert_type,
            "alert_description": self.alert_description,
            "severity": self.severity,
            "service_name": self.service_name,
            "services": json.dumps(self.services),
            "resolved": self.resolved,
            "root_cause": self.root_cause,
            "summary": self.summary,
            "skills_used": json.dumps(self.skills_used),
            "key_findings": json.dumps(self.key_findings),
            "duration_seconds": self.duration_seconds,
            "effectiveness_score": self.effectiveness_score,
        }
    
    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Episode":
        """Create Episode from SQLite row."""
        return cls(
            id=row["id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            alert_type=row["alert_type"],
            alert_description=row["alert_description"],
            severity=row["severity"],
            service_name=row["service_name"],
            services=json.loads(row["services"]),
            resolved=bool(row["resolved"]),
            root_cause=row["root_cause"],
            summary=row["summary"],
            skills_used=json.loads(row["skills_used"]),
            key_findings=json.loads(row["key_findings"]),
            duration_seconds=row["duration_seconds"],
            effectiveness_score=row["effectiveness_score"],
        )


class Strategy(BaseModel):
    """Generated investigation strategy from past episodes."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    alert_type: str
    service_name: str = "*"  # "*" means any service
    strategy_text: str
    source_episode_ids: list[str] = Field(default_factory=list)
    episode_count: int = 0


# SQL Schema
SCHEMA = """
-- Episodes table: stores completed investigations
CREATE TABLE IF NOT EXISTS episodes (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    alert_description TEXT,
    severity TEXT DEFAULT 'info',
    service_name TEXT,
    services TEXT DEFAULT '[]',  -- JSON array
    resolved INTEGER DEFAULT 0,
    root_cause TEXT,
    summary TEXT,
    skills_used TEXT DEFAULT '[]',  -- JSON array
    key_findings TEXT DEFAULT '[]',  -- JSON array
    duration_seconds REAL,
    effectiveness_score REAL DEFAULT 0.5
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_episodes_alert_type ON episodes(alert_type);
CREATE INDEX IF NOT EXISTS idx_episodes_service ON episodes(service_name);
CREATE INDEX IF NOT EXISTS idx_episodes_resolved ON episodes(resolved);
CREATE INDEX IF NOT EXISTS idx_episodes_created ON episodes(created_at DESC);

-- FTS5 for full-text search on key fields
CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts USING fts5(
    id,
    alert_type,
    alert_description,
    service_name,
    root_cause,
    summary,
    content='episodes',
    content_rowid='rowid'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS episodes_ai AFTER INSERT ON episodes BEGIN
    INSERT INTO episodes_fts(rowid, id, alert_type, alert_description, service_name, root_cause, summary)
    VALUES (new.rowid, new.id, new.alert_type, new.alert_description, new.service_name, new.root_cause, new.summary);
END;

CREATE TRIGGER IF NOT EXISTS episodes_ad AFTER DELETE ON episodes BEGIN
    INSERT INTO episodes_fts(episodes_fts, rowid, id, alert_type, alert_description, service_name, root_cause, summary)
    VALUES ('delete', old.rowid, old.id, old.alert_type, old.alert_description, old.service_name, old.root_cause, old.summary);
END;

CREATE TRIGGER IF NOT EXISTS episodes_au AFTER UPDATE ON episodes BEGIN
    INSERT INTO episodes_fts(episodes_fts, rowid, id, alert_type, alert_description, service_name, root_cause, summary)
    VALUES ('delete', old.rowid, old.id, old.alert_type, old.alert_description, old.service_name, old.root_cause, old.summary);
    INSERT INTO episodes_fts(rowid, id, alert_type, alert_description, service_name, root_cause, summary)
    VALUES (new.rowid, new.id, new.alert_type, new.alert_description, new.service_name, new.root_cause, new.summary);
END;

-- Strategies table: cached investigation strategies
CREATE TABLE IF NOT EXISTS strategies (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    service_name TEXT DEFAULT '*',
    strategy_text TEXT NOT NULL,
    source_episode_ids TEXT DEFAULT '[]',  -- JSON array
    episode_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_strategies_lookup ON strategies(alert_type, service_name);
"""


class EpisodicMemory:
    """SQLite-based episodic memory for investigation history."""
    
    def __init__(self, db_path: Path | str = ".autosre/memory.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._conn() as conn:
            conn.executescript(SCHEMA)
            logger.info(f"[MEMORY] Initialized database at {self.db_path}")
    
    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    
    def store(self, episode: Episode) -> str:
        """Store a completed investigation episode.
        
        Args:
            episode: The episode to store.
            
        Returns:
            The episode ID.
        """
        data = episode.to_dict()
        
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO episodes (
                    id, created_at, alert_type, alert_description, severity,
                    service_name, services, resolved, root_cause, summary,
                    skills_used, key_findings, duration_seconds, effectiveness_score
                ) VALUES (
                    :id, :created_at, :alert_type, :alert_description, :severity,
                    :service_name, :services, :resolved, :root_cause, :summary,
                    :skills_used, :key_findings, :duration_seconds, :effectiveness_score
                )
                """,
                data
            )
        
        logger.info(f"[MEMORY] Stored episode {episode.id}: {episode.alert_type}/{episode.service_name}")
        return episode.id
    
    def get(self, episode_id: str) -> Optional[Episode]:
        """Get an episode by ID."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM episodes WHERE id = ?",
                (episode_id,)
            ).fetchone()
        
        return Episode.from_row(row) if row else None
    
    def search_similar(
        self,
        alert_type: str = "",
        service_name: str = "",
        query: str = "",
        limit: int = 5,
    ) -> list[Episode]:
        """Search for similar past investigations.
        
        Priority order:
        1. Exact alert_type + service_name match
        2. Same alert_type, any service
        3. Same service, any alert_type
        4. Full-text search on query
        
        Args:
            alert_type: Type of alert (e.g., "http_500", "high_latency")
            service_name: Name of affected service
            query: Full-text search query
            limit: Maximum results to return
            
        Returns:
            List of matching episodes, most relevant first.
        """
        results: list[Episode] = []
        seen_ids: set[str] = set()
        
        with self._conn() as conn:
            # Tier 1: Exact match on alert_type + service
            if alert_type and service_name:
                rows = conn.execute(
                    """
                    SELECT * FROM episodes 
                    WHERE alert_type = ? AND service_name = ?
                    ORDER BY effectiveness_score DESC, created_at DESC
                    LIMIT ?
                    """,
                    (alert_type, service_name, limit)
                ).fetchall()
                
                for row in rows:
                    ep = Episode.from_row(row)
                    if ep.id not in seen_ids:
                        results.append(ep)
                        seen_ids.add(ep.id)
            
            # Tier 2: Same alert_type, any service
            if alert_type and len(results) < limit:
                remaining = limit - len(results)
                rows = conn.execute(
                    """
                    SELECT * FROM episodes 
                    WHERE alert_type = ?
                    ORDER BY effectiveness_score DESC, created_at DESC
                    LIMIT ?
                    """,
                    (alert_type, remaining + len(seen_ids))
                ).fetchall()
                
                for row in rows:
                    ep = Episode.from_row(row)
                    if ep.id not in seen_ids:
                        results.append(ep)
                        seen_ids.add(ep.id)
                        if len(results) >= limit:
                            break
            
            # Tier 3: Same service, any alert
            if service_name and len(results) < limit:
                remaining = limit - len(results)
                rows = conn.execute(
                    """
                    SELECT * FROM episodes 
                    WHERE service_name = ?
                    ORDER BY effectiveness_score DESC, created_at DESC
                    LIMIT ?
                    """,
                    (service_name, remaining + len(seen_ids))
                ).fetchall()
                
                for row in rows:
                    ep = Episode.from_row(row)
                    if ep.id not in seen_ids:
                        results.append(ep)
                        seen_ids.add(ep.id)
                        if len(results) >= limit:
                            break
            
            # Tier 4: Full-text search
            if query and len(results) < limit:
                remaining = limit - len(results)
                rows = conn.execute(
                    """
                    SELECT e.* FROM episodes e
                    JOIN episodes_fts fts ON e.id = fts.id
                    WHERE episodes_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (query, remaining + len(seen_ids))
                ).fetchall()
                
                for row in rows:
                    ep = Episode.from_row(row)
                    if ep.id not in seen_ids:
                        results.append(ep)
                        seen_ids.add(ep.id)
                        if len(results) >= limit:
                            break
        
        logger.info(f"[MEMORY] Found {len(results)} similar episodes for {alert_type}/{service_name}")
        return results[:limit]
    
    def search_text(self, query: str, limit: int = 10) -> list[Episode]:
        """Full-text search across episodes."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT e.* FROM episodes e
                JOIN episodes_fts fts ON e.id = fts.id
                WHERE episodes_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit)
            ).fetchall()
        
        return [Episode.from_row(row) for row in rows]
    
    def get_all(self, limit: int = 100) -> list[Episode]:
        """Get all episodes, most recent first."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM episodes ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
        
        return [Episode.from_row(row) for row in rows]
    
    def get_stats(self) -> dict[str, Any]:
        """Get memory statistics."""
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
            resolved = conn.execute(
                "SELECT COUNT(*) FROM episodes WHERE resolved = 1"
            ).fetchone()[0]
            strategies = conn.execute("SELECT COUNT(*) FROM strategies").fetchone()[0]
            
            # Get top alert types
            alert_types = conn.execute(
                """
                SELECT alert_type, COUNT(*) as count 
                FROM episodes 
                GROUP BY alert_type 
                ORDER BY count DESC 
                LIMIT 5
                """
            ).fetchall()
            
            # Get top services
            services = conn.execute(
                """
                SELECT service_name, COUNT(*) as count 
                FROM episodes 
                WHERE service_name != ''
                GROUP BY service_name 
                ORDER BY count DESC 
                LIMIT 5
                """
            ).fetchall()
        
        return {
            "total_episodes": total,
            "resolved_episodes": resolved,
            "unresolved_episodes": total - resolved,
            "strategies_count": strategies,
            "resolution_rate": resolved / total if total > 0 else 0,
            "top_alert_types": [{"type": r[0], "count": r[1]} for r in alert_types],
            "top_services": [{"service": r[0], "count": r[1]} for r in services],
        }
    
    def delete(self, episode_id: str) -> bool:
        """Delete an episode by ID."""
        with self._conn() as conn:
            cursor = conn.execute("DELETE FROM episodes WHERE id = ?", (episode_id,))
            return cursor.rowcount > 0
    
    def clear(self) -> int:
        """Clear all episodes. Returns count deleted."""
        with self._conn() as conn:
            cursor = conn.execute("DELETE FROM episodes")
            conn.execute("DELETE FROM strategies")
            return cursor.rowcount
    
    # ----- Strategy methods -----
    
    def store_strategy(self, strategy: Strategy) -> str:
        """Store a generated strategy."""
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO strategies 
                (id, created_at, alert_type, service_name, strategy_text, source_episode_ids, episode_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    strategy.id,
                    strategy.created_at.isoformat(),
                    strategy.alert_type,
                    strategy.service_name,
                    strategy.strategy_text,
                    json.dumps(strategy.source_episode_ids),
                    strategy.episode_count,
                )
            )
        
        logger.info(f"[MEMORY] Stored strategy for {strategy.alert_type}/{strategy.service_name}")
        return strategy.id
    
    def get_strategy(self, alert_type: str, service_name: str = "*") -> Optional[Strategy]:
        """Get cached strategy for an alert type + service."""
        with self._conn() as conn:
            # Try exact match first
            row = conn.execute(
                "SELECT * FROM strategies WHERE alert_type = ? AND service_name = ?",
                (alert_type, service_name)
            ).fetchone()
            
            # Fall back to wildcard service
            if not row and service_name != "*":
                row = conn.execute(
                    "SELECT * FROM strategies WHERE alert_type = ? AND service_name = '*'",
                    (alert_type,)
                ).fetchone()
        
        if not row:
            return None
        
        return Strategy(
            id=row["id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            alert_type=row["alert_type"],
            service_name=row["service_name"],
            strategy_text=row["strategy_text"],
            source_episode_ids=json.loads(row["source_episode_ids"]),
            episode_count=row["episode_count"],
        )
