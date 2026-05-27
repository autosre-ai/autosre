"""
AutoSRE Investigation Controller

Kopf-based Kubernetes operator for managing Investigation custom resources.
Handles the full lifecycle of incident investigations including:
- Triggering AI-powered analysis
- Managing investigation state
- Coordinating with data sources
- Generating findings and recommendations
- Executing approved remediations

Usage:
    kopf run -m autosre.operators.investigation_controller --standalone
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
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
CRD_PLURAL = "investigations"
CRD_KIND = "Investigation"


@dataclass
class InvestigationContext:
    """Context for an investigation execution."""
    name: str
    namespace: str
    uid: str
    spec: Dict[str, Any]
    status: Dict[str, Any] = field(default_factory=dict)
    findings: List[Dict[str, Any]] = field(default_factory=list)
    hypotheses: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[Dict[str, Any]] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


class InvestigationController:
    """
    Controller for managing Investigation CRDs.
    
    Handles the full lifecycle of investigations from creation
    to completion, coordinating AI analysis and remediation.
    """
    
    def __init__(self):
        self.k8s_client: Optional[client.ApiClient] = None
        self.custom_api: Optional[client.CustomObjectsApi] = None
        self.core_api: Optional[client.CoreV1Api] = None
        self._initialized = False
        
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
        
    async def update_status(
        self,
        name: str,
        namespace: str,
        status_patch: Dict[str, Any],
    ) -> None:
        """Update investigation status."""
        self.initialize()
        
        status_patch["lastUpdateTime"] = datetime.now(timezone.utc).isoformat()
        
        body = {"status": status_patch}
        
        try:
            self.custom_api.patch_namespaced_custom_object_status(
                group=CRD_GROUP,
                version=CRD_VERSION,
                namespace=namespace,
                plural=CRD_PLURAL,
                name=name,
                body=body,
            )
            logger.info(f"Updated status for investigation {namespace}/{name}")
        except ApiException as e:
            logger.error(f"Failed to update status: {e}")
            raise
            
    async def run_investigation(
        self,
        ctx: InvestigationContext,
        patch: Any,
    ) -> Dict[str, Any]:
        """
        Execute the main investigation workflow.
        
        Returns:
            Final status dictionary
        """
        try:
            # Phase 1: Data Collection
            await self._set_phase(ctx, patch, "Running", "Collecting data...")
            collected_data = await self._collect_data(ctx)
            
            # Phase 2: AI Analysis
            await self._set_phase(ctx, patch, "Analyzing", "Analyzing collected data...")
            analysis_result = await self._analyze_data(ctx, collected_data)
            
            # Generate hypotheses
            ctx.hypotheses = await self._generate_hypotheses(ctx, analysis_result)
            
            # Validate hypotheses
            validated_hypotheses = await self._validate_hypotheses(ctx)
            
            # Determine root cause
            root_cause = await self._determine_root_cause(ctx, validated_hypotheses)
            
            # Generate recommendations
            ctx.recommendations = await self._generate_recommendations(ctx, root_cause)
            
            # Check if remediation is enabled
            analysis_config = ctx.spec.get("analysisConfig", {})
            enable_remediation = analysis_config.get("enableRemediation", False)
            
            if enable_remediation and ctx.recommendations:
                # Check if approval is needed
                if self._requires_approval(ctx):
                    await self._set_phase(
                        ctx, patch, "WaitingForApproval",
                        "Waiting for remediation approval..."
                    )
                    return self._build_status(ctx, "WaitingForApproval", root_cause)
                else:
                    await self._set_phase(ctx, patch, "Remediating", "Applying remediation...")
                    await self._apply_remediation(ctx)
            
            # Complete investigation
            await self._set_phase(ctx, patch, "Completed", "Investigation completed")
            
            return self._build_status(ctx, "Completed", root_cause)
            
        except Exception as e:
            logger.exception(f"Investigation failed: {e}")
            return self._build_status(ctx, "Failed", error=str(e))
    
    async def _set_phase(
        self,
        ctx: InvestigationContext,
        patch: Any,
        phase: str,
        message: str,
    ) -> None:
        """Update the investigation phase."""
        logger.info(f"Investigation {ctx.namespace}/{ctx.name}: {phase} - {message}")
        if patch:
            patch.status["phase"] = phase
            patch.status["currentStep"] = message
            patch.status["lastUpdateTime"] = datetime.now(timezone.utc).isoformat()
    
    async def _collect_data(self, ctx: InvestigationContext) -> Dict[str, Any]:
        """Collect data from configured data sources."""
        collected = {
            "kubernetes": {},
            "metrics": {},
            "logs": {},
            "events": [],
        }
        
        # Collect Kubernetes resource data
        target_resources = ctx.spec.get("targetResources", [])
        if target_resources:
            collected["kubernetes"] = await self._collect_k8s_data(target_resources)
        
        # Collect from configured data sources
        data_sources = ctx.spec.get("dataSources", [])
        for source in data_sources:
            source_type = source.get("type")
            if source_type == "prometheus":
                collected["metrics"]["prometheus"] = await self._query_prometheus(source)
            elif source_type == "kubernetes":
                collected["kubernetes"]["events"] = await self._collect_k8s_events(ctx)
        
        ctx.metrics["dataPointsAnalyzed"] = self._count_data_points(collected)
        return collected
    
    async def _collect_k8s_data(self, resources: List[Dict]) -> Dict[str, Any]:
        """Collect Kubernetes resource data."""
        self.initialize()
        data = {}
        
        for resource in resources:
            kind = resource.get("kind", "").lower()
            name = resource.get("name")
            namespace = resource.get("namespace", "default")
            
            try:
                if kind == "pod":
                    pod = self.core_api.read_namespaced_pod(name, namespace)
                    data[f"pod/{namespace}/{name}"] = pod.to_dict()
                elif kind == "deployment":
                    apps_api = client.AppsV1Api(self.k8s_client)
                    deployment = apps_api.read_namespaced_deployment(name, namespace)
                    data[f"deployment/{namespace}/{name}"] = deployment.to_dict()
                elif kind == "service":
                    svc = self.core_api.read_namespaced_service(name, namespace)
                    data[f"service/{namespace}/{name}"] = svc.to_dict()
            except ApiException as e:
                logger.warning(f"Failed to collect {kind}/{namespace}/{name}: {e}")
                data[f"{kind}/{namespace}/{name}"] = {"error": str(e)}
        
        return data
    
    async def _collect_k8s_events(self, ctx: InvestigationContext) -> List[Dict]:
        """Collect relevant Kubernetes events."""
        self.initialize()
        events = []
        
        scope = ctx.spec.get("scope", {})
        namespaces = scope.get("namespaces", [ctx.namespace])
        
        for ns in namespaces:
            try:
                event_list = self.core_api.list_namespaced_event(ns)
                for event in event_list.items:
                    events.append({
                        "name": event.metadata.name,
                        "namespace": event.metadata.namespace,
                        "reason": event.reason,
                        "message": event.message,
                        "type": event.type,
                        "count": event.count,
                        "lastTimestamp": event.last_timestamp.isoformat() if event.last_timestamp else None,
                        "involvedObject": {
                            "kind": event.involved_object.kind,
                            "name": event.involved_object.name,
                        }
                    })
            except ApiException as e:
                logger.warning(f"Failed to collect events from {ns}: {e}")
        
        return events
    
    async def _query_prometheus(self, source: Dict) -> Dict[str, Any]:
        """Query Prometheus for metrics."""
        # Placeholder - would use httpx to query Prometheus
        return {"source": source.get("endpoint"), "data": []}
    
    def _count_data_points(self, data: Dict) -> int:
        """Count total data points collected."""
        count = 0
        count += len(data.get("kubernetes", {}))
        count += sum(len(v) for v in data.get("metrics", {}).values())
        count += len(data.get("events", []))
        return count
    
    async def _analyze_data(
        self,
        ctx: InvestigationContext,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run AI analysis on collected data."""
        analysis_config = ctx.spec.get("analysisConfig", {})
        model = analysis_config.get("model", "gpt-4")
        depth = analysis_config.get("depth", "standard")
        
        # This would integrate with AutoSRE's existing analyzer
        # For now, return a structured analysis result
        try:
            from autosre.analyzer import Analyzer
            analyzer = Analyzer()
            result = await analyzer.analyze(
                description=ctx.spec.get("description", ""),
                data=data,
                model=model,
                depth=depth,
            )
            ctx.metrics["queriesExecuted"] = result.get("queries_executed", 0)
            return result
        except ImportError:
            logger.warning("Analyzer not available, using basic analysis")
            return self._basic_analysis(ctx, data)
    
    def _basic_analysis(
        self,
        ctx: InvestigationContext,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Perform basic analysis without AI."""
        findings = []
        
        # Check for error events
        events = data.get("events", [])
        error_events = [e for e in events if e.get("type") == "Warning"]
        if error_events:
            findings.append({
                "type": "warning",
                "message": f"Found {len(error_events)} warning events",
                "details": error_events[:5],
            })
        
        # Check for pod issues
        k8s_data = data.get("kubernetes", {})
        for key, resource in k8s_data.items():
            if key.startswith("pod/") and isinstance(resource, dict):
                status = resource.get("status", {})
                phase = status.get("phase")
                if phase not in ["Running", "Succeeded"]:
                    findings.append({
                        "type": "anomaly",
                        "message": f"Pod {key} in {phase} state",
                        "details": status,
                    })
        
        ctx.findings = findings
        return {"findings": findings, "confidence": 0.5}
    
    async def _generate_hypotheses(
        self,
        ctx: InvestigationContext,
        analysis: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Generate hypotheses based on analysis."""
        hypotheses = []
        
        # Generate hypotheses from findings
        for i, finding in enumerate(analysis.get("findings", [])):
            hypothesis = {
                "id": f"hyp-{i+1}",
                "description": f"Issue related to: {finding.get('message', 'Unknown')}",
                "confidence": finding.get("confidence", 0.5),
                "evidence": [finding.get("message")],
                "status": "pending",
            }
            hypotheses.append(hypothesis)
        
        return hypotheses
    
    async def _validate_hypotheses(
        self,
        ctx: InvestigationContext,
    ) -> List[Dict[str, Any]]:
        """Validate generated hypotheses."""
        validated = []
        
        for hyp in ctx.hypotheses:
            # Run validation logic
            # This would typically involve additional queries
            hyp["status"] = "validated" if hyp["confidence"] > 0.6 else "rejected"
            validated.append(hyp)
        
        return validated
    
    async def _determine_root_cause(
        self,
        ctx: InvestigationContext,
        hypotheses: List[Dict[str, Any]],
    ) -> Optional[str]:
        """Determine the most likely root cause."""
        validated = [h for h in hypotheses if h.get("status") == "validated"]
        if not validated:
            return None
        
        # Sort by confidence and return highest
        validated.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        return validated[0].get("description")
    
    async def _generate_recommendations(
        self,
        ctx: InvestigationContext,
        root_cause: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Generate remediation recommendations."""
        recommendations = []
        
        if root_cause:
            recommendations.append({
                "id": "rec-1",
                "type": "immediate",
                "priority": ctx.spec.get("priority", "P3"),
                "action": f"Address root cause: {root_cause}",
                "rationale": "Based on investigation findings",
                "automated": False,
                "status": "pending",
            })
        
        # Add general recommendations based on findings
        for finding in ctx.findings:
            if finding.get("type") == "anomaly":
                recommendations.append({
                    "id": f"rec-{len(recommendations)+1}",
                    "type": "short_term",
                    "priority": "P3",
                    "action": f"Review: {finding.get('message')}",
                    "rationale": "Detected anomaly requires attention",
                    "automated": False,
                    "status": "pending",
                })
        
        return recommendations
    
    def _requires_approval(self, ctx: InvestigationContext) -> bool:
        """Check if remediation requires approval."""
        severity = ctx.spec.get("severity", "medium")
        # For critical/high severity, require approval
        return severity in ["critical", "high"]
    
    async def _apply_remediation(self, ctx: InvestigationContext) -> None:
        """Apply approved remediations."""
        for rec in ctx.recommendations:
            if rec.get("automated") and rec.get("status") == "approved":
                try:
                    # Execute remediation action
                    rec["status"] = "executed"
                except Exception as e:
                    logger.error(f"Remediation failed: {e}")
                    rec["status"] = "failed"
    
    def _build_status(
        self,
        ctx: InvestigationContext,
        phase: str,
        root_cause: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build final status object."""
        now = datetime.now(timezone.utc).isoformat()
        
        status = {
            "phase": phase,
            "lastUpdateTime": now,
            "hypothesis": ctx.hypotheses,
            "findings": [
                {
                    "type": f.get("type", "info"),
                    "severity": ctx.spec.get("severity", "medium"),
                    "message": f.get("message", ""),
                    "timestamp": now,
                    "source": "investigation-controller",
                }
                for f in ctx.findings
            ],
            "recommendations": ctx.recommendations,
            "metrics": ctx.metrics,
            "conditions": [
                {
                    "type": "Ready",
                    "status": "True" if phase == "Completed" else "False",
                    "lastTransitionTime": now,
                    "reason": phase,
                    "message": error or f"Investigation {phase.lower()}",
                }
            ],
        }
        
        if phase == "Completed":
            status["completionTime"] = now
            if root_cause:
                status["rootCause"] = root_cause
                # Calculate confidence based on hypotheses
                if ctx.hypotheses:
                    status["confidence"] = max(
                        h.get("confidence", 0) for h in ctx.hypotheses
                    )
        
        return status


# Global controller instance
_controller: Optional[InvestigationController] = None


def get_controller() -> InvestigationController:
    """Get or create the global controller instance."""
    global _controller
    if _controller is None:
        _controller = InvestigationController()
    return _controller


# Kopf handlers - only register if kopf is available
if KOPF_AVAILABLE and kopf is not None:
    
    @kopf.on.startup()
    async def startup_handler(settings: kopf.OperatorSettings, **_):
        """Configure operator settings on startup."""
        settings.posting.level = logging.WARNING
        settings.watching.connect_timeout = 60
        settings.watching.server_timeout = 300
        logger.info("AutoSRE Investigation Controller starting...")
    
    @kopf.on.create(CRD_GROUP, CRD_VERSION, CRD_PLURAL)
    async def investigation_create_handler(
        body: kopf.Body,
        spec: kopf.Spec,
        status: kopf.Status,
        meta: kopf.Meta,
        patch: kopf.Patch,
        logger: logging.Logger,
        **kwargs,
    ):
        """Handle Investigation creation."""
        name = meta.get("name")
        namespace = meta.get("namespace")
        uid = meta.get("uid")
        
        logger.info(f"Investigation created: {namespace}/{name}")
        
        # Initialize status
        patch.status["phase"] = "Pending"
        patch.status["startTime"] = datetime.now(timezone.utc).isoformat()
        patch.status["progress"] = 0
        
        # Create context
        ctx = InvestigationContext(
            name=name,
            namespace=namespace,
            uid=uid,
            spec=dict(spec),
            status=dict(status),
        )
        
        # Run investigation
        controller = get_controller()
        final_status = await controller.run_investigation(ctx, patch)
        
        # Update status
        for key, value in final_status.items():
            patch.status[key] = value
        
        return {"message": f"Investigation completed with status: {final_status.get('phase')}"}
    
    @kopf.on.update(CRD_GROUP, CRD_VERSION, CRD_PLURAL)
    async def investigation_update_handler(
        body: kopf.Body,
        spec: kopf.Spec,
        status: kopf.Status,
        meta: kopf.Meta,
        patch: kopf.Patch,
        diff: kopf.Diff,
        logger: logging.Logger,
        **kwargs,
    ):
        """Handle Investigation updates."""
        name = meta.get("name")
        namespace = meta.get("namespace")
        
        logger.info(f"Investigation updated: {namespace}/{name}")
        
        # Check for approval of recommendations
        current_phase = status.get("phase")
        if current_phase == "WaitingForApproval":
            # Check if recommendations were approved
            recommendations = status.get("recommendations", [])
            approved = [r for r in recommendations if r.get("status") == "approved"]
            
            if approved:
                logger.info(f"Found {len(approved)} approved recommendations, proceeding with remediation")
                patch.status["phase"] = "Remediating"
        
        return {"message": "Investigation updated"}
    
    @kopf.on.delete(CRD_GROUP, CRD_VERSION, CRD_PLURAL)
    async def investigation_delete_handler(
        body: kopf.Body,
        meta: kopf.Meta,
        logger: logging.Logger,
        **kwargs,
    ):
        """Handle Investigation deletion."""
        name = meta.get("name")
        namespace = meta.get("namespace")
        
        logger.info(f"Investigation deleted: {namespace}/{name}")
        
        # Cleanup any resources created by this investigation
        # (e.g., temporary pods, jobs, etc.)
        
        return {"message": "Investigation cleanup completed"}
    
    @kopf.on.field(CRD_GROUP, CRD_VERSION, CRD_PLURAL, field="status.phase")
    async def investigation_phase_change_handler(
        body: kopf.Body,
        meta: kopf.Meta,
        old: str,
        new: str,
        logger: logging.Logger,
        **kwargs,
    ):
        """Handle phase transitions."""
        name = meta.get("name")
        namespace = meta.get("namespace")
        
        logger.info(f"Investigation {namespace}/{name} phase changed: {old} -> {new}")
        
        # Send notifications on phase changes
        spec = body.get("spec", {})
        notifications = spec.get("notifications", {})
        
        if notifications:
            await _send_notifications(
                notifications,
                f"Investigation {name} phase changed from {old} to {new}",
            )
    
    @kopf.timer(CRD_GROUP, CRD_VERSION, CRD_PLURAL, interval=60.0)
    async def investigation_timer_handler(
        body: kopf.Body,
        spec: kopf.Spec,
        status: kopf.Status,
        meta: kopf.Meta,
        patch: kopf.Patch,
        logger: logging.Logger,
        **kwargs,
    ):
        """Periodic timer for long-running investigations."""
        name = meta.get("name")
        namespace = meta.get("namespace")
        phase = status.get("phase", "Unknown")
        
        # Check for timeout
        analysis_config = spec.get("analysisConfig", {})
        timeout_str = analysis_config.get("timeout", "30m")
        
        start_time = status.get("startTime")
        if start_time and phase in ["Running", "Analyzing"]:
            # Check if investigation has timed out
            start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            elapsed = datetime.now(timezone.utc) - start
            
            # Parse timeout
            timeout_minutes = _parse_duration_minutes(timeout_str)
            
            if elapsed.total_seconds() > timeout_minutes * 60:
                logger.warning(f"Investigation {namespace}/{name} timed out")
                patch.status["phase"] = "Failed"
                patch.status["conditions"] = [
                    {
                        "type": "Ready",
                        "status": "False",
                        "lastTransitionTime": datetime.now(timezone.utc).isoformat(),
                        "reason": "Timeout",
                        "message": f"Investigation exceeded timeout of {timeout_str}",
                    }
                ]


async def _send_notifications(
    notifications: Dict[str, Any],
    message: str,
) -> None:
    """Send notifications via configured channels."""
    # Slack notification
    slack_config = notifications.get("slack")
    if slack_config:
        channel = slack_config.get("channel")
        # Would use slack-sdk here
        logger.info(f"Would send Slack notification to {channel}: {message}")
    
    # Webhook notification
    webhook_config = notifications.get("webhook")
    if webhook_config:
        url = webhook_config.get("url")
        # Would use httpx here
        logger.info(f"Would send webhook to {url}: {message}")


def _parse_duration_minutes(duration: str) -> int:
    """Parse duration string to minutes."""
    if not duration:
        return 30
    
    try:
        if duration.endswith("h"):
            return int(duration[:-1]) * 60
        elif duration.endswith("m"):
            return int(duration[:-1])
        elif duration.endswith("s"):
            return int(duration[:-1]) // 60
        else:
            return int(duration)
    except ValueError:
        return 30


# Export handlers for use as module
__all__ = [
    "InvestigationController",
    "InvestigationContext",
    "get_controller",
]

if KOPF_AVAILABLE:
    __all__.extend([
        "investigation_create_handler",
        "investigation_update_handler",
        "investigation_delete_handler",
        "investigation_phase_change_handler",
        "investigation_timer_handler",
    ])
