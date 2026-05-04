"""
Context Store - The foundation of AutoSRE

The context store maintains the current state of:
- Service topology (what exists, how things connect)
- Ownership (who owns what)
- Recent changes (what changed, when, who)
- Runbooks (how to fix things)
- Incidents (past and current)

This is the PRIMARY data source for agent reasoning.
Without good context, LLMs produce garbage recommendations.
"""

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)

from autosre.foundation.models import (
    Service,
    Ownership,
    ChangeEvent,
    Runbook,
    Alert,
    Incident,
    ServiceStatus,
    ChangeType,
    Severity,
)


class ContextStore:
    """
    SQLite-backed context store.
    
    Provides persistent storage for all context data that the agent
    needs to reason about incidents.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the context store.
        
        Args:
            db_path: Path to SQLite database. Defaults to ~/.autosre/context.db
        """
        if db_path is None:
            db_path = str(Path.home() / ".autosre" / "context.db")
        
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                -- Services table
                CREATE TABLE IF NOT EXISTS services (
                    name TEXT PRIMARY KEY,
                    namespace TEXT DEFAULT 'default',
                    cluster TEXT DEFAULT 'default',
                    dependencies TEXT DEFAULT '[]',
                    dependents TEXT DEFAULT '[]',
                    status TEXT DEFAULT 'unknown',
                    replicas INTEGER DEFAULT 1,
                    ready_replicas INTEGER DEFAULT 0,
                    labels TEXT DEFAULT '{}',
                    annotations TEXT DEFAULT '{}',
                    created_at TEXT,
                    last_updated TEXT
                );
                
                -- Ownership table
                CREATE TABLE IF NOT EXISTS ownership (
                    service_name TEXT PRIMARY KEY,
                    team TEXT NOT NULL,
                    slack_channel TEXT,
                    pagerduty_service_id TEXT,
                    oncall_email TEXT,
                    escalation_contacts TEXT DEFAULT '[]',
                    tier INTEGER DEFAULT 3,
                    slo_target REAL
                );
                
                -- Changes table
                CREATE TABLE IF NOT EXISTS changes (
                    id TEXT PRIMARY KEY,
                    change_type TEXT NOT NULL,
                    service_name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    author TEXT NOT NULL,
                    commit_sha TEXT,
                    pr_number INTEGER,
                    pr_url TEXT,
                    previous_version TEXT,
                    new_version TEXT,
                    timestamp TEXT NOT NULL,
                    successful INTEGER DEFAULT 1,
                    rolled_back INTEGER DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_changes_service ON changes(service_name);
                CREATE INDEX IF NOT EXISTS idx_changes_timestamp ON changes(timestamp);
                
                -- Runbooks table
                CREATE TABLE IF NOT EXISTS runbooks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    alert_names TEXT DEFAULT '[]',
                    services TEXT DEFAULT '[]',
                    keywords TEXT DEFAULT '[]',
                    description TEXT NOT NULL,
                    steps TEXT DEFAULT '[]',
                    automated INTEGER DEFAULT 0,
                    automation_script TEXT,
                    requires_approval INTEGER DEFAULT 1,
                    author TEXT,
                    last_updated TEXT,
                    success_rate REAL
                );
                
                -- Alerts table
                CREATE TABLE IF NOT EXISTS alerts (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    severity TEXT DEFAULT 'medium',
                    source TEXT DEFAULT 'prometheus',
                    service_name TEXT,
                    namespace TEXT,
                    cluster TEXT,
                    summary TEXT NOT NULL,
                    description TEXT,
                    labels TEXT DEFAULT '{}',
                    annotations TEXT DEFAULT '{}',
                    fired_at TEXT NOT NULL,
                    resolved_at TEXT,
                    metric_query TEXT,
                    metric_value REAL
                );
                CREATE INDEX IF NOT EXISTS idx_alerts_service ON alerts(service_name);
                CREATE INDEX IF NOT EXISTS idx_alerts_fired ON alerts(fired_at);
                
                -- Incidents table
                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    severity TEXT DEFAULT 'medium',
                    alerts TEXT DEFAULT '[]',
                    services TEXT DEFAULT '[]',
                    changes TEXT DEFAULT '[]',
                    root_cause TEXT,
                    remediation TEXT,
                    runbook_used TEXT,
                    started_at TEXT NOT NULL,
                    detected_at TEXT,
                    acknowledged_at TEXT,
                    resolved_at TEXT,
                    assigned_to TEXT,
                    team TEXT,
                    agent_analysis TEXT,
                    agent_confidence REAL,
                    human_override INTEGER DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_incidents_started ON incidents(started_at);
            """)
    
    # ==================== Services ====================
    
    def add_service(self, service: Service) -> None:
        """Add or update a service."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO services 
                (name, namespace, cluster, dependencies, dependents, status,
                 replicas, ready_replicas, labels, annotations, created_at, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                service.name,
                service.namespace,
                service.cluster,
                json.dumps(service.dependencies),
                json.dumps(service.dependents),
                service.status.value,
                service.replicas,
                service.ready_replicas,
                json.dumps(service.labels),
                json.dumps(service.annotations),
                service.created_at.isoformat() if service.created_at else None,
                utcnow().isoformat(),
            ))
    
    def get_service(self, name: str) -> Optional[Service]:
        """Get a service by name."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM services WHERE name = ?", (name,)
            ).fetchone()
            
            if row is None:
                return None
            
            return Service(
                name=row["name"],
                namespace=row["namespace"],
                cluster=row["cluster"],
                dependencies=json.loads(row["dependencies"]),
                dependents=json.loads(row["dependents"]),
                status=ServiceStatus(row["status"]),
                replicas=row["replicas"],
                ready_replicas=row["ready_replicas"],
                labels=json.loads(row["labels"]),
                annotations=json.loads(row["annotations"]),
                created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
                last_updated=datetime.fromisoformat(row["last_updated"]) if row["last_updated"] else None,
            )
    
    def list_services(self, namespace: Optional[str] = None, cluster: Optional[str] = None) -> list[Service]:
        """List all services, optionally filtered by namespace/cluster."""
        query = "SELECT * FROM services WHERE 1=1"
        params = []
        
        if namespace:
            query += " AND namespace = ?"
            params.append(namespace)
        if cluster:
            query += " AND cluster = ?"
            params.append(cluster)
        
        services = []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            for row in conn.execute(query, params):
                services.append(Service(
                    name=row["name"],
                    namespace=row["namespace"],
                    cluster=row["cluster"],
                    dependencies=json.loads(row["dependencies"]),
                    dependents=json.loads(row["dependents"]),
                    status=ServiceStatus(row["status"]),
                    replicas=row["replicas"],
                    ready_replicas=row["ready_replicas"],
                    labels=json.loads(row["labels"]),
                    annotations=json.loads(row["annotations"]),
                    created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
                    last_updated=datetime.fromisoformat(row["last_updated"]) if row["last_updated"] else None,
                ))
        
        return services
    
    # ==================== Ownership ====================
    
    def set_ownership(self, ownership: Ownership) -> None:
        """Set ownership for a service."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO ownership
                (service_name, team, slack_channel, pagerduty_service_id,
                 oncall_email, escalation_contacts, tier, slo_target)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ownership.service_name,
                ownership.team,
                ownership.slack_channel,
                ownership.pagerduty_service_id,
                ownership.oncall_email,
                json.dumps(ownership.escalation_contacts),
                ownership.tier,
                ownership.slo_target,
            ))
    
    def get_ownership(self, service_name: str) -> Optional[Ownership]:
        """Get ownership for a service."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM ownership WHERE service_name = ?", (service_name,)
            ).fetchone()
            
            if row is None:
                return None
            
            return Ownership(
                service_name=row["service_name"],
                team=row["team"],
                slack_channel=row["slack_channel"],
                pagerduty_service_id=row["pagerduty_service_id"],
                oncall_email=row["oncall_email"],
                escalation_contacts=json.loads(row["escalation_contacts"]),
                tier=row["tier"],
                slo_target=row["slo_target"],
            )
    
    # ==================== Changes ====================
    
    def add_change(self, change: ChangeEvent) -> None:
        """Record a change event."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO changes
                (id, change_type, service_name, description, author, commit_sha,
                 pr_number, pr_url, previous_version, new_version, timestamp,
                 successful, rolled_back)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                change.id,
                change.change_type.value,
                change.service_name,
                change.description,
                change.author,
                change.commit_sha,
                change.pr_number,
                change.pr_url,
                change.previous_version,
                change.new_version,
                change.timestamp.isoformat(),
                1 if change.successful else 0,
                1 if change.rolled_back else 0,
            ))
    
    def get_recent_changes(
        self,
        service_name: Optional[str] = None,
        hours: int = 24,
        limit: int = 50
    ) -> list[ChangeEvent]:
        """Get recent changes, optionally filtered by service."""
        cutoff = (utcnow() - timedelta(hours=hours)).isoformat()
        
        query = "SELECT * FROM changes WHERE timestamp > ?"
        params: list = [cutoff]
        
        if service_name:
            query += " AND service_name = ?"
            params.append(service_name)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        changes = []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            for row in conn.execute(query, params):
                changes.append(ChangeEvent(
                    id=row["id"],
                    change_type=ChangeType(row["change_type"]),
                    service_name=row["service_name"],
                    description=row["description"],
                    author=row["author"],
                    commit_sha=row["commit_sha"],
                    pr_number=row["pr_number"],
                    pr_url=row["pr_url"],
                    previous_version=row["previous_version"],
                    new_version=row["new_version"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    successful=bool(row["successful"]),
                    rolled_back=bool(row["rolled_back"]),
                ))
        
        return changes
    
    # ==================== Runbooks ====================
    
    def add_runbook(self, runbook: Runbook) -> None:
        """Add or update a runbook."""
        with sqlite3.connect(self.db_path) as conn:
            # Serialize steps properly (can be list of strings or RunbookStep objects)
            steps_serialized = []
            for step in runbook.steps:
                if isinstance(step, str):
                    steps_serialized.append(step)
                else:
                    # RunbookStep model - convert to dict
                    steps_serialized.append(step.model_dump())
            
            conn.execute("""
                INSERT OR REPLACE INTO runbooks
                (id, title, alert_names, services, keywords, description,
                 steps, automated, automation_script, requires_approval,
                 author, last_updated, success_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                runbook.id,
                runbook.title,
                json.dumps(runbook.alert_names),
                json.dumps(runbook.services),
                json.dumps(runbook.keywords),
                runbook.description,
                json.dumps(steps_serialized),
                1 if runbook.automated else 0,
                runbook.automation_script,
                1 if runbook.requires_approval else 0,
                runbook.author,
                utcnow().isoformat(),
                runbook.success_rate,
            ))
    
    def find_runbook(self, alert_name: Optional[str] = None, service_name: Optional[str] = None) -> list[Runbook]:
        """Find runbooks matching an alert or service."""
        runbooks = []
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            for row in conn.execute("SELECT * FROM runbooks"):
                rb = Runbook(
                    id=row["id"],
                    title=row["title"],
                    alert_names=json.loads(row["alert_names"]),
                    services=json.loads(row["services"]),
                    keywords=json.loads(row["keywords"]),
                    description=row["description"],
                    steps=json.loads(row["steps"]),
                    automated=bool(row["automated"]),
                    automation_script=row["automation_script"],
                    requires_approval=bool(row["requires_approval"]),
                    author=row["author"],
                    last_updated=datetime.fromisoformat(row["last_updated"]) if row["last_updated"] else None,
                    success_rate=row["success_rate"],
                )
                
                # Check if runbook matches
                if alert_name and alert_name in rb.alert_names:
                    runbooks.append(rb)
                elif service_name and service_name in rb.services:
                    runbooks.append(rb)
                elif not alert_name and not service_name:
                    runbooks.append(rb)
        
        return runbooks
    
    # ==================== Alerts ====================
    
    def add_alert(self, alert: Alert) -> None:
        """Record an alert."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO alerts
                (id, name, severity, source, service_name, namespace, cluster,
                 summary, description, labels, annotations, fired_at,
                 resolved_at, metric_query, metric_value)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.id,
                alert.name,
                alert.severity.value,
                alert.source,
                alert.service_name,
                alert.namespace,
                alert.cluster,
                alert.summary,
                alert.description,
                json.dumps(alert.labels),
                json.dumps(alert.annotations),
                alert.fired_at.isoformat(),
                alert.resolved_at.isoformat() if alert.resolved_at else None,
                alert.metric_query,
                alert.metric_value,
            ))
    
    def get_firing_alerts(self, service_name: Optional[str] = None) -> list[Alert]:
        """Get currently firing alerts."""
        query = "SELECT * FROM alerts WHERE resolved_at IS NULL"
        params = []
        
        if service_name:
            query += " AND service_name = ?"
            params.append(service_name)
        
        query += " ORDER BY fired_at DESC"
        
        alerts = []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            for row in conn.execute(query, params):
                alerts.append(Alert(
                    id=row["id"],
                    name=row["name"],
                    severity=Severity(row["severity"]),
                    source=row["source"],
                    service_name=row["service_name"],
                    namespace=row["namespace"],
                    cluster=row["cluster"],
                    summary=row["summary"],
                    description=row["description"],
                    labels=json.loads(row["labels"]),
                    annotations=json.loads(row["annotations"]),
                    fired_at=datetime.fromisoformat(row["fired_at"]),
                    resolved_at=datetime.fromisoformat(row["resolved_at"]) if row["resolved_at"] else None,
                    metric_query=row["metric_query"],
                    metric_value=row["metric_value"],
                ))
        
        return alerts
    
    # ==================== Incidents ====================
    
    def create_incident(self, incident: Incident) -> None:
        """Create a new incident."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO incidents
                (id, title, severity, alerts, services, changes, root_cause,
                 remediation, runbook_used, started_at, detected_at, acknowledged_at,
                 resolved_at, assigned_to, team, agent_analysis, agent_confidence,
                 human_override)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                incident.id,
                incident.title,
                incident.severity.value,
                json.dumps(incident.alerts),
                json.dumps(incident.services),
                json.dumps(incident.changes),
                incident.root_cause,
                incident.remediation,
                incident.runbook_used,
                incident.started_at.isoformat(),
                incident.detected_at.isoformat() if incident.detected_at else None,
                incident.acknowledged_at.isoformat() if incident.acknowledged_at else None,
                incident.resolved_at.isoformat() if incident.resolved_at else None,
                incident.assigned_to,
                incident.team,
                incident.agent_analysis,
                incident.agent_confidence,
                1 if incident.human_override else 0,
            ))
    
    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Get an incident by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM incidents WHERE id = ?", (incident_id,)
            ).fetchone()
            
            if row is None:
                return None
            
            return self._row_to_incident(row)
    
    def get_open_incidents(self) -> list[Incident]:
        """Get all open (unresolved) incidents."""
        incidents = []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            for row in conn.execute(
                "SELECT * FROM incidents WHERE resolved_at IS NULL ORDER BY started_at DESC"
            ):
                incidents.append(self._row_to_incident(row))
        return incidents
    
    def _row_to_incident(self, row: sqlite3.Row) -> Incident:
        """Convert a database row to an Incident model."""
        return Incident(
            id=row["id"],
            title=row["title"],
            severity=Severity(row["severity"]),
            alerts=json.loads(row["alerts"]),
            services=json.loads(row["services"]),
            changes=json.loads(row["changes"]),
            root_cause=row["root_cause"],
            remediation=row["remediation"],
            runbook_used=row["runbook_used"],
            started_at=datetime.fromisoformat(row["started_at"]),
            detected_at=datetime.fromisoformat(row["detected_at"]) if row["detected_at"] else None,
            acknowledged_at=datetime.fromisoformat(row["acknowledged_at"]) if row["acknowledged_at"] else None,
            resolved_at=datetime.fromisoformat(row["resolved_at"]) if row["resolved_at"] else None,
            assigned_to=row["assigned_to"],
            team=row["team"],
            agent_analysis=row["agent_analysis"],
            agent_confidence=row["agent_confidence"],
            human_override=bool(row["human_override"]),
        )
    
    # ==================== Context Summary ====================
    
    def get_context_summary(self) -> dict:
        """Get a summary of all context data for display."""
        with sqlite3.connect(self.db_path) as conn:
            services_count = conn.execute("SELECT COUNT(*) FROM services").fetchone()[0]
            ownership_count = conn.execute("SELECT COUNT(*) FROM ownership").fetchone()[0]
            changes_24h = conn.execute(
                "SELECT COUNT(*) FROM changes WHERE timestamp > ?",
                ((utcnow() - timedelta(hours=24)).isoformat(),)
            ).fetchone()[0]
            runbooks_count = conn.execute("SELECT COUNT(*) FROM runbooks").fetchone()[0]
            firing_alerts = conn.execute(
                "SELECT COUNT(*) FROM alerts WHERE resolved_at IS NULL"
            ).fetchone()[0]
            open_incidents = conn.execute(
                "SELECT COUNT(*) FROM incidents WHERE resolved_at IS NULL"
            ).fetchone()[0]
        
        return {
            "services": services_count,
            "ownership_mappings": ownership_count,
            "changes_last_24h": changes_24h,
            "runbooks": runbooks_count,
            "firing_alerts": firing_alerts,
            "open_incidents": open_incidents,
        }
