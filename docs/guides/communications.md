# Incident Communications Guide

This guide covers AutoSRE's incident communications capabilities for automating stakeholder notifications, status page updates, and war room coordination during incidents.

## Overview

AutoSRE's communications module provides:

- **Statuspage Integration**: Automated public status page updates
- **War Room Coordination**: Centralized incident response with timeline tracking
- **Stakeholder Notifications**: Multi-channel notifications with escalation policies
- **Message Templates**: Consistent, professional incident communications

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Incident Communications Module                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐   │
│  │  Statuspage  │  │   War Room   │  │ Stakeholder  │  │   Message     │   │
│  │   Client     │  │ Coordinator  │  │  Notifier    │  │  Templates    │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └───────┬───────┘   │
│         │                 │                 │                   │           │
│  ┌──────┴─────────────────┴─────────────────┴───────────────────┴───────┐   │
│  │                      Communication Orchestrator                       │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────┐  │   │
│  │  │   Escalation   │  │   Timeline     │  │   Multi-Channel        │  │   │
│  │  │   Policies     │  │   Tracking     │  │   Delivery             │  │   │
│  │  └────────────────┘  └────────────────┘  └────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────────┤
│              Slack | Email | SMS | PagerDuty | Statuspage.io                │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Status Page Integration

Create and manage public status page incidents:

```python
from autosre.comms import (
    StatusPageClient,
    StatusPageConfig,
    IncidentStatus,
    IncidentImpact,
    ComponentStatus,
)

# Configure client
config = StatusPageConfig(
    api_key="your-statuspage-api-key",
    page_id="your-page-id",
    component_mapping={
        "payment-service": "component-123",
        "api-gateway": "component-456",
        "user-service": "component-789",
    },
    auto_create_incidents=True,
)

client = StatusPageClient(config)

# Create incident
incident = await client.create_incident(
    name="Payment Processing Delayed",
    status=IncidentStatus.INVESTIGATING,
    impact=IncidentImpact.MINOR,
    body="We are investigating reports of delayed payment processing.",
    component_ids=["component-123"],
    component_status=ComponentStatus.DEGRADED_PERFORMANCE,
)

print(f"Created incident: {incident.id}")
print(f"Status page link: {incident.shortlink}")
```

### 2. Post Status Updates

Keep stakeholders informed with status updates:

```python
# Post investigation update
await client.post_update(
    incident_id=incident.id,
    status=IncidentStatus.IDENTIFIED,
    body="We have identified the root cause as a database connection pool issue.",
    component_updates={
        "component-123": ComponentStatus.PARTIAL_OUTAGE,
    },
)

# Post mitigation update
await client.post_update(
    incident_id=incident.id,
    status=IncidentStatus.MONITORING,
    body="A fix has been deployed. We are monitoring the situation.",
)

# Resolve incident
await client.resolve_incident(
    incident_id=incident.id,
    body="The issue has been fully resolved. Payment processing is back to normal.",
)
```

### 3. War Room Coordination

Set up and manage incident war rooms:

```python
from autosre.comms import (
    WarRoomCoordinator,
    WarRoomConfig,
    WarRoomRole,
    WarRoomEventType,
    WarRoomState,
)

# Configure war room
config = WarRoomConfig(
    create_slack_channel=True,
    slack_channel_prefix="inc-",
    create_video_bridge=True,
    video_platform="zoom",
    notify_on_call=True,
    escalation_timeout_minutes=15,
)

coordinator = WarRoomCoordinator(config)

# Create war room for incident
war_room = await coordinator.create_war_room(
    incident_id="INC-2024-001",
    title="Payment API Latency Spike",
    severity="high",
    affected_services=["payment-api", "checkout-service"],
    summary="Payment API experiencing 5x latency increase",
)

print(f"War room created: {war_room.name}")
print(f"Slack channel: {war_room.slack_channel_name}")
print(f"Video bridge: {war_room.bridge.url if war_room.bridge else 'N/A'}")
```

### 4. Manage War Room Participants

Add responders and assign roles:

```python
# Add incident commander
ic = await coordinator.add_participant(
    war_room_id=war_room.id,
    user_id="user-001",
    name="Jane Smith",
    role=WarRoomRole.INCIDENT_COMMANDER,
    email="jane@example.com",
)

# Add technical lead
tech_lead = await coordinator.add_participant(
    war_room_id=war_room.id,
    user_id="user-002",
    name="Bob Engineer",
    role=WarRoomRole.TECHNICAL_LEAD,
)

# Add subject matter expert
await coordinator.add_participant(
    war_room_id=war_room.id,
    user_id="user-003",
    name="Alice DBA",
    role=WarRoomRole.SUBJECT_MATTER_EXPERT,
)
```

### 5. Track Timeline Events

Log investigation progress:

