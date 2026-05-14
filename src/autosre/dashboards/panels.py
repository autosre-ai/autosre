"""Panel builders for AutoSRE V2 dashboards."""
from dataclasses import dataclass, field
from typing import Any, Optional, List
from .models import Panel, PanelType, Target, Threshold

@dataclass
class PanelConfig:
    """Configuration for panel building."""
    default_height: int = 8
    default_width: int = 12
    prometheus_uid: str = "prometheus"
    loki_uid: str = "loki"
    tempo_uid: str = "tempo"

class PanelBuilder:
    """Builds panels with common configurations."""
    def __init__(self, config: Optional[PanelConfig] = None):
        self.config = config or PanelConfig()
    
    def timeseries(self, title: str, query: str, **kwargs) -> Panel:
        return Panel(title=title, type=PanelType.TIMESERIES,
            width=kwargs.get("width", self.config.default_width),
            height=kwargs.get("height", self.config.default_height),
            targets=[Target(expr=query, legend_format=kwargs.get("legend", ""),
                datasource_uid=self.config.prometheus_uid)])
    
    def stat(self, title: str, query: str, **kwargs) -> Panel:
        return Panel(title=title, type=PanelType.STAT,
            width=kwargs.get("width", 6), height=kwargs.get("height", 4),
            targets=[Target(expr=query, instant=True, datasource_uid=self.config.prometheus_uid)])
    
    def gauge(self, title: str, query: str, min_val: float = 0, max_val: float = 1, **kwargs) -> Panel:
        return Panel(title=title, type=PanelType.GAUGE,
            width=kwargs.get("width", 6), height=kwargs.get("height", 6),
            targets=[Target(expr=query, instant=True, datasource_uid=self.config.prometheus_uid)],
            field_config={"defaults": {"min": min_val, "max": max_val}})
    
    def table(self, title: str, query: str, **kwargs) -> Panel:
        return Panel(title=title, type=PanelType.TABLE,
            width=kwargs.get("width", 12), height=kwargs.get("height", 8),
            targets=[Target(expr=query, instant=True, datasource_uid=self.config.prometheus_uid)])
    
    def logs(self, title: str, query: str, **kwargs) -> Panel:
        return Panel(title=title, type=PanelType.LOGS,
            width=kwargs.get("width", 24), height=kwargs.get("height", 10),
            targets=[Target(expr=query, datasource_uid=self.config.loki_uid, datasource_type="loki")])

# Convenience aliases
MetricPanel = PanelBuilder
LogsPanel = PanelBuilder
TracesPanel = PanelBuilder
TablePanel = PanelBuilder
StatPanel = PanelBuilder
GaugePanel = PanelBuilder
