"""
Compliance Remediation Tracking

Track, assign, and manage remediation tasks for compliance findings.
Integrates with issue tracking systems like Jira and GitHub Issues.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
import json

from autosre.logging import get_logger
from autosre.compliance.audit import AuditFinding, AuditSeverity, ComplianceFramework

logger = get_logger(__name__)


class RemediationStatus(Enum):
    """Status of a remediation task."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_REVIEW = "pending_review"
    RESOLVED = "resolved"
    ACCEPTED_RISK = "accepted_risk"
    DEFERRED = "deferred"


class RemediationPriority(Enum):
    """Priority levels for remediation tasks."""

    CRITICAL = "critical"  # Fix immediately
    HIGH = "high"  # Fix within 7 days
    MEDIUM = "medium"  # Fix within 30 days
    LOW = "low"  # Fix within 90 days


@dataclass
class RemediationTask:
    """A remediation task for a compliance finding."""

    task_id: str
    finding: AuditFinding
    status: RemediationStatus
    priority: RemediationPriority
    assigned_to: str | None
    due_date: datetime | None
    created_at: datetime
    updated_at: datetime
    comments: list[dict[str, Any]] = field(default_factory=list)
    external_ticket_id: str | None = None
    external_ticket_url: str | None = None
    resolution_notes: str | None = None
    resolved_at: datetime | None = None
    resolved_by: str | None = None

    @property
    def is_overdue(self) -> bool:
        """Check if the task is overdue."""
        if self.status in [RemediationStatus.RESOLVED, RemediationStatus.ACCEPTED_RISK]:
            return False
        if self.due_date is None:
            return False
        return datetime.now(timezone.utc) > self.due_date

    @property
    def days_until_due(self) -> int | None:
        """Days until due date (negative if overdue)."""
        if self.due_date is None:
            return None
        delta = self.due_date - datetime.now(timezone.utc)
        return delta.days

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "finding_id": self.finding.id,
            "framework": self.finding.framework.value,
            "requirement_id": self.finding.requirement_id,
            "title": self.finding.title,
            "status": self.status.value,
            "priority": self.priority.value,
            "assigned_to": self.assigned_to,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "is_overdue": self.is_overdue,
            "days_until_due": self.days_until_due,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "external_ticket_id": self.external_ticket_id,
            "external_ticket_url": self.external_ticket_url,
        }


@dataclass
class RemediationProgress:
    """Progress tracking for remediation efforts."""

    total_tasks: int
    open: int
    in_progress: int
    pending_review: int
    resolved: int
    accepted_risk: int
    deferred: int
    overdue: int
    critical_open: int
    high_open: int

    @property
    def completion_rate(self) -> float:
        """Percentage of completed tasks."""
        if self.total_tasks == 0:
            return 100.0
        completed = self.resolved + self.accepted_risk
        return (completed / self.total_tasks) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_tasks": self.total_tasks,
            "open": self.open,
            "in_progress": self.in_progress,
            "pending_review": self.pending_review,
            "resolved": self.resolved,
            "accepted_risk": self.accepted_risk,
            "deferred": self.deferred,
            "overdue": self.overdue,
            "critical_open": self.critical_open,
            "high_open": self.high_open,
            "completion_rate": f"{self.completion_rate:.1f}%",
        }


