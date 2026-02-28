# Shared Elasticsearch Module

Production-ready Elasticsearch infrastructure for all AI projects (Wizard, Report Agent, Jolt).

## Features

- ✅ **AsyncElasticsearch** client with production-ready configuration
- ✅ **Multi-tenant isolation** (index-level + query-level + app-level)
- ✅ **Automatic retry logic** with exponential backoff (3 attempts)
- ✅ **HTTP compression** enabled for bandwidth efficiency
- ✅ **Connection pooling** (managed automatically by client)
- ✅ **Proper lifecycle management** (async close)
- ✅ **Standardized index naming** across projects
- ✅ **Common CRUD operations** with tenant filtering
- ✅ **Tenant cleanup operations** for offboarding/GDPR compliance

## Quick Start

### Installation

Ensure `elasticsearch[async]` is installed:

```bash
pip install "elasticsearch[async]"
```

### Basic Usage

```python
from shared.elasticsearch import BaseElasticsearchClient, build_index_name
from shared.elasticsearch import common_operations

# Initialize client
client = BaseElasticsearchClient(url="https://es.example.com:9200")

# Get AsyncElasticsearch instance
es = await client.get_client()

# Build multi-tenant index name
index_name = build_index_name(
    project="wizard",
    organization_id="org123",
    tenant_id="tenant456"
)
# Result: "wizard-org123-tenant456"

# Index a document with automatic tenant filtering
await common_operations.index_document(
    client=es,
    index_name=index_name,
    doc_id="flow-123",
    document={"data": "example"},
    tenant_id="tenant456",
    organization_id="org123",
    refresh=True
)

# Search with automatic tenant filtering
results = await common_operations.search_documents(
    client=es,
    index_name=index_name,
    tenant_id="tenant456",
    organization_id="org123",
    query={"match": {"field": "value"}},
    size=100
)

# Close client when done (important!)
await client.close()
```

### FastAPI Integration (Recommended)

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from shared.elasticsearch import BaseElasticsearchClient

# Global client instance
es_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global es_client
    es_client = BaseElasticsearchClient(url=settings.ELASTICSEARCH_URL)
    yield
    await es_client.close()

app = FastAPI(lifespan=lifespan)
```

## Multi-Tenant Index Naming

### Standard Format

```
{project}[-{suffix}]-{organization_id}-{tenant_id}
```

### Examples

```python
# Basic index
build_index_name("wizard", "org123", "tenant456")
# → "wizard-org123-tenant456"

# With suffix for checkpoints
build_index_name("wizard", "org123", "tenant456", "checkpoints")
# → "wizard-checkpoints-org123-tenant456"

# Report generator
build_index_name("reports", "org99", "tenant22")
# → "reports-org99-tenant22"

# JOLT transformations
build_index_name("jolt", "org55", "tenant77", "transformations")
# → "jolt-transformations-org55-tenant77"
```

### Features

- **Automatic sanitization**: Invalid characters → hyphens
- **Lowercase conversion**: MyProject → myproject
- **Length validation**: Max 255 characters (ES limit)
- **Pattern validation**: Must start with letter/digit

## Security: Multi-Tenant Isolation

### Three-Layer Defense

1. **Index-level**: Separate index per tenant
2. **Query-level**: ALL operations auto-inject tenant filters
3. **Application-level**: Verify tenant context before operations

### Automatic Tenant Filtering

```python
# User query (can be from untrusted source)
user_query = {"match": {"field": "value"}}

# Internally wrapped with tenant filter (automatic)
filtered_query = {
    "bool": {
        "must": user_query,
        "filter": [
            {"term": {"tenant_id": "tenant456"}},
            {"term": {"organization_id": "org123"}}
        ]
    }
}
```

**Result**: Even if user tries to access other tenant's data, the filter prevents it.

## API Reference

### BaseElasticsearchClient

```python
client = BaseElasticsearchClient(
    url="https://es.example.com:9200",
    api_key=None,              # Optional: API key auth (preferred)
    username=None,             # Optional: basic auth username
    password=None,             # Optional: basic auth password
    request_timeout=30,        # Timeout in seconds
    max_retries=3,             # Retry count
    retry_on_timeout=True,     # Retry on timeout
)

# Get client
es = await client.get_client()

# Health check
healthy = await client.health_check()

# Create index with mappings
await client.create_index_if_not_exists(
    index_name="my-index",
    mappings={"properties": {...}},
    settings={"number_of_shards": 1}
)

