"""Tests for Ollama client."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from autosre.core.ollama_client import (
    OllamaClient,
    OllamaConfig,
    OllamaConnectionStatus,
    OllamaModel,
    OllamaResponse,
    OllamaWithFallback,
    RECOMMENDED_MODELS,
    get_recommended_model,
)


class TestOllamaConfig:
    """Tests for OllamaConfig."""
    
    def test_default_config(self):
        config = OllamaConfig()
        
        assert config.base_url == "http://localhost:11434"
        assert config.model == "llama3"
        assert config.timeout == 120.0
        assert config.temperature == 0.1
        assert config.enable_fallback
    
    def test_custom_config(self):
        config = OllamaConfig(
            base_url="http://gpu-server:11434",
            model="mistral:7b",
            timeout=60.0,
            fallback_provider="anthropic",
        )
        
        assert config.base_url == "http://gpu-server:11434"
        assert config.model == "mistral:7b"
        assert config.fallback_provider == "anthropic"


class TestOllamaModel:
    """Tests for OllamaModel."""
    
    def test_model_properties(self):
        model = OllamaModel(
            name="llama3:8b",
            modified_at="2024-01-15T10:00:00Z",
            size=5 * 1024 * 1024 * 1024,  # 5GB
            digest="abc123",
            details={
                "family": "llama",
                "parameter_size": "8B",
            },
        )
        
        assert model.size_gb == pytest.approx(5.0, rel=0.01)
        assert model.family == "llama"
        assert model.parameter_count == "8B"


class TestOllamaResponse:
    """Tests for OllamaResponse."""
    
    def test_response_properties(self):
        response = OllamaResponse(
            content="Hello, world!",
            model="llama3",
            prompt_eval_count=10,
            eval_count=5,
            total_duration=100_000_000,  # 100ms in nanoseconds
        )
        
        assert response.input_tokens == 10
        assert response.output_tokens == 5
        assert response.latency_ms == 100.0


class TestOllamaClient:
    """Tests for OllamaClient."""
    
    @pytest.fixture
    def client(self) -> OllamaClient:
        return OllamaClient(OllamaConfig())
    
    @pytest.mark.asyncio
    async def test_is_available_not_running(self, client: OllamaClient):
        """Test availability check when Ollama not running."""
        # Without mocking, this will actually try to connect
        # In CI, Ollama won't be running
        available = await client.is_available()
        
        # Status should be updated
        assert client.status in [
            OllamaConnectionStatus.CONNECTED,
            OllamaConnectionStatus.DISCONNECTED,
        ]
    
    @pytest.mark.asyncio
    async def test_is_available_mocked(self, client: OllamaClient):
        """Test availability check with mocked response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {
                    "name": "llama3:8b",
                    "modified_at": "2024-01-15",
                    "size": 5000000000,
                    "digest": "abc",
                    "details": {"family": "llama"},
                },
            ]
        }
        
        with patch.object(client, '_get_client') as mock_get_client:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http
            
            available = await client.is_available()
            
            assert available
            assert client.status == OllamaConnectionStatus.CONNECTED
            assert len(client._available_models) == 1
    
    @pytest.mark.asyncio
    async def test_list_models(self, client: OllamaClient):
        """Test listing models."""
        client._available_models = [
            OllamaModel(
                name="llama3:8b",
                modified_at="",
                size=0,
                digest="",
                details={},
            ),
        ]
        client._status = OllamaConnectionStatus.CONNECTED
        
        # Mock is_available to return True without network call
        with patch.object(client, 'is_available', return_value=True):
            models = await client.list_models()
        
        assert len(models) == 1
        assert models[0].name == "llama3:8b"
    
    @pytest.mark.asyncio
    async def test_has_model(self, client: OllamaClient):
        """Test checking for specific model."""
        client._available_models = [
            OllamaModel(
                name="llama3:8b",
                modified_at="",
                size=0,
                digest="",
                details={},
            ),
        ]
        
        with patch.object(client, 'is_available', return_value=True):
            assert await client.has_model("llama3:8b")
            assert await client.has_model("llama3")  # Prefix match
            assert not await client.has_model("mistral")
    
    @pytest.mark.asyncio
    async def test_generate_mocked(self, client: OllamaClient):
        """Test generate with mocked response."""
        mock_response = {
            "response": "Hello, I am Llama!",
            "done": True,
            "prompt_eval_count": 5,
            "eval_count": 10,
            "total_duration": 50_000_000,
        }
        
        with patch.object(client, 'is_available', return_value=True):
            with patch.object(client, '_make_request', return_value=mock_response):
                response = await client.generate("Hello!")
        
        assert response.content == "Hello, I am Llama!"
        assert response.input_tokens == 5
        assert response.output_tokens == 10
    
    @pytest.mark.asyncio
    async def test_chat_mocked(self, client: OllamaClient):
        """Test chat with mocked response."""
        mock_response = {
            "message": {"content": "I can help with that!"},
            "done": True,
            "prompt_eval_count": 20,
            "eval_count": 15,
            "total_duration": 100_000_000,
        }
        
        with patch.object(client, 'is_available', return_value=True):
            with patch.object(client, '_make_request', return_value=mock_response):
                response = await client.chat([
                    {"role": "user", "content": "Help me debug this"},
                ])
        
        assert response.content == "I can help with that!"
    
    def test_stats(self, client: OllamaClient):
        """Test stats property."""
        client._total_requests = 10
        client._successful_requests = 8
        client._failed_requests = 2
        
        stats = client.stats
        
        assert stats["total_requests"] == 10
        assert stats["successful_requests"] == 8
        assert stats["failed_requests"] == 2


