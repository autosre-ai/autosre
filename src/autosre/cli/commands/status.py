"""Status command for AutoSRE.

Enhanced status display showing:
- Current configuration (provider, model)
- Memory stats (investigations, episodes)
- Last investigation summary
- Connected services status
- Version and environment info
"""

import platform
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


def get_version() -> str:
    """Get AutoSRE version."""
    try:
        from autosre import __version__
        return __version__
    except ImportError:
        return "0.2.0"


def get_config_info() -> dict:
    """Get current configuration details."""
    try:
        from autosre.config import Settings
        settings = Settings()
        
        # Determine active model based on provider
        if settings.llm_provider == "anthropic":
            model = settings.anthropic_model
        elif settings.llm_provider == "openai":
            model = settings.openai_model
        elif settings.llm_provider == "azure":
            model = settings.azure_openai_deployment
        else:
            model = settings.ollama_model
        
        return {
            "provider": settings.llm_provider,
            "model": model,
            "prometheus_url": settings.prometheus_url,
            "loki_url": settings.loki_url,
            "slack_enabled": settings.slack_enabled,
            "require_approval": settings.require_approval,
            "max_iterations": settings.max_iterations,
            "mcp_enabled": settings.mcp_enabled,
        }
    except Exception as e:
        return {"error": str(e)}


def get_memory_stats() -> dict:
    """Get memory statistics from episodic memory."""
    memory_db = Path("~/.autosre/memory.db").expanduser()
    
    if not memory_db.exists():
        return {"exists": False}
    
    try:
        with sqlite3.connect(memory_db) as conn:
            # Episode counts
            cursor = conn.execute("SELECT COUNT(*) FROM episodes")
            total_episodes = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) FROM episodes WHERE resolved = 1")
            resolved_count = cursor.fetchone()[0]
            
            # Strategy counts
            cursor = conn.execute("SELECT COUNT(*) FROM strategies")
            total_strategies = cursor.fetchone()[0]
            
            # Average effectiveness
            cursor = conn.execute("""
                SELECT AVG(effectiveness_score) FROM episodes WHERE resolved = 1
            """)
            avg_effectiveness = cursor.fetchone()[0] or 0.0
            
            # Top alert types
            cursor = conn.execute("""
                SELECT alert_type, COUNT(*) as count 
                FROM episodes 
                GROUP BY alert_type 
                ORDER BY count DESC 
                LIMIT 3
            """)
            top_alerts = [{"type": row[0], "count": row[1]} for row in cursor.fetchall()]
            
            # Recent activity (last 7 days)
            cursor = conn.execute("""
                SELECT COUNT(*) FROM episodes 
                WHERE created_at > datetime('now', '-7 days')
            """)
            recent_count = cursor.fetchone()[0]
            
        return {
            "exists": True,
            "total_episodes": total_episodes,
            "resolved_count": resolved_count,
            "total_strategies": total_strategies,
            "resolution_rate": round(resolved_count / total_episodes * 100, 1) if total_episodes > 0 else 0,
            "avg_effectiveness": round(avg_effectiveness, 2),
            "top_alerts": top_alerts,
            "recent_count": recent_count,
        }
    except Exception as e:
        return {"exists": True, "error": str(e)}


