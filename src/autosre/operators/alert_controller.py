"""
AutoSRE Alert Controller

Kopf-based Kubernetes operator for managing Alert custom resources.
Handles incoming alerts and triggers investigations based on configured policies.

Features:
- Alert deduplication and correlation
- Automatic investigation triggering
- Alert lifecycle management
- Integration with external alerting systems

Usage:
    kopf run -m autosre.operators.alert_controller --standalone
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field

try:
    import kopf
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException
    KOPF_AVAILABLE = True
except ImportError:
    KOPF_AVAILABLE = False
    kopf = None  # type: ignore

logger = logging.getLogger(__name__)

# CRD Configuration
CRD_GROUP = "autosre.io"
CRD_VERSION = "v1alpha1"
ALERT_PLURAL = "alerts"
ALERT_KIND = "Alert"
INVESTIGATION_PLURAL = "investigations"


@dataclass
class AlertContext:
    """Context for alert processing."""
    name: str
    namespace: str
    uid: str
    spec: Dict[str, Any]
    status: Dict[str, Any] = field(default_factory=dict)
    fingerprint: str = ""
    
    def __post_init__(self):
        """Calculate fingerprint if not provided."""
        if not self.fingerprint:
            self.fingerprint = self._calculate_fingerprint()
    
    def _calculate_fingerprint(self) -> str:
        """Calculate unique fingerprint for deduplication."""
        # Create fingerprint from alert characteristics
        fp_data = {
            "alertName": self.spec.get("alertName"),
            "severity": self.spec.get("severity"),
            "labels": self.spec.get("labels", {}),
        }
        fp_str = str(sorted(fp_data.items()))
        return hashlib.sha256(fp_str.encode()).hexdigest()[:16]


class AlertController:
    """
    Controller for managing Alert CRDs.
    
    Handles alert lifecycle, deduplication, correlation,
    and automatic investigation triggering.
    """
    
    def __init__(self):
        self.k8s_client: Optional[client.ApiClient] = None
        self.custom_api: Optional[client.CustomObjectsApi] = None
        self.core_api: Optional[client.CoreV1Api] = None
        self._initialized = False
        
        # In-memory cache for deduplication
        self._alert_cache: Dict[str, datetime] = {}
        self._correlation_groups: Dict[str, Set[str]] = {}
        
    def initialize(self):
        """Initialize Kubernetes clients."""
        if self._initialized:
            return
            
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()
            
        self.k8s_client = client.ApiClient()
        self.custom_api = client.CustomObjectsApi(self.k8s_client)
        self.core_api = client.CoreV1Api(self.k8s_client)
        self._initialized = True
    
    async def process_alert(
        self,
        ctx: AlertContext,
        patch: Any,
    ) -> Dict[str, Any]:
        """
        Process an incoming alert.
        
        Returns:
            Updated status dictionary
        """
        now = datetime.now(timezone.utc).isoformat()
        
        # Initialize status
        status = {
            "state": "Firing",
            "firstSeenAt": now,
            "lastSeenAt": now,
            "firingCount": 1,
            "conditions": [],
        }
        
        # Check for duplicates
        if await self._is_duplicate(ctx):
            return await self._handle_duplicate(ctx, status)
        
        # Add to cache
        self._alert_cache[ctx.fingerprint] = datetime.now(timezone.utc)
        
        # Correlate with other alerts
        correlation_group = await self._correlate_alert(ctx)
        if correlation_group:
            status["correlationGroup"] = correlation_group
        
        # Check investigation policy
        policy = ctx.spec.get("investigationPolicy", {})
        auto_investigate = policy.get("autoInvestigate", True)
        
        if auto_investigate and self._should_investigate(ctx):
            investigation_ref = await self._create_investigation(ctx)
            if investigation_ref:
                status["state"] = "Investigating"
                status["investigationRef"] = investigation_ref
        
        status["conditions"].append({
            "type": "Processed",
            "status": "True",
            "lastTransitionTime": now,
            "reason": "AlertProcessed",
            "message": "Alert has been processed successfully",
        })
        
        return status
    
    async def _is_duplicate(self, ctx: AlertContext) -> bool:
        """Check if this is a duplicate alert."""
        policy = ctx.spec.get("investigationPolicy", {})
        suppress_duplicates = policy.get("suppressDuplicates", True)
        
        if not suppress_duplicates:
            return False
        
        # Check cache
        if ctx.fingerprint in self._alert_cache:
            last_seen = self._alert_cache[ctx.fingerprint]
            suppression_window = policy.get("suppressionWindow", "1h")
            window_minutes = self._parse_duration_minutes(suppression_window)
            
            if datetime.now(timezone.utc) - last_seen < timedelta(minutes=window_minutes):
                return True
        
        return False
    
    async def _handle_duplicate(
        self,
        ctx: AlertContext,
        status: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle a duplicate alert."""
        now = datetime.now(timezone.utc).isoformat()
        
        status["lastSeenAt"] = now
        status["firingCount"] = status.get("firingCount", 1) + 1
        
        # Update cache
        self._alert_cache[ctx.fingerprint] = datetime.now(timezone.utc)
        
        # Find existing investigation
        existing_investigation = await self._find_existing_investigation(ctx)
        if existing_investigation:
            status["investigationRef"] = existing_investigation
            status["state"] = "Investigating"
        
        status["conditions"].append({
            "type": "Duplicate",
            "status": "True",
            "lastTransitionTime": now,
            "reason": "DuplicateAlert",
            "message": f"Duplicate alert suppressed. Total occurrences: {status['firingCount']}",
        })
        
        return status
    
    async def _correlate_alert(self, ctx: AlertContext) -> Optional[str]:
        """Correlate alert with other related alerts."""
        # Get routing info for correlation
        routing = ctx.spec.get("routing", {})
        service = routing.get("service")
        
        if not service:
            return None
        
        # Create or find correlation group based on service
        group_key = f"{service}-{ctx.spec.get('severity', 'unknown')}"
        
        if group_key not in self._correlation_groups:
            self._correlation_groups[group_key] = set()
        
        self._correlation_groups[group_key].add(ctx.uid)
        
        # Return group ID if there are multiple alerts
        if len(self._correlation_groups[group_key]) > 1:
            return hashlib.sha256(group_key.encode()).hexdigest()[:12]
        
        return None
    
    def _should_investigate(self, ctx: AlertContext) -> bool:
        """Determine if this alert should trigger an investigation."""
        policy = ctx.spec.get("investigationPolicy", {})
        min_severity = policy.get("minSeverityForInvestigation", "medium")
        
        severity_order = ["info", "low", "medium", "high", "critical"]
        alert_severity = ctx.spec.get("severity", "medium")
        
        try:
            alert_idx = severity_order.index(alert_severity)
            min_idx = severity_order.index(min_severity)
            return alert_idx >= min_idx
        except ValueError:
            return True
    
    async def _create_investigation(
        self,
        ctx: AlertContext,
    ) -> Optional[Dict[str, str]]:
        """Create an Investigation resource for this alert."""
        self.initialize()
        
        policy = ctx.spec.get("investigationPolicy", {})
        
        # Build investigation spec
        investigation = {
            "apiVersion": f"{CRD_GROUP}/{CRD_VERSION}",
            "kind": "Investigation",
            "metadata": {
                "name": f"inv-{ctx.name[:40]}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "namespace": ctx.namespace,
                "labels": {
                    "autosre.io/alert": ctx.name,
                    "autosre.io/severity": ctx.spec.get("severity", "medium"),
                },
                "ownerReferences": [
                    {
                        "apiVersion": f"{CRD_GROUP}/{CRD_VERSION}",
                        "kind": ALERT_KIND,
                        "name": ctx.name,
                        "uid": ctx.uid,
                        "blockOwnerDeletion": True,
                    }
                ],
            },
            "spec": {
                "description": self._build_investigation_description(ctx),
                "severity": ctx.spec.get("severity", "medium"),
                "alertRef": {
                    "name": ctx.name,
                    "namespace": ctx.namespace,
                },
                "targetResources": ctx.spec.get("affectedResources", []),
                "analysisConfig": {
                    "model": "gpt-4",
                    "depth": self._get_analysis_depth(ctx),
                    "enableRemediation": False,  # Require approval by default
                },
            },
        }
        
        # Add runbook reference if specified
        runbook_ref = policy.get("runbookRef")
        if runbook_ref:
            investigation["spec"]["runbookRef"] = runbook_ref
        
        try:
            result = self.custom_api.create_namespaced_custom_object(
                group=CRD_GROUP,
                version=CRD_VERSION,
                namespace=ctx.namespace,
                plural=INVESTIGATION_PLURAL,
                body=investigation,
            )
            
            logger.info(
                f"Created investigation {result['metadata']['name']} "
                f"for alert {ctx.namespace}/{ctx.name}"
            )
            
            return {
                "name": result["metadata"]["name"],
                "namespace": result["metadata"]["namespace"],
                "uid": result["metadata"]["uid"],
            }
            
        except ApiException as e:
            logger.error(f"Failed to create investigation: {e}")
            return None
    
    def _build_investigation_description(self, ctx: AlertContext) -> str:
        """Build investigation description from alert."""
        parts = [
            f"Alert: {ctx.spec.get('alertName', 'Unknown')}",
            f"Severity: {ctx.spec.get('severity', 'medium')}",
        ]
        
        if ctx.spec.get("description"):
            parts.append(f"\n{ctx.spec['description']}")
        
        if ctx.spec.get("summary"):
            parts.append(f"\nSummary: {ctx.spec['summary']}")
        
        # Add metrics info
        metrics = ctx.spec.get("metrics", [])
        if metrics:
            parts.append("\nMetrics:")
            for m in metrics[:5]:
                parts.append(f"  - {m.get('name')}: {m.get('value')} (threshold: {m.get('threshold')})")
        
        return "\n".join(parts)
    
    def _get_analysis_depth(self, ctx: AlertContext) -> str:
        """Determine analysis depth based on severity."""
        severity = ctx.spec.get("severity", "medium")
        
        if severity == "critical":
            return "deep"
        elif severity == "high":
            return "standard"
        else:
            return "quick"
    
    async def _find_existing_investigation(
        self,
        ctx: AlertContext,
    ) -> Optional[Dict[str, str]]:
        """Find an existing investigation for this alert."""
        self.initialize()
        
        try:
            investigations = self.custom_api.list_namespaced_custom_object(
                group=CRD_GROUP,
                version=CRD_VERSION,
                namespace=ctx.namespace,
                plural=INVESTIGATION_PLURAL,
                label_selector=f"autosre.io/alert={ctx.name}",
            )
            
            items = investigations.get("items", [])
            for inv in items:
                status = inv.get("status", {})
                phase = status.get("phase")
                
                # Return if there's an active investigation
                if phase in ["Pending", "Running", "Analyzing", "WaitingForApproval"]:
                    return {
                        "name": inv["metadata"]["name"],
                        "namespace": inv["metadata"]["namespace"],
                        "uid": inv["metadata"]["uid"],
                    }
            
            return None
            
        except ApiException as e:
            logger.warning(f"Failed to find existing investigation: {e}")
            return None
    
    async def acknowledge_alert(
        self,
        name: str,
        namespace: str,
        acknowledged_by: str,
    ) -> Dict[str, Any]:
        """Acknowledge an alert."""
        now = datetime.now(timezone.utc).isoformat()
        
        return {
            "state": "Acknowledged",
            "acknowledgedAt": now,
            "acknowledgedBy": acknowledged_by,
            "history": [{
                "timestamp": now,
                "fromState": "Firing",
                "toState": "Acknowledged",
                "reason": "Manual acknowledgement",
                "actor": acknowledged_by,
            }],
        }
    
    async def silence_alert(
        self,
        name: str,
        namespace: str,
        duration: str,
        reason: str,
        silenced_by: str,
    ) -> Dict[str, Any]:
        """Silence an alert for a duration."""
        now = datetime.now(timezone.utc)
        duration_minutes = self._parse_duration_minutes(duration)
        until = now + timedelta(minutes=duration_minutes)
        
        return {
            "state": "Silenced",
            "silenced": {
                "until": until.isoformat(),
                "reason": reason,
                "silencedBy": silenced_by,
            },
            "history": [{
                "timestamp": now.isoformat(),
                "fromState": "Firing",
                "toState": "Silenced",
                "reason": reason,
                "actor": silenced_by,
            }],
        }
    
    async def resolve_alert(
        self,
        name: str,
        namespace: str,
    ) -> Dict[str, Any]:
        """Mark an alert as resolved."""
        now = datetime.now(timezone.utc).isoformat()
        
        return {
            "state": "Resolved",
            "resolvedAt": now,
            "conditions": [{
                "type": "Resolved",
                "status": "True",
                "lastTransitionTime": now,
                "reason": "AlertResolved",
                "message": "Alert has been resolved",
            }],
        }
    
    def _parse_duration_minutes(self, duration: str) -> int:
        """Parse duration string to minutes."""
        if not duration:
            return 60
        
        try:
            if duration.endswith("d"):
                return int(duration[:-1]) * 24 * 60
            elif duration.endswith("h"):
                return int(duration[:-1]) * 60
            elif duration.endswith("m"):
                return int(duration[:-1])
            elif duration.endswith("s"):
                return max(1, int(duration[:-1]) // 60)
            else:
                return int(duration)
        except ValueError:
            return 60
    
    def cleanup_cache(self, max_age_hours: int = 24):
        """Clean up old entries from the alert cache."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        
        expired = [
            fp for fp, ts in self._alert_cache.items()
            if ts < cutoff
        ]
        
        for fp in expired:
            del self._alert_cache[fp]
        
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired alert cache entries")


# Global controller instance
_controller: Optional[AlertController] = None


def get_controller() -> AlertController:
    """Get or create the global controller instance."""
    global _controller
    if _controller is None:
        _controller = AlertController()
    return _controller


# Kopf handlers - only register if kopf is available
if KOPF_AVAILABLE and kopf is not None:
    
    @kopf.on.startup()
    async def alert_startup_handler(settings: kopf.OperatorSettings, **_):
        """Configure operator settings on startup."""
        settings.posting.level = logging.WARNING
        logger.info("AutoSRE Alert Controller starting...")
    
    @kopf.on.create(CRD_GROUP, CRD_VERSION, ALERT_PLURAL)
    async def alert_create_handler(
        body: kopf.Body,
        spec: kopf.Spec,
        status: kopf.Status,
        meta: kopf.Meta,
        patch: kopf.Patch,
        logger: logging.Logger,
        **kwargs,
    ):
        """Handle Alert creation."""
        name = meta.get("name")
        namespace = meta.get("namespace")
        uid = meta.get("uid")
        
        logger.info(f"Alert created: {namespace}/{name} - {spec.get('alertName')}")
        
        # Create context
        ctx = AlertContext(
            name=name,
            namespace=namespace,
            uid=uid,
            spec=dict(spec),
            status=dict(status),
        )
        
        # Process alert
        controller = get_controller()
        new_status = await controller.process_alert(ctx, patch)
        
        # Update status
        for key, value in new_status.items():
            patch.status[key] = value
        
        return {"message": f"Alert processed with state: {new_status.get('state')}"}
    
    @kopf.on.update(CRD_GROUP, CRD_VERSION, ALERT_PLURAL)
    async def alert_update_handler(
        body: kopf.Body,
        spec: kopf.Spec,
        status: kopf.Status,
        meta: kopf.Meta,
        patch: kopf.Patch,
        diff: kopf.Diff,
        logger: logging.Logger,
        **kwargs,
    ):
        """Handle Alert updates."""
        name = meta.get("name")
        namespace = meta.get("namespace")
        
        # Check for state changes
        for op, field, old, new in diff:
            if field == ("spec", "endsAt") and new:
                # Alert has been resolved externally
                logger.info(f"Alert {namespace}/{name} resolved externally")
                controller = get_controller()
                resolve_status = await controller.resolve_alert(name, namespace)
                for key, value in resolve_status.items():
                    patch.status[key] = value
        
        return {"message": "Alert updated"}
    
    @kopf.on.delete(CRD_GROUP, CRD_VERSION, ALERT_PLURAL)
    async def alert_delete_handler(
        body: kopf.Body,
        meta: kopf.Meta,
        logger: logging.Logger,
        **kwargs,
    ):
        """Handle Alert deletion."""
        name = meta.get("name")
        namespace = meta.get("namespace")
        
        logger.info(f"Alert deleted: {namespace}/{name}")
        
        # Clean up from cache
        spec = body.get("spec", {})
        ctx = AlertContext(
            name=name,
            namespace=namespace,
            uid=meta.get("uid", ""),
            spec=spec,
        )
        
        controller = get_controller()
        if ctx.fingerprint in controller._alert_cache:
            del controller._alert_cache[ctx.fingerprint]
        
        return {"message": "Alert cleanup completed"}
    
    @kopf.on.field(CRD_GROUP, CRD_VERSION, ALERT_PLURAL, field="status.state")
    async def alert_state_change_handler(
        body: kopf.Body,
        meta: kopf.Meta,
        old: str,
        new: str,
        patch: kopf.Patch,
        logger: logging.Logger,
        **kwargs,
    ):
        """Handle alert state transitions."""
        name = meta.get("name")
        namespace = meta.get("namespace")
        
        logger.info(f"Alert {namespace}/{name} state changed: {old} -> {new}")
        
        # Add to history
        now = datetime.now(timezone.utc).isoformat()
        history = body.get("status", {}).get("history", [])
        history.append({
            "timestamp": now,
            "fromState": old,
            "toState": new,
            "reason": "State transition",
            "actor": "system",
        })
        patch.status["history"] = history[-10:]  # Keep last 10 entries
    
    @kopf.timer(CRD_GROUP, CRD_VERSION, ALERT_PLURAL, interval=300.0)
    async def alert_timer_handler(
        body: kopf.Body,
        spec: kopf.Spec,
        status: kopf.Status,
        meta: kopf.Meta,
        patch: kopf.Patch,
        logger: logging.Logger,
        **kwargs,
    ):
        """Periodic timer for alert maintenance."""
        name = meta.get("name")
        namespace = meta.get("namespace")
        state = status.get("state", "Unknown")
        
        now = datetime.now(timezone.utc)
        
        # Check for silenced alerts that should be unsilenced
        if state == "Silenced":
            silenced = status.get("silenced", {})
            until = silenced.get("until")
            
            if until:
                until_dt = datetime.fromisoformat(until.replace("Z", "+00:00"))
                if now >= until_dt:
                    logger.info(f"Unsilencing alert {namespace}/{name}")
                    patch.status["state"] = "Firing"
                    patch.status["silenced"] = None
        
        # Check for stale alerts
        last_seen = status.get("lastSeenAt")
        if last_seen and state == "Firing":
            last_seen_dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
            # Expire alerts not seen in 24 hours
            if now - last_seen_dt > timedelta(hours=24):
                logger.info(f"Expiring stale alert {namespace}/{name}")
                patch.status["state"] = "Expired"
    
    @kopf.daemon(CRD_GROUP, CRD_VERSION, ALERT_PLURAL)
    async def alert_daemon(
        stopped: kopf.DaemonStopped,
        body: kopf.Body,
        meta: kopf.Meta,
        logger: logging.Logger,
        **kwargs,
    ):
        """Background daemon for alert monitoring."""
        name = meta.get("name")
        namespace = meta.get("namespace")
        
        try:
            while not stopped:
                # Clean up cache periodically
                controller = get_controller()
                controller.cleanup_cache()
                
                # Sleep for 1 hour
                await asyncio.sleep(3600)
                
        except asyncio.CancelledError:
            logger.info(f"Alert daemon for {namespace}/{name} stopped")


# Webhook handler for external alert sources
async def handle_alertmanager_webhook(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Handle incoming webhook from Alertmanager.
    
    Returns:
        List of created Alert resource references
    """
    controller = get_controller()
    controller.initialize()
    
    created = []
    alerts = payload.get("alerts", [])
    
    for alert in alerts:
        alert_name = alert.get("labels", {}).get("alertname", "unknown")
        
        alert_resource = {
            "apiVersion": f"{CRD_GROUP}/{CRD_VERSION}",
            "kind": ALERT_KIND,
            "metadata": {
                "name": f"am-{alert_name}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "namespace": "autosre-system",
                "labels": alert.get("labels", {}),
            },
            "spec": {
                "alertName": alert_name,
                "severity": alert.get("labels", {}).get("severity", "medium"),
                "description": alert.get("annotations", {}).get("description", ""),
                "summary": alert.get("annotations", {}).get("summary", ""),
                "source": {
                    "type": "alertmanager",
                    "fingerprint": alert.get("fingerprint"),
                    "url": alert.get("generatorURL"),
                },
                "labels": alert.get("labels", {}),
                "annotations": alert.get("annotations", {}),
                "startsAt": alert.get("startsAt"),
                "endsAt": alert.get("endsAt"),
                "rawPayload": alert,
            },
        }
        
        try:
            result = controller.custom_api.create_namespaced_custom_object(
                group=CRD_GROUP,
                version=CRD_VERSION,
                namespace="autosre-system",
                plural=ALERT_PLURAL,
                body=alert_resource,
            )
            
            created.append({
                "name": result["metadata"]["name"],
                "namespace": result["metadata"]["namespace"],
            })
            
        except ApiException as e:
            logger.error(f"Failed to create alert from webhook: {e}")
    
    return created


# Export handlers
__all__ = [
    "AlertController",
    "AlertContext",
    "get_controller",
    "handle_alertmanager_webhook",
]

if KOPF_AVAILABLE:
    __all__.extend([
        "alert_create_handler",
        "alert_update_handler",
        "alert_delete_handler",
        "alert_state_change_handler",
        "alert_timer_handler",
    ])
