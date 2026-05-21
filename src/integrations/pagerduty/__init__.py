"""PagerDuty integration for AutoSRE.

Provides:
- PagerDutyClient: API client for PagerDuty REST API
- PagerDutyWebhook: Webhook handler for PagerDuty events
- PagerDutySkill: Skill for querying PagerDuty in investigations
- Pydantic models for PagerDuty entities
"""

from .client import (
    PagerDutyClient,
    PagerDutyError,
    PagerDutyAuthError,
    PagerDutyNotFoundError,
    PagerDutyRateLimitError,
)
from .webhook import PagerDutyWebhook, WebhookVerificationError
from .skill import PagerDutySkill
from .models import (
    Incident,
    IncidentStatus,
    IncidentUrgency,
    Alert,
    AlertSeverity,
    Service,
    Escalation,
    User,
    Note,
    LogEntry,
    OnCall,
    PagerDutyEvent,
    WebhookEvent,
    WebhookEventType,
    WebhookPayload,
)

__all__ = [
    # Client
    "PagerDutyClient",
    "PagerDutyError",
    "PagerDutyAuthError",
    "PagerDutyNotFoundError",
    "PagerDutyRateLimitError",
    # Webhook
    "PagerDutyWebhook",
    "WebhookVerificationError",
    # Skill
    "PagerDutySkill",
    # Models
    "Incident",
    "IncidentStatus",
    "IncidentUrgency",
    "Alert",
    "AlertSeverity",
    "Service",
    "Escalation",
    "User",
    "Note",
    "LogEntry",
    "OnCall",
    "PagerDutyEvent",
    "WebhookEvent",
    "WebhookEventType",
    "WebhookPayload",
]
