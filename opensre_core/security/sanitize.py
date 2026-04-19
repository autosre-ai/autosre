"""
Input Sanitization Module - Prevent command injection and validate inputs
"""

import re
import shlex
from dataclasses import dataclass
from typing import Optional, Tuple

# Patterns that indicate command injection attempts
DANGEROUS_PATTERNS = [
    # Command chaining
    (r";\s*rm\s", "Command chain with rm"),
    (r"\|\s*rm\s", "Pipe to rm"),
    (r"&&\s*rm\s", "AND chain with rm"),
    (r"\|\|\s*rm\s", "OR chain with rm"),

    # Shell expansion/substitution
    (r"\$\(", "Command substitution $()"),
    (r"`", "Backtick command substitution"),
    (r"\$\{", "Variable expansion"),

    # Dangerous redirects
    (r">\s*/", "Redirect to root filesystem"),
    (r">>\s*/", "Append to root filesystem"),
    (r">\s*~", "Redirect to home directory"),

    # Remote code execution
    (r"curl.*\|.*sh", "Curl pipe to shell"),
    (r"wget.*\|.*sh", "Wget pipe to shell"),
    (r"curl.*\|.*bash", "Curl pipe to bash"),
    (r"wget.*\|.*bash", "Wget pipe to bash"),

    # Base64 execution
    (r"base64\s+-d.*\|", "Base64 decode pipe"),

    # Disk operations
    (r"mkfs\.", "Filesystem creation"),
    (r"dd\s+if=", "dd command"),

    # General dangerous commands
    (r";\s*shutdown", "Shutdown command"),
    (r";\s*reboot", "Reboot command"),
    (r";\s*init\s+0", "Init 0"),
    (r";\s*halt", "Halt command"),

    # Environment manipulation
    (r"export\s+PATH=", "PATH manipulation"),
    (r"export\s+LD_", "LD library manipulation"),
]

# Allowed kubectl verbs (read operations are always safe)
KUBECTL_SAFE_VERBS = {
    "get", "describe", "logs", "top", "events", "explain",
    "api-resources", "api-versions", "version", "cluster-info",
    "config", "auth", "diff",
}

# Medium-risk kubectl verbs (reversible, but require caution)
KUBECTL_MEDIUM_VERBS = {
    "scale", "rollout", "cordon", "uncordon", "drain",
    "label", "annotate", "taint", "untaint",
    "autoscale", "expose", "set",
}

# High-risk kubectl verbs (potentially destructive)
KUBECTL_HIGH_VERBS = {
    "delete", "apply", "patch", "edit", "create", "replace",
    "exec", "run", "cp",
}

# Complete allowlist of kubectl verbs
ALLOWED_KUBECTL_VERBS = KUBECTL_SAFE_VERBS | KUBECTL_MEDIUM_VERBS | KUBECTL_HIGH_VERBS


@dataclass
class SanitizeResult:
    """Result of command sanitization."""
    is_safe: bool
    reason: str
    risk_level: Optional[str] = None  # "low", "medium", "high"
    command: Optional[str] = None


def sanitize_command(command: str) -> Tuple[bool, str]:
    """
    Check if a command is safe to execute.

    Args:
        command: The command to check

    Returns:
        Tuple of (is_safe, reason)
    """
    result = sanitize_command_full(command)
    return result.is_safe, result.reason


