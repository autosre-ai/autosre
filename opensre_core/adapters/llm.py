"""
LLM Adapter - Interface with local and cloud LLMs
"""

from dataclasses import dataclass
from typing import Any, AsyncIterator

import httpx
import ollama
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

from opensre_core.config import settings


@dataclass
class LLMResponse:
    """Response from LLM."""
    content: str
    model: str
    tokens_used: int | None = None
    finish_reason: str | None = None


class LLMAdapter:
    """
    Unified adapter for multiple LLM providers.
    
    Supports:
    - Ollama (local, privacy-first)
    - OpenAI (GPT-4)
    - Anthropic (Claude)
    """
    
    def __init__(self, provider: str | None = None):
        self.provider = provider or settings.llm_provider
        self._ollama_client: ollama.AsyncClient | None = None
        self._openai_client: AsyncOpenAI | None = None
        self._anthropic_client: AsyncAnthropic | None = None
    
    async def health_check(self) -> dict[str, Any]:
        """Check LLM connection."""
        if self.provider == "ollama":
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{settings.ollama_host}/api/tags", timeout=5)
                response.raise_for_status()
                models = response.json().get("models", [])
                model_names = [m["name"] for m in models][:3]
                return {
                    "status": "healthy",
                    "details": f"Ollama ({', '.join(model_names)}...)",
                }
        
        elif self.provider == "openai":
            if not settings.openai_api_key:
                raise ValueError("OpenAI API key not configured")
            return {"status": "healthy", "details": f"OpenAI ({settings.openai_model})"}
        
        elif self.provider == "anthropic":
            if not settings.anthropic_api_key:
                raise ValueError("Anthropic API key not configured")
            return {"status": "healthy", "details": f"Anthropic ({settings.anthropic_model})"}
        
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
    
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        """Generate a response from the LLM."""
        if self.provider == "ollama":
            return await self._generate_ollama(prompt, system_prompt, temperature, max_tokens)
        elif self.provider == "openai":
            return await self._generate_openai(prompt, system_prompt, temperature, max_tokens)
        elif self.provider == "anthropic":
            return await self._generate_anthropic(prompt, system_prompt, temperature, max_tokens)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
    
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Generate streaming response from the LLM."""
        if self.provider == "ollama":
            async for chunk in self._stream_ollama(prompt, system_prompt, temperature):
                yield chunk
        elif self.provider == "openai":
            async for chunk in self._stream_openai(prompt, system_prompt, temperature):
                yield chunk
        elif self.provider == "anthropic":
            async for chunk in self._stream_anthropic(prompt, system_prompt, temperature):
                yield chunk
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
    
    # =========================================================================
    # Ollama Implementation
    # =========================================================================
    
    @property
    def ollama_client(self) -> ollama.AsyncClient:
        if self._ollama_client is None:
            self._ollama_client = ollama.AsyncClient(host=settings.ollama_host)
        return self._ollama_client
    
    async def _generate_ollama(
        self,
        prompt: str,
        system_prompt: str | None,
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
        
        return LLMResponse(
            content=response["message"]["content"],
            model=settings.ollama_model,
            tokens_used=response.get("eval_count"),
            finish_reason=response.get("done_reason"),
        )
    
    async def _stream_ollama(
        self,
        prompt: str,
        system_prompt: str | None,
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
    
    @property
    def openai_client(self) -> AsyncOpenAI:
        if self._openai_client is None:
            self._openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._openai_client
    
    async def _generate_openai(
        self,
        prompt: str,
        system_prompt: str | None,
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
        return LLMResponse(
            content=choice.message.content or "",
            model=settings.openai_model,
            tokens_used=response.usage.total_tokens if response.usage else None,
            finish_reason=choice.finish_reason,
        )
    
    async def _stream_openai(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
    ) -> AsyncIterator[str]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        stream = await self.openai_client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    # =========================================================================
    # Anthropic Implementation
    # =========================================================================
    
    @property
    def anthropic_client(self) -> AsyncAnthropic:
        if self._anthropic_client is None:
            self._anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._anthropic_client
    
    async def _generate_anthropic(
        self,
        prompt: str,
        system_prompt: str | None,
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
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
            finish_reason=response.stop_reason,
        )
    
    async def _stream_anthropic(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
    ) -> AsyncIterator[str]:
        async with self.anthropic_client.messages.stream(
            model=settings.anthropic_model,
            max_tokens=2048,
            system=system_prompt or "You are a helpful assistant.",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        ) as stream:
            async for text in stream.text_stream:
                yield text
