"""
Information and health check endpoints.
"""

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.analysis import DEMO_MAX_TEXT_LENGTH

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
            "demo_max_text_length": DEMO_MAX_TEXT_LENGTH,
            "authenticated_max_text_length": settings.MAX_MANUSCRIPT_CHARS,
            "max_file_size_mb": settings.MAX_FILE_SIZE_MB,
            "plagiarism_threshold": settings.PLAGIARISM_THRESHOLD,
        },
        "features_enabled": {
            "plagiarism_check": settings.ENABLE_PLAGIARISM_CHECK,
            "citation_analysis": settings.ENABLE_CITATION_ANALYSIS,
            "reviewer_matching": settings.ENABLE_REVIEWER_MATCHING,
            "auto_detect_language": settings.AUTO_DETECT_LANGUAGE,
        },
    }
