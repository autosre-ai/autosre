"""
Logs Subagent — Investigates using log search.

Skills:
- search_logs: Search logs with patterns
- tail_logs: Tail recent logs
- grep_errors: Find error patterns
"""

import asyncio
import logging
import subprocess
from typing import Any, Optional

from .base import BaseSubagent, Skill

logger = logging.getLogger(__name__)


class LocalLogSkill(Skill):
    """Base skill for local log commands."""
    
    log_dir: str = "/var/log"
    
    async def run_cmd(self, cmd: list[str], timeout: int = 30) -> str:
        """Run a shell command."""
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )
            
            output = result.stdout
            if result.returncode != 0 and result.stderr:
                output += f"\nStderr: {result.stderr}"
            
            return output or "No output"
            
        except subprocess.TimeoutExpired:
            return "Error: Command timed out"
        except FileNotFoundError:
            return f"Error: Command not found: {cmd[0]}"
        except Exception as e:
            return f"Error: {e}"


class SearchLogsSkill(LocalLogSkill):
    """Search logs for patterns."""
    
    name: str = "search_logs"
    description: str = "Search log files for patterns using grep. Good for finding specific errors."
    parameters: dict[str, Any] = {
        "pattern": {"type": "string", "description": "Search pattern (regex supported)"},
        "file": {"type": "string", "description": "Log file path or glob (e.g., '/var/log/app/*.log')"},
        "context_lines": {"type": "integer", "description": "Lines of context (default: 3)"},
        "case_insensitive": {"type": "boolean", "description": "Case insensitive search"},
    }
    
    async def execute(
        self,
        pattern: str,
        file: str = "",
        context_lines: int = 3,
        case_insensitive: bool = True,
        **kwargs: Any,
    ) -> str:
        cmd = ["grep"]
        
        if case_insensitive:
            cmd.append("-i")
        
        cmd.extend(["-C", str(context_lines)])
        cmd.append(pattern)
        
        if file:
            cmd.append(file)
        else:
            cmd.append(f"{self.log_dir}/*.log")
        
        return await self.run_cmd(cmd)


class TailLogsSkill(LocalLogSkill):
    """Tail recent log entries."""
    
    name: str = "tail_logs"
    description: str = "Get the most recent log entries from a file."
    parameters: dict[str, Any] = {
        "file": {"type": "string", "description": "Log file path"},
        "lines": {"type": "integer", "description": "Number of lines (default: 100)"},
    }
    
    async def execute(
        self,
        file: str,
        lines: int = 100,
        **kwargs: Any,
    ) -> str:
        cmd = ["tail", "-n", str(lines), file]
        return await self.run_cmd(cmd)


class GrepErrorsSkill(LocalLogSkill):
    """Find error patterns in logs."""
    
    name: str = "grep_errors"
    description: str = "Search for common error patterns (ERROR, Exception, FATAL, panic)."
    parameters: dict[str, Any] = {
        "file": {"type": "string", "description": "Log file path or glob"},
        "lines": {"type": "integer", "description": "Max lines to return (default: 50)"},
    }
    
    async def execute(
        self,
        file: str,
        lines: int = 50,
        **kwargs: Any,
    ) -> str:
        # Search for common error patterns
        patterns = [
            "ERROR",
            "Exception",
            "FATAL",
            "panic",
            "fail",
            "timeout",
            "refused",
            "OOM",
        ]
        
        pattern = "|".join(patterns)
        cmd = ["grep", "-E", "-i", pattern, file]
        
        result = await self.run_cmd(cmd)
        
        # Limit output
        result_lines = result.split("\n")
        if len(result_lines) > lines:
            return "\n".join(result_lines[:lines]) + f"\n... ({len(result_lines) - lines} more lines)"
        
        return result


