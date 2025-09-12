"""
Ollama provider implementation for Campfire.

This provider uses Ollama for local inference with fallback RAG mode
when token ID access is not available.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from .base import LLMProvider, GenerationError, ModelNotAvailableError

logger = logging.getLogger(__name__)


class OllamaProvider:
    """
    Ollama provider implementation with RAG fallback mode.
    
    This provider is more accessible and easier to set up than vLLM,
    but may not support full token-level operations for Harmony tools.
    """
    
    def __init__(
        self,
        model_name: str = "gpt-oss:20b",
        base_url: str = "http://localhost:11434",
        timeout: float = 120.0
    ):
        """
        Initialize Ollama provider.
        
        Args:
            model_name: Name of the model to use
            base_url: Base URL for Ollama API
            timeout: Request timeout in seconds
        """
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        
        self._client = httpx.Client(timeout=timeout)
        self._model_info = None
        
    def supports_tokens(self) -> bool:
        """
        Ollama typically doesn't support token ID access.
        
        This means we'll need to use RAG prefetch fallback mode
        instead of full Harmony tool loops.
        """
        return False
    
    def generate(
        self, 
        prefill_ids: List[int], 
        stop_token_ids: List[int],
        max_tokens: int = 2048,
        temperature: float = 0.1
    ) -> Dict[str, Any]:
        """
        Generate completion using Ollama API.
        
        Since Ollama doesn't typically support token IDs directly,
        this method converts token IDs to text and uses text-based generation.
        
        Args:
            prefill_ids: Token IDs to convert to text prompt
            stop_token_ids: Token IDs to convert to stop strings
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            Dict with completion text and metadata
        """
        if not prefill_ids:
            raise GenerationError("prefill_ids cannot be empty")
            
        try:
            # For Ollama, we need to convert token IDs to text
            # This is a limitation since we don't have direct token access
            # In a real implementation, we'd need a tokenizer for this conversion
            # For now, we'll assume the prefill_ids represent a text prompt
            
            # Convert prefill_ids to text (simplified approach)
            # In practice, you'd need the actual tokenizer for the model
            prompt_text = self._decode_tokens_fallback(prefill_ids)
            
            # Convert stop token IDs to stop strings (simplified)
            stop_strings = self._decode_stop_tokens_fallback(stop_token_ids)
            
            # Prepare request payload
            payload = {
                "model": self.model_name,
                "prompt": prompt_text,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                }
            }
            
            # Add stop strings if available
            if stop_strings:
                payload["options"]["stop"] = stop_strings
            
            # Make request to Ollama
            response = self._client.post(
                f"{self.base_url}/api/generate",
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            completion_text = result.get("response", "")
            
            # Since we don't have token IDs, we'll estimate them
            # This is a limitation of the Ollama approach
            estimated_completion_tokens = self._estimate_tokens(completion_text)
            estimated_prompt_tokens = self._estimate_tokens(prompt_text)
            
            return {
                "completion_tokens": estimated_completion_tokens,  # Estimated
                "completion_text": completion_text,
                "finish_reason": "stop" if result.get("done", False) else "length",
                "usage": {
                    "prompt_tokens": len(estimated_prompt_tokens),
                    "completion_tokens": len(estimated_completion_tokens),
                    "total_tokens": len(estimated_prompt_tokens) + len(estimated_completion_tokens),
                }
            }
            
        except httpx.HTTPError as e:
            raise GenerationError(f"Ollama HTTP error: {str(e)}") from e
        except json.JSONDecodeError as e:
            raise GenerationError(f"Invalid JSON response from Ollama: {str(e)}") from e
        except Exception as e:
            raise GenerationError(f"Ollama generation failed: {str(e)}") from e
    
    def is_available(self) -> bool:
        """Check if Ollama is available and the model is loaded."""
        try:
            # Check if Ollama is running
            response = self._client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            
            # Check if our model is available
            models = response.json().get("models", [])
            model_names = [model.get("name", "") for model in models]
            
            # Check if our model is in the list (exact match or partial match)
            model_available = any(
                self.model_name in name or name in self.model_name 
                for name in model_names
            )
            
            if not model_available:
                logger.warning(f"Model {self.model_name} not found in Ollama. Available models: {model_names}")
                return False
                
            return True
            
        except Exception as e:
            logger.warning(f"Ollama availability check failed: {e}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the model from Ollama."""
        if self._model_info is not None:
            return self._model_info
            
        try:
            # Get model information from Ollama
            response = self._client.post(
                f"{self.base_url}/api/show",
                json={"name": self.model_name}
            )
            response.raise_for_status()
            
            model_data = response.json()
            
            self._model_info = {
                "name": self.model_name,
                "provider": "ollama",
                "supports_tokens": False,
                "size": model_data.get("size", 0),
                "format": model_data.get("details", {}).get("format", "unknown"),
                "family": model_data.get("details", {}).get("family", "unknown"),
                "parameter_size": model_data.get("details", {}).get("parameter_size", "unknown"),
            }
            
            return self._model_info
            
        except Exception as e:
            logger.warning(f"Could not get model info from Ollama: {e}")
            return {
                "name": self.model_name,
                "provider": "ollama",
                "supports_tokens": False,
                "status": "unknown"
            }
    
    def _decode_tokens_fallback(self, token_ids: List[int]) -> str:
        """
        Fallback method to convert token IDs to text.
        
        Since Ollama doesn't provide direct token access, this is a simplified
        approach. In a real implementation, you'd need the actual tokenizer.
        """
        # This is a placeholder implementation
        # In practice, you'd need to use the same tokenizer as the model
        # For now, we'll assume this is already text or use a simple mapping
        
        # If token_ids look like ASCII values, convert them
        try:
            if all(32 <= tid <= 126 for tid in token_ids):
                return "".join(chr(tid) for tid in token_ids)
        except (ValueError, TypeError):
            pass
            
        # Otherwise, return a placeholder that indicates we need text input
        return f"<tokens:{len(token_ids)}>"
    
    def _decode_stop_tokens_fallback(self, stop_token_ids: List[int]) -> List[str]:
        """
        Fallback method to convert stop token IDs to stop strings.
        """
        stop_strings = []
        for token_id in stop_token_ids:
            try:
                # Simple ASCII conversion attempt
                if 32 <= token_id <= 126:
                    stop_strings.append(chr(token_id))
            except (ValueError, TypeError):
                continue
                
        return stop_strings
    
    def _estimate_tokens(self, text: str) -> List[int]:
        """
        Estimate token IDs from text.
        
        This is a rough approximation since we don't have the actual tokenizer.
        """
        # Very rough estimation: ~4 characters per token on average
        estimated_count = max(1, len(text) // 4)
        
        # Return dummy token IDs (in practice, you'd use a real tokenizer)
        return list(range(estimated_count))
    
    def __del__(self):
        """Clean up HTTP client."""
        if hasattr(self, '_client'):
            self._client.close()