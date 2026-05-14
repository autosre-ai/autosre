"""Dashboard export for AutoSRE V2."""
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional
from .models import Dashboard

class ExportFormat(str, Enum):
    JSON = "json"
    TERRAFORM = "terraform"
    JSONNET = "jsonnet"

@dataclass
class GrafanaExporter:
    """Export dashboards to Grafana JSON format."""
    folder_uid: Optional[str] = None
    overwrite: bool = True
    
    def export(self, dashboard: Dashboard) -> dict[str, Any]:
        result = {"dashboard": dashboard.to_grafana_json(), "overwrite": self.overwrite}
        if self.folder_uid:
            result["folderUid"] = self.folder_uid
        return result
    
    def export_json(self, dashboard: Dashboard, indent: int = 2) -> str:
        return json.dumps(self.export(dashboard), indent=indent)

@dataclass
class TerraformExporter:
    """Export dashboards to Terraform format."""
    provider: str = "grafana"
    
    def export(self, dashboard: Dashboard, resource_name: str) -> str:
        json_config = json.dumps(dashboard.to_grafana_json())
        return f'''resource "grafana_dashboard" "{resource_name}" {{
  config_json = jsonencode({json_config})
}}'''

@dataclass
class JsonnetExporter:
    """Export dashboards to Jsonnet/Grafonnet format."""
    
    def export(self, dashboard: Dashboard) -> str:
        return f'''local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;

dashboard.new(
  '{dashboard.title}',
  uid='{dashboard.uid}',
  tags={json.dumps(dashboard.tags)},
)'''

class ExportManager:
    """Manages dashboard exports."""
    def __init__(self):
        self._grafana = GrafanaExporter()
        self._terraform = TerraformExporter()
        self._jsonnet = JsonnetExporter()
    
    def export(self, dashboard: Dashboard, format: ExportFormat = ExportFormat.JSON, **kwargs) -> str:
        if format == ExportFormat.JSON:
            return self._grafana.export_json(dashboard)
        elif format == ExportFormat.TERRAFORM:
            resource_name = kwargs.get("resource_name", dashboard.uid.replace("-", "_"))
            return self._terraform.export(dashboard, resource_name)
        elif format == ExportFormat.JSONNET:
            return self._jsonnet.export(dashboard)
        raise ValueError(f"Unknown format: {format}")
    
    def export_to_file(self, dashboard: Dashboard, path: str, format: ExportFormat = ExportFormat.JSON, **kwargs) -> None:
        content = self.export(dashboard, format, **kwargs)
        with open(path, "w") as f:
            f.write(content)
