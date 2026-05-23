"""Memory service - manages episodes and strategies."""

from datetime import datetime, timedelta, timezone
from typing import Any
import uuid

import structlog

from ..models.memory import (
    Episode,
    EpisodeList,
    EpisodeSearch,
    EpisodeSearchResults,
    EpisodeMatch,
    EpisodeOutcome,
    Strategy,
    StrategyList,
    StrategyType,
    MemoryStats,
)

logger = structlog.get_logger()


class MemoryService:
    """Service for managing episodic memory and learned strategies."""

    def __init__(self) -> None:
        # In production, backed by PostgreSQL + vector database
        self._episodes: dict[str, Episode] = {}
        self._strategies: dict[str, Strategy] = {}
        self._initialize_sample_data()

    def _initialize_sample_data(self) -> None:
        """Initialize with sample data for demonstration."""
        # Sample episodes
        sample_episodes = [
            Episode(
                episode_id="ep-001",
                investigation_id="inv-sample-001",
                service="api-gateway",
                alert_type="high_error_rate",
                symptoms=[
                    "Error rate > 5%",
                    "p99 latency increased 300%",
                    "Recent deployment 15 minutes prior",
                ],
                root_cause="Memory leak in connection pool",
                resolution="Rolled back deployment, patched memory leak",
                outcome=EpisodeOutcome.RESOLVED,
                duration_seconds=847,
                created_at=datetime.now(timezone.utc) - timedelta(days=3),
                feedback_rating=4,
                tags=["deployment", "memory-leak", "rollback"],
            ),
            Episode(
                episode_id="ep-002",
                investigation_id="inv-sample-002",
                service="auth-service",
                alert_type="latency_spike",
                symptoms=[
                    "p99 latency > 2s",
                    "Database connection pool exhausted",
                    "High CPU on database replica",
                ],
                root_cause="Missing index on user lookup query",
                resolution="Added composite index, latency normalized",
                outcome=EpisodeOutcome.RESOLVED,
                duration_seconds=1234,
                created_at=datetime.now(timezone.utc) - timedelta(days=7),
                feedback_rating=5,
                tags=["database", "index", "performance"],
            ),
        ]

        for ep in sample_episodes:
            self._episodes[ep.episode_id] = ep

        # Sample strategies
        sample_strategies = [
            Strategy(
                strategy_id="strat-001",
                name="Post-Deployment Error Spike",
                description="Handle error rate increases following deployments",
                strategy_type=StrategyType.DIAGNOSTIC,
                applicable_to=["high_error_rate", "latency_spike"],
                conditions={"recent_deployment": True, "error_rate_increase": "> 100%"},
                steps=[
                    "Check deployment timeline in last 30 minutes",
                    "Compare error rates before and after deployment",
                    "Identify changed services",
                    "Review deployment diff for risky changes",
                    "Assess rollback feasibility",
                ],
                success_rate=0.87,
                avg_resolution_time=600,
                learned_from=["ep-001"],
                created_at=datetime.now(timezone.utc) - timedelta(days=30),
                updated_at=datetime.now(timezone.utc) - timedelta(days=1),
                usage_count=23,
            ),
            Strategy(
                strategy_id="strat-002",
                name="Database Performance Degradation",
                description="Diagnose slow database queries and connection issues",
                strategy_type=StrategyType.DIAGNOSTIC,
                applicable_to=["latency_spike", "database_error"],
                conditions={"database_latency_increase": "> 200%"},
                steps=[
                    "Check database connection pool utilization",
                    "Identify slow queries from database logs",
                    "Review query execution plans",
                    "Check for missing indexes",
                    "Verify replica lag",
                ],
                success_rate=0.79,
                avg_resolution_time=900,
                learned_from=["ep-002"],
                created_at=datetime.now(timezone.utc) - timedelta(days=20),
                updated_at=datetime.now(timezone.utc) - timedelta(days=5),
                usage_count=15,
            ),
        ]

        for strat in sample_strategies:
            self._strategies[strat.strategy_id] = strat

    async def list_episodes(
        self,
        service: str | None = None,
        outcome: EpisodeOutcome | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> EpisodeList:
        """List episodes with optional filters."""
        episodes = list(self._episodes.values())

        # Apply filters
        if service:
            episodes = [e for e in episodes if e.service == service]
        if outcome:
            episodes = [e for e in episodes if e.outcome == outcome]
        if date_from:
            episodes = [e for e in episodes if e.created_at >= date_from]
        if date_to:
            episodes = [e for e in episodes if e.created_at <= date_to]

        # Sort by date descending
        episodes.sort(key=lambda x: x.created_at, reverse=True)

        total = len(episodes)
        start = (page - 1) * page_size
        end = start + page_size
        page_episodes = episodes[start:end]

        return EpisodeList(
            episodes=page_episodes,
            total=total,
            page=page,
            page_size=page_size,
            has_more=end < total,
        )

    async def get_episode(self, episode_id: str) -> Episode | None:
        """Get a specific episode by ID."""
        return self._episodes.get(episode_id)

    async def search_episodes(self, search: EpisodeSearch) -> EpisodeSearchResults:
        """Search episodes using semantic or keyword search."""
        results: list[EpisodeMatch] = []

        # Simple keyword matching (in production: vector similarity search)
        query_lower = search.query.lower()

        for episode in self._episodes.values():
            # Apply filters
            if search.service and episode.service != search.service:
                continue
            if search.alert_type and episode.alert_type != search.alert_type:
                continue
            if search.outcome and episode.outcome != search.outcome:
                continue
            if search.min_rating and (
                not episode.feedback_rating or episode.feedback_rating < search.min_rating
            ):
                continue
            if search.date_from and episode.created_at < search.date_from:
                continue
            if search.date_to and episode.created_at > search.date_to:
                continue

            # Calculate match score (simplified)
            score = 0.0
            matched_on = []

            # Check symptoms
            for symptom in episode.symptoms:
                if query_lower in symptom.lower():
                    score += 0.3
                    matched_on.append("symptoms")
                    break

            # Check root cause
            if episode.root_cause and query_lower in episode.root_cause.lower():
                score += 0.4
                matched_on.append("root_cause")

            # Check tags
            for tag in episode.tags:
                if query_lower in tag.lower():
                    score += 0.2
                    matched_on.append("tags")
                    break

            # Check service/alert type match
            if query_lower in episode.service.lower():
                score += 0.1
                matched_on.append("service")

            if score > 0:
                results.append(
                    EpisodeMatch(
                        episode=episode,
                        score=min(score, 1.0),
                        matched_on=matched_on,
                    )
                )

        # Sort by score descending
        results.sort(key=lambda x: x.score, reverse=True)
        results = results[: search.limit]

        return EpisodeSearchResults(
            results=results,
            query=search.query,
            search_type="semantic" if search.use_semantic else "keyword",
            total_matches=len(results),
        )

    async def create_episode(self, episode: Episode) -> Episode:
        """Store a new episode."""
        if not episode.episode_id:
            episode.episode_id = f"ep-{uuid.uuid4().hex[:8]}"

        self._episodes[episode.episode_id] = episode

        logger.info(
            "episode_created",
            episode_id=episode.episode_id,
            service=episode.service,
            outcome=episode.outcome,
        )

        return episode

    async def list_strategies(
        self,
        strategy_type: StrategyType | None = None,
        service: str | None = None,
    ) -> StrategyList:
        """List learned strategies."""
        strategies = list(self._strategies.values())

        if strategy_type:
            strategies = [s for s in strategies if s.strategy_type == strategy_type]
        if service:
            strategies = [
                s for s in strategies
                if not s.applicable_to or service in s.applicable_to
            ]

        # Sort by success rate descending
        strategies.sort(key=lambda x: x.success_rate, reverse=True)

        return StrategyList(
            strategies=strategies,
            total=len(strategies),
        )

    async def get_strategy(self, strategy_id: str) -> Strategy | None:
        """Get a specific strategy by ID."""
        return self._strategies.get(strategy_id)

    async def get_stats(self) -> MemoryStats:
        """Get memory system statistics."""
        episodes = list(self._episodes.values())
        strategies = list(self._strategies.values())

        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)

        recent_episodes = [e for e in episodes if e.created_at >= week_ago]

        # Calculate success rate
        resolved = len([e for e in episodes if e.outcome == EpisodeOutcome.RESOLVED])
        success_rate = resolved / len(episodes) if episodes else 0.0

        # Average resolution time
        durations = [e.duration_seconds for e in episodes]
        avg_duration = sum(durations) / len(durations) if durations else 0.0

        # Top services
        service_counts: dict[str, int] = {}
        for e in episodes:
            service_counts[e.service] = service_counts.get(e.service, 0) + 1

        top_services = [
            {"service": k, "count": v}
            for k, v in sorted(service_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

        # Top alert types
        type_counts: dict[str, int] = {}
        for e in episodes:
            type_counts[e.alert_type] = type_counts.get(e.alert_type, 0) + 1

        top_types = [
            {"type": k, "count": v}
            for k, v in sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

        # Feedback summary
        feedback: dict[str, int] = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
        for e in episodes:
            if e.feedback_rating:
                feedback[str(e.feedback_rating)] = feedback.get(str(e.feedback_rating), 0) + 1

        return MemoryStats(
            total_episodes=len(episodes),
            total_strategies=len(strategies),
            episodes_last_7_days=len(recent_episodes),
            avg_resolution_time=avg_duration,
            success_rate=success_rate,
            top_services=top_services,
            top_alert_types=top_types,
            feedback_summary=feedback,
            storage_size_mb=0.5,  # Placeholder
        )
