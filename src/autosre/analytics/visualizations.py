"""
Visualization and Chart Generation

Generates charts and visualizations for SRE analytics:
- Time series charts (incidents over time)
- Distribution charts (severity breakdown)
- Heatmaps (incidents by hour/day)
- Trend lines
- SLO burn-down charts
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ChartType(str, Enum):
    """Types of charts that can be generated."""
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    HEATMAP = "heatmap"
    AREA = "area"
    SCATTER = "scatter"
    GAUGE = "gauge"
    BURNDOWN = "burndown"


@dataclass
class DataSeries:
    """A data series for a chart."""
    name: str
    data: list[tuple[Any, float]]  # (x, y) pairs
    color: Optional[str] = None
    type: Optional[str] = None  # Override chart type for this series
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "data": self.data,
            "color": self.color,
            "type": self.type,
        }


@dataclass
class TimeSeriesChart:
    """A time series chart."""
    chart_id: str
    title: str
    chart_type: ChartType
    series: list[DataSeries]
    x_axis_label: str = "Time"
    y_axis_label: str = "Value"
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    annotations: list[dict] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "chart_id": self.chart_id,
            "title": self.title,
            "chart_type": self.chart_type.value,
            "series": [s.to_dict() for s in self.series],
            "x_axis_label": self.x_axis_label,
            "y_axis_label": self.y_axis_label,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "annotations": self.annotations,
        }
    
    def to_ascii(self, width: int = 60, height: int = 15) -> str:
        """
        Render chart as ASCII art for terminal display.
        """
        if not self.series or not self.series[0].data:
            return f"[No data for chart: {self.title}]"
        
        # Combine all data points
        all_values = []
        for s in self.series:
            all_values.extend([v for _, v in s.data])
        
        if not all_values:
            return f"[No data for chart: {self.title}]"
        
        min_val = min(all_values)
        max_val = max(all_values)
        range_val = max_val - min_val or 1
        
        # Build ASCII chart
        lines = []
        lines.append(f"  {self.title}")
        lines.append("  " + "─" * width)
        
        # Get first series for simple rendering
        data = self.series[0].data
        step = max(1, len(data) // width)
        sampled = data[::step][:width]
        
        for row in range(height - 1, -1, -1):
            threshold = min_val + (row / (height - 1)) * range_val
            line = []
            
            # Y-axis label
            if row == height - 1:
                line.append(f"{max_val:>6.1f}│")
            elif row == 0:
                line.append(f"{min_val:>6.1f}│")
            elif row == height // 2:
                mid = (max_val + min_val) / 2
                line.append(f"{mid:>6.1f}│")
            else:
                line.append("      │")
            
            # Plot points
            for _, value in sampled:
                if value >= threshold:
                    if self.chart_type == ChartType.BAR:
                        line.append("█")
                    elif self.chart_type == ChartType.AREA:
                        line.append("▓")
                    else:
                        line.append("●" if row == int((value - min_val) / range_val * (height - 1)) else "│")
                else:
                    line.append(" ")
            
            lines.append("".join(line))
        
        # X-axis
        lines.append("      └" + "─" * width)
        lines.append(f"       {self.x_axis_label}")
        
        # Legend
        if len(self.series) > 1:
            legend = "  Legend: " + ", ".join(s.name for s in self.series)
            lines.append(legend)
        
        return "\n".join(lines)
    
    def to_mermaid(self) -> str:
        """
        Render chart as Mermaid diagram for documentation.
        """
        if self.chart_type == ChartType.PIE:
            return self._to_mermaid_pie()
        else:
            return self._to_mermaid_xy()
    
    def _to_mermaid_xy(self) -> str:
        """Generate Mermaid XY chart."""
        lines = [
            "```mermaid",
            "xychart-beta",
            f'    title "{self.title}"',
        ]
        
        # X-axis
        if self.series and self.series[0].data:
            x_labels = [str(x)[:10] for x, _ in self.series[0].data[:10]]
            lines.append(f'    x-axis [{", ".join(x_labels)}]')
        
        # Series
        for series in self.series:
            values = [str(int(v)) for _, v in series.data[:10]]
            lines.append(f'    line [{", ".join(values)}]')
        
        lines.append("```")
        return "\n".join(lines)
    
    def _to_mermaid_pie(self) -> str:
        """Generate Mermaid pie chart."""
        lines = [
            "```mermaid",
            "pie showData",
            f'    title {self.title}',
        ]
        
        if self.series:
            for x, y in self.series[0].data:
                lines.append(f'    "{x}" : {y}')
        
        lines.append("```")
        return "\n".join(lines)


@dataclass
class DistributionChart:
    """A distribution/categorical chart (pie, bar)."""
    chart_id: str
    title: str
    chart_type: ChartType
    categories: list[str]
    values: list[float]
    colors: Optional[list[str]] = None
    
    def to_dict(self) -> dict:
        return {
            "chart_id": self.chart_id,
            "title": self.title,
            "chart_type": self.chart_type.value,
            "categories": self.categories,
            "values": self.values,
            "colors": self.colors,
        }
    
    def to_ascii(self, width: int = 50) -> str:
        """Render as ASCII bar chart."""
        if not self.categories or not self.values:
            return f"[No data for chart: {self.title}]"
        
        lines = [f"  {self.title}", ""]
        
        max_val = max(self.values) or 1
        max_label_len = max(len(c) for c in self.categories)
        
        for cat, val in zip(self.categories, self.values):
            bar_len = int((val / max_val) * (width - max_label_len - 10))
            bar = "█" * bar_len
            lines.append(f"  {cat:>{max_label_len}} │{bar} {val:.0f}")
        
        return "\n".join(lines)
    
    def to_mermaid(self) -> str:
        """Generate Mermaid diagram."""
        if self.chart_type == ChartType.PIE:
            lines = [
                "```mermaid",
                "pie showData",
                f"    title {self.title}",
            ]
            for cat, val in zip(self.categories, self.values):
                lines.append(f'    "{cat}" : {val}')
            lines.append("```")
        else:
            x_axis_items = ", ".join(f'"{c}"' for c in self.categories[:10])
            bar_items = ", ".join(str(int(v)) for v in self.values[:10])
            lines = [
                "```mermaid",
                "xychart-beta",
                f'    title "{self.title}"',
                f'    x-axis [{x_axis_items}]',
                f'    bar [{bar_items}]',
                "```",
            ]
        return "\n".join(lines)


@dataclass
class HeatmapChart:
    """A heatmap chart (e.g., incidents by hour/day)."""
    chart_id: str
    title: str
    x_labels: list[str]
    y_labels: list[str]
    data: list[list[float]]  # 2D matrix
    color_scale: str = "heat"  # "heat", "cool", "mono"
    
    def to_dict(self) -> dict:
        return {
            "chart_id": self.chart_id,
            "title": self.title,
            "x_labels": self.x_labels,
            "y_labels": self.y_labels,
            "data": self.data,
            "color_scale": self.color_scale,
        }
    
    def to_ascii(self) -> str:
        """Render as ASCII heatmap."""
        if not self.data:
            return f"[No data for heatmap: {self.title}]"
        
        # Heat characters
        heat_chars = " ░▒▓█"
        
        # Flatten and get range
        all_vals = [v for row in self.data for v in row]
        min_val = min(all_vals)
        max_val = max(all_vals)
        range_val = max_val - min_val or 1
        
        lines = [f"  {self.title}", ""]
        
        # X-axis labels
        x_header = "       " + "".join(f"{x[:2]:>3}" for x in self.x_labels)
        lines.append(x_header)
        
        # Data rows
        for i, row in enumerate(self.data):
            y_label = self.y_labels[i][:5] if i < len(self.y_labels) else "?"
            row_str = f"{y_label:>5} │"
            
            for val in row:
                intensity = int((val - min_val) / range_val * (len(heat_chars) - 1))
                row_str += f" {heat_chars[intensity]} "
            
            lines.append(row_str)
        
        # Legend
        lines.append("")
        lines.append(f"  Min: {min_val:.0f}  Max: {max_val:.0f}")
        lines.append(f"  Scale: {' '.join(heat_chars)}")
        
        return "\n".join(lines)


class ChartGenerator:
    """
    Generates various charts for SRE analytics.
    
    Supports multiple output formats:
    - Dict (for JSON APIs)
    - ASCII (for terminal)
    - Mermaid (for documentation)
    - Data format for JS charting libraries
    """
    
    def __init__(self):
        self._chart_counter = 0
    
    def _next_id(self, prefix: str = "chart") -> str:
        """Generate unique chart ID."""
        self._chart_counter += 1
        return f"{prefix}_{self._chart_counter}"
    
    def incidents_over_time(
        self,
        incidents: list[dict],
        period_days: int = 30,
        resolution: str = "day",  # "hour", "day", "week"
    ) -> TimeSeriesChart:
        """
        Generate incident count over time chart.
        
        Args:
            incidents: List of incident dictionaries
            period_days: Number of days to chart
            resolution: Time resolution
            
        Returns:
            TimeSeriesChart
        """
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=period_days)
        
        # Group incidents by time bucket
        buckets = {}
        
        for incident in incidents:
            ts = incident.get("timestamp") or incident.get("created_at")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            
            if not ts or ts < start:
                continue
            
            # Bucket key
            if resolution == "hour":
                key = ts.replace(minute=0, second=0, microsecond=0)
            elif resolution == "day":
                key = ts.replace(hour=0, minute=0, second=0, microsecond=0)
            elif resolution == "week":
                key = ts - timedelta(days=ts.weekday())
                key = key.replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                key = ts.replace(hour=0, minute=0, second=0, microsecond=0)
            
            buckets[key] = buckets.get(key, 0) + 1
        
        # Fill in missing buckets
        if resolution == "day":
            delta = timedelta(days=1)
        elif resolution == "hour":
            delta = timedelta(hours=1)
        elif resolution == "week":
            delta = timedelta(weeks=1)
        else:
            delta = timedelta(days=1)
        
        current = start
        while current <= now:
            if current not in buckets:
                buckets[current] = 0
            current += delta
        
        # Sort and create data points
        sorted_buckets = sorted(buckets.items())
        data = [(ts.strftime("%Y-%m-%d"), count) for ts, count in sorted_buckets]
        
        series = DataSeries(
            name="Incidents",
            data=data,
            color="#FF6B6B",
        )
        
        return TimeSeriesChart(
            chart_id=self._next_id("incidents_time"),
            title="Incidents Over Time",
            chart_type=ChartType.LINE,
            series=[series],
            x_axis_label="Date",
            y_axis_label="Incidents",
            start_time=start,
            end_time=now,
        )
    
    def severity_distribution(
        self,
        incidents: list[dict],
    ) -> DistributionChart:
        """
        Generate severity distribution pie/bar chart.
        """
        severity_counts = {}
        for incident in incidents:
            sev = incident.get("severity", "unknown")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
        
        # Order by severity
        severity_order = ["critical", "high", "medium", "low", "info", "unknown"]
        categories = []
        values = []
        
        for sev in severity_order:
            if sev in severity_counts:
                categories.append(sev.capitalize())
                values.append(severity_counts[sev])
        
        # Add any remaining
        for sev, count in severity_counts.items():
            if sev not in severity_order:
                categories.append(sev.capitalize())
                values.append(count)
        
        colors = ["#FF4444", "#FF8C00", "#FFD700", "#90EE90", "#87CEEB", "#808080"]
        
        return DistributionChart(
            chart_id=self._next_id("severity_dist"),
            title="Incidents by Severity",
            chart_type=ChartType.PIE,
            categories=categories,
            values=values,
            colors=colors[:len(categories)],
        )
    
    def service_incidents(
        self,
        incidents: list[dict],
        top_n: int = 10,
    ) -> DistributionChart:
        """
        Generate top services by incident count.
        """
        service_counts = {}
        for incident in incidents:
            service = incident.get("service", "unknown")
            service_counts[service] = service_counts.get(service, 0) + 1
        
        sorted_services = sorted(
            service_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:top_n]
        
        categories = [s for s, _ in sorted_services]
        values = [c for _, c in sorted_services]
        
        return DistributionChart(
            chart_id=self._next_id("service_incidents"),
            title="Top Services by Incidents",
            chart_type=ChartType.BAR,
            categories=categories,
            values=values,
        )
    
    def incident_heatmap(
        self,
        incidents: list[dict],
    ) -> HeatmapChart:
        """
        Generate incident heatmap by hour and day of week.
        """
        # Initialize matrix (7 days x 24 hours)
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        hours = [f"{h:02d}" for h in range(24)]
        data = [[0] * 24 for _ in range(7)]
        
        for incident in incidents:
            ts = incident.get("timestamp") or incident.get("created_at")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            
            if ts:
                day_idx = ts.weekday()
                hour_idx = ts.hour
                data[day_idx][hour_idx] += 1
        
        return HeatmapChart(
            chart_id=self._next_id("incident_heatmap"),
            title="Incidents by Day and Hour",
            x_labels=hours,
            y_labels=days,
            data=data,
            color_scale="heat",
        )
    
    def mttr_trend(
        self,
        incidents: list[dict],
        period_days: int = 30,
    ) -> TimeSeriesChart:
        """
        Generate MTTR trend over time.
        """
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=period_days)
        
        # Group by week
        weekly_mttr = {}
        
        for incident in incidents:
            ts = incident.get("timestamp") or incident.get("created_at")
            ttr = incident.get("ttr") or incident.get("time_to_resolve")
            
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            
            if not ts or ts < start or not ttr:
                continue
            
            # Week key
            week_start = ts - timedelta(days=ts.weekday())
            week_key = week_start.strftime("%Y-%m-%d")
            
            if week_key not in weekly_mttr:
                weekly_mttr[week_key] = []
            weekly_mttr[week_key].append(float(ttr))
        
        # Calculate averages
        data = []
        for week, values in sorted(weekly_mttr.items()):
            avg = sum(values) / len(values) if values else 0
            data.append((week, avg))
        
        series = DataSeries(
            name="MTTR (minutes)",
            data=data,
            color="#4ECDC4",
        )
        
        return TimeSeriesChart(
            chart_id=self._next_id("mttr_trend"),
            title="Mean Time To Resolve (Weekly Average)",
            chart_type=ChartType.LINE,
            series=[series],
            x_axis_label="Week",
            y_axis_label="MTTR (minutes)",
            start_time=start,
            end_time=now,
        )
    
    def slo_burndown(
        self,
        slo_name: str,
        budget_total: float,
        error_events: list[tuple[datetime, float]],
        period_days: int = 30,
    ) -> TimeSeriesChart:
        """
        Generate SLO error budget burndown chart.
        
        Args:
            slo_name: Name of the SLO
            budget_total: Total error budget
            error_events: List of (timestamp, error_amount) tuples
            period_days: Period in days
        """
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=period_days)
        
        # Calculate cumulative budget consumed
        sorted_events = sorted(error_events, key=lambda x: x[0])
        
        data = []
        cumulative = 0
        
        # Add start point
        data.append((start.strftime("%Y-%m-%d"), budget_total))
        
        for ts, error in sorted_events:
            if ts < start:
                continue
            cumulative += error
            remaining = max(0, budget_total - cumulative)
            data.append((ts.strftime("%Y-%m-%d"), remaining))
        
        # Add end point
        remaining = max(0, budget_total - cumulative)
        data.append((now.strftime("%Y-%m-%d"), remaining))
        
        # Ideal burndown line
        ideal_data = [
            (start.strftime("%Y-%m-%d"), budget_total),
            (now.strftime("%Y-%m-%d"), 0),
        ]
        
        series = [
            DataSeries(
                name="Actual Budget",
                data=data,
                color="#FF6B6B",
            ),
            DataSeries(
                name="Ideal Pace",
                data=ideal_data,
                color="#888888",
                type="line",
            ),
        ]
        
        return TimeSeriesChart(
            chart_id=self._next_id("slo_burndown"),
            title=f"Error Budget Burndown: {slo_name}",
            chart_type=ChartType.BURNDOWN,
            series=series,
            x_axis_label="Date",
            y_axis_label="Budget Remaining",
            start_time=start,
            end_time=now,
        )
    
    def comparison_chart(
        self,
        title: str,
        current_period: list[tuple[Any, float]],
        previous_period: list[tuple[Any, float]],
        metric_name: str = "Value",
    ) -> TimeSeriesChart:
        """
        Generate comparison chart between two periods.
        """
        series = [
            DataSeries(
                name="Current Period",
                data=current_period,
                color="#4ECDC4",
            ),
            DataSeries(
                name="Previous Period",
                data=previous_period,
                color="#888888",
            ),
        ]
        
        return TimeSeriesChart(
            chart_id=self._next_id("comparison"),
            title=title,
            chart_type=ChartType.LINE,
            series=series,
            x_axis_label="Time",
            y_axis_label=metric_name,
        )
    
    def gauge_chart(
        self,
        title: str,
        value: float,
        max_value: float = 100,
        thresholds: Optional[list[tuple[float, str]]] = None,
    ) -> dict:
        """
        Generate gauge chart data.
        
        Args:
            title: Chart title
            value: Current value
            max_value: Maximum value
            thresholds: List of (threshold, color) tuples
            
        Returns:
            Dict with gauge configuration
        """
        if thresholds is None:
            thresholds = [
                (0.5, "#90EE90"),   # Green
                (0.8, "#FFD700"),   # Yellow
                (1.0, "#FF4444"),   # Red
            ]
        
        # Determine color based on value
        pct = value / max_value if max_value > 0 else 0
        color = "#888888"
        for threshold, c in thresholds:
            if pct <= threshold:
                color = c
                break
        
        return {
            "chart_id": self._next_id("gauge"),
            "chart_type": "gauge",
            "title": title,
            "value": value,
            "max_value": max_value,
            "percentage": round(pct * 100, 1),
            "color": color,
            "thresholds": thresholds,
        }
    
    def render_dashboard(
        self,
        incidents: list[dict],
        period_days: int = 30,
        format: str = "ascii",
    ) -> str:
        """
        Render a complete dashboard with multiple charts.
        
        Args:
            incidents: List of incidents
            period_days: Period to analyze
            format: Output format ("ascii", "mermaid")
            
        Returns:
            Rendered dashboard string
        """
        lines = [
            "=" * 70,
            "  SRE ANALYTICS DASHBOARD",
            f"  Period: Last {period_days} days",
            "=" * 70,
            "",
        ]
        
        # Generate charts
        incidents_chart = self.incidents_over_time(incidents, period_days)
        severity_chart = self.severity_distribution(incidents)
        service_chart = self.service_incidents(incidents)
        heatmap = self.incident_heatmap(incidents)
        
        if format == "ascii":
            lines.append(incidents_chart.to_ascii())
            lines.append("")
            lines.append("-" * 70)
            lines.append("")
            lines.append(severity_chart.to_ascii())
            lines.append("")
            lines.append("-" * 70)
            lines.append("")
            lines.append(service_chart.to_ascii())
            lines.append("")
            lines.append("-" * 70)
            lines.append("")
            lines.append(heatmap.to_ascii())
        elif format == "mermaid":
            lines.append("### Incidents Over Time")
            lines.append(incidents_chart.to_mermaid())
            lines.append("")
            lines.append("### Severity Distribution")
            lines.append(severity_chart.to_mermaid())
            lines.append("")
            lines.append("### Top Services")
            lines.append(service_chart.to_mermaid())
        
        lines.append("")
        lines.append("=" * 70)
        
        return "\n".join(lines)
