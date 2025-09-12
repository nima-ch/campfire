"""
LLM Provider factory and configuration management.

This module provides factory functions to create and manage different
LLM provider instances based on configuration and availability.
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Type

from .base import LLMProvider, ModelNotAvailableError
from .ollama_provider import OllamaProvider
from .vllm_provider import VLLMProvider
from .lmstudio_provider import LMStudioProvider

logger = logging.getLogger(__name__)


class ProviderType(Enum):
    """Enumeration of supported LLM provider types."""
    VLLM = "vllm"
    OLLAMA = "ollama"
    LMSTUDIO = "lmstudio"


class ProviderConfig:
    """Configuration class for LLM providers."""
    
    def __init__(
        self,
        provider_type: ProviderType,
        model_name: str = "gpt-oss:20b",
        **kwargs
    ):
        """
        Initialize provider configuration.
        
        Args:
            provider_type: Type of provider to use
            model_name: Name of the model to load
            **kwargs: Provider-specific configuration options
        """
        self.provider_type = provider_type
        self.model_name = model_name
        self.config = kwargs
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "ProviderConfig":
        """Create ProviderConfig from dictionary."""
        provider_type_str = config_dict.get("provider", "ollama")
        try:
            provider_type = ProviderType(provider_type_str.lower())
        except ValueError:
            logger.warning(f"Unknown provider type: {provider_type_str}, defaulting to ollama")
            provider_type = ProviderType.OLLAMA
            
        model_name = config_dict.get("model_name", "gpt-oss:20b")
        
        # Extract provider-specific config
        config = {k: v for k, v in config_dict.items() 
                 if k not in ["provider", "model_name"]}
        
        return cls(provider_type, model_name, **config)


def create_provider(config: ProviderConfig) -> LLMProvider:
    """
    Create an LLM provider instance based on configuration.
    
    Args:
        config: Provider configuration
        
    Returns:
        Initialized LLM provider instance
        
    Raises:
        ModelNotAvailableError: If the provider cannot be created or initialized
    """
    provider_classes: Dict[ProviderType, Type[LLMProvider]] = {
        ProviderType.VLLM: VLLMProvider,
        ProviderType.OLLAMA: OllamaProvider,
        ProviderType.LMSTUDIO: LMStudioProvider,
    }
    
    provider_class = provider_classes.get(config.provider_type)
    if provider_class is None:
        raise ModelNotAvailableError(f"Unknown provider type: {config.provider_type}")
    
    try:
        # Create provider instance with configuration
        provider = provider_class(
            model_name=config.model_name,
            **config.config
        )
        
        # Verify the provider is available
        if not provider.is_available():
            raise ModelNotAvailableError(
                f"Provider {config.provider_type.value} is not available"
            )
        
        logger.info(f"Created {config.provider_type.value} provider with model: {config.model_name}")
        return provider
        
    except Exception as e:
        raise ModelNotAvailableError(
            f"Failed to create {config.provider_type.value} provider: {str(e)}"
        ) from e


def get_available_providers() -> List[Dict[str, Any]]:
    """
    Get a list of available LLM providers on the system.
    
    Returns:
        List of dictionaries containing provider information
    """
    providers = []
    
    # Test each provider type
    for provider_type in ProviderType:
        try:
            config = ProviderConfig(provider_type)
            provider = create_provider(config)
            
            model_info = provider.get_model_info()
            providers.append({
                "type": provider_type.value,
                "available": True,
                "supports_tokens": provider.supports_tokens(),
                "model_info": model_info,
            })
            
        except Exception as e:
            providers.append({
                "type": provider_type.value,
                "available": False,
                "error": str(e),
                "supports_tokens": False,
            })
            logger.debug(f"Provider {provider_type.value} not available: {e}")
    
    return providers


def create_best_available_provider(
    preferred_order: Optional[List[ProviderType]] = None,
    model_name: str = "gpt-oss:20b",
    **kwargs
) -> LLMProvider:
    """
    Create the best available LLM provider based on preference order.
    
    Args:
        preferred_order: List of provider types in order of preference
        model_name: Name of the model to use
        **kwargs: Additional configuration options
        
    Returns:
        The best available LLM provider
        
    Raises:
        ModelNotAvailableError: If no providers are available
    """
    if preferred_order is None:
        # Default preference: vLLM (best performance) > Ollama (most accessible) > LM Studio
        preferred_order = [ProviderType.VLLM, ProviderType.OLLAMA, ProviderType.LMSTUDIO]
    
    last_error = None
    
    for provider_type in preferred_order:
        try:
            config = ProviderConfig(provider_type, model_name, **kwargs)
            provider = create_provider(config)
            
            logger.info(f"Successfully created {provider_type.value} provider")
            return provider
            
        except Exception as e:
            last_error = e
            logger.debug(f"Failed to create {provider_type.value} provider: {e}")
            continue
    
    # If we get here, no providers were available
    available_info = get_available_providers()
    available_types = [p["type"] for p in available_info if p["available"]]
    
    if available_types:
        error_msg = f"No providers from preferred list {[p.value for p in preferred_order]} are available. Available providers: {available_types}"
    else:
        error_msg = "No LLM providers are available on this system"
    
    raise ModelNotAvailableError(error_msg) from last_error


def create_provider_from_string(provider_type: str) -> LLMProvider:
    """
    Create an LLM provider instance based on provider type string.
    
    Args:
        provider_type: Provider type as string (ollama, vllm, lmstudio)
        
    Returns:
        Initialized LLM provider instance
        
    Raises:
        ModelNotAvailableError: If the provider cannot be created or initialized
    """
    try:
        provider_enum = ProviderType(provider_type.lower())
        config = ProviderConfig(provider_enum)
        return create_provider(config)
    except ValueError:
        raise ModelNotAvailableError(f"Unknown provider type: {provider_type}")


def auto_detect_provider(model_name: str = "gpt-oss:20b") -> LLMProvider:
    """
    Automatically detect and create the best available provider.
    
    This function tries providers in order of capability and performance:
    1. vLLM (best performance, full token support)
    2. Ollama (good balance of features and accessibility)
    3. LM Studio (alternative option)
    
    Args:
        model_name: Name of the model to use
        
    Returns:
        The best available LLM provider
        
    Raises:
        ModelNotAvailableError: If no providers are available
    """
    return create_best_available_provider(model_name=model_name)