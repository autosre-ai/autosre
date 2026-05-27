"""
Input/Output Validators for AI Safety

Provides comprehensive validation for AI model inputs and outputs:
- Input sanitization and injection detection
- Output content filtering and classification
- Schema validation for structured responses
- Prompt injection defense mechanisms
"""

import asyncio
import hashlib
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, UTC, timezone
from enum import Enum
from typing import Any, Callable, Optional, Pattern

from pydantic import BaseModel, Field


class ValidationSeverity(str, Enum):
    """Severity levels for validation issues."""
    
    INFO = "info"           # Informational, no action needed
    WARNING = "warning"     # Potential issue, allow with logging
    ERROR = "error"         # Issue that should block action
    CRITICAL = "critical"   # Severe issue, must block and alert


class ContentCategory(str, Enum):
    """Categories of content for classification."""
    
    SAFE = "safe"
    SENSITIVE = "sensitive"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    MALICIOUS = "malicious"
    INJECTION = "injection"
    JAILBREAK = "jailbreak"
    TOXIC = "toxic"


class SanitizationType(str, Enum):
    """Types of input sanitization."""
    
    STRIP_HTML = "strip_html"
    ESCAPE_SPECIAL = "escape_special"
    NORMALIZE_UNICODE = "normalize_unicode"
    REMOVE_NULL_BYTES = "remove_null_bytes"
    TRUNCATE = "truncate"
    MASK_CREDENTIALS = "mask_credentials"
    MASK_PII = "mask_pii"
    CUSTOM = "custom"


class InjectionType(str, Enum):
    """Types of prompt injection attacks."""
    
    DIRECT = "direct"               # Direct instruction override
    INDIRECT = "indirect"           # Hidden instructions in data
    JAILBREAK = "jailbreak"         # Attempt to bypass restrictions
    EXTRACTION = "extraction"       # Data extraction attempts
    ROLEPLAY = "roleplay"           # Role-playing manipulation
    DELIMITER = "delimiter"         # Delimiter confusion
    ENCODING = "encoding"           # Encoded malicious content
    CONTEXT_SWITCH = "context_switch"  # Context switching attacks


class FilterAction(str, Enum):
    """Actions to take when content is filtered."""
    
    ALLOW = "allow"           # Allow content through
    WARN = "warn"             # Allow but log warning
    REDACT = "redact"         # Remove/mask specific content
    REPLACE = "replace"       # Replace with safe alternative
    BLOCK = "block"           # Block entirely
    ESCALATE = "escalate"     # Require human review


@dataclass
class ValidationResult:
    """Result of a validation check."""
    
    valid: bool
    severity: ValidationSeverity = ValidationSeverity.INFO
    category: Optional[ContentCategory] = None
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    validator_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float = 0.0
    
    # Remediation
    sanitized_content: Optional[str] = None
    suggested_action: Optional[FilterAction] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "valid": self.valid,
            "severity": self.severity.value,
            "category": self.category.value if self.category else None,
            "message": self.message,
            "details": self.details,
            "validator_id": self.validator_id,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
            "suggested_action": self.suggested_action.value if self.suggested_action else None,
        }


class SanitizationRule(BaseModel):
    """A rule for sanitizing input content."""
    
    id: str
    name: str
    type: SanitizationType
    enabled: bool = True
    
    # Configuration
    pattern: Optional[str] = None  # Regex pattern for matching
    replacement: str = ""          # Replacement text
    max_length: int = 0           # For truncation
    
    # Custom function (name of registered function)
    custom_function: Optional[str] = None
    
    # Scope
    applies_to: list[str] = Field(default_factory=lambda: ["all"])
    
    # Metadata
    description: str = ""
    priority: int = Field(default=100, ge=0)


class InputValidationConfig(BaseModel):
    """Configuration for input validation."""
    
    # Length limits
    max_length: int = Field(default=100000)
    min_length: int = Field(default=0)
    
    # Character restrictions
    allowed_characters: Optional[str] = None  # Regex character class
    blocked_patterns: list[str] = Field(default_factory=list)
    
    # Content restrictions
    block_code_execution: bool = True
    block_file_paths: bool = True
    block_urls: bool = False
    
    # Injection detection
    detect_injections: bool = True
    injection_sensitivity: float = Field(default=0.7, ge=0.0, le=1.0)
    
    # Sanitization
    sanitization_rules: list[SanitizationRule] = Field(default_factory=list)
    apply_default_sanitization: bool = True
    
    # Rate limiting
    max_requests_per_minute: int = Field(default=60)
    max_tokens_per_minute: int = Field(default=100000)


