"""
AutoSRE Doctor Command

Health check command to verify AutoSRE setup and diagnose issues.
"""

import importlib
import platform
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(
    name="doctor",
    help="Check AutoSRE setup health and diagnose issues",
    no_args_is_help=False,
)

console = Console()

# Config directory
CONFIG_DIR = Path("~/.autosre").expanduser()
CONFIG_FILE = CONFIG_DIR / "config.yaml"


class HealthCheck:
    """Represents a single health check result."""

    def __init__(self, name: str, status: str, message: str, details: Optional[str] = None):
        self.name = name
        self.status = status  # "ok", "warning", "error", "skip"
        self.message = message
        self.details = details

    @property
    def icon(self) -> str:
        icons = {
            "ok": "[green]✓[/]",
            "warning": "[yellow]⚠[/]",
            "error": "[red]✗[/]",
            "skip": "[dim]○[/]",
        }
        return icons.get(self.status, "[dim]?[/]")


def check_python_version() -> HealthCheck:
    """Check Python version is 3.11+."""
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"

    if version >= (3, 11):
        return HealthCheck(
            "Python Version",
            "ok",
            f"Python {version_str}",
            f"Platform: {platform.platform()}"
        )
    elif version >= (3, 10):
        return HealthCheck(
            "Python Version",
            "warning",
            f"Python {version_str} (3.11+ recommended)",
            "Some features may not work correctly"
        )
    else:
        return HealthCheck(
            "Python Version",
            "error",
            f"Python {version_str} (3.11+ required)",
            "Please upgrade Python"
        )


def check_required_packages() -> list[HealthCheck]:
    """Check required dependencies are installed."""
    results = []

    # Core packages
    core_packages = [
        ("typer", "CLI framework"),
        ("rich", "Rich terminal output"),
        ("pydantic", "Data validation"),
        ("pydantic_settings", "Configuration"),
        ("httpx", "HTTP client"),
        ("yaml", "YAML parsing"),
    ]

    # LLM packages
    llm_packages = [
        ("anthropic", "Anthropic Claude API"),
        ("openai", "OpenAI API"),
        ("litellm", "LLM abstraction"),
    ]

    # Infrastructure packages
    infra_packages = [
        ("kubernetes", "Kubernetes client"),
        ("prometheus_client", "Prometheus client"),
    ]

    all_packages = [
        ("Core", core_packages),
        ("LLM", llm_packages),
        ("Infrastructure", infra_packages),
    ]

    for category, packages in all_packages:
        for pkg_name, description in packages:
            try:
                # Handle special package names (yaml -> pyyaml)
                import_name = pkg_name
                if pkg_name == "yaml":
                    import_name = "yaml"

                module = importlib.import_module(import_name)
                version = getattr(module, "__version__", "unknown")

                results.append(HealthCheck(
                    f"{category}: {description}",
                    "ok",
                    f"{pkg_name} {version}",
                ))
            except ImportError:
                results.append(HealthCheck(
                    f"{category}: {description}",
                    "error",
                    f"{pkg_name} not installed",
                    f"pip install {pkg_name}"
                ))

    return results


def check_config_file() -> HealthCheck:
    """Check if config file exists and is valid."""
    if not CONFIG_DIR.exists():
        return HealthCheck(
            "Config Directory",
            "warning",
            "~/.autosre not found",
            "Run 'autosre config init' to create"
        )

    if not CONFIG_FILE.exists():
        return HealthCheck(
            "Config File",
            "warning",
            "config.yaml not found",
            "Run 'autosre config init' to create"
        )

    # Try to parse the config
    try:
        import yaml
        with open(CONFIG_FILE) as f:
            config = yaml.safe_load(f)
            if config is None:
                return HealthCheck(
                    "Config File",
                    "warning",
                    "config.yaml is empty",
                    str(CONFIG_FILE)
                )
            key_count = len(config)
            return HealthCheck(
                "Config File",
                "ok",
                f"Found with {key_count} settings",
                str(CONFIG_FILE)
            )
    except Exception as e:
        return HealthCheck(
            "Config File",
            "error",
            f"Invalid YAML: {e}",
            str(CONFIG_FILE)
        )


