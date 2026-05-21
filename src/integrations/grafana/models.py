"""Pydantic models for Grafana entities."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DashboardType(str, Enum):
    """Dashboard types."""
    DASH_DB = "dash-db"
    DASH_FOLDER = "dash-folder"
    DASH_HOME = "dash-home"


class AlertState(str, Enum):
    """Grafana alert states."""
    ALERTING = "alerting"
    NO_DATA = "no_data"
    PENDING = "pending"
    NORMAL = "normal"
    OK = "ok"
    PAUSED = "paused"
    UNKNOWN = "unknown"


class AnnotationType(str, Enum):
    """Annotation types."""
    ALERT = "alert"
    ANNOTATION = "annotation"


# Datasource Models

class DatasourcePlugin(BaseModel):
    """Datasource plugin info."""
    type: str = Field(..., description="Plugin type")
    name: str = Field(..., description="Plugin name")
    
    model_config = {"extra": "allow"}


class Datasource(BaseModel):
    """A Grafana datasource."""
    id: int = Field(..., description="Datasource ID")
    uid: str = Field(..., description="Datasource UID")
    org_id: int | None = Field(default=None, alias="orgId", description="Organization ID")
    name: str = Field(..., description="Datasource name")
    type: str = Field(..., description="Datasource type (prometheus, elasticsearch, etc.)")
    type_name: str | None = Field(default=None, alias="typeName", description="Type display name")
    type_logo_url: str | None = Field(default=None, alias="typeLogoUrl", description="Type logo URL")
    access: str = Field(default="proxy", description="Access mode (proxy/direct)")
    url: str = Field(default="", description="Datasource URL")
    user: str | None = Field(default=None, description="Basic auth user")
    database: str | None = Field(default=None, description="Database name")
    basic_auth: bool = Field(default=False, alias="basicAuth", description="Basic auth enabled")
    basic_auth_user: str | None = Field(default=None, alias="basicAuthUser", description="Basic auth user")
    with_credentials: bool = Field(default=False, alias="withCredentials", description="With credentials")
    is_default: bool = Field(default=False, alias="isDefault", description="Is default datasource")
    json_data: dict[str, Any] = Field(default_factory=dict, alias="jsonData", description="JSON config")
    read_only: bool = Field(default=False, alias="readOnly", description="Read-only")
    
    model_config = {"extra": "allow", "populate_by_name": True}


class DatasourceHealth(BaseModel):
    """Datasource health check result."""
    status: str = Field(..., description="Health status")
    message: str = Field(default="", description="Health message")
    
    model_config = {"extra": "allow"}


# Dashboard Models

class DashboardMeta(BaseModel):
    """Dashboard metadata."""
    type: DashboardType | str = Field(default=DashboardType.DASH_DB, description="Dashboard type")
    can_save: bool = Field(default=True, alias="canSave", description="Can save")
    can_edit: bool = Field(default=True, alias="canEdit", description="Can edit")
    can_admin: bool = Field(default=False, alias="canAdmin", description="Can admin")
    can_star: bool = Field(default=True, alias="canStar", description="Can star")
    can_delete: bool = Field(default=True, alias="canDelete", description="Can delete")
    slug: str = Field(default="", description="Dashboard slug")
    url: str = Field(default="", description="Dashboard URL")
    expires: datetime | None = Field(default=None, description="Snapshot expiration")
    created: datetime | None = Field(default=None, description="Creation time")
    updated: datetime | None = Field(default=None, description="Last update time")
    updated_by: str | None = Field(default=None, alias="updatedBy", description="Updated by user")
    created_by: str | None = Field(default=None, alias="createdBy", description="Created by user")
    version: int = Field(default=1, description="Dashboard version")
    folder_id: int | None = Field(default=None, alias="folderId", description="Folder ID")
    folder_uid: str | None = Field(default=None, alias="folderUid", description="Folder UID")
    folder_title: str | None = Field(default=None, alias="folderTitle", description="Folder title")
    folder_url: str | None = Field(default=None, alias="folderUrl", description="Folder URL")
    provisioned: bool = Field(default=False, description="Is provisioned")
    provisioned_external_id: str | None = Field(default=None, alias="provisionedExternalId")
    is_starred: bool = Field(default=False, alias="isStarred", description="Is starred")
    
    model_config = {"extra": "allow", "populate_by_name": True}


class Panel(BaseModel):
    """A dashboard panel."""
    id: int = Field(..., description="Panel ID")
    type: str = Field(..., description="Panel type (graph, stat, table, etc.)")
    title: str = Field(default="", description="Panel title")
    description: str | None = Field(default=None, description="Panel description")
    grid_pos: dict[str, int] | None = Field(default=None, alias="gridPos", description="Grid position")
    datasource: str | dict[str, Any] | None = Field(default=None, description="Datasource ref")
    targets: list[dict[str, Any]] = Field(default_factory=list, description="Query targets")
    options: dict[str, Any] = Field(default_factory=dict, description="Panel options")
    field_config: dict[str, Any] | None = Field(default=None, alias="fieldConfig", description="Field config")
    transformations: list[dict[str, Any]] = Field(default_factory=list, description="Data transformations")
    
    model_config = {"extra": "allow", "populate_by_name": True}


class TemplateVariable(BaseModel):
    """Dashboard template variable."""
    name: str = Field(..., description="Variable name")
    type: str = Field(..., description="Variable type")
    label: str | None = Field(default=None, description="Display label")
    query: str | dict[str, Any] | None = Field(default=None, description="Variable query")
    datasource: str | dict[str, Any] | None = Field(default=None, description="Datasource")
    current: dict[str, Any] | None = Field(default=None, description="Current value")
    options: list[dict[str, Any]] = Field(default_factory=list, description="Options")
    multi: bool = Field(default=False, description="Allow multi-select")
    include_all: bool = Field(default=False, alias="includeAll", description="Include all option")
    refresh: int = Field(default=0, description="Refresh mode")
    hide: int = Field(default=0, description="Hide mode")
    
    model_config = {"extra": "allow", "populate_by_name": True}


class Dashboard(BaseModel):
    """A Grafana dashboard."""
    id: int | None = Field(default=None, description="Dashboard ID")
    uid: str = Field(..., description="Dashboard UID")
    title: str = Field(..., description="Dashboard title")
    description: str | None = Field(default=None, description="Dashboard description")
    tags: list[str] = Field(default_factory=list, description="Dashboard tags")
    style: str = Field(default="dark", description="Dashboard style")
    timezone: str = Field(default="browser", description="Timezone")
    editable: bool = Field(default=True, description="Is editable")
    hide_controls: bool = Field(default=False, alias="hideControls", description="Hide controls")
    graphTooltip: int = Field(default=0, description="Graph tooltip mode")
    panels: list[Panel] = Field(default_factory=list, description="Dashboard panels")
    templating: dict[str, list[TemplateVariable]] = Field(default_factory=dict, description="Template vars")
    annotations: dict[str, Any] = Field(default_factory=dict, description="Annotations config")
    refresh: str | None = Field(default=None, description="Auto-refresh interval")
    schema_version: int = Field(default=16, alias="schemaVersion", description="Schema version")
    version: int | None = Field(default=None, description="Dashboard version")
    links: list[dict[str, Any]] = Field(default_factory=list, description="Dashboard links")
    time: dict[str, str] | None = Field(default=None, description="Default time range")
    fiscal_year_start_month: int = Field(default=0, alias="fiscalYearStartMonth")
    live_now: bool = Field(default=False, alias="liveNow", description="Live mode")
    week_start: str = Field(default="", alias="weekStart", description="Week start day")
    
    model_config = {"extra": "allow", "populate_by_name": True}
    
    @property
    def template_variables(self) -> list[TemplateVariable]:
        """Get template variables."""
        return self.templating.get("list", [])


class DashboardResponse(BaseModel):
    """Response from getting a dashboard."""
    dashboard: Dashboard = Field(..., description="Dashboard data")
    meta: DashboardMeta = Field(..., description="Dashboard metadata")
    
    model_config = {"extra": "allow"}


class DashboardSearchResult(BaseModel):
    """A search result item."""
    id: int = Field(..., description="Dashboard ID")
    uid: str = Field(..., description="Dashboard UID")
    title: str = Field(..., description="Dashboard title")
    uri: str = Field(default="", description="Dashboard URI")
    url: str = Field(default="", description="Dashboard URL")
    slug: str = Field(default="", description="Dashboard slug")
    type: DashboardType | str = Field(default=DashboardType.DASH_DB, description="Result type")
    tags: list[str] = Field(default_factory=list, description="Dashboard tags")
    is_starred: bool = Field(default=False, alias="isStarred", description="Is starred")
    folder_id: int | None = Field(default=None, alias="folderId", description="Folder ID")
    folder_uid: str | None = Field(default=None, alias="folderUid", description="Folder UID")
    folder_title: str | None = Field(default=None, alias="folderTitle", description="Folder title")
    folder_url: str | None = Field(default=None, alias="folderUrl", description="Folder URL")
    sort_meta: int = Field(default=0, alias="sortMeta", description="Sort metadata")
    
    model_config = {"extra": "allow", "populate_by_name": True}


# Annotation Models

class Annotation(BaseModel):
    """A Grafana annotation."""
    id: int | None = Field(default=None, description="Annotation ID")
    alert_id: int | None = Field(default=None, alias="alertId", description="Alert ID")
    alert_name: str | None = Field(default=None, alias="alertName", description="Alert name")
    dashboard_id: int | None = Field(default=None, alias="dashboardId", description="Dashboard ID")
    dashboard_uid: str | None = Field(default=None, alias="dashboardUID", description="Dashboard UID")
    panel_id: int | None = Field(default=None, alias="panelId", description="Panel ID")
    user_id: int | None = Field(default=None, alias="userId", description="User ID")
    user_name: str | None = Field(default=None, alias="userName", description="User name")
    new_state: str | None = Field(default=None, alias="newState", description="New alert state")
    prev_state: str | None = Field(default=None, alias="prevState", description="Previous alert state")
    created: int | None = Field(default=None, description="Created timestamp (ms)")
    updated: int | None = Field(default=None, description="Updated timestamp (ms)")
    time: int = Field(..., description="Annotation time (ms)")
    time_end: int | None = Field(default=None, alias="timeEnd", description="End time for region")
    text: str = Field(default="", description="Annotation text")
    tags: list[str] = Field(default_factory=list, description="Annotation tags")
    data: dict[str, Any] = Field(default_factory=dict, description="Additional data")
    
    model_config = {"extra": "allow", "populate_by_name": True}
    
    @property
    def time_datetime(self) -> datetime:
        """Get annotation time as datetime."""
        return datetime.fromtimestamp(self.time / 1000)
    
    @property
    def is_region(self) -> bool:
        """Check if this is a region annotation."""
        return self.time_end is not None and self.time_end > self.time


# Alert Models

class AlertNotification(BaseModel):
    """Alert notification channel."""
    id: int = Field(..., description="Channel ID")
    uid: str = Field(..., description="Channel UID")
    name: str = Field(..., description="Channel name")
    type: str = Field(..., description="Channel type")
    is_default: bool = Field(default=False, alias="isDefault", description="Is default")
    send_reminder: bool = Field(default=False, alias="sendReminder", description="Send reminders")
    disable_resolve_message: bool = Field(default=False, alias="disableResolveMessage")
    created: datetime | None = Field(default=None, description="Creation time")
    updated: datetime | None = Field(default=None, description="Last update time")
    settings: dict[str, Any] = Field(default_factory=dict, description="Channel settings")
    
    model_config = {"extra": "allow", "populate_by_name": True}


class AlertRule(BaseModel):
    """A Grafana alert rule (legacy)."""
    id: int = Field(..., description="Alert ID")
    dashboard_id: int = Field(..., alias="dashboardId", description="Dashboard ID")
    dashboard_uid: str | None = Field(default=None, alias="dashboardUid", description="Dashboard UID")
    dashboard_slug: str | None = Field(default=None, alias="dashboardSlug", description="Dashboard slug")
    panel_id: int = Field(..., alias="panelId", description="Panel ID")
    name: str = Field(..., description="Alert name")
    state: AlertState = Field(..., description="Alert state")
    new_state_date: datetime | None = Field(default=None, alias="newStateDate", description="State change time")
    eval_date: datetime | None = Field(default=None, alias="evalDate", description="Last evaluation time")
    eval_data: dict[str, Any] | None = Field(default=None, alias="evalData", description="Evaluation data")
    execution_error: str | None = Field(default=None, alias="executionError", description="Execution error")
    url: str | None = Field(default=None, description="Alert URL")
    handler: int = Field(default=1, description="Handler")
    silenced: bool = Field(default=False, description="Is silenced")
    frequency: int = Field(default=60, description="Evaluation frequency (seconds)")
    for_duration: int = Field(default=0, alias="for", description="For duration (seconds)")
    
    model_config = {"extra": "allow", "populate_by_name": True}


# Query Models

class QueryTarget(BaseModel):
    """A query target."""
    ref_id: str = Field(..., alias="refId", description="Reference ID")
    datasource: str | dict[str, Any] | None = Field(default=None, description="Datasource")
    expr: str | None = Field(default=None, description="Query expression (Prometheus)")
    query: str | None = Field(default=None, description="Query string (generic)")
    format: str | None = Field(default=None, description="Result format")
    instant: bool = Field(default=False, description="Instant query")
    range: bool = Field(default=True, description="Range query")
    interval: str | None = Field(default=None, description="Query interval")
    interval_ms: int | None = Field(default=None, alias="intervalMs", description="Interval in ms")
    legend_format: str | None = Field(default=None, alias="legendFormat", description="Legend format")
    
    model_config = {"extra": "allow", "populate_by_name": True}


class QueryRequest(BaseModel):
    """A query request."""
    queries: list[QueryTarget] = Field(..., description="Query targets")
    from_time: str = Field(..., alias="from", description="Start time")
    to_time: str = Field(..., alias="to", description="End time")
    
    model_config = {"extra": "allow", "populate_by_name": True}


class QueryResultFrame(BaseModel):
    """A data frame in query results."""
    schema: dict[str, Any] = Field(default_factory=dict, description="Frame schema")
    data: dict[str, Any] = Field(default_factory=dict, description="Frame data")
    
    model_config = {"extra": "allow"}


class QueryResult(BaseModel):
    """Query result."""
    ref_id: str = Field(default="", alias="refId", description="Reference ID")
    meta: dict[str, Any] = Field(default_factory=dict, description="Result metadata")
    frames: list[QueryResultFrame] = Field(default_factory=list, description="Data frames")
    
    model_config = {"extra": "allow", "populate_by_name": True}


class QueryResponse(BaseModel):
    """Response from datasource query."""
    results: dict[str, QueryResult] = Field(default_factory=dict, description="Results by ref ID")
    
    model_config = {"extra": "allow"}


# Folder Models

class Folder(BaseModel):
    """A Grafana folder."""
    id: int = Field(..., description="Folder ID")
    uid: str = Field(..., description="Folder UID")
    title: str = Field(..., description="Folder title")
    url: str = Field(default="", description="Folder URL")
    has_acl: bool = Field(default=False, alias="hasAcl", description="Has ACL")
    can_save: bool = Field(default=True, alias="canSave", description="Can save")
    can_edit: bool = Field(default=True, alias="canEdit", description="Can edit")
    can_admin: bool = Field(default=False, alias="canAdmin", description="Can admin")
    can_delete: bool = Field(default=True, alias="canDelete", description="Can delete")
    created: datetime | None = Field(default=None, description="Creation time")
    created_by: str | None = Field(default=None, alias="createdBy", description="Created by")
    updated: datetime | None = Field(default=None, description="Last update time")
    updated_by: str | None = Field(default=None, alias="updatedBy", description="Updated by")
    version: int = Field(default=1, description="Folder version")
    
    model_config = {"extra": "allow", "populate_by_name": True}


# Organization/User Models

class User(BaseModel):
    """A Grafana user."""
    id: int = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    name: str = Field(default="", description="User name")
    login: str = Field(..., description="User login")
    theme: str = Field(default="", description="User theme")
    org_id: int = Field(default=1, alias="orgId", description="Organization ID")
    is_grafana_admin: bool = Field(default=False, alias="isGrafanaAdmin", description="Is admin")
    is_disabled: bool = Field(default=False, alias="isDisabled", description="Is disabled")
    is_external: bool = Field(default=False, alias="isExternal", description="Is external user")
    auth_labels: list[str] = Field(default_factory=list, alias="authLabels", description="Auth labels")
    updated_at: datetime | None = Field(default=None, alias="updatedAt", description="Last update")
    created_at: datetime | None = Field(default=None, alias="createdAt", description="Creation time")
    avatar_url: str | None = Field(default=None, alias="avatarUrl", description="Avatar URL")
    
    model_config = {"extra": "allow", "populate_by_name": True}


class Organization(BaseModel):
    """A Grafana organization."""
    id: int = Field(..., description="Organization ID")
    name: str = Field(..., description="Organization name")
    address: dict[str, Any] = Field(default_factory=dict, description="Address info")
    
    model_config = {"extra": "allow"}


# Render Models

class RenderOptions(BaseModel):
    """Options for rendering a panel."""
    width: int = Field(default=800, description="Image width")
    height: int = Field(default=400, description="Image height")
    from_time: str = Field(default="now-6h", alias="from", description="Start time")
    to_time: str = Field(default="now", alias="to", description="End time")
    tz: str = Field(default="", description="Timezone")
    timeout: int = Field(default=60, description="Render timeout (seconds)")
    scale: int = Field(default=1, description="Render scale")
    
    model_config = {"extra": "allow", "populate_by_name": True}
