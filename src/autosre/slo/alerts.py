"""
Alert Rule Generator for AutoSRE V2.

Auto-generates Prometheus alerting rules for SLOs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import yaml

from .definition import SLODefinition


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    PAGE = "page"
    TICKET = "ticket"
    INFO = "info"


@dataclass
class RuleConfig:
    """Configuration for alert rule generation."""
    
    # Multi-window burn rates
    fast_burn_rate: float = 14.4  # 1-hour burn rate for paging
    slow_burn_rate: float = 6.0  # 6-hour burn rate for paging
    ticket_burn_rate: float = 1.0  # 24-hour burn rate for tickets
    
    # Windows
    short_window: str = "1h"
    long_window: str = "6h"
    slow_window: str = "24h"
    
    # Labels
    default_labels: dict[str, str] = field(default_factory=dict)
    
    # Alert settings
    include_runbook_url: bool = True
    runbook_base_url: str = "https://runbooks.example.com/slo"


@dataclass
class AlertRule:
    """A single Prometheus alerting rule."""
    
    alert_name: str
    expr: str
    for_duration: str = "2m"
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "alert": self.alert_name,
            "expr": self.expr,
            "for": self.for_duration,
            "labels": self.labels,
            "annotations": self.annotations,
        }
    
    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False)


@dataclass
class BurnRateAlert:
    """Multi-window burn rate alert."""
    
    slo_name: str
    severity: AlertSeverity
    short_window: str
    short_threshold: float
    long_window: str
    long_threshold: float
    
    def to_expr(self, sli_metric: str) -> str:
        """Generate PromQL expression."""
        short_expr = f"sum(rate({sli_metric}[{self.short_window}])) / sum(rate({sli_metric}[{self.short_window}]))"
        long_expr = f"sum(rate({sli_metric}[{self.long_window}])) / sum(rate({sli_metric}[{self.long_window}]))"
        
        return f"({short_expr} > {self.short_threshold}) and ({long_expr} > {self.long_threshold})"


@dataclass
class ErrorBudgetAlert:
    """Error budget threshold alert."""
    
    slo_name: str
    threshold_percent: float  # e.g., 25 for 25% remaining
    severity: AlertSeverity
    
    def to_expr(self, error_rate_metric: str, target: float, window: str) -> str:
        """Generate PromQL expression."""
        error_budget = 1 - target
        return f"(1 - (sum(increase({error_rate_metric}[{window}])) / (sum(increase({error_rate_metric}[{window}])) * {error_budget}))) < {self.threshold_percent / 100}"


@dataclass
class MultiWindowAlert:
    """Multi-window multi-burn-rate alert (Google SRE style)."""
    
    slo: SLODefinition
    page_alerts: List[AlertRule] = field(default_factory=list)
    ticket_alerts: List[AlertRule] = field(default_factory=list)
    
    def to_prometheus_rules(self) -> list[dict]:
        """Generate Prometheus rules."""
        return [r.to_dict() for r in self.page_alerts + self.ticket_alerts]


class AlertRuleGenerator:
    """
    Generates Prometheus alerting rules for SLOs.
    
    Implements Google SRE multi-window multi-burn-rate alerting.
    
    Example:
        generator = AlertRuleGenerator()
        rules = generator.generate(slo)
        
        # Export to YAML
        yaml_output = generator.to_prometheus_yaml(rules)
    """
    
    # Multi-window burn rate configurations (Google SRE recommendation)
    BURN_RATE_CONFIGS = [
        # Page: Fast burn (2% budget in 1 hour)
        {"severity": AlertSeverity.PAGE, "short_window": "5m", "short_threshold": 14.4,
         "long_window": "1h", "long_threshold": 14.4, "for": "2m"},
        {"severity": AlertSeverity.PAGE, "short_window": "30m", "short_threshold": 6,
         "long_window": "6h", "long_threshold": 6, "for": "15m"},
        # Ticket: Slow burn
        {"severity": AlertSeverity.TICKET, "short_window": "2h", "short_threshold": 3,
         "long_window": "24h", "long_threshold": 3, "for": "1h"},
        {"severity": AlertSeverity.TICKET, "short_window": "6h", "short_threshold": 1,
         "long_window": "3d", "long_threshold": 1, "for": "3h"},
    ]
    
    def __init__(self, config: Optional[RuleConfig] = None):
        self.config = config or RuleConfig()
    
    def generate(self, slo: SLODefinition) -> list[AlertRule]:
        """
        Generate alerting rules for an SLO.
        
        Returns both page-worthy and ticket-worthy alerts.
        """
        rules = []
        
        # Generate burn rate alerts
        for burn_config in self.BURN_RATE_CONFIGS:
            rule = self._create_burn_rate_rule(slo, burn_config)
            rules.append(rule)
        
        # Generate error budget exhaustion alert
        budget_rule = self._create_budget_alert(slo)
        rules.append(budget_rule)
        
        return rules
    
    def _create_burn_rate_rule(
        self,
        slo: SLODefinition,
        config: dict[str, Any],
    ) -> AlertRule:
        """Create a burn rate alerting rule."""
        severity = config["severity"]
        short_window = config["short_window"]
        long_window = config["long_window"]
        short_threshold = config["short_threshold"]
        long_threshold = config["long_threshold"]
        for_duration = config.get("for", "5m")
        
        # Build PromQL expression
        error_budget = 1 - slo.target
        
        # Calculate burn rate from SLI
        sli_query = slo.get_sli_query()
        
        # Burn rate = (1 - SLI) / error_budget
        short_burn = f"((1 - ({sli_query})) / {error_budget})"
        long_burn = f"((1 - ({sli_query})) / {error_budget})"
        
        expr = f"({short_burn} > {short_threshold}) and ({long_burn} > {long_threshold})"
        
        # Simplify for recording rule usage
        expr = f'(slo:{slo.name}:burn_rate:{short_window} > {short_threshold}) and (slo:{slo.name}:burn_rate:{long_window} > {long_threshold})'
        
        labels = {
            "severity": severity.value,
            "slo": slo.name,
            "service": slo.service,
            **self.config.default_labels,
        }
        
        annotations = {
            "summary": f"High burn rate on {slo.name} SLO",
            "description": f"Service {slo.service} is burning error budget at {short_threshold}x rate over {short_window} and {long_threshold}x over {long_window}",
        }
        
        if self.config.include_runbook_url:
            annotations["runbook_url"] = f"{self.config.runbook_base_url}/{slo.name}"
        
        return AlertRule(
            alert_name=f"SLO{slo.name.title().replace('-', '')}HighBurnRate",
            expr=expr,
            for_duration=for_duration,
            labels=labels,
            annotations=annotations,
        )
    
    def _create_budget_alert(self, slo: SLODefinition) -> AlertRule:
        """Create an error budget exhaustion alert."""
        error_budget = 1 - slo.target
        
        expr = f'slo:{slo.name}:error_budget_remaining < 0.1'
        
        labels = {
            "severity": "ticket",
            "slo": slo.name,
            "service": slo.service,
            **self.config.default_labels,
        }
        
        annotations = {
            "summary": f"Low error budget on {slo.name}",
            "description": f"Error budget for {slo.name} is below 10%. Current value: {{{{ $value | humanizePercentage }}}}",
        }
        
        if self.config.include_runbook_url:
            annotations["runbook_url"] = f"{self.config.runbook_base_url}/{slo.name}"
        
        return AlertRule(
            alert_name=f"SLO{slo.name.title().replace('-', '')}LowErrorBudget",
            expr=expr,
            for_duration="5m",
            labels=labels,
            annotations=annotations,
        )
    
    def generate_recording_rules(self, slo: SLODefinition) -> list[dict]:
        """
        Generate recording rules for efficient alerting.
        
        Pre-computes burn rates at various windows.
        """
        rules = []
        windows = ["5m", "30m", "1h", "2h", "6h", "24h", "3d"]
        
        error_budget = 1 - slo.target
        sli_query = slo.get_sli_query()
        
        # SLI recording rule
        rules.append({
            "record": f"slo:{slo.name}:sli",
            "expr": sli_query,
            "labels": {"slo": slo.name, "service": slo.service},
        })
        
        # Burn rate at various windows
        for window in windows:
            rules.append({
                "record": f"slo:{slo.name}:burn_rate:{window}",
                "expr": f"((1 - (slo:{slo.name}:sli)) / {error_budget})",
                "labels": {"slo": slo.name, "service": slo.service, "window": window},
            })
        
        # Error budget remaining
        rules.append({
            "record": f"slo:{slo.name}:error_budget_remaining",
            "expr": f"1 - ((1 - slo:{slo.name}:sli) / {error_budget})",
            "labels": {"slo": slo.name, "service": slo.service},
        })
        
        return rules
    
    def to_prometheus_yaml(
        self,
        rules: list[AlertRule],
        group_name: str = "slo-alerts",
    ) -> str:
        """Export rules to Prometheus YAML format."""
        rule_group = {
            "groups": [{
                "name": group_name,
                "rules": [r.to_dict() for r in rules],
            }]
        }
        return yaml.dump(rule_group, default_flow_style=False)
    
    def to_prometheus_rules_file(
        self,
        slos: list[SLODefinition],
        output_path: str,
    ) -> None:
        """Generate complete Prometheus rules file for multiple SLOs."""
        all_recording_rules = []
        all_alert_rules = []
        
        for slo in slos:
            all_recording_rules.extend(self.generate_recording_rules(slo))
            all_alert_rules.extend([r.to_dict() for r in self.generate(slo)])
        
        rules = {
            "groups": [
                {
                    "name": "slo-recording-rules",
                    "rules": all_recording_rules,
                },
                {
                    "name": "slo-alerting-rules",
                    "rules": all_alert_rules,
                },
            ]
        }
        
        with open(output_path, "w") as f:
            yaml.dump(rules, f, default_flow_style=False)
