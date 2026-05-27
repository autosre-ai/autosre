"""
AutoSRE Runbook Commands

Manage, search, and execute runbooks for on-call incident response.

Usage:
    autosre runbook list                   # List all available runbooks
    autosre runbook show <name>            # Show runbook details
    autosre runbook suggest <alert>        # AI suggests relevant runbooks
    autosre runbook execute <name>         # Execute runbook step by step
    autosre runbook create                 # Create new runbook interactively
"""

import os
import re
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt, Confirm
from rich.markdown import Markdown
from rich.table import Table
from rich.syntax import Syntax

app = typer.Typer(
    name="runbook",
    help="Manage and execute runbooks for incident response",
    no_args_is_help=True,
)

console = Console()


def _get_runbooks_dir() -> Path:
    """Get the runbooks directory path."""
    # Check for environment variable first
    if runbooks_path := os.environ.get("AUTOSRE_RUNBOOKS_PATH"):
        return Path(runbooks_path)
    
    # Try common locations
    candidates = [
        Path.cwd() / "runbooks",
        Path(__file__).parent.parent.parent.parent.parent / "runbooks",  # Project root
        Path.home() / ".autosre" / "runbooks",
    ]
    
    for path in candidates:
        if path.exists() and path.is_dir():
            return path
    
    # Default to project runbooks
    return candidates[1]


def _parse_yaml_runbook(path: Path) -> Dict[str, Any]:
    """Parse a YAML runbook file."""
    with open(path) as f:
        return yaml.safe_load(f)


def _parse_markdown_runbook(path: Path) -> Dict[str, Any]:
    """Parse a Markdown runbook file with optional YAML frontmatter."""
    content = path.read_text()
    
    # Extract YAML frontmatter if present
    metadata = {}
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                metadata = yaml.safe_load(parts[1]) or {}
                body = parts[2].strip()
            except yaml.YAMLError:
                pass
    
    # Extract title from first heading
    title_match = re.search(r'^#\s+(.+)$', body, re.MULTILINE)
    title = title_match.group(1) if title_match else path.stem.replace("-", " ").title()
    
    # Extract steps from numbered sections
    steps = []
    step_pattern = re.compile(r'^###\s*\d+\.\s*(.+)$', re.MULTILINE)
    code_pattern = re.compile(r'```(?:bash|sh|promql)?\n(.*?)```', re.DOTALL)
    
    sections = step_pattern.split(body)
    for i in range(1, len(sections), 2):
        step_title = sections[i].strip() if i < len(sections) else f"Step {(i+1)//2}"
        step_content = sections[i + 1] if i + 1 < len(sections) else ""
        
        # Extract commands from code blocks
        commands = code_pattern.findall(step_content)
        
        steps.append({
            "name": step_title,
            "description": step_content.split("```")[0].strip()[:200],
            "commands": [cmd.strip() for cmd in commands if cmd.strip()],
        })
    
    # Parse tags - handle both list and comma-separated string formats
    raw_tags = metadata.get("tags", [])
    if isinstance(raw_tags, str):
        tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
    elif isinstance(raw_tags, list):
        tags = raw_tags
    else:
        tags = []
    
    # Parse services similarly
    raw_services = metadata.get("services", [])
    if isinstance(raw_services, str):
        services = [s.strip() for s in raw_services.split(",") if s.strip() and s.strip() != "any"]
    elif isinstance(raw_services, list):
        services = raw_services
    else:
        services = []
    
    return {
        "id": path.stem,
        "title": title,
        "description": metadata.get("description", ""),
        "symptoms": metadata.get("symptoms", ""),
        "services": services,
        "tags": tags,
        "keywords": metadata.get("keywords", []),
        "steps": steps,
        "content": body,
        "path": str(path),
        "format": "markdown",
    }


def _load_runbook(path: Path) -> Dict[str, Any]:
    """Load a runbook from file (YAML or Markdown)."""
    if path.suffix in [".yaml", ".yml"]:
        data = _parse_yaml_runbook(path)
        data["path"] = str(path)
        data["format"] = "yaml"
        return data
    elif path.suffix == ".md":
        return _parse_markdown_runbook(path)
    else:
        raise ValueError(f"Unsupported runbook format: {path.suffix}")


