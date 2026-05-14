"""
AlertManager integration for AutoSRE V2.

Provides async AlertManager API client with support for:
- Alert ingestion and polling
- Silence management
- Alert grouping and routing
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field

from autosre.core.alert import Alert, AlertGroup, AlertStatus
from autosre.utils.config import AlertManagerConfig, get_config
from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class SilenceMatcher(BaseModel):
    """A single matcher for a silence."""

    name: str
    value: str
    is_regex: bool = Field(default=False, alias="isRegex")
    is_equal: bool = Field(default=True, alias="isEqual")


class Silence(BaseModel):
    """An AlertManager silence."""

    id: str | None = None
    matchers: list[SilenceMatcher]
    starts_at: datetime = Field(alias="startsAt")
    ends_at: datetime = Field(alias="endsAt")
    created_by: str = Field(alias="createdBy")
    comment: str
    status: dict[str, Any] | None = None

    class Config:
        populate_by_name = True


class AlertManagerAlert(BaseModel):
    """AlertManager alert format."""

    labels: dict[str, str]
    annotations: dict[str, str] = Field(default_factory=dict)
    starts_at: datetime | None = Field(default=None, alias="startsAt")
    ends_at: datetime | None = Field(default=None, alias="endsAt")
    generator_url: str | None = Field(default=None, alias="generatorURL")
    fingerprint: str | None = None
    status: dict[str, str] | None = None
    receivers: list[dict[str, str]] | None = None

    class Config:
        populate_by_name = True


@dataclass
class AlertStatus:
    """Alert status from AlertManager."""

    state: str
    silenced_by: list[str]
    inhibited_by: list[str]


class AlertManagerClient:
    """
    Async AlertManager client.

    Provides methods for managing alerts and silences.
    """

    def __init__(self, config: AlertManagerConfig | None = None):
        """
        Initialize AlertManager client.

        Args:
            config: AlertManager configuration. Uses global config if not provided.
        """
        self.config = config or get_config().alertmanager
        self._client: httpx.AsyncClient | None = None
        self._polling_task: asyncio.Task | None = None
        self._callbacks: list = []

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.url,
                verify=self.config.verify_ssl,
                timeout=self.config.timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client and stop polling."""
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
            self._polling_task = None

        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_alerts(
        self,
        active: bool = True,
        silenced: bool = False,
        inhibited: bool = False,
        unprocessed: bool = False,
        filter_labels: dict[str, str] | None = None,
        receiver: str | None = None,
    ) -> list[Alert]:
        """
        Get alerts from AlertManager.

        Args:
            active: Include active alerts
            silenced: Include silenced alerts
            inhibited: Include inhibited alerts
            unprocessed: Include unprocessed alerts
            filter_labels: Filter by labels (format: key=value)
            receiver: Filter by receiver name

        Returns:
            List of normalized Alert objects
        """
        client = await self._get_client()

        params: dict[str, Any] = {
            "active": str(active).lower(),
            "silenced": str(silenced).lower(),
            "inhibited": str(inhibited).lower(),
            "unprocessed": str(unprocessed).lower(),
        }

        if filter_labels:
            params["filter"] = [f'{k}="{v}"' for k, v in filter_labels.items()]

        if receiver:
            params["receiver"] = receiver

        try:
            response = await client.get("/api/v2/alerts", params=params)
            response.raise_for_status()

            alerts_data = response.json()
            alerts = []

            for alert_data in alerts_data:
                try:
                    am_alert = AlertManagerAlert(**alert_data)
                    alert = Alert.from_alertmanager({
                        "labels": am_alert.labels,
                        "annotations": am_alert.annotations,
                        "startsAt": am_alert.starts_at.isoformat() if am_alert.starts_at else None,
                        "endsAt": am_alert.ends_at.isoformat() if am_alert.ends_at else None,
                        "fingerprint": am_alert.fingerprint,
                        "status": am_alert.status.get("state", "firing") if am_alert.status else "firing",
                    })
                    alerts.append(alert)
                except Exception as e:
                    logger.warning("Failed to parse alert", error=str(e))

            logger.debug("Retrieved alerts", count=len(alerts))
            return alerts

        except httpx.HTTPStatusError as e:
            logger.error("Failed to get alerts", status_code=e.response.status_code)
            raise
        except Exception as e:
            logger.error("Failed to get alerts", error=str(e))
            raise

    async def get_alert_groups(self) -> list[AlertGroup]:
        """Get grouped alerts from AlertManager."""
        client = await self._get_client()

        try:
            response = await client.get("/api/v2/alerts/groups")
            response.raise_for_status()

            groups_data = response.json()
            groups = []

            for group_data in groups_data:
                alerts = []
                for alert_data in group_data.get("alerts", []):
                    try:
                        alert = Alert.from_alertmanager(alert_data)
                        alerts.append(alert)
                    except Exception as e:
                        logger.warning("Failed to parse grouped alert", error=str(e))

                if alerts:
                    groups.append(AlertGroup(
                        group_key=str(group_data.get("labels", {})),
                        alerts=alerts,
                        common_labels=group_data.get("labels", {}),
                    ))

            return groups

        except Exception as e:
            logger.error("Failed to get alert groups", error=str(e))
            raise

    async def create_silence(
        self,
        matchers: list[dict[str, Any]],
        duration: timedelta | None = None,
        ends_at: datetime | None = None,
        created_by: str = "autosre",
        comment: str = "Created by AutoSRE",
    ) -> str:
        """
        Create a new silence.

        Args:
            matchers: Label matchers [{"name": "key", "value": "val", "isRegex": false}]
            duration: Silence duration (alternative to ends_at)
            ends_at: Silence end time (alternative to duration)
            created_by: Creator identifier
            comment: Silence comment

        Returns:
            Silence ID
        """
        if not ends_at:
            if duration:
                ends_at = datetime.now(timezone.utc) + duration
            else:
                ends_at = datetime.now(timezone.utc) + timedelta(hours=2)

        client = await self._get_client()

        payload = {
            "matchers": matchers,
            "startsAt": datetime.now(timezone.utc).isoformat(),
            "endsAt": ends_at.isoformat(),
            "createdBy": created_by,
            "comment": comment,
        }

        try:
            response = await client.post("/api/v2/silences", json=payload)
            response.raise_for_status()

            result = response.json()
            silence_id = result.get("silenceID", str(uuid4()))

            logger.info(
                "Created silence",
                silence_id=silence_id,
                ends_at=ends_at.isoformat(),
            )

            return silence_id

        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to create silence",
                status_code=e.response.status_code,
                response=e.response.text,
            )
            raise

    async def delete_silence(self, silence_id: str) -> bool:
        """
        Delete (expire) a silence.

        Args:
            silence_id: ID of silence to delete

        Returns:
            True if successful
        """
        client = await self._get_client()

        try:
            response = await client.delete(f"/api/v2/silence/{silence_id}")
            response.raise_for_status()

            logger.info("Deleted silence", silence_id=silence_id)
            return True

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning("Silence not found", silence_id=silence_id)
                return False
            raise

    async def get_silences(
        self,
        filter_labels: dict[str, str] | None = None,
    ) -> list[Silence]:
        """Get active silences."""
        client = await self._get_client()

        params = {}
        if filter_labels:
            params["filter"] = [f'{k}="{v}"' for k, v in filter_labels.items()]

        try:
            response = await client.get("/api/v2/silences", params=params)
            response.raise_for_status()

            silences_data = response.json()
            return [Silence(**s) for s in silences_data]

        except Exception as e:
            logger.error("Failed to get silences", error=str(e))
            raise

    async def silence_alert(
        self,
        alert: Alert,
        duration: timedelta | None = None,
        comment: str | None = None,
        created_by: str = "autosre",
    ) -> str:
        """
        Silence a specific alert.

        Args:
            alert: Alert to silence
            duration: Silence duration (default: 2 hours)
            comment: Silence comment
            created_by: Creator identifier

        Returns:
            Silence ID
        """
        matchers = [
            {"name": k, "value": v, "isRegex": False}
            for k, v in alert.labels.items()
        ]

        return await self.create_silence(
            matchers=matchers,
            duration=duration,
            comment=comment or f"Silenced by AutoSRE: {alert.name}",
            created_by=created_by,
        )

    async def get_status(self) -> dict[str, Any]:
        """Get AlertManager status."""
        client = await self._get_client()

        try:
            response = await client.get("/api/v2/status")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to get status", error=str(e))
            raise

    async def get_receivers(self) -> list[dict[str, Any]]:
        """Get configured receivers."""
        client = await self._get_client()

        try:
            response = await client.get("/api/v2/receivers")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to get receivers", error=str(e))
            raise

    def on_alert(self, callback) -> None:
        """
        Register callback for new alerts.

        The callback will be called with a list of Alert objects
        when new alerts are detected during polling.
        """
        self._callbacks.append(callback)

    async def start_polling(self, interval: float | None = None) -> None:
        """
        Start polling for alerts.

        Args:
            interval: Polling interval in seconds (default: from config)
        """
        if self._polling_task and not self._polling_task.done():
            logger.warning("Polling already started")
            return

        interval = interval or self.config.poll_interval
        self._polling_task = asyncio.create_task(self._poll_loop(interval))
        logger.info("Started alert polling", interval=interval)

    async def _poll_loop(self, interval: float) -> None:
        """Internal polling loop."""
        seen_fingerprints: set[str] = set()

        while True:
            try:
                alerts = await self.get_alerts(active=True)

                # Find new alerts
                new_alerts = []
                current_fingerprints = set()

                for alert in alerts:
                    if alert.fingerprint:
                        current_fingerprints.add(alert.fingerprint)
                        if alert.fingerprint not in seen_fingerprints:
                            new_alerts.append(alert)
                            seen_fingerprints.add(alert.fingerprint)

                # Clean up old fingerprints
                seen_fingerprints = seen_fingerprints & current_fingerprints

                # Notify callbacks
                if new_alerts:
                    logger.info("New alerts detected", count=len(new_alerts))
                    for callback in self._callbacks:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(new_alerts)
                            else:
                                callback(new_alerts)
                        except Exception as e:
                            logger.error("Alert callback error", error=str(e))

            except Exception as e:
                logger.error("Polling error", error=str(e))

            await asyncio.sleep(interval)

    async def check_connection(self) -> bool:
        """Check if AlertManager is reachable."""
        try:
            status = await self.get_status()
            return "cluster" in status
        except Exception as e:
            logger.warning("AlertManager connection check failed", error=str(e))
            return False