```python
# Log hypothesis
await coordinator.log_event(
    war_room_id=war_room.id,
    event_type=WarRoomEventType.HYPOTHESIS_ADDED,
    description="Database connection pool exhaustion suspected",
    actor="Bob Engineer",
)

# Log validation
await coordinator.log_event(
    war_room_id=war_room.id,
    event_type=WarRoomEventType.HYPOTHESIS_VALIDATED,
    description="Confirmed: connection pool at 100% utilization",
    actor="Alice DBA",
    metadata={"connection_count": 150, "max_connections": 150},
)

# Log root cause
await coordinator.update_status(
    war_room_id=war_room.id,
    root_cause="Connection leak in payment-service v2.3.1 causing pool exhaustion",
    updated_by="Bob Engineer",
)
```

### 6. Stakeholder Notifications

Notify stakeholders with escalation:

```python
from autosre.comms import (
    StakeholderNotifier,
    Stakeholder,
    StakeholderGroup,
    EscalationPolicy,
    EscalationLevel,
    NotificationChannel,
    StakeholderPriority,
)

notifier = StakeholderNotifier()

# Add stakeholders
notifier.add_stakeholder(Stakeholder(
    id="eng-001",
    name="Jane Engineer",
    email="jane@example.com",
    slack_user_id="U12345",
    pagerduty_user_id="PUSER123",
    service_ownership=["payment-api", "checkout-service"],
))

notifier.add_stakeholder(Stakeholder(
    id="mgr-001",
    name="Pat Manager",
    email="pat@example.com",
    role="Engineering Manager",
))

# Create stakeholder groups
notifier.add_group(StakeholderGroup(
    id="payments-team",
    name="Payments Team",
    stakeholders=["eng-001"],
    services=["payment-api", "checkout-service"],
    severities=["critical", "high", "warning"],
))

notifier.add_group(StakeholderGroup(
    id="engineering-leadership",
    name="Engineering Leadership",
    stakeholders=["mgr-001"],
    escalation_group=True,
    severities=["critical"],
))

# Send notifications
results = await notifier.notify(
    incident_id="INC-2024-001",
    title="Payment API Latency Spike",
    message="Payment API experiencing 5x latency increase affecting checkout.",
    severity="high",
    affected_services=["payment-api"],
    priority=StakeholderPriority.HIGH,
)

print(f"Sent {len(results)} notifications")
```

### 7. Escalation Policies

Configure automatic escalation:

```python
# Define escalation policy
policy = EscalationPolicy(
    name="Payment Service Critical",
    description="Escalation policy for payment service critical incidents",
    levels=[
        EscalationLevel(
            level=1,
            name="Primary On-Call",
            stakeholder_groups=["payments-team"],
            timeout_minutes=5,
            channels=[NotificationChannel.PAGERDUTY, NotificationChannel.SLACK],
        ),
        EscalationLevel(
            level=2,
            name="Secondary On-Call",
            stakeholder_groups=["payments-team"],
            timeout_minutes=10,
            channels=[NotificationChannel.PAGERDUTY, NotificationChannel.SMS],
        ),
        EscalationLevel(
            level=3,
            name="Engineering Manager",
            stakeholder_groups=["engineering-leadership"],
            timeout_minutes=15,
            channels=[NotificationChannel.PAGERDUTY, NotificationChannel.VOICE],
        ),
    ],
    services=["payment-api", "checkout-service"],
    severities=["critical"],
)

notifier.add_escalation_policy(policy)

# Trigger escalation
await notifier.escalate(
    incident_id="INC-2024-001",
    title="Payment API Latency Spike",
    message="No acknowledgment received. Escalating.",
    severity="critical",
    affected_services=["payment-api"],
    reason="No acknowledgment within 5 minutes",
)
```

### 8. Message Templates

Use templates for consistent communications:

```python
from autosre.comms import (
    TemplateEngine,
    TemplateContext,
    INITIAL_NOTIFICATION_TEMPLATE,
    UPDATE_TEMPLATE,
    RESOLUTION_TEMPLATE,
)

engine = TemplateEngine()

# Create context
context = TemplateContext(
    incident_id="INC-2024-001",
    incident_title="Payment API Latency Spike",
    severity="high",
    status="investigating",
    affected_services=["payment-api", "checkout-service"],
    impact_description="Users may experience delays during checkout.",
    affected_users="~5% of users",
    incident_commander="Jane Smith",
    war_room_link="https://example.slack.com/archives/C123456",
    next_update_eta="30 minutes",
)

# Render initial notification
message = engine.render(INITIAL_NOTIFICATION_TEMPLATE, context)
print(message.subject)
print(message.body)

# Render update
context.status = "identified"
context.root_cause = "Database connection pool exhaustion"
context.mitigation_steps = [
    "Increased connection pool size",
    "Deployed fix for connection leak",
]
update = engine.render(UPDATE_TEMPLATE, context)
```

## Template Variables

Available variables for message templates:

