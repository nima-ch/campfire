"""
Tests for the base LLM provider protocol and exceptions.
"""

import pytest
from typing import Any, Dict, List

from campfire.llm.base import (
    LLMProvider,
    LLMProviderError,
    ModelNotAvailableError,
    GenerationError,
    TokenizationError,
)


class MockLLMProvider:
    """Mock implementation of LLMProvider for testing."""
    
    def __init__(self, supports_tokens: bool = True, available: bool = True):
        self._supports_tokens = supports_tokens
        self._available = available
        self._model_info = {
            "name": "mock-model",
            "provider": "mock",
            "supports_tokens": supports_tokens,
        }
    
    def supports_tokens(self) -> bool:
        return self._supports_tokens
    
    def generate(
        self, 
        prefill_ids: List[int], 
        stop_token_ids: List[int],
        max_tokens: int = 2048,
        temperature: float = 0.1
    ) -> Dict[str, Any]:
        if not self._available:
            raise GenerationError("Provider not available")
            
        if not prefill_ids:
            raise GenerationError("Empty prefill_ids")
            
        # Mock generation
        completion_tokens = [1, 2, 3, 4, 5]  # Mock token IDs
        completion_text = "This is a mock response."
        
        return {
            "completion_tokens": completion_tokens,
            "completion_text": completion_text,
            "finish_reason": "stop",
            "usage": {
                "prompt_tokens": len(prefill_ids),
                "completion_tokens": len(completion_tokens),
                "total_tokens": len(prefill_ids) + len(completion_tokens),
            }
        }
    
    def is_available(self) -> bool:
        return self._available
    
    def get_model_info(self) -> Dict[str, Any]:
        return self._model_info


class TestLLMProviderProtocol:
    """Test the LLM provider protocol interface."""
    
    def test_mock_provider_implements_protocol(self):
        """Test that our mock provider implements the protocol correctly."""
        provider = MockLLMProvider()
        
        # Test protocol methods exist and work
        assert provider.supports_tokens() is True
        assert provider.is_available() is True
        
        model_info = provider.get_model_info()
        assert isinstance(model_info, dict)
        assert "name" in model_info
        assert "provider" in model_info
        
        # Test generation
        result = provider.generate([1, 2, 3], [4, 5])
        assert isinstance(result, dict)
        assert "completion_tokens" in result
        assert "completion_text" in result
        assert "finish_reason" in result
        assert "usage" in result
    
    def test_provider_with_token_support(self):
        """Test provider that supports tokens."""
        provider = MockLLMProvider(supports_tokens=True)
        assert provider.supports_tokens() is True
    
    def test_provider_without_token_support(self):
        """Test provider that doesn't support tokens."""
        provider = MockLLMProvider(supports_tokens=False)
        assert provider.supports_tokens() is False
    
    def test_generation_with_valid_input(self):
        """Test generation with valid input parameters."""
        provider = MockLLMProvider()
        
        result = provider.generate(
            prefill_ids=[1, 2, 3],
            stop_token_ids=[4, 5],
            max_tokens=100,
            temperature=0.5
        )
        
        assert result["completion_text"] == "This is a mock response."
        assert result["finish_reason"] == "stop"
        assert result["usage"]["prompt_tokens"] == 3
        assert result["usage"]["completion_tokens"] == 5
        assert result["usage"]["total_tokens"] == 8
    
    def test_generation_with_empty_prefill(self):
        """Test that generation fails with empty prefill_ids."""
        provider = MockLLMProvider()
        
        with pytest.raises(GenerationError, match="Empty prefill_ids"):
            provider.generate([], [4, 5])
    
    def test_unavailable_provider(self):
        """Test behavior when provider is not available."""
        provider = MockLLMProvider(available=False)
        
        assert provider.is_available() is False
        
        with pytest.raises(GenerationError, match="Provider not available"):
            provider.generate([1, 2, 3], [4, 5])


class TestLLMProviderExceptions:
    """Test LLM provider exception hierarchy."""
    
    def test_base_exception(self):
        """Test base LLMProviderError exception."""
        error = LLMProviderError("Base error")
        assert str(error) == "Base error"
        assert isinstance(error, Exception)
    
    def test_model_not_available_error(self):
        """Test ModelNotAvailableError exception."""
        error = ModelNotAvailableError("Model not found")
        assert str(error) == "Model not found"
        assert isinstance(error, LLMProviderError)
        assert isinstance(error, Exception)
    
    def test_generation_error(self):
        """Test GenerationError exception."""
        error = GenerationError("Generation failed")
        assert str(error) == "Generation failed"
        assert isinstance(error, LLMProviderError)
        assert isinstance(error, Exception)
    
    def test_tokenization_error(self):
        """Test TokenizationError exception."""
        error = TokenizationError("Tokenization failed")
        assert str(error) == "Tokenization failed"
        assert isinstance(error, LLMProviderError)
        assert isinstance(error, Exception)
    
    def test_exception_chaining(self):
        """Test that exceptions can be chained properly."""
        original_error = ValueError("Original error")
        
        try:
            raise GenerationError("Generation failed") from original_error
        except GenerationError as e:
            assert str(e) == "Generation failed"
            assert e.__cause__ is original_error
            assert isinstance(e.__cause__, ValueError)