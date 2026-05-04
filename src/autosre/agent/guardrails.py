"""
Guardrails - Safety checks and approval flows.

Ensures that:
- Destructive actions require approval
- Blast radius is limited
- All actions are audited
- Dry run is the default
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from enum import Enum

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class ApprovalStatus(str, Enum):
    """Status of an approval request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    AUTO_APPROVED = "auto_approved"


class RiskLevel(str, Enum):
    """Risk level of an action."""
    LOW = "low"        # Can auto-approve
    MEDIUM = "medium"  # Requires human approval
    HIGH = "high"      # Requires senior approval
    CRITICAL = "critical"  # Requires multiple approvals


class ApprovalRequest(BaseModel):
    """A request for action approval."""
    id: str
    action_type: str
    target: str
    description: str
    
    # Risk assessment
    risk_level: RiskLevel
    blast_radius: int = Field(default=0, description="Number of potentially affected services")
    
    # Requester
    requester: str = Field(default="autosre-agent")
    reason: str = Field(default="Automated remediation")
    
    # Approval
    status: ApprovalStatus = Field(default=ApprovalStatus.PENDING)
    approver: Optional[str] = None
    approval_notes: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


class AuditEntry(BaseModel):
    """An audit log entry."""
    timestamp: datetime = Field(default_factory=utcnow)
    action_type: str
    target: str
    actor: str = Field(default="autosre-agent")
    
    # Details
    status: str
    details: dict = Field(default_factory=dict)
    
    # Approval
    approval_id: Optional[str] = None
    approved_by: Optional[str] = None


