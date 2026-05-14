"""
SRE Knowledge Base for AutoSRE V2.

Stores and retrieves SRE knowledge including runbooks, past incidents,
service documentation, and learned patterns.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class KnowledgeType(str, Enum):
    """Types of knowledge entries."""

    RUNBOOK = "runbook"
    INCIDENT = "incident"
    SERVICE_DOC = "service_doc"
    PATTERN = "pattern"
    ROOT_CAUSE = "root_cause"
    REMEDIATION = "remediation"
    METRIC = "metric"
    ALERT_RULE = "alert_rule"
    TOPOLOGY = "topology"
    CUSTOM = "custom"


class KnowledgeEntry(BaseModel):
    """
    A single knowledge base entry.

    Entries are versioned and can be tagged for easy retrieval.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    type: KnowledgeType
    title: str
    content: str
    summary: str | None = Field(default=None, description="Brief summary for search results")

    # Categorization
    tags: list[str] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list, description="Related services")
    alert_names: list[str] = Field(default_factory=list, description="Related alert names")

    # Metadata
    source: str = Field(default="manual", description="Where this knowledge came from")
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in this knowledge (1.0 for verified)",
    )
    version: int = Field(default=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = Field(default="system")

    # For incidents
    incident_id: str | None = None
    resolution_time_seconds: float | None = None
    was_successful: bool | None = None

    # Embedding for semantic search (optional)
    embedding: list[float] | None = Field(default=None, exclude=True)

    def update(self, **fields: Any) -> None:
        """Update entry fields and bump version."""
        for key, value in fields.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.version += 1
        self.updated_at = datetime.now(timezone.utc)

    def matches_tags(self, required_tags: list[str]) -> bool:
        """Check if entry has all required tags."""
        return all(tag in self.tags for tag in required_tags)

    def matches_service(self, service: str) -> bool:
        """Check if entry is related to a service."""
        return service.lower() in [s.lower() for s in self.services]

    def to_prompt_context(self) -> str:
        """Format for LLM prompt context."""
        lines = [
            f"## {self.title}",
            f"Type: {self.type.value}",
        ]

        if self.summary:
            lines.append(f"Summary: {self.summary}")

        if self.services:
            lines.append(f"Services: {', '.join(self.services)}")

        if self.tags:
            lines.append(f"Tags: {', '.join(self.tags)}")

        lines.append("")
        lines.append(self.content)

        return "\n".join(lines)


class SearchResult(BaseModel):
    """A knowledge search result with relevance score."""

    entry: KnowledgeEntry
    score: float = Field(ge=0.0, le=1.0, description="Relevance score")
    match_reason: str | None = None


class KnowledgeBase:
    """
    SRE Knowledge Base.

    Stores and retrieves knowledge entries with support for:
    - Tag-based filtering
    - Service-based queries
    - Full-text search
    - Semantic search (when embeddings available)
    """

    def __init__(self, storage_path: Path | str | None = None):
        """
        Initialize knowledge base.

        Args:
            storage_path: Path to store knowledge files. Uses memory-only if None.
        """
        self._storage_path = Path(storage_path) if storage_path else None
        self._entries: dict[str, KnowledgeEntry] = {}
        self._index: dict[str, set[str]] = {
            "by_type": {},
            "by_tag": {},
            "by_service": {},
            "by_alert": {},
        }

        if self._storage_path:
            self._storage_path.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    def _load_from_disk(self) -> None:
        """Load entries from disk storage."""
        if not self._storage_path:
            return

        index_file = self._storage_path / "index.json"
        if not index_file.exists():
            return

        try:
            with open(index_file) as f:
                index_data = json.load(f)

            for entry_id in index_data.get("entries", []):
                entry_file = self._storage_path / f"{entry_id}.json"
                if entry_file.exists():
                    with open(entry_file) as f:
                        entry_data = json.load(f)
                    entry = KnowledgeEntry(**entry_data)
                    self._entries[entry.id] = entry
                    self._update_index(entry)

            logger.info(
                "Loaded knowledge base",
                entry_count=len(self._entries),
                path=str(self._storage_path),
            )
        except Exception as e:
            logger.error("Failed to load knowledge base", error=str(e))

    def _save_to_disk(self) -> None:
        """Save entries to disk storage."""
        if not self._storage_path:
            return

        # Save index
        index_file = self._storage_path / "index.json"
        with open(index_file, "w") as f:
            json.dump({"entries": list(self._entries.keys())}, f)

        # Save each entry
        for entry_id, entry in self._entries.items():
            entry_file = self._storage_path / f"{entry_id}.json"
            with open(entry_file, "w") as f:
                json.dump(entry.model_dump(exclude={"embedding"}), f, default=str)

    def _update_index(self, entry: KnowledgeEntry) -> None:
        """Update search indexes for an entry."""
        # Type index
        if entry.type.value not in self._index["by_type"]:
            self._index["by_type"][entry.type.value] = set()
        self._index["by_type"][entry.type.value].add(entry.id)

        # Tag index
        for tag in entry.tags:
            tag_lower = tag.lower()
            if tag_lower not in self._index["by_tag"]:
                self._index["by_tag"][tag_lower] = set()
            self._index["by_tag"][tag_lower].add(entry.id)

        # Service index
        for service in entry.services:
            service_lower = service.lower()
            if service_lower not in self._index["by_service"]:
                self._index["by_service"][service_lower] = set()
            self._index["by_service"][service_lower].add(entry.id)

        # Alert index
        for alert in entry.alert_names:
            alert_lower = alert.lower()
            if alert_lower not in self._index["by_alert"]:
                self._index["by_alert"][alert_lower] = set()
            self._index["by_alert"][alert_lower].add(entry.id)

    def _remove_from_index(self, entry: KnowledgeEntry) -> None:
        """Remove entry from indexes."""
        for index_type in self._index.values():
            for entry_set in index_type.values():
                entry_set.discard(entry.id)

    def add(self, entry: KnowledgeEntry) -> str:
        """
        Add a knowledge entry.

        Args:
            entry: Knowledge entry to add

        Returns:
            Entry ID
        """
        self._entries[entry.id] = entry
        self._update_index(entry)
        self._save_to_disk()

        logger.info(
            "Added knowledge entry",
            entry_id=entry.id,
            type=entry.type.value,
            title=entry.title,
        )
        return entry.id

    def get(self, entry_id: str) -> KnowledgeEntry | None:
        """Get an entry by ID."""
        return self._entries.get(entry_id)

    def update(self, entry_id: str, **fields: Any) -> KnowledgeEntry | None:
        """
        Update an existing entry.

        Args:
            entry_id: ID of entry to update
            **fields: Fields to update

        Returns:
            Updated entry or None if not found
        """
        entry = self._entries.get(entry_id)
        if not entry:
            return None

        self._remove_from_index(entry)
        entry.update(**fields)
        self._update_index(entry)
        self._save_to_disk()

        logger.info("Updated knowledge entry", entry_id=entry_id)
        return entry

    def delete(self, entry_id: str) -> bool:
        """
        Delete an entry.

        Args:
            entry_id: ID of entry to delete

        Returns:
            True if deleted, False if not found
        """
        entry = self._entries.get(entry_id)
        if not entry:
            return False

        self._remove_from_index(entry)
        del self._entries[entry_id]
        self._save_to_disk()

        # Remove file
        if self._storage_path:
            entry_file = self._storage_path / f"{entry_id}.json"
            if entry_file.exists():
                entry_file.unlink()

        logger.info("Deleted knowledge entry", entry_id=entry_id)
        return True

    def search(
        self,
        query: str | None = None,
        types: list[KnowledgeType] | None = None,
        tags: list[str] | None = None,
        services: list[str] | None = None,
        alert_names: list[str] | None = None,
        min_confidence: float = 0.0,
        limit: int = 10,
    ) -> list[SearchResult]:
        """
        Search knowledge base.

        Args:
            query: Full-text search query
            types: Filter by knowledge types
            tags: Filter by tags (AND logic)
            services: Filter by related services (OR logic)
            alert_names: Filter by related alerts (OR logic)
            min_confidence: Minimum confidence threshold
            limit: Maximum results to return

        Returns:
            List of search results with relevance scores
        """
        # Start with all entries or filter by type
        if types:
            candidate_ids: set[str] = set()
            for kt in types:
                candidate_ids.update(
                    self._index["by_type"].get(kt.value, set())
                )
        else:
            candidate_ids = set(self._entries.keys())

        # Filter by tags (AND logic)
        if tags:
            for tag in tags:
                tag_matches = self._index["by_tag"].get(tag.lower(), set())
                candidate_ids &= tag_matches

        # Filter by services (OR logic)
        if services:
            service_matches: set[str] = set()
            for service in services:
                service_matches.update(
                    self._index["by_service"].get(service.lower(), set())
                )
            candidate_ids &= service_matches

        # Filter by alerts (OR logic)
        if alert_names:
            alert_matches: set[str] = set()
            for alert in alert_names:
                alert_matches.update(
                    self._index["by_alert"].get(alert.lower(), set())
                )
            candidate_ids &= alert_matches

        # Get entries and filter by confidence
        results: list[SearchResult] = []
        for entry_id in candidate_ids:
            entry = self._entries.get(entry_id)
            if not entry or entry.confidence < min_confidence:
                continue

            # Calculate relevance score
            score = self._calculate_relevance(entry, query, tags, services, alert_names)

            results.append(SearchResult(
                entry=entry,
                score=score,
                match_reason=self._get_match_reason(entry, query, tags, services, alert_names),
            ))

        # Sort by score and limit
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def _calculate_relevance(
        self,
        entry: KnowledgeEntry,
        query: str | None,
        tags: list[str] | None,
        services: list[str] | None,
        alert_names: list[str] | None,
    ) -> float:
        """Calculate relevance score for an entry."""
        score = 0.5  # Base score

        # Text match boost
        if query:
            query_lower = query.lower()
            if query_lower in entry.title.lower():
                score += 0.3
            if query_lower in entry.content.lower():
                score += 0.1
            if entry.summary and query_lower in entry.summary.lower():
                score += 0.1

        # Exact tag match boost
        if tags:
            matching_tags = sum(1 for t in tags if t.lower() in [tag.lower() for tag in entry.tags])
            score += 0.05 * matching_tags

        # Service match boost
        if services:
            matching_services = sum(1 for s in services if entry.matches_service(s))
            score += 0.1 * matching_services

        # Alert match boost (high value)
        if alert_names:
            matching_alerts = sum(
                1 for a in alert_names
                if a.lower() in [alert.lower() for alert in entry.alert_names]
            )
            score += 0.15 * matching_alerts

        # Recency boost (newer = higher)
        days_old = (datetime.now(timezone.utc) - entry.updated_at).days
        if days_old < 7:
            score += 0.1
        elif days_old < 30:
            score += 0.05

        # Confidence factor
        score *= entry.confidence

        return min(score, 1.0)

    def _get_match_reason(
        self,
        entry: KnowledgeEntry,
        query: str | None,
        tags: list[str] | None,
        services: list[str] | None,
        alert_names: list[str] | None,
    ) -> str:
        """Generate human-readable match reason."""
        reasons = []

        if query and query.lower() in entry.title.lower():
            reasons.append("title match")
        if tags:
            matching = [t for t in tags if t.lower() in [tag.lower() for tag in entry.tags]]
            if matching:
                reasons.append(f"tags: {', '.join(matching)}")
        if services:
            matching = [s for s in services if entry.matches_service(s)]
            if matching:
                reasons.append(f"services: {', '.join(matching)}")
        if alert_names:
            matching = [a for a in alert_names if a.lower() in [alert.lower() for alert in entry.alert_names]]
            if matching:
                reasons.append(f"alerts: {', '.join(matching)}")

        return "; ".join(reasons) if reasons else "general match"

    def find_related(
        self,
        entry_id: str,
        limit: int = 5,
    ) -> list[SearchResult]:
        """
        Find entries related to a given entry.

        Uses shared tags, services, and alerts to find related content.
        """
        entry = self._entries.get(entry_id)
        if not entry:
            return []

        return self.search(
            tags=entry.tags[:3] if entry.tags else None,
            services=entry.services[:2] if entry.services else None,
            alert_names=entry.alert_names[:2] if entry.alert_names else None,
            limit=limit + 1,  # +1 to account for self
        )

    def get_for_alert(
        self,
        alert_name: str,
        service: str | None = None,
        limit: int = 5,
    ) -> list[SearchResult]:
        """
        Get knowledge relevant to a specific alert.

        Prioritizes:
        1. Exact alert name matches
        2. Service-related runbooks
        3. Similar incident patterns
        """
        results = self.search(
            alert_names=[alert_name],
            services=[service] if service else None,
            types=[
                KnowledgeType.RUNBOOK,
                KnowledgeType.INCIDENT,
                KnowledgeType.ROOT_CAUSE,
            ],
            limit=limit,
        )

        # If not enough results, broaden search
        if len(results) < limit and service:
            additional = self.search(
                services=[service],
                types=[KnowledgeType.RUNBOOK, KnowledgeType.SERVICE_DOC],
                limit=limit - len(results),
            )
            # Deduplicate
            existing_ids = {r.entry.id for r in results}
            for result in additional:
                if result.entry.id not in existing_ids:
                    results.append(result)

        return results[:limit]

    def record_incident(
        self,
        alert_name: str,
        service: str,
        root_cause: str,
        resolution: str,
        was_successful: bool,
        resolution_time_seconds: float,
        tags: list[str] | None = None,
    ) -> str:
        """
        Record a past incident for future reference.

        This creates a knowledge entry that can be used by the
        investigation system to learn from past incidents.
        """
        entry = KnowledgeEntry(
            type=KnowledgeType.INCIDENT,
            title=f"Incident: {alert_name} in {service}",
            content=f"Root Cause:\n{root_cause}\n\nResolution:\n{resolution}",
            summary=f"{'Resolved' if was_successful else 'Unresolved'}: {root_cause[:100]}",
            tags=tags or [],
            services=[service],
            alert_names=[alert_name],
            source="investigation",
            confidence=0.9 if was_successful else 0.5,
            was_successful=was_successful,
            resolution_time_seconds=resolution_time_seconds,
        )

        return self.add(entry)

    def add_runbook(
        self,
        title: str,
        content: str,
        services: list[str],
        alert_names: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """Add a runbook to the knowledge base."""
        entry = KnowledgeEntry(
            type=KnowledgeType.RUNBOOK,
            title=title,
            content=content,
            services=services,
            alert_names=alert_names or [],
            tags=tags or ["runbook"],
            source="manual",
            confidence=1.0,
        )
        return self.add(entry)

    def add_pattern(
        self,
        title: str,
        description: str,
        indicators: list[str],
        root_cause: str,
        remediation: str,
        services: list[str] | None = None,
        confidence: float = 0.8,
    ) -> str:
        """
        Add a learned pattern to the knowledge base.

        Patterns are used to recognize common failure modes.
        """
        content = f"""## Indicators
{chr(10).join(f'- {i}' for i in indicators)}

## Root Cause
{root_cause}

## Remediation
{remediation}
"""
        entry = KnowledgeEntry(
            type=KnowledgeType.PATTERN,
            title=title,
            content=content,
            summary=description,
            services=services or [],
            tags=["pattern", "learned"],
            source="pattern_learning",
            confidence=confidence,
        )
        return self.add(entry)

    @property
    def stats(self) -> dict[str, Any]:
        """Get knowledge base statistics."""
        type_counts = {}
        for entry in self._entries.values():
            type_counts[entry.type.value] = type_counts.get(entry.type.value, 0) + 1

        return {
            "total_entries": len(self._entries),
            "by_type": type_counts,
            "unique_services": len(self._index["by_service"]),
            "unique_tags": len(self._index["by_tag"]),
            "unique_alerts": len(self._index["by_alert"]),
        }
