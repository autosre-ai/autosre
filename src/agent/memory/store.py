"""
PostgreSQL storage layer for the episodic memory system.

Provides async CRUD operations for episodes, strategies, and key findings.
Uses asyncpg for high-performance async PostgreSQL access with connection pooling.
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, AsyncIterator, Optional
from uuid import UUID

import asyncpg
from asyncpg import Pool, Connection

from .models import (
    Episode,
    EpisodeCreate,
    EpisodeUpdate,
    KeyFinding,
    MemorySearchResult,
    MemoryStats,
    Severity,
    Strategy,
    StrategyCreate,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATABASE_URL = os.getenv(
    "MEMORY_DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql://autosre:autosre@localhost:5432/autosre")
)

POOL_MIN_SIZE = int(os.getenv("MEMORY_POOL_MIN_SIZE", "2"))
POOL_MAX_SIZE = int(os.getenv("MEMORY_POOL_MAX_SIZE", "10"))


# ---------------------------------------------------------------------------
# Connection Pool Management
# ---------------------------------------------------------------------------

_pool: Optional[Pool] = None


async def get_pool() -> Pool:
    """Get or create the connection pool."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=POOL_MIN_SIZE,
            max_size=POOL_MAX_SIZE,
            command_timeout=30.0,
        )
        logger.info(f"[MEMORY-STORE] Created connection pool (min={POOL_MIN_SIZE}, max={POOL_MAX_SIZE})")
    return _pool


async def close_pool() -> None:
    """Close the connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("[MEMORY-STORE] Closed connection pool")


@asynccontextmanager
async def get_connection() -> AsyncIterator[Connection]:
    """Get a connection from the pool."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


# ---------------------------------------------------------------------------
# Episode Operations
# ---------------------------------------------------------------------------

async def store_episode(episode: EpisodeCreate) -> Episode:
    """
    Store a new investigation episode.
    
    Args:
        episode: Episode data to store
        
    Returns:
        The created Episode with generated ID and timestamps
    """
    async with get_connection() as conn:
        now = datetime.utcnow()
        episode_id = await conn.fetchval(
            """
            INSERT INTO episodes (
                agent_run_id, org_id, team_node_id,
                alert_type, alert_description, severity, services,
                agents_used, skills_used, key_findings,
                resolved, root_cause, summary, remediation_steps,
                effectiveness_score, confidence, duration_seconds,
                created_at, updated_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15, $16, $17, $18, $19
            ) RETURNING id
            """,
            episode.agent_run_id,
            episode.org_id,
            episode.team_node_id,
            episode.alert_type,
            episode.alert_description,
            episode.severity.value if isinstance(episode.severity, Severity) else episode.severity,
            episode.services,
            episode.agents_used,
            episode.skills_used,
            [kf if isinstance(kf, dict) else kf.model_dump() for kf in episode.key_findings],
            episode.resolved,
            episode.root_cause,
            episode.summary,
            episode.remediation_steps,
            episode.effectiveness_score,
            episode.confidence,
            episode.duration_seconds,
            now,
            now,
        )
        
        logger.info(f"[MEMORY-STORE] Stored episode {episode_id}: {episode.alert_type}/{','.join(episode.services)}")
        
        return Episode(
            id=episode_id,
            agent_run_id=episode.agent_run_id,
            org_id=episode.org_id,
            team_node_id=episode.team_node_id,
            alert_type=episode.alert_type,
            alert_description=episode.alert_description,
            severity=episode.severity,
            services=episode.services,
            agents_used=episode.agents_used,
            skills_used=episode.skills_used,
            key_findings=[KeyFinding(**kf) if isinstance(kf, dict) else kf for kf in episode.key_findings],
            resolved=episode.resolved,
            root_cause=episode.root_cause,
            summary=episode.summary,
            remediation_steps=episode.remediation_steps,
            effectiveness_score=episode.effectiveness_score,
            confidence=episode.confidence,
            duration_seconds=episode.duration_seconds,
            created_at=now,
            updated_at=now,
        )


async def get_episode(episode_id: UUID, org_id: str = "default") -> Optional[Episode]:
    """
    Retrieve a single episode by ID.
    
    Args:
        episode_id: The episode UUID
        org_id: Organization ID for access control
        
    Returns:
        The Episode if found, None otherwise
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM episodes
            WHERE id = $1 AND org_id = $2
            """,
            episode_id,
            org_id,
        )
        
        if row is None:
            return None
        
        return _row_to_episode(row)


