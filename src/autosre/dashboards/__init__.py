"""
AutoSRE V2 Dashboards Module.

Dashboard generation and management with:
- DashboardGenerator: Auto-create Grafana dashboards
- PanelBuilder: Build panels from natural language
- TemplateEngine: SLO/SLI dashboard templates
- ExportManager: Export to JSON/Terraform

Example:
    from autosre.dashboards import DashboardGenerator

    generator = DashboardGenerator()
    dashboard = generator.create_service_dashboard("api-gateway")
    json_output = dashboard.to_grafana_json()
"""

from .models import (
    Dashboard,
    Panel,
    PanelType,
    Target,
    Row,
    Annotation,
    Variable,
    DashboardLink,
    TimeRange,
)

from .generator import (
    DashboardGenerator,
    GeneratorConfig,
    ServiceDashboard,
    SLODashboard,
    InfrastructureDashboard,
)

from .panels import (
    PanelBuilder,
    PanelConfig,
    MetricPanel,
    LogsPanel,
    TracesPanel,
    TablePanel,
    StatPanel,
    GaugePanel,
)

from .templates import (
    TemplateEngine,
    DashboardTemplate,
    TemplateVariable,
    SLOTemplate,
    K8sTemplate,
    GoldenSignalsTemplate,
)

from .export import (
    ExportManager,
    ExportFormat,
    GrafanaExporter,
    TerraformExporter,
    JsonnetExporter,
)

__all__ = [
    # Models
    "Dashboard",
    "Panel",
    "PanelType",
    "Target",
    "Row",
    "Annotation",
    "Variable",
    "DashboardLink",
    "TimeRange",
    # Generator
    "DashboardGenerator",
    "GeneratorConfig",
    "ServiceDashboard",
    "SLODashboard",
    "InfrastructureDashboard",
    # Panels
    "PanelBuilder",
    "PanelConfig",
    "MetricPanel",
    "LogsPanel",
    "TracesPanel",
    "TablePanel",
    "StatPanel",
    "GaugePanel",
    # Templates
    "TemplateEngine",
    "DashboardTemplate",
    "TemplateVariable",
    "SLOTemplate",
    "K8sTemplate",
    "GoldenSignalsTemplate",
    # Export
    "ExportManager",
    "ExportFormat",
    "GrafanaExporter",
    "TerraformExporter",
    "JsonnetExporter",
]
