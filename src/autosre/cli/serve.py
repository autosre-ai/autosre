"""AutoSRE CLI - API server commands."""

from __future__ import annotations

import os
import signal
import sys
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(
    name="serve",
    help="Start the AutoSRE API server",
    invoke_without_command=True,
)

console = Console()


@app.callback(invoke_without_command=True)
def serve(
    ctx: typer.Context,
    host: Annotated[
        str,
        typer.Option("--host", "-h", help="Host to bind to"),
    ] = "0.0.0.0",
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port to listen on"),
    ] = 8080,
    workers: Annotated[
        int,
        typer.Option("--workers", "-w", help="Number of worker processes"),
    ] = 1,
    reload: Annotated[
        bool,
        typer.Option("--reload", "-r", help="Enable auto-reload for development"),
    ] = False,
    log_level: Annotated[
        str,
        typer.Option("--log-level", "-l", help="Log level"),
    ] = "info",
    timeout: Annotated[
        int,
        typer.Option("--timeout", "-t", help="Worker timeout in seconds"),
    ] = 120,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """Start the AutoSRE API server."""
    if ctx.invoked_subcommand is not None:
        return
    
    import json as json_module
    
    config = {
        "host": host,
        "port": port,
        "workers": workers,
        "reload": reload,
        "log_level": log_level,
        "timeout": timeout,
    }
    
    if json_output:
        console.print_json(json_module.dumps({
            "action": "start",
            "config": config,
        }))
    
    # Display startup info
    mode = "[cyan]development[/cyan]" if reload else "[green]production[/green]"
    
    console.print(Panel(
        f"""[bold]Host:[/bold] {host}
[bold]Port:[/bold] {port}
[bold]Workers:[/bold] {workers}
[bold]Mode:[/bold] {mode}
[bold]Log level:[/bold] {log_level}

[dim]API endpoints:[/dim]
  • GET  /health           - Health check
  • GET  /api/v1/alerts    - List alerts
  • POST /api/v1/alerts    - Create alert
  • GET  /api/v1/investigate/:id - Get investigation
  • POST /api/v1/investigate - Start investigation
  • GET  /api/v1/runbooks  - List runbooks
  • POST /api/v1/runbooks/:id/run - Execute runbook

[dim]Press Ctrl+C to stop[/dim]""",
        title="🚀 AutoSRE API Server",
        border_style="cyan",
    ))
    
    # Try to import and run uvicorn
    try:
        import uvicorn
    except ImportError:
        console.print("[red]Error: uvicorn not installed[/red]")
        console.print("Install with: pip install uvicorn")
        raise typer.Exit(1)
    
    # Check if API module exists
    try:
        from autosre.api import app as api_app
    except ImportError:
        console.print("[yellow]Warning: API module not found, creating minimal app[/yellow]")
        
        # Create a minimal FastAPI app for demo
        try:
            from fastapi import FastAPI
            from fastapi.responses import JSONResponse
            
            api_app = FastAPI(
                title="AutoSRE API",
                description="LLM-powered incident investigation and remediation",
                version="2.0.0",
            )
            
            @api_app.get("/health")
            def health():
                return {"status": "healthy", "version": "2.0.0"}
            
            @api_app.get("/api/v1/alerts")
            def list_alerts():
                return {"alerts": [], "total": 0}
            
            @api_app.get("/api/v1/runbooks")
            def list_runbooks():
                return {"runbooks": [], "total": 0}
            
        except ImportError:
            console.print("[red]Error: fastapi not installed[/red]")
            console.print("Install with: pip install fastapi uvicorn")
            raise typer.Exit(1)
    
    # Run the server
    try:
        uvicorn.run(
            api_app,
            host=host,
            port=port,
            workers=workers if not reload else 1,
            reload=reload,
            log_level=log_level.lower(),
            timeout_keep_alive=timeout,
        )
    except KeyboardInterrupt:
        console.print("\n[dim]Server stopped[/dim]")


