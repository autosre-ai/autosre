"""Datadog Integration for AutoSRE V2.

Provides Datadog integration for:
- Metrics submission
- Event creation
- Monitor management
- Log queries
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import httpx
from pydantic import BaseModel, Field

from autosre.integrations.base import (
    AuthenticatedIntegration,
    ConnectionConfig,
    HealthCheckResult,
    HealthStatus,
    IntegrationError,
)
from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class MetricType(str, Enum):
    """Datadog metric types."""
    
    GAUGE = "gauge"
    COUNT = "count"
    RATE = "rate"
    DISTRIBUTION = "distribution"


class AlertType(str, Enum):
    """Datadog alert types."""
    
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    SUCCESS = "success"


class Priority(str, Enum):
    """Event priority."""
    
    NORMAL = "normal"
    LOW = "low"


class MonitorType(str, Enum):
    """Datadog monitor types."""
    
    METRIC_ALERT = "metric alert"
    SERVICE_CHECK = "service check"
    EVENT_ALERT = "event alert"
    QUERY_ALERT = "query alert"
    COMPOSITE = "composite"
    LOG_ALERT = "log alert"
    PROCESS_ALERT = "process alert"
    NETWORK_ALERT = "network alert"
    RUM_ALERT = "rum alert"
    TRACE_ANALYTICS = "trace-analytics alert"


class MonitorState(str, Enum):
    """Monitor states."""
    
    OK = "OK"
    ALERT = "Alert"
    WARN = "Warn"
    NO_DATA = "No Data"


@dataclass
class DatadogConfig:
    """Configuration for Datadog integration."""
    
    # API keys
    api_key: str
    app_key: str
    
    # Site (us1, us3, us5, eu1, ap1)
    site: str = "us1"
    
    # Base URL (auto-generated from site)
    base_url: Optional[str] = None
    
    # Timeouts
    timeout_seconds: float = 30.0
    
    # Default tags
    default_tags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.base_url:
            site_urls = {
                "us1": "https://api.datadoghq.com",
                "us3": "https://api.us3.datadoghq.com",
                "us5": "https://api.us5.datadoghq.com",
                "eu1": "https://api.datadoghq.eu",
                "ap1": "https://api.ap1.datadoghq.com",
            }
            self.base_url = site_urls.get(self.site, site_urls["us1"])


class DatadogMetric(BaseModel):
    """Datadog metric model."""
    
    metric: str
    type: MetricType = MetricType.GAUGE
    
    # Data points: list of [timestamp, value] or just value
    points: List[Union[float, List[float]]] = Field(default_factory=list)
    
    # Tags
    tags: List[str] = Field(default_factory=list)
    
    # Host
    host: Optional[str] = None
    
    # Interval for rate/count
    interval: Optional[int] = None
    
    # Unit
    unit: Optional[str] = None
    
    def add_point(
        self,
        value: float,
        timestamp: Optional[float] = None,
    ) -> None:
        """Add a data point."""
        ts = timestamp or time.time()
        self.points.append([ts, value])


class DatadogEvent(BaseModel):
    """Datadog event model."""
    
    title: str
    text: str
    
    # Timing
    date_happened: Optional[int] = None
    
    # Classification
    alert_type: AlertType = AlertType.INFO
    priority: Priority = Priority.NORMAL
    
    # Tags
    tags: List[str] = Field(default_factory=list)
    
    # Aggregation
    aggregation_key: Optional[str] = None
    
    # Source
    source_type_name: Optional[str] = None
    host: Optional[str] = None
    device_name: Optional[str] = None
    
    # Related resources
    related_event_id: Optional[int] = None


class DatadogMonitor(BaseModel):
    """Datadog monitor model."""
    
    # Identity
    id: Optional[int] = None
    
    # Definition
    name: str
    type: MonitorType
    query: str
    message: str
    
    # Tags
    tags: List[str] = Field(default_factory=list)
    
    # Options
    options: Dict[str, Any] = Field(default_factory=dict)
    
    # Priority
    priority: Optional[int] = None
    
    # State
    overall_state: Optional[MonitorState] = None
    
    # Timing
    created: Optional[datetime] = None
    modified: Optional[datetime] = None
    
    # Multi
    multi: bool = False


class DatadogLog(BaseModel):
    """Datadog log entry."""
    
    message: str
    service: Optional[str] = None
    status: Optional[str] = None
    
    # Timing
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Host info
    host: Optional[str] = None
    
    # Tags
    tags: List[str] = Field(default_factory=list)
    
    # Attributes
    attributes: Dict[str, Any] = Field(default_factory=dict)


class DatadogServiceCheck(BaseModel):
    """Datadog service check."""
    
    check: str
    host_name: str
    status: int  # 0=OK, 1=Warning, 2=Critical, 3=Unknown
    
    timestamp: Optional[int] = None
    message: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class DatadogIntegration(AuthenticatedIntegration):
    """
    Datadog integration for observability.
    
    Provides comprehensive Datadog functionality:
    - Metric submission
    - Event creation
    - Monitor management
    - Log queries
    - Service checks
    
    Example:
        config = DatadogConfig(
            api_key="your-api-key",
            app_key="your-app-key",
            site="us1",
        )
        
        async with DatadogIntegration(config) as dd:
            # Submit metrics
            await dd.submit_metrics([
                DatadogMetric(
                    metric="autosre.investigation.duration",
                    points=[[time.time(), 45.2]],
                    tags=["env:production"],
                )
            ])
            
            # Create event
            await dd.create_event(DatadogEvent(
                title="Investigation Started",
                text="Investigating high latency alert",
                alert_type=AlertType.INFO,
            ))
            
            # Query logs
            logs = await dd.query_logs("service:api status:error")
    """
    
    def __init__(self, config: DatadogConfig):
        """Initialize Datadog integration.
        
        Args:
            config: Datadog configuration
        """
        self.dd_config = config
        
        conn_config = ConnectionConfig(
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            headers={
                "Content-Type": "application/json",
                "DD-API-KEY": config.api_key,
                "DD-APPLICATION-KEY": config.app_key,
            },
        )
        
        super().__init__(config=conn_config)
    
    @property
    def name(self) -> str:
        return "datadog"
    
    async def health_check(self) -> HealthCheckResult:
        """Check Datadog connectivity."""
        try:
            start = asyncio.get_event_loop().time()
            await self._request("GET", "/api/v1/validate")
            latency = (asyncio.get_event_loop().time() - start) * 1000
            
            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message="Connected to Datadog",
                latency_ms=latency,
                details={"site": self.dd_config.site},
            )
        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=str(e),
            )
    
    # Metrics
    
    async def submit_metrics(
        self,
        metrics: List[DatadogMetric],
    ) -> None:
        """Submit metrics to Datadog.
        
        Args:
            metrics: List of metrics to submit
        """
        # Build series payload
        series = []
        for metric in metrics:
            # Add default tags
            tags = list(metric.tags)
            tags.extend(self.dd_config.default_tags)
            
            point_data = {
                "metric": metric.metric,
                "type": metric.type.value,
                "points": metric.points,
                "tags": tags,
            }
            
            if metric.host:
                point_data["host"] = metric.host
            if metric.interval:
                point_data["interval"] = metric.interval
            if metric.unit:
                point_data["unit"] = metric.unit
            
            series.append(point_data)
        
        await self._request(
            "POST",
            "/api/v2/series",
            json={"series": series},
        )
        
        logger.debug(
            "Submitted metrics to Datadog",
            count=len(metrics),
        )
    
    async def submit_metric(
        self,
        name: str,
        value: float,
        metric_type: MetricType = MetricType.GAUGE,
        tags: Optional[List[str]] = None,
        host: Optional[str] = None,
    ) -> None:
        """Submit a single metric.
        
        Args:
            name: Metric name
            value: Metric value
            metric_type: Metric type
            tags: Tags
            host: Host name
        """
        metric = DatadogMetric(
            metric=name,
            type=metric_type,
            points=[[time.time(), value]],
            tags=tags or [],
            host=host,
        )
        
        await self.submit_metrics([metric])
    
    async def query_metrics(
        self,
        query: str,
        from_time: int,
        to_time: int,
    ) -> Dict[str, Any]:
        """Query metrics.
        
        Args:
            query: Metrics query
            from_time: Start timestamp
            to_time: End timestamp
            
        Returns:
            Query results
        """
        data = await self._request(
            "GET",
            "/api/v1/query",
            params={
                "query": query,
                "from": from_time,
                "to": to_time,
            },
        )
        
        return data
    
    # Events
    
    async def create_event(
        self,
        event: DatadogEvent,
    ) -> Dict[str, Any]:
        """Create an event.
        
        Args:
            event: Event to create
            
        Returns:
            Created event data
        """
        # Add default tags
        tags = list(event.tags)
        tags.extend(self.dd_config.default_tags)
        
        payload = {
            "title": event.title,
            "text": event.text,
            "alert_type": event.alert_type.value,
            "priority": event.priority.value,
            "tags": tags,
        }
        
        if event.date_happened:
            payload["date_happened"] = event.date_happened
        if event.aggregation_key:
            payload["aggregation_key"] = event.aggregation_key
        if event.source_type_name:
            payload["source_type_name"] = event.source_type_name
        if event.host:
            payload["host"] = event.host
        
        data = await self._request(
            "POST",
            "/api/v1/events",
            json=payload,
        )
        
        logger.info(
            "Created Datadog event",
            title=event.title,
            alert_type=event.alert_type.value,
        )
        
        return data
    
    async def get_event(self, event_id: int) -> Dict[str, Any]:
        """Get an event by ID.
        
        Args:
            event_id: Event ID
            
        Returns:
            Event data
        """
        data = await self._request(
            "GET",
            f"/api/v1/events/{event_id}",
        )
        
        return data.get("event", {})
    
    async def query_events(
        self,
        start: int,
        end: int,
        priority: Optional[Priority] = None,
        tags: Optional[List[str]] = None,
        sources: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query events.
        
        Args:
            start: Start timestamp
            end: End timestamp
            priority: Filter by priority
            tags: Filter by tags
            sources: Filter by sources
            
        Returns:
            List of events
        """
        params = {
            "start": start,
            "end": end,
        }
        
        if priority:
            params["priority"] = priority.value
        if tags:
            params["tags"] = ",".join(tags)
        if sources:
            params["sources"] = sources
        
        data = await self._request(
            "GET",
            "/api/v1/events",
            params=params,
        )
        
        return data.get("events", [])
    
    # Monitors
    
    async def create_monitor(
        self,
        monitor: DatadogMonitor,
    ) -> DatadogMonitor:
        """Create a monitor.
        
        Args:
            monitor: Monitor to create
            
        Returns:
            Created monitor
        """
        payload = {
            "name": monitor.name,
            "type": monitor.type.value,
            "query": monitor.query,
            "message": monitor.message,
            "tags": monitor.tags,
            "options": monitor.options,
        }
        
        if monitor.priority:
            payload["priority"] = monitor.priority
        
        data = await self._request(
            "POST",
            "/api/v1/monitor",
            json=payload,
        )
        
        monitor.id = data.get("id")
        
        logger.info(
            "Created Datadog monitor",
            id=monitor.id,
            name=monitor.name,
        )
        
        return monitor
    
    async def get_monitor(self, monitor_id: int) -> DatadogMonitor:
        """Get a monitor by ID.
        
        Args:
            monitor_id: Monitor ID
            
        Returns:
            DatadogMonitor
        """
        data = await self._request(
            "GET",
            f"/api/v1/monitor/{monitor_id}",
        )
        
        return DatadogMonitor(
            id=data.get("id"),
            name=data.get("name", ""),
            type=MonitorType(data.get("type", "query alert")),
            query=data.get("query", ""),
            message=data.get("message", ""),
            tags=data.get("tags", []),
            options=data.get("options", {}),
            priority=data.get("priority"),
            overall_state=MonitorState(data["overall_state"]) if data.get("overall_state") else None,
        )
    
    async def list_monitors(
        self,
        group_states: Optional[List[str]] = None,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        monitor_tags: Optional[List[str]] = None,
    ) -> List[DatadogMonitor]:
        """List monitors.
        
        Args:
            group_states: Filter by group states
            name: Filter by name
            tags: Filter by tags
            monitor_tags: Filter by monitor tags
            
        Returns:
            List of monitors
        """
        params = {}
        
        if group_states:
            params["group_states"] = ",".join(group_states)
        if name:
            params["name"] = name
        if tags:
            params["tags"] = ",".join(tags)
        if monitor_tags:
            params["monitor_tags"] = ",".join(monitor_tags)
        
        data = await self._request(
            "GET",
            "/api/v1/monitor",
            params=params if params else None,
        )
        
        monitors = []
        for m in data:
            monitors.append(DatadogMonitor(
                id=m.get("id"),
                name=m.get("name", ""),
                type=MonitorType(m.get("type", "query alert")),
                query=m.get("query", ""),
                message=m.get("message", ""),
                tags=m.get("tags", []),
                overall_state=MonitorState(m["overall_state"]) if m.get("overall_state") else None,
            ))
        
        return monitors
    
    async def update_monitor(
        self,
        monitor_id: int,
        updates: Dict[str, Any],
    ) -> DatadogMonitor:
        """Update a monitor.
        
        Args:
            monitor_id: Monitor ID
            updates: Fields to update
            
        Returns:
            Updated monitor
        """
        data = await self._request(
            "PUT",
            f"/api/v1/monitor/{monitor_id}",
            json=updates,
        )
        
        return await self.get_monitor(monitor_id)
    
    async def delete_monitor(self, monitor_id: int) -> None:
        """Delete a monitor.
        
        Args:
            monitor_id: Monitor ID
        """
        await self._request(
            "DELETE",
            f"/api/v1/monitor/{monitor_id}",
        )
        
        logger.info(
            "Deleted Datadog monitor",
            id=monitor_id,
        )
    
    async def mute_monitor(
        self,
        monitor_id: int,
        scope: Optional[str] = None,
        end: Optional[int] = None,
    ) -> None:
        """Mute a monitor.
        
        Args:
            monitor_id: Monitor ID
            scope: Mute scope
            end: End timestamp
        """
        payload = {}
        if scope:
            payload["scope"] = scope
        if end:
            payload["end"] = end
        
        await self._request(
            "POST",
            f"/api/v1/monitor/{monitor_id}/mute",
            json=payload if payload else None,
        )
    
    async def unmute_monitor(
        self,
        monitor_id: int,
        scope: Optional[str] = None,
    ) -> None:
        """Unmute a monitor.
        
        Args:
            monitor_id: Monitor ID
            scope: Unmute scope
        """
        payload = {}
        if scope:
            payload["scope"] = scope
        
        await self._request(
            "POST",
            f"/api/v1/monitor/{monitor_id}/unmute",
            json=payload if payload else None,
        )
    
    # Service Checks
    
    async def submit_service_check(
        self,
        check: DatadogServiceCheck,
    ) -> None:
        """Submit a service check.
        
        Args:
            check: Service check to submit
        """
        payload = {
            "check": check.check,
            "host_name": check.host_name,
            "status": check.status,
            "tags": check.tags,
        }
        
        if check.timestamp:
            payload["timestamp"] = check.timestamp
        if check.message:
            payload["message"] = check.message
        
        await self._request(
            "POST",
            "/api/v1/check_run",
            json=payload,
        )
    
    # Logs
    
    async def query_logs(
        self,
        query: str,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query logs.
        
        Args:
            query: Log query
            from_time: Start time
            to_time: End time
            limit: Maximum results
            
        Returns:
            List of log entries
        """
        # Default time range: last hour
        now = datetime.now(timezone.utc)
        to_time = to_time or now
        from_time = from_time or (now - __import__('datetime').timedelta(hours=1))
        
        payload = {
            "filter": {
                "query": query,
                "from": from_time.isoformat(),
                "to": to_time.isoformat(),
            },
            "page": {
                "limit": limit,
            },
        }
        
        data = await self._request(
            "POST",
            "/api/v2/logs/events/search",
            json=payload,
        )
        
        return data.get("data", [])
    
    async def send_logs(
        self,
        logs: List[DatadogLog],
    ) -> None:
        """Send logs to Datadog.
        
        Args:
            logs: Logs to send
        """
        payload = []
        
        for log in logs:
            entry = {
                "message": log.message,
                "ddsource": "autosre",
                "ddtags": ",".join(log.tags + self.dd_config.default_tags),
            }
            
            if log.service:
                entry["service"] = log.service
            if log.status:
                entry["status"] = log.status
            if log.host:
                entry["hostname"] = log.host
            
            # Add custom attributes
            for key, value in log.attributes.items():
                entry[key] = value
            
            payload.append(entry)
        
        # Use log intake endpoint
        client = await self._get_client()
        
        # Logs API has different endpoint
        log_url = self.dd_config.base_url.replace("api.", "http-intake.logs.")
        
        response = await client.post(
            f"{log_url}/api/v2/logs",
            json=payload,
        )
        response.raise_for_status()
        
        logger.debug(
            "Sent logs to Datadog",
            count=len(logs),
        )
    
    # Dashboard Shortcuts
    
    async def get_dashboard(self, dashboard_id: str) -> Dict[str, Any]:
        """Get a dashboard.
        
        Args:
            dashboard_id: Dashboard ID
            
        Returns:
            Dashboard data
        """
        return await self._request(
            "GET",
            f"/api/v1/dashboard/{dashboard_id}",
        )
    
    async def list_dashboards(self) -> List[Dict[str, Any]]:
        """List all dashboards.
        
        Returns:
            List of dashboards
        """
        data = await self._request(
            "GET",
            "/api/v1/dashboard",
        )
        
        return data.get("dashboards", [])