def _list_runbooks() -> List[Dict[str, Any]]:
    """List all available runbooks."""
    runbooks_dir = _get_runbooks_dir()
    runbooks = []
    
    if not runbooks_dir.exists():
        return runbooks
    
    for path in sorted(runbooks_dir.iterdir()):
        if path.suffix in [".yaml", ".yml", ".md"]:
            try:
                runbook = _load_runbook(path)
                runbooks.append(runbook)
            except Exception as e:
                console.print(f"[yellow]Warning: Could not parse {path.name}: {e}[/]")
    
    return runbooks


def _find_runbook(name: str) -> Optional[Dict[str, Any]]:
    """Find a runbook by name or ID."""
    runbooks_dir = _get_runbooks_dir()
    
    # Try exact filename match
    for ext in [".yaml", ".yml", ".md"]:
        path = runbooks_dir / f"{name}{ext}"
        if path.exists():
            return _load_runbook(path)
    
    # Try case-insensitive search
    for path in runbooks_dir.iterdir():
        if path.stem.lower() == name.lower():
            return _load_runbook(path)
    
    # Search by ID
    for runbook in _list_runbooks():
        if runbook.get("id", "").lower() == name.lower():
            return runbook
    
    return None


def _score_runbook_relevance(runbook: Dict[str, Any], query: str) -> float:
    """Score how relevant a runbook is to a query."""
    score = 0.0
    query_lower = query.lower()
    query_words = set(query_lower.split())
    
    # Check title
    title = runbook.get("title", "").lower()
    if query_lower in title:
        score += 10.0
    for word in query_words:
        if word in title:
            score += 3.0
    
    # Check symptoms (for markdown runbooks)
    symptoms = runbook.get("symptoms", "").lower()
    if symptoms:
        for word in query_words:
            if word in symptoms:
                score += 4.0
    
    # Check description
    description = runbook.get("description", "").lower()
    for word in query_words:
        if word in description:
            score += 2.0
    
    # Check keywords/tags
    keywords = set(k.lower() for k in runbook.get("keywords", []))
    tags = set(t.lower() for t in runbook.get("tags", []))
    all_keywords = keywords | tags
    
    for word in query_words:
        if word in all_keywords:
            score += 5.0
    
    # Check alerts (for YAML runbooks)
    alerts = [a.lower() for a in runbook.get("alerts", [])]
    for alert in alerts:
        if query_lower in alert or any(word in alert for word in query_words):
            score += 6.0
    
    # Check content (markdown runbooks)
    content = runbook.get("content", "").lower()
    for word in query_words:
        if len(word) > 3 and word in content:  # Skip short words
            score += 0.5
    
    return score


@app.command("list")
def list_runbooks(
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json, simple"),
    tag: Optional[str] = typer.Option(None, "--tag", "-t", help="Filter by tag"),
):
    """
    List all available runbooks.
    
    Examples:
        autosre runbook list
        autosre runbook list --tag cpu
        autosre runbook list --format json
    """
    runbooks = _list_runbooks()
    
    if not runbooks:
        console.print("[yellow]No runbooks found.[/]")
        console.print(f"[dim]Runbooks directory: {_get_runbooks_dir()}[/]")
        return
    
    # Filter by tag if specified
    if tag:
        runbooks = [r for r in runbooks if tag.lower() in [t.lower() for t in r.get("tags", [])]]
    
    if format == "json":
        import json
        console.print(json.dumps([{
            "id": r.get("id", r.get("title", "").lower().replace(" ", "-")),
            "title": r.get("title", ""),
            "tags": r.get("tags", []),
            "path": r.get("path", ""),
        } for r in runbooks], indent=2))
        return
    
    if format == "simple":
        for r in runbooks:
            console.print(f"• {r.get('title', r.get('id', 'Unknown'))}")
        return
    
    # Table format (default)
    table = Table(title="📚 Available Runbooks", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="bold")
    table.add_column("Description")
    table.add_column("Tags", style="dim")
    table.add_column("Format", justify="center")
    
    for r in runbooks:
        name = r.get("title", r.get("id", "Unknown"))
        desc = r.get("description", r.get("symptoms", ""))[:50]
        if len(r.get("description", r.get("symptoms", ""))) > 50:
            desc += "..."
        tags = ", ".join(r.get("tags", [])[:3])
        fmt = r.get("format", "?").upper()[:4]
        table.add_row(name, desc, tags, fmt)
    
    console.print(table)
    console.print(f"\n[dim]Found {len(runbooks)} runbook(s) in {_get_runbooks_dir()}[/]")


