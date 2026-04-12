"""
Information and health check endpoints.
"""

from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()


@router.get("/info")
async def api_info():
    """API information and documentation."""
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "description": "AI-powered manuscript pre-review system with comprehensive text analysis",
        "features": [
            "AI-powered summarization",
            "Keyword extraction",
            "Language quality analysis",
            "PDF text extraction",
            "Plagiarism detection",
            "Citation analysis",
            "Reviewer matching",
            "Multi-language support",
        ],
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "health": "/health",
        },
        "authentication": {
            "register": "POST /api/v1/auth/register",
            "login": "POST /api/v1/auth/login",
            "profile": "GET /api/v1/auth/profile (requires authentication)",
        },
        "limits": {
            "demo_max_text_length": 5000,
            "authenticated_max_text_length": 200000,
        },
    }
