"""
Analysis endpoints for manuscript processing.
"""

import asyncio
import logging
import time
from dataclasses import asdict
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select

from app.api.responses import COMMON_RESPONSES, ErrorResponse, error_examples
from app.core.cache import AIResultCache
from app.core.config import settings
from app.core.deps import (
    AdminUser,
    AuthenticatedUser,
    DbSession,
)
from app.core.security_utils import sanitize_filename, sanitize_manuscript_text
from app.models.analysis import ManuscriptAnalysis
from app.schemas.analysis import (
    AnalysisHistoryItem,
    AnalysisHistoryResponse,
    AnalysisMetadata,
    AnalysisResponse,
    DemoAnalysisRequest,
    LanguageInfo,
    LanguageQuality,
)
from app.schemas.citation import CitationAnalysisResult
from app.schemas.plagiarism import PlagiarismResult
from app.services.ai_processor import ManuscriptPreReviewer
from app.services.citation_analyzer import get_citation_analyzer
from app.services.language_detector import get_language_detector

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize AI processor
pre_reviewer = ManuscriptPreReviewer()

# Serialises demo analyses: the summariser model is shared and heavy, so only
# one demo request may run it at a time.
_demo_analysis_lock = asyncio.Lock()


@router.post(
    "/pre-review",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        **COMMON_RESPONSES,
        400: error_examples(
            {
                "summary": "No input provided",
                "message": "Either 'manuscript_file' (PDF) or 'manuscript_text' is required",
            },
            {
                "summary": "Text too short",
                "message": "Text too short for meaningful analysis (minimum 50 characters)",
            },
            {
                "summary": "Invalid file type",
                "message": "Invalid file type. Only PDF files are supported",
            },
        ),
        413: {
            "description": "The manuscript exceeds the configured character limit",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "HTTP_ERROR",
                            "message": "Text exceeds maximum allowed length of 200,000 characters",
                        }
                    }
                }
            },
        },
        503: {
            "description": "The analysis queue is unavailable",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "HTTP_ERROR",
                            "message": "Analysis queue is temporarily unavailable",
                        }
                    }
                }
            },
        },
    },
)
async def pre_review(
    db: DbSession,
    current_user: AuthenticatedUser,
    manuscript_text: Optional[str] = Form(None),
    manuscript_file: Optional[UploadFile] = File(None),
):
    """
    AI-assisted manuscript pre-review (authenticated).
    Accepts either PDF file or text input.
    Returns a task ID to poll for results.
    """
    try:
        # Input validation
        if not manuscript_file and not manuscript_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either 'manuscript_file' (PDF) or 'manuscript_text' is required",
            )

        # Handle PDF upload
        if manuscript_file:
            filename = manuscript_file.filename or ""
            if not filename.lower().endswith(".pdf"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid file type. Only PDF files are supported",
                )

            content = await manuscript_file.read()
            from io import BytesIO

            loop = asyncio.get_event_loop()
            manuscript_text = await loop.run_in_executor(None, pre_reviewer.extract_text_from_pdf, BytesIO(content))

            if not manuscript_text or not manuscript_text.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Unable to extract text from PDF",
                )

        # Sanitize manuscript text
        if not manuscript_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Manuscript text is required",
            )
        manuscript_text = sanitize_manuscript_text(manuscript_text)

        # Validate text length
        if len(manuscript_text) < 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Text too short for meaningful analysis (minimum 50 characters)",
            )
        if len(manuscript_text) > settings.MAX_MANUSCRIPT_CHARS:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Text exceeds maximum allowed length of {settings.MAX_MANUSCRIPT_CHARS:,} characters",
            )

        # Always create a new analysis record and queue a task. Cached AI
        # results are keyed by endpoint namespace and must not replace the
        # submission response, which callers need for status polling.

        # Create initial record
        analysis = ManuscriptAnalysis(
            user_id=current_user.id,
            original_filename=sanitize_filename(manuscript_file.filename)
            if manuscript_file and manuscript_file.filename
            else None,
            input_type="pdf" if manuscript_file else "text",
            manuscript_text=manuscript_text,
            status="PENDING",
        )
        db.add(analysis)
        await db.commit()
        await db.refresh(analysis)

        # Trigger background task
        from app.tasks.analysis import process_manuscript_task

        try:
            # Pass only the database identifier to Celery. Manuscript content
            # remains in the database instead of being copied into the broker
            # and the extended Celery result metadata.
            task = process_manuscript_task.delay(analysis.id)
        except Exception as exc:
            analysis.status = "FAILED"
            await db.commit()
            logger.error("Failed to enqueue analysis %s: %s", analysis.id, exc, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Analysis queue is temporarily unavailable",
            ) from exc

        # Update with task_id
        analysis.task_id = task.id
        await db.commit()

        return {
            "task_id": task.id,
            "analysis_id": analysis.id,
            "status": "PENDING",
            "message": "Analysis started successfully. Poll /status/{task_id} for results.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis submission error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during submission",
        )


