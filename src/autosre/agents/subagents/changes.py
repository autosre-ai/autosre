"""
Changes Subagent — First question: What changed recently?

From Google SRE book: The majority of outages are caused by changes.
Always correlate issue timing with recent changes.

Change sources:
- Kubernetes deployments
- Config changes
- Infrastructure changes
- Feature flags
- Dependency updates
- Traffic pattern changes
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional, Protocol

from pydantic import BaseModel, Field

from .base import BaseSubagent, SubagentConfig
from .react import Tool, create_tool

logger = logging.getLogger(__name__)


class ChangeType(str, Enum):
    """Types of changes to track."""
    DEPLOYMENT = "deployment"
    CONFIG = "config"
    INFRASTRUCTURE = "infrastructure"
    FEATURE_FLAG = "feature_flag"
    DEPENDENCY = "dependency"
    TRAFFIC_PATTERN = "traffic_pattern"
    SCALING = "scaling"
    SECRET_ROTATION = "secret_rotation"
    DATABASE_MIGRATION = "database_migration"


class ChangeSource(str, Enum):
    """Source systems for changes."""
    KUBERNETES = "kubernetes"
    GITHUB = "github"
    GITLAB = "gitlab"
    ARGOCD = "argocd"
    TERRAFORM = "terraform"
    LAUNCHDARKLY = "launchdarkly"
    CONFIGMAP = "configmap"
    HELM = "helm"
    FLUX = "flux"


class Change(BaseModel):
    """A single change event."""
    id: str
    type: ChangeType
    source: ChangeSource
    timestamp: datetime
    
    # What changed
    service: Optional[str] = None
    namespace: Optional[str] = None
    description: str = ""
    
    # Git info
    commit_sha: Optional[str] = None
    commit_message: Optional[str] = None
    author: Optional[str] = None
    pr_number: Optional[int] = None
    pr_url: Optional[str] = None
    
    # Deployment info
    previous_version: Optional[str] = None
    new_version: Optional[str] = None
    image: Optional[str] = None
    
    # Config info
    config_key: Optional[str] = None
    old_value: Optional[str] = None  # Sanitized
    new_value: Optional[str] = None  # Sanitized
    
    # Metadata
    raw_data: dict[str, Any] = Field(default_factory=dict)
    
    def time_ago(self, reference: Optional[datetime] = None) -> str:
        """Human-readable time since change."""
        ref = reference or datetime.utcnow()
        delta = ref - self.timestamp
        
        if delta.total_seconds() < 60:
            return f"{int(delta.total_seconds())}s ago"
        elif delta.total_seconds() < 3600:
            return f"{int(delta.total_seconds() / 60)}m ago"
        elif delta.total_seconds() < 86400:
            return f"{int(delta.total_seconds() / 3600)}h ago"
        else:
            return f"{int(delta.total_seconds() / 86400)}d ago"
    
    def summary(self) -> str:
        """One-line summary of the change."""
        parts = [f"[{self.type.value}]"]
        
        if self.service:
            parts.append(self.service)
        
        if self.description:
            parts.append(self.description[:80])
        elif self.commit_message:
            parts.append(self.commit_message[:80])
        
        parts.append(f"({self.time_ago()})")
        
        return " ".join(parts)


class ChangesResult(BaseModel):
    """Result from changes investigation."""
    service: str
    time_range_hours: int
    changes: list[Change] = Field(default_factory=list)
    
    # Correlation analysis
    changes_near_incident: list[Change] = Field(default_factory=list)
    most_suspicious: Optional[Change] = None
    correlation_score: float = 0.0
    
    # By type
    deployments: int = 0
    config_changes: int = 0
    infra_changes: int = 0
    
    # Summary
    summary: str = ""
    
    def has_recent_deployment(self, within_minutes: int = 30) -> bool:
        """Check if there's a deployment within the time window."""
        cutoff = datetime.utcnow() - timedelta(minutes=within_minutes)
        return any(
            c.type == ChangeType.DEPLOYMENT and c.timestamp > cutoff
            for c in self.changes
        )


CHANGES_CAPABILITIES = """
**Changes Investigation**:
- Query Kubernetes deployment events
- Check GitHub/GitLab deployments API
- Review config changes (ConfigMaps, Secrets)
- Check feature flag changes
- Analyze traffic pattern shifts
- Correlate change timing with incident start

**Key Principle**: The majority of incidents are caused by changes.
Always ask "What changed?" early in any investigation.

**Sources**:
- Kubernetes: deployment events, replicaset changes, configmap updates
- GitHub: deployments API, releases, merged PRs
- ArgoCD: sync events, rollouts
- Feature flags: LaunchDarkly, Split, custom
- Infrastructure: Terraform apply events
"""


class GitHubClient:
    """Minimal GitHub client for deployments API."""
    
    def __init__(self, token: str, org: str = "", repo: str = ""):
        self.token = token
        self.org = org
        self.repo = repo
        self.base_url = "https://api.github.com"
    
    async def get_deployments(
        self,
        repo: Optional[str] = None,
        environment: Optional[str] = None,
        per_page: int = 30,
    ) -> list[dict[str, Any]]:
        """Get recent deployments from GitHub."""
        try:
            import httpx
        except ImportError:
            return []
        
        repo = repo or f"{self.org}/{self.repo}"
        url = f"{self.base_url}/repos/{repo}/deployments"
        
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }
        
        params = {"per_page": per_page}
        if environment:
            params["environment"] = environment
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=headers, params=params, timeout=30)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning(f"GitHub deployments API failed: {e}")
            return []
    
    async def get_deployment_statuses(
        self,
        repo: str,
        deployment_id: int,
    ) -> list[dict[str, Any]]:
        """Get statuses for a deployment."""
        try:
            import httpx
        except ImportError:
            return []
        
        url = f"{self.base_url}/repos/{repo}/deployments/{deployment_id}/statuses"
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=headers, timeout=30)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning(f"GitHub deployment statuses failed: {e}")
            return []


