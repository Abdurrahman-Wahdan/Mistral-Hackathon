"""
Common Elasticsearch CRUD operations with automatic tenant filtering.

Provides reusable operations that enforce multi-tenant isolation:
- ALL queries automatically filter by tenant_id + organization_id
- Defense-in-depth security (index-level + query-level + app-level)
- Consistent error handling
- Logging for audit trails

Security Model:
    1. Index-level isolation: Separate index per tenant
    2. Query-level filtering: ALL operations inject tenant filters
    3. Application-level validation: Verify tenant context before operations
"""

import logging
from typing import Optional, Dict, Any, List
from elasticsearch import AsyncElasticsearch, NotFoundError

from .exceptions import ElasticsearchQueryError

logger = logging.getLogger(__name__)


async def index_document(
    client: AsyncElasticsearch,
    index_name: str,
    doc_id: str,
    document: Dict[str, Any],
    tenant_id: str,
    organization_id: str,
    refresh: Any = False,
) -> str:
    """
    Index a document with automatic tenant metadata injection.

    Adds tenant_id and organization_id to document for query-level filtering.

    Args:
        client: AsyncElasticsearch client
        index_name: Target index name
        doc_id: Document ID
        document: Document data (will be modified to add tenant fields)
        tenant_id: Tenant identifier
        organization_id: Organization identifier
        refresh: Refresh policy - False (default), True, or "wait_for"

    Returns:
        Document ID

    Raises:
        ElasticsearchQueryError: If indexing fails
    """
    try:
        # Inject tenant metadata for query-level filtering
        doc_with_tenant = {
            **document,
            "tenant_id": tenant_id,
            "organization_id": organization_id,
        }

        response = await client.index(
            index=index_name,
            id=doc_id,
            document=doc_with_tenant,
            refresh=refresh,
        )

        logger.debug(
            f"Indexed document {doc_id} in {index_name} "
            f"(tenant: {tenant_id}, org: {organization_id}, result: {response['result']})"
        )

        return doc_id

    except Exception as e:
        logger.error(
            f"Error indexing document {doc_id} in {index_name}: {e}",
            exc_info=True,
        )
        raise ElasticsearchQueryError(f"Failed to index document: {e}")


