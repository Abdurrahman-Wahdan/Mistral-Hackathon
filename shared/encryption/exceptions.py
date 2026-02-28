"""Custom exceptions for encryption module."""


class EncryptionError(Exception):
    """Base exception for encryption errors."""

    pass


class MissingKeyError(EncryptionError):
    """Raised when ENCRYPTION_KEY environment variable is not set."""

    pass


class DecryptionError(EncryptionError):
    """Raised when decryption fails (invalid key or corrupted data)."""

    pass
