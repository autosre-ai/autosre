"""
Subagent Executor Node

Executes a single investigation subagent's ReAct loop.
Each subagent has access to domain-specific tools and runs
a reasoning + action loop to gather evidence.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Callable

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool

from ..config import (
    AgentConfig,
    build_llm,
    build_model_config,
    build_prompt_config,
)

logger = logging.getLogger(__name__)


SUBAGENT_SYSTEM_TEMPLATE = """You are the {agent_name} investigation agent for an AI SRE system.
Your role is to INVESTIGATE a production incident — gather evidence from your domain and report findings.

{custom_prompt}

## Investigation Context
Alert: {alert_summary}

## Service Topology (from Knowledge Graph)
{service_topology}

## Environment Context
{environment_context}

## Hypotheses to Test
{hypotheses}

## Available Tools
{tool_catalog}

## How to Work
1. Use the available tools to gather evidence from your domain
2. Investigate systematically — test each hypothesis with evidence
3. When done, provide a clear summary of your findings and confidence level

## Rules
- NEVER modify production resources — investigation is read-only
- Do NOT call the same tool with the same arguments twice
- Do NOT fabricate data — if a query returns nothing, report "no data found"
- If your domain has no relevant signals for this alert, say so and stop
- Do NOT suggest remediation actions — your job is investigation only
- Report WHAT you found (or didn't find), with evidence
"""


def make_subagent_executor() -> Callable[[dict], dict]:
    """Create the subagent executor function for use with Send() fan-out.
    
    Returns a function that executes a single subagent's investigation loop.
    This factory pattern allows the executor to be instantiated once and
    reused for all subagent invocations.
    """
    
    def subagent_executor(state: dict) -> dict:
        """Execute a single investigation subagent's ReAct loop.
        
        Receives Send() payload with agent_id and context.
        Returns agent_states update with findings.
        """
        agent_id = state.get("agent_id", "unknown")
        alert = state.get("alert", {})
        hypotheses = state.get("hypotheses", [])
        team_config_raw = state.get("team_config", {})
        max_react_loops = state.get(
            "max_react_loops",
            int(os.getenv("SUBAGENT_MAX_REACT_LOOPS", "25"))
        )
        
        logger.info(f"[SUBAGENT:{agent_id}] Starting investigation (max {max_react_loops} loops)")
        start_time = time.time()
        
        # Get agent config
        agents_config = team_config_raw.get("agents", {})
        investigation_config = agents_config.get("investigation", {})
        sub_agents_config = investigation_config.get("sub_agents_config", {})
        agent_raw_config = sub_agents_config.get(agent_id, agents_config.get(agent_id, {}))
        
        # Build agent config
        agent_config = AgentConfig(
            name=agent_id,
            prompt=build_prompt_config(agent_raw_config),
            model=build_model_config(agent_raw_config),
        )
        
        # Build tools for this agent
        tools = _get_tools_for_agent(agent_id, team_config_raw)
        tool_catalog = _format_tool_catalog(tools)
        
        # Build LLM with tool binding
        try:
            llm = build_llm(agent_config)
            if tools:
                llm_with_tools = llm.bind_tools(tools)
            else:
                llm_with_tools = llm
        except Exception as e:
            logger.error(f"[SUBAGENT:{agent_id}] Failed to build LLM: {e}")
            return _error_result(agent_id, f"Failed to initialize: {e}", start_time)
        
        # Build system prompt
        custom_prompt = agent_raw_config.get("prompt", {}).get("system", "")
        hypotheses_text = _format_hypotheses(hypotheses)
        
        kg_context_data = state.get("kg_context", {})
        from .kg_context import format_kg_for_agent
        service_topology = format_kg_for_agent(agent_id, kg_context_data)
        
        env_manifest = team_config_raw.get("environment_manifest", {})
        environment_context = _format_env_for_agent(agent_id, env_manifest)
        
        system_prompt = SUBAGENT_SYSTEM_TEMPLATE.format(
            agent_name=agent_id,
            custom_prompt=custom_prompt,
            alert_summary=json.dumps(alert, indent=2),
            service_topology=service_topology,
            environment_context=environment_context or "No environment manifest. Use discovery queries.",
            hypotheses=hypotheses_text,
            tool_catalog=tool_catalog or "No specialized tools available.",
        )
        
        # Run ReAct loop
        messages_list: list[Any] = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Begin your investigation of the alert. Agent: {agent_id}"),
        ]
        
        react_timeline: list[dict] = []
        tool_map = {t.name: t for t in tools} if tools else {}
        seen_calls: set[str] = set()  # Track (tool_name, args_hash) to prevent duplicates
        tool_call_count = 0
        
        agent_run_config = {"run_name": agent_id, "metadata": {"agent_id": agent_id}}
        
        for loop_idx in range(max_react_loops):
            try:
                response = llm_with_tools.invoke(messages_list, config=agent_run_config)
                messages_list.append(response)
                
                # Check for tool calls
                if hasattr(response, "tool_calls") and response.tool_calls:
                    for tool_call in response.tool_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]
                        
                        # Deduplication check
                        call_key = f"{tool_name}:{json.dumps(tool_args, sort_keys=True)}"
                        if call_key in seen_calls:
                            messages_list.append(ToolMessage(
                                content="DUPLICATE: You already called this tool with identical arguments.",
                                tool_call_id=tool_call["id"],
                            ))
                            react_timeline.append({
                                "loop": loop_idx,
                                "action": "duplicate_skipped",
                                "tool": tool_name,
                            })
                            continue
                        
                        seen_calls.add(call_key)
                        react_timeline.append({
                            "loop": loop_idx,
                            "action": "tool_call",
                            "tool": tool_name,
                            "args": {k: str(v)[:200] for k, v in tool_args.items()},
                        })
                        
                        # Execute tool
                        if tool_name in tool_map:
                            try:
                                tool_result = tool_map[tool_name].invoke(tool_args, config=agent_run_config)
                            except Exception as e:
                                tool_result = f"Error: {e}"
                        else:
                            tool_result = f"Unknown tool: {tool_name}"
                        
                        messages_list.append(ToolMessage(
                            content=str(tool_result)[:10000],
                            tool_call_id=tool_call["id"],
                        ))
                        
                        tool_call_count += 1
                    
                    # Reflection checkpoint every 5 tool calls
                    if tool_call_count > 0 and tool_call_count % 5 == 0:
                        messages_list.append(HumanMessage(
                            content=(
                                "REFLECTION CHECKPOINT: Before making more tool calls, assess:\n"
                                "1. What have you learned so far?\n"
                                "2. Which hypotheses can you confirm or eliminate?\n"
                                "3. What is the single most valuable next action?\n"
                                "4. Are you making progress or going in circles?\n"
                                "State your assessment concisely, then continue."
                            )
                        ))
                        logger.info(f"[SUBAGENT:{agent_id}] Reflection at {tool_call_count} tool calls")
                else:
                    # No tool calls — agent is done
                    react_timeline.append({"loop": loop_idx, "action": "final_response"})
                    break
                    
            except Exception as e:
                logger.error(f"[SUBAGENT:{agent_id}] Loop {loop_idx} error: {e}")
                react_timeline.append({"loop": loop_idx, "action": "error", "error": str(e)})
                break
        else:
            logger.warning(f"[SUBAGENT:{agent_id}] Hit max react loops ({max_react_loops})")
        
        hit_max_loops = loop_idx >= max_react_loops - 1
        
        # Extract final findings
        findings = _extract_findings(messages_list, llm, agent_run_config, hit_max_loops, agent_id)
        
        duration = time.time() - start_time
        logger.info(f"[SUBAGENT:{agent_id}] Completed in {duration:.1f}s, {len(react_timeline)} actions")
        
        return {
            "agent_states": {
                agent_id: {
                    "status": "completed",
                    "findings": findings,
                    "evidence": [e for e in react_timeline if e.get("action") == "tool_call"],
                    "confidence": 0.7,
                    "react_loops": len(react_timeline),
                    "duration_seconds": duration,
                }
            }
        }
    
    return subagent_executor


def _get_tools_for_agent(agent_id: str, team_config_raw: dict) -> list[BaseTool]:
    """Get the tools available for a specific agent.
    
    This is a placeholder that should be extended to load actual tools
    based on agent type and team configuration.
    """
    # TODO: Implement actual tool loading based on agent type
    # For now, return empty list - tools will be provided by skills
    return []


def _format_tool_catalog(tools: list[BaseTool]) -> str:
    """Format tools as a catalog string for the prompt."""
    if not tools:
        return ""
    
    lines = []
    for tool in tools:
        lines.append(f"- **{tool.name}**: {tool.description}")
    return "\n".join(lines)


def _format_hypotheses(hypotheses: list[dict]) -> str:
    """Format hypotheses for the prompt."""
    if not hypotheses:
        return "No specific hypotheses — investigate broadly."
    
    lines = []
    for h in hypotheses:
        if isinstance(h, dict):
            lines.append(f"- {h.get('hypothesis', str(h))}")
        else:
            lines.append(f"- {h}")
    return "\n".join(lines)


def _format_env_for_agent(agent_id: str, manifest: dict) -> str:
    """Format environment manifest for a specific agent type."""
    if not manifest:
        return ""
    
    agent_lower = agent_id.lower()
    lines = []
    
    if agent_lower in ("metrics", "observability"):
        m = manifest.get("metrics", {})
        if m:
            lines.append(f"Backend: {m.get('backend', 'unknown')}")
            if m.get("naming_convention"):
                lines.append(f"Naming: {m['naming_convention']}")
            km = m.get("key_metrics", {})
            if km:
                lines.append("Key metrics:")
                for purpose, metric in km.items():
                    lines.append(f"  {purpose}: {metric}")
    
    elif agent_lower in ("log_analysis", "logs"):
        lg = manifest.get("logs", {})
        if lg:
            lines.append(f"Backend: {lg.get('backend', 'unknown')}")
            lines.append(f"Index: {lg.get('index_pattern', 'unknown')}")
            fm = lg.get("field_mapping", {})
            if fm:
                lines.append("Field mapping:")
                for purpose, field in fm.items():
                    lines.append(f"  {purpose}: {field}")
    
    elif agent_lower in ("kubernetes", "k8s"):
        k = manifest.get("kubernetes", {})
        if k.get("namespace"):
            lines.append(f"Namespace: {k['namespace']}")
    
    return "\n".join(lines) if lines else ""


def _extract_findings(
    messages_list: list,
    llm: Any,
    run_config: dict,
    hit_max_loops: bool,
    agent_id: str,
) -> str:
    """Extract final findings from the message history."""
    findings = ""
    
    # Look for clean final response (no tool_calls)
    for msg in reversed(messages_list):
        if isinstance(msg, AIMessage) and msg.content and not getattr(msg, "tool_calls", None):
            findings = msg.content
            break
    
    # If hit max loops, generate forced summary
    if not findings and hit_max_loops:
        try:
            summary_msgs = messages_list + [HumanMessage(
                content=(
                    "You have reached the maximum investigation steps. "
                    "Based on all evidence gathered, provide a concise summary of:\n"
                    "1. What you found\n"
                    "2. The likely root cause\n"
                    "3. Your confidence level\n"
                    "Do NOT call any tools. Just summarize."
                )
            )]
            summary_response = llm.invoke(summary_msgs, config=run_config)
            if summary_response.content:
                findings = summary_response.content
                logger.info(f"[SUBAGENT:{agent_id}] Generated forced summary")
        except Exception as e:
            logger.warning(f"[SUBAGENT:{agent_id}] Forced summary failed: {e}")
    
    # Fallback: any AIMessage content
    if not findings:
        for msg in reversed(messages_list):
            if isinstance(msg, AIMessage) and msg.content:
                findings = msg.content
                break
    
    if not findings:
        findings = f"Agent {agent_id} completed investigation but did not produce a summary."
    
    return findings


def _error_result(agent_id: str, error_msg: str, start_time: float) -> dict:
    """Return an error result for the subagent."""
    return {
        "agent_states": {
            agent_id: {
                "status": "error",
                "findings": error_msg,
                "evidence": [],
                "confidence": 0.0,
                "react_loops": 0,
                "duration_seconds": time.time() - start_time,
            }
        }
    }
