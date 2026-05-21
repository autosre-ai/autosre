"""SRE Skills/Tools System.

This module provides infrastructure investigation tools for SRE agents:

- **kubernetes**: K8s cluster investigation (pods, deployments, services, events, nodes)
- **metrics**: Query Prometheus, Datadog, Grafana
- **logs**: Search Elasticsearch, Loki, tail log files
- **aws**: AWS infrastructure (EC2, RDS, CloudWatch, ECS)
- **traces**: Distributed tracing (Jaeger, Tempo)

Each skill module provides:
- A main class (e.g., KubernetesTools) with get_tools() method
- A convenience function (e.g., get_kubernetes_tools())
- Configuration dataclasses with from_env() class methods
- Mock mode support for testing

Usage:
    from src.agent.skills import get_all_tools, make_load_skill, make_run_script
    
    # Get all tools for an agent
    tools = get_all_tools(mock_mode=False)
    
    # Or get specific skill tools
    from src.agent.skills.kubernetes import get_kubernetes_tools
    k8s_tools = get_kubernetes_tools()
"""

import logging
import os
from pathlib import Path
from typing import Optional
import subprocess

from langchain_core.tools import BaseTool, tool

logger = logging.getLogger(__name__)

# Skill module imports
from .base import (
    BaseSRETool,
    ToolResult,
    SREToolError,
    TimeoutError,
    ConnectionError,
    AuthenticationError,
    sre_tool,
    with_timeout,
)

from .kubernetes import (
    KubernetesTools,
    KubernetesConfig,
    get_kubernetes_tools,
)

from .metrics import (
    MetricsTools,
    PrometheusConfig,
    DatadogConfig,
    GrafanaConfig,
    get_metrics_tools,
)

from .logs import (
    LogsTools,
    ElasticsearchConfig,
    LokiConfig,
    get_logs_tools,
)

from .aws import (
    AWSTools,
    AWSConfig,
    get_aws_tools,
)

from .traces import (
    TracesTools,
    JaegerConfig,
    TempoConfig,
    get_traces_tools,
)


# Default skills directory (for skill-based loading)
DEFAULT_SKILLS_DIR = os.getenv(
    "SKILLS_DIR",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), ".claude", "skills"),
)


def get_all_tools(
    mock_mode: bool = False,
    enabled_skills: Optional[set[str]] = None,
) -> list[BaseTool]:
    """Get all SRE investigation tools.
    
    Args:
        mock_mode: If True, tools return mock data instead of real API calls.
        enabled_skills: Set of skill names to enable. None enables all.
            Valid names: 'kubernetes', 'metrics', 'logs', 'aws', 'traces'
    
    Returns:
        List of LangChain BaseTool objects.
    """
    all_skills = {
        "kubernetes": get_kubernetes_tools,
        "metrics": get_metrics_tools,
        "logs": get_logs_tools,
        "aws": get_aws_tools,
        "traces": get_traces_tools,
    }
    
    tools = []
    for skill_name, get_tools_fn in all_skills.items():
        if enabled_skills is None or skill_name in enabled_skills:
            try:
                skill_tools = get_tools_fn(mock_mode=mock_mode)
                tools.extend(skill_tools)
                logger.debug(f"Loaded {len(skill_tools)} tools from {skill_name}")
            except Exception as e:
                logger.warning(f"Failed to load {skill_name} tools: {e}")
    
    logger.info(f"Loaded {len(tools)} total SRE tools")
    return tools


def _resolve_skill_dir(skill_name: str, skills_dir: str) -> Optional[Path]:
    """Find the skill directory by name (directory name or frontmatter name)."""
    import re
    
    skills_path = Path(skills_dir)
    if not skills_path.is_dir():
        return None
    
    # Direct directory match
    direct = skills_path / skill_name
    if direct.is_dir() and (direct / "SKILL.md").is_file():
        return direct
    
    # Search by frontmatter name
    for skill_dir in skills_path.iterdir():
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        try:
            text = skill_md.read_text(encoding="utf-8")
            match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
            if match:
                for line in match.group(1).splitlines():
                    if line.startswith("name:"):
                        fm_name = line.split(":", 1)[1].strip()
                        if fm_name == skill_name:
                            return skill_dir
        except Exception:
            continue
    
    return None


