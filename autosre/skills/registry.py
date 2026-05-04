"""
Skill Registry — Loads and manages skills from YAML + Python files.

Skills are modular investigation tools that subagents can use.
Each skill has:
- A YAML definition (metadata, parameters)
- A Python implementation (actual code)
"""

import importlib.util
import logging
from pathlib import Path
from typing import Any, Callable, Optional

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SkillParameter(BaseModel):
    """Definition of a skill parameter."""
    
    name: str
    type: str = "string"
    description: str = ""
    required: bool = False
    default: Any = None


class SkillDefinition(BaseModel):
    """Definition of a skill from YAML."""
    
    name: str
    description: str = ""
    category: str = ""  # kubernetes, metrics, logs, etc.
    parameters: list[SkillParameter] = Field(default_factory=list)
    requires: list[str] = Field(default_factory=list)  # Required tools/binaries
    examples: list[str] = Field(default_factory=list)


class Skill:
    """A loaded skill ready for execution."""
    
    def __init__(
        self,
        definition: SkillDefinition,
        execute_fn: Callable[..., Any],
    ):
        self.definition = definition
        self.name = definition.name
        self.description = definition.description
        self.category = definition.category
        self._execute_fn = execute_fn
    
    async def execute(self, **kwargs: Any) -> str:
        """Execute the skill with given parameters."""
        result = self._execute_fn(**kwargs)
        
        # Handle async functions
        if hasattr(result, "__await__"):
            result = await result
        
        return str(result)
    
    def to_tool_definition(self) -> dict[str, Any]:
        """Convert to OpenAI-style tool definition."""
        properties = {}
        required = []
        
        for param in self.definition.parameters:
            properties[param.name] = {
                "type": param.type,
                "description": param.description,
            }
            if param.required:
                required.append(param.name)
            if param.default is not None:
                properties[param.name]["default"] = param.default
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


class SkillRegistry:
    """Registry for loading and managing skills."""
    
    def __init__(self, skills_dir: Optional[Path] = None):
        self.skills_dir = skills_dir
        self._skills: dict[str, Skill] = {}
        self._categories: dict[str, list[str]] = {}
    
    def register(self, skill: Skill) -> None:
        """Register a skill."""
        self._skills[skill.name] = skill
        
        if skill.category:
            if skill.category not in self._categories:
                self._categories[skill.category] = []
            self._categories[skill.category].append(skill.name)
        
        logger.debug(f"[SKILLS] Registered: {skill.name}")
    
    def get(self, name: str) -> Optional[Skill]:
        """Get a skill by name."""
        return self._skills.get(name)
    
    def list_all(self) -> list[str]:
        """List all skill names."""
        return list(self._skills.keys())
    
    def list_by_category(self, category: str) -> list[str]:
        """List skills in a category."""
        return self._categories.get(category, [])
    
    def get_categories(self) -> list[str]:
        """List all categories."""
        return list(self._categories.keys())
    
    def load_from_directory(self, skills_dir: Optional[Path] = None) -> int:
        """Load skills from a directory.
        
        Directory structure:
            skills/
            ├── kubernetes/
            │   ├── skill.yaml      # Skill definitions
            │   ├── pod_logs.py     # Implementation
            │   └── describe.py
            ├── metrics/
            │   ├── skill.yaml
            │   └── query.py
        
        Returns number of skills loaded.
        """
        if skills_dir:
            self.skills_dir = skills_dir
        
        if not self.skills_dir or not self.skills_dir.exists():
            logger.warning(f"[SKILLS] Directory not found: {self.skills_dir}")
            return 0
        
        count = 0
        
        for category_dir in self.skills_dir.iterdir():
            if not category_dir.is_dir():
                continue
            
            skill_yaml = category_dir / "skill.yaml"
            if not skill_yaml.exists():
                continue
            
            # Load skill definitions
            with open(skill_yaml) as f:
                data = yaml.safe_load(f) or {}
            
            category = category_dir.name
            
            for skill_data in data.get("skills", []):
                skill_name = skill_data.get("name")
                if not skill_name:
                    continue
                
                # Create definition
                parameters = [
                    SkillParameter(**p) if isinstance(p, dict) else SkillParameter(name=str(p))
                    for p in skill_data.get("parameters", [])
                ]
                
                definition = SkillDefinition(
                    name=skill_name,
                    description=skill_data.get("description", ""),
                    category=category,
                    parameters=parameters,
                    requires=skill_data.get("requires", []),
                    examples=skill_data.get("examples", []),
                )
                
                # Load implementation
                impl_file = category_dir / f"{skill_name}.py"
                execute_fn = self._load_implementation(impl_file, skill_name)
                
                if execute_fn:
                    skill = Skill(definition=definition, execute_fn=execute_fn)
                    self.register(skill)
                    count += 1
        
        logger.info(f"[SKILLS] Loaded {count} skills from {self.skills_dir}")
        return count
    
    def _load_implementation(
        self,
        impl_file: Path,
        skill_name: str,
    ) -> Optional[Callable[..., Any]]:
        """Load skill implementation from Python file."""
        if not impl_file.exists():
            logger.warning(f"[SKILLS] Implementation not found: {impl_file}")
            return self._create_stub(skill_name)
        
        try:
            spec = importlib.util.spec_from_file_location(skill_name, impl_file)
            if not spec or not spec.loader:
                return None
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Look for execute function
            if hasattr(module, "execute"):
                return module.execute
            elif hasattr(module, skill_name):
                return getattr(module, skill_name)
            elif hasattr(module, "main"):
                return module.main
            else:
                logger.warning(f"[SKILLS] No execute function in {impl_file}")
                return self._create_stub(skill_name)
                
        except Exception as e:
            logger.error(f"[SKILLS] Failed to load {impl_file}: {e}")
            return self._create_stub(skill_name)
    
    def _create_stub(self, skill_name: str) -> Callable[..., str]:
        """Create a stub implementation."""
        def stub(**kwargs: Any) -> str:
            return f"Skill '{skill_name}' not implemented. Args: {kwargs}"
        return stub
    
    def to_catalog(self) -> str:
        """Generate skill catalog text for prompts."""
        lines = []
        
        for category in sorted(self._categories.keys()):
            lines.append(f"## {category.title()}")
            
            for skill_name in self._categories[category]:
                skill = self._skills.get(skill_name)
                if skill:
                    lines.append(f"- **{skill.name}**: {skill.description}")
            
            lines.append("")
        
        return "\n".join(lines)


# Global registry
_registry: Optional[SkillRegistry] = None


def get_registry() -> SkillRegistry:
    """Get global skill registry."""
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry


def load_skills(skills_dir: Path) -> int:
    """Load skills from directory into global registry."""
    return get_registry().load_from_directory(skills_dir)
