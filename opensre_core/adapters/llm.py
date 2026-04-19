"""
LLM Adapter - Interface with local and cloud LLMs

Supports:
- Ollama (local, privacy-first)
- OpenAI (GPT-4, GPT-4o)
- Anthropic (Claude 3)
- Azure OpenAI

Features:
- Retry with exponential backoff
- Response caching
- Streaming support
- Comprehensive metrics
"""

import asyncio
import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, AsyncIterator, Callable, TypeVar

import httpx
import ollama
from anthropic import AsyncAnthropic
from openai import AsyncAzureOpenAI, AsyncOpenAI

from opensre_core.config import settings
from opensre_core.metrics import record_llm_error, record_llm_request

logger = logging.getLogger(__name__)

# Type var for retry decorator
T = TypeVar("T")


class LLMProvider(Enum):
    """Supported LLM providers."""

    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE = "azure"


@dataclass
class LLMResponse:
    """Response from LLM."""

    content: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    finish_reason: str | None = None
    cached: bool = False

    @property
    def tokens_used(self) -> int:
        """Total tokens used (for backward compatibility)."""
        return self.input_tokens + self.output_tokens


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    backoff_factor: float = 2.0
    max_wait: float = 30.0
    retryable_errors: tuple[type[Exception], ...] = field(
        default_factory=lambda: (
            ConnectionError,
            TimeoutError,
            httpx.ConnectError,
            httpx.ReadTimeout,
        )
    )


def with_retry(config: RetryConfig | None = None) -> Callable:
    """
    Decorator for async functions with exponential backoff retry.

    Args:
        config: Retry configuration. Uses defaults if not provided.
    """
    cfg = config or RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_error: Exception | None = None

            for attempt in range(cfg.max_retries):
                try:
                    return await func(*args, **kwargs)
                except cfg.retryable_errors as e:
                    last_error = e
                    if attempt < cfg.max_retries - 1:
                        wait = min(cfg.backoff_factor**attempt, cfg.max_wait)
                        logger.warning(
                            f"LLM request failed (attempt {attempt + 1}/{cfg.max_retries}), "
                            f"retrying in {wait:.1f}s: {e}"
                        )
                        await asyncio.sleep(wait)
                except Exception:
                    # Non-retryable error, raise immediately
                    raise

            # All retries exhausted
            raise last_error or RuntimeError("Retry failed with no error captured")

        return wrapper

    return decorator


class LRUCache:
    """Simple LRU cache with TTL support."""

    def __init__(self, max_size: int = 100, ttl_seconds: float = 3600):
        self._cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl_seconds

    def _make_key(self, prompt: str, system_prompt: str, temperature: float) -> str:
        """Generate cache key from parameters."""
        key_data = f"{prompt}|{system_prompt}|{temperature}"
        return hashlib.sha256(key_data.encode()).hexdigest()

    def get(
        self, prompt: str, system_prompt: str, temperature: float
    ) -> LLMResponse | None:
        """Get cached response if exists and not expired."""
        key = self._make_key(prompt, system_prompt, temperature)
        if key not in self._cache:
            return None

        timestamp, response = self._cache[key]
        if time.time() - timestamp > self._ttl:
            # Expired
            del self._cache[key]
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        return response

    def set(
        self, prompt: str, system_prompt: str, temperature: float, response: LLMResponse
    ) -> None:
        """Cache a response."""
        key = self._make_key(prompt, system_prompt, temperature)

        # Remove oldest if at capacity
        while len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)

        self._cache[key] = (time.time(), response)

    def clear(self) -> None:
        """Clear all cached responses."""
        self._cache.clear()


