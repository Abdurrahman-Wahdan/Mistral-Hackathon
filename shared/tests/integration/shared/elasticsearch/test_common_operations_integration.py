import sys
import uuid
from typing import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from elasticsearch import AsyncElasticsearch

project_root = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(project_root))

from shared.elasticsearch.common_operations import (
    index_document,
    get_document,
    search_documents,
    count_documents,
    delete_by_query,
    delete_tenant_indexes,
)


pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def es_client() -> AsyncGenerator[AsyncElasticsearch, None]:
    client = AsyncElasticsearch(
        hosts=["http://localhost:9200"],
        request_timeout=5,
    )
    try:
        if not await client.options(request_timeout=5).ping():
            await client.close()
            pytest.skip("Elasticsearch not available on http://localhost:9200")
    except Exception:
        await client.close()
        pytest.skip("Elasticsearch not available on http://localhost:9200")

    yield client

    # Ensure client is properly closed even if event loop is closing
    try:
        await client.close()
    except RuntimeError as e:
        if "Event loop is closed" not in str(e):
            raise


@pytest.fixture
def tenant_context() -> dict:
    test_id = uuid.uuid4().hex[:8]
    return {
        "tenant_id": f"tenant-{test_id}",
        "organization_id": f"org-{test_id}",
    }


async def _create_index(client: AsyncElasticsearch, index_name: str) -> None:
    await client.indices.create(
        index=index_name,
        mappings={
            "properties": {
                "tenant_id": {"type": "keyword"},
                "organization_id": {"type": "keyword"},
                "user_intent": {"type": "text"},
            }
        },
        settings={"number_of_shards": 1, "number_of_replicas": 0},
    )


@pytest.mark.asyncio
async def test_index_get_search_count_delete(es_client, tenant_context):
    index_name = f"shared-test-{uuid.uuid4().hex[:8]}"
    await _create_index(es_client, index_name)

    try:
        doc_id = await index_document(
            client=es_client,
            index_name=index_name,
            doc_id="doc-1",
            document={"user_intent": "Test intent"},
            tenant_id=tenant_context["tenant_id"],
            organization_id=tenant_context["organization_id"],
            refresh=True,
        )

        assert doc_id == "doc-1"

        doc = await get_document(
            client=es_client,
            index_name=index_name,
            doc_id="doc-1",
            tenant_id=tenant_context["tenant_id"],
            organization_id=tenant_context["organization_id"],
        )
        assert doc is not None
        assert doc["user_intent"] == "Test intent"

        other_tenant = {
            "tenant_id": f"tenant-{uuid.uuid4().hex[:8]}",
            "organization_id": tenant_context["organization_id"],
        }
        await index_document(
            client=es_client,
            index_name=index_name,
            doc_id="doc-2",
            document={"user_intent": "Other tenant intent"},
            tenant_id=other_tenant["tenant_id"],
            organization_id=other_tenant["organization_id"],
            refresh=True,
        )

        docs = await search_documents(
            client=es_client,
            index_name=index_name,
            tenant_id=tenant_context["tenant_id"],
            organization_id=tenant_context["organization_id"],
        )
        assert len(docs) == 1
        assert docs[0]["user_intent"] == "Test intent"

        count = await count_documents(
            client=es_client,
            index_name=index_name,
            tenant_id=tenant_context["tenant_id"],
            organization_id=tenant_context["organization_id"],
        )
        assert count == 1

        deleted = await delete_by_query(
            client=es_client,
            index_name=index_name,
            tenant_id=tenant_context["tenant_id"],
            organization_id=tenant_context["organization_id"],
            refresh=True,
        )
        assert deleted == 1

        remaining = await count_documents(
            client=es_client,
            index_name=index_name,
            tenant_id=tenant_context["tenant_id"],
            organization_id=tenant_context["organization_id"],
        )
        assert remaining == 0
    finally:
        await es_client.indices.delete(index=index_name, ignore_unavailable=True)


@pytest.mark.asyncio
async def test_delete_tenant_indexes_integration(es_client, tenant_context):
    index_a = f"shared-test-a-{uuid.uuid4().hex[:8]}"
    index_b = f"shared-test-b-{uuid.uuid4().hex[:8]}"
    await _create_index(es_client, index_a)
    await _create_index(es_client, index_b)

    try:
        await index_document(
            client=es_client,
            index_name=index_a,
            doc_id="doc-a",
            document={"user_intent": "A"},
            tenant_id=tenant_context["tenant_id"],
            organization_id=tenant_context["organization_id"],
            refresh=True,
        )
        await index_document(
            client=es_client,
            index_name=index_b,
            doc_id="doc-b",
            document={"user_intent": "B"},
            tenant_id=tenant_context["tenant_id"],
            organization_id=tenant_context["organization_id"],
            refresh=True,
        )

        total_deleted = await delete_tenant_indexes(
            client=es_client,
            index_patterns=[index_a, index_b],
            tenant_id=tenant_context["tenant_id"],
            organization_id=tenant_context["organization_id"],
        )

        assert total_deleted == 2
    finally:
        await es_client.indices.delete(index=index_a, ignore_unavailable=True)
        await es_client.indices.delete(index=index_b, ignore_unavailable=True)
