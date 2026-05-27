"""
AutoSRE Benchmark Command

Performance benchmarking for AutoSRE components:
- Memory system (read/write speed)
- LLM response latency
- Evidence collection speed
- Overall investigation timing
"""

import asyncio
import json
import statistics
import time
import uuid
from datetime import datetime, timezone
from typing import Any, NamedTuple, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

app = typer.Typer(
    name="benchmark",
    help="Performance benchmarking for AutoSRE components",
    no_args_is_help=False,
)

console = Console()


class BenchmarkResult(NamedTuple):
    """Result of a single benchmark."""
    name: str
    samples: list[float]
    unit: str = "ms"
    passed: bool = True
    error: str | None = None

    @property
    def min_time(self) -> float:
        return min(self.samples) if self.samples else 0.0

    @property
    def max_time(self) -> float:
        return max(self.samples) if self.samples else 0.0

    @property
    def mean_time(self) -> float:
        return statistics.mean(self.samples) if self.samples else 0.0

    @property
    def median_time(self) -> float:
        return statistics.median(self.samples) if self.samples else 0.0

    @property
    def stddev(self) -> float:
        return statistics.stdev(self.samples) if len(self.samples) > 1 else 0.0

    @property
    def ops_per_sec(self) -> float:
        if not self.samples or self.mean_time == 0:
            return 0.0
        # Convert from ms to ops/sec
        return 1000.0 / self.mean_time