# Close (important!)
await client.close()
```

### Common Operations

```python
from shared.elasticsearch import common_operations

# Index document
await common_operations.index_document(
    client, index_name, doc_id, document,
    tenant_id, organization_id, refresh=False
)

# Get document (with tenant verification)
doc = await common_operations.get_document(
    client, index_name, doc_id,
    tenant_id, organization_id
)

# Search documents (auto-filtered by tenant)
results = await common_operations.search_documents(
    client, index_name, tenant_id, organization_id,
    query=None, size=100, sort=None
)

# Count documents
count = await common_operations.count_documents(
    client, index_name, tenant_id, organization_id,
    query=None
)

# Delete by query (auto-filtered by tenant)
deleted = await common_operations.delete_by_query(
    client, index_name, tenant_id, organization_id,
    query=None
)
```

## Configuration

### Environment Variables

```bash
# Elasticsearch URL (required)
ELASTICSEARCH_URL=https://es.oneteg.com:9200

# Authentication (optional)
ELASTICSEARCH_API_KEY=your-api-key-here
# OR
ELASTICSEARCH_USERNAME=wizard_user
ELASTICSEARCH_PASSWORD=secret
```

### Production Settings

```python
# Recommended configuration
client = BaseElasticsearchClient(
    url=settings.ELASTICSEARCH_URL,
    api_key=settings.ELASTICSEARCH_API_KEY,  # Preferred over basic auth
    request_timeout=30,                       # 30s timeout
    max_retries=3,                            # 3 retry attempts
    retry_on_timeout=True,                    # Retry on timeout
    # http_compress=True is enabled by default
)
```

## Best Practices

1. **Always close the client**: Use FastAPI lifespan or explicit `await client.close()`
2. **Use API keys**: More secure than basic auth, easier to rotate
3. **Enable compression**: Already enabled by default (http_compress=True)
4. **Set appropriate timeouts**: Default 30s is good for most cases
5. **Handle errors gracefully**: Catch `ElasticsearchError` exceptions
6. **Verify tenant context**: Always pass tenant_id and organization_id
7. **Use singleton pattern**: One client instance per application

## Error Handling

```python
from shared.elasticsearch.exceptions import (
    ElasticsearchConnectionError,
    ElasticsearchIndexError,
    ElasticsearchQueryError,
)

try:
    results = await common_operations.search_documents(...)
except ElasticsearchQueryError as e:
    logger.error(f"Search failed: {e}")
    # Handle gracefully
except ElasticsearchConnectionError as e:
    logger.error(f"Connection failed: {e}")
    # Maybe retry or fallback to cache
```

## Tenant Cleanup

For tenant offboarding or GDPR compliance:

```python
from shared.elasticsearch import common_operations

# Delete all tenant data across multiple indexes
total_deleted = await common_operations.delete_tenant_indexes(
    client=es,
    index_patterns=[
        "wizard-org123-tenant456",
        "wizard-checkpoints-org123-tenant456",
    ],
    tenant_id="tenant456",
    organization_id="org123",
)

print(f"Deleted {total_deleted} documents")
```

**Recommended**: Create project-specific wrapper methods instead of calling directly:

```python
# In your project's storage class
class WizardStorage:
    async def delete_tenant_data(self, tenant_id, org_id):
        patterns = [
            build_index_name("wizard", org_id, tenant_id),
            build_index_name("wizard", org_id, tenant_id, "checkpoints"),
        ]
        return await common_operations.delete_tenant_indexes(
            client, patterns, tenant_id, org_id
        )
```

See [TENANT_CLEANUP_GUIDE.md](./TENANT_CLEANUP_GUIDE.md) for complete examples and best practices.

## Testing

See unit tests in `tests/shared/elasticsearch/` for examples.

## Future Projects

To adopt this module in Report Agent or Jolt:

1. Import the shared module
2. Create project-specific mappings
3. Use `build_index_name(project="your-project", ...)`
4. Use `common_operations` for CRUD
5. Follow same multi-tenant patterns

## References

- [Elasticsearch Python Client Documentation](https://www.elastic.co/guide/en/elasticsearch/client/python-api/current/index.html)
- [AsyncElasticsearch Best Practices](https://www.elastic.co/guide/en/elasticsearch/client/python-api/8.19/async.html)
- [Python Client Configuration](https://www.elastic.co/guide/en/elasticsearch/client/python-api/current/config.html)
