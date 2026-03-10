"""
Plagiarism detection API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Annotated
import logging

from app.core.database import get_db
from app.core.deps import get_authenticated_user, DbSession, AuthenticatedUser, AdminUser
from app.core.config import settings
from app.models.user import User
from app.schemas.plagiarism import (
    PlagiarismResult,
    PlagiarismCheckRequest,
    PlagiarismIndexStats
)
from app.services.plagiarism_detector import get_plagiarism_detector

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/check", response_model=PlagiarismResult)
async def check_plagiarism(
    request: PlagiarismCheckRequest,
    db: DbSession,
    current_user: AuthenticatedUser
):
    """
    Check manuscript text for plagiarism against stored documents.
    
    This endpoint compares the submitted text against all previously
    analyzed manuscripts to detect potential similarities.
    
    - **manuscript_text**: The text to check (50-100000 characters)
    - **threshold**: Optional similarity threshold (0.1-0.95, default: 0.5)
    """
    if not settings.ENABLE_PLAGIARISM_CHECK:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Plagiarism checking is disabled"
        )
    
    try:
        detector = get_plagiarism_detector()
        
        # Check against database (async)
        result = await detector.check_similarity_with_database_async(
            text=request.manuscript_text,
            db=db
        )
        
        logger.info(
            f"Plagiarism check by {current_user.username}: "
            f"similarity={result.overall_similarity}, "
            f"checked_against={result.checked_against}"
        )
        
        return PlagiarismResult(
            is_plagiarized=result.is_plagiarized,
            overall_similarity=result.overall_similarity,
            similar_documents=[
                {
                    "analysis_id": doc.analysis_id,
                    "similarity_score": doc.similarity_score,
                    "matched_segments": doc.matched_segments,
                    "original_filename": doc.original_filename
                }
                for doc in result.similar_documents
            ],
            unique_content_percentage=result.unique_content_percentage,
            processing_time=result.processing_time,
            checked_against=result.checked_against
        )
        
    except Exception as e:
        logger.error(f"Plagiarism check error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error during plagiarism check"
        )


@router.get("/stats", response_model=PlagiarismIndexStats)
async def get_plagiarism_stats(
    current_user: AuthenticatedUser
):
    """
    Get plagiarism detection index statistics.
    
    Returns information about the plagiarism detection system
    including number of indexed documents and configuration.
    
    Requires authentication.
    """
    detector = get_plagiarism_detector()
    stats = detector.get_index_stats()
    
    return PlagiarismIndexStats(**stats)


@router.post("/index/rebuild")
async def rebuild_plagiarism_index(
    db: DbSession,
    current_user: AdminUser
):
    """
    Rebuild the plagiarism detection index from database.
    
    This operation loads all document fingerprints from the database
    into the in-memory LSH index for faster querying.
    
    Note: This is an admin operation and may take time for large databases.
    """
    from app.models.analysis import ManuscriptAnalysis
    
    try:
        detector = get_plagiarism_detector()
        
        # Get all analyses with their fingerprints (async)
        stmt = select(ManuscriptAnalysis).filter(
            ManuscriptAnalysis.status == 'COMPLETED'
        )
        result = await db.execute(stmt)
        analyses = result.scalars().all()
        
        indexed_count = 0
        for analysis in analyses:
            if analysis.manuscript_text:
                success = detector.add_to_index(
                    doc_id=analysis.id,
                    text=analysis.manuscript_text,
                    filename=analysis.original_filename
                )
                if success:
                    indexed_count += 1
        
        logger.info(f"Rebuilt plagiarism index: {indexed_count} documents indexed by {current_user.username}")
        
        return {
            "message": "Index rebuilt successfully",
            "documents_indexed": indexed_count,
            "rebuilt_by": current_user.username
        }
        
    except Exception as e:
        logger.error(f"Failed to rebuild index: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to rebuild plagiarism index"
        )
