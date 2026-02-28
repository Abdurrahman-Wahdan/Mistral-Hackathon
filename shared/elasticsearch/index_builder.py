"""
Multi-tenant index naming utilities for Elasticsearch.

Provides standardized index naming across all AI projects:
- Format: {project}[-{suffix}]-{organization_id}-{tenant_id}
- Validation and sanitization
- Lowercase conversion
- Length enforcement (ES limit: 255 chars)

Examples:
    wizard-org123-tenant456
    wizard-checkpoints-org123-tenant456
    reports-org99-tenant22
    jolt-transformations-org55-tenant77
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Elasticsearch index name constraints
MAX_INDEX_NAME_LENGTH = 255
VALID_INDEX_NAME_PATTERN = re.compile(r'^[a-z0-9][a-z0-9\-_]*$')


def build_index_name(
    project: str,
    organization_id: str,
    tenant_id: str,
    suffix: Optional[str] = None,
) -> str:
    """
    Build multi-tenant Elasticsearch index name.

    Creates standardized index names with automatic validation and sanitization.
    Format: {project}[-{suffix}]-{org_id}-{tenant_id}

    Args:
        project: Project name (e.g., "wizard", "reports", "jolt")
        organization_id: Organization identifier
        tenant_id: Tenant identifier
        suffix: Optional suffix (e.g., "checkpoints", "sessions")

    Returns:
        Validated index name (lowercase, sanitized)

    Raises:
        ValueError: If inputs are invalid or result exceeds length limit

    Examples:
        >>> build_index_name("wizard", "org123", "tenant456")
        'wizard-org123-tenant456'

        >>> build_index_name("wizard", "org123", "tenant456", "checkpoints")
        'wizard-checkpoints-org123-tenant456'

        >>> build_index_name("reports", "org99", "tenant22")
        'reports-org99-tenant22'
    """
    # Validate inputs
    if not project:
        raise ValueError("Project name is required")
    if not organization_id:
        raise ValueError("Organization ID is required")
    if not tenant_id:
        raise ValueError("Tenant ID is required")

    # Sanitize inputs (remove invalid characters, convert to lowercase)
    project = _sanitize_component(project)
    organization_id = _sanitize_component(organization_id)
    tenant_id = _sanitize_component(tenant_id)

    # Build index name
    if suffix:
        suffix = _sanitize_component(suffix)
        index_name = f"{project}-{suffix}-{organization_id}-{tenant_id}"
    else:
        index_name = f"{project}-{organization_id}-{tenant_id}"

    # Validate final index name
    if len(index_name) > MAX_INDEX_NAME_LENGTH:
        raise ValueError(
            f"Index name exceeds maximum length ({MAX_INDEX_NAME_LENGTH} chars): "
            f"{index_name} ({len(index_name)} chars)"
        )

    if not VALID_INDEX_NAME_PATTERN.match(index_name):
        raise ValueError(
            f"Invalid index name format: {index_name}. "
            f"Must start with lowercase letter or digit, contain only lowercase letters, "
            f"digits, hyphens, and underscores."
        )

    logger.debug(f"Built index name: {index_name}")
    return index_name


def _sanitize_component(component: str) -> str:
    """
    Sanitize index name component.

    - Converts to lowercase
    - Replaces invalid characters with hyphens
    - Removes leading/trailing hyphens
    - Collapses multiple consecutive hyphens

    Args:
        component: Component to sanitize

    Returns:
        Sanitized component

    Examples:
        >>> _sanitize_component("MyProject_123")
        'myproject-123'

        >>> _sanitize_component("org__456__")
        'org-456'

        >>> _sanitize_component("Tenant#789")
        'tenant-789'
    """
    # Convert to lowercase
    sanitized = component.lower()

    # Replace invalid characters with hyphens
    # Valid: lowercase letters, digits, hyphens, underscores
    sanitized = re.sub(r'[^a-z0-9\-_]', '-', sanitized)

    # Replace underscores with hyphens (for consistency)
    sanitized = sanitized.replace('_', '-')

    # Collapse multiple consecutive hyphens
    sanitized = re.sub(r'-+', '-', sanitized)

    # Remove leading/trailing hyphens
    sanitized = sanitized.strip('-')

    # Ensure doesn't start with hyphen or underscore (ES requirement)
    if sanitized and not sanitized[0].isalnum():
        sanitized = 'x' + sanitized

    return sanitized


def validate_index_name(index_name: str) -> bool:
    """
    Validate Elasticsearch index name.

    Checks:
    - Length <= 255 characters
    - Starts with lowercase letter or digit
    - Contains only lowercase letters, digits, hyphens, underscores
    - Doesn't contain consecutive periods (..)

    Args:
        index_name: Index name to validate

    Returns:
        True if valid, False otherwise
    """
    if not index_name:
        return False

    if len(index_name) > MAX_INDEX_NAME_LENGTH:
        return False

    if not VALID_INDEX_NAME_PATTERN.match(index_name):
        return False

    # Additional ES constraints
    if '..' in index_name:  # No consecutive periods
        return False

    if index_name in ['.', '..']:  # Reserved names
        return False

    return True
