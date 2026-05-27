"""
Message Templates

Provides templating for incident communications with pre-built
templates for common scenarios.
"""

from datetime import datetime, timezone
from typing import Any, Optional
import re
import uuid

from pydantic import BaseModel, Field


class TemplateContext(BaseModel):
    """Context data for template rendering."""
    
    # Incident details
    incident_id: str = Field(..., description="Incident identifier")
    incident_title: str = Field(..., description="Incident title")
    severity: str = Field(default="unknown", description="Incident severity")
    status: str = Field(default="investigating", description="Current status")
    
    # Timing
    started_at: Optional[datetime] = Field(None, description="Incident start time")
    detected_at: Optional[datetime] = Field(None, description="Detection time")
    resolved_at: Optional[datetime] = Field(None, description="Resolution time")
    
    # Impact
    affected_services: list[str] = Field(
        default_factory=list,
        description="Affected services"
    )
    impact_description: Optional[str] = Field(None, description="Impact description")
    affected_users: Optional[str] = Field(None, description="Affected user count/percentage")
    affected_regions: list[str] = Field(
        default_factory=list,
        description="Affected regions"
    )
    
    # Root cause & resolution
    root_cause: Optional[str] = Field(None, description="Root cause")
    mitigation_steps: list[str] = Field(
        default_factory=list,
        description="Mitigation steps taken"
    )
    resolution_summary: Optional[str] = Field(None, description="Resolution summary")
    
    # Investigation
    hypotheses: list[str] = Field(
        default_factory=list,
        description="Investigation hypotheses"
    )
    findings: list[str] = Field(
        default_factory=list,
        description="Investigation findings"
    )
    timeline_events: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Timeline events"
    )
    
    # Team
    incident_commander: Optional[str] = Field(None, description="Incident commander")
    communications_lead: Optional[str] = Field(None, description="Communications lead")
    technical_lead: Optional[str] = Field(None, description="Technical lead")
    
    # Links
    war_room_link: Optional[str] = Field(None, description="War room link")
    statuspage_link: Optional[str] = Field(None, description="Status page link")
    runbook_link: Optional[str] = Field(None, description="Runbook link")
    dashboard_link: Optional[str] = Field(None, description="Dashboard link")
    
    # Next steps
    next_steps: list[str] = Field(
        default_factory=list,
        description="Next steps"
    )
    next_update_eta: Optional[str] = Field(None, description="ETA for next update")
    postmortem_date: Optional[datetime] = Field(None, description="Postmortem date")
    
    # Custom fields
    custom: dict[str, Any] = Field(
        default_factory=dict,
        description="Custom template fields"
    )
    
    def get_duration(self) -> Optional[str]:
        """Get incident duration as string."""
        if not self.started_at:
            return None
        
        end = self.resolved_at or datetime.now(timezone.utc)
        duration = end - self.started_at
        
        hours = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
    
    def format_time(self, dt: Optional[datetime]) -> str:
        """Format datetime for display."""
        if not dt:
            return "N/A"
        return dt.strftime("%Y-%m-%d %H:%M UTC")


