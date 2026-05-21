"""Memory commands for AutoSRE CLI."""

import click

from .client import AutoSREClient
from .utils import (
    console,
    create_table,
    format_timestamp,
    get_formatter,
    spinner,
)


@click.group()
@click.pass_context
def memory(ctx: click.Context):
    """Manage investigation memory.
    
    The memory system stores patterns, solutions, and learnings
    from past investigations to improve future incident response.
    """
    pass


@memory.command("search")
@click.argument("query")
@click.option("--limit", "-n", default=10, help="Number of results to return")
@click.option(
    "--type", "-t", "memory_type",
    type=click.Choice(["pattern", "solution", "runbook", "all"]),
    default="all",
    help="Type of memory to search",
)
@click.pass_context
def search_memory(
    ctx: click.Context,
    query: str,
    limit: int,
    memory_type: str,
):
    """Search investigation memory.
    
    Examples:
        autosre memory search "database timeout"
        autosre memory search "OOM" --type pattern
        autosre memory search "redis connection" -n 5
    """
    formatter = get_formatter(ctx)
    
    try:
        with AutoSREClient() as client:
            with spinner(f'Searching memory for "{query}"...', formatter.json_mode):
                results = client.search_memory(
                    query=query,
                    limit=limit,
                    memory_type=None if memory_type == "all" else memory_type,
                )
            
            if formatter.json_mode:
                formatter.print_json(results)
                return
            
            if not results:
                formatter.print_info(f'No results found for "{query}"')
                return
            
            table = create_table(
                f'Memory Search: "{query}"',
                [
                    ("Type", "cyan"),
                    ("Title", "white"),
                    ("Score", "green"),
                    ("Created", "dim"),
                ],
            )
            
            for item in results:
                title = item.get("title", item.get("summary", ""))
                if len(title) > 50:
                    title = title[:47] + "..."
                
                score = item.get("score", item.get("relevance", 0))
                score_str = f"{score:.2f}" if isinstance(score, float) else str(score)
                
                table.add_row(
                    item.get("type", "unknown"),
                    title,
                    score_str,
                    format_timestamp(item.get("created_at")),
                )
            
            console.print(table)
            
            # Show details of top result if it has content
            if results and results[0].get("content"):
                console.print("\n[bold]Top Result:[/bold]")
                content = results[0].get("content", "")
                if len(content) > 500:
                    content = content[:500] + "..."
                console.print(f"[dim]{content}[/dim]")
    
    except Exception as e:
        formatter.print_error(f"Memory search failed: {e}")
        ctx.exit(1)


@memory.command("stats")
@click.pass_context
def memory_stats(ctx: click.Context):
    """Show memory statistics.
    
    Displays counts and metrics about the memory store,
    including number of patterns, solutions, and runbooks.
    """
    formatter = get_formatter(ctx)
    
    try:
        with AutoSREClient() as client:
            with spinner("Fetching memory statistics...", formatter.json_mode):
                stats = client.get_memory_stats()
            
            if formatter.json_mode:
                formatter.print_json(stats)
                return
            
            console.print("[bold cyan]Memory Statistics[/bold cyan]\n")
            
            # Overall counts
            table = create_table(
                "Memory Counts",
                [
                    ("Type", "cyan"),
                    ("Count", "green"),
                ],
            )
            
            counts = stats.get("counts", {})
            for mem_type, count in counts.items():
                table.add_row(mem_type.title(), str(count))
            
            total = stats.get("total", sum(counts.values()))
            table.add_row("[bold]Total[/bold]", f"[bold]{total}[/bold]")
            
            console.print(table)
            
            # Additional metrics
            metrics = stats.get("metrics", {})
            if metrics:
                console.print("\n[bold cyan]Metrics[/bold cyan]\n")
                
                for key, value in metrics.items():
                    label = key.replace("_", " ").title()
                    if isinstance(value, float):
                        console.print(f"  {label}: {value:.2f}")
                    else:
                        console.print(f"  {label}: {value}")
            
            # Storage info
            storage = stats.get("storage", {})
            if storage:
                console.print("\n[bold cyan]Storage[/bold cyan]\n")
                console.print(f"  Backend: {storage.get('backend', 'unknown')}")
                if "size_mb" in storage:
                    console.print(f"  Size: {storage['size_mb']:.2f} MB")
                if "last_updated" in storage:
                    console.print(f"  Last Updated: {format_timestamp(storage['last_updated'])}")
    
    except Exception as e:
        formatter.print_error(f"Failed to get memory stats: {e}")
        ctx.exit(1)


@memory.command("add")
@click.option("--type", "-t", "memory_type", required=True,
              type=click.Choice(["pattern", "solution", "runbook"]),
              help="Type of memory entry")
@click.option("--title", "-T", required=True, help="Title of the entry")
@click.option("--content", "-c", help="Content (or use --file)")
@click.option("--file", "-f", "content_file", type=click.Path(exists=True),
              help="Read content from file")
@click.option("--tag", "-g", multiple=True, help="Tags for the entry")
@click.pass_context
def add_memory(
    ctx: click.Context,
    memory_type: str,
    title: str,
    content: str | None,
    content_file: str | None,
    tag: tuple[str, ...],
):
    """Add a new memory entry.
    
    Examples:
        autosre memory add --type pattern --title "Redis OOM" -c "Look for memory limits"
        autosre memory add --type runbook --title "DB Failover" --file runbook.md
    """
    formatter = get_formatter(ctx)
    
    # Get content
    if content_file:
        with open(content_file) as f:
            content = f.read()
    elif not content:
        # Read from stdin
        content = click.get_text_stream("stdin").read()
    
    if not content:
        formatter.print_error("Content is required")
        ctx.exit(1)
    
    formatter.print_info("Memory add endpoint not yet implemented in API")
    formatter.print_info(f"Would add {memory_type}: {title}")


@memory.command("export")
@click.option("--output", "-o", type=click.Path(), help="Output file (default: stdout)")
@click.option("--format", "-f", "output_format",
              type=click.Choice(["json", "yaml"]),
              default="json",
              help="Output format")
@click.pass_context
def export_memory(
    ctx: click.Context,
    output: str | None,
    output_format: str,
):
    """Export memory data.
    
    Export all memory entries for backup or migration.
    """
    formatter = get_formatter(ctx)
    formatter.print_info("Memory export not yet implemented")