class Benchmarker:
    """Runs performance benchmarks on AutoSRE components."""

    def __init__(self, iterations: int = 10, warmup: int = 2):
        self.iterations = iterations
        self.warmup = warmup
        self.results: list[BenchmarkResult] = []

    def _create_test_episode(self) -> Any:
        """Create a test episode for memory benchmarks."""
        from autosre.memory import Episode

        return Episode(
            id=f"bench-{uuid.uuid4().hex[:8]}",
            created_at=datetime.now(timezone.utc),
            alert_type="benchmark_test",
            service_name="benchmark-service",
            severity="info",
            root_cause="Benchmark test root cause",
            summary="This is a benchmark test episode",
            resolved=True,
            effectiveness_score=0.95,
            skills_used=["prometheus", "kubernetes", "log_analysis"],
            key_findings=[
                {"finding": "Test finding 1", "confidence": 0.9},
                {"finding": "Test finding 2", "confidence": 0.85},
            ],
            duration_seconds=120,
            symptoms=["High error rate", "Increased latency"],
            metrics={"error_rate": 0.05, "p99_latency": 250},
            logs=["Error: Connection timeout", "Warning: Resource pressure"],
            topology={"upstream": ["api-gateway"], "downstream": ["database"]},
            steps_taken=["Checked metrics", "Analyzed logs", "Identified root cause"],
            hypotheses=["Database overload (0.8 likelihood)", "Network latency (0.3 likelihood)"],
            resolution="Scaled database replicas",
            tags=["benchmark", "test"],
        )

    async def benchmark_memory_write(self, progress: Progress, task_id: int) -> BenchmarkResult:
        """Benchmark memory write operations."""
        from autosre.memory import EpisodicMemory
        import tempfile
        import os

        samples: list[float] = []
        
        try:
            # Use a temporary database for benchmarking
            with tempfile.TemporaryDirectory() as tmpdir:
                db_path = os.path.join(tmpdir, "bench_memory.db")
                memory = EpisodicMemory(db_path=db_path)

                # Warmup
                for _ in range(self.warmup):
                    episode = self._create_test_episode()
                    memory.store_episode(episode)

                # Actual benchmark
                for i in range(self.iterations):
                    episode = self._create_test_episode()
                    
                    start = time.perf_counter()
                    memory.store_episode(episode)
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    
                    samples.append(elapsed_ms)
                    progress.update(task_id, advance=1)

            return BenchmarkResult(
                name="Memory Write",
                samples=samples,
                unit="ms",
                passed=True,
            )
        except Exception as e:
            return BenchmarkResult(
                name="Memory Write",
                samples=[],
                unit="ms",
                passed=False,
                error=str(e),
            )

    async def benchmark_memory_read(self, progress: Progress, task_id: int) -> BenchmarkResult:
        """Benchmark memory read/search operations."""
        from autosre.memory import EpisodicMemory, MemoryQuery
        import tempfile
        import os

        samples: list[float] = []

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                db_path = os.path.join(tmpdir, "bench_memory.db")
                memory = EpisodicMemory(db_path=db_path)

                # Pre-populate with test data
                for _ in range(50):
                    episode = self._create_test_episode()
                    memory.store_episode(episode)

                # Warmup
                for _ in range(self.warmup):
                    query = MemoryQuery(text="benchmark", service="benchmark-service")
                    await memory.retrieve(query, limit=10)

                # Actual benchmark
                for i in range(self.iterations):
                    query = MemoryQuery(text="benchmark", service="benchmark-service")
                    
                    start = time.perf_counter()
                    await memory.retrieve(query, limit=10)
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    
                    samples.append(elapsed_ms)
                    progress.update(task_id, advance=1)

            return BenchmarkResult(
                name="Memory Read",
                samples=samples,
                unit="ms",
                passed=True,
            )
        except Exception as e:
            return BenchmarkResult(
                name="Memory Read",
                samples=[],
                unit="ms",
                passed=False,
                error=str(e),
            )

    async def benchmark_memory_search(self, progress: Progress, task_id: int) -> BenchmarkResult:
        """Benchmark memory similarity search."""
        from autosre.memory import EpisodicMemory
        import tempfile
        import os

        samples: list[float] = []

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                db_path = os.path.join(tmpdir, "bench_memory.db")
                memory = EpisodicMemory(db_path=db_path)

                # Pre-populate with test data across different alert types
                alert_types = ["error_rate", "latency", "availability", "resource_exhaustion"]
                for _ in range(25):
                    for alert_type in alert_types:
                        episode = self._create_test_episode()
                        episode.alert_type = alert_type
                        memory.store_episode(episode)

                # Warmup
                for _ in range(self.warmup):
                    memory.search_similar("error_rate", service="benchmark-service", limit=5)

                # Actual benchmark
                for i in range(self.iterations):
                    start = time.perf_counter()
                    memory.search_similar("error_rate", service="benchmark-service", limit=5)
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    
                    samples.append(elapsed_ms)
                    progress.update(task_id, advance=1)

            return BenchmarkResult(
                name="Memory Search",
                samples=samples,
                unit="ms",
                passed=True,
            )
        except Exception as e:
            return BenchmarkResult(
                name="Memory Search",
                samples=[],
                unit="ms",
                passed=False,
                error=str(e),
            )

    async def benchmark_llm_latency(self, progress: Progress, task_id: int) -> BenchmarkResult:
        """Benchmark LLM response latency (if configured)."""
        samples: list[float] = []

        try:
            from autosre.config import Settings
            from autosre.llm import LLMRouter, get_router
            from autosre.llm.router import LLMConfig, LLMProvider, TaskType

            settings = Settings()

            # Check if we have a configured LLM provider
            if settings.llm_provider == "ollama":
                # Check if Ollama is running
                import httpx
                try:
                    resp = httpx.get(f"{settings.ollama_host}/api/tags", timeout=2.0)
                    if resp.status_code != 200:
                        raise ConnectionError("Ollama not responding")
                except Exception:
                    return BenchmarkResult(
                        name="LLM Latency",
                        samples=[],
                        unit="ms",
                        passed=False,
                        error="Ollama not available (skipped)",
                    )

                config = LLMConfig(
                    provider=LLMProvider.OLLAMA,
                    model=settings.ollama_model,
                    base_url=settings.ollama_host,
                )
            elif settings.llm_provider == "anthropic" and settings.anthropic_api_key:
                config = LLMConfig(
                    provider=LLMProvider.ANTHROPIC,
                    model=settings.anthropic_model,
                    api_key=settings.anthropic_api_key,
                )
            elif settings.llm_provider == "openai" and settings.openai_api_key:
                config = LLMConfig(
                    provider=LLMProvider.OPENAI,
                    model=settings.openai_model,
                    api_key=settings.openai_api_key,
                )
            else:
                return BenchmarkResult(
                    name="LLM Latency",
                    samples=[],
                    unit="ms",
                    passed=False,
                    error="No LLM provider configured (skipped)",
                )

            router = LLMRouter(configs=[config])

            test_prompt = "Respond with only the word 'OK'. Do not say anything else."

            # Only do 3 iterations for LLM (expensive/slow)
            llm_iterations = min(3, self.iterations)

            # Warmup with 1 call
            try:
                await router.complete(test_prompt, task=TaskType.ANALYSIS)
            except Exception as e:
                return BenchmarkResult(
                    name="LLM Latency",
                    samples=[],
                    unit="ms",
                    passed=False,
                    error=f"LLM call failed: {str(e)[:50]}",
                )

            # Benchmark
            for i in range(llm_iterations):
                start = time.perf_counter()
                await router.complete(test_prompt, task=TaskType.ANALYSIS)
                elapsed_ms = (time.perf_counter() - start) * 1000
                
                samples.append(elapsed_ms)
                progress.update(task_id, advance=1)

            # Fill remaining progress
            remaining = self.iterations - llm_iterations
            progress.update(task_id, advance=remaining)

            return BenchmarkResult(
                name="LLM Latency",
                samples=samples,
                unit="ms",
                passed=True,
            )
        except Exception as e:
            progress.update(task_id, advance=self.iterations)
            return BenchmarkResult(
                name="LLM Latency",
                samples=[],
                unit="ms",
                passed=False,
                error=str(e),
            )

    async def benchmark_evidence_collection(self, progress: Progress, task_id: int) -> BenchmarkResult:
        """Benchmark evidence collection (simulated)."""
        samples: list[float] = []

        try:
            from autosre.compliance.evidence import EvidenceCollector, EvidenceType
            from autosre.compliance.audit import ComplianceFramework
            from datetime import timedelta

            collector = EvidenceCollector()
            
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=30)

            # Warmup
            for _ in range(self.warmup):
                await collector.collect_access_logs(start_date, end_date, ComplianceFramework.SOC2)

            # Benchmark - collecting different evidence types
            for i in range(self.iterations):
                start = time.perf_counter()
                await collector.collect_access_logs(start_date, end_date, ComplianceFramework.SOC2)
                await collector.collect_encryption_config(ComplianceFramework.SOC2)
                elapsed_ms = (time.perf_counter() - start) * 1000
                
                samples.append(elapsed_ms)
                progress.update(task_id, advance=1)

            return BenchmarkResult(
                name="Evidence Collection",
                samples=samples,
                unit="ms",
                passed=True,
            )
        except Exception as e:
            progress.update(task_id, advance=self.iterations)
            return BenchmarkResult(
                name="Evidence Collection",
                samples=[],
                unit="ms",
                passed=False,
                error=str(e),
            )

    async def benchmark_config_loading(self, progress: Progress, task_id: int) -> BenchmarkResult:
        """Benchmark configuration loading."""
        samples: list[float] = []

        try:
            # Clear any cached settings
            from autosre import config as config_module
            
            for i in range(self.iterations):
                # Force reload of settings
                start = time.perf_counter()
                from autosre.config import Settings
                settings = Settings()
                _ = settings.llm_provider  # Access a property
                elapsed_ms = (time.perf_counter() - start) * 1000
                
                samples.append(elapsed_ms)
                progress.update(task_id, advance=1)

            return BenchmarkResult(
                name="Config Loading",
                samples=samples,
                unit="ms",
                passed=True,
            )
        except Exception as e:
            progress.update(task_id, advance=self.iterations)
            return BenchmarkResult(
                name="Config Loading",
                samples=[],
                unit="ms",
                passed=False,
                error=str(e),
            )

    async def run_all(self) -> list[BenchmarkResult]:
        """Run all benchmarks with progress display."""
        benchmarks = [
            ("Memory Write", self.benchmark_memory_write),
            ("Memory Read", self.benchmark_memory_read),
            ("Memory Search", self.benchmark_memory_search),
            ("Config Loading", self.benchmark_config_loading),
            ("Evidence Collection", self.benchmark_evidence_collection),
            ("LLM Latency", self.benchmark_llm_latency),
        ]

        results: list[BenchmarkResult] = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            for name, bench_func in benchmarks:
                task_id = progress.add_task(f"[cyan]{name}...", total=self.iterations)
                result = await bench_func(progress, task_id)
                results.append(result)
                
                # Update task description with result
                if result.passed:
                    progress.update(task_id, description=f"[green]✓ {name}")
                else:
                    progress.update(task_id, description=f"[red]✗ {name}")

        self.results = results
        return results


