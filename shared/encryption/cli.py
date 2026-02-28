#!/usr/bin/env python3
"""
CLI tool to encrypt/decrypt values for .env files.

Usage:
    # Generate a new encryption key
    python -m shared.encryption.cli --generate-key

    # Encrypt a value (requires ENCRYPTION_KEY env var)
    python -m shared.encryption.cli "my-secret-api-key"

    # Decrypt a value
    python -m shared.encryption.cli --decrypt "enc:gAAAAA..."
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Encrypt/decrypt values for .env files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Generate encryption key
    python -m shared.encryption.cli --generate-key

    # Encrypt a value
    export ENCRYPTION_KEY=<your-key>
    python -m shared.encryption.cli "sk-ant-api03-..."

    # Decrypt a value
    python -m shared.encryption.cli --decrypt "enc:gAAAAA..."
        """,
    )
    parser.add_argument("value", nargs="?", help="Value to encrypt/decrypt")
    parser.add_argument(
        "--generate-key", action="store_true", help="Generate a new encryption key"
    )
    parser.add_argument(
        "--decrypt", action="store_true", help="Decrypt a value instead of encrypting"
    )
    args = parser.parse_args()

    if args.generate_key:
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        print(f"ENCRYPTION_KEY={key}")
        return 0

    if not args.value:
        parser.error("Value required unless using --generate-key")

    from .fernet_encryption import decrypt as do_decrypt
    from .fernet_encryption import encrypt

    try:
        if args.decrypt:
            result = do_decrypt(args.value)
        else:
            result = encrypt(args.value)
        print(result)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
