"""
Embedding provider registry.

Auto-imports and registers all available embedding providers.
Providers are checked in order during auto-detection (first match wins).

Best Practice: Always specify provider explicitly to avoid iteration overhead.
Example: get_embedding("qwen3-8b", provider="local")
"""

from typing import List, Optional
from .base import BaseEmbeddingProvider
from .openai_provider import OpenAIProvider
from .google_provider import GoogleProvider
from .local_provider import LocalProvider


# Provider registry - all available providers
# Order matters for auto-detection! Specific patterns before generic ones.
PROVIDERS: List[BaseEmbeddingProvider] = [
    OpenAIProvider(),    # Matches: text-embedding-*
    GoogleProvider(),    # Matches: models/embedding-*, gemini-*, gecko-*
    LocalProvider(),     # Matches: qwen*, bge-*, all-minilm*, etc.
]


def get_provider(model_id: str, provider_name: Optional[str] = None) -> BaseEmbeddingProvider:
    """
    Get the provider that matches the given model ID.

    Args:
        model_id: The embedding model identifier
        provider_name: Optional provider name to skip auto-detection ("openai", "google", "local")

    Returns:
        Provider instance that can handle the model

    Raises:
        ValueError: If no provider matches the model ID or if specified provider doesn't exist
    """
    # If provider name is specified, find it directly
    if provider_name:
        for provider in PROVIDERS:
            if provider.provider_name == provider_name.lower():
                if not provider.matches(model_id):
                    raise ValueError(
                        f"Provider '{provider_name}' does not support model '{model_id}'. "
                        f"Please check the model ID or use auto-detection."
                    )
                return provider

        raise ValueError(
            f"Provider '{provider_name}' not found.\n"
            f"Available providers: {', '.join(p.provider_name for p in PROVIDERS)}"
        )

    # Auto-detect provider by matching model ID
    for provider in PROVIDERS:
        if provider.matches(model_id):
            return provider

    raise ValueError(
        f"Unknown embedding model: {model_id}\n"
        f"No provider found to handle this model.\n"
        f"Available providers: {', '.join(p.provider_name for p in PROVIDERS)}"
    )


__all__ = [
    "BaseEmbeddingProvider",
    "OpenAIProvider",
    "GoogleProvider",
    "LocalProvider",
    "PROVIDERS",
    "get_provider",
]
