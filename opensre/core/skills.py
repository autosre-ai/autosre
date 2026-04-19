"""Skill system for OpenSRE."""

import importlib.util
import inspect
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable

from .exceptions import SkillExecutionError, SkillLoadError, SkillNotFoundError
from .models import SkillInfo, SkillMetadata
from .utils import load_yaml


class Skill(ABC):
    """Base class for all OpenSRE skills.
    
    Skills are the building blocks of agents. They provide methods
    that can be called during agent execution.
    
    Example:
        class MySkill(Skill):
            name = "my_skill"
            version = "1.0.0"
            
            def setup(self, config: dict) -> None:
                self.api_key = config.get("api_key")
            
            def do_something(self, context: dict, param1: str) -> dict:
                # Do work here
                return {"result": "done"}
    """
    
    name: str = "base_skill"
    version: str = "1.0.0"
    description: str = ""
    
    def __init__(self):
        self._config: dict[str, Any] = {}
        self._initialized = False
    
    def setup(self, config: dict[str, Any]) -> None:
        """Initialize the skill with configuration.
        
        Override this method to perform skill-specific setup.
        """
        self._config = config
        self._initialized = True
    
    def teardown(self) -> None:
        """Clean up resources.
        
        Override this method to perform cleanup when the skill is unloaded.
        """
        pass
    
    @property
    def config(self) -> dict[str, Any]:
        """Get skill configuration."""
        return self._config
    
    def get_methods(self) -> list[str]:
        """Get list of callable methods (excluding internals)."""
        methods = []
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if name.startswith("_"):
                continue
            if name in ("setup", "teardown", "get_methods"):
                continue
            methods.append(name)
        return methods
    
    def call(self, method: str, context: dict[str, Any], **kwargs: Any) -> Any:
        """Call a skill method with context and arguments."""
        if not hasattr(self, method):
            raise SkillExecutionError(
                self.name, method, f"Method '{method}' not found"
            )
        
        func = getattr(self, method)
        if not callable(func):
            raise SkillExecutionError(
                self.name, method, f"'{method}' is not callable"
            )
        
        try:
            # Check if method accepts context
            sig = inspect.signature(func)
            if "context" in sig.parameters:
                return func(context=context, **kwargs)
            else:
                return func(**kwargs)
        except Exception as e:
            raise SkillExecutionError(self.name, method, str(e)) from e


