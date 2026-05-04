"""ADK-based multi-agent system for OpenSRE.

This module provides Google Agent Development Kit (ADK) integration
for sophisticated multi-agent incident investigation workflows.

Key components:
- tools: OpenSRE tools wrapped for ADK agents
- sre_team: Multi-agent SRE team for coordinated investigation
"""

from .sre_team import create_sre_team, investigate_with_adk

__all__ = ["create_sre_team", "investigate_with_adk"]
