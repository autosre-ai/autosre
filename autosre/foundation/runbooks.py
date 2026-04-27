"""
Runbook Indexer - Find and match runbooks to incidents.

Runbooks contain documented remediation procedures.
This module:
- Indexes runbooks for search
- Matches alerts to relevant runbooks
- Tracks runbook effectiveness
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import re

import yaml

from autosre.foundation.models import Runbook, Alert
from autosre.foundation.context_store import ContextStore


class RunbookIndexer:
    """
    Runbook indexer and matcher.
    
    Indexes runbooks and matches them to alerts/incidents
    for remediation guidance.
    """
    
    def __init__(self, context_store: ContextStore):
        """
        Initialize with a context store.
        
        Args:
            context_store: The ContextStore to read/write runbooks
        """
        self.context_store = context_store
    
    def add_runbook(self, runbook: Runbook) -> None:
        """
        Add or update a runbook.
        
        Args:
            runbook: The runbook to add
        """
        self.context_store.add_runbook(runbook)
    
    def load_from_directory(self, directory: str | Path) -> int:
        """
        Load runbooks from a directory of YAML/Markdown files.
        
        Supported formats:
        - .yaml/.yml: Structured runbook definition
        - .md: Markdown with frontmatter
        
        Args:
            directory: Path to runbook directory
            
        Returns:
            Number of runbooks loaded
        """
        directory = Path(directory)
        count = 0
        
        for path in directory.rglob("*"):
            if path.suffix in [".yaml", ".yml"]:
                runbook = self._load_yaml_runbook(path)
                if runbook:
                    self.add_runbook(runbook)
                    count += 1
            elif path.suffix == ".md":
                runbook = self._load_markdown_runbook(path)
                if runbook:
                    self.add_runbook(runbook)
                    count += 1
        
        return count
    
    def _load_yaml_runbook(self, path: Path) -> Optional[Runbook]:
        """Load a runbook from YAML file."""
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            
            if not data:
                return None
            
            return Runbook(
                id=data.get("id", path.stem),
                title=data.get("title", path.stem),
                alert_names=data.get("alert_names", []),
                services=data.get("services", []),
                keywords=data.get("keywords", []),
                description=data.get("description", ""),
                steps=data.get("steps", []),
                automated=data.get("automated", False),
                automation_script=data.get("automation_script"),
                requires_approval=data.get("requires_approval", True),
                author=data.get("author"),
                last_updated=datetime.now(timezone.utc),
            )
        except Exception:
            return None
    
    def _load_markdown_runbook(self, path: Path) -> Optional[Runbook]:
        """Load a runbook from Markdown with YAML frontmatter."""
        try:
            content = path.read_text()
            
            # Extract YAML frontmatter
            frontmatter = {}
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    content = parts[2]
            
            # Extract steps from numbered lists
            steps = []
            for line in content.split("\n"):
                # Match numbered list items
                match = re.match(r"^\s*\d+\.\s+(.+)$", line)
                if match:
                    steps.append(match.group(1).strip())
            
            # Extract title from first H1
            title = frontmatter.get("title", path.stem)
            for line in content.split("\n"):
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
            
            return Runbook(
                id=frontmatter.get("id", path.stem),
                title=title,
                alert_names=frontmatter.get("alert_names", []),
                services=frontmatter.get("services", []),
                keywords=frontmatter.get("keywords", []),
                description=frontmatter.get("description", ""),
                steps=steps if steps else frontmatter.get("steps", []),
                automated=frontmatter.get("automated", False),
                automation_script=frontmatter.get("automation_script"),
                requires_approval=frontmatter.get("requires_approval", True),
                author=frontmatter.get("author"),
                last_updated=datetime.now(timezone.utc),
            )
        except Exception:
            return None
    
    def find_for_alert(self, alert: Alert) -> list[Runbook]:
        """
        Find runbooks that match an alert.
        
        Matching strategy:
        1. Exact alert name match
        2. Service match
        3. Keyword match in alert summary/description
        
        Args:
            alert: The alert to match
            
        Returns:
            List of matching runbooks, best match first
        """
        # Get all runbooks
        all_runbooks = self.context_store.find_runbook()
        
        scored = []
        for runbook in all_runbooks:
            score = self._score_match(runbook, alert)
            if score > 0:
                scored.append((runbook, score))
        
        # Sort by score
        scored.sort(key=lambda x: -x[1])
        
        return [r for r, _ in scored]
    
    def _score_match(self, runbook: Runbook, alert: Alert) -> float:
        """Score how well a runbook matches an alert."""
        score = 0.0
        
        # Exact alert name match (highest priority)
        if alert.name in runbook.alert_names:
            score += 10.0
        
        # Partial alert name match
        for alert_pattern in runbook.alert_names:
            if alert_pattern.lower() in alert.name.lower():
                score += 5.0
                break
        
        # Service match
        if alert.service_name and alert.service_name in runbook.services:
            score += 8.0
        
        # Keyword match in summary/description
        text = f"{alert.summary} {alert.description or ''}".lower()
        for keyword in runbook.keywords:
            if keyword.lower() in text:
                score += 2.0
        
        # Label matches
        for label_value in alert.labels.values():
            for keyword in runbook.keywords:
                if keyword.lower() in str(label_value).lower():
                    score += 1.0
        
        return score
    
    def search(self, query: str) -> list[Runbook]:
        """
        Search runbooks by text query.
        
        Args:
            query: Search query
            
        Returns:
            List of matching runbooks
        """
        all_runbooks = self.context_store.find_runbook()
        query_lower = query.lower()
        
        matches = []
        for runbook in all_runbooks:
            # Search in title, description, keywords
            searchable = " ".join([
                runbook.title,
                runbook.description,
                " ".join(runbook.keywords),
                " ".join(runbook.alert_names),
                " ".join(runbook.services),
            ]).lower()
            
            if query_lower in searchable:
                matches.append(runbook)
        
        return matches
    
    def list_all(self) -> list[Runbook]:
        """List all indexed runbooks."""
        return self.context_store.find_runbook()
    
    def get_by_id(self, runbook_id: str) -> Optional[Runbook]:
        """Get a specific runbook by ID."""
        runbooks = self.context_store.find_runbook()
        for rb in runbooks:
            if rb.id == runbook_id:
                return rb
        return None
    
    def record_usage(self, runbook_id: str, successful: bool) -> None:
        """
        Record that a runbook was used.
        
        Updates the success rate for the runbook.
        
        Args:
            runbook_id: ID of the runbook
            successful: Whether the remediation was successful
        """
        runbook = self.get_by_id(runbook_id)
        if not runbook:
            return
        
        # Simple success rate update
        # In a real implementation, we'd track individual uses
        current_rate = runbook.success_rate or 0.5
        # Weighted moving average
        new_rate = (current_rate * 0.9) + (1.0 if successful else 0.0) * 0.1
        
        runbook.success_rate = new_rate
        runbook.last_updated = datetime.now(timezone.utc)
        self.add_runbook(runbook)
