"""
Security Audit Logging

Provides comprehensive security audit logging for SRE operations:
- Security event logging with tamper-evident trails
- Access monitoring and anomaly detection
- Compliance reporting (SOC2, PCI-DSS, HIPAA)
- Forensic investigation support
- Real-time security alerting
"""

import asyncio
import hashlib
import hmac
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class SecurityEventType(str, Enum):
    """Types of security events."""
    
    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    MFA_CHALLENGE = "mfa_challenge"
    MFA_SUCCESS = "mfa_success"
    MFA_FAILURE = "mfa_failure"
    PASSWORD_CHANGE = "password_change"
    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"
    
    # Authorization events
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    ROLE_CHANGE = "role_change"
    PERMISSION_CHANGE = "permission_change"
    
    # Resource access events
    RESOURCE_READ = "resource_read"
    RESOURCE_CREATE = "resource_create"
    RESOURCE_UPDATE = "resource_update"
    RESOURCE_DELETE = "resource_delete"
    SECRET_ACCESS = "secret_access"
    CONFIG_CHANGE = "config_change"
    
    # Security incidents
    BRUTE_FORCE_DETECTED = "brute_force_detected"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    ANOMALY_DETECTED = "anomaly_detected"
    POLICY_VIOLATION = "policy_violation"
    DATA_EXFILTRATION = "data_exfiltration"
    INTRUSION_ATTEMPT = "intrusion_attempt"
    
    # System events
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    BACKUP_CREATED = "backup_created"
    BACKUP_RESTORED = "backup_restored"
    CERTIFICATE_EXPIRY = "certificate_expiry"
    
    # Compliance events
    AUDIT_LOG_ACCESS = "audit_log_access"
    COMPLIANCE_CHECK = "compliance_check"
    POLICY_CHANGE = "policy_change"


class EventSeverity(str, Enum):
    """Security event severity levels."""
    
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditLogDestination(str, Enum):
    """Audit log storage destinations."""
    
    LOCAL_FILE = "local_file"
    SYSLOG = "syslog"
    CLOUDWATCH = "cloudwatch"
    STACKDRIVER = "stackdriver"
    ELASTICSEARCH = "elasticsearch"
    SPLUNK = "splunk"
    S3 = "s3"
    GCS = "gcs"


class ComplianceFramework(str, Enum):
    """Compliance frameworks for reporting."""
    
    SOC2 = "soc2"
    PCI_DSS = "pci_dss"
    HIPAA = "hipaa"
    GDPR = "gdpr"
    ISO_27001 = "iso_27001"
    NIST_CSF = "nist_csf"
    FedRAMP = "fedramp"


# =============================================================================
# Configuration
# =============================================================================


class SecurityAuditConfig(BaseModel):
    """Security audit logging configuration."""
    
    enabled: bool = Field(default=True, description="Enable security audit logging")
    
    # Storage settings
    destinations: list[AuditLogDestination] = Field(
        default_factory=lambda: [AuditLogDestination.LOCAL_FILE],
        description="Log destinations"
    )
    log_path: str = Field(default="/var/log/autosre/security-audit.log", description="Local log path")
    retention_days: int = Field(default=365, description="Log retention period in days")
    
    # Integrity settings
    enable_hmac: bool = Field(default=True, description="Enable HMAC signatures for tamper detection")
    hmac_key_path: Optional[str] = Field(default=None, description="Path to HMAC signing key")
    enable_chain_verification: bool = Field(default=True, description="Enable hash chain verification")
    
    # Event settings
    log_read_events: bool = Field(default=False, description="Log read operations (verbose)")
    event_types: list[SecurityEventType] = Field(
        default_factory=lambda: list(SecurityEventType),
        description="Event types to log"
    )
    
    # Alerting
    alert_on_critical: bool = Field(default=True, description="Alert on critical events")
    alert_on_high: bool = Field(default=True, description="Alert on high severity events")
    
    # Compliance
    compliance_frameworks: list[ComplianceFramework] = Field(
        default_factory=list,
        description="Compliance frameworks to support"
    )


class AlertConfig(BaseModel):
    """Security alert configuration."""
    
    enabled: bool = Field(default=True, description="Enable security alerts")
    
    # Thresholds
    login_failure_threshold: int = Field(default=5, description="Failed logins before alert")
    login_failure_window_minutes: int = Field(default=5, description="Time window for login failures")
    suspicious_activity_threshold: int = Field(default=3, description="Suspicious events before alert")
    
    # Channels
    webhook_url: Optional[str] = Field(default=None, description="Alert webhook URL")
    email_recipients: list[str] = Field(default_factory=list, description="Email recipients")
    slack_channel: Optional[str] = Field(default=None, description="Slack channel for alerts")
    pagerduty_key: Optional[str] = Field(default=None, description="PagerDuty service key")


