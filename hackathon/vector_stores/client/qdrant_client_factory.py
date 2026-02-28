"""
Centralized Qdrant client factory with singleton pattern.

Provides a shared AsyncQdrantClient instance across the entire application
to avoid redundant connections and improve resource efficiency.
"""

import logging
import threading
from typing import Optional, Dict, Any
from qdrant_client import AsyncQdrantClient

logger = logging.getLogger(__name__)

_ASYNC_CLIENT_CACHE: Dict[tuple, AsyncQdrantClient] = {}
_ASYNC_CLIENT_LOCK = threading.Lock()


def get_qdrant_client(
    url: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: Optional[int] = None,
    prefer_grpc: bool = False,
) -> AsyncQdrantClient:
    """
    Get or create a shared AsyncQdrantClient instance.

    Uses singleton pattern with caching based on connection parameters.

    Args:
        url: Qdrant server URL (defaults to settings.QDRANT_URL)
        api_key: API key for authentication (defaults to settings.QDRANT_API_KEY)
        timeout: Request timeout in seconds (defaults to settings.QDRANT_TIMEOUT)
        prefer_grpc: Use gRPC instead of HTTP

    Returns:
        Shared AsyncQdrantClient instance

    Raises:
        ValueError: If URL not configured
        RuntimeError: If client creation fails
    """
    from config.settings import settings

    url = url or settings.QDRANT_URL
    api_key = api_key or settings.QDRANT_API_KEY
    timeout = timeout or settings.QDRANT_TIMEOUT

    if not url:
        raise ValueError(
            "Qdrant URL not configured. "
            "Please set QDRANT_URL in your .env file or pass url parameter."
        )

    cache_key = (url, api_key or "", timeout, prefer_grpc)

    cached_client = _ASYNC_CLIENT_CACHE.get(cache_key)
    if cached_client is not None:
        logger.debug(f"Using cached AsyncQdrantClient for {url}")
        return cached_client

    with _ASYNC_CLIENT_LOCK:
        cached_client = _ASYNC_CLIENT_CACHE.get(cache_key)
        if cached_client is not None:
            return cached_client

        logger.info(f"Creating new AsyncQdrantClient for {url}")
        try:
            client = AsyncQdrantClient(
                url=url,
                api_key=api_key if api_key else None,
                timeout=timeout,
                prefer_grpc=prefer_grpc,
            )

            _ASYNC_CLIENT_CACHE[cache_key] = client
            logger.info(f"AsyncQdrantClient cached for {url}")
            return client

        except Exception as e:
            logger.error(f"Failed to create AsyncQdrantClient: {e}")
            raise RuntimeError(f"Could not connect to Qdrant at {url}: {e}")


def clear_client_cache():
    """Clear the Qdrant client cache."""
    with _ASYNC_CLIENT_LOCK:
        async_cache_size = len(_ASYNC_CLIENT_CACHE)
        _ASYNC_CLIENT_CACHE.clear()
    logger.info(f"Cleared Qdrant client cache ({async_cache_size} clients removed)")


def get_client_info() -> Dict[str, Any]:
    """Get information about cached clients."""
    with _ASYNC_CLIENT_LOCK:
        cache_keys = list(_ASYNC_CLIENT_CACHE.keys())

    return {
        "cached_clients": len(cache_keys),
        "cache_keys": [
            {
                "url": key[0],
                "has_api_key": bool(key[1]),
                "timeout": key[2],
                "prefer_grpc": key[3]
            }
            for key in cache_keys
        ],
    }