class SkillRegistry:
    """Registry for discovering and loading skills."""
    
    def __init__(self, skills_dir: Path | str | None = None):
        self.skills_dir = Path(skills_dir) if skills_dir else None
        self._skills: dict[str, Skill] = {}
        self._skill_classes: dict[str, type[Skill]] = {}
        self._metadata: dict[str, SkillMetadata] = {}
    
    def discover(self, skills_dir: Path | str | None = None) -> list[SkillInfo]:
        """Discover skills in the given directory.
        
        Each skill should be in its own directory with:
        - skill.yaml: Metadata
        - skill.py or __init__.py: Implementation
        """
        search_dir = Path(skills_dir) if skills_dir else self.skills_dir
        if not search_dir or not search_dir.exists():
            return []
        
        discovered: list[SkillInfo] = []
        
        for item in search_dir.iterdir():
            if not item.is_dir():
                continue
            if item.name.startswith("_"):
                continue
            
            # Look for skill.yaml
            metadata_file = item / "skill.yaml"
            if not metadata_file.exists():
                continue
            
            try:
                raw_metadata = load_yaml(metadata_file)
                metadata = SkillMetadata(**raw_metadata)
                self._metadata[metadata.name] = metadata
                
                discovered.append(SkillInfo(
                    name=metadata.name,
                    version=metadata.version,
                    description=metadata.description,
                    methods=metadata.methods,
                    path=str(item),
                    loaded=metadata.name in self._skills
                ))
            except Exception as e:
                discovered.append(SkillInfo(
                    name=item.name,
                    version="unknown",
                    description="",
                    methods=[],
                    path=str(item),
                    loaded=False,
                    error=str(e)
                ))
        
        return discovered
    
    def load(self, skill_name: str, config: dict[str, Any] | None = None) -> Skill:
        """Load a skill by name.
        
        Looks for the skill in the skills directory and loads it dynamically.
        """
        # Return cached instance if already loaded
        if skill_name in self._skills:
            return self._skills[skill_name]
        
        # Find skill directory
        skill_dir = self._find_skill_dir(skill_name)
        if not skill_dir:
            raise SkillNotFoundError(skill_name)
        
        # Load skill class
        skill_class = self._load_skill_class(skill_name, skill_dir)
        
        # Instantiate and setup
        skill = skill_class()
        skill.setup(config or {})
        
        self._skills[skill_name] = skill
        self._skill_classes[skill_name] = skill_class
        
        return skill
    
    def _find_skill_dir(self, skill_name: str) -> Path | None:
        """Find the directory for a skill."""
        if not self.skills_dir or not self.skills_dir.exists():
            return None
        
        # Direct match
        direct = self.skills_dir / skill_name
        if direct.exists():
            return direct
        
        # Check metadata for matching names
        for item in self.skills_dir.iterdir():
            if not item.is_dir():
                continue
            metadata_file = item / "skill.yaml"
            if metadata_file.exists():
                try:
                    raw = load_yaml(metadata_file)
                    if raw.get("name") == skill_name:
                        return item
                except Exception:
                    continue
        
        return None
    
    def _load_skill_class(self, skill_name: str, skill_dir: Path) -> type[Skill]:
        """Load a skill class from a directory."""
        # Try actions.py first (new style), then skill.py, then __init__.py
        for filename in ("actions.py", "skill.py", "__init__.py"):
            skill_file = skill_dir / filename
            if skill_file.exists():
                break
        else:
            raise SkillLoadError(skill_name, "No actions.py, skill.py, or __init__.py found")
        
        try:
            # Load module dynamically
            module_name = f"opensre_skill_{skill_name}"
            spec = importlib.util.spec_from_file_location(module_name, skill_file)
            if spec is None or spec.loader is None:
                raise SkillLoadError(skill_name, "Failed to create module spec")
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            # Import opensre_core.skills.Skill for compatibility check
            try:
                from opensre_core.skills import Skill as CoreSkill
                core_skill_classes = (Skill, CoreSkill)
            except ImportError:
                core_skill_classes = (Skill,)
            
            # Find Skill subclass - check both this module's Skill and opensre_core.skills.Skill
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if obj in core_skill_classes:
                    continue
                if any(issubclass(obj, cls) for cls in core_skill_classes if cls is not None):
                    # Wrap opensre_core skills in an adapter if needed
                    if not issubclass(obj, Skill):
                        return self._wrap_core_skill(obj, skill_name)
                    return obj
            
            raise SkillLoadError(skill_name, "No Skill subclass found")
            
        except SkillLoadError:
            raise
        except Exception as e:
            raise SkillLoadError(skill_name, str(e)) from e
    
    def _wrap_core_skill(self, core_class: type, skill_name: str) -> type[Skill]:
        """Wrap an opensre_core.skills.Skill class in an opensre.core.skills.Skill adapter."""
        
        class SkillAdapter(Skill):
            name = getattr(core_class, 'name', skill_name)
            version = getattr(core_class, 'version', '1.0.0')
            description = getattr(core_class, 'description', '')
            
            def __init__(self):
                super().__init__()
                self._core_instance = None
                self._core_class = core_class
            
            def setup(self, config: dict[str, Any]) -> None:
                super().setup(config)
                # Create the core skill instance with config
                self._core_instance = self._core_class(config)
            
            def teardown(self) -> None:
                if self._core_instance:
                    import asyncio
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        loop = None
                    
                    if loop and loop.is_running():
                        asyncio.create_task(self._core_instance.shutdown())
                    else:
                        asyncio.run(self._core_instance.shutdown())
            
            def get_methods(self) -> list[str]:
                if self._core_instance:
                    # Get actions from the core skill
                    actions = self._core_instance.get_actions()
                    return [a.name for a in actions]
                return []
            
            def call(self, method: str, context: dict[str, Any], **kwargs: Any) -> Any:
                if not self._core_instance:
                    raise SkillExecutionError(self.name, method, "Skill not initialized")
                
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                
                # Get the method from the core instance
                if hasattr(self._core_instance, method):
                    func = getattr(self._core_instance, method)
                    if asyncio.iscoroutinefunction(func):
                        if loop and loop.is_running():
                            import concurrent.futures
                            with concurrent.futures.ThreadPoolExecutor() as pool:
                                future = pool.submit(asyncio.run, func(**kwargs))
                                result = future.result()
                        else:
                            result = asyncio.run(func(**kwargs))
                    else:
                        result = func(**kwargs)
                    return result
                else:
                    # Try invoke for action-based skills
                    if loop and loop.is_running():
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            future = pool.submit(
                                asyncio.run,
                                self._core_instance.invoke(method, **kwargs)
                            )
                            result = future.result()
                    else:
                        result = asyncio.run(self._core_instance.invoke(method, **kwargs))
                    
                    # ActionResult handling
                    if hasattr(result, 'success'):
                        if result.success:
                            return result.data
                        else:
                            raise SkillExecutionError(self.name, method, result.error or "Unknown error")
                    return result
        
        SkillAdapter.__name__ = f"{core_class.__name__}Adapter"
        return SkillAdapter
    
    def get(self, skill_name: str) -> Skill | None:
        """Get a loaded skill by name."""
        return self._skills.get(skill_name)
    
    def unload(self, skill_name: str) -> None:
        """Unload a skill and clean up resources."""
        if skill_name in self._skills:
            skill = self._skills[skill_name]
            skill.teardown()
            del self._skills[skill_name]
        if skill_name in self._skill_classes:
            del self._skill_classes[skill_name]
    
    def unload_all(self) -> None:
        """Unload all skills."""
        for skill_name in list(self._skills.keys()):
            self.unload(skill_name)
    
    def list_loaded(self) -> list[str]:
        """List names of loaded skills."""
        return list(self._skills.keys())
    
    def get_metadata(self, skill_name: str) -> SkillMetadata | None:
        """Get metadata for a skill."""
        return self._metadata.get(skill_name)
    
    def register(self, skill_class: type[Skill], config: dict[str, Any] | None = None) -> Skill:
        """Register a skill class directly (for programmatic use)."""
        skill = skill_class()
        skill.setup(config or {})
        self._skills[skill.name] = skill
        self._skill_classes[skill.name] = skill_class
        return skill


def skill(
    name: str | None = None,
    version: str = "1.0.0",
    description: str = ""
) -> Callable[[type], type[Skill]]:
    """Decorator to create a skill from a class.
    
    Example:
        @skill(name="my_skill", version="1.0.0")
        class MySkill:
            def do_something(self, context: dict) -> dict:
                return {"done": True}
    """
    def decorator(cls: type) -> type[Skill]:
        # Create a new class that inherits from Skill
        skill_name = name or cls.__name__.lower()
        
        new_cls = type(
            cls.__name__,
            (Skill,),
            {
                "name": skill_name,
                "version": version,
                "description": description,
                **{k: v for k, v in cls.__dict__.items() if not k.startswith("__")}
            }
        )
        return new_cls
    
    return decorator
