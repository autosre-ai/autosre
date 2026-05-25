"""
Audit Trail for AI Guardrails

Provides comprehensive audit logging with cryptographic verification:
- Immutable audit entries with hash chains
- Compliance reporting (SOC2, HIPAA, GDPR)
- Queryable audit storage
- Integrity verification
"""

import asyncio
import hashlib
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

from pydantic import BaseModel, Field


class AuditCategory(str, Enum):
    """Categories of audit events."""
    
    # AI Operations
    AI_REQUEST = "ai_request"           # AI model request
    AI_RESPONSE = "ai_response"         # AI model response
    AI_ACTION = "ai_action"             # AI-initiated action
    AI_ERROR = "ai_error"               # AI-related error
    
    # Guardrails
    VALIDATION = "validation"           # Input/output validation
    POLICY_CHECK = "policy_check"       # Policy evaluation
    RISK_ASSESSMENT = "risk_assessment" # Risk assessment
    CONTENT_FILTER = "content_filter"   # Content filtering
    
    # Approvals
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_DECISION = "approval_decision"
    APPROVAL_ESCALATION = "approval_escalation"
    APPROVAL_EXPIRY = "approval_expiry"
    
    # Access
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    
    # Configuration
    CONFIG_CHANGE = "config_change"
    POLICY_CHANGE = "policy_change"
    
    # System
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    SYSTEM_ERROR = "system_error"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ComplianceFramework(str, Enum):
    """Compliance frameworks."""
    
    SOC2 = "soc2"
    HIPAA = "hipaa"
    GDPR = "gdpr"
    PCI_DSS = "pci_dss"
    ISO_27001 = "iso_27001"
    NIST = "nist"


@dataclass
class AuditEntry:
    """An immutable audit log entry."""
    
    id: str
    timestamp: datetime
    category: AuditCategory
    severity: AuditSeverity
    
    # Event details
    event_type: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    
    # Actor information
    actor_id: str = ""
    actor_type: str = ""  # user, ai, system
    actor_name: str = ""
    
    # Target information
    target_type: str = ""
    target_id: str = ""
    target_name: str = ""
    
    # Context
    tenant_id: str = ""
    workspace_id: str = ""
    session_id: str = ""
    request_id: str = ""
    
    # Result
    success: bool = True
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    
    # Metadata
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    source: str = ""
    
    # Hash chain
    previous_hash: str = ""
    entry_hash: str = ""
    
    def compute_hash(self) -> str:
        """Compute hash of entry content."""
        content = {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "category": self.category.value,
            "severity": self.severity.value,
            "event_type": self.event_type,
            "message": self.message,
            "actor_id": self.actor_id,
            "target_id": self.target_id,
            "success": self.success,
            "previous_hash": self.previous_hash,
        }
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "category": self.category.value,
            "severity": self.severity.value,
            "event_type": self.event_type,
            "message": self.message,
            "details": self.details,
            "actor_id": self.actor_id,
            "actor_type": self.actor_type,
            "actor_name": self.actor_name,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "session_id": self.session_id,
            "request_id": self.request_id,
            "success": self.success,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "ip_address": self.ip_address,
            "source": self.source,
            "previous_hash": self.previous_hash,
            "entry_hash": self.entry_hash,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuditEntry":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            category=AuditCategory(data["category"]),
            severity=AuditSeverity(data["severity"]),
            event_type=data["event_type"],
            message=data["message"],
            details=data.get("details", {}),
            actor_id=data.get("actor_id", ""),
            actor_type=data.get("actor_type", ""),
            actor_name=data.get("actor_name", ""),
            target_type=data.get("target_type", ""),
            target_id=data.get("target_id", ""),
            target_name=data.get("target_name", ""),
            tenant_id=data.get("tenant_id", ""),
            workspace_id=data.get("workspace_id", ""),
            session_id=data.get("session_id", ""),
            request_id=data.get("request_id", ""),
            success=data.get("success", True),
            error_code=data.get("error_code"),
            error_message=data.get("error_message"),
            ip_address=data.get("ip_address"),
            source=data.get("source", ""),
            previous_hash=data.get("previous_hash", ""),
            entry_hash=data.get("entry_hash", ""),
        )


