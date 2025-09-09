"""
LM Studio provider implementation for Campfire.

This provider uses LM Studio's OpenAI-compatible API for local inference.
It provides an alternative backend option for users who prefer LM Studio.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from .base import LLMProvider, GenerationError, ModelNotAvailableError

logger = logging.getLogger(__name__)


class LMStudioProvider:
    """
    LM Studio provider implementation using OpenAI-compatible API.
    
    This provider offers an alternative to vLLM and Ollama for users
    who prefer LM Studio's interface and model management.
    """
    
    def __init__(
        self,
        model_name: str = "gpt-oss-20b",
        base_url: str = "http://localhost:1234/v1",
        timeout: float = 120.0
    ):
        """
        Initialize LM Studio provider.
        
        Args:
            model_name: Name of the model to use
            base_url: Base URL for LM Studio API (OpenAI-compatible)
            timeout: Request timeout in seconds
        """
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        
        self._client = httpx.Client(timeout=timeout)
        self._model_info = None
        
    def supports_tokens(self) -> bool:
        """
        LM Studio typically doesn't support direct token ID access.
        
        Like Ollama, this means we'll need to use RAG prefetch fallback mode
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
        Generate completion using LM Studio's OpenAI-compatible API.
        
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
            # Convert token IDs to text (simplified approach)
            prompt_text = self._decode_tokens_fallback(prefill_ids)
            
            # Convert stop token IDs to stop strings
            stop_strings = self._decode_stop_tokens_fallback(stop_token_ids)
            
            # Prepare OpenAI-compatible request
            payload = {
                "model": self.model_name,
                "messages": [
                    {"role": "user", "content": prompt_text}
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False,
            }
            
            # Add stop strings if available
            if stop_strings:
                payload["stop"] = stop_strings
            
            # Make request to LM Studio
            response = self._client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            result = response.json()
            
            # Extract completion from OpenAI-style response
            if "choices" not in result or not result["choices"]:
                raise GenerationError("No choices in LM Studio response")
                
            choice = result["choices"][0]
            completion_text = choice.get("message", {}).get("content", "")
            finish_reason = choice.get("finish_reason", "unknown")
            
            # Extract usage information
            usage = result.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens_count = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", 0)
            
            # Estimate completion token IDs (since we don't have direct access)
            estimated_completion_tokens = self._estimate_tokens(completion_text)
            
            return {
                "completion_tokens": estimated_completion_tokens,
                "completion_text": completion_text,
                "finish_reason": finish_reason,
                "usage": {
                    "prompt_tokens": prompt_tokens or self._estimate_token_count(prompt_text),
                    "completion_tokens": completion_tokens_count or len(estimated_completion_tokens),
                    "total_tokens": total_tokens or (prompt_tokens + completion_tokens_count),
                }
            }
            
        except httpx.HTTPError as e:
            raise GenerationError(f"LM Studio HTTP error: {str(e)}") from e
        except json.JSONDecodeError as e:
            raise GenerationError(f"Invalid JSON response from LM Studio: {str(e)}") from e
        except Exception as e:
            raise GenerationError(f"LM Studio generation failed: {str(e)}") from e
    
    def is_available(self) -> bool:
        """Check if LM Studio is available and responsive."""
        try:
            # Check if LM Studio is running by getting models list
            response = self._client.get(f"{self.base_url}/models")
            response.raise_for_status()
            
            models_data = response.json()
            models = models_data.get("data", [])
            
            if not models:
                logger.warning("No models available in LM Studio")
                return False
            
            # Check if our model is available (or if any model is loaded)
            model_ids = [model.get("id", "") for model in models]
            
            # For LM Studio, we might need to be flexible with model names
            model_available = any(
                self.model_name in model_id or model_id in self.model_name
                for model_id in model_ids
            )
            
            if not model_available:
                logger.info(f"Specific model {self.model_name} not found, but LM Studio is available with models: {model_ids}")
                # LM Studio might have a model loaded that we can use
                return len(models) > 0
                
            return True
            
        except Exception as e:
            logger.warning(f"LM Studio availability check failed: {e}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about available models from LM Studio."""
        if self._model_info is not None:
            return self._model_info
            
        try:
            # Get models list from LM Studio
            response = self._client.get(f"{self.base_url}/models")
            response.raise_for_status()
            
            models_data = response.json()
            models = models_data.get("data", [])
            
            if models:
                # Use the first available model or find our specific model
                target_model = None
                for model in models:
                    model_id = model.get("id", "")
                    if self.model_name in model_id or model_id in self.model_name:
                        target_model = model
                        break
                
                # If no specific match, use the first model
                if target_model is None and models:
                    target_model = models[0]
                    
                if target_model:
                    self._model_info = {
                        "name": target_model.get("id", self.model_name),
                        "provider": "lmstudio",
                        "supports_tokens": False,
                        "object": target_model.get("object", "model"),
                        "created": target_model.get("created", 0),
                        "owned_by": target_model.get("owned_by", "lmstudio"),
                    }
                    return self._model_info
            
            # Fallback if no models found
            self._model_info = {
                "name": self.model_name,
                "provider": "lmstudio",
                "supports_tokens": False,
                "status": "no_models_available"
            }
            return self._model_info
            
        except Exception as e:
            logger.warning(f"Could not get model info from LM Studio: {e}")
            return {
                "name": self.model_name,
                "provider": "lmstudio",
                "supports_tokens": False,
                "status": "unknown"
            }
    
    def _decode_tokens_fallback(self, token_ids: List[int]) -> str:
        """
        Fallback method to convert token IDs to text.
        
        Since LM Studio doesn't provide direct token access, this is a simplified
        approach similar to the Ollama implementation.
        """
        # Try ASCII conversion first
        try:
            if all(32 <= tid <= 126 for tid in token_ids):
                return "".join(chr(tid) for tid in token_ids)
        except (ValueError, TypeError):
            pass
            
        # Return a placeholder indicating we need text input
        return f"<tokens:{len(token_ids)}>"
    
    def _decode_stop_tokens_fallback(self, stop_token_ids: List[int]) -> List[str]:
        """
        Fallback method to convert stop token IDs to stop strings.
        """
        stop_strings = []
        for token_id in stop_token_ids:
            try:
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
        
        # Return dummy token IDs
        return list(range(estimated_count))
    
    def _estimate_token_count(self, text: str) -> int:
        """Estimate the number of tokens in text."""
        return max(1, len(text) // 4)
    
    def __del__(self):
        """Clean up HTTP client."""
        if hasattr(self, '_client'):
            self._client.close()