class MessageTemplate(BaseModel):
    """A message template for incident communications."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Template ID")
    name: str = Field(..., description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    category: str = Field(default="general", description="Template category")
    
    # Template content
    subject: str = Field(..., description="Message subject template")
    body: str = Field(..., description="Message body template")
    
    # Format options
    format: str = Field(default="markdown", description="Output format (markdown, plain, html)")
    
    # Placeholders
    required_fields: list[str] = Field(
        default_factory=list,
        description="Required context fields"
    )
    optional_fields: list[str] = Field(
        default_factory=list,
        description="Optional context fields"
    )
    
    # Usage metadata
    channels: list[str] = Field(
        default_factory=lambda: ["slack", "email", "statuspage"],
        description="Supported channels"
    )
    severity_levels: list[str] = Field(
        default_factory=lambda: ["critical", "high", "warning", "low"],
        description="Applicable severity levels"
    )


class TemplateRegistry:
    """Registry for message templates."""
    
    def __init__(self) -> None:
        """Initialize the template registry."""
        self._templates: dict[str, MessageTemplate] = {}
    
    def register(self, template: MessageTemplate) -> None:
        """Register a template.
        
        Args:
            template: Template to register
        """
        self._templates[template.id] = template
        self._templates[template.name] = template
    
    def get(self, template_id_or_name: str) -> Optional[MessageTemplate]:
        """Get a template by ID or name.
        
        Args:
            template_id_or_name: Template ID or name
            
        Returns:
            Template if found
        """
        return self._templates.get(template_id_or_name)
    
    def list_templates(self, category: Optional[str] = None) -> list[MessageTemplate]:
        """List all templates.
        
        Args:
            category: Filter by category
            
        Returns:
            List of templates
        """
        templates = list(set(self._templates.values()))
        if category:
            templates = [t for t in templates if t.category == category]
        return templates
    
    def list_categories(self) -> list[str]:
        """List all template categories.
        
        Returns:
            List of unique categories
        """
        return list(set(t.category for t in self._templates.values()))


class TemplateEngine:
    """Engine for rendering message templates.
    
    Supports variable substitution and conditional sections.
    
    Example:
        engine = TemplateEngine()
        
        context = TemplateContext(
            incident_id="INC-123",
            incident_title="Payment API Latency",
            severity="high",
            affected_services=["payment-api"],
        )
        
        result = engine.render(INITIAL_NOTIFICATION_TEMPLATE, context)
        print(result.subject)
        print(result.body)
    """
    
    def __init__(self, registry: Optional[TemplateRegistry] = None) -> None:
        """Initialize the template engine.
        
        Args:
            registry: Template registry
        """
        self.registry = registry or TemplateRegistry()
        self._load_builtin_templates()
    
    def _load_builtin_templates(self) -> None:
        """Load built-in templates into registry."""
        for template in get_builtin_templates():
            self.registry.register(template)
    
    def render(
        self,
        template: MessageTemplate,
        context: TemplateContext,
    ) -> "RenderedMessage":
        """Render a template with context.
        
        Args:
            template: Template to render
            context: Context data
            
        Returns:
            Rendered message
        """
        # Convert context to dict
        ctx = context.model_dump()
        ctx["duration"] = context.get_duration()
        ctx["started_at_formatted"] = context.format_time(context.started_at)
        ctx["resolved_at_formatted"] = context.format_time(context.resolved_at)
        
        # Render subject and body
        subject = self._render_string(template.subject, ctx)
        body = self._render_string(template.body, ctx)
        
        return RenderedMessage(
            template_id=template.id,
            subject=subject,
            body=body,
            format=template.format,
        )
    
    def render_by_name(
        self,
        template_name: str,
        context: TemplateContext,
    ) -> "RenderedMessage":
        """Render a template by name.
        
        Args:
            template_name: Template name
            context: Context data
            
        Returns:
            Rendered message
        """
        template = self.registry.get(template_name)
        if not template:
            raise ValueError(f"Template not found: {template_name}")
        return self.render(template, context)
    
    def _render_string(self, template_str: str, context: dict[str, Any]) -> str:
        """Render a template string with context.
        
        Supports:
        - Simple substitution: {{variable}}
        - Default values: {{variable|default_value}}
        - Conditional sections: {{#if condition}}...{{/if}}
        - List iteration: {{#each items}}...{{/each}}
        
        Args:
            template_str: Template string
            context: Context dictionary
            
        Returns:
            Rendered string
        """
        result = template_str
        
        # Handle conditional sections {{#if condition}}...{{/if}}
        if_pattern = r'\{\{#if\s+(\w+)\}\}(.*?)\{\{/if\}\}'
        while re.search(if_pattern, result, re.DOTALL):
            def replace_if(match):
                var_name = match.group(1)
                content = match.group(2)
                value = context.get(var_name)
                if value:
                    return content
                return ""
            result = re.sub(if_pattern, replace_if, result, flags=re.DOTALL)
        
        # Handle else sections {{#if condition}}...{{else}}...{{/if}}
        if_else_pattern = r'\{\{#if\s+(\w+)\}\}(.*?)\{\{else\}\}(.*?)\{\{/if\}\}'
        while re.search(if_else_pattern, result, re.DOTALL):
            def replace_if_else(match):
                var_name = match.group(1)
                if_content = match.group(2)
                else_content = match.group(3)
                value = context.get(var_name)
                if value:
                    return if_content
                return else_content
            result = re.sub(if_else_pattern, replace_if_else, result, flags=re.DOTALL)
        
        # Handle list iteration {{#each items}}...{{/each}}
        each_pattern = r'\{\{#each\s+(\w+)\}\}(.*?)\{\{/each\}\}'
        while re.search(each_pattern, result, re.DOTALL):
            def replace_each(match):
                list_name = match.group(1)
                item_template = match.group(2)
                items = context.get(list_name, [])
                if not items:
                    return ""
                rendered_items = []
                for item in items:
                    if isinstance(item, dict):
                        item_str = self._render_string(item_template, item)
                    else:
                        item_str = item_template.replace("{{this}}", str(item))
                    rendered_items.append(item_str)
                return "".join(rendered_items)
            result = re.sub(each_pattern, replace_each, result, flags=re.DOTALL)
        
        # Handle simple substitution with defaults {{variable|default}}
        default_pattern = r'\{\{(\w+)\|([^}]*)\}\}'
        def replace_default(match):
            var_name = match.group(1)
            default_val = match.group(2)
            value = context.get(var_name)
            if value is None or value == "" or (isinstance(value, list) and len(value) == 0):
                return default_val
            if isinstance(value, list):
                return ", ".join(str(v) for v in value)
            return str(value)
        result = re.sub(default_pattern, replace_default, result)
        
        # Handle simple substitution {{variable}}
        simple_pattern = r'\{\{(\w+)\}\}'
        def replace_simple(match):
            var_name = match.group(1)
            value = context.get(var_name, "")
            if isinstance(value, list):
                return ", ".join(str(v) for v in value)
            return str(value) if value else ""
        result = re.sub(simple_pattern, replace_simple, result)
        
        return result.strip()


class RenderedMessage(BaseModel):
    """A rendered message from a template."""
    
    template_id: str = Field(..., description="Source template ID")
    subject: str = Field(..., description="Rendered subject")
    body: str = Field(..., description="Rendered body")
    format: str = Field(default="markdown", description="Message format")


# ============================================================================
# Built-in Templates
# ============================================================================

INITIAL_NOTIFICATION_TEMPLATE = MessageTemplate(
    name="initial_notification",
    description="Initial incident notification to stakeholders",
    category="incident",
    subject="[{{severity|INCIDENT}}] {{incident_title}} - {{incident_id}}",
    body="""# Incident Notification

**Incident ID:** {{incident_id}}
**Severity:** {{severity}}
**Status:** {{status|Investigating}}

## Summary
{{impact_description|We are currently investigating an issue.}}

## Affected Services
{{#if affected_services}}
{{#each affected_services}}- {{this}}
{{/each}}{{else}}
Determining affected services...{{/if}}

{{#if affected_users}}
## User Impact
{{affected_users}}
{{/if}}

{{#if affected_regions}}
## Affected Regions
{{#each affected_regions}}- {{this}}
{{/each}}{{/if}}

## Current Actions
We are actively investigating this issue. Our team has been engaged and is working to determine the root cause.

{{#if incident_commander}}
**Incident Commander:** {{incident_commander}}
{{/if}}

{{#if next_update_eta}}
**Next Update:** {{next_update_eta}}
{{/if}}

---
{{#if war_room_link}}[Join War Room]({{war_room_link}}) | {{/if}}{{#if statuspage_link}}[Status Page]({{statuspage_link}}){{/if}}
""",
    required_fields=["incident_id", "incident_title"],
    optional_fields=["severity", "status", "impact_description", "affected_services", "affected_users", "affected_regions", "incident_commander", "next_update_eta", "war_room_link", "statuspage_link"],
    channels=["slack", "email"],
    severity_levels=["critical", "high", "warning"],
)

UPDATE_TEMPLATE = MessageTemplate(
    name="status_update",
    description="Status update during incident",
    category="incident",
    subject="[UPDATE] {{incident_title}} - {{incident_id}} - {{status}}",
    body="""# Incident Update

**Incident ID:** {{incident_id}}
**Severity:** {{severity}}
**Status:** {{status}}
**Duration:** {{duration|Ongoing}}

## Update Summary
{{impact_description}}

{{#if root_cause}}
## Root Cause Identified
{{root_cause}}
{{/if}}

{{#if mitigation_steps}}
## Mitigation Steps
{{#each mitigation_steps}}- {{this}}
{{/each}}{{/if}}

{{#if findings}}
## Recent Findings
{{#each findings}}- {{this}}
{{/each}}{{/if}}

{{#if next_steps}}
## Next Steps
{{#each next_steps}}- {{this}}
{{/each}}{{/if}}

{{#if next_update_eta}}
**Next Update:** {{next_update_eta}}
{{/if}}

---
{{#if war_room_link}}[Join War Room]({{war_room_link}}) | {{/if}}{{#if statuspage_link}}[Status Page]({{statuspage_link}}){{/if}}
""",
    required_fields=["incident_id", "incident_title", "status"],
    optional_fields=["severity", "impact_description", "root_cause", "mitigation_steps", "findings", "next_steps", "next_update_eta", "duration", "war_room_link", "statuspage_link"],
    channels=["slack", "email", "statuspage"],
)

RESOLUTION_TEMPLATE = MessageTemplate(
    name="resolution",
    description="Incident resolution notification",
    category="incident",
    subject="[RESOLVED] {{incident_title}} - {{incident_id}}",
    body="""# Incident Resolved ✅

**Incident ID:** {{incident_id}}
**Status:** Resolved
**Duration:** {{duration}}

## Summary
{{resolution_summary|The incident has been resolved.}}

## Root Cause
{{root_cause|Root cause analysis in progress.}}

{{#if mitigation_steps}}
## Resolution Steps
{{#each mitigation_steps}}- {{this}}
{{/each}}{{/if}}

## Impact Summary
{{impact_description|See postmortem for full impact assessment.}}

{{#if affected_services}}
**Affected Services:** {{affected_services}}
{{/if}}

{{#if affected_users}}
**User Impact:** {{affected_users}}
{{/if}}

## Next Steps
- Full postmortem will be conducted{{#if postmortem_date}} on {{postmortem_date}}{{/if}}
- Action items will be tracked and addressed
{{#if next_steps}}{{#each next_steps}}- {{this}}
{{/each}}{{/if}}

---
Thank you for your patience. We apologize for any inconvenience caused.

{{#if statuspage_link}}[View Status Page]({{statuspage_link}}){{/if}}
""",
    required_fields=["incident_id", "incident_title"],
    optional_fields=["duration", "resolution_summary", "root_cause", "mitigation_steps", "impact_description", "affected_services", "affected_users", "postmortem_date", "next_steps", "statuspage_link"],
    channels=["slack", "email", "statuspage"],
)

POSTMORTEM_SUMMARY_TEMPLATE = MessageTemplate(
    name="postmortem_summary",
    description="Brief postmortem summary for stakeholders",
    category="postmortem",
    subject="[POSTMORTEM] {{incident_title}} - {{incident_id}}",
    body="""# Postmortem Summary

**Incident ID:** {{incident_id}}
**Date:** {{started_at_formatted}}
**Duration:** {{duration}}
**Severity:** {{severity}}

## Executive Summary
{{resolution_summary}}

## Impact
{{impact_description}}

{{#if affected_services}}
**Affected Services:** {{affected_services}}
{{/if}}

{{#if affected_users}}
**User Impact:** {{affected_users}}
{{/if}}

## Root Cause
{{root_cause}}

## Timeline Highlights
{{#each timeline_events}}- **{{time}}**: {{description}}
{{/each}}

## Key Learnings
{{#each findings}}- {{this}}
{{/each}}

## Action Items
{{#each next_steps}}- {{this}}
{{/each}}

---
Full postmortem document available {{#if runbook_link}}[here]({{runbook_link}}){{else}}upon request{{/if}}.
""",
    required_fields=["incident_id", "incident_title", "root_cause"],
    optional_fields=["started_at_formatted", "duration", "severity", "resolution_summary", "impact_description", "affected_services", "affected_users", "timeline_events", "findings", "next_steps", "runbook_link"],
    channels=["email"],
)

EXECUTIVE_BRIEF_TEMPLATE = MessageTemplate(
    name="executive_brief",
    description="Executive-level incident brief",
    category="executive",
    subject="[EXEC BRIEF] {{severity}} Incident: {{incident_title}}",
    body="""# Executive Incident Brief

**Incident:** {{incident_title}}
**Severity:** {{severity}}
**Status:** {{status}}
**Duration:** {{duration|Ongoing}}

## Business Impact
{{impact_description}}

{{#if affected_users}}
**Affected Users:** {{affected_users}}
{{/if}}

{{#if affected_regions}}
**Affected Regions:** {{affected_regions}}
{{/if}}

## Current Status
{{resolution_summary|Investigation in progress.}}

{{#if root_cause}}
## Root Cause
{{root_cause}}
{{/if}}

## Response Team
{{#if incident_commander}}- **Incident Commander:** {{incident_commander}}{{/if}}
{{#if technical_lead}}- **Technical Lead:** {{technical_lead}}{{/if}}
{{#if communications_lead}}- **Communications Lead:** {{communications_lead}}{{/if}}

{{#if next_update_eta}}
## Next Update
{{next_update_eta}}
{{/if}}

---
{{#if war_room_link}}[Join War Room]({{war_room_link}}){{/if}}
""",
    required_fields=["incident_id", "incident_title", "severity"],
    optional_fields=["status", "duration", "impact_description", "affected_users", "affected_regions", "resolution_summary", "root_cause", "incident_commander", "technical_lead", "communications_lead", "next_update_eta", "war_room_link"],
    channels=["email", "slack"],
    severity_levels=["critical", "high"],
)

STATUSPAGE_UPDATE_TEMPLATE = MessageTemplate(
    name="statuspage_update",
    description="Statuspage.io incident update",
    category="statuspage",
    subject="{{incident_title}}",
    body="""{{status}} - {{impact_description}}

{{#if root_cause}}Root cause: {{root_cause}}{{/if}}

{{#if mitigation_steps}}Steps taken:
{{#each mitigation_steps}}- {{this}}
{{/each}}{{/if}}

{{#if next_update_eta}}Next update in {{next_update_eta}}.{{/if}}""",
    format="plain",
    required_fields=["incident_title", "status", "impact_description"],
    optional_fields=["root_cause", "mitigation_steps", "next_update_eta"],
    channels=["statuspage"],
)

SLACK_ALERT_TEMPLATE = MessageTemplate(
    name="slack_alert",
    description="Slack incident alert message",
    category="slack",
    subject=":rotating_light: {{severity}} Incident: {{incident_title}}",
    body=""":rotating_light: *{{severity|INCIDENT}} Incident Alert*

*{{incident_title}}*
`{{incident_id}}`

:warning: *Impact:* {{impact_description|Investigating...}}

:mag: *Status:* {{status}}

{{#if affected_services}}:desktop_computer: *Affected Services:* {{affected_services}}{{/if}}

{{#if incident_commander}}:bust_in_silhouette: *Incident Commander:* {{incident_commander}}{{/if}}

{{#if war_room_link}}:speech_balloon: <{{war_room_link}}|Join War Room>{{/if}}
{{#if statuspage_link}}:page_facing_up: <{{statuspage_link}}|Status Page>{{/if}}
{{#if dashboard_link}}:chart_with_upwards_trend: <{{dashboard_link}}|Dashboard>{{/if}}""",
    format="slack",
    required_fields=["incident_id", "incident_title"],
    optional_fields=["severity", "impact_description", "status", "affected_services", "incident_commander", "war_room_link", "statuspage_link", "dashboard_link"],
    channels=["slack"],
)

CUSTOMER_NOTIFICATION_TEMPLATE = MessageTemplate(
    name="customer_notification",
    description="Customer-facing incident notification",
    category="customer",
    subject="Service Update: {{incident_title}}",
    body="""Dear Valued Customer,

We are currently experiencing {{impact_description|an issue with our services}}.

**Affected Services:** {{affected_services|Some services may be affected}}

{{#if affected_regions}}
**Affected Regions:** {{affected_regions}}
{{/if}}

Our team is actively working to resolve this issue. We apologize for any inconvenience this may cause.

{{#if next_update_eta}}
We will provide an update {{next_update_eta}}.
{{/if}}

For real-time updates, please visit our status page{{#if statuspage_link}}: {{statuspage_link}}{{/if}}

Thank you for your patience and understanding.

Best regards,
The Support Team
""",
    format="plain",
    required_fields=["incident_title"],
    optional_fields=["impact_description", "affected_services", "affected_regions", "next_update_eta", "statuspage_link"],
    channels=["email"],
)


def get_builtin_templates() -> list[MessageTemplate]:
    """Get all built-in message templates.
    
    Returns:
        List of built-in templates
    """
    return [
        INITIAL_NOTIFICATION_TEMPLATE,
        UPDATE_TEMPLATE,
        RESOLUTION_TEMPLATE,
        POSTMORTEM_SUMMARY_TEMPLATE,
        EXECUTIVE_BRIEF_TEMPLATE,
        STATUSPAGE_UPDATE_TEMPLATE,
        SLACK_ALERT_TEMPLATE,
        CUSTOMER_NOTIFICATION_TEMPLATE,
    ]