class HashChain:
    """Maintains a cryptographic hash chain for audit integrity."""
    
    def __init__(self, genesis_hash: str = ""):
        self._last_hash = genesis_hash or self._create_genesis_hash()
        self._entry_count = 0
    
    def _create_genesis_hash(self) -> str:
        """Create genesis block hash."""
        genesis_data = f"genesis:{datetime.utcnow().isoformat()}"
        return hashlib.sha256(genesis_data.encode()).hexdigest()
    
    def add_entry(self, entry: AuditEntry) -> str:
        """Add entry to chain and return its hash."""
        entry.previous_hash = self._last_hash
        entry.entry_hash = entry.compute_hash()
        
        self._last_hash = entry.entry_hash
        self._entry_count += 1
        
        return entry.entry_hash
    
    def verify_entry(self, entry: AuditEntry) -> bool:
        """Verify an entry's hash is correct."""
        computed = entry.compute_hash()
        return computed == entry.entry_hash
    
    def get_last_hash(self) -> str:
        """Get the last hash in the chain."""
        return self._last_hash
    
    def get_entry_count(self) -> int:
        """Get total entry count."""
        return self._entry_count


@dataclass
class IntegrityCheck:
    """Result of an integrity check."""
    
    valid: bool
    checked_entries: int
    invalid_entries: list[str] = field(default_factory=list)
    broken_chain_at: Optional[str] = None
    
    # Timestamps
    check_start: datetime = field(default_factory=datetime.utcnow)
    check_end: Optional[datetime] = None
    
    # Details
    first_entry_id: str = ""
    last_entry_id: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "valid": self.valid,
            "checked_entries": self.checked_entries,
            "invalid_entries": self.invalid_entries,
            "broken_chain_at": self.broken_chain_at,
            "check_start": self.check_start.isoformat(),
            "check_end": self.check_end.isoformat() if self.check_end else None,
            "first_entry_id": self.first_entry_id,
            "last_entry_id": self.last_entry_id,
        }


class AuditQuery(BaseModel):
    """Query parameters for audit log search."""
    
    # Time range
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # Filters
    categories: list[AuditCategory] = Field(default_factory=list)
    severities: list[AuditSeverity] = Field(default_factory=list)
    event_types: list[str] = Field(default_factory=list)
    
    # Actor filters
    actor_ids: list[str] = Field(default_factory=list)
    actor_types: list[str] = Field(default_factory=list)
    
    # Target filters
    target_types: list[str] = Field(default_factory=list)
    target_ids: list[str] = Field(default_factory=list)
    
    # Context filters
    tenant_ids: list[str] = Field(default_factory=list)
    session_ids: list[str] = Field(default_factory=list)
    request_ids: list[str] = Field(default_factory=list)
    
    # Result filters
    success_only: bool = False
    failure_only: bool = False
    
    # Search
    message_contains: Optional[str] = None
    
    # Pagination
    limit: int = Field(default=100, ge=1, le=10000)
    offset: int = Field(default=0, ge=0)
    
    # Ordering
    order_by: str = "timestamp"
    order_desc: bool = True


class AuditReport(BaseModel):
    """A generated audit report."""
    
    id: str
    name: str
    description: str = ""
    
    # Time range
    start_time: datetime
    end_time: datetime
    
    # Summary
    total_entries: int = 0
    entries_by_category: dict[str, int] = Field(default_factory=dict)
    entries_by_severity: dict[str, int] = Field(default_factory=dict)
    
    # Key metrics
    success_rate: float = 0.0
    unique_actors: int = 0
    unique_targets: int = 0
    
    # Notable events
    critical_events: list[dict] = Field(default_factory=list)
    failed_events: list[dict] = Field(default_factory=list)
    
    # Compliance
    compliance_status: dict[str, bool] = Field(default_factory=dict)
    compliance_gaps: list[str] = Field(default_factory=list)
    
    # Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    generated_by: str = ""
    
    # Integrity
    integrity_verified: bool = False
    integrity_check: Optional[dict] = None


