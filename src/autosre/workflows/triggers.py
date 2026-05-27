"""
Workflow Triggers

Event-based triggers that initiate workflow execution:
- AlertTrigger: Triggered by alerts (Prometheus, PagerDuty, etc.)
- ScheduleTrigger: Cron-based scheduled execution
- WebhookTrigger: HTTP webhook-triggered workflows
- ManualTrigger: Manually triggered workflows
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union
import asyncio
import hashlib
import re

try:
    from croniter import croniter
    HAS_CRONITER = True
except ImportError:
    HAS_CRONITER = False
    croniter = None  # type: ignore


class TriggerType(str, Enum):
    """Types of workflow triggers."""
    ALERT = "alert"
    SCHEDULE = "schedule"
    WEBHOOK = "webhook"
    MANUAL = "manual"
    EVENT = "event"


@dataclass
class TriggerEvent:
    """
    Event that triggers a workflow execution.
    
    Contains all context needed to start a workflow:
    - Trigger type and source
    - Payload data
    - Metadata
    """
    trigger_type: TriggerType
    trigger_id: str
    payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: Optional[str] = None
    tenant_id: Optional[str] = None
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def event_id(self) -> str:
        """Generate unique event ID."""
        data = f"{self.trigger_type.value}:{self.trigger_id}:{self.timestamp.isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "event_id": self.event_id,
            "trigger_type": self.trigger_type.value,
            "trigger_id": self.trigger_id,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "tenant_id": self.tenant_id,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
        }


class Trigger(ABC):
    """Base class for workflow triggers."""

    def __init__(
        self,
        id: str,
        workflow_ids: Optional[List[str]] = None,
        enabled: bool = True,
        description: Optional[str] = None,
        tenant_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.id = id
        self.workflow_ids = workflow_ids or []
        self.enabled = enabled
        self.description = description
        self.tenant_id = tenant_id
        self.metadata = metadata or {}
        self._callbacks: List[Callable[[TriggerEvent], None]] = []

    @property
    @abstractmethod
    def trigger_type(self) -> TriggerType:
        """Return the trigger type."""
        pass

    @abstractmethod
    def matches(self, event_data: Dict[str, Any]) -> bool:
        """Check if the trigger matches the given event data."""
        pass

    def register_callback(self, callback: Callable[[TriggerEvent], None]) -> None:
        """Register a callback for when this trigger fires."""
        self._callbacks.append(callback)

    def fire(self, payload: Dict[str, Any], **kwargs) -> TriggerEvent:
        """Fire the trigger with the given payload."""
        event = TriggerEvent(
            trigger_type=self.trigger_type,
            trigger_id=self.id,
            payload=payload,
            tenant_id=self.tenant_id,
            **kwargs,
        )
        
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception:
                pass  # Don't let callback errors break trigger
        
        return event

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "type": self.trigger_type.value,
            "workflow_ids": self.workflow_ids,
            "enabled": self.enabled,
            "description": self.description,
            "tenant_id": self.tenant_id,
            "metadata": self.metadata,
        }


class AlertTrigger(Trigger):
    """
    Trigger workflows based on alerts.
    
    Supports filtering by:
    - Severity levels
    - Alert names (regex patterns)
    - Labels
    - Source systems
    """

    def __init__(
        self,
        id: str,
        severities: Optional[List[str]] = None,
        alert_names: Optional[List[str]] = None,
        labels: Optional[Dict[str, str]] = None,
        sources: Optional[List[str]] = None,
        dedupe_window_seconds: int = 60,
        **kwargs,
    ):
        super().__init__(id, **kwargs)
        self.severities = severities or ["critical", "high"]
        self.alert_names = alert_names or []
        self.labels = labels or {}
        self.sources = sources or []
        self.dedupe_window_seconds = dedupe_window_seconds
        self._recent_alerts: Dict[str, datetime] = {}

    @property
    def trigger_type(self) -> TriggerType:
        return TriggerType.ALERT

    def matches(self, event_data: Dict[str, Any]) -> bool:
        """Check if alert matches trigger criteria."""
        if not self.enabled:
            return False
        
        # Check severity
        severity = event_data.get("severity", "").lower()
        if self.severities and severity not in self.severities:
            return False
        
        # Check alert name
        alert_name = event_data.get("alert_name", event_data.get("name", ""))
        if self.alert_names:
            matches_name = any(
                re.match(pattern, alert_name, re.IGNORECASE)
                for pattern in self.alert_names
            )
            if not matches_name:
                return False
        
        # Check labels
        alert_labels = event_data.get("labels", {})
        for key, value in self.labels.items():
            if alert_labels.get(key) != value:
                return False
        
        # Check source
        source = event_data.get("source", "")
        if self.sources and source not in self.sources:
            return False
        
        # Dedupe check
        alert_fingerprint = self._get_fingerprint(event_data)
        now = datetime.now(timezone.utc)
        
        if alert_fingerprint in self._recent_alerts:
            last_seen = self._recent_alerts[alert_fingerprint]
            if (now - last_seen).total_seconds() < self.dedupe_window_seconds:
                return False
        
        self._recent_alerts[alert_fingerprint] = now
        self._cleanup_recent_alerts()
        
        return True

    def _get_fingerprint(self, event_data: Dict[str, Any]) -> str:
        """Generate fingerprint for deduplication."""
        parts = [
            event_data.get("alert_name", ""),
            event_data.get("severity", ""),
            str(sorted(event_data.get("labels", {}).items())),
        ]
        return hashlib.md5(":".join(parts).encode()).hexdigest()

    def _cleanup_recent_alerts(self) -> None:
        """Remove expired entries from recent alerts."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=self.dedupe_window_seconds * 2)
        self._recent_alerts = {
            fp: ts for fp, ts in self._recent_alerts.items()
            if ts > cutoff
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        data = super().to_dict()
        data.update({
            "severities": self.severities,
            "alert_names": self.alert_names,
            "labels": self.labels,
            "sources": self.sources,
            "dedupe_window_seconds": self.dedupe_window_seconds,
        })
        return data


class ScheduleTrigger(Trigger):
    """
    Trigger workflows on a schedule (cron-based).
    
    Supports:
    - Cron expressions
    - Timezone awareness
    - Catch-up for missed runs
    """

    def __init__(
        self,
        id: str,
        cron: str,
        timezone: str = "UTC",
        catch_up: bool = False,
        max_catch_up_runs: int = 5,
        **kwargs,
    ):
        super().__init__(id, **kwargs)
        self.cron = cron
        self.timezone = timezone
        self.catch_up = catch_up
        self.max_catch_up_runs = max_catch_up_runs
        self._last_run: Optional[datetime] = None
        self._validate_cron()

    def _validate_cron(self) -> None:
        """Validate cron expression."""
        try:
            croniter(self.cron)
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid cron expression '{self.cron}': {e}")

    @property
    def trigger_type(self) -> TriggerType:
        return TriggerType.SCHEDULE

    @property
    def next_run(self) -> datetime:
        """Calculate next scheduled run time."""
        base = self._last_run or datetime.now(timezone.utc)
        cron = croniter(self.cron, base)
        return cron.get_next(datetime)

    @property
    def previous_run(self) -> datetime:
        """Calculate previous scheduled run time."""
        cron = croniter(self.cron, datetime.now(timezone.utc))
        return cron.get_prev(datetime)

    def matches(self, event_data: Dict[str, Any]) -> bool:
        """Check if it's time to trigger (used for manual checks)."""
        if not self.enabled:
            return False
        
        now = datetime.now(timezone.utc)
        
        if self._last_run is None:
            # First run - check if we're at a scheduled time
            prev = self.previous_run
            return (now - prev).total_seconds() < 60
        
        # Check if next scheduled time has passed
        return now >= self.next_run

    def should_run_now(self) -> bool:
        """Check if the trigger should fire now."""
        return self.matches({})

    def mark_run(self) -> None:
        """Mark that the trigger has run."""
        self._last_run = datetime.now(timezone.utc)

    def get_missed_runs(self) -> List[datetime]:
        """Get list of missed run times for catch-up."""
        if not self.catch_up or self._last_run is None:
            return []
        
        missed = []
        cron = croniter(self.cron, self._last_run)
        now = datetime.now(timezone.utc)
        
        while len(missed) < self.max_catch_up_runs:
            next_time = cron.get_next(datetime)
            if next_time >= now:
                break
            missed.append(next_time)
        
        return missed

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        data = super().to_dict()
        data.update({
            "cron": self.cron,
            "timezone": self.timezone,
            "catch_up": self.catch_up,
            "max_catch_up_runs": self.max_catch_up_runs,
            "next_run": self.next_run.isoformat() if self.enabled else None,
        })
        return data


class WebhookTrigger(Trigger):
    """
    Trigger workflows via HTTP webhooks.
    
    Supports:
    - Path matching
    - Method filtering
    - Header/query parameter validation
    - Payload schema validation
    - Authentication (API keys, signatures)
    """

    def __init__(
        self,
        id: str,
        path: str,
        methods: Optional[List[str]] = None,
        required_headers: Optional[Dict[str, str]] = None,
        api_key: Optional[str] = None,
        validate_signature: bool = False,
        signature_header: str = "X-Signature",
        signature_secret: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(id, **kwargs)
        self.path = path
        self.methods = methods or ["POST"]
        self.required_headers = required_headers or {}
        self.api_key = api_key
        self.validate_signature = validate_signature
        self.signature_header = signature_header
        self.signature_secret = signature_secret

    @property
    def trigger_type(self) -> TriggerType:
        return TriggerType.WEBHOOK

    @property
    def endpoint(self) -> str:
        """Get the webhook endpoint path."""
        return f"/api/v1/webhooks/{self.id}" if not self.path.startswith("/") else self.path

    def matches(self, event_data: Dict[str, Any]) -> bool:
        """Check if webhook request matches trigger criteria."""
        if not self.enabled:
            return False
        
        # Check method
        method = event_data.get("method", "POST").upper()
        if method not in [m.upper() for m in self.methods]:
            return False
        
        # Check path
        request_path = event_data.get("path", "")
        if not self._path_matches(request_path):
            return False
        
        # Check required headers
        headers = event_data.get("headers", {})
        for key, value in self.required_headers.items():
            if headers.get(key) != value:
                return False
        
        # Check API key if configured
        if self.api_key:
            auth_header = headers.get("Authorization", "")
            if not auth_header.endswith(self.api_key):
                return False
        
        # Check signature if configured
        if self.validate_signature:
            signature = headers.get(self.signature_header, "")
            body = event_data.get("body", "")
            if not self._verify_signature(body, signature):
                return False
        
        return True

    def _path_matches(self, request_path: str) -> bool:
        """Check if request path matches trigger path."""
        # Simple path matching with wildcards
        pattern = self.path.replace("*", ".*")
        return bool(re.match(f"^{pattern}$", request_path))

    def _verify_signature(self, body: str, signature: str) -> bool:
        """Verify request signature."""
        if not self.signature_secret:
            return True
        
        import hmac
        expected = hmac.new(
            self.signature_secret.encode(),
            body.encode(),
            hashlib.sha256,
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        data = super().to_dict()
        data.update({
            "path": self.path,
            "endpoint": self.endpoint,
            "methods": self.methods,
            "required_headers": self.required_headers,
            "has_api_key": bool(self.api_key),
            "validate_signature": self.validate_signature,
        })
        return data


class ManualTrigger(Trigger):
    """
    Manual trigger for workflows that are started by users.
    
    Supports:
    - Required inputs validation
    - User permissions
    - Confirmation requirements
    """

    def __init__(
        self,
        id: str,
        required_inputs: Optional[List[str]] = None,
        allowed_users: Optional[List[str]] = None,
        allowed_roles: Optional[List[str]] = None,
        require_confirmation: bool = False,
        confirmation_message: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(id, **kwargs)
        self.required_inputs = required_inputs or []
        self.allowed_users = allowed_users or []
        self.allowed_roles = allowed_roles or []
        self.require_confirmation = require_confirmation
        self.confirmation_message = confirmation_message

    @property
    def trigger_type(self) -> TriggerType:
        return TriggerType.MANUAL

    def matches(self, event_data: Dict[str, Any]) -> bool:
        """Check if manual trigger request is valid."""
        if not self.enabled:
            return False
        
        # Check required inputs
        inputs = event_data.get("inputs", {})
        for required in self.required_inputs:
            if required not in inputs:
                return False
        
        # Check user permissions
        user = event_data.get("user", "")
        user_roles = event_data.get("roles", [])
        
        if self.allowed_users and user not in self.allowed_users:
            if not any(role in self.allowed_roles for role in user_roles):
                return False
        
        # Check confirmation if required
        if self.require_confirmation:
            confirmed = event_data.get("confirmed", False)
            if not confirmed:
                return False
        
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        data = super().to_dict()
        data.update({
            "required_inputs": self.required_inputs,
            "allowed_users": self.allowed_users,
            "allowed_roles": self.allowed_roles,
            "require_confirmation": self.require_confirmation,
            "confirmation_message": self.confirmation_message,
        })
        return data


class TriggerManager:
    """
    Manages all workflow triggers.
    
    Responsibilities:
    - Trigger registration and discovery
    - Event routing to matching triggers
    - Schedule management
    - Webhook endpoint management
    """

    def __init__(self):
        self._triggers: Dict[str, Trigger] = {}
        self._workflow_triggers: Dict[str, List[str]] = {}  # workflow_id -> trigger_ids
        self._callbacks: List[Callable[[TriggerEvent, List[str]], None]] = []
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None

    def register(self, trigger: Trigger) -> None:
        """Register a trigger."""
        self._triggers[trigger.id] = trigger
        
        # Update workflow -> trigger mapping
        for workflow_id in trigger.workflow_ids:
            if workflow_id not in self._workflow_triggers:
                self._workflow_triggers[workflow_id] = []
            if trigger.id not in self._workflow_triggers[workflow_id]:
                self._workflow_triggers[workflow_id].append(trigger.id)

    def unregister(self, trigger_id: str) -> None:
        """Unregister a trigger."""
        trigger = self._triggers.pop(trigger_id, None)
        if trigger:
            for workflow_id in trigger.workflow_ids:
                if workflow_id in self._workflow_triggers:
                    self._workflow_triggers[workflow_id] = [
                        tid for tid in self._workflow_triggers[workflow_id]
                        if tid != trigger_id
                    ]

    def get(self, trigger_id: str) -> Optional[Trigger]:
        """Get a trigger by ID."""
        return self._triggers.get(trigger_id)

    def list_triggers(
        self,
        trigger_type: Optional[TriggerType] = None,
        workflow_id: Optional[str] = None,
        enabled_only: bool = False,
    ) -> List[Trigger]:
        """List triggers with optional filtering."""
        triggers = list(self._triggers.values())
        
        if trigger_type:
            triggers = [t for t in triggers if t.trigger_type == trigger_type]
        
        if workflow_id:
            trigger_ids = self._workflow_triggers.get(workflow_id, [])
            triggers = [t for t in triggers if t.id in trigger_ids]
        
        if enabled_only:
            triggers = [t for t in triggers if t.enabled]
        
        return triggers

    def get_triggers_for_workflow(self, workflow_id: str) -> List[Trigger]:
        """Get all triggers configured for a workflow."""
        trigger_ids = self._workflow_triggers.get(workflow_id, [])
        return [self._triggers[tid] for tid in trigger_ids if tid in self._triggers]

    def on_trigger(
        self, callback: Callable[[TriggerEvent, List[str]], None]
    ) -> None:
        """Register callback for when any trigger fires."""
        self._callbacks.append(callback)

    async def process_alert(self, alert_data: Dict[str, Any]) -> List[TriggerEvent]:
        """Process an incoming alert and fire matching triggers."""
        events = []
        
        for trigger in self.list_triggers(TriggerType.ALERT, enabled_only=True):
            if trigger.matches(alert_data):
                event = trigger.fire(alert_data, source="alert")
                events.append(event)
                self._notify_callbacks(event, trigger.workflow_ids)
        
        return events

    async def process_webhook(
        self, request_data: Dict[str, Any]
    ) -> Optional[TriggerEvent]:
        """Process an incoming webhook request."""
        for trigger in self.list_triggers(TriggerType.WEBHOOK, enabled_only=True):
            if trigger.matches(request_data):
                payload = request_data.get("body", {})
                if isinstance(payload, str):
                    import json
                    try:
                        payload = json.loads(payload)
                    except json.JSONDecodeError:
                        payload = {"raw": payload}
                
                event = trigger.fire(payload, source="webhook")
                self._notify_callbacks(event, trigger.workflow_ids)
                return event
        
        return None

    async def trigger_manual(
        self, trigger_id: str, inputs: Dict[str, Any], user: str = ""
    ) -> Optional[TriggerEvent]:
        """Manually fire a trigger."""
        trigger = self.get(trigger_id)
        if not trigger:
            return None
        
        event_data = {"inputs": inputs, "user": user, "confirmed": True}
        
        if not trigger.matches(event_data):
            return None
        
        event = trigger.fire(inputs, source="manual")
        self._notify_callbacks(event, trigger.workflow_ids)
        return event

    def _notify_callbacks(
        self, event: TriggerEvent, workflow_ids: List[str]
    ) -> None:
        """Notify registered callbacks of trigger event."""
        for callback in self._callbacks:
            try:
                callback(event, workflow_ids)
            except Exception:
                pass  # Don't let callback errors break trigger processing

    async def start_scheduler(self) -> None:
        """Start the schedule trigger processor."""
        if self._running:
            return
        
        self._running = True
        self._scheduler_task = asyncio.create_task(self._run_scheduler())

    async def stop_scheduler(self) -> None:
        """Stop the schedule trigger processor."""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

    async def _run_scheduler(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                now = datetime.now(timezone.utc)
                
                for trigger in self.list_triggers(TriggerType.SCHEDULE, enabled_only=True):
                    if isinstance(trigger, ScheduleTrigger):
                        if trigger.should_run_now():
                            event = trigger.fire(
                                {"scheduled_time": now.isoformat()},
                                source="schedule",
                            )
                            trigger.mark_run()
                            self._notify_callbacks(event, trigger.workflow_ids)
                
                # Check every 30 seconds
                await asyncio.sleep(30)
                
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(30)  # Continue on errors

    def to_dict(self) -> Dict[str, Any]:
        """Serialize trigger manager state."""
        return {
            "triggers": [t.to_dict() for t in self._triggers.values()],
            "workflow_triggers": self._workflow_triggers,
            "running": self._running,
        }
