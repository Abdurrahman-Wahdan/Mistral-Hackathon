"""
Unit tests for Elasticsearch index builder.

Tests index naming convention and validation.
"""

import pytest
from shared.elasticsearch.index_builder import build_index_name, validate_index_name


class TestBuildIndexName:
    """Test multi-tenant index name building."""

    def test_build_index_name_basic(self):
        """Test basic index name without suffix."""
        index_name = build_index_name(
            project="wizard",
            organization_id="org123",
            tenant_id="tenant456"
        )

        assert index_name == "wizard-org123-tenant456"

    def test_build_index_name_with_suffix(self):
        """Test index name with suffix."""
        index_name = build_index_name(
            project="wizard",
            organization_id="org123",
            tenant_id="tenant456",
            suffix="checkpoints"
        )

        assert index_name == "wizard-checkpoints-org123-tenant456"

    def test_build_index_name_lowercase(self):
        """Test that index names are lowercased."""
        index_name = build_index_name(
            project="WIZARD",
            organization_id="ORG123",
            tenant_id="TENANT456"
        )

        assert index_name == "wizard-org123-tenant456"
        assert index_name.islower()

    def test_build_index_name_sanitization(self):
        """Test that special characters are removed/sanitized."""
        index_name = build_index_name(
            project="wizard",
            organization_id="org@123",  # Special char
            tenant_id="tenant#456"       # Special char
        )

        # Should remove or replace special characters
        assert "@" not in index_name
        assert "#" not in index_name

    def test_build_index_name_different_projects(self):
        """Test index names for different projects."""
        wizard_index = build_index_name("wizard", "org123", "tenant456")
        report_index = build_index_name("report", "org123", "tenant456")
        jolt_index = build_index_name("jolt", "org123", "tenant456")

        assert wizard_index == "wizard-org123-tenant456"
        assert report_index == "report-org123-tenant456"
        assert jolt_index == "jolt-org123-tenant456"

    def test_build_index_name_different_tenants(self):
        """Test index names for different tenants."""
        tenant1_index = build_index_name("wizard", "org123", "tenant-aaa")
        tenant2_index = build_index_name("wizard", "org123", "tenant-bbb")

        assert tenant1_index != tenant2_index
        assert "tenant-aaa" in tenant1_index
        assert "tenant-bbb" in tenant2_index

    def test_build_index_name_max_length(self):
        """Test that index names respect Elasticsearch 255 char limit."""
        # Try to create very long index name
        long_project = "a" * 100
        long_org = "b" * 100
        long_tenant = "c" * 100

        with pytest.raises(ValueError, match="Index name exceeds maximum length"):
            build_index_name(long_project, long_org, long_tenant)


class TestValidateIndexName:
    """Test index name validation."""

    def test_validate_valid_index_name(self):
        """Test validation passes for valid index names."""
        assert validate_index_name("wizard-org123-tenant456") is True

    def test_validate_index_name_with_suffix(self):
        """Test validation passes for index with suffix."""
        assert validate_index_name("wizard-checkpoints-org123-tenant456") is True

    def test_validate_index_name_too_long(self):
        """Test validation fails for index name exceeding 255 chars."""
        long_name = "a" * 256
        assert validate_index_name(long_name) is False

    def test_validate_index_name_invalid_chars(self):
        """Test validation fails for invalid characters."""
        # Elasticsearch doesn't allow uppercase, spaces, special chars
        assert validate_index_name("Wizard-Index") is False  # Uppercase
        assert validate_index_name("wizard index") is False   # Space
        assert validate_index_name("wizard@index") is False   # Special char

    def test_validate_index_name_starts_with_hyphen(self):
        """Test validation fails if index starts with hyphen or underscore."""
        assert validate_index_name("-wizard-index") is False
        assert validate_index_name("_wizard-index") is False

    def test_validate_index_name_reserved_names(self):
        """Test validation fails for reserved Elasticsearch names."""
        assert validate_index_name(".") is False
        assert validate_index_name("..") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
