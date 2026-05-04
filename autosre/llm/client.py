"""
LLM Client — Unified interface for Anthropic and OpenAI.

Simple client that supports:
- Text completion
- Structured output (via JSON parsing)
- Automatic provider fallback

No LangChain dependency - direct API calls.
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Optional, Type, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMResponse(BaseModel):
    """Standard response from LLM."""
    
    content: str
    model: str
    provider: str
    usage: dict[str, int] = {}
    raw_response: Optional[dict[str, Any]] = None


class BaseLLMClient(ABC):
    """Abstract base for LLM clients."""
    
    provider: str = "base"
    
    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate completion for a prompt."""
        pass
    
    async def complete_structured(
        self,
        prompt: str,
        output_type: Type[T],
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> T:
        """Generate structured output matching a Pydantic model.
        
        Uses JSON mode and parses response into the output_type.
        """
        # Build system prompt with schema
        schema_json = json.dumps(output_type.model_json_schema(), indent=2)
        structured_system = f"""{system}

IMPORTANT: Respond with valid JSON matching this schema:
{schema_json}

Do not include any text before or after the JSON."""

        response = await self.complete(
            prompt=prompt,
            system=structured_system,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )
        
        # Parse response as JSON
        content = response.content.strip()
        
        # Handle markdown code blocks
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        try:
            data = json.loads(content)
            return output_type.model_validate(data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}\nContent: {content[:500]}")
            raise ValueError(f"LLM did not return valid JSON: {e}")


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude client."""
    
    provider = "anthropic"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
    ):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
    
    async def complete(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate completion using Anthropic API."""
        try:
            import anthropic
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")
        
        client = anthropic.AsyncAnthropic(api_key=self.api_key)
        
        messages = [{"role": "user", "content": prompt}]
        
        try:
            response = await client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system if system else anthropic.NOT_GIVEN,
                messages=messages,
            )
            
            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text
            
            return LLMResponse(
                content=content,
                model=self.model,
                provider=self.provider,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
            )
            
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise


class OpenAIClient(BaseLLMClient):
    """OpenAI GPT client."""
    
    provider = "openai"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o",
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")
    
    async def complete(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate completion using OpenAI API."""
        try:
            import openai
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")
        
        client = openai.AsyncOpenAI(api_key=self.api_key)
        
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = await client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=messages,
            )
            
            content = response.choices[0].message.content or ""
            
            return LLMResponse(
                content=content,
                model=self.model,
                provider=self.provider,
                usage={
                    "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "output_tokens": response.usage.completion_tokens if response.usage else 0,
                },
            )
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise


class FallbackLLMClient(BaseLLMClient):
    """LLM client with automatic fallback between providers."""
    
    provider = "fallback"
    
    def __init__(
        self,
        primary: Optional[BaseLLMClient] = None,
        fallback: Optional[BaseLLMClient] = None,
    ):
        self.primary = primary
        self.fallback = fallback
        self._active: Optional[BaseLLMClient] = None
    
    def _get_client(self) -> BaseLLMClient:
        """Get the first available client."""
        if self.primary:
            return self.primary
        if self.fallback:
            return self.fallback
        raise ValueError("No LLM clients configured")
    
    async def complete(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> LLMResponse:
        """Complete with automatic fallback."""
        errors = []
        
        # Try primary
        if self.primary:
            try:
                response = await self.primary.complete(
                    prompt=prompt,
                    system=system,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs,
                )
                self._active = self.primary
                return response
            except Exception as e:
                logger.warning(f"Primary LLM failed, trying fallback: {e}")
                errors.append(f"primary ({self.primary.provider}): {e}")
        
        # Try fallback
        if self.fallback:
            try:
                response = await self.fallback.complete(
                    prompt=prompt,
                    system=system,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs,
                )
                self._active = self.fallback
                return response
            except Exception as e:
                errors.append(f"fallback ({self.fallback.provider}): {e}")
        
        raise RuntimeError(f"All LLM providers failed: {errors}")


# ----- Factory functions -----

_default_client: Optional[BaseLLMClient] = None


def create_client(
    provider: str = "anthropic",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> BaseLLMClient:
    """Create an LLM client for the specified provider.
    
    Args:
        provider: "anthropic" or "openai"
        model: Model name (uses provider default if None)
        api_key: API key (uses environment variable if None)
        
    Returns:
        Configured LLM client.
    """
    if provider == "anthropic":
        return AnthropicClient(
            api_key=api_key,
            model=model or "claude-sonnet-4-20250514",
        )
    elif provider == "openai":
        return OpenAIClient(
            api_key=api_key,
            model=model or "gpt-4o",
        )
    else:
        raise ValueError(f"Unknown provider: {provider}")


def create_client_with_fallback(
    primary_provider: str = "anthropic",
    primary_model: Optional[str] = None,
    fallback_provider: str = "openai",
    fallback_model: Optional[str] = None,
) -> FallbackLLMClient:
    """Create a client with automatic fallback.
    
    Tries to create both primary and fallback clients.
    If one fails (e.g., missing API key), continues with the other.
    """
    primary: Optional[BaseLLMClient] = None
    fallback: Optional[BaseLLMClient] = None
    
    try:
        primary = create_client(primary_provider, primary_model)
    except ValueError as e:
        logger.warning(f"Could not create primary client: {e}")
    
    try:
        fallback = create_client(fallback_provider, fallback_model)
    except ValueError as e:
        logger.warning(f"Could not create fallback client: {e}")
    
    if not primary and not fallback:
        raise ValueError("No LLM clients could be created. Set ANTHROPIC_API_KEY or OPENAI_API_KEY.")
    
    return FallbackLLMClient(primary=primary, fallback=fallback)


def get_llm_client() -> BaseLLMClient:
    """Get the default LLM client (creates one if needed)."""
    global _default_client
    if _default_client is None:
        _default_client = create_client_with_fallback()
    return _default_client


def set_llm_client(client: BaseLLMClient) -> None:
    """Set the default LLM client."""
    global _default_client
    _default_client = client
