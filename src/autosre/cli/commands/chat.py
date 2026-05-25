"""
AutoSRE Chat Commands

Interactive chat session with the SRE AI assistant.
"""

import random
import time
from typing import Optional, List, Dict

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.markdown import Markdown

app = typer.Typer(
    name="chat",
    help="Interactive chat with the SRE AI assistant",
)

console = Console()


def _generate_mock_response(message: str, history: List[Dict[str, str]]) -> str:
    """Generate mock chat response for demo purposes."""
    message_lower = message.lower()
    
    # Contextual responses based on keywords
    if "cpu" in message_lower or "high cpu" in message_lower:
        return """Based on typical high CPU scenarios, here are the key things to check:

1. **Recent Deployments**: Check if any new code was deployed in the last 24 hours
   - Command: `kubectl rollout history deployment/<service-name>`

2. **Process Analysis**: Identify high-CPU processes
   - Command: `kubectl exec -it <pod> -- top -bn1 | head -20`

3. **GC Pressure**: For Java/JVM services, check garbage collection
   - Look for GC pause warnings in logs
   - Check heap memory utilization

4. **Traffic Spike**: Verify if request volume has increased
   - Query: `sum(rate(http_requests_total[5m])) by (service)`

Would you like me to start an investigation on a specific service?"""
    
    elif "memory" in message_lower or "oom" in message_lower:
        return """Memory issues are often caused by:

1. **Memory Leaks**: Objects not being garbage collected
   - Monitor heap growth over time
   - Take heap dumps for analysis

2. **Undersized Limits**: Container limits too low for workload
   - Check: `kubectl describe pod <pod> | grep -A2 Limits`

3. **Cache Growth**: Unbounded in-memory caches
   - Implement LRU eviction policies

4. **Connection Pool Leaks**: Database/HTTP connections not being closed

For immediate mitigation, consider:
- Increasing memory limits (if available)
- Restarting affected pods
- Scaling horizontally to distribute load

Run `/investigate memory issues on <service>` for detailed analysis."""
    
    elif "latency" in message_lower or "slow" in message_lower:
        return """High latency typically stems from:

1. **Database Queries**: Slow or missing indexes
   - Check slow query logs
   - Analyze query plans with EXPLAIN

2. **Network Issues**: Increased round-trip times
   - Check for DNS resolution delays
   - Verify network policies aren't throttling

3. **Resource Contention**: CPU/memory pressure
   - Check if pods are being throttled
   - Review resource requests/limits

4. **External Dependencies**: Downstream services slow
   - Check distributed traces
   - Review dependency health

Tip: Start with the p99 latency breakdown to identify the slowest component."""
    
    elif "runbook" in message_lower:
        return """I can help you find relevant runbooks. Here's what's available:

**Common Runbooks:**
- RB-001: On-Call Escalation Procedures
- RB-012: Database Failover Process
- RB-023: High CPU Troubleshooting
- RB-031: Memory Leak Investigation
- RB-042: Kubernetes Pod Restart Procedures
- RB-056: SSL Certificate Renewal
- RB-067: Redis Cluster Recovery

To search for a specific runbook, try:
- "runbook for database failover"
- "how to restart kubernetes pods"
- "escalation procedures"

Which runbook would you like to explore?"""
    
    elif "help" in message_lower or "what can you do" in message_lower:
        return """I'm your AI SRE assistant. Here's how I can help:

**Investigation & Analysis**
- Analyze incidents and find root causes
- Query metrics, logs, and traces
- Correlate events across services

**Runbooks & Documentation**
- Search and retrieve runbook procedures
- Explain past incident resolutions
- Provide best practice recommendations

**Operations**
- Check service health status
- Review recent alerts and events
- Suggest remediation actions

**Example Questions:**
- "Why is the API latency high?"
- "Show me the runbook for database failover"
- "What caused the outage last Tuesday?"
- "How do I scale the payment service?"

Use `/investigate <incident>` to start a detailed AI investigation."""
    
    elif "hello" in message_lower or "hi" in message_lower or "hey" in message_lower:
        return """Hello! I'm your AutoSRE assistant, ready to help with your infrastructure and reliability needs.

I can help you:
- Investigate incidents and find root causes
- Search runbooks and documentation  
- Analyze metrics and logs
- Provide SRE best practices

What would you like to work on today?"""
    
    elif any(word in message_lower for word in ["thank", "thanks"]):
        return "You're welcome! Let me know if you need anything else."
    
    elif "error" in message_lower or "exception" in message_lower:
        return """To help diagnose the error, I'll need a bit more context:

1. **Service affected**: Which service is generating the error?
2. **Error message**: What's the exact error message or stack trace?
3. **Frequency**: Is this a spike or gradual increase?
4. **Recent changes**: Any deployments or config changes?

In the meantime, here are some quick checks:
- Check error logs: `kubectl logs -l app=<service> --tail=100`
- View events: `kubectl get events --sort-by='.lastTimestamp'`
- Check pod status: `kubectl get pods -l app=<service>`

Use `/investigate <error description>` for an AI-powered analysis."""
    
    elif "alert" in message_lower or "pagerduty" in message_lower or "on-call" in message_lower:
        return """For alert management, here's what I can help with:

**Current Status**
- Check active alerts across monitoring systems
- View alert history and resolution patterns

**Alert Actions**
- Acknowledge alerts (with proper escalation)
- Snooze alerts during known maintenance
- Route alerts to appropriate teams

**Best Practices**
- Define proper alert thresholds
- Set up escalation policies
- Create runbooks for common alerts

Run `autosre alerts` to see current active alerts, or describe the specific alert you're dealing with."""

    elif "kubernetes" in message_lower or "k8s" in message_lower or "pod" in message_lower:
        return """For Kubernetes issues, here are some common troubleshooting steps:

**Pod Issues**
- `kubectl describe pod <pod>` - Check events and conditions
- `kubectl logs <pod>` - View container logs
- `kubectl get pods -o wide` - Check node placement

**Deployment Issues**
- `kubectl rollout status deployment/<name>` - Check rollout progress
- `kubectl rollout history deployment/<name>` - View revision history
- `kubectl rollout undo deployment/<name>` - Rollback if needed

**Resource Issues**
- `kubectl top pods` - Check CPU/memory usage
- `kubectl describe node <node>` - Check node capacity

What specific Kubernetes issue are you facing?"""

    else:
        # Generic contextual response
        context_hint = ""
        if len(history) > 2:
            context_hint = "Based on our conversation, "
        
        return f"""{context_hint}I understand you're asking about: "{message[:50]}{'...' if len(message) > 50 else ''}"

To provide the most accurate help, could you specify:
- Which service or system is affected?
- When did you first notice this issue?
- Are there any error messages or alerts?

You can also:
- Use `/investigate <description>` for AI-powered analysis
- Use `/help` to see available commands
- Ask about specific runbooks or procedures"""


