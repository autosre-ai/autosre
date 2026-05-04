"""Multi-agent SRE team using Google ADK.

This module implements a sophisticated multi-agent incident investigation
system using the Google Agent Development Kit (ADK).

Team Structure:
- Observer: Gathers metrics, logs, and events
- Analyzer: Correlates data and identifies patterns
- Diagnostician: Determines root cause with confidence scoring
- Remediator: Suggests and executes fixes

The agents work in sequence, with each agent's output feeding the next.
"""

import os
from dataclasses import dataclass, field
from typing import Any

from google.adk import Agent
from google.adk.agents import SequentialAgent
from google.adk.models.lite_llm import LiteLlm

from .tools import (
    create_action_tools,
    create_kubernetes_tools,
    create_prometheus_tools,
)


@dataclass
class ADKInvestigationResult:
    """Result from ADK multi-agent investigation."""
    observations: str
    analysis: str
    diagnosis: str
    root_cause: str
    confidence: float
    recommended_actions: list[str]
    remediation_output: str
    agent_outputs: dict[str, Any] = field(default_factory=dict)


def _get_model() -> LiteLlm:
    """Get the configured LLM model for ADK agents.

    Uses LiteLLM for flexibility with different providers.
    Defaults to Ollama with llama3.2 if no API keys are configured.
    """
    # Check for various API keys
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return LiteLlm(model="gemini/gemini-2.0-flash")
    elif os.environ.get("ANTHROPIC_API_KEY"):
        return LiteLlm(model="anthropic/claude-3-5-sonnet-20241022")
    elif os.environ.get("OPENAI_API_KEY"):
        return LiteLlm(model="openai/gpt-4o")
    else:
        # Default to local Ollama
        return LiteLlm(model="ollama/llama3.2")


def create_observer_agent() -> Agent:
    """Create the Observer agent.

    The Observer's role is to gather all relevant observability data:
    - Prometheus metrics and alerts
    - Kubernetes pod statuses and events
    - Service health indicators
    """
    model = _get_model()

    tools = create_prometheus_tools() + create_kubernetes_tools()

    return Agent(
        name="Observer",
        model=model,
        instruction="""You are the Observer agent in an SRE team. Your job is to collect
all relevant observability data for the incident.

When investigating an issue, systematically gather:

1. **Alerts**: Check for any firing Prometheus alerts
2. **Pod Status**: List pods in the affected namespace, note any that are unhealthy
3. **Events**: Get recent warning events that might indicate problems
4. **Metrics**: Query relevant service metrics (CPU, memory, error rates, latency)
5. **Logs**: If specific pods are problematic, get their recent logs

Be thorough but focused. For each piece of information you gather:
- Note what's normal vs abnormal
- Include timestamps when relevant
- Highlight anything that stands out

Return your observations in a structured format:
---
## Alerts
[List any firing alerts]

## Pod Status
[Pod health summary]

## Events
[Recent warning events]

## Metrics
[Key metric values and anomalies]

## Logs Summary
[Notable log patterns if checked]

## Initial Impressions
[What stands out from the data]
---""",
        tools=tools,
    )


def create_analyzer_agent() -> Agent:
    """Create the Analyzer agent.

    The Analyzer correlates observations and identifies patterns:
    - Timeline reconstruction
    - Correlation analysis
    - Anomaly identification
    """
    model = _get_model()

    return Agent(
        name="Analyzer",
        model=model,
        instruction="""You are the Analyzer agent in an SRE team. Given observations from
the Observer, your job is to find patterns and correlations.

Analyze the data to:

1. **Timeline**: Reconstruct the sequence of events
   - What happened first?
   - How did issues propagate?

2. **Correlations**: Find relationships between observations
   - Do pod restarts correlate with metric spikes?
   - Are multiple services affected in a pattern?

3. **Anomalies**: Identify what deviates from normal
   - Compare to baseline behavior
   - Highlight unusual patterns

4. **Dependencies**: Map affected components
   - Which services are directly affected?
   - What are the upstream/downstream dependencies?

5. **Scope**: Determine blast radius
   - How widespread is the issue?
   - Is it isolated or systemic?

Provide your analysis in a structured format:
---
## Timeline
[Ordered sequence of events]

## Correlations Found
[Relationships between observations]

## Anomalies Detected
[What's abnormal and by how much]

## Affected Components
[Direct and indirect impact]

## Key Patterns
[Most significant findings]
---""",
    )


