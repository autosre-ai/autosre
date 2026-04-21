"""
Tests for the enhanced LLM adapter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opensre_core.adapters.llm import (
    LLMAdapter,
    LLMProvider,
    LLMResponse,
    LRUCache,
    RetryConfig,
    create_llm_adapter,
    with_retry,
)


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_tokens_used_property(self):
        """Test tokens_used returns sum of input and output tokens."""
        response = LLMResponse(
            content="test",
            model="test-model",
            provider="test",
            input_tokens=100,
            output_tokens=50,
        )
        assert response.tokens_used == 150

    def test_tokens_used_with_zero_tokens(self):
        """Test tokens_used with default zero values."""
        response = LLMResponse(
            content="test",
            model="test-model",
            provider="test",
        )
        assert response.tokens_used == 0

    def test_cached_default_false(self):
        """Test cached defaults to False."""
        response = LLMResponse(
            content="test",
            model="test-model",
            provider="test",
        )
        assert response.cached is False


class TestLLMProvider:
    """Tests for LLMProvider enum."""

    def test_provider_values(self):
        """Test all provider values exist."""
        assert LLMProvider.OLLAMA.value == "ollama"
        assert LLMProvider.OPENAI.value == "openai"
        assert LLMProvider.ANTHROPIC.value == "anthropic"
        assert LLMProvider.AZURE.value == "azure"

    def test_provider_from_string(self):
        """Test creating provider from string."""
        assert LLMProvider("ollama") == LLMProvider.OLLAMA
        assert LLMProvider("openai") == LLMProvider.OPENAI
        assert LLMProvider("anthropic") == LLMProvider.ANTHROPIC
        assert LLMProvider("azure") == LLMProvider.AZURE


class TestRetryConfig:
    """Tests for RetryConfig dataclass."""

    def test_default_values(self):
        """Test default retry configuration."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.backoff_factor == 2.0
        assert config.max_wait == 30.0
        assert ConnectionError in config.retryable_errors
        assert TimeoutError in config.retryable_errors

    def test_custom_values(self):
        """Test custom retry configuration."""
        config = RetryConfig(max_retries=5, backoff_factor=1.5, max_wait=60.0)
        assert config.max_retries == 5
        assert config.backoff_factor == 1.5
        assert config.max_wait == 60.0


class TestWithRetry:
    """Tests for the with_retry decorator."""

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self):
        """Test retry happens on ConnectionError."""
        call_count = 0

        @with_retry(RetryConfig(max_retries=3, backoff_factor=0.01))
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection failed")
            return "success"

        result = await flaky_func()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_value_error(self):
        """Test no retry on non-retryable errors."""
        call_count = 0

        @with_retry(RetryConfig(max_retries=3, backoff_factor=0.01))
        async def bad_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Bad value")

        with pytest.raises(ValueError):
            await bad_func()

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self):
        """Test exception raised when all retries exhausted."""
        config = RetryConfig(max_retries=3, backoff_factor=0.01)

        @with_retry(config)
        async def always_fails():
            raise ConnectionError("Always fails")

        with pytest.raises(ConnectionError):
            await always_fails()


