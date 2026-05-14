"""Helper utilities.

Common utility functions used across the codebase.
"""

import json
import re
from datetime import timedelta
from typing import Any, Optional


def format_duration(seconds: float) -> str:
    """Format duration in human-readable form.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string (e.g., "2h 30m 15s")
        
    Example:
        >>> format_duration(9015)
        '2h 30m 15s'
    """
    if seconds < 0:
        return "0s"
    
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")
    
    return " ".join(parts)


def format_bytes(num_bytes: int) -> str:
    """Format byte count in human-readable form.
    
    Args:
        num_bytes: Number of bytes
        
    Returns:
        Formatted string (e.g., "1.5 GB")
        
    Example:
        >>> format_bytes(1536000000)
        '1.43 GB'
    """
    if num_bytes < 0:
        return "0 B"
    
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if abs(num_bytes) < 1024.0:
            if unit == "B":
                return f"{num_bytes} {unit}"
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024.0
    
    return f"{num_bytes:.2f} EB"


def truncate_string(
    s: str,
    max_length: int = 100,
    suffix: str = "...",
) -> str:
    """Truncate string to maximum length.
    
    Args:
        s: String to truncate
        max_length: Maximum length (including suffix)
        suffix: Suffix to add when truncated
        
    Returns:
        Truncated string
        
    Example:
        >>> truncate_string("Hello World", max_length=8)
        'Hello...'
    """
    if len(s) <= max_length:
        return s
    
    return s[:max_length - len(suffix)] + suffix


def parse_duration(duration_str: str) -> timedelta:
    """Parse duration string into timedelta.
    
    Supports formats like:
    - "30s" (seconds)
    - "5m" (minutes)
    - "2h" (hours)
    - "1d" (days)
    - "2h30m" (combined)
    
    Args:
        duration_str: Duration string
        
    Returns:
        timedelta object
        
    Raises:
        ValueError: If format is invalid
        
    Example:
        >>> parse_duration("2h30m")
        datetime.timedelta(seconds=9000)
    """
    if not duration_str:
        raise ValueError("Empty duration string")
    
    # Try simple integer (assume seconds)
    try:
        return timedelta(seconds=int(duration_str))
    except ValueError:
        pass
    
    total_seconds = 0
    pattern = re.compile(r"(\d+)([smhdw])")
    
    multipliers = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400,
        "w": 604800,
    }
    
    matches = pattern.findall(duration_str.lower())
    if not matches:
        raise ValueError(f"Invalid duration format: {duration_str}")
    
    for value, unit in matches:
        if unit not in multipliers:
            raise ValueError(f"Unknown duration unit: {unit}")
        total_seconds += int(value) * multipliers[unit]
    
    return timedelta(seconds=total_seconds)


def safe_json_loads(
    s: str,
    default: Any = None,
) -> Any:
    """Safely parse JSON string.
    
    Args:
        s: JSON string
        default: Default value if parsing fails
        
    Returns:
        Parsed JSON or default value
        
    Example:
        >>> safe_json_loads('{"key": "value"}')
        {'key': 'value'}
        >>> safe_json_loads('invalid', default={})
        {}
    """
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return default


def extract_json_from_text(text: str) -> Optional[dict[str, Any]]:
    """Extract JSON object from text that may contain other content.
    
    Useful for parsing LLM responses that include JSON in markdown blocks.
    
    Args:
        text: Text that may contain JSON
        
    Returns:
        Extracted JSON dict or None
        
    Example:
        >>> extract_json_from_text('Here is the result: ```json\\n{"key": "value"}\\n```')
        {'key': 'value'}
    """
    # Try direct parsing first
    result = safe_json_loads(text)
    if result is not None:
        return result
    
    # Try to find JSON in markdown code blocks
    json_block_pattern = r"```(?:json)?\s*([\s\S]*?)```"
    matches = re.findall(json_block_pattern, text)
    
    for match in matches:
        result = safe_json_loads(match.strip())
        if result is not None:
            return result
    
    # Try to find JSON object directly
    json_pattern = r"\{[\s\S]*\}"
    matches = re.findall(json_pattern, text)
    
    for match in matches:
        result = safe_json_loads(match)
        if isinstance(result, dict):
            return result
    
    return None


def snake_to_camel(snake_str: str) -> str:
    """Convert snake_case to camelCase.
    
    Args:
        snake_str: Snake case string
        
    Returns:
        Camel case string
        
    Example:
        >>> snake_to_camel("hello_world")
        'helloWorld'
    """
    components = snake_str.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def camel_to_snake(camel_str: str) -> str:
    """Convert camelCase to snake_case.
    
    Args:
        camel_str: Camel case string
        
    Returns:
        Snake case string
        
    Example:
        >>> camel_to_snake("helloWorld")
        'hello_world'
    """
    pattern = re.compile(r"(?<!^)(?=[A-Z])")
    return pattern.sub("_", camel_str).lower()


def deep_merge(
    base: dict[str, Any],
    override: dict[str, Any],
) -> dict[str, Any]:
    """Deep merge two dictionaries.
    
    Args:
        base: Base dictionary
        override: Override dictionary
        
    Returns:
        Merged dictionary
        
    Example:
        >>> deep_merge({'a': {'b': 1}}, {'a': {'c': 2}})
        {'a': {'b': 1, 'c': 2}}
    """
    result = base.copy()
    
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result


def flatten_dict(
    d: dict[str, Any],
    parent_key: str = "",
    sep: str = ".",
) -> dict[str, Any]:
    """Flatten a nested dictionary.
    
    Args:
        d: Dictionary to flatten
        parent_key: Parent key prefix
        sep: Separator between keys
        
    Returns:
        Flattened dictionary
        
    Example:
        >>> flatten_dict({'a': {'b': {'c': 1}}})
        {'a.b.c': 1}
    """
    items: list[tuple[str, Any]] = []
    
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep).items())
        else:
            items.append((new_key, v))
    
    return dict(items)
