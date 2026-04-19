"""Utility functions for OpenSRE."""

import os
import re
from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path | str) -> dict[str, Any]:
    """Load a YAML file and return its contents."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"YAML file not found: {path}")
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def save_yaml(path: Path | str, data: dict[str, Any]) -> None:
    """Save data to a YAML file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def resolve_env_vars(value: str) -> str:
    """Resolve environment variables in a string.
    
    Supports ${VAR} and ${VAR:-default} syntax.
    """
    pattern = r'\$\{([^}]+)\}'
    
    def replacer(match: re.Match) -> str:
        expr = match.group(1)
        if ":-" in expr:
            var_name, default = expr.split(":-", 1)
            return os.environ.get(var_name, default)
        return os.environ.get(expr, match.group(0))
    
    return re.sub(pattern, replacer, value)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def resolve_template(template: str, context: dict[str, Any]) -> str:
    """Resolve a template string with context variables.
    
    Supports {{ variable }} and {{ variable.nested }} syntax.
    """
    pattern = r'\{\{\s*([^}]+)\s*\}\}'
    
    def replacer(match: re.Match) -> str:
        expr = match.group(1).strip()
        parts = expr.split(".")
        value: Any = context
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return match.group(0)
            if value is None:
                return match.group(0)
        return str(value)
    
    return re.sub(pattern, replacer, template)


def resolve_dict_templates(data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Recursively resolve templates in a dictionary."""
    result = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key] = resolve_template(value, context)
        elif isinstance(value, dict):
            result[key] = resolve_dict_templates(value, context)
        elif isinstance(value, list):
            result[key] = [
                resolve_template(v, context) if isinstance(v, str) else v
                for v in value
            ]
        else:
            result[key] = value
    return result


def get_project_root() -> Path:
    """Get the project root by looking for opensre.yaml."""
    current = Path.cwd()
    while current != current.parent:
        if (current / "opensre.yaml").exists():
            return current
        current = current.parent
    return Path.cwd()


def ensure_dir(path: Path | str) -> Path:
    """Ensure a directory exists."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def snake_to_camel(name: str) -> str:
    """Convert snake_case to CamelCase."""
    components = name.split("_")
    return "".join(x.title() for x in components)


def camel_to_snake(name: str) -> str:
    """Convert CamelCase to snake_case."""
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