def _stream_text(text: str, delay: float = 0.012) -> None:
    """Stream text character by character for a natural feel."""
    for char in text:
        console.print(char, end="", highlight=False)
        time.sleep(delay)
    console.print()  # Final newline


def _show_chat_help() -> None:
    """Display chat help information."""
    console.print(Panel(
        "[bold cyan]Available Commands[/bold cyan]\n\n"
        "  [bold]/help[/bold]               Show this help message\n"
        "  [bold]/clear[/bold]              Clear conversation history\n"
        "  [bold]/history[/bold]            Show conversation history\n"
        "  [bold]/investigate[/bold] <desc> Start an incident investigation\n"
        "  [bold]/model[/bold] [name]       Show or switch the current model\n"
        "  [bold]/temp[/bold] [value]       Show or set temperature (0.0-1.0)\n"
        "  [bold]/exit[/bold]               Exit chat (also: /quit, Ctrl+C)\n\n"
        "[bold cyan]Tips[/bold cyan]\n\n"
        "  • Ask about incidents, runbooks, or best practices\n"
        "  • Describe symptoms and I'll help diagnose issues\n"
        "  • Reference specific services for targeted help\n"
        "  • Use natural language - I understand context!",
        title="💡 Chat Help",
        border_style="cyan",
    ))


