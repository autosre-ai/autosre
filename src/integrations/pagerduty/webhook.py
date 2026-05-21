"""PagerDuty webhook handler for AutoSRE.

Handles PagerDuty V3 webhook events and converts them to AutoSRE investigations.
See: https://developer.pagerduty.com/docs/webhooks/v3-overview/
"""

import hashlib
import hmac
import logging
from datetime import datetime
from typing import Any

from .models import (
    Incident,
    IncidentStatus,
    PagerDutyEvent,
    WebhookEvent,
    WebhookEventType,
    WebhookPayload,
)

logger = logging.getLogger(__name__)


class WebhookVerificationError(Exception):
    """Webhook signature verification failed."""
    pass


class PagerDutyWebhook:
    """Handler for PagerDuty V3 webhook events.
    
    Usage:
        handler = PagerDutyWebhook(
            signing_secret="your-secret",
            investigation_callback=start_investigation,
        )
        
        # In your FastAPI route:
        @router.post("/webhooks/pagerduty")
        async def webhook(request: Request):
            body = await request.body()
            signature = request.headers.get("X-PagerDuty-Signature")
            events = handler.verify_and_parse(body, signature)
            await handler.handle_events(events)
    """
    
    def __init__(
        self,
        signing_secret: str | None = None,
        investigation_callback: Any | None = None,
        resolution_callback: Any | None = None,
    ):
        """Initialize webhook handler.
        
        Args:
            signing_secret: PagerDuty webhook signing secret for verification
            investigation_callback: Async callback for starting investigations
            resolution_callback: Async callback for storing resolutions
        """
        self.signing_secret = signing_secret
        self.investigation_callback = investigation_callback
        self.resolution_callback = resolution_callback
    
    def verify_signature(self, payload: bytes, signature: str | None) -> bool:
        """Verify webhook signature.
        
        Args:
            payload: Raw request body
            signature: X-PagerDuty-Signature header value
            
        Returns:
            True if signature is valid
            
        Raises:
            WebhookVerificationError: If verification fails
        """
        if not self.signing_secret:
            logger.warning("No signing secret configured, skipping verification")
            return True
        
        if not signature:
            raise WebhookVerificationError("Missing signature header")
        
        # PagerDuty V3 uses: v1=<hmac-sha256-hex>
        if not signature.startswith("v1="):
            raise WebhookVerificationError(f"Invalid signature format: {signature[:20]}")
        
        expected_sig = signature[3:]  # Remove "v1=" prefix
        
        computed_sig = hmac.new(
            self.signing_secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
        
        if not hmac.compare_digest(computed_sig, expected_sig):
            raise WebhookVerificationError("Signature mismatch")
        
        return True
    
    def parse_payload(self, payload: dict[str, Any]) -> list[WebhookEvent]:
        """Parse webhook payload into events.
        
        Args:
            payload: Parsed JSON payload
            
        Returns:
            List of WebhookEvent objects
        """
        # V3 webhooks send an array of events
        if isinstance(payload, list):
            events = []
            for item in payload:
                try:
                    event = WebhookEvent.model_validate(item)
                    events.append(event)
                except Exception as e:
                    logger.warning(f"Failed to parse webhook event: {e}")
            return events
        
        # Single event (wrapped or unwrapped)
        if "event" in payload:
            try:
                return [WebhookEvent.model_validate(payload)]
            except Exception as e:
                logger.warning(f"Failed to parse webhook event: {e}")
                return []
        
        # Legacy V2 format fallback
        if "messages" in payload:
            logger.warning("Received V2 webhook format, please upgrade to V3")
            return self._parse_v2_payload(payload)
        
        logger.warning(f"Unknown webhook payload format: {list(payload.keys())}")
        return []
    
    def _parse_v2_payload(self, payload: dict[str, Any]) -> list[WebhookEvent]:
        """Parse legacy V2 webhook payload.
        
        Args:
            payload: V2 webhook payload
            
        Returns:
            List of WebhookEvent objects
        """
        events = []
        for message in payload.get("messages", []):
            try:
                event_type = message.get("event")
                incident = message.get("incident", {})
                
                # Map V2 event types to V3
                event_type_map = {
                    "incident.trigger": WebhookEventType.INCIDENT_TRIGGERED,
                    "incident.acknowledge": WebhookEventType.INCIDENT_ACKNOWLEDGED,
                    "incident.resolve": WebhookEventType.INCIDENT_RESOLVED,
                    "incident.escalate": WebhookEventType.INCIDENT_ESCALATED,
                    "incident.assign": WebhookEventType.INCIDENT_REASSIGNED,
                }
                
                v3_event_type = event_type_map.get(event_type)
                if not v3_event_type:
                    logger.warning(f"Unknown V2 event type: {event_type}")
                    continue
                
                pd_event = PagerDutyEvent(
                    event=v3_event_type,
                    created_on=datetime.fromisoformat(
                        message.get("created_on", datetime.utcnow().isoformat())
                    ),
                    data={"incident": incident},
                    id=message.get("id", ""),
                )
                
                events.append(WebhookEvent(
                    routing_key=payload.get("routing_key"),
                    event=pd_event,
                ))
            except Exception as e:
                logger.warning(f"Failed to parse V2 message: {e}")
        
        return events
    
    def verify_and_parse(
        self,
        body: bytes,
        signature: str | None,
    ) -> list[WebhookEvent]:
        """Verify signature and parse webhook payload.
        
        Args:
            body: Raw request body
            signature: X-PagerDuty-Signature header value
            
        Returns:
            List of WebhookEvent objects
            
        Raises:
            WebhookVerificationError: If signature verification fails
        """
        self.verify_signature(body, signature)
        
        import json
        payload = json.loads(body)
        return self.parse_payload(payload)
    
    async def handle_events(self, events: list[WebhookEvent]) -> list[dict[str, Any]]:
        """Handle multiple webhook events.
        
        Args:
            events: List of WebhookEvent objects
            
        Returns:
            List of results from handling each event
        """
        results = []
        for event in events:
            try:
                result = await self.handle_event(event)
                results.append(result)
            except Exception as e:
                logger.error(f"Error handling event {event.event.id}: {e}")
                results.append({"event_id": event.event.id, "error": str(e)})
        return results
    
    async def handle_event(self, event: WebhookEvent) -> dict[str, Any]:
        """Handle a single webhook event.
        
        Args:
            event: WebhookEvent object
            
        Returns:
            Result dict with event handling details
        """
        event_type = event.event_type
        event_id = event.event.id
        
        logger.info(f"Handling PagerDuty event: {event_type} ({event_id})")
        
        if event_type == WebhookEventType.INCIDENT_TRIGGERED:
            return await self.handle_incident_trigger(event.event.data)
        
        elif event_type == WebhookEventType.INCIDENT_RESOLVED:
            return await self.handle_incident_resolve(event.event.data)
        
        elif event_type == WebhookEventType.INCIDENT_ACKNOWLEDGED:
            return await self.handle_incident_acknowledge(event.event.data)
        
        elif event_type == WebhookEventType.INCIDENT_ESCALATED:
            return await self.handle_incident_escalate(event.event.data)
        
        elif event_type == WebhookEventType.INCIDENT_REASSIGNED:
            return await self.handle_incident_reassign(event.event.data)
        
        else:
            logger.debug(f"Ignoring event type: {event_type}")
            return {"event_id": event_id, "action": "ignored", "event_type": str(event_type)}
    
    @staticmethod
    def _extract_incident(data: dict[str, Any]) -> Incident | None:
        """Extract incident from event data.
        
        Args:
            data: Event data dict
            
        Returns:
            Incident object or None
        """
        incident_data = data.get("incident")
        if not incident_data:
            return None
        
        try:
            return Incident.model_validate(incident_data)
        except Exception as e:
            logger.warning(f"Failed to parse incident: {e}")
            return None
    
    async def handle_incident_trigger(self, data: dict[str, Any]) -> dict[str, Any]:
        """Handle incident.triggered event.
        
        Starts an AutoSRE investigation for the triggered incident.
        
        Args:
            data: Event data containing incident details
            
        Returns:
            Result dict with investigation details
        """
        incident = self._extract_incident(data)
        if not incident:
            return {"error": "No incident data in event"}
        
        logger.info(
            f"Incident triggered: #{incident.incident_number} - {incident.title} "
            f"(urgency: {incident.urgency}, status: {incident.status})"
        )
        
        # Build investigation context
        investigation_context = {
            "source": "pagerduty",
            "incident_id": incident.id,
            "incident_number": incident.incident_number,
            "title": incident.title,
            "description": incident.description,
            "urgency": incident.urgency.value if incident.urgency else "high",
            "status": incident.status.value if incident.status else "triggered",
            "service": self._extract_service_info(incident),
            "html_url": incident.html_url,
            "created_at": incident.created_at.isoformat() if incident.created_at else None,
            "priority": self._extract_priority(incident),
            "raw_incident": incident.model_dump(mode="json"),
        }
        
        # Start investigation via callback
        if self.investigation_callback:
            try:
                result = await self.investigation_callback(investigation_context)
                return {
                    "action": "investigation_started",
                    "incident_id": incident.id,
                    "incident_number": incident.incident_number,
                    "investigation": result,
                }
            except Exception as e:
                logger.error(f"Failed to start investigation: {e}")
                return {
                    "action": "investigation_failed",
                    "incident_id": incident.id,
                    "error": str(e),
                }
        
        return {
            "action": "investigation_pending",
            "incident_id": incident.id,
            "incident_number": incident.incident_number,
            "context": investigation_context,
        }
    
    async def handle_incident_resolve(self, data: dict[str, Any]) -> dict[str, Any]:
        """Handle incident.resolved event.
        
        Stores resolution information in memory for learning.
        
        Args:
            data: Event data containing resolution details
            
        Returns:
            Result dict
        """
        incident = self._extract_incident(data)
        if not incident:
            return {"error": "No incident data in event"}
        
        logger.info(
            f"Incident resolved: #{incident.incident_number} - {incident.title}"
        )
        
        # Extract resolution details
        resolution_context = {
            "source": "pagerduty",
            "incident_id": incident.id,
            "incident_number": incident.incident_number,
            "title": incident.title,
            "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
            "resolved_by": self._extract_resolver(incident),
            "service": self._extract_service_info(incident),
            "duration_minutes": self._calculate_duration(incident),
        }
        
        # Store resolution via callback
        if self.resolution_callback:
            try:
                await self.resolution_callback(resolution_context)
                return {
                    "action": "resolution_stored",
                    "incident_id": incident.id,
                    "incident_number": incident.incident_number,
                }
            except Exception as e:
                logger.error(f"Failed to store resolution: {e}")
                return {
                    "action": "resolution_store_failed",
                    "incident_id": incident.id,
                    "error": str(e),
                }
        
        return {
            "action": "resolution_noted",
            "incident_id": incident.id,
            "incident_number": incident.incident_number,
            "context": resolution_context,
        }
    
    async def handle_incident_acknowledge(self, data: dict[str, Any]) -> dict[str, Any]:
        """Handle incident.acknowledged event.
        
        Args:
            data: Event data
            
        Returns:
            Result dict
        """
        incident = self._extract_incident(data)
        if not incident:
            return {"error": "No incident data in event"}
        
        logger.info(f"Incident acknowledged: #{incident.incident_number}")
        
        return {
            "action": "acknowledged",
            "incident_id": incident.id,
            "incident_number": incident.incident_number,
        }
    
    async def handle_incident_escalate(self, data: dict[str, Any]) -> dict[str, Any]:
        """Handle incident.escalated event.
        
        Args:
            data: Event data
            
        Returns:
            Result dict
        """
        incident = self._extract_incident(data)
        if not incident:
            return {"error": "No incident data in event"}
        
        logger.info(f"Incident escalated: #{incident.incident_number}")
        
        return {
            "action": "escalated",
            "incident_id": incident.id,
            "incident_number": incident.incident_number,
        }
    
    async def handle_incident_reassign(self, data: dict[str, Any]) -> dict[str, Any]:
        """Handle incident.reassigned event.
        
        Args:
            data: Event data
            
        Returns:
            Result dict
        """
        incident = self._extract_incident(data)
        if not incident:
            return {"error": "No incident data in event"}
        
        logger.info(f"Incident reassigned: #{incident.incident_number}")
        
        return {
            "action": "reassigned",
            "incident_id": incident.id,
            "incident_number": incident.incident_number,
            "assignments": [
                {"user_id": uid} for uid in incident.assigned_users
            ],
        }
    
    @staticmethod
    def _extract_service_info(incident: Incident) -> dict[str, Any] | None:
        """Extract service information from incident.
        
        Args:
            incident: Incident object
            
        Returns:
            Service info dict or None
        """
        if not incident.service:
            return None
        
        if isinstance(incident.service, dict):
            return {
                "id": incident.service.get("id"),
                "name": incident.service.get("name"),
                "html_url": incident.service.get("html_url"),
            }
        
        return {
            "id": incident.service.id,
            "name": incident.service.name,
            "html_url": incident.service.html_url,
        }
    
    @staticmethod
    def _extract_priority(incident: Incident) -> int:
        """Extract priority as integer (1-5).
        
        Args:
            incident: Incident object
            
        Returns:
            Priority integer (1 = highest)
        """
        if incident.priority:
            # Try to extract P1, P2, etc. from name
            name = incident.priority.name or ""
            if name.startswith("P") and len(name) >= 2:
                try:
                    return int(name[1])
                except ValueError:
                    pass
            
            # Use order if available
            if incident.priority.order is not None:
                return incident.priority.order + 1
        
        # Default based on urgency
        if incident.urgency == "high":
            return 2
        return 4
    
    @staticmethod
    def _extract_resolver(incident: Incident) -> dict[str, Any] | None:
        """Extract resolver information from incident.
        
        Args:
            incident: Incident object
            
        Returns:
            Resolver info dict or None
        """
        if not incident.last_status_change_by:
            return None
        
        resolver = incident.last_status_change_by
        if isinstance(resolver, dict):
            return {
                "id": resolver.get("id"),
                "name": resolver.get("name"),
                "email": resolver.get("email"),
            }
        
        return {
            "id": resolver.id,
            "name": resolver.name,
            "email": resolver.email,
        }
    
    @staticmethod
    def _calculate_duration(incident: Incident) -> int | None:
        """Calculate incident duration in minutes.
        
        Args:
            incident: Incident object
            
        Returns:
            Duration in minutes or None
        """
        if not incident.created_at or not incident.resolved_at:
            return None
        
        delta = incident.resolved_at - incident.created_at
        return int(delta.total_seconds() / 60)
