"""
Tests for LLM provider factory and configuration management.
"""

import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any

from campfire.llm.factory import (
    ProviderType,
    ProviderConfig,
    create_provider,
    get_available_providers,
    create_best_available_provider,
    auto_detect_provider,
)
from campfire.llm.base import ModelNotAvailableError


class TestProviderType:
    """Test ProviderType enumeration."""
    
    def test_provider_types(self):
        """Test that all expected provider types exist."""
        assert ProviderType.VLLM.value == "vllm"
        assert ProviderType.OLLAMA.value == "ollama"
        assert ProviderType.LMSTUDIO.value == "lmstudio"


class TestProviderConfig:
    """Test ProviderConfig class."""
    
    def test_init(self):
        """Test ProviderConfig initialization."""
        config = ProviderConfig(
            ProviderType.VLLM,
            model_name="test-model",
            tensor_parallel_size=2,
            gpu_memory_utilization=0.8
        )
        
        assert config.provider_type == ProviderType.VLLM
        assert config.model_name == "test-model"
        assert config.config["tensor_parallel_size"] == 2
        assert config.config["gpu_memory_utilization"] == 0.8
    
    def test_from_dict_valid(self):
        """Test creating ProviderConfig from valid dictionary."""
        config_dict = {
            "provider": "vllm",
            "model_name": "gpt-oss-20b",
            "tensor_parallel_size": 4,
            "gpu_memory_utilization": 0.9
        }
        
        config = ProviderConfig.from_dict(config_dict)
        
        assert config.provider_type == ProviderType.VLLM
        assert config.model_name == "gpt-oss-20b"
        assert config.config["tensor_parallel_size"] == 4
        assert config.config["gpu_memory_utilization"] == 0.9
    
    def test_from_dict_unknown_provider(self):
        """Test creating ProviderConfig with unknown provider type."""
        config_dict = {
            "provider": "unknown_provider",
            "model_name": "test-model"
        }
        
        config = ProviderConfig.from_dict(config_dict)
        
        # Should default to OLLAMA
        assert config.provider_type == ProviderType.OLLAMA
        assert config.model_name == "test-model"
    
    def test_from_dict_defaults(self):
        """Test creating ProviderConfig with minimal dictionary."""
        config_dict = {}
        
        config = ProviderConfig.from_dict(config_dict)
        
        assert config.provider_type == ProviderType.OLLAMA
        assert config.model_name == "gpt-oss-20b"
        assert config.config == {}


