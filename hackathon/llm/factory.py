"""
Mistral-only LLM factory with model discovery and caching.
"""

import logging
from typing import List, Dict, Optional, Any

import httpx
from langchain_core.language_models.chat_models import BaseChatModel

try:
    from langchain_mistralai import ChatMistralAI
except ImportError:
    ChatMistralAI = None

from config.settings import settings

logger = logging.getLogger(__name__)

_MODEL_CACHE: Dict[str, List[Dict[str, Any]]] = {}
_ALL_MODELS_CACHE: Optional[Dict[str, List[Dict[str, Any]]]] = None

MISTRAL_MODEL_PREFIXES = ("mistral", "open-mistral", "codestral", "pixtral", "ministral")


class ProviderConfigError(Exception):
    """Raised when provider configuration is missing or invalid."""
    pass


class ProviderConnectionError(Exception):
    """Raised when connection to provider API fails."""
    pass


class UnknownProviderError(Exception):
    """Raised when model ID doesn't match the supported provider."""
    pass


def _validate_mistral_model(model_id: str) -> None:
    """Ensure only Mistral-family models are used in this hackathon project."""
    if not model_id.lower().startswith(MISTRAL_MODEL_PREFIXES):
        raise UnknownProviderError(
            "Only Mistral models are supported. "
            f"Got: {model_id}. Expected prefixes: {', '.join(MISTRAL_MODEL_PREFIXES)}"
        )


def build_llm_params(
    base_params: Dict[str, Any],
    temperature: float,
    max_tokens: Optional[int] = None,
    **extra_kwargs
) -> Dict[str, Any]:
    """Build LLM parameters with consistent structure."""
    params = {**base_params, "temperature": temperature}
    if max_tokens is not None:
        params["max_tokens"] = max_tokens
    return {**params, **extra_kwargs}


def get_llm(
    model_id: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    **kwargs
) -> BaseChatModel:
    """
    Create a Mistral LLM instance.

    Args:
        model_id: Mistral model identifier
        temperature: Sampling temperature (0.0 to 1.0)
        max_tokens: Maximum tokens to generate
        **kwargs: Additional model parameters
    """
    if ChatMistralAI is None:
        raise ProviderConfigError(
            "langchain-mistralai is not installed. Install it to use Mistral models."
        )
    if not settings.MISTRAL_API_KEY:
        raise ProviderConfigError("MISTRAL_API_KEY not configured in settings")

    model_id = model_id or settings.DEFAULT_MODEL
    temperature = temperature if temperature is not None else settings.DEFAULT_TEMPERATURE
    _validate_mistral_model(model_id)

    base_params = {"model": model_id}
    params = build_llm_params(base_params, temperature, max_tokens, **kwargs)

    # Keep compatibility with langchain-mistralai versions using different key names.
    try:
        return ChatMistralAI(api_key=settings.MISTRAL_API_KEY, **params)
    except TypeError:
        return ChatMistralAI(mistral_api_key=settings.MISTRAL_API_KEY, **params)


def fetch_mistral_models_http() -> Dict[str, Any]:
    """Fetch raw model data from Mistral API."""
    if not settings.MISTRAL_API_KEY:
        raise ProviderConfigError("MISTRAL_API_KEY not configured in settings")

    try:
        response = httpx.get(
            "https://api.mistral.ai/v1/models",
            headers={"Authorization": f"Bearer {settings.MISTRAL_API_KEY}"},
            timeout=10.0
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        raise ProviderConnectionError(f"Failed to fetch Mistral models: {exc}") from exc


def parse_mistral_models(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse Mistral API response into standardized model list."""
    models = []

    for model in data.get("data", []):
        model_id = model.get("id")
        if not model_id:
            continue
        if any(excluded in model_id for excluded in ["embed", "ocr", "moderation"]):
            continue
        if model_id.startswith(MISTRAL_MODEL_PREFIXES):
            models.append({
                "id": model_id,
                "name": model_id.replace("-", " ").title(),
                "provider": "mistral",
                "context_window": model.get("max_context_length")
            })

    return models


def list_mistral_models(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """Fetch available Mistral models from API."""
    if not force_refresh and "mistral" in _MODEL_CACHE:
        return _MODEL_CACHE["mistral"]

    if not settings.MISTRAL_API_KEY:
        logger.warning("MISTRAL_API_KEY not set, skipping Mistral models")
        _MODEL_CACHE["mistral"] = []
        return _MODEL_CACHE["mistral"]

    try:
        raw_data = fetch_mistral_models_http()
        models = parse_mistral_models(raw_data)
        logger.info(f"Fetched {len(models)} Mistral models")
        _MODEL_CACHE["mistral"] = models
        return models
    except Exception as exc:
        logger.error(f"Failed to fetch Mistral models: {exc}")
        _MODEL_CACHE["mistral"] = []
        return _MODEL_CACHE["mistral"]


def clear_model_cache() -> None:
    """Clear cached model listings."""
    global _ALL_MODELS_CACHE
    _MODEL_CACHE.clear()
    _ALL_MODELS_CACHE = None
    logger.info("LLM model cache cleared")


def list_all_models(force_refresh: bool = False) -> Dict[str, List[Dict[str, Any]]]:
    """Get all available models from configured providers (Mistral-only)."""
    global _ALL_MODELS_CACHE
    if not force_refresh and _ALL_MODELS_CACHE is not None:
        return _ALL_MODELS_CACHE

    logger.info("Fetching models from Mistral provider...")
    all_models = {"mistral": list_mistral_models(force_refresh=force_refresh)}
    all_models = {k: v for k, v in all_models.items() if v}

    total = sum(len(models) for models in all_models.values())
    logger.info(f"Total models available: {total}")

    _ALL_MODELS_CACHE = all_models
    return all_models
