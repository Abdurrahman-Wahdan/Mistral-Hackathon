"""
Google embedding provider with dynamic model discovery.
"""

import logging
from typing import List, Dict, Any
import httpx
from langchain_core.embeddings import Embeddings

from config.settings import settings
from .base import BaseEmbeddingProvider

logger = logging.getLogger(__name__)


class GoogleProvider(BaseEmbeddingProvider):
    """Google embedding provider with dynamic model fetching."""

    provider_name = "google"

    @staticmethod
    def matches(model_id: str) -> bool:
        """Check if model ID matches Google pattern."""
        model_lower = model_id.lower()
        return (
            model_lower.startswith("models/embedding") or
            model_lower.startswith("models/text-embedding") or
            ("embedding" in model_lower and ("gemini" in model_lower or "gecko" in model_lower))
        )

    def create(self, model_id: str, **kwargs) -> Embeddings:
        """Create Google embedding instance."""
        if not settings.GOOGLE_API_KEY:
            raise ValueError(
                "GOOGLE_API_KEY not configured in settings. "
                "Please set GOOGLE_API_KEY in your .env file."
            )

        try:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings

            logger.info(f"Creating Google embedding: {model_id}")

            return GoogleGenerativeAIEmbeddings(
                model=model_id,
                google_api_key=settings.GOOGLE_API_KEY,
                **kwargs
            )
        except ImportError:
            raise RuntimeError(
                "langchain-google-genai not installed. "
                "Install with: pip install langchain-google-genai"
            )

    def fetch_available_models(self) -> List[Dict[str, Any]]:
        """Fetch available Google embedding models from API."""
        api_key = settings.GOOGLE_API_KEY

        if not api_key:
            logger.warning("GOOGLE_API_KEY not set, cannot fetch Google models")
            return []

        try:
            response = httpx.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                params={"key": api_key},
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()

            embedding_models = []

            for model in data.get("models", []):
                model_name = model["name"]
                methods = model.get("supportedGenerationMethods", [])

                if "embedContent" not in methods:
                    continue

                if "embedding" not in model_name.lower():
                    continue

                dimensions = None
                if "outputDimensionality" in model:
                    dimensions = model["outputDimensionality"]
                else:
                    if "embedding-001" in model_name or "gecko" in model_name:
                        dimensions = 768
                    elif "text-embedding-004" in model_name:
                        dimensions = 768

                display_name = model.get("displayName", model_name.replace("models/", ""))

                embedding_models.append({
                    "id": model_name,
                    "name": display_name,
                    "dimensions": dimensions,
                    "provider": "google"
                })

            logger.info(f"Fetched {len(embedding_models)} Google embedding models")
            return embedding_models

        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to fetch Google models: HTTP {e.response.status_code}")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch Google models: {str(e)}")
            return []
