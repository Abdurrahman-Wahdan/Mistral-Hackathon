"""
Unit tests for Elasticsearch common_operations module.

Tests CRUD operations with mocked AsyncElasticsearch client.
Verifies tenant filtering, error handling, and query construction.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from elasticsearch import NotFoundError

from shared.elasticsearch.common_operations import (
    index_document,
    get_document,
    search_documents,
    delete_by_query,
    count_documents,
    delete_tenant_indexes,
)
from shared.elasticsearch.exceptions import ElasticsearchQueryError


@pytest.fixture
def mock_es_client():
    """Create mock AsyncElasticsearch client."""
    client = AsyncMock()
    return client


@pytest.fixture
def sample_tenant_context():
    """Sample tenant context for testing."""
    return {
        "tenant_id": "tenant-test-123",
        "organization_id": "org-test-456",
    }


@pytest.fixture
def sample_document():
    """Sample document for indexing."""
    return {
        "session_id": "session-abc-123",
        "user_intent": "Test user intent",
        "created_at": "2025-01-14T10:00:00Z",
    }


class TestIndexDocument:
    """Test document indexing with tenant metadata injection."""

    @pytest.mark.asyncio
    async def test_index_document_success(
        self, mock_es_client, sample_tenant_context, sample_document
    ):
        """Test successful document indexing."""
        # Setup mock response
        mock_es_client.index.return_value = {
            "result": "created",
            "_id": "doc-123",
        }

        # Index document
        doc_id = await index_document(
            client=mock_es_client,
            index_name="test-index",
            doc_id="doc-123",
            document=sample_document.copy(),
            tenant_id=sample_tenant_context["tenant_id"],
            organization_id=sample_tenant_context["organization_id"],
            refresh=True,
        )

        # Verify result
        assert doc_id == "doc-123"

        # Verify ES client called with tenant metadata injected
        mock_es_client.index.assert_called_once()
        call_args = mock_es_client.index.call_args
        indexed_doc = call_args.kwargs["document"]

        assert indexed_doc["tenant_id"] == sample_tenant_context["tenant_id"]
        assert indexed_doc["organization_id"] == sample_tenant_context["organization_id"]
        assert indexed_doc["session_id"] == sample_document["session_id"]
        assert call_args.kwargs["index"] == "test-index"
        assert call_args.kwargs["id"] == "doc-123"
        assert call_args.kwargs["refresh"] is True

    @pytest.mark.asyncio
    async def test_index_document_no_refresh(
        self, mock_es_client, sample_tenant_context, sample_document
    ):
        """Test indexing without immediate refresh."""
        mock_es_client.index.return_value = {"result": "created"}

        await index_document(
            client=mock_es_client,
            index_name="test-index",
            doc_id="doc-123",
            document=sample_document.copy(),
            tenant_id=sample_tenant_context["tenant_id"],
            organization_id=sample_tenant_context["organization_id"],
            refresh=False,
        )

        call_args = mock_es_client.index.call_args
        assert call_args.kwargs["refresh"] is False

    @pytest.mark.asyncio
    async def test_index_document_error(
        self, mock_es_client, sample_tenant_context, sample_document
    ):
        """Test error handling during indexing."""
        mock_es_client.index.side_effect = Exception("ES connection failed")

        with pytest.raises(ElasticsearchQueryError, match="Failed to index document"):
            await index_document(
                client=mock_es_client,
                index_name="test-index",
                doc_id="doc-123",
                document=sample_document.copy(),
                tenant_id=sample_tenant_context["tenant_id"],
                organization_id=sample_tenant_context["organization_id"],
            )


class TestGetDocument:
    """Test document retrieval with tenant verification."""

    @pytest.mark.asyncio
    async def test_get_document_success(self, mock_es_client, sample_tenant_context):
        """Test successful document retrieval with matching tenant."""
        # Setup mock response
        mock_es_client.get.return_value = {
            "found": True,
            "_source": {
                "session_id": "session-123",
                "user_intent": "Test intent",
                "tenant_id": sample_tenant_context["tenant_id"],
                "organization_id": sample_tenant_context["organization_id"],
            },
        }

        # Get document
        doc = await get_document(
            client=mock_es_client,
            index_name="test-index",
            doc_id="doc-123",
            tenant_id=sample_tenant_context["tenant_id"],
            organization_id=sample_tenant_context["organization_id"],
        )

        # Verify result
        assert doc is not None
        assert doc["session_id"] == "session-123"
        assert doc["tenant_id"] == sample_tenant_context["tenant_id"]

        # Verify ES client called
        mock_es_client.get.assert_called_once_with(
            index="test-index",
            id="doc-123",
        )

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, mock_es_client, sample_tenant_context):
        """Test document not found."""
        mock_es_client.get.return_value = {"found": False}

        doc = await get_document(
            client=mock_es_client,
            index_name="test-index",
            doc_id="doc-123",
            tenant_id=sample_tenant_context["tenant_id"],
            organization_id=sample_tenant_context["organization_id"],
        )

        assert doc is None

    @pytest.mark.asyncio
    async def test_get_document_not_found_exception(
        self, mock_es_client, sample_tenant_context
    ):
        """Test NotFoundError exception handling."""
        # NotFoundError requires meta and body arguments
        mock_meta = MagicMock()
        mock_meta.status = 404
        mock_es_client.get.side_effect = NotFoundError(
            "Document not found",
            meta=mock_meta,
            body={}
        )

        doc = await get_document(
            client=mock_es_client,
            index_name="test-index",
            doc_id="doc-123",
            tenant_id=sample_tenant_context["tenant_id"],
            organization_id=sample_tenant_context["organization_id"],
        )

        assert doc is None

    @pytest.mark.asyncio
    async def test_get_document_tenant_mismatch(
        self, mock_es_client, sample_tenant_context
    ):
        """Test tenant mismatch returns None (security)."""
        # Document belongs to different tenant
        mock_es_client.get.return_value = {
            "found": True,
            "_source": {
                "session_id": "session-123",
                "tenant_id": "other-tenant",
                "organization_id": "other-org",
            },
        }

        # Try to get with different tenant context
        doc = await get_document(
            client=mock_es_client,
            index_name="test-index",
            doc_id="doc-123",
            tenant_id=sample_tenant_context["tenant_id"],
            organization_id=sample_tenant_context["organization_id"],
        )

        # Should return None (access denied)
        assert doc is None

    @pytest.mark.asyncio
    async def test_get_document_error(self, mock_es_client, sample_tenant_context):
        """Test error handling during retrieval."""
        mock_es_client.get.side_effect = Exception("ES connection failed")

        with pytest.raises(ElasticsearchQueryError, match="Failed to get document"):
            await get_document(
                client=mock_es_client,
                index_name="test-index",
                doc_id="doc-123",
                tenant_id=sample_tenant_context["tenant_id"],
                organization_id=sample_tenant_context["organization_id"],
            )


class TestSearchDocuments:
    """Test document search with automatic tenant filtering."""

    @pytest.mark.asyncio
    async def test_search_documents_match_all(
        self, mock_es_client, sample_tenant_context
    ):
        """Test search with match_all query."""
        # Setup mock response
        mock_es_client.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "session_id": "session-1",
                            "tenant_id": sample_tenant_context["tenant_id"],
                            "organization_id": sample_tenant_context["organization_id"],
                        }
                    },
                    {
                        "_source": {
                            "session_id": "session-2",
                            "tenant_id": sample_tenant_context["tenant_id"],
                            "organization_id": sample_tenant_context["organization_id"],
                        }
                    },
                ]
            }
        }

        # Search documents
        docs = await search_documents(
            client=mock_es_client,
            index_name="test-index",
            tenant_id=sample_tenant_context["tenant_id"],
            organization_id=sample_tenant_context["organization_id"],
            query=None,
            size=100,
        )

        # Verify results
        assert len(docs) == 2
        assert docs[0]["session_id"] == "session-1"
        assert docs[1]["session_id"] == "session-2"

        # Verify tenant filter injected
        call_args = mock_es_client.search.call_args
        query = call_args.kwargs["query"]
        assert query["bool"]["must"] == {"match_all": {}}
        assert {"term": {"tenant_id": sample_tenant_context["tenant_id"]}} in query["bool"]["filter"]
        assert {"term": {"organization_id": sample_tenant_context["organization_id"]}} in query["bool"]["filter"]

    @pytest.mark.asyncio
    async def test_search_documents_with_user_query(
        self, mock_es_client, sample_tenant_context
    ):
        """Test search with user-provided query."""
        mock_es_client.search.return_value = {"hits": {"hits": []}}

        user_query = {"match": {"user_intent": "test"}}

        await search_documents(
            client=mock_es_client,
            index_name="test-index",
            tenant_id=sample_tenant_context["tenant_id"],
            organization_id=sample_tenant_context["organization_id"],
            query=user_query,
        )

        # Verify user query combined with tenant filter
        call_args = mock_es_client.search.call_args
        query = call_args.kwargs["query"]
        assert query["bool"]["must"] == user_query
        assert len(query["bool"]["filter"]) == 2  # tenant_id + organization_id

    @pytest.mark.asyncio
    async def test_search_documents_with_sort(
        self, mock_es_client, sample_tenant_context
    ):
        """Test search with sort criteria."""
        mock_es_client.search.return_value = {"hits": {"hits": []}}

        sort = [{"created_at": {"order": "desc"}}]

        await search_documents(
            client=mock_es_client,
            index_name="test-index",
            tenant_id=sample_tenant_context["tenant_id"],
            organization_id=sample_tenant_context["organization_id"],
            sort=sort,
        )

        call_args = mock_es_client.search.call_args
        assert call_args.kwargs["sort"] == sort

    @pytest.mark.asyncio
    async def test_search_documents_with_source_filtering(
        self, mock_es_client, sample_tenant_context
    ):
        """Test search with _source filtering."""
        mock_es_client.search.return_value = {"hits": {"hits": []}}

        source = ["session_id", "user_intent"]

        await search_documents(
            client=mock_es_client,
            index_name="test-index",
            tenant_id=sample_tenant_context["tenant_id"],
            organization_id=sample_tenant_context["organization_id"],
            source=source,
        )

        call_args = mock_es_client.search.call_args
        assert call_args.kwargs["_source"] == source

    @pytest.mark.asyncio
    async def test_search_documents_error(self, mock_es_client, sample_tenant_context):
        """Test error handling during search."""
        mock_es_client.search.side_effect = Exception("ES query failed")

        with pytest.raises(ElasticsearchQueryError, match="Failed to search documents"):
            await search_documents(
                client=mock_es_client,
                index_name="test-index",
                tenant_id=sample_tenant_context["tenant_id"],
                organization_id=sample_tenant_context["organization_id"],
            )


class TestDeleteByQuery:
    """Test document deletion with automatic tenant filtering."""

    @pytest.mark.asyncio
    async def test_delete_by_query_success(
        self, mock_es_client, sample_tenant_context
    ):
        """Test successful deletion."""
        mock_es_client.delete_by_query.return_value = {"deleted": 5}

        count = await delete_by_query(
            client=mock_es_client,
            index_name="test-index",
            tenant_id=sample_tenant_context["tenant_id"],
            organization_id=sample_tenant_context["organization_id"],
            query={"match": {"status": "completed"}},
        )

        assert count == 5

        # Verify tenant filter injected
        call_args = mock_es_client.delete_by_query.call_args
        query = call_args.kwargs["query"]
        assert query["bool"]["must"] == {"match": {"status": "completed"}}
        assert len(query["bool"]["filter"]) == 2
        assert call_args.kwargs["conflicts"] == "proceed"

    @pytest.mark.asyncio
    async def test_delete_by_query_match_all(
        self, mock_es_client, sample_tenant_context
    ):
        """Test deletion with match_all query."""
        mock_es_client.delete_by_query.return_value = {"deleted": 10}

        count = await delete_by_query(
            client=mock_es_client,
            index_name="test-index",
            tenant_id=sample_tenant_context["tenant_id"],
            organization_id=sample_tenant_context["organization_id"],
            query=None,
        )

        assert count == 10

        call_args = mock_es_client.delete_by_query.call_args
        query = call_args.kwargs["query"]
        assert query["bool"]["must"] == {"match_all": {}}

    @pytest.mark.asyncio
    async def test_delete_by_query_error(self, mock_es_client, sample_tenant_context):
        """Test error handling during deletion."""
        mock_es_client.delete_by_query.side_effect = Exception("ES deletion failed")

        with pytest.raises(ElasticsearchQueryError, match="Failed to delete documents"):
            await delete_by_query(
                client=mock_es_client,
                index_name="test-index",
                tenant_id=sample_tenant_context["tenant_id"],
                organization_id=sample_tenant_context["organization_id"],
            )


class TestCountDocuments:
    """Test document counting with automatic tenant filtering."""

    @pytest.mark.asyncio
    async def test_count_documents_success(
        self, mock_es_client, sample_tenant_context
    ):
        """Test successful count."""
        mock_es_client.count.return_value = {"count": 42}

        count = await count_documents(
            client=mock_es_client,
            index_name="test-index",
            tenant_id=sample_tenant_context["tenant_id"],
            organization_id=sample_tenant_context["organization_id"],
            query={"match": {"status": "completed"}},
        )

        assert count == 42

        # Verify tenant filter injected
        call_args = mock_es_client.count.call_args
        query = call_args.kwargs["query"]
        assert query["bool"]["must"] == {"match": {"status": "completed"}}
        assert len(query["bool"]["filter"]) == 2

    @pytest.mark.asyncio
    async def test_count_documents_match_all(
        self, mock_es_client, sample_tenant_context
    ):
        """Test count with match_all query."""
        mock_es_client.count.return_value = {"count": 100}

        count = await count_documents(
            client=mock_es_client,
            index_name="test-index",
            tenant_id=sample_tenant_context["tenant_id"],
            organization_id=sample_tenant_context["organization_id"],
            query=None,
        )

        assert count == 100

    @pytest.mark.asyncio
    async def test_count_documents_error(self, mock_es_client, sample_tenant_context):
        """Test error handling during count."""
        mock_es_client.count.side_effect = Exception("ES count failed")

        with pytest.raises(ElasticsearchQueryError, match="Failed to count documents"):
            await count_documents(
                client=mock_es_client,
                index_name="test-index",
                tenant_id=sample_tenant_context["tenant_id"],
                organization_id=sample_tenant_context["organization_id"],
            )


class TestDeleteTenantIndexes:
    """Test tenant cleanup across multiple indexes."""

    @pytest.mark.asyncio
    async def test_delete_tenant_indexes_success(
        self, mock_es_client, sample_tenant_context
    ):
        """Test successful tenant cleanup."""
        # Setup mocks
        mock_es_client.indices.exists.return_value = True
        mock_es_client.delete_by_query.return_value = {"deleted": 10}

        index_patterns = [
            "wizard-org-tenant-flows",
            "wizard-org-tenant-checkpoints",
        ]

        total = await delete_tenant_indexes(
            client=mock_es_client,
            index_patterns=index_patterns,
            tenant_id=sample_tenant_context["tenant_id"],
            organization_id=sample_tenant_context["organization_id"],
        )

        assert total == 20  # 10 from each index

        # Verify existence checks
        assert mock_es_client.indices.exists.call_count == 2

        # Verify deletions
        assert mock_es_client.delete_by_query.call_count == 2

    @pytest.mark.asyncio
    async def test_delete_tenant_indexes_nonexistent_index(
        self, mock_es_client, sample_tenant_context
    ):
        """Test cleanup skips non-existent indexes."""
        # First index exists, second doesn't
        mock_es_client.indices.exists.side_effect = [True, False]
        mock_es_client.delete_by_query.return_value = {"deleted": 5}

        index_patterns = ["existing-index", "nonexistent-index"]

        total = await delete_tenant_indexes(
            client=mock_es_client,
            index_patterns=index_patterns,
            tenant_id=sample_tenant_context["tenant_id"],
            organization_id=sample_tenant_context["organization_id"],
        )

        # Only one index deleted
        assert total == 5
        assert mock_es_client.delete_by_query.call_count == 1

    @pytest.mark.asyncio
    async def test_delete_tenant_indexes_partial_failure(
        self, mock_es_client, sample_tenant_context
    ):
        """Test cleanup continues on partial failure."""
        mock_es_client.indices.exists.return_value = True

        # First deletion fails, second succeeds
        mock_es_client.delete_by_query.side_effect = [
            Exception("First index deletion failed"),
            {"deleted": 15},
        ]

        index_patterns = ["index-1", "index-2"]

        # Should not raise exception, continues with other indexes
        total = await delete_tenant_indexes(
            client=mock_es_client,
            index_patterns=index_patterns,
            tenant_id=sample_tenant_context["tenant_id"],
            organization_id=sample_tenant_context["organization_id"],
        )

        # Only second index deleted
        assert total == 15

    @pytest.mark.asyncio
    async def test_delete_tenant_indexes_empty_list(
        self, mock_es_client, sample_tenant_context
    ):
        """Test cleanup with empty index list."""
        total = await delete_tenant_indexes(
            client=mock_es_client,
            index_patterns=[],
            tenant_id=sample_tenant_context["tenant_id"],
            organization_id=sample_tenant_context["organization_id"],
        )

        assert total == 0
        mock_es_client.indices.exists.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
