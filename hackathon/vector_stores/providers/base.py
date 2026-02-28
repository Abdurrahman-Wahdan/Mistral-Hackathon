"""
Base provider class for vector stores.

All vector store providers must inherit from BaseVectorStoreProvider and implement:
- provider_name: Unique identifier for the provider
- create(): Method to instantiate the vector store
- get_default_collections(): Default collection names for this provider
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from langchain_core.vectorstores import VectorStore
from langchain_core.embeddings import Embeddings


class BaseVectorStoreProvider(ABC):
    """Base class for all vector store providers."""

    provider_name: str = ""

    @abstractmethod
    def create(
        self,
        collection_name: str,
        embedding: Embeddings,
        **kwargs
    ) -> VectorStore:
        """
        Create a vector store instance.

        Args:
            collection_name: Name of the collection to use
            embedding: Embedding model instance
            **kwargs: Provider-specific configuration

        Returns:
            LangChain VectorStore instance
        """
        pass

    def get_default_collections(self) -> Dict[str, str]:
        """Get default collection names for this provider."""
        return {}

    def get_info(self) -> Dict[str, Any]:
        """Get provider information."""
        return {
            "name": self.provider_name,
            "status": "unknown",
            "requires": [],
            "features": [],
        }
