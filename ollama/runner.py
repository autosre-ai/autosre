#!/usr/bin/env python3
"""
OpenSRE Ollama Runner

Usage:
    opensre-ollama "investigate high latency on payment-service"
    opensre-ollama --watch  # continuous incident monitoring
    
Requires: ollama, opensre model
Build model: ollama create opensre -f ollama/Modelfile
"""

import json
import re
import subprocess
import sys
from typing import Any

# Tool implementations
class Tools:
    def __init__(self, prometheus_url: str = "http://localhost:9090", 
                 kubeconfig: str | None = None):
        self.prometheus_url = prometheus_url
        self.kubeconfig = kubeconfig
    
    def prometheus(self, query: str, duration: str = "1h") -> dict:
        """Execute PromQL query."""
        import httpx
        try:
            r = httpx.get(
                f"{self.prometheus_url}/api/v1/query",
                params={"query": query},
                timeout=10
            )
            return r.json()
        except Exception as e:
            return {"error": str(e)}
    
    def kubernetes(self, action: str, namespace: str, resource: str = "pods",
                   name: str | None = None, tail: int = 100) -> dict:
        """Execute kubectl command."""
        cmd = ["kubectl", action, resource, "-n", namespace]
        if name:
            cmd.append(name)
        if action == "logs" and tail:
            cmd.extend(["--tail", str(tail)])
        cmd.append("-o=json" if action in ["get", "describe"] else "")
        
        try:
            result = subprocess.run(
                [c for c in cmd if c],  # filter empty strings
                capture_output=True, text=True, timeout=30
            )
            if action in ["get"]:
                return json.loads(result.stdout)
            return {"output": result.stdout, "stderr": result.stderr}
        except Exception as e:
            return {"error": str(e)}
    
    def logs(self, service: str, query: str = "", duration: str = "30m",
             level: str = "error") -> dict:
        """Search logs (placeholder - integrate with your logging system)."""
        # Could integrate with: Loki, Elasticsearch, CloudWatch, etc.
        return {
            "message": f"Log search for {service}: query='{query}' level={level}",
            "entries": []  # Would contain actual log entries
        }
    
    def runbook(self, query: str = "", alert: str = "") -> dict:
        """Lookup runbook (placeholder - integrate with your runbook system)."""
        return {
            "message": f"Runbook lookup: alert={alert} query={query}",
            "runbook": None  # Would contain runbook content
        }
    
    def remediate(self, action: str, target: str, params: dict = None) -> dict:
        """Execute remediation - ALWAYS REQUIRES CONFIRMATION."""
        return {
            "status": "pending_approval",
            "action": action,
            "target": target,
            "params": params,
            "message": f"⚠️  Remediation requires approval: {action} {target}"
        }
    
    def execute(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool by name."""
        if not hasattr(self, tool_name):
            return {"error": f"Unknown tool: {tool_name}"}
        return getattr(self, tool_name)(**arguments)


def parse_tool_calls(response: str) -> list[dict]:
    """Extract tool calls from model response."""
    pattern = r'<tool_call>\s*({.*?})\s*</tool_call>'
    matches = re.findall(pattern, response, re.DOTALL)
    calls = []
    for match in matches:
        try:
            calls.append(json.loads(match))
        except json.JSONDecodeError:
            pass
    return calls


def run_opensre(prompt: str, model: str = "opensre", max_turns: int = 5):
    """Run OpenSRE investigation loop."""
    tools = Tools()
    messages = [{"role": "user", "content": prompt}]
    
    for turn in range(max_turns):
        # Call Ollama
        result = subprocess.run(
            ["ollama", "run", model, json.dumps(messages[-1]["content"])],
            capture_output=True, text=True
        )
        response = result.stdout
        
        print(f"\n{'='*60}")
        print(f"🤖 OpenSRE (turn {turn + 1}):")
        print(response)
        
        # Check for tool calls
        tool_calls = parse_tool_calls(response)
        
        if not tool_calls:
            # No more tool calls, investigation complete
            break
        
        # Execute tools and add results
        tool_results = []
        for call in tool_calls:
            print(f"\n🔧 Executing: {call['name']}({call.get('arguments', {})})")
            result = tools.execute(call["name"], call.get("arguments", {}))
            tool_results.append({
                "tool": call["name"],
                "result": result
            })
            print(f"   Result: {json.dumps(result, indent=2)[:500]}...")
        
        # Add tool results to conversation
        messages.append({"role": "assistant", "content": response})
        messages.append({
            "role": "user", 
            "content": f"Tool results:\n{json.dumps(tool_results, indent=2)}"
        })
    
    print("\n" + "="*60)
    print("✅ Investigation complete")


def main():
    if len(sys.argv) < 2:
        print("Usage: opensre-ollama 'describe the incident'")
        print("       opensre-ollama --build  # build the model first")
        sys.exit(1)
    
    if sys.argv[1] == "--build":
        print("Building OpenSRE Ollama model...")
        subprocess.run([
            "ollama", "create", "opensre", 
            "-f", "ollama/Modelfile"
        ])
        print("✅ Model built! Run with: ollama run opensre")
        return
    
    prompt = " ".join(sys.argv[1:])
    run_opensre(prompt)


if __name__ == "__main__":
    main()
