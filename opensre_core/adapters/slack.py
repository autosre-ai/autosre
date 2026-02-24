"""
OpenSRE Slack Adapter — Interactive incident response in Slack
"""

import json
from typing import Optional
from dataclasses import dataclass
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from opensre_core.config import settings


@dataclass
class SlackMessage:
    """Represents a Slack message with blocks."""
    channel: str
    blocks: list
    text: str  # Fallback text


class SlackAdapter:
    """
    Slack integration for OpenSRE.
    
    Sends investigation results with interactive buttons for:
    - Approving recommended actions
    - Requesting more investigation
    - Dismissing alerts
    """
    
    def __init__(self):
        self.client = WebClient(token=settings.slack_bot_token)
        self.channel = settings.slack_channel
    
    async def send_investigation(self, result) -> Optional[str]:
        """
        Send an investigation result to Slack with interactive buttons.
        
        Returns the message timestamp (ts) for updates.
        """
        blocks = self._build_investigation_blocks(result)
        
        try:
            response = self.client.chat_postMessage(
                channel=self.channel,
                blocks=blocks,
                text=f"🔍 OpenSRE: {result.alert_name or 'Investigation Complete'}",
            )
            return response["ts"]
        except SlackApiError as e:
            print(f"Slack error: {e.response['error']}")
            return None
    
    def _build_investigation_blocks(self, result) -> list:
        """Build Slack Block Kit blocks for an investigation result."""
        
        # Risk emoji mapping
        risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}
        
        blocks = [
            # Header
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🔍 OpenSRE Analysis",
                    "emoji": True
                }
            },
            # Alert info
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Alert:*\n{result.alert_name or 'Manual Investigation'}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Time:*\n{result.timestamp}"
                    }
                ]
            },
            {"type": "divider"},
            
            # What was found
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*📊 What I found:*"
                }
            },
        ]
        
        # Add observations as bullet points
        observations_text = "\n".join(f"• {obs.summary}" for obs in result.observations[:5])
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": observations_text
            }
        })
        
        # Root cause section
        confidence_bar = "█" * int(result.confidence * 10) + "░" * (10 - int(result.confidence * 10))
        blocks.extend([
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🎯 Root Cause* (confidence: {result.confidence:.0%})\n{confidence_bar}\n\n{result.root_cause}"
                }
            }
        ])
        
        # Contributing factors if present
        if result.contributing_factors:
            factors_text = "\n".join(f"• {f}" for f in result.contributing_factors[:3])
            blocks.append({
                "type": "context",
                "elements": [{
                    "type": "mrkdwn",
                    "text": f"*Contributing factors:* {factors_text}"
                }]
            })
        
        # Recommended action (primary)
        if result.actions:
            primary = result.actions[0]
            blocks.extend([
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*✅ Recommended Action:*\n{risk_emoji.get(primary.risk, '⚪')} {primary.description}"
                    }
                }
            ])
            
            # Command preview (collapsible via context block)
            if primary.command:
                blocks.append({
                    "type": "context",
                    "elements": [{
                        "type": "mrkdwn",
                        "text": f"```{primary.command}```"
                    }]
                })
        
        # Interactive buttons
        buttons = []
        
        if result.actions:
            buttons.append({
                "type": "button",
                "text": {"type": "plain_text", "text": "✅ Approve", "emoji": True},
                "style": "primary",
                "action_id": "approve_action",
                "value": json.dumps({
                    "action_id": result.actions[0].id,
                    "investigation_id": result.id,
                })
            })
        
        buttons.extend([
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "🔍 Investigate More", "emoji": True},
                "action_id": "investigate_more",
                "value": json.dumps({"investigation_id": result.id})
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "❌ Dismiss", "emoji": True},
                "style": "danger",
                "action_id": "dismiss",
                "value": json.dumps({"investigation_id": result.id})
            }
        ])
        
        blocks.append({
            "type": "actions",
            "elements": buttons
        })
        
        # Footer
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f"🤖 OpenSRE v{settings.version} • Investigation #{result.id[:8]}"
            }]
        })
        
        return blocks
    
    async def update_message(self, channel: str, ts: str, text: str, blocks: list = None):
        """Update an existing Slack message."""
        try:
            self.client.chat_update(
                channel=channel,
                ts=ts,
                text=text,
                blocks=blocks,
            )
        except SlackApiError as e:
            print(f"Slack update error: {e.response['error']}")
    
    async def send_action_result(self, channel: str, thread_ts: str, action, success: bool):
        """Send action execution result as a thread reply."""
        
        if success:
            text = f"✅ *Action completed successfully*\n```{action.command}```"
            color = "good"
        else:
            text = f"❌ *Action failed*\n```{action.error}```"
            color = "danger"
        
        try:
            self.client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                attachments=[{
                    "color": color,
                    "blocks": [{
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": text}
                    }]
                }]
            )
        except SlackApiError as e:
            print(f"Slack error: {e.response['error']}")
    
    async def handle_interaction(self, payload: dict):
        """
        Handle Slack interactive component callbacks.
        
        Called when user clicks Approve/Investigate/Dismiss buttons.
        """
        action = payload.get("actions", [{}])[0]
        action_id = action.get("action_id")
        value = json.loads(action.get("value", "{}"))
        user = payload.get("user", {}).get("name", "unknown")
        channel = payload.get("channel", {}).get("id")
        message_ts = payload.get("message", {}).get("ts")
        
        if action_id == "approve_action":
            # Execute the approved action
            from opensre_core.agents.act import Actor
            actor = Actor()
            
            result = await actor.execute(value["action_id"])
            
            # Update original message
            await self.update_message(
                channel=channel,
                ts=message_ts,
                text=f"✅ Action approved by @{user}",
                blocks=self._build_approved_blocks(value, user)
            )
            
            # Send result in thread
            await self.send_action_result(channel, message_ts, result, result.success)
            
        elif action_id == "investigate_more":
            # Trigger deeper investigation
            await self.update_message(
                channel=channel,
                ts=message_ts,
                text=f"🔍 Further investigation requested by @{user}",
            )
            # TODO: Trigger orchestrator.investigate_deeper()
            
        elif action_id == "dismiss":
            await self.update_message(
                channel=channel,
                ts=message_ts,
                text=f"❌ Dismissed by @{user}",
                blocks=self._build_dismissed_blocks(user)
            )
    
    def _build_approved_blocks(self, value: dict, user: str) -> list:
        """Build blocks for an approved action message."""
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"✅ *Action approved by @{user}*\n\nExecuting remediation..."
                }
            },
            {
                "type": "context",
                "elements": [{
                    "type": "mrkdwn",
                    "text": f"Action ID: {value.get('action_id', 'unknown')[:8]}"
                }]
            }
        ]
    
    def _build_dismissed_blocks(self, user: str) -> list:
        """Build blocks for a dismissed alert message."""
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"❌ *Alert dismissed by @{user}*"
                }
            }
        ]


# Webhook handler for Slack events
async def handle_slack_event(request_body: dict):
    """Handle incoming Slack events (URL verification, interactions)."""
    
    # URL verification challenge
    if request_body.get("type") == "url_verification":
        return {"challenge": request_body.get("challenge")}
    
    # Interactive component callback
    if request_body.get("type") == "block_actions":
        adapter = SlackAdapter()
        await adapter.handle_interaction(request_body)
        return {"ok": True}
    
    return {"ok": True}
