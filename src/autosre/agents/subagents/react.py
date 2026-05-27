"""
ReAct Loop — Reason + Act loop for subagent execution.

This implements the ReAct pattern where the LLM alternates between:
1. Think - Decide what to investigate next
2. Act - Execute a tool
3. Observe - Process the result
4. Repeat until done or max iterations

Key features:
- Tool call deduplication (don't repeat same tool+args)
- Reflection checkpoints (every 5 iterations)
- Early exit (no findings after attempts)
- Forced summarization (after max iterations)
- Context management (trim old messages)
- Error recovery (retry once or move on)
"""

import hashlib
import json
import logging
import time
from typing import Any, Callable, Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# ----- LLM Protocol -----

class LLMProtocol(Protocol):
    """Protocol for LLM clients."""
    
    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> Any:
        """Generate completion for a prompt."""
        ...


# ----- Tool Call Models -----

class ToolCall(BaseModel):
    """A tool call decided by the LLM."""
    
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    reasoning: str = ""  # Why this tool?


class ToolResult(BaseModel):
    """Result of executing a tool."""
    
    success: bool = True
    output: str = ""
    duration_ms: int = 0
    error: Optional[str] = None


class Tool(BaseModel):
    """A tool available to the subagent."""
    
    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    
    # The actual callable - not serialized
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    _executor: Optional[Callable[..., str]] = None
    
    def set_executor(self, executor: Callable[..., str]) -> None:
        """Set the tool executor function."""
        object.__setattr__(self, "_executor", executor)
    
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool and return result."""
        start = time.time()
        try:
            if self._executor is None:
                return ToolResult(
                    success=False,
                    error=f"Tool {self.name} has no executor",
                    duration_ms=0,
                )
            
            # Handle both sync and async executors
            result = self._executor(**kwargs)
            if hasattr(result, "__await__"):
                result = await result
            
            duration_ms = int((time.time() - start) * 1000)
            return ToolResult(
                success=True,
                output=str(result),
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            logger.error(f"Tool {self.name} failed: {e}")
            return ToolResult(
                success=False,
                output="",
                duration_ms=duration_ms,
                error=str(e),
            )
    
    def to_schema(self) -> dict[str, Any]:
        """Return JSON schema for this tool."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters or {"type": "object", "properties": {}},
        }


# ----- ReAct Message Types -----

class Message(BaseModel):
    """A message in the ReAct conversation."""
    
    role: str  # "system", "user", "assistant", "tool"
    content: str
    tool_call: Optional[ToolCall] = None
    tool_result: Optional[ToolResult] = None
    
    def token_estimate(self) -> int:
        """Rough token estimate for context management."""
        return len(self.content) // 4


# ----- ReAct Configuration -----

class ReactConfig(BaseModel):
    """Configuration for the ReAct loop."""
    
    max_iterations: int = 15
    reflection_interval: int = 5
    max_context_tokens: int = 100000
    max_no_findings_attempts: int = 3
    tool_retry_count: int = 1
    temperature: float = 0.0
    max_output_tokens: int = 4096


# ----- ReAct Loop Decision -----

class ReactDecision(BaseModel):
    """LLM's decision about next action."""
    
    action: str  # "tool_call", "finish", "reflect"
    tool_call: Optional[ToolCall] = None
    summary: Optional[str] = None  # If finishing
    confidence: float = 0.0


# ----- Evidence Model -----

class Evidence(BaseModel):
    """Evidence gathered during investigation."""
    
    source: str
    skill: str
    query: str = ""
    result: str = ""
    relevance: float = 0.5


# ----- Result Model -----

class SubagentResult(BaseModel):
    """Result from a subagent investigation."""
    
    agent_id: str
    status: str = "completed"  # "completed", "failed", "timeout"
    findings: str = ""
    evidence: list[Evidence] = Field(default_factory=list)
    duration_seconds: float = 0.0
    react_loops: int = 0
    error: Optional[str] = None


REACT_SYSTEM_PROMPT = """You are investigating: {hypothesis}

## Alert Context
{alert_context}

## Service Context
{service_context}

## Available Tools
{tool_list}

## Investigation Rules
1. NEVER repeat the same tool call with the same arguments - you will be told if you already called it
2. If no relevant findings after {max_no_findings} tool calls, summarize and exit
3. Quote evidence exactly: [SOURCE] at [TIMESTAMP]: "exact quote"
4. Maximum {max_iterations} tool calls per investigation
5. After each tool result, briefly analyze what you learned
6. Be systematic - test one thing at a time

## Response Format
Respond with JSON in this format:

For tool calls:
{{"action": "tool_call", "tool_call": {{"name": "tool_name", "arguments": {{}}, "reasoning": "why this tool"}}}}

When finished:
{{"action": "finish", "summary": "Your findings summary", "confidence": 0.8}}

For reflection:
{{"action": "reflect", "summary": "What I've learned so far and what to investigate next"}}

Always include a brief reasoning before the JSON explaining your thinking."""

