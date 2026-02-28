# Tenant Cleanup Guide

## Overview

The `delete_tenant_indexes()` function in `common_operations.py` provides a reusable way to delete all data for a tenant across multiple Elasticsearch indexes.

## When to Use

- **Tenant offboarding**: When a tenant cancels their subscription
- **GDPR compliance**: Right to be forgotten / data deletion requests
- **Testing cleanup**: Clear test tenant data after integration tests
- **Data retention**: Automated cleanup after retention period expires

## Usage Examples

### Example 1: Wizard Tenant Cleanup

```python
from services.storage import get_wizard_storage

# In your tenant offboarding API endpoint
@app.delete("/admin/tenants/{tenant_id}")
async def offboard_tenant(
    tenant_id: str,
    organization_id: str,
):
    storage = get_wizard_storage()

    # Deletes from:
    # - wizard-{org_id}-{tenant_id}
    # - wizard-checkpoints-{org_id}-{tenant_id}
    total_deleted = await storage.delete_tenant_data(
        tenant_id=tenant_id,
        organization_id=organization_id
    )

    return {
        "status": "success",
        "documents_deleted": total_deleted
    }
```

### Example 2: Report Agent Tenant Cleanup

```python
from shared.elasticsearch import common_operations
from report.storage import get_report_storage

# In ReportStorage class
class ReportStorage:
    async def delete_tenant_data(
        self,
        tenant_id: str,
        organization_id: str,
    ) -> int:
        """Delete all Report Agent data for a tenant."""
        client = await self.base_client.get_client()

        # Define Report-specific index patterns
        index_patterns = [
            build_index_name("report", organization_id, tenant_id),
        ]

        # Use shared helper
        total = await common_operations.delete_tenant_indexes(
            client,
            index_patterns,
            tenant_id,
            organization_id,
        )

        return total
```

### Example 3: Jolt Transformer Tenant Cleanup

```python
from shared.elasticsearch import common_operations
from jolt.storage import get_jolt_storage

# In JoltStorage class
class JoltStorage:
    async def delete_tenant_data(
        self,
        tenant_id: str,
        organization_id: str,
    ) -> int:
        """Delete all Jolt data for a tenant."""
        client = await self.base_client.get_client()

        # Define Jolt-specific index patterns
        index_patterns = [
            build_index_name("jolt-transformations", organization_id, tenant_id),
            build_index_name("jolt-logs", organization_id, tenant_id),
        ]

        # Use shared helper
        total = await common_operations.delete_tenant_indexes(
            client,
            index_patterns,
            tenant_id,
            organization_id,
        )

        return total
```

### Example 4: Multi-Project Cleanup (Advanced)

```python
from shared.elasticsearch import common_operations, BaseElasticsearchClient

async def delete_tenant_all_projects(
    tenant_id: str,
    organization_id: str,
) -> Dict[str, int]:
    """
    Delete tenant data across ALL projects.

    Use case: Complete tenant offboarding
    """
    client = BaseElasticsearchClient()
    es_client = await client.get_client()

    results = {}

    # Wizard cleanup
    wizard_patterns = [
        build_index_name("wizard", organization_id, tenant_id),
        build_index_name("wizard", organization_id, tenant_id, "checkpoints"),
    ]
    results["wizard"] = await common_operations.delete_tenant_indexes(
        es_client, wizard_patterns, tenant_id, organization_id
    )

    # Report Agent cleanup
    report_patterns = [
        build_index_name("report", organization_id, tenant_id),
    ]
    results["report"] = await common_operations.delete_tenant_indexes(
        es_client, report_patterns, tenant_id, organization_id
    )

    # Jolt cleanup
    jolt_patterns = [
        build_index_name("jolt-transformations", organization_id, tenant_id),
        build_index_name("jolt-logs", organization_id, tenant_id),
    ]
    results["jolt"] = await common_operations.delete_tenant_indexes(
        es_client, jolt_patterns, tenant_id, organization_id
    )

    await client.close()

    return results

# Usage
results = await delete_tenant_all_projects("tenant-456", "org-123")
# Returns: {"wizard": 150, "report": 75, "jolt": 200}
```