class TestCreateProvider:
    """Test create_provider function."""
    
    @patch('campfire.llm.factory.VLLMProvider')
    def test_create_vllm_provider(self, mock_vllm_class):
        """Test creating vLLM provider."""
        mock_provider = Mock()
        mock_provider.is_available.return_value = True
        mock_vllm_class.return_value = mock_provider
        
        config = ProviderConfig(
            ProviderType.VLLM,
            model_name="test-model",
            tensor_parallel_size=2
        )
        
        result = create_provider(config)
        
        assert result is mock_provider
        mock_vllm_class.assert_called_once_with(
            model_name="test-model",
            tensor_parallel_size=2
        )
        mock_provider.is_available.assert_called_once()
    
    @patch('campfire.llm.factory.OllamaProvider')
    def test_create_ollama_provider(self, mock_ollama_class):
        """Test creating Ollama provider."""
        mock_provider = Mock()
        mock_provider.is_available.return_value = True
        mock_ollama_class.return_value = mock_provider
        
        config = ProviderConfig(
            ProviderType.OLLAMA,
            model_name="test-model",
            base_url="http://localhost:11434"
        )
        
        result = create_provider(config)
        
        assert result is mock_provider
        mock_ollama_class.assert_called_once_with(
            model_name="test-model",
            base_url="http://localhost:11434"
        )
    
    @patch('campfire.llm.factory.LMStudioProvider')
    def test_create_lmstudio_provider(self, mock_lmstudio_class):
        """Test creating LM Studio provider."""
        mock_provider = Mock()
        mock_provider.is_available.return_value = True
        mock_lmstudio_class.return_value = mock_provider
        
        config = ProviderConfig(
            ProviderType.LMSTUDIO,
            model_name="test-model"
        )
        
        result = create_provider(config)
        
        assert result is mock_provider
        mock_lmstudio_class.assert_called_once_with(model_name="test-model")
    
    def test_create_provider_unknown_type(self):
        """Test creating provider with unknown type."""
        # Create a mock ProviderType that doesn't exist in the mapping
        config = Mock()
        config.provider_type = "unknown"
        config.model_name = "test-model"
        config.config = {}
        
        with pytest.raises(ModelNotAvailableError, match="Unknown provider type"):
            create_provider(config)
    
    @patch('campfire.llm.factory.VLLMProvider')
    def test_create_provider_not_available(self, mock_vllm_class):
        """Test creating provider that is not available."""
        mock_provider = Mock()
        mock_provider.is_available.return_value = False
        mock_vllm_class.return_value = mock_provider
        
        config = ProviderConfig(ProviderType.VLLM, model_name="test-model")
        
        with pytest.raises(ModelNotAvailableError, match="Provider vllm is not available"):
            create_provider(config)
    
    @patch('campfire.llm.factory.VLLMProvider')
    def test_create_provider_initialization_error(self, mock_vllm_class):
        """Test creating provider with initialization error."""
        mock_vllm_class.side_effect = RuntimeError("Initialization failed")
        
        config = ProviderConfig(ProviderType.VLLM, model_name="test-model")
        
        with pytest.raises(ModelNotAvailableError, match="Failed to create vllm provider"):
            create_provider(config)


class TestGetAvailableProviders:
    """Test get_available_providers function."""
    
    @patch('campfire.llm.factory.create_provider')
    def test_get_available_providers_all_available(self, mock_create_provider):
        """Test getting available providers when all are available."""
        # Mock providers
        mock_vllm = Mock()
        mock_vllm.supports_tokens.return_value = True
        mock_vllm.get_model_info.return_value = {"name": "vllm-model", "provider": "vllm"}
        
        mock_ollama = Mock()
        mock_ollama.supports_tokens.return_value = False
        mock_ollama.get_model_info.return_value = {"name": "ollama-model", "provider": "ollama"}
        
        mock_lmstudio = Mock()
        mock_lmstudio.supports_tokens.return_value = False
        mock_lmstudio.get_model_info.return_value = {"name": "lmstudio-model", "provider": "lmstudio"}
        
        # Configure mock to return different providers based on config
        def create_provider_side_effect(config):
            if config.provider_type == ProviderType.VLLM:
                return mock_vllm
            elif config.provider_type == ProviderType.OLLAMA:
                return mock_ollama
            elif config.provider_type == ProviderType.LMSTUDIO:
                return mock_lmstudio
        
        mock_create_provider.side_effect = create_provider_side_effect
        
        providers = get_available_providers()
        
        assert len(providers) == 3
        
        # Check vLLM provider
        vllm_info = next(p for p in providers if p["type"] == "vllm")
        assert vllm_info["available"] is True
        assert vllm_info["supports_tokens"] is True
        assert vllm_info["model_info"]["name"] == "vllm-model"
        
        # Check Ollama provider
        ollama_info = next(p for p in providers if p["type"] == "ollama")
        assert ollama_info["available"] is True
        assert ollama_info["supports_tokens"] is False
        
        # Check LM Studio provider
        lmstudio_info = next(p for p in providers if p["type"] == "lmstudio")
        assert lmstudio_info["available"] is True
        assert lmstudio_info["supports_tokens"] is False
    
    @patch('campfire.llm.factory.create_provider')
    def test_get_available_providers_some_unavailable(self, mock_create_provider):
        """Test getting available providers when some are unavailable."""
        def create_provider_side_effect(config):
            if config.provider_type == ProviderType.VLLM:
                raise ModelNotAvailableError("vLLM not installed")
            elif config.provider_type == ProviderType.OLLAMA:
                mock_provider = Mock()
                mock_provider.supports_tokens.return_value = False
                mock_provider.get_model_info.return_value = {"name": "ollama-model"}
                return mock_provider
            elif config.provider_type == ProviderType.LMSTUDIO:
                raise ModelNotAvailableError("LM Studio not running")
        
        mock_create_provider.side_effect = create_provider_side_effect
        
        providers = get_available_providers()
        
        assert len(providers) == 3
        
        # Check that vLLM is marked as unavailable
        vllm_info = next(p for p in providers if p["type"] == "vllm")
        assert vllm_info["available"] is False
        assert "error" in vllm_info
        assert vllm_info["supports_tokens"] is False
        
        # Check that Ollama is available
        ollama_info = next(p for p in providers if p["type"] == "ollama")
        assert ollama_info["available"] is True
        
        # Check that LM Studio is unavailable
        lmstudio_info = next(p for p in providers if p["type"] == "lmstudio")
        assert lmstudio_info["available"] is False
        assert "error" in lmstudio_info


