"""
Mistral embedding provider with dynamic model discovery.
"""

import logging
from typing import List, Dict, Any

import httpx
from langchain_core.embeddings import Embeddings

from config.settings import settings
from .base import BaseEmbeddingProvider

logger = logging.getLogger(__name__)


class MistralProvider(BaseEmbeddingProvider):
    """Mistral embedding provider with dynamic model fetching."""

    provider_name = "mistral"

    @staticmethod
    def matches(model_id: str) -> bool:
        """Check if model ID matches Mistral embedding pattern."""
        model_lower = model_id.lower()
        return ("embed" in model_lower) and (
            model_lower.startswith("mistral")
            or model_lower.startswith("open-mistral")
            or model_lower.startswith("codestral")
            or model_lower.startswith("pixtral")
            or model_lower.startswith("ministral")
        )

    def create(self, model_id: str, **kwargs) -> Embeddings:
        """Create Mistral embedding instance."""
        if not settings.MISTRAL_API_KEY:
            raise ValueError(
                "MISTRAL_API_KEY not configured in settings. "
                "Please set MISTRAL_API_KEY in your .env file."
            )

        try:
            from langchain_mistralai import MistralAIEmbeddings

            logger.info(f"Creating Mistral embedding: {model_id}")

            # Mistral embedding client does not support a dimensions override.
            kwargs.pop("dimensions", None)
            kwargs.pop("output_dimensionality", None)

            return MistralAIEmbeddings(
                model=model_id,
                mistral_api_key=settings.MISTRAL_API_KEY,
                **kwargs
            )
        except ImportError:
            raise RuntimeError(
                "langchain-mistralai not installed. "
                "Install with: pip install langchain-mistralai"
            )

    def fetch_available_models(self) -> List[Dict[str, Any]]:
        """Fetch available Mistral embedding models from API."""
        if not settings.MISTRAL_API_KEY:
            logger.warning("MISTRAL_API_KEY not set, cannot fetch Mistral models")
            return []

        try:
            response = httpx.get(
                "https://api.mistral.ai/v1/models",
                headers={"Authorization": f"Bearer {settings.MISTRAL_API_KEY}"},
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()

            # Known defaults; Mistral may not expose dimensions in model metadata.
            dimensions_map = {
                "mistral-embed": 1024,
                "mistral-embed-latest": 1024,
            }

            embedding_models = []
            for model in data.get("data", []):
                model_id = model.get("id", "")
                if not model_id or "embed" not in model_id.lower():
                    continue

                embedding_models.append({
                    "id": model_id,
                    "name": model_id.replace("-", " ").title(),
                    "dimensions": dimensions_map.get(model_id),
                    "provider": "mistral",
                })

            logger.info(f"Fetched {len(embedding_models)} Mistral embedding models")
            return embedding_models

        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to fetch Mistral models: HTTP {e.response.status_code}")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch Mistral models: {str(e)}")
            return []