class JournalctlSkill(LocalLogSkill):
    """Search systemd journal logs."""
    
    name: str = "journalctl"
    description: str = "Search systemd journal for service logs (Linux only)."
    parameters: dict[str, Any] = {
        "unit": {"type": "string", "description": "Systemd unit name (e.g., 'nginx', 'docker')"},
        "since": {"type": "string", "description": "Time filter (e.g., '5 minutes ago', '1 hour ago')"},
        "priority": {"type": "string", "description": "Log priority (emerg, alert, crit, err, warning)"},
        "lines": {"type": "integer", "description": "Number of lines (default: 100)"},
    }
    
    async def execute(
        self,
        unit: str = "",
        since: str = "5 minutes ago",
        priority: str = "",
        lines: int = 100,
        **kwargs: Any,
    ) -> str:
        cmd = ["journalctl", "--no-pager", "-n", str(lines)]
        
        if unit:
            cmd.extend(["-u", unit])
        
        if since:
            cmd.extend(["--since", since])
        
        if priority:
            cmd.extend(["-p", priority])
        
        return await self.run_cmd(cmd)


class LokiSearchSkill(Skill):
    """Search Grafana Loki logs."""
    
    name: str = "loki_search"
    description: str = "Search logs in Grafana Loki using LogQL."
    parameters: dict[str, Any] = {
        "query": {"type": "string", "description": "LogQL query (e.g., '{job=\"nginx\"} |= \"error\"')"},
        "limit": {"type": "integer", "description": "Max entries (default: 100)"},
    }
    
    loki_url: str = "http://localhost:3100"
    
    async def execute(
        self,
        query: str,
        limit: int = 100,
        **kwargs: Any,
    ) -> str:
        try:
            import httpx
        except ImportError:
            return "Error: httpx not installed"
        
        url = f"{self.loki_url}/loki/api/v1/query_range"
        
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        start = now - timedelta(hours=1)
        
        params = {
            "query": query,
            "limit": limit,
            "start": int(start.timestamp() * 1e9),
            "end": int(now.timestamp() * 1e9),
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                if data.get("status") != "success":
                    return f"Error: {data.get('error', 'Unknown error')}"
                
                results = data.get("data", {}).get("result", [])
                if not results:
                    return "No logs found"
                
                # Format results
                lines = []
                for stream in results:
                    labels = stream.get("stream", {})
                    entries = stream.get("values", [])
                    
                    for ts, line in entries[:limit]:
                        lines.append(line)
                
                return "\n".join(lines[:limit]) or "No logs found"
                
        except Exception as e:
            return f"Error: {e}"


class LogsSubagent(BaseSubagent):
    """Log investigation subagent."""
    
    name = "logs"
    description = "Investigates using log search: grep, tail, journalctl, Loki"
    custom_prompt = """You are an expert at log analysis and troubleshooting.

Investigation approach:
1. Start with recent errors: grep for ERROR, Exception, FATAL
2. Look for patterns: repeated errors, timeouts, connection failures
3. Check timestamps: correlate with incident start time
4. Follow the trace: find related log entries using request IDs
5. Check dependent services: look for upstream/downstream errors

Common patterns to search:
- Connection refused / timeout
- OOM / Out of memory
- Stack traces and exceptions
- Authentication failures
- Rate limiting / throttling
- DNS resolution failures

Focus on:
- First occurrence of errors (root cause often appears first)
- Patterns that changed recently
- Correlation with deployments or config changes"""
    
    def __init__(
        self,
        log_dir: str = "/var/log",
        loki_url: str = "http://localhost:3100",
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.log_dir = log_dir
        self.loki_url = loki_url
    
    def get_skills(self) -> list[Skill]:
        """Return available log skills."""
        skills = [
            SearchLogsSkill(log_dir=self.log_dir),
            TailLogsSkill(log_dir=self.log_dir),
            GrepErrorsSkill(log_dir=self.log_dir),
            JournalctlSkill(log_dir=self.log_dir),
            LokiSearchSkill(loki_url=self.loki_url),
        ]
        return skills