def make_load_skill(
    enabled_skills: Optional[set[str]] = None,
    skills_dir: str = DEFAULT_SKILLS_DIR,
):
    """Create a scoped load_skill tool that only loads allowed skills.
    
    This is used for SKILL.md-based skill loading (Claude SDK pattern).
    
    Args:
        enabled_skills: Set of allowed skill names, or None for all skills.
        skills_dir: Path to skills directory.
        
    Returns:
        LangChain tool for loading skill documentation.
    """
    @tool
    def load_skill(skill_name: str) -> str:
        """Load a skill's SKILL.md documentation to learn its methodology and available scripts.

        Use this tool to learn about a skill before running its scripts.
        Returns the full SKILL.md content with methodology, scripts list, and usage examples.

        Args:
            skill_name: Name of the skill to load (e.g., 'infrastructure-kubernetes').
        """
        # Check if skill is allowed
        if enabled_skills is not None and skill_name not in enabled_skills:
            return f"Error: Skill '{skill_name}' is not enabled for this agent."

        skill_dir = _resolve_skill_dir(skill_name, skills_dir)
        if not skill_dir:
            return f"Error: Skill '{skill_name}' not found in {skills_dir}."

        skill_md = skill_dir / "SKILL.md"
        try:
            content = skill_md.read_text(encoding="utf-8")
            # List available scripts
            scripts_dir = skill_dir / "scripts"
            scripts = []
            if scripts_dir.is_dir():
                scripts = sorted(f.name for f in scripts_dir.iterdir() if f.is_file())

            if scripts:
                content += "\n\n## Available Scripts\n"
                for s in scripts:
                    content += f"- `{scripts_dir / s}`\n"

            return content
        except Exception as e:
            return f"Error loading skill '{skill_name}': {e}"

    return load_skill


def make_run_script(
    enabled_skills: Optional[set[str]] = None,
    skills_dir: str = DEFAULT_SKILLS_DIR,
):
    """Create a scoped run_script tool that only runs scripts from allowed skills.
    
    This is used for executing skill scripts (Claude SDK pattern).
    
    Args:
        enabled_skills: Set of allowed skill names, or None for all skills.
        skills_dir: Path to skills directory.
        
    Returns:
        LangChain tool for running skill scripts.
    """
    import re
    import shutil
    
    @tool
    def run_script(command: str, timeout: int = 120) -> str:
        """Execute a skill script or shell command and return its output.

        Use this to run skill scripts (Python/Bash) that interact with infrastructure,
        APIs, and monitoring systems. Scripts are located in skill directories under
        .claude/skills/{skill-name}/scripts/.

        Args:
            command: The full command to execute (e.g., 'python .claude/skills/infrastructure-kubernetes/scripts/list_pods.py -n default').
            timeout: Maximum execution time in seconds (default 120).
        """
        # Validate the command references an allowed skill if it's a skill script
        skills_path = Path(skills_dir)
        if str(skills_path) in command or ".claude/skills/" in command:
            # Extract skill directory name from command
            match = re.search(r"\.claude/skills/([^/]+)/", command)
            if match:
                skill_dir_name = match.group(1)
                # Check if this skill is allowed
                if enabled_skills is not None:
                    skill_dir = _resolve_skill_dir(skill_dir_name, skills_dir)
                    if skill_dir is None:
                        return f"Error: Skill '{skill_dir_name}' not found."
                    
                    # Check against enabled set
                    skill_md = skill_dir / "SKILL.md"
                    fm_name = skill_dir_name
                    try:
                        text = skill_md.read_text(encoding="utf-8")
                        fm_match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
                        if fm_match:
                            for line in fm_match.group(1).splitlines():
                                if line.startswith("name:"):
                                    fm_name = line.split(":", 1)[1].strip()
                                    break
                    except Exception:
                        pass
                    
                    if fm_name not in enabled_skills and skill_dir_name not in enabled_skills:
                        return f"Error: Skill '{skill_dir_name}' is not enabled for this agent."

        try:
            # Determine cwd
            cwd = None
            skills_path_obj = Path(skills_dir)
            if skills_path_obj.is_dir():
                for parent in [skills_path_obj] + list(skills_path_obj.parents):
                    if parent.name == ".claude":
                        cwd = str(parent.parent)
                        break
                if cwd is None:
                    cwd = str(skills_path_obj.parent.parent)

            # Fix "python" → "python3"
            actual_command = command
            if (command.startswith("python ") or " python " in command) and not shutil.which("python"):
                actual_command = command.replace("python ", "python3 ", 1)

            result = subprocess.run(
                actual_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
            )
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}" if output else result.stderr
            if result.returncode != 0:
                output += f"\n[exit code: {result.returncode}]"
            return output if output else "(no output)"
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {timeout} seconds."
        except Exception as e:
            return f"Error executing command: {e}"

    return run_script


