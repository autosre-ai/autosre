"""
Sandbox Environment - Safe environment for testing and evaluation.

The sandbox provides:
- Kind cluster auto-setup
- Prometheus + Grafana stack
- Sample applications
- Chaos injection capabilities
"""

from autosre.sandbox.cluster import SandboxCluster
from autosre.sandbox.chaos import ChaosInjector
from autosre.sandbox.observability import ObservabilityStack

__all__ = [
    "SandboxCluster",
    "ChaosInjector",
    "ObservabilityStack",
]
