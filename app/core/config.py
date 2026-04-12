"""
Application configuration using Pydantic Settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List, Optional
import os
import json


class Settings(BaseSettings):
    """Application settings."""

    # Project
    PROJECT_NAME: str = "Saliksik AI"
    VERSION: str = "2.1.0"  # All enhancements implemented
    DEBUG: bool = False

    # Database
    # Async URL for FastAPI endpoints (postgresql+asyncpg://...)
    # NEVER hardcode credentials — set via DATABASE_URL env var
    DATABASE_URL: str = "postgresql+asyncpg://localhost:5432/saliksik_ai_dev"

    # Sync URL for Celery/Alebmic (postgresql://...)
    # We can default this to the sync version of the same DB
    SQLALCHEMY_DATABASE_URI: Optional[str] = None

    @property
    def sync_database_url(self) -> str:
        """Fallback to generating sync URL from async one if not provided."""
        if self.SQLALCHEMY_DATABASE_URI:
            return self.SQLALCHEMY_DATABASE_URI
        # Naive conversion: replace postgresql+asyncpg with postgresql
        return self.DATABASE_URL.replace("+asyncpg", "").replace("+aiosqlite", "")

    # Security
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # 1 hour (use env var to override)

    # Account lockout
    MAX_LOGIN_ATTEMPTS: int = 5  # Failed attempts before lockout
    LOCKOUT_MINUTES: int = 15  # Duration of account lockout

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if not v or len(v) < 32:
            raise ValueError(
                "SECRET_KEY is required and must be at least 32 characters. "
                "Set it via the SECRET_KEY environment variable. "
                'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )
        return v

    # CORS — override via env: ALLOWED_ORIGINS='["https://app.example.com"]'
    # or comma-separated: ALLOWED_ORIGINS=https://app.example.com,https://admin.example.com
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                return json.loads(v)
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # File Upload
    MAX_FILE_SIZE_MB: int = 50

    # Rate Limiting
    RATE_LIMIT_ANON: str = "60/hour"
    RATE_LIMIT_USER: str = "100/hour"

    # Redis Cache
    REDIS_URL: str = ""
    CACHE_TTL: int = 3600  # 1 hour

    # Celery
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""

    # AI Configuration
    AI_LIGHT_MODE: bool = False

    # Enhancement Feature Flags
    ENABLE_PLAGIARISM_CHECK: bool = True
    PLAGIARISM_THRESHOLD: float = 0.5
    ENABLE_CITATION_ANALYSIS: bool = True
    ENABLE_REVIEWER_MATCHING: bool = True

    # Multi-Language Settings
    SUPPORTED_LANGUAGES: str = "en,es,fr,de"  # Comma-separated
    DEFAULT_LANGUAGE: str = "en"
    AUTO_DETECT_LANGUAGE: bool = True

    # Email / SMTP
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@saliksik.ai"
    SMTP_FROM_NAME: str = "Saliksik AI"
    EMAIL_VERIFY_EXPIRE_HOURS: int = 24
    FRONTEND_URL: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=True, extra="ignore"
    )


settings = Settings()
