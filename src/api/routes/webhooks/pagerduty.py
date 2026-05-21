"""PagerDuty webhook endpoint for AutoSRE API.

Receives PagerDuty V3 webhook events and triggers investigations.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from integrations.pagerduty import PagerDutyWebhook
from integrations.pagerduty.webhook import WebhookVerificationError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])


class WebhookResponse(BaseModel):
    """Response for webhook events."""
    status: str = Field(..., description="Processing status")
    events_processed: int = Field(..., description="Number of events processed")
    results: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Results for each event"
    )


class WebhookConfig(BaseModel):
    """PagerDuty webhook configuration."""
    signing_secret: str | None = None
    enabled: bool = True


# Webhook handler instance - configured at startup
_webhook_handler: PagerDutyWebhook | None = None


def get_webhook_handler() -> PagerDutyWebhook:
    """Get the configured webhook handler."""
    global _webhook_handler
    if _webhook_handler is None:
        # Create a default handler - should be configured at app startup
        _webhook_handler = PagerDutyWebhook()
    return _webhook_handler


def configure_webhook_handler(
    signing_secret: str | None = None,
    investigation_callback: Any | None = None,
    resolution_callback: Any | None = None,
) -> PagerDutyWebhook:
    """Configure the webhook handler.
    
    Call this at application startup to configure the handler.
    
    Args:
        signing_secret: PagerDuty webhook signing secret
        investigation_callback: Async function to start investigations
        resolution_callback: Async function to store resolutions
        
    Returns:
        Configured PagerDutyWebhook instance
    """
    global _webhook_handler
    _webhook_handler = PagerDutyWebhook(
        signing_secret=signing_secret,
        investigation_callback=investigation_callback,
        resolution_callback=resolution_callback,
    )
    return _webhook_handler


@router.post(
    "/webhooks/pagerduty",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
    summary="PagerDuty Webhook",
    description="Receive PagerDuty V3 webhook events",
)
async def pagerduty_webhook(
    request: Request,
    x_pagerduty_signature: str | None = Header(
        default=None,
        alias="X-PagerDuty-Signature",
        description="Webhook signature for verification",
    ),
    handler: PagerDutyWebhook = Depends(get_webhook_handler),
) -> WebhookResponse:
    """Handle incoming PagerDuty webhook events.
    
    This endpoint receives PagerDuty V3 webhook events and processes them
    to trigger AutoSRE investigations.
    
    **Event Types Handled:**
    - `incident.triggered` - Starts a new investigation
    - `incident.resolved` - Stores resolution for learning
    - `incident.acknowledged` - Logged for timeline
    - `incident.escalated` - Logged for timeline
    - `incident.reassigned` - Logged for timeline
    
    **Webhook Configuration:**
    1. In PagerDuty, go to Service → Integrations → Add Extension
    2. Select "Generic V3 Webhooks"
    3. Set the webhook URL to this endpoint
    4. Copy the signing secret and configure it in AutoSRE
    
    **Signature Verification:**
    If a signing secret is configured, the `X-PagerDuty-Signature` header
    must be present and valid. The signature uses HMAC-SHA256.
    """
    # Read raw body for signature verification
    body = await request.body()
    
    if not body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty request body",
        )
    
    try:
        # Verify signature and parse events
        events = handler.verify_and_parse(body, x_pagerduty_signature)
    except WebhookVerificationError as e:
        logger.warning(f"Webhook verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Signature verification failed: {e}",
        )
    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid webhook payload: {e}",
        )
    
    if not events:
        return WebhookResponse(
            status="ok",
            events_processed=0,
            results=[],
        )
    
    # Process events
    try:
        results = await handler.handle_events(events)
    except Exception as e:
        logger.error(f"Error processing webhook events: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing events: {e}",
        )
    
    return WebhookResponse(
        status="ok",
        events_processed=len(events),
        results=results,
    )


@router.get(
    "/webhooks/pagerduty/health",
    status_code=status.HTTP_200_OK,
    summary="PagerDuty Webhook Health",
    description="Health check for PagerDuty webhook endpoint",
)
async def pagerduty_webhook_health() -> dict[str, Any]:
    """Health check for PagerDuty webhook endpoint.
    
    Returns configuration status (without secrets).
    """
    handler = get_webhook_handler()
    return {
        "status": "healthy",
        "signature_verification": handler.signing_secret is not None,
        "investigation_callback": handler.investigation_callback is not None,
        "resolution_callback": handler.resolution_callback is not None,
    }
