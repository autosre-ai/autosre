"""
Postmortem Generator for AutoSRE.

Auto-generates blameless postmortem drafts from incident investigations.
Key principle: Focus on SYSTEMS, not people. What failed in the process?
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Any, Optional
from enum import Enum


class ActionPriority(Enum):
    """Priority levels for action items."""
    P0 = "P0"  # Critical - must fix immediately
    P1 = "P1"  # High - fix this week
    P2 = "P2"  # Medium - fix this sprint
    P3 = "P3"  # Low - fix when able


@dataclass
class TimelineEvent:
    """A single event in the incident timeline."""
    
    timestamp: datetime
    description: str
    actor: str = "system"  # system, ai, on-call, automated
    event_type: str = "observation"  # detection, action, escalation, resolution
    evidence_url: Optional[str] = None
    
    def to_markdown(self) -> str:
        """Format as markdown."""
        ts = self.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
        return f"- **{ts}** [{self.actor}] {self.description}"


@dataclass
class ActionItem:
    """Post-incident action item with ownership and deadline."""
    
    title: str
    description: str
    owner: str
    priority: ActionPriority
    due_date: date
    category: str = "process"  # process, monitoring, tooling, documentation, training
    ticket_url: Optional[str] = None
    completed: bool = False
    
    def to_markdown(self) -> str:
        """Format as markdown."""
        status = "✅" if self.completed else "⬜"
        due = self.due_date.strftime("%Y-%m-%d")
        return (
            f"- {status} **[{self.priority.value}]** {self.title}\n"
            f"  - Owner: {self.owner}\n"
            f"  - Due: {due}\n"
            f"  - Category: {self.category}\n"
            f"  - {self.description}"
        )


@dataclass
class AIPerformanceReview:
    """Review of AI agent performance during incident."""
    
    total_actions: int = 0
    correct_actions: int = 0
    incorrect_actions: int = 0
    time_spent_deliberating_seconds: int = 0
    time_spent_acting_seconds: int = 0
    evidence_citations: int = 0
    hypotheses_tested: int = 0
    false_positives: int = 0
    
    observations: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    
    @property
    def accuracy_rate(self) -> float:
        """Calculate accuracy rate."""
        if self.total_actions == 0:
            return 0.0
        return self.correct_actions / self.total_actions
    
    @property
    def deliberation_ratio(self) -> float:
        """Ratio of deliberation to action time."""
        total = self.time_spent_deliberating_seconds + self.time_spent_acting_seconds
        if total == 0:
            return 0.0
        return self.time_spent_deliberating_seconds / total
    
    def to_markdown(self) -> str:
        """Format as markdown."""
        lines = [
            "### AI Performance Metrics",
            f"- Total actions: {self.total_actions}",
            f"- Correct actions: {self.correct_actions} ({self.accuracy_rate:.1%})",
            f"- Incorrect actions: {self.incorrect_actions}",
            f"- Time deliberating: {self.time_spent_deliberating_seconds}s",
            f"- Time acting: {self.time_spent_acting_seconds}s",
            f"- Deliberation ratio: {self.deliberation_ratio:.1%}",
            f"- Evidence citations: {self.evidence_citations}",
            f"- Hypotheses tested: {self.hypotheses_tested}",
            f"- False positives: {self.false_positives}",
            "",
            "### Observations",
        ]
        
        for obs in self.observations:
            lines.append(f"- {obs}")
        
        if self.improvements:
            lines.append("")
            lines.append("### Recommended Improvements")
            for imp in self.improvements:
                lines.append(f"- {imp}")
        
        return "\n".join(lines)


@dataclass
class PostmortemDraft:
    """Complete postmortem document draft."""
    
    title: str
    incident_id: str
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    author: str = "AutoSRE"
    status: str = "draft"  # draft, review, published
    
    # Content sections
    summary: str = ""
    user_impact: str = ""
    timeline: list[TimelineEvent] = field(default_factory=list)
    root_cause: str = ""
    system_failures: list[str] = field(default_factory=list)  # What SYSTEMS failed
    contributing_factors: list[str] = field(default_factory=list)
    
    # AI-specific
    ai_performance: Optional[AIPerformanceReview] = None
    
    # Actions and learnings
    action_items: list[ActionItem] = field(default_factory=list)
    lessons_learned: list[str] = field(default_factory=list)
    
    # Metrics
    time_to_detect_minutes: Optional[int] = None
    time_to_mitigate_minutes: Optional[int] = None
    time_to_resolve_minutes: Optional[int] = None
    
    def to_markdown(self) -> str:
        """Generate full postmortem markdown document."""
        lines = [
            f"# Incident Postmortem: {self.title}",
            "",
            f"**Incident ID:** {self.incident_id}",
            f"**Date:** {self.created_at.strftime('%Y-%m-%d')}",
            f"**Author:** {self.author}",
            f"**Status:** {self.status}",
            "",
            "---",
            "",
            "## Summary",
            "",
            self.summary or "_To be filled in_",
            "",
            "## User Impact",
            "",
            self.user_impact or "_To be filled in_",
            "",
            "## Incident Metrics",
            "",
            f"- Time to Detect (TTD): {self.time_to_detect_minutes or 'Unknown'} minutes",
            f"- Time to Mitigate (TTM): {self.time_to_mitigate_minutes or 'Unknown'} minutes",
            f"- Time to Resolve (TTR): {self.time_to_resolve_minutes or 'Unknown'} minutes",
            "",
            "## Timeline",
            "",
        ]
        
        if self.timeline:
            for event in sorted(self.timeline, key=lambda e: e.timestamp):
                lines.append(event.to_markdown())
        else:
            lines.append("_Timeline to be reconstructed_")
        
        lines.extend([
            "",
            "## Root Cause",
            "",
            self.root_cause or "_Root cause analysis pending_",
            "",
            "## What SYSTEMS Failed (Not People)",
            "",
            "> **Note:** This is a blameless postmortem. We focus on system and process",
            "> failures, not individual actions. Every person involved was doing their",
            "> best with the information available at the time.",
            "",
        ])
        
        if self.system_failures:
            for failure in self.system_failures:
                lines.append(f"- {failure}")
        else:
            lines.append("_System failures to be identified_")
        
        if self.contributing_factors:
            lines.extend([
                "",
                "### Contributing Factors",
                "",
            ])
            for factor in self.contributing_factors:
                lines.append(f"- {factor}")
        
        # AI Performance Review section
        if self.ai_performance:
            lines.extend([
                "",
                "## AI Performance Review",
                "",
                self.ai_performance.to_markdown(),
            ])
        
        lines.extend([
            "",
            "## Action Items",
            "",
        ])
        
        if self.action_items:
            # Group by priority
            for priority in ActionPriority:
                items = [a for a in self.action_items if a.priority == priority]
                if items:
                    lines.append(f"### {priority.value} Items")
                    lines.append("")
                    for item in items:
                        lines.append(item.to_markdown())
                    lines.append("")
        else:
            lines.append("_Action items to be defined_")
        
        lines.extend([
            "",
            "## Lessons Learned",
            "",
        ])
        
        if self.lessons_learned:
            for lesson in self.lessons_learned:
                lines.append(f"- {lesson}")
        else:
            lines.append("_Lessons to be discussed in postmortem review_")
        
        return "\n".join(lines)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "incident_id": self.incident_id,
            "created_at": self.created_at.isoformat(),
            "author": self.author,
            "status": self.status,
            "summary": self.summary,
            "user_impact": self.user_impact,
            "timeline": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "description": e.description,
                    "actor": e.actor,
                    "event_type": e.event_type,
                }
                for e in self.timeline
            ],
            "root_cause": self.root_cause,
            "system_failures": self.system_failures,
            "contributing_factors": self.contributing_factors,
            "action_items": [
                {
                    "title": a.title,
                    "description": a.description,
                    "owner": a.owner,
                    "priority": a.priority.value,
                    "due_date": a.due_date.isoformat(),
                    "category": a.category,
                    "completed": a.completed,
                }
                for a in self.action_items
            ],
            "lessons_learned": self.lessons_learned,
            "time_to_detect_minutes": self.time_to_detect_minutes,
            "time_to_mitigate_minutes": self.time_to_mitigate_minutes,
            "time_to_resolve_minutes": self.time_to_resolve_minutes,
        }


class PostmortemGenerator:
    """
    Generates blameless postmortem drafts from incident investigations.
    
    Key principles:
    - Focus on SYSTEMS, not people
    - Include AI performance review
    - Generate actionable items with ownership
    - Emphasize process improvements
    """
    
    def __init__(self, default_owner: str = "TBD"):
        """
        Initialize generator.
        
        Args:
            default_owner: Default owner for unassigned action items
        """
        self.default_owner = default_owner
    
    def generate_from_investigation(
        self,
        investigation: dict[str, Any],
        incident_id: str,
        title: Optional[str] = None,
    ) -> PostmortemDraft:
        """
        Generate postmortem draft from an investigation result.
        
        Args:
            investigation: Investigation data from AutoSRE
            incident_id: Unique incident identifier
            title: Optional title override
            
        Returns:
            PostmortemDraft ready for review
        """
        # Extract key information
        alert = investigation.get("alert", {})
        synthesis = investigation.get("synthesis", {})
        timeline_events = investigation.get("timeline", [])
        metrics = investigation.get("metrics", {})
        
        draft = PostmortemDraft(
            title=title or alert.get("name", f"Incident {incident_id}"),
            incident_id=incident_id,
        )
        
        # Build summary
        draft.summary = self._build_summary(alert, synthesis)
        draft.user_impact = alert.get("user_impact", synthesis.get("user_impact", ""))
        
        # Build timeline
        draft.timeline = self._build_timeline(timeline_events, investigation)
        
        # Root cause from synthesis
        draft.root_cause = synthesis.get("root_cause", "")
        
        # Identify system failures (blameless!)
        draft.system_failures = self._identify_system_failures(investigation)
        draft.contributing_factors = synthesis.get("contributing_factors", [])
        
        # AI performance review
        draft.ai_performance = self._review_ai_performance(investigation)
        
        # Generate action items
        draft.action_items = self._generate_action_items(draft)
        
        # Extract lessons
        draft.lessons_learned = synthesis.get("lessons_learned", [])
        
        # Metrics
        draft.time_to_detect_minutes = metrics.get("ttd_minutes")
        draft.time_to_mitigate_minutes = metrics.get("ttm_minutes")
        draft.time_to_resolve_minutes = metrics.get("ttr_minutes")
        
        return draft
    
    def _build_summary(
        self,
        alert: dict[str, Any],
        synthesis: dict[str, Any],
    ) -> str:
        """Build incident summary."""
        parts = []
        
        if alert.get("failure_mode"):
            parts.append(f"**What happened:** {alert['failure_mode']}")
        
        if synthesis.get("summary"):
            parts.append(synthesis["summary"])
        
        if alert.get("user_impact"):
            parts.append(f"**Impact:** {alert['user_impact']}")
        
        return "\n\n".join(parts) if parts else ""
    
    def _build_timeline(
        self,
        events: list[dict[str, Any]],
        investigation: dict[str, Any],
    ) -> list[TimelineEvent]:
        """Build incident timeline."""
        timeline = []
        
        # Add investigation events
        for event in events:
            timeline.append(TimelineEvent(
                timestamp=datetime.fromisoformat(event["timestamp"]) if isinstance(event.get("timestamp"), str) else event.get("timestamp", datetime.utcnow()),
                description=event.get("description", event.get("message", "")),
                actor=event.get("actor", "system"),
                event_type=event.get("type", "observation"),
            ))
        
        # Add alert detection
        alert = investigation.get("alert", {})
        if alert.get("fired_at"):
            timeline.append(TimelineEvent(
                timestamp=datetime.fromisoformat(alert["fired_at"]) if isinstance(alert["fired_at"], str) else alert["fired_at"],
                description=f"Alert fired: {alert.get('name', 'Unknown')}",
                actor="monitoring",
                event_type="detection",
            ))
        
        return sorted(timeline, key=lambda e: e.timestamp)
    
    def _identify_system_failures(
        self,
        investigation: dict[str, Any],
    ) -> list[str]:
        """
        Identify what SYSTEMS failed (not people).
        
        This is the core of blameless postmortems.
        """
        failures = []
        
        synthesis = investigation.get("synthesis", {})
        
        # Look for explicit system failures
        if synthesis.get("system_failures"):
            failures.extend(synthesis["system_failures"])
        
        # Infer from root cause
        root_cause = synthesis.get("root_cause", "")
        if root_cause:
            # Common system failure patterns
            patterns = [
                ("monitoring", "Monitoring system did not detect the issue early enough"),
                ("alerting", "Alerting rules did not trigger appropriately"),
                ("runbook", "Runbook was missing or incomplete"),
                ("automation", "Automated remediation did not exist or failed"),
                ("capacity", "Capacity planning did not anticipate this load"),
                ("testing", "Test coverage did not catch this failure mode"),
                ("deployment", "Deployment process allowed problematic change"),
                ("rollback", "Rollback mechanism was too slow or unavailable"),
            ]
            
            root_lower = root_cause.lower()
            for keyword, failure in patterns:
                if keyword in root_lower and failure not in failures:
                    failures.append(failure)
        
        # Check for missing requirements
        alert = investigation.get("alert", {})
        if not alert.get("runbook_url"):
            failures.append("No runbook was available for this alert")
        
        if not failures:
            failures.append("System failures to be identified during postmortem review")
        
        return failures
    
    def _review_ai_performance(
        self,
        investigation: dict[str, Any],
    ) -> AIPerformanceReview:
        """Review AI agent performance during the incident."""
        review = AIPerformanceReview()
        
        # Extract AI metrics from investigation
        ai_metrics = investigation.get("ai_metrics", {})
        
        review.total_actions = ai_metrics.get("total_actions", 0)
        review.correct_actions = ai_metrics.get("correct_actions", 0)
        review.incorrect_actions = ai_metrics.get("incorrect_actions", 0)
        review.time_spent_deliberating_seconds = ai_metrics.get("deliberation_time_seconds", 0)
        review.time_spent_acting_seconds = ai_metrics.get("action_time_seconds", 0)
        review.evidence_citations = ai_metrics.get("evidence_citations", 0)
        review.hypotheses_tested = ai_metrics.get("hypotheses_tested", 0)
        review.false_positives = ai_metrics.get("false_positives", 0)
        
        # Generate observations
        if review.accuracy_rate < 0.8:
            review.observations.append(
                f"Accuracy rate was {review.accuracy_rate:.1%}, below 80% target"
            )
        
        if review.deliberation_ratio < 0.2:
            review.observations.append(
                "AI may have acted too quickly without sufficient deliberation"
            )
            review.improvements.append(
                "Increase PAUSE checklist enforcement before taking actions"
            )
        
        if review.evidence_citations == 0 and review.total_actions > 0:
            review.observations.append(
                "No evidence citations found - recommendations may lack justification"
            )
            review.improvements.append(
                "Require evidence citation for all diagnostic conclusions"
            )
        
        if review.false_positives > 0:
            review.observations.append(
                f"AI had {review.false_positives} false positive diagnoses"
            )
            review.improvements.append(
                "Add more hypothesis testing before concluding root cause"
            )
        
        return review
    
    def _generate_action_items(
        self,
        draft: PostmortemDraft,
    ) -> list[ActionItem]:
        """Generate action items from postmortem content."""
        items = []
        today = date.today()
        
        # Action items from system failures
        for failure in draft.system_failures:
            priority = ActionPriority.P2
            category = "process"
            
            # Determine priority and category based on failure type
            if "monitoring" in failure.lower():
                category = "monitoring"
                priority = ActionPriority.P1
            elif "runbook" in failure.lower():
                category = "documentation"
                priority = ActionPriority.P1
            elif "automation" in failure.lower():
                category = "tooling"
            elif "testing" in failure.lower():
                category = "process"
            
            # Calculate due date based on priority
            due_days = {
                ActionPriority.P0: 3,
                ActionPriority.P1: 7,
                ActionPriority.P2: 14,
                ActionPriority.P3: 30,
            }
            
            from datetime import timedelta
            due_date = today + timedelta(days=due_days[priority])
            
            items.append(ActionItem(
                title=f"Address: {failure[:50]}...",
                description=f"Implement fix for system failure: {failure}",
                owner=self.default_owner,
                priority=priority,
                due_date=due_date,
                category=category,
            ))
        
        # Action items from AI performance
        if draft.ai_performance and draft.ai_performance.improvements:
            for improvement in draft.ai_performance.improvements:
                items.append(ActionItem(
                    title=f"AI Improvement: {improvement[:50]}...",
                    description=improvement,
                    owner="AI/SRE Team",
                    priority=ActionPriority.P2,
                    due_date=today + timedelta(days=14),
                    category="tooling",
                ))
        
        return items
    
    def add_action_item(
        self,
        draft: PostmortemDraft,
        title: str,
        description: str,
        owner: str,
        priority: ActionPriority,
        due_date: date,
        category: str = "process",
    ) -> PostmortemDraft:
        """Add an action item to a postmortem draft."""
        draft.action_items.append(ActionItem(
            title=title,
            description=description,
            owner=owner,
            priority=priority,
            due_date=due_date,
            category=category,
        ))
        return draft
    
    def add_lesson_learned(
        self,
        draft: PostmortemDraft,
        lesson: str,
    ) -> PostmortemDraft:
        """Add a lesson learned to a postmortem draft."""
        draft.lessons_learned.append(lesson)
        return draft
