"""
AutoSRE Investigation Commands

Run AI-powered incident investigations from the command line.
Connects to real infrastructure (Prometheus, Kubernetes, Elasticsearch).
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import typer
import yaml
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.tree import Tree

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="investigate",
    help="Run AI-powered incident investigations",
    no_args_is_help=True,
)

console = Console()


class ConfigurationError(Exception):
    """Raised when required configuration is missing."""
    pass


def load_config() -> dict[str, Any]:
    """Load configuration from ~/.autosre/config.yaml.
    
    Returns:
        Configuration dictionary
        
    Raises:
        ConfigurationError: If config file is missing or invalid
    """
    config_path = Path("~/.autosre/config.yaml").expanduser()
    
    if not config_path.exists():
        raise ConfigurationError(
            f"Configuration file not found: {config_path}\n"
            "Please create ~/.autosre/config.yaml with your infrastructure settings.\n"
            "See: autosre config init"
        )
    
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
            return config or {}
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in config file: {e}")


def _format_evidence(evidence: dict) -> str:
    """Format evidence for display."""
    source = evidence.get("source", "unknown")
    confidence = evidence.get("confidence", 0.0)
    data = evidence.get("data", {})
    
    lines = [f"📋 [cyan]{source}[/] (confidence: {confidence:.0%})"]
    if isinstance(data, dict):
        for k, v in list(data.items())[:3]:  # Show first 3 items
            lines.append(f"   • {k}: {v}")
    elif isinstance(data, str):
        lines.append(f"   {data[:100]}...")
    return "\n".join(lines)


def _format_hypothesis(hypothesis: dict, index: int) -> str:
    """Format hypothesis for display."""
    title = hypothesis.get("title", f"Hypothesis {index}")
    likelihood = hypothesis.get("likelihood", 0.0)
    supporting = hypothesis.get("supporting_evidence", [])
    
    stars = "⭐" * int(likelihood * 5)
    lines = [f"[bold]💡 {title}[/] {stars} ({likelihood:.0%})"]
    
    if supporting:
        lines.append("   Supporting evidence:")
        for ev in supporting[:2]:
            lines.append(f"   • {ev}")
    
    return "\n".join(lines)


class InvestigationRunner:
    """Manages the investigation execution and display using real infrastructure."""
    
    def __init__(
        self,
        alert: str,
        service: Optional[str] = None,
        severity: str = "high",
        output_format: str = "text",
        stream: bool = True,
        demo: bool = False,
    ):
        self.alert = alert
        self.service = service
        self.severity = severity
        self.output_format = output_format
        self.stream = stream
        self.demo = demo
        self.investigation_id = str(uuid4())[:8]
        self.start_time = datetime.now(UTC)
        
        # Investigation state
        self.evidence: list = []
        self.hypotheses: list = []
        self.root_cause: Optional[str] = None
        self.report: Optional[str] = None
        
        # Load configuration (allow missing in demo mode)
        try:
            self.config = load_config()
        except ConfigurationError:
            if demo:
                self.config = {}
            else:
                raise
        
        # Initialize skill instances (lazy loading)
        self._prometheus_skill = None
        self._kubernetes_skill = None
        self._logs_subagent = None
        
    def _get_prometheus_skill(self):
        """Get or create Prometheus skill instance."""
        if self._prometheus_skill is None:
            try:
                from skills.prometheus import PrometheusSkill
            except ImportError:
                raise ConfigurationError(
                    "PrometheusSkill not available. Install with: pip install opensre-skills"
                )
            
            prom_config = self.config.get("prometheus", {})
            url = prom_config.get("url") or os.environ.get("PROMETHEUS_URL")
            
            if not url:
                raise ConfigurationError(
                    "Prometheus URL not configured.\n"
                    "Set prometheus.url in ~/.autosre/config.yaml or PROMETHEUS_URL environment variable."
                )
            
            self._prometheus_skill = PrometheusSkill({
                "url": url,
                "alertmanager_url": prom_config.get("alertmanager_url"),
                "timeout": prom_config.get("timeout", 30),
                "auth": prom_config.get("auth", {}),
            })
        
        return self._prometheus_skill
    
    def _get_kubernetes_skill(self):
        """Get or create Kubernetes skill instance."""
        if self._kubernetes_skill is None:
            try:
                from skills.kubernetes import KubernetesSkill
            except ImportError:
                raise ConfigurationError(
                    "KubernetesSkill not available. Install with: pip install opensre-skills"
                )
            
            k8s_config = self.config.get("kubernetes", {})
            
            self._kubernetes_skill = KubernetesSkill({
                "kubeconfig": k8s_config.get("kubeconfig"),
                "context": k8s_config.get("context"),
                "namespace": k8s_config.get("namespace", "default"),
            })
        
        return self._kubernetes_skill
    
    def _get_logs_subagent(self):
        """Get or create Logs subagent instance."""
        if self._logs_subagent is None:
            from autosre.agents.subagents.logs import LogsSubagent
            
            logs_config = self.config.get("logs", {})
            backend_url = logs_config.get("url") or os.environ.get("ELASTICSEARCH_URL")
            
            if not backend_url:
                raise ConfigurationError(
                    "Logs backend URL not configured.\n"
                    "Set logs.url in ~/.autosre/config.yaml or ELASTICSEARCH_URL environment variable."
                )
            
            self._logs_subagent = LogsSubagent(
                backend=logs_config.get("backend", "elasticsearch"),
                backend_url=backend_url,
                index_pattern=logs_config.get("index_pattern", "logs-*"),
                dry_run=False,
            )
        
        return self._logs_subagent
        
    async def run_async(self) -> dict:
        """Run the investigation asynchronously."""
        from autosre.memory import EpisodicMemory, Episode, MemoryQuery
        
        # Initialize memory
        memory = EpisodicMemory()
        
        # Phase 1: Context Gathering
        mode_text = "Demo (Simulated Data)" if self.demo else "Live (Real Infrastructure)"
        if self.stream:
            console.print()
            console.print(Panel(
                f"[bold cyan]🔍 Investigation {self.investigation_id}[/]\n\n"
                f"[bold]Alert:[/] {self.alert}\n"
                f"[bold]Service:[/] {self.service or 'auto-detect'}\n"
                f"[bold]Severity:[/] {self.severity}\n"
                f"[bold]Mode:[/] {mode_text}",
                title="Investigation Started",
                border_style="cyan",
            ))
        
        # Check for similar past incidents
        if self.stream:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Searching episodic memory...", total=None)
                
                # Search memory for similar incidents
                query = MemoryQuery(
                    text=self.alert,
                    service=self.service,
                    alert_type=self._classify_alert(),
                )
                similar_episodes = await memory.retrieve(query, limit=3)
                
                progress.update(task, description=f"Found {len(similar_episodes)} similar incidents")
        
        # Phase 2: Evidence Collection from real infrastructure
        self.evidence = await self._collect_real_evidence()
        
        if self.stream:
            console.print()
            console.print("[bold]📊 Evidence Collected:[/]")
            for ev in self.evidence:
                console.print(_format_evidence(ev))
            console.print()
        
        # Phase 3: Hypothesis Generation using real LLM
        self.hypotheses = await self._generate_real_hypotheses()
        
        if self.stream:
            console.print("[bold]🧠 Hypotheses:[/]")
            for i, hyp in enumerate(self.hypotheses, 1):
                console.print(_format_hypothesis(hyp, i))
            console.print()
        
        # Phase 4: Root Cause Analysis
        if self.hypotheses:
            self.root_cause = self.hypotheses[0].get("title", "Unknown")
        
        if self.stream:
            console.print(Panel(
                f"[bold green]Root Cause:[/] {self.root_cause}",
                title="🎯 Analysis Complete",
                border_style="green",
            ))
        
        # Phase 5: Generate Report
        self.report = self._generate_report()
        
        # Store episode in memory
        duration = (datetime.now(UTC) - self.start_time).total_seconds()
        episode = Episode(
            id=self.investigation_id,
            alert_type=self._classify_alert(),
            service_name=self.service,
            severity=self.severity,
            root_cause=self.root_cause,
            summary=f"Investigation of: {self.alert}",
            resolved=True,
            effectiveness_score=0.85,
            skills_used=["prometheus", "kubernetes", "logs"],
            key_findings=[{"finding": h.get("title")} for h in self.hypotheses[:3]],
            duration_seconds=int(duration),
            steps_taken=["context_gathering", "evidence_collection", "hypothesis_generation", "root_cause_analysis"],
        )
        await memory.store(episode)
        
        result = {
            "investigation_id": self.investigation_id,
            "alert": self.alert,
            "service": self.service,
            "severity": self.severity,
            "evidence": self.evidence,
            "hypotheses": self.hypotheses,
            "root_cause": self.root_cause,
            "report": self.report,
            "duration_seconds": duration,
        }
        
        return result
    
    def _classify_alert(self) -> str:
        """Classify the alert type."""
        alert_lower = self.alert.lower()
        if any(word in alert_lower for word in ["error", "5xx", "exception", "failed"]):
            return "error_rate"
        elif any(word in alert_lower for word in ["latency", "slow", "timeout", "p99"]):
            return "latency"
        elif any(word in alert_lower for word in ["memory", "oom", "cpu", "disk"]):
            return "resource_exhaustion"
        elif any(word in alert_lower for word in ["down", "unavailable", "unreachable"]):
            return "availability"
        return "general"
    
    async def _collect_real_evidence(self) -> list:
        """Collect real evidence from configured infrastructure sources."""
        # In demo mode, return simulated evidence
        if self.demo:
            return self._generate_demo_evidence()
        
        evidence = []
        errors = []
        
        # Collect from Prometheus
        try:
            prom_evidence = await self._collect_prometheus_evidence()
            if prom_evidence:
                evidence.append(prom_evidence)
        except ConfigurationError as e:
            logger.warning(f"Prometheus not configured: {e}")
            errors.append(f"prometheus: {e}")
        except Exception as e:
            logger.error(f"Prometheus error: {e}")
            errors.append(f"prometheus: {e}")
        
        # Collect from Kubernetes
        try:
            k8s_evidence = await self._collect_kubernetes_evidence()
            if k8s_evidence:
                evidence.append(k8s_evidence)
        except ConfigurationError as e:
            logger.warning(f"Kubernetes not configured: {e}")
            errors.append(f"kubernetes: {e}")
        except Exception as e:
            logger.error(f"Kubernetes error: {e}")
            errors.append(f"kubernetes: {e}")
        
        # Collect from Logs
        try:
            logs_evidence = await self._collect_logs_evidence()
            if logs_evidence:
                evidence.append(logs_evidence)
        except ConfigurationError as e:
            logger.warning(f"Logs backend not configured: {e}")
            errors.append(f"logs: {e}")
        except Exception as e:
            logger.error(f"Logs error: {e}")
            errors.append(f"logs: {e}")
        
        if not evidence:
            raise ConfigurationError(
                f"No evidence could be collected. Infrastructure errors:\n" +
                "\n".join(f"  - {err}" for err in errors) +
                "\n\nPlease configure at least one data source in ~/.autosre/config.yaml\n"
                "Or use --demo flag to run with simulated data."
            )
        
        return evidence
    
    def _generate_demo_evidence(self) -> list:
        """Generate simulated evidence for demo mode based on alert type."""
        import random
        evidence = []
        alert_type = self._classify_alert()
        service = self.service or "api-gateway"
        
        # Prometheus-like metrics evidence
        prom_data = {}
        if alert_type == "latency":
            prom_data = {
                "p99_latency": f"{random.uniform(1.5, 5.0):.2f}s",
                "p50_latency": f"{random.uniform(0.3, 0.8):.2f}s",
                "request_rate": f"{random.randint(100, 500)}/s",
                "active_alerts": random.randint(1, 3),
            }
        elif alert_type == "error_rate":
            prom_data = {
                "error_rate": f"{random.uniform(5.0, 25.0):.1f}%",
                "5xx_count": random.randint(50, 500),
                "request_rate": f"{random.randint(200, 800)}/s",
                "active_alerts": random.randint(2, 5),
            }
        elif alert_type == "resource_exhaustion":
            prom_data = {
                "cpu_usage": f"{random.uniform(85, 98):.1f}%",
                "memory_usage": f"{random.uniform(80, 95):.1f}%",
                "container_restarts": random.randint(1, 10),
            }
        else:
            prom_data = {
                "request_rate": f"{random.randint(100, 500)}/s",
                "error_rate": f"{random.uniform(0.5, 5.0):.1f}%",
                "p99_latency": f"{random.uniform(0.5, 2.0):.2f}s",
            }
        
        evidence.append({
            "source": "prometheus (demo)",
            "confidence": 0.85,
            "data": prom_data,
        })
        
        # Kubernetes-like evidence
        k8s_data = {
            "pod_status": f"{random.randint(2, 4)}/{random.randint(3, 5)} Running",
            "restarts": random.randint(0, 8),
        }
        if alert_type == "resource_exhaustion":
            k8s_data["warning_events"] = random.randint(3, 10)
            k8s_data["top_event"] = random.choice(["OOMKilled", "FailedScheduling", "BackOff"])
        elif alert_type in ["error_rate", "latency"]:
            k8s_data["warning_events"] = random.randint(1, 5)
            k8s_data["top_event"] = random.choice(["Unhealthy", "FailedLiveness", "BackOff"])
        
        evidence.append({
            "source": "kubernetes (demo)",
            "confidence": 0.80,
            "data": k8s_data,
        })
        
        # Logs-like evidence
        logs_data = {
            "error_count": random.randint(50, 500),
            "pattern_matches": random.randint(100, 1000),
        }
        if alert_type == "latency":
            logs_data["sample_error"] = f"Connection timeout after 30s connecting to upstream service"
        elif alert_type == "error_rate":
            logs_data["sample_error"] = f"NullPointerException in RequestHandler.process()"
        elif alert_type == "resource_exhaustion":
            logs_data["sample_error"] = f"OutOfMemoryError: Java heap space"
        else:
            logs_data["sample_error"] = f"Service {service} returned error: connection refused"
        
        evidence.append({
            "source": "logs (demo)",
            "confidence": 0.75,
            "data": logs_data,
        })
        
        return evidence
    
    async def _collect_prometheus_evidence(self) -> Optional[dict]:
        """Query Prometheus for relevant metrics."""
        skill = self._get_prometheus_skill()
        await skill.initialize()
        
        try:
            data = {}
            
            # Build service-specific queries
            service_filter = f'service="{self.service}"' if self.service else ""
            
            # Query error rate
            if "error" in self.alert.lower() or self._classify_alert() == "error_rate":
                error_query = f'sum(rate(http_requests_total{{status=~"5..",{service_filter}}}[5m])) / sum(rate(http_requests_total{{{service_filter}}}[5m])) * 100'
                result = await skill.query(error_query)
                if result.success and result.data:
                    error_rate = result.data[0].value if result.data else 0
                    data["error_rate"] = f"{error_rate:.1f}%"
            
            # Query latency
            if "latency" in self.alert.lower() or self._classify_alert() == "latency":
                latency_query = f'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{{{service_filter}}}[5m])) by (le))'
                result = await skill.query(latency_query)
                if result.success and result.data:
                    p99 = result.data[0].value if result.data else 0
                    data["p99_latency"] = f"{p99:.2f}s"
            
            # Query request rate
            req_query = f'sum(rate(http_requests_total{{{service_filter}}}[5m]))'
            result = await skill.query(req_query)
            if result.success and result.data:
                req_rate = result.data[0].value if result.data else 0
                data["request_rate"] = f"{req_rate:.1f}/s"
            
            # Get active alerts
            alerts_result = await skill.get_alerts(state="firing")
            if alerts_result.success and alerts_result.data:
                relevant_alerts = [a for a in alerts_result.data 
                                 if not self.service or self.service in str(a.labels)]
                data["active_alerts"] = len(relevant_alerts)
            
            if data:
                return {
                    "source": "prometheus",
                    "confidence": 0.9,
                    "data": data,
                }
            return None
            
        finally:
            await skill.shutdown()
    
    async def _collect_kubernetes_evidence(self) -> Optional[dict]:
        """Query Kubernetes for pod and deployment status."""
        skill = self._get_kubernetes_skill()
        await skill.initialize()
        
        try:
            data = {}
            namespace = self.config.get("kubernetes", {}).get("namespace", "default")
            
            # Get pod status for the service
            labels = f"app={self.service}" if self.service else None
            pods_result = await skill.get_pods(namespace=namespace, labels=labels)
            
            if pods_result.success and pods_result.data:
                pods = pods_result.data
                running = sum(1 for p in pods if p.status == "Running" and p.ready)
                total = len(pods)
                total_restarts = sum(p.restarts for p in pods)
                
                data["pod_status"] = f"{running}/{total} Running"
                data["restarts"] = total_restarts
                
                # Check for recently restarted pods
                crash_looping = [p.name for p in pods if p.restarts > 3]
                if crash_looping:
                    data["crash_looping"] = crash_looping[:3]
            
            # Get recent events
            events_result = await skill.get_events(namespace=namespace, minutes=30)
            if events_result.success and events_result.data:
                warning_events = [e for e in events_result.data if e.type == "Warning"]
                if warning_events:
                    data["warning_events"] = len(warning_events)
                    # Get most common event reason
                    reasons = [e.reason for e in warning_events]
                    if reasons:
                        data["top_event"] = max(set(reasons), key=reasons.count)
            
            if data:
                return {
                    "source": "kubernetes",
                    "confidence": 0.85,
                    "data": data,
                }
            return None
            
        finally:
            pass  # KubernetesSkill doesn't have shutdown
    
    async def _collect_logs_evidence(self) -> Optional[dict]:
        """Search logs for error patterns."""
        subagent = self._get_logs_subagent()
        
        data = {}
        
        # Build search query based on alert
        if self.service:
            # Get error logs for the service
            es_query = subagent._build_es_query(
                must=[{"term": {"service": self.service}}],
                filter_=[{"term": {"level": "error"}}],
                time_range="1h",
            )
            result = await subagent._search_elasticsearch(es_query, size=100)
            
            if "error" not in result:
                hits = result.get("hits", {})
                total = hits.get("total", {}).get("value", 0)
                data["error_count"] = total
                
                # Extract common error patterns
                logs = hits.get("hits", [])
                if logs:
                    messages = [h.get("_source", {}).get("message", "")[:100] for h in logs[:10]]
                    if messages:
                        data["sample_error"] = messages[0]
        
        # Search for specific keywords from alert
        keywords = ["error", "exception", "timeout", "connection", "failed"]
        alert_keywords = [kw for kw in keywords if kw in self.alert.lower()]
        
        if alert_keywords:
            search_query = " OR ".join(alert_keywords)
            es_query = subagent._build_es_query(
                must=[{"query_string": {"query": search_query, "default_field": "message"}}],
                time_range="1h",
            )
            result = await subagent._search_elasticsearch(es_query, size=50)
            
            if "error" not in result:
                hits = result.get("hits", {})
                total = hits.get("total", {}).get("value", 0)
                data["pattern_matches"] = total
        
        if data:
            return {
                "source": "logs",
                "confidence": 0.75,
                "data": data,
            }
        return None
    
    async def _generate_real_hypotheses(self) -> list:
        """Generate hypotheses using real LLM (OpenAI or Anthropic)."""
        llm_config = self.config.get("llm", {})
        provider = llm_config.get("provider") or os.environ.get("OPENSRE_LLM_PROVIDER", "anthropic")
        
        # Build context from evidence
        evidence_context = json.dumps(self.evidence, indent=2, default=str)
        
        prompt = f"""You are an expert SRE analyzing an incident. Based on the evidence collected, generate hypotheses for the root cause.

