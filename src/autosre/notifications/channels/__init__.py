"""Channels package for notification integrations."""

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

__all__ = [
    "SlackIntegration",
    "SlackMessage",
    "SlackBlock",
    "PagerDutyIntegration",
    "PagerDutyIncident",
    "PagerDutyEvent",
    "TeamsIntegration",
    "TeamsMessage",
    "TeamsCard",
    "EmailSender",
    "EmailMessage",
    "EmailTemplate",
    "WebhookManager",
    "Webhook",
    "WebhookEvent",
]
