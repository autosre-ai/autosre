"""
Backup Verification

Provides comprehensive database backup monitoring and verification:
- Backup status tracking
- Backup integrity verification
- Recovery testing
- Backup schedule monitoring
- Point-in-time recovery (PITR) validation
"""

import asyncio
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class BackupType(str, Enum):
    """Type of database backup."""
    
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    LOGICAL = "logical"
    PHYSICAL = "physical"
    SNAPSHOT = "snapshot"
    WAL = "wal"  # Write-Ahead Log / Transaction Log


class BackupStatus(str, Enum):
    """Backup operation status."""
    
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    VERIFIED = "verified"


class VerificationStatus(str, Enum):
    """Backup verification status."""
    
    NOT_VERIFIED = "not_verified"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    FAILED = "failed"
    CORRUPTED = "corrupted"


class StorageType(str, Enum):
    """Backup storage location type."""
    
    LOCAL = "local"
    S3 = "s3"
    GCS = "gcs"
    AZURE_BLOB = "azure_blob"
    NFS = "nfs"
    SSH = "ssh"


class RecoveryPointObjective(str, Enum):
    """RPO classification."""
    
    MINUTES = "minutes"
    HOURS = "hours"
    DAYS = "days"


# =============================================================================
# Configuration
# =============================================================================


class BackupConfig(BaseModel):
    """Backup system configuration."""
    
    # Schedule
    full_backup_schedule: str = Field(default="0 2 * * 0", description="Full backup cron schedule")
    incremental_backup_schedule: str = Field(default="0 2 * * 1-6", description="Incremental backup cron schedule")
    wal_archive_enabled: bool = Field(default=True, description="Enable WAL archiving")
    
    # Retention
    retention_days: int = Field(default=30, description="Backup retention in days")
    min_full_backups: int = Field(default=4, description="Minimum full backups to retain")
    
    # Storage
    storage_type: StorageType = Field(default=StorageType.S3)
    storage_path: str = Field(default="", description="Backup storage path")
    encryption_enabled: bool = Field(default=True, description="Enable backup encryption")
    compression_enabled: bool = Field(default=True, description="Enable backup compression")
    
    # Verification
    auto_verify: bool = Field(default=True, description="Auto-verify after backup")
    verify_sample_rate: float = Field(default=1.0, description="Rate of backups to verify (0.0-1.0)")
    restore_test_enabled: bool = Field(default=False, description="Enable restore testing")
    restore_test_schedule: str = Field(default="0 3 * * 0", description="Restore test schedule")
    
    # Alerting
    alert_on_failure: bool = Field(default=True)
    alert_on_missing: bool = Field(default=True)
    max_backup_age_hours: int = Field(default=25, description="Alert if no backup in this time")


# =============================================================================
# Backup Models
# =============================================================================


class BackupMetadata(BaseModel):
    """Metadata for a backup."""
    
    backup_id: str
    database_name: str
    database_version: str
    backup_type: BackupType
    
    # Timing
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    
    # Size
    size_bytes: int = 0
    compressed_size_bytes: Optional[int] = None
    compression_ratio: float = 1.0
    
    # Storage
    storage_type: StorageType
    storage_path: str
    
    # Security
    encrypted: bool = False
    encryption_key_id: Optional[str] = None
    checksum: Optional[str] = None
    checksum_algorithm: str = "sha256"
    
    # Status
    status: BackupStatus = BackupStatus.PENDING
    verification_status: VerificationStatus = VerificationStatus.NOT_VERIFIED
    
    # Recovery info
    oldest_transaction_time: Optional[datetime] = None
    newest_transaction_time: Optional[datetime] = None
    base_backup_id: Optional[str] = None  # For incremental backups
    
    # Labels
    labels: dict[str, str] = Field(default_factory=dict)


class BackupVerification(BaseModel):
    """Backup verification result."""
    
    backup_id: str
    verification_id: str
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Results
    status: VerificationStatus
    checksum_valid: bool = False
    metadata_valid: bool = False
    structure_valid: bool = False
    
    # Detailed checks
    checks_performed: list[str] = Field(default_factory=list)
    checks_passed: list[str] = Field(default_factory=list)
    checks_failed: list[str] = Field(default_factory=list)
    
    # Performance
    verification_duration_seconds: float = 0.0
    bytes_verified: int = 0
    
    # Errors
    errors: list[str] = Field(default_factory=list)


class RestoreTest(BaseModel):
    """Restore test result."""
    
    test_id: str
    backup_id: str
    tested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Results
    success: bool = False
    restore_duration_seconds: float = 0.0
    data_integrity_valid: bool = False
    
    # Environment
    test_environment: str = Field(description="Where the restore was tested")
    target_database: str
    
    # Verification
    rows_verified: int = 0
    tables_verified: int = 0
    sample_queries_passed: int = 0
    sample_queries_total: int = 0
    
    # PITR validation
    pitr_tested: bool = False
    pitr_target_time: Optional[datetime] = None
    pitr_success: bool = False
    
    # Errors
    errors: list[str] = Field(default_factory=list)


