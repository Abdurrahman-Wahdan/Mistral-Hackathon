"""
Shared encryption module for AI projects.

Provides Fernet-based encryption for sensitive configuration values.
Supports key rotation via comma-separated keys in ENCRYPTION_KEY env var.

Usage:
    from shared.encryption import encrypt, decrypt, is_encrypted

    # Encrypt a value
    encrypted = encrypt("my-api-key")  # Returns "enc:gAAAAA..."

    # Decrypt a value (auto-detects encrypted vs plaintext)
    plaintext = decrypt(encrypted)  # Returns "my-api-key"
    plaintext = decrypt("plain-value")  # Returns "plain-value" (passthrough)

    # Check if encrypted
    if is_encrypted(value):
        ...
"""

from .exceptions import DecryptionError, EncryptionError, MissingKeyError
from .fernet_encryption import clear_cache, decrypt, encrypt, is_encrypted

__all__ = [
    "encrypt",
    "decrypt",
    "is_encrypted",
    "clear_cache",
    "EncryptionError",
    "DecryptionError",
    "MissingKeyError",
]
