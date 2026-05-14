"""AutoSRE CLI - Interactive chat commands."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

app = typer.Typer(
    name="chat",
    help="Interactive chat with AutoSRE",
    invoke_without_command=True,
)

console = Console()

# Default chat history file
CHAT_HISTORY_FILE = Path.home() / ".autosre" / "chat_history.json"


def _load_history() -> list[dict]:
    """Load chat history from file."""
    if not CHAT_HISTORY_FILE.exists():
        return []
    try:
        with open(CHAT_HISTORY_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _save_history(history: list[dict]) -> None:
    """Save chat history to file."""
    CHAT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CHAT_HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2, default=str)


def _add_to_history(role: str, content: str) -> None:
    """Add a message to history."""
    history = _load_history()
    history.append({
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow().isoformat(),
    })
    # Keep last 100 messages
    history = history[-100:]
    _save_history(history)


def _process_question(question: str, context: Optional[str] = None) -> str:
    """Process a question through the LLM."""
    # TODO: Actually call the LLM via the agent system
    # This is a mock response for demo
    
    question_lower = question.lower()
    
    if "alert" in question_lower or "firing" in question_lower:
        return """Based on current monitoring data:

## Active Alerts Summary
- **3 alerts** currently firing
- **1 critical**: PodCrashLooping on payment-service
- **1 high**: HighCPUUsage on api-gateway
- **1 medium**: HighMemoryUsage on user-service

### Recommended Actions
1. Investigate the payment-service crash loop first (critical)
2. Check recent deployments to payment-service
3. Review pod logs for error patterns

Use `autosre alerts list` for full details."""

    elif "investigate" in question_lower:
        return """To start an investigation:

```bash
autosre investigate start <alert-id>
```

The investigation will:
1. Gather relevant metrics and logs
2. Form hypotheses about root cause
3. Test each hypothesis with data
4. Recommend or execute remediation

Options:
- `--auto-remediate`: Allow automatic fixes
- `--max-depth 5`: Limit investigation depth
- `--timeout 300`: Set timeout in seconds"""

    elif "runbook" in question_lower:
        return """Runbooks are automated procedures for common issues.

**Available runbooks:**
- `high-cpu`: Scale and investigate CPU issues
- `pod-restart`: Debug crash loops
- `disk-space`: Clean up and expand storage

To run: `autosre runbook run <name> --dry-run`"""

    else:
        return f"""I understand you're asking about: *{question}*

I'm an SRE assistant that can help with:
- 🚨 **Alert management** - list, acknowledge, investigate
- 🔍 **Investigations** - automated root cause analysis  
- 📖 **Runbooks** - execute and manage procedures
- 📊 **Metrics** - query and analyze system data

Try asking about alerts, investigations, or runbooks!"""


@app.callback(invoke_without_command=True)
def chat_main(
    ctx: typer.Context,
    model: Annotated[
        Optional[str],
        typer.Option("--model", "-m", help="LLM model to use"),
    ] = None,
    context_file: Annotated[
        Optional[Path],
        typer.Option("--context", "-c", help="File with additional context"),
    ] = None,
) -> None:
    """Start interactive chat mode."""
    if ctx.invoked_subcommand is not None:
        return
    
    # Interactive mode
    console.print(Panel(
        """[bold cyan]AutoSRE Chat[/bold cyan]
        
Ask me anything about your infrastructure, alerts, or incidents.
I can help investigate issues, run diagnostics, and suggest fixes.

[dim]Commands:[/dim]
  /help     - Show available commands
  /clear    - Clear chat history
  /history  - Show recent history
  /exit     - Exit chat

[dim]Press Ctrl+C to exit[/dim]""",
        title="🤖 AutoSRE Assistant",
        border_style="cyan",
    ))
    
    context = None
    if context_file and context_file.exists():
        context = context_file.read_text()
        console.print(f"[dim]Loaded context from {context_file}[/dim]\n")
    
    while True:
        try:
            question = Prompt.ask("\n[bold cyan]You[/bold cyan]")
            
            if not question.strip():
                continue
            
            # Handle commands
            if question.startswith("/"):
                cmd = question.lower().strip()
                
                if cmd in ("/exit", "/quit", "/q"):
                    console.print("[dim]Goodbye![/dim]")
                    break
                
                elif cmd == "/help":
                    console.print("""