REFLECTION_PROMPT = """## Reflection Checkpoint

You've made {tool_calls} tool calls so far. Before continuing, assess:

1. **What have you learned?** Key findings so far
2. **Which hypotheses can you confirm or eliminate?** Based on evidence
3. **What is the single most valuable next action?** Prioritize
4. **Are you making progress or going in circles?** Be honest

After reflection, continue investigating or finish if you have enough evidence.

Remember: Quality over quantity. Don't make tool calls just to fill the iteration limit."""

FORCED_SUMMARY_PROMPT = """## Maximum Iterations Reached

You have reached the maximum number of tool calls ({max_iterations}).

Based on ALL the evidence gathered above, provide a final summary:

1. **Key Findings**: What did you discover? Quote specific evidence.
2. **Likely Root Cause**: Based on evidence, what's the most likely cause?
3. **Confidence Level**: 0.0-1.0 with reasoning
4. **Gaps**: What couldn't you verify?

DO NOT call any tools. Just provide your summary as JSON:
{{"action": "finish", "summary": "...", "confidence": 0.X}}"""


# ----- Tool Call Deduplication -----

def hash_tool_call(name: str, args: dict[str, Any]) -> str:
    """Create a hash for tool call deduplication."""
    # Sort keys for consistent hashing
    args_str = json.dumps(args, sort_keys=True, default=str)
    return hashlib.sha256(f"{name}:{args_str}".encode()).hexdigest()[:16]


# ----- Context Management -----

def estimate_context_size(messages: list[Message]) -> int:
    """Estimate total token count of messages."""
    return sum(msg.token_estimate() for msg in messages)


def trim_old_messages(
    messages: list[Message],
    max_tokens: int,
    keep_system: bool = True,
    keep_recent: int = 10,
) -> list[Message]:
    """Trim old messages to fit within token budget.
    
    Keeps:
    - System message (if keep_system)
    - Last N messages (keep_recent)
    - Trims from the middle
    """
    if estimate_context_size(messages) <= max_tokens:
        return messages
    
    # Separate system message
    system_msgs = [m for m in messages if m.role == "system"] if keep_system else []
    other_msgs = [m for m in messages if m.role != "system"]
    
    # Keep recent messages
    if len(other_msgs) <= keep_recent:
        return system_msgs + other_msgs
    
    recent = other_msgs[-keep_recent:]
    
    # Add a summary of trimmed messages
    trimmed_count = len(other_msgs) - keep_recent
    summary_msg = Message(
        role="system",
        content=f"[Note: {trimmed_count} earlier messages trimmed to manage context length. Key evidence should be repeated in recent messages.]",
    )
    
    return system_msgs + [summary_msg] + recent


# ----- Main ReAct Loop -----

