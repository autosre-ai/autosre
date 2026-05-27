"""
Episodic Memory Storage

SQLite-based episodic memory for AutoSRE incident investigations.
Stores and retrieves episodes from past investigations, enabling
the agent to learn from historical context.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .models import Episode, Strategy, MemoryQuery


class EpisodicMemory:
    """
    Manages persistent episodic memory using SQLite.
    
    Episodes capture:
    - What happened (symptoms, metrics, logs)
    - What was tried (investigation steps)
    - What worked (successful diagnoses)
    - What the root cause was
    """
    
    def __init__(self, db_path: str = "~/.autosre/memory.db", storage_path: Optional[str] = None):
        """Initialize the episodic memory system.
        
        Args:
            db_path: Path to the SQLite database file.
            storage_path: Deprecated alias for db_path.
        """
        # Support legacy storage_path parameter
        actual_path = storage_path or db_path
        self.db_path = Path(actual_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        
        # In-memory cache for fast access
        self._episodes_cache: List[Episode] = []
    
    def _init_db(self) -> None:
        """Create database tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    alert_type TEXT NOT NULL,
                    service_name TEXT,
                    severity TEXT DEFAULT 'info',
                    root_cause TEXT,
                    summary TEXT,
                    resolved INTEGER DEFAULT 0,
                    effectiveness_score REAL DEFAULT 0.0,
                    skills_used TEXT,
                    key_findings TEXT,
                    duration_seconds INTEGER,
                    symptoms TEXT,
                    metrics TEXT,
                    logs TEXT,
                    topology TEXT,
                    steps_taken TEXT,
                    hypotheses TEXT,
                    resolution TEXT,
                    tags TEXT,
                    embedding TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_alert ON episodes(alert_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_service ON episodes(service_name)")
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS strategies (
                    id TEXT PRIMARY KEY,
                    alert_type TEXT NOT NULL,
                    service_name TEXT DEFAULT '*',
                    strategy_text TEXT NOT NULL,
                    source_episode_ids TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    
    def store_episode(self, episode: Episode) -> str:
        """Store an episode in the database.
        
        Args:
            episode: The Episode to store.
            
        Returns:
            The episode ID.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO episodes (
                    id, created_at, alert_type, service_name, severity,
                    root_cause, summary, resolved, effectiveness_score,
                    skills_used, key_findings, duration_seconds,
                    symptoms, metrics, logs, topology, steps_taken,
                    hypotheses, resolution, tags, embedding
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                episode.id,
                episode.created_at.isoformat(),
                episode.alert_type,
                episode.service_name,
                episode.severity,
                episode.root_cause,
                episode.summary,
                1 if episode.resolved else 0,
                episode.effectiveness_score,
                json.dumps(episode.skills_used),
                json.dumps(episode.key_findings),
                episode.duration_seconds,
                json.dumps(episode.symptoms),
                json.dumps(episode.metrics),
                json.dumps(episode.logs),
                json.dumps(episode.topology),
                json.dumps(episode.steps_taken),
                json.dumps(episode.hypotheses),
                episode.resolution,
                json.dumps(episode.tags),
                json.dumps(episode.embedding) if episode.embedding else None
            ))
            conn.commit()
        return episode.id
    
    async def store(self, episode: Episode) -> str:
        """Async wrapper for store_episode (for backward compatibility)."""
        return self.store_episode(episode)
    
    def search_similar(
        self, 
        alert_type: str, 
        service: Optional[str] = None, 
        limit: int = 3
    ) -> List[Episode]:
        """Search for similar episodes by alert type and optionally service.
        
        Args:
            alert_type: The type of alert to search for.
            service: Optional service name to filter by.
            limit: Maximum number of episodes to return.
            
        Returns:
            List of matching Episode objects, ordered by recency.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            if service:
                # First try exact match on both alert_type and service_name
                cursor = conn.execute("""
                    SELECT * FROM episodes 
                    WHERE alert_type = ? AND service_name = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (alert_type, service, limit))
                rows = cursor.fetchall()
                
                # If not enough results, also include same alert_type with any service
                if len(rows) < limit:
                    remaining = limit - len(rows)
                    existing_ids = [row['id'] for row in rows]
                    
                    if existing_ids:
                        placeholders = ','.join('?' * len(existing_ids))
                        cursor = conn.execute(f"""
                            SELECT * FROM episodes 
                            WHERE alert_type = ? AND id NOT IN ({placeholders})
                            ORDER BY created_at DESC
                            LIMIT ?
                        """, (alert_type, *existing_ids, remaining))
                    else:
                        cursor = conn.execute("""
                            SELECT * FROM episodes 
                            WHERE alert_type = ?
                            ORDER BY created_at DESC
                            LIMIT ?
                        """, (alert_type, remaining))
                    rows.extend(cursor.fetchall())
            else:
                cursor = conn.execute("""
                    SELECT * FROM episodes 
                    WHERE alert_type = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (alert_type, limit))
                rows = cursor.fetchall()
        
        return [self._row_to_episode(row) for row in rows]
    
    async def retrieve(self, query: MemoryQuery, limit: int = 5) -> List[Episode]:
        """Retrieve relevant episodes matching the query (async interface).
        
        Args:
            query: MemoryQuery with search parameters.
            limit: Maximum number of episodes to return.
            
        Returns:
            List of matching Episode objects.
        """
        if query.alert_type:
            return self.search_similar(query.alert_type, query.service, limit)
        
        # Fallback: return most recent episodes
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM episodes 
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
        
        return [self._row_to_episode(row) for row in rows]
    
    def _row_to_episode(self, row: sqlite3.Row) -> Episode:
        """Convert a database row to an Episode object."""
        return Episode(
            id=row['id'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else datetime.now(timezone.utc),
            alert_type=row['alert_type'],
            service_name=row['service_name'],
            severity=row['severity'] or 'info',
            root_cause=row['root_cause'],
            summary=row['summary'],
            resolved=bool(row['resolved']),
            effectiveness_score=row['effectiveness_score'] or 0.0,
            skills_used=json.loads(row['skills_used']) if row['skills_used'] else [],
            key_findings=json.loads(row['key_findings']) if row['key_findings'] else [],
            duration_seconds=row['duration_seconds'],
            symptoms=json.loads(row['symptoms']) if row['symptoms'] else [],
            metrics=json.loads(row['metrics']) if row['metrics'] else {},
            logs=json.loads(row['logs']) if row['logs'] else [],
            topology=json.loads(row['topology']) if row['topology'] else {},
            steps_taken=json.loads(row['steps_taken']) if row['steps_taken'] else [],
            hypotheses=json.loads(row['hypotheses']) if row['hypotheses'] else [],
            resolution=row['resolution'],
            tags=json.loads(row['tags']) if row['tags'] else [],
            embedding=json.loads(row['embedding']) if row['embedding'] else None
        )
    
    async def get(self, episode_id: str) -> Optional[Episode]:
        """Get a specific episode by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM episodes WHERE id = ?", (episode_id,))
            row = cursor.fetchone()
        
        return self._row_to_episode(row) if row else None
    
    async def update(self, episode_id: str, updates: dict) -> bool:
        """Update an existing episode."""
        episode = await self.get(episode_id)
        if not episode:
            return False
        
        # Merge updates into episode
        episode_dict = episode.model_dump()
        episode_dict.update(updates)
        updated_episode = Episode(**episode_dict)
        self.store_episode(updated_episode)
        return True
    
    def store_strategy(self, strategy: Strategy) -> str:
        """Store a strategy in the database.
        
        Args:
            strategy: The Strategy to store.
            
        Returns:
            The strategy ID.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO strategies (
                    id, alert_type, service_name, strategy_text,
                    source_episode_ids, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                strategy.id,
                strategy.alert_type,
                strategy.service_name,
                strategy.strategy_text,
                json.dumps(strategy.source_episode_ids),
                strategy.created_at.isoformat()
            ))
            conn.commit()
        return strategy.id
    
    def get_or_generate_strategy(
        self, 
        alert_type: str, 
        service: Optional[str] = None
    ) -> Optional[str]:
        """Get an existing strategy or return None if none exists.
        
        Args:
            alert_type: The type of alert.
            service: Optional service name.
            
        Returns:
            Strategy text if found, None otherwise.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Try exact match first (specific service)
            if service:
                cursor = conn.execute("""
                    SELECT strategy_text FROM strategies
                    WHERE alert_type = ? AND service_name = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (alert_type, service))
                row = cursor.fetchone()
                if row:
                    return row['strategy_text']
            
            # Try wildcard match (any service)
            cursor = conn.execute("""
                SELECT strategy_text FROM strategies
                WHERE alert_type = ? AND service_name = '*'
                ORDER BY created_at DESC
                LIMIT 1
            """, (alert_type,))
            row = cursor.fetchone()
            
            return row['strategy_text'] if row else None
    
    def get_stats(self) -> dict:
        """Get statistics about the episodic memory.
        
        Returns:
            Dictionary with memory statistics.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM episodes")
            total_episodes = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) FROM episodes WHERE resolved = 1")
            resolved_count = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) FROM strategies")
            total_strategies = cursor.fetchone()[0]
            
            cursor = conn.execute("""
                SELECT alert_type, COUNT(*) as count 
                FROM episodes 
                GROUP BY alert_type 
                ORDER BY count DESC 
                LIMIT 5
            """)
            top_alert_types = [{"alert_type": row[0], "count": row[1]} for row in cursor.fetchall()]
            
            cursor = conn.execute("""
                SELECT AVG(effectiveness_score) FROM episodes WHERE resolved = 1
            """)
            avg_effectiveness = cursor.fetchone()[0] or 0.0
            
            cursor = conn.execute("""
                SELECT AVG(duration_seconds) FROM episodes 
                WHERE resolved = 1 AND duration_seconds IS NOT NULL
            """)
            avg_duration = cursor.fetchone()[0]
        
        return {
            "total_episodes": total_episodes,
            "resolved_count": resolved_count,
            "resolution_rate": resolved_count / total_episodes if total_episodes > 0 else 0.0,
            "total_strategies": total_strategies,
            "top_alert_types": top_alert_types,
            "avg_effectiveness_score": round(avg_effectiveness, 2),
            "avg_resolution_seconds": round(avg_duration, 0) if avg_duration else None
        }
    
    def clear(self) -> None:
        """Clear all data from the database. Use with caution!"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM episodes")
            conn.execute("DELETE FROM strategies")
            conn.commit()
