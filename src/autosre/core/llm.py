"""AutoSRE LLM Client - Unified client supporting multiple providers."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, TypeVar

import tiktoken

from .config import (
    CacheBackend,
    LLMProviderSettings,
    LLMProviderType,
    RetrySettings,
    Settings,
    get_settings,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# EXCEPTIONS
# =============================================================================


class LLMError(Exception):
    """Base exception for LLM errors."""
    pass


class LLMRateLimitError(LLMError):
    """Rate limit exceeded."""
    
    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class LLMAuthenticationError(LLMError):
    """Authentication failed."""
    pass


class LLMContextLengthError(LLMError):
    """Context length exceeded."""
    
    def __init__(self, message: str, max_tokens: int, requested_tokens: int):
        super().__init__(message)
        self.max_tokens = max_tokens
        self.requested_tokens = requested_tokens


class LLMProviderError(LLMError):
    """Provider-specific error."""
    
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


# =============================================================================
# RESPONSE MODELS
# =============================================================================


@dataclass
class LLMResponse:
    """Standardized LLM response."""
    
    content: str
    model: str
    provider: str
    
    # Token usage
    input_tokens: int = 0
    output_tokens: int = 0
    
    # Metadata
    finish_reason: str | None = None
    latency_ms: float = 0
    cached: bool = False
    
    # Raw response for debugging
    raw_response: dict[str, Any] | None = None
    
    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens


@dataclass
class Message:
    """Chat message."""
    
    role: str  # system, user, assistant
    content: str
    name: str | None = None
    
    def to_dict(self) -> dict[str, str]:
        """Convert to dict for API calls."""
        d = {"role": self.role, "content": self.content}
        if self.name:
            d["name"] = self.name
        return d


# =============================================================================
# CACHING
# =============================================================================


class ResponseCache(ABC):
    """Abstract cache interface."""
    
    @abstractmethod
    async def get(self, key: str) -> LLMResponse | None:
        """Get cached response."""
        pass
    
    @abstractmethod
    async def set(self, key: str, response: LLMResponse, ttl: int) -> None:
        """Cache a response."""
        pass
    
    @abstractmethod
    async def clear(self) -> None:
        """Clear the cache."""
        pass


class MemoryCache(ResponseCache):
    """In-memory LRU cache."""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache: dict[str, tuple[LLMResponse, float]] = {}
    
    async def get(self, key: str) -> LLMResponse | None:
        if key in self._cache:
            response, expiry = self._cache[key]
            if time.time() < expiry:
                return response
            del self._cache[key]
        return None
    
    async def set(self, key: str, response: LLMResponse, ttl: int) -> None:
        # Simple LRU: remove oldest if at capacity
        if len(self._cache) >= self.max_size:
            oldest = min(self._cache.items(), key=lambda x: x[1][1])
            del self._cache[oldest[0]]
        
        self._cache[key] = (response, time.time() + ttl)
    
    async def clear(self) -> None:
        self._cache.clear()


class DiskCache(ResponseCache):
    """Disk-based cache using shelve."""
    
    def __init__(self, path: str):
        import shelve
        self.path = path
        self._db = shelve.open(path)
    
    async def get(self, key: str) -> LLMResponse | None:
        if key in self._db:
            data, expiry = self._db[key]
            if time.time() < expiry:
                return LLMResponse(**data)
            del self._db[key]
        return None
    
    async def set(self, key: str, response: LLMResponse, ttl: int) -> None:
        self._db[key] = (response.__dict__, time.time() + ttl)
        self._db.sync()
    
    async def clear(self) -> None:
        self._db.clear()
        self._db.sync()


# =============================================================================
# TOKEN COUNTING
# =============================================================================


class TokenCounter:
    """Count tokens for different models."""
    
    # Approximate characters per token for models without tiktoken support
    CHARS_PER_TOKEN = 4
    
    # Cache encodings
    _encodings: dict[str, Any] = {}
    
    @classmethod
    def count(cls, text: str, model: str = "gpt-4") -> int:
        """Count tokens in text for a given model.
        
        Args:
            text: Text to count tokens for
            model: Model name for tokenizer selection
            
        Returns:
            Estimated token count
        """
        try:
            encoding = cls._get_encoding(model)
            return len(encoding.encode(text))
        except Exception:
            # Fallback to character-based estimation
            return len(text) // cls.CHARS_PER_TOKEN
    
    @classmethod
    def count_messages(cls, messages: list[dict[str, str]], model: str = "gpt-4") -> int:
        """Count tokens in a list of messages.
        
        Based on OpenAI's token counting guide.
        """
        try:
            encoding = cls._get_encoding(model)
            
            # Message overhead varies by model
            if "gpt-4" in model or "gpt-3.5" in model:
                tokens_per_message = 3
                tokens_per_name = 1
            else:
                tokens_per_message = 4
                tokens_per_name = 0
            
            total = 0
            for message in messages:
                total += tokens_per_message
                for key, value in message.items():
                    total += len(encoding.encode(str(value)))
                    if key == "name":
                        total += tokens_per_name
            
            total += 3  # Every reply is primed with <|start|>assistant<|message|>
            return total
            
        except Exception:
            # Fallback
            total_chars = sum(len(str(v)) for m in messages for v in m.values())
            return total_chars // cls.CHARS_PER_TOKEN
    
    @classmethod
    def _get_encoding(cls, model: str) -> Any:
        """Get or create encoding for a model."""
        if model not in cls._encodings:
            try:
                cls._encodings[model] = tiktoken.encoding_for_model(model)
            except KeyError:
                # Fallback to cl100k_base (GPT-4 encoding)
                cls._encodings[model] = tiktoken.get_encoding("cl100k_base")
        return cls._encodings[model]


# =============================================================================
# RETRY LOGIC
# =============================================================================


def with_retry(settings: RetrySettings | None = None):
    """Decorator for retry logic with exponential backoff."""
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            retry_settings = settings or RetrySettings()
            last_exception = None
            
            for attempt in range(retry_settings.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                    
                except LLMRateLimitError as e:
                    last_exception = e
                    delay = e.retry_after or _calculate_delay(
                        attempt, retry_settings
                    )
                    logger.warning(
                        f"Rate limited, retrying in {delay:.1f}s (attempt {attempt + 1})"
                    )
                    await asyncio.sleep(delay)
                    
                except LLMProviderError as e:
                    if e.status_code not in retry_settings.retryable_status_codes:
                        raise
                    
                    last_exception = e
                    delay = _calculate_delay(attempt, retry_settings)
                    logger.warning(
                        f"Provider error {e.status_code}, retrying in {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)
                    
                except Exception as e:
                    # Don't retry other exceptions
                    raise
            
            raise last_exception or LLMError("Max retries exceeded")
        
        return wrapper
    return decorator


def _calculate_delay(attempt: int, settings: RetrySettings) -> float:
    """Calculate delay with exponential backoff and optional jitter."""
    delay = settings.base_delay * (settings.exponential_base ** attempt)
    delay = min(delay, settings.max_delay)
    
    if settings.jitter:
        delay *= (0.5 + random.random())
    
    return delay


# =============================================================================
# PROVIDER IMPLEMENTATIONS
# =============================================================================


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    AZURE_OPENAI = "azure_openai"
    TOGETHER = "together"


class BaseProvider(ABC):
    """Base class for LLM providers."""
    
    def __init__(self, settings: LLMProviderSettings, retry_settings: RetrySettings):
        self.settings = settings
        self.retry_settings = retry_settings
        self._client: Any = None
    
    @abstractmethod
    async def complete(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate a completion."""
        pass
    
    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate a chat completion."""
        pass
    
    @abstractmethod
    async def stream(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """Stream a completion."""
        pass
    
    @abstractmethod
    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """Stream a chat completion."""
        pass
    
    def _get_model(self, model: str | None) -> str:
        """Get model, falling back to default."""
        return model or self.settings.default_model or ""


class OpenAIProvider(BaseProvider):
    """OpenAI provider implementation."""
    
    async def _get_client(self):
        """Lazily initialize client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError:
                raise ImportError("openai package required: pip install openai")
            
            self._client = AsyncOpenAI(
                api_key=self.settings.api_key.get_secret_value() if self.settings.api_key else None,
                base_url=self.settings.base_url,
                timeout=self.settings.timeout,
                max_retries=0,  # We handle retries
            )
        return self._client
    
    @with_retry()
    async def complete(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate completion via chat API."""
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(messages, model, max_tokens, temperature, **kwargs)
    
    @with_retry()
    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate chat completion."""
        client = await self._get_client()
        model = self._get_model(model)
        
        start = time.time()
        
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )
        except Exception as e:
            self._handle_error(e)
        
        latency = (time.time() - start) * 1000
        
        return LLMResponse(
            content=response.choices[0].message.content or "",
            model=response.model,
            provider="openai",
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
            finish_reason=response.choices[0].finish_reason,
            latency_ms=latency,
            raw_response=response.model_dump() if hasattr(response, 'model_dump') else None,
        )
    
    async def stream(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """Stream completion."""
        messages = [{"role": "user", "content": prompt}]
        async for chunk in self.stream_chat(messages, model, max_tokens, temperature, **kwargs):
            yield chunk
    
    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion."""
        client = await self._get_client()
        model = self._get_model(model)
        
        try:
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
                **kwargs
            )
            
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            self._handle_error(e)
    
    def _handle_error(self, e: Exception) -> None:
        """Convert OpenAI errors to our exceptions."""
        from openai import APIStatusError, RateLimitError, AuthenticationError
        
        if isinstance(e, RateLimitError):
            retry_after = None
            if hasattr(e, 'response') and e.response:
                retry_after = e.response.headers.get('retry-after')
            raise LLMRateLimitError(str(e), float(retry_after) if retry_after else None)
        
        if isinstance(e, AuthenticationError):
            raise LLMAuthenticationError(str(e))
        
        if isinstance(e, APIStatusError):
            raise LLMProviderError(str(e), e.status_code)
        
        raise LLMError(str(e))


class AnthropicProvider(BaseProvider):
    """Anthropic provider implementation."""
    
    async def _get_client(self):
        """Lazily initialize client."""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
            except ImportError:
                raise ImportError("anthropic package required: pip install anthropic")
            
            self._client = AsyncAnthropic(
                api_key=self.settings.api_key.get_secret_value() if self.settings.api_key else None,
                base_url=self.settings.base_url,
                timeout=self.settings.timeout,
                max_retries=0,
            )
        return self._client
    
    @with_retry()
    async def complete(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate completion."""
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(messages, model, max_tokens, temperature, **kwargs)
    
    @with_retry()
    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate chat completion."""
        client = await self._get_client()
        model = self._get_model(model)
        
        # Extract system message if present
        system = None
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                chat_messages.append(msg)
        
        start = time.time()
        
        try:
            response = await client.messages.create(
                model=model,
                messages=chat_messages,
                max_tokens=max_tokens or 4096,
                temperature=temperature,
                system=system,
                **kwargs
            )
        except Exception as e:
            self._handle_error(e)
        
        latency = (time.time() - start) * 1000
        
        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text
        
        return LLMResponse(
            content=content,
            model=response.model,
            provider="anthropic",
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            finish_reason=response.stop_reason,
            latency_ms=latency,
            raw_response=response.model_dump() if hasattr(response, 'model_dump') else None,
        )
    
    async def stream(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """Stream completion."""
        messages = [{"role": "user", "content": prompt}]
        async for chunk in self.stream_chat(messages, model, max_tokens, temperature, **kwargs):
            yield chunk
    
    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion."""
        client = await self._get_client()
        model = self._get_model(model)
        
        system = None
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                chat_messages.append(msg)
        
        try:
            async with client.messages.stream(
                model=model,
                messages=chat_messages,
                max_tokens=max_tokens or 4096,
                temperature=temperature,
                system=system,
                **kwargs
            ) as stream:
                async for text in stream.text_stream:
                    yield text
                    
        except Exception as e:
            self._handle_error(e)
    
    def _handle_error(self, e: Exception) -> None:
        """Convert Anthropic errors to our exceptions."""
        from anthropic import APIStatusError, RateLimitError, AuthenticationError
        
        if isinstance(e, RateLimitError):
            raise LLMRateLimitError(str(e))
        
        if isinstance(e, AuthenticationError):
            raise LLMAuthenticationError(str(e))
        
        if isinstance(e, APIStatusError):
            raise LLMProviderError(str(e), e.status_code)
        
        raise LLMError(str(e))


class OllamaProvider(BaseProvider):
    """Ollama provider implementation (local models)."""
    
    async def _get_client(self):
        """Lazily initialize client."""
        if self._client is None:
            try:
                from ollama import AsyncClient
            except ImportError:
                raise ImportError("ollama package required: pip install ollama")
            
            self._client = AsyncClient(
                host=self.settings.base_url or "http://localhost:11434"
            )
        return self._client
    
    @with_retry()
    async def complete(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate completion."""
        client = await self._get_client()
        model = self._get_model(model)
        
        start = time.time()
        
        options = {"temperature": temperature}
        if max_tokens:
            options["num_predict"] = max_tokens
        
        response = await client.generate(
            model=model,
            prompt=prompt,
            options=options,
            **kwargs
        )
        
        latency = (time.time() - start) * 1000
        
        return LLMResponse(
            content=response["response"],
            model=model,
            provider="ollama",
            input_tokens=response.get("prompt_eval_count", 0),
            output_tokens=response.get("eval_count", 0),
            latency_ms=latency,
            raw_response=response,
        )
    
    @with_retry()
    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate chat completion."""
        client = await self._get_client()
        model = self._get_model(model)
        
        start = time.time()
        
        options = {"temperature": temperature}
        if max_tokens:
            options["num_predict"] = max_tokens
        
        response = await client.chat(
            model=model,
            messages=messages,
            options=options,
            **kwargs
        )
        
        latency = (time.time() - start) * 1000
        
        return LLMResponse(
            content=response["message"]["content"],
            model=model,
            provider="ollama",
            input_tokens=response.get("prompt_eval_count", 0),
            output_tokens=response.get("eval_count", 0),
            latency_ms=latency,
            raw_response=response,
        )
    
    async def stream(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """Stream completion."""
        client = await self._get_client()
        model = self._get_model(model)
        
        options = {"temperature": temperature}
        if max_tokens:
            options["num_predict"] = max_tokens
        
        async for chunk in await client.generate(
            model=model,
            prompt=prompt,
            options=options,
            stream=True,
            **kwargs
        ):
            if chunk.get("response"):
                yield chunk["response"]
    
    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion."""
        client = await self._get_client()
        model = self._get_model(model)
        
        options = {"temperature": temperature}
        if max_tokens:
            options["num_predict"] = max_tokens
        
        async for chunk in await client.chat(
            model=model,
            messages=messages,
            options=options,
            stream=True,
            **kwargs
        ):
            if chunk.get("message", {}).get("content"):
                yield chunk["message"]["content"]


class AzureOpenAIProvider(BaseProvider):
    """Azure OpenAI provider implementation."""
    
    async def _get_client(self):
        """Lazily initialize client."""
        if self._client is None:
            try:
                from openai import AsyncAzureOpenAI
            except ImportError:
                raise ImportError("openai package required: pip install openai")
            
            self._client = AsyncAzureOpenAI(
                api_key=self.settings.api_key.get_secret_value() if self.settings.api_key else None,
                api_version=self.settings.api_version or "2024-02-15-preview",
                azure_endpoint=self.settings.base_url or "",
                timeout=self.settings.timeout,
                max_retries=0,
            )
        return self._client
    
    @with_retry()
    async def complete(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate completion."""
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(messages, model, max_tokens, temperature, **kwargs)
    
    @with_retry()
    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate chat completion."""
        client = await self._get_client()
        deployment = model or self.settings.deployment_name or self._get_model(model)
        
        start = time.time()
        
        response = await client.chat.completions.create(
            model=deployment,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )
        
        latency = (time.time() - start) * 1000
        
        return LLMResponse(
            content=response.choices[0].message.content or "",
            model=response.model,
            provider="azure_openai",
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
            finish_reason=response.choices[0].finish_reason,
            latency_ms=latency,
            raw_response=response.model_dump() if hasattr(response, 'model_dump') else None,
        )
    
    async def stream(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """Stream completion."""
        messages = [{"role": "user", "content": prompt}]
        async for chunk in self.stream_chat(messages, model, max_tokens, temperature, **kwargs):
            yield chunk
    
    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion."""
        client = await self._get_client()
        deployment = model or self.settings.deployment_name or self._get_model(model)
        
        stream = await client.chat.completions.create(
            model=deployment,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
            **kwargs
        )
        
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class TogetherProvider(BaseProvider):
    """Together AI provider implementation."""
    
    async def _get_client(self):
        """Lazily initialize client - uses OpenAI-compatible API."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError:
                raise ImportError("openai package required: pip install openai")
            
            self._client = AsyncOpenAI(
                api_key=self.settings.api_key.get_secret_value() if self.settings.api_key else None,
                base_url=self.settings.base_url or "https://api.together.xyz/v1",
                timeout=self.settings.timeout,
                max_retries=0,
            )
        return self._client
    
    @with_retry()
    async def complete(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate completion."""
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(messages, model, max_tokens, temperature, **kwargs)
    
    @with_retry()
    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate chat completion."""
        client = await self._get_client()
        model = self._get_model(model)
        
        start = time.time()
        
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )
        
        latency = (time.time() - start) * 1000
        
        return LLMResponse(
            content=response.choices[0].message.content or "",
            model=response.model,
            provider="together",
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
            finish_reason=response.choices[0].finish_reason,
            latency_ms=latency,
            raw_response=response.model_dump() if hasattr(response, 'model_dump') else None,
        )
    
    async def stream(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """Stream completion."""
        messages = [{"role": "user", "content": prompt}]
        async for chunk in self.stream_chat(messages, model, max_tokens, temperature, **kwargs):
            yield chunk
    
    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion."""
        client = await self._get_client()
        model = self._get_model(model)
        
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
            **kwargs
        )
        
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


# =============================================================================
# UNIFIED LLM CLIENT
# =============================================================================


class LLMClient:
    """Unified LLM client supporting multiple providers.
    
    Features:
    - Multiple provider support (OpenAI, Anthropic, Ollama, Azure, Together)
    - Automatic retry with exponential backoff
    - Response caching
    - Token counting and limits
    - Structured output parsing
    
    Example:
        >>> client = LLMClient()
        >>> response = await client.complete("Hello, world!")
        >>> print(response.content)
        
        >>> # Use specific provider
        >>> response = await client.chat(
        ...     messages=[{"role": "user", "content": "Hello"}],
        ...     provider=LLMProvider.ANTHROPIC,
        ...     model="claude-3-sonnet-20240229"
        ... )
    """
    
    def __init__(self, settings: Settings | None = None):
        """Initialize the LLM client.
        
        Args:
            settings: Configuration settings. Uses global settings if not provided.
        """
        self.settings = settings or get_settings()
        self._providers: dict[LLMProvider, BaseProvider] = {}
        self._cache: ResponseCache | None = None
        
        # Initialize cache if enabled
        if self.settings.cache.enabled:
            self._init_cache()
    
    def _init_cache(self) -> None:
        """Initialize the response cache."""
        cache_settings = self.settings.cache
        
        if cache_settings.backend == CacheBackend.MEMORY:
            self._cache = MemoryCache(cache_settings.max_size)
        elif cache_settings.backend == CacheBackend.DISK:
            cache_settings.disk_path.mkdir(parents=True, exist_ok=True)
            self._cache = DiskCache(str(cache_settings.disk_path / "llm_cache"))
        # Redis would require additional async setup
    
    def _get_provider(self, provider: LLMProvider | None = None) -> BaseProvider:
        """Get or create a provider instance.
        
        Args:
            provider: Provider to use. Uses default if not specified.
            
        Returns:
            Provider instance
        """
        if provider is None:
            provider = LLMProvider(self.settings.default_provider.value)
        
        if provider not in self._providers:
            provider_settings = self.settings.get_provider_settings(
                LLMProviderType(provider.value)
            )
            
            provider_classes = {
                LLMProvider.OPENAI: OpenAIProvider,
                LLMProvider.ANTHROPIC: AnthropicProvider,
                LLMProvider.OLLAMA: OllamaProvider,
                LLMProvider.AZURE_OPENAI: AzureOpenAIProvider,
                LLMProvider.TOGETHER: TogetherProvider,
            }
            
            provider_class = provider_classes[provider]
            self._providers[provider] = provider_class(
                provider_settings, 
                self.settings.retry
            )
        
        return self._providers[provider]
    
    def _cache_key(
        self,
        method: str,
        prompt_or_messages: str | list,
        model: str,
        **kwargs: Any
    ) -> str:
        """Generate cache key for a request."""
        key_data = {
            "method": method,
            "input": prompt_or_messages,
            "model": model,
            **{k: v for k, v in kwargs.items() if k != "stream"}
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()
    
    async def complete(
        self,
        prompt: str,
        provider: LLMProvider | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        use_cache: bool = True,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate a completion.
        
        Args:
            prompt: The prompt text
            provider: LLM provider to use
            model: Model name (uses provider default if not specified)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-2)
            use_cache: Whether to use response cache
            **kwargs: Additional provider-specific arguments
            
        Returns:
            LLMResponse with the completion
        """
        provider_instance = self._get_provider(provider)
        model = model or self._get_model(provider)
        
        # Check cache
        if use_cache and self._cache:
            cache_key = self._cache_key("complete", prompt, model, temperature=temperature)
            cached = await self._cache.get(cache_key)
            if cached:
                cached.cached = True
                return cached
        
        # Check token limits
        input_tokens = TokenCounter.count(prompt, model)
        self._check_token_limits(input_tokens, model, max_tokens)
        
        response = await provider_instance.complete(
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )
        
        # Cache response
        if use_cache and self._cache and response.content:
            await self._cache.set(
                self._cache_key("complete", prompt, model, temperature=temperature),
                response,
                self.settings.cache.ttl_seconds
            )
        
        return response
    
    async def chat(
        self,
        messages: list[dict[str, str]] | list[Message],
        provider: LLMProvider | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        use_cache: bool = True,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate a chat completion.
        
        Args:
            messages: List of chat messages
            provider: LLM provider to use
            model: Model name
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            use_cache: Whether to use response cache
            **kwargs: Additional provider-specific arguments
            
        Returns:
            LLMResponse with the completion
        """
        provider_instance = self._get_provider(provider)
        model = model or self._get_model(provider)
        
        # Convert Message objects to dicts
        msg_dicts = [
            m.to_dict() if isinstance(m, Message) else m 
            for m in messages
        ]
        
        # Check cache
        if use_cache and self._cache:
            cache_key = self._cache_key("chat", msg_dicts, model, temperature=temperature)
            cached = await self._cache.get(cache_key)
            if cached:
                cached.cached = True
                return cached
        
        # Check token limits
        input_tokens = TokenCounter.count_messages(msg_dicts, model)
        self._check_token_limits(input_tokens, model, max_tokens)
        
        response = await provider_instance.chat(
            messages=msg_dicts,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )
        
        # Cache response
        if use_cache and self._cache and response.content:
            await self._cache.set(
                self._cache_key("chat", msg_dicts, model, temperature=temperature),
                response,
                self.settings.cache.ttl_seconds
            )
        
        return response
    
    async def stream(
        self,
        prompt: str,
        provider: LLMProvider | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """Stream a completion.
        
        Args:
            prompt: The prompt text
            provider: LLM provider to use
            model: Model name
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional arguments
            
        Yields:
            Text chunks as they're generated
        """
        provider_instance = self._get_provider(provider)
        model = model or self._get_model(provider)
        
        async for chunk in provider_instance.stream(
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        ):
            yield chunk
    
    async def stream_chat(
        self,
        messages: list[dict[str, str]] | list[Message],
        provider: LLMProvider | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """Stream a chat completion.
        
        Args:
            messages: List of chat messages
            provider: LLM provider to use
            model: Model name
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional arguments
            
        Yields:
            Text chunks as they're generated
        """
        provider_instance = self._get_provider(provider)
        model = model or self._get_model(provider)
        
        msg_dicts = [
            m.to_dict() if isinstance(m, Message) else m 
            for m in messages
        ]
        
        async for chunk in provider_instance.stream_chat(
            messages=msg_dicts,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        ):
            yield chunk
    
    def _get_model(self, provider: LLMProvider | None = None) -> str:
        """Get default model for a provider."""
        if provider is None:
            return self.settings.default_model
        
        provider_settings = self.settings.get_provider_settings(
            LLMProviderType(provider.value)
        )
        return provider_settings.default_model or self.settings.default_model
    
    def _check_token_limits(
        self,
        input_tokens: int,
        model: str,
        max_tokens: int | None
    ) -> None:
        """Check if request is within token limits."""
        limits = self.settings.tokens.model_limits.get(model, {})
        context_window = limits.get(
            "context_window", 
            self.settings.tokens.default_context_window
        )
        
        max_output = max_tokens or limits.get(
            "max_tokens",
            self.settings.tokens.default_max_tokens
        )
        
        total_needed = input_tokens + max_output + self.settings.tokens.response_reserve
        
        if total_needed > context_window:
            raise LLMContextLengthError(
                f"Request exceeds context window: {total_needed} > {context_window}",
                max_tokens=context_window,
                requested_tokens=total_needed
            )
    
    async def parse_json(
        self,
        response: LLMResponse | str,
        schema: type[T] | None = None,
    ) -> dict[str, Any] | T:
        """Parse JSON from LLM response.
        
        Args:
            response: LLM response or raw text
            schema: Optional Pydantic model to validate against
            
        Returns:
            Parsed JSON as dict or Pydantic model
        """
        content = response.content if isinstance(response, LLMResponse) else response
        
        # Extract JSON from markdown code blocks if present
        import re
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
        if json_match:
            content = json_match.group(1)
        
        data = json.loads(content)
        
        if schema:
            return schema.model_validate(data)
        
        return data
    
    async def clear_cache(self) -> None:
        """Clear the response cache."""
        if self._cache:
            await self._cache.clear()
    
    def count_tokens(self, text: str, model: str | None = None) -> int:
        """Count tokens in text.
        
        Args:
            text: Text to count
            model: Model for tokenizer selection
            
        Returns:
            Token count
        """
        return TokenCounter.count(text, model or self.settings.default_model)
    
    def count_message_tokens(
        self, 
        messages: list[dict[str, str]], 
        model: str | None = None
    ) -> int:
        """Count tokens in messages.
        
        Args:
            messages: Chat messages
            model: Model for tokenizer selection
            
        Returns:
            Token count
        """
        return TokenCounter.count_messages(messages, model or self.settings.default_model)
