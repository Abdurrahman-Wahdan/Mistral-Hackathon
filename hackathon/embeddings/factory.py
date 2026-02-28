"""
Embedding factory with provider-based architecture.

Providers:
- openai: OpenAI embeddings (text-embedding-*)
- google: Google embeddings (models/embedding-*, gemini-embedding-*)
- local: Local models (qwen3-8b, etc.)

Best Practice - Always specify provider explicitly:
    from embeddings.factory import get_embedding

    emb = get_embedding("text-embedding-3-large", provider="openai")
    emb = get_embedding("models/gemini-embedding-001", provider="google")
    emb = get_embedding("qwen3-8b", provider="local")
"""

import logging
from typing import Optional, List, Dict, Any
from langchain_core.embeddings import Embeddings

from config.settings import settings
from embeddings.providers import PROVIDERS, get_provider

logger = logging.getLogger(__name__)


def get_embedding(
    model_id: Optional[str] = None,
    provider: Optional[str] = None,
    **kwargs
) -> Embeddings:
    """
    Create an embedding model instance.

    Args:
        model_id: Embedding model identifier. If None, uses EMBEDDING_MODEL from settings
        provider: Provider name ("openai", "google", "local"). Recommended to specify.
        **kwargs: Provider-specific parameters

    Returns:
        LangChain Embeddings instance
    """
    model_id = model_id or settings.EMBEDDING_MODEL

    logger.info(f"Creating embedding model: {model_id}" +
                (f" (provider: {provider})" if provider else " (auto-detect)"))

    provider_instance = get_provider(model_id, provider_name=provider)

    if settings.EMBEDDING_DIMENSIONS:
        if provider_instance.provider_name == "google":
            kwargs.setdefault("output_dimensionality", settings.EMBEDDING_DIMENSIONS)
        else:
            kwargs.setdefault("dimensions", settings.EMBEDDING_DIMENSIONS)

    return provider_instance.create(model_id, **kwargs)


def list_supported_models() -> Dict[str, List[Dict[str, Any]]]:
    """List all supported embedding models by provider."""
    all_models = {}

    for provider in PROVIDERS:
        try:
            models = provider.fetch_available_models()
            if models:
                all_models[provider.provider_name] = models
        except Exception as e:
            logger.error(f"Failed to fetch models from {provider.provider_name}: {e}")

    return all_models


def embed_texts_batch(
    texts: List[str],
    model_id: Optional[str] = None,
    batch_size: int = 100,
    **kwargs
) -> List[List[float]]:
    """
    Generate embeddings for a list of texts with batching.

    Args:
        texts: List of texts to embed
        model_id: Embedding model to use (default from settings)
        batch_size: Batch size for processing
        **kwargs: Additional parameters for get_embedding()

    Returns:
        List of embedding vectors
    """
    if not texts:
        return []

    embedding_model = get_embedding(model_id, **kwargs)

    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        embeddings = embedding_model.embed_documents(batch)
        all_embeddings.extend(embeddings)

        if i + batch_size < len(texts):
            logger.info(f"Processed {i + batch_size}/{len(texts)} embeddings")

    logger.info(f"Generated {len(all_embeddings)} embeddings total")
    return all_embeddings


def clear_embedding_cache():
    """Clear all embedding model caches."""
    from embeddings.providers import PROVIDERS
    from embeddings.providers.local_provider import clear_local_model_cache

    for provider in PROVIDERS:
        if hasattr(provider.fetch_available_models, 'cache_clear'):
            provider.fetch_available_models.cache_clear()
            logger.info(f"Cleared {provider.provider_name} model list cache")

    clear_local_model_cache()
    logger.info("All embedding caches cleared")
