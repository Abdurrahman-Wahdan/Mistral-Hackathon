# Shared Encryption Module

Simple Fernet-based encryption for API keys and sensitive configuration values across all AI projects.

## Features

- **Fernet symmetric encryption** (AES-128-CBC + HMAC)
- **Key rotation support** via MultiFernet
- **Backward compatible** - plaintext values pass through unchanged
- **Cached Fernet instance** - no performance overhead
- **~70 lines of code** - simple and maintainable

## Quick Start

### 1. Generate an Encryption Key

```bash
cd /path/to/dax/ai
python -m shared.encryption.cli --generate-key
# Output: ENCRYPTION_KEY=YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY=
```

### 2. Set the Environment Variable

Add to your `.env` file or export in shell:

```bash
export ENCRYPTION_KEY=YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY=
```

### 3. Encrypt Your API Keys

```bash
python -m shared.encryption.cli "sk-ant-api03-your-actual-key"
# Output: enc:gAAAAABl...
```

### 4. Update Your .env File

```env
ENCRYPTION_KEY=YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY=
ANTHROPIC_API_KEY=enc:gAAAAABl...
OPENAI_API_KEY=enc:gAAAAABl...
```

## Usage in Code

### Import the Module

```python
import sys
from pathlib import Path

# Add ai/ root to Python path
_ai_root = Path(__file__).resolve().parent.parent.parent
if str(_ai_root) not in sys.path:
    sys.path.insert(0, str(_ai_root))

from shared.encryption import encrypt, decrypt, is_encrypted
```

### Encrypt/Decrypt Values

```python
# Encrypt
encrypted = encrypt("my-api-key")
# Returns: "enc:gAAAAABl..."

# Decrypt (auto-detects encrypted vs plaintext)
plaintext = decrypt(encrypted)      # Returns: "my-api-key"
plaintext = decrypt("plain-value")  # Returns: "plain-value" (passthrough)

# Check if encrypted
if is_encrypted(value):
    print("Value is encrypted")
```

### Integration with Pydantic Settings

```python
from pydantic import field_validator
from pydantic_settings import BaseSettings
from shared.encryption import decrypt

class Settings(BaseSettings):
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    @field_validator('ANTHROPIC_API_KEY', 'OPENAI_API_KEY', mode='before')
    @classmethod
    def decrypt_sensitive_fields(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return v
        return decrypt(v)
```

## Key Rotation

When you need to rotate the encryption key:

1. **Generate new key:**
   ```bash
   python -m shared.encryption.cli --generate-key
   ```

2. **Set both keys (newest first):**
   ```bash
   export ENCRYPTION_KEY=new-key,old-key
   ```

3. **Re-encrypt all values:**
   ```bash
   python -m shared.encryption.cli "my-api-key"
   ```

4. **Update .env files** with newly encrypted values

5. **Remove old key:**
   ```bash
   export ENCRYPTION_KEY=new-key
   ```

## CLI Reference

```bash
# Generate a new encryption key
python -m shared.encryption.cli --generate-key

# Encrypt a value
python -m shared.encryption.cli "my-secret-value"

# Decrypt a value
python -m shared.encryption.cli --decrypt "enc:gAAAAABl..."
```

## API Reference

### `encrypt(value: str) -> str`
Encrypts a value and returns it with the `enc:` prefix.

### `decrypt(value: str) -> str`
Decrypts a value. Returns plaintext unchanged (backward compatibility).

### `is_encrypted(value: str) -> bool`
Returns `True` if the value starts with `enc:`.

### `clear_cache() -> None`
Clears the cached Fernet instance. Useful for testing or after key rotation.

## Exceptions

- `MissingKeyError` - Raised when `ENCRYPTION_KEY` is not set
- `DecryptionError` - Raised when decryption fails (wrong key or corrupted data)
- `EncryptionError` - Base exception for all encryption errors

## Security Notes

- **Never commit `ENCRYPTION_KEY` to git** - use environment variables or secrets manager
- **Use different keys per environment** (dev, staging, prod)
- **Rotate keys periodically** - the module supports key rotation via MultiFernet
- **Fernet is secure** - uses AES-128-CBC with HMAC for authenticated encryption
