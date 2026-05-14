"""
AutoSRE V2 End-to-End Tests.

This package contains comprehensive E2E tests for the AutoSRE V2 system:

- test_alert_lifecycle.py: Complete alert flow from webhook to resolution
- test_investigation_flow.py: Investigation scenarios (CPU, OOMKill, Latency)
- test_chat_interaction.py: Chat/conversation flows
- test_api.py: Full API test suite

Run with: pytest tests/e2e/ -v
"""

__all__ = [
    "test_alert_lifecycle",
    "test_investigation_flow",
    "test_chat_interaction",
    "test_api",
]
