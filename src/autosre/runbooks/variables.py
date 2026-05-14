"""
Variable Resolver for runbooks.

Handles dynamic variable substitution in runbook steps.
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any

from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class VariableResolver:
    """
    Resolves variables in runbook templates.
    
    Supports:
    - {{ variable }} syntax
    - Nested variables
    - Built-in variables (timestamp, env, etc.)
    - Filters/transformations
    
    Example:
        resolver = VariableResolver()
        
        result = resolver.resolve_string(
            "kubectl get pods -n {{ namespace }}",
            {"namespace": "production"}
        )
        # -> "kubectl get pods -n production"
        
        # With filters
        result = resolver.resolve_string(
            "{{ name | upper }}",
            {"name": "api-server"}
        )
        # -> "API-SERVER"
    """
    
    def __init__(self):
        # Built-in variables
        self._builtins: dict[str, callable] = {
            "timestamp": lambda: datetime.utcnow().isoformat(),
            "date": lambda: datetime.utcnow().strftime("%Y-%m-%d"),
            "time": lambda: datetime.utcnow().strftime("%H:%M:%S"),
            "hostname": lambda: os.uname().nodename,
            "user": lambda: os.getenv("USER", "unknown"),
        }
        
        # Filters
        self._filters: dict[str, callable] = {
            "upper": lambda x: str(x).upper(),
            "lower": lambda x: str(x).lower(),
            "strip": lambda x: str(x).strip(),
            "default": lambda x, d: x if x else d,
            "quote": lambda x: f'"{x}"',
            "json": lambda x: __import__("json").dumps(x),
            "base64": lambda x: __import__("base64").b64encode(str(x).encode()).decode(),
            "int": lambda x: int(x),
            "float": lambda x: float(x),
            "bool": lambda x: str(x).lower() in ("true", "1", "yes"),
            "list": lambda x: x if isinstance(x, list) else [x],
            "first": lambda x: x[0] if x else None,
            "last": lambda x: x[-1] if x else None,
            "join": lambda x, sep=",": sep.join(str(i) for i in x) if isinstance(x, list) else x,
            "split": lambda x, sep=",": str(x).split(sep),
            "replace": lambda x, old, new: str(x).replace(old, new),
            "regex_replace": lambda x, pattern, repl: re.sub(pattern, repl, str(x)),
            "truncate": lambda x, length=50: str(x)[:length],
        }
    
    def register_builtin(self, name: str, func: callable) -> None:
        """Register a built-in variable."""
        self._builtins[name] = func
    
    def register_filter(self, name: str, func: callable) -> None:
        """Register a filter."""
        self._filters[name] = func
    
    def resolve_string(
        self,
        template: str,
        context: dict[str, Any],
    ) -> str:
        """
        Resolve variables in a string template.
        
        Args:
            template: Template string with {{ variable }} placeholders
            context: Variable values
            
        Returns:
            Resolved string
        """
        if not template:
            return template
        
        # Pattern: {{ variable }} or {{ variable | filter }}
        pattern = r"\{\{\s*([^}]+)\s*\}\}"
        
        def replacer(match: re.Match) -> str:
            expr = match.group(1).strip()
            return str(self._evaluate_expression(expr, context))
        
        return re.sub(pattern, replacer, template)
    
    def resolve_dict(
        self,
        data: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Resolve variables in a dictionary.
        
        Args:
            data: Dictionary with template values
            context: Variable values
            
        Returns:
            Resolved dictionary
        """
        result = {}
        
        for key, value in data.items():
            # Resolve key
            resolved_key = self.resolve_string(key, context) if isinstance(key, str) else key
            
            # Resolve value
            if isinstance(value, str):
                result[resolved_key] = self.resolve_string(value, context)
            elif isinstance(value, dict):
                result[resolved_key] = self.resolve_dict(value, context)
            elif isinstance(value, list):
                result[resolved_key] = self.resolve_list(value, context)
            else:
                result[resolved_key] = value
        
        return result
    
    def resolve_list(
        self,
        data: list[Any],
        context: dict[str, Any],
    ) -> list[Any]:
        """
        Resolve variables in a list.
        
        Args:
            data: List with template values
            context: Variable values
            
        Returns:
            Resolved list
        """
        result = []
        
        for item in data:
            if isinstance(item, str):
                result.append(self.resolve_string(item, context))
            elif isinstance(item, dict):
                result.append(self.resolve_dict(item, context))
            elif isinstance(item, list):
                result.append(self.resolve_list(item, context))
            else:
                result.append(item)
        
        return result
    
    def resolve_any(
        self,
        data: Any,
        context: dict[str, Any],
    ) -> Any:
        """
        Resolve variables in any data type.
        
        Args:
            data: Data with potential template values
            context: Variable values
            
        Returns:
            Resolved data
        """
        if isinstance(data, str):
            return self.resolve_string(data, context)
        elif isinstance(data, dict):
            return self.resolve_dict(data, context)
        elif isinstance(data, list):
            return self.resolve_list(data, context)
        else:
            return data
    
    def _evaluate_expression(
        self,
        expr: str,
        context: dict[str, Any],
    ) -> Any:
        """Evaluate a variable expression."""
        # Split by pipe for filters
        parts = [p.strip() for p in expr.split("|")]
        
        # Get base value
        var_expr = parts[0]
        value = self._get_value(var_expr, context)
        
        # Apply filters
        for i in range(1, len(parts)):
            filter_expr = parts[i].strip()
            value = self._apply_filter(filter_expr, value)
        
        return value
    
    def _get_value(
        self,
        var_expr: str,
        context: dict[str, Any],
    ) -> Any:
        """Get value for a variable expression."""
        # Check for nested access: foo.bar.baz
        parts = var_expr.split(".")
        
        # Start with context
        value = context
        
        for part in parts:
            # Check for array index: items[0]
            array_match = re.match(r"(\w+)\[(\d+)\]", part)
            
            if array_match:
                key = array_match.group(1)
                index = int(array_match.group(2))
                
                if isinstance(value, dict):
                    value = value.get(key)
                
                if isinstance(value, list) and index < len(value):
                    value = value[index]
                else:
                    value = None
            else:
                if isinstance(value, dict):
                    # Check context first
                    if part in value:
                        value = value[part]
                    # Check builtins
                    elif part in self._builtins:
                        value = self._builtins[part]()
                    # Check environment
                    elif part.startswith("env_"):
                        env_var = part[4:]
                        value = os.getenv(env_var, "")
                    else:
                        value = None
                else:
                    value = None
            
            if value is None:
                break
        
        return value
    
    def _apply_filter(
        self,
        filter_expr: str,
        value: Any,
    ) -> Any:
        """Apply a filter to a value."""
        # Parse filter name and arguments
        # Format: filter_name or filter_name(arg1, arg2)
        match = re.match(r"(\w+)(?:\(([^)]*)\))?", filter_expr)
        
        if not match:
            logger.warning(f"Invalid filter expression: {filter_expr}")
            return value
        
        filter_name = match.group(1)
        args_str = match.group(2)
        
        if filter_name not in self._filters:
            logger.warning(f"Unknown filter: {filter_name}")
            return value
        
        filter_func = self._filters[filter_name]
        
        # Parse arguments
        if args_str:
            args = self._parse_filter_args(args_str)
            return filter_func(value, *args)
        else:
            return filter_func(value)
    
    def _parse_filter_args(self, args_str: str) -> list[Any]:
        """Parse filter arguments."""
        args = []
        
        # Simple parsing - split by comma
        for arg in args_str.split(","):
            arg = arg.strip()
            
            # String literal
            if (arg.startswith('"') and arg.endswith('"')) or \
               (arg.startswith("'") and arg.endswith("'")):
                args.append(arg[1:-1])
            # Number
            elif arg.isdigit():
                args.append(int(arg))
            elif re.match(r"^\d+\.\d+$", arg):
                args.append(float(arg))
            # Boolean
            elif arg.lower() in ("true", "false"):
                args.append(arg.lower() == "true")
            else:
                args.append(arg)
        
        return args
    
    def get_required_variables(self, template: str) -> set[str]:
        """
        Extract required variable names from a template.
        
        Args:
            template: Template string
            
        Returns:
            Set of variable names
        """
        pattern = r"\{\{\s*([^}|]+)"
        matches = re.findall(pattern, template)
        
        variables = set()
        for match in matches:
            var_name = match.strip().split(".")[0]
            if var_name not in self._builtins:
                variables.add(var_name)
        
        return variables
    
    def validate_template(
        self,
        template: str,
        context: dict[str, Any],
    ) -> list[str]:
        """
        Validate a template against provided context.
        
        Args:
            template: Template string
            context: Available variables
            
        Returns:
            List of missing variables
        """
        required = self.get_required_variables(template)
        missing = []
        
        for var in required:
            if var not in context:
                missing.append(var)
        
        return missing