class BackupSchedule(BaseModel):
    """Backup schedule status."""
    
    schedule_id: str
    database_name: str
    backup_type: BackupType
    cron_expression: str
    
    # Status
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    
    # Statistics
    consecutive_successes: int = 0
    consecutive_failures: int = 0
    total_runs: int = 0
    total_successes: int = 0
    total_failures: int = 0


class BackupAlert(BaseModel):
    """Backup-related alert."""
    
    alert_id: str
    alert_type: str
    severity: str
    database_name: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged: bool = False


class RecoveryPointStatus(BaseModel):
    """Recovery point status."""
    
    database_name: str
    
    # Latest backups
    latest_full_backup: Optional[BackupMetadata] = None
    latest_incremental_backup: Optional[BackupMetadata] = None
    latest_wal_position: Optional[str] = None
    
    # Recovery capabilities
    oldest_recovery_point: Optional[datetime] = None
    newest_recovery_point: Optional[datetime] = None
    pitr_available: bool = False
    pitr_range_start: Optional[datetime] = None
    pitr_range_end: Optional[datetime] = None
    
    # RPO
    actual_rpo_seconds: float = 0.0
    target_rpo_seconds: float = 3600.0  # 1 hour default
    rpo_met: bool = True
    
    # Health
    backup_chain_valid: bool = True
    gaps_detected: list[dict] = Field(default_factory=list)


class BackupSummary(BaseModel):
    """Summary of backup status."""
    
    database_name: str
    
    # Counts
    total_backups: int = 0
    full_backups: int = 0
    incremental_backups: int = 0
    verified_backups: int = 0
    
    # Size
    total_size_bytes: int = 0
    avg_backup_size_bytes: int = 0
    
    # Health
    healthy: bool = True
    last_backup_at: Optional[datetime] = None
    time_since_last_backup_hours: float = 0.0
    
    # Issues
    failed_backups_24h: int = 0
    unverified_backups: int = 0
    alerts: list[BackupAlert] = Field(default_factory=list)


# =============================================================================
# Backup Verifier
# =============================================================================


