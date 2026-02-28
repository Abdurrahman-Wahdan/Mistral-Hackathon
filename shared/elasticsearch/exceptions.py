"""
Custom exceptions for Elasticsearch operations.
"""


class ElasticsearchError(Exception):
    """Base exception for Elasticsearch errors"""
    pass


class ElasticsearchConnectionError(ElasticsearchError):
    """Raised when connection to Elasticsearch fails"""
    pass


class ElasticsearchIndexError(ElasticsearchError):
    """Raised when index operations fail"""
    pass


class ElasticsearchQueryError(ElasticsearchError):
    """Raised when query operations fail"""
    pass
