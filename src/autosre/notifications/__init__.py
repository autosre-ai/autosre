"""Notification Hub for AutoSRE V2.

Provides comprehensive notification capabilities:
- Multi-channel notification routing
- Rich message formatting
- Escalation policies
- Delivery tracking
"""

from autosre.notifications.notification_router import (
    NotificationRouter,
    Notification,
    NotificationChannel,
    NotificationPriority,
    NotificationStatus,
    DeliveryResult,
)
from autosre.notifications.channels.slack import (
    SlackIntegration,
    SlackMessage,
    SlackBlock,
)
from autosre.notifications.channels.pagerduty import (
    PagerDutyIntegration,
    PagerDutyIncident,
    PagerDutyEvent,
)
from autosre.notifications.channels.teams import (
    TeamsIntegration,
    TeamsMessage,
    TeamsCard,
)
from autosre.notifications.channels.email import (
    EmailSender,
    EmailMessage,
    EmailTemplate,
)
from autosre.notifications.channels.webhook import (
    WebhookManager,
    Webhook,
    WebhookEvent,
)
from autosre.notifications.escalation_engine import (
    EscalationEngine,
    EscalationPolicy,
    EscalationRule,
    EscalationLevel,
)

__all__ = [
    # Router
    "NotificationRouter",
    "Notification",
    "NotificationChannel",
    "NotificationPriority",
    "NotificationStatus",
    "DeliveryResult",
    # Slack
    "SlackIntegration",
    "SlackMessage",
    "SlackBlock",
    # PagerDuty
    "PagerDutyIntegration",
    "PagerDutyIncident",
    "PagerDutyEvent",
    # Teams
    "TeamsIntegration",
    "TeamsMessage",
    "TeamsCard",
    # Email
    "EmailSender",
    "EmailMessage",
    "EmailTemplate",
    # Webhook
    "WebhookManager",
    "Webhook",
    "WebhookEvent",
    # Escalation
    "EscalationEngine",
    "EscalationPolicy",
    "EscalationRule",
    "EscalationLevel",
]