class Guardrails:
    """
    Safety guardrails for automated actions.
    
    Provides:
    - Risk assessment
    - Approval workflow
    - Blast radius checks
    - Audit logging
    """
    
    def __init__(
        self,
        db_path: Optional[str] = None,
        auto_approve_low_risk: bool = True,
        max_blast_radius: int = 5,
    ):
        """
        Initialize guardrails.
        
        Args:
            db_path: Path to audit database
            auto_approve_low_risk: Auto-approve low risk actions
            max_blast_radius: Maximum services that can be affected
        """
        if db_path is None:
            db_path = str(Path.home() / ".autosre" / "audit.db")
        
        self.db_path = db_path
        self.auto_approve_low_risk = auto_approve_low_risk
        self.max_blast_radius = max_blast_radius
        
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize audit database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY,
                    action_type TEXT NOT NULL,
                    target TEXT NOT NULL,
                    description TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    blast_radius INTEGER DEFAULT 0,
                    requester TEXT NOT NULL,
                    reason TEXT,
                    status TEXT NOT NULL,
                    approver TEXT,
                    approval_notes TEXT,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    resolved_at TEXT
                );
                
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    target TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    status TEXT NOT NULL,
                    details TEXT,
                    approval_id TEXT,
                    approved_by TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
                CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status);
            """)
    
    def assess_risk(
        self,
        action_type: str,
        target: str,
        params: Optional[dict] = None,
    ) -> tuple[RiskLevel, int]:
        """
        Assess the risk level of an action.
        
        Returns:
            Tuple of (risk_level, blast_radius)
        """
        params = params or {}
        
        # Default risk levels by action type
        risk_map = {
            "notification": RiskLevel.LOW,
            "ticket": RiskLevel.LOW,
            "scale": RiskLevel.MEDIUM,
            "restart": RiskLevel.MEDIUM,
            "rollback": RiskLevel.HIGH,
            "script": RiskLevel.CRITICAL,
        }
        
        risk = risk_map.get(action_type, RiskLevel.MEDIUM)
        
        # Estimate blast radius
        blast_radius = 1  # At minimum, affects the target
        
        # Increase for critical services
        if params.get("tier", 3) == 1:
            risk = RiskLevel.HIGH if risk == RiskLevel.MEDIUM else risk
            blast_radius = max(blast_radius, 3)
        
        # Increase for production namespace
        if params.get("namespace") == "production":
            if risk == RiskLevel.LOW:
                risk = RiskLevel.MEDIUM
        
        # Scale affects more services
        if action_type == "scale":
            replicas = params.get("replicas", 1)
            current = params.get("current_replicas", 1)
            if replicas == 0:
                risk = RiskLevel.HIGH
                blast_radius = max(blast_radius, 5)
            elif replicas < current / 2:
                risk = RiskLevel.HIGH
        
        return risk, blast_radius
    
    def request_approval(
        self,
        action_type: str,
        target: str,
        description: str,
        risk_level: RiskLevel,
        blast_radius: int,
        reason: str = "Automated remediation",
    ) -> ApprovalRequest:
        """
        Request approval for an action.
        
        Returns:
            ApprovalRequest with status
        """
        import uuid
        from datetime import timedelta
        
        request = ApprovalRequest(
            id=str(uuid.uuid4())[:8],
            action_type=action_type,
            target=target,
            description=description,
            risk_level=risk_level,
            blast_radius=blast_radius,
            reason=reason,
            expires_at=utcnow() + timedelta(hours=1),
        )
        
        # Check auto-approval
        if self.auto_approve_low_risk and risk_level == RiskLevel.LOW:
            request.status = ApprovalStatus.AUTO_APPROVED
            request.approver = "auto"
            request.resolved_at = utcnow()
        
        # Check blast radius
        if blast_radius > self.max_blast_radius:
            request.status = ApprovalStatus.REJECTED
            request.approval_notes = f"Blast radius {blast_radius} exceeds limit {self.max_blast_radius}"
            request.resolved_at = utcnow()
        
        # Save to database
        self._save_approval(request)
        
        return request
    
    def approve(
        self,
        approval_id: str,
        approver: str,
        notes: Optional[str] = None,
    ) -> Optional[ApprovalRequest]:
        """
        Approve a pending request.
        
        Returns:
            Updated ApprovalRequest or None if not found
        """
        request = self._get_approval(approval_id)
        if not request:
            return None
        
        if request.status != ApprovalStatus.PENDING:
            return request
        
        request.status = ApprovalStatus.APPROVED
        request.approver = approver
        request.approval_notes = notes
        request.resolved_at = utcnow()
        
        self._save_approval(request)
        
        return request
    
    def reject(
        self,
        approval_id: str,
        approver: str,
        notes: Optional[str] = None,
    ) -> Optional[ApprovalRequest]:
        """
        Reject a pending request.
        
        Returns:
            Updated ApprovalRequest or None if not found
        """
        request = self._get_approval(approval_id)
        if not request:
            return None
        
        if request.status != ApprovalStatus.PENDING:
            return request
        
        request.status = ApprovalStatus.REJECTED
        request.approver = approver
        request.approval_notes = notes
        request.resolved_at = utcnow()
        
        self._save_approval(request)
        
        return request
    
    def audit(
        self,
        action_type: str,
        target: str,
        status: str,
        details: Optional[dict] = None,
        approval_id: Optional[str] = None,
        approved_by: Optional[str] = None,
    ) -> None:
        """
        Log an action to the audit trail.
        
        Args:
            action_type: Type of action
            target: Target of the action
            status: Result status
            details: Additional details
            approval_id: Related approval ID
            approved_by: Who approved (if applicable)
        """
        entry = AuditEntry(
            action_type=action_type,
            target=target,
            status=status,
            details=details or {},
            approval_id=approval_id,
            approved_by=approved_by,
        )
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO audit_log
                (timestamp, action_type, target, actor, status, details, approval_id, approved_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.timestamp.isoformat(),
                entry.action_type,
                entry.target,
                entry.actor,
                entry.status,
                json.dumps(entry.details),
                entry.approval_id,
                entry.approved_by,
            ))
    
    def get_audit_log(
        self,
        limit: int = 100,
        action_type: Optional[str] = None,
    ) -> list[dict]:
        """Get audit log entries."""
        query = "SELECT * FROM audit_log"
        params = []
        
        if action_type:
            query += " WHERE action_type = ?"
            params.append(action_type)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            
            return [
                {
                    "timestamp": row["timestamp"],
                    "action_type": row["action_type"],
                    "target": row["target"],
                    "actor": row["actor"],
                    "status": row["status"],
                    "details": json.loads(row["details"]) if row["details"] else {},
                    "approval_id": row["approval_id"],
                    "approved_by": row["approved_by"],
                }
                for row in rows
            ]
    
    def get_pending_approvals(self) -> list[ApprovalRequest]:
        """Get all pending approval requests."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM approvals WHERE status = ?",
                (ApprovalStatus.PENDING.value,)
            ).fetchall()
            
            return [self._row_to_approval(row) for row in rows]
    
    def _save_approval(self, request: ApprovalRequest) -> None:
        """Save an approval request."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO approvals
                (id, action_type, target, description, risk_level, blast_radius,
                 requester, reason, status, approver, approval_notes,
                 created_at, expires_at, resolved_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                request.id,
                request.action_type,
                request.target,
                request.description,
                request.risk_level.value,
                request.blast_radius,
                request.requester,
                request.reason,
                request.status.value,
                request.approver,
                request.approval_notes,
                request.created_at.isoformat(),
                request.expires_at.isoformat() if request.expires_at else None,
                request.resolved_at.isoformat() if request.resolved_at else None,
            ))
    
    def _get_approval(self, approval_id: str) -> Optional[ApprovalRequest]:
        """Get an approval request by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM approvals WHERE id = ?",
                (approval_id,)
            ).fetchone()
            
            if row:
                return self._row_to_approval(row)
            return None
    
    def _row_to_approval(self, row: sqlite3.Row) -> ApprovalRequest:
        """Convert a database row to ApprovalRequest."""
        return ApprovalRequest(
            id=row["id"],
            action_type=row["action_type"],
            target=row["target"],
            description=row["description"],
            risk_level=RiskLevel(row["risk_level"]),
            blast_radius=row["blast_radius"],
            requester=row["requester"],
            reason=row["reason"],
            status=ApprovalStatus(row["status"]),
            approver=row["approver"],
            approval_notes=row["approval_notes"],
            created_at=datetime.fromisoformat(row["created_at"]),
            expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
            resolved_at=datetime.fromisoformat(row["resolved_at"]) if row["resolved_at"] else None,
        )
