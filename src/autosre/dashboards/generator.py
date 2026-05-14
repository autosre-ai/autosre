"""
Dashboard Generator for AutoSRE V2.

Auto-creates Grafana dashboards for various use cases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from autosre.utils.logging import get_logger
from .models import (
    Dashboard, Panel, PanelType, Target, Row, Variable, Annotation,
    Threshold, TimeRange, DashboardLink
)

logger = get_logger(__name__)


@dataclass
class GeneratorConfig:
    """Configuration for dashboard generation."""
    
    # Data sources
    prometheus_uid: str = "prometheus"
    loki_uid: str = "loki"
    tempo_uid: str = "tempo"
    
    # Defaults
    default_refresh: str = "30s"
    default_time_range: str = "6h"
    
    # Panel sizing
    panel_width: int = 12
    panel_height: int = 8
    stat_height: int = 4
    
    # Features
    include_logs: bool = True
    include_traces: bool = True
    include_alerting: bool = True
    
    # Tags
    default_tags: list[str] = field(default_factory=lambda: ["autosre", "auto-generated"])


class ServiceDashboard:
    """
    Generates a service-specific dashboard.
    
    Includes:
    - Golden signals (latency, traffic, errors, saturation)
    - SLO tracking
    - Logs panel
    - Traces panel
    """
    
    def __init__(self, config: Optional[GeneratorConfig] = None):
        self.config = config or GeneratorConfig()
    
    def generate(
        self,
        service_name: str,
        namespace: Optional[str] = None,
        custom_metrics: Optional[list[str]] = None,
    ) -> Dashboard:
        """Generate a service dashboard."""
        dashboard = Dashboard(
            title=f"{service_name} - Service Dashboard",
            description=f"Auto-generated dashboard for {service_name}",
            tags=self.config.default_tags + [service_name],
            refresh=self.config.default_refresh,
        )
        
        # Add variables
        self._add_variables(dashboard, namespace)
        
        # Add golden signals row
        self._add_golden_signals_row(dashboard, service_name)
        
        # Add SLO row
        self._add_slo_row(dashboard, service_name)
        
        # Add resource metrics row
        self._add_resource_row(dashboard, service_name)
        
        # Add logs row
        if self.config.include_logs:
            self._add_logs_row(dashboard, service_name)
        
        # Add traces row
        if self.config.include_traces:
            self._add_traces_row(dashboard, service_name)
        
        return dashboard
    
    def _add_variables(
        self,
        dashboard: Dashboard,
        namespace: Optional[str],
    ) -> None:
        """Add template variables."""
        # Namespace variable
        dashboard.add_variable(Variable(
            name="namespace",
            label="Namespace",
            type="query",
            query='label_values(up{job=~".*"}, namespace)',
            datasource_uid=self.config.prometheus_uid,
            include_all=True,
            current={"text": namespace or "All", "value": namespace or "$__all"},
        ))
        
        # Instance variable
        dashboard.add_variable(Variable(
            name="instance",
            label="Instance",
            type="query",
            query='label_values(up{namespace="$namespace"}, instance)',
            datasource_uid=self.config.prometheus_uid,
            multi=True,
            include_all=True,
        ))
    
    def _add_golden_signals_row(
        self,
        dashboard: Dashboard,
        service_name: str,
    ) -> None:
        """Add golden signals panels."""
        # Row header
        row = Row(title="Golden Signals", y=0)
        dashboard.add_row(row)
        
        # Request rate panel
        rate_panel = Panel(
            title="Request Rate",
            type=PanelType.TIMESERIES,
            x=0, y=1, width=6, height=8,
            targets=[Target(
                expr=f'sum(rate(http_requests_total{{service="{service_name}"}}[5m]))',
                legend_format="requests/s",
                datasource_uid=self.config.prometheus_uid,
            )],
            options={"legend": {"displayMode": "list"}},
        )
        dashboard.add_panel(rate_panel)
        
        # Error rate panel
        error_panel = Panel(
            title="Error Rate",
            type=PanelType.TIMESERIES,
            x=6, y=1, width=6, height=8,
            targets=[Target(
                expr=f'sum(rate(http_requests_total{{service="{service_name}",status=~"5.."}}[5m])) / sum(rate(http_requests_total{{service="{service_name}"}}[5m]))',
                legend_format="error rate",
                datasource_uid=self.config.prometheus_uid,
            )],
            thresholds=[
                Threshold(value=None, color="green"),
                Threshold(value=0.01, color="yellow"),
                Threshold(value=0.05, color="red"),
            ],
            field_config={"defaults": {"unit": "percentunit", "max": 1}},
        )
        dashboard.add_panel(error_panel)
        
        # Latency panel
        latency_panel = Panel(
            title="Request Latency",
            type=PanelType.TIMESERIES,
            x=12, y=1, width=6, height=8,
            targets=[
                Target(
                    expr=f'histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket{{service="{service_name}"}}[5m])) by (le))',
                    legend_format="p50",
                    datasource_uid=self.config.prometheus_uid,
                ),
                Target(
                    expr=f'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{{service="{service_name}"}}[5m])) by (le))',
                    legend_format="p95",
                    ref_id="B",
                    datasource_uid=self.config.prometheus_uid,
                ),
                Target(
                    expr=f'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{{service="{service_name}"}}[5m])) by (le))',
                    legend_format="p99",
                    ref_id="C",
                    datasource_uid=self.config.prometheus_uid,
                ),
            ],
            field_config={"defaults": {"unit": "s"}},
        )
        dashboard.add_panel(latency_panel)
        
        # Saturation panel
        saturation_panel = Panel(
            title="CPU Saturation",
            type=PanelType.TIMESERIES,
            x=18, y=1, width=6, height=8,
            targets=[Target(
                expr=f'sum(rate(container_cpu_usage_seconds_total{{pod=~"{service_name}.*"}}[5m]))',
                legend_format="cpu usage",
                datasource_uid=self.config.prometheus_uid,
            )],
            field_config={"defaults": {"unit": "cores"}},
        )
        dashboard.add_panel(saturation_panel)
    
    def _add_slo_row(
        self,
        dashboard: Dashboard,
        service_name: str,
    ) -> None:
        """Add SLO tracking panels."""
        row = Row(title="SLO Status", y=9)
        dashboard.add_row(row)
        
        # Availability SLO
        availability_panel = Panel(
            title="Availability (30d)",
            type=PanelType.GAUGE,
            x=0, y=10, width=6, height=6,
            targets=[Target(
                expr=f'1 - (sum(rate(http_requests_total{{service="{service_name}",status=~"5.."}}[30d])) / sum(rate(http_requests_total{{service="{service_name}"}}[30d])))',
                instant=True,
                datasource_uid=self.config.prometheus_uid,
            )],
            thresholds=[
                Threshold(value=None, color="red"),
                Threshold(value=0.99, color="yellow"),
                Threshold(value=0.999, color="green"),
            ],
            field_config={"defaults": {"unit": "percentunit", "min": 0.9, "max": 1}},
        )
        dashboard.add_panel(availability_panel)
        
        # Error budget
        budget_panel = Panel(
            title="Error Budget Remaining",
            type=PanelType.STAT,
            x=6, y=10, width=6, height=6,
            targets=[Target(
                expr=f'1 - (sum(increase(http_requests_total{{service="{service_name}",status=~"5.."}}[30d])) / (sum(increase(http_requests_total{{service="{service_name}"}}[30d])) * 0.001))',
                instant=True,
                datasource_uid=self.config.prometheus_uid,
            )],
            thresholds=[
                Threshold(value=None, color="red"),
                Threshold(value=0.25, color="yellow"),
                Threshold(value=0.5, color="green"),
            ],
            field_config={"defaults": {"unit": "percentunit"}},
        )
        dashboard.add_panel(budget_panel)
        
        # Latency SLO
        latency_slo_panel = Panel(
            title="Latency SLO (p99 < 500ms)",
            type=PanelType.STAT,
            x=12, y=10, width=6, height=6,
            targets=[Target(
                expr=f'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{{service="{service_name}"}}[30d])) by (le)) < 0.5',
                instant=True,
                datasource_uid=self.config.prometheus_uid,
            )],
            options={
                "textMode": "value_and_name",
                "colorMode": "background",
            },
        )
        dashboard.add_panel(latency_slo_panel)
    
    def _add_resource_row(
        self,
        dashboard: Dashboard,
        service_name: str,
    ) -> None:
        """Add resource metrics panels."""
        row = Row(title="Resource Usage", y=16, collapsed=True)
        
        # CPU panel
        cpu_panel = Panel(
            title="CPU Usage",
            type=PanelType.TIMESERIES,
            x=0, y=17, width=12, height=8,
            targets=[Target(
                expr=f'sum(rate(container_cpu_usage_seconds_total{{pod=~"{service_name}.*"}}[5m])) by (pod)',
                legend_format="{{{{pod}}}}",
                datasource_uid=self.config.prometheus_uid,
            )],
            field_config={"defaults": {"unit": "cores"}},
        )
        row.panels.append(cpu_panel)
        
        # Memory panel
        memory_panel = Panel(
            title="Memory Usage",
            type=PanelType.TIMESERIES,
            x=12, y=17, width=12, height=8,
            targets=[Target(
                expr=f'sum(container_memory_working_set_bytes{{pod=~"{service_name}.*"}}) by (pod)',
                legend_format="{{{{pod}}}}",
                datasource_uid=self.config.prometheus_uid,
            )],
            field_config={"defaults": {"unit": "bytes"}},
        )
        row.panels.append(memory_panel)
        
        dashboard.add_row(row)
    
    def _add_logs_row(
        self,
        dashboard: Dashboard,
        service_name: str,
    ) -> None:
        """Add logs panel."""
        row = Row(title="Logs", y=25, collapsed=True)
        
        logs_panel = Panel(
            title=f"Logs - {service_name}",
            type=PanelType.LOGS,
            x=0, y=26, width=24, height=10,
            targets=[Target(
                expr=f'{{service="{service_name}"}}',
                datasource_uid=self.config.loki_uid,
                datasource_type="loki",
            )],
            options={
                "showTime": True,
                "showLabels": True,
                "showCommonLabels": False,
                "wrapLogMessage": True,
                "sortOrder": "Descending",
                "enableLogDetails": True,
            },
        )
        row.panels.append(logs_panel)
        dashboard.add_row(row)
    
    def _add_traces_row(
        self,
        dashboard: Dashboard,
        service_name: str,
    ) -> None:
        """Add traces panel."""
        row = Row(title="Traces", y=36, collapsed=True)
        
        traces_panel = Panel(
            title=f"Recent Traces - {service_name}",
            type=PanelType.TABLE,
            x=0, y=37, width=24, height=10,
            targets=[Target(
                expr=f'{{resource.service.name="{service_name}"}}',
                datasource_uid=self.config.tempo_uid,
                datasource_type="tempo",
            )],
        )
        row.panels.append(traces_panel)
        dashboard.add_row(row)


class SLODashboard:
    """Generates SLO-focused dashboards."""
    
    def __init__(self, config: Optional[GeneratorConfig] = None):
        self.config = config or GeneratorConfig()
    
    def generate(
        self,
        slo_name: str,
        sli_query: str,
        target: float = 0.999,
        window_days: int = 30,
    ) -> Dashboard:
        """Generate an SLO dashboard."""
        dashboard = Dashboard(
            title=f"SLO: {slo_name}",
            description=f"SLO tracking for {slo_name} (target: {target*100:.2f}%)",
            tags=self.config.default_tags + ["slo", slo_name],
            refresh=self.config.default_refresh,
        )
        
        # Current SLO status
        status_panel = Panel(
            title="Current SLO Status",
            type=PanelType.GAUGE,
            x=0, y=0, width=8, height=8,
            targets=[Target(
                expr=sli_query,
                instant=True,
                datasource_uid=self.config.prometheus_uid,
            )],
            thresholds=[
                Threshold(value=None, color="red"),
                Threshold(value=target - 0.01, color="yellow"),
                Threshold(value=target, color="green"),
            ],
            field_config={"defaults": {"unit": "percentunit", "min": target - 0.1, "max": 1}},
        )
        dashboard.add_panel(status_panel)
        
        # Error budget remaining
        budget_remaining = 1 - target
        budget_panel = Panel(
            title="Error Budget Remaining",
            type=PanelType.STAT,
            x=8, y=0, width=8, height=8,
            targets=[Target(
                expr=f'1 - ((1 - ({sli_query})) / {budget_remaining})',
                instant=True,
                datasource_uid=self.config.prometheus_uid,
            )],
            thresholds=[
                Threshold(value=None, color="red"),
                Threshold(value=0.25, color="yellow"),
                Threshold(value=0.5, color="green"),
            ],
            field_config={"defaults": {"unit": "percentunit"}},
        )
        dashboard.add_panel(budget_panel)
        
        # Burn rate
        burn_panel = Panel(
            title="Burn Rate (1h)",
            type=PanelType.STAT,
            x=16, y=0, width=8, height=8,
            targets=[Target(
                expr=f'(1 - ({sli_query})) / {budget_remaining}',
                instant=True,
                datasource_uid=self.config.prometheus_uid,
            )],
            thresholds=[
                Threshold(value=None, color="green"),
                Threshold(value=1, color="yellow"),
                Threshold(value=14.4, color="red"),  # Burns budget in 1h at 14.4x
            ],
        )
        dashboard.add_panel(burn_panel)
        
        # SLI over time
        sli_timeseries = Panel(
            title="SLI Over Time",
            type=PanelType.TIMESERIES,
            x=0, y=8, width=24, height=8,
            targets=[Target(
                expr=sli_query,
                legend_format="SLI",
                datasource_uid=self.config.prometheus_uid,
            )],
            thresholds=[
                Threshold(value=target, color="green"),
            ],
            field_config={"defaults": {"unit": "percentunit"}},
        )
        dashboard.add_panel(sli_timeseries)
        
        return dashboard


class InfrastructureDashboard:
    """Generates infrastructure overview dashboards."""
    
    def __init__(self, config: Optional[GeneratorConfig] = None):
        self.config = config or GeneratorConfig()
    
    def generate(
        self,
        cluster_name: Optional[str] = None,
    ) -> Dashboard:
        """Generate an infrastructure dashboard."""
        title = f"{cluster_name} Infrastructure" if cluster_name else "Infrastructure Overview"
        
        dashboard = Dashboard(
            title=title,
            description="Infrastructure health and resource utilization",
            tags=self.config.default_tags + ["infrastructure"],
            refresh=self.config.default_refresh,
        )
        
        # Add cluster overview row
        self._add_cluster_overview(dashboard)
        
        # Add node metrics row
        self._add_node_metrics(dashboard)
        
        # Add pod metrics row
        self._add_pod_metrics(dashboard)
        
        return dashboard
    
    def _add_cluster_overview(self, dashboard: Dashboard) -> None:
        """Add cluster overview panels."""
        row = Row(title="Cluster Overview", y=0)
        dashboard.add_row(row)
        
        # Node count
        node_panel = Panel(
            title="Nodes",
            type=PanelType.STAT,
            x=0, y=1, width=4, height=4,
            targets=[Target(
                expr='count(kube_node_info)',
                instant=True,
                datasource_uid=self.config.prometheus_uid,
            )],
        )
        dashboard.add_panel(node_panel)
        
        # Pod count
        pod_panel = Panel(
            title="Running Pods",
            type=PanelType.STAT,
            x=4, y=1, width=4, height=4,
            targets=[Target(
                expr='sum(kube_pod_status_phase{phase="Running"})',
                instant=True,
                datasource_uid=self.config.prometheus_uid,
            )],
        )
        dashboard.add_panel(pod_panel)
        
        # CPU utilization
        cpu_panel = Panel(
            title="Cluster CPU",
            type=PanelType.GAUGE,
            x=8, y=1, width=4, height=4,
            targets=[Target(
                expr='sum(rate(container_cpu_usage_seconds_total[5m])) / sum(machine_cpu_cores)',
                instant=True,
                datasource_uid=self.config.prometheus_uid,
            )],
            thresholds=[
                Threshold(value=None, color="green"),
                Threshold(value=0.7, color="yellow"),
                Threshold(value=0.9, color="red"),
            ],
            field_config={"defaults": {"unit": "percentunit", "max": 1}},
        )
        dashboard.add_panel(cpu_panel)
        
        # Memory utilization
        memory_panel = Panel(
            title="Cluster Memory",
            type=PanelType.GAUGE,
            x=12, y=1, width=4, height=4,
            targets=[Target(
                expr='sum(container_memory_working_set_bytes) / sum(machine_memory_bytes)',
                instant=True,
                datasource_uid=self.config.prometheus_uid,
            )],
            thresholds=[
                Threshold(value=None, color="green"),
                Threshold(value=0.7, color="yellow"),
                Threshold(value=0.9, color="red"),
            ],
            field_config={"defaults": {"unit": "percentunit", "max": 1}},
        )
        dashboard.add_panel(memory_panel)
    
    def _add_node_metrics(self, dashboard: Dashboard) -> None:
        """Add node metrics panels."""
        row = Row(title="Node Metrics", y=5, collapsed=True)
        
        # Node CPU
        node_cpu_panel = Panel(
            title="Node CPU Usage",
            type=PanelType.TIMESERIES,
            x=0, y=6, width=12, height=8,
            targets=[Target(
                expr='1 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) by (instance)',
                legend_format="{{instance}}",
                datasource_uid=self.config.prometheus_uid,
            )],
            field_config={"defaults": {"unit": "percentunit", "max": 1}},
        )
        row.panels.append(node_cpu_panel)
        
        # Node memory
        node_memory_panel = Panel(
            title="Node Memory Usage",
            type=PanelType.TIMESERIES,
            x=12, y=6, width=12, height=8,
            targets=[Target(
                expr='1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)',
                legend_format="{{instance}}",
                datasource_uid=self.config.prometheus_uid,
            )],
            field_config={"defaults": {"unit": "percentunit", "max": 1}},
        )
        row.panels.append(node_memory_panel)
        
        dashboard.add_row(row)
    
    def _add_pod_metrics(self, dashboard: Dashboard) -> None:
        """Add pod metrics panels."""
        row = Row(title="Pod Metrics", y=14, collapsed=True)
        
        # Top CPU pods
        top_cpu_panel = Panel(
            title="Top CPU Pods",
            type=PanelType.TABLE,
            x=0, y=15, width=12, height=8,
            targets=[Target(
                expr='topk(10, sum(rate(container_cpu_usage_seconds_total[5m])) by (pod))',
                instant=True,
                datasource_uid=self.config.prometheus_uid,
            )],
        )
        row.panels.append(top_cpu_panel)
        
        # Top memory pods
        top_memory_panel = Panel(
            title="Top Memory Pods",
            type=PanelType.TABLE,
            x=12, y=15, width=12, height=8,
            targets=[Target(
                expr='topk(10, sum(container_memory_working_set_bytes) by (pod))',
                instant=True,
                datasource_uid=self.config.prometheus_uid,
            )],
            field_config={"defaults": {"unit": "bytes"}},
        )
        row.panels.append(top_memory_panel)
        
        dashboard.add_row(row)


class DashboardGenerator:
    """
    High-level dashboard generator for AutoSRE.
    
    Example:
        generator = DashboardGenerator()
        
        # Create service dashboard
        dashboard = generator.create_service_dashboard("api-gateway")
        
        # Create SLO dashboard
        slo_dashboard = generator.create_slo_dashboard(
            "API Availability",
            sli_query="...",
            target=0.999
        )
    """
    
    def __init__(self, config: Optional[GeneratorConfig] = None):
        self.config = config or GeneratorConfig()
        self._service = ServiceDashboard(config)
        self._slo = SLODashboard(config)
        self._infra = InfrastructureDashboard(config)
    
    def create_service_dashboard(
        self,
        service_name: str,
        namespace: Optional[str] = None,
        custom_metrics: Optional[list[str]] = None,
    ) -> Dashboard:
        """Create a service dashboard."""
        return self._service.generate(service_name, namespace, custom_metrics)
    
    def create_slo_dashboard(
        self,
        slo_name: str,
        sli_query: str,
        target: float = 0.999,
        window_days: int = 30,
    ) -> Dashboard:
        """Create an SLO dashboard."""
        return self._slo.generate(slo_name, sli_query, target, window_days)
    
    def create_infrastructure_dashboard(
        self,
        cluster_name: Optional[str] = None,
    ) -> Dashboard:
        """Create an infrastructure dashboard."""
        return self._infra.generate(cluster_name)
