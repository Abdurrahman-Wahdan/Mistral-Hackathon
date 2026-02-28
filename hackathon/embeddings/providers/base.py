"""
Base provider class for embedding models.

Providers fetch available models dynamically from their APIs rather than
using hardcoded lists. This ensures we always have the latest models.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from langchain_core.embeddings import Embeddings


class BaseEmbeddingProvider(ABC):
    """Base class for all embedding providers."""

    provider_name: str = ""

    @staticmethod
    @abstractmethod
    def matches(model_id: str) -> bool:
        """Check if this provider supports the given model ID."""
        pass

    @abstractmethod
    def create(self, model_id: str, **kwargs) -> Embeddings:
        """Create an embedding model instance."""
        pass

    @abstractmethod
    def fetch_available_models(self) -> List[Dict[str, Any]]:
        """Fetch available embedding models from provider API."""
        pass

    def get_dimensions(self, model_id: str) -> Optional[int]:
        """Get embedding dimensions for a model."""
        try:
            models = self.fetch_available_models()
            for model in models:
                if model["id"] == model_id:
                    return model.get("dimensions")
            return None
        except Exception:
            return None
