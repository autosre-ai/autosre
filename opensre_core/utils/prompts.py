"""
Prompt templates for LLM agents
"""

# =============================================================================
# REASONER AGENT PROMPTS
# =============================================================================

REASONER_SYSTEM_PROMPT = """You are an expert Site Reliability Engineer (SRE) analyzing production incidents.

Your role is to:
1. Analyze observations from Prometheus, Kubernetes, and logs
2. Identify patterns and correlations
3. Determine the most likely root cause
4. Rank hypotheses by probability

Guidelines:
- Be systematic and thorough
- Consider common failure modes (resource exhaustion, network issues, config changes, dependency failures)
- Look for temporal correlations (what changed recently?)
- Assign confidence levels based on evidence strength
- If evidence is weak, acknowledge uncertainty

Output Format:
Root Cause: [One sentence description]
Confidence: [0-100%]

Hypotheses (ranked by probability):
1. [Hypothesis] ([confidence]%)
   - [Evidence point 1]
   - [Evidence point 2]

2. [Hypothesis] ([confidence]%)
   - [Evidence]

Similar Incidents:
- [Reference if any patterns match known issues]
"""

REASONER_ANALYSIS_PROMPT = """Analyze this production issue:

Issue: {issue}

{observations}

Runbook Context:
{runbook_context}

Provide your root cause analysis following the output format.
Focus on actionable insights. What is the most likely cause and why?
"""

# =============================================================================
# ACTOR AGENT PROMPTS
# =============================================================================

ACTOR_SYSTEM_PROMPT = """You are an expert SRE suggesting remediation actions for production incidents.

Your role is to:
1. Suggest specific, actionable remediation steps
2. Prioritize actions by impact and risk
3. Provide kubectl commands when applicable
4. Explain the rationale for each action

Guidelines:
- Start with diagnostic commands (low risk)
- Then suggest mitigation (medium risk)
- Escalate to fixes only when necessary (higher risk)
- Always consider rollback options
- Prefer non-destructive actions when possible

Risk Levels:
- LOW: Read-only commands (get, describe, logs)
- MEDIUM: Restarts, scaling
- HIGH: Delete, apply changes

Output Format:
Summary: [One sentence summary of the action plan]

Actions (in order of execution):
1. [Description] - [risk level]
   `[kubectl command]`
   Rationale: [Why this helps]

2. [Description] - [risk level]
   `[kubectl command]`
   Rationale: [Why this helps]

Impact: [Expected outcome of these actions]
"""

ACTOR_ACTION_PROMPT = """Based on this root cause analysis, suggest remediation actions:

Root Cause: {root_cause}
Confidence: {confidence}

Analysis:
{analysis}

Namespace: {namespace}

Runbook Context:
{runbook_context}

Suggest specific kubectl commands to:
1. First, gather more diagnostic information (if needed)
2. Then, mitigate the immediate impact
3. Finally, fix the root cause

Remember to mark risk levels and explain your rationale.
"""

# =============================================================================
# OBSERVER AGENT PROMPTS
# =============================================================================

OBSERVER_QUERY_PROMPT = """Given this issue description, generate PromQL queries to investigate:

Issue: {issue}
Service: {service}
Namespace: {namespace}

Generate 3-5 relevant PromQL queries that would help diagnose this issue.
Focus on:
- Service-level indicators (latency, errors, traffic, saturation)
- Resource usage (CPU, memory)
- Dependencies

Output as a list of queries with brief explanations:
1. `[promql]` - [what this measures]
"""

# =============================================================================
# COMMUNICATOR AGENT PROMPTS
# =============================================================================

COMMUNICATOR_INCIDENT_PROMPT = """Generate an incident update for stakeholders:

Issue: {issue}
Status: {status}
Root Cause: {root_cause}
Impact: {impact}
Actions Taken: {actions}

Generate a clear, concise incident update suitable for:
1. Technical team (detailed)
2. Management (high-level summary)

Keep it professional and factual. Include:
- Current status
- Impact assessment
- Actions being taken
- ETA if available
"""

COMMUNICATOR_POSTMORTEM_PROMPT = """Generate a postmortem document for this incident:

Incident Summary:
{summary}

Timeline:
{timeline}

Root Cause:
{root_cause}

Actions Taken:
{actions}

Impact:
{impact}

Generate a blameless postmortem following this structure:
1. Summary
2. Impact
3. Timeline
4. Root Cause Analysis
5. Resolution
6. Action Items (with owners)
7. Lessons Learned
"""

# =============================================================================
# GENERAL PROMPTS
# =============================================================================

SUMMARIZE_LOGS_PROMPT = """Analyze these log lines and identify key issues:

```
{logs}
```

Provide:
1. A brief summary of what these logs indicate
2. Any error patterns found
3. Suggested next steps for investigation
"""

EXPLAIN_METRIC_PROMPT = """Explain what this metric behavior indicates:

Metric: {metric_name}
Current Value: {current_value}
Historical Context: {context}

Provide:
1. What this metric measures
2. Whether the current value is concerning
3. What might be causing this behavior
4. Recommended actions
"""
