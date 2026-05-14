"""
Dashboard data models for AutoSRE V2.

Provides canonical representations for Grafana-compatible dashboards.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict


class PanelType(str, Enum):
    """Type of dashboard panel."""
    
    TIMESERIES = "timeseries"
    GRAPH = "graph"  # Legacy
    STAT = "stat"
    GAUGE = "gauge"
    BAR_GAUGE = "bargauge"
    TABLE = "table"
    TEXT = "text"
    LOGS = "logs"
    TRACES = "traces"
    HEATMAP = "heatmap"
    HISTOGRAM = "histogram"
    PIE = "piechart"
    NODE_GRAPH = "nodeGraph"
    ALERT_LIST = "alertlist"
    NEWS = "news"
    ROW = "row"


class ThresholdMode(str, Enum):
    """Threshold mode for visualizations."""
    
    ABSOLUTE = "absolute"
    PERCENTAGE = "percentage"


@dataclass
class TimeRange:
    """Dashboard time range."""
    
    from_time: str = "now-6h"
    to_time: str = "now"
    
    def to_dict(self) -> dict[str, str]:
        return {"from": self.from_time, "to": self.to_time}


@dataclass
class Threshold:
    """Visualization threshold."""
    
    value: Optional[float] = None
    color: str = "green"
    state: str = "ok"  # ok, warning, critical
    
    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"color": self.color}
        if self.value is not None:
            result["value"] = self.value
        return result


@dataclass
class Target:
    """Panel data source target (query)."""
    
    expr: str  # PromQL query
    legend_format: str = ""
    ref_id: str = "A"
    
    # Data source
    datasource_uid: Optional[str] = None
    datasource_type: str = "prometheus"
    
    # Additional settings
    instant: bool = False
    range: bool = True
    interval: str = ""
    
    # Loki/Logs specific
    log_query: Optional[str] = None
    
    # Tempo/Traces specific
    trace_query: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        result = {
            "expr": self.expr,
            "legendFormat": self.legend_format,
            "refId": self.ref_id,
            "instant": self.instant,
            "range": self.range,
        }
        
        if self.datasource_uid:
            result["datasource"] = {
                "uid": self.datasource_uid,
                "type": self.datasource_type,
            }
        
        if self.interval:
            result["interval"] = self.interval
        
        return result


@dataclass
class FieldOverride:
    """Field override configuration."""
    
    field_name: str
    properties: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "matcher": {
                "id": "byName",
                "options": self.field_name,
            },
            "properties": [
                {"id": k, "value": v}
                for k, v in self.properties.items()
            ],
        }


@dataclass
class Panel:
    """Dashboard panel."""
    
    title: str
    type: PanelType
    
    # Positioning
    x: int = 0
    y: int = 0
    width: int = 12
    height: int = 8
    
    # Data
    targets: list[Target] = field(default_factory=list)
    
    # Visualization
    description: str = ""
    transparent: bool = False
    
    # Options (type-specific)
    options: dict[str, Any] = field(default_factory=dict)
    field_config: dict[str, Any] = field(default_factory=dict)
    
    # Thresholds
    thresholds: list[Threshold] = field(default_factory=list)
    
    # Overrides
    overrides: list[FieldOverride] = field(default_factory=list)
    
    # Links
    links: list[dict] = field(default_factory=list)
    
    # ID (auto-generated)
    id: Optional[int] = None
    
    def to_dict(self) -> dict[str, Any]:
        result = {
            "title": self.title,
            "type": self.type.value,
            "gridPos": {
                "x": self.x,
                "y": self.y,
                "w": self.width,
                "h": self.height,
            },
            "targets": [t.to_dict() for t in self.targets],
            "options": self.options,
            "fieldConfig": self._build_field_config(),
            "transparent": self.transparent,
        }
        
        if self.id is not None:
            result["id"] = self.id
        
        if self.description:
            result["description"] = self.description
        
        if self.links:
            result["links"] = self.links
        
        return result
    
    def _build_field_config(self) -> dict[str, Any]:
        """Build field configuration."""
        config: dict[str, Any] = {
            "defaults": dict(self.field_config.get("defaults", {})),
            "overrides": [o.to_dict() for o in self.overrides],
        }
        
        # Add overrides from field_config if present
        if "overrides" in self.field_config:
            config["overrides"].extend(self.field_config["overrides"])
        
        # Add thresholds
        if self.thresholds:
            config["defaults"]["thresholds"] = {
                "mode": "absolute",
                "steps": [t.to_dict() for t in self.thresholds],
            }
        
        return config


@dataclass
class Row:
    """Dashboard row (collapsible section)."""
    
    title: str
    collapsed: bool = False
    panels: list[Panel] = field(default_factory=list)
    
    # Positioning
    y: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "type": "row",
            "collapsed": self.collapsed,
            "gridPos": {"x": 0, "y": self.y, "w": 24, "h": 1},
            "panels": [p.to_dict() for p in self.panels] if self.collapsed else [],
        }


@dataclass
class Variable:
    """Dashboard template variable."""
    
    name: str
    type: str = "query"  # query, custom, constant, datasource, textbox
    label: str = ""
    
    # Query variable
    query: str = ""
    datasource_uid: Optional[str] = None
    
    # Options
    multi: bool = False
    include_all: bool = False
    all_value: str = ""
    
    # Custom variable
    options: list[dict[str, str]] = field(default_factory=list)
    
    # Default
    current: dict[str, Any] = field(default_factory=dict)
    
    # Display
    hide: int = 0  # 0=show, 1=hide label, 2=hide all
    
    # Refresh
    refresh: int = 1  # 0=never, 1=on dashboard load, 2=on time range change
    
    def to_dict(self) -> dict[str, Any]:
        result = {
            "name": self.name,
            "type": self.type,
            "label": self.label or self.name,
            "multi": self.multi,
            "includeAll": self.include_all,
            "hide": self.hide,
            "refresh": self.refresh,
        }
        
        if self.type == "query":
            result["query"] = self.query
            if self.datasource_uid:
                result["datasource"] = {"uid": self.datasource_uid}
        elif self.type == "custom":
            result["options"] = self.options
        
        if self.all_value:
            result["allValue"] = self.all_value
        
        if self.current:
            result["current"] = self.current
        
        return result


@dataclass
class Annotation:
    """Dashboard annotation query."""
    
    name: str
    datasource_uid: Optional[str] = None
    
    # Query
    expr: str = ""
    
    # Display
    enable: bool = True
    hide: bool = False
    icon_color: str = "red"
    
    # Built-in annotations
    built_in: int = 0  # 1 for built-in
    
    def to_dict(self) -> dict[str, Any]:
        result = {
            "name": self.name,
            "enable": self.enable,
            "hide": self.hide,
            "iconColor": self.icon_color,
            "builtIn": self.built_in,
        }
        
        if self.datasource_uid:
            result["datasource"] = {"uid": self.datasource_uid}
        
        if self.expr:
            result["expr"] = self.expr
        
        return result


@dataclass
class DashboardLink:
    """Dashboard link."""
    
    title: str
    type: str = "link"  # link, dashboards
    url: str = ""
    
    # Options
    target_blank: bool = True
    icon: str = "external link"
    include_vars: bool = False
    keep_time: bool = False
    
    # Dashboard links
    tags: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        result = {
            "title": self.title,
            "type": self.type,
            "targetBlank": self.target_blank,
            "icon": self.icon,
            "includeVars": self.include_vars,
            "keepTime": self.keep_time,
        }
        
        if self.url:
            result["url"] = self.url
        
        if self.tags:
            result["tags"] = self.tags
        
        return result


class Dashboard(BaseModel):
    """
    Complete Grafana dashboard definition.
    """
    
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    # Identity
    uid: str = Field(default_factory=lambda: str(uuid4())[:12])
    title: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    
    # Content
    panels: list[dict] = Field(default_factory=list)  # Use dict for flexibility
    rows: list[dict] = Field(default_factory=list)
    
    # Variables
    templating: list[dict] = Field(default_factory=list)
    
    # Annotations
    annotations: list[dict] = Field(default_factory=list)
    
    # Links
    links: list[dict] = Field(default_factory=list)
    
    # Settings
    editable: bool = True
    graphTooltip: int = 0  # 0=default, 1=shared crosshair, 2=shared tooltip
    timezone: str = "browser"
    
    # Time
    time: dict = Field(default_factory=lambda: {"from": "now-6h", "to": "now"})
    time_options: list[str] = Field(default_factory=lambda: [
        "5m", "15m", "1h", "6h", "12h", "24h", "2d", "7d", "30d"
    ])
    refresh: str = ""
    
    # Version
    version: int = 1
    schema_version: int = 39
    
    def add_panel(self, panel: Panel) -> None:
        """Add a panel to the dashboard."""
        # Assign ID if not set
        if panel.id is None:
            panel.id = len(self.panels) + 1
        self.panels.append(panel.to_dict())
    
    def add_row(self, row: Row) -> None:
        """Add a row to the dashboard."""
        self.rows.append(row.to_dict())
        # If row has panels and is not collapsed, add them
        if not row.collapsed:
            for panel in row.panels:
                self.add_panel(panel)
    
    def add_variable(self, variable: Variable) -> None:
        """Add a template variable."""
        self.templating.append(variable.to_dict())
    
    def add_annotation(self, annotation: Annotation) -> None:
        """Add an annotation."""
        self.annotations.append(annotation.to_dict())
    
    def add_link(self, link: DashboardLink) -> None:
        """Add a dashboard link."""
        self.links.append(link.to_dict())
    
    def set_time_range(self, time_range: TimeRange) -> None:
        """Set dashboard time range."""
        self.time = time_range.to_dict()
    
    def to_grafana_json(self) -> dict[str, Any]:
        """Export to Grafana JSON format."""
        # Combine rows and panels
        all_panels = list(self.rows) + self.panels
        
        return {
            "uid": self.uid,
            "title": self.title,
            "description": self.description,
            "tags": self.tags,
            "panels": all_panels,
            "templating": {"list": self.templating},
            "annotations": {"list": self.annotations},
            "links": self.links,
            "editable": self.editable,
            "graphTooltip": self.graphTooltip,
            "timezone": self.timezone,
            "time": self.time,
            "timepicker": {"refresh_intervals": self.time_options},
            "refresh": self.refresh,
            "version": self.version,
            "schemaVersion": self.schema_version,
        }
    
    def to_json(self, **kwargs) -> str:
        """Export to JSON string."""
        import json
        return json.dumps(self.to_grafana_json(), **kwargs)