| Variable | Description |
|----------|-------------|
| `incident_id` | Incident identifier |
| `incident_title` | Incident title |
| `severity` | Incident severity (critical, high, warning, low) |
| `status` | Current status (investigating, identified, monitoring, resolved) |
| `started_at` | Incident start timestamp |
| `resolved_at` | Resolution timestamp |
| `duration` | Incident duration |
| `affected_services` | List of affected services |
| `impact_description` | Description of impact |
| `affected_users` | User impact description |
| `affected_regions` | List of affected regions |
| `root_cause` | Root cause description |
| `mitigation_steps` | List of mitigation steps |
| `resolution_summary` | Resolution summary |
| `hypotheses` | Investigation hypotheses |
| `findings` | Investigation findings |
| `incident_commander` | IC name |
| `technical_lead` | Tech lead name |
| `communications_lead` | Comms lead name |
| `war_room_link` | War room URL |
| `statuspage_link` | Status page URL |
| `dashboard_link` | Dashboard URL |
| `next_update_eta` | ETA for next update |

## Built-in Templates

| Template | Description | Channels |
|----------|-------------|----------|
| `initial_notification` | Initial incident alert | Slack, Email |
| `status_update` | Progress update | Slack, Email, Statuspage |
| `resolution` | Incident resolved | Slack, Email, Statuspage |
| `postmortem_summary` | Postmortem brief | Email |
| `executive_brief` | Executive-level summary | Email, Slack |
| `statuspage_update` | Statuspage.io format | Statuspage |
| `slack_alert` | Slack-formatted alert | Slack |
| `customer_notification` | Customer-facing update | Email |

## Custom Templates

Create custom templates for your organization:

```python
from autosre.comms import MessageTemplate, TemplateRegistry

# Create custom template
custom_template = MessageTemplate(
    name="on_call_handoff",
    description="On-call handoff notification",
    category="oncall",
    subject="[HANDOFF] {{incident_title}} - {{incident_id}}",
    body="""# On-Call Handoff

**Incident:** {{incident_title}} ({{incident_id}})
**Status:** {{status}}
**Duration:** {{duration}}

## Current State
{{impact_description}}

## Key Findings
{{#each findings}}- {{this}}
{{/each}}

## Pending Actions
{{#each next_steps}}- {{this}}
{{/each}}

## Context for Next On-Call
{{custom.handoff_notes}}

---
Outgoing: {{custom.outgoing_oncall}}
Incoming: {{custom.incoming_oncall}}
""",
    required_fields=["incident_id", "incident_title"],
    channels=["slack", "email"],
)

# Register template
engine.registry.register(custom_template)

# Use template
context.custom = {
    "handoff_notes": "Database team is engaged. Waiting for their analysis.",
    "outgoing_oncall": "Jane Smith",
    "incoming_oncall": "Bob Engineer",
}
message = engine.render(custom_template, context)
```

## War Room Checklist

Default incident response checklist phases:

### Triage
1. Acknowledge incident
2. Assign Incident Commander
3. Create communication channels
4. Assess severity and impact
5. Notify stakeholders

### Communication
6. Update status page

### Investigation
7. Identify affected services
8. Form hypotheses
9. Gather evidence
10. Identify root cause

### Mitigation
11. Implement mitigation

### Resolution
12. Verify resolution
13. Post resolution update

### Closure
14. Schedule postmortem
15. Close war room

## Integration with AutoSRE

The communications module integrates with other AutoSRE components:

### With Orchestrator

```python
from autosre import Orchestrator
from autosre.comms import StatusPageClient, WarRoomCoordinator

orchestrator = Orchestrator(
    statuspage_client=status_client,
    war_room_coordinator=coordinator,
)

# Automatic status page and war room on alert
result = await orchestrator.investigate(alert)

# Communications are handled automatically
print(f"Status page: {result.statuspage_incident_id}")
print(f"War room: {result.war_room_id}")
```

### With Postmortem Generator

```python
from autosre import PostmortemGenerator
from autosre.comms import TemplateEngine, POSTMORTEM_SUMMARY_TEMPLATE

# Generate postmortem
generator = PostmortemGenerator()
postmortem = await generator.generate(investigation_result)

# Send summary using template
context = TemplateContext(
    incident_id=postmortem.incident_id,
    incident_title=postmortem.title,
    root_cause=postmortem.root_cause,
    findings=postmortem.key_learnings,
    next_steps=[ai.description for ai in postmortem.action_items],
)

engine = TemplateEngine()
summary = engine.render(POSTMORTEM_SUMMARY_TEMPLATE, context)
```

## Best Practices

### 1. Communication Timing
- Send initial notification within 5 minutes of incident detection
- Post updates at least every 30 minutes during active incidents
- Use clear ETAs for next updates

### 2. Message Content
- Lead with impact, not technical details
- Use consistent severity language
- Include actionable information (war room links, status pages)
- Be honest about unknowns

### 3. Stakeholder Management
- Define clear escalation policies before incidents
- Map services to stakeholder groups
- Respect quiet hours for non-critical notifications
- Track acknowledgments

### 4. War Room Discipline
- Assign clear roles (IC, Tech Lead, Scribe)
- Log all significant events to timeline
- Use checklist to ensure nothing is missed
- Close war room properly with postmortem scheduling

## API Reference

See the [API Documentation](../reference/api.md) for complete API reference.

## Related Guides

- [Slack Integration](./slack-integration.md)
- [PagerDuty Integration](./pagerduty-integration.md)
- [Workflows](./workflows.md)
