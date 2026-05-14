"""
LLM Client abstraction for AutoSRE V2.

Provides a unified interface for multiple LLM providers with:
- Async support
- Automatic retries
- Structured output
- Tool/function calling
- Token tracking
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, TypeVar

from pydantic import BaseModel

from autosre.utils.config import LLMConfig, get_config
from autosre.utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"


@dataclass
class LLMMessage:
    """A message in a conversation."""

    role: str  # system, user, assistant, tool
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


@dataclass
class ToolDefinition:
    """Definition of a tool/function for LLM."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any] | None = None


@dataclass
class ToolCall:
    """A tool call from the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """Response from LLM."""

    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    raw_response: Any = None

    @property
    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return len(self.tool_calls) > 0

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._request_count = 0

    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> LLMResponse:
        """Generate a completion."""
        ...

    @abstractmethod
    async def complete_structured(
        self,
        messages: list[LLMMessage],
        response_model: type[T],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> T:
        """Generate a structured completion with Pydantic model."""
        ...

    async def complete_with_retry(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        max_retries: int | None = None,
    ) -> LLMResponse:
        """Complete with automatic retry on failure."""
        retries = max_retries if max_retries is not None else self.config.max_retries
        last_error = None

        for attempt in range(retries + 1):
            try:
                return await self.complete(
                    messages=messages,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception as e:
                last_error = e
                if attempt < retries:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(
                        "LLM request failed, retrying",
                        attempt=attempt + 1,
                        max_retries=retries,
                        wait_seconds=wait_time,
                        error=str(e),
                    )
                    await asyncio.sleep(wait_time)

        raise last_error

    @property
    def stats(self) -> dict[str, Any]:
        """Get usage statistics."""
        return {
            "provider": self.config.provider,
            "model": self.config.model,
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
            "total_tokens": self._total_input_tokens + self._total_output_tokens,
            "request_count": self._request_count,
        }


class OpenAIClient(BaseLLMClient):
    """OpenAI API client."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._client = None

    async def _get_client(self):
        """Lazy initialize OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError:
                raise ImportError(
                    "openai package required. Install with: pip install openai"
                )

            api_key = self.config.api_key.get_secret_value() if self.config.api_key else None
            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
            )
        return self._client

    def _convert_messages(self, messages: list[LLMMessage]) -> list[dict[str, Any]]:
        """Convert to OpenAI message format."""
        result = []
        for msg in messages:
            converted: dict[str, Any] = {
                "role": msg.role,
                "content": msg.content,
            }
            if msg.name:
                converted["name"] = msg.name
            if msg.tool_call_id:
                converted["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                converted["tool_calls"] = msg.tool_calls
            result.append(converted)
        return result

    def _convert_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        """Convert to OpenAI tool format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in tools
        ]

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> LLMResponse:
        """Generate completion using OpenAI API."""
        client = await self._get_client()
        start_time = datetime.now(timezone.utc)

        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": self._convert_messages(messages),
            "temperature": temperature if temperature is not None else self.config.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.config.max_tokens,
        }

        if tools:
            kwargs["tools"] = self._convert_tools(tools)
            kwargs["tool_choice"] = "auto"

        if stop:
            kwargs["stop"] = stop

        response = await client.chat.completions.create(**kwargs)
        latency = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        # Track usage
        usage = response.usage
        if usage:
            self._total_input_tokens += usage.prompt_tokens
            self._total_output_tokens += usage.completion_tokens
        self._request_count += 1

        # Parse tool calls
        tool_calls = []
        choice = response.choices[0]
        if choice.message.tool_calls:
            import json
            for tc in choice.message.tool_calls:
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments),
                ))

        return LLMResponse(
            content=choice.message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            model=response.model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            latency_ms=latency,
            raw_response=response,
        )

    async def complete_structured(
        self,
        messages: list[LLMMessage],
        response_model: type[T],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> T:
        """Generate structured output using OpenAI's response_format."""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError("openai package required")

        client = await self._get_client()

        # Use OpenAI's native structured output
        response = await client.beta.chat.completions.parse(
            model=self.config.model,
            messages=self._convert_messages(messages),
            response_format=response_model,
            temperature=temperature if temperature is not None else self.config.temperature,
            max_tokens=max_tokens if max_tokens is not None else self.config.max_tokens,
        )

        self._request_count += 1
        if response.usage:
            self._total_input_tokens += response.usage.prompt_tokens
            self._total_output_tokens += response.usage.completion_tokens

        return response.choices[0].message.parsed


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude API client."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._client = None

    async def _get_client(self):
        """Lazy initialize Anthropic client."""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
            except ImportError:
                raise ImportError(
                    "anthropic package required. Install with: pip install anthropic"
                )

            api_key = self.config.api_key.get_secret_value() if self.config.api_key else None
            self._client = AsyncAnthropic(
                api_key=api_key,
                timeout=self.config.timeout,
            )
        return self._client

    def _convert_messages(
        self, messages: list[LLMMessage]
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Convert messages, extracting system prompt."""
        system_prompt = None
        converted = []

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
            elif msg.role == "tool":
                # Anthropic uses tool_result
                converted.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id,
                        "content": msg.content,
                    }],
                })
            else:
                converted.append({
                    "role": msg.role,
                    "content": msg.content,
                })

        return system_prompt, converted

    def _convert_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        """Convert to Anthropic tool format."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters,
            }
            for tool in tools
        ]

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> LLMResponse:
        """Generate completion using Anthropic API."""
        client = await self._get_client()
        start_time = datetime.now(timezone.utc)

        system_prompt, converted_messages = self._convert_messages(messages)

        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": converted_messages,
            "max_tokens": max_tokens if max_tokens is not None else self.config.max_tokens,
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        if temperature is not None:
            kwargs["temperature"] = temperature
        elif self.config.temperature is not None:
            kwargs["temperature"] = self.config.temperature

        if tools:
            kwargs["tools"] = self._convert_tools(tools)

        if stop:
            kwargs["stop_sequences"] = stop

        response = await client.messages.create(**kwargs)
        latency = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        # Track usage
        self._total_input_tokens += response.usage.input_tokens
        self._total_output_tokens += response.usage.output_tokens
        self._request_count += 1

        # Parse response content
        content = None
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content = block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input,
                ))

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=response.stop_reason or "stop",
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=latency,
            raw_response=response,
        )

    async def complete_structured(
        self,
        messages: list[LLMMessage],
        response_model: type[T],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> T:
        """Generate structured output using tool calling."""
        import json

        # Create tool for structured output
        schema = response_model.model_json_schema()
        tool = ToolDefinition(
            name="respond",
            description="Respond with structured data",
            parameters=schema,
        )

        # Add instruction to use tool
        messages = messages.copy()
        messages.append(LLMMessage(
            role="user",
            content="Use the 'respond' tool to provide your response in the required format.",
        ))

        response = await self.complete(
            messages=messages,
            tools=[tool],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        if not response.tool_calls:
            raise ValueError("Model did not use structured output tool")

        return response_model(**response.tool_calls[0].arguments)


class OllamaClient(BaseLLMClient):
    """Ollama local LLM client."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._base_url = config.base_url or "http://localhost:11434"

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> LLMResponse:
        """Generate completion using Ollama API."""
        import httpx

        start_time = datetime.now(timezone.utc)

        # Convert messages
        converted_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": converted_messages,
            "stream": False,
        }

        options: dict[str, Any] = {}
        if temperature is not None:
            options["temperature"] = temperature
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        if stop:
            options["stop"] = stop

        if options:
            payload["options"] = options

        # Ollama tool support (if model supports it)
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in tools
            ]

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.post(
                f"{self._base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        latency = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        # Parse tool calls if present
        tool_calls = []
        message = data.get("message", {})
        if "tool_calls" in message:
            for tc in message["tool_calls"]:
                tool_calls.append(ToolCall(
                    id=tc.get("id", ""),
                    name=tc["function"]["name"],
                    arguments=tc["function"]["arguments"],
                ))

        # Estimate tokens (Ollama doesn't always provide)
        content = message.get("content", "")
        input_tokens = data.get("prompt_eval_count", len(str(messages)) // 4)
        output_tokens = data.get("eval_count", len(content) // 4)

        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens
        self._request_count += 1

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason="stop",
            model=self.config.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency,
            raw_response=data,
        )

    async def complete_structured(
        self,
        messages: list[LLMMessage],
        response_model: type[T],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> T:
        """Generate structured output with JSON mode."""
        import json

        # Add JSON instruction
        schema = response_model.model_json_schema()
        messages = messages.copy()
        messages.append(LLMMessage(
            role="user",
            content=f"Respond with valid JSON matching this schema:\n{json.dumps(schema, indent=2)}",
        ))

        response = await self.complete(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Parse JSON from response
        content = response.content or ""
        # Try to extract JSON if wrapped in markdown
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        return response_model(**json.loads(content.strip()))


class LLMClient:
    """
    Factory for LLM clients.

    Creates the appropriate client based on provider configuration.
    """

    _instances: dict[str, BaseLLMClient] = {}

    @classmethod
    def create(cls, config: LLMConfig | None = None) -> BaseLLMClient:
        """
        Create or get cached LLM client.

        Args:
            config: LLM configuration. Uses global config if not provided.

        Returns:
            Appropriate LLM client instance
        """
        if config is None:
            config = get_config().llm

        # Cache key based on provider and model
        cache_key = f"{config.provider}:{config.model}:{config.base_url}"

        if cache_key not in cls._instances:
            provider = LLMProvider(config.provider)

            if provider == LLMProvider.OPENAI:
                cls._instances[cache_key] = OpenAIClient(config)
            elif provider == LLMProvider.ANTHROPIC:
                cls._instances[cache_key] = AnthropicClient(config)
            elif provider == LLMProvider.OLLAMA:
                cls._instances[cache_key] = OllamaClient(config)
            else:
                raise ValueError(f"Unsupported LLM provider: {config.provider}")

            logger.info(
                "Created LLM client",
                provider=config.provider,
                model=config.model,
            )

        return cls._instances[cache_key]

    @classmethod
    def clear_cache(cls) -> None:
        """Clear cached client instances."""
        cls._instances.clear()


# Convenience functions
async def complete(
    messages: list[LLMMessage],
    tools: list[ToolDefinition] | None = None,
    config: LLMConfig | None = None,
    **kwargs: Any,
) -> LLMResponse:
    """Quick completion using default client."""
    client = LLMClient.create(config)
    return await client.complete(messages, tools, **kwargs)


async def complete_structured(
    messages: list[LLMMessage],
    response_model: type[T],
    config: LLMConfig | None = None,
    **kwargs: Any,
) -> T:
    """Quick structured completion using default client."""
    client = LLMClient.create(config)
    return await client.complete_structured(messages, response_model, **kwargs)