async def get_document(
    client: AsyncElasticsearch,
    index_name: str,
    doc_id: str,
    tenant_id: str,
    organization_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Get document by ID with tenant verification.

    Verifies tenant_id and organization_id match before returning document.
    Defense-in-depth: Even if doc_id is compromised, can't access other tenant's data.

    Args:
        client: AsyncElasticsearch client
        index_name: Source index name
        doc_id: Document ID
        tenant_id: Tenant identifier (for verification)
        organization_id: Organization identifier (for verification)

    Returns:
        Document data or None if not found or tenant mismatch

    Raises:
        ElasticsearchQueryError: If retrieval fails unexpectedly
    """
    try:
        response = await client.get(
            index=index_name,
            id=doc_id,
        )

        if not response["found"]:
            return None

        doc = response["_source"]

        # Verify tenant ownership (defense-in-depth)
        if doc.get("tenant_id") != tenant_id or doc.get("organization_id") != organization_id:
            logger.warning(
                f"Tenant mismatch for document {doc_id}: "
                f"expected tenant {tenant_id}, org {organization_id}, "
                f"got tenant {doc.get('tenant_id')}, org {doc.get('organization_id')}"
            )
            return None

        logger.debug(
            f"Retrieved document {doc_id} from {index_name} "
            f"(tenant: {tenant_id}, org: {organization_id})"
        )

        return doc

    except NotFoundError:
        logger.debug(f"Document {doc_id} not found in {index_name}")
        return None

    except Exception as e:
        logger.error(
            f"Error retrieving document {doc_id} from {index_name}: {e}",
            exc_info=True,
        )
        raise ElasticsearchQueryError(f"Failed to get document: {e}")


async def search_documents(
    client: AsyncElasticsearch,
    index_name: str,
    tenant_id: str,
    organization_id: str,
    query: Optional[Dict[str, Any]] = None,
    size: int = 100,
    sort: Optional[List] = None,
    source: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Search documents with automatic tenant filtering.

    CRITICAL: ALL queries are wrapped with tenant_id + organization_id filters.
    This enforces multi-tenant isolation at the query level.

    Args:
        client: AsyncElasticsearch client
        index_name: Source index name
        tenant_id: Tenant identifier (injected as filter)
        organization_id: Organization identifier (injected as filter)
        query: Optional user query (will be combined with tenant filter)
        size: Maximum number of results (default: 100)
        sort: Optional sort criteria
        source: Optional list of fields to return (_source filtering)

    Returns:
        List of matching documents

    Raises:
        ElasticsearchQueryError: If search fails
    """
    try:
        # Build query with mandatory tenant filtering (defense-in-depth)
        user_query = query if query else {"match_all": {}}

        filtered_query = {
            "bool": {
                "must": user_query,
                "filter": [
                    {"term": {"tenant_id": tenant_id}},
                    {"term": {"organization_id": organization_id}},
                ],
            }
        }

        search_params = {
            "index": index_name,
            "query": filtered_query,
            "size": size,
        }

        if sort:
            search_params["sort"] = sort

        if source:
            search_params["_source"] = source

        response = await client.search(**search_params)

        hits = response["hits"]["hits"]
        documents = [hit["_source"] for hit in hits]

        logger.debug(
            f"Search in {index_name} returned {len(documents)} documents "
            f"(tenant: {tenant_id}, org: {organization_id})"
        )

        return documents

    except Exception as e:
        logger.error(
            f"Error searching in {index_name}: {e}",
            exc_info=True,
        )
        raise ElasticsearchQueryError(f"Failed to search documents: {e}")


async def delete_by_query(
    client: AsyncElasticsearch,
    index_name: str,
    tenant_id: str,
    organization_id: str,
    query: Optional[Dict[str, Any]] = None,
    refresh: bool = False,
) -> int:
    """
    Delete documents matching query with automatic tenant filtering.

    CRITICAL: Tenant filter is ALWAYS applied to prevent cross-tenant deletion.

    Args:
        client: AsyncElasticsearch client
        index_name: Target index name
        tenant_id: Tenant identifier (injected as filter)
        organization_id: Organization identifier (injected as filter)
        query: Optional user query (will be combined with tenant filter)
        refresh: Refresh policy - False or True (default: False)

    Returns:
        Number of documents deleted

    Raises:
        ElasticsearchQueryError: If deletion fails
    """
    try:
        # Build query with mandatory tenant filtering (critical for safety)
        user_query = query if query else {"match_all": {}}

        filtered_query = {
            "bool": {
                "must": user_query,
                "filter": [
                    {"term": {"tenant_id": tenant_id}},
                    {"term": {"organization_id": organization_id}},
                ],
            }
        }

        response = await client.delete_by_query(
            index=index_name,
            query=filtered_query,
            conflicts="proceed",  # Handle version conflicts gracefully
            refresh=refresh,
        )

        deleted_count = response.get("deleted", 0)

        logger.info(
            f"Deleted {deleted_count} documents from {index_name} "
            f"(tenant: {tenant_id}, org: {organization_id})"
        )

        return deleted_count

    except Exception as e:
        logger.error(
            f"Error deleting from {index_name}: {e}",
            exc_info=True,
        )
        raise ElasticsearchQueryError(f"Failed to delete documents: {e}")


async def count_documents(
    client: AsyncElasticsearch,
    index_name: str,
    tenant_id: str,
    organization_id: str,
    query: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Count documents matching query with automatic tenant filtering.

    Args:
        client: AsyncElasticsearch client
        index_name: Source index name
        tenant_id: Tenant identifier (injected as filter)
        organization_id: Organization identifier (injected as filter)
        query: Optional user query (will be combined with tenant filter)

    Returns:
        Number of matching documents

    Raises:
        ElasticsearchQueryError: If count fails
    """
    try:
        # Build query with mandatory tenant filtering
        user_query = query if query else {"match_all": {}}

        filtered_query = {
            "bool": {
                "must": user_query,
                "filter": [
                    {"term": {"tenant_id": tenant_id}},
                    {"term": {"organization_id": organization_id}},
                ],
            }
        }

        response = await client.count(
            index=index_name,
            query=filtered_query,
        )

        count = response.get("count", 0)

        logger.debug(
            f"Count in {index_name}: {count} documents "
            f"(tenant: {tenant_id}, org: {organization_id})"
        )

        return count

    except Exception as e:
        logger.error(
            f"Error counting in {index_name}: {e}",
            exc_info=True,
        )
        raise ElasticsearchQueryError(f"Failed to count documents: {e}")


async def delete_tenant_indexes(
    client: AsyncElasticsearch,
    index_patterns: List[str],
    tenant_id: str,
    organization_id: str,
    refresh: bool = False,
) -> int:
    """
    Delete all data for a tenant across multiple indexes.

    Generic helper for tenant cleanup/offboarding. Can be used by any project
    (Wizard, Report Agent, Jolt) to delete tenant data from their indexes.

    Args:
        client: AsyncElasticsearch client
        index_patterns: List of index names or patterns to delete from
                       Can include exact names or wildcards
                       Example: ["wizard-org123-tenant456",
                                "wizard-checkpoints-org123-tenant456"]
        tenant_id: Tenant identifier (for verification)
        organization_id: Organization identifier (for verification)
        refresh: Refresh policy after delete (default: False)

    Returns:
        Total number of documents deleted across all indexes

    Raises:
        ElasticsearchQueryError: If deletion fails

    Example:
        >>> # Wizard cleanup
        >>> total = await delete_tenant_indexes(
        ...     client,
        ...     ["wizard-org123-tenant456", "wizard-checkpoints-org123-tenant456"],
        ...     "tenant456",
        ...     "org123"
        ... )
        >>> print(f"Deleted {total} documents")

        >>> # Report Agent cleanup
        >>> total = await delete_tenant_indexes(
        ...     client,
        ...     ["report-org123-tenant456"],
        ...     "tenant456",
        ...     "org123"
        ... )
    """
    total_deleted = 0

    for index_pattern in index_patterns:
        try:
            # Check if index exists
            exists = await client.indices.exists(index=index_pattern)
            if not exists:
                logger.debug(
                    f"Index {index_pattern} does not exist, skipping "
                    f"(tenant: {tenant_id}, org: {organization_id})"
                )
                continue

            # Delete all documents for this tenant from the index
            count = await delete_by_query(
                client,
                index_pattern,
                tenant_id,
                organization_id,
                {"match_all": {}},  # Delete all docs (tenant filter applied automatically)
                refresh=refresh,
            )

            total_deleted += count
            logger.info(
                f"Deleted {count} documents from {index_pattern} "
                f"(tenant: {tenant_id}, org: {organization_id})"
            )

        except Exception as e:
            # Log error but continue with other indexes
            logger.error(
                f"Error deleting from {index_pattern}: {e}",
                exc_info=True,
            )
            # Don't raise - try to clean up other indexes even if one fails

    logger.info(
        f"Tenant cleanup complete: deleted {total_deleted} total documents "
        f"(tenant: {tenant_id}, org: {organization_id})"
    )

    return total_deleted


async def get_version_history(
    client: AsyncElasticsearch,
    index_name: str,
    tenant_id: str,
    organization_id: str,
    entity_id_field: str,
    entity_id: str,
    version_field: str = "flow_version",
    source_fields: Optional[List[str]] = None,
    size: int = 100,
) -> List[Dict[str, Any]]:
    """
    Get lightweight version history (metadata only, no full report).

    Retrieves version metadata for an entity (e.g., flow, workflow) with automatic
    tenant filtering. Useful for displaying version history without loading full documents.

    Args:
        client: AsyncElasticsearch client
        index_name: Source index name
        tenant_id: Tenant identifier (injected as filter)
        organization_id: Organization identifier (injected as filter)
        entity_id_field: Field name for entity ID (e.g., "flow_id", "workflow_id")
        entity_id: Entity identifier to get history for
        version_field: Field name for version number (default: "flow_version")
        source_fields: Optional list of fields to return. If None, returns commonly used fields
        size: Maximum number of versions to return (default: 100)

    Returns:
        List of version metadata dictionaries, sorted by version descending (newest first)

    Raises:
        ElasticsearchQueryError: If retrieval fails

    Example:
        >>> # Get flow version history for report-generator
        >>> history = await get_version_history(
        ...     client,
        ...     "report-org123-tenant456",
        ...     "tenant456",
        ...     "org123",
        ...     "flow_id",
        ...     "flow-uuid-123",
        ...     source_fields=["flow_id", "flow_version", "generated_at", "model_used", "is_latest"]
        ... )
        >>> for version in history:
        ...     print(f"Version {version['flow_version']}: {version['generated_at']}")
    """
    try:
        # Use default source fields if not provided
        if source_fields is None:
            source_fields = [
                entity_id_field,
                version_field,
                "generated_at",
                "model_used",
                "tokens_used",
                "is_latest",
            ]

        # Build query with tenant filtering
        query = {"term": {entity_id_field: entity_id}}

        # Use search_documents for automatic tenant filtering
        documents = await search_documents(
            client=client,
            index_name=index_name,
            tenant_id=tenant_id,
            organization_id=organization_id,
            query=query,
            size=size,
            sort=[{version_field: {"order": "desc"}}],
            source=source_fields,
        )

        logger.debug(
            f"Retrieved {len(documents)} version history entries for {entity_id_field}={entity_id} "
            f"(tenant: {tenant_id}, org: {organization_id})"
        )

        return documents

    except Exception as e:
        logger.error(
            f"Error retrieving version history for {entity_id_field}={entity_id}: {e}",
            exc_info=True,
        )
        raise ElasticsearchQueryError(f"Failed to get version history: {e}")