def check_api_keys() -> list[HealthCheck]:
    """Check API keys are configured (without revealing them)."""
    results = []

    try:
        from autosre.config import Settings
        settings = Settings()

        # Check based on configured provider
        provider = settings.llm_provider

        # Anthropic
        if settings.anthropic_api_key:
            masked = f"sk-ant-...{settings.anthropic_api_key[-4:]}"
            status = "ok" if provider == "anthropic" else "skip"
            results.append(HealthCheck(
                "Anthropic API Key",
                status,
                f"Configured ({masked})",
                "Active" if provider == "anthropic" else "Not active provider"
            ))
        else:
            status = "error" if provider == "anthropic" else "skip"
            results.append(HealthCheck(
                "Anthropic API Key",
                status,
                "Not configured",
                "Set OPENSRE_ANTHROPIC_API_KEY"
            ))

        # OpenAI
        if settings.openai_api_key:
            masked = f"sk-...{settings.openai_api_key[-4:]}"
            status = "ok" if provider == "openai" else "skip"
            results.append(HealthCheck(
                "OpenAI API Key",
                status,
                f"Configured ({masked})",
                "Active" if provider == "openai" else "Not active provider"
            ))
        else:
            status = "error" if provider == "openai" else "skip"
            results.append(HealthCheck(
                "OpenAI API Key",
                status,
                "Not configured",
                "Set OPENSRE_OPENAI_API_KEY"
            ))

        # Azure OpenAI
        if settings.azure_openai_api_key:
            masked = f"...{settings.azure_openai_api_key[-4:]}"
            status = "ok" if provider == "azure" else "skip"
            results.append(HealthCheck(
                "Azure OpenAI API Key",
                status,
                f"Configured ({masked})",
                "Active" if provider == "azure" else "Not active provider"
            ))
        else:
            status = "error" if provider == "azure" else "skip"
            results.append(HealthCheck(
                "Azure OpenAI API Key",
                status,
                "Not configured",
                "Set OPENSRE_AZURE_OPENAI_API_KEY"
            ))

        # Slack
        if settings.slack_bot_token:
            results.append(HealthCheck(
                "Slack Bot Token",
                "ok",
                "Configured",
                f"Channel: {settings.slack_channel}"
            ))
        else:
            results.append(HealthCheck(
                "Slack Bot Token",
                "skip",
                "Not configured",
                "Optional: Set OPENSRE_SLACK_BOT_TOKEN"
            ))

        # PagerDuty
        if settings.pagerduty_api_key:
            results.append(HealthCheck(
                "PagerDuty API Key",
                "ok",
                "Configured",
            ))
        else:
            results.append(HealthCheck(
                "PagerDuty API Key",
                "skip",
                "Not configured",
                "Optional: Set OPENSRE_PAGERDUTY_API_KEY"
            ))

        # Show current LLM provider
        results.insert(0, HealthCheck(
            "LLM Provider",
            "ok",
            f"{provider.title()}",
            f"Model: {settings.anthropic_model if provider == 'anthropic' else settings.openai_model if provider == 'openai' else settings.ollama_model}"
        ))

    except Exception as e:
        results.append(HealthCheck(
            "Settings",
            "error",
            f"Could not load settings: {e}",
        ))

    return results


def check_prometheus_connection() -> HealthCheck:
    """Check Prometheus connectivity."""
    try:
        from autosre.config import Settings
        settings = Settings()

        if not settings.prometheus_url:
            return HealthCheck(
                "Prometheus",
                "skip",
                "Not configured",
                "Set OPENSRE_PROMETHEUS_URL"
            )

        import httpx
        try:
            # Try to reach Prometheus
            response = httpx.get(
                f"{settings.prometheus_url}/-/healthy",
                timeout=5.0
            )
            if response.status_code == 200:
                return HealthCheck(
                    "Prometheus",
                    "ok",
                    "Connected",
                    settings.prometheus_url
                )
            else:
                return HealthCheck(
                    "Prometheus",
                    "warning",
                    f"HTTP {response.status_code}",
                    settings.prometheus_url
                )
        except httpx.ConnectError:
            return HealthCheck(
                "Prometheus",
                "warning",
                "Cannot connect",
                f"URL: {settings.prometheus_url}"
            )
        except Exception as e:
            return HealthCheck(
                "Prometheus",
                "warning",
                f"Error: {type(e).__name__}",
                settings.prometheus_url
            )

    except Exception as e:
        return HealthCheck(
            "Prometheus",
            "error",
            f"Settings error: {e}",
        )