Alert: {self.alert}
Service: {self.service or "Unknown"}
Severity: {self.severity}

Evidence collected:
{evidence_context}

Generate 3 hypotheses for the root cause, ranked by likelihood. For each hypothesis, explain the supporting evidence.

Respond in JSON format:
[
  {{
    "title": "Brief description of the hypothesis",
    "likelihood": 0.0-1.0,
    "supporting_evidence": ["evidence point 1", "evidence point 2"]
  }}
]"""

        try:
            if provider == "anthropic":
                hypotheses = await self._call_anthropic(prompt, llm_config)
            elif provider == "openai":
                hypotheses = await self._call_openai(prompt, llm_config)
            elif provider == "litellm":
                hypotheses = await self._call_litellm(prompt, llm_config)
            else:
                raise ConfigurationError(f"Unknown LLM provider: {provider}. Use 'anthropic', 'openai', or 'litellm'")
            
            return hypotheses
            
        except Exception as e:
            logger.error(f"LLM hypothesis generation failed: {e}")
            # Fallback to rule-based hypotheses
            return self._generate_fallback_hypotheses()
    
    async def _call_anthropic(self, prompt: str, config: dict) -> list:
        """Call Anthropic API for hypothesis generation."""
        api_key = config.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ConfigurationError(
                "Anthropic API key not configured.\n"
                "Set llm.api_key in ~/.autosre/config.yaml or ANTHROPIC_API_KEY environment variable."
            )
        
        try:
            import anthropic
        except ImportError:
            raise ConfigurationError("anthropic package not installed. Run: pip install anthropic")
        
        client = anthropic.Anthropic(api_key=api_key)
        
        response = client.messages.create(
            model=config.get("model", "claude-sonnet-4-20250514"),
            max_tokens=config.get("max_tokens", 2048),
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse JSON from response
        text = response.content[0].text
        # Find JSON array in response
        import re
        json_match = re.search(r'\[[\s\S]*\]', text)
        if json_match:
            return json.loads(json_match.group())
        return []
    
    async def _call_openai(self, prompt: str, config: dict) -> list:
        """Call OpenAI API for hypothesis generation."""
        api_key = config.get("api_key") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ConfigurationError(
                "OpenAI API key not configured.\n"
                "Set llm.api_key in ~/.autosre/config.yaml or OPENAI_API_KEY environment variable."
            )
        
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ConfigurationError("openai package not installed. Run: pip install openai")
        
        client = AsyncOpenAI(api_key=api_key)
        
        response = await client.chat.completions.create(
            model=config.get("model", "gpt-4o"),
            max_tokens=config.get("max_tokens", 2048),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        text = response.choices[0].message.content
        result = json.loads(text)
        # Handle both array and object with hypotheses key
        if isinstance(result, list):
            return result
        return result.get("hypotheses", [])
    
    async def _call_litellm(self, prompt: str, config: dict) -> list:
        """Call LiteLLM for hypothesis generation."""
        try:
            import litellm
        except ImportError:
            raise ConfigurationError("litellm package not installed. Run: pip install litellm")
        
        model = config.get("model", "gpt-4o")
        
        response = await litellm.acompletion(
            model=model,
            max_tokens=config.get("max_tokens", 2048),
            messages=[{"role": "user", "content": prompt}],
        )
        
        text = response.choices[0].message.content
        import re
        json_match = re.search(r'\[[\s\S]*\]', text)
        if json_match:
            return json.loads(json_match.group())
        return []
    
    def _generate_fallback_hypotheses(self) -> list:
        """Generate rule-based hypotheses when LLM is unavailable."""
        hypotheses = []
        alert_type = self._classify_alert()
        
        # Analyze evidence to generate hypotheses
        for ev in self.evidence:
            source = ev.get("source", "").lower()
            data = ev.get("data", {})
            
            if "prometheus" in source:
                if data.get("error_rate"):
                    hypotheses.append({
                        "title": "Elevated error rate indicating application issues",
                        "likelihood": 0.7,
                        "supporting_evidence": [
                            f"Error rate: {data['error_rate']}",
                            "Prometheus metrics show increased failures"
                        ]
                    })
                if data.get("p99_latency"):
                    hypotheses.append({
                        "title": "High latency indicating performance degradation",
                        "likelihood": 0.75,
                        "supporting_evidence": [
                            f"P99 latency: {data['p99_latency']}",
                            "Response times exceed normal thresholds"
                        ]
                    })
                if data.get("cpu_usage") or data.get("memory_usage"):
                    hypotheses.append({
                        "title": "Resource exhaustion causing service degradation",
                        "likelihood": 0.8,
                        "supporting_evidence": [
                            f"CPU: {data.get('cpu_usage', 'N/A')}, Memory: {data.get('memory_usage', 'N/A')}",
                            "Container may need more resources or has a leak"
                        ]
                    })
            
            if "kubernetes" in source:
                if data.get("restarts", 0) > 0:
                    hypotheses.append({
                        "title": "Pod instability causing service disruption",
                        "likelihood": 0.65,
                        "supporting_evidence": [
                            f"Pod restarts: {data.get('restarts', 0)}",
                            f"Pod status: {data.get('pod_status', 'unknown')}"
                        ]
                    })
                if data.get("top_event"):
                    hypotheses.append({
                        "title": f"Kubernetes event: {data['top_event']}",
                        "likelihood": 0.6,
                        "supporting_evidence": [
                            f"Warning events: {data.get('warning_events', 0)}",
                            f"Most common event: {data['top_event']}"
                        ]
                    })
            
            if "logs" in source:
                if data.get("error_count", 0) > 0:
                    hypotheses.append({
                        "title": "Application errors detected in logs",
                        "likelihood": 0.6,
                        "supporting_evidence": [
                            f"Error count: {data.get('error_count', 0)}",
                            data.get("sample_error", "")[:100] if data.get("sample_error") else ""
                        ]
                    })
        
        # Add alert-type specific hypotheses if we don't have enough
        if len(hypotheses) < 3:
            if alert_type == "latency":
                hypotheses.append({
                    "title": "Upstream dependency experiencing slowdown",
                    "likelihood": 0.55,
                    "supporting_evidence": [
                        f"Alert indicates: {self.alert}",
                        "Check downstream service dependencies"
                    ]
                })
            elif alert_type == "error_rate":
                hypotheses.append({
                    "title": "Recent deployment may have introduced bugs",
                    "likelihood": 0.5,
                    "supporting_evidence": [
                        "Check recent deployments and config changes",
                        "Review error patterns for root cause"
                    ]
                })
        
        # Sort by likelihood
        hypotheses.sort(key=lambda x: x["likelihood"], reverse=True)
        return hypotheses[:3]
    
    def _generate_report(self) -> str:
        """Generate investigation report."""
        duration = (datetime.now(UTC) - self.start_time).total_seconds()
        
        report = f"""# Investigation Report

