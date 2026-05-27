"""
Slack Message Formatting

Rich message formatting using Slack Block Kit for investigation updates,
findings, and results. All formatters return Block Kit blocks for use
with the Slack API.

Block Kit Reference: https://api.slack.com/block-kit
"""

from datetime import datetime, timezone
from typing import Optional


def format_investigation_start(
    investigation_id: str,
    alert: dict,
    requested_by: str,
) -> list[dict]:
    """
    Format the initial investigation start message.
    
    Args:
        investigation_id: Unique investigation identifier
        alert: Alert data that triggered the investigation
        requested_by: Slack user ID or name who requested
        
    Returns:
        List of Block Kit blocks
    """
    service = alert.get("service", "Unknown")
    severity = alert.get("severity", "medium")
    description = alert.get("description", "No description provided")
    
    # Severity emoji mapping
    severity_emoji = {
        "critical": "🔴",
        "high": "🟠",
        "medium": "🟡",
        "low": "🟢",
    }.get(severity.lower(), "⚪")
    
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🔍 Investigation Started",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Investigation ID:*\n`{investigation_id}`",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Requested by:*\n{requested_by}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Service:*\n`{service}`",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Severity:*\n{severity_emoji} {severity.capitalize()}",
                },
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Alert Description:*\n{description}",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"⏱️ Started at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC | "
                            f"React with 👍/👎 to provide feedback on results",
                },
            ],
        },
        {"type": "divider"},
    ]


def format_progress_update(
    investigation_id: str,
    step: str,
    status: str,
    details: Optional[str] = None,
) -> list[dict]:
    """
    Format a progress update during investigation.
    
    Args:
        investigation_id: Investigation identifier
        step: Name of the current step
        status: Step status (in_progress, complete, error)
        details: Optional additional details
        
    Returns:
        List of Block Kit blocks
    """
    # Status indicators
    status_indicator = {
        "in_progress": "🔄",
        "complete": "✅",
        "error": "❌",
        "pending": "⏳",
    }.get(status, "▫️")
    
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{status_indicator} *{step}*",
            },
        },
    ]
    
    if details:
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": details[:300],  # Truncate long details
                },
            ],
        })
    
    return blocks


def format_evidence_found(
    investigation_id: str,
    finding_type: str,
    summary: str,
    details: Optional[dict] = None,
    confidence: Optional[float] = None,
) -> list[dict]:
    """
    Format a finding or evidence discovery.
    
    Args:
        investigation_id: Investigation identifier
        finding_type: Type of finding (metric, log, trace, etc.)
        summary: Brief summary of the finding
        details: Optional structured details
        confidence: Optional confidence score (0.0-1.0)
        
    Returns:
        List of Block Kit blocks
    """
    # Type emoji mapping
    type_emoji = {
        "metric": "📊",
        "log": "📝",
        "trace": "🔗",
        "config": "⚙️",
        "deployment": "🚀",
        "error": "🐛",
        "hypothesis": "💡",
    }.get(finding_type.lower(), "📌")
    
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{type_emoji} *Evidence Found: {finding_type.capitalize()}*\n{summary}",
            },
        },
    ]
    
    # Add details if present
    if details:
        detail_lines = []
        for key, value in list(details.items())[:5]:  # Max 5 fields
            detail_lines.append(f"• *{key}:* {value}")
        
        if detail_lines:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "\n".join(detail_lines),
                    },
                ],
            })
    
    # Add confidence if present
    if confidence is not None:
        confidence_bar = _format_confidence_bar(confidence)
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Confidence: {confidence_bar} {confidence:.0%}",
                },
            ],
        })
    
    return blocks


def format_investigation_complete(
    investigation_id: str,
    status: str,
    root_cause: str,
    summary: str,
    recommendations: list[str],
    duration_seconds: Optional[float] = None,
) -> list[dict]:
    """
    Format the final investigation completion message.
    
    Args:
        investigation_id: Investigation identifier
        status: Final status (completed, timeout, error)
        root_cause: Identified root cause
        summary: Investigation summary
        recommendations: List of recommendations
        duration_seconds: Total investigation duration
        
    Returns:
        List of Block Kit blocks
    """
    # Status indicator
    status_emoji = {
        "completed": "✅",
        "timeout": "⏰",
        "error": "❌",
    }.get(status, "ℹ️")
    
    # Format duration
    duration_str = ""
    if duration_seconds:
        if duration_seconds < 60:
            duration_str = f"{duration_seconds:.1f}s"
        else:
            minutes = int(duration_seconds // 60)
            seconds = int(duration_seconds % 60)
            duration_str = f"{minutes}m {seconds}s"
    
    blocks = [
        {"type": "divider"},
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{status_emoji} Investigation Complete",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Investigation ID:* `{investigation_id}`",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*🎯 Root Cause:*\n{root_cause}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*📋 Summary:*\n{summary}",
            },
        },
    ]
    
    # Add recommendations
    if recommendations:
        rec_text = "*💡 Recommendations:*\n"
        for i, rec in enumerate(recommendations[:5], 1):  # Max 5 recommendations
            rec_text += f"{i}. {rec}\n"
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": rec_text,
            },
        })
    
    # Context with duration and feedback prompt
    context_text = []
    if duration_str:
        context_text.append(f"⏱️ Duration: {duration_str}")
    context_text.append("React with 👍/👎 to provide feedback")
    
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": " | ".join(context_text),
            },
        ],
    })
    
    # Action buttons
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "📊 View Full Report",
                    "emoji": True,
                },
                "url": f"https://autosre.example.com/investigations/{investigation_id}",
                "action_id": "view_report",
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "🔄 Re-investigate",
                    "emoji": True,
                },
                "action_id": f"reinvestigate_{investigation_id}",
            },
        ],
    })
    
    return blocks