class TestLRUCache:
    """Tests for the LRU cache implementation."""

    def test_cache_set_and_get(self):
        """Test basic cache set and get."""
        cache = LRUCache(max_size=10, ttl_seconds=3600)
        response = LLMResponse(content="cached", model="test", provider="test")

        cache.set("prompt", "system", 0.7, response)
        result = cache.get("prompt", "system", 0.7)

        assert result is not None
        assert result.content == "cached"

    def test_cache_miss(self):
        """Test cache miss returns None."""
        cache = LRUCache(max_size=10, ttl_seconds=3600)
        result = cache.get("missing", "system", 0.7)
        assert result is None

    def test_cache_key_differs_by_prompt(self):
        """Test different prompts have different cache keys."""
        cache = LRUCache(max_size=10, ttl_seconds=3600)
        response1 = LLMResponse(content="response1", model="test", provider="test")
        response2 = LLMResponse(content="response2", model="test", provider="test")

        cache.set("prompt1", "system", 0.7, response1)
        cache.set("prompt2", "system", 0.7, response2)

        assert cache.get("prompt1", "system", 0.7).content == "response1"
        assert cache.get("prompt2", "system", 0.7).content == "response2"

    def test_cache_key_differs_by_temperature(self):
        """Test different temperatures have different cache keys."""
        cache = LRUCache(max_size=10, ttl_seconds=3600)
        response1 = LLMResponse(content="temp_0.5", model="test", provider="test")
        response2 = LLMResponse(content="temp_0.9", model="test", provider="test")

        cache.set("prompt", "system", 0.5, response1)
        cache.set("prompt", "system", 0.9, response2)

        assert cache.get("prompt", "system", 0.5).content == "temp_0.5"
        assert cache.get("prompt", "system", 0.9).content == "temp_0.9"

    def test_cache_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = LRUCache(max_size=2, ttl_seconds=3600)

        for i in range(3):
            response = LLMResponse(content=f"response{i}", model="test", provider="test")
            cache.set(f"prompt{i}", "system", 0.7, response)

        # First item should be evicted
        assert cache.get("prompt0", "system", 0.7) is None
        assert cache.get("prompt1", "system", 0.7) is not None
        assert cache.get("prompt2", "system", 0.7) is not None

    def test_cache_clear(self):
        """Test cache clear removes all entries."""
        cache = LRUCache(max_size=10, ttl_seconds=3600)
        response = LLMResponse(content="cached", model="test", provider="test")

        cache.set("prompt", "system", 0.7, response)
        cache.clear()

        assert cache.get("prompt", "system", 0.7) is None