def create_diagnostician_agent() -> Agent:
    """Create the Diagnostician agent.

    The Diagnostician determines root cause:
    - Hypothesis generation
    - Evidence evaluation
    - Confidence scoring
    """
    model = _get_model()

    return Agent(
        name="Diagnostician",
        model=model,
        instruction="""You are the Diagnostician agent in an SRE team. Given analysis from
the Analyzer, your job is to determine the root cause.

Follow a scientific approach:

1. **Generate Hypotheses**: Based on the analysis, propose possible root causes
   - Consider common failure modes
   - Think about what could cause the observed patterns

2. **Evaluate Evidence**: For each hypothesis
   - What evidence supports it?
   - What evidence contradicts it?
   - What's still unknown?

3. **Assign Confidence**: Rate each hypothesis
   - High (>80%): Strong evidence, fits all observations
   - Medium (50-80%): Good evidence but some uncertainty
   - Low (<50%): Possible but limited evidence

4. **Determine Root Cause**: Identify the most likely cause
   - Consider if multiple factors are involved
   - Distinguish root cause from symptoms

Provide your diagnosis:
---
## Hypotheses Considered
[List each hypothesis with supporting/contradicting evidence]

## Root Cause
[Most likely root cause]

## Confidence: [X%]
[Explain your confidence level]

## Contributing Factors
[Secondary issues that may have contributed]

## Remaining Uncertainty
[What we don't know / need to verify]
---""",
    )


def create_remediator_agent() -> Agent:
    """Create the Remediator agent.

    The Remediator suggests and can execute fixes:
    - Immediate mitigation
    - Permanent fixes
    - Risk assessment
    """
    model = _get_model()

    tools = create_action_tools()

    return Agent(
        name="Remediator",
        model=model,
        instruction="""You are the Remediator agent in an SRE team. Given a root cause
diagnosis, your job is to recommend and potentially execute fixes.

For each issue, consider:

1. **Immediate Mitigation**: What can we do RIGHT NOW to reduce impact?
   - Quick fixes to restore service
   - Workarounds while we fix properly

2. **Permanent Fix**: What's the proper solution?
   - Address root cause, not just symptoms
   - Prevent recurrence

3. **Risk Assessment**: For each action
   - What could go wrong?
   - What's the blast radius?
   - Is it reversible?

4. **Prioritization**: Order by
   - Impact (how much will it help?)
   - Safety (how risky is it?)
   - Speed (how fast can we do it?)

IMPORTANT SAFETY RULES:
- NEVER execute destructive actions without explicit confirmation
- Prefer safe, reversible actions (like scaling up) over risky ones (like deleting pods)
- When in doubt, recommend but don't execute
- Consider rate limits and cascading effects

You have tools to:
- Restart individual pods
- Scale deployments
- Trigger rollout restarts

Provide your recommendations:
---
## Immediate Actions (do now)
[Numbered list with risk level: LOW/MEDIUM/HIGH]

## Short-term Fixes (next 24h)
[Actions to stabilize]

## Long-term Prevention (next sprint)
[Permanent solutions]

## Actions Taken
[If you executed any actions, report results here]

## Post-Incident Tasks
[Follow-up items for later]
---""",
        tools=tools,
    )


def create_sre_team() -> SequentialAgent:
    """Create a multi-agent SRE team.

    The team consists of:
    1. Observer - Gathers data
    2. Analyzer - Finds patterns
    3. Diagnostician - Determines root cause
    4. Remediator - Suggests/executes fixes

    They execute sequentially, with each agent building on the previous.

    Returns:
        SequentialAgent that orchestrates the team
    """
    observer = create_observer_agent()
    analyzer = create_analyzer_agent()
    diagnostician = create_diagnostician_agent()
    remediator = create_remediator_agent()

    # Sequential workflow: Observe → Analyze → Diagnose → Remediate
    return SequentialAgent(
        name="SRE_Investigation_Team",
        description="Multi-agent SRE team for comprehensive incident investigation",
        sub_agents=[observer, analyzer, diagnostician, remediator],
    )


