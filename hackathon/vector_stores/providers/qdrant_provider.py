"""
Qdrant vector store provider using centralized client factory.
"""

import logging
from typing import Dict, Any
from langchain_core.vectorstores import VectorStore
from langchain_core.embeddings import Embeddings

from config.settings import settings
from .base import BaseVectorStoreProvider
from vector_stores.client import get_qdrant_client, clear_client_cache

logger = logging.getLogger(__name__)


class QdrantProvider(BaseVectorStoreProvider):
    """Qdrant vector store provider with singleton client caching."""

    provider_name = "qdrant"

    def create(
        self,
        collection_name: str,
        embedding: Embeddings,
        **kwargs
    ) -> VectorStore:
        """
        Create Qdrant vector store using centralized client factory.

        Args:
            collection_name: Name of the Qdrant collection
            embedding: Embedding model instance
            **kwargs: Qdrant configuration (url, api_key, timeout, prefer_grpc)

        Returns:
            Qdrant VectorStore instance
        """
        try:
            from langchain_qdrant import Qdrant
        except ImportError:
            raise RuntimeError(
                "Qdrant dependencies not installed. "
                "Install with: pip install langchain-qdrant qdrant-client"
            )

        url = kwargs.get("url", settings.QDRANT_URL)
        api_key = kwargs.get("api_key", settings.QDRANT_API_KEY)
        timeout = kwargs.get("timeout", settings.QDRANT_TIMEOUT)
        prefer_grpc = kwargs.get("prefer_grpc", settings.QDRANT_PREFER_GRPC)

        client = get_qdrant_client(
            url=url,
            api_key=api_key,
            timeout=timeout,
            prefer_grpc=prefer_grpc
        )

        try:
            vector_store = Qdrant(
                client=client,
                collection_name=collection_name,
                embeddings=embedding,
            )
            logger.info(f"Created Qdrant vector store: {collection_name}")
            return vector_store
        except Exception as e:
            logger.error(f"Failed to create Qdrant vector store: {e}")
            raise RuntimeError(f"Could not initialize Qdrant store: {e}")

    def get_default_collections(self) -> Dict[str, str]:
        """Get default Qdrant collection names."""
        return {
            "connectors": settings.QDRANT_COLLECTION_CONNECTORS,
            "actions": settings.QDRANT_COLLECTION_ACTIONS,
            "documents": "documents",
        }

    def get_info(self) -> Dict[str, Any]:
        """Get Qdrant provider information."""
        return {
            "name": self.provider_name,
            "status": "production",
            "requires": ["langchain-qdrant", "qdrant-client"],
            "features": [
                "vector_similarity_search",
                "metadata_filtering",
                "hybrid_search",
                "grpc_support",
            ],
            "default_url": settings.QDRANT_URL,
        }


def clear_qdrant_client_cache():
    """Clear the Qdrant client cache."""
    clear_client_cache()
