"""Report Generator for AutoSRE V2.

Core report generation functionality:
- Multiple output formats (PDF, HTML, JSON)
- Template system
- Chart generation
- Export capabilities
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field

from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class ReportFormat(str, Enum):
    """Supported report output formats."""
    
    HTML = "html"
    PDF = "pdf"
    JSON = "json"
    MARKDOWN = "markdown"
    CSV = "csv"


class ReportType(str, Enum):
    """Types of reports."""
    
    INCIDENT = "incident"
    INVESTIGATION = "investigation"
    SLO = "slo"
    SECURITY = "security"
    COST = "cost"
    EXECUTIVE = "executive"
    OPERATIONAL = "operational"
    CUSTOM = "custom"


class ReportSection(BaseModel):
    """A section within a report."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    content: str  # HTML or Markdown
    order: int = 0
    
    # Optional elements
    charts: List[Dict[str, Any]] = Field(default_factory=list)
    tables: List[Dict[str, Any]] = Field(default_factory=list)
    images: List[Dict[str, str]] = Field(default_factory=list)
    
    # Metadata
    collapsed: bool = False
    page_break_before: bool = False


class Report(BaseModel):
    """A generated report."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    
    # Classification
    report_type: ReportType
    title: str
    subtitle: Optional[str] = None
    
    # Time range
    period_start: datetime
    period_end: datetime
    
    # Content
    summary: Optional[str] = None
    sections: List[ReportSection] = Field(default_factory=list)
    
    # Metrics
    key_metrics: Dict[str, Any] = Field(default_factory=dict)
    
    # Output
    format: ReportFormat = ReportFormat.HTML
    output_data: Optional[str] = None  # Generated content
    output_path: Optional[str] = None  # File path if saved
    
    # Metadata
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    generated_by: str = "autosre"
    version: str = "1.0"
    
    # Status
    status: str = "pending"  # pending, generating, completed, failed
    error: Optional[str] = None
    
    def add_section(
        self,
        title: str,
        content: str,
        **kwargs,
    ) -> ReportSection:
        """Add a section to the report."""
        order = len(self.sections)
        section = ReportSection(
            title=title,
            content=content,
            order=order,
            **kwargs,
        )
        self.sections.append(section)
        return section


class ChartData(BaseModel):
    """Data for a chart."""
    
    chart_type: str = "line"  # line, bar, pie, area
    title: str
    labels: List[str] = Field(default_factory=list)
    datasets: List[Dict[str, Any]] = Field(default_factory=list)
    options: Dict[str, Any] = Field(default_factory=dict)


class TableData(BaseModel):
    """Data for a table."""
    
    title: Optional[str] = None
    headers: List[str]
    rows: List[List[Any]]
    footer: Optional[List[str]] = None
    sortable: bool = False
    searchable: bool = False


class ReportTemplate(BaseModel):
    """A report template."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    report_type: ReportType
    
    # Template content
    html_template: str
    css_styles: str = ""
    
    # Default sections
    default_sections: List[str] = Field(default_factory=list)
    
    # Branding
    logo_url: Optional[str] = None
    header_html: Optional[str] = None
    footer_html: Optional[str] = None
    
    # Options
    include_toc: bool = True
    include_page_numbers: bool = True