@app.command("status")
def server_status(
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port to check"),
    ] = 8080,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """Check if the API server is running."""
    import json as json_module
    import socket
    
    # Try to connect to the port
    is_running = False
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex(('localhost', port))
            is_running = result == 0
    except Exception:
        is_running = False
    
    # Try to get health info
    health_info = None
    if is_running:
        try:
            import urllib.request
            with urllib.request.urlopen(f"http://localhost:{port}/health", timeout=2) as response:
                health_info = json_module.loads(response.read().decode())
        except Exception:
            pass
    
    if json_output:
        console.print_json(json_module.dumps({
            "running": is_running,
            "port": port,
            "health": health_info,
        }))
        return
    
    if is_running:
        console.print(f"[green]✓[/green] Server is running on port {port}")
        if health_info:
            console.print(f"  Status: {health_info.get('status', 'unknown')}")
            console.print(f"  Version: {health_info.get('version', 'unknown')}")
    else:
        console.print(f"[red]✗[/red] Server is not running on port {port}")


@app.command("dev")
def dev_server(
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port to listen on"),
    ] = 8080,
) -> None:
    """Start server in development mode with auto-reload."""
    ctx = typer.Context(serve)
    serve(
        ctx=ctx,
        host="127.0.0.1",
        port=port,
        workers=1,
        reload=True,
        log_level="debug",
        timeout=120,
        json_output=False,
    )


@app.command("prod")
def prod_server(
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port to listen on"),
    ] = 8080,
    workers: Annotated[
        int,
        typer.Option("--workers", "-w", help="Number of worker processes"),
    ] = 4,
) -> None:
    """Start server in production mode."""
    ctx = typer.Context(serve)
    serve(
        ctx=ctx,
        host="0.0.0.0",
        port=port,
        workers=workers,
        reload=False,
        log_level="info",
        timeout=120,
        json_output=False,
    )


@app.command("routes")
def show_routes(
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """Show all API routes."""
    import json as json_module
    
    routes = [
        {"method": "GET", "path": "/health", "description": "Health check endpoint"},
        {"method": "GET", "path": "/docs", "description": "OpenAPI documentation"},
        {"method": "GET", "path": "/redoc", "description": "ReDoc documentation"},
        {"method": "GET", "path": "/api/v1/alerts", "description": "List alerts"},
        {"method": "POST", "path": "/api/v1/alerts", "description": "Create alert"},
        {"method": "GET", "path": "/api/v1/alerts/{id}", "description": "Get alert by ID"},
        {"method": "PUT", "path": "/api/v1/alerts/{id}/ack", "description": "Acknowledge alert"},
        {"method": "PUT", "path": "/api/v1/alerts/{id}/resolve", "description": "Resolve alert"},
        {"method": "GET", "path": "/api/v1/investigations", "description": "List investigations"},
        {"method": "POST", "path": "/api/v1/investigations", "description": "Start investigation"},
        {"method": "GET", "path": "/api/v1/investigations/{id}", "description": "Get investigation"},
        {"method": "GET", "path": "/api/v1/investigations/{id}/timeline", "description": "Get timeline"},
        {"method": "GET", "path": "/api/v1/investigations/{id}/report", "description": "Get report"},
        {"method": "GET", "path": "/api/v1/runbooks", "description": "List runbooks"},
        {"method": "GET", "path": "/api/v1/runbooks/{id}", "description": "Get runbook"},
        {"method": "POST", "path": "/api/v1/runbooks/{id}/run", "description": "Execute runbook"},
        {"method": "POST", "path": "/api/v1/chat", "description": "Chat endpoint"},
        {"method": "GET", "path": "/api/v1/config", "description": "Get configuration"},
    ]
    
    if json_output:
        console.print_json(json_module.dumps({"routes": routes}))
        return
    
    table = Table(
        title="🛣️  API Routes",
        show_header=True,
        header_style="bold cyan",
    )
    
    table.add_column("Method", style="bold")
    table.add_column("Path")
    table.add_column("Description", style="dim")
    
    for route in routes:
        method = route["method"]
        method_color = {
            "GET": "green",
            "POST": "yellow",
            "PUT": "blue",
            "DELETE": "red",
        }.get(method, "white")
        
        table.add_row(
            f"[{method_color}]{method}[/{method_color}]",
            route["path"],
            route["description"],
        )
    
    console.print(table)