async def update_episode(
    episode_id: UUID,
    update: EpisodeUpdate,
    org_id: str = "default"
) -> Optional[Episode]:
    """
    Update an existing episode.
    
    Args:
        episode_id: The episode UUID
        update: Fields to update
        org_id: Organization ID for access control
        
    Returns:
        The updated Episode if found, None otherwise
    """
    # Build dynamic UPDATE query based on provided fields
    updates = []
    values = []
    param_idx = 1
    
    update_data = update.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        if value is not None:
            updates.append(f"{field} = ${param_idx}")
            if field == "key_findings":
                value = [kf if isinstance(kf, dict) else kf for kf in value]
            values.append(value)
            param_idx += 1
    
    if not updates:
        return await get_episode(episode_id, org_id)
    
    updates.append(f"updated_at = ${param_idx}")
    values.append(datetime.utcnow())
    param_idx += 1
    
    values.append(episode_id)
    values.append(org_id)
    
    query = f"""
        UPDATE episodes
        SET {', '.join(updates)}
        WHERE id = ${param_idx} AND org_id = ${param_idx + 1}
        RETURNING *
    """
    
    async with get_connection() as conn:
        row = await conn.fetchrow(query, *values)
        
        if row is None:
            return None
        
        logger.info(f"[MEMORY-STORE] Updated episode {episode_id}")
        return _row_to_episode(row)


async def list_episodes(
    org_id: str = "default",
    alert_type: Optional[str] = None,
    service_name: Optional[str] = None,
    resolved: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Episode]:
    """
    List episodes with optional filtering.
    
    Args:
        org_id: Organization ID
        alert_type: Filter by alert type
        service_name: Filter by service name (checks array membership)
        resolved: Filter by resolution status
        limit: Maximum results
        offset: Pagination offset
        
    Returns:
        List of matching Episodes
    """
    conditions = ["org_id = $1"]
    values: list[Any] = [org_id]
    param_idx = 2
    
    if alert_type:
        conditions.append(f"alert_type = ${param_idx}")
        values.append(alert_type)
        param_idx += 1
    
    if service_name:
        conditions.append(f"${param_idx} = ANY(services)")
        values.append(service_name)
        param_idx += 1
    
    if resolved is not None:
        conditions.append(f"resolved = ${param_idx}")
        values.append(resolved)
        param_idx += 1
    
    values.extend([limit, offset])
    
    query = f"""
        SELECT * FROM episodes
        WHERE {' AND '.join(conditions)}
        ORDER BY created_at DESC
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
    """
    
    async with get_connection() as conn:
        rows = await conn.fetch(query, *values)
        return [_row_to_episode(row) for row in rows]


async def search_similar(
    org_id: str = "default",
    alert_type: Optional[str] = None,
    service_name: Optional[str] = None,
    prompt: Optional[str] = None,
    limit: int = 5,
) -> list[MemorySearchResult]:
    """
    Search for similar past episodes.
    
    Currently uses keyword matching on alert_type and services.
    Future: Add vector similarity search using embeddings.
    
    Args:
        org_id: Organization ID
        alert_type: Alert type to match
        service_name: Service to match
        prompt: Free-text prompt for semantic search (future)
        limit: Maximum results
        
    Returns:
        List of MemorySearchResult with similarity scores
    """
    conditions = ["org_id = $1"]
    values: list[Any] = [org_id]
    param_idx = 2
    
    # Build match scoring
    score_parts = []
    
    if alert_type:
        conditions.append(f"(alert_type = ${param_idx} OR alert_type = 'unknown')")
        score_parts.append(f"CASE WHEN alert_type = ${param_idx} THEN 0.4 ELSE 0.0 END")
        values.append(alert_type)
        param_idx += 1
    
    if service_name:
        conditions.append(f"(${param_idx} = ANY(services) OR cardinality(services) = 0)")
        score_parts.append(f"CASE WHEN ${param_idx} = ANY(services) THEN 0.3 ELSE 0.0 END")
        values.append(service_name)
        param_idx += 1
    
    # Add score for resolved episodes (prefer successful investigations)
    score_parts.append("CASE WHEN resolved THEN 0.2 ELSE 0.0 END")
    
    # Add recency boost
    score_parts.append("CASE WHEN created_at > NOW() - INTERVAL '30 days' THEN 0.1 ELSE 0.0 END")
    
    score_expr = " + ".join(score_parts) if score_parts else "0.5"
    
    values.append(limit)
    
    query = f"""
        SELECT *, ({score_expr}) as similarity_score
        FROM episodes
        WHERE {' AND '.join(conditions)}
        ORDER BY similarity_score DESC, effectiveness_score DESC, created_at DESC
        LIMIT ${param_idx}
    """
    
    async with get_connection() as conn:
        rows = await conn.fetch(query, *values)
        
        results = []
        for row in rows:
            episode = _row_to_episode(row)
            score = float(row.get("similarity_score", 0.5))
            
            # Determine match reasons
            reasons = []
            if alert_type and row["alert_type"] == alert_type:
                reasons.append("Same alert type")
            if service_name and service_name in (row["services"] or []):
                reasons.append("Same service")
            if row["resolved"]:
                reasons.append("Successfully resolved")
            
            results.append(MemorySearchResult(
                episode=episode,
                similarity_score=min(score, 1.0),
                match_reasons=reasons,
            ))
        
        logger.info(f"[MEMORY-STORE] Found {len(results)} similar episodes for {alert_type}/{service_name}")
        return results


