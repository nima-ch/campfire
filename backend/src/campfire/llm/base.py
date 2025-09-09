"""
Base LLM Provider protocol interface.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Protocol


class LLMProvider(Protocol):
    """
    Protocol interface for LLM providers.
    
    This defines the contract that all LLM provider implementations must follow
    to ensure consistent behavior across different backends (vLLM, Ollama, LM Studio).
    """
    
    @abstractmethod
    def supports_tokens(self) -> bool:
        """
        Check if this provider supports token-level operations.
        
        Returns:
            bool: True if the provider supports token IDs for Harmony tool calls,
                  False if it requires fallback RAG mode.
        """
        pass
    
    @abstractmethod
    def generate(
        self, 
        prefill_ids: List[int], 
        stop_token_ids: List[int],
        max_tokens: int = 2048,
        temperature: float = 0.1
    ) -> Dict[str, Any]:
        """
        Generate completion from prefill token IDs.
        
        Args:
            prefill_ids: List of token IDs to use as prefill/prompt
            stop_token_ids: List of token IDs that should stop generation
            max_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature (0.0 = deterministic)
            
        Returns:
            Dict containing:
                - "completion_tokens": List[int] - Generated token IDs
                - "completion_text": str - Generated text
                - "finish_reason": str - Reason generation stopped
                - "usage": Dict - Token usage statistics
                
        Raises:
            LLMProviderError: If generation fails
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this provider is available and ready to use.
        
        Returns:
            bool: True if the provider can be used, False otherwise
        """
        pass
    
    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the loaded model.
        
        Returns:
            Dict containing model metadata like name, size, capabilities
        """
        pass


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""
    pass


class ModelNotAvailableError(LLMProviderError):
    """Raised when a model is not available or not loaded."""
    pass


class GenerationError(LLMProviderError):
    """Raised when text generation fails."""
    pass


class TokenizationError(LLMProviderError):
    """Raised when tokenization operations fail."""
    pass