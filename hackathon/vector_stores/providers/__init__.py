"""
Vector store provider registry.

Auto-imports and registers all available vector store providers.
Currently only Qdrant is supported (production use).

Best Practice: Specify provider explicitly when multiple providers are available.
Example: get_provider("qdrant")

Future: When adding new providers, just add them to the PROVIDERS list.
"""

from typing import List
from .base import BaseVectorStoreProvider
from .qdrant_provider import QdrantProvider


# Provider registry - all available providers
PROVIDERS: List[BaseVectorStoreProvider] = [
    QdrantProvider(),    # Production vector store
]


def get_provider(provider_name: str) -> BaseVectorStoreProvider:
    """
    Get the vector store provider by name.

    Args:
        provider_name: Provider identifier (currently only "qdrant")

    Returns:
        Provider instance that can create vector stores

    Raises:
        ValueError: If provider name is not found
    """
    provider_name_lower = provider_name.lower()

    for provider in PROVIDERS:
        if provider.provider_name == provider_name_lower:
            return provider

    available = ', '.join(p.provider_name for p in PROVIDERS)
    raise ValueError(
        f"Unknown vector store provider: {provider_name}\n"
        f"Available providers: {available}"
    )


def list_providers() -> List[str]:
    """List all available vector store provider names."""
    return [p.provider_name for p in PROVIDERS]


__all__ = [
    "BaseVectorStoreProvider",
    "QdrantProvider",
    "PROVIDERS",
    "get_provider",
    "list_providers",
]