## Function Signature

```python
async def delete_tenant_indexes(
    client: AsyncElasticsearch,
    index_patterns: List[str],
    tenant_id: str,
    organization_id: str,
) -> int:
    """
    Delete all data for a tenant across multiple indexes.

    Args:
        client: AsyncElasticsearch client
        index_patterns: List of index names to delete from
                       Example: ["wizard-org123-tenant456",
                                "wizard-checkpoints-org123-tenant456"]
        tenant_id: Tenant identifier (for verification)
        organization_id: Organization identifier (for verification)

    Returns:
        Total number of documents deleted across all indexes
    """
```

## Security Features

### 1. **Automatic Tenant Filtering**
Even though you're passing index patterns, the function STILL applies tenant filters:

```python
# Internally calls delete_by_query with tenant filter
filtered_query = {
    "bool": {
        "must": {"match_all": {}},
        "filter": [
            {"term": {"tenant_id.keyword": tenant_id}},
            {"term": {"organization_id.keyword": organization_id}},
        ],
    }
}
```

**Why this matters**: Even if wrong index pattern is passed, can only delete matching tenant's data.

### 2. **Index Existence Check**
Checks if index exists before attempting deletion (prevents errors):

```python
exists = await client.indices.exists(index=index_pattern)
if not exists:
    logger.debug(f"Index {index_pattern} does not exist, skipping")
    continue
```

### 3. **Graceful Error Handling**
If one index deletion fails, continues with others:

```python
except Exception as e:
    logger.error(f"Error deleting from {index_pattern}: {e}")
    # Don't raise - try to clean up other indexes even if one fails
```

## Best Practices

### 1. **Always Use Project-Specific Wrapper**

❌ **DON'T** call `delete_tenant_indexes()` directly from API endpoints:
```python
# BAD - tight coupling, error-prone
@app.delete("/admin/tenants/{tenant_id}")
async def delete_tenant(tenant_id, org_id):
    client = await get_es_client()
    await common_operations.delete_tenant_indexes(
        client,
        ["wizard-org-tenant", "wizard-checkpoints-org-tenant"],  # Hardcoded!
        tenant_id,
        org_id
    )
```

✅ **DO** create project-specific method:
```python
# GOOD - clean abstraction
@app.delete("/admin/tenants/{tenant_id}")
async def delete_tenant(tenant_id, org_id):
    storage = get_wizard_storage()
    await storage.delete_tenant_data(tenant_id, org_id)
```

### 2. **Define Index Patterns in Project Config**

```python
# In wizard/config/settings.py
class WizardSettings(BaseSettings):
    # Index patterns for tenant cleanup
    TENANT_INDEXES: List[str] = [
        "wizard",
        "wizard-checkpoints",
    ]

# In WizardStorage
async def delete_tenant_data(self, tenant_id, org_id):
    patterns = [
        build_index_name(prefix, org_id, tenant_id)
        for prefix in settings.TENANT_INDEXES
    ]
    return await common_operations.delete_tenant_indexes(...)
```

### 3. **Add Confirmation for Production**

```python
async def delete_tenant_data(
    self,
    tenant_id: str,
    organization_id: str,
    confirm: bool = False,  # Require explicit confirmation
) -> int:
    """Delete all tenant data (IRREVERSIBLE!)"""
    if not confirm:
        raise ValueError(
            "Tenant deletion requires explicit confirmation. "
            "Set confirm=True to proceed."
        )

    # Log for audit trail
    logger.warning(
        f"TENANT DELETION INITIATED: tenant={tenant_id}, "
        f"org={organization_id}"
    )

    total = await common_operations.delete_tenant_indexes(...)

    logger.warning(
        f"TENANT DELETION COMPLETE: deleted {total} documents "
        f"(tenant={tenant_id}, org={organization_id})"
    )

    return total
```

### 4. **Testing Pattern**