def check_kubernetes_connection() -> HealthCheck:
    """Check Kubernetes connectivity."""
    try:
        from kubernetes import client, config as k8s_config

        # Try to load config
        try:
            k8s_config.load_incluster_config()
            config_source = "in-cluster"
        except k8s_config.ConfigException:
            try:
                k8s_config.load_kube_config()
                config_source = "kubeconfig"
            except Exception:
                return HealthCheck(
                    "Kubernetes",
                    "warning",
                    "No kubeconfig found",
                    "Set KUBECONFIG or ensure ~/.kube/config exists"
                )

        # Try to list namespaces
        try:
            v1 = client.CoreV1Api()
            namespaces = v1.list_namespace(timeout_seconds=5)
            ns_count = len(namespaces.items)
            return HealthCheck(
                "Kubernetes",
                "ok",
                f"Connected ({ns_count} namespaces)",
                f"Config: {config_source}"
            )
        except client.ApiException as e:
            return HealthCheck(
                "Kubernetes",
                "warning",
                f"API error: {e.reason}",
                f"Config: {config_source}"
            )
        except Exception as e:
            return HealthCheck(
                "Kubernetes",
                "warning",
                f"Cannot list namespaces: {type(e).__name__}",
                f"Config: {config_source}"
            )

    except ImportError:
        return HealthCheck(
            "Kubernetes",
            "skip",
            "kubernetes package not installed",
            "pip install kubernetes"
        )
    except Exception as e:
        return HealthCheck(
            "Kubernetes",
            "error",
            f"Error: {e}",
        )


def check_loki_connection() -> HealthCheck:
    """Check Loki connectivity."""
    try:
        from autosre.config import Settings
        settings = Settings()

        if not settings.loki_url:
            return HealthCheck(
                "Loki",
                "skip",
                "Not configured",
                "Set OPENSRE_LOKI_URL"
            )

        import httpx
        try:
            # Try to reach Loki
            response = httpx.get(
                f"{settings.loki_url}/ready",
                timeout=5.0
            )
            if response.status_code == 200:
                return HealthCheck(
                    "Loki",
                    "ok",
                    "Connected",
                    settings.loki_url
                )
            else:
                return HealthCheck(
                    "Loki",
                    "warning",
                    f"HTTP {response.status_code}",
                    settings.loki_url
                )
        except httpx.ConnectError:
            return HealthCheck(
                "Loki",
                "warning",
                "Cannot connect",
                settings.loki_url
            )
        except Exception as e:
            return HealthCheck(
                "Loki",
                "warning",
                f"Error: {type(e).__name__}",
                settings.loki_url
            )

    except Exception as e:
        return HealthCheck(
            "Loki",
            "error",
            f"Settings error: {e}",
        )


def check_ollama_connection() -> HealthCheck:
    """Check Ollama connectivity (if configured)."""
    try:
        from autosre.config import Settings
        settings = Settings()

        if settings.llm_provider != "ollama":
            return HealthCheck(
                "Ollama",
                "skip",
                "Not active provider",
                f"Current provider: {settings.llm_provider}"
            )

        import httpx
        try:
            response = httpx.get(
                f"{settings.ollama_host}/api/tags",
                timeout=5.0
            )
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                model_names = [m.get("name", "") for m in models]

                if settings.ollama_model in model_names or any(settings.ollama_model.split(":")[0] in m for m in model_names):
                    return HealthCheck(
                        "Ollama",
                        "ok",
                        f"Connected ({len(models)} models)",
                        f"Model: {settings.ollama_model}"
                    )
                else:
                    return HealthCheck(
                        "Ollama",
                        "warning",
                        f"Model '{settings.ollama_model}' not found",
                        f"Available: {', '.join(model_names[:3])}..."
                    )
            else:
                return HealthCheck(
                    "Ollama",
                    "warning",
                    f"HTTP {response.status_code}",
                    settings.ollama_host
                )
        except httpx.ConnectError:
            return HealthCheck(
                "Ollama",
                "error",
                "Cannot connect",
                f"URL: {settings.ollama_host}"
            )
        except Exception as e:
            return HealthCheck(
                "Ollama",
                "warning",
                f"Error: {type(e).__name__}",
                settings.ollama_host
            )

    except Exception as e:
        return HealthCheck(
            "Ollama",
            "error",
            f"Settings error: {e}",
        )