class TestLLMAdapter:
    """Tests for the LLMAdapter class."""

    def test_adapter_creation_default_provider(self):
        """Test adapter creation with default provider."""
        with patch("opensre_core.adapters.llm.settings") as mock_settings:
            mock_settings.llm_provider = "ollama"
            adapter = LLMAdapter()
            assert adapter.provider == LLMProvider.OLLAMA

    def test_adapter_creation_with_provider(self):
        """Test adapter creation with explicit provider."""
        adapter = LLMAdapter(provider="openai")
        assert adapter.provider == LLMProvider.OPENAI

    def test_adapter_cache_disabled(self):
        """Test adapter with cache disabled."""
        adapter = LLMAdapter(cache_enabled=False)
        assert adapter._cache_enabled is False

    def test_adapter_custom_retry_config(self):
        """Test adapter with custom retry config."""
        config = RetryConfig(max_retries=5)
        adapter = LLMAdapter(retry_config=config)
        assert adapter._retry_config.max_retries == 5

    @pytest.mark.asyncio
    async def test_generate_uses_cache(self):
        """Test generate uses cache when available."""
        adapter = LLMAdapter(provider="ollama", cache_enabled=True)

        # Pre-populate cache
        cached_response = LLMResponse(
            content="cached response",
            model="test",
            provider="ollama",
        )
        adapter._cache.set("test prompt", "system prompt", 0.7, cached_response)

        # Should return cached response without calling LLM
        result = await adapter.generate(
            prompt="test prompt",
            system_prompt="system prompt",
            temperature=0.7,
            use_cache=True,
        )

        assert result.content == "cached response"
        assert result.cached is True

    @pytest.mark.asyncio
    async def test_generate_skips_cache_when_disabled(self):
        """Test generate skips cache when use_cache=False."""
        adapter = LLMAdapter(provider="ollama")

        # Pre-populate cache
        cached_response = LLMResponse(
            content="cached response",
            model="test",
            provider="ollama",
        )
        adapter._cache.set("test prompt", "", 0.7, cached_response)

        # Mock the actual generation
        mock_response = LLMResponse(
            content="fresh response",
            model="llama3.1:8b",
            provider="ollama",
        )

        with patch.object(
            adapter, "_generate_with_retry", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = mock_response

            result = await adapter.generate(
                prompt="test prompt",
                use_cache=False,
            )

            assert result.content == "fresh response"
            mock_gen.assert_called_once()

    def test_clear_cache(self):
        """Test clear_cache method."""
        adapter = LLMAdapter()
        response = LLMResponse(content="test", model="test", provider="test")
        adapter._cache.set("prompt", "system", 0.7, response)

        adapter.clear_cache()

        assert adapter._cache.get("prompt", "system", 0.7) is None


class TestLLMAdapterHealthCheck:
    """Tests for LLM adapter health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_ollama_success(self):
        """Test Ollama health check success."""
        adapter = LLMAdapter(provider="ollama")

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "models": [
                    {"name": "llama3.1:8b"},
                    {"name": "mistral:7b"},
                ]
            }
            mock_response.raise_for_status = MagicMock()

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await adapter.health_check()

            assert result["status"] == "healthy"
            assert result["provider"] == "ollama"
            assert "latency_ms" in result

    @pytest.mark.asyncio
    async def test_health_check_openai_no_key(self):
        """Test OpenAI health check without API key."""
        adapter = LLMAdapter(provider="openai")

        with patch("opensre_core.adapters.llm.settings") as mock_settings:
            mock_settings.openai_api_key = None

            result = await adapter.health_check()

            assert result["status"] == "error"
            assert "not configured" in result["details"]


class TestFactoryFunctions:
    """Tests for factory and convenience functions."""

    def test_create_llm_adapter(self):
        """Test create_llm_adapter factory function."""
        adapter = create_llm_adapter(provider="anthropic")
        assert adapter.provider == LLMProvider.ANTHROPIC

    def test_create_llm_adapter_with_kwargs(self):
        """Test create_llm_adapter with additional kwargs."""
        adapter = create_llm_adapter(
            provider="openai",
            cache_enabled=False,
            cache_max_size=50,
        )
        assert adapter.provider == LLMProvider.OPENAI
        assert adapter._cache_enabled is False


class TestLLMAdapterOllama:
    """Tests for Ollama-specific functionality."""

    @pytest.mark.asyncio
    async def test_generate_ollama(self):
        """Test Ollama generation."""
        adapter = LLMAdapter(provider="ollama")

        mock_response = {
            "message": {"content": "Hello from Ollama"},
            "prompt_eval_count": 10,
            "eval_count": 20,
            "done_reason": "stop",
        }

        # Mock the internal client directly
        mock_client = AsyncMock()
        mock_client.chat = AsyncMock(return_value=mock_response)
        adapter._ollama_client = mock_client

        with patch("opensre_core.adapters.llm.settings") as mock_settings:
            mock_settings.ollama_model = "llama3.1:8b"

            response = await adapter._generate_ollama(
                prompt="Hello",
                system_prompt="You are helpful",
                temperature=0.7,
                max_tokens=100,
            )

            assert response.content == "Hello from Ollama"
            assert response.provider == "ollama"
            assert response.input_tokens == 10
            assert response.output_tokens == 20


class TestLLMAdapterOpenAI:
    """Tests for OpenAI-specific functionality."""

    @pytest.mark.asyncio
    async def test_generate_openai(self):
        """Test OpenAI generation."""
        adapter = LLMAdapter(provider="openai")

        mock_choice = MagicMock()
        mock_choice.message.content = "Hello from OpenAI"
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 15
        mock_usage.completion_tokens = 25

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        # Mock the internal client directly
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        adapter._openai_client = mock_client

        with patch("opensre_core.adapters.llm.settings") as mock_settings:
            mock_settings.openai_model = "gpt-4o-mini"

            response = await adapter._generate_openai(
                prompt="Hello",
                system_prompt="You are helpful",
                temperature=0.7,
                max_tokens=100,
            )

            assert response.content == "Hello from OpenAI"
            assert response.provider == "openai"
            assert response.input_tokens == 15
            assert response.output_tokens == 25


class TestLLMAdapterAnthropic:
    """Tests for Anthropic-specific functionality."""

    @pytest.mark.asyncio
    async def test_generate_anthropic(self):
        """Test Anthropic generation."""
        adapter = LLMAdapter(provider="anthropic")

        mock_content = MagicMock()
        mock_content.text = "Hello from Claude"

        mock_usage = MagicMock()
        mock_usage.input_tokens = 12
        mock_usage.output_tokens = 18

        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_response.usage = mock_usage
        mock_response.stop_reason = "end_turn"

        # Mock the internal client directly
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        adapter._anthropic_client = mock_client

        with patch("opensre_core.adapters.llm.settings") as mock_settings:
            mock_settings.anthropic_model = "claude-3-sonnet-20240229"

            response = await adapter._generate_anthropic(
                prompt="Hello",
                system_prompt="You are helpful",
                temperature=0.7,
                max_tokens=100,
            )

            assert response.content == "Hello from Claude"
            assert response.provider == "anthropic"
            assert response.input_tokens == 12
            assert response.output_tokens == 18
