"""
Base Elasticsearch client with async support and production-ready configuration.

Provides reusable AsyncElasticsearch client with:
- Automatic retry logic with exponential backoff
- Connection pooling (managed automatically by client)
- Proper lifecycle management
- HTTP compression for bandwidth optimization
- Health check capabilities
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from elasticsearch import AsyncElasticsearch, NotFoundError

from .exceptions import ElasticsearchConnectionError, ElasticsearchIndexError

logger = logging.getLogger(__name__)


class BaseElasticsearchClient:
    """
    Base Elasticsearch client for all AI projects.

    Manages AsyncElasticsearch connection with production-ready configuration:
    - Request timeout: 30s
    - Max retries: 3 with exponential backoff
    - Retry on timeout enabled
    - HTTP compression enabled for bandwidth efficiency
    - Proper async lifecycle management

    Usage:
        client = BaseElasticsearchClient(url="https://es.example.com:9200")
        es_client = await client.get_client()
        # ... perform operations ...
        await client.close()

    Or with context manager pattern (recommended for FastAPI):
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            client = BaseElasticsearchClient(url=settings.ELASTICSEARCH_URL)
            yield
            await client.close()
    """

    def __init__(
        self,
        url: str,
        api_key: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        request_timeout: int = 30,
        max_retries: int = 3,
        retry_on_timeout: bool = True,
    ):
        """
        Initialize Elasticsearch client.

        Args:
            url: Elasticsearch URL (e.g., "https://es.example.com:9200")
            api_key: Optional API key for authentication (preferred method)
            username: Optional username for basic auth
            password: Optional password for basic auth
            request_timeout: Request timeout in seconds (default: 30)
            max_retries: Maximum number of retries per request (default: 3)
            retry_on_timeout: Enable retry on timeout errors (default: True)
        """
        self.url = url
        self.api_key = api_key
        self.username = username
        self.password = password
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        self.retry_on_timeout = retry_on_timeout

        self._client: Optional[AsyncElasticsearch] = None
        self._init_lock = asyncio.Lock()

        logger.info(f"BaseElasticsearchClient initialized - URL: {self.url}")

    async def get_client(self) -> AsyncElasticsearch:
        """
        Get or create AsyncElasticsearch client.

        Thread-safe lazy initialization with proper connection configuration.

        Returns:
            AsyncElasticsearch client instance

        Raises:
            ElasticsearchConnectionError: If connection fails
        """
        if self._client is not None:
            return self._client

        async with self._init_lock:
            # Double-check after acquiring lock
            if self._client is not None:
                return self._client

            logger.info("Initializing new AsyncElasticsearch client connection...")

            try:
                # Build connection parameters following best practices
                conn_params = {
                    "hosts": [self.url],
                    "request_timeout": self.request_timeout,
                    "max_retries": self.max_retries,
                    "retry_on_timeout": self.retry_on_timeout,
                    "http_compress": True,  # Enable gzip compression for bandwidth efficiency
                }

                # Add authentication if provided
                # API key is preferred method (more secure, easier to rotate)
                if self.api_key:
                    conn_params["api_key"] = self.api_key
                    logger.debug("Using API key authentication")
                elif self.username and self.password:
                    conn_params["basic_auth"] = (self.username, self.password)
                    logger.debug("Using basic authentication")

                # Create client
                client = AsyncElasticsearch(**conn_params)
                self._client = client

                logger.info("AsyncElasticsearch client initialized successfully")
                return self._client

            except Exception as e:
                logger.error(f"Failed to create Elasticsearch client: {e}", exc_info=True)
                raise ElasticsearchConnectionError(f"Failed to initialize Elasticsearch client: {e}")

    async def close(self):
        """
        Close Elasticsearch client connection.

        IMPORTANT: Must be called before the client instance is garbage collected
        to avoid aiohttp unclosed connection warnings.

        Best practice: Use in FastAPI lifespan or similar cleanup hooks.
        """
        if self._client:
            logger.info("Closing AsyncElasticsearch client connection...")
            try:
                await self._client.close()
                self._client = None
                logger.info("AsyncElasticsearch client closed successfully")
            except Exception as e:
                logger.error(f"Error closing Elasticsearch client: {e}", exc_info=True)

    async def health_check(self) -> bool:
        """
        Check Elasticsearch cluster health.

        Returns:
            True if cluster is reachable and healthy, False otherwise
        """
        try:
            client = await self.get_client()
            health = await client.cluster.health()
            status = health.get("status", "unknown")
            logger.info(f"Elasticsearch health check: {status}")
            return status in ["green", "yellow"]  # Yellow is acceptable for single-node
        except Exception as e:
            logger.error(f"Elasticsearch health check failed: {e}")
            return False

    async def create_index_if_not_exists(
        self,
        index_name: str,
        mappings: Dict[str, Any],
        settings: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Create index with mappings if it doesn't exist.

        Handles race conditions from concurrent index creation gracefully.

        Args:
            index_name: Name of the index to create
            mappings: Index mappings (ES schema)
            settings: Optional index settings (shards, replicas, etc.)

        Returns:
            True if index was created or already exists, False on error

        Raises:
            ElasticsearchIndexError: If index creation fails unexpectedly
        """
        client = await self.get_client()

        try:
            # Check if index exists
            index_exists = await client.indices.exists(index=index_name)

            if index_exists:
                logger.debug(f"Index {index_name} already exists")
                return True

            # Create index with mappings
            logger.info(f"Creating Elasticsearch index: {index_name}")

            create_params = {
                "index": index_name,
                "mappings": mappings,
            }

            if settings:
                create_params["settings"] = settings
            else:
                # Default settings: 1 shard, 0 replicas (suitable for single-node dev)
                create_params["settings"] = {
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                }

            await client.indices.create(**create_params)
            logger.info(f"Index {index_name} created successfully")
            return True

        except NotFoundError as e:
            # NotFoundError here is unexpected; avoid recursive retries
            logger.error(
                f"Unexpected NotFoundError while creating index {index_name}: {e}",
                exc_info=True,
            )
            raise ElasticsearchIndexError(
                f"Unexpected error creating index {index_name}: {e}"
            )

        except Exception as e:
            # Handle concurrent creation race condition
            if "resource_already_exists_exception" in str(e):
                logger.debug(f"Index {index_name} already exists (concurrent creation)")
                return True

            # Unexpected error
            logger.error(f"Error creating index {index_name}: {e}", exc_info=True)
            raise ElasticsearchIndexError(f"Failed to create index {index_name}: {e}")

    async def index_exists(self, index_name: str) -> bool:
        """
        Check if an index exists.

        Args:
            index_name: Name of the index to check

        Returns:
            True if index exists, False otherwise
        """
        try:
            client = await self.get_client()
            return await client.indices.exists(index=index_name)
        except Exception as e:
            logger.error(f"Error checking if index {index_name} exists: {e}")
            return False
