"""
AutoSRE Model Commands

Configure AI model settings for AutoSRE.
"""

import json
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(
    name="model",
    help="Configure AI model settings",
    no_args_is_help=True,
)

console = Console()

# Config directory
CONFIG_DIR = Path("~/.autosre").expanduser()
CONFIG_FILE = CONFIG_DIR / "config.yaml"

# Provider configurations
PROVIDERS = {
    "ollama": {
        "name": "Ollama",
        "description": "Local LLM server (free, private)",
        "requires_api_key": False,
        "default_model": "llama3.1:8b",
        "models": [
            "llama3.1:8b",
            "llama3.1:70b",
            "llama3.2:3b",
            "llama3.2:1b",
            "codellama:7b",
            "codellama:13b",
            "mistral:7b",
            "mixtral:8x7b",
            "qwen2.5:7b",
            "qwen2.5:14b",
            "qwen2.5:32b",
            "phi3:mini",
            "phi3:medium",
            "deepseek-coder:6.7b",
            "deepseek-coder-v2:16b",
        ],
    },
    "openai": {
        "name": "OpenAI",
        "description": "OpenAI GPT models (requires API key)",
        "requires_api_key": True,
        "api_key_env": "OPENSRE_OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
        "models": [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
            "o1-preview",
            "o1-mini",
        ],
    },
    "anthropic": {
        "name": "Anthropic",
        "description": "Anthropic Claude models (requires API key)",
        "requires_api_key": True,
        "api_key_env": "OPENSRE_ANTHROPIC_API_KEY",
        "default_model": "claude-3-5-sonnet-20241022",
        "models": [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
        ],
    },
    "azure": {
        "name": "Azure OpenAI",
        "description": "Azure-hosted OpenAI models (requires endpoint + API key)",
        "requires_api_key": True,
        "api_key_env": "OPENSRE_AZURE_OPENAI_API_KEY",
        "default_model": "gpt-4",
        "models": [
            "gpt-4",
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-35-turbo",
        ],
    },
}


def _get_config() -> dict:
    """Load configuration from file."""
    if CONFIG_FILE.exists():
        import yaml
        with open(CONFIG_FILE) as f:
            return yaml.safe_load(f) or {}
    return {}


