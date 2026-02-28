"""
Vector store factory with provider-based architecture.

Usage:
    from vector_stores.factory import get_vector_store
    from embeddings.factory import get_embedding

    emb = get_embedding("models/gemini-embedding-001", provider="google")
    db = get_vector_store("qdrant", "my_collection", emb)
"""

import logging
from typing import List, Dict, Any
from langchain_core.vectorstores import VectorStore
from langchain_core.embeddings import Embeddings

from config.settings import settings
from vector_stores.providers import get_provider, list_providers, PROVIDERS

logger = logging.getLogger(__name__)


def get_vector_store(
    provider: str,
    collection_name: str,
    embedding: Embeddings,
    **kwargs
) -> VectorStore:
    """
    Create a vector store instance using provider pattern.

    Args:
        provider: Vector store provider name (currently only "qdrant")
        collection_name: Name of the collection to use
        embedding: Embedding model instance from get_embedding()
        **kwargs: Provider-specific configuration

    Returns:
        LangChain VectorStore instance
    """
    logger.info(f"Creating vector store: {provider}/{collection_name}")
    provider_instance = get_provider(provider)
    return provider_instance.create(collection_name, embedding, **kwargs)


def list_supported_providers() -> List[str]:
    """List all available vector store providers."""
    return list_providers()


def get_provider_info(provider: str) -> Dict[str, Any]:
    """Get detailed information about a specific provider."""
    provider_instance = get_provider(provider)
    info = provider_instance.get_info()
    info["default_collections"] = provider_instance.get_default_collections()
    return info


def get_default_collection_name(data_type: str = "documents", provider: str = "qdrant") -> str:
    """Get default collection name based on data type and provider."""
    provider_instance = get_provider(provider)
    collections = provider_instance.get_default_collections()
    return collections.get(data_type, data_type)


def create_embedding_pipeline(
    embedding_model: str = None,
    embedding_provider: str = None,
    vector_store_provider: str = "qdrant",
    collection_name: str = "documents",
    embedding_kwargs: Dict[str, Any] = None,
    vector_store_kwargs: Dict[str, Any] = None,
) -> tuple:
    """
    Create both embedding model and vector store in one call.

    Args:
        embedding_model: Embedding model ID (defaults to settings.EMBEDDING_MODEL)
        embedding_provider: Embedding provider name (defaults to settings.DEFAULT_EMBEDDING_PROVIDER)
        vector_store_provider: Vector store provider (default: "qdrant")
        collection_name: Collection name (default: "documents")
        embedding_kwargs: Parameters specific to embedding model
        vector_store_kwargs: Parameters specific to vector store

    Returns:
        Tuple of (embedding_model, vector_store)
    """
    from embeddings.factory import get_embedding

    embedding_model = embedding_model or settings.EMBEDDING_MODEL
    embedding_provider = embedding_provider or settings.DEFAULT_EMBEDDING_PROVIDER
    embedding_kwargs = embedding_kwargs or {}
    vector_store_kwargs = vector_store_kwargs or {}

    embedding = get_embedding(embedding_model, provider=embedding_provider, **embedding_kwargs)
    vector_store = get_vector_store(
        provider=vector_store_provider,
        collection_name=collection_name,
        embedding=embedding,
        **vector_store_kwargs
    )

    return embedding, vector_store


def clear_vector_store_cache():
    """Clear all vector store caches."""
    from vector_stores.providers.qdrant_provider import clear_qdrant_client_cache
    clear_qdrant_client_cache()
    logger.info("All vector store caches cleared")
