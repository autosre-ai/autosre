"""Webhook Routes.

Endpoints for receiving alerts from external systems like Alertmanager and PagerDuty.
"""

import hashlib
import hmac
import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Request, status

logger = logging.getLogger(__name__)

router = APIRouter()


def verify_alertmanager_signature(
    payload: bytes,
    signature: Optional[str],
    secret: str,
) -> bool:
    """Verify Alertmanager webhook signature if configured."""
    if not secret:
        return True  # No signature verification configured
    if not signature:
        return False

    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


def verify_pagerduty_signature(
    payload: bytes,
    signatures: Optional[str],
    secret: str,
) -> bool:
    """Verify PagerDuty webhook signature (v3 format)."""
    if not secret:
        return True  # No signature verification configured
    if not signatures:
        return False

    # PagerDuty sends comma-separated signatures for different versions
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    for sig in signatures.split(","):
        if sig.startswith("v1=") and hmac.compare_digest(sig[3:], expected):
            return True
    return False


@router.post("/alertmanager")
async def alertmanager_webhook(
    request: Request,
    x_alertmanager_signature: Optional[str] = Header(None),
) -> dict[str, Any]:
    """
    Receive alerts from Prometheus Alertmanager.

    Expected payload format:
    {
        "version": "4",
        "groupKey": "...",
        "status": "firing|resolved",
        "receiver": "...",
        "groupLabels": {...},
        "commonLabels": {...},
        "commonAnnotations": {...},
        "externalURL": "...",
        "alerts": [
            {
                "status": "firing|resolved",
                "labels": {...},
                "annotations": {...},
                "startsAt": "...",
                "endsAt": "...",
                "generatorURL": "...",
                "fingerprint": "..."
            }
        ]
    }
    """
    body = await request.body()

    # TODO: Get secret from settings
    webhook_secret = ""  # settings.alertmanager_webhook_secret

    if webhook_secret and not verify_alertmanager_signature(
        body, x_alertmanager_signature, webhook_secret
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON payload: {e}",
        )

    alerts_received = 0
    alerts_created = 0

    for alert in payload.get("alerts", []):
        alerts_received += 1
        try:
            # TODO: Process alert - create/update in database
            # TODO: Trigger auto-investigation if configured
            logger.info(
                "Received Alertmanager alert",
                extra={
                    "fingerprint": alert.get("fingerprint"),
                    "status": alert.get("status"),
                    "alertname": alert.get("labels", {}).get("alertname"),
                },
            )
            alerts_created += 1
        except Exception as e:
            logger.error(f"Failed to process alert: {e}")

    return {
        "status": "ok",
        "received": alerts_received,
        "created": alerts_created,
    }


@router.post("/pagerduty")
async def pagerduty_webhook(
    request: Request,
    x_pagerduty_signature: Optional[str] = Header(None),
) -> dict[str, Any]:
    """
    Receive events from PagerDuty webhooks (v3).

    Expected payload format:
    {
        "event": {
            "id": "...",
            "event_type": "incident.triggered|incident.acknowledged|...",
            "resource_type": "incident",
            "occurred_at": "...",
            "agent": {...},
            "client": {...},
            "data": {
                "id": "...",
                "type": "incident",
                "self": "...",
                "html_url": "...",
                "number": 123,
                "status": "triggered|acknowledged|resolved",
                "title": "...",
                "service": {...},
                "assignments": [...],
                ...
            }
        }
    }
    """
    body = await request.body()

    # TODO: Get secret from settings
    webhook_secret = ""  # settings.pagerduty_webhook_secret

    if webhook_secret and not verify_pagerduty_signature(
        body, x_pagerduty_signature, webhook_secret
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON payload: {e}",
        )

    event = payload.get("event", {})
    event_type = event.get("event_type", "unknown")
    incident_data = event.get("data", {})

    logger.info(
        "Received PagerDuty event",
        extra={
            "event_type": event_type,
            "incident_id": incident_data.get("id"),
            "incident_number": incident_data.get("number"),
        },
    )

    # TODO: Process event based on type
    # - incident.triggered -> Create alert, maybe auto-investigate
    # - incident.acknowledged -> Update alert status
    # - incident.resolved -> Mark alert resolved

    return {
        "status": "ok",
        "event_type": event_type,
        "processed": True,
    }


@router.post("/generic")
async def generic_webhook(
    request: Request,
    x_webhook_secret: Optional[str] = Header(None),
) -> dict[str, Any]:
    """
    Generic webhook endpoint for custom integrations.

    Expected minimum payload:
    {
        "alertname": "...",
        "severity": "critical|warning|info",
        "summary": "...",
        "description": "...",
        "source": "...",
        "labels": {...},
        "annotations": {...}
    }
    """
    body = await request.body()

    # TODO: Get secret from settings
    expected_secret = ""  # settings.generic_webhook_secret

    if expected_secret and x_webhook_secret != expected_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook secret",
        )

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON payload: {e}",
        )

    # Validate required fields
    required_fields = ["alertname", "severity", "summary"]
    missing_fields = [f for f in required_fields if f not in payload]
    if missing_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required fields: {missing_fields}",
        )

    logger.info(
        "Received generic webhook alert",
        extra={
            "alertname": payload.get("alertname"),
            "severity": payload.get("severity"),
            "source": payload.get("source"),
        },
    )

    # TODO: Create alert from payload

    return {
        "status": "ok",
        "message": "Alert received",
    }
