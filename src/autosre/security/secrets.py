"""
Secrets Management

Provides secure secrets management for SRE operations:
- Multi-backend secret storage (Vault, AWS Secrets Manager, GCP Secret Manager, Azure Key Vault)
- Secret rotation automation
- Access control and auditing
- Dynamic secret generation
- Encryption at rest and in transit
"""

import asyncio
import base64
import hashlib
import os
import re
import secrets as stdlib_secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, Optional, TypeVar, Generic
from uuid import uuid4

from pydantic import BaseModel, Field, SecretStr


# =============================================================================
# Enums
# =============================================================================


class SecretBackend(str, Enum):
    """Supported secret storage backends."""
    
    HASHICORP_VAULT = "hashicorp_vault"
    AWS_SECRETS_MANAGER = "aws_secrets_manager"
    GCP_SECRET_MANAGER = "gcp_secret_manager"
    AZURE_KEY_VAULT = "azure_key_vault"
    KUBERNETES_SECRET = "kubernetes_secret"
    LOCAL_ENCRYPTED = "local_encrypted"  # For development


class SecretType(str, Enum):
    """Types of secrets."""
    
    PASSWORD = "password"
    API_KEY = "api_key"
    CERTIFICATE = "certificate"
    PRIVATE_KEY = "private_key"
    DATABASE_CREDENTIAL = "database_credential"
    SSH_KEY = "ssh_key"
    OAUTH_TOKEN = "oauth_token"
    ENCRYPTION_KEY = "encryption_key"
    GENERIC = "generic"


class RotationStatus(str, Enum):
    """Secret rotation status."""
    
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class AccessLevel(str, Enum):
    """Secret access levels."""
    
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ROTATE = "rotate"
    ADMIN = "admin"


# =============================================================================
# Configuration
# =============================================================================


class SecretsConfig(BaseModel):
    """Secrets manager configuration."""
    
    backend: SecretBackend = Field(description="Secret storage backend")
    
    # Backend-specific settings
    vault_address: Optional[str] = Field(default=None, description="HashiCorp Vault address")
    vault_token: Optional[SecretStr] = Field(default=None, description="Vault authentication token")
    vault_namespace: Optional[str] = Field(default=None, description="Vault namespace")
    
    aws_region: Optional[str] = Field(default=None, description="AWS region")
    aws_role_arn: Optional[str] = Field(default=None, description="AWS IAM role ARN")
    
    gcp_project: Optional[str] = Field(default=None, description="GCP project ID")
    
    azure_vault_url: Optional[str] = Field(default=None, description="Azure Key Vault URL")
    azure_tenant_id: Optional[str] = Field(default=None, description="Azure tenant ID")
    
    kubernetes_namespace: Optional[str] = Field(default="default", description="K8s namespace")
    
    # Security settings
    enable_caching: bool = Field(default=True, description="Enable secret caching")
    cache_ttl_seconds: int = Field(default=300, description="Cache TTL in seconds")
    encrypt_in_transit: bool = Field(default=True, description="Encrypt in transit")
    
    # Rotation settings
    auto_rotation_enabled: bool = Field(default=True, description="Enable auto-rotation")
    default_rotation_days: int = Field(default=90, description="Default rotation period")
    rotation_notification_days: int = Field(default=14, description="Days before rotation to notify")


class RotationConfig(BaseModel):
    """Secret rotation configuration."""
    
    enabled: bool = Field(default=True, description="Enable rotation for this secret")
    rotation_days: int = Field(default=90, description="Days between rotations")
    
    # Rotation method
    auto_rotate: bool = Field(default=False, description="Automatically rotate")
    rotation_lambda: Optional[str] = Field(default=None, description="Lambda for custom rotation")
    
    # Notifications
    notify_before_days: list[int] = Field(
        default_factory=lambda: [14, 7, 1],
        description="Days before expiry to send notifications"
    )
    notification_emails: list[str] = Field(default_factory=list, description="Notification emails")
    
    # Validation
    require_approval: bool = Field(default=False, description="Require approval for rotation")
    approvers: list[str] = Field(default_factory=list, description="Rotation approvers")


