"""
RunbookManager - Loads, indexes, and retrieves runbooks for context-aware troubleshooting.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Runbook:
    """A runbook document with metadata."""
    name: str
    path: str
    content: str
    symptoms: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    @property
    def title(self) -> str:
        """Extract title from content (first H1)."""
        for line in self.content.split("\n"):
            if line.startswith("# "):
                return line[2:].strip()
        return self.name.replace("-", " ").title()

    @property
    def summary(self) -> str:
        """Get a brief summary (first paragraph after title)."""
        lines = self.content.split("\n")
        in_content = False
        summary_lines = []

        for line in lines:
            if line.startswith("# "):
                in_content = True
                continue
            if in_content:
                if line.strip() == "" and summary_lines:
                    break
                if line.strip() and not line.startswith("#"):
                    summary_lines.append(line.strip())

        return " ".join(summary_lines)[:200]


class RunbookManager:
    """
    Manages runbook loading, indexing, and retrieval.

    Runbooks are markdown files with YAML frontmatter:

    ---
    symptoms: high memory, OOMKilled, memory leak
    services: any
    tags: memory, resource, oom
    ---

    # High Memory Usage / OOMKilled
    ...
    """

    def __init__(self, runbook_dir: str | Path = "runbooks"):
        self.runbook_dir = Path(runbook_dir)
        self.runbooks: dict[str, Runbook] = {}
        self._keyword_index: dict[str, set[str]] = {}  # keyword -> set of runbook names
        self._load_runbooks()

    def _load_runbooks(self):
        """Load all runbooks from directory."""
        if not self.runbook_dir.exists():
            self.runbook_dir.mkdir(parents=True)
            return

        for path in self.runbook_dir.glob("**/*.md"):
            try:
                runbook = self._parse_runbook(path)
                self.runbooks[runbook.name] = runbook
                self._index_runbook(runbook)
            except Exception as e:
                print(f"Warning: Failed to load runbook {path}: {e}")

    def _parse_runbook(self, path: Path) -> Runbook:
        """Parse a runbook markdown file."""
        raw_content = path.read_text()

        # Extract frontmatter (YAML between ---)
        symptoms: list[str] = []
        services: list[str] = []
        tags: list[str] = []
        content = raw_content

        if raw_content.startswith("---"):
            parts = raw_content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1]
                content = parts[2].strip()

                # Parse YAML-like frontmatter
                for line in frontmatter.strip().split("\n"):
                    line = line.strip()
                    if line.startswith("symptoms:"):
                        symptoms = [s.strip() for s in line.split(":", 1)[1].split(",") if s.strip()]
                    elif line.startswith("services:"):
                        services = [s.strip() for s in line.split(":", 1)[1].split(",") if s.strip()]
                    elif line.startswith("tags:"):
                        tags = [t.strip() for t in line.split(":", 1)[1].split(",") if t.strip()]

        return Runbook(
            name=path.stem,
            path=str(path),
            content=content,
            symptoms=symptoms,
            services=services,
            tags=tags,
        )

    def _index_runbook(self, runbook: Runbook):
        """Build keyword index for a runbook."""
        # Index symptoms
        for symptom in runbook.symptoms:
            for word in self._tokenize(symptom):
                self._add_to_index(word, runbook.name)

        # Index tags
        for tag in runbook.tags:
            for word in self._tokenize(tag):
                self._add_to_index(word, runbook.name)

        # Index services
        for service in runbook.services:
            if service.lower() != "any":
                for word in self._tokenize(service):
                    self._add_to_index(word, runbook.name)

        # Index title words
        for word in self._tokenize(runbook.title):
            self._add_to_index(word, runbook.name)

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into searchable words."""
        # Split on non-alphanumeric, lowercase, filter short words
        words = re.split(r"[^a-zA-Z0-9]+", text.lower())
        return [w for w in words if len(w) >= 2]

    def _add_to_index(self, keyword: str, runbook_name: str):
        """Add a keyword -> runbook mapping."""
        if keyword not in self._keyword_index:
            self._keyword_index[keyword] = set()
        self._keyword_index[keyword].add(runbook_name)

    def find_relevant(
        self,
        issue: str,
        observations: list[str] | None = None,
        limit: int = 3,
    ) -> list[Runbook]:
        """
        Find runbooks relevant to an issue.

        Scoring:
        - +3 points for service name match
        - +2 points for symptom match
        - +1 point for tag match
        - +1 point for keyword match in issue/observations

        Returns top N runbooks sorted by relevance score.
        """
        observations = observations or []
        relevant: list[tuple[int, Runbook]] = []

        issue_lower = issue.lower()
        obs_text = " ".join(observations).lower()
        combined_text = f"{issue_lower} {obs_text}"

        for runbook in self.runbooks.values():
            score = 0

            # Check symptoms (high value)
            for symptom in runbook.symptoms:
                symptom_lower = symptom.lower()
                if symptom_lower in issue_lower:
                    score += 3
                elif symptom_lower in obs_text:
                    score += 2
                # Partial match (any symptom word appears)
                elif any(word in combined_text for word in self._tokenize(symptom_lower)):
                    score += 1

            # Check tags (medium value)
            for tag in runbook.tags:
                tag_lower = tag.lower()
                if tag_lower in combined_text:
                    score += 2

            # Check services (high value for specific matches)
            for service in runbook.services:
                if service.lower() == "any":
                    continue
                if service.lower() in issue_lower:
                    score += 4

            # Keyword matching from index
            issue_tokens = self._tokenize(combined_text)
            for token in issue_tokens:
                if token in self._keyword_index:
                    if runbook.name in self._keyword_index[token]:
                        score += 1

            if score > 0:
                relevant.append((score, runbook))

        # Sort by score descending
        relevant.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in relevant[:limit]]

    def search(self, query: str) -> list[Runbook]:
        """Search runbooks by query string."""
        return self.find_relevant(query, limit=10)

    def get_context(self, runbooks: list[Runbook], max_length: int = 3000) -> str:
        """
        Build context string from runbooks for LLM.

        Produces a formatted string that can be injected into the
        reasoning prompt to provide relevant troubleshooting guidance.
        """
        if not runbooks:
            return "No relevant runbooks found."

        parts = ["## Relevant Runbooks\n"]
        total_length = len(parts[0])

        for rb in runbooks:
            header = f"\n### {rb.title}\n"
            header += f"*Tags: {', '.join(rb.tags)}*\n\n"

            # Include content up to a reasonable limit
            available = max_length - total_length - len(header) - 100
            if available <= 0:
                break

            content = rb.content
            if len(content) > available // len(runbooks):
                content = content[:available // len(runbooks)] + "\n...(truncated)"

            section = header + content
            parts.append(section)
            total_length += len(section)

        return "\n".join(parts)

    def get(self, name: str) -> Optional[Runbook]:
        """Get a runbook by name."""
        return self.runbooks.get(name)

    def list_all(self) -> list[Runbook]:
        """List all runbooks."""
        return list(self.runbooks.values())

    def add_runbook(self, path: Path | str) -> Runbook:
        """Add a runbook from a file path."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Runbook not found: {path}")

        runbook = self._parse_runbook(path)
        self.runbooks[runbook.name] = runbook
        self._index_runbook(runbook)
        return runbook

    def reload(self):
        """Reload all runbooks from disk."""
        self.runbooks.clear()
        self._keyword_index.clear()
        self._load_runbooks()