# =============================================================================
# Audit Event Models
# =============================================================================


class Actor(BaseModel):
    """Entity performing an action."""
    
    id: str = Field(description="Actor identifier (user ID, service account, etc.)")
    type: str = Field(description="Actor type (user, service, system)")
    name: Optional[str] = Field(default=None, description="Actor display name")
    email: Optional[str] = Field(default=None, description="Actor email")
    ip_address: Optional[str] = Field(default=None, description="Source IP address")
    user_agent: Optional[str] = Field(default=None, description="User agent string")
    session_id: Optional[str] = Field(default=None, description="Session identifier")
    
    # Context
    tenant_id: Optional[str] = Field(default=None, description="Tenant ID for multi-tenant systems")
    organization_id: Optional[str] = Field(default=None, description="Organization ID")
    roles: list[str] = Field(default_factory=list, description="Actor roles at time of event")


class Resource(BaseModel):
    """Resource being accessed or modified."""
    
    type: str = Field(description="Resource type (deployment, secret, config, etc.)")
    id: str = Field(description="Resource identifier")
    name: Optional[str] = Field(default=None, description="Resource name")
    namespace: Optional[str] = Field(default=None, description="Resource namespace")
    
    # Context
    parent_id: Optional[str] = Field(default=None, description="Parent resource ID")
    labels: dict[str, str] = Field(default_factory=dict, description="Resource labels")


