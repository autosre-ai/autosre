"""
Enhanced Ollama LLM Client for AutoSRE.

Provides:
- Local LLM inference with Ollama
- Zero API cost, data stays local
- Graceful fallback if Ollama unavailable
- Support for models like Gemma 2B, Llama 3, Mistral
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from autosre.utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class OllamaConnectionStatus(str, Enum):
    """Ollama connection status."""
    
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    CHECKING = "checking"


@dataclass
class OllamaConfig:
    """Ollama configuration."""
    
    base_url: str = "http://localhost:11434"
    model: str = "llama3"  # Default model
    timeout: float = 120.0
    temperature: float = 0.1
    max_tokens: int = 4096
    
    # Fallback settings
    enable_fallback: bool = True
    fallback_provider: str | None = None  # e.g., "openai"
    
    # Health check
    health_check_interval: float = 30.0
    retry_attempts: int = 3
    retry_delay: float = 1.0


@dataclass
class OllamaModel:
    """Information about an available Ollama model."""
    
    name: str
    modified_at: str
    size: int
    digest: str
    details: dict[str, Any]
    
    @property
    def size_gb(self) -> float:
        """Size in GB."""
        return self.size / (1024 ** 3)
    
    @property
    def family(self) -> str:
        """Model family (llama, gemma, mistral, etc)."""
        return self.details.get("family", "unknown")
    
    @property
    def parameter_count(self) -> str:
        """Parameter count string."""
        return self.details.get("parameter_size", "unknown")


class OllamaResponse(BaseModel):
    """Response from Ollama API."""
    
    content: str
    model: str
    done: bool = True
    
    # Token usage (estimated by Ollama)
    prompt_eval_count: int = 0
    eval_count: int = 0
    
    # Timing
    total_duration: int = 0  # nanoseconds
    load_duration: int = 0
    prompt_eval_duration: int = 0
    eval_duration: int = 0
    
    # Raw response
    raw: dict[str, Any] | None = None
    
    @property
    def input_tokens(self) -> int:
        return self.prompt_eval_count
    
    @property
    def output_tokens(self) -> int:
        return self.eval_count
    
    @property
    def latency_ms(self) -> float:
        return self.total_duration / 1_000_000


class OllamaClient:
    """
    Enhanced Ollama client with graceful fallback.
    
    Features:
    - Connection health monitoring
    - Automatic retry on transient failures
    - Graceful fallback to other providers
    - Model listing and management
    - Structured output support
    
    Example:
        >>> client = OllamaClient()
        >>> if await client.is_available():
        ...     response = await client.chat([
        ...         {"role": "user", "content": "Hello!"}
        ...     ])
        ...     print(response.content)
    """
    
    def __init__(self, config: OllamaConfig | None = None):
        self.config = config or OllamaConfig()
        self._status = OllamaConnectionStatus.DISCONNECTED
        self._available_models: list[OllamaModel] = []
        self._last_health_check: datetime | None = None
        self._http_client: httpx.AsyncClient | None = None
        
        # Stats
        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._fallback_requests = 0
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=self.config.timeout,
            )
        return self._http_client
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
    
    async def is_available(self, force_check: bool = False) -> bool:
        """
        Check if Ollama is available and responsive.
        
        Args:
            force_check: Force a new check even if recently checked
            
        Returns:
            True if Ollama is available
        """
        # Use cached result if recent
        if not force_check and self._last_health_check:
            elapsed = (datetime.now(timezone.utc) - self._last_health_check).total_seconds()
            if elapsed < self.config.health_check_interval:
                return self._status == OllamaConnectionStatus.CONNECTED
        
        self._status = OllamaConnectionStatus.CHECKING
        
        try:
            client = await self._get_client()
            response = await client.get("/api/tags", timeout=5.0)
            
            if response.status_code == 200:
                self._status = OllamaConnectionStatus.CONNECTED
                self._last_health_check = datetime.now(timezone.utc)
                
                # Parse available models
                data = response.json()
                self._available_models = [
                    OllamaModel(
                        name=m["name"],
                        modified_at=m.get("modified_at", ""),
                        size=m.get("size", 0),
                        digest=m.get("digest", ""),
                        details=m.get("details", {}),
                    )
                    for m in data.get("models", [])
                ]
                
                logger.info(
                    f"Ollama connected. Available models: "
                    f"{[m.name for m in self._available_models]}"
                )
                return True
            else:
                self._status = OllamaConnectionStatus.ERROR
                logger.warning(f"Ollama health check failed: {response.status_code}")
                return False
                
        except Exception as e:
            self._status = OllamaConnectionStatus.DISCONNECTED
            logger.warning(f"Ollama not available: {e}")
            return False
    
    async def list_models(self) -> list[OllamaModel]:
        """List available Ollama models."""
        await self.is_available(force_check=True)
        return self._available_models
    
    async def has_model(self, model_name: str) -> bool:
        """Check if a specific model is available."""
        models = await self.list_models()
        return any(m.name == model_name or m.name.startswith(model_name) for m in models)
    
    async def pull_model(self, model_name: str) -> bool:
        """
        Pull a model from Ollama registry.
        
        Args:
            model_name: Name of model to pull
            
        Returns:
            True if successful
        """
        try:
            client = await self._get_client()
            
            logger.info(f"Pulling Ollama model: {model_name}")
            
            # Pull is a streaming endpoint
            async with client.stream(
                "POST",
                "/api/pull",
                json={"name": model_name},
                timeout=None,  # No timeout for pull
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        data = json.loads(line)
                        status = data.get("status", "")
                        if "pulling" in status.lower():
                            logger.info(f"Pull progress: {status}")
                        elif "success" in status.lower():
                            logger.info(f"Successfully pulled {model_name}")
                            return True
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to pull model {model_name}: {e}")
            return False
    
    async def _make_request(
        self,
        endpoint: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Make request with retry logic."""
        last_error = None
        
        for attempt in range(self.config.retry_attempts):
            try:
                client = await self._get_client()
                response = await client.post(endpoint, json=payload)
                response.raise_for_status()
                self._successful_requests += 1
                return response.json()
                
            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(f"Ollama timeout (attempt {attempt + 1})")
                
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code >= 500:
                    logger.warning(f"Ollama server error (attempt {attempt + 1}): {e}")
                else:
                    raise  # Don't retry client errors
                    
            except Exception as e:
                last_error = e
                logger.warning(f"Ollama request failed (attempt {attempt + 1}): {e}")
            
            if attempt < self.config.retry_attempts - 1:
                await asyncio.sleep(self.config.retry_delay * (attempt + 1))
        
        self._failed_requests += 1
        raise last_error or Exception("Ollama request failed")
    
    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        system: str | None = None,
        **kwargs: Any,
    ) -> OllamaResponse:
        """
        Generate a completion.
        
        Args:
            prompt: The prompt text
            model: Model to use (defaults to config)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            system: System prompt
            **kwargs: Additional Ollama options
            
        Returns:
            OllamaResponse
        """
        self._total_requests += 1
        
        # Check availability
        if not await self.is_available():
            raise ConnectionError("Ollama is not available")
        
        model = model or self.config.model
        
        # Build options
        options = {
            "temperature": temperature or self.config.temperature,
        }
        if max_tokens:
            options["num_predict"] = max_tokens
        
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "options": options,
            "stream": False,
        }
        
        if system:
            payload["system"] = system
        
        data = await self._make_request("/api/generate", payload)
        
        return OllamaResponse(
            content=data.get("response", ""),
            model=model,
            done=data.get("done", True),
            prompt_eval_count=data.get("prompt_eval_count", 0),
            eval_count=data.get("eval_count", 0),
            total_duration=data.get("total_duration", 0),
            load_duration=data.get("load_duration", 0),
            prompt_eval_duration=data.get("prompt_eval_duration", 0),
            eval_duration=data.get("eval_duration", 0),
            raw=data,
        )
    
    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> OllamaResponse:
        """
        Generate a chat completion.
        
        Args:
            messages: Chat messages [{"role": "user", "content": "..."}]
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            **kwargs: Additional options
            
        Returns:
            OllamaResponse
        """
        self._total_requests += 1
        
        if not await self.is_available():
            raise ConnectionError("Ollama is not available")
        
        model = model or self.config.model
        
        options = {
            "temperature": temperature or self.config.temperature,
        }
        if max_tokens:
            options["num_predict"] = max_tokens
        
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "options": options,
            "stream": False,
        }
        
        data = await self._make_request("/api/chat", payload)
        
        message = data.get("message", {})
        
        return OllamaResponse(
            content=message.get("content", ""),
            model=model,
            done=data.get("done", True),
            prompt_eval_count=data.get("prompt_eval_count", 0),
            eval_count=data.get("eval_count", 0),
            total_duration=data.get("total_duration", 0),
            raw=data,
        )
    
    async def chat_structured(
        self,
        messages: list[dict[str, str]],
        response_model: type[T],
        model: str | None = None,
        temperature: float | None = None,
    ) -> T:
        """
        Generate structured output matching a Pydantic model.
        
        Args:
            messages: Chat messages
            response_model: Pydantic model for response
            model: LLM model to use
            temperature: Sampling temperature
            
        Returns:
            Parsed Pydantic model
        """
        schema = response_model.model_json_schema()
        
        # Add JSON instruction
        json_instruction = {
            "role": "system",
            "content": (
                f"You must respond with valid JSON matching this schema:\n"
                f"```json\n{json.dumps(schema, indent=2)}\n```\n"
                f"Only output the JSON, no other text."
            ),
        }
        
        augmented_messages = [json_instruction] + messages
        
        response = await self.chat(
            messages=augmented_messages,
            model=model,
            temperature=temperature,
        )
        
        # Parse JSON from response
        content = response.content.strip()
        
        # Try to extract JSON if wrapped
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        try:
            data = json.loads(content.strip())
            return response_model(**data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Ollama JSON response: {e}")
            logger.debug(f"Raw content: {content}")
            raise ValueError(f"Invalid JSON response from Ollama: {e}")
    
    @property
    def status(self) -> OllamaConnectionStatus:
        """Get current connection status."""
        return self._status
    
    @property
    def stats(self) -> dict[str, Any]:
        """Get usage statistics."""
        return {
            "status": self._status.value,
            "total_requests": self._total_requests,
            "successful_requests": self._successful_requests,
            "failed_requests": self._failed_requests,
            "fallback_requests": self._fallback_requests,
            "available_models": [m.name for m in self._available_models],
            "last_health_check": self._last_health_check.isoformat() if self._last_health_check else None,
        }


class OllamaWithFallback:
    """
    Ollama client with automatic fallback to other providers.
    
    If Ollama is unavailable, automatically falls back to configured
    provider (OpenAI, Anthropic, etc).
    
    Example:
        >>> client = OllamaWithFallback(
        ...     ollama_config=OllamaConfig(model="llama3"),
        ...     fallback_provider="openai",
        ... )
        >>> response = await client.chat([
        ...     {"role": "user", "content": "Hello!"}
        ... ])
    """
    
    def __init__(
        self,
        ollama_config: OllamaConfig | None = None,
        fallback_provider: str | None = None,
        fallback_model: str | None = None,
        fallback_api_key: str | None = None,
    ):
        self.ollama = OllamaClient(ollama_config)
        self.fallback_provider = fallback_provider or (
            ollama_config.fallback_provider if ollama_config else None
        )
        self.fallback_model = fallback_model
        self.fallback_api_key = fallback_api_key
        
        self._fallback_client: Any = None
        self._using_fallback = False
    
    async def _get_fallback_client(self) -> Any:
        """Get or create fallback client."""
        if self._fallback_client is not None:
            return self._fallback_client
        
        if not self.fallback_provider:
            raise ValueError("No fallback provider configured")
        
        if self.fallback_provider == "openai":
            try:
                from openai import AsyncOpenAI
            except ImportError:
                raise ImportError("openai package required for fallback")
            
            self._fallback_client = AsyncOpenAI(api_key=self.fallback_api_key)
            
        elif self.fallback_provider == "anthropic":
            try:
                from anthropic import AsyncAnthropic
            except ImportError:
                raise ImportError("anthropic package required for fallback")
            
            self._fallback_client = AsyncAnthropic(api_key=self.fallback_api_key)
        else:
            raise ValueError(f"Unknown fallback provider: {self.fallback_provider}")
        
        return self._fallback_client
    
    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> OllamaResponse:
        """
        Chat with automatic fallback.
        
        Tries Ollama first, falls back to configured provider if unavailable.
        """
        # Try Ollama first
        if await self.ollama.is_available():
            try:
                self._using_fallback = False
                return await self.ollama.chat(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
            except Exception as e:
                logger.warning(f"Ollama request failed, trying fallback: {e}")
        
        # Fallback
        if not self.fallback_provider:
            raise ConnectionError(
                "Ollama is not available and no fallback provider configured"
            )
        
        self._using_fallback = True
        self.ollama._fallback_requests += 1
        
        logger.info(f"Using fallback provider: {self.fallback_provider}")
        
        client = await self._get_fallback_client()
        fallback_model = model or self.fallback_model
        
        if self.fallback_provider == "openai":
            response = await client.chat.completions.create(
                model=fallback_model or "gpt-4o-mini",
                messages=messages,
                temperature=temperature or 0.1,
                max_tokens=max_tokens,
            )
            
            return OllamaResponse(
                content=response.choices[0].message.content or "",
                model=response.model,
                prompt_eval_count=response.usage.prompt_tokens if response.usage else 0,
                eval_count=response.usage.completion_tokens if response.usage else 0,
                raw={"provider": "openai", "response": response.model_dump()},
            )
            
        elif self.fallback_provider == "anthropic":
            # Extract system message
            system = None
            chat_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    system = msg["content"]
                else:
                    chat_messages.append(msg)
            
            response = await client.messages.create(
                model=fallback_model or "claude-3-haiku-20240307",
                messages=chat_messages,
                system=system,
                temperature=temperature or 0.1,
                max_tokens=max_tokens or 4096,
            )
            
            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text
            
            return OllamaResponse(
                content=content,
                model=response.model,
                prompt_eval_count=response.usage.input_tokens,
                eval_count=response.usage.output_tokens,
                raw={"provider": "anthropic", "response": response.model_dump()},
            )
        
        raise ValueError(f"Unknown fallback provider: {self.fallback_provider}")
    
    @property
    def using_fallback(self) -> bool:
        """Check if currently using fallback provider."""
        return self._using_fallback
    
    async def close(self) -> None:
        """Close all clients."""
        await self.ollama.close()


# Recommended local models for SRE tasks
RECOMMENDED_MODELS = {
    "llama3": {
        "name": "llama3:8b",
        "description": "Meta's Llama 3 8B - Good balance of speed and quality",
        "size_gb": 4.7,
        "recommended_ram_gb": 8,
    },
    "llama3:70b": {
        "name": "llama3:70b",
        "description": "Meta's Llama 3 70B - Best quality, requires significant RAM",
        "size_gb": 40,
        "recommended_ram_gb": 64,
    },
    "mistral": {
        "name": "mistral:7b",
        "description": "Mistral 7B - Fast and efficient",
        "size_gb": 4.1,
        "recommended_ram_gb": 8,
    },
    "gemma2": {
        "name": "gemma2:2b",
        "description": "Google Gemma 2B - Lightweight, good for simple tasks",
        "size_gb": 1.6,
        "recommended_ram_gb": 4,
    },
    "gemma2:9b": {
        "name": "gemma2:9b",
        "description": "Google Gemma 9B - Good quality for medium tasks",
        "size_gb": 5.5,
        "recommended_ram_gb": 12,
    },
    "codellama": {
        "name": "codellama:7b",
        "description": "Code Llama 7B - Specialized for code tasks",
        "size_gb": 3.8,
        "recommended_ram_gb": 8,
    },
    "phi3": {
        "name": "phi3:mini",
        "description": "Microsoft Phi-3 Mini - Compact but capable",
        "size_gb": 2.3,
        "recommended_ram_gb": 4,
    },
    "qwen2": {
        "name": "qwen2:7b",
        "description": "Alibaba Qwen2 7B - Strong multilingual support",
        "size_gb": 4.4,
        "recommended_ram_gb": 8,
    },
}


def get_recommended_model(available_ram_gb: float = 8.0) -> str:
    """
    Get recommended model based on available RAM.
    
    Args:
        available_ram_gb: Available RAM in GB
        
    Returns:
        Recommended model name
    """
    suitable = [
        (name, info) for name, info in RECOMMENDED_MODELS.items()
        if info["recommended_ram_gb"] <= available_ram_gb
    ]
    
    if not suitable:
        return "gemma2:2b"  # Smallest option
    
    # Prefer llama3 if available
    for name, _ in suitable:
        if name == "llama3":
            return "llama3:8b"
    
    # Otherwise, pick largest that fits
    suitable.sort(key=lambda x: x[1]["recommended_ram_gb"], reverse=True)
    return suitable[0][1]["name"]
