"""
Tests for OllamaProvider implementation.
"""

import json
import pytest
from unittest.mock import Mock, patch
from typing import Any, Dict

import httpx

from campfire.llm.ollama_provider import OllamaProvider
from campfire.llm.base import GenerationError, ModelNotAvailableError


class TestOllamaProvider:
    """Test OllamaProvider implementation."""
    
    def test_init(self):
        """Test OllamaProvider initialization."""
        provider = OllamaProvider(
            model_name="test-model",
            base_url="http://localhost:11434",
            timeout=60.0
        )
        
        assert provider.model_name == "test-model"
        assert provider.base_url == "http://localhost:11434"
        assert provider.timeout == 60.0
        assert provider._model_info is None
    
    def test_supports_tokens(self):
        """Test that OllamaProvider doesn't support tokens."""
        provider = OllamaProvider()
        assert provider.supports_tokens() is False
    
    @patch('httpx.Client')
    def test_generate_success(self, mock_client_class):
        """Test successful text generation."""
        # Mock HTTP client and response
        mock_client = Mock()
        mock_response = Mock()
        
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "response": "This is a test response from Ollama.",
            "done": True
        }
        
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        provider = OllamaProvider(model_name="test-model")
        
        result = provider.generate(
            prefill_ids=[72, 101, 108, 108, 111],  # "Hello" in ASCII
            stop_token_ids=[46],  # "." in ASCII
            max_tokens=100,
            temperature=0.5
        )
        
        assert result["completion_text"] == "This is a test response from Ollama."
        assert result["finish_reason"] == "stop"
        assert "completion_tokens" in result
        assert "usage" in result
        
        # Verify the API call was made correctly
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "http://localhost:11434/api/generate"
        
        payload = call_args[1]["json"]
        assert payload["model"] == "test-model"
        assert payload["stream"] is False
        assert payload["options"]["temperature"] == 0.5
        assert payload["options"]["num_predict"] == 100
    
    def test_generate_empty_prefill(self):
        """Test generation with empty prefill_ids."""
        provider = OllamaProvider()
        
        with pytest.raises(GenerationError, match="prefill_ids cannot be empty"):
            provider.generate([], [46])
    
    @patch('httpx.Client')
    def test_generate_http_error(self, mock_client_class):
        """Test generation with HTTP error."""
        mock_client = Mock()
        mock_response = Mock()
        
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=Mock(), response=Mock()
        )
        
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        provider = OllamaProvider()
        
        with pytest.raises(GenerationError, match="Ollama HTTP error"):
            provider.generate([72, 101, 108, 108, 111], [46])
    
    @patch('httpx.Client')
    def test_generate_json_error(self, mock_client_class):
        """Test generation with invalid JSON response."""
        mock_client = Mock()
        mock_response = Mock()
        
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        provider = OllamaProvider()
        
        with pytest.raises(GenerationError, match="Invalid JSON response from Ollama"):
            provider.generate([72, 101, 108, 108, 111], [46])
    
    @patch('httpx.Client')
    def test_is_available_success(self, mock_client_class):
        """Test successful availability check."""
        mock_client = Mock()
        mock_response = Mock()
        
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "models": [
                {"name": "gpt-oss-20b"},
                {"name": "llama2:7b"}
            ]
        }
        
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        provider = OllamaProvider(model_name="gpt-oss-20b")
        assert provider.is_available() is True
        
        mock_client.get.assert_called_once_with("http://localhost:11434/api/tags")
    
    @patch('httpx.Client')
    def test_is_available_model_not_found(self, mock_client_class):
        """Test availability check when model is not found."""
        mock_client = Mock()
        mock_response = Mock()
        
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "models": [
                {"name": "llama2:7b"},
                {"name": "codellama:13b"}
            ]
        }
        
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        provider = OllamaProvider(model_name="gpt-oss-20b")
        assert provider.is_available() is False
    
    @patch('httpx.Client')
    def test_is_available_http_error(self, mock_client_class):
        """Test availability check with HTTP error."""
        mock_client = Mock()
        mock_client.get.side_effect = httpx.ConnectError("Connection failed")
        mock_client_class.return_value = mock_client
        
        provider = OllamaProvider()
        assert provider.is_available() is False
    
    @patch('httpx.Client')
    def test_get_model_info_success(self, mock_client_class):
        """Test successful model info retrieval."""
        mock_client = Mock()
        mock_response = Mock()
        
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "size": 12345678,
            "details": {
                "format": "gguf",
                "family": "llama",
                "parameter_size": "20B"
            }
        }
        
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        provider = OllamaProvider(model_name="test-model")
        info = provider.get_model_info()
        
        assert info["name"] == "test-model"
        assert info["provider"] == "ollama"
        assert info["supports_tokens"] is False
        assert info["size"] == 12345678
        assert info["format"] == "gguf"
        assert info["family"] == "llama"
        assert info["parameter_size"] == "20B"
        
        mock_client.post.assert_called_once_with(
            "http://localhost:11434/api/show",
            json={"name": "test-model"}
        )
    
    @patch('httpx.Client')
    def test_get_model_info_error(self, mock_client_class):
        """Test model info retrieval with error."""
        mock_client = Mock()
        mock_client.post.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=Mock(), response=Mock()
        )
        mock_client_class.return_value = mock_client
        
        provider = OllamaProvider(model_name="test-model")
        info = provider.get_model_info()
        
        assert info["name"] == "test-model"
        assert info["provider"] == "ollama"
        assert info["supports_tokens"] is False
        assert info["status"] == "unknown"
    
    def test_decode_tokens_fallback_ascii(self):
        """Test token decoding with ASCII values."""
        provider = OllamaProvider()
        
        # Test ASCII conversion
        ascii_tokens = [72, 101, 108, 108, 111]  # "Hello"
        result = provider._decode_tokens_fallback(ascii_tokens)
        assert result == "Hello"
    
    def test_decode_tokens_fallback_non_ascii(self):
        """Test token decoding with non-ASCII values."""
        provider = OllamaProvider()
        
        # Test non-ASCII tokens
        non_ascii_tokens = [1000, 2000, 3000]
        result = provider._decode_tokens_fallback(non_ascii_tokens)
        assert result == "<tokens:3>"
    
    def test_decode_stop_tokens_fallback(self):
        """Test stop token decoding."""
        provider = OllamaProvider()
        
        # Test ASCII stop tokens
        stop_tokens = [46, 33, 63]  # ".", "!", "?"
        result = provider._decode_stop_tokens_fallback(stop_tokens)
        assert result == [".", "!", "?"]
        
        # Test non-ASCII stop tokens
        non_ascii_stop = [1000, 46, 2000]
        result = provider._decode_stop_tokens_fallback(non_ascii_stop)
        assert result == ["."]  # Only the ASCII one
    
    def test_estimate_tokens(self):
        """Test token estimation from text."""
        provider = OllamaProvider()
        
        text = "This is a test sentence."
        tokens = provider._estimate_tokens(text)
        
        # Should estimate roughly 1 token per 4 characters
        expected_count = max(1, len(text) // 4)
        assert len(tokens) == expected_count
        assert all(isinstance(token, int) for token in tokens)
    
    def test_client_cleanup(self):
        """Test that HTTP client is properly cleaned up."""
        provider = OllamaProvider()
        mock_client = Mock()
        provider._client = mock_client
        
        # Simulate deletion
        provider.__del__()
        
        mock_client.close.assert_called_once()