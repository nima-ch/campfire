"""
vLLM provider implementation for Campfire.

This provider uses vLLM for high-performance local inference with full
Harmony tool-loop support via token ID access.
"""

import logging
from typing import Any, Dict, List, Optional

from .base import LLMProvider, GenerationError, ModelNotAvailableError, TokenizationError

logger = logging.getLogger(__name__)


class VLLMProvider:
    """
    vLLM provider implementation with full Harmony support.
    
    This provider offers the best performance and full token-level access
    for Harmony tool calls, but requires more system resources.
    """
    
    def __init__(
        self, 
        model_name: str = "gpt-oss-20b",
        tensor_parallel_size: int = 1,
        gpu_memory_utilization: float = 0.8,
        max_model_len: Optional[int] = None
    ):
        """
        Initialize vLLM provider.
        
        Args:
            model_name: Name of the model to load
            tensor_parallel_size: Number of GPUs to use for tensor parallelism
            gpu_memory_utilization: Fraction of GPU memory to use
            max_model_len: Maximum sequence length (None for model default)
        """
        self.model_name = model_name
        self.tensor_parallel_size = tensor_parallel_size
        self.gpu_memory_utilization = gpu_memory_utilization
        self.max_model_len = max_model_len
        
        self._engine = None
        self._tokenizer = None
        self._model_info = None
        
    def _initialize_engine(self) -> None:
        """Initialize the vLLM engine if not already done."""
        if self._engine is not None:
            return
            
        try:
            from vllm import LLM, SamplingParams
            from vllm.engine.arg_utils import EngineArgs
            
            # Create engine arguments
            engine_args = EngineArgs(
                model=self.model_name,
                tensor_parallel_size=self.tensor_parallel_size,
                gpu_memory_utilization=self.gpu_memory_utilization,
                max_model_len=self.max_model_len,
                trust_remote_code=True,
                enforce_eager=False,
            )
            
            # Initialize the LLM engine
            self._engine = LLM(**engine_args.create_engine_configs())
            self._tokenizer = self._engine.get_tokenizer()
            
            # Cache model info
            self._model_info = {
                "name": self.model_name,
                "provider": "vllm",
                "supports_tokens": True,
                "max_model_len": self._engine.llm_engine.model_config.max_model_len,
                "vocab_size": len(self._tokenizer.get_vocab()),
            }
            
            logger.info(f"vLLM engine initialized with model: {self.model_name}")
            
        except ImportError as e:
            raise ModelNotAvailableError(
                "vLLM is not installed. Install with: uv add vllm"
            ) from e
        except Exception as e:
            raise ModelNotAvailableError(
                f"Failed to initialize vLLM engine: {str(e)}"
            ) from e
    
    def supports_tokens(self) -> bool:
        """vLLM supports full token-level operations."""
        return True
    
    def generate(
        self, 
        prefill_ids: List[int], 
        stop_token_ids: List[int],
        max_tokens: int = 2048,
        temperature: float = 0.1
    ) -> Dict[str, Any]:
        """
        Generate completion using vLLM engine.
        
        Args:
            prefill_ids: Token IDs to use as prefill
            stop_token_ids: Token IDs that should stop generation
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            Dict with completion tokens, text, and metadata
        """
        self._initialize_engine()
        
        if not prefill_ids:
            raise GenerationError("prefill_ids cannot be empty")
            
        try:
            from vllm import SamplingParams
            
            # Convert token IDs to text for vLLM input
            prefill_text = self._tokenizer.decode(prefill_ids)
            
            # Convert stop token IDs to stop strings
            stop_strings = []
            for token_id in stop_token_ids:
                try:
                    stop_str = self._tokenizer.decode([token_id])
                    if stop_str.strip():  # Only add non-empty strings
                        stop_strings.append(stop_str)
                except Exception:
                    logger.warning(f"Could not decode stop token ID: {token_id}")
            
            # Create sampling parameters
            sampling_params = SamplingParams(
                max_tokens=max_tokens,
                temperature=temperature,
                stop=stop_strings if stop_strings else None,
                include_stop_str_in_output=False,
            )
            
            # Generate completion
            outputs = self._engine.generate([prefill_text], sampling_params)
            
            if not outputs:
                raise GenerationError("No output generated")
                
            output = outputs[0]
            completion_text = output.outputs[0].text
            finish_reason = output.outputs[0].finish_reason
            
            # Tokenize the completion to get token IDs
            completion_tokens = self._tokenizer.encode(completion_text)
            
            # Calculate usage statistics
            prompt_tokens = len(prefill_ids)
            completion_token_count = len(completion_tokens)
            total_tokens = prompt_tokens + completion_token_count
            
            return {
                "completion_tokens": completion_tokens,
                "completion_text": completion_text,
                "finish_reason": finish_reason,
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_token_count,
                    "total_tokens": total_tokens,
                }
            }
            
        except Exception as e:
            raise GenerationError(f"vLLM generation failed: {str(e)}") from e
    
    def is_available(self) -> bool:
        """Check if vLLM is available and can be initialized."""
        try:
            # If engine is already initialized, it's available
            if self._engine is not None:
                return True
                
            import vllm
            # Try to initialize if not already done
            self._initialize_engine()
            return True
        except (ImportError, ModelNotAvailableError):
            return False
        except Exception as e:
            logger.warning(f"vLLM availability check failed: {e}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model."""
        if self._model_info is None:
            try:
                self._initialize_engine()
            except (ImportError, ModelNotAvailableError):
                # Return fallback info if initialization fails
                return {
                    "name": self.model_name,
                    "provider": "vllm", 
                    "supports_tokens": True,
                    "status": "not_initialized"
                }
        return self._model_info or {
            "name": self.model_name,
            "provider": "vllm", 
            "supports_tokens": True,
            "status": "not_initialized"
        }