class TestCreateBestAvailableProvider:
    """Test create_best_available_provider function."""
    
    @patch('campfire.llm.factory.create_provider')
    def test_create_best_available_first_choice(self, mock_create_provider):
        """Test creating best available provider when first choice works."""
        mock_provider = Mock()
        mock_create_provider.return_value = mock_provider
        
        result = create_best_available_provider(
            preferred_order=[ProviderType.VLLM, ProviderType.OLLAMA],
            model_name="test-model"
        )
        
        assert result is mock_provider
        # Should only try the first provider
        assert mock_create_provider.call_count == 1
        
        # Check that it was called with vLLM config
        call_args = mock_create_provider.call_args[0][0]
        assert call_args.provider_type == ProviderType.VLLM
        assert call_args.model_name == "test-model"
    
    @patch('campfire.llm.factory.create_provider')
    def test_create_best_available_fallback(self, mock_create_provider):
        """Test creating best available provider with fallback."""
        mock_ollama_provider = Mock()
        
        def create_provider_side_effect(config):
            if config.provider_type == ProviderType.VLLM:
                raise ModelNotAvailableError("vLLM not available")
            elif config.provider_type == ProviderType.OLLAMA:
                return mock_ollama_provider
        
        mock_create_provider.side_effect = create_provider_side_effect
        
        result = create_best_available_provider(
            preferred_order=[ProviderType.VLLM, ProviderType.OLLAMA],
            model_name="test-model"
        )
        
        assert result is mock_ollama_provider
        assert mock_create_provider.call_count == 2
    
    @patch('campfire.llm.factory.create_provider')
    @patch('campfire.llm.factory.get_available_providers')
    def test_create_best_available_none_available(self, mock_get_available, mock_create_provider):
        """Test creating best available provider when none are available."""
        mock_create_provider.side_effect = ModelNotAvailableError("No providers available")
        mock_get_available.return_value = []
        
        with pytest.raises(ModelNotAvailableError, match="No LLM providers are available"):
            create_best_available_provider(
                preferred_order=[ProviderType.VLLM, ProviderType.OLLAMA],
                model_name="test-model"
            )
    
    @patch('campfire.llm.factory.create_provider')
    def test_create_best_available_default_order(self, mock_create_provider):
        """Test creating best available provider with default order."""
        mock_provider = Mock()
        mock_create_provider.return_value = mock_provider
        
        result = create_best_available_provider(model_name="test-model")
        
        assert result is mock_provider
        # Should try vLLM first (default order)
        call_args = mock_create_provider.call_args[0][0]
        assert call_args.provider_type == ProviderType.VLLM


class TestAutoDetectProvider:
    """Test auto_detect_provider function."""
    
    @patch('campfire.llm.factory.create_best_available_provider')
    def test_auto_detect_provider(self, mock_create_best):
        """Test auto-detecting provider."""
        mock_provider = Mock()
        mock_create_best.return_value = mock_provider
        
        result = auto_detect_provider(model_name="test-model")
        
        assert result is mock_provider
        mock_create_best.assert_called_once_with(model_name="test-model")