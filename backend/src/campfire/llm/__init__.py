"""
LLM Provider abstraction layer for Campfire.

This module provides a unified interface for different local LLM backends
including vLLM, Ollama, and LM Studio.
"""

from .base import LLMProvider
from .factory import create_provider, get_available_providers
from .ollama_provider import OllamaProvider
from .vllm_provider import VLLMProvider
from .lmstudio_provider import LMStudioProvider

__all__ = [
    "LLMProvider",
    "OllamaProvider", 
    "VLLMProvider",
    "LMStudioProvider",
    "create_provider",
    "get_available_providers",
]