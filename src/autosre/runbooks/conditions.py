"""
Condition Evaluator for runbooks.

Evaluates conditions for conditional step execution.
"""

from __future__ import annotations

import re
from typing import Any

from autosre.utils.logging import get_logger

from .models import Condition, ConditionOperator

logger = get_logger(__name__)


class ConditionError(Exception):
    """Error evaluating condition."""
    pass


class ConditionEvaluator:
    """
    Evaluates conditions for runbook step execution.
    
    Supports:
    - Comparison operators (==, !=, >, <, etc.)
    - Logical operators (and, or)
    - String operations (contains, matches)
    - Existence checks
    
    Example:
        evaluator = ConditionEvaluator()
        
        condition = Condition(
            left="status",
            operator=ConditionOperator.EQUALS,
            right="success"
        )
        
        result = evaluator.evaluate(condition, {"status": "success"})
        # -> True
    """
    
    def __init__(self):
        # Operator implementations
        self._operators: dict[ConditionOperator, callable] = {
            ConditionOperator.EQUALS: self._equals,
            ConditionOperator.NOT_EQUALS: self._not_equals,
            ConditionOperator.GREATER_THAN: self._greater_than,
            ConditionOperator.LESS_THAN: self._less_than,
            ConditionOperator.CONTAINS: self._contains,
            ConditionOperator.NOT_CONTAINS: self._not_contains,
            ConditionOperator.MATCHES: self._matches,
            ConditionOperator.EXISTS: self._exists,
            ConditionOperator.NOT_EXISTS: self._not_exists,
            ConditionOperator.AND: self._and,
            ConditionOperator.OR: self._or,
        }
    
    def evaluate(
        self,
        condition: Condition,
        context: dict[str, Any],
    ) -> bool:
        """
        Evaluate a condition against a context.
        
        Args:
            condition: Condition to evaluate
            context: Variable values
            
        Returns:
            True if condition is met
        """
        try:
            operator_func = self._operators.get(condition.operator)
            
            if not operator_func:
                raise ConditionError(f"Unknown operator: {condition.operator}")
            
            return operator_func(condition, context)
            
        except Exception as e:
            logger.error(f"Condition evaluation failed: {e}")
            return False
    
    def evaluate_string(
        self,
        condition_str: str,
        context: dict[str, Any],
    ) -> bool:
        """
        Evaluate a condition from string format.
        
        Args:
            condition_str: Condition string (e.g., "status == success")
            context: Variable values
            
        Returns:
            True if condition is met
        """
        condition = self.parse_condition(condition_str)
        return self.evaluate(condition, context)
    
    def parse_condition(self, condition_str: str) -> Condition:
        """
        Parse a condition from string format.
        
        Supported formats:
        - "variable == value"
        - "variable != value"
        - "variable > 10"
        - "variable contains substring"
        - "variable matches ^pattern$"
        - "variable exists"
        - "cond1 and cond2"
        - "cond1 or cond2"
        
        Args:
            condition_str: Condition string
            
        Returns:
            Parsed condition
        """
        condition_str = condition_str.strip()
        
        # Check for compound conditions
        if " and " in condition_str:
            parts = condition_str.split(" and ", 1)
            return Condition(
                left="",
                operator=ConditionOperator.AND,
                conditions=[
                    self.parse_condition(parts[0]),
                    self.parse_condition(parts[1]),
                ],
            )
        
        if " or " in condition_str:
            parts = condition_str.split(" or ", 1)
            return Condition(
                left="",
                operator=ConditionOperator.OR,
                conditions=[
                    self.parse_condition(parts[0]),
                    self.parse_condition(parts[1]),
                ],
            )
        
        # Parse simple conditions
        patterns = [
            (r"^(.+?)\s*==\s*(.+)$", ConditionOperator.EQUALS),
            (r"^(.+?)\s*!=\s*(.+)$", ConditionOperator.NOT_EQUALS),
            (r"^(.+?)\s*>\s*(.+)$", ConditionOperator.GREATER_THAN),
            (r"^(.+?)\s*<\s*(.+)$", ConditionOperator.LESS_THAN),
            (r"^(.+?)\s+contains\s+(.+)$", ConditionOperator.CONTAINS),
            (r"^(.+?)\s+not\s+contains\s+(.+)$", ConditionOperator.NOT_CONTAINS),
            (r"^(.+?)\s+matches\s+(.+)$", ConditionOperator.MATCHES),
            (r"^(.+?)\s+exists$", ConditionOperator.EXISTS),
            (r"^(.+?)\s+not\s+exists$", ConditionOperator.NOT_EXISTS),
        ]
        
        for pattern, operator in patterns:
            match = re.match(pattern, condition_str, re.IGNORECASE)
            if match:
                left = match.group(1).strip()
                right = match.group(2).strip() if match.lastindex >= 2 else None
                
                # Remove quotes from right value
                if right and (
                    (right.startswith('"') and right.endswith('"')) or
                    (right.startswith("'") and right.endswith("'"))
                ):
                    right = right[1:-1]
                
                # Convert numeric values
                if right and right.isdigit():
                    right = int(right)
                elif right and re.match(r"^\d+\.\d+$", right):
                    right = float(right)
                elif right and right.lower() in ("true", "false"):
                    right = right.lower() == "true"
                
                return Condition(
                    left=left,
                    operator=operator,
                    right=right,
                )
        
        # Default: check if truthy
        return Condition(
            left=condition_str,
            operator=ConditionOperator.EXISTS,
            right=True,
        )
    
    def _get_value(
        self,
        expr: str,
        context: dict[str, Any],
    ) -> Any:
        """Get value from context using expression."""
        # Handle nested access: foo.bar.baz
        parts = expr.split(".")
        value = context
        
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        
        return value
    
    def _equals(
        self,
        condition: Condition,
        context: dict[str, Any],
    ) -> bool:
        """Equals comparison."""
        left_value = self._get_value(condition.left, context)
        right_value = condition.right
        
        # Type coercion
        if isinstance(left_value, bool) or isinstance(right_value, bool):
            return bool(left_value) == bool(right_value)
        
        return left_value == right_value
    
    def _not_equals(
        self,
        condition: Condition,
        context: dict[str, Any],
    ) -> bool:
        """Not equals comparison."""
        return not self._equals(condition, context)
    
    def _greater_than(
        self,
        condition: Condition,
        context: dict[str, Any],
    ) -> bool:
        """Greater than comparison."""
        left_value = self._get_value(condition.left, context)
        right_value = condition.right
        
        try:
            return float(left_value) > float(right_value)
        except (TypeError, ValueError):
            return False
    
    def _less_than(
        self,
        condition: Condition,
        context: dict[str, Any],
    ) -> bool:
        """Less than comparison."""
        left_value = self._get_value(condition.left, context)
        right_value = condition.right
        
        try:
            return float(left_value) < float(right_value)
        except (TypeError, ValueError):
            return False
    
    def _contains(
        self,
        condition: Condition,
        context: dict[str, Any],
    ) -> bool:
        """Contains check."""
        left_value = self._get_value(condition.left, context)
        right_value = condition.right
        
        if left_value is None:
            return False
        
        if isinstance(left_value, str):
            return str(right_value) in left_value
        elif isinstance(left_value, (list, tuple)):
            return right_value in left_value
        elif isinstance(left_value, dict):
            return right_value in left_value
        
        return False
    
    def _not_contains(
        self,
        condition: Condition,
        context: dict[str, Any],
    ) -> bool:
        """Not contains check."""
        return not self._contains(condition, context)
    
    def _matches(
        self,
        condition: Condition,
        context: dict[str, Any],
    ) -> bool:
        """Regex match."""
        left_value = self._get_value(condition.left, context)
        pattern = condition.right
        
        if left_value is None or pattern is None:
            return False
        
        try:
            return bool(re.match(str(pattern), str(left_value)))
        except re.error:
            logger.warning(f"Invalid regex pattern: {pattern}")
            return False
    
    def _exists(
        self,
        condition: Condition,
        context: dict[str, Any],
    ) -> bool:
        """Existence check."""
        value = self._get_value(condition.left, context)
        return value is not None
    
    def _not_exists(
        self,
        condition: Condition,
        context: dict[str, Any],
    ) -> bool:
        """Non-existence check."""
        return not self._exists(condition, context)
    
    def _and(
        self,
        condition: Condition,
        context: dict[str, Any],
    ) -> bool:
        """Logical AND."""
        if not condition.conditions:
            return True
        
        return all(
            self.evaluate(sub_cond, context)
            for sub_cond in condition.conditions
        )
    
    def _or(
        self,
        condition: Condition,
        context: dict[str, Any],
    ) -> bool:
        """Logical OR."""
        if not condition.conditions:
            return False
        
        return any(
            self.evaluate(sub_cond, context)
            for sub_cond in condition.conditions
        )
    
    def validate_condition(self, condition: Condition) -> list[str]:
        """
        Validate a condition structure.
        
        Args:
            condition: Condition to validate
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Check for compound conditions
        if condition.operator in (ConditionOperator.AND, ConditionOperator.OR):
            if not condition.conditions:
                errors.append(f"{condition.operator.value} requires nested conditions")
            else:
                for sub_cond in condition.conditions:
                    errors.extend(self.validate_condition(sub_cond))
        else:
            # Check left operand
            if not condition.left:
                errors.append("Condition requires left operand")
            
            # Check right operand for comparison operators
            if condition.operator not in (
                ConditionOperator.EXISTS,
                ConditionOperator.NOT_EXISTS,
            ):
                if condition.right is None:
                    errors.append(f"{condition.operator.value} requires right operand")
        
        return errors
    
    def explain(
        self,
        condition: Condition,
        context: dict[str, Any],
    ) -> str:
        """
        Generate explanation of condition evaluation.
        
        Args:
            condition: Condition to explain
            context: Variable values
            
        Returns:
            Human-readable explanation
        """
        result = self.evaluate(condition, context)
        
        if condition.operator in (ConditionOperator.AND, ConditionOperator.OR):
            sub_explanations = [
                f"  - {self.explain(sub_cond, context)}"
                for sub_cond in condition.conditions
            ]
            return f"({condition.operator.value})\n" + "\n".join(sub_explanations)
        
        left_value = self._get_value(condition.left, context)
        
        return (
            f"'{condition.left}' ({left_value}) "
            f"{condition.operator.value} "
            f"'{condition.right}' -> {result}"
        )
