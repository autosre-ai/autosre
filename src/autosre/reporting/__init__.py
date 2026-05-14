"""Reporting & Compliance module for AutoSRE V2.

Provides comprehensive reporting capabilities:
- PDF/HTML report generation
- Incident reports
- SLO compliance reports
- Security posture reports
- Cost reports
- Scheduled report delivery
"""

from autosre.reporting.report_generator import (
    ReportGenerator,
    Report,
    ReportFormat,
    ReportType,
)
from autosre.reporting.incident_report import (
    IncidentReport,
    IncidentReportData,
    IncidentTimeline,
)
from autosre.reporting.slo_report import (
    SLOReport,
    SLOReportData,
    SLOStatus,
)
from autosre.reporting.security_report import (
    SecurityReport,
    SecurityReportData,
    SecurityFinding,
)
from autosre.reporting.cost_report import (
    CostReport,
    CostReportData,
    CostBreakdown,
)
from autosre.reporting.scheduled_reports import (
    ScheduledReports,
    ReportSchedule,
    ReportDelivery,
    ScheduleConfig,
    DeliveryConfig,
    DeliveryChannel,
    ScheduleFrequency,
    ReportStatus,
)

__all__ = [
    # Generator
    "ReportGenerator",
    "Report",
    "ReportFormat",
    "ReportType",
    # Incident
    "IncidentReport",
    "IncidentReportData",
    "IncidentTimeline",
    # SLO
    "SLOReport",
    "SLOReportData",
    "SLOStatus",
    # Security
    "SecurityReport",
    "SecurityReportData",
    "SecurityFinding",
    # Cost
    "CostReport",
    "CostReportData",
    "CostBreakdown",
    # Scheduled
    "ScheduledReports",
    "ReportSchedule",
    "ReportDelivery",
    "ScheduleConfig",
    "DeliveryConfig",
    "DeliveryChannel",
    "ScheduleFrequency",
    "ReportStatus",
]
