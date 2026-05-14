"""AutoSRE Prompt Templates - System prompts and templates for LLM interactions."""

from __future__ import annotations

from string import Template
from typing import Any


class PromptTemplates:
    """SRE-focused prompt templates for different investigation stages."""
    
    # =========================================================================
    # SYSTEM PROMPTS
    # =========================================================================
    
    SYSTEM_PROMPT = """You are AutoSRE, an expert Site Reliability Engineer AI assistant.

Your role is to help investigate production incidents, identify root causes, and recommend remediations.

## Core Principles
1. **Data-Driven**: Base conclusions on evidence, not assumptions
2. **Methodical**: Follow a structured investigation process
3. **Safe**: Prefer diagnostic actions over destructive ones
4. **Clear**: Communicate findings clearly and concisely
5. **Humble**: Acknowledge uncertainty and limitations

## Investigation Approach
1. Gather initial context from the alert
2. Form hypotheses based on symptoms
3. Collect relevant observations (metrics, logs, traces)
4. Test hypotheses with evidence
5. Identify root cause with confidence level
6. Recommend remediation steps

## Output Format
Always structure your responses with clear sections:
- Use Markdown formatting
- Include confidence levels (low/medium/high or percentages)
- Cite specific evidence for conclusions
- Separate facts from interpretations"""

    # =========================================================================
    # TRIAGE PROMPT
    # =========================================================================
    
    TRIAGE_PROMPT = Template("""## Incident Triage

Analyze this incoming alert and provide initial triage.

### Alert Details
$alert_context

### Available Context
$additional_context

### Your Task
1. **Severity Assessment**: Is the severity accurate? Should it be escalated?
2. **Initial Hypotheses**: What are the most likely causes? (list 3-5)
3. **Immediate Actions**: What diagnostic steps should we take first?
4. **Data Needed**: What additional data would help the investigation?

### Output Format
```json
{
    "severity_assessment": {
        "current": "string",
        "recommended": "string",
        "reason": "string"
    },
    "hypotheses": [
        {
            "statement": "string",
            "likelihood": "high|medium|low",
            "reasoning": "string"
        }
    ],
    "immediate_actions": [
        {
            "action": "string",
            "tool": "string",
            "priority": 1
        }
    ],
    "data_needed": [
        {
            "type": "metrics|logs|traces|config",
            "description": "string",
            "query_hint": "string"
        }
    ],
    "escalation_needed": false,
    "escalation_reason": "string or null"
}
```""")

    # =========================================================================
    # INVESTIGATION PROMPT
    # =========================================================================
    
    INVESTIGATION_PROMPT = Template("""## Investigation Step

Continue investigating the incident based on new observations.

### Alert Context
$alert_context

### Current Hypotheses
$hypotheses

### Recent Observations
$observations

### Actions Taken
$actions_taken

### Your Task
Analyze the new observations and update the investigation:

1. **Evidence Analysis**: What do the observations tell us?
2. **Hypothesis Update**: Which hypotheses are supported/refuted?
3. **Next Steps**: What should we investigate next?
4. **Confidence**: How confident are we in the current direction?

### Output Format
```json
{
    "evidence_analysis": [
        {
            "observation_id": "uuid",
            "interpretation": "string",
            "is_anomalous": true,
            "relevance": "high|medium|low"
        }
    ],
    "hypothesis_updates": [
        {
            "hypothesis_id": "uuid",
            "new_status": "investigating|confirmed|rejected|inconclusive",
            "new_confidence": 0.8,
            "reasoning": "string"
        }
    ],
    "new_hypotheses": [
        {
            "statement": "string",
            "reasoning": "string",
            "verification_steps": ["string"]
        }
    ],
    "next_actions": [
        {
            "type": "diagnostic|remediation",
            "name": "string",
            "description": "string",
            "tool": "string",
            "parameters": {},
            "priority": 1
        }
    ],
    "overall_confidence": 0.6,
    "investigation_status": "continue|needs_more_data|ready_for_root_cause"
}
```""")

    # =========================================================================
    # ROOT CAUSE ANALYSIS PROMPT
    # =========================================================================
    
    ROOT_CAUSE_PROMPT = Template("""## Root Cause Analysis

Determine the root cause based on the investigation.

### Alert Context
$alert_context

### Investigation Summary
$investigation_summary

### Confirmed Hypotheses
$confirmed_hypotheses

### Key Observations
$key_observations

### Your Task
Based on all evidence, determine the root cause:

1. **Root Cause**: What is the primary root cause?
2. **Contributing Factors**: What else contributed to the incident?
3. **Chain of Events**: Reconstruct the timeline
4. **Confidence Level**: How certain are we?

### Output Format
```json
{
    "root_cause": {
        "summary": "One sentence root cause",
        "detailed_explanation": "Full explanation",
        "confidence": 0.85,
        "evidence": ["list of key evidence points"]
    },
    "contributing_factors": [
        {
            "factor": "string",
            "impact": "high|medium|low",
            "explanation": "string"
        }
    ],
    "timeline": [
        {
            "timestamp": "ISO timestamp or relative",
            "event": "string",
            "significance": "string"
        }
    ],
    "uncertainties": [
        "Things we're still not sure about"
    ],
    "verification_needed": [
        "Additional checks to confirm root cause"
    ]
}
```""")

    # =========================================================================
    # REMEDIATION PROMPT
    # =========================================================================
    
    REMEDIATION_PROMPT = Template("""## Remediation Planning

Plan remediation based on the root cause analysis.

### Root Cause
$root_cause

### Current State
$current_state

### Available Tools
$available_tools

### Constraints
$constraints

### Your Task
Plan the remediation steps:

1. **Immediate Actions**: What needs to happen right now?
2. **Verification Steps**: How do we confirm the fix works?
3. **Rollback Plan**: What if the fix makes things worse?
4. **Prevention**: How do we prevent this in the future?

### Output Format
```json
{
    "immediate_actions": [
        {
            "name": "string",
            "description": "string",
            "type": "remediation|scale|restart|rollback|config_change",
            "tool": "string",
            "command": "string or null",
            "parameters": {},
            "is_destructive": false,
            "requires_approval": true,
            "risk_level": "low|medium|high|critical",
            "expected_impact": "string",
            "estimated_time": "string"
        }
    ],
    "verification_steps": [
        {
            "step": "string",
            "success_criteria": "string",
            "tool": "string"
        }
    ],
    "rollback_plan": {
        "trigger_conditions": ["when to rollback"],
        "steps": [
            {
                "action": "string",
                "tool": "string"
            }
        ]
    },
    "prevention_recommendations": [
        {
            "recommendation": "string",
            "priority": "high|medium|low",
            "effort": "low|medium|high",
            "type": "monitoring|automation|process|architecture"
        }
    ],
    "communication": {
        "stakeholders_to_notify": ["list of roles/teams"],
        "status_message": "string for status page",
        "internal_update": "string for team"
    }
}
```""")

    # =========================================================================
    # CHAT / INTERACTIVE PROMPT
    # =========================================================================
    
    CHAT_PROMPT = Template("""## Interactive Investigation

You are helping an SRE investigate an incident interactively.

### Investigation Context
$investigation_context

### Recent Observations
$recent_observations

### User Question
$user_question

### Your Task
Answer the user's question helpfully. You can:
- Explain what's happening in plain language
- Suggest next investigation steps
- Interpret data and metrics
- Recommend actions
- Clarify technical concepts

Be conversational but precise. If you're not sure, say so.""")

    # =========================================================================
    # OBSERVATION SUMMARIZATION
    # =========================================================================
    
    SUMMARIZE_OBSERVATION_PROMPT = Template("""Summarize this $observation_type observation concisely:

**Source:** $source
**Query:** $query

**Data:**
```
$data
```

Provide:
1. A one-sentence summary
2. Key anomalies or notable patterns (if any)
3. Relevance to the investigation

Output as JSON:
```json
{
    "summary": "string",
    "anomalies": ["list of anomalies"],
    "is_anomalous": false,
    "relevance_score": 0.5,
    "key_values": {"metric": "value"}
}
```""")

    # =========================================================================
    # STRUCTURED OUTPUT EXTRACTION
    # =========================================================================
    
    EXTRACT_STRUCTURED_PROMPT = Template("""Extract structured information from this text.

**Text:**
$text

**Expected Schema:**
$schema

Output valid JSON matching the schema. If information is missing, use null.""")

    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    @classmethod
    def render(cls, template_name: str, **kwargs: Any) -> str:
        """Render a template by name with the given variables.
        
        Args:
            template_name: Name of the template (e.g., 'TRIAGE_PROMPT')
            **kwargs: Variables to substitute in the template
            
        Returns:
            Rendered template string
        """
        template = getattr(cls, template_name, None)
        if template is None:
            raise ValueError(f"Unknown template: {template_name}")
        
        if isinstance(template, Template):
            return template.safe_substitute(**kwargs)
        return str(template)
    
    @classmethod
    def triage(
        cls,
        alert_context: str,
        additional_context: str = "None available"
    ) -> str:
        """Render the triage prompt."""
        return cls.TRIAGE_PROMPT.safe_substitute(
            alert_context=alert_context,
            additional_context=additional_context
        )
    
    @classmethod
    def investigate(
        cls,
        alert_context: str,
        hypotheses: str,
        observations: str,
        actions_taken: str = "None yet"
    ) -> str:
        """Render the investigation prompt."""
        return cls.INVESTIGATION_PROMPT.safe_substitute(
            alert_context=alert_context,
            hypotheses=hypotheses,
            observations=observations,
            actions_taken=actions_taken
        )
    
    @classmethod
    def root_cause(
        cls,
        alert_context: str,
        investigation_summary: str,
        confirmed_hypotheses: str,
        key_observations: str
    ) -> str:
        """Render the root cause analysis prompt."""
        return cls.ROOT_CAUSE_PROMPT.safe_substitute(
            alert_context=alert_context,
            investigation_summary=investigation_summary,
            confirmed_hypotheses=confirmed_hypotheses,
            key_observations=key_observations
        )
    
    @classmethod
    def remediate(
        cls,
        root_cause: str,
        current_state: str,
        available_tools: str,
        constraints: str = "None specified"
    ) -> str:
        """Render the remediation prompt."""
        return cls.REMEDIATION_PROMPT.safe_substitute(
            root_cause=root_cause,
            current_state=current_state,
            available_tools=available_tools,
            constraints=constraints
        )
    
    @classmethod
    def chat(
        cls,
        investigation_context: str,
        recent_observations: str,
        user_question: str
    ) -> str:
        """Render the chat prompt."""
        return cls.CHAT_PROMPT.safe_substitute(
            investigation_context=investigation_context,
            recent_observations=recent_observations,
            user_question=user_question
        )
    
    @classmethod
    def summarize_observation(
        cls,
        observation_type: str,
        source: str,
        query: str,
        data: str
    ) -> str:
        """Render the observation summarization prompt."""
        return cls.SUMMARIZE_OBSERVATION_PROMPT.safe_substitute(
            observation_type=observation_type,
            source=source,
            query=query,
            data=data
        )