# Default HTML template
DEFAULT_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        :root {
            --primary-color: #007bff;
            --success-color: #28a745;
            --warning-color: #ffc107;
            --danger-color: #dc3545;
            --text-color: #333;
            --bg-color: #fff;
            --border-color: #dee2e6;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: var(--text-color);
            background: var(--bg-color);
            margin: 0;
            padding: 40px;
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .header {
            border-bottom: 3px solid var(--primary-color);
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        
        .header h1 {
            margin: 0;
            color: var(--primary-color);
            font-size: 2.5em;
        }
        
        .header .subtitle {
            color: #666;
            font-size: 1.2em;
            margin-top: 5px;
        }
        
        .header .period {
            color: #888;
            font-size: 0.9em;
            margin-top: 10px;
        }
        
        .summary {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
        }
        
        .metrics {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .metric-card {
            background: #fff;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 20px;
            text-align: center;
        }
        
        .metric-card .value {
            font-size: 2em;
            font-weight: bold;
            color: var(--primary-color);
        }
        
        .metric-card .label {
            color: #666;
            font-size: 0.9em;
            margin-top: 5px;
        }
        
        .section {
            margin-bottom: 40px;
            page-break-inside: avoid;
        }
        
        .section h2 {
            color: var(--primary-color);
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 10px;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        
        th, td {
            border: 1px solid var(--border-color);
            padding: 12px;
            text-align: left;
        }
        
        th {
            background: #f8f9fa;
            font-weight: 600;
        }
        
        tr:nth-child(even) {
            background: #f8f9fa;
        }
        
        .status-success { color: var(--success-color); }
        .status-warning { color: var(--warning-color); }
        .status-danger { color: var(--danger-color); }
        
        .footer {
            margin-top: 50px;
            padding-top: 20px;
            border-top: 1px solid var(--border-color);
            font-size: 0.85em;
            color: #888;
            text-align: center;
        }
        
        @media print {
            body { padding: 20px; }
            .no-print { display: none; }
            .page-break { page-break-after: always; }
        }
    </style>
    {{ custom_styles }}
</head>
<body>
    <div class="header">
        {{ header_content }}
        <h1>{{ title }}</h1>
        {% if subtitle %}
        <div class="subtitle">{{ subtitle }}</div>
        {% endif %}
        <div class="period">Period: {{ period_start }} - {{ period_end }}</div>
    </div>
    
    {% if summary %}
    <div class="summary">
        {{ summary }}
    </div>
    {% endif %}
    
    {% if key_metrics %}
    <div class="metrics">
        {% for key, value in key_metrics.items() %}
        <div class="metric-card">
            <div class="value">{{ value }}</div>
            <div class="label">{{ key }}</div>
        </div>
        {% endfor %}
    </div>
    {% endif %}
    
    {% for section in sections %}
    <div class="section" {% if section.page_break_before %}style="page-break-before: always;"{% endif %}>
        <h2>{{ section.title }}</h2>
        {{ section.content }}
        
        {% for chart in section.charts %}
        <div class="chart">
            {{ chart.html }}
        </div>
        {% endfor %}
        
        {% for table in section.tables %}
        {{ table.html }}
        {% endfor %}
    </div>
    {% endfor %}
    
    <div class="footer">
        {{ footer_content }}
        <p>Generated by {{ generated_by }} on {{ generated_at }}</p>
        <p>Report ID: {{ report_id }}</p>
    </div>
</body>
</html>
"""


class ReportGenerator:
    """
    Generates reports in various formats.
    
    Provides:
    - Multiple output formats
    - Template system
    - Chart and table rendering
    - PDF generation
    
    Example:
        generator = ReportGenerator()
        
        report = Report(
            tenant_id="tenant-123",
            report_type=ReportType.INCIDENT,
            title="Weekly Incident Report",
            period_start=datetime(2024, 1, 1),
            period_end=datetime(2024, 1, 7),
            key_metrics={
                "Total Incidents": 15,
                "MTTR": "2.5 hours",
                "Resolution Rate": "95%",
            },
        )
        
        report.add_section(
            title="Executive Summary",
            content="<p>This week saw 15 incidents...</p>",
        )
        
        html = await generator.generate(report, ReportFormat.HTML)
    """
    
    def __init__(
        self,
        template_dir: Optional[str] = None,
    ):
        """Initialize ReportGenerator.
        
        Args:
            template_dir: Directory containing custom templates
        """
        self.template_dir = Path(template_dir) if template_dir else None
        self._templates: Dict[str, ReportTemplate] = {}
        self._default_template = DEFAULT_HTML_TEMPLATE
    
    def register_template(self, template: ReportTemplate) -> None:
        """Register a custom template.
        
        Args:
            template: Template to register
        """
        self._templates[template.id] = template
    
    async def generate(
        self,
        report: Report,
        format: ReportFormat = ReportFormat.HTML,
        template_id: Optional[str] = None,
    ) -> str:
        """Generate a report in the specified format.
        
        Args:
            report: Report to generate
            format: Output format
            template_id: Optional template ID
            
        Returns:
            Generated report content
        """
        report.format = format
        report.status = "generating"
        
        try:
            if format == ReportFormat.HTML:
                output = await self._generate_html(report, template_id)
            elif format == ReportFormat.JSON:
                output = await self._generate_json(report)
            elif format == ReportFormat.MARKDOWN:
                output = await self._generate_markdown(report)
            elif format == ReportFormat.CSV:
                output = await self._generate_csv(report)
            elif format == ReportFormat.PDF:
                output = await self._generate_pdf(report, template_id)
            else:
                raise ValueError(f"Unsupported format: {format}")
            
            report.output_data = output
            report.status = "completed"
            
            logger.info(
                "Generated report",
                report_id=report.id,
                format=format.value,
                sections=len(report.sections),
            )
            
            return output
            
        except Exception as e:
            report.status = "failed"
            report.error = str(e)
            logger.error(
                "Report generation failed",
                report_id=report.id,
                error=str(e),
            )
            raise
    
    async def save(
        self,
        report: Report,
        path: str,
    ) -> str:
        """Save a generated report to file.
        
        Args:
            report: Report with generated output
            path: File path to save to
            
        Returns:
            Saved file path
        """
        if not report.output_data:
            raise ValueError("Report has no generated output")
        
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if report.format == ReportFormat.PDF:
            # PDF is binary
            with open(output_path, 'wb') as f:
                f.write(base64.b64decode(report.output_data))
        else:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report.output_data)
        
        report.output_path = str(output_path)
        
        logger.info(
            "Saved report",
            report_id=report.id,
            path=str(output_path),
        )
        
        return str(output_path)
    
    async def _generate_html(
        self,
        report: Report,
        template_id: Optional[str] = None,
    ) -> str:
        """Generate HTML report."""
        template = self._get_template(template_id)
        
        # Simple template rendering (would use Jinja2 in production)
        html = template
        
        # Replace placeholders
        replacements = {
            "{{ title }}": report.title,
            "{{ subtitle }}": report.subtitle or "",
            "{{ period_start }}": report.period_start.strftime("%Y-%m-%d"),
            "{{ period_end }}": report.period_end.strftime("%Y-%m-%d"),
            "{{ summary }}": report.summary or "",
            "{{ generated_by }}": report.generated_by,
            "{{ generated_at }}": report.generated_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "{{ report_id }}": report.id,
            "{{ custom_styles }}": "",
            "{{ header_content }}": "",
            "{{ footer_content }}": "",
        }
        
        for key, value in replacements.items():
            html = html.replace(key, value)
        
        # Render key metrics
        if report.key_metrics:
            metrics_html = '<div class="metrics">'
            for key, value in report.key_metrics.items():
                metrics_html += f'''
                <div class="metric-card">
                    <div class="value">{value}</div>
                    <div class="label">{key}</div>
                </div>
                '''
            metrics_html += '</div>'
        else:
            metrics_html = ""
        
        # Find and replace metrics section
        html = html.replace("{% if key_metrics %}", "").replace("{% endif %}", "")
        html = html.replace("""{% for key, value in key_metrics.items() %}
        <div class="metric-card">
            <div class="value">{{ value }}</div>
            <div class="label">{{ key }}</div>
        </div>
        {% endfor %}""", "")
        
        # Insert metrics
        html = html.replace('<div class="metrics">\n        \n    </div>', metrics_html)
        
        # Render sections
        sections_html = ""
        for section in sorted(report.sections, key=lambda s: s.order):
            section_html = f'''
            <div class="section">
                <h2>{section.title}</h2>
                {section.content}
            </div>
            '''
            sections_html += section_html
        
        # Replace sections placeholder (simplified)
        html = html.replace("""{% for section in sections %}
    <div class="section" {% if section.page_break_before %}style="page-break-before: always;"{% endif %}>
        <h2>{{ section.title }}</h2>
        {{ section.content }}
        
        {% for chart in section.charts %}
        <div class="chart">
            {{ chart.html }}
        </div>
        {% endfor %}
        
        {% for table in section.tables %}
        {{ table.html }}
        {% endfor %}
    </div>
    {% endfor %}""", sections_html)
        
        # Clean up remaining template tags
        import re
        html = re.sub(r'{%.*?%}', '', html)
        html = re.sub(r'{{.*?}}', '', html)
        
        return html
    
    async def _generate_json(self, report: Report) -> str:
        """Generate JSON report."""
        data = {
            "id": report.id,
            "type": report.report_type.value,
            "title": report.title,
            "subtitle": report.subtitle,
            "period": {
                "start": report.period_start.isoformat(),
                "end": report.period_end.isoformat(),
            },
            "summary": report.summary,
            "key_metrics": report.key_metrics,
            "sections": [
                {
                    "title": s.title,
                    "content": s.content,
                    "charts": s.charts,
                    "tables": s.tables,
                }
                for s in report.sections
            ],
            "generated_at": report.generated_at.isoformat(),
            "generated_by": report.generated_by,
        }
        
        return json.dumps(data, indent=2)
    
    async def _generate_markdown(self, report: Report) -> str:
        """Generate Markdown report."""
        lines = [
            f"# {report.title}",
            "",
        ]
        
        if report.subtitle:
            lines.append(f"*{report.subtitle}*")
            lines.append("")
        
        lines.extend([
            f"**Period:** {report.period_start.strftime('%Y-%m-%d')} to {report.period_end.strftime('%Y-%m-%d')}",
            "",
        ])
        
        if report.summary:
            lines.extend([
                "## Summary",
                "",
                report.summary,
                "",
            ])
        
        if report.key_metrics:
            lines.extend([
                "## Key Metrics",
                "",
            ])
            for key, value in report.key_metrics.items():
                lines.append(f"- **{key}:** {value}")
            lines.append("")
        
        for section in sorted(report.sections, key=lambda s: s.order):
            lines.extend([
                f"## {section.title}",
                "",
                section.content,
                "",
            ])
        
        lines.extend([
            "---",
            f"*Generated by {report.generated_by} on {report.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}*",
            f"*Report ID: {report.id}*",
        ])
        
        return "\n".join(lines)
    
    async def _generate_csv(self, report: Report) -> str:
        """Generate CSV report (for tabular data)."""
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(["Report", report.title])
        writer.writerow(["Period", f"{report.period_start.date()} to {report.period_end.date()}"])
        writer.writerow([])
        
        # Key metrics
        if report.key_metrics:
            writer.writerow(["Key Metrics"])
            for key, value in report.key_metrics.items():
                writer.writerow([key, value])
            writer.writerow([])
        
        # Sections with tables
        for section in report.sections:
            for table in section.tables:
                writer.writerow([section.title])
                if "headers" in table:
                    writer.writerow(table["headers"])
                if "rows" in table:
                    for row in table["rows"]:
                        writer.writerow(row)
                writer.writerow([])
        
        return output.getvalue()
    
    async def _generate_pdf(
        self,
        report: Report,
        template_id: Optional[str] = None,
    ) -> str:
        """Generate PDF report.
        
        Returns base64-encoded PDF data.
        """
        # First generate HTML
        html = await self._generate_html(report, template_id)
        
        # In production, would use weasyprint, reportlab, or similar
        # For now, return a placeholder indicating PDF generation would happen
        
        logger.warning(
            "PDF generation requires weasyprint or similar library",
            report_id=report.id,
        )
        
        # Return base64-encoded HTML as fallback
        return base64.b64encode(html.encode()).decode()
    
    def _get_template(self, template_id: Optional[str] = None) -> str:
        """Get template content."""
        if template_id and template_id in self._templates:
            return self._templates[template_id].html_template
        return self._default_template
    
    def render_table(self, data: TableData) -> str:
        """Render a table to HTML.
        
        Args:
            data: Table data
            
        Returns:
            HTML table
        """
        html = []
        
        if data.title:
            html.append(f"<h3>{data.title}</h3>")
        
        html.append("<table>")
        
        # Headers
        html.append("<thead><tr>")
        for header in data.headers:
            html.append(f"<th>{header}</th>")
        html.append("</tr></thead>")
        
        # Body
        html.append("<tbody>")
        for row in data.rows:
            html.append("<tr>")
            for cell in row:
                html.append(f"<td>{cell}</td>")
            html.append("</tr>")
        html.append("</tbody>")
        
        # Footer
        if data.footer:
            html.append("<tfoot><tr>")
            for cell in data.footer:
                html.append(f"<td>{cell}</td>")
            html.append("</tr></tfoot>")
        
        html.append("</table>")
        
        return "\n".join(html)
    
    def render_chart_placeholder(self, data: ChartData) -> str:
        """Render a chart placeholder.
        
        In production, would use Chart.js, Plotly, or similar.
        
        Args:
            data: Chart data
            
        Returns:
            HTML chart placeholder
        """
        return f"""
        <div class="chart-placeholder" style="background: #f8f9fa; padding: 40px; text-align: center; border-radius: 8px; margin: 20px 0;">
            <p style="color: #666;">[{data.chart_type.upper()} CHART]</p>
            <p style="font-weight: bold;">{data.title}</p>
            <p style="font-size: 0.9em; color: #888;">Labels: {', '.join(data.labels[:5])}{'...' if len(data.labels) > 5 else ''}</p>
            <p style="font-size: 0.9em; color: #888;">Datasets: {len(data.datasets)}</p>
        </div>
        """
