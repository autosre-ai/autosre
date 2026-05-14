"""Incident summary generation."""

from datetime import datetime
from typing import Any, Optional, List, Dict

from pydantic import BaseModel, Field, ConfigDict

from autosre.models.common import utc_now, generate_id


class IncidentSummary(BaseModel):
    """Generated incident summary."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    summary_id: str = Field(default_factory=generate_id)
    
    # Summary
    title: str = Field(default="")
    executive_summary: str = Field(default="")
    technical_summary: str = Field(default="")
    
    # Timeline
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    
    # Impact
    impact_summary: str = Field(default="")
    affected_services: list[str] = Field(default_factory=list)
    affected_users: str = Field(default="")
    
    # Root cause
    root_cause_summary: str = Field(default="")
    
    # Resolution
    resolution_summary: str = Field(default="")
    remediation_steps: list[str] = Field(default_factory=list)
    
    # Action items
    action_items: list[dict[str, str]] = Field(default_factory=list)
    
    # Metadata
    generated_at: datetime = Field(default_factory=utc_now)
    word_count: int = Field(default=0, ge=0)


class SummaryGenerator:
    """Generate incident summaries.
    
    Creates structured summaries from incident data:
    - Executive summary
    - Technical details
    - Timeline reconstruction
    - Impact assessment
    - Resolution steps
    
    Features:
    - Template-based generation
    - Key information extraction
    - Multiple output formats
    """
    
    def __init__(
        self,
        max_summary_length: int = 500,
        include_timeline: bool = True,
        include_metrics: bool = True,
    ):
        """Initialize the generator.
        
        Args:
            max_summary_length: Maximum summary length in words
            include_timeline: Include timeline in summary
            include_metrics: Include metrics in summary
        """
        self.max_summary_length = max_summary_length
        self.include_timeline = include_timeline
        self.include_metrics = include_metrics
    
    def generate(
        self,
        title: str,
        description: str,
        events: Optional[List[Dict[str, Any]]] = None,
        root_cause: str = "",
        resolution: str = "",
        affected_services: Optional[List[str]] = None,
        severity: str = "",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> IncidentSummary:
        """Generate incident summary.
        
        Args:
            title: Incident title
            description: Incident description
            events: Timeline events
            root_cause: Root cause analysis
            resolution: Resolution description
            affected_services: Affected services
            severity: Severity level
            start_time: Incident start time
            end_time: Incident end time
            metrics: Incident metrics
            
        Returns:
            Generated summary
        """
        events = events or []
        affected_services = affected_services or []
        metrics = metrics or {}
        
        # Generate executive summary
        executive_summary = self._generate_executive_summary(
            title, description, severity, affected_services, root_cause, resolution
        )
        
        # Generate technical summary
        technical_summary = self._generate_technical_summary(
            description, root_cause, resolution, metrics
        )
        
        # Generate timeline
        timeline = []
        if self.include_timeline:
            timeline = self._generate_timeline(events, start_time, end_time)
        
        # Generate impact summary
        impact_summary = self._generate_impact_summary(
            affected_services, severity, metrics
        )
        
        # Generate root cause summary
        root_cause_summary = self._summarize_root_cause(root_cause)
        
        # Generate resolution summary
        resolution_summary = self._summarize_resolution(resolution)
        
        # Extract remediation steps
        remediation_steps = self._extract_remediation_steps(resolution)
        
        # Generate action items
        action_items = self._generate_action_items(root_cause, resolution)
        
        # Calculate word count
        all_text = f"{executive_summary} {technical_summary} {impact_summary}"
        word_count = len(all_text.split())
        
        return IncidentSummary(
            title=self._generate_title(title, severity),
            executive_summary=executive_summary,
            technical_summary=technical_summary,
            timeline=timeline,
            impact_summary=impact_summary,
            affected_services=affected_services,
            root_cause_summary=root_cause_summary,
            resolution_summary=resolution_summary,
            remediation_steps=remediation_steps,
            action_items=action_items,
            word_count=word_count,
        )
    
    def _generate_title(self, title: str, severity: str) -> str:
        """Generate summary title.
        
        Args:
            title: Original title
            severity: Severity level
            
        Returns:
            Summary title
        """
        if severity:
            return f"[{severity.upper()}] {title}"
        return title
    
    def _generate_executive_summary(
        self,
        title: str,
        description: str,
        severity: str,
        services: List[str],
        root_cause: str,
        resolution: str,
    ) -> str:
        """Generate executive summary.
        
        Args:
            title: Incident title
            description: Description
            severity: Severity
            services: Affected services
            root_cause: Root cause
            resolution: Resolution
            
        Returns:
            Executive summary
        """
        parts = []
        
        # Opening
        if severity:
            parts.append(f"This was a {severity} incident affecting ")
        else:
            parts.append("An incident occurred affecting ")
        
        if services:
            parts.append(f"the following services: {', '.join(services[:3])}. ")
        else:
            parts.append("production systems. ")
        
        # Brief description
        if description:
            # Take first sentence
            first_sentence = description.split('.')[0]
            if len(first_sentence) > 100:
                first_sentence = first_sentence[:100] + "..."
            parts.append(f"{first_sentence}. ")
        
        # Root cause (brief)
        if root_cause:
            root_cause_brief = root_cause.split('.')[0]
            if len(root_cause_brief) > 100:
                root_cause_brief = root_cause_brief[:100] + "..."
            parts.append(f"Root cause: {root_cause_brief}. ")
        
        # Resolution (brief)
        if resolution:
            resolution_brief = resolution.split('.')[0]
            if len(resolution_brief) > 100:
                resolution_brief = resolution_brief[:100] + "..."
            parts.append(f"Resolution: {resolution_brief}.")
        
        return "".join(parts)
    
    def _generate_technical_summary(
        self,
        description: str,
        root_cause: str,
        resolution: str,
        metrics: Dict[str, Any],
    ) -> str:
        """Generate technical summary.
        
        Args:
            description: Description
            root_cause: Root cause
            resolution: Resolution
            metrics: Metrics
            
        Returns:
            Technical summary
        """
        parts = []
        
        if description:
            parts.append(f"Description: {description[:300]}")
        
        if root_cause:
            parts.append(f"\n\nRoot Cause Analysis: {root_cause}")
        
        if resolution:
            parts.append(f"\n\nResolution: {resolution}")
        
        if self.include_metrics and metrics:
            metrics_str = ", ".join([f"{k}: {v}" for k, v in list(metrics.items())[:5]])
            parts.append(f"\n\nMetrics: {metrics_str}")
        
        return "".join(parts)
    
    def _generate_timeline(
        self,
        events: List[Dict[str, Any]],
        start_time: Optional[datetime],
        end_time: Optional[datetime],
    ) -> List[Dict[str, Any]]:
        """Generate timeline from events.
        
        Args:
            events: Timeline events
            start_time: Start time
            end_time: End time
            
        Returns:
            Timeline list
        """
        timeline = []
        
        if start_time:
            timeline.append({
                "time": start_time.isoformat(),
                "event": "Incident started",
                "type": "start",
            })
        
        for event in events:
            timeline.append({
                "time": event.get("timestamp", ""),
                "event": event.get("description", ""),
                "type": event.get("type", "event"),
            })
        
        if end_time:
            timeline.append({
                "time": end_time.isoformat(),
                "event": "Incident resolved",
                "type": "end",
            })
        
        return timeline
    
    def _generate_impact_summary(
        self,
        services: List[str],
        severity: str,
        metrics: Dict[str, Any],
    ) -> str:
        """Generate impact summary.
        
        Args:
            services: Affected services
            severity: Severity
            metrics: Metrics
            
        Returns:
            Impact summary
        """
        parts = []
        
        if services:
            parts.append(f"Affected {len(services)} service(s): {', '.join(services)}.")
        
        if severity:
            impact_map = {
                "sev1": "Complete service outage",
                "sev2": "Major degradation",
                "sev3": "Partial impact",
                "sev4": "Minor impact",
                "sev5": "Minimal impact",
            }
            parts.append(f" {impact_map.get(severity.lower(), 'Unknown impact level')}.")
        
        if metrics:
            if "error_rate" in metrics:
                parts.append(f" Error rate: {metrics['error_rate']}%.")
            if "affected_users" in metrics:
                parts.append(f" Affected users: {metrics['affected_users']}.")
            if "duration_minutes" in metrics:
                parts.append(f" Duration: {metrics['duration_minutes']} minutes.")
        
        return "".join(parts) if parts else "Impact assessment not available."
    
    def _summarize_root_cause(self, root_cause: str) -> str:
        """Summarize root cause.
        
        Args:
            root_cause: Full root cause analysis
            
        Returns:
            Summarized root cause
        """
        if not root_cause:
            return "Root cause under investigation."
        
        # Take first 200 characters or first two sentences
        sentences = root_cause.split('.')
        if len(sentences) > 2:
            return f"{sentences[0]}. {sentences[1]}."
        return root_cause[:200] + ("..." if len(root_cause) > 200 else "")
    
    def _summarize_resolution(self, resolution: str) -> str:
        """Summarize resolution.
        
        Args:
            resolution: Full resolution
            
        Returns:
            Summarized resolution
        """
        if not resolution:
            return "Resolution pending."
        
        return resolution[:200] + ("..." if len(resolution) > 200 else "")
    
    def _extract_remediation_steps(self, resolution: str) -> List[str]:
        """Extract remediation steps from resolution.
        
        Args:
            resolution: Resolution text
            
        Returns:
            List of steps
        """
        if not resolution:
            return []
        
        steps = []
        
        # Look for numbered steps
        import re
        numbered = re.findall(r'\d+[.\)]\s*([^.]+\.)', resolution)
        steps.extend(numbered)
        
        # Look for bullet points
        bullets = re.findall(r'[-•]\s*([^.]+\.)', resolution)
        steps.extend(bullets)
        
        # If no structured steps, extract sentences
        if not steps:
            sentences = resolution.split('.')
            steps = [s.strip() + '.' for s in sentences if len(s.strip()) > 10][:5]
        
        return steps[:10]
    
    def _generate_action_items(
        self,
        root_cause: str,
        resolution: str,
    ) -> List[Dict[str, str]]:
        """Generate action items from incident.
        
        Args:
            root_cause: Root cause
            resolution: Resolution
            
        Returns:
            List of action items
        """
        action_items = []
        
        # Generic action items based on keywords
        text = f"{root_cause} {resolution}".lower()
        
        if "monitoring" in text or "alert" in text:
            action_items.append({
                "action": "Review and improve monitoring/alerting",
                "priority": "high",
                "owner": "SRE Team",
            })
        
        if "configuration" in text or "config" in text:
            action_items.append({
                "action": "Review configuration management practices",
                "priority": "medium",
                "owner": "Platform Team",
            })
        
        if "deployment" in text or "deploy" in text:
            action_items.append({
                "action": "Review deployment pipeline and rollback procedures",
                "priority": "high",
                "owner": "DevOps Team",
            })
        
        if "capacity" in text or "scale" in text:
            action_items.append({
                "action": "Review capacity planning",
                "priority": "medium",
                "owner": "SRE Team",
            })
        
        # Default action item
        if not action_items:
            action_items.append({
                "action": "Conduct post-incident review",
                "priority": "medium",
                "owner": "Team Lead",
            })
        
        return action_items
    
    def generate_slack_message(self, summary: IncidentSummary) -> str:
        """Generate Slack-formatted message.
        
        Args:
            summary: Incident summary
            
        Returns:
            Slack message
        """
        parts = [
            f"*{summary.title}*",
            "",
            f"*Summary:* {summary.executive_summary}",
            "",
            f"*Impact:* {summary.impact_summary}",
        ]
        
        if summary.affected_services:
            parts.append(f"*Services:* {', '.join(summary.affected_services)}")
        
        if summary.root_cause_summary:
            parts.append(f"*Root Cause:* {summary.root_cause_summary}")
        
        if summary.resolution_summary:
            parts.append(f"*Resolution:* {summary.resolution_summary}")
        
        if summary.action_items:
            parts.append("")
            parts.append("*Action Items:*")
            for item in summary.action_items:
                parts.append(f"• [{item['priority'].upper()}] {item['action']} - {item['owner']}")
        
        return "\n".join(parts)
