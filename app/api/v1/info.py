"""
Information and health check endpoints.
"""
from fastapi import APIRouter
from app.core.config import settings
import os

router = APIRouter()


@router.get("/info")
async def api_info():
    """API information and documentation."""
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "description": "AI-powered manuscript pre-review system with comprehensive text analysis",
        "features": [
            "AI-powered summarization using BART model",
            "Keyword extraction with TF-IDF",
            "Language quality analysis",
            "PDF text extraction",
            "JWT-based authentication",
            "Redis caching for performance",
            "Rate limiting and security controls"
        ],
        "endpoints": {
            "docs": "/docs - Interactive API documentation (Swagger UI)",
            "redoc": "/redoc - Alternative API documentation (ReDoc)",
            "health": "/health - Health check endpoint",
            "api_info": "/api/v1/info - This endpoint"
        },
        "authentication": {
            "register": "POST /api/v1/auth/register",
            "login": "POST /api/v1/auth/login",
            "profile": "GET /api/v1/auth/profile (requires authentication)"
        },
        "analysis": {
            "demo": "POST /api/v1/analysis/demo (public, max 5000 chars)",
            "pre_review": "POST /api/v1/analysis/pre-review (authenticated)",
            "history": "GET /api/v1/analysis/history (authenticated)"
        },
        "limits": {
            "demo": {
                "max_text_length": 5000,
                "file_upload": False,
                "rate_limit": settings.RATE_LIMIT_ANON
            },
            "authenticated": {
                "max_file_size": f"{settings.MAX_FILE_SIZE_MB}MB",
                "max_text_length": 50000,
                "rate_limit": settings.RATE_LIMIT_USER
            }
        },
        "status": {
            "server": "online",
            "debug_mode": settings.DEBUG,
            "cache_backend": "redis" if settings.REDIS_URL else "memory"
        }
    }