@router.get(
    "/status/{task_id}",
    responses={
        **COMMON_RESPONSES,
        200: {
            "description": "The analysis result (completed) or the current status",
            "content": {
                "application/json": {
                    "schema": {
                        "oneOf": [
                            {"$ref": "#/components/schemas/AnalysisResponse"},
                            {"$ref": "#/components/schemas/AnalysisStatusResponse"},
                        ]
                    }
                }
            },
        },
    },
)
async def get_analysis_status(task_id: str, db: DbSession, current_user: AuthenticatedUser):
    """Check the status of an analysis task."""
    stmt = select(ManuscriptAnalysis).filter(
        ManuscriptAnalysis.task_id == task_id,
        ManuscriptAnalysis.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    analysis = result.scalar_one_or_none()

    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis task not found")

    if analysis.status == "COMPLETED":
        # Type narrowing: when status is COMPLETED, these fields must be set
        assert analysis.summary is not None, "Summary should be set when completed"
        assert analysis.keywords is not None, "Keywords should be set when completed"
        assert analysis.language_quality is not None, "Language quality should be set when completed"

        keywords: list[str] = analysis.keywords if isinstance(analysis.keywords, list) else []
        created_at: datetime | None = analysis.created_at

        # Build LanguageQuality from dict with proper types
        lq = analysis.language_quality or {}
        language_quality = LanguageQuality(
            word_count=int(lq.get("word_count", 0)),
            unique_words=int(lq.get("unique_words", 0)),
            sentence_count=int(lq.get("sentence_count", 0)),
            named_entities=int(lq.get("named_entities", 0)),
            readability_score=float(lq.get("readability_score", 0.0)),
            grammar_issues=int(lq["grammar_issues"]) if "grammar_issues" in lq else None,
            grammar_check_available=bool(lq["grammar_check_available"]) if "grammar_check_available" in lq else None,
            flesch_kincaid_grade=(
                float(lq["flesch_kincaid_grade"]) if lq.get("flesch_kincaid_grade") is not None else None
            ),
            automated_readability=(
                float(lq["automated_readability"]) if lq.get("automated_readability") is not None else None
            ),
            readability_language=str(lq["readability_language"]) if lq.get("readability_language") else None,
            readability_approximate=bool(lq["readability_approximate"]) if "readability_approximate" in lq else None,
        )

        language = LanguageInfo(**analysis.language_info) if analysis.language_info else None
        plagiarism = PlagiarismResult(**analysis.plagiarism_result) if analysis.plagiarism_result else None
        citation_analysis = CitationAnalysisResult(**analysis.citation_analysis) if analysis.citation_analysis else None

        return AnalysisResponse(
            summary=analysis.summary,
            keywords=keywords,
            language_quality=language_quality,
            metadata=AnalysisMetadata(
                analysis_id=int(analysis.id),
                input_length=len(analysis.manuscript_text),
                processing_time=float(round(analysis.processing_time, 2)) if analysis.processing_time else 0.0,
                user=current_user.username,
                timestamp=created_at,
                cached=False,
            ),
            language=language,
            plagiarism=plagiarism,
            citation_analysis=citation_analysis,
        )
    elif analysis.status == "FAILED":
        return {
            "task_id": task_id,
            "status": "FAILED",
            "message": "Analysis failed. Please try again.",
        }
    else:
        return {
            "task_id": task_id,
            "status": analysis.status,
            "message": "Analysis in progress...",
        }


@router.post("/demo", response_model=AnalysisResponse)
async def demo_analysis(request: DemoAnalysisRequest):
    """
    Public demo endpoint (no authentication required).
    Limited to 5000 characters.
    """
    start_time = time.time()

    # Sanitize input
    manuscript_text = sanitize_manuscript_text(request.manuscript_text)

    if len(manuscript_text) < 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text too short for meaningful analysis (minimum 50 characters)",
        )

    try:
        # Check cache (demo namespace only)
        cached_result = AIResultCache.get_cached_result(manuscript_text, namespace="demo")
        if cached_result:
            logger.info("Cache hit for demo request")
            cached_result["metadata"]["cached"] = True
            cached_result["metadata"]["demo"] = True
            return cached_result

        # Generate analysis (CPU/GPU bound work runs in a worker thread)
        logger.info(f"Processing demo manuscript ({len(manuscript_text)} chars)")
        language = None
        citation_analysis = None
        async with _demo_analysis_lock:
            try:
                language_info = await asyncio.to_thread(get_language_detector().detect_language, manuscript_text)
                language = LanguageInfo(**asdict(language_info))
                pre_reviewer.set_language(language_info.code)
            except Exception as exc:
                logger.warning("Demo language detection failed: %s", exc)

            report = await asyncio.to_thread(pre_reviewer.generate_report, manuscript_text)
        processing_time = time.time() - start_time

        if settings.ENABLE_CITATION_ANALYSIS:
            try:
                citation = await asyncio.to_thread(get_citation_analyzer().analyze, manuscript_text)
                citation_analysis = CitationAnalysisResult(**asdict(citation))
            except Exception as exc:
                logger.warning("Demo citation analysis failed: %s", exc)

        response = AnalysisResponse(
            summary=report["summary"],
            keywords=report["keywords"],
            language_quality=LanguageQuality(**report["language_quality"]),
            metadata=AnalysisMetadata(
                input_length=len(manuscript_text),
                processing_time=round(processing_time, 2),
                cached=False,
                demo=True,
            ),
            language=language,
            citation_analysis=citation_analysis,
        )

        # Cache for 2 hours
        AIResultCache.cache_result(manuscript_text, response.model_dump(), ttl=7200, namespace="demo")

        return response

    except Exception as e:
        logger.error(f"Demo analysis error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during processing",
        )