class OutputValidationConfig(BaseModel):
    """Configuration for output validation."""
    
    # Content filtering
    filter_sensitive_data: bool = True
    filter_pii: bool = True
    filter_credentials: bool = True
    
    # Response restrictions
    max_response_length: int = Field(default=500000)
    block_executable_code: bool = True
    require_json_schema: bool = False
    
    # Classification
    classify_content: bool = True
    block_categories: list[ContentCategory] = Field(
        default_factory=lambda: [ContentCategory.MALICIOUS, ContentCategory.TOXIC]
    )
    
    # Formatting
    enforce_response_format: bool = False
    response_format: Optional[str] = None  # JSON schema


class OutputClassification(BaseModel):
    """Classification of AI output content."""
    
    category: ContentCategory
    confidence: float = Field(ge=0.0, le=1.0)
    
    # Details
    detected_patterns: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    
    # Metadata
    model_used: str = ""
    classification_time_ms: float = 0.0


class ResponseSchemaConfig(BaseModel):
    """Configuration for response schema validation."""
    
    model_config = {"protected_namespaces": ()}
    
    json_schema: dict[str, Any] = Field(alias="schema")
    strict: bool = True
    allow_extra_fields: bool = False
    coerce_types: bool = False
    
    # Error handling
    return_partial_on_error: bool = False
    default_values: dict[str, Any] = Field(default_factory=dict)


class Validator(ABC):
    """Base class for all validators."""
    
    def __init__(self, validator_id: Optional[str] = None):
        self.validator_id = validator_id or self.__class__.__name__
        self._custom_functions: dict[str, Callable] = {}
    
    @abstractmethod
    async def validate(self, content: str, context: Optional[dict] = None) -> ValidationResult:
        """Validate content and return result."""
        pass
    
    def register_function(self, name: str, func: Callable) -> None:
        """Register a custom function for use in validation."""
        self._custom_functions[name] = func
    
    def _create_result(
        self,
        valid: bool,
        severity: ValidationSeverity = ValidationSeverity.INFO,
        message: str = "",
        **kwargs
    ) -> ValidationResult:
        """Helper to create validation result."""
        return ValidationResult(
            valid=valid,
            severity=severity,
            message=message,
            validator_id=self.validator_id,
            **kwargs
        )


