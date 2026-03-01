"""
Configuration settings for hackathon project.
Uses pydantic-settings to load from environment variables.
"""

import sys
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator
from typing import Optional


# Get the directory where this settings.py file is located
SETTINGS_DIR = Path(__file__).parent
# Go up two levels to get project root (Mistral-Hackathon)
PROJECT_ROOT = SETTINGS_DIR.parent.parent
# Path to .env file
ENV_FILE = PROJECT_ROOT / ".env"

# Add ai/ root to Python path for shared module imports
_ai_root = SETTINGS_DIR.parent.parent
if str(_ai_root) not in sys.path:
    sys.path.insert(0, str(_ai_root))

from shared.encryption import decrypt, MissingKeyError


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ===== Encryption =====
    ENCRYPTION_KEY: Optional[str] = None

    # ===== Provider API Keys =====
    MISTRAL_API_KEY: str = ""
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = "OYTbf65OHHFELVut7v2H"

    # ===== Default LLM Settings =====
    DEFAULT_MODEL: str = "mistral-large-latest"
    DEFAULT_TEMPERATURE: float = 0.1
    DEFAULT_MAX_TOKENS: int = 4096

    # ===== HR Agent LLM Settings =====
    HR_QUESTION_GEN_MODEL: str = "mistral-medium-latest"
    HR_QUESTION_GEN_TEMPERATURE: float = 0.2

    HR_INTERVIEW_MODEL: str = "mistral-large-latest"
    HR_INTERVIEW_TEMPERATURE: float = 0.1

    HR_SIM_CANDIDATE_MODEL: str = "mistral-large-latest"
    HR_SIM_CANDIDATE_TEMPERATURE: float = 0.5

    HR_ANALYSIS_MODEL: str = "mistral-medium-latest"
    HR_ANALYSIS_TEMPERATURE: float = 0.2
    HR_ANALYSIS_CONCURRENCY: int = 4

    # ===== Retry & Resilience =====
    LLM_MAX_RETRIES: int = 6
    LLM_RETRY_BASE_DELAY_SECONDS: float = 1.0
    LLM_RETRY_MAX_DELAY_SECONDS: float = 20.0
    LLM_RETRY_JITTER_RATIO: float = 0.2

    # ===== Qdrant Vector Database Configuration =====
    QDRANT_URL: str = Field(default="http://localhost:6333", validation_alias="QDRANT_API_URL")
    QDRANT_API_KEY: str = Field(default="", validation_alias="QDRANT_API_KEY")
    QDRANT_COLLECTION: str = "company_info"
    QDRANT_TIMEOUT: int = 30
    QDRANT_PREFER_GRPC: bool = False

    # ===== Embedding Configuration =====
    EMBEDDING_MODEL: str = "mistral-embed"
    EMBEDDING_DIMENSIONS: int = 1024
    EMBEDDING_DEVICE: str = "cpu"
    DEFAULT_EMBEDDING_PROVIDER: str = "mistral"

    # ===== Vector Store Configuration =====
    DEFAULT_VECTOR_STORE: str = "qdrant"

    # ===== LangSmith Tracing (optional) =====
    LANGSMITH_TRACING: bool = Field(default=False)
    LANGSMITH_PROJECT: str = Field(default="hackathon")
    LANGSMITH_API_KEY: Optional[str] = Field(default=None)

    # ===== Application Settings =====
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    INTERVIEW_API_HOST: str = "0.0.0.0"
    INTERVIEW_API_PORT: int = 8081
    INTERVIEW_API_CORS_ORIGINS: str = "*"

    @model_validator(mode='after')
    def decrypt_sensitive_fields(self):
        """Auto-decrypt values with 'enc:' prefix after Settings is fully loaded."""
        sensitive_fields = [
            'MISTRAL_API_KEY',
            'QDRANT_API_KEY',
        ]

        for field_name in sensitive_fields:
            value = getattr(self, field_name, None)
            if value is None or value == "":
                continue

            if value.startswith("enc:"):
                if not self.ENCRYPTION_KEY:
                    raise MissingKeyError(
                        f"ENCRYPTION_KEY not set but {field_name} is encrypted. "
                        "Set ENCRYPTION_KEY in environment or .env file."
                    )
                decrypted = decrypt(value, key=self.ENCRYPTION_KEY)
                object.__setattr__(self, field_name, decrypted)

        return self


# Global settings instance
settings = Settings()