class SecurityEvent(BaseModel):
    """Individual security audit event."""
    
    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique event ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    
    # Event classification
    event_type: SecurityEventType = Field(description="Type of security event")
    severity: EventSeverity = Field(description="Event severity")
    category: str = Field(description="Event category (auth, access, security, system)")
    
    # Who
    actor: Actor = Field(description="Who performed the action")
    
    # What
    action: str = Field(description="Action performed")
    resource: Optional[Resource] = Field(default=None, description="Resource affected")
    
    # Outcome
    success: bool = Field(default=True, description="Whether action succeeded")
    outcome: str = Field(default="success", description="Outcome description")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    
    # Context
    context: dict[str, Any] = Field(default_factory=dict, description="Additional context")
    correlation_id: Optional[str] = Field(default=None, description="Request correlation ID")
    
    # Integrity
    previous_hash: Optional[str] = Field(default=None, description="Hash of previous event")
    event_hash: Optional[str] = Field(default=None, description="Hash of this event")
    hmac_signature: Optional[str] = Field(default=None, description="HMAC signature")
    
    # Compliance mapping
    compliance_controls: list[str] = Field(
        default_factory=list,
        description="Compliance controls this event relates to"
    )
    
    def compute_hash(self, previous_hash: Optional[str] = None) -> str:
        """Compute hash of event for chain verification."""
        data = {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "actor_id": self.actor.id,
            "action": self.action,
            "success": self.success,
            "previous_hash": previous_hash or "",
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


class AuditLogEntry(BaseModel):
    """Serialized audit log entry."""
    
    event: SecurityEvent
    schema_version: str = Field(default="1.0", description="Log schema version")
    logged_at: datetime = Field(default_factory=datetime.utcnow)
    log_source: str = Field(default="autosre", description="Source system")


# =============================================================================
# Query and Reporting
# =============================================================================


class AuditQuery(BaseModel):
    """Query for searching audit logs."""
    
    # Time range
    start_time: Optional[datetime] = Field(default=None, description="Start of time range")
    end_time: Optional[datetime] = Field(default=None, description="End of time range")
    
    # Filters
    event_types: list[SecurityEventType] = Field(default_factory=list, description="Event types to include")
    severities: list[EventSeverity] = Field(default_factory=list, description="Severity levels")
    actor_ids: list[str] = Field(default_factory=list, description="Filter by actor IDs")
    resource_types: list[str] = Field(default_factory=list, description="Filter by resource types")
    
    # Search
    text_search: Optional[str] = Field(default=None, description="Full-text search")
    
    # Pagination
    limit: int = Field(default=100, ge=1, le=10000, description="Maximum results")
    offset: int = Field(default=0, ge=0, description="Result offset")
    
    # Sort
    sort_by: str = Field(default="timestamp", description="Sort field")
    sort_desc: bool = Field(default=True, description="Sort descending")


class AuditQueryResult(BaseModel):
    """Result of audit log query."""
    
    events: list[SecurityEvent] = Field(default_factory=list)
    total_count: int = Field(default=0, description="Total matching events")
    query: AuditQuery = Field(description="Query that produced these results")
    executed_at: datetime = Field(default_factory=datetime.utcnow)


class ComplianceReport(BaseModel):
    """Compliance audit report."""
    
    report_id: str = Field(default_factory=lambda: str(uuid4()))
    framework: ComplianceFramework = Field(description="Compliance framework")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    period_start: datetime = Field(description="Report period start")
    period_end: datetime = Field(description="Report period end")
    
    # Summary
    total_events: int = Field(default=0, description="Total events in period")
    events_by_type: dict[str, int] = Field(default_factory=dict)
    events_by_severity: dict[str, int] = Field(default_factory=dict)
    
    # Compliance status
    controls_checked: int = Field(default=0, description="Number of controls evaluated")
    controls_passed: int = Field(default=0, description="Controls with no violations")
    controls_failed: int = Field(default=0, description="Controls with violations")
    
    # Findings
    findings: list[dict[str, Any]] = Field(default_factory=list, description="Compliance findings")
    
    # Score
    compliance_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Compliance score")
    
    @property
    def is_compliant(self) -> bool:
        """Check if fully compliant."""
        return self.controls_failed == 0


class SecurityAlert(BaseModel):
    """Security alert generated from audit events."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    severity: EventSeverity = Field(description="Alert severity")
    title: str = Field(description="Alert title")
    description: str = Field(description="Alert description")
    
    # Related events
    event_ids: list[str] = Field(default_factory=list, description="Related event IDs")
    event_count: int = Field(default=1, description="Number of related events")
    
    # Context
    actor: Optional[Actor] = Field(default=None, description="Primary actor")
    source_ip: Optional[str] = Field(default=None, description="Source IP if applicable")
    
    # Status
    acknowledged: bool = Field(default=False, description="Alert acknowledged")
    acknowledged_by: Optional[str] = Field(default=None, description="Who acknowledged")
    resolved: bool = Field(default=False, description="Alert resolved")
    
    # Actions
    recommended_actions: list[str] = Field(default_factory=list, description="Recommended actions")


# =============================================================================
# Security Audit Logger Implementation
# =============================================================================


class SecurityAuditLogger:
    """
    Enterprise security audit logging for SRE operations.
    
    Provides tamper-evident audit logging with:
    - Cryptographic hash chains for integrity
    - HMAC signatures for authenticity
    - Real-time anomaly detection
    - Compliance reporting
    
    Example:
        audit_logger = SecurityAuditLogger(config)
        
        # Log a security event
        await audit_logger.log_event(
            event_type=SecurityEventType.LOGIN_SUCCESS,
            actor=Actor(id="user-123", type="user"),
            action="User logged in",
            context={"method": "oauth2"}
        )
        
        # Query audit logs
        results = await audit_logger.query(AuditQuery(
            start_time=datetime.utcnow() - timedelta(days=7),
            event_types=[SecurityEventType.LOGIN_FAILURE],
        ))
        
        # Generate compliance report
        report = await audit_logger.generate_compliance_report(
            framework=ComplianceFramework.SOC2,
            period_start=datetime(2024, 1, 1),
            period_end=datetime(2024, 3, 31),
        )
    """
    
    def __init__(
        self,
        config: Optional[SecurityAuditConfig] = None,
        alert_config: Optional[AlertConfig] = None,
    ):
        """Initialize the security audit logger."""
        self.config = config or SecurityAuditConfig()
        self.alert_config = alert_config or AlertConfig()
        
        # In-memory storage (production would use actual storage backends)
        self._events: list[SecurityEvent] = []
        self._alerts: list[SecurityAlert] = []
        
        # Hash chain
        self._last_hash: Optional[str] = None
        
        # HMAC key
        self._hmac_key: bytes = self._load_hmac_key()
        
        # Event handlers
        self._event_handlers: list[Callable[[SecurityEvent], None]] = []
        
        # Anomaly detection state
        self._login_failures: dict[str, list[datetime]] = {}  # IP -> timestamps
    
    async def log_event(
        self,
        event_type: SecurityEventType,
        actor: Actor,
        action: str,
        severity: Optional[EventSeverity] = None,
        resource: Optional[Resource] = None,
        success: bool = True,
        outcome: str = "success",
        error_message: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ) -> SecurityEvent:
        """
        Log a security audit event.
        
        Args:
            event_type: Type of security event
            actor: Who performed the action
            action: Description of the action
            severity: Event severity (auto-determined if not provided)
            resource: Resource being accessed/modified
            success: Whether the action succeeded
            outcome: Outcome description
            error_message: Error message if failed
            context: Additional context
            correlation_id: Request correlation ID
            
        Returns:
            The logged SecurityEvent
        """
        # Auto-determine severity if not provided
        if severity is None:
            severity = self._determine_severity(event_type, success)
        
        # Create event
        event = SecurityEvent(
            event_type=event_type,
            severity=severity,
            category=self._get_category(event_type),
            actor=actor,
            action=action,
            resource=resource,
            success=success,
            outcome=outcome,
            error_message=error_message,
            context=context or {},
            correlation_id=correlation_id,
            compliance_controls=self._map_compliance_controls(event_type),
        )
        
        # Add hash chain integrity
        if self.config.enable_chain_verification:
            event.previous_hash = self._last_hash
            event.event_hash = event.compute_hash(self._last_hash)
            self._last_hash = event.event_hash
        
        # Add HMAC signature
        if self.config.enable_hmac:
            event.hmac_signature = self._sign_event(event)
        
        # Store event
        self._events.append(event)
        
        # Check for anomalies
        await self._check_anomalies(event)
        
        # Call event handlers
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception:
                pass  # Don't let handler errors affect logging
        
        # Alert if needed
        if self._should_alert(event):
            await self._create_alert(event)
        
        return event
    
    async def query(self, query: AuditQuery) -> AuditQueryResult:
        """
        Query audit logs.
        
        Args:
            query: Query parameters
            
        Returns:
            AuditQueryResult with matching events
        """
        # Filter events
        events = self._events.copy()
        
        if query.start_time:
            events = [e for e in events if e.timestamp >= query.start_time]
        
        if query.end_time:
            events = [e for e in events if e.timestamp <= query.end_time]
        
        if query.event_types:
            events = [e for e in events if e.event_type in query.event_types]
        
        if query.severities:
            events = [e for e in events if e.severity in query.severities]
        
        if query.actor_ids:
            events = [e for e in events if e.actor.id in query.actor_ids]
        
        if query.resource_types:
            events = [e for e in events if e.resource and e.resource.type in query.resource_types]
        
        if query.text_search:
            search_lower = query.text_search.lower()
            events = [
                e for e in events
                if search_lower in e.action.lower() or
                   search_lower in e.actor.id.lower() or
                   (e.resource and search_lower in e.resource.name.lower())
            ]
        
        # Sort
        reverse = query.sort_desc
        if query.sort_by == "timestamp":
            events.sort(key=lambda e: e.timestamp, reverse=reverse)
        elif query.sort_by == "severity":
            severity_order = {s: i for i, s in enumerate(EventSeverity)}
            events.sort(key=lambda e: severity_order[e.severity], reverse=reverse)
        
        total_count = len(events)
        
        # Paginate
        events = events[query.offset : query.offset + query.limit]
        
        return AuditQueryResult(
            events=events,
            total_count=total_count,
            query=query,
        )
    
    async def generate_compliance_report(
        self,
        framework: ComplianceFramework,
        period_start: datetime,
        period_end: datetime,
    ) -> ComplianceReport:
        """
        Generate a compliance audit report.
        
        Args:
            framework: Compliance framework to report on
            period_start: Report period start
            period_end: Report period end
            
        Returns:
            ComplianceReport with findings and scores
        """
        # Query events in period
        query = AuditQuery(
            start_time=period_start,
            end_time=period_end,
            limit=100000,
        )
        result = await self.query(query)
        
        # Count events by type and severity
        events_by_type: dict[str, int] = {}
        events_by_severity: dict[str, int] = {}
        
        for event in result.events:
            events_by_type[event.event_type.value] = events_by_type.get(event.event_type.value, 0) + 1
            events_by_severity[event.severity.value] = events_by_severity.get(event.severity.value, 0) + 1
        
        # Evaluate compliance controls
        controls = self._get_framework_controls(framework)
        controls_passed = 0
        controls_failed = 0
        findings = []
        
        for control in controls:
            passed, finding = self._evaluate_control(control, result.events)
            if passed:
                controls_passed += 1
            else:
                controls_failed += 1
                findings.append(finding)
        
        # Calculate score
        total_controls = len(controls)
        score = (controls_passed / total_controls * 100) if total_controls > 0 else 100.0
        
        return ComplianceReport(
            framework=framework,
            period_start=period_start,
            period_end=period_end,
            total_events=result.total_count,
            events_by_type=events_by_type,
            events_by_severity=events_by_severity,
            controls_checked=total_controls,
            controls_passed=controls_passed,
            controls_failed=controls_failed,
            findings=findings,
            compliance_score=score,
        )
    
    async def verify_chain_integrity(
        self,
        start_index: int = 0,
        end_index: Optional[int] = None,
    ) -> tuple[bool, list[str]]:
        """
        Verify the integrity of the audit log hash chain.
        
        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []
        events = self._events[start_index:end_index]
        
        prev_hash = None
        for i, event in enumerate(events):
            if i == 0 and start_index == 0:
                # First event should have no previous hash
                if event.previous_hash is not None:
                    errors.append(f"Event {event.id}: First event has previous_hash")
            else:
                if event.previous_hash != prev_hash:
                    errors.append(f"Event {event.id}: previous_hash mismatch")
            
            # Verify event hash
            computed_hash = event.compute_hash(event.previous_hash)
            if event.event_hash != computed_hash:
                errors.append(f"Event {event.id}: event_hash mismatch (tampering detected)")
            
            prev_hash = event.event_hash
        
        return len(errors) == 0, errors
    
    async def verify_hmac(self, event: SecurityEvent) -> bool:
        """Verify HMAC signature of an event."""
        if not event.hmac_signature:
            return False
        
        expected_sig = self._sign_event(event)
        return hmac.compare_digest(event.hmac_signature, expected_sig)
    
    def add_event_handler(self, handler: Callable[[SecurityEvent], None]) -> None:
        """Add a handler to be called for each logged event."""
        self._event_handlers.append(handler)
    
    def get_alerts(
        self,
        acknowledged: Optional[bool] = None,
        resolved: Optional[bool] = None,
        limit: int = 100,
    ) -> list[SecurityAlert]:
        """Get security alerts."""
        alerts = self._alerts.copy()
        
        if acknowledged is not None:
            alerts = [a for a in alerts if a.acknowledged == acknowledged]
        
        if resolved is not None:
            alerts = [a for a in alerts if a.resolved == resolved]
        
        return alerts[-limit:]
    
    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge a security alert."""
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                alert.acknowledged_by = acknowledged_by
                return True
        return False
    
    # ==========================================================================
    # Private Methods
    # ==========================================================================
    
    def _load_hmac_key(self) -> bytes:
        """Load or generate HMAC signing key."""
        if self.config.hmac_key_path and os.path.exists(self.config.hmac_key_path):
            with open(self.config.hmac_key_path, "rb") as f:
                return f.read()
        return os.urandom(32)  # Generate random key
    
    def _sign_event(self, event: SecurityEvent) -> str:
        """Sign an event with HMAC."""
        data = f"{event.id}:{event.timestamp.isoformat()}:{event.event_type.value}"
        return hmac.new(self._hmac_key, data.encode(), hashlib.sha256).hexdigest()
    
    def _determine_severity(self, event_type: SecurityEventType, success: bool) -> EventSeverity:
        """Determine severity based on event type."""
        # Critical events
        if event_type in [
            SecurityEventType.INTRUSION_ATTEMPT,
            SecurityEventType.DATA_EXFILTRATION,
            SecurityEventType.PRIVILEGE_ESCALATION,
        ]:
            return EventSeverity.CRITICAL
        
        # High severity events
        if event_type in [
            SecurityEventType.BRUTE_FORCE_DETECTED,
            SecurityEventType.SUSPICIOUS_ACTIVITY,
            SecurityEventType.POLICY_VIOLATION,
            SecurityEventType.SECRET_ACCESS,
        ]:
            return EventSeverity.HIGH
        
        # Medium severity events
        if event_type in [
            SecurityEventType.LOGIN_FAILURE,
            SecurityEventType.ACCESS_DENIED,
            SecurityEventType.MFA_FAILURE,
            SecurityEventType.CONFIG_CHANGE,
            SecurityEventType.ROLE_CHANGE,
        ]:
            return EventSeverity.MEDIUM
        
        # Low severity events
        if event_type in [
            SecurityEventType.PASSWORD_CHANGE,
            SecurityEventType.API_KEY_CREATED,
            SecurityEventType.API_KEY_REVOKED,
        ]:
            return EventSeverity.LOW
        
        return EventSeverity.INFO
    
    def _get_category(self, event_type: SecurityEventType) -> str:
        """Get category for event type."""
        auth_events = [
            SecurityEventType.LOGIN_SUCCESS,
            SecurityEventType.LOGIN_FAILURE,
            SecurityEventType.LOGOUT,
            SecurityEventType.MFA_CHALLENGE,
            SecurityEventType.MFA_SUCCESS,
            SecurityEventType.MFA_FAILURE,
            SecurityEventType.PASSWORD_CHANGE,
            SecurityEventType.API_KEY_CREATED,
            SecurityEventType.API_KEY_REVOKED,
        ]
        
        access_events = [
            SecurityEventType.ACCESS_GRANTED,
            SecurityEventType.ACCESS_DENIED,
            SecurityEventType.RESOURCE_READ,
            SecurityEventType.RESOURCE_CREATE,
            SecurityEventType.RESOURCE_UPDATE,
            SecurityEventType.RESOURCE_DELETE,
            SecurityEventType.SECRET_ACCESS,
        ]
        
        security_events = [
            SecurityEventType.BRUTE_FORCE_DETECTED,
            SecurityEventType.SUSPICIOUS_ACTIVITY,
            SecurityEventType.ANOMALY_DETECTED,
            SecurityEventType.POLICY_VIOLATION,
            SecurityEventType.DATA_EXFILTRATION,
            SecurityEventType.INTRUSION_ATTEMPT,
            SecurityEventType.PRIVILEGE_ESCALATION,
        ]
        
        if event_type in auth_events:
            return "authentication"
        elif event_type in access_events:
            return "access"
        elif event_type in security_events:
            return "security"
        else:
            return "system"
    
    def _map_compliance_controls(self, event_type: SecurityEventType) -> list[str]:
        """Map event type to compliance controls."""
        mappings = {
            SecurityEventType.LOGIN_SUCCESS: ["SOC2-CC6.1", "PCI-8.2", "ISO-A.9.4.2"],
            SecurityEventType.LOGIN_FAILURE: ["SOC2-CC6.1", "PCI-8.2", "ISO-A.9.4.2"],
            SecurityEventType.ACCESS_DENIED: ["SOC2-CC6.3", "PCI-7.1", "ISO-A.9.4.1"],
            SecurityEventType.SECRET_ACCESS: ["SOC2-CC6.7", "PCI-3.4", "ISO-A.10.1.2"],
            SecurityEventType.CONFIG_CHANGE: ["SOC2-CC8.1", "PCI-11.5", "ISO-A.12.1.2"],
        }
        return mappings.get(event_type, [])
    
    def _get_framework_controls(self, framework: ComplianceFramework) -> list[dict]:
        """Get controls for a compliance framework."""
        # Simplified control list
        controls = {
            ComplianceFramework.SOC2: [
                {"id": "CC6.1", "name": "User Authentication", "description": "Verify user authentication controls"},
                {"id": "CC6.3", "name": "Access Control", "description": "Verify access control mechanisms"},
                {"id": "CC6.7", "name": "Data Protection", "description": "Verify data protection controls"},
                {"id": "CC8.1", "name": "Change Management", "description": "Verify change management"},
            ],
            ComplianceFramework.PCI_DSS: [
                {"id": "8.2", "name": "Authentication", "description": "Strong authentication"},
                {"id": "7.1", "name": "Access Restriction", "description": "Restrict access to system components"},
                {"id": "10.1", "name": "Audit Trails", "description": "Audit trail linking"},
            ],
        }
        return controls.get(framework, [])
    
    def _evaluate_control(
        self, control: dict, events: list[SecurityEvent]
    ) -> tuple[bool, Optional[dict]]:
        """Evaluate a compliance control against events."""
        # Simplified control evaluation
        control_id = control["id"]
        
        # Example: Check for authentication failures without lockout
        if control_id == "CC6.1" or control_id == "8.2":
            failures = [e for e in events if e.event_type == SecurityEventType.LOGIN_FAILURE]
            if len(failures) > 100:
                return False, {
                    "control_id": control_id,
                    "finding": "Excessive login failures detected",
                    "count": len(failures),
                    "recommendation": "Implement account lockout policy",
                }
        
        return True, None
    
    def _should_alert(self, event: SecurityEvent) -> bool:
        """Check if event should trigger an alert."""
        if not self.alert_config.enabled:
            return False
        
        if event.severity == EventSeverity.CRITICAL and self.config.alert_on_critical:
            return True
        
        if event.severity == EventSeverity.HIGH and self.config.alert_on_high:
            return True
        
        return False
    
    async def _create_alert(self, event: SecurityEvent) -> SecurityAlert:
        """Create a security alert from an event."""
        alert = SecurityAlert(
            severity=event.severity,
            title=f"{event.event_type.value.replace('_', ' ').title()} Detected",
            description=f"{event.action} by {event.actor.id}",
            event_ids=[event.id],
            actor=event.actor,
            source_ip=event.actor.ip_address,
            recommended_actions=self._get_recommended_actions(event),
        )
        
        self._alerts.append(alert)
        return alert
    
    async def _check_anomalies(self, event: SecurityEvent) -> None:
        """Check for anomalous patterns."""
        # Track login failures by IP
        if event.event_type == SecurityEventType.LOGIN_FAILURE:
            ip = event.actor.ip_address or "unknown"
            now = datetime.utcnow()
            window = timedelta(minutes=self.alert_config.login_failure_window_minutes)
            
            if ip not in self._login_failures:
                self._login_failures[ip] = []
            
            # Add this failure
            self._login_failures[ip].append(now)
            
            # Remove old failures outside window
            self._login_failures[ip] = [
                ts for ts in self._login_failures[ip]
                if now - ts <= window
            ]
            
            # Check threshold
            if len(self._login_failures[ip]) >= self.alert_config.login_failure_threshold:
                # Log brute force detection
                await self.log_event(
                    event_type=SecurityEventType.BRUTE_FORCE_DETECTED,
                    actor=event.actor,
                    action=f"Brute force attack detected from {ip}",
                    severity=EventSeverity.HIGH,
                    context={
                        "failure_count": len(self._login_failures[ip]),
                        "window_minutes": self.alert_config.login_failure_window_minutes,
                    },
                )
    
    def _get_recommended_actions(self, event: SecurityEvent) -> list[str]:
        """Get recommended actions for an event."""
        recommendations = {
            SecurityEventType.BRUTE_FORCE_DETECTED: [
                "Block source IP address",
                "Enable account lockout",
                "Review authentication logs",
                "Consider implementing CAPTCHA",
            ],
            SecurityEventType.INTRUSION_ATTEMPT: [
                "Isolate affected systems",
                "Capture forensic evidence",
                "Notify security team",
                "Review access patterns",
            ],
            SecurityEventType.PRIVILEGE_ESCALATION: [
                "Revoke elevated privileges",
                "Review authorization changes",
                "Audit system access",
            ],
        }
        return recommendations.get(event.event_type, ["Review event and take appropriate action"])


# =============================================================================
# Backwards Compatibility Layer
# =============================================================================
# These classes maintain compatibility with the original simpler audit API
# used by tests and older code.


class EventType(str, Enum):
    """Simple event types for backwards compatibility."""
    
    # Auth events
    AUTH_SUCCESS = "auth.success"
    AUTH_FAILURE = "auth.failure"
    AUTH_REVOKE = "auth.revoke"
    
    # Investigation events
    INVESTIGATION_START = "investigation.start"
    INVESTIGATION_COMPLETE = "investigation.complete"
    
    # Action events
    ACTION_PROPOSED = "action.proposed"
    ACTION_APPROVED = "action.approved"
    ACTION_REJECTED = "action.rejected"
    ACTION_EXECUTED = "action.executed"
    ACTION_FAILED = "action.failed"
    
    # Security events
    COMMAND_SANITIZE_FAIL = "command.sanitize_fail"
    PERMISSION_DENIED = "permission.denied"
    
    # Config events
    CONFIG_CHANGE = "config.change"


@dataclass
class AuditEntry:
    """Simple audit entry for backwards compatibility."""
    
    timestamp: str
    event_type: str
    user: str
    action: str
    result: str
    details: dict = field(default_factory=dict)
    source_ip: Optional[str] = None
    session_id: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert entry to dictionary."""
        d = {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "user": self.user,
            "action": self.action,
            "result": self.result,
            "details": self.details,
        }
        if self.source_ip:
            d["source_ip"] = self.source_ip
        if self.session_id:
            d["session_id"] = self.session_id
        return d
    
    def to_json(self) -> str:
        """Convert entry to JSON string."""
        return json.dumps(self.to_dict())


class AuditLogger:
    """Simple audit logger for backwards compatibility."""
    
    def __init__(self, log_dir: str = "/var/log/autosre/audit"):
        """Initialize audit logger."""
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self._current_file: Optional[str] = None
    
    def _get_log_file(self) -> str:
        """Get current log file path."""
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        return os.path.join(self.log_dir, f"audit-{date_str}.jsonl")
    
    def log(
        self,
        event_type: Union[EventType, str],
        user: str,
        action: str,
        result: str = "success",
        details: Optional[dict] = None,
        source_ip: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> AuditEntry:
        """Log an audit entry."""
        # Convert EventType enum to string if needed
        if isinstance(event_type, EventType):
            event_type_str = event_type.value
        else:
            event_type_str = str(event_type)
        
        entry = AuditEntry(
            timestamp=datetime.utcnow().isoformat() + "Z",
            event_type=event_type_str,
            user=user,
            action=action,
            result=result,
            details=details or {},
            source_ip=source_ip,
            session_id=session_id,
        )
        
        # Write to log file
        log_file = self._get_log_file()
        with open(log_file, "a") as f:
            f.write(entry.to_json() + "\n")
        
        return entry
    
    def log_investigation(
        self,
        user: str,
        issue: str,
        namespace: Optional[str] = None,
        **kwargs,
    ) -> AuditEntry:
        """Log investigation start."""
        action = f"Started investigation: {issue}"
        details = {"issue": issue}
        if namespace:
            details["namespace"] = namespace
        details.update(kwargs)
        
        return self.log(
            event_type=EventType.INVESTIGATION_START,
            user=user,
            action=action,
            details=details,
        )
    
    def log_investigation_complete(
        self,
        user: str,
        investigation_id: str,
        root_cause: str,
        actions_count: int = 0,
        **kwargs,
    ) -> AuditEntry:
        """Log investigation completion."""
        details = {
            "investigation_id": investigation_id,
            "root_cause": root_cause,
            "actions_count": actions_count,
            "actions_proposed": actions_count,  # Alias for backwards compatibility
        }
        details.update(kwargs)
        
        return self.log(
            event_type=EventType.INVESTIGATION_COMPLETE,
            user=user,
            action=f"Completed investigation {investigation_id}",
            details=details,
        )
    
    def log_action_proposed(
        self,
        user: str,
        action_id: str,
        command: str,
        risk: str = "low",
        **kwargs,
    ) -> AuditEntry:
        """Log action proposal."""
        details = {
            "action_id": action_id,
            "command": command,
            "risk_level": risk,
        }
        details.update(kwargs)
        
        return self.log(
            event_type=EventType.ACTION_PROPOSED,
            user=user,
            action=f"Proposed action: {command}",
            details=details,
        )
    
    def log_action_approved(
        self,
        user: str,
        action_id: str,
        approver: Optional[str] = None,
        command: Optional[str] = None,
        approved_by: Optional[str] = None,
        **kwargs,
    ) -> AuditEntry:
        """Log action approval."""
        details = {"action_id": action_id}
        # Support both 'approver' and 'approved_by' for backwards compatibility
        actual_approver = approved_by or approver
        if actual_approver:
            details["approver"] = actual_approver
            details["approved_by"] = actual_approver
        if command:
            details["command"] = command
        details.update(kwargs)
        
        return self.log(
            event_type=EventType.ACTION_APPROVED,
            user=user,
            action=f"Approved action {action_id}",
            details=details,
        )
    
    def log_action_executed(
        self,
        user: str,
        action_id: str,
        command: str,
        output: Optional[str] = None,
        exit_code: Optional[int] = None,
        **kwargs,
    ) -> AuditEntry:
        """Log action execution."""
        details = {
            "action_id": action_id,
            "command": command,
        }
        if output:
            details["output"] = output
        if exit_code is not None:
            details["exit_code"] = str(exit_code)
        details.update(kwargs)
        
        # Determine result based on exit_code
        result = "success"
        if exit_code is not None and exit_code != 0:
            result = "failure"
        
        return self.log(
            event_type=EventType.ACTION_EXECUTED,
            user=user,
            action=f"Executed: {command}",
            result=result,
            details=details,
        )
    
    def log_action_rejected(
        self,
        user: str,
        action_id: str,
        reason: str,
        **kwargs,
    ) -> AuditEntry:
        """Log action rejection."""
        details = {
            "action_id": action_id,
            "reason": reason,
        }
        details.update(kwargs)
        
        return self.log(
            event_type=EventType.ACTION_REJECTED,
            user=user,
            action=f"Rejected action {action_id}: {reason}",
            result="rejected",
            details=details,
        )
    
    def log_sanitize_failure(
        self,
        user: str,
        command: str,
        reason: str,
        **kwargs,
    ) -> AuditEntry:
        """Log command sanitization failure."""
        details = {
            "command": command,
            "reason": reason,
        }
        details.update(kwargs)
        
        return self.log(
            event_type=EventType.COMMAND_SANITIZE_FAIL,
            user=user,
            action=f"Blocked command: {command}",
            result="blocked",
            details=details,
        )
    
    def log_permission_denied(
        self,
        user: str,
        action: str,
        required_permission: str,
        **kwargs,
    ) -> AuditEntry:
        """Log permission denied event."""
        details = {
            "action": action,
            "required_permission": required_permission,
        }
        details.update(kwargs)
        
        return self.log(
            event_type=EventType.PERMISSION_DENIED,
            user=user,
            action=f"Permission denied for: {action}",
            result="denied",
            details=details,
        )
    
    def _get_log_path(self):
        """Get current log file path as Path object."""
        from pathlib import Path
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        return Path(self.log_dir) / f"audit-{date_str}.jsonl"


# Global logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger(log_dir: Optional[str] = None) -> AuditLogger:
    """Get or create the global audit logger."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger(log_dir=log_dir or "/var/log/autosre/audit")
    return _audit_logger


def audit_log(
    event_type: Union[EventType, str],
    user: str,
    action: str,
    **kwargs,
) -> AuditEntry:
    """Convenience function to log an audit entry."""
    logger = get_audit_logger()
    return logger.log(event_type=event_type, user=user, action=action, **kwargs)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Enums
    "SecurityEventType",
    "EventSeverity",
    "AuditLogDestination",
    "ComplianceFramework",
    # Configuration
    "SecurityAuditConfig",
    "AlertConfig",
    # Models
    "Actor",
    "Resource",
    "SecurityEvent",
    "AuditLogEntry",
    # Query and Reporting
    "AuditQuery",
    "AuditQueryResult",
    "ComplianceReport",
    "SecurityAlert",
    # Logger
    "SecurityAuditLogger",
    # Backwards compatibility
    "EventType",
    "AuditEntry",
    "AuditLogger",
    "get_audit_logger",
    "audit_log",
]