class RemediationTracker:
    """
    Compliance Remediation Tracker.

    Tracks remediation tasks for compliance findings and integrates
    with external issue tracking systems.
    """

    # Default due dates based on severity
    SEVERITY_DUE_DAYS = {
        AuditSeverity.CRITICAL: 1,
        AuditSeverity.HIGH: 7,
        AuditSeverity.MEDIUM: 30,
        AuditSeverity.LOW: 90,
        AuditSeverity.INFORMATIONAL: None,
    }

    def __init__(self):
        self.tasks: dict[str, RemediationTask] = {}
        self.jira_config: dict[str, Any] | None = None
        self.github_config: dict[str, Any] | None = None

    async def create_task(
        self,
        finding: AuditFinding,
        assigned_to: str | None = None,
        due_date: datetime | None = None,
        priority: RemediationPriority | str | None = None,
    ) -> RemediationTask:
        """
        Create a remediation task for a finding.

        Args:
            finding: The compliance finding requiring remediation
            assigned_to: Email or username of assignee
            due_date: Due date (defaults based on severity)
            priority: Priority level (defaults based on severity)

        Returns:
            Created RemediationTask
        """
        import uuid

        task_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        # Determine priority
        if priority is None:
            priority = self._severity_to_priority(finding.severity)
        elif isinstance(priority, str):
            priority = RemediationPriority(priority)

        # Determine due date
        if due_date is None:
            due_days = self.SEVERITY_DUE_DAYS.get(finding.severity)
            if due_days is not None:
                due_date = now + timedelta(days=due_days)

        task = RemediationTask(
            task_id=task_id,
            finding=finding,
            status=RemediationStatus.OPEN,
            priority=priority,
            assigned_to=assigned_to,
            due_date=due_date,
            created_at=now,
            updated_at=now,
        )

        self.tasks[task_id] = task
        logger.info(
            f"Created remediation task {task_id} for finding {finding.id}"
        )

        return task

    async def create_tasks_from_findings(
        self,
        findings: list[AuditFinding],
        assigned_to: str | None = None,
        skip_passed: bool = True,
    ) -> list[RemediationTask]:
        """
        Create remediation tasks for multiple findings.

        Args:
            findings: List of compliance findings
            assigned_to: Default assignee for all tasks
            skip_passed: Skip findings that passed

        Returns:
            List of created tasks
        """
        tasks = []
        for finding in findings:
            if skip_passed and finding.passed:
                continue
            task = await self.create_task(finding, assigned_to=assigned_to)
            tasks.append(task)
        return tasks

    def _severity_to_priority(self, severity: AuditSeverity) -> RemediationPriority:
        """Map audit severity to remediation priority."""
        mapping = {
            AuditSeverity.CRITICAL: RemediationPriority.CRITICAL,
            AuditSeverity.HIGH: RemediationPriority.HIGH,
            AuditSeverity.MEDIUM: RemediationPriority.MEDIUM,
            AuditSeverity.LOW: RemediationPriority.LOW,
            AuditSeverity.INFORMATIONAL: RemediationPriority.LOW,
        }
        return mapping.get(severity, RemediationPriority.MEDIUM)

    async def update_status(
        self,
        task_id: str,
        status: RemediationStatus | str,
        comment: str | None = None,
        updated_by: str | None = None,
    ) -> RemediationTask:
        """
        Update the status of a remediation task.

        Args:
            task_id: Task identifier
            status: New status
            comment: Optional comment
            updated_by: Username of person making update

        Returns:
            Updated task
        """
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")

        if isinstance(status, str):
            status = RemediationStatus(status)

        task = self.tasks[task_id]
        task.status = status
        task.updated_at = datetime.now(timezone.utc)

        if comment:
            task.comments.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "author": updated_by,
                "text": comment,
            })

        if status == RemediationStatus.RESOLVED:
            task.resolved_at = datetime.now(timezone.utc)
            task.resolved_by = updated_by

        logger.info(f"Updated task {task_id} status to {status.value}")
        return task

    async def assign_task(
        self,
        task_id: str,
        assigned_to: str,
    ) -> RemediationTask:
        """Assign a task to a user."""
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")

        task = self.tasks[task_id]
        task.assigned_to = assigned_to
        task.updated_at = datetime.now(timezone.utc)

        logger.info(f"Assigned task {task_id} to {assigned_to}")
        return task

    async def add_comment(
        self,
        task_id: str,
        comment: str,
        author: str | None = None,
    ) -> RemediationTask:
        """Add a comment to a task."""
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")

        task = self.tasks[task_id]
        task.comments.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "author": author,
            "text": comment,
        })
        task.updated_at = datetime.now(timezone.utc)

        return task

    async def resolve_task(
        self,
        task_id: str,
        resolution_notes: str,
        resolved_by: str,
    ) -> RemediationTask:
        """Resolve a remediation task."""
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")

        task = self.tasks[task_id]
        task.status = RemediationStatus.RESOLVED
        task.resolution_notes = resolution_notes
        task.resolved_at = datetime.now(timezone.utc)
        task.resolved_by = resolved_by
        task.updated_at = datetime.now(timezone.utc)

        logger.info(f"Resolved task {task_id} by {resolved_by}")
        return task

    async def accept_risk(
        self,
        task_id: str,
        justification: str,
        accepted_by: str,
    ) -> RemediationTask:
        """Accept risk for a finding instead of remediating."""
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")

        task = self.tasks[task_id]
        task.status = RemediationStatus.ACCEPTED_RISK
        task.resolution_notes = f"Risk Accepted: {justification}"
        task.resolved_at = datetime.now(timezone.utc)
        task.resolved_by = accepted_by
        task.updated_at = datetime.now(timezone.utc)

        logger.warning(
            f"Risk accepted for task {task_id} by {accepted_by}: {justification}"
        )
        return task

    async def get_progress(self) -> RemediationProgress:
        """Get overall progress on remediation tasks."""
        tasks = list(self.tasks.values())

        return RemediationProgress(
            total_tasks=len(tasks),
            open=sum(1 for t in tasks if t.status == RemediationStatus.OPEN),
            in_progress=sum(
                1 for t in tasks if t.status == RemediationStatus.IN_PROGRESS
            ),
            pending_review=sum(
                1 for t in tasks if t.status == RemediationStatus.PENDING_REVIEW
            ),
            resolved=sum(
                1 for t in tasks if t.status == RemediationStatus.RESOLVED
            ),
            accepted_risk=sum(
                1 for t in tasks if t.status == RemediationStatus.ACCEPTED_RISK
            ),
            deferred=sum(
                1 for t in tasks if t.status == RemediationStatus.DEFERRED
            ),
            overdue=sum(1 for t in tasks if t.is_overdue),
            critical_open=sum(
                1
                for t in tasks
                if t.priority == RemediationPriority.CRITICAL
                and t.status
                not in [RemediationStatus.RESOLVED, RemediationStatus.ACCEPTED_RISK]
            ),
            high_open=sum(
                1
                for t in tasks
                if t.priority == RemediationPriority.HIGH
                and t.status
                not in [RemediationStatus.RESOLVED, RemediationStatus.ACCEPTED_RISK]
            ),
        )

    async def get_tasks_by_status(
        self, status: RemediationStatus | str
    ) -> list[RemediationTask]:
        """Get tasks filtered by status."""
        if isinstance(status, str):
            status = RemediationStatus(status)
        return [t for t in self.tasks.values() if t.status == status]

    async def get_tasks_by_framework(
        self, framework: ComplianceFramework | str
    ) -> list[RemediationTask]:
        """Get tasks filtered by framework."""
        if isinstance(framework, str):
            framework = ComplianceFramework(framework)
        return [t for t in self.tasks.values() if t.finding.framework == framework]

    async def get_overdue_tasks(self) -> list[RemediationTask]:
        """Get all overdue tasks."""
        return [t for t in self.tasks.values() if t.is_overdue]

    async def get_tasks_by_assignee(self, assignee: str) -> list[RemediationTask]:
        """Get tasks assigned to a specific user."""
        return [t for t in self.tasks.values() if t.assigned_to == assignee]

    # Jira Integration

    def configure_jira(
        self,
        url: str,
        project: str,
        api_token: str,
        username: str | None = None,
    ) -> None:
        """Configure Jira integration."""
        self.jira_config = {
            "url": url,
            "project": project,
            "api_token": api_token,
            "username": username,
        }
        logger.info(f"Jira integration configured for project {project}")

    async def sync_to_jira(
        self,
        findings: list[AuditFinding],
        issue_type: str = "Bug",
        labels: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Create Jira issues for compliance findings.

        Args:
            findings: List of findings to create issues for
            issue_type: Jira issue type
            labels: Additional labels to add

        Returns:
            List of created Jira issue references
        """
        if not self.jira_config:
            raise ValueError("Jira not configured. Call configure_jira() first.")

        # In production, this would use the Jira API
        created_issues = []
        default_labels = ["compliance", "autosre"]

        for finding in findings:
            if finding.passed:
                continue

            issue_data = {
                "project": self.jira_config["project"],
                "summary": f"[{finding.framework.value.upper()}] {finding.title}",
                "description": (
                    f"**Compliance Finding**\n\n"
                    f"**Framework:** {finding.framework.value}\n"
                    f"**Requirement:** {finding.requirement_id}\n"
                    f"**Severity:** {finding.severity.value}\n\n"
                    f"**Description:**\n{finding.description}\n\n"
                    f"**Remediation:**\n{finding.remediation or 'See compliance documentation'}"
                ),
                "issuetype": issue_type,
                "labels": default_labels + (labels or []),
                "priority": self._severity_to_jira_priority(finding.severity),
            }

            # Simulate Jira API call
            import uuid

            issue_key = f"{self.jira_config['project']}-{len(created_issues) + 1}"
            created_issues.append({
                "key": issue_key,
                "url": f"{self.jira_config['url']}/browse/{issue_key}",
                "finding_id": finding.id,
            })

            logger.info(f"Created Jira issue {issue_key} for finding {finding.id}")

        return created_issues

    def _severity_to_jira_priority(self, severity: AuditSeverity) -> str:
        """Map severity to Jira priority."""
        mapping = {
            AuditSeverity.CRITICAL: "Highest",
            AuditSeverity.HIGH: "High",
            AuditSeverity.MEDIUM: "Medium",
            AuditSeverity.LOW: "Low",
            AuditSeverity.INFORMATIONAL: "Lowest",
        }
        return mapping.get(severity, "Medium")

    # GitHub Issues Integration

    def configure_github(
        self,
        owner: str,
        repo: str,
        token: str,
    ) -> None:
        """Configure GitHub Issues integration."""
        self.github_config = {
            "owner": owner,
            "repo": repo,
            "token": token,
        }
        logger.info(f"GitHub integration configured for {owner}/{repo}")

    async def sync_to_github(
        self,
        findings: list[AuditFinding],
        labels: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Create GitHub issues for compliance findings.

        Args:
            findings: List of findings to create issues for
            labels: Additional labels to add

        Returns:
            List of created GitHub issue references
        """
        if not self.github_config:
            raise ValueError("GitHub not configured. Call configure_github() first.")

        created_issues = []
        default_labels = ["compliance"]

        for finding in findings:
            if finding.passed:
                continue

            severity_label = f"severity:{finding.severity.value}"
            framework_label = f"framework:{finding.framework.value}"

            issue_data = {
                "title": f"[{finding.framework.value.upper()}] {finding.title}",
                "body": (
                    f"## Compliance Finding\n\n"
                    f"- **Framework:** {finding.framework.value}\n"
                    f"- **Requirement:** {finding.requirement_id}\n"
                    f"- **Severity:** {finding.severity.value}\n\n"
                    f"### Description\n{finding.description}\n\n"
                    f"### Remediation\n{finding.remediation or 'See compliance documentation'}"
                ),
                "labels": default_labels + [severity_label, framework_label] + (labels or []),
            }

            # Simulate GitHub API call
            issue_number = len(created_issues) + 1
            created_issues.append({
                "number": issue_number,
                "url": f"https://github.com/{self.github_config['owner']}/{self.github_config['repo']}/issues/{issue_number}",
                "finding_id": finding.id,
            })

            logger.info(
                f"Created GitHub issue #{issue_number} for finding {finding.id}"
            )

        return created_issues

    # Export/Import

    def export_tasks(self) -> str:
        """Export all tasks as JSON."""
        return json.dumps(
            [t.to_dict() for t in self.tasks.values()],
            indent=2,
            default=str,
        )

    async def generate_remediation_report(self) -> dict[str, Any]:
        """Generate a remediation status report."""
        progress = await self.get_progress()
        overdue = await self.get_overdue_tasks()

        by_framework: dict[str, dict[str, int]] = {}
        for task in self.tasks.values():
            fw = task.finding.framework.value
            if fw not in by_framework:
                by_framework[fw] = {"total": 0, "open": 0, "resolved": 0}
            by_framework[fw]["total"] += 1
            if task.status == RemediationStatus.RESOLVED:
                by_framework[fw]["resolved"] += 1
            elif task.status in [RemediationStatus.OPEN, RemediationStatus.IN_PROGRESS]:
                by_framework[fw]["open"] += 1

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": progress.to_dict(),
            "by_framework": by_framework,
            "overdue_count": len(overdue),
            "overdue_tasks": [t.to_dict() for t in overdue[:10]],  # Top 10
            "recent_resolutions": [
                t.to_dict()
                for t in sorted(
                    [t for t in self.tasks.values() if t.resolved_at],
                    key=lambda x: x.resolved_at or datetime.min,
                    reverse=True,
                )[:5]
            ],
        }