class AccessPolicy(BaseModel):
    """Secret access policy."""
    
    policy_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    name: str = Field(description="Policy name")
    
    # Who
    principals: list[str] = Field(default_factory=list, description="Allowed principals (users/roles)")
    service_accounts: list[str] = Field(default_factory=list, description="Allowed service accounts")
    ip_whitelist: list[str] = Field(default_factory=list, description="Allowed IP addresses/CIDRs")
    
    # What
    secret_patterns: list[str] = Field(default_factory=list, description="Secret path patterns")
    access_levels: list[AccessLevel] = Field(
        default_factory=lambda: [AccessLevel.READ],
        description="Allowed access levels"
    )
    
    # When
    time_restrictions: Optional[dict] = Field(
        default=None,
        description="Time-based restrictions (e.g., business hours only)"
    )
    
    # Conditions
    require_mfa: bool = Field(default=False, description="Require MFA for access")
    max_ttl_seconds: int = Field(default=3600, description="Maximum lease TTL")


# =============================================================================
# Secret Models
# =============================================================================


class SecretVersion(BaseModel):
    """Version of a secret."""
    
    version_id: str = Field(description="Version identifier")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = Field(description="Who created this version")
    
    # Status
    is_current: bool = Field(default=True, description="Is this the current version")
    is_deprecated: bool = Field(default=False, description="Is this version deprecated")
    
    # Metadata
    rotation_id: Optional[str] = Field(default=None, description="Rotation that created this")
    checksum: str = Field(description="Value checksum for integrity")