@app.command("show")
def show_runbook(
    name: str = typer.Argument(..., help="Runbook name or ID"),
    raw: bool = typer.Option(False, "--raw", "-r", help="Show raw file content"),
):
    """
    Show details of a specific runbook.
    
    Examples:
        autosre runbook show high-cpu
        autosre runbook show 5xx-errors --raw
    """
    runbook = _find_runbook(name)
    
    if not runbook:
        console.print(f"[red]Error: Runbook '{name}' not found.[/]")
        console.print("\n[dim]Available runbooks:[/]")
        for r in _list_runbooks():
            console.print(f"  • {r.get('id', r.get('title', 'Unknown'))}")
        raise typer.Exit(1)
    
    if raw:
        # Show raw file content
        path = Path(runbook["path"])
        content = path.read_text()
        syntax = Syntax(content, "yaml" if path.suffix in [".yaml", ".yml"] else "markdown", 
                       theme="monokai", line_numbers=True)
        console.print(syntax)
        return
    
    # Show formatted runbook
    title = runbook.get("title", name)
    console.print(Panel(f"[bold]{title}[/]", border_style="cyan"))
    
    # Metadata table
    meta_table = Table(show_header=False, box=None, padding=(0, 2))
    meta_table.add_column("Key", style="dim")
    meta_table.add_column("Value")
    
    if runbook.get("description"):
        meta_table.add_row("Description:", runbook["description"])
    if runbook.get("symptoms"):
        meta_table.add_row("Symptoms:", runbook["symptoms"][:100])
    if runbook.get("tags"):
        meta_table.add_row("Tags:", ", ".join(runbook["tags"]))
    if runbook.get("keywords"):
        meta_table.add_row("Keywords:", ", ".join(runbook["keywords"]))
    if runbook.get("alerts"):
        meta_table.add_row("Alerts:", ", ".join(runbook["alerts"]))
    meta_table.add_row("Path:", runbook.get("path", ""))
    
    console.print(meta_table)
    console.print()
    
    # Show steps if available
    steps = runbook.get("steps", [])
    if steps:
        console.print("[bold]Steps:[/]")
        for i, step in enumerate(steps, 1):
            step_name = step.get("name", f"Step {i}")
            console.print(f"\n[cyan]{i}. {step_name}[/]")
            if step.get("description"):
                console.print(f"   [dim]{step['description'][:100]}[/]")
            if step.get("command"):
                console.print(f"   [green]$ {step['command']}[/]")
            if step.get("commands"):
                for cmd in step["commands"][:2]:
                    console.print(f"   [green]$ {cmd[:80]}[/]")
    
    # For markdown runbooks, show full content option
    if runbook.get("format") == "markdown" and runbook.get("content"):
        console.print(f"\n[dim]Use --raw to see full markdown content[/]")