```python
import pytest
from services.storage import get_wizard_storage

@pytest.mark.asyncio
async def test_tenant_cleanup():
    storage = get_wizard_storage()

    # Create test data
    await storage.save_completed_flow(
        flow=test_flow,
        tenant_id="test-tenant",
        organization_id="test-org",
        ...
    )

    # Verify data exists
    flow = await storage.get_flow(
        session_id="test-session",
        tenant_id="test-tenant",
        organization_id="test-org"
    )
    assert flow is not None

    # Cleanup
    deleted = await storage.delete_tenant_data(
        tenant_id="test-tenant",
        organization_id="test-org"
    )
    assert deleted > 0

    # Verify data deleted
    flow = await storage.get_flow(
        session_id="test-session",
        tenant_id="test-tenant",
        organization_id="test-org"
    )
    assert flow is None
```

## Return Value

The function returns the **total number of documents deleted** across all indexes.

**Example**:
```python
total = await storage.delete_tenant_data("tenant-456", "org-123")
print(f"Deleted {total} documents")
# Output: Deleted 237 documents
```

**Breakdown by index** (from logs):
```
INFO: Deleted 150 documents from wizard-org123-tenant456
INFO: Deleted 87 documents from wizard-checkpoints-org123-tenant456
INFO: Tenant cleanup complete: deleted 237 total documents
```

## Monitoring

### Metrics to Track

1. **Deletion Volume**: Number of documents deleted per tenant
2. **Deletion Time**: How long cleanup takes (can indicate data volume issues)
3. **Failure Rate**: Percentage of cleanup operations that fail
4. **Partial Failures**: Indexes where deletion succeeded vs. failed

### Logging

The function logs at multiple levels:

- **DEBUG**: Index skipped (doesn't exist)
- **INFO**: Documents deleted from each index
- **WARNING**: (Currently none, but could add for large deletions)
- **ERROR**: Deletion failures for specific indexes

### Alerts

**Recommended alerts**:
- Tenant deletion takes >5 minutes (investigate data volume)
- Tenant deletion fails for same tenant 3+ times (investigate)
- Partial deletion (some indexes deleted, others failed)

## Migration Guide

### For Existing Projects (Report Agent, Jolt)

1. **Add `delete_tenant_data()` method** to your storage class:
```python
class ReportStorage:
    async def delete_tenant_data(self, tenant_id, org_id):
        # Use shared helper
        ...
```

2. **Define your index patterns** (project-specific)

3. **Test with a test tenant** before using in production

4. **Add to your admin API** for tenant offboarding

5. **Document in your README** how to use it

## Future Enhancements

### 1. **Dry Run Mode** (Recommended)
```python
async def delete_tenant_indexes(
    ...,
    dry_run: bool = False,  # NEW
):
    if dry_run:
        # Count what WOULD be deleted, don't actually delete
        count = await count_documents(...)
        logger.info(f"DRY RUN: Would delete {count} documents")
        return count
    else:
        # Actual deletion
        ...
```

### 2. **Backup Before Delete** (Optional)
```python
async def delete_tenant_indexes(
    ...,
    backup: bool = False,  # NEW
):
    if backup:
        # Export to S3/backup before deleting
        await export_tenant_data(...)

    # Then delete
    ...
```

### 3. **Scheduled Cleanup** (Future)
```python
# Celery/Lambda scheduled task
@celery.task
async def cleanup_expired_tenants():
    # Find tenants past retention period
    expired = await get_expired_tenants()

    for tenant in expired:
        await delete_tenant_all_projects(
            tenant.tenant_id,
            tenant.organization_id
        )
```

## Summary

The `delete_tenant_indexes()` shared helper provides:

- ✅ **Reusable** across all AI projects
- ✅ **Secure** with automatic tenant filtering
- ✅ **Robust** with graceful error handling
- ✅ **Flexible** - projects control their own index patterns
- ✅ **Observable** with comprehensive logging
- ✅ **Safe** with index existence checks

**Use it whenever you need to clean up tenant data!**
