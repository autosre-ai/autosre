"""
AutoSRE Agent Configuration

Configuration management for the SRE agent including model settings,
prompt templates, and environment-based configuration loading.
Integrates with LiteLLM for multi-provider LLM support.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import httpx


# ---------------------------------------------------------------------------
# Configuration Data Classes
# ---------------------------------------------------------------------------


@dataclass
class PromptConfig:
    """Prompt configuration for an agent.
    
    Allows customization of agent behavior through prompt engineering.
    """
    system: str = ""
    prefix: str = ""
    suffix: str = ""


@dataclass
class ModelConfig:
    """Model settings for LLM calls.
    
    Used by build_llm() to configure the LangChain ChatOpenAI wrapper
    pointing at LiteLLM proxy.
    """
    name: str = "claude-sonnet-4-20250514"
    temperature: float | None = None  # 0.0-1.0, None = provider default
    max_tokens: int | None = None  # Maximum response tokens
    top_p: float | None = None  # Nucleus sampling (0.0-1.0)


@dataclass
class MemoryConfig:
    """Memory system configuration."""
    enabled: bool = True
    store_all: bool = True  # Store unsuccessful investigations too
    strategy_window: int = 5  # Episodes for strategy generation
    max_similar_episodes: int = 3  # Episodes to prepend to prompt


@dataclass
class SkillsConfig:
    """Skills/tools configuration."""
    enabled: list[str] = field(default_factory=lambda: ["*"])
    disabled: list[str] = field(default_factory=list)


@dataclass
class AgentConfig:
    """Configuration for a single agent (planner, subagent, etc.).
    
    Loaded from team config service or environment variables.
    """
    enabled: bool = True
    name: str = ""
    prompt: PromptConfig = field(default_factory=PromptConfig)
    tools: dict[str, bool] = field(default_factory=dict)
    skills: dict[str, bool] = field(default_factory=dict)
    model: ModelConfig = field(default_factory=ModelConfig)
    max_turns: int | None = None
    sub_agents: dict[str, bool] = field(default_factory=dict)


@dataclass
class TeamConfig:
    """Team-level configuration.
    
    Contains all agent configs, skills settings, memory config,
    and business context loaded from the config service.
    """
    agents: dict[str, AgentConfig] = field(default_factory=dict)
    skills: SkillsConfig = field(default_factory=SkillsConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    business_context: str = ""
    environment_manifest: dict = field(default_factory=dict)
    raw_config: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Environment Configuration
# ---------------------------------------------------------------------------


def get_config_service_url() -> str:
    """Get the config service URL from environment."""
    return os.getenv(
        "CONFIG_SERVICE_URL",
        "http://localhost:8080"
    )


def get_litellm_config() -> dict[str, str]:
    """Get LiteLLM proxy configuration from environment."""
    return {
        "base_url": os.getenv("LITELLM_BASE_URL", "http://localhost:4000/v1"),
        "api_key": os.getenv(
            "LITELLM_API_KEY",
            os.getenv("OPENAI_API_KEY", "sk-placeholder")
        ),
    }


def get_neo4j_config() -> dict[str, str]:
    """Get Neo4j connection configuration from environment."""
    return {
        "uri": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        "user": os.getenv("NEO4J_USER", "neo4j"),
        "password": os.getenv("NEO4J_PASSWORD", ""),
    }


def get_investigation_limits() -> dict[str, int]:
    """Get investigation loop limits from environment."""
    return {
        "max_iterations": int(os.getenv("MAX_ITERATIONS", "3")),
        "max_react_loops": int(os.getenv("SUBAGENT_MAX_REACT_LOOPS", "25")),
    }


# ---------------------------------------------------------------------------
# Config Loading
# ---------------------------------------------------------------------------


def load_team_config() -> TeamConfig:
    """Load team configuration from config service or environment.
    
    Priority:
    1. TEAM_TOKEN env var → Bearer token auth
    2. AUTOSRE_TENANT_ID + AUTOSRE_TEAM_ID → header-based auth
    3. Fall back to defaults if config service unavailable
    
    Returns:
        TeamConfig with agents, skills, memory settings, etc.
    
    Raises:
        RuntimeError: If required auth env vars are missing and no fallback.
    """
    config_url = get_config_service_url()
    team_token = os.getenv("TEAM_TOKEN")
    tenant_id = os.getenv("AUTOSRE_TENANT_ID")
    team_id = os.getenv("AUTOSRE_TEAM_ID")
    
    # Build request headers
    if team_token:
        headers = {"Authorization": f"Bearer {team_token}"}
    elif tenant_id and team_id:
        headers = {"X-Org-Id": tenant_id, "X-Team-Node-Id": team_id}
    else:
        # No auth configured - return defaults
        return _default_team_config()
    
    try:
        url = f"{config_url}/api/v1/config/me/effective"
        resp = httpx.get(url, headers=headers, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        effective = data.get("effective_config", data)
        return _parse_team_config(effective)
    except Exception as e:
        # Log warning and return defaults
        import logging
        logging.getLogger(__name__).warning(
            f"Failed to load team config from {config_url}: {e}. Using defaults."
        )
        return _default_team_config()


def _default_team_config() -> TeamConfig:
    """Build default team configuration when config service is unavailable."""
    default_model = ModelConfig(name=os.getenv("DEFAULT_MODEL", "claude-sonnet-4-20250514"))
    
    return TeamConfig(
        agents={
            "planner": AgentConfig(
                name="planner",
                model=default_model,
            ),
            "investigation": AgentConfig(
                name="investigation",
                model=default_model,
                sub_agents={
                    "kubernetes": True,
                    "metrics": True,
                    "log_analysis": True,
                    "traces": True,
                },
            ),
            "writeup": AgentConfig(
                name="writeup",
                model=default_model,
            ),
        },
        skills=SkillsConfig(enabled=["*"]),
        memory=MemoryConfig(),
    )


def _parse_team_config(data: dict) -> TeamConfig:
    """Parse raw config dict into TeamConfig."""
    agents: dict[str, AgentConfig] = {}
    
    for name, cfg in data.get("agents", {}).items():
        prompt_data = cfg.get("prompt", {})
        model_data = cfg.get("model", {})
        
        agents[name] = AgentConfig(
            enabled=cfg.get("enabled", True),
            name=name,
            prompt=PromptConfig(
                system=prompt_data.get("system", ""),
                prefix=prompt_data.get("prefix", ""),
                suffix=prompt_data.get("suffix", ""),
            ),
            tools={k: bool(v) for k, v in cfg.get("tools", {}).items()},
            skills={k: bool(v) for k, v in cfg.get("skills", {}).items()},
            model=ModelConfig(
                name=model_data.get("name", "claude-sonnet-4-20250514"),
                temperature=model_data.get("temperature"),
                max_tokens=model_data.get("max_tokens"),
                top_p=model_data.get("top_p"),
            ),
            max_turns=cfg.get("max_turns"),
            sub_agents={k: bool(v) for k, v in cfg.get("sub_agents", {}).items()},
        )
    
    skills_data = data.get("skills", {})
    memory_data = data.get("memory", {})
    
    return TeamConfig(
        agents=agents,
        skills=SkillsConfig(
            enabled=skills_data.get("enabled", ["*"]),
            disabled=skills_data.get("disabled", []),
        ),
        memory=MemoryConfig(
            enabled=memory_data.get("enabled", True),
            store_all=memory_data.get("store_all", True),
            strategy_window=memory_data.get("strategy_window", 5),
            max_similar_episodes=memory_data.get("max_similar_episodes", 3),
        ),
        business_context=data.get("business_context", ""),
        environment_manifest=data.get("environment_manifest", {}),
        raw_config=data,
    )


# ---------------------------------------------------------------------------
# LLM Builder
# ---------------------------------------------------------------------------


def build_llm(agent_config: AgentConfig) -> Any:
    """Build a LangChain ChatOpenAI instance pointing at LiteLLM proxy.
    
    Uses the agent's model config (name, temperature, max_tokens, top_p).
    LiteLLM proxy handles routing to the actual provider (OpenAI, Anthropic, etc).
    
    Args:
        agent_config: Agent configuration with model settings.
        
    Returns:
        ChatOpenAI instance configured for the agent.
    """
    from langchain_openai import ChatOpenAI
    
    litellm_config = get_litellm_config()
    
    kwargs: dict[str, Any] = {
        "base_url": litellm_config["base_url"],
        "api_key": litellm_config["api_key"],
        "model": agent_config.model.name,
    }
    
    if agent_config.model.temperature is not None:
        kwargs["temperature"] = agent_config.model.temperature
    if agent_config.model.max_tokens is not None:
        kwargs["max_tokens"] = agent_config.model.max_tokens
    if agent_config.model.top_p is not None:
        kwargs["top_p"] = agent_config.model.top_p
    
    return ChatOpenAI(**kwargs)


def build_prompt_config(raw: dict) -> PromptConfig:
    """Build PromptConfig from raw dict."""
    prompt_data = raw.get("prompt", {})
    return PromptConfig(
        system=prompt_data.get("system", ""),
        prefix=prompt_data.get("prefix", ""),
        suffix=prompt_data.get("suffix", ""),
    )


def build_model_config(raw: dict) -> ModelConfig:
    """Build ModelConfig from raw dict."""
    model_data = raw.get("model", {})
    return ModelConfig(
        name=model_data.get("name", "claude-sonnet-4-20250514"),
        temperature=model_data.get("temperature"),
        max_tokens=model_data.get("max_tokens"),
        top_p=model_data.get("top_p"),
    )


def get_agent_config(name: str, team_config: TeamConfig) -> AgentConfig:
    """Get agent config by name, falling back to defaults."""
    if name in team_config.agents:
        return team_config.agents[name]
    
    # Return default config
    return AgentConfig(
        name=name,
        model=ModelConfig(),
    )


def get_available_subagents(team_config: TeamConfig) -> list[str]:
    """Get list of enabled investigation subagents from config.
    
    Checks the 'investigation' agent's sub_agents field and returns
    the names of enabled subagents.
    """
    investigation_config = team_config.agents.get("investigation")
    if not investigation_config:
        return ["kubernetes", "metrics", "log_analysis", "traces"]
    
    sub_agents = investigation_config.sub_agents
    if not sub_agents:
        return ["kubernetes", "metrics", "log_analysis", "traces"]
    
    # Normalize aliases
    alias_map = {"k8s": "kubernetes", "logs": "log_analysis"}
    enabled = [alias_map.get(name, name) for name, is_enabled in sub_agents.items() if is_enabled]
    
    # Deduplicate while preserving order
    seen: set[str] = set()
    return [a for a in enabled if a not in seen and not seen.add(a)]