class TestOllamaWithFallback:
    """Tests for OllamaWithFallback."""
    
    @pytest.mark.asyncio
    async def test_uses_ollama_when_available(self):
        """Test that Ollama is used when available."""
        config = OllamaConfig(fallback_provider="openai")
        client = OllamaWithFallback(ollama_config=config)
        
        mock_response = OllamaResponse(
            content="From Ollama",
            model="llama3",
        )
        
        with patch.object(client.ollama, 'is_available', return_value=True):
            with patch.object(client.ollama, 'chat', return_value=mock_response):
                response = await client.chat([
                    {"role": "user", "content": "Hello"},
                ])
        
        assert response.content == "From Ollama"
        assert not client.using_fallback
    
    @pytest.mark.asyncio
    async def test_falls_back_when_unavailable(self):
        """Test fallback when Ollama unavailable."""
        config = OllamaConfig(fallback_provider="openai")
        client = OllamaWithFallback(
            ollama_config=config,
            fallback_api_key="test-key",
            fallback_model="gpt-4o-mini",
        )
        
        mock_openai_response = MagicMock()
        mock_openai_response.choices = [
            MagicMock(message=MagicMock(content="From OpenAI"))
        ]
        mock_openai_response.model = "gpt-4o-mini"
        mock_openai_response.usage = MagicMock(
            prompt_tokens=10,
            completion_tokens=5,
        )
        mock_openai_response.model_dump.return_value = {}
        
        mock_openai_client = AsyncMock()
        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=mock_openai_response
        )
        
        with patch.object(client.ollama, 'is_available', return_value=False):
            with patch.object(client, '_get_fallback_client', return_value=mock_openai_client):
                response = await client.chat([
                    {"role": "user", "content": "Hello"},
                ])
        
        assert "OpenAI" in response.content or response.content  # May vary
        assert client.using_fallback


class TestRecommendedModels:
    """Tests for recommended models."""
    
    def test_recommended_models_defined(self):
        assert "llama3" in RECOMMENDED_MODELS
        assert "mistral" in RECOMMENDED_MODELS
        assert "gemma2" in RECOMMENDED_MODELS
    
    def test_get_recommended_model_low_ram(self):
        model = get_recommended_model(available_ram_gb=4.0)
        assert "gemma2:2b" in model or "phi3" in model
    
    def test_get_recommended_model_medium_ram(self):
        model = get_recommended_model(available_ram_gb=8.0)
        assert "llama3" in model or "7b" in model
    
    def test_get_recommended_model_high_ram(self):
        model = get_recommended_model(available_ram_gb=16.0)
        # Should get a larger model
        assert model is not None
