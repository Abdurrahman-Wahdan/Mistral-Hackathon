"""
OpenAI embedding provider with dynamic model discovery.
"""

import logging
from typing import List, Dict, Any
import httpx
from langchain_core.embeddings import Embeddings

from config.settings import settings
from .base import BaseEmbeddingProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseEmbeddingProvider):
    """OpenAI embedding provider with dynamic model fetching."""

    provider_name = "openai"

    @staticmethod
    def matches(model_id: str) -> bool:
        """Check if model ID matches OpenAI pattern."""
        return model_id.lower().startswith("text-embedding")

    def create(self, model_id: str, **kwargs) -> Embeddings:
        """Create OpenAI embedding instance."""
        if not settings.OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY not configured in settings. "
                "Please set OPENAI_API_KEY in your .env file."
            )

        try:
            from langchain_openai import OpenAIEmbeddings

            logger.info(f"Creating OpenAI embedding: {model_id}")

            return OpenAIEmbeddings(
                model=model_id,
                openai_api_key=settings.OPENAI_API_KEY,
                **kwargs
            )
        except ImportError:
            raise RuntimeError(
                "langchain-openai not installed. "
                "Install with: pip install langchain-openai"
            )

    def fetch_available_models(self) -> List[Dict[str, Any]]:
        """Fetch available OpenAI embedding models from API."""
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not set, cannot fetch OpenAI models")
            return []

        try:
            response = httpx.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()

            embedding_models = []

            dimensions_map = {
                "text-embedding-3-large": 3072,
                "text-embedding-3-small": 1536,
                "text-embedding-ada-002": 1536,
            }

            for model in data.get("data", []):
                model_id = model["id"]

                if "embedding" in model_id and model_id.startswith("text-embedding"):
                    embedding_models.append({
                        "id": model_id,
                        "name": model_id.replace("-", " ").title(),
                        "dimensions": dimensions_map.get(model_id, 1536),
                        "provider": "openai"
                    })

            logger.info(f"Fetched {len(embedding_models)} OpenAI embedding models")
            return embedding_models

        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to fetch OpenAI models: HTTP {e.response.status_code}")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch OpenAI models: {str(e)}")
            return []