class LLMAdapter:
    """
    Unified adapter for multiple LLM providers.

    Supports:
    - Ollama (local, privacy-first)
    - OpenAI (GPT-4, GPT-4o)
    - Anthropic (Claude 3)
    - Azure OpenAI

    Features:
    - Automatic retry with exponential backoff
    - Response caching for identical prompts
    - Streaming support
    - Comprehensive Prometheus metrics
    """

    def __init__(
        self,
        provider: str | None = None,
        cache_enabled: bool = True,
        cache_max_size: int = 100,
        cache_ttl_seconds: float = 3600,
        retry_config: RetryConfig | None = None,
    ):
        self.provider = LLMProvider(provider or settings.llm_provider)
        self._ollama_client: ollama.AsyncClient | None = None
        self._openai_client: AsyncOpenAI | None = None
        self._anthropic_client: AsyncAnthropic | None = None
        self._azure_client: AsyncAzureOpenAI | None = None

        # Caching
        self._cache_enabled = cache_enabled
        self._cache = LRUCache(max_size=cache_max_size, ttl_seconds=cache_ttl_seconds)

        # Retry configuration
        self._retry_config = retry_config or RetryConfig()

    async def health_check(self) -> dict[str, Any]:
        """Check LLM connection health."""
        start_time = time.time()

        try:
            if self.provider == LLMProvider.OLLAMA:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{settings.ollama_host}/api/tags", timeout=5
                    )
                    response.raise_for_status()
                    models = response.json().get("models", [])
                    model_names = [m["name"] for m in models][:3]
                    return {
                        "status": "healthy",
                        "provider": "ollama",
                        "model": settings.ollama_model,
                        "details": f"Available: {', '.join(model_names)}...",
                        "latency_ms": int((time.time() - start_time) * 1000),
                    }

            elif self.provider == LLMProvider.OPENAI:
                if not settings.openai_api_key:
                    return {"status": "error", "details": "OpenAI API key not configured"}
                # Quick validation - list models
                client = self.openai_client
                return {
                    "status": "healthy",
                    "provider": "openai",
                    "model": settings.openai_model,
                    "details": "API key configured",
                    "latency_ms": int((time.time() - start_time) * 1000),
                }

            elif self.provider == LLMProvider.ANTHROPIC:
                if not settings.anthropic_api_key:
                    return {
                        "status": "error",
                        "details": "Anthropic API key not configured",
                    }
                return {
                    "status": "healthy",
                    "provider": "anthropic",
                    "model": settings.anthropic_model,
                    "details": "API key configured",
                    "latency_ms": int((time.time() - start_time) * 1000),
                }

            elif self.provider == LLMProvider.AZURE:
                azure_endpoint = getattr(settings, "azure_openai_endpoint", None)
                azure_key = getattr(settings, "azure_openai_api_key", None)
                if not azure_endpoint or not azure_key:
                    return {
                        "status": "error",
                        "details": "Azure OpenAI not configured",
                    }
                return {
                    "status": "healthy",
                    "provider": "azure",
                    "model": getattr(settings, "azure_openai_deployment", "unknown"),
                    "details": f"Endpoint: {azure_endpoint}",
                    "latency_ms": int((time.time() - start_time) * 1000),
                }

            else:
                return {"status": "error", "details": f"Unknown provider: {self.provider}"}

        except Exception as e:
            return {
                "status": "error",
                "provider": self.provider.value,
                "details": str(e),
                "latency_ms": int((time.time() - start_time) * 1000),
            }

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        use_cache: bool = True,
    ) -> LLMResponse:
        """
        Generate a response from the LLM.

        Args:
            prompt: User prompt
            system_prompt: System instructions
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            use_cache: Whether to use cached responses

        Returns:
            LLMResponse with content, token usage, and metadata
        """
        system_prompt = system_prompt or ""

        # Check cache
        if use_cache and self._cache_enabled:
            cached = self._cache.get(prompt, system_prompt, temperature)
            if cached:
                logger.debug("Cache hit for LLM request")
                cached.cached = True
                return cached

        # Generate with retry
        response = await self._generate_with_retry(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Cache response
        if use_cache and self._cache_enabled:
            self._cache.set(prompt, system_prompt, temperature, response)

        return response

    @with_retry()
    async def _generate_with_retry(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        """Generate with automatic retry on transient failures."""
        start_time = time.time()
        model = self._get_model_name()

        try:
            if self.provider == LLMProvider.OLLAMA:
                response = await self._generate_ollama(
                    prompt, system_prompt, temperature, max_tokens
                )
            elif self.provider == LLMProvider.OPENAI:
                response = await self._generate_openai(
                    prompt, system_prompt, temperature, max_tokens
                )
            elif self.provider == LLMProvider.ANTHROPIC:
                response = await self._generate_anthropic(
                    prompt, system_prompt, temperature, max_tokens
                )
            elif self.provider == LLMProvider.AZURE:
                response = await self._generate_azure(
                    prompt, system_prompt, temperature, max_tokens
                )
            else:
                raise ValueError(f"Unknown provider: {self.provider}")

            # Calculate latency
            latency = time.time() - start_time
            response.latency_ms = int(latency * 1000)

            # Record metrics
            record_llm_request(
                provider=self.provider.value,
                model=model,
                success=True,
                latency=latency,
                tokens=response.tokens_used,
            )

            return response

        except Exception as e:
            latency = time.time() - start_time
            record_llm_request(
                provider=self.provider.value,
                model=model,
                success=False,
                latency=latency,
            )
            record_llm_error(
                provider=self.provider.value, model=model, error_type=type(e).__name__
            )
            raise

    def _get_model_name(self) -> str:
        """Get the model name for the current provider."""
        if self.provider == LLMProvider.OLLAMA:
            return settings.ollama_model
        elif self.provider == LLMProvider.OPENAI:
            return settings.openai_model
        elif self.provider == LLMProvider.ANTHROPIC:
            return settings.anthropic_model
        elif self.provider == LLMProvider.AZURE:
            return getattr(settings, "azure_openai_deployment", "unknown")
        return "unknown"

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """
        Generate streaming response from the LLM.

        Yields individual tokens/chunks as they're generated.
        Useful for real-time UI updates.
        """
        system_prompt = system_prompt or ""

        if self.provider == LLMProvider.OLLAMA:
            async for chunk in self._stream_ollama(prompt, system_prompt, temperature):
                yield chunk
        elif self.provider == LLMProvider.OPENAI:
            async for chunk in self._stream_openai(
                prompt, system_prompt, temperature, max_tokens
            ):
                yield chunk
        elif self.provider == LLMProvider.ANTHROPIC:
            async for chunk in self._stream_anthropic(
                prompt, system_prompt, temperature, max_tokens
            ):
                yield chunk
        elif self.provider == LLMProvider.AZURE:
            async for chunk in self._stream_azure(
                prompt, system_prompt, temperature, max_tokens
            ):
                yield chunk
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def clear_cache(self) -> None:
        """Clear the response cache."""
        self._cache.clear()

    # =========================================================================
    # Client Properties (Lazy Initialization)
    # =========================================================================

    @property
    def ollama_client(self) -> ollama.AsyncClient:
        if self._ollama_client is None:
            self._ollama_client = ollama.AsyncClient(host=settings.ollama_host)
        return self._ollama_client

    @property
    def openai_client(self) -> AsyncOpenAI:
        if self._openai_client is None:
            self._openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._openai_client

    @property
    def anthropic_client(self) -> AsyncAnthropic:
        if self._anthropic_client is None:
            self._anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._anthropic_client

    @property
    def azure_client(self) -> AsyncAzureOpenAI:
        if self._azure_client is None:
            azure_endpoint = getattr(settings, "azure_openai_endpoint", "")
            azure_key = getattr(settings, "azure_openai_api_key", "")
            api_version = getattr(settings, "azure_openai_api_version", "2024-02-01")
            self._azure_client = AsyncAzureOpenAI(
                azure_endpoint=azure_endpoint,
                api_key=azure_key,
                api_version=api_version,
            )
        return self._azure_client

    # =========================================================================
    # Ollama Implementation
    # =========================================================================

    async def _generate_ollama(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.ollama_client.chat(
            model=settings.ollama_model,
            messages=messages,
            options={
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        )

        # Ollama includes some token info
        prompt_eval_count = response.get("prompt_eval_count", 0)
        eval_count = response.get("eval_count", 0)

        return LLMResponse(
            content=response["message"]["content"],
            model=settings.ollama_model,
            provider="ollama",
            input_tokens=prompt_eval_count,
            output_tokens=eval_count,
            finish_reason=response.get("done_reason"),
        )

    async def _stream_ollama(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
    ) -> AsyncIterator[str]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async for chunk in await self.ollama_client.chat(
            model=settings.ollama_model,
            messages=messages,
            options={"temperature": temperature},
            stream=True,
        ):
            if chunk.get("message", {}).get("content"):
                yield chunk["message"]["content"]

    # =========================================================================
    # OpenAI Implementation
    # =========================================================================

    async def _generate_openai(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.openai_client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        choice = response.choices[0]
        usage = response.usage

        return LLMResponse(
            content=choice.message.content or "",
            model=settings.openai_model,
            provider="openai",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            finish_reason=choice.finish_reason,
        )

    async def _stream_openai(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        stream = await self.openai_client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    # =========================================================================
    # Anthropic Implementation
    # =========================================================================

    async def _generate_anthropic(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        response = await self.anthropic_client.messages.create(
            model=settings.anthropic_model,
            max_tokens=max_tokens,
            system=system_prompt or "You are a helpful assistant.",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )

        return LLMResponse(
            content=response.content[0].text,
            model=settings.anthropic_model,
            provider="anthropic",
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            finish_reason=response.stop_reason,
        )

    async def _stream_anthropic(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        async with self.anthropic_client.messages.stream(
            model=settings.anthropic_model,
            max_tokens=max_tokens,
            system=system_prompt or "You are a helpful assistant.",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    # =========================================================================
    # Azure OpenAI Implementation
    # =========================================================================

    async def _generate_azure(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        deployment = getattr(settings, "azure_openai_deployment", "gpt-4")

        response = await self.azure_client.chat.completions.create(
            model=deployment,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        choice = response.choices[0]
        usage = response.usage

        return LLMResponse(
            content=choice.message.content or "",
            model=deployment,
            provider="azure",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            finish_reason=choice.finish_reason,
        )

    async def _stream_azure(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        deployment = getattr(settings, "azure_openai_deployment", "gpt-4")

        stream = await self.azure_client.chat.completions.create(
            model=deployment,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


# =============================================================================
# Convenience Functions
# =============================================================================


def create_llm_adapter(
    provider: str | None = None,
    **kwargs,
) -> LLMAdapter:
    """
    Factory function to create an LLM adapter.

    Args:
        provider: LLM provider (ollama, openai, anthropic, azure)
        **kwargs: Additional arguments passed to LLMAdapter

    Returns:
        Configured LLMAdapter instance
    """
    return LLMAdapter(provider=provider, **kwargs)


async def quick_generate(
    prompt: str,
    system_prompt: str | None = None,
    provider: str | None = None,
) -> str:
    """
    Quick one-shot generation with default settings.

    For simple use cases where you just need a response.
    """
    adapter = create_llm_adapter(provider=provider)
    response = await adapter.generate(prompt=prompt, system_prompt=system_prompt)
    return response.content