def get_last_investigation() -> Optional[dict]:
    """Get summary of the last investigation."""
    memory_db = Path("~/.autosre/memory.db").expanduser()
    
    if not memory_db.exists():
        return None
    
    try:
        with sqlite3.connect(memory_db) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT id, created_at, alert_type, service_name, severity, 
                       summary, resolved, effectiveness_score, root_cause
                FROM episodes 
                ORDER BY created_at DESC 
                LIMIT 1
            """)
            row = cursor.fetchone()
            
            if row:
                return {
                    "id": row["id"][:8] if row["id"] else "N/A",
                    "created_at": row["created_at"],
                    "alert_type": row["alert_type"],
                    "service": row["service_name"] or "unknown",
                    "severity": row["severity"] or "info",
                    "summary": row["summary"][:100] + "..." if row["summary"] and len(row["summary"]) > 100 else row["summary"],
                    "resolved": bool(row["resolved"]),
                    "effectiveness": row["effectiveness_score"] or 0.0,
                    "root_cause": row["root_cause"][:80] + "..." if row["root_cause"] and len(row["root_cause"]) > 80 else row["root_cause"],
                }
    except Exception:
        pass
    
    return None


def check_service_quick(name: str, url: str, health_path: str) -> dict:
    """Quick connectivity check for a service."""
    if not url:
        return {"status": "skip", "message": "Not configured"}
    
    try:
        import httpx
        response = httpx.get(f"{url}{health_path}", timeout=2.0)
        if response.status_code == 200:
            return {"status": "ok", "message": "Connected"}
        else:
            return {"status": "warning", "message": f"HTTP {response.status_code}"}
    except Exception:
        return {"status": "error", "message": "Unreachable"}


def check_kubernetes_quick() -> dict:
    """Quick Kubernetes connectivity check."""
    try:
        from kubernetes import client, config as k8s_config
        
        try:
            k8s_config.load_incluster_config()
            source = "in-cluster"
        except Exception:
            try:
                k8s_config.load_kube_config()
                source = "kubeconfig"
            except Exception:
                return {"status": "skip", "message": "No config"}
        
        v1 = client.CoreV1Api()
        v1.list_namespace(timeout_seconds=2, limit=1)
        return {"status": "ok", "message": f"Connected ({source})"}
    except ImportError:
        return {"status": "skip", "message": "Not installed"}
    except Exception:
        return {"status": "error", "message": "Cannot connect"}


def check_llm_quick() -> dict:
    """Quick LLM provider check."""
    try:
        from autosre.config import Settings
        settings = Settings()
        
        provider = settings.llm_provider
        
        if provider == "anthropic":
            if settings.anthropic_api_key:
                return {"status": "ok", "message": "API key configured"}
            return {"status": "error", "message": "Missing API key"}
        elif provider == "openai":
            if settings.openai_api_key:
                return {"status": "ok", "message": "API key configured"}
            return {"status": "error", "message": "Missing API key"}
        elif provider == "azure":
            if settings.azure_openai_api_key:
                return {"status": "ok", "message": "API key configured"}
            return {"status": "error", "message": "Missing API key"}
        elif provider == "ollama":
            import httpx
            try:
                response = httpx.get(f"{settings.ollama_host}/api/tags", timeout=2.0)
                if response.status_code == 200:
                    return {"status": "ok", "message": "Ollama running"}
            except Exception:
                pass
            return {"status": "warning", "message": "Ollama not running"}
        
        return {"status": "skip", "message": "Unknown provider"}
    except Exception as e:
        return {"status": "error", "message": str(e)[:30]}


def get_status_icon(status: str) -> str:
    """Get status icon for display."""
    icons = {
        "ok": "[green]✓[/]",
        "warning": "[yellow]⚠[/]",
        "error": "[red]✗[/]",
        "skip": "[dim]○[/]",
    }
    return icons.get(status, "[dim]?[/]")


def run_status(quiet: bool = False, verbose: bool = False) -> None:
    """Display AutoSRE status.
    
    Args:
        quiet: Minimal output, just show if ready
        verbose: Show additional details
    """
    if quiet:
        # Quick check - just verify essentials
        config = get_config_info()
        llm_status = check_llm_quick()
        
        if "error" not in config and llm_status["status"] == "ok":
            console.print("[green]✓[/] AutoSRE ready")
        else:
            console.print("[red]✗[/] AutoSRE not ready")
        return
    
    # Version and Environment Panel
    version = get_version()
    env_text = Text()
    env_text.append(f"AutoSRE v{version}", style="bold cyan")
    env_text.append(f" | Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    env_text.append(f" | {platform.system()} {platform.machine()}")
    
    console.print(Panel(env_text, title="[bold]Environment[/]", border_style="blue"))
    console.print()
    
    # Configuration Panel
    config = get_config_info()
    
    if "error" in config:
        console.print(Panel(
            f"[red]Error loading config:[/] {config['error']}",
            title="[bold]Configuration[/]",
            border_style="red"
        ))
    else:
        config_table = Table(show_header=False, box=None, padding=(0, 2))
        config_table.add_column("Setting", style="dim")
        config_table.add_column("Value", style="bold")
        
        config_table.add_row("LLM Provider", f"[cyan]{config['provider'].title()}[/]")
        config_table.add_row("Model", config["model"])
        config_table.add_row("Approval Required", "Yes" if config["require_approval"] else "No")
        config_table.add_row("Max Iterations", str(config["max_iterations"]))
        config_table.add_row("MCP Enabled", "Yes" if config["mcp_enabled"] else "No")
        
        console.print(Panel(config_table, title="[bold]Configuration[/]", border_style="cyan"))
    
    console.print()
    
    # Connected Services Panel
    services_table = Table(show_header=True, header_style="bold", box=None)
    services_table.add_column("Service", width=15)
    services_table.add_column("Status", width=10)
    services_table.add_column("Details", width=35)
    
    # LLM
    llm_status = check_llm_quick()
    services_table.add_row(
        "LLM Provider",
        get_status_icon(llm_status["status"]),
        llm_status["message"]
    )
    
    # Prometheus
    prom_url = config.get("prometheus_url", "") if "error" not in config else ""
    prom_status = check_service_quick("Prometheus", prom_url, "/-/healthy")
    services_table.add_row(
        "Prometheus",
        get_status_icon(prom_status["status"]),
        prom_status["message"] if prom_status["status"] != "ok" else prom_url[:35] if prom_url else "Connected"
    )
    
    # Loki
    loki_url = config.get("loki_url", "") if "error" not in config else ""
    loki_status = check_service_quick("Loki", loki_url, "/ready")
    services_table.add_row(
        "Loki",
        get_status_icon(loki_status["status"]),
        loki_status["message"] if loki_status["status"] != "ok" else loki_url[:35] if loki_url else "Connected"
    )
    
    # Kubernetes
    k8s_status = check_kubernetes_quick()
    services_table.add_row(
        "Kubernetes",
        get_status_icon(k8s_status["status"]),
        k8s_status["message"]
    )
    
    # Slack
    slack_enabled = config.get("slack_enabled", False) if "error" not in config else False
    services_table.add_row(
        "Slack",
        get_status_icon("ok" if slack_enabled else "skip"),
        "Configured" if slack_enabled else "Not configured"
    )
    
    console.print(Panel(services_table, title="[bold]Connected Services[/]", border_style="green"))
    console.print()
    
    # Memory Stats Panel
    memory_stats = get_memory_stats()
    
    if not memory_stats["exists"]:
        console.print(Panel(
            "[dim]No episodic memory found. Run an investigation to start building memory.[/]",
            title="[bold]Memory Stats[/]",
            border_style="yellow"
        ))
    elif "error" in memory_stats:
        console.print(Panel(
            f"[red]Error reading memory:[/] {memory_stats['error']}",
            title="[bold]Memory Stats[/]",
            border_style="red"
        ))
    else:
        memory_table = Table(show_header=False, box=None, padding=(0, 2))
        memory_table.add_column("Metric", style="dim")
        memory_table.add_column("Value", style="bold", justify="right")
        
        memory_table.add_row("Total Episodes", str(memory_stats["total_episodes"]))
        memory_table.add_row("Resolved", f"{memory_stats['resolved_count']} ({memory_stats['resolution_rate']}%)")
        memory_table.add_row("Strategies", str(memory_stats["total_strategies"]))
        memory_table.add_row("Avg Effectiveness", f"{memory_stats['avg_effectiveness']:.2f}")
        memory_table.add_row("Last 7 Days", str(memory_stats["recent_count"]))
        
        if memory_stats["top_alerts"] and verbose:
            memory_table.add_row("", "")  # Spacer
            memory_table.add_row("[dim]Top Alert Types[/]", "")
            for alert in memory_stats["top_alerts"]:
                memory_table.add_row(f"  {alert['type']}", str(alert["count"]))
        
        console.print(Panel(memory_table, title="[bold]Memory Stats[/]", border_style="magenta"))
    
    console.print()
    
    # Last Investigation Panel
    last_inv = get_last_investigation()
    
    if last_inv:
        inv_text = Text()
        
        # Severity color
        severity_colors = {
            "critical": "red",
            "high": "yellow",
            "medium": "blue",
            "low": "green",
            "info": "dim",
        }
        sev_color = severity_colors.get(last_inv["severity"], "white")
        
        inv_text.append(f"ID: ", style="dim")
        inv_text.append(f"{last_inv['id']}\n", style="bold")
        inv_text.append(f"Alert: ", style="dim")
        inv_text.append(f"{last_inv['alert_type']}", style="cyan")
        inv_text.append(f" | Service: ", style="dim")
        inv_text.append(f"{last_inv['service']}\n", style="cyan")
        inv_text.append(f"Severity: ", style="dim")
        inv_text.append(f"{last_inv['severity'].upper()}", style=sev_color)
        inv_text.append(f" | Status: ", style="dim")
        inv_text.append("Resolved ✓" if last_inv["resolved"] else "Open", 
                       style="green" if last_inv["resolved"] else "yellow")
        inv_text.append(f" | Effectiveness: ", style="dim")
        inv_text.append(f"{last_inv['effectiveness']:.1f}\n", style="bold")
        
        if last_inv.get("root_cause"):
            inv_text.append(f"\nRoot Cause: ", style="dim")
            inv_text.append(f"{last_inv['root_cause']}\n", style="italic")
        
        if last_inv.get("summary"):
            inv_text.append(f"\nSummary: ", style="dim")
            inv_text.append(f"{last_inv['summary']}", style="italic")
        
        # Parse and format time
        try:
            created = datetime.fromisoformat(last_inv["created_at"].replace("Z", "+00:00"))
            time_ago = datetime.now(timezone.utc) - created.replace(tzinfo=timezone.utc)
            if time_ago.days > 0:
                time_str = f"{time_ago.days}d ago"
            elif time_ago.seconds >= 3600:
                time_str = f"{time_ago.seconds // 3600}h ago"
            else:
                time_str = f"{time_ago.seconds // 60}m ago"
        except Exception:
            time_str = last_inv["created_at"][:19] if last_inv["created_at"] else "unknown"
        
        console.print(Panel(
            inv_text,
            title=f"[bold]Last Investigation[/] [dim]({time_str})[/]",
            border_style="blue"
        ))
    else:
        console.print(Panel(
            "[dim]No investigations recorded yet.[/]",
            title="[bold]Last Investigation[/]",
            border_style="dim"
        ))
    
    console.print()
    
    # Quick tips if verbose
    if verbose:
        tips = [
            "• Run [cyan]autosre doctor[/] for detailed health checks",
            "• Run [cyan]autosre investigate <service>[/] to start an investigation",
            "• Run [cyan]autosre config show[/] to see all configuration options",
        ]
        console.print(Panel("\n".join(tips), title="[bold]Quick Tips[/]", border_style="dim"))
