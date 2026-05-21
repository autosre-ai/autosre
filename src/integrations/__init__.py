"""AutoSRE Integrations.

This package contains integrations with external services:
- pagerduty: PagerDuty incident management integration
"""

from . import pagerduty

__all__ = [
    "pagerduty",
]
