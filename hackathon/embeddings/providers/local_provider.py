"""
Local embedding provider for locally-hosted models.

Supports local models like Qwen, BGE, and other sentence-transformers models.
Implements instance-level caching to avoid reloading heavy models.
"""

import logging
from typing import List, Dict, Any, Optional
from langchain_core.embeddings import Embeddings

from config.settings import settings
from .base import BaseEmbeddingProvider

logger = logging.getLogger(__name__)

# Module-level cache for local model instances
_LOCAL_MODEL_CACHE: Dict[tuple, Embeddings] = {}


class LocalProvider(BaseEmbeddingProvider):
    """Local embedding provider for locally-hosted models."""

    provider_name = "local"

    _supported_models = {
        "qwen3-8b": {
            "name": "Qwen3 8B",
            "dimensions": 4096,
            "implementation": "qwen3"
        },
        "qwen3": {
            "name": "Qwen3",
            "dimensions": 4096,
            "implementation": "qwen3"
        },
        "qwen": {
            "name": "Qwen",
            "dimensions": 4096,
            "implementation": "qwen3"
        },
    }

    @staticmethod
    def matches(model_id: str) -> bool:
        """Check if model ID matches a local model pattern."""
        model_lower = model_id.lower()

        if model_lower in LocalProvider._supported_models:
            return True

        local_prefixes = ["qwen", "qwen3"]
        return any(model_lower.startswith(prefix) for prefix in local_prefixes)

    def create(self, model_id: str, **kwargs) -> Embeddings:
        """Create local embedding instance."""
        model_lower = model_id.lower()

        implementation = None
        if model_lower in self._supported_models:
            implementation = self._supported_models[model_lower]["implementation"]
        elif any(model_lower.startswith(prefix) for prefix in ["qwen3", "qwen"]):
            implementation = "qwen3"

        if not implementation:
            raise ValueError(
                f"Unsupported local model: {model_id}\n"
                f"Supported local models: {', '.join(self._supported_models.keys())}"
            )

        if implementation == "qwen3":
            return self._create_qwen3(model_id, **kwargs)

        raise ValueError(f"Unknown implementation: {implementation}")

    def _create_qwen3(self, model_id: str, **kwargs) -> Embeddings:
        """Create Qwen3 embedding instance with caching."""
        try:
            from embeddings.models.qwen_embedding import Qwen3Embedding

            device = kwargs.pop("device", settings.EMBEDDING_DEVICE)
            batch_size = kwargs.pop("batch_size", 16)
            normalize = kwargs.pop("normalize_embeddings", True)
            max_tokens = kwargs.pop("max_tokens", 32768)
            dimensions = kwargs.pop("dimensions", settings.EMBEDDING_DIMENSIONS)

            cache_key = (model_id, device, batch_size, normalize, max_tokens, dimensions)

            if cache_key in _LOCAL_MODEL_CACHE:
                logger.info(f"Using cached Qwen3 embedding: {model_id} (device={device})")
                return _LOCAL_MODEL_CACHE[cache_key]

            logger.info(f"Loading Qwen3 embedding (may take 1-2 minutes): {model_id}")

            instance = Qwen3Embedding(
                model_name=model_id,
                device=device,
                batch_size=batch_size,
                normalize_embeddings=normalize,
                max_tokens=max_tokens,
                dimensions=dimensions,
                **kwargs
            )

            _LOCAL_MODEL_CACHE[cache_key] = instance
            logger.info(f"Qwen3 model loaded and cached: {model_id}")

            return instance

        except ImportError as e:
            raise RuntimeError(
                f"Failed to import Qwen3 embedding model: {e}\n"
                "Make sure sentence-transformers is installed: pip install sentence-transformers"
            )

    def fetch_available_models(self) -> List[Dict[str, Any]]:
        """Get available local embedding models."""
        return [
            {
                "id": model_id,
                "name": info["name"],
                "dimensions": info["dimensions"],
                "provider": "local"
            }
            for model_id, info in self._supported_models.items()
        ]


def clear_local_model_cache():
    """Clear the local model instance cache."""
    global _LOCAL_MODEL_CACHE
    cache_size = len(_LOCAL_MODEL_CACHE)
    _LOCAL_MODEL_CACHE.clear()
    logger.info(f"Cleared local model cache ({cache_size} instances removed)")