def resolve_tools(
    agent_name: str,
    enabled_skills: Optional[set[str]] = None,
    skills_dir: str = DEFAULT_SKILLS_DIR,
    mock_mode: bool = False,
    include_native_tools: bool = True,
) -> list[BaseTool]:
    """Build the tool list for an agent based on configuration.
    
    This combines:
    1. Native Python tools (get_all_tools)
    2. Skill-based tools (load_skill + run_script) if skills_dir exists
    
    Args:
        agent_name: Agent identifier (for logging).
        enabled_skills: Set of allowed skill names for this agent, or None for all.
        skills_dir: Path to skills directory.
        mock_mode: If True, return mock data from native tools.
        include_native_tools: If True, include Python-based SRE tools.
        
    Returns:
        List of LangChain BaseTool objects.
    """
    tools: list[BaseTool] = []
    
    # Add native Python tools
    if include_native_tools:
        native_tools = get_all_tools(mock_mode=mock_mode, enabled_skills=enabled_skills)
        tools.extend(native_tools)
    
    # Add skill-based tools if skills directory exists
    if Path(skills_dir).is_dir():
        load_skill = make_load_skill(enabled_skills, skills_dir)
        run_script = make_run_script(enabled_skills, skills_dir)
        tools.append(load_skill)
        tools.append(run_script)
    
    logger.info(
        f"[TOOLS] Resolved {len(tools)} tools for agent '{agent_name}' "
        f"(skills: {'all' if enabled_skills is None else len(enabled_skills)})"
    )
    
    return tools


def get_skill_catalog(
    enabled_skills: Optional[set[str]] = None,
) -> str:
    """Build a text catalog of available native skills for system prompts.
    
    Args:
        enabled_skills: Set of allowed skill names, or None for all.
        
    Returns:
        Markdown-formatted skill catalog string.
    """
    all_skills = {
        "kubernetes": "Kubernetes cluster investigation - pods, deployments, services, events, nodes",
        "metrics": "Query metrics from Prometheus, Datadog, Grafana",
        "logs": "Search logs in Elasticsearch, Loki, or tail log files",
        "aws": "AWS infrastructure - EC2, RDS, CloudWatch, ECS",
        "traces": "Distributed tracing - Jaeger, Tempo",
    }
    
    lines = [
        "## Available SRE Skills\n",
        "These tools are available for infrastructure investigation:\n",
    ]
    
    for skill_name, description in all_skills.items():
        if enabled_skills is None or skill_name in enabled_skills:
            lines.append(f"- **{skill_name}**: {description}")
    
    return "\n".join(lines)


# Export all public symbols
__all__ = [
    # Base classes
    "BaseSRETool",
    "ToolResult",
    "SREToolError",
    "TimeoutError",
    "ConnectionError",
    "AuthenticationError",
    "sre_tool",
    "with_timeout",
    # Kubernetes
    "KubernetesTools",
    "KubernetesConfig",
    "get_kubernetes_tools",
    # Metrics
    "MetricsTools",
    "PrometheusConfig",
    "DatadogConfig",
    "GrafanaConfig",
    "get_metrics_tools",
    # Logs
    "LogsTools",
    "ElasticsearchConfig",
    "LokiConfig",
    "get_logs_tools",
    # AWS
    "AWSTools",
    "AWSConfig",
    "get_aws_tools",
    # Traces
    "TracesTools",
    "JaegerConfig",
    "TempoConfig",
    "get_traces_tools",
    # Top-level functions
    "get_all_tools",
    "resolve_tools",
    "make_load_skill",
    "make_run_script",
    "get_skill_catalog",
]