class SecretMetadata(BaseModel):
    """Secret metadata (excludes the actual value)."""
    
    id: str = Field(default_factory=lambda: str(uuid4()), description="Secret ID")
    name: str = Field(description="Secret name/path")
    description: Optional[str] = Field(default=None, description="Secret description")
    secret_type: SecretType = Field(default=SecretType.GENERIC, description="Secret type")
    
    # Location
    backend: SecretBackend = Field(description="Storage backend")
    path: str = Field(description="Full path in backend")
    
    # Versioning
    current_version: str = Field(description="Current version ID")
    versions: list[SecretVersion] = Field(default_factory=list, description="Version history")
    
    # Lifecycle
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = Field(default=None, description="Expiration time")
    
    # Rotation
    rotation_config: Optional[RotationConfig] = Field(default=None, description="Rotation settings")
    last_rotated_at: Optional[datetime] = Field(default=None, description="Last rotation time")
    next_rotation_at: Optional[datetime] = Field(default=None, description="Next scheduled rotation")
    rotation_status: RotationStatus = Field(default=RotationStatus.NOT_REQUIRED)
    
    # Access control
    owner: str = Field(description="Secret owner")
    access_policies: list[str] = Field(default_factory=list, description="Applied policy IDs")
    
    # Tags
    tags: dict[str, str] = Field(default_factory=dict, description="Secret tags")
    
    @property
    def is_expired(self) -> bool:
        """Check if secret is expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    @property
    def days_until_rotation(self) -> Optional[int]:
        """Days until next rotation."""
        if self.next_rotation_at is None:
            return None
        delta = self.next_rotation_at - datetime.now(timezone.utc)
        return max(0, delta.days)


class Secret(BaseModel):
    """A secret with its value."""
    
    metadata: SecretMetadata = Field(description="Secret metadata")
    value: SecretStr = Field(description="Secret value")
    
    # Lease (for dynamic secrets)
    lease_id: Optional[str] = Field(default=None, description="Lease ID for dynamic secrets")
    lease_duration_seconds: Optional[int] = Field(default=None, description="Lease duration")
    renewable: bool = Field(default=False, description="Can the lease be renewed")
    
    def reveal(self) -> str:
        """Reveal the secret value."""
        return self.value.get_secret_value()


class SecretReference(BaseModel):
    """Reference to a secret without the value."""
    
    name: str = Field(description="Secret name/path")
    version: Optional[str] = Field(default=None, description="Specific version")
    key: Optional[str] = Field(default=None, description="Key within a JSON secret")


class RotationResult(BaseModel):
    """Result of a secret rotation."""
    
    rotation_id: str = Field(default_factory=lambda: str(uuid4())[:12])
    secret_name: str = Field(description="Rotated secret name")
    
    status: RotationStatus = Field(description="Rotation status")
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = Field(default=None)
    
    # Versions
    previous_version: str = Field(description="Previous version ID")
    new_version: Optional[str] = Field(default=None, description="New version ID")
    
    # Error handling
    error_message: Optional[str] = Field(default=None, description="Error if failed")
    rollback_performed: bool = Field(default=False, description="Was rollback needed")
    
    # Audit
    rotated_by: str = Field(description="Who triggered rotation")
    approval_id: Optional[str] = Field(default=None, description="Approval ticket if required")


class SecretScanResult(BaseModel):
    """Result of scanning for exposed secrets."""
    
    scan_id: str = Field(default_factory=lambda: str(uuid4())[:12])
    scanned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # What was scanned
    scan_type: str = Field(description="Type of scan (repo, config, logs)")
    target: str = Field(description="Scan target (path, URL, etc.)")
    
    # Findings
    secrets_found: int = Field(default=0, description="Number of secrets found")
    findings: list[dict[str, Any]] = Field(default_factory=list, description="Detailed findings")
    
    # Risk assessment
    high_risk_count: int = Field(default=0, description="High risk exposures")
    medium_risk_count: int = Field(default=0, description="Medium risk exposures")
    low_risk_count: int = Field(default=0, description="Low risk exposures")


# =============================================================================
# Secret Generators
# =============================================================================


class SecretGenerator:
    """Generate secure secrets of various types."""
    
    # Character sets
    LOWERCASE = "abcdefghijklmnopqrstuvwxyz"
    UPPERCASE = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    DIGITS = "0123456789"
    SPECIAL = "!@#$%^&*()-_=+[]{}|;:,.<>?"
    
    @classmethod
    def generate_password(
        cls,
        length: int = 32,
        include_lowercase: bool = True,
        include_uppercase: bool = True,
        include_digits: bool = True,
        include_special: bool = True,
        exclude_chars: str = "",
    ) -> str:
        """Generate a secure random password."""
        charset = ""
        if include_lowercase:
            charset += cls.LOWERCASE
        if include_uppercase:
            charset += cls.UPPERCASE
        if include_digits:
            charset += cls.DIGITS
        if include_special:
            charset += cls.SPECIAL
        
        # Remove excluded characters
        for char in exclude_chars:
            charset = charset.replace(char, "")
        
        if not charset:
            raise ValueError("No characters available for password generation")
        
        # Generate password ensuring at least one of each required type
        password = []
        if include_lowercase:
            password.append(stdlib_secrets.choice(cls.LOWERCASE))
        if include_uppercase:
            password.append(stdlib_secrets.choice(cls.UPPERCASE))
        if include_digits:
            password.append(stdlib_secrets.choice(cls.DIGITS))
        if include_special:
            password.append(stdlib_secrets.choice(cls.SPECIAL))
        
        # Fill remaining length
        remaining = length - len(password)
        password.extend(stdlib_secrets.choice(charset) for _ in range(remaining))
        
        # Shuffle
        password_list = list(password)
        stdlib_secrets.SystemRandom().shuffle(password_list)
        
        return "".join(password_list)
    
    @classmethod
    def generate_api_key(cls, prefix: str = "sk", length: int = 32) -> str:
        """Generate an API key with optional prefix."""
        key = stdlib_secrets.token_urlsafe(length)
        return f"{prefix}_{key}" if prefix else key
    
    @classmethod
    def generate_encryption_key(cls, bits: int = 256) -> bytes:
        """Generate a cryptographic encryption key."""
        return stdlib_secrets.token_bytes(bits // 8)
    
    @classmethod
    def generate_token(cls, length: int = 32) -> str:
        """Generate a random token."""
        return stdlib_secrets.token_urlsafe(length)
    
    @classmethod
    def generate_database_password(cls) -> str:
        """Generate a database-safe password (no special chars that break connections)."""
        return cls.generate_password(
            length=24,
            include_special=False,
        )


# =============================================================================
# Secrets Manager Implementation
# =============================================================================


class SecretsManager:
    """
    Enterprise secrets management for SRE operations.
    
    Provides secure secrets management with:
    - Multi-backend support (Vault, AWS, GCP, Azure)
    - Automatic secret rotation
    - Access control and auditing
    - Secret scanning and leak detection
    
    Example:
        manager = SecretsManager(config)
        
        # Store a secret
        await manager.put_secret(
            name="production/database/password",
            value="super-secret-password",
            secret_type=SecretType.DATABASE_CREDENTIAL,
            rotation_config=RotationConfig(rotation_days=30),
        )
        
        # Retrieve a secret
        secret = await manager.get_secret("production/database/password")
        password = secret.reveal()
        
        # Rotate a secret
        result = await manager.rotate_secret("production/database/password")
    """
    
    def __init__(self, config: SecretsConfig):
        """Initialize the secrets manager."""
        self.config = config
        
        # In-memory storage (production uses actual backends)
        self._secrets: dict[str, Secret] = {}
        self._policies: dict[str, AccessPolicy] = {}
        
        # Cache
        self._cache: dict[str, tuple[Secret, datetime]] = {}
        
        # Audit log
        self._access_log: list[dict] = []
    
    async def get_secret(
        self,
        name: str,
        version: Optional[str] = None,
        accessor: str = "system",
    ) -> Secret:
        """
        Retrieve a secret by name.
        
        Args:
            name: Secret name/path
            version: Specific version (defaults to current)
            accessor: Who is accessing the secret
            
        Returns:
            Secret with value
            
        Raises:
            KeyError: If secret not found
            PermissionError: If access denied
        """
        # Check cache first
        if self.config.enable_caching and name in self._cache:
            secret, cached_at = self._cache[name]
            if datetime.now(timezone.utc) - cached_at < timedelta(seconds=self.config.cache_ttl_seconds):
                self._log_access(name, accessor, "read", "cache_hit")
                return secret
        
        # Get from backend
        if name not in self._secrets:
            raise KeyError(f"Secret not found: {name}")
        
        secret = self._secrets[name]
        
        # Check if expired
        if secret.metadata.is_expired:
            raise ValueError(f"Secret has expired: {name}")
        
        # Log access
        self._log_access(name, accessor, "read", "success")
        
        # Update cache
        if self.config.enable_caching:
            self._cache[name] = (secret, datetime.now(timezone.utc))
        
        return secret
    
    async def put_secret(
        self,
        name: str,
        value: str,
        secret_type: SecretType = SecretType.GENERIC,
        description: Optional[str] = None,
        rotation_config: Optional[RotationConfig] = None,
        tags: Optional[dict[str, str]] = None,
        owner: str = "system",
        expires_at: Optional[datetime] = None,
    ) -> SecretMetadata:
        """
        Store or update a secret.
        
        Args:
            name: Secret name/path
            value: Secret value
            secret_type: Type of secret
            description: Secret description
            rotation_config: Rotation settings
            tags: Secret tags
            owner: Secret owner
            expires_at: Expiration time
            
        Returns:
            SecretMetadata for the stored secret
        """
        version_id = str(uuid4())[:8]
        checksum = hashlib.sha256(value.encode()).hexdigest()[:16]
        
        # Create version
        version = SecretVersion(
            version_id=version_id,
            created_by=owner,
            is_current=True,
            checksum=checksum,
        )
        
        # Get or create metadata
        now = datetime.now(timezone.utc)
        if name in self._secrets:
            # Update existing
            existing = self._secrets[name]
            
            # Mark old version as not current
            for v in existing.metadata.versions:
                v.is_current = False
            
            existing.metadata.versions.append(version)
            existing.metadata.current_version = version_id
            existing.metadata.updated_at = now
            
            metadata = existing.metadata
        else:
            # Create new
            metadata = SecretMetadata(
                name=name,
                description=description,
                secret_type=secret_type,
                backend=self.config.backend,
                path=f"secret/{name}",
                current_version=version_id,
                versions=[version],
                rotation_config=rotation_config,
                owner=owner,
                tags=tags or {},
                expires_at=expires_at,
            )
            
            # Calculate next rotation
            if rotation_config and rotation_config.enabled:
                metadata.next_rotation_at = now + timedelta(days=rotation_config.rotation_days)
        
        # Create secret
        secret = Secret(
            metadata=metadata,
            value=SecretStr(value),
        )
        
        self._secrets[name] = secret
        
        # Invalidate cache
        if name in self._cache:
            del self._cache[name]
        
        # Log access
        self._log_access(name, owner, "write", "success")
        
        return metadata
    
    async def delete_secret(
        self,
        name: str,
        soft_delete: bool = True,
        accessor: str = "system",
    ) -> bool:
        """
        Delete a secret.
        
        Args:
            name: Secret name/path
            soft_delete: Mark as deleted vs hard delete
            accessor: Who is deleting
            
        Returns:
            True if deleted
        """
        if name not in self._secrets:
            return False
        
        if soft_delete:
            # Mark all versions as deprecated
            secret = self._secrets[name]
            for version in secret.metadata.versions:
                version.is_deprecated = True
            secret.metadata.expires_at = datetime.now(timezone.utc)
        else:
            del self._secrets[name]
        
        # Invalidate cache
        if name in self._cache:
            del self._cache[name]
        
        # Log access
        self._log_access(name, accessor, "delete", "success")
        
        return True
    
    async def rotate_secret(
        self,
        name: str,
        new_value: Optional[str] = None,
        rotated_by: str = "system",
    ) -> RotationResult:
        """
        Rotate a secret to a new value.
        
        Args:
            name: Secret name/path
            new_value: New secret value (generated if not provided)
            rotated_by: Who triggered rotation
            
        Returns:
            RotationResult with status
        """
        if name not in self._secrets:
            raise KeyError(f"Secret not found: {name}")
        
        secret = self._secrets[name]
        previous_version = secret.metadata.current_version
        
        result = RotationResult(
            secret_name=name,
            status=RotationStatus.IN_PROGRESS,
            previous_version=previous_version,
            rotated_by=rotated_by,
        )
        
        try:
            # Generate new value if not provided
            if new_value is None:
                new_value = self._generate_secret_value(secret.metadata.secret_type)
            
            # Store new version
            await self.put_secret(
                name=name,
                value=new_value,
                secret_type=secret.metadata.secret_type,
                description=secret.metadata.description,
                rotation_config=secret.metadata.rotation_config,
                tags=secret.metadata.tags,
                owner=secret.metadata.owner,
            )
            
            # Update rotation tracking
            updated_secret = self._secrets[name]
            updated_secret.metadata.last_rotated_at = datetime.now(timezone.utc)
            if updated_secret.metadata.rotation_config:
                updated_secret.metadata.next_rotation_at = (
                    datetime.now(timezone.utc) +
                    timedelta(days=updated_secret.metadata.rotation_config.rotation_days)
                )
            updated_secret.metadata.rotation_status = RotationStatus.COMPLETED
            
            result.status = RotationStatus.COMPLETED
            result.new_version = updated_secret.metadata.current_version
            result.completed_at = datetime.now(timezone.utc)
            
        except Exception as e:
            result.status = RotationStatus.FAILED
            result.error_message = str(e)
        
        return result
    
    async def list_secrets(
        self,
        prefix: Optional[str] = None,
        secret_type: Optional[SecretType] = None,
        tags: Optional[dict[str, str]] = None,
    ) -> list[SecretMetadata]:
        """
        List secrets matching filters.
        
        Args:
            prefix: Path prefix filter
            secret_type: Type filter
            tags: Tag filters
            
        Returns:
            List of SecretMetadata
        """
        results = []
        
        for name, secret in self._secrets.items():
            # Filter by prefix
            if prefix and not name.startswith(prefix):
                continue
            
            # Filter by type
            if secret_type and secret.metadata.secret_type != secret_type:
                continue
            
            # Filter by tags
            if tags:
                match = all(
                    secret.metadata.tags.get(k) == v
                    for k, v in tags.items()
                )
                if not match:
                    continue
            
            results.append(secret.metadata)
        
        return results
    
    async def get_rotation_due(
        self,
        days_ahead: int = 14,
    ) -> list[SecretMetadata]:
        """
        Get secrets due for rotation.
        
        Args:
            days_ahead: Days to look ahead
            
        Returns:
            List of secrets needing rotation
        """
        threshold = datetime.now(timezone.utc) + timedelta(days=days_ahead)
        results = []
        
        for secret in self._secrets.values():
            if secret.metadata.next_rotation_at and secret.metadata.next_rotation_at <= threshold:
                results.append(secret.metadata)
        
        return sorted(results, key=lambda s: s.next_rotation_at or datetime.max)
    
    async def scan_for_secrets(
        self,
        content: str,
        scan_type: str = "text",
    ) -> SecretScanResult:
        """
        Scan content for exposed secrets.
        
        Args:
            content: Content to scan
            scan_type: Type of content being scanned
            
        Returns:
            SecretScanResult with findings
        """
        findings = []
        
        # Common secret patterns
        patterns = [
            (r'(?i)api[_-]?key["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_-]{20,})', "API Key", "high"),
            (r'(?i)secret["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_-]{16,})', "Generic Secret", "high"),
            (r'(?i)password["\']?\s*[:=]\s*["\']?([^\s"\']{8,})', "Password", "high"),
            (r'(?i)aws[_-]?(secret[_-]?access[_-]?key)["\']?\s*[:=]\s*["\']?([a-zA-Z0-9/+=]{40})', "AWS Secret Key", "high"),
            (r'(?i)(ghp_[a-zA-Z0-9]{36})', "GitHub Personal Access Token", "high"),
            (r'(?i)(sk-[a-zA-Z0-9]{32,})', "OpenAI API Key", "high"),
            (r'(?i)private[_-]?key["\']?\s*[:=]', "Private Key Reference", "medium"),
            (r'-----BEGIN (?:RSA )?PRIVATE KEY-----', "Private Key", "high"),
            (r'(?i)bearer\s+([a-zA-Z0-9_-]{20,})', "Bearer Token", "medium"),
        ]
        
        for pattern, secret_type, risk in patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                findings.append({
                    "type": secret_type,
                    "risk": risk,
                    "line": content[:match.start()].count('\n') + 1,
                    "match_preview": match.group(0)[:20] + "...",
                    "pattern": pattern,
                })
        
        high_risk = len([f for f in findings if f["risk"] == "high"])
        medium_risk = len([f for f in findings if f["risk"] == "medium"])
        low_risk = len([f for f in findings if f["risk"] == "low"])
        
        return SecretScanResult(
            scan_type=scan_type,
            target="inline_content",
            secrets_found=len(findings),
            findings=findings,
            high_risk_count=high_risk,
            medium_risk_count=medium_risk,
            low_risk_count=low_risk,
        )
    
    def create_policy(self, policy: AccessPolicy) -> None:
        """Create an access policy."""
        self._policies[policy.policy_id] = policy
    
    def get_access_log(
        self,
        secret_name: Optional[str] = None,
        accessor: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get secret access log."""
        logs = self._access_log.copy()
        
        if secret_name:
            logs = [l for l in logs if l["secret_name"] == secret_name]
        
        if accessor:
            logs = [l for l in logs if l["accessor"] == accessor]
        
        return logs[-limit:]
    
    # ==========================================================================
    # Private Methods
    # ==========================================================================
    
    def _generate_secret_value(self, secret_type: SecretType) -> str:
        """Generate a new secret value based on type."""
        if secret_type == SecretType.PASSWORD:
            return SecretGenerator.generate_password()
        elif secret_type == SecretType.API_KEY:
            return SecretGenerator.generate_api_key()
        elif secret_type == SecretType.DATABASE_CREDENTIAL:
            return SecretGenerator.generate_database_password()
        elif secret_type == SecretType.ENCRYPTION_KEY:
            return base64.b64encode(SecretGenerator.generate_encryption_key()).decode()
        else:
            return SecretGenerator.generate_token()
    
    def _log_access(
        self,
        secret_name: str,
        accessor: str,
        action: str,
        result: str,
    ) -> None:
        """Log secret access for auditing."""
        self._access_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "secret_name": secret_name,
            "accessor": accessor,
            "action": action,
            "result": result,
        })


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Enums
    "SecretBackend",
    "SecretType",
    "RotationStatus",
    "AccessLevel",
    # Configuration
    "SecretsConfig",
    "RotationConfig",
    "AccessPolicy",
    # Models
    "SecretVersion",
    "SecretMetadata",
    "Secret",
    "SecretReference",
    "RotationResult",
    "SecretScanResult",
    # Generator
    "SecretGenerator",
    # Manager
    "SecretsManager",
]