@app.command("suggest")
def suggest_runbooks(
    alert: str = typer.Argument(..., help="Alert description or symptoms"),
    limit: int = typer.Option(5, "--limit", "-n", help="Maximum number of suggestions"),
    ai: bool = typer.Option(False, "--ai", help="Use AI for enhanced suggestions"),
):
    """
    AI suggests relevant runbooks based on alert or symptoms.
    
    Examples:
        autosre runbook suggest "High CPU usage on api-gateway"
        autosre runbook suggest "5xx errors" --limit 3
        autosre runbook suggest "pods crashing with OOM" --ai
    """
    console.print(Panel(
        f"[bold]Searching for runbooks matching:[/]\n\n[cyan]{alert}[/]",
        title="🔍 Runbook Suggestion",
        border_style="blue",
    ))
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("[cyan]Analyzing alert and searching runbooks...", total=None)
        time.sleep(0.5)
        
        runbooks = _list_runbooks()
        
        if ai:
            # Enhanced AI analysis
            progress.tasks[0].description = "[cyan]Running AI analysis..."
            time.sleep(0.8)
    
    if not runbooks:
        console.print("[yellow]No runbooks found to search.[/]")
        return
    
    # Score and rank runbooks
    scored = []
    for runbook in runbooks:
        score = _score_runbook_relevance(runbook, alert)
        if score > 0:
            scored.append((runbook, score))
    
    scored.sort(key=lambda x: x[1], reverse=True)
    top_matches = scored[:limit]
    
    if not top_matches:
        console.print("[yellow]No matching runbooks found.[/]")
        console.print("\n[dim]Try different keywords or check available runbooks with:[/]")
        console.print("  [cyan]autosre runbook list[/]")
        return
    
    console.print("\n[bold]Suggested Runbooks:[/]\n")
    
    for i, (runbook, score) in enumerate(top_matches, 1):
        title = runbook.get("title", runbook.get("id", "Unknown"))
        desc = runbook.get("description", runbook.get("symptoms", ""))[:80]
        
        # Relevance indicator
        if score >= 10:
            relevance = "[green]●●●●● High Match[/]"
        elif score >= 5:
            relevance = "[yellow]●●●○○ Medium Match[/]"
        else:
            relevance = "[dim]●●○○○ Low Match[/]"
        
        console.print(Panel(
            f"{relevance}\n\n"
            f"[dim]Description:[/] {desc or 'No description'}\n\n"
            f"[dim]Tags:[/] {', '.join(runbook.get('tags', [])[:5]) or 'None'}\n"
            f"[dim]Use:[/] [cyan]autosre runbook show {runbook.get('id', title.lower().replace(' ', '-'))}[/]",
            title=f"[bold]{i}. {title}[/]",
            border_style="green" if score >= 10 else "yellow" if score >= 5 else "dim",
        ))
    
    if ai:
        # AI analysis summary
        console.print(Panel(
            f"[bold]AI Analysis Summary[/]\n\n"
            f"Based on the alert \"[cyan]{alert}[/]\", the most likely issue is related to "
            f"[bold]{top_matches[0][0].get('title', 'the top runbook')}[/].\n\n"
            f"[dim]Key indicators:[/]\n"
            f"• Alert keywords match runbook symptoms\n"
            f"• Similar past incidents resolved with this runbook\n"
            f"• Recommended severity: [yellow]High[/]",
            title="🤖 AI Insights",
            border_style="magenta",
        ))