class InputSanitizer:
    """Sanitizes input content before processing."""
    
    # Common PII patterns
    PII_PATTERNS = {
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "phone": r"\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b",
        "ssn": r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b",
        "credit_card": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
        "ip_address": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    }
    
    # Credential patterns
    CREDENTIAL_PATTERNS = {
        "api_key": r"(?i)(api[_-]?key|apikey)\s*[:=]\s*['\"]?[\w-]{20,}['\"]?",
        "aws_key": r"(?i)(AKIA|ABIA|ACCA|ASIA)[A-Z0-9]{16}",
        "password": r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?[^\s'\"]+['\"]?",
        "token": r"(?i)(token|bearer|auth)\s*[:=]\s*['\"]?[\w-]{20,}['\"]?",
        "secret": r"(?i)(secret|private[_-]?key)\s*[:=]\s*['\"]?[\w-]{20,}['\"]?",
    }
    
    def __init__(self, rules: Optional[list[SanitizationRule]] = None):
        self.rules = sorted(rules or [], key=lambda r: r.priority)
        self._compiled_patterns: dict[str, Pattern] = {}
    
    def sanitize(self, content: str, context: Optional[dict] = None) -> tuple[str, list[dict]]:
        """Sanitize content and return (sanitized_content, changes_made)."""
        changes: list[dict] = []
        result = content
        
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            original = result
            result = self._apply_rule(result, rule)
            
            if result != original:
                changes.append({
                    "rule_id": rule.id,
                    "rule_type": rule.type.value,
                    "original_length": len(original),
                    "new_length": len(result),
                })
        
        return result, changes
    
    def _apply_rule(self, content: str, rule: SanitizationRule) -> str:
        """Apply a single sanitization rule."""
        if rule.type == SanitizationType.STRIP_HTML:
            return re.sub(r"<[^>]+>", "", content)
        
        elif rule.type == SanitizationType.ESCAPE_SPECIAL:
            # Escape common special characters
            special = {"<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;"}
            for char, escape in special.items():
                content = content.replace(char, escape)
            return content
        
        elif rule.type == SanitizationType.NORMALIZE_UNICODE:
            import unicodedata
            return unicodedata.normalize("NFKC", content)
        
        elif rule.type == SanitizationType.REMOVE_NULL_BYTES:
            return content.replace("\x00", "")
        
        elif rule.type == SanitizationType.TRUNCATE:
            if rule.max_length > 0 and len(content) > rule.max_length:
                return content[:rule.max_length] + "..."
            return content
        
        elif rule.type == SanitizationType.MASK_CREDENTIALS:
            result = content
            for name, pattern in self.CREDENTIAL_PATTERNS.items():
                result = re.sub(
                    pattern,
                    f"[{name.upper()}_REDACTED]",
                    result
                )
            return result
        
        elif rule.type == SanitizationType.MASK_PII:
            result = content
            for name, pattern in self.PII_PATTERNS.items():
                result = re.sub(
                    pattern,
                    f"[{name.upper()}_MASKED]",
                    result
                )
            return result
        
        elif rule.type == SanitizationType.CUSTOM:
            if rule.pattern:
                compiled = self._get_pattern(rule.pattern)
                return compiled.sub(rule.replacement, content)
            return content
        
        return content
    
    def _get_pattern(self, pattern: str) -> Pattern:
        """Get or compile a regex pattern."""
        if pattern not in self._compiled_patterns:
            self._compiled_patterns[pattern] = re.compile(pattern)
        return self._compiled_patterns[pattern]


class PromptInjectionDetector:
    """Detects prompt injection attacks in input content."""
    
    # Injection patterns by type
    INJECTION_PATTERNS = {
        InjectionType.DIRECT: [
            r"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?)",
            r"(?i)disregard\s+(all\s+)?(your\s+)?instructions?",
            r"(?i)forget\s+(everything|all)\s+(you\s+)?(were|have been)\s+told",
            r"(?i)new\s+instructions?:\s*",
            r"(?i)system:\s*you\s+are\s+now",
            r"(?i)override\s+(your\s+)?(programming|instructions?)",
        ],
        InjectionType.JAILBREAK: [
            r"(?i)pretend\s+(you\s+are|to\s+be)\s+(an?\s+)?(evil|unrestricted|unfiltered)",
            r"(?i)act\s+as\s+(an?\s+)?(uncensored|unrestricted)",
            r"(?i)dan\s+mode",
            r"(?i)developer\s+mode\s+enabled",
            r"(?i)hypothetically\s+speaking\s*,?\s*if\s+you\s+had\s+no\s+restrictions",
            r"(?i)in\s+this\s+fictional\s+scenario\s+where\s+rules?\s+don'?t\s+apply",
        ],
        InjectionType.DELIMITER: [
            r"\[/?SYSTEM\]",
            r"\[/?USER\]",
            r"\[/?ASSISTANT\]",
            r"<\|?system\|?>",
            r"<\|?user\|?>",
            r"<\|?assistant\|?>",
            r"###\s*(system|user|assistant)",
        ],
        InjectionType.EXTRACTION: [
            r"(?i)what\s+are\s+your\s+(system\s+)?instructions",
            r"(?i)repeat\s+(your\s+)?(system\s+)?prompt",
            r"(?i)show\s+me\s+your\s+(hidden|secret)\s+instructions",
            r"(?i)output\s+your\s+(system|initial)\s+prompt",
            r"(?i)reveal\s+(the|your)\s+prompt",
        ],
        InjectionType.ROLEPLAY: [
            r"(?i)you\s+are\s+now\s+playing\s+(the\s+)?(role|character)\s+of",
            r"(?i)imagine\s+you\s+(are|were)\s+a(n)?\s+\w+\s+without\s+restrictions",
            r"(?i)let'?s\s+roleplay",
            r"(?i)you\s+are\s+no\s+longer\s+(an?\s+)?ai",
        ],
        InjectionType.ENCODING: [
            r"(?i)decode\s+this\s+base64",
            r"(?i)execute\s+this\s+encoded",
            r"(?:eval|exec)\s*\(",
            r"(?i)rot13:\s*",
        ],
        InjectionType.CONTEXT_SWITCH: [
            r"(?i)now\s+let'?s\s+change\s+the\s+topic",
            r"(?i)but\s+first\s*,?\s*(let'?s|I\s+need\s+you\s+to)",
            r"(?i)before\s+that\s*,?\s*(do|answer|tell\s+me)",
        ],
    }
    
    def __init__(self, sensitivity: float = 0.7):
        self.sensitivity = sensitivity
        self._compiled_patterns: dict[InjectionType, list[Pattern]] = {}
        self._compile_patterns()
    
    def _compile_patterns(self) -> None:
        """Compile all regex patterns."""
        for injection_type, patterns in self.INJECTION_PATTERNS.items():
            self._compiled_patterns[injection_type] = [
                re.compile(p) for p in patterns
            ]
    
    def detect(self, content: str) -> tuple[bool, list[dict]]:
        """Detect injection attempts in content.
        
        Returns (is_injection, detections).
        """
        detections: list[dict] = []
        content_lower = content.lower()
        
        for injection_type, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                matches = pattern.findall(content)
                if matches:
                    detections.append({
                        "type": injection_type.value,
                        "pattern": pattern.pattern,
                        "matches": matches[:5],  # Limit match count
                        "confidence": self._calculate_confidence(
                            injection_type, len(matches)
                        ),
                    })
        
        # Apply sensitivity threshold
        if detections:
            max_confidence = max(d["confidence"] for d in detections)
            is_injection = max_confidence >= self.sensitivity
        else:
            is_injection = False
        
        return is_injection, detections
    
    def _calculate_confidence(self, injection_type: InjectionType, match_count: int) -> float:
        """Calculate confidence score for detection."""
        # Base confidence by type
        base_confidence = {
            InjectionType.DIRECT: 0.9,
            InjectionType.JAILBREAK: 0.85,
            InjectionType.DELIMITER: 0.8,
            InjectionType.EXTRACTION: 0.75,
            InjectionType.ROLEPLAY: 0.6,
            InjectionType.ENCODING: 0.7,
            InjectionType.CONTEXT_SWITCH: 0.5,
        }.get(injection_type, 0.5)
        
        # Boost for multiple matches
        confidence = base_confidence + (min(match_count - 1, 3) * 0.05)
        
        return min(confidence, 1.0)


class InputValidator(Validator):
    """Validates AI model input content."""
    
    def __init__(
        self,
        config: Optional[InputValidationConfig] = None,
        validator_id: Optional[str] = None,
    ):
        super().__init__(validator_id)
        self.config = config or InputValidationConfig()
        
        self.sanitizer = InputSanitizer(
            rules=self.config.sanitization_rules
        )
        self.injection_detector = PromptInjectionDetector(
            sensitivity=self.config.injection_sensitivity
        )
        
        # Compile blocked patterns
        self._blocked_patterns = [
            re.compile(p) for p in self.config.blocked_patterns
        ]
    
    async def validate(
        self,
        content: str,
        context: Optional[dict] = None,
    ) -> ValidationResult:
        """Validate input content."""
        start_time = datetime.now(UTC)
        context = context or {}
        issues: list[dict] = []
        
        # Length validation
        if len(content) > self.config.max_length:
            return self._create_result(
                valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Content exceeds maximum length ({len(content)} > {self.config.max_length})",
                category=ContentCategory.RESTRICTED,
                suggested_action=FilterAction.BLOCK,
            )
        
        if len(content) < self.config.min_length:
            return self._create_result(
                valid=False,
                severity=ValidationSeverity.WARNING,
                message=f"Content below minimum length ({len(content)} < {self.config.min_length})",
                suggested_action=FilterAction.WARN,
            )
        
        # Check blocked patterns
        for pattern in self._blocked_patterns:
            if pattern.search(content):
                issues.append({
                    "type": "blocked_pattern",
                    "pattern": pattern.pattern,
                })
        
        # Check for code execution attempts
        if self.config.block_code_execution:
            code_patterns = [
                r"(?:eval|exec|compile)\s*\(",
                r"__import__\s*\(",
                r"subprocess\.",
                r"os\.system\s*\(",
                r"<script[^>]*>",
            ]
            for pattern in code_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    issues.append({
                        "type": "code_execution",
                        "pattern": pattern,
                    })
        
        # Check injection attempts
        if self.config.detect_injections:
            is_injection, detections = self.injection_detector.detect(content)
            if is_injection:
                duration = (datetime.now(UTC) - start_time).total_seconds() * 1000
                return self._create_result(
                    valid=False,
                    severity=ValidationSeverity.CRITICAL,
                    message="Potential prompt injection detected",
                    category=ContentCategory.INJECTION,
                    details={"detections": detections},
                    suggested_action=FilterAction.BLOCK,
                    duration_ms=duration,
                )
        
        # Apply sanitization
        sanitized, changes = self.sanitizer.sanitize(content, context)
        
        # Build result
        duration = (datetime.now(UTC) - start_time).total_seconds() * 1000
        
        if issues:
            return self._create_result(
                valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Found {len(issues)} validation issues",
                details={"issues": issues},
                suggested_action=FilterAction.BLOCK,
                duration_ms=duration,
            )
        
        return self._create_result(
            valid=True,
            severity=ValidationSeverity.INFO,
            message="Input validation passed",
            category=ContentCategory.SAFE,
            sanitized_content=sanitized if changes else None,
            details={"sanitization_changes": changes} if changes else {},
            suggested_action=FilterAction.ALLOW,
            duration_ms=duration,
        )


class ContentFilter:
    """Filters content based on classification rules."""
    
    # Toxic content patterns
    TOXIC_PATTERNS = [
        r"(?i)\b(kill|murder|attack|harm)\s+(yourself|yourself|him|her|them)\b",
        r"(?i)how\s+to\s+(make|build|create)\s+(a\s+)?(bomb|weapon|explosive)",
        r"(?i)instructions\s+for\s+(creating|making)\s+.*\s+(weapon|drug|explosive)",
    ]
    
    def __init__(
        self,
        block_categories: Optional[list[ContentCategory]] = None,
    ):
        self.block_categories = block_categories or [
            ContentCategory.MALICIOUS,
            ContentCategory.TOXIC,
        ]
        self._toxic_patterns = [re.compile(p) for p in self.TOXIC_PATTERNS]
    
    def filter(
        self,
        content: str,
        context: Optional[dict] = None,
    ) -> tuple[str, FilterAction, list[dict]]:
        """Filter content and return (filtered_content, action, reasons).
        
        Returns the filtered content, action taken, and list of reasons.
        """
        reasons: list[dict] = []
        
        # Check for toxic content
        for pattern in self._toxic_patterns:
            if pattern.search(content):
                reasons.append({
                    "type": "toxic_content",
                    "pattern": pattern.pattern,
                })
        
        if reasons:
            # Check if any blocked category applies
            for reason in reasons:
                if reason["type"] == "toxic_content":
                    if ContentCategory.TOXIC in self.block_categories:
                        return "", FilterAction.BLOCK, reasons
                    else:
                        return content, FilterAction.WARN, reasons
        
        return content, FilterAction.ALLOW, reasons


class OutputValidator(Validator):
    """Validates AI model output content."""
    
    def __init__(
        self,
        config: Optional[OutputValidationConfig] = None,
        validator_id: Optional[str] = None,
    ):
        super().__init__(validator_id)
        self.config = config or OutputValidationConfig()
        
        self.sanitizer = InputSanitizer(rules=[
            SanitizationRule(
                id="mask_creds",
                name="Mask Credentials",
                type=SanitizationType.MASK_CREDENTIALS,
                enabled=self.config.filter_credentials,
            ),
            SanitizationRule(
                id="mask_pii",
                name="Mask PII",
                type=SanitizationType.MASK_PII,
                enabled=self.config.filter_pii,
            ),
        ])
        
        self.content_filter = ContentFilter(
            block_categories=self.config.block_categories
        )
    
    async def validate(
        self,
        content: str,
        context: Optional[dict] = None,
    ) -> ValidationResult:
        """Validate output content."""
        start_time = datetime.now(UTC)
        context = context or {}
        
        # Length validation
        if len(content) > self.config.max_response_length:
            return self._create_result(
                valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Response exceeds maximum length ({len(content)} > {self.config.max_response_length})",
                suggested_action=FilterAction.BLOCK,
            )
        
        # Content filtering
        filtered_content, action, filter_reasons = self.content_filter.filter(
            content, context
        )
        
        if action == FilterAction.BLOCK:
            duration = (datetime.now(UTC) - start_time).total_seconds() * 1000
            return self._create_result(
                valid=False,
                severity=ValidationSeverity.CRITICAL,
                message="Content blocked by filter",
                category=ContentCategory.RESTRICTED,
                details={"filter_reasons": filter_reasons},
                suggested_action=FilterAction.BLOCK,
                duration_ms=duration,
            )
        
        # Sanitize sensitive data
        if self.config.filter_sensitive_data:
            sanitized, changes = self.sanitizer.sanitize(content, context)
        else:
            sanitized, changes = content, []
        
        # Check for executable code
        if self.config.block_executable_code:
            code_patterns = [
                r"```(?:python|bash|sh|javascript|js).*?```",
                r"<script[^>]*>.*?</script>",
            ]
            for pattern in code_patterns:
                if re.search(pattern, content, re.IGNORECASE | re.DOTALL):
                    # This is a warning since code in responses might be intentional
                    pass
        
        duration = (datetime.now(UTC) - start_time).total_seconds() * 1000
        
        return self._create_result(
            valid=True,
            severity=ValidationSeverity.WARNING if filter_reasons else ValidationSeverity.INFO,
            message="Output validation passed" if not filter_reasons else "Output validated with warnings",
            category=ContentCategory.SAFE,
            sanitized_content=sanitized if changes else None,
            details={
                "sanitization_changes": changes,
                "filter_warnings": filter_reasons,
            } if changes or filter_reasons else {},
            suggested_action=action,
            duration_ms=duration,
        )


class PromptValidator(Validator):
    """Validates prompts before sending to AI models."""
    
    def __init__(
        self,
        max_prompt_length: int = 100000,
        max_messages: int = 100,
        validator_id: Optional[str] = None,
    ):
        super().__init__(validator_id)
        self.max_prompt_length = max_prompt_length
        self.max_messages = max_messages
        
        self.injection_detector = PromptInjectionDetector(sensitivity=0.8)
    
    async def validate(
        self,
        content: str,
        context: Optional[dict] = None,
    ) -> ValidationResult:
        """Validate a prompt."""
        start_time = datetime.now(UTC)
        
        # Length check
        if len(content) > self.max_prompt_length:
            return self._create_result(
                valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Prompt exceeds maximum length",
                suggested_action=FilterAction.BLOCK,
            )
        
        # Injection detection
        is_injection, detections = self.injection_detector.detect(content)
        
        duration = (datetime.now(UTC) - start_time).total_seconds() * 1000
        
        if is_injection:
            return self._create_result(
                valid=False,
                severity=ValidationSeverity.CRITICAL,
                message="Potential prompt injection detected",
                category=ContentCategory.INJECTION,
                details={"detections": detections},
                suggested_action=FilterAction.BLOCK,
                duration_ms=duration,
            )
        
        return self._create_result(
            valid=True,
            message="Prompt validation passed",
            category=ContentCategory.SAFE,
            suggested_action=FilterAction.ALLOW,
            duration_ms=duration,
        )
    
    async def validate_conversation(
        self,
        messages: list[dict[str, str]],
    ) -> ValidationResult:
        """Validate a conversation (list of messages)."""
        start_time = datetime.now(UTC)
        
        if len(messages) > self.max_messages:
            return self._create_result(
                valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Conversation exceeds maximum message count ({len(messages)} > {self.max_messages})",
                suggested_action=FilterAction.BLOCK,
            )
        
        # Validate each message
        all_detections: list[dict] = []
        total_length = 0
        
        for i, msg in enumerate(messages):
            content = msg.get("content", "")
            total_length += len(content)
            
            if total_length > self.max_prompt_length:
                return self._create_result(
                    valid=False,
                    severity=ValidationSeverity.ERROR,
                    message="Total conversation length exceeds maximum",
                    suggested_action=FilterAction.BLOCK,
                )
            
            # Check user messages for injections
            if msg.get("role") == "user":
                is_injection, detections = self.injection_detector.detect(content)
                if detections:
                    for d in detections:
                        d["message_index"] = i
                    all_detections.extend(detections)
        
        duration = (datetime.now(UTC) - start_time).total_seconds() * 1000
        
        if all_detections:
            max_confidence = max(d["confidence"] for d in all_detections)
            if max_confidence >= 0.8:
                return self._create_result(
                    valid=False,
                    severity=ValidationSeverity.CRITICAL,
                    message="Injection detected in conversation",
                    category=ContentCategory.INJECTION,
                    details={"detections": all_detections},
                    suggested_action=FilterAction.BLOCK,
                    duration_ms=duration,
                )
        
        return self._create_result(
            valid=True,
            message="Conversation validation passed",
            category=ContentCategory.SAFE,
            details={"message_count": len(messages), "total_length": total_length},
            suggested_action=FilterAction.ALLOW,
            duration_ms=duration,
        )


class SchemaValidator(Validator):
    """Validates AI responses against JSON schemas."""
    
    def __init__(
        self,
        config: Optional[ResponseSchemaConfig] = None,
        validator_id: Optional[str] = None,
    ):
        super().__init__(validator_id)
        self.config = config
    
    async def validate(
        self,
        content: str,
        context: Optional[dict] = None,
    ) -> ValidationResult:
        """Validate content against schema."""
        start_time = datetime.now(UTC)
        
        if not self.config:
            return self._create_result(
                valid=True,
                message="No schema configured, skipping validation",
                suggested_action=FilterAction.ALLOW,
            )
        
        # Try to parse JSON
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            duration = (datetime.now(UTC) - start_time).total_seconds() * 1000
            return self._create_result(
                valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Invalid JSON: {str(e)}",
                details={"parse_error": str(e)},
                suggested_action=FilterAction.BLOCK,
                duration_ms=duration,
            )
        
        # Validate against schema
        errors = self._validate_schema(data, self.config.json_schema)
        
        duration = (datetime.now(UTC) - start_time).total_seconds() * 1000
        
        if errors:
            if self.config.strict:
                return self._create_result(
                    valid=False,
                    severity=ValidationSeverity.ERROR,
                    message=f"Schema validation failed with {len(errors)} errors",
                    details={"schema_errors": errors},
                    suggested_action=FilterAction.BLOCK,
                    duration_ms=duration,
                )
            else:
                return self._create_result(
                    valid=True,
                    severity=ValidationSeverity.WARNING,
                    message=f"Schema validation passed with {len(errors)} warnings",
                    details={"schema_warnings": errors},
                    suggested_action=FilterAction.WARN,
                    duration_ms=duration,
                )
        
        return self._create_result(
            valid=True,
            message="Schema validation passed",
            suggested_action=FilterAction.ALLOW,
            duration_ms=duration,
        )
    
    def _validate_schema(self, data: Any, schema: dict) -> list[str]:
        """Simple schema validation (for full validation use jsonschema library)."""
        errors: list[str] = []
        
        if "type" in schema:
            expected_type = schema["type"]
            actual_type = type(data).__name__
            type_map = {
                "string": "str",
                "integer": "int",
                "number": ("int", "float"),
                "boolean": "bool",
                "array": "list",
                "object": "dict",
            }
            
            expected = type_map.get(expected_type, expected_type)
            if isinstance(expected, tuple):
                if actual_type not in expected:
                    errors.append(f"Expected type {expected_type}, got {actual_type}")
            elif actual_type != expected:
                errors.append(f"Expected type {expected_type}, got {actual_type}")
        
        if "required" in schema and isinstance(data, dict):
            for field in schema["required"]:
                if field not in data:
                    errors.append(f"Missing required field: {field}")
        
        if "properties" in schema and isinstance(data, dict):
            if not self.config.allow_extra_fields:
                allowed_fields = set(schema["properties"].keys())
                actual_fields = set(data.keys())
                extra_fields = actual_fields - allowed_fields
                if extra_fields:
                    errors.append(f"Extra fields not allowed: {extra_fields}")
        
        return errors
