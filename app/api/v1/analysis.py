"""
Analysis endpoints for manuscript processing.
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, Annotated
import asyncio
import time
import logging
from app.core.database import get_db
from app.core.deps import get_authenticated_user, DbSession, AuthenticatedUser
from app.core.cache import AIResultCache
from app.models.user import User
from app.models.analysis import ManuscriptAnalysis, ProcessingError
from app.schemas.analysis import (
    AnalysisRequest,
    DemoAnalysisRequest,
    AnalysisResponse,
    AnalysisHistoryResponse,
    AnalysisHistoryItem,
    LanguageQuality,
    AnalysisMetadata
)
from app.services.ai_processor import ManuscriptPreReviewer
from app.core.security_utils import sanitize_manuscript_text, sanitize_filename

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize AI processor
pre_reviewer = ManuscriptPreReviewer()


@router.post("/pre-review", status_code=status.HTTP_202_ACCEPTED)
async def pre_review(
    db: DbSession,
    current_user: AuthenticatedUser,
    manuscript_text: Optional[str] = Form(None),
    manuscript_file: Optional[UploadFile] = File(None)
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
                detail="Either 'manuscript_file' (PDF) or 'manuscript_text' is required"
            )
        
        # Handle PDF upload
        if manuscript_file:
            if not manuscript_file.filename.lower().endswith('.pdf'):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid file type. Only PDF files are supported"
                )
            
            content = await manuscript_file.read()
            from io import BytesIO
            loop = asyncio.get_event_loop()
            manuscript_text = await loop.run_in_executor(
                None, pre_reviewer.extract_text_from_pdf, BytesIO(content)
            )
            
            if not manuscript_text or not manuscript_text.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Unable to extract text from PDF"
                )
        
        # Sanitize manuscript text
        manuscript_text = sanitize_manuscript_text(manuscript_text)
        
        # Validate text length
        if len(manuscript_text) < 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Text too short for meaningful analysis (minimum 50 characters)"
            )
        
        # Check cache first
        cached_result = AIResultCache.get_cached_result(manuscript_text)
        if cached_result:
            logger.info(f"Cache hit for user {current_user.username}")
            cached_result["metadata"]["cached"] = True
            return cached_result
        
        # Create initial record
        analysis = ManuscriptAnalysis(
            user_id=current_user.id,
            original_filename=sanitize_filename(manuscript_file.filename) if manuscript_file else None,
            input_type='pdf' if manuscript_file else 'text',
            manuscript_text=manuscript_text[:10000],
            status='PENDING'
        )
        db.add(analysis)
        await db.commit()
        await db.refresh(analysis)
        
        # Trigger background task
        from app.tasks.analysis import process_manuscript_task
        task = process_manuscript_task.delay(analysis.id, manuscript_text)
        
        # Update with task_id
        analysis.task_id = task.id
        await db.commit()
        
        return {
            "task_id": task.id,
            "analysis_id": analysis.id,
            "status": "PENDING",
            "message": "Analysis started successfully. Poll /status/{task_id} for results."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis submission error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during submission"
        )


@router.get("/status/{task_id}")
async def get_analysis_status(
    task_id: str,
    db: DbSession,
    current_user: AuthenticatedUser
):
    """Check the status of an analysis task."""
    stmt = select(ManuscriptAnalysis).filter(
        ManuscriptAnalysis.task_id == task_id,
        ManuscriptAnalysis.user_id == current_user.id
    )
    result = await db.execute(stmt)
    analysis = result.scalar_one_or_none()
    
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis task not found"
        )
        
    if analysis.status == 'COMPLETED':
        return AnalysisResponse(
            summary=analysis.summary,
            keywords=analysis.keywords,
            language_quality=LanguageQuality(**analysis.language_quality),
            metadata=AnalysisMetadata(
                analysis_id=analysis.id,
                input_length=len(analysis.manuscript_text),
                processing_time=round(analysis.processing_time, 2) if analysis.processing_time else 0,
                user=current_user.username,
                timestamp=analysis.created_at,
                cached=False
            )
        )
    elif analysis.status == 'FAILED':
        return {
            "task_id": task_id,
            "status": "FAILED",
            "message": "Analysis failed. Please try again."
        }
    else:
        return {
            "task_id": task_id,
            "status": analysis.status,
            "message": "Analysis in progress..."
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
            detail="Text too short for meaningful analysis (minimum 50 characters)"
        )
    
    try:
        # Check cache
        cached_result = AIResultCache.get_cached_result(manuscript_text)
        if cached_result:
            logger.info("Cache hit for demo request")
            cached_result["metadata"]["cached"] = True
            cached_result["metadata"]["demo"] = True
            return cached_result
        
        # Generate analysis
        logger.info(f"Processing demo manuscript ({len(manuscript_text)} chars)")
        report = pre_reviewer.generate_report(manuscript_text)
        processing_time = time.time() - start_time
        
        response = AnalysisResponse(
            summary=report['summary'],
            keywords=report['keywords'],
            language_quality=LanguageQuality(**report['language_quality']),
            metadata=AnalysisMetadata(
                input_length=len(manuscript_text),
                processing_time=round(processing_time, 2),
                cached=False,
                demo=True
            )
        )
        
        # Cache for 2 hours
        AIResultCache.cache_result(manuscript_text, response.model_dump(), ttl=7200)
        
        return response
        
    except Exception as e:
        logger.error(f"Demo analysis error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during processing"
        )


@router.get("/history", response_model=AnalysisHistoryResponse)
async def get_history(
    db: DbSession,
    current_user: AuthenticatedUser,
    page: int = 1,
    page_size: int = 20
):
    """Get user's analysis history with pagination."""
    
    page_size = min(page_size, 100)
    offset = (page - 1) * page_size
    
    # Query analyses
    query = select(ManuscriptAnalysis).filter(
        ManuscriptAnalysis.user_id == current_user.id
    ).order_by(ManuscriptAnalysis.created_at.desc())
    
    # Count total
    count_stmt = select(func.count()).select_from(ManuscriptAnalysis).filter(
        ManuscriptAnalysis.user_id == current_user.id
    )
    total_count_result = await db.execute(count_stmt)
    total_count = total_count_result.scalar()

    # Get page
    result = await db.execute(query.offset(offset).limit(page_size))
    analyses = result.scalars().all()
    
    # Build response
    results = []
    for analysis in analyses:
        results.append(AnalysisHistoryItem(
            id=analysis.id,
            filename=analysis.original_filename,
            input_type=analysis.input_type,
            word_count=analysis.language_quality.get('word_count', 0),
            readability_score=analysis.language_quality.get('readability_score', 0),
            created_at=analysis.created_at,
            processing_time=analysis.processing_time
        ))
    
    return AnalysisHistoryResponse(
        results=results,
        pagination={
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": (total_count + page_size - 1) // page_size,
            "has_next": offset + page_size < total_count,
            "has_previous": page > 1
        }
    )


@router.get("/cache/stats")
async def cache_stats():
    """Get cache statistics."""
    stats = AIResultCache.get_cache_stats()
    return {"cache": stats, "message": "Cache statistics retrieved successfully"}


@router.post("/cache/clear")
async def clear_cache(current_user: AuthenticatedUser):
    """Clear cache (authenticated users only)."""
    success = AIResultCache.clear_all_cache()
    return {
        "message": "Cache cleared successfully" if success else "Failed to clear cache",
        "cleared_by": current_user.username
    }