async def delete_episode(episode_id: UUID, org_id: str = "default") -> bool:
    """Delete an episode by ID."""
    async with get_connection() as conn:
        result = await conn.execute(
            """
            DELETE FROM episodes
            WHERE id = $1 AND org_id = $2
            """,
            episode_id,
            org_id,
        )
        deleted = result == "DELETE 1"
        if deleted:
            logger.info(f"[MEMORY-STORE] Deleted episode {episode_id}")
        return deleted


# ---------------------------------------------------------------------------
# Strategy Operations
# ---------------------------------------------------------------------------

async def store_strategy(strategy: StrategyCreate) -> Strategy:
    """Store a new investigation strategy."""
    async with get_connection() as conn:
        now = datetime.utcnow()
        expires_at = now + timedelta(days=7)  # Strategies expire after a week
        
        strategy_id = await conn.fetchval(
            """
            INSERT INTO strategies (
                org_id, team_node_id,
                alert_type, service_name, strategy_text,
                source_episode_ids, episode_count,
                created_at, updated_at, expires_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING id
            """,
            strategy.org_id,
            strategy.team_node_id,
            strategy.alert_type,
            strategy.service_name,
            strategy.strategy_text,
            [str(eid) for eid in strategy.source_episode_ids],
            strategy.episode_count,
            now,
            now,
            expires_at,
        )
        
        logger.info(f"[MEMORY-STORE] Stored strategy {strategy_id}: {strategy.alert_type}/{strategy.service_name}")
        
        return Strategy(
            id=strategy_id,
            org_id=strategy.org_id,
            team_node_id=strategy.team_node_id,
            alert_type=strategy.alert_type,
            service_name=strategy.service_name,
            strategy_text=strategy.strategy_text,
            source_episode_ids=strategy.source_episode_ids,
            episode_count=strategy.episode_count,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
        )


async def get_strategy(
    org_id: str,
    alert_type: str,
    service_name: str = "*",
) -> Optional[Strategy]:
    """
    Get a cached strategy for the given alert type and service.
    
    Returns the most recent non-expired strategy that matches.
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM strategies
            WHERE org_id = $1
              AND alert_type = $2
              AND (service_name = $3 OR service_name = '*')
              AND (expires_at IS NULL OR expires_at > NOW())
            ORDER BY 
                CASE WHEN service_name = $3 THEN 0 ELSE 1 END,
                created_at DESC
            LIMIT 1
            """,
            org_id,
            alert_type,
            service_name,
        )
        
        if row is None:
            return None
        
        return _row_to_strategy(row)


async def upsert_strategy(strategy: StrategyCreate) -> Strategy:
    """Insert or update a strategy (replaces existing for same scope)."""
    async with get_connection() as conn:
        now = datetime.utcnow()
        expires_at = now + timedelta(days=7)
        
        row = await conn.fetchrow(
            """
            INSERT INTO strategies (
                org_id, team_node_id,
                alert_type, service_name, strategy_text,
                source_episode_ids, episode_count,
                created_at, updated_at, expires_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (org_id, alert_type, service_name)
            DO UPDATE SET
                strategy_text = EXCLUDED.strategy_text,
                source_episode_ids = EXCLUDED.source_episode_ids,
                episode_count = EXCLUDED.episode_count,
                updated_at = EXCLUDED.updated_at,
                expires_at = EXCLUDED.expires_at
            RETURNING *
            """,
            strategy.org_id,
            strategy.team_node_id,
            strategy.alert_type,
            strategy.service_name,
            strategy.strategy_text,
            [str(eid) for eid in strategy.source_episode_ids],
            strategy.episode_count,
            now,
            now,
            expires_at,
        )
        
        return _row_to_strategy(row)


