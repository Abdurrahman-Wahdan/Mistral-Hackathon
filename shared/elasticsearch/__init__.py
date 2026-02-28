"""
Shared Elasticsearch module for AI projects.

Provides reusable ES infrastructure with multi-tenant support.
"""

from .base_client import BaseElasticsearchClient
from .index_builder import build_index_name, validate_index_name
from .exceptions import (
    ElasticsearchConnectionError,
    ElasticsearchIndexError,
    ElasticsearchQueryError,
)
from . import common_operations

__all__ = [
    "BaseElasticsearchClient",
    "build_index_name",
    "validate_index_name",
    "common_operations",
    "ElasticsearchConnectionError",
    "ElasticsearchIndexError",
    "ElasticsearchQueryError",
]
