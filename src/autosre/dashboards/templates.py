"""Dashboard templates for AutoSRE V2."""
from dataclasses import dataclass, field
from typing import Any, Optional, List
from .models import Dashboard, Panel, PanelType, Target, Variable, Row
from .generator import GeneratorConfig

@dataclass
class TemplateVariable:
    """Template variable definition."""
    name: str
    description: str
    default: str = ""
    required: bool = True

@dataclass  
class DashboardTemplate:
    """Base dashboard template."""
    name: str
    description: str
    variables: List[TemplateVariable] = field(default_factory=list)
    
    def render(self, **kwargs) -> Dashboard:
        raise NotImplementedError

class SLOTemplate(DashboardTemplate):
    """Template for SLO dashboards."""
    def __init__(self):
        super().__init__(
            name="slo",
            description="SLO tracking dashboard",
            variables=[
                TemplateVariable("slo_name", "SLO name"),
                TemplateVariable("sli_query", "SLI PromQL query"),
                TemplateVariable("target", "SLO target (0-1)", default="0.999"),
            ]
        )
    
    def render(self, slo_name: str, sli_query: str, target: float = 0.999, **kwargs) -> Dashboard:
        from .generator import SLODashboard
        return SLODashboard().generate(slo_name, sli_query, target)

class K8sTemplate(DashboardTemplate):
    """Template for Kubernetes dashboards."""
    def __init__(self):
        super().__init__(
            name="kubernetes",
            description="Kubernetes cluster dashboard",
            variables=[TemplateVariable("cluster", "Cluster name", required=False)]
        )
    
    def render(self, cluster: Optional[str] = None, **kwargs) -> Dashboard:
        from .generator import InfrastructureDashboard
        return InfrastructureDashboard().generate(cluster)

class GoldenSignalsTemplate(DashboardTemplate):
    """Template for Golden Signals dashboards."""
    def __init__(self):
        super().__init__(
            name="golden_signals",
            description="Golden signals (latency, traffic, errors, saturation)",
            variables=[
                TemplateVariable("service", "Service name"),
                TemplateVariable("namespace", "Kubernetes namespace", required=False),
            ]
        )
    
    def render(self, service: str, namespace: Optional[str] = None, **kwargs) -> Dashboard:
        from .generator import ServiceDashboard
        return ServiceDashboard().generate(service, namespace)

class TemplateEngine:
    """Manages and renders dashboard templates."""
    def __init__(self):
        self._templates = {
            "slo": SLOTemplate(),
            "kubernetes": K8sTemplate(),
            "golden_signals": GoldenSignalsTemplate(),
        }
    
    def list_templates(self) -> List[str]:
        return list(self._templates.keys())
    
    def get_template(self, name: str) -> Optional[DashboardTemplate]:
        return self._templates.get(name)
    
    def render(self, template_name: str, **kwargs) -> Dashboard:
        template = self._templates.get(template_name)
        if not template:
            raise ValueError(f"Unknown template: {template_name}")
        return template.render(**kwargs)
    
    def register(self, template: DashboardTemplate) -> None:
        self._templates[template.name] = template
