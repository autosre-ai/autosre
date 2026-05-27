"""Tool registry for managing available tools.

Provides a centralized registry for tool registration and discovery,
allowing the agent to find and invoke tools by name or category.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolMetadata:
    """Metadata about a registered tool."""
    
    name: str
    description: str
    category: str
    methods: List[str] = field(default_factory=list)
    required_config: List[str] = field(default_factory=list)


class ToolRegistry:
    """Registry for managing available tools.
    
    Allows tools to be registered, discovered, and invoked by name.
    Supports categorization and filtering of tools.
    
    Example:
        registry = ToolRegistry()
        registry.register(PrometheusTool())
        
        # Get tool by name
        prom = registry.get("PrometheusTool")
        
        # List tools by category
        obs_tools = registry.list_by_category("observability")
    """
    
    def __init__(self):
        self._tools: Dict[str, Any] = {}
        self._metadata: Dict[str, ToolMetadata] = {}
    
    def register(
        self,
        tool: Any,
        name: Optional[str] = None,
        category: str = "general",
        description: Optional[str] = None,
    ) -> None:
        """Register a tool with the registry.
        
        Args:
            tool: The tool instance to register
            name: Optional name override (defaults to class name)
            category: Tool category for grouping
            description: Tool description (defaults to docstring)
        """
        tool_name = name or tool.__class__.__name__
        
        # Extract methods (excluding private/dunder methods)
        methods = [
            m for m in dir(tool)
            if not m.startswith("_") and callable(getattr(tool, m))
        ]
        
        # Extract description from docstring if not provided
        tool_description = description or (tool.__class__.__doc__ or "").strip().split("\n")[0]
        
        # Store tool and metadata
        self._tools[tool_name] = tool
        self._metadata[tool_name] = ToolMetadata(
            name=tool_name,
            description=tool_description,
            category=category,
            methods=methods,
        )
    
    def get(self, name: str) -> Optional[Any]:
        """Get a tool by name.
        
        Args:
            name: Tool name
            
        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)
    
    def list_all(self) -> List[ToolMetadata]:
        """List all registered tools.
        
        Returns:
            List of tool metadata
        """
        return list(self._metadata.values())
    
    def list_by_category(self, category: str) -> List[ToolMetadata]:
        """List tools by category.
        
        Args:
            category: Category to filter by
            
        Returns:
            List of tool metadata in the category
        """
        return [
            meta for meta in self._metadata.values()
            if meta.category == category
        ]
    
    def categories(self) -> List[str]:
        """Get all registered categories.
        
        Returns:
            List of unique category names
        """
        return list(set(meta.category for meta in self._metadata.values()))
    
    def has(self, name: str) -> bool:
        """Check if a tool is registered.
        
        Args:
            name: Tool name
            
        Returns:
            True if tool exists
        """
        return name in self._tools
    
    def unregister(self, name: str) -> bool:
        """Unregister a tool.
        
        Args:
            name: Tool name
            
        Returns:
            True if tool was removed
        """
        if name in self._tools:
            del self._tools[name]
            del self._metadata[name]
            return True
        return False


# Global registry singleton
_global_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """Get the global tool registry.
    
    Returns:
        The global ToolRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry
