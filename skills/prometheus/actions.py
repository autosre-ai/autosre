"""
Prometheus Skill Actions

Provides actions for querying Prometheus metrics, managing alerts,
and monitoring scrape targets.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
import re
import logging

import httpx

from opensre_core.skills import Skill, ActionResult, action

logger = logging.getLogger(__name__)


@dataclass
class MetricResult:
    """Result from a Prometheus query."""
    metric_name: str
    labels: dict[str, str]
    value: float | None = None
    values: list[tuple[datetime, float]] = field(default_factory=list)


@dataclass
class AlertResult:
    """Active alert from Prometheus."""
    alert_name: str
    state: str  # firing, pending
    labels: dict[str, str]
    annotations: dict[str, str]
    started_at: datetime | None = None
    value: float | None = None


@dataclass
class AlertRule:
    """Configured alert rule."""
    name: str
    expression: str
    duration: str
    labels: dict[str, str]
    annotations: dict[str, str]
    state: str  # inactive, pending, firing


@dataclass
class TargetInfo:
    """Scrape target information."""
    job: str
    instance: str
    health: str  # up, down, unknown
    labels: dict[str, str]
    last_scrape: datetime | None = None
    scrape_duration: float | None = None
    error: str | None = None


@dataclass
class SilenceResult:
    """Result of creating a silence."""
    silence_id: str
    starts_at: datetime
    ends_at: datetime
    matchers: list[dict[str, str]]


class PrometheusSkill(Skill):
    """Skill for interacting with Prometheus metrics and alerts."""
    
    name = "prometheus"
    version = "1.0.0"
    description = "Query Prometheus metrics, manage alerts, and monitor targets"
    
    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.url = self.config.get("url", "http://localhost:9090")
        self.alertmanager_url = self.config.get("alertmanager_url")
        self.timeout = self.config.get("timeout", 30)
        self._auth = self._build_auth()
        self._client: httpx.AsyncClient | None = None
        
        # Register actions
        self.register_action("query", self.query, "Execute instant PromQL query")
        self.register_action("query_range", self.query_range, "Execute range query")
        self.register_action("get_alerts", self.get_alerts, "List active alerts")
        self.register_action("get_alert_rules", self.get_alert_rules, "List alert rules")
        self.register_action("silence_alert", self.silence_alert, "Create alert silence", requires_approval=True)
        self.register_action("delete_silence", self.delete_silence, "Remove silence", requires_approval=True)
        self.register_action("get_targets", self.get_targets, "List scrape targets")
    
    def _build_auth(self) -> httpx.Auth | None:
        """Build auth handler from config."""
        auth_config = self.config.get("auth", {})
        auth_type = auth_config.get("type", "none")
        
        if auth_type == "basic":
            return httpx.BasicAuth(
                auth_config.get("username", ""),
                auth_config.get("password", ""),
            )
        elif auth_type == "bearer":
            # Return None; we'll add header manually
            return None
        return None
    
    def _get_headers(self) -> dict[str, str]:
        """Get request headers."""
        headers = {"Accept": "application/json"}
        auth_config = self.config.get("auth", {})
        if auth_config.get("type") == "bearer":
            headers["Authorization"] = f"Bearer {auth_config.get('token', '')}"
        return headers
    
    async def initialize(self) -> None:
        """Initialize HTTP client."""
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            auth=self._auth,
        )
        await super().initialize()
    
    async def shutdown(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        await super().shutdown()
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Get HTTP client, creating if needed."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                auth=self._auth,
            )
        return self._client
    
    async def health_check(self) -> ActionResult[dict[str, Any]]:
        """Check Prometheus connection health."""
        try:
            response = await self.client.get(
                f"{self.url}/-/healthy",
                headers=self._get_headers(),
            )
            if response.status_code == 200:
                return ActionResult.ok({
                    "status": "healthy",
                    "url": self.url,
                })
            return ActionResult.fail(f"Unhealthy: HTTP {response.status_code}")
        except Exception as e:
            return ActionResult.fail(f"Connection failed: {e}")
    
    @action(description="Execute instant PromQL query")
    async def query(self, promql: str, time_range: str = "5m") -> ActionResult[list[MetricResult]]:
        """Execute an instant PromQL query.
        
        Args:
            promql: PromQL expression to execute
            time_range: Time range for rate/increase functions (default: "5m")
            
        Returns:
            List of metric results
        """
        try:
            response = await self.client.get(
                f"{self.url}/api/v1/query",
                params={"query": promql},
                headers=self._get_headers(),
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") != "success":
                return ActionResult.fail(data.get("error", "Query failed"))
            
            results = self._parse_instant_result(data.get("data", {}).get("result", []))
            return ActionResult.ok(results, query=promql, result_count=len(results))
            
        except httpx.HTTPStatusError as e:
            return ActionResult.fail(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            return ActionResult.fail(f"Query failed: {e}")
    
    @action(description="Execute range PromQL query")
    async def query_range(
        self,
        promql: str,
        start: datetime | None = None,
        end: datetime | None = None,
        step: str = "15s",
    ) -> ActionResult[list[MetricResult]]:
        """Execute a range query for time series data.
        
        Args:
            promql: PromQL expression
            start: Start time (default: 1 hour ago)
            end: End time (default: now)
            step: Query step interval
            
        Returns:
            List of metric results with time series values
        """
        end = end or datetime.now()
        start = start or (end - timedelta(hours=1))
        
        try:
            response = await self.client.get(
                f"{self.url}/api/v1/query_range",
                params={
                    "query": promql,
                    "start": start.timestamp(),
                    "end": end.timestamp(),
                    "step": step,
                },
                headers=self._get_headers(),
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") != "success":
                return ActionResult.fail(data.get("error", "Query failed"))
            
            results = self._parse_range_result(data.get("data", {}).get("result", []))
            return ActionResult.ok(results, query=promql, result_count=len(results))
            
        except Exception as e:
            return ActionResult.fail(f"Range query failed: {e}")
    
    @action(description="List active alerts")
    async def get_alerts(self, state: str | None = None) -> ActionResult[list[AlertResult]]:
        """Get active alerts from Prometheus.
        
        Args:
            state: Filter by state (firing, pending, or None for all)
            
        Returns:
            List of active alerts
        """
        try:
            response = await self.client.get(
                f"{self.url}/api/v1/alerts",
                headers=self._get_headers(),
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") != "success":
                return ActionResult.fail(data.get("error", "Failed to get alerts"))
            
            alerts = []
            for alert in data.get("data", {}).get("alerts", []):
                alert_state = alert.get("state", "unknown")
                if state and alert_state != state:
                    continue
                    
                alerts.append(AlertResult(
                    alert_name=alert.get("labels", {}).get("alertname", "unknown"),
                    state=alert_state,
                    labels=alert.get("labels", {}),
                    annotations=alert.get("annotations", {}),
                    started_at=self._parse_time(alert.get("activeAt")),
                    value=self._parse_float(alert.get("value")),
                ))
            
            return ActionResult.ok(alerts, total=len(alerts))
            
        except Exception as e:
            return ActionResult.fail(f"Failed to get alerts: {e}")
    
    @action(description="List configured alert rules")
    async def get_alert_rules(self) -> ActionResult[list[AlertRule]]:
        """Get all configured alerting rules.
        
        Returns:
            List of alert rules with their expressions
        """
        try:
            response = await self.client.get(
                f"{self.url}/api/v1/rules",
                params={"type": "alert"},
                headers=self._get_headers(),
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") != "success":
                return ActionResult.fail(data.get("error", "Failed to get rules"))
            
            rules = []
            for group in data.get("data", {}).get("groups", []):
                for rule in group.get("rules", []):
                    if rule.get("type") == "alerting":
                        rules.append(AlertRule(
                            name=rule.get("name", "unknown"),
                            expression=rule.get("query", ""),
                            duration=rule.get("duration", "0s"),
                            labels=rule.get("labels", {}),
                            annotations=rule.get("annotations", {}),
                            state=rule.get("state", "inactive"),
                        ))
            
            return ActionResult.ok(rules, total=len(rules))
            
        except Exception as e:
            return ActionResult.fail(f"Failed to get alert rules: {e}")
    
    @action(description="Create silence for an alert", requires_approval=True)
    async def silence_alert(
        self,
        alert_name: str,
        duration: str,
        comment: str = "Silenced via OpenSRE",
    ) -> ActionResult[SilenceResult]:
        """Create a silence for an alert.
        
        Requires Alertmanager to be configured.
        
        Args:
            alert_name: Name of the alert to silence
            duration: Duration string (e.g., "2h", "30m")
            comment: Reason for the silence
            
        Returns:
            Silence result with ID
        """
        if not self.alertmanager_url:
            return ActionResult.fail("Alertmanager URL not configured")
        
        try:
            duration_seconds = self._parse_duration(duration)
            starts_at = datetime.utcnow()
            ends_at = starts_at + timedelta(seconds=duration_seconds)
            
            payload = {
                "matchers": [
                    {"name": "alertname", "value": alert_name, "isRegex": False}
                ],
                "startsAt": starts_at.isoformat() + "Z",
                "endsAt": ends_at.isoformat() + "Z",
                "comment": comment,
                "createdBy": "opensre",
            }
            
            response = await self.client.post(
                f"{self.alertmanager_url}/api/v2/silences",
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            data = response.json()
            
            return ActionResult.ok(SilenceResult(
                silence_id=data.get("silenceID", ""),
                starts_at=starts_at,
                ends_at=ends_at,
                matchers=payload["matchers"],
            ))
            
        except Exception as e:
            return ActionResult.fail(f"Failed to create silence: {e}")
    
    @action(description="Remove an active silence", requires_approval=True)
    async def delete_silence(self, silence_id: str) -> ActionResult[bool]:
        """Delete an active silence.
        
        Args:
            silence_id: ID of the silence to remove
            
        Returns:
            True if deleted successfully
        """
        if not self.alertmanager_url:
            return ActionResult.fail("Alertmanager URL not configured")
        
        try:
            response = await self.client.delete(
                f"{self.alertmanager_url}/api/v2/silence/{silence_id}",
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return ActionResult.ok(True, silence_id=silence_id)
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return ActionResult.fail(f"Silence not found: {silence_id}")
            return ActionResult.fail(f"Failed to delete silence: {e}")
        except Exception as e:
            return ActionResult.fail(f"Failed to delete silence: {e}")
    
    @action(description="List scrape targets")
    async def get_targets(self) -> ActionResult[list[TargetInfo]]:
        """Get all scrape targets and their status.
        
        Returns:
            List of targets with health status
        """
        try:
            response = await self.client.get(
                f"{self.url}/api/v1/targets",
                headers=self._get_headers(),
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") != "success":
                return ActionResult.fail(data.get("error", "Failed to get targets"))
            
            targets = []
            for target in data.get("data", {}).get("activeTargets", []):
                targets.append(TargetInfo(
                    job=target.get("labels", {}).get("job", "unknown"),
                    instance=target.get("labels", {}).get("instance", "unknown"),
                    health=target.get("health", "unknown"),
                    labels=target.get("labels", {}),
                    last_scrape=self._parse_time(target.get("lastScrape")),
                    scrape_duration=target.get("lastScrapeDuration"),
                    error=target.get("lastError") or None,
                ))
            
            return ActionResult.ok(targets, active=len(targets))
            
        except Exception as e:
            return ActionResult.fail(f"Failed to get targets: {e}")
    
    # Helper methods
    
    def _parse_instant_result(self, result: list) -> list[MetricResult]:
        """Parse instant query result."""
        metrics = []
        for item in result:
            metric = item.get("metric", {})
            value = item.get("value", [])
            
            metrics.append(MetricResult(
                metric_name=metric.get("__name__", "unknown"),
                labels={k: v for k, v in metric.items() if k != "__name__"},
                value=float(value[1]) if len(value) > 1 else None,
            ))
        return metrics
    
    def _parse_range_result(self, result: list) -> list[MetricResult]:
        """Parse range query result."""
        metrics = []
        for item in result:
            metric = item.get("metric", {})
            values = item.get("values", [])
            
            parsed_values = [
                (datetime.fromtimestamp(v[0]), float(v[1]))
                for v in values
            ]
            
            metrics.append(MetricResult(
                metric_name=metric.get("__name__", "unknown"),
                labels={k: v for k, v in metric.items() if k != "__name__"},
                value=parsed_values[-1][1] if parsed_values else None,
                values=parsed_values,
            ))
        return metrics
    
    def _parse_time(self, time_str: str | None) -> datetime | None:
        """Parse ISO timestamp."""
        if not time_str:
            return None
        try:
            return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        except ValueError:
            return None
    
    def _parse_float(self, value: Any) -> float | None:
        """Safely parse float."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def _parse_duration(self, duration: str) -> int:
        """Parse duration string to seconds.
        
        Supports: 30s, 5m, 2h, 1d
        """
        match = re.match(r"^(\d+)([smhd])$", duration.lower())
        if not match:
            raise ValueError(f"Invalid duration format: {duration}")
        
        value = int(match.group(1))
        unit = match.group(2)
        
        multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        return value * multipliers[unit]
