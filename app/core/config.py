"""
Application configuration using Pydantic Settings.
"""
from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """Application settings."""
    
    # Project
    PROJECT_NAME: str = "Saliksik AI"
    VERSION: str = "2.1.0"  # All enhancements implemented
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = "postgresql://saliksik:saliksik123@localhost:5432/saliksik_ai_dev"
    
    # Security
    SECRET_KEY: str = "django-insecure-change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    
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
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