def display_results(results: list[BenchmarkResult], json_output: bool = False):
    """Display benchmark results in a table or JSON."""
    if json_output:
        output = []
        for r in results:
            output.append({
                "name": r.name,
                "passed": r.passed,
                "error": r.error,
                "samples": len(r.samples),
                "min_ms": round(r.min_time, 3) if r.passed else None,
                "max_ms": round(r.max_time, 3) if r.passed else None,
                "mean_ms": round(r.mean_time, 3) if r.passed else None,
                "median_ms": round(r.median_time, 3) if r.passed else None,
                "stddev_ms": round(r.stddev, 3) if r.passed else None,
                "ops_per_sec": round(r.ops_per_sec, 1) if r.passed else None,
            })
        console.print(json.dumps(output, indent=2))
        return

    # Create results table
    table = Table(
        title="⚡ AutoSRE Benchmark Results",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Benchmark", style="white")
    table.add_column("Status", justify="center")
    table.add_column("Min", justify="right")
    table.add_column("Mean", justify="right")
    table.add_column("Max", justify="right")
    table.add_column("Std Dev", justify="right")
    table.add_column("Ops/sec", justify="right", style="green")

    for r in results:
        if r.passed and r.samples:
            status = "[green]✓ PASS[/]"
            min_str = f"{r.min_time:.2f}ms"
            mean_str = f"{r.mean_time:.2f}ms"
            max_str = f"{r.max_time:.2f}ms"
            stddev_str = f"{r.stddev:.2f}ms" if r.stddev > 0 else "-"
            ops_str = f"{r.ops_per_sec:.1f}"
        else:
            status = f"[red]✗ SKIP[/]"
            min_str = "-"
            mean_str = "-"
            max_str = "-"
            stddev_str = "-"
            ops_str = "-"

        table.add_row(r.name, status, min_str, mean_str, max_str, stddev_str, ops_str)

    console.print()
    console.print(table)

    # Show errors if any
    errors = [r for r in results if r.error]
    if errors:
        console.print()
        console.print("[yellow]Notes:[/]")
        for r in errors:
            console.print(f"  • {r.name}: {r.error}")

    # Summary
    passed = sum(1 for r in results if r.passed and r.samples)
    total = len(results)
    console.print()
    console.print(f"[bold]Summary:[/] {passed}/{total} benchmarks completed successfully")
    console.print()


@app.callback(invoke_without_command=True)
def benchmark_main(
    ctx: typer.Context,
    iterations: int = typer.Option(10, "--iterations", "-n", help="Number of iterations per benchmark"),
    warmup: int = typer.Option(2, "--warmup", "-w", help="Number of warmup iterations"),
    json_output: bool = typer.Option(False, "--json", help="Output results as JSON"),
    include_llm: bool = typer.Option(True, "--llm/--no-llm", help="Include LLM latency benchmark"),
):
    """
    Run performance benchmarks on AutoSRE components.
    
    Measures:
    - Memory system read/write/search performance
    - Configuration loading speed
    - Evidence collection latency
    - LLM response times (if configured)
    
    Examples:
        autosre benchmark                    # Run all benchmarks
        autosre benchmark -n 20              # 20 iterations
        autosre benchmark --json             # Output as JSON
        autosre benchmark --no-llm           # Skip LLM benchmark
    """
    if ctx.invoked_subcommand is not None:
        return

    if not json_output:
        console.print()
        console.print(Panel(
            "[bold cyan]AutoSRE Performance Benchmark[/]\n\n"
            f"Iterations: {iterations} | Warmup: {warmup}",
            border_style="cyan",
        ))
        console.print()

    benchmarker = Benchmarker(iterations=iterations, warmup=warmup)
    results = asyncio.run(benchmarker.run_all())
    
    # Filter out LLM if requested
    if not include_llm:
        results = [r for r in results if r.name != "LLM Latency"]

    display_results(results, json_output=json_output)


@app.command("memory")
def benchmark_memory(
    iterations: int = typer.Option(10, "--iterations", "-n", help="Number of iterations"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """
    Benchmark memory system only.
    
    Tests write, read, and search operations on the episodic memory.
    """
    if not json_output:
        console.print()
        console.print("[bold cyan]Memory System Benchmark[/]")
        console.print()

    benchmarker = Benchmarker(iterations=iterations, warmup=2)

    async def run_memory_benchmarks():
        results = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            for name, func in [
                ("Memory Write", benchmarker.benchmark_memory_write),
                ("Memory Read", benchmarker.benchmark_memory_read),
                ("Memory Search", benchmarker.benchmark_memory_search),
            ]:
                task_id = progress.add_task(f"[cyan]{name}...", total=iterations)
                result = await func(progress, task_id)
                results.append(result)
                if result.passed:
                    progress.update(task_id, description=f"[green]✓ {name}")
                else:
                    progress.update(task_id, description=f"[red]✗ {name}")
        return results

    results = asyncio.run(run_memory_benchmarks())
    display_results(results, json_output=json_output)


@app.command("llm")
def benchmark_llm(
    iterations: int = typer.Option(3, "--iterations", "-n", help="Number of iterations (default 3 to limit API costs)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """
    Benchmark LLM response latency.
    
    Tests the configured LLM provider's response time.
    Note: Limited iterations by default to minimize API costs.
    """
    if not json_output:
        console.print()
        console.print("[bold cyan]LLM Latency Benchmark[/]")
        console.print()

    benchmarker = Benchmarker(iterations=iterations, warmup=1)

    async def run_llm_benchmark():
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task_id = progress.add_task("[cyan]LLM Latency...", total=iterations)
            result = await benchmarker.benchmark_llm_latency(progress, task_id)
            if result.passed:
                progress.update(task_id, description="[green]✓ LLM Latency")
            else:
                progress.update(task_id, description="[red]✗ LLM Latency")
        return [result]

    results = asyncio.run(run_llm_benchmark())
    display_results(results, json_output=json_output)