class KubernetesChangesClient:
    """Client to get changes from Kubernetes."""
    
    def __init__(self, kubeconfig: Optional[str] = None, context: Optional[str] = None):
        self.kubeconfig = kubeconfig
        self.context = context
    
    async def get_deployment_events(
        self,
        namespace: Optional[str] = None,
        service: Optional[str] = None,
        hours: int = 24,
    ) -> list[Change]:
        """Get deployment-related events from Kubernetes."""
        # This would use kubernetes client - simplified for now
        try:
            from kubernetes import client, config
            
            if self.kubeconfig:
                config.load_kube_config(config_file=self.kubeconfig, context=self.context)
            else:
                try:
                    config.load_incluster_config()
                except:
                    config.load_kube_config(context=self.context)
            
            apps_v1 = client.AppsV1Api()
            core_v1 = client.CoreV1Api()
            
            changes = []
            
            # Get recent replicaset events (indicates deployments)
            if namespace:
                rs_list = apps_v1.list_namespaced_replica_set(namespace)
            else:
                rs_list = apps_v1.list_replica_set_for_all_namespaces()
            
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            
            for rs in rs_list.items:
                if rs.metadata.creation_timestamp and rs.metadata.creation_timestamp.replace(tzinfo=None) > cutoff:
                    # This is a new replicaset - likely a deployment
                    owner = rs.metadata.owner_references[0] if rs.metadata.owner_references else None
                    
                    if owner and owner.kind == "Deployment":
                        changes.append(Change(
                            id=rs.metadata.uid,
                            type=ChangeType.DEPLOYMENT,
                            source=ChangeSource.KUBERNETES,
                            timestamp=rs.metadata.creation_timestamp.replace(tzinfo=None),
                            service=owner.name,
                            namespace=rs.metadata.namespace,
                            description=f"New ReplicaSet {rs.metadata.name}",
                            new_version=rs.metadata.labels.get("pod-template-hash", ""),
                            image=rs.spec.template.spec.containers[0].image if rs.spec.template.spec.containers else None,
                        ))
            
            # Get ConfigMap changes (events)
            events = core_v1.list_event_for_all_namespaces(
                field_selector="involvedObject.kind=ConfigMap",
            )
            
            for event in events.items:
                if event.last_timestamp and event.last_timestamp.replace(tzinfo=None) > cutoff:
                    changes.append(Change(
                        id=event.metadata.uid,
                        type=ChangeType.CONFIG,
                        source=ChangeSource.CONFIGMAP,
                        timestamp=event.last_timestamp.replace(tzinfo=None),
                        namespace=event.metadata.namespace,
                        description=f"ConfigMap {event.involved_object.name}: {event.reason}",
                        config_key=event.involved_object.name,
                    ))
            
            return changes
            
        except ImportError:
            logger.warning("kubernetes package not installed")
            return []
        except Exception as e:
            logger.warning(f"Failed to get Kubernetes changes: {e}")
            return []
    
    async def get_configmap_changes(
        self,
        namespace: str,
        name: str,
    ) -> Optional[Change]:
        """Get details of a specific ConfigMap."""
        try:
            from kubernetes import client, config
            
            if self.kubeconfig:
                config.load_kube_config(config_file=self.kubeconfig, context=self.context)
            else:
                try:
                    config.load_incluster_config()
                except:
                    config.load_kube_config(context=self.context)
            
            core_v1 = client.CoreV1Api()
            cm = core_v1.read_namespaced_config_map(name, namespace)
            
            return Change(
                id=cm.metadata.uid,
                type=ChangeType.CONFIG,
                source=ChangeSource.CONFIGMAP,
                timestamp=cm.metadata.creation_timestamp.replace(tzinfo=None),
                namespace=namespace,
                description=f"ConfigMap {name}",
                config_key=name,
                raw_data={"keys": list(cm.data.keys()) if cm.data else []},
            )
        except Exception as e:
            logger.warning(f"Failed to get ConfigMap: {e}")
            return None