def _save_config(config: dict):
    """Save configuration to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    import yaml
    with open(CONFIG_FILE, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)


def _get_current_settings():
    """Get current settings from Settings class, with config file overrides."""
    try:
        from autosre.config import Settings
        settings = Settings()
        
        # Override settings with values from config file
        config = _get_config()
        if config:
            # Update settings object with config file values
            for key, value in config.items():
                if hasattr(settings, key):
                    object.__setattr__(settings, key, value)
        
        return settings
    except Exception:
        return None


@app.command("list")
def list_models(
    provider: Optional[str] = typer.Argument(
        None,
        help="Filter by provider: ollama, openai, anthropic, azure"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """
    Show available models for each provider.
    
    Lists supported AI providers and their models.
    
    Examples:
        autosre model list              # List all providers and models
        autosre model list ollama       # List only Ollama models
        autosre model list --json       # JSON output
    """
    if provider and provider not in PROVIDERS:
        console.print(f"[red]Unknown provider: {provider}[/]")
        console.print(f"Available providers: {', '.join(PROVIDERS.keys())}")
        raise typer.Exit(1)
    
    providers_to_show = {provider: PROVIDERS[provider]} if provider else PROVIDERS
    
    if json_output:
        output = {}
        for prov, info in providers_to_show.items():
            output[prov] = {
                "name": info["name"],
                "description": info["description"],
                "requires_api_key": info["requires_api_key"],
                "default_model": info["default_model"],
                "models": info["models"],
            }
        console.print(json.dumps(output, indent=2))
        return
    
    # Get current settings
    settings = _get_current_settings()
    current_provider = settings.llm_provider if settings else None
    
    console.print()
    
    for prov, info in providers_to_show.items():
        is_current = prov == current_provider
        header = f"[bold cyan]{info['name']}[/]"
        if is_current:
            header += " [green](active)[/]"
        
        # Get current model for this provider
        current_model = None
        if settings and prov == current_provider:
            if prov == "ollama":
                current_model = settings.ollama_model
            elif prov == "openai":
                current_model = settings.openai_model
            elif prov == "anthropic":
                current_model = settings.anthropic_model
            elif prov == "azure":
                current_model = settings.azure_openai_deployment
        
        table = Table(
            title=header,
            show_header=True,
            header_style="bold",
            title_justify="left",
        )
        table.add_column("Model", style="cyan")
        table.add_column("Status")
        
        for model in info["models"]:
            status = ""
            if model == current_model:
                status = "[green]● current[/]"
            elif model == info["default_model"]:
                status = "[dim]default[/]"
            table.add_row(model, status)
        
        console.print(table)
        
        # Show requirements
        if info["requires_api_key"]:
            api_key_env = info.get("api_key_env", "")
            console.print(f"  [dim]Requires: {api_key_env}[/]")
        else:
            console.print(f"  [dim]{info['description']}[/]")
        console.print()


@app.command("use")
def use_model(
    provider: str = typer.Argument(..., help="Provider: ollama, openai, anthropic, azure"),
    model: str = typer.Argument(..., help="Model name to use"),
):
    """
    Set the active AI model.
    
    Configures which provider and model AutoSRE uses for AI operations.
    
    Examples:
        autosre model use ollama llama3.1:8b
        autosre model use openai gpt-4o
        autosre model use anthropic claude-3-5-sonnet-20241022
        autosre model use azure gpt-4
    """
    if provider not in PROVIDERS:
        console.print(f"[red]Unknown provider: {provider}[/]")
        console.print(f"Available providers: {', '.join(PROVIDERS.keys())}")
        raise typer.Exit(1)
    
    provider_info = PROVIDERS[provider]
    
    # Warn if model is not in known list
    if model not in provider_info["models"]:
        console.print(f"[yellow]Note: '{model}' is not in the standard model list for {provider}.[/]")
        console.print("[dim]Proceeding anyway - you may be using a custom/newer model.[/]")
    
    # Check for API key requirement
    if provider_info["requires_api_key"]:
        api_key_env = provider_info.get("api_key_env", "")
        if api_key_env and not os.environ.get(api_key_env):
            console.print(f"[yellow]⚠ Warning: {api_key_env} not set[/]")
            console.print(f"[dim]Set this environment variable before using {provider}[/]")
    
    # Check for Azure-specific requirements
    if provider == "azure":
        if not os.environ.get("OPENSRE_AZURE_OPENAI_ENDPOINT"):
            console.print("[yellow]⚠ Warning: OPENSRE_AZURE_OPENAI_ENDPOINT not set[/]")
    
    # Load and update config
    config = _get_config()
    config["llm_provider"] = provider
    
    # Set the model for the specific provider
    if provider == "ollama":
        config["ollama_model"] = model
    elif provider == "openai":
        config["openai_model"] = model
    elif provider == "anthropic":
        config["anthropic_model"] = model
    elif provider == "azure":
        config["azure_openai_deployment"] = model
    
    _save_config(config)
    
    console.print()
    console.print(Panel(
        f"[green]✓[/] Model configuration updated\n\n"
        f"[bold]Provider:[/] {provider_info['name']}\n"
        f"[bold]Model:[/] {model}\n\n"
        f"[dim]Config saved to: {CONFIG_FILE}[/]",
        title="Model Set",
        border_style="green",
    ))


@app.command("test")
def test_model(
    timeout: int = typer.Option(30, "--timeout", "-t", help="Timeout in seconds"),
):
    """
    Test the current model connection.
    
    Sends a simple request to verify the AI model is working.
    
    Example:
        autosre model test
        autosre model test --timeout 60
    """
    settings = _get_current_settings()
    if not settings:
        console.print("[red]Could not load settings[/]")
        raise typer.Exit(1)
    
    provider = settings.llm_provider
    provider_info = PROVIDERS.get(provider, {})
    
    # Get the model name
    if provider == "ollama":
        model = settings.ollama_model
    elif provider == "openai":
        model = settings.openai_model
    elif provider == "anthropic":
        model = settings.anthropic_model
    elif provider == "azure":
        model = settings.azure_openai_deployment
    else:
        model = "unknown"
    
    console.print()
    console.print(f"[bold]Testing connection to {provider_info.get('name', provider)}...[/]")
    console.print(f"[dim]Model: {model}[/]")
    console.print()
    
    import httpx
    import time
    
    start_time = time.time()
    
    try:
        if provider == "ollama":
            # Test Ollama connection
            try:
                response = httpx.get(
                    f"{settings.ollama_host}/api/tags",
                    timeout=timeout
                )
                if response.status_code != 200:
                    console.print(f"[red]✗ Ollama server returned HTTP {response.status_code}[/]")
                    raise typer.Exit(1)
                
                tags = response.json()
                available_models = [m["name"] for m in tags.get("models", [])]
                
                if model not in available_models and not any(model.split(":")[0] in m for m in available_models):
                    console.print(f"[yellow]⚠ Model '{model}' not found locally[/]")
                    console.print(f"[dim]Available models: {', '.join(available_models[:5])}...[/]")
                    console.print(f"[dim]Run: ollama pull {model}[/]")
                else:
                    console.print(f"[green]✓ Ollama server connected[/]")
                    console.print(f"[green]✓ Model '{model}' available[/]")
                
                # Try a simple generation
                console.print("[dim]Sending test prompt...[/]")
                gen_response = httpx.post(
                    f"{settings.ollama_host}/api/generate",
                    json={
                        "model": model,
                        "prompt": "Say 'Hello from AutoSRE!' in exactly 5 words.",
                        "stream": False,
                    },
                    timeout=timeout
                )
                
                if gen_response.status_code == 200:
                    result = gen_response.json()
                    elapsed = time.time() - start_time
                    console.print(f"[green]✓ Model responded in {elapsed:.2f}s[/]")
                    console.print(f"[dim]Response: {result.get('response', '')[:100]}...[/]")
                else:
                    console.print(f"[red]✗ Generation failed: HTTP {gen_response.status_code}[/]")
                    raise typer.Exit(1)
                    
            except httpx.ConnectError:
                console.print(f"[red]✗ Cannot connect to Ollama at {settings.ollama_host}[/]")
                console.print("[dim]Make sure Ollama is running: ollama serve[/]")
                raise typer.Exit(1)
        
        elif provider == "openai":
            # Test OpenAI connection
            if not settings.openai_api_key:
                console.print("[red]✗ OPENSRE_OPENAI_API_KEY not set[/]")
                raise typer.Exit(1)
            
            try:
                import openai
                client = openai.OpenAI(api_key=settings.openai_api_key)
                
                console.print("[dim]Sending test prompt...[/]")
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "Say 'Hello from AutoSRE!' in exactly 5 words."}],
                    max_tokens=50,
                    timeout=timeout,
                )
                
                elapsed = time.time() - start_time
                console.print(f"[green]✓ OpenAI API connected[/]")
                console.print(f"[green]✓ Model '{model}' responded in {elapsed:.2f}s[/]")
                console.print(f"[dim]Response: {response.choices[0].message.content}[/]")
                
            except openai.AuthenticationError:
                console.print("[red]✗ Invalid API key[/]")
                raise typer.Exit(1)
            except openai.NotFoundError:
                console.print(f"[red]✗ Model '{model}' not found[/]")
                raise typer.Exit(1)
            except Exception as e:
                console.print(f"[red]✗ OpenAI error: {e}[/]")
                raise typer.Exit(1)
        
        elif provider == "anthropic":
            # Test Anthropic connection
            if not settings.anthropic_api_key:
                console.print("[red]✗ OPENSRE_ANTHROPIC_API_KEY not set[/]")
                raise typer.Exit(1)
            
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
                
                console.print("[dim]Sending test prompt...[/]")
                response = client.messages.create(
                    model=model,
                    max_tokens=50,
                    messages=[{"role": "user", "content": "Say 'Hello from AutoSRE!' in exactly 5 words."}],
                )
                
                elapsed = time.time() - start_time
                console.print(f"[green]✓ Anthropic API connected[/]")
                console.print(f"[green]✓ Model '{model}' responded in {elapsed:.2f}s[/]")
                console.print(f"[dim]Response: {response.content[0].text}[/]")
                
            except anthropic.AuthenticationError:
                console.print("[red]✗ Invalid API key[/]")
                raise typer.Exit(1)
            except anthropic.NotFoundError:
                console.print(f"[red]✗ Model '{model}' not found[/]")
                raise typer.Exit(1)
            except Exception as e:
                console.print(f"[red]✗ Anthropic error: {e}[/]")
                raise typer.Exit(1)
        
        elif provider == "azure":
            # Test Azure OpenAI connection
            if not settings.azure_openai_api_key:
                console.print("[red]✗ OPENSRE_AZURE_OPENAI_API_KEY not set[/]")
                raise typer.Exit(1)
            if not settings.azure_openai_endpoint:
                console.print("[red]✗ OPENSRE_AZURE_OPENAI_ENDPOINT not set[/]")
                raise typer.Exit(1)
            
            try:
                import openai
                client = openai.AzureOpenAI(
                    api_key=settings.azure_openai_api_key,
                    api_version=settings.azure_openai_api_version,
                    azure_endpoint=settings.azure_openai_endpoint,
                )
                
                console.print("[dim]Sending test prompt...[/]")
                response = client.chat.completions.create(
                    model=model,  # This is the deployment name in Azure
                    messages=[{"role": "user", "content": "Say 'Hello from AutoSRE!' in exactly 5 words."}],
                    max_tokens=50,
                    timeout=timeout,
                )
                
                elapsed = time.time() - start_time
                console.print(f"[green]✓ Azure OpenAI connected[/]")
                console.print(f"[green]✓ Deployment '{model}' responded in {elapsed:.2f}s[/]")
                console.print(f"[dim]Response: {response.choices[0].message.content}[/]")
                
            except openai.AuthenticationError:
                console.print("[red]✗ Invalid API key or endpoint[/]")
                raise typer.Exit(1)
            except openai.NotFoundError:
                console.print(f"[red]✗ Deployment '{model}' not found[/]")
                raise typer.Exit(1)
            except Exception as e:
                console.print(f"[red]✗ Azure OpenAI error: {e}[/]")
                raise typer.Exit(1)
        
        else:
            console.print(f"[red]Unknown provider: {provider}[/]")
            raise typer.Exit(1)
        
        console.print()
        console.print("[green]✓ Model test passed![/]")
        
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]✗ Test failed: {e}[/]")
        raise typer.Exit(1)


@app.command("info")
def show_info(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """
    Show current model configuration.
    
    Displays the active AI provider and model settings.
    
    Examples:
        autosre model info
        autosre model info --json
    """
    settings = _get_current_settings()
    if not settings:
        console.print("[red]Could not load settings[/]")
        raise typer.Exit(1)
    
    provider = settings.llm_provider
    provider_info = PROVIDERS.get(provider, {"name": provider})
    
    # Get model and additional config based on provider
    if provider == "ollama":
        model = settings.ollama_model
        extra = {"host": settings.ollama_host}
    elif provider == "openai":
        model = settings.openai_model
        extra = {"api_key_set": bool(settings.openai_api_key)}
    elif provider == "anthropic":
        model = settings.anthropic_model
        extra = {"api_key_set": bool(settings.anthropic_api_key)}
    elif provider == "azure":
        model = settings.azure_openai_deployment
        extra = {
            "endpoint_set": bool(settings.azure_openai_endpoint),
            "api_key_set": bool(settings.azure_openai_api_key),
            "api_version": settings.azure_openai_api_version,
        }
    else:
        model = "unknown"
        extra = {}
    
    info = {
        "provider": provider,
        "provider_name": provider_info.get("name", provider),
        "model": model,
        **extra,
    }
    
    if json_output:
        console.print(json.dumps(info, indent=2))
        return
    
    console.print()
    
    table = Table(
        title="Current Model Configuration",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Setting", style="cyan")
    table.add_column("Value")
    
    table.add_row("Provider", f"[bold]{provider_info.get('name', provider)}[/]")
    table.add_row("Model", f"[bold green]{model}[/]")
    
    # Provider-specific rows
    if provider == "ollama":
        table.add_row("Host", settings.ollama_host)
    elif provider == "openai":
        key_status = "[green]✓ Set[/]" if settings.openai_api_key else "[red]✗ Not set[/]"
        table.add_row("API Key", key_status)
    elif provider == "anthropic":
        key_status = "[green]✓ Set[/]" if settings.anthropic_api_key else "[red]✗ Not set[/]"
        table.add_row("API Key", key_status)
    elif provider == "azure":
        endpoint_status = "[green]✓ Set[/]" if settings.azure_openai_endpoint else "[red]✗ Not set[/]"
        key_status = "[green]✓ Set[/]" if settings.azure_openai_api_key else "[red]✗ Not set[/]"
        table.add_row("Endpoint", endpoint_status)
        table.add_row("API Key", key_status)
        table.add_row("API Version", settings.azure_openai_api_version)
    
    console.print(table)
    console.print()
    console.print(f"[dim]Config file: {CONFIG_FILE}[/]")
    console.print()
    console.print("[dim]Use 'autosre model use <provider> <model>' to change[/]")
    console.print("[dim]Use 'autosre model test' to verify connection[/]")