def check_memory_db() -> HealthCheck:
    """Check episodic memory database."""
    memory_path = CONFIG_DIR / "memory.db"

    if memory_path.exists():
        size_kb = memory_path.stat().st_size / 1024
        return HealthCheck(
            "Episodic Memory",
            "ok",
            f"Database found ({size_kb:.1f} KB)",
            str(memory_path)
        )
    else:
        return HealthCheck(
            "Episodic Memory",
            "skip",
            "Not initialized",
            "Will be created on first investigation"
        )


@app.callback(invoke_without_command=True)
def doctor(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """
    Check AutoSRE setup health and diagnose issues.

    Performs comprehensive health checks on:
    - Python version and dependencies
    - Configuration files
    - API keys and credentials
    - Service connections (Prometheus, K8s, etc.)

    Examples:
        autosre doctor
        autosre doctor --verbose
        autosre doctor --json
    """
    if ctx.invoked_subcommand is not None:
        return

    all_checks: list[HealthCheck] = []

    console.print()
    console.print("[bold cyan]🩺 AutoSRE Doctor[/]")
    console.print("[dim]Checking your setup...[/]")
    console.print()

    # Python version
    all_checks.append(check_python_version())

    # Required packages
    all_checks.extend(check_required_packages())

    # Config file
    all_checks.append(check_config_file())

    # API keys
    all_checks.extend(check_api_keys())

    # Service connections
    all_checks.append(check_prometheus_connection())
    all_checks.append(check_kubernetes_connection())
    all_checks.append(check_loki_connection())
    all_checks.append(check_ollama_connection())

    # Memory database
    all_checks.append(check_memory_db())

    # JSON output
    if json_output:
        import json
        output = {
            "checks": [
                {
                    "name": c.name,
                    "status": c.status,
                    "message": c.message,
                    "details": c.details,
                }
                for c in all_checks
            ],
            "summary": {
                "ok": sum(1 for c in all_checks if c.status == "ok"),
                "warning": sum(1 for c in all_checks if c.status == "warning"),
                "error": sum(1 for c in all_checks if c.status == "error"),
                "skip": sum(1 for c in all_checks if c.status == "skip"),
            }
        }
        console.print(json.dumps(output, indent=2))
        return

    # Build results table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Check", style="cyan")
    table.add_column("Status")
    table.add_column("Message")
    if verbose:
        table.add_column("Details", style="dim")

    for check in all_checks:
        status_text = f"{check.icon}"

        if check.status == "ok":
            msg_style = "green"
        elif check.status == "warning":
            msg_style = "yellow"
        elif check.status == "error":
            msg_style = "red"
        else:
            msg_style = "dim"

        if verbose:
            table.add_row(
                check.name,
                status_text,
                f"[{msg_style}]{check.message}[/]",
                check.details or "",
            )
        else:
            table.add_row(
                check.name,
                status_text,
                f"[{msg_style}]{check.message}[/]",
            )

    console.print(table)
    console.print()

    # Summary
    ok_count = sum(1 for c in all_checks if c.status == "ok")
    warning_count = sum(1 for c in all_checks if c.status == "warning")
    error_count = sum(1 for c in all_checks if c.status == "error")
    skip_count = sum(1 for c in all_checks if c.status == "skip")

    summary_parts = []
    if ok_count:
        summary_parts.append(f"[green]{ok_count} passed[/]")
    if warning_count:
        summary_parts.append(f"[yellow]{warning_count} warnings[/]")
    if error_count:
        summary_parts.append(f"[red]{error_count} errors[/]")
    if skip_count:
        summary_parts.append(f"[dim]{skip_count} skipped[/]")

    summary_text = " • ".join(summary_parts)

    if error_count > 0:
        console.print(Panel(
            f"[bold red]✗ Some checks failed[/]\n\n{summary_text}",
            title="Summary",
            border_style="red",
        ))
        raise typer.Exit(1)
    elif warning_count > 0:
        console.print(Panel(
            f"[bold yellow]⚠ Some checks have warnings[/]\n\n{summary_text}",
            title="Summary",
            border_style="yellow",
        ))
    else:
        console.print(Panel(
            f"[bold green]✓ All checks passed[/]\n\n{summary_text}",
            title="Summary",
            border_style="green",
        ))

    console.print()


# Allow running as standalone command
def main():
    """Entry point for doctor command."""
    app()


if __name__ == "__main__":
    main()