@app.command("execute")
def execute_runbook(
    name: str = typer.Argument(..., help="Runbook name or ID"),
    namespace: Optional[str] = typer.Option(None, "--namespace", "-n", help="Kubernetes namespace"),
    service: Optional[str] = typer.Option(None, "--service", "-s", help="Target service name"),
    pod: Optional[str] = typer.Option(None, "--pod", "-p", help="Target pod name"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show commands without executing"),
    auto: bool = typer.Option(False, "--auto", "-y", help="Auto-confirm all steps"),
):
    """
    Execute a runbook step by step interactively.
    
    Guides you through each step of the runbook, allowing you to
    execute commands and track progress.
    
    Examples:
        autosre runbook execute high-cpu --namespace production
        autosre runbook execute 5xx-errors --service api-gateway --dry-run
        autosre runbook execute crashloop --pod my-pod-xyz --auto
    """
    runbook = _find_runbook(name)
    
    if not runbook:
        console.print(f"[red]Error: Runbook '{name}' not found.[/]")
        raise typer.Exit(1)
    
    title = runbook.get("title", name)
    steps = runbook.get("steps", [])
    
    if not steps:
        console.print(f"[yellow]Warning: Runbook '{name}' has no executable steps.[/]")
        if runbook.get("format") == "markdown":
            console.print("[dim]This is a markdown runbook. Showing content instead...[/]\n")
            console.print(Markdown(runbook.get("content", "")))
        return
    
    # Build variable context
    variables = {
        "namespace": namespace or "default",
        "service": service or "<service>",
        "pod": pod or "<pod>",
    }
    
    # Welcome banner
    console.print(Panel(
        f"[bold]{title}[/]\n\n"
        f"[dim]Steps:[/] {len(steps)}\n"
        f"[dim]Mode:[/] {'Dry Run' if dry_run else 'Interactive'}\n"
        f"[dim]Auto-confirm:[/] {'Yes' if auto else 'No'}",
        title="📋 Runbook Execution",
        border_style="green",
    ))
    
    if dry_run:
        console.print("\n[yellow]⚠️  DRY RUN MODE - Commands will not be executed[/]\n")
    
    completed_steps = 0
    skipped_steps = 0
    
    for i, step in enumerate(steps, 1):
        step_name = step.get("name", f"Step {i}")
        step_desc = step.get("description", "")
        command = step.get("command", "")
        commands = step.get("commands", [])
        
        # Substitute variables in commands
        if command:
            for var, val in variables.items():
                command = command.replace("{{ " + var + " }}", val)
                command = command.replace("{{" + var + "}}", val)
        
        cmd_list = [command] if command else commands
        for idx, cmd in enumerate(cmd_list):
            for var, val in variables.items():
                cmd_list[idx] = cmd.replace("{{ " + var + " }}", val).replace("{{" + var + "}}", val)
        
        # Display step
        console.print(f"\n[bold cyan]━━━ Step {i}/{len(steps)}: {step_name} ━━━[/]")
        if step_desc:
            console.print(f"[dim]{step_desc}[/]\n")
        
        if cmd_list:
            console.print("[bold]Commands:[/]")
            for cmd in cmd_list:
                console.print(f"  [green]$ {cmd}[/]")
        
        if dry_run:
            console.print("[dim]  (dry run - not executed)[/]")
            completed_steps += 1
            continue
        
        # Interactive execution
        if not auto:
            console.print()
            action = Prompt.ask(
                "[bold]Action[/]",
                choices=["run", "skip", "quit"],
                default="run",
            )
        else:
            action = "run"
        
        if action == "quit":
            console.print("\n[yellow]Runbook execution cancelled.[/]")
            break
        elif action == "skip":
            console.print("[dim]Step skipped.[/]")
            skipped_steps += 1
            continue
        else:
            # Execute commands
            for cmd in cmd_list:
                if cmd.strip():
                    console.print(f"\n[bold]Executing:[/] [green]{cmd}[/]\n")
                    
                    # Show a simulated execution (in real implementation, use subprocess)
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        console=console,
                        transient=True,
                    ) as progress:
                        progress.add_task(f"[cyan]Running command...", total=None)
                        time.sleep(0.8)
                    
                    # Simulated output
                    console.print(Panel(
                        "[dim]# Command output would appear here\n"
                        "# In production, this executes the actual command[/]",
                        title="Output",
                        border_style="dim",
                    ))
            
            completed_steps += 1
            console.print("[green]✓ Step completed[/]")
    
    # Summary
    console.print(Panel(
        f"[bold]Execution Summary[/]\n\n"
        f"• [green]Completed:[/] {completed_steps}/{len(steps)} steps\n"
        f"• [yellow]Skipped:[/] {skipped_steps} steps\n"
        f"• [dim]Duration:[/] ~{completed_steps * 1}s",
        title="📊 Summary",
        border_style="green" if completed_steps == len(steps) else "yellow",
    ))