class ChangesSubagent(BaseSubagent):
    """
    Changes Investigation Subagent.
    
    The FIRST question in any investigation should be: "What changed?"
    
    This subagent:
    1. Queries all change sources (K8s, GitHub, config, flags)
    2. Correlates change timing with incident start
    3. Identifies most suspicious changes
    4. Integrates with GitHub deployments API
    """
    
    agent_id = "changes"
    agent_name = "Changes Investigation Agent"
    capabilities_description = CHANGES_CAPABILITIES
    
    def __init__(
        self,
        config: Optional[SubagentConfig] = None,
        kubernetes_client: Optional[KubernetesChangesClient] = None,
        github_client: Optional[GitHubClient] = None,
        dry_run: bool = False,
    ):
        super().__init__(config)
        self.k8s = kubernetes_client or KubernetesChangesClient()
        self.github = github_client
        self.dry_run = dry_run
    
    async def get_recent_changes(
        self,
        service: Optional[str] = None,
        namespace: Optional[str] = None,
        hours: int = 24,
        incident_time: Optional[datetime] = None,
    ) -> ChangesResult:
        """
        Get all recent changes, correlated with incident timing.
        
        Args:
            service: Filter to specific service
            namespace: Filter to specific namespace
            hours: How far back to look
            incident_time: When incident started (for correlation)
            
        Returns:
            ChangesResult with all changes and correlation analysis
        """
        incident_time = incident_time or datetime.utcnow()
        all_changes: list[Change] = []
        
        # Get Kubernetes changes
        k8s_changes = await self.k8s.get_deployment_events(
            namespace=namespace,
            service=service,
            hours=hours,
        )
        all_changes.extend(k8s_changes)
        
        # Get GitHub deployments if configured
        if self.github:
            github_deployments = await self.github.get_deployments()
            for dep in github_deployments:
                created_at = datetime.fromisoformat(dep["created_at"].replace("Z", ""))
                if created_at > datetime.utcnow() - timedelta(hours=hours):
                    all_changes.append(Change(
                        id=str(dep["id"]),
                        type=ChangeType.DEPLOYMENT,
                        source=ChangeSource.GITHUB,
                        timestamp=created_at,
                        description=dep.get("description", ""),
                        commit_sha=dep.get("sha"),
                        author=dep.get("creator", {}).get("login"),
                        raw_data=dep,
                    ))
        
        # Sort by timestamp (most recent first)
        all_changes.sort(key=lambda c: c.timestamp, reverse=True)
        
        # Filter to service if specified
        if service:
            all_changes = [
                c for c in all_changes
                if c.service == service or c.service is None
            ]
        
        # Correlate with incident time
        # Changes within 30 min before incident are suspicious
        correlation_window = timedelta(minutes=30)
        changes_near_incident = [
            c for c in all_changes
            if 0 < (incident_time - c.timestamp).total_seconds() < correlation_window.total_seconds()
        ]
        
        # Find most suspicious change
        most_suspicious = None
        if changes_near_incident:
            # Deployments are most suspicious
            deployments = [c for c in changes_near_incident if c.type == ChangeType.DEPLOYMENT]
            if deployments:
                most_suspicious = deployments[0]
            else:
                most_suspicious = changes_near_incident[0]
        
        # Calculate correlation score
        correlation_score = 0.0
        if most_suspicious:
            time_delta = (incident_time - most_suspicious.timestamp).total_seconds() / 60
            # Higher score if change was closer to incident
            if time_delta < 5:
                correlation_score = 0.95
            elif time_delta < 15:
                correlation_score = 0.80
            elif time_delta < 30:
                correlation_score = 0.60
            else:
                correlation_score = 0.30
        
        # Build summary
        summary_parts = []
        if all_changes:
            summary_parts.append(f"Found {len(all_changes)} changes in last {hours}h")
        if changes_near_incident:
            summary_parts.append(f"{len(changes_near_incident)} changes within 30 min of incident")
        if most_suspicious:
            summary_parts.append(f"Most suspicious: {most_suspicious.summary()}")
        
        return ChangesResult(
            service=service or "all",
            time_range_hours=hours,
            changes=all_changes,
            changes_near_incident=changes_near_incident,
            most_suspicious=most_suspicious,
            correlation_score=correlation_score,
            deployments=len([c for c in all_changes if c.type == ChangeType.DEPLOYMENT]),
            config_changes=len([c for c in all_changes if c.type == ChangeType.CONFIG]),
            infra_changes=len([c for c in all_changes if c.type == ChangeType.INFRASTRUCTURE]),
            summary=". ".join(summary_parts) if summary_parts else "No changes found",
        )
    
    async def get_tools(self) -> list[Tool]:
        """Return changes investigation tools."""
        
        async def list_recent_changes(
            service: Optional[str] = None,
            hours: int = 24,
        ) -> str:
            """List all recent changes."""
            if self.dry_run:
                return f"[DRY RUN] Would list changes for service={service}, hours={hours}"
            
            result = await self.get_recent_changes(
                service=service,
                hours=hours,
            )
            
            lines = [
                f"Changes for {result.service} (last {hours}h):",
                f"Total: {len(result.changes)} | Deployments: {result.deployments} | Config: {result.config_changes}",
                "",
            ]
            
            for change in result.changes[:20]:
                lines.append(f"  {change.summary()}")
            
            if len(result.changes) > 20:
                lines.append(f"  ... and {len(result.changes) - 20} more")
            
            return "\n".join(lines)
        
        async def get_changes_near_incident(
            service: Optional[str] = None,
            incident_time: Optional[str] = None,
            window_minutes: int = 30,
        ) -> str:
            """Get changes that occurred shortly before incident."""
            if self.dry_run:
                return f"[DRY RUN] Would get changes near incident"
            
            inc_time = datetime.utcnow()
            if incident_time:
                try:
                    inc_time = datetime.fromisoformat(incident_time)
                except:
                    pass
            
            result = await self.get_recent_changes(
                service=service,
                hours=24,
                incident_time=inc_time,
            )
            
            lines = [
                f"Changes within {window_minutes} minutes of incident:",
                f"Correlation score: {result.correlation_score:.2f}",
                "",
            ]
            
            if result.most_suspicious:
                lines.append(f"⚠️  MOST SUSPICIOUS: {result.most_suspicious.summary()}")
                lines.append("")
            
            for change in result.changes_near_incident:
                lines.append(f"  {change.summary()}")
            
            if not result.changes_near_incident:
                lines.append("  No changes found in the correlation window")
            
            return "\n".join(lines)
        
        async def get_deployment_details(
            service: str,
            deployment_id: Optional[str] = None,
        ) -> str:
            """Get detailed info about a specific deployment."""
            if self.dry_run:
                return f"[DRY RUN] Would get deployment details for {service}"
            
            result = await self.get_recent_changes(service=service, hours=48)
            
            deployments = [c for c in result.changes if c.type == ChangeType.DEPLOYMENT]
            
            if not deployments:
                return f"No recent deployments found for {service}"
            
            lines = [f"Recent deployments for {service}:", ""]
            
            for dep in deployments[:5]:
                lines.append(f"ID: {dep.id}")
                lines.append(f"  Time: {dep.timestamp.isoformat()} ({dep.time_ago()})")
                lines.append(f"  Image: {dep.image or 'N/A'}")
                lines.append(f"  Author: {dep.author or 'N/A'}")
                lines.append(f"  Commit: {dep.commit_sha or 'N/A'}")
                if dep.commit_message:
                    lines.append(f"  Message: {dep.commit_message[:100]}")
                lines.append("")
            
            return "\n".join(lines)
        
        async def check_github_deployments(
            repo: str,
            environment: Optional[str] = None,
        ) -> str:
            """Check GitHub deployments API for a repository."""
            if not self.github:
                return "GitHub client not configured"
            
            if self.dry_run:
                return f"[DRY RUN] Would check GitHub deployments for {repo}"
            
            deployments = await self.github.get_deployments(
                repo=repo,
                environment=environment,
            )
            
            if not deployments:
                return f"No deployments found for {repo}"
            
            lines = [f"GitHub deployments for {repo}:", ""]
            
            for dep in deployments[:10]:
                created = dep.get("created_at", "unknown")
                env = dep.get("environment", "unknown")
                sha = dep.get("sha", "")[:8]
                creator = dep.get("creator", {}).get("login", "unknown")
                desc = dep.get("description", "")[:50]
                
                lines.append(f"  [{env}] {created} by {creator}")
                lines.append(f"    Commit: {sha} - {desc}")
            
            return "\n".join(lines)
        
        async def correlate_changes_with_metrics(
            service: str,
            metric_anomaly_time: str,
        ) -> str:
            """Correlate metric anomaly timing with recent changes."""
            if self.dry_run:
                return f"[DRY RUN] Would correlate changes with metrics"
            
            try:
                anomaly_time = datetime.fromisoformat(metric_anomaly_time)
            except:
                anomaly_time = datetime.utcnow()
            
            result = await self.get_recent_changes(
                service=service,
                hours=24,
                incident_time=anomaly_time,
            )
            
            lines = [
                f"Correlating changes with metric anomaly at {metric_anomaly_time}",
                "",
            ]
            
            if result.correlation_score > 0.8:
                lines.append("🔴 HIGH CORRELATION - Change likely caused the issue")
            elif result.correlation_score > 0.5:
                lines.append("🟡 MODERATE CORRELATION - Change may be related")
            else:
                lines.append("🟢 LOW CORRELATION - Change unlikely to be related")
            
            lines.append(f"Correlation score: {result.correlation_score:.2f}")
            lines.append("")
            
            if result.most_suspicious:
                lines.append(f"Most suspicious change:")
                lines.append(f"  {result.most_suspicious.summary()}")
                if result.most_suspicious.commit_sha:
                    lines.append(f"  Commit: {result.most_suspicious.commit_sha}")
            
            return "\n".join(lines)
        
        return [
            create_tool(
                name="list_recent_changes",
                description="List all recent changes (deployments, config, infra). Start here to see what changed.",
                executor=list_recent_changes,
                parameters={
                    "type": "object",
                    "properties": {
                        "service": {"type": "string", "description": "Filter to specific service"},
                        "hours": {"type": "integer", "description": "How far back to look (default: 24)"},
                    },
                },
            ),
            create_tool(
                name="get_changes_near_incident",
                description="Get changes that occurred shortly before the incident. Critical for correlation.",
                executor=get_changes_near_incident,
                parameters={
                    "type": "object",
                    "properties": {
                        "service": {"type": "string", "description": "Filter to specific service"},
                        "incident_time": {"type": "string", "description": "Incident start time (ISO8601)"},
                        "window_minutes": {"type": "integer", "description": "Correlation window (default: 30)"},
                    },
                },
            ),
            create_tool(
                name="get_deployment_details",
                description="Get detailed information about deployments for a service.",
                executor=get_deployment_details,
                parameters={
                    "type": "object",
                    "properties": {
                        "service": {"type": "string", "description": "Service name"},
                        "deployment_id": {"type": "string", "description": "Specific deployment ID"},
                    },
                    "required": ["service"],
                },
            ),
            create_tool(
                name="check_github_deployments",
                description="Query GitHub Deployments API for a repository.",
                executor=check_github_deployments,
                parameters={
                    "type": "object",
                    "properties": {
                        "repo": {"type": "string", "description": "Repository (owner/repo format)"},
                        "environment": {"type": "string", "description": "Filter to environment (production, staging)"},
                    },
                    "required": ["repo"],
                },
            ),
            create_tool(
                name="correlate_changes_with_metrics",
                description="Correlate metric anomaly timing with recent changes. High correlation = likely cause.",
                executor=correlate_changes_with_metrics,
                parameters={
                    "type": "object",
                    "properties": {
                        "service": {"type": "string", "description": "Service name"},
                        "metric_anomaly_time": {"type": "string", "description": "When the metric anomaly started (ISO8601)"},
                    },
                    "required": ["service", "metric_anomaly_time"],
                },
            ),
        ]
    
    def get_hypothesis(
        self,
        alert: dict[str, Any],
        hypotheses: list[str],
        service_context: str = "",
    ) -> str:
        """Build changes-focused hypothesis."""
        service = alert.get("service", alert.get("labels", {}).get("service", "unknown"))
        
        return f"""Investigating recent changes for {service}:

The MAJORITY of production incidents are caused by changes.

Key questions:
1. What deployments happened in the last 24 hours?
2. Were there config changes (ConfigMaps, feature flags)?
3. Did any change happen shortly before the alert fired?
4. Can we correlate the issue timing with a specific change?

Start by listing all recent changes, then correlate with incident timing."""


def create_changes_subagent(
    github_token: Optional[str] = None,
    github_org: str = "",
    github_repo: str = "",
    config: Optional[SubagentConfig] = None,
    dry_run: bool = False,
) -> ChangesSubagent:
    """Factory function to create Changes subagent."""
    github_client = None
    if github_token:
        github_client = GitHubClient(
            token=github_token,
            org=github_org,
            repo=github_repo,
        )
    
    return ChangesSubagent(
        config=config,
        github_client=github_client,
        dry_run=dry_run,
    )
