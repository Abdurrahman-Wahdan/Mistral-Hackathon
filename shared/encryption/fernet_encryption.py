"""
Simple Fernet encryption for sensitive configuration values.

Uses a pre-generated Fernet key stored in ENCRYPTION_KEY environment variable.
Supports key rotation via comma-separated keys (newest first).
"""

import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from .exceptions import DecryptionError, MissingKeyError

ENCRYPTED_PREFIX = "enc:"
ENV_KEY_NAME = "ENCRYPTION_KEY"


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet | MultiFernet:
    """
    Get cached Fernet instance.

    Supports key rotation via comma-separated keys (newest first).
    The first key is used for encryption, all keys can decrypt.
    """
    key_str = os.environ.get(ENV_KEY_NAME, "")
    if not key_str:
        raise MissingKeyError(
            f"{ENV_KEY_NAME} not set. Generate with: "
            "python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )
    keys = [k.strip() for k in key_str.split(",") if k.strip()]
    if len(keys) == 1:
        return Fernet(keys[0].encode())
    # MultiFernet: first key encrypts, all keys can decrypt (for rotation)
    return MultiFernet([Fernet(k.encode()) for k in keys])


def clear_cache() -> None:
    """Clear the cached Fernet instance (useful for testing or key rotation)."""
    _get_fernet.cache_clear()


def encrypt(value: str) -> str:
    """Encrypt a value and return with prefix."""
    return ENCRYPTED_PREFIX + _get_fernet().encrypt(value.encode()).decode()


def decrypt(value: str, key: str | None = None) -> str:
    """
    Decrypt a value.

    Args:
        value: The value to decrypt (with 'enc:' prefix if encrypted)
        key: Optional encryption key. If not provided, reads from ENCRYPTION_KEY env var.

    Returns as-is if not encrypted (backward compatibility with plaintext values).
    """
    if not value.startswith(ENCRYPTED_PREFIX):
        return value
    try:
        encrypted_part = value[len(ENCRYPTED_PREFIX) :]
        if key:
            # Use provided key directly
            fernet = Fernet(key.encode())
            return fernet.decrypt(encrypted_part.encode()).decode()
        return _get_fernet().decrypt(encrypted_part.encode()).decode()
    except InvalidToken as e:
        raise DecryptionError(f"Failed to decrypt. Check {ENV_KEY_NAME}.") from e


def is_encrypted(value: str) -> bool:
    """Check if a value is encrypted (has the enc: prefix)."""
    return value.startswith(ENCRYPTED_PREFIX)