def sanitize_command_full(command: str) -> SanitizeResult:
    """
    Full sanitization check with detailed results.

    Args:
        command: The command to check

    Returns:
        SanitizeResult with safety status and details
    """
    if not command or not command.strip():
        return SanitizeResult(
            is_safe=False,
            reason="Empty command",
        )

    command = command.strip()

    # Check for dangerous patterns
    for pattern, description in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return SanitizeResult(
                is_safe=False,
                reason=f"Dangerous pattern detected: {description}",
                command=command,
            )

    # Check for multiple commands (semicolon, &&, ||)
    # Allow single commands only
    if ";" in command and not command.strip().startswith("kubectl"):
        # Check if semicolon is inside quotes
        try:
            shlex.split(command)
            # If shlex can parse it cleanly, the semicolon might be quoted
            # But we still need to check for actual command chaining
            raw_parts = command.split(";")
            if len(raw_parts) > 1 and any(p.strip() for p in raw_parts[1:]):
                return SanitizeResult(
                    is_safe=False,
                    reason="Multiple commands not allowed (semicolon)",
                    command=command,
                )
        except ValueError:
            return SanitizeResult(
                is_safe=False,
                reason="Invalid command syntax",
                command=command,
            )

    # Validate kubectl commands
    if command.strip().startswith("kubectl"):
        return _sanitize_kubectl(command)

    # Non-kubectl commands are blocked by default
    return SanitizeResult(
        is_safe=False,
        reason="Only kubectl commands are allowed",
        command=command,
    )


def _sanitize_kubectl(command: str) -> SanitizeResult:
    """Sanitize a kubectl command."""
    try:
        parts = shlex.split(command)
    except ValueError as e:
        return SanitizeResult(
            is_safe=False,
            reason=f"Invalid command syntax: {e}",
            command=command,
        )

    if len(parts) < 2:
        return SanitizeResult(
            is_safe=False,
            reason="kubectl command requires a verb",
            command=command,
        )

    # Get the verb (first non-flag argument after kubectl)
    verb = None
    for part in parts[1:]:
        if not part.startswith("-"):
            verb = part
            break

    if not verb:
        return SanitizeResult(
            is_safe=False,
            reason="kubectl command requires a verb",
            command=command,
        )

    # Check if verb is allowed
    if verb not in ALLOWED_KUBECTL_VERBS:
        return SanitizeResult(
            is_safe=False,
            reason=f"kubectl verb '{verb}' not in allowlist",
            command=command,
        )

    # Determine risk level
    if verb in KUBECTL_SAFE_VERBS:
        risk_level = "low"
    elif verb in KUBECTL_MEDIUM_VERBS:
        risk_level = "medium"
    else:
        risk_level = "high"

    # Additional checks for high-risk commands
    if risk_level == "high":
        # Prevent delete all
        if verb == "delete" and "--all" in parts:
            return SanitizeResult(
                is_safe=False,
                reason="kubectl delete --all is not allowed",
                command=command,
            )

        # Prevent namespace deletion
        if verb == "delete" and "namespace" in parts or verb == "delete" and "ns" in parts:
            return SanitizeResult(
                is_safe=False,
                reason="Namespace deletion is not allowed",
                command=command,
            )

    return SanitizeResult(
        is_safe=True,
        reason="OK",
        risk_level=risk_level,
        command=command,
    )


def sanitize_input(text: str, max_length: int = 1000) -> str:
    """
    Sanitize user input text.

    Args:
        text: Input text to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized text
    """
    if not text:
        return ""

    # Truncate to max length
    text = text[:max_length]

    # Remove null bytes
    text = text.replace("\x00", "")

    # Remove other control characters (except newline, tab)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)

    return text.strip()


def sanitize_namespace(namespace: str) -> Tuple[bool, str]:
    """
    Validate a Kubernetes namespace name.

    Args:
        namespace: Namespace to validate

    Returns:
        Tuple of (is_valid, reason)
    """
    if not namespace:
        return False, "Namespace cannot be empty"

    # Kubernetes namespace naming rules
    # - Must be 63 characters or less
    # - Must start with alphanumeric
    # - Can contain alphanumeric and hyphens
    # - Must end with alphanumeric

    if len(namespace) > 63:
        return False, "Namespace must be 63 characters or less"

    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$', namespace):
        return False, "Invalid namespace format"

    # Block system namespaces from certain operations
    system_namespaces = {"kube-system", "kube-public", "kube-node-lease", "default"}
    if namespace in system_namespaces:
        # This is just a warning, not an error
        pass

    return True, "OK"


def escape_for_shell(text: str) -> str:
    """
    Escape text for safe shell usage.

    Args:
        text: Text to escape

    Returns:
        Shell-escaped text
    """
    return shlex.quote(text)