## Summary
- **Investigation ID:** {self.investigation_id}
- **Alert:** {self.alert}
- **Service:** {self.service or 'Not specified'}
- **Severity:** {self.severity}
- **Duration:** {duration:.1f}s
- **Status:** Completed

## Root Cause
{self.root_cause or 'Under investigation'}

## Evidence Summary
"""
        for ev in self.evidence:
            report += f"\n### {ev.get('source', 'Unknown')}\n"
            report += f"Confidence: {ev.get('confidence', 0):.0%}\n"
            data = ev.get("data", {})
            if isinstance(data, dict):
                for k, v in data.items():
                    report += f"- **{k}:** {v}\n"
        
        report += "\n## Hypotheses (ranked by likelihood)\n"
        for i, hyp in enumerate(self.hypotheses, 1):
            report += f"\n### {i}. {hyp.get('title')}\n"
            report += f"Likelihood: {hyp.get('likelihood', 0):.0%}\n"
            if hyp.get("supporting_evidence"):
                report += "Supporting evidence:\n"
                for ev in hyp["supporting_evidence"]:
                    report += f"- {ev}\n"
        
        report += f"""
## Recommendations
1. Review recent deployments for configuration changes
2. Check connection pool settings for {self.service or 'affected service'}
3. Monitor error rates after implementing fix
4. Update runbook with this incident pattern