async def investigate_with_adk(
    issue: str,
    namespace: str = "default",
    auto_remediate: bool = False,
) -> ADKInvestigationResult:
    """Run an investigation using the ADK agent team.

    This creates a multi-agent team that:
    1. Observes - Gathers metrics, logs, events
    2. Analyzes - Correlates and finds patterns
    3. Diagnoses - Determines root cause
    4. Remediates - Suggests (and optionally executes) fixes

    Args:
        issue: Description of the incident to investigate
        namespace: Kubernetes namespace to focus on
        auto_remediate: If True, allow agents to execute safe remediation actions

    Returns:
        ADKInvestigationResult with findings and recommendations

    Example:
        result = await investigate_with_adk(
            "High latency on checkout-service",
            namespace="production"
        )
        print(result.root_cause)
        print(result.recommended_actions)
    """
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    # Create the SRE team
    team = create_sre_team()

    # Set up session
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="opensre",
        user_id="cli-user",
    )

    # Create runner
    runner = Runner(
        agent=team,
        app_name="opensre",
        session_service=session_service,
    )

    # Build the investigation prompt
    remediation_note = ""
    if not auto_remediate:
        remediation_note = "\n\nIMPORTANT: Do NOT execute any remediation actions. Only recommend actions for human approval."

    prompt = f"""
INCIDENT INVESTIGATION

Issue: {issue}
Namespace: {namespace}

Please investigate this incident thoroughly. Work through each phase:
1. Observer: Gather all relevant observability data
2. Analyzer: Find patterns and correlations
3. Diagnostician: Determine root cause with confidence
4. Remediator: Recommend fixes (prioritized by impact and safety)
{remediation_note}

Begin the investigation.
"""

    # Run the investigation
    final_response = ""
    async for event in runner.run_async(
        user_id=session.user_id,
        session_id=session.id,
        new_message=prompt,
    ):
        if hasattr(event, 'content') and event.content:
            if hasattr(event.content, 'parts'):
                for part in event.content.parts:
                    if hasattr(part, 'text'):
                        final_response += part.text

    # Parse the response into structured result
    result = _parse_investigation_response(final_response)

    return result


def _parse_investigation_response(response: str) -> ADKInvestigationResult:
    """Parse the multi-agent response into a structured result.

    This is a best-effort parser that extracts key sections from
    the combined agent outputs.
    """
    import re

    # Default values
    observations = ""
    analysis = ""
    diagnosis = ""
    root_cause = "Unable to determine"
    confidence = 0.0
    recommended_actions = []
    remediation = ""

    # Try to extract sections
    sections = response.split("---")

    for section in sections:
        section_lower = section.lower()

        if "alerts" in section_lower and "pod status" in section_lower:
            observations = section.strip()
        elif "timeline" in section_lower and "correlations" in section_lower:
            analysis = section.strip()
        elif "root cause" in section_lower and "confidence" in section_lower:
            diagnosis = section.strip()

            # Extract confidence percentage
            conf_match = re.search(r'confidence[:\s]*(\d+)%', section_lower)
            if conf_match:
                confidence = float(conf_match.group(1)) / 100

            # Extract root cause
            rc_match = re.search(r'## root cause\s*\n(.+?)(?=\n##|\n---|\Z)', section, re.IGNORECASE | re.DOTALL)
            if rc_match:
                root_cause = rc_match.group(1).strip()

        elif "immediate actions" in section_lower:
            remediation = section.strip()

            # Extract action items
            action_matches = re.findall(r'\d+\.\s*(.+?)(?:\[|\(|$)', section)
            recommended_actions = [a.strip() for a in action_matches if a.strip()]

    return ADKInvestigationResult(
        observations=observations,
        analysis=analysis,
        diagnosis=diagnosis,
        root_cause=root_cause,
        confidence=confidence,
        recommended_actions=recommended_actions,
        remediation_output=remediation,
        agent_outputs={
            "full_response": response,
        }
    )


# Convenience aliases for direct import
SRETeam = create_sre_team
investigate = investigate_with_adk