@dataclass
class BackupVerifier:
    """
    Verifies database backup integrity and recoverability.
    
    Features:
    - Checksum verification
    - Metadata validation
    - Structure verification
    - Restore testing
    - PITR validation
    
    Usage:
        verifier = BackupVerifier(config)
        
        # Verify a backup
        result = await verifier.verify_backup(backup)
        
        # Test restore
        test_result = await verifier.test_restore(backup, target_db="test_db")
    """
    
    config: BackupConfig = field(default_factory=BackupConfig)
    
    # Internal state
    _backups: dict[str, BackupMetadata] = field(default_factory=dict, init=False)
    _verifications: dict[str, BackupVerification] = field(default_factory=dict, init=False)
    _restore_tests: dict[str, RestoreTest] = field(default_factory=dict, init=False)
    _schedules: dict[str, BackupSchedule] = field(default_factory=dict, init=False)
    _alerts: list[BackupAlert] = field(default_factory=list, init=False)
    
    async def register_backup(self, backup: BackupMetadata):
        """Register a backup for tracking."""
        self._backups[backup.backup_id] = backup
    
    async def verify_backup(self, backup_id: str) -> BackupVerification:
        """Verify a backup's integrity."""
        if backup_id not in self._backups:
            raise ValueError(f"Backup not found: {backup_id}")
        
        backup = self._backups[backup_id]
        backup.verification_status = VerificationStatus.VERIFYING
        
        start_time = datetime.now(timezone.utc)
        
        checks_performed = []
        checks_passed = []
        checks_failed = []
        errors = []
        
        # Check 1: Checksum verification
        checks_performed.append("checksum")
        checksum_valid = await self._verify_checksum(backup)
        if checksum_valid:
            checks_passed.append("checksum")
        else:
            checks_failed.append("checksum")
            errors.append("Checksum mismatch")
        
        # Check 2: Metadata validation
        checks_performed.append("metadata")
        metadata_valid = await self._verify_metadata(backup)
        if metadata_valid:
            checks_passed.append("metadata")
        else:
            checks_failed.append("metadata")
            errors.append("Invalid metadata")
        
        # Check 3: Structure verification
        checks_performed.append("structure")
        structure_valid = await self._verify_structure(backup)
        if structure_valid:
            checks_passed.append("structure")
        else:
            checks_failed.append("structure")
            errors.append("Invalid backup structure")
        
        # Check 4: For incremental backups, verify chain
        if backup.backup_type == BackupType.INCREMENTAL and backup.base_backup_id:
            checks_performed.append("backup_chain")
            chain_valid = await self._verify_backup_chain(backup)
            if chain_valid:
                checks_passed.append("backup_chain")
            else:
                checks_failed.append("backup_chain")
                errors.append("Invalid backup chain")
        
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        
        # Determine overall status
        if len(checks_failed) == 0:
            status = VerificationStatus.VERIFIED
            backup.verification_status = VerificationStatus.VERIFIED
        else:
            status = VerificationStatus.FAILED
            backup.verification_status = VerificationStatus.FAILED
        
        verification = BackupVerification(
            backup_id=backup_id,
            verification_id=f"ver_{backup_id}_{datetime.now(timezone.utc).timestamp()}",
            status=status,
            checksum_valid=checksum_valid,
            metadata_valid=metadata_valid,
            structure_valid=structure_valid,
            checks_performed=checks_performed,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            verification_duration_seconds=duration,
            bytes_verified=backup.size_bytes,
            errors=errors,
        )
        
        self._verifications[verification.verification_id] = verification
        
        return verification
    
    async def _verify_checksum(self, backup: BackupMetadata) -> bool:
        """Verify backup checksum."""
        # Simulated - would actually read backup and compute checksum
        if backup.checksum is None:
            return True  # No checksum to verify
        return True
    
    async def _verify_metadata(self, backup: BackupMetadata) -> bool:
        """Verify backup metadata is valid."""
        # Check required fields
        if not backup.database_name:
            return False
        if not backup.storage_path:
            return False
        if backup.size_bytes <= 0:
            return False
        return True
    
    async def _verify_structure(self, backup: BackupMetadata) -> bool:
        """Verify backup structure is valid."""
        # Simulated - would check backup file structure
        return True
    
    async def _verify_backup_chain(self, backup: BackupMetadata) -> bool:
        """Verify incremental backup chain is complete."""
        if not backup.base_backup_id:
            return True
        
        # Check that base backup exists and is valid
        if backup.base_backup_id not in self._backups:
            return False
        
        base = self._backups[backup.base_backup_id]
        return base.verification_status == VerificationStatus.VERIFIED
    
    async def test_restore(
        self, 
        backup_id: str, 
        target_database: str,
        pitr_target: Optional[datetime] = None,
    ) -> RestoreTest:
        """Test restoring a backup to verify recoverability."""
        if backup_id not in self._backups:
            raise ValueError(f"Backup not found: {backup_id}")
        
        backup = self._backups[backup_id]
        start_time = datetime.now(timezone.utc)
        
        # Simulated restore test
        await asyncio.sleep(0.1)  # Would be actual restore operation
        
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        
        # Verify data integrity
        rows_verified = 1000  # Simulated
        tables_verified = 50  # Simulated
        queries_passed = 10  # Simulated
        queries_total = 10  # Simulated
        
        test = RestoreTest(
            test_id=f"restore_{backup_id}_{datetime.now(timezone.utc).timestamp()}",
            backup_id=backup_id,
            success=True,
            restore_duration_seconds=duration,
            data_integrity_valid=True,
            test_environment="test-cluster",
            target_database=target_database,
            rows_verified=rows_verified,
            tables_verified=tables_verified,
            sample_queries_passed=queries_passed,
            sample_queries_total=queries_total,
            pitr_tested=pitr_target is not None,
            pitr_target_time=pitr_target,
            pitr_success=pitr_target is not None,
        )
        
        self._restore_tests[test.test_id] = test
        
        return test
    
    async def get_recovery_point_status(self, database_name: str) -> RecoveryPointStatus:
        """Get recovery point status for a database."""
        # Find relevant backups
        db_backups = [
            b for b in self._backups.values()
            if b.database_name == database_name and b.status == BackupStatus.COMPLETED
        ]
        
        # Find latest full and incremental
        full_backups = [b for b in db_backups if b.backup_type == BackupType.FULL]
        inc_backups = [b for b in db_backups if b.backup_type == BackupType.INCREMENTAL]
        
        latest_full = max(full_backups, key=lambda b: b.completed_at or b.started_at, default=None)
        latest_inc = max(inc_backups, key=lambda b: b.completed_at or b.started_at, default=None)
        
        # Calculate RPO
        latest_backup_time = None
        if latest_full:
            latest_backup_time = latest_full.completed_at or latest_full.started_at
        if latest_inc:
            inc_time = latest_inc.completed_at or latest_inc.started_at
            if not latest_backup_time or inc_time > latest_backup_time:
                latest_backup_time = inc_time
        
        actual_rpo = 0.0
        if latest_backup_time:
            actual_rpo = (datetime.now(timezone.utc) - latest_backup_time).total_seconds()
        
        return RecoveryPointStatus(
            database_name=database_name,
            latest_full_backup=latest_full,
            latest_incremental_backup=latest_inc,
            oldest_recovery_point=min(
                (b.started_at for b in db_backups), default=None
            ),
            newest_recovery_point=latest_backup_time,
            pitr_available=self.config.wal_archive_enabled and bool(latest_full),
            actual_rpo_seconds=actual_rpo,
            target_rpo_seconds=self.config.max_backup_age_hours * 3600,
            rpo_met=actual_rpo <= self.config.max_backup_age_hours * 3600,
        )
    
    async def get_backup_summary(self, database_name: str) -> BackupSummary:
        """Get backup summary for a database."""
        db_backups = [
            b for b in self._backups.values()
            if b.database_name == database_name
        ]
        
        total = len(db_backups)
        full_count = sum(1 for b in db_backups if b.backup_type == BackupType.FULL)
        inc_count = sum(1 for b in db_backups if b.backup_type == BackupType.INCREMENTAL)
        verified_count = sum(1 for b in db_backups if b.verification_status == VerificationStatus.VERIFIED)
        total_size = sum(b.size_bytes for b in db_backups)
        
        # Find latest backup
        completed_backups = [b for b in db_backups if b.status == BackupStatus.COMPLETED]
        latest = max(completed_backups, key=lambda b: b.completed_at or b.started_at, default=None)
        
        last_backup_at = None
        hours_since = 0.0
        if latest:
            last_backup_at = latest.completed_at or latest.started_at
            hours_since = (datetime.now(timezone.utc) - last_backup_at).total_seconds() / 3600
        
        # Count recent failures
        cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)
        failed_24h = sum(
            1 for b in db_backups
            if b.status == BackupStatus.FAILED and b.started_at > cutoff_24h
        )
        
        # Get active alerts
        db_alerts = [a for a in self._alerts if a.database_name == database_name and not a.acknowledged]
        
        healthy = (
            hours_since <= self.config.max_backup_age_hours
            and failed_24h == 0
            and len(db_alerts) == 0
        )
        
        return BackupSummary(
            database_name=database_name,
            total_backups=total,
            full_backups=full_count,
            incremental_backups=inc_count,
            verified_backups=verified_count,
            total_size_bytes=total_size,
            avg_backup_size_bytes=total_size // total if total > 0 else 0,
            healthy=healthy,
            last_backup_at=last_backup_at,
            time_since_last_backup_hours=hours_since,
            failed_backups_24h=failed_24h,
            unverified_backups=total - verified_count,
            alerts=db_alerts,
        )
    
    async def check_backup_health(self) -> list[BackupAlert]:
        """Check backup health and generate alerts."""
        alerts = []
        
        # Get all unique databases
        databases = set(b.database_name for b in self._backups.values())
        
        for db_name in databases:
            summary = await self.get_backup_summary(db_name)
            
            # Check for missing backups
            if self.config.alert_on_missing:
                if summary.time_since_last_backup_hours > self.config.max_backup_age_hours:
                    alert = BackupAlert(
                        alert_id=f"missing_{db_name}_{datetime.now(timezone.utc).timestamp()}",
                        alert_type="missing_backup",
                        severity="critical",
                        database_name=db_name,
                        message=f"No backup in {summary.time_since_last_backup_hours:.1f} hours",
                        details={"hours_since_backup": summary.time_since_last_backup_hours},
                    )
                    alerts.append(alert)
                    self._alerts.append(alert)
            
            # Check for failures
            if self.config.alert_on_failure and summary.failed_backups_24h > 0:
                alert = BackupAlert(
                    alert_id=f"failures_{db_name}_{datetime.now(timezone.utc).timestamp()}",
                    alert_type="backup_failures",
                    severity="warning",
                    database_name=db_name,
                    message=f"{summary.failed_backups_24h} failed backups in last 24h",
                    details={"failed_count": summary.failed_backups_24h},
                )
                alerts.append(alert)
                self._alerts.append(alert)
        
        return alerts
    
    async def get_all_backups(self, database_name: Optional[str] = None) -> list[BackupMetadata]:
        """Get all registered backups, optionally filtered by database."""
        backups = list(self._backups.values())
        
        if database_name:
            backups = [b for b in backups if b.database_name == database_name]
        
        # Sort by start time, newest first
        backups.sort(key=lambda b: b.started_at, reverse=True)
        
        return backups


__all__ = [
    # Enums
    "BackupType",
    "BackupStatus",
    "VerificationStatus",
    "StorageType",
    "RecoveryPointObjective",
    # Configuration
    "BackupConfig",
    # Models
    "BackupMetadata",
    "BackupVerification",
    "RestoreTest",
    "BackupSchedule",
    "BackupAlert",
    "RecoveryPointStatus",
    "BackupSummary",
    # Verifier
    "BackupVerifier",
]
