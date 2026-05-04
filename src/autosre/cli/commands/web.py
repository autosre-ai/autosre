"""AutoSRE web commands - Start and manage the web dashboard."""

import click
from rich.console import Console
from rich.panel import Panel

console = Console()


@click.group()
def web():
    """Start and manage the web dashboard.
    
    The web dashboard provides a visual interface for:
    - Viewing system status
    - Running evaluation scenarios
    - Browsing the context store
    - Monitoring agent activity
    - Submitting feedback
    
    \b
    Examples:
      $ autosre web start                # Start on default port 8080
      $ autosre web start --port 3000    # Start on custom port
    """
    pass


@web.command("start")
@click.option("--port", "-p", default=8080, help="Port to run on")
@click.option("--host", "-h", default="0.0.0.0", help="Host to bind to")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
@click.option("--open", "open_browser", is_flag=True, help="Open browser automatically")
def start(port: int, host: str, reload: bool, open_browser: bool):
    """Start the web dashboard.
    
    Launches the FastAPI server with the AutoSRE dashboard.
    
    \b
    Examples:
      $ autosre web start
      $ autosre web start --port 3000
      $ autosre web start --reload      # Development mode
      $ autosre web start --open        # Open in browser
    """
    import uvicorn
    import webbrowser
    import threading
    
    console.print()
    console.print(Panel.fit(
        f"[bold cyan]🌐 AutoSRE Web Dashboard[/bold cyan]\n\n"
        f"URL: http://{host if host != '0.0.0.0' else 'localhost'}:{port}\n"
        f"API Docs: http://{host if host != '0.0.0.0' else 'localhost'}:{port}/api/docs\n\n"
        f"[dim]Press Ctrl+C to stop[/dim]",
        border_style="cyan"
    ))
    console.print()
    
    if open_browser:
        def open_in_browser():
            import time
            time.sleep(1.5)  # Wait for server to start
            webbrowser.open(f"http://localhost:{port}")
        
        threading.Thread(target=open_in_browser, daemon=True).start()
    
    uvicorn.run(
        "autosre.web.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


@web.command("status")
def status():
    """Check if the web dashboard is running.
    
    Checks if the web server is accessible.
    """
    import httpx
    from autosre.config import settings
    
    url = f"http://localhost:{settings.ui_port}/health"
    
    try:
        response = httpx.get(url, timeout=2.0)
        if response.status_code == 200:
            console.print(f"[green]✓[/green] Web dashboard is running at http://localhost:{settings.ui_port}")
        else:
            console.print(f"[yellow]⚠[/yellow] Web dashboard responded with status {response.status_code}")
    except httpx.ConnectError:
        console.print(f"[red]✗[/red] Web dashboard is not running")
        console.print(f"[dim]Start it with: autosre web start[/dim]")
    except Exception as e:
        console.print(f"[red]✗[/red] Error checking status: {e}")