def _run_investigation(description: str, mock: bool = True) -> None:
    """Run an investigation from within chat."""
    from autosre.cli.commands.investigate import InvestigationRunner
    
    runner = InvestigationRunner(
        alert=description,
        service=None,
        severity="high",
        mock=mock,
        output_format="text",
        stream=True,
    )
    
    runner.run()


@app.command("start")
def start(
    message: Optional[str] = typer.Argument(None, help="Initial message (or start interactive mode)"),
    context: Optional[str] = typer.Option(
        None, "--context", "-c", help="Additional context file or incident ID"
    ),
    model: str = typer.Option(
        "gpt-4", "--model", "-m", help="LLM model to use"
    ),
    temperature: float = typer.Option(
        0.7, "--temperature", "-t", help="Response temperature (0.0-1.0)"
    ),
    mock: bool = typer.Option(
        True, "--mock/--live", help="Use mock responses (default) or live LLM"
    ),
):
    """
    Start an interactive chat session with the SRE assistant.

    Ask questions about:
    - System architecture and dependencies
    - Runbook procedures
    - Past incidents and resolutions
    - Best practices and recommendations
    
    Examples:
        autosre chat start
        autosre chat start "Why is the API slow?"
        autosre chat start --model gpt-4-turbo --temperature 0.5
    """
    # Conversation history
    history: List[Dict[str, str]] = []
    current_model = model
    current_temp = temperature
    
    # Welcome banner
    console.print()
    console.print(Panel(
        "[bold]Interactive SRE Assistant[/bold]\n\n"
        f"[dim]Model:[/dim] {current_model}   [dim]Temperature:[/dim] {current_temp}\n"
        f"[dim]Mode:[/dim] {'Mock (demo)' if mock else 'Live LLM'}\n\n"
        "[dim]Type [bold]/help[/bold] for commands, [bold]/exit[/bold] to quit[/dim]",
        title="💬 AutoSRE Chat",
        border_style="green",
    ))
    
    if context:
        console.print(f"[dim]Context loaded:[/dim] {context}\n")
    
    # Process initial message if provided
    if message:
        console.print(f"\n[bold blue]You:[/bold blue] {message}")
        history.append({"role": "user", "content": message})
        
        console.print()
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task("[cyan]Thinking...", total=None)
            time.sleep(0.6 + random.uniform(0.2, 0.5))
        
        response = _generate_mock_response(message, history)
        console.print("[bold green]AutoSRE:[/bold green]")
        _stream_text(response, delay=0.006)
        history.append({"role": "assistant", "content": response})
    
    # Interactive REPL loop
    while True:
        try:
            # Get user input with styled prompt
            console.print()
            user_input = Prompt.ask("[bold blue]You[/bold blue]")
            
            if not user_input.strip():
                continue
            
            cmd = user_input.strip().lower()
            
            # Handle exit commands
            if cmd in ["/exit", "/quit", "exit", "quit", "q"]:
                console.print("\n[dim]Goodbye! Stay reliable. 🚀[/dim]\n")
                break
            
            # Handle /help
            if cmd == "/help":
                _show_chat_help()
                continue
            
            # Handle /clear
            if cmd == "/clear":
                history.clear()
                console.print("[dim]✓ Conversation history cleared.[/dim]")
                continue
            
            # Handle /history
            if cmd == "/history":
                if not history:
                    console.print("[dim]No conversation history yet.[/dim]")
                else:
                    console.print(f"\n[bold]Conversation History[/bold] ({len(history)} messages)\n")
                    for i, msg in enumerate(history):
                        role_color = "blue" if msg["role"] == "user" else "green"
                        role_name = "You" if msg["role"] == "user" else "AutoSRE"
                        preview = msg["content"][:80].replace("\n", " ")
                        if len(msg["content"]) > 80:
                            preview += "..."
                        console.print(f"  [{role_color}]{i+1}. {role_name}:[/{role_color}] {preview}")
                continue
            
            # Handle /model
            if cmd.startswith("/model"):
                parts = user_input.strip().split(maxsplit=1)
                if len(parts) > 1:
                    current_model = parts[1]
                    console.print(f"[dim]✓ Model switched to: {current_model}[/dim]")
                else:
                    console.print(f"[dim]Current model: {current_model}[/dim]")
                    console.print("[dim]Usage: /model <model-name> (e.g., gpt-4-turbo, claude-3-opus)[/dim]")
                continue
            
            # Handle /temp
            if cmd.startswith("/temp"):
                parts = user_input.strip().split(maxsplit=1)
                if len(parts) > 1:
                    try:
                        new_temp = float(parts[1])
                        if 0.0 <= new_temp <= 1.0:
                            current_temp = new_temp
                            console.print(f"[dim]✓ Temperature set to: {current_temp}[/dim]")
                        else:
                            console.print("[red]Temperature must be between 0.0 and 1.0[/red]")
                    except ValueError:
                        console.print("[red]Invalid temperature value[/red]")
                else:
                    console.print(f"[dim]Current temperature: {current_temp}[/dim]")
                    console.print("[dim]Usage: /temp <value> (0.0 = deterministic, 1.0 = creative)[/dim]")
                continue
            
            # Handle /investigate
            if cmd.startswith("/investigate"):
                parts = user_input.strip().split(maxsplit=1)
                if len(parts) > 1:
                    incident_desc = parts[1]
                    console.print(f"\n[yellow]Starting investigation: {incident_desc}[/yellow]")
                    
                    # Run the investigation
                    _run_investigation(incident_desc, mock=mock)
                    
                    # Add to history
                    history.append({"role": "user", "content": f"/investigate {incident_desc}"})
                    history.append({"role": "assistant", "content": f"Investigation completed for: {incident_desc}"})
                else:
                    console.print("[dim]Usage: /investigate <incident description>[/dim]")
                    console.print("[dim]Example: /investigate High error rate on checkout service[/dim]")
                continue
            
            # Handle unknown commands
            if user_input.strip().startswith("/"):
                console.print(f"[yellow]Unknown command: {user_input.strip().split()[0]}[/yellow]")
                console.print("[dim]Type /help for available commands[/dim]")
                continue
            
            # Regular message - add to history and get response
            history.append({"role": "user", "content": user_input})
            
            # Show thinking indicator
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                progress.add_task("[cyan]Thinking...", total=None)
                time.sleep(0.4 + random.uniform(0.2, 0.5))
            
            # Generate and stream response
            response = _generate_mock_response(user_input, history)
            console.print("[bold green]AutoSRE:[/bold green]")
            _stream_text(response, delay=0.006)
            history.append({"role": "assistant", "content": response})
            
        except KeyboardInterrupt:
            console.print("\n\n[dim]Goodbye! Stay reliable. 🚀[/dim]\n")
            break
        except EOFError:
            console.print("\n\n[dim]Goodbye! Stay reliable. 🚀[/dim]\n")
            break


# Make 'start' the default command when just running 'autosre chat'
@app.callback(invoke_without_command=True)
def chat_callback(
    ctx: typer.Context,
    message: Optional[str] = typer.Argument(None, help="Initial message (or start interactive mode)"),
    context: Optional[str] = typer.Option(
        None, "--context", "-c", help="Additional context file or incident ID"
    ),
    model: str = typer.Option(
        "gpt-4", "--model", "-m", help="LLM model to use"
    ),
    temperature: float = typer.Option(
        0.7, "--temperature", "-t", help="Response temperature (0.0-1.0)"
    ),
    mock: bool = typer.Option(
        True, "--mock/--live", help="Use mock responses (default) or live LLM"
    ),
):
    """Interactive chat with the SRE AI assistant."""
    if ctx.invoked_subcommand is None:
        # No subcommand provided, run 'start' with the provided arguments
        start(
            message=message,
            context=context,
            model=model,
            temperature=temperature,
            mock=mock,
        )