---
*Generated by AutoSRE v0.2.0*
"""
        return report
    
    def run(self) -> dict:
        """Run the investigation synchronously."""
        return asyncio.run(self.run_async())


@app.command()
def run(
    alert: str = typer.Argument(..., help="Alert or incident description"),
    service: str = typer.Option(None, "--service", "-s", help="Service name"),
    severity: str = typer.Option("high", "--severity", help="Severity level: low|medium|high|critical"),
    output: str = typer.Option("text", "--output", "-o", help="Output format: text|json|markdown"),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="Stream output in real-time"),
    save: Optional[Path] = typer.Option(None, "--save", help="Save report to file"),
    demo: bool = typer.Option(False, "--demo", "-d", help="Run with simulated data (no infrastructure required)"),
):
    """
    Start an AI-powered investigation using real infrastructure.
    
    Connects to Prometheus, Kubernetes, and log backends configured in ~/.autosre/config.yaml.
    Uses LLM (Anthropic/OpenAI) for hypothesis generation.
    
    Examples:
        autosre investigate run "High error rate on checkout"
        autosre investigate run "API latency spike" --service api-gateway
        autosre investigate run "Redis connection errors" --output json --save report.json
        autosre investigate run "API latency spike" --demo  # Run without infrastructure
    """
    try:
        runner = InvestigationRunner(
            alert=alert,
            service=service,
            severity=severity,
            output_format=output,
            stream=stream,
            demo=demo,
        )
        
        result = runner.run()
        
        # Output formatting
        if output == "json":
            json_output = json.dumps(result, indent=2, default=str)
            if save:
                save.write_text(json_output)
                console.print(f"[green]✓[/] Report saved to {save}")
            else:
                console.print(json_output)
        
        elif output == "markdown":
            if save:
                save.write_text(result["report"])
                console.print(f"[green]✓[/] Report saved to {save}")
            else:
                console.print()
                console.print(Markdown(result["report"]))
        
        else:  # text
            if save:
                save.write_text(result["report"])
                console.print(f"[green]✓[/] Report saved to {save}")
            elif not stream:
                console.print(Markdown(result["report"]))
                
    except ConfigurationError as e:
        console.print(f"[red]Configuration Error:[/] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/] {e}")
        logger.exception("Investigation failed")
        raise typer.Exit(1)


@app.command()
def history(
    service: str = typer.Option(None, "--service", "-s", help="Filter by service"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of results"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show recent investigations from memory."""
    from autosre.memory import EpisodicMemory
    
    memory = EpisodicMemory()
    stats = memory.get_stats()
    
    if json_output:
        console.print(json.dumps(stats, indent=2))
        return
    
    table = Table(title="Recent Investigations", show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Alert Type", style="yellow")
    table.add_column("Service")
    table.add_column("Root Cause")
    table.add_column("Duration")
    table.add_column("Status", style="green")
    
    # Query recent episodes
    import asyncio
    from autosre.memory import MemoryQuery
    
    async def get_episodes():
        query = MemoryQuery(text="", service=service)
        return await memory.retrieve(query, limit=limit)
    
    episodes = asyncio.run(get_episodes())
    
    for ep in episodes:
        duration_str = f"{ep.duration_seconds}s" if ep.duration_seconds else "-"
        status = "[green]✓ Resolved[/]" if ep.resolved else "[yellow]Pending[/]"
        table.add_row(
            ep.id[:8],
            ep.alert_type,
            ep.service_name or "-",
            (ep.root_cause or "-")[:30],
            duration_str,
            status,
        )
    
    if not episodes:
        console.print("[yellow]No investigations found[/]")
    else:
        console.print(table)


@app.command()
def replay(
    investigation_id: str = typer.Argument(..., help="Investigation ID to replay"),
):
    """Replay a past investigation with visualization."""
    import asyncio
    from autosre.memory import EpisodicMemory
    
    memory = EpisodicMemory()
    
    async def get_episode():
        return await memory.get(investigation_id)
    
    episode = asyncio.run(get_episode())
    
    if not episode:
        console.print(f"[red]Investigation {investigation_id} not found[/]")
        raise typer.Exit(1)
    
    # Display episode details
    console.print(Panel(
        f"[bold]Alert Type:[/] {episode.alert_type}\n"
        f"[bold]Service:[/] {episode.service_name or 'N/A'}\n"
        f"[bold]Root Cause:[/] {episode.root_cause or 'Unknown'}\n"
        f"[bold]Duration:[/] {episode.duration_seconds}s\n"
        f"[bold]Status:[/] {'✓ Resolved' if episode.resolved else 'Pending'}",
        title=f"Investigation {episode.id}",
        border_style="cyan",
    ))
    
    # Show steps taken
    if episode.steps_taken:
        console.print("\n[bold]Steps Taken:[/]")
        for i, step in enumerate(episode.steps_taken, 1):
            console.print(f"  {i}. {step}")
    
    # Show key findings
    if episode.key_findings:
        console.print("\n[bold]Key Findings:[/]")
        for finding in episode.key_findings:
            if isinstance(finding, dict):
                console.print(f"  • {finding.get('finding', finding)}")
            else:
                console.print(f"  • {finding}")