@router.get("/history", response_model=AnalysisHistoryResponse, responses=COMMON_RESPONSES)
async def get_history(db: DbSession, current_user: AuthenticatedUser, page: int = 1, page_size: int = 20):
    """Get user's analysis history with pagination."""

    page_size = min(page_size, 100)
    offset = (page - 1) * page_size

    # Query analyses
    query = (
        select(ManuscriptAnalysis)
        .filter(ManuscriptAnalysis.user_id == current_user.id)
        .order_by(ManuscriptAnalysis.created_at.desc())
    )

    # Count total
    count_stmt = (
        select(func.count()).select_from(ManuscriptAnalysis).filter(ManuscriptAnalysis.user_id == current_user.id)
    )
    total_count_result = await db.execute(count_stmt)
    total_count = total_count_result.scalar()

    # Get page
    result = await db.execute(query.offset(offset).limit(page_size))
    analyses = result.scalars().all()

    # Build response
    results = []
    for analysis in analyses:
        results.append(
            AnalysisHistoryItem(
                id=analysis.id,
                filename=analysis.original_filename,
                input_type=analysis.input_type,
                word_count=int((analysis.language_quality or {}).get("word_count", 0) or 0),
                readability_score=float((analysis.language_quality or {}).get("readability_score", 0) or 0),
                created_at=analysis.created_at,
                processing_time=analysis.processing_time,
            )
        )

    return AnalysisHistoryResponse(
        results=results,
        pagination={
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": (total_count + page_size - 1) // page_size,
            "has_next": offset + page_size < total_count,
            "has_previous": page > 1,
        },
    )


@router.get("/cache/stats", responses=COMMON_RESPONSES)
async def cache_stats(current_user: AdminUser):
    """Get cache statistics (admin only)."""
    stats = AIResultCache.get_cache_stats()
    return {"cache": stats, "message": "Cache statistics retrieved successfully"}


@router.post("/cache/clear", responses=COMMON_RESPONSES)
async def clear_cache(current_user: AdminUser):
    """Clear cache (admin only)."""
    success = AIResultCache.clear_all_cache()
    return {
        "message": "Cache cleared successfully" if success else "Failed to clear cache",
        "cleared_by": current_user.username,
    }
