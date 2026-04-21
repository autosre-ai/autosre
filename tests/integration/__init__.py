"""
OpenSRE Integration Tests

This package contains integration tests that run OpenSRE investigations
against real or simulated Kubernetes environments.
"""

from tests.integration.scenarios import SCENARIOS, Scenario, get_scenario_names
from tests.integration.test_runner import TestResult, TestRunner

__all__ = [
    "SCENARIOS",
    "Scenario",
    "TestRunner",
    "TestResult",
    "get_scenario_names",
]
