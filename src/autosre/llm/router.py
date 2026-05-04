"""
LLM Router

Routes LLM requests to appropriate providers based on task type,
cost, and availability.
"""
from typing import Optional, List, Dict, Any
from enum import Enum, auto
from dataclasses import dataclass


class LLMProvider(Enum):
    """Supported LLM providers."""
    OLLAMA = auto()
    ANTHROPIC = auto()
    OPENAI = auto()


class TaskType(Enum):
    """Types of LLM tasks for routing decisions."""
    ANALYSIS = auto()      # Analyzing metrics/logs
    PLANNING = auto()      # Planning investigation steps
    SYNTHESIS = auto()     # Synthesizing findings
    WRITEUP = auto()       # Generating reports
    EMBEDDING = auto()     # Creating embeddings


@dataclass
class LLMConfig:
    """Configuration for an LLM provider."""
    provider: LLMProvider
    model: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.7


@dataclass
class LLMResponse:
    """Response from an LLM call."""
    content: str
    model: str
    provider: LLMProvider
    usage: Dict[str, int]
    metadata: Dict[str, Any]


class LLMRouter:
    """
    Routes LLM requests to appropriate providers.
    
    Features:
    - Provider abstraction
    - Task-based routing
    - Fallback handling
    - Cost optimization
    """
    
    def __init__(self, configs: Optional[List[LLMConfig]] = None):
        self.configs = configs or []
        self._provider_map: Dict[LLMProvider, LLMConfig] = {}
        self._task_routing: Dict[TaskType, LLMProvider] = {}
        
        for config in self.configs:
            self._provider_map[config.provider] = config
    
    def set_task_routing(self, task: TaskType, provider: LLMProvider):
        """Configure which provider handles which task type."""
        self._task_routing[task] = provider
    
    async def complete(
        self,
        prompt: str,
        task: TaskType = TaskType.ANALYSIS,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        """Send a completion request to the appropriate provider."""
        provider = self._task_routing.get(task)
        if not provider:
            provider = self._get_default_provider()
        
        config = self._provider_map.get(provider)
        if not config:
            raise ValueError(f"No configuration for provider {provider}")
        
        return await self._call_provider(config, prompt, system_prompt, **kwargs)
    
    async def embed(self, text: str) -> List[float]:
        """Generate embeddings for text."""
        # TODO: Implement embedding
        return []
    
    def _get_default_provider(self) -> LLMProvider:
        """Get the default provider."""
        if self._provider_map:
            return next(iter(self._provider_map.keys()))
        return LLMProvider.OLLAMA
    
    async def _call_provider(
        self,
        config: LLMConfig,
        prompt: str,
        system_prompt: Optional[str],
        **kwargs,
    ) -> LLMResponse:
        """Call a specific LLM provider."""
        if config.provider == LLMProvider.OLLAMA:
            return await self._call_ollama(config, prompt, system_prompt, **kwargs)
        elif config.provider == LLMProvider.ANTHROPIC:
            return await self._call_anthropic(config, prompt, system_prompt, **kwargs)
        elif config.provider == LLMProvider.OPENAI:
            return await self._call_openai(config, prompt, system_prompt, **kwargs)
        else:
            raise ValueError(f"Unknown provider: {config.provider}")
    
    async def _call_ollama(
        self,
        config: LLMConfig,
        prompt: str,
        system_prompt: Optional[str],
        **kwargs,
    ) -> LLMResponse:
        """Call Ollama provider."""
        try:
            import ollama
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = ollama.chat(
                model=config.model,
                messages=messages,
            )
            
            return LLMResponse(
                content=response["message"]["content"],
                model=config.model,
                provider=LLMProvider.OLLAMA,
                usage={},
                metadata=response,
            )
        except ImportError:
            raise RuntimeError("ollama package not installed")
    
    async def _call_anthropic(
        self,
        config: LLMConfig,
        prompt: str,
        system_prompt: Optional[str],
        **kwargs,
    ) -> LLMResponse:
        """Call Anthropic provider."""
        try:
            import anthropic
            
            client = anthropic.Anthropic(api_key=config.api_key)
            
            response = client.messages.create(
                model=config.model,
                max_tokens=config.max_tokens,
                system=system_prompt or "",
                messages=[{"role": "user", "content": prompt}],
            )
            
            return LLMResponse(
                content=response.content[0].text,
                model=config.model,
                provider=LLMProvider.ANTHROPIC,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
                metadata={},
            )
        except ImportError:
            raise RuntimeError("anthropic package not installed")
    
    async def _call_openai(
        self,
        config: LLMConfig,
        prompt: str,
        system_prompt: Optional[str],
        **kwargs,
    ) -> LLMResponse:
        """Call OpenAI provider."""
        try:
            import openai
            
            client = openai.OpenAI(api_key=config.api_key)
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = client.chat.completions.create(
                model=config.model,
                messages=messages,
                max_tokens=config.max_tokens,
            )
            
            return LLMResponse(
                content=response.choices[0].message.content,
                model=config.model,
                provider=LLMProvider.OPENAI,
                usage={
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                },
                metadata={},
            )
        except ImportError:
            raise RuntimeError("openai package not installed")