async def list_strategies(
    org_id: str = "default",
    alert_type: Optional[str] = None,
    include_expired: bool = False,
) -> list[Strategy]:
    """List all strategies for an organization."""
    conditions = ["org_id = $1"]
    values: list[Any] = [org_id]
    param_idx = 2
    
    if alert_type:
        conditions.append(f"alert_type = ${param_idx}")
        values.append(alert_type)
        param_idx += 1
    
    if not include_expired:
        conditions.append("(expires_at IS NULL OR expires_at > NOW())")
    
    query = f"""
        SELECT * FROM strategies
        WHERE {' AND '.join(conditions)}
        ORDER BY alert_type, service_name
    """
    
    async with get_connection() as conn:
        rows = await conn.fetch(query, *values)
        return [_row_to_strategy(row) for row in rows]


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

async def get_memory_stats(org_id: str = "default") -> MemoryStats:
    """Get comprehensive memory system statistics."""
    async with get_connection() as conn:
        # Basic counts
        counts = await conn.fetchrow(
            """
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE resolved) as resolved,
                COUNT(*) FILTER (WHERE NOT resolved) as unresolved,
                AVG(effectiveness_score) as avg_effectiveness,
                AVG(duration_seconds) FILTER (WHERE duration_seconds IS NOT NULL) as avg_duration,
                MIN(created_at) as oldest,
                MAX(created_at) as newest
            FROM episodes
            WHERE org_id = $1
            """,
            org_id,
        )
        
        # By alert type
        alert_type_counts = await conn.fetch(
            """
            SELECT alert_type, COUNT(*) as count
            FROM episodes
            WHERE org_id = $1
            GROUP BY alert_type
            ORDER BY count DESC
            """,
            org_id,
        )
        
        # Strategy count
        strategy_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM strategies
            WHERE org_id = $1 AND (expires_at IS NULL OR expires_at > NOW())
            """,
            org_id,
        )
        
        return MemoryStats(
            total_episodes=counts["total"] or 0,
            resolved_episodes=counts["resolved"] or 0,
            unresolved_episodes=counts["unresolved"] or 0,
            strategies_count=strategy_count or 0,
            episodes_by_alert_type={row["alert_type"]: row["count"] for row in alert_type_counts},
            avg_effectiveness_score=float(counts["avg_effectiveness"] or 0),
            avg_resolution_time_seconds=float(counts["avg_duration"]) if counts["avg_duration"] else None,
            oldest_episode=counts["oldest"],
            newest_episode=counts["newest"],
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_episode(row: asyncpg.Record) -> Episode:
    """Convert a database row to an Episode model."""
    key_findings = []
    for kf in (row["key_findings"] or []):
        if isinstance(kf, dict):
            key_findings.append(KeyFinding(**kf))
    
    return Episode(
        id=row["id"],
        agent_run_id=row["agent_run_id"],
        org_id=row["org_id"],
        team_node_id=row["team_node_id"],
        alert_type=row["alert_type"],
        alert_description=row["alert_description"],
        severity=Severity(row["severity"]) if row["severity"] else Severity.INFO,
        services=row["services"] or [],
        agents_used=row["agents_used"] or [],
        skills_used=row["skills_used"] or [],
        key_findings=key_findings,
        resolved=row["resolved"],
        root_cause=row["root_cause"],
        summary=row["summary"],
        remediation_steps=row["remediation_steps"] or [],
        effectiveness_score=float(row["effectiveness_score"] or 0),
        confidence=float(row["confidence"] or 0),
        duration_seconds=float(row["duration_seconds"]) if row["duration_seconds"] else None,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_strategy(row: asyncpg.Record) -> Strategy:
    """Convert a database row to a Strategy model."""
    source_ids = []
    for eid in (row["source_episode_ids"] or []):
        try:
            source_ids.append(UUID(eid) if isinstance(eid, str) else eid)
        except (ValueError, TypeError):
            pass
    
    return Strategy(
        id=row["id"],
        org_id=row["org_id"],
        team_node_id=row["team_node_id"],
        alert_type=row["alert_type"],
        service_name=row["service_name"],
        strategy_text=row["strategy_text"],
        source_episode_ids=source_ids,
        episode_count=row["episode_count"] or 0,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        expires_at=row["expires_at"],
    )