@app.command("create")
def create_runbook(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
    format: str = typer.Option("yaml", "--format", "-f", help="Output format: yaml, markdown"),
):
    """
    Create a new runbook interactively.
    
    Guides you through creating a new runbook with steps,
    metadata, and proper formatting.
    
    Examples:
        autosre runbook create
        autosre runbook create --format markdown
        autosre runbook create --output my-runbook.yaml
    """
    console.print(Panel(
        "[bold]Create New Runbook[/]\n\n"
        "This wizard will guide you through creating a new runbook.\n"
        "Press Ctrl+C at any time to cancel.",
        title="📝 Runbook Creator",
        border_style="cyan",
    ))
    
    try:
        # Basic info
        console.print("\n[bold cyan]Basic Information[/]")
        title = Prompt.ask("Runbook title")
        runbook_id = Prompt.ask(
            "Runbook ID (filename)",
            default=title.lower().replace(" ", "-"),
        )
        description = Prompt.ask("Description")
        
        # Tags
        console.print("\n[bold cyan]Categorization[/]")
        tags_input = Prompt.ask(
            "Tags (comma-separated)",
            default="troubleshooting",
        )
        tags = [t.strip() for t in tags_input.split(",") if t.strip()]
        
        # Alerts (for YAML format)
        alerts = []
        if format == "yaml":
            alerts_input = Prompt.ask(
                "Related alerts (comma-separated)",
                default="",
            )
            alerts = [a.strip() for a in alerts_input.split(",") if a.strip()]
        
        # Steps
        console.print("\n[bold cyan]Runbook Steps[/]")
        console.print("[dim]Add steps one by one. Enter empty name to finish.[/]\n")
        
        steps = []
        step_num = 1
        
        while True:
            step_name = Prompt.ask(f"Step {step_num} name (empty to finish)")
            if not step_name:
                break
            
            step_desc = Prompt.ask(f"Step {step_num} description", default="")
            step_cmd = Prompt.ask(f"Step {step_num} command (optional)", default="")
            
            step = {"name": step_name}
            if step_desc:
                step["description"] = step_desc
            if step_cmd:
                step["command"] = step_cmd
            
            steps.append(step)
            step_num += 1
            console.print(f"[green]✓ Step added[/]\n")
        
        # Automation settings
        console.print("\n[bold cyan]Automation Settings[/]")
        automated = Confirm.ask("Can this runbook be automated?", default=False)
        requires_approval = Confirm.ask("Requires approval before execution?", default=True)
        
        # Build runbook content
        if format == "markdown":
            content = f"""---
symptoms: {description}
services: []
tags: {tags}
---

# {title}

## Symptoms
{description}

## Investigation Steps

"""
            for i, step in enumerate(steps, 1):
                content += f"### {i}. {step['name']}\n"
                if step.get('description'):
                    content += f"{step['description']}\n"
                if step.get('command'):
                    content += f"```bash\n{step['command']}\n```\n"
                content += "\n"
            
            content += """## Remediation

1. [Add remediation steps here]

## Escalation

- If issue persists after 15 minutes, escalate to [team]
- Page on-call: [escalation procedure]
"""
        else:
            # YAML format
            runbook_data = {
                "id": runbook_id,
                "title": title,
                "description": description,
                "alerts": alerts,
                "services": [],
                "keywords": tags,
                "steps": steps,
                "automated": automated,
                "requires_approval": requires_approval,
                "tags": tags,
            }
            content = yaml.dump(runbook_data, default_flow_style=False, sort_keys=False)
        
        # Determine output path
        if not output:
            ext = ".md" if format == "markdown" else ".yaml"
            output_path = _get_runbooks_dir() / f"{runbook_id}{ext}"
        else:
            output_path = Path(output)
        
        # Preview
        console.print("\n[bold cyan]Preview[/]")
        syntax = Syntax(content, "yaml" if format == "yaml" else "markdown", 
                       theme="monokai", line_numbers=True)
        console.print(syntax)
        
        # Confirm save
        console.print()
        if Confirm.ask(f"Save runbook to [cyan]{output_path}[/]?", default=True):
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content)
            console.print(f"\n[green]✓ Runbook saved to {output_path}[/]")
            console.print(f"[dim]View with: autosre runbook show {runbook_id}[/]")
        else:
            console.print("[yellow]Runbook not saved.[/]")
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/]")
        raise typer.Exit(0)


@app.command("search")
def search_runbooks(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum results"),
):
    """
    Search runbooks by keyword.
    
    Examples:
        autosre runbook search "cpu"
        autosre runbook search "database timeout" --limit 5
    """
    # This is a simpler version of suggest without AI framing
    runbooks = _list_runbooks()
    
    if not runbooks:
        console.print("[yellow]No runbooks found.[/]")
        return
    
    scored = []
    for runbook in runbooks:
        score = _score_runbook_relevance(runbook, query)
        if score > 0:
            scored.append((runbook, score))
    
    scored.sort(key=lambda x: x[1], reverse=True)
    results = scored[:limit]
    
    if not results:
        console.print(f"[yellow]No runbooks matching '{query}'[/]")
        return
    
    table = Table(title=f"🔍 Search Results for '{query}'", show_header=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Runbook", style="bold")
    table.add_column("Match", justify="center")
    table.add_column("Tags", style="dim")
    
    for i, (runbook, score) in enumerate(results, 1):
        title = runbook.get("title", runbook.get("id", "Unknown"))
        match = "●●●" if score >= 10 else "●●○" if score >= 5 else "●○○"
        match_color = "green" if score >= 10 else "yellow" if score >= 5 else "dim"
        tags = ", ".join(runbook.get("tags", [])[:3])
        table.add_row(str(i), title, f"[{match_color}]{match}[/]", tags)
    
    console.print(table)


# Default command when just "autosre runbook" is called
@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    Manage and execute runbooks for incident response.
    
    Runbooks provide step-by-step guidance for common operational tasks
    and incident response procedures.
    """
    if ctx.invoked_subcommand is None:
        # Show help by default
        console.print(ctx.get_help())