async def react_loop(
    hypothesis: str,
    tools: list[Tool],
    alert: dict[str, Any],
    service_context: str = "",
    llm: Optional[LLMProtocol] = None,
    config: Optional[ReactConfig] = None,
    agent_id: str = "unknown",
) -> SubagentResult:
    """Run the ReAct loop for investigation.
    
    Args:
        hypothesis: The hypothesis being tested
        tools: List of available tools
        alert: Alert being investigated
        service_context: Service topology/context info
        llm: LLM client
        config: ReAct configuration
        agent_id: Identifier for this subagent
        
    Returns:
        SubagentResult with findings and evidence
    """
    config = config or ReactConfig()
    
    if llm is None:
        return SubagentResult(
            agent_id=agent_id,
            status="failed",
            findings="No LLM client provided",
            error="No LLM client",
        )
    
    start_time = time.time()
    
    # Build tool map and schema
    tool_map = {t.name: t for t in tools}
    tool_list = "\n".join(
        f"- **{t.name}**: {t.description}"
        for t in tools
    )
    
    # Build system prompt
    alert_context = json.dumps(alert, indent=2, default=str)
    
    system_prompt = REACT_SYSTEM_PROMPT.format(
        hypothesis=hypothesis,
        alert_context=alert_context,
        service_context=service_context or "No service context available",
        tool_list=tool_list,
        max_no_findings=config.max_no_findings_attempts,
        max_iterations=config.max_iterations,
    )
    
    # Initialize message history
    messages: list[Message] = [
        Message(role="system", content=system_prompt),
        Message(role="user", content=f"Begin investigating: {hypothesis}"),
    ]
    
    # Track state
    seen_calls: set[str] = set()
    evidence: list[Evidence] = []
    tool_call_count = 0
    no_findings_count = 0
    last_error: Optional[str] = None
    
    logger.info(f"[{agent_id}] Starting ReAct loop for: {hypothesis[:50]}...")
    
    for iteration in range(config.max_iterations):
        # Check context size and trim if needed
        messages = trim_old_messages(
            messages,
            config.max_context_tokens,
            keep_system=True,
            keep_recent=15,
        )
        
        # Reflection checkpoint every N tool calls
        if tool_call_count > 0 and tool_call_count % config.reflection_interval == 0:
            messages.append(Message(
                role="user",
                content=REFLECTION_PROMPT.format(tool_calls=tool_call_count),
            ))
            logger.info(f"[{agent_id}] Reflection checkpoint at {tool_call_count} tool calls")
        
        # Build prompt for LLM
        prompt = "\n\n".join(
            f"[{msg.role.upper()}]\n{msg.content}"
            for msg in messages
            if msg.role != "system"
        )
        
        try:
            # Support both system= and system_prompt= patterns
            response = await llm.complete(
                prompt=prompt,
                system=system_prompt,
                system_prompt=system_prompt,
                temperature=config.temperature,
                max_tokens=config.max_output_tokens,
            )
            
            # Extract content from response
            if hasattr(response, "content"):
                content = response.content
            else:
                content = str(response)
            
            # Parse decision from response
            decision = _parse_decision(content)
            
            if decision is None:
                logger.warning(f"[{agent_id}] Could not parse decision, retrying...")
                messages.append(Message(
                    role="assistant",
                    content=content,
                ))
                messages.append(Message(
                    role="user",
                    content="Please respond with valid JSON in the required format.",
                ))
                continue
            
            # Handle decision
            if decision.action == "finish":
                logger.info(f"[{agent_id}] Finishing with confidence {decision.confidence:.2f}")
                
                return SubagentResult(
                    agent_id=agent_id,
                    status="completed",
                    findings=decision.summary or "No findings",
                    evidence=evidence,
                    duration_seconds=time.time() - start_time,
                    react_loops=iteration + 1,
                )
            
            elif decision.action == "reflect":
                # Add reflection to history and continue
                messages.append(Message(
                    role="assistant",
                    content=content,
                ))
                continue
            
            elif decision.action == "tool_call" and decision.tool_call:
                tool_call = decision.tool_call
                
                # Check for duplicate
                call_hash = hash_tool_call(tool_call.name, tool_call.arguments)
                if call_hash in seen_calls:
                    logger.info(f"[{agent_id}] Duplicate call skipped: {tool_call.name}")
                    messages.append(Message(
                        role="assistant",
                        content=content,
                    ))
                    messages.append(Message(
                        role="tool",
                        content=f"DUPLICATE: You already called {tool_call.name} with these exact arguments. Use the previous result.",
                        tool_call=tool_call,
                    ))
                    continue
                
                seen_calls.add(call_hash)
                
                # Check if tool exists
                if tool_call.name not in tool_map:
                    messages.append(Message(
                        role="assistant",
                        content=content,
                    ))
                    messages.append(Message(
                        role="tool",
                        content=f"ERROR: Unknown tool '{tool_call.name}'. Available: {', '.join(tool_map.keys())}",
                        tool_call=tool_call,
                    ))
                    continue
                
                # Execute tool
                tool = tool_map[tool_call.name]
                logger.info(f"[{agent_id}] Executing: {tool_call.name}({json.dumps(tool_call.arguments)[:100]})")
                
                result = await tool.execute(**tool_call.arguments)
                tool_call_count += 1
                
                # Handle errors with retry
                if not result.success and config.tool_retry_count > 0:
                    logger.warning(f"[{agent_id}] Tool failed, retrying: {result.error}")
                    result = await tool.execute(**tool_call.arguments)
                
                # Add to messages
                messages.append(Message(
                    role="assistant",
                    content=content,
                ))
                
                if result.success:
                    # Check if result has meaningful content
                    if _is_empty_result(result.output):
                        no_findings_count += 1
                        result_content = f"[No data found]\n{result.output}"
                    else:
                        no_findings_count = 0  # Reset on finding something
                        result_content = result.output
                    
                    messages.append(Message(
                        role="tool",
                        content=f"Tool: {tool_call.name}\nDuration: {result.duration_ms}ms\n\nResult:\n{result_content[:8000]}",
                        tool_call=tool_call,
                        tool_result=result,
                    ))
                    
                    # Record evidence
                    evidence.append(Evidence(
                        source=agent_id,
                        skill=tool_call.name,
                        query=json.dumps(tool_call.arguments),
                        result=result.output[:5000],
                        relevance=0.5 if _is_empty_result(result.output) else 0.7,
                    ))
                else:
                    messages.append(Message(
                        role="tool",
                        content=f"Tool: {tool_call.name}\nERROR: {result.error}",
                        tool_call=tool_call,
                        tool_result=result,
                    ))
                    last_error = result.error
                
                # Check for early exit (no findings)
                if no_findings_count >= config.max_no_findings_attempts:
                    logger.info(f"[{agent_id}] Early exit: no findings after {no_findings_count} attempts")
                    messages.append(Message(
                        role="user",
                        content=f"You've made {no_findings_count} tool calls with no relevant findings. Please summarize what you attempted and conclude.",
                    ))
            
            else:
                # Unknown action
                messages.append(Message(
                    role="assistant",
                    content=content,
                ))
                messages.append(Message(
                    role="user",
                    content=f"Unknown action: {decision.action}. Use 'tool_call', 'finish', or 'reflect'.",
                ))
        
        except Exception as e:
            logger.error(f"[{agent_id}] ReAct iteration {iteration} error: {e}")
            last_error = str(e)
            # Continue to next iteration
    
    # Max iterations reached - force summarization
    logger.warning(f"[{agent_id}] Max iterations ({config.max_iterations}) reached, forcing summary")
    
    summary = await _force_summarization(
        messages=messages,
        llm=llm,
        config=config,
        agent_id=agent_id,
    )
    
    return SubagentResult(
        agent_id=agent_id,
        status="completed",
        findings=summary,
        evidence=evidence,
        duration_seconds=time.time() - start_time,
        react_loops=config.max_iterations,
        error=last_error,
    )