# Webhook handler for receiving alerts
class WebhookPayload(BaseModel):
    """AlertManager webhook payload."""

    version: str = "4"
    group_key: str = Field(alias="groupKey")
    truncated_alerts: int = Field(default=0, alias="truncatedAlerts")
    status: str
    receiver: str
    group_labels: dict[str, str] = Field(default_factory=dict, alias="groupLabels")
    common_labels: dict[str, str] = Field(default_factory=dict, alias="commonLabels")
    common_annotations: dict[str, str] = Field(default_factory=dict, alias="commonAnnotations")
    external_url: str = Field(default="", alias="externalURL")
    alerts: list[dict[str, Any]]

    class Config:
        populate_by_name = True


def parse_webhook(payload: dict[str, Any]) -> list[Alert]:
    """
    Parse AlertManager webhook payload into Alert objects.

    Args:
        payload: Raw webhook JSON payload

    Returns:
        List of Alert objects
    """
    try:
        webhook = WebhookPayload(**payload)

        alerts = []
        for alert_data in webhook.alerts:
            try:
                alert = Alert.from_alertmanager(alert_data)
                alerts.append(alert)
            except Exception as e:
                logger.warning("Failed to parse webhook alert", error=str(e))

        logger.debug(
            "Parsed webhook",
            alert_count=len(alerts),
            status=webhook.status,
        )

        return alerts

    except Exception as e:
        logger.error("Failed to parse webhook payload", error=str(e))
        raise


# Module-level convenience
_default_client: AlertManagerClient | None = None


def get_client() -> AlertManagerClient:
    """Get the default AlertManager client."""
    global _default_client
    if _default_client is None:
        _default_client = AlertManagerClient()
    return _default_client