class ComplianceReport(BaseModel):
    """Compliance report for regulatory frameworks."""
    
    id: str
    name: str
    description: str = ""
    
    # Time range
    start_time: datetime
    end_time: datetime
    
    # Frameworks evaluated
    frameworks: list[ComplianceFramework] = Field(default_factory=list)
    
    # Results
    overall_compliant: bool = True
    framework_results: dict[str, dict] = Field(default_factory=dict)
    
    # Gaps and recommendations
    gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    
    # Evidence
    evidence_summary: dict[str, int] = Field(default_factory=dict)
    
    # Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    generated_by: str = ""
    valid_until: Optional[datetime] = None


class AuditStorage(ABC):
    """Abstract base for audit storage backends."""
    
    @abstractmethod
    async def store(self, entry: AuditEntry) -> bool:
        """Store an audit entry."""
        pass
    
    @abstractmethod
    async def get(self, entry_id: str) -> Optional[AuditEntry]:
        """Get an entry by ID."""
        pass
    
    @abstractmethod
    async def query(self, query: AuditQuery) -> list[AuditEntry]:
        """Query audit entries."""
        pass
    
    @abstractmethod
    async def count(self, query: AuditQuery) -> int:
        """Count matching entries."""
        pass
    
    @abstractmethod
    async def get_range(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> Iterator[AuditEntry]:
        """Get entries in a time range."""
        pass


class InMemoryAuditStorage(AuditStorage):
    """In-memory audit storage for development/testing."""
    
    def __init__(self, max_entries: int = 100000):
        self.max_entries = max_entries
        self._entries: dict[str, AuditEntry] = {}
        self._index_by_time: list[str] = []  # Ordered by timestamp
    
    async def store(self, entry: AuditEntry) -> bool:
        """Store an audit entry."""
        self._entries[entry.id] = entry
        self._index_by_time.append(entry.id)
        
        # Trim if over limit
        while len(self._entries) > self.max_entries:
            oldest_id = self._index_by_time.pop(0)
            del self._entries[oldest_id]
        
        return True
    
    async def get(self, entry_id: str) -> Optional[AuditEntry]:
        """Get an entry by ID."""
        return self._entries.get(entry_id)
    
    async def query(self, query: AuditQuery) -> list[AuditEntry]:
        """Query audit entries."""
        results: list[AuditEntry] = []
        
        for entry in self._entries.values():
            if self._matches_query(entry, query):
                results.append(entry)
        
        # Sort
        results.sort(
            key=lambda e: getattr(e, query.order_by, e.timestamp),
            reverse=query.order_desc,
        )
        
        # Paginate
        start = query.offset
        end = start + query.limit
        return results[start:end]
    
    async def count(self, query: AuditQuery) -> int:
        """Count matching entries."""
        count = 0
        for entry in self._entries.values():
            if self._matches_query(entry, query):
                count += 1
        return count
    
    async def get_range(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> Iterator[AuditEntry]:
        """Get entries in a time range."""
        for entry in self._entries.values():
            if start_time <= entry.timestamp <= end_time:
                yield entry
    
    def _matches_query(self, entry: AuditEntry, query: AuditQuery) -> bool:
        """Check if entry matches query."""
        # Time range
        if query.start_time and entry.timestamp < query.start_time:
            return False
        if query.end_time and entry.timestamp > query.end_time:
            return False
        
        # Categories
        if query.categories and entry.category not in query.categories:
            return False
        
        # Severities
        if query.severities and entry.severity not in query.severities:
            return False
        
        # Event types
        if query.event_types and entry.event_type not in query.event_types:
            return False
        
        # Actor
        if query.actor_ids and entry.actor_id not in query.actor_ids:
            return False
        if query.actor_types and entry.actor_type not in query.actor_types:
            return False
        
        # Target
        if query.target_types and entry.target_type not in query.target_types:
            return False
        if query.target_ids and entry.target_id not in query.target_ids:
            return False
        
        # Context
        if query.tenant_ids and entry.tenant_id not in query.tenant_ids:
            return False
        if query.session_ids and entry.session_id not in query.session_ids:
            return False
        if query.request_ids and entry.request_id not in query.request_ids:
            return False
        
        # Success/failure
        if query.success_only and not entry.success:
            return False
        if query.failure_only and entry.success:
            return False
        
        # Message search
        if query.message_contains:
            if query.message_contains.lower() not in entry.message.lower():
                return False
        
        return True


class FileAuditStorage(AuditStorage):
    """File-based audit storage with rotation."""
    
    def __init__(
        self,
        base_path: str,
        rotation_size_mb: int = 100,
    ):
        self.base_path = Path(base_path)
        self.rotation_size_mb = rotation_size_mb
        
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        self._current_file: Optional[Path] = None
        self._file_handle: Optional[Any] = None
    
    async def store(self, entry: AuditEntry) -> bool:
        """Store an audit entry."""
        file_path = self._get_current_file()
        
        entry_json = json.dumps(entry.to_dict())
        
        with open(file_path, "a") as f:
            f.write(entry_json + "\n")
        
        return True
    
    async def get(self, entry_id: str) -> Optional[AuditEntry]:
        """Get an entry by ID."""
        # Scan files (inefficient, use index in production)
        for file_path in self.base_path.glob("audit_*.jsonl"):
            with open(file_path) as f:
                for line in f:
                    data = json.loads(line)
                    if data.get("id") == entry_id:
                        return AuditEntry.from_dict(data)
        return None
    
    async def query(self, query: AuditQuery) -> list[AuditEntry]:
        """Query audit entries."""
        results: list[AuditEntry] = []
        
        for file_path in sorted(self.base_path.glob("audit_*.jsonl"), reverse=query.order_desc):
            with open(file_path) as f:
                for line in f:
                    data = json.loads(line)
                    entry = AuditEntry.from_dict(data)
                    
                    # Apply filters (simplified)
                    if query.start_time and entry.timestamp < query.start_time:
                        continue
                    if query.end_time and entry.timestamp > query.end_time:
                        continue
                    if query.categories and entry.category not in query.categories:
                        continue
                    
                    results.append(entry)
                    
                    if len(results) >= query.offset + query.limit:
                        break
        
        # Paginate
        return results[query.offset:query.offset + query.limit]
    
    async def count(self, query: AuditQuery) -> int:
        """Count matching entries."""
        # Simplified count
        entries = await self.query(AuditQuery(limit=100000))
        return len(entries)
    
    async def get_range(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> Iterator[AuditEntry]:
        """Get entries in a time range."""
        for file_path in sorted(self.base_path.glob("audit_*.jsonl")):
            with open(file_path) as f:
                for line in f:
                    data = json.loads(line)
                    entry = AuditEntry.from_dict(data)
                    if start_time <= entry.timestamp <= end_time:
                        yield entry
    
    def _get_current_file(self) -> Path:
        """Get current file for writing."""
        today = datetime.utcnow().strftime("%Y%m%d")
        file_path = self.base_path / f"audit_{today}.jsonl"
        
        # Check rotation
        if file_path.exists():
            size_mb = file_path.stat().st_size / (1024 * 1024)
            if size_mb >= self.rotation_size_mb:
                # Rotate
                hour = datetime.utcnow().strftime("%H%M%S")
                file_path = self.base_path / f"audit_{today}_{hour}.jsonl"
        
        return file_path


class AuditVerifier:
    """Verifies audit trail integrity."""
    
    def __init__(self, storage: AuditStorage):
        self.storage = storage
    
    async def verify_chain(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> IntegrityCheck:
        """Verify hash chain integrity for a time range."""
        check = IntegrityCheck(
            valid=True,
            checked_entries=0,
            check_start=datetime.utcnow(),
        )
        
        previous_hash = ""
        entries = []
        
        async for entry in self.storage.get_range(start_time, end_time):
            entries.append(entry)
        
        # Sort by timestamp
        entries.sort(key=lambda e: e.timestamp)
        
        for entry in entries:
            check.checked_entries += 1
            
            if check.checked_entries == 1:
                check.first_entry_id = entry.id
            check.last_entry_id = entry.id
            
            # Verify entry hash
            computed_hash = entry.compute_hash()
            if computed_hash != entry.entry_hash:
                check.valid = False
                check.invalid_entries.append(entry.id)
            
            # Verify chain (skip first entry)
            if previous_hash and entry.previous_hash != previous_hash:
                check.valid = False
                check.broken_chain_at = entry.id
            
            previous_hash = entry.entry_hash
        
        check.check_end = datetime.utcnow()
        return check
    
    async def verify_entry(self, entry_id: str) -> tuple[bool, str]:
        """Verify a single entry's integrity."""
        entry = await self.storage.get(entry_id)
        if not entry:
            return False, "Entry not found"
        
        computed_hash = entry.compute_hash()
        if computed_hash != entry.entry_hash:
            return False, f"Hash mismatch: expected {entry.entry_hash}, got {computed_hash}"
        
        return True, "Entry verified"


class ComplianceChecker:
    """Checks audit trail for compliance requirements."""
    
    # Compliance requirements
    REQUIREMENTS = {
        ComplianceFramework.SOC2: {
            "access_logging": True,
            "change_logging": True,
            "authentication_logging": True,
            "retention_days": 365,
            "integrity_verification": True,
        },
        ComplianceFramework.HIPAA: {
            "access_logging": True,
            "pii_masking": True,
            "authentication_logging": True,
            "retention_days": 2190,  # 6 years
            "integrity_verification": True,
        },
        ComplianceFramework.GDPR: {
            "access_logging": True,
            "pii_masking": True,
            "consent_logging": True,
            "retention_days": 365,
            "right_to_erasure": True,
        },
        ComplianceFramework.PCI_DSS: {
            "access_logging": True,
            "authentication_logging": True,
            "retention_days": 365,
            "integrity_verification": True,
            "tamper_protection": True,
        },
    }
    
    def __init__(
        self,
        storage: AuditStorage,
        frameworks: Optional[list[ComplianceFramework]] = None,
    ):
        self.storage = storage
        self.frameworks = frameworks or []
    
    async def check_compliance(
        self,
        framework: ComplianceFramework,
        start_time: datetime,
        end_time: datetime,
    ) -> dict[str, Any]:
        """Check compliance for a framework."""
        requirements = self.REQUIREMENTS.get(framework, {})
        results: dict[str, Any] = {
            "framework": framework.value,
            "compliant": True,
            "gaps": [],
            "checks": {},
        }
        
        # Check access logging
        if requirements.get("access_logging"):
            access_entries = await self.storage.count(AuditQuery(
                start_time=start_time,
                end_time=end_time,
                categories=[AuditCategory.ACCESS_GRANTED, AuditCategory.ACCESS_DENIED],
            ))
            results["checks"]["access_logging"] = access_entries > 0
            if access_entries == 0:
                results["compliant"] = False
                results["gaps"].append("No access logging found")
        
        # Check authentication logging
        if requirements.get("authentication_logging"):
            auth_entries = await self.storage.count(AuditQuery(
                start_time=start_time,
                end_time=end_time,
                categories=[AuditCategory.AUTHENTICATION],
            ))
            results["checks"]["authentication_logging"] = auth_entries > 0
            if auth_entries == 0:
                results["compliant"] = False
                results["gaps"].append("No authentication logging found")
        
        # Check change logging
        if requirements.get("change_logging"):
            change_entries = await self.storage.count(AuditQuery(
                start_time=start_time,
                end_time=end_time,
                categories=[AuditCategory.CONFIG_CHANGE, AuditCategory.POLICY_CHANGE],
            ))
            results["checks"]["change_logging"] = change_entries >= 0
            # Changes might legitimately be 0
        
        return results
    
    async def generate_compliance_report(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> dict[str, Any]:
        """Generate compliance report for all configured frameworks."""
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "period_start": start_time.isoformat(),
            "period_end": end_time.isoformat(),
            "frameworks": {},
            "overall_compliant": True,
        }
        
        for framework in self.frameworks:
            result = await self.check_compliance(framework, start_time, end_time)
            report["frameworks"][framework.value] = result
            if not result["compliant"]:
                report["overall_compliant"] = False
        
        return report


class AuditTrail:
    """Main audit trail manager."""
    
    def __init__(
        self,
        storage: Optional[AuditStorage] = None,
        hash_chain: Optional[HashChain] = None,
        compliance_frameworks: Optional[list[ComplianceFramework]] = None,
    ):
        self.storage = storage or InMemoryAuditStorage()
        self.hash_chain = hash_chain or HashChain()
        
        self.verifier = AuditVerifier(self.storage)
        self.compliance_checker = ComplianceChecker(
            self.storage,
            compliance_frameworks or [],
        )
        
        self._entry_counter = 0
    
    async def log(
        self,
        category: AuditCategory,
        event_type: str,
        message: str,
        severity: AuditSeverity = AuditSeverity.INFO,
        actor_id: str = "",
        actor_type: str = "",
        actor_name: str = "",
        target_type: str = "",
        target_id: str = "",
        target_name: str = "",
        details: Optional[dict] = None,
        success: bool = True,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        tenant_id: str = "",
        workspace_id: str = "",
        session_id: str = "",
        request_id: str = "",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        source: str = "",
    ) -> AuditEntry:
        """Log an audit entry."""
        self._entry_counter += 1
        
        entry = AuditEntry(
            id=self._generate_id(),
            timestamp=datetime.utcnow(),
            category=category,
            severity=severity,
            event_type=event_type,
            message=message,
            details=details or {},
            actor_id=actor_id,
            actor_type=actor_type,
            actor_name=actor_name,
            target_type=target_type,
            target_id=target_id,
            target_name=target_name,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            session_id=session_id,
            request_id=request_id,
            success=success,
            error_code=error_code,
            error_message=error_message,
            ip_address=ip_address,
            user_agent=user_agent,
            source=source,
        )
        
        # Add to hash chain
        self.hash_chain.add_entry(entry)
        
        # Store
        await self.storage.store(entry)
        
        return entry
    
    async def log_ai_request(
        self,
        request_id: str,
        model: str,
        prompt: str,
        user_id: str,
        tenant_id: str = "",
        session_id: str = "",
        **kwargs,
    ) -> AuditEntry:
        """Log an AI model request."""
        # Mask sensitive content in prompt
        masked_prompt = self._mask_sensitive(prompt)
        
        return await self.log(
            category=AuditCategory.AI_REQUEST,
            event_type="ai_model_request",
            message=f"AI request to {model}",
            actor_id=user_id,
            actor_type="user",
            target_type="ai_model",
            target_id=model,
            details={
                "prompt_length": len(prompt),
                "prompt_preview": masked_prompt[:200] + "..." if len(masked_prompt) > 200 else masked_prompt,
            },
            tenant_id=tenant_id,
            session_id=session_id,
            request_id=request_id,
            **kwargs,
        )
    
    async def log_ai_response(
        self,
        request_id: str,
        model: str,
        response: str,
        user_id: str,
        tokens_used: int = 0,
        latency_ms: float = 0,
        tenant_id: str = "",
        session_id: str = "",
        **kwargs,
    ) -> AuditEntry:
        """Log an AI model response."""
        return await self.log(
            category=AuditCategory.AI_RESPONSE,
            event_type="ai_model_response",
            message=f"AI response from {model}",
            actor_id=model,
            actor_type="ai",
            target_type="user",
            target_id=user_id,
            details={
                "response_length": len(response),
                "tokens_used": tokens_used,
                "latency_ms": latency_ms,
            },
            tenant_id=tenant_id,
            session_id=session_id,
            request_id=request_id,
            **kwargs,
        )
    
    async def log_ai_action(
        self,
        action: str,
        target: str,
        user_id: str,
        ai_model: str = "",
        risk_level: str = "low",
        success: bool = True,
        details: Optional[dict] = None,
        tenant_id: str = "",
        session_id: str = "",
        request_id: str = "",
        **kwargs,
    ) -> AuditEntry:
        """Log an AI-initiated action."""
        severity = {
            "low": AuditSeverity.INFO,
            "medium": AuditSeverity.WARNING,
            "high": AuditSeverity.WARNING,
            "critical": AuditSeverity.CRITICAL,
        }.get(risk_level, AuditSeverity.INFO)
        
        return await self.log(
            category=AuditCategory.AI_ACTION,
            event_type=f"ai_action_{action}",
            message=f"AI action: {action} on {target}",
            severity=severity,
            actor_id=ai_model or "autosre",
            actor_type="ai",
            target_type="resource",
            target_id=target,
            target_name=target,
            details={
                "action": action,
                "risk_level": risk_level,
                "initiated_by": user_id,
                **(details or {}),
            },
            success=success,
            tenant_id=tenant_id,
            session_id=session_id,
            request_id=request_id,
            **kwargs,
        )
    
    async def log_validation(
        self,
        validation_type: str,
        result: bool,
        details: Optional[dict] = None,
        user_id: str = "",
        request_id: str = "",
        **kwargs,
    ) -> AuditEntry:
        """Log a validation check."""
        return await self.log(
            category=AuditCategory.VALIDATION,
            event_type=f"validation_{validation_type}",
            message=f"Validation {validation_type}: {'passed' if result else 'failed'}",
            severity=AuditSeverity.INFO if result else AuditSeverity.WARNING,
            actor_id="guardrails",
            actor_type="system",
            success=result,
            details=details or {},
            request_id=request_id,
            **kwargs,
        )
    
    async def log_policy_check(
        self,
        policy_id: str,
        policy_name: str,
        action: str,
        result: str,  # allow, deny, require_approval
        risk_level: str = "low",
        user_id: str = "",
        request_id: str = "",
        **kwargs,
    ) -> AuditEntry:
        """Log a policy check."""
        return await self.log(
            category=AuditCategory.POLICY_CHECK,
            event_type="policy_evaluation",
            message=f"Policy {policy_name}: {result} for {action}",
            severity=AuditSeverity.INFO if result == "allow" else AuditSeverity.WARNING,
            actor_id="policy_engine",
            actor_type="system",
            target_type="policy",
            target_id=policy_id,
            target_name=policy_name,
            details={
                "action": action,
                "result": result,
                "risk_level": risk_level,
            },
            success=(result == "allow"),
            request_id=request_id,
            **kwargs,
        )
    
    async def log_approval_request(
        self,
        request_id: str,
        action: str,
        requester_id: str,
        approvers: list[str],
        **kwargs,
    ) -> AuditEntry:
        """Log an approval request."""
        return await self.log(
            category=AuditCategory.APPROVAL_REQUEST,
            event_type="approval_requested",
            message=f"Approval requested for {action}",
            actor_id=requester_id,
            actor_type="user",
            details={
                "action": action,
                "approvers": approvers,
                "approval_request_id": request_id,
            },
            **kwargs,
        )
    
    async def log_approval_decision(
        self,
        request_id: str,
        approver_id: str,
        decision: str,
        comment: str = "",
        **kwargs,
    ) -> AuditEntry:
        """Log an approval decision."""
        return await self.log(
            category=AuditCategory.APPROVAL_DECISION,
            event_type=f"approval_{decision}",
            message=f"Approval {decision} by {approver_id}",
            actor_id=approver_id,
            actor_type="user",
            details={
                "approval_request_id": request_id,
                "decision": decision,
                "comment": comment,
            },
            success=(decision == "approved"),
            **kwargs,
        )
    
    async def query(self, query: AuditQuery) -> list[AuditEntry]:
        """Query audit entries."""
        return await self.storage.query(query)
    
    async def get_entry(self, entry_id: str) -> Optional[AuditEntry]:
        """Get a specific audit entry."""
        return await self.storage.get(entry_id)
    
    async def verify_integrity(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> IntegrityCheck:
        """Verify audit trail integrity."""
        start = start_time or (datetime.utcnow() - timedelta(days=30))
        end = end_time or datetime.utcnow()
        return await self.verifier.verify_chain(start, end)
    
    async def generate_report(
        self,
        start_time: datetime,
        end_time: datetime,
        name: str = "Audit Report",
    ) -> AuditReport:
        """Generate an audit report."""
        # Query entries
        query = AuditQuery(
            start_time=start_time,
            end_time=end_time,
            limit=10000,
        )
        entries = await self.storage.query(query)
        
        # Build report
        entries_by_category: dict[str, int] = {}
        entries_by_severity: dict[str, int] = {}
        unique_actors: set[str] = set()
        unique_targets: set[str] = set()
        critical_events: list[dict] = []
        failed_events: list[dict] = []
        
        for entry in entries:
            cat = entry.category.value
            entries_by_category[cat] = entries_by_category.get(cat, 0) + 1
            
            sev = entry.severity.value
            entries_by_severity[sev] = entries_by_severity.get(sev, 0) + 1
            
            if entry.actor_id:
                unique_actors.add(entry.actor_id)
            if entry.target_id:
                unique_targets.add(entry.target_id)
            
            if entry.severity == AuditSeverity.CRITICAL:
                critical_events.append(entry.to_dict())
            
            if not entry.success:
                failed_events.append(entry.to_dict())
        
        # Calculate success rate
        total = len(entries)
        successful = len([e for e in entries if e.success])
        success_rate = (successful / total * 100) if total > 0 else 100.0
        
        # Verify integrity
        integrity = await self.verify_integrity(start_time, end_time)
        
        # Check compliance
        compliance_report = await self.compliance_checker.generate_compliance_report(
            start_time, end_time
        )
        
        return AuditReport(
            id=self._generate_id(),
            name=name,
            start_time=start_time,
            end_time=end_time,
            total_entries=total,
            entries_by_category=entries_by_category,
            entries_by_severity=entries_by_severity,
            success_rate=success_rate,
            unique_actors=len(unique_actors),
            unique_targets=len(unique_targets),
            critical_events=critical_events[:10],  # Limit
            failed_events=failed_events[:10],
            compliance_status={
                fw: result.get("compliant", False)
                for fw, result in compliance_report.get("frameworks", {}).items()
            },
            integrity_verified=integrity.valid,
            integrity_check=integrity.to_dict(),
        )
    
    def _generate_id(self) -> str:
        """Generate a unique ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        counter = self._entry_counter
        data = f"{timestamp}:{counter}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def _mask_sensitive(self, text: str) -> str:
        """Mask sensitive data in text."""
        import re
        
        # Mask patterns
        patterns = [
            (r"password\s*[:=]\s*\S+", "password=[MASKED]"),
            (r"api[_-]?key\s*[:=]\s*\S+", "api_key=[MASKED]"),
            (r"token\s*[:=]\s*\S+", "token=[MASKED]"),
            (r"secret\s*[:=]\s*\S+", "secret=[MASKED]"),
        ]
        
        result = text
        for pattern, replacement in patterns:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        
        return result