def _parse_decision(content: str) -> Optional[ReactDecision]:
    """Parse LLM response into a ReactDecision."""
    # Find JSON in the response
    try:
        # Try to find JSON block
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        
        if json_start == -1 or json_end == 0:
            return None
        
        json_str = content[json_start:json_end]
        data = json.loads(json_str)
        
        action = data.get("action", "")
        
        if action == "tool_call":
            tool_call_data = data.get("tool_call", {})
            return ReactDecision(
                action="tool_call",
                tool_call=ToolCall(
                    name=tool_call_data.get("name", ""),
                    arguments=tool_call_data.get("arguments", {}),
                    reasoning=tool_call_data.get("reasoning", ""),
                ),
            )
        elif action == "finish":
            return ReactDecision(
                action="finish",
                summary=data.get("summary", ""),
                confidence=float(data.get("confidence", 0.5)),
            )
        elif action == "reflect":
            return ReactDecision(
                action="reflect",
                summary=data.get("summary", ""),
            )
        else:
            return None
            
    except json.JSONDecodeError:
        return None
    except Exception as e:
        logger.warning(f"Failed to parse decision: {e}")
        return None


def _is_empty_result(output: str) -> bool:
    """Check if a tool result indicates no data found."""
    if not output or not output.strip():
        return True
    
    empty_indicators = [
        "no data",
        "no results",
        "not found",
        "empty",
        "[]",
        "{}",
        "null",
        "none",
    ]
    
    output_lower = output.lower().strip()
    return any(indicator in output_lower for indicator in empty_indicators)


async def _force_summarization(
    messages: list[Message],
    llm: LLMProtocol,
    config: ReactConfig,
    agent_id: str,
) -> str:
    """Force the LLM to summarize when max iterations reached."""
    # Build prompt from message history
    prompt = "\n\n".join(
        f"[{msg.role.upper()}]\n{msg.content}"
        for msg in messages
        if msg.role != "system"
    )
    
    prompt += "\n\n" + FORCED_SUMMARY_PROMPT.format(
        max_iterations=config.max_iterations,
    )
    
    try:
        system_content = messages[0].content if messages and messages[0].role == "system" else ""
        
        response = await llm.complete(
            prompt=prompt,
            system=system_content,
            system_prompt=system_content,
            temperature=0.0,
            max_tokens=config.max_output_tokens,
        )
        
        # Extract content
        if hasattr(response, "content"):
            content = response.content
        else:
            content = str(response)
        
        # Try to parse as decision
        decision = _parse_decision(content)
        if decision and decision.summary:
            return decision.summary
        
        # Fall back to raw content
        return content
        
    except Exception as e:
        logger.error(f"[{agent_id}] Forced summarization failed: {e}")
        return f"Investigation completed with {config.max_iterations} tool calls. Error generating summary: {e}"


# ----- Helper: Create tools from callables -----

def create_tool(
    name: str,
    description: str,
    executor: Callable[..., str],
    parameters: Optional[dict[str, Any]] = None,
) -> Tool:
    """Create a Tool from a callable.
    
    Args:
        name: Tool name
        description: What the tool does
        executor: Function to execute (sync or async)
        parameters: JSON schema for parameters
        
    Returns:
        Configured Tool instance
    """
    tool = Tool(
        name=name,
        description=description,
        parameters=parameters or {"type": "object", "properties": {}},
    )
    tool.set_executor(executor)
    return tool
