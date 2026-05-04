"""
Skills Registry — Dynamic skill discovery and loading.

Skills are pluggable investigation capabilities (like OpenSRE's skill system).
Each skill is a directory containing:
- SKILL.md: Documentation with YAML frontmatter
- Scripts or tools for investigation
"""

import logging
import re
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field
import yaml

logger = logging.getLogger(__name__)


class SkillMetadata(BaseModel):
    """Metadata from SKILL.md frontmatter."""
    
    name: str
    description: str = ""
    version: str = "1.0.0"
    author: str = ""
    category: str = "general"
    tags: list[str] = Field(default_factory=list)
    requires: list[str] = Field(default_factory=list)  # Required tools/binaries
    
    # Skill configuration
    enabled: bool = True
    agents: list[str] = Field(default_factory=list)  # Which agents can use this


class Skill(BaseModel):
    """A loaded skill."""
    
    id: str  # Directory name
    path: Path
    metadata: SkillMetadata
    readme: str = ""  # Full SKILL.md content
    
    def get_scripts(self) -> list[Path]:
        """Get all executable scripts in the skill directory."""
        scripts = []
        for ext in ["*.sh", "*.py", "*.js"]:
            scripts.extend(self.path.glob(ext))
        return sorted(scripts)
    
    def to_catalog_entry(self) -> str:
        """Format for skill catalog prompt."""
        return f"""### {self.metadata.name}
{self.metadata.description}
- Category: {self.metadata.category}
- Tags: {', '.join(self.metadata.tags) if self.metadata.tags else 'none'}
"""


class SkillRegistry:
    """Registry of available investigation skills.
    
    Discovers skills from a directory structure like:
    
        skills/
        ├── kubernetes/
        │   ├── SKILL.md
        │   ├── get_pods.sh
        │   └── describe_resource.py
        ├── prometheus/
        │   ├── SKILL.md
        │   └── query.sh
        ...
    """
    
    def __init__(self, skills_dir: Path | str = "skills"):
        self.skills_dir = Path(skills_dir)
        self._skills: dict[str, Skill] = {}
        self._loaded = False
    
    def load(self) -> None:
        """Load all skills from the skills directory."""
        if not self.skills_dir.exists():
            logger.warning(f"[SKILLS] Directory not found: {self.skills_dir}")
            self._loaded = True
            return
        
        for skill_dir in sorted(self.skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            
            try:
                skill = self._load_skill(skill_dir, skill_md)
                self._skills[skill.id] = skill
                logger.debug(f"[SKILLS] Loaded: {skill.id} ({skill.metadata.name})")
            except Exception as e:
                logger.warning(f"[SKILLS] Failed to load {skill_dir.name}: {e}")
        
        self._loaded = True
        logger.info(f"[SKILLS] Loaded {len(self._skills)} skills from {self.skills_dir}")
    
    def _load_skill(self, skill_dir: Path, skill_md: Path) -> Skill:
        """Load a single skill from its directory."""
        content = skill_md.read_text(encoding="utf-8")
        
        # Parse YAML frontmatter
        metadata_dict = {}
        readme = content
        
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", content, re.DOTALL)
        if match:
            try:
                metadata_dict = yaml.safe_load(match.group(1)) or {}
            except yaml.YAMLError:
                pass
            readme = content[match.end():]
        
        # Ensure name exists
        if "name" not in metadata_dict:
            metadata_dict["name"] = skill_dir.name
        
        metadata = SkillMetadata(**metadata_dict)
        
        return Skill(
            id=skill_dir.name,
            path=skill_dir,
            metadata=metadata,
            readme=readme.strip(),
        )
    
    def get(self, skill_id: str) -> Optional[Skill]:
        """Get a skill by ID."""
        if not self._loaded:
            self.load()
        return self._skills.get(skill_id)
    
    def list(self) -> list[Skill]:
        """List all loaded skills."""
        if not self._loaded:
            self.load()
        return list(self._skills.values())
    
    def list_ids(self) -> list[str]:
        """List all skill IDs."""
        if not self._loaded:
            self.load()
        return list(self._skills.keys())
    
    def filter_by_agent(self, agent_id: str) -> list[Skill]:
        """Get skills available to a specific agent."""
        if not self._loaded:
            self.load()
        
        result = []
        for skill in self._skills.values():
            if not skill.metadata.agents or agent_id in skill.metadata.agents:
                result.append(skill)
        return result
    
    def filter_by_category(self, category: str) -> list[Skill]:
        """Get skills in a specific category."""
        if not self._loaded:
            self.load()
        return [s for s in self._skills.values() if s.metadata.category == category]
    
    def get_catalog(
        self,
        agent_id: Optional[str] = None,
        enabled_only: bool = True,
    ) -> str:
        """Generate skill catalog text for LLM prompts.
        
        Args:
            agent_id: Filter to skills for this agent.
            enabled_only: Only include enabled skills.
            
        Returns:
            Markdown-formatted skill catalog.
        """
        if not self._loaded:
            self.load()
        
        skills = list(self._skills.values())
        
        if agent_id:
            skills = [s for s in skills 
                     if not s.metadata.agents or agent_id in s.metadata.agents]
        
        if enabled_only:
            skills = [s for s in skills if s.metadata.enabled]
        
        if not skills:
            return "No skills available."
        
        lines = ["# Available Skills\n"]
        
        # Group by category
        categories: dict[str, list[Skill]] = {}
        for skill in skills:
            cat = skill.metadata.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(skill)
        
        for category in sorted(categories.keys()):
            lines.append(f"## {category.title()}\n")
            for skill in categories[category]:
                lines.append(skill.to_catalog_entry())
        
        return "\n".join(lines)
    
    def __len__(self) -> int:
        if not self._loaded:
            self.load()
        return len(self._skills)
    
    def __contains__(self, skill_id: str) -> bool:
        if not self._loaded:
            self.load()
        return skill_id in self._skills


# Global registry instance
_registry: Optional[SkillRegistry] = None


def get_skill_registry(skills_dir: Optional[Path | str] = None) -> SkillRegistry:
    """Get global skill registry."""
    global _registry
    if _registry is None or skills_dir is not None:
        _registry = SkillRegistry(skills_dir or "skills")
        _registry.load()
    return _registry


def load_skills(skills_dir: Path | str) -> SkillRegistry:
    """Load skills from directory and set as global registry."""
    global _registry
    _registry = SkillRegistry(skills_dir)
    _registry.load()
    return _registry
