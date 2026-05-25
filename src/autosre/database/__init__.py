"""
AutoSRE Database Reliability Module

Enterprise-grade database reliability monitoring providing:
- Database health checks and monitoring
- Query performance analysis and optimization
- Replication lag monitoring and failover readiness
- Backup verification and recovery testing
- Multi-database fleet management

Enables comprehensive database SRE capabilities for
incident detection, performance optimization, and disaster recovery.

Usage:
    from autosre.database import (
        # Health Checks
        DatabaseHealthChecker, DatabaseConfig, HealthCheckConfig,
        DatabaseHealthReport, HealthStatus, CheckType,
        # Performance
        QueryPerformanceAnalyzer, PerformanceConfig,
        QueryStatistics, SlowQueryReport, IndexRecommendation,
        # Replication
        ReplicationMonitor, ReplicationConfig,
        ReplicationTopology, ReplicaStatus, ReplicaHealth,
        # Backup
        BackupVerifier, BackupConfig,
        BackupMetadata, BackupVerification, RecoveryPointStatus,
    )
"""

from autosre.database.health import (
    # Enums
    DatabaseType,
    HealthStatus,
    CheckType,
    AlertLevel,
    # Configuration
    DatabaseConfig,
    HealthCheckConfig,
    # Results
    CheckResult,
    ConnectionPoolStatus,
    ResourceStatus,
    LongRunningQuery,
    DeadlockInfo,
    HealthAlert,
    DatabaseHealthReport,
    # Health Checker
    DatabaseHealthChecker,
    MultiDatabaseHealthMonitor,
)
from autosre.database.performance import (
    # Enums
    QueryType,
    PerformanceLevel,
    ScanType,
    JoinType,
    OptimizationType,
    # Configuration
    PerformanceConfig,
    # Models
    QueryFingerprint,
    QueryExecution,
    QueryPlan,
    QueryStatistics,
    SlowQueryReport,
    IndexRecommendation,
    PerformanceRegression,
    # Analyzer
    QueryPerformanceAnalyzer,
)
from autosre.database.replication import (
    # Enums
    ReplicationRole,
    ReplicationType,
    ReplicationState,
    ReplicaHealth,
    FailoverReadiness,
    # Configuration
    ReplicationConfig,
    # Models
    ReplicationNode,
    ReplicationLag,
    ReplicationSlot,
    ReplicaStatus,
    ReplicationTopology,
    ReplicationAlert,
    LagHistoryPoint,
    # Monitor
    ReplicationMonitor,
)
from autosre.database.backup import (
    # Enums
    BackupType,
    BackupStatus,
    VerificationStatus,
    StorageType,
    RecoveryPointObjective,
    # Configuration
    BackupConfig,
    # Models
    BackupMetadata,
    BackupVerification,
    RestoreTest,
    BackupSchedule,
    BackupAlert,
    RecoveryPointStatus,
    BackupSummary,
    # Verifier
    BackupVerifier,
)

__all__ = [
    # Health - Enums
    "DatabaseType",
    "HealthStatus",
    "CheckType",
    "AlertLevel",
    # Health - Configuration
    "DatabaseConfig",
    "HealthCheckConfig",
    # Health - Results
    "CheckResult",
    "ConnectionPoolStatus",
    "ResourceStatus",
    "LongRunningQuery",
    "DeadlockInfo",
    "HealthAlert",
    "DatabaseHealthReport",
    # Health - Checkers
    "DatabaseHealthChecker",
    "MultiDatabaseHealthMonitor",
    # Performance - Enums
    "QueryType",
    "PerformanceLevel",
    "ScanType",
    "JoinType",
    "OptimizationType",
    # Performance - Configuration
    "PerformanceConfig",
    # Performance - Models
    "QueryFingerprint",
    "QueryExecution",
    "QueryPlan",
    "QueryStatistics",
    "SlowQueryReport",
    "IndexRecommendation",
    "PerformanceRegression",
    # Performance - Analyzer
    "QueryPerformanceAnalyzer",
    # Replication - Enums
    "ReplicationRole",
    "ReplicationType",
    "ReplicationState",
    "ReplicaHealth",
    "FailoverReadiness",
    # Replication - Configuration
    "ReplicationConfig",
    # Replication - Models
    "ReplicationNode",
    "ReplicationLag",
    "ReplicationSlot",
    "ReplicaStatus",
    "ReplicationTopology",
    "ReplicationAlert",
    "LagHistoryPoint",
    # Replication - Monitor
    "ReplicationMonitor",
    # Backup - Enums
    "BackupType",
    "BackupStatus",
    "VerificationStatus",
    "StorageType",
    "RecoveryPointObjective",
    # Backup - Configuration
    "BackupConfig",
    # Backup - Models
    "BackupMetadata",
    "BackupVerification",
    "RestoreTest",
    "BackupSchedule",
    "BackupAlert",
    "RecoveryPointStatus",
    "BackupSummary",
    # Backup - Verifier
    "BackupVerifier",
]
