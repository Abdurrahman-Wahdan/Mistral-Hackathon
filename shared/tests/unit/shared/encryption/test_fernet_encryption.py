"""
Unit tests for Fernet encryption module.

Tests encrypt, decrypt, and key management functionality.
"""

import os
import pytest
from cryptography.fernet import Fernet

from shared.encryption import (
    encrypt,
    decrypt,
    is_encrypted,
    clear_cache,
    MissingKeyError,
    DecryptionError,
)
from shared.encryption.fernet_encryption import ENCRYPTED_PREFIX, ENV_KEY_NAME


@pytest.fixture(autouse=True)
def clean_environment():
    """Clean up environment and cache before/after each test."""
    # Store original value
    original_key = os.environ.get(ENV_KEY_NAME)

    # Clear cache before test
    clear_cache()

    yield

    # Restore original value after test
    clear_cache()
    if original_key is not None:
        os.environ[ENV_KEY_NAME] = original_key
    elif ENV_KEY_NAME in os.environ:
        del os.environ[ENV_KEY_NAME]


@pytest.fixture
def encryption_key():
    """Generate a valid Fernet key for testing."""
    return Fernet.generate_key().decode()


@pytest.fixture
def set_encryption_key(encryption_key):
    """Set the encryption key in environment."""
    os.environ[ENV_KEY_NAME] = encryption_key
    clear_cache()  # Clear cache to pick up new key
    return encryption_key


class TestEncrypt:
    """Test encryption functionality."""

    def test_encrypt_returns_prefixed_value(self, set_encryption_key):
        """Test that encrypted values have the enc: prefix."""
        result = encrypt("my-secret-value")

        assert result.startswith(ENCRYPTED_PREFIX)

    def test_encrypt_produces_different_output_each_time(self, set_encryption_key):
        """Test that encrypting same value twice gives different ciphertext (due to IV)."""
        value = "my-secret-value"

        result1 = encrypt(value)
        result2 = encrypt(value)

        # Fernet uses random IV, so outputs should differ
        assert result1 != result2

    def test_encrypt_empty_string(self, set_encryption_key):
        """Test encrypting empty string."""
        result = encrypt("")

        assert result.startswith(ENCRYPTED_PREFIX)
        assert decrypt(result) == ""

    def test_encrypt_unicode(self, set_encryption_key):
        """Test encrypting unicode strings."""
        value = "こんにちは世界 🔐"

        result = encrypt(value)
        decrypted = decrypt(result)

        assert decrypted == value

    def test_encrypt_without_key_raises_error(self):
        """Test that encrypting without ENCRYPTION_KEY raises MissingKeyError."""
        if ENV_KEY_NAME in os.environ:
            del os.environ[ENV_KEY_NAME]
        clear_cache()

        with pytest.raises(MissingKeyError) as exc_info:
            encrypt("some-value")

        assert ENV_KEY_NAME in str(exc_info.value)


class TestDecrypt:
    """Test decryption functionality."""

    def test_decrypt_encrypted_value(self, set_encryption_key):
        """Test decrypting a properly encrypted value."""
        original = "my-secret-api-key"
        encrypted = encrypt(original)

        result = decrypt(encrypted)

        assert result == original

    def test_decrypt_plaintext_passthrough(self, set_encryption_key):
        """Test that plaintext values pass through unchanged."""
        plaintext = "sk-ant-api03-plain-key"

        result = decrypt(plaintext)

        assert result == plaintext

    def test_decrypt_plaintext_without_key_passthrough(self):
        """Test that plaintext passes through even without ENCRYPTION_KEY."""
        if ENV_KEY_NAME in os.environ:
            del os.environ[ENV_KEY_NAME]
        clear_cache()

        plaintext = "sk-ant-api03-plain-key"
        result = decrypt(plaintext)

        assert result == plaintext

    def test_decrypt_with_wrong_key_raises_error(self, encryption_key):
        """Test that decrypting with wrong key raises DecryptionError."""
        # Encrypt with one key
        os.environ[ENV_KEY_NAME] = encryption_key
        clear_cache()
        encrypted = encrypt("my-secret")

        # Try to decrypt with different key
        different_key = Fernet.generate_key().decode()
        os.environ[ENV_KEY_NAME] = different_key
        clear_cache()

        with pytest.raises(DecryptionError):
            decrypt(encrypted)

    def test_decrypt_corrupted_value_raises_error(self, set_encryption_key):
        """Test that corrupted encrypted values raise DecryptionError."""
        corrupted = f"{ENCRYPTED_PREFIX}this-is-not-valid-base64-fernet-data"

        with pytest.raises(DecryptionError):
            decrypt(corrupted)

    def test_decrypt_empty_encrypted_prefix_raises_error(self, set_encryption_key):
        """Test that just the prefix raises DecryptionError."""
        just_prefix = ENCRYPTED_PREFIX

        with pytest.raises(DecryptionError):
            decrypt(just_prefix)