def format_error(
    title: str,
    message: str,
    details: Optional[dict] = None,
) -> list[dict]:
    """
    Format an error message.
    
    Args:
        title: Error title
        message: Error message
        details: Optional additional details
        
    Returns:
        List of Block Kit blocks
    """
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"❌ *{title}*\n{message}",
            },
        },
    ]
    
    if details:
        detail_lines = [f"• *{k}:* {v}" for k, v in details.items()]
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "\n".join(detail_lines),
                },
            ],
        })
    
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": "If this persists, please contact your SRE team or "
                        "check the AutoSRE dashboard for more details.",
            },
        ],
    })
    
    return blocks


def format_hypothesis(
    hypothesis: str,
    priority: str,
    agents: list[str],
) -> list[dict]:
    """
    Format a hypothesis being investigated.
    
    Args:
        hypothesis: The hypothesis text
        priority: Priority level (high, medium, low)
        agents: Agents assigned to test this hypothesis
        
    Returns:
        List of Block Kit blocks
    """
    priority_emoji = {
        "high": "🔴",
        "medium": "🟡",
        "low": "🟢",
    }.get(priority.lower(), "⚪")
    
    agents_str = ", ".join(f"`{a}`" for a in agents) if agents else "None assigned"
    
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"💡 *Hypothesis:* {hypothesis}\n"
                        f"{priority_emoji} Priority: {priority.capitalize()}\n"
                        f"🤖 Agents: {agents_str}",
            },
        },
    ]


def format_agent_result(
    agent_id: str,
    status: str,
    findings: str,
    confidence: float,
    tool_calls: int = 0,
) -> list[dict]:
    """
    Format results from an investigation agent.
    
    Args:
        agent_id: Agent identifier
        status: Agent status (completed, error, timeout)
        findings: Agent's findings
        confidence: Confidence score
        tool_calls: Number of tool calls made
        
    Returns:
        List of Block Kit blocks
    """
    status_emoji = {
        "completed": "✅",
        "error": "❌",
        "timeout": "⏰",
    }.get(status, "▫️")
    
    confidence_bar = _format_confidence_bar(confidence)
    
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🤖 *Agent `{agent_id}`* {status_emoji}\n"
                        f"Confidence: {confidence_bar} {confidence:.0%}\n"
                        f"Tool calls: {tool_calls}",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": findings[:500] if len(findings) > 500 else findings,
                },
            ],
        },
    ]


def format_metrics_attachment(
    title: str,
    metrics: list[dict],
) -> list[dict]:
    """
    Format a metrics summary attachment.
    
    Args:
        title: Attachment title
        metrics: List of metric dicts with name, value, and optional trend
        
    Returns:
        List of Block Kit blocks
    """
    fields = []
    for metric in metrics[:6]:  # Max 6 metrics
        name = metric.get("name", "Unknown")
        value = metric.get("value", "N/A")
        trend = metric.get("trend", "")
        
        trend_emoji = ""
        if trend == "up":
            trend_emoji = "📈"
        elif trend == "down":
            trend_emoji = "📉"
        elif trend == "stable":
            trend_emoji = "➡️"
        
        fields.append({
            "type": "mrkdwn",
            "text": f"*{name}:*\n{value} {trend_emoji}",
        })
    
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*📊 {title}*",
            },
        },
        {
            "type": "section",
            "fields": fields,
        },
    ]


def _format_confidence_bar(confidence: float) -> str:
    """
    Create a visual confidence bar using block characters.
    
    Args:
        confidence: Confidence score between 0.0 and 1.0
        
    Returns:
        Unicode bar representation
    """
    filled = int(confidence * 10)
    empty = 10 - filled
    return "█" * filled + "░" * empty
