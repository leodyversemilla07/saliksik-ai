"""
Citation analysis API endpoints.
"""

import logging
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, status

from app.api.responses import COMMON_RESPONSES
from app.core.config import settings
from app.core.deps import AuthenticatedUser
from app.schemas.citation import CitationAnalysisRequest, CitationAnalysisResult
from app.services.citation_analyzer import analyze_citations as run_citation_analysis

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/analyze", response_model=CitationAnalysisResult, responses=COMMON_RESPONSES)
async def analyze_citations(request: CitationAnalysisRequest, current_user: AuthenticatedUser):
    """
    Analyse the references and in-text citations of a manuscript.

    The analyzer detects the citation style (APA, MLA, IEEE, Chicago), parses
    the reference list, cross-checks it against the in-text citations and
    reports formatting problems, orphaned citations and outdated references.
    """
    if not settings.ENABLE_CITATION_ANALYSIS:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Citation analysis is disabled",
        )

    try:
        # Parsing is CPU bound and the optional DOI verification performs
        # outbound HTTP calls: both stay off the event loop.
        result = await run_citation_analysis(request.manuscript_text)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Citation analysis failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error during citation analysis",
        ) from exc

    return CitationAnalysisResult(**asdict(result))
