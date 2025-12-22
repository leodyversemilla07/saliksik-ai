"""
Plagiarism detection API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy.orm import Session
import logging

from app.core.database import get_db
from app.core.deps import get_current_user
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
        
        # Check against database
        result = detector.check_similarity_with_database(
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
async def get_plagiarism_stats():
    """
    Get plagiarism detection index statistics.
    
    Returns information about the plagiarism detection system
    including number of indexed documents and configuration.
    """
    detector = get_plagiarism_detector()
    stats = detector.get_index_stats()
    
    return PlagiarismIndexStats(**stats)


@router.post("/index/rebuild")
async def rebuild_plagiarism_index(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Rebuild the plagiarism detection index from database.
    
    This operation loads all document fingerprints from the database
    into the in-memory LSH index for faster querying.
    
    Note: This is an admin operation and may take time for large databases.
    """
    from app.models.document_fingerprint import DocumentFingerprint
    from app.models.analysis import ManuscriptAnalysis
    
    try:
        detector = get_plagiarism_detector()
        
        # Get all analyses with their fingerprints
        analyses = db.query(ManuscriptAnalysis).filter(
            ManuscriptAnalysis.status == 'COMPLETED'
        ).all()
        
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