class TestDecryptWithKeyParameter:
    """Test decrypt with explicit key parameter (for model_validator use)."""

    def test_decrypt_with_explicit_key(self, encryption_key):
        """Test decrypt() with key parameter bypasses environment."""
        # Set up environment key
        os.environ[ENV_KEY_NAME] = encryption_key
        clear_cache()

        # Encrypt a value
        encrypted = encrypt("my-secret")

        # Clear environment key
        del os.environ[ENV_KEY_NAME]
        clear_cache()

        # Decrypt using explicit key parameter (should work without env key)
        result = decrypt(encrypted, key=encryption_key)

        assert result == "my-secret"

    def test_decrypt_with_explicit_key_plaintext_passthrough(self, encryption_key):
        """Test that plaintext passes through even with key parameter."""
        plaintext = "sk-ant-api03-plain-key"

        result = decrypt(plaintext, key=encryption_key)

        assert result == plaintext

    def test_decrypt_with_wrong_explicit_key_raises_error(self, encryption_key):
        """Test that wrong explicit key raises DecryptionError."""
        # Encrypt with one key
        os.environ[ENV_KEY_NAME] = encryption_key
        clear_cache()
        encrypted = encrypt("my-secret")

        # Clear env and try with different key
        del os.environ[ENV_KEY_NAME]
        clear_cache()
        wrong_key = Fernet.generate_key().decode()

        with pytest.raises(DecryptionError):
            decrypt(encrypted, key=wrong_key)


class TestIsEncrypted:
    """Test is_encrypted helper function."""

    def test_is_encrypted_true_for_encrypted_value(self, set_encryption_key):
        """Test that is_encrypted returns True for encrypted values."""
        encrypted = encrypt("secret")

        assert is_encrypted(encrypted) is True

    def test_is_encrypted_false_for_plaintext(self):
        """Test that is_encrypted returns False for plaintext."""
        assert is_encrypted("sk-ant-api03-plain-key") is False

    def test_is_encrypted_false_for_similar_prefix(self):
        """Test that similar but different prefixes return False."""
        assert is_encrypted("encrypted:value") is False
        assert is_encrypted("ENC:value") is False
        assert is_encrypted("Enc:value") is False

    def test_is_encrypted_true_for_prefix_only(self):
        """Test that just the prefix returns True (though invalid for decrypt)."""
        assert is_encrypted(ENCRYPTED_PREFIX) is True


class TestKeyRotation:
    """Test key rotation with MultiFernet."""

    def test_decrypt_with_old_key_after_rotation(self):
        """Test that values encrypted with old key can be decrypted after rotation."""
        old_key = Fernet.generate_key().decode()
        new_key = Fernet.generate_key().decode()

        # Encrypt with old key
        os.environ[ENV_KEY_NAME] = old_key
        clear_cache()
        encrypted = encrypt("my-secret")

        # Rotate: set both keys (new first)
        os.environ[ENV_KEY_NAME] = f"{new_key},{old_key}"
        clear_cache()

        # Should still decrypt
        result = decrypt(encrypted)
        assert result == "my-secret"

    def test_encrypt_uses_first_key(self):
        """Test that encryption uses the first key in the list."""
        key1 = Fernet.generate_key().decode()
        key2 = Fernet.generate_key().decode()

        # Set two keys
        os.environ[ENV_KEY_NAME] = f"{key1},{key2}"
        clear_cache()
        encrypted = encrypt("my-secret")

        # Should be decryptable with just key1
        os.environ[ENV_KEY_NAME] = key1
        clear_cache()
        result = decrypt(encrypted)

        assert result == "my-secret"

    def test_multiple_keys_with_spaces(self):
        """Test that keys with spaces around commas work."""
        key1 = Fernet.generate_key().decode()
        key2 = Fernet.generate_key().decode()

        # Encrypt with key2
        os.environ[ENV_KEY_NAME] = key2
        clear_cache()
        encrypted = encrypt("my-secret")

        # Set both keys with spaces
        os.environ[ENV_KEY_NAME] = f"{key1} , {key2}"  # Note spaces
        clear_cache()

        # Should still decrypt
        result = decrypt(encrypted)
        assert result == "my-secret"


class TestClearCache:
    """Test cache clearing functionality."""

    def test_clear_cache_allows_key_change(self):
        """Test that clearing cache allows picking up new key."""
        key1 = Fernet.generate_key().decode()
        key2 = Fernet.generate_key().decode()

        # Set first key and encrypt
        os.environ[ENV_KEY_NAME] = key1
        clear_cache()
        encrypted1 = encrypt("secret1")

        # Change key without clearing cache - would use old cached key
        os.environ[ENV_KEY_NAME] = key2
        # Don't clear cache - this would still use key1
        encrypted2_same_key = encrypt("secret2")

        # Clear cache and encrypt again
        clear_cache()
        encrypted2_new_key = encrypt("secret2")

        # encrypted2_same_key should be decryptable with key1
        os.environ[ENV_KEY_NAME] = key1
        clear_cache()
        assert decrypt(encrypted1) == "secret1"
        assert decrypt(encrypted2_same_key) == "secret2"

        # encrypted2_new_key should only be decryptable with key2
        os.environ[ENV_KEY_NAME] = key2
        clear_cache()
        assert decrypt(encrypted2_new_key) == "secret2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
