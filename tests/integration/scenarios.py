"""
Test Scenarios for OpenSRE Integration Tests

Defines all test scenarios with:
- Kubernetes manifest to deploy
- Issue description to investigate
- Expected observations and outcomes
- Confidence thresholds
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TestScenario:
    """Definition of a test scenario."""
    name: str
    manifest: str | None  # Path to k8s manifest relative to project root
    issue: str  # Issue description for investigation
    expected_observations: list[str] = field(default_factory=list)
    expected_root_cause_keywords: list[str] = field(default_factory=list)
    expected_confidence_min: float = 0.5
    expected_actions: list[str] = field(default_factory=list)
    timeout_seconds: int = 120
    namespace: str = "default"
    description: str = ""
    severity: str = "medium"  # low, medium, high, critical


# Base path for examples
EXAMPLES_PATH = Path(__file__).parent.parent.parent / "examples"


SCENARIOS = {
    "memory_hog": TestScenario(
        name="memory_hog",
        manifest="examples/memory-hog.yaml",
        issue="high memory usage in default namespace",
        expected_observations=[
            "memory",
            "container",
            "stress",
        ],
        expected_root_cause_keywords=[
            "memory",
            "memory-hog",
            "stress",
        ],
        expected_confidence_min=0.5,
        expected_actions=[
            "restart",
            "scale",
            "limit",
        ],
        timeout_seconds=120,
        description="Pod consuming high memory via stress tool",
        severity="medium",
    ),
    
    "cpu_hog": TestScenario(
        name="cpu_hog",
        manifest="examples/cpu-hog.yaml",
        issue="high CPU usage in default namespace",
        expected_observations=[
            "cpu",
            "throttl",
            "stress",
        ],
        expected_root_cause_keywords=[
            "cpu",
            "cpu-hog",
            "stress",
            "throttl",
        ],
        expected_confidence_min=0.5,
        expected_actions=[
            "restart",
            "scale",
            "limit",
        ],
        timeout_seconds=120,
        description="Pod consuming high CPU via stress tool",
        severity="medium",
    ),
    
    "crashloop": TestScenario(
        name="crashloop",
        manifest="examples/crashloop.yaml",
        issue="pod crashlooping in default namespace",
        expected_observations=[
            "CrashLoopBackOff",
            "restart",
            "exit",
            "BackOff",
        ],
        expected_root_cause_keywords=[
            "crash",
            "exit",
            "restart",
            "fail",
        ],
        expected_confidence_min=0.6,
        expected_actions=[
            "logs",
            "describe",
            "restart",
        ],
        timeout_seconds=120,
        description="Pod that exits with error code, causing CrashLoopBackOff",
        severity="high",
    ),
    
    "oom_kill": TestScenario(
        name="oom_kill",
        manifest="examples/oom-pod.yaml",
        issue="OOM killed pod in default namespace",
        expected_observations=[
            "OOMKilled",
            "memory",
            "limit",
        ],
        expected_root_cause_keywords=[
            "oom",
            "memory",
            "limit",
            "kill",
        ],
        expected_confidence_min=0.6,
        expected_actions=[
            "increase",
            "limit",
            "memory",
        ],
        timeout_seconds=120,
        description="Pod exceeds memory limit and gets OOM killed",
        severity="high",
    ),
    
    "latency_issue": TestScenario(
        name="latency_issue",
        manifest=None,  # Requires actual service with latency
        issue="high latency on checkout service",
        expected_observations=[
            "latency",
            "response",
            "slow",
        ],
        expected_root_cause_keywords=[
            "latency",
            "slow",
            "response",
        ],
        expected_confidence_min=0.4,  # Lower threshold - may not have metrics
        expected_actions=[
            "scale",
            "resource",
            "investigate",
        ],
        timeout_seconds=120,
        description="Service experiencing high latency",
        severity="medium",
    ),
    
    "error_rate": TestScenario(
        name="error_rate",
        manifest=None,  # Requires actual service with errors
        issue="5xx errors on api service",
        expected_observations=[
            "error",
            "5xx",
            "fail",
        ],
        expected_root_cause_keywords=[
            "error",
            "fail",
            "exception",
        ],
        expected_confidence_min=0.4,  # Lower threshold - may not have metrics
        expected_actions=[
            "logs",
            "restart",
            "rollback",
        ],
        timeout_seconds=120,
        description="Service returning 5xx errors",
        severity="high",
    ),
    
    "healthy_check": TestScenario(
        name="healthy_check",
        manifest=None,  # Uses existing resources
        issue="check health of default namespace",
        expected_observations=[
            "running",
            "healthy",
        ],
        expected_root_cause_keywords=[
            "healthy",
            "normal",
            "no issue",
        ],
        expected_confidence_min=0.3,  # May report no issues
        expected_actions=[],  # Should suggest no actions
        timeout_seconds=120,
        description="Health check of namespace (should be healthy)",
        severity="low",
    ),
    
    "network_issue": TestScenario(
        name="network_issue",
        manifest=None,
        issue="network connectivity issues between pods",
        expected_observations=[
            "network",
            "connection",
            "timeout",
        ],
        expected_root_cause_keywords=[
            "network",
            "dns",
            "connection",
        ],
        expected_confidence_min=0.4,
        expected_actions=[
            "network",
            "policy",
            "dns",
        ],
        timeout_seconds=120,
        description="Network connectivity problems",
        severity="high",
    ),
    
    "disk_pressure": TestScenario(
        name="disk_pressure",
        manifest=None,
        issue="disk pressure on nodes",
        expected_observations=[
            "disk",
            "storage",
            "volume",
        ],
        expected_root_cause_keywords=[
            "disk",
            "storage",
            "full",
            "pressure",
        ],
        expected_confidence_min=0.4,
        expected_actions=[
            "clean",
            "expand",
            "evict",
        ],
        timeout_seconds=120,
        description="Node experiencing disk pressure",
        severity="high",
    ),
    
    "pending_pods": TestScenario(
        name="pending_pods",
        manifest=None,
        issue="pods stuck in pending state",
        expected_observations=[
            "pending",
            "schedul",
            "resource",
        ],
        expected_root_cause_keywords=[
            "pending",
            "schedule",
            "resource",
            "insufficient",
        ],
        expected_confidence_min=0.5,
        expected_actions=[
            "scale",
            "node",
            "resource",
        ],
        timeout_seconds=120,
        description="Pods unable to be scheduled",
        severity="medium",
    ),
}


# Convenience function to get scenarios with manifests only
def get_deployable_scenarios() -> list[TestScenario]:
    """Get scenarios that have associated manifests to deploy."""
    return [s for s in SCENARIOS.values() if s.manifest is not None]


# Convenience function to get all scenario names
def get_scenario_names() -> list[str]:
    """Get all scenario names."""
    return list(SCENARIOS.keys())


# Quick access to specific scenario groups
RESOURCE_SCENARIOS = ["memory_hog", "cpu_hog", "oom_kill", "disk_pressure"]
STABILITY_SCENARIOS = ["crashloop", "pending_pods"]
NETWORK_SCENARIOS = ["latency_issue", "error_rate", "network_issue"]
HEALTH_SCENARIOS = ["healthy_check"]


def get_scenarios_by_category(category: str) -> list[TestScenario]:
    """Get scenarios by category."""
    categories = {
        "resource": RESOURCE_SCENARIOS,
        "stability": STABILITY_SCENARIOS,
        "network": NETWORK_SCENARIOS,
        "health": HEALTH_SCENARIOS,
    }
    names = categories.get(category, [])
    return [SCENARIOS[name] for name in names if name in SCENARIOS]
