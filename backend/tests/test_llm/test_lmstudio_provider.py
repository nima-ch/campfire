"""
Tests for LMStudioProvider implementation.
"""

import json
import pytest
from unittest.mock import Mock, patch
from typing import Any, Dict

import httpx

from campfire.llm.lmstudio_provider import LMStudioProvider
from campfire.llm.base import GenerationError, ModelNotAvailableError


class TestLMStudioProvider:
    """Test LMStudioProvider implementation."""
    
    def test_init(self):
        """Test LMStudioProvider initialization."""
        provider = LMStudioProvider(
            model_name="test-model",
            base_url="http://localhost:1234/v1",
            timeout=90.0
        )
        
        assert provider.model_name == "test-model"
        assert provider.base_url == "http://localhost:1234/v1"
        assert provider.timeout == 90.0
        assert provider._model_info is None
    
    def test_supports_tokens(self):
        """Test that LMStudioProvider doesn't support tokens."""
        provider = LMStudioProvider()
        assert provider.supports_tokens() is False
    
    @patch('httpx.Client')
    def test_generate_success(self, mock_client_class):
        """Test successful text generation."""
        # Mock HTTP client and response
        mock_client = Mock()
        mock_response = Mock()
        
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "This is a test response from LM Studio."
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 15,
                "total_tokens": 25
            }
        }
        
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        provider = LMStudioProvider(model_name="test-model")
        
        result = provider.generate(
            prefill_ids=[72, 101, 108, 108, 111],  # "Hello" in ASCII
            stop_token_ids=[46],  # "." in ASCII
            max_tokens=100,
            temperature=0.5
        )
        
        assert result["completion_text"] == "This is a test response from LM Studio."
        assert result["finish_reason"] == "stop"
        assert result["usage"]["prompt_tokens"] == 10
        assert result["usage"]["completion_tokens"] == 15
        assert result["usage"]["total_tokens"] == 25
        
        # Verify the API call was made correctly
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "http://localhost:1234/v1/chat/completions"
        
        payload = call_args[1]["json"]
        assert payload["model"] == "test-model"
        assert payload["max_tokens"] == 100
        assert payload["temperature"] == 0.5
        assert payload["stream"] is False
        assert len(payload["messages"]) == 1
        assert payload["messages"][0]["role"] == "user"
    
    def test_generate_empty_prefill(self):
        """Test generation with empty prefill_ids."""
        provider = LMStudioProvider()
        
        with pytest.raises(GenerationError, match="prefill_ids cannot be empty"):
            provider.generate([], [46])
    
    @patch('httpx.Client')
    def test_generate_no_choices(self, mock_client_class):
        """Test generation with no choices in response."""
        mock_client = Mock()
        mock_response = Mock()
        
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"choices": []}
        
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        provider = LMStudioProvider()
        
        with pytest.raises(GenerationError, match="No choices in LM Studio response"):
            provider.generate([72, 101, 108, 108, 111], [46])
    
    @patch('httpx.Client')
    def test_generate_http_error(self, mock_client_class):
        """Test generation with HTTP error."""
        mock_client = Mock()
        mock_response = Mock()
        
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error", request=Mock(), response=Mock()
        )
        
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        provider = LMStudioProvider()
        
        with pytest.raises(GenerationError, match="LM Studio HTTP error"):
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
        
        provider = LMStudioProvider()
        
        with pytest.raises(GenerationError, match="Invalid JSON response from LM Studio"):
            provider.generate([72, 101, 108, 108, 111], [46])
    
    @patch('httpx.Client')
    def test_generate_with_usage_fallback(self, mock_client_class):
        """Test generation with missing usage information."""
        mock_client = Mock()
        mock_response = Mock()
        
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "Response without usage info."
                    },
                    "finish_reason": "length"
                }
            ]
            # No usage field
        }
        
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        provider = LMStudioProvider()
        
        result = provider.generate([72, 101, 108, 108, 111], [46])
        
        assert result["completion_text"] == "Response without usage info."
        assert result["finish_reason"] == "length"
        # Should have estimated usage
        assert result["usage"]["prompt_tokens"] > 0
        assert result["usage"]["completion_tokens"] > 0
    
    @patch('httpx.Client')
    def test_is_available_success(self, mock_client_class):
        """Test successful availability check."""
        mock_client = Mock()
        mock_response = Mock()
        
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "data": [
                {"id": "gpt-oss-20b", "object": "model"},
                {"id": "llama-2-7b", "object": "model"}
            ]
        }
        
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        provider = LMStudioProvider(model_name="gpt-oss-20b")
        assert provider.is_available() is True
        
        mock_client.get.assert_called_once_with("http://localhost:1234/v1/models")
    
    @patch('httpx.Client')
    def test_is_available_no_models(self, mock_client_class):
        """Test availability check with no models."""
        mock_client = Mock()
        mock_response = Mock()
        
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"data": []}
        
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        provider = LMStudioProvider()
        assert provider.is_available() is False
    
    @patch('httpx.Client')
    def test_is_available_model_not_exact_match(self, mock_client_class):
        """Test availability check with partial model name match."""
        mock_client = Mock()
        mock_response = Mock()
        
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "data": [
                {"id": "some-other-model", "object": "model"}
            ]
        }
        
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        provider = LMStudioProvider(model_name="gpt-oss-20b")
        # Should still return True because LM Studio has models available
        assert provider.is_available() is True
    
    @patch('httpx.Client')
    def test_is_available_http_error(self, mock_client_class):
        """Test availability check with HTTP error."""
        mock_client = Mock()
        mock_client.get.side_effect = httpx.ConnectError("Connection failed")
        mock_client_class.return_value = mock_client
        
        provider = LMStudioProvider()
        assert provider.is_available() is False
    
    @patch('httpx.Client')
    def test_get_model_info_success(self, mock_client_class):
        """Test successful model info retrieval."""
        mock_client = Mock()
        mock_response = Mock()
        
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "gpt-oss-20b",
                    "object": "model",
                    "created": 1234567890,
                    "owned_by": "lmstudio"
                }
            ]
        }
        
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        provider = LMStudioProvider(model_name="gpt-oss-20b")
        info = provider.get_model_info()
        
        assert info["name"] == "gpt-oss-20b"
        assert info["provider"] == "lmstudio"
        assert info["supports_tokens"] is False
        assert info["object"] == "model"
        assert info["created"] == 1234567890
        assert info["owned_by"] == "lmstudio"
    
    @patch('httpx.Client')
    def test_get_model_info_fallback_model(self, mock_client_class):
        """Test model info retrieval with fallback to first available model."""
        mock_client = Mock()
        mock_response = Mock()
        
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "some-other-model",
                    "object": "model",
                    "created": 1234567890,
                    "owned_by": "lmstudio"
                }
            ]
        }
        
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        provider = LMStudioProvider(model_name="gpt-oss-20b")
        info = provider.get_model_info()
        
        # Should use the first available model
        assert info["name"] == "some-other-model"
        assert info["provider"] == "lmstudio"
    
    @patch('httpx.Client')
    def test_get_model_info_error(self, mock_client_class):
        """Test model info retrieval with error."""
        mock_client = Mock()
        mock_client.get.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=Mock(), response=Mock()
        )
        mock_client_class.return_value = mock_client
        
        provider = LMStudioProvider(model_name="test-model")
        info = provider.get_model_info()
        
        assert info["name"] == "test-model"
        assert info["provider"] == "lmstudio"
        assert info["supports_tokens"] is False
        assert info["status"] == "unknown"
    
    def test_decode_tokens_fallback_ascii(self):
        """Test token decoding with ASCII values."""
        provider = LMStudioProvider()
        
        # Test ASCII conversion
        ascii_tokens = [72, 101, 108, 108, 111]  # "Hello"
        result = provider._decode_tokens_fallback(ascii_tokens)
        assert result == "Hello"
    
    def test_decode_tokens_fallback_non_ascii(self):
        """Test token decoding with non-ASCII values."""
        provider = LMStudioProvider()
        
        # Test non-ASCII tokens
        non_ascii_tokens = [1000, 2000, 3000]
        result = provider._decode_tokens_fallback(non_ascii_tokens)
        assert result == "<tokens:3>"
    
    def test_estimate_tokens(self):
        """Test token estimation from text."""
        provider = LMStudioProvider()
        
        text = "This is a test sentence."
        tokens = provider._estimate_tokens(text)
        
        # Should estimate roughly 1 token per 4 characters
        expected_count = max(1, len(text) // 4)
        assert len(tokens) == expected_count
        assert all(isinstance(token, int) for token in tokens)
    
    def test_estimate_token_count(self):
        """Test token count estimation."""
        provider = LMStudioProvider()
        
        text = "This is a test."
        count = provider._estimate_token_count(text)
        
        expected_count = max(1, len(text) // 4)
        assert count == expected_count
    
    def test_client_cleanup(self):
        """Test that HTTP client is properly cleaned up."""
        provider = LMStudioProvider()
        mock_client = Mock()
        provider._client = mock_client
        
        # Simulate deletion
        provider.__del__()
        
        mock_client.close.assert_called_once()