[bold]Available Commands:[/bold]
  /help     - Show this help
  /clear    - Clear chat history
  /history  - Show recent messages
  /alerts   - Show active alerts
  /exit     - Exit chat mode
""")
                    continue
                
                elif cmd == "/clear":
                    _save_history([])
                    console.print("[dim]Chat history cleared[/dim]")
                    continue
                
                elif cmd == "/history":
                    history = _load_history()[-10:]
                    if not history:
                        console.print("[dim]No history[/dim]")
                    else:
                        for msg in history:
                            role = msg["role"]
                            content = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
                            ts = msg.get("timestamp", "")[:16]
                            console.print(f"[dim]{ts}[/dim] [{role}]: {content}")
                    continue
                
                elif cmd == "/alerts":
                    from . import alerts
                    alerts.list_alerts(status=None, severity=None, limit=10, json_output=False)
                    continue
                
                else:
                    console.print(f"[yellow]Unknown command: {cmd}[/yellow]")
                    continue
            
            # Save question to history
            _add_to_history("user", question)
            
            # Process question
            with console.status("[cyan]Thinking...[/cyan]"):
                response = _process_question(question, context)
            
            # Save response to history
            _add_to_history("assistant", response)
            
            # Display response
            console.print()
            console.print(Panel(
                Markdown(response),
                title="[bold green]AutoSRE[/bold green]",
                border_style="green",
            ))
            
        except KeyboardInterrupt:
            console.print("\n[dim]Goodbye![/dim]")
            break
        except EOFError:
            break


@app.command("ask")
def ask_question(
    question: Annotated[str, typer.Argument(help="Question to ask")],
    context_file: Annotated[
        Optional[Path],
        typer.Option("--context", "-c", help="File with additional context"),
    ] = None,
    model: Annotated[
        Optional[str],
        typer.Option("--model", "-m", help="LLM model to use"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """Ask a one-shot question."""
    context = None
    if context_file and context_file.exists():
        context = context_file.read_text()
    
    # Process question
    response = _process_question(question, context)
    
    # Save to history
    _add_to_history("user", question)
    _add_to_history("assistant", response)
    
    if json_output:
        output = {
            "question": question,
            "response": response,
            "model": model or "default",
            "timestamp": datetime.utcnow().isoformat(),
        }
        console.print_json(json.dumps(output))
        return
    
    console.print(Panel(
        Markdown(response),
        title="[bold green]AutoSRE[/bold green]",
        border_style="green",
    ))


@app.command("history")
def show_history(
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", help="Number of messages to show"),
    ] = 20,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output as JSON"),
    ] = False,
) -> None:
    """View chat history."""
    history = _load_history()
    history = history[-limit:]
    
    if json_output:
        console.print_json(json.dumps(history))
        return
    
    if not history:
        console.print("[dim]No chat history found[/dim]")
        return
    
    table = Table(
        title="💬 Chat History",
        show_header=True,
        header_style="bold cyan",
    )
    
    table.add_column("Time", style="dim", width=16)
    table.add_column("Role", width=10)
    table.add_column("Message")
    
    for msg in history:
        ts = msg.get("timestamp", "")[:16]
        role = msg["role"]
        content = msg["content"]
        
        # Truncate long messages
        if len(content) > 80:
            content = content[:77] + "..."
        
        role_style = "cyan" if role == "user" else "green"
        table.add_row(
            ts,
            f"[{role_style}]{role}[/{role_style}]",
            content,
        )
    
    console.print(table)


@app.command("clear")
def clear_history() -> None:
    """Clear chat history."""
    _save_history([])
    console.print("[green]✓[/green] Chat history cleared")
