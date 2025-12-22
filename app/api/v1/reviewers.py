"""
Reviewer management and matching API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.config import settings
from app.models.user import User
from app.models.reviewer import Reviewer, ReviewerMatch
from app.models.analysis import ManuscriptAnalysis
from app.schemas.reviewer import (
    ReviewerCreate,
    ReviewerUpdate,
    ReviewerResponse,
    ReviewerSuggestion,
    ReviewerMatchResponse,
    ReviewerAssignRequest,
    ReviewerMatchStatus,
    ReviewerListResponse,
    ReviewerSuggestionsResponse
)
from app.services.reviewer_matcher import get_reviewer_matcher

logger = logging.getLogger(__name__)
router = APIRouter()


def _reviewer_to_response(reviewer: Reviewer) -> ReviewerResponse:
    """Convert Reviewer model to response schema."""
    return ReviewerResponse(
        id=reviewer.id,
        user_id=reviewer.user_id,
        username=reviewer.user.username if reviewer.user else "Unknown",
        email=reviewer.user.email if reviewer.user else "",
        expertise_keywords=reviewer.expertise_keywords or [],
        expertise_description=reviewer.expertise_description,
        institution=reviewer.institution,
        department=reviewer.department,
        orcid_id=reviewer.orcid_id,
        is_available=reviewer.is_available,
        current_assignments=reviewer.current_assignments,
        max_assignments=reviewer.max_assignments,
        available_slots=reviewer.available_slots,
        created_at=reviewer.created_at,
        updated_at=reviewer.updated_at
    )


@router.post("/", response_model=ReviewerResponse, status_code=status.HTTP_201_CREATED)
async def create_reviewer_profile(
    request: ReviewerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a reviewer profile for the current user.
    
    A user can only have one reviewer profile.
    """
    if not settings.ENABLE_REVIEWER_MATCHING:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Reviewer matching is disabled"
        )
    
    # Check if user already has a reviewer profile
    existing = db.query(Reviewer).filter(Reviewer.user_id == current_user.id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a reviewer profile"
        )
    
    try:
        # Create expertise embedding
        matcher = get_reviewer_matcher()
        embedding = matcher.create_expertise_embedding(
            request.expertise_keywords,
            request.expertise_description
        )
        
        # Create reviewer profile
        reviewer = Reviewer(
            user_id=current_user.id,
            expertise_keywords=request.expertise_keywords,
            expertise_description=request.expertise_description,
            expertise_embedding=embedding,
            institution=request.institution,
            department=request.department,
            orcid_id=request.orcid_id,
            max_assignments=request.max_assignments
        )
        
        db.add(reviewer)
        db.commit()
        db.refresh(reviewer)
        
        logger.info(f"Created reviewer profile for user {current_user.username}")
        
        return _reviewer_to_response(reviewer)
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create reviewer profile: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create reviewer profile"
        )


@router.get("/me", response_model=ReviewerResponse)
async def get_my_reviewer_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the current user's reviewer profile."""
    reviewer = db.query(Reviewer).filter(Reviewer.user_id == current_user.id).first()
    
    if not reviewer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No reviewer profile found for current user"
        )
    
    return _reviewer_to_response(reviewer)


@router.put("/me", response_model=ReviewerResponse)
async def update_my_reviewer_profile(
    request: ReviewerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update the current user's reviewer profile."""
    reviewer = db.query(Reviewer).filter(Reviewer.user_id == current_user.id).first()
    
    if not reviewer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No reviewer profile found for current user"
        )
    
    try:
        # Update fields if provided
        if request.expertise_keywords is not None:
            reviewer.expertise_keywords = request.expertise_keywords
        if request.expertise_description is not None:
            reviewer.expertise_description = request.expertise_description
        if request.institution is not None:
            reviewer.institution = request.institution
        if request.department is not None:
            reviewer.department = request.department
        if request.orcid_id is not None:
            reviewer.orcid_id = request.orcid_id
        if request.is_available is not None:
            reviewer.is_available = request.is_available
        if request.max_assignments is not None:
            reviewer.max_assignments = request.max_assignments
        
        # Re-create embedding if keywords or description changed
        if request.expertise_keywords is not None or request.expertise_description is not None:
            matcher = get_reviewer_matcher()
            reviewer.expertise_embedding = matcher.create_expertise_embedding(
                reviewer.expertise_keywords,
                reviewer.expertise_description
            )
        
        db.commit()
        db.refresh(reviewer)
        
        logger.info(f"Updated reviewer profile for user {current_user.username}")
        
        return _reviewer_to_response(reviewer)
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update reviewer profile: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update reviewer profile"
        )


@router.get("/", response_model=ReviewerListResponse)
async def list_reviewers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    available_only: bool = Query(False),
    keyword: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all reviewers with optional filtering.
    
    - **available_only**: Only show reviewers accepting new assignments
    - **keyword**: Filter by expertise keyword
    """
    query = db.query(Reviewer)
    
    if available_only:
        query = query.filter(Reviewer.is_available == True)
    
    if keyword:
        # JSON array contains filter (PostgreSQL specific, falls back to LIKE for others)
        query = query.filter(
            Reviewer.expertise_keywords.contains([keyword.lower()])
        )
    
    total_count = query.count()
    offset = (page - 1) * page_size
    reviewers = query.offset(offset).limit(page_size).all()
    
    return ReviewerListResponse(
        results=[_reviewer_to_response(r) for r in reviewers],
        total_count=total_count,
        page=page,
        page_size=page_size,
        has_next=offset + page_size < total_count,
        has_previous=page > 1
    )


@router.get("/analysis/{analysis_id}/suggestions", response_model=ReviewerSuggestionsResponse)
async def get_reviewer_suggestions(
    analysis_id: int,
    top_n: int = Query(5, ge=1, le=20),
    min_score: float = Query(0.1, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get reviewer suggestions for a manuscript analysis.
    
    - **top_n**: Maximum number of suggestions (1-20)
    - **min_score**: Minimum match score threshold (0.0-1.0)
    """
    if not settings.ENABLE_REVIEWER_MATCHING:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Reviewer matching is disabled"
        )
    
    # Get the analysis
    analysis = db.query(ManuscriptAnalysis).filter(
        ManuscriptAnalysis.id == analysis_id
    ).first()
    
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found"
        )
    
    # Check permission (user must own the analysis or be admin)
    if analysis.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this analysis"
        )
    
    # Get keywords from analysis
    manuscript_keywords = analysis.keywords or []
    manuscript_text = analysis.manuscript_text or ""
    
    # Find matching reviewers
    matcher = get_reviewer_matcher()
    suggestions = matcher.find_matching_reviewers(
        manuscript_keywords=manuscript_keywords,
        manuscript_text=manuscript_text,
        db=db,
        top_n=top_n,
        min_score=min_score,
        exclude_user_ids=[current_user.id]  # Exclude manuscript author
    )
    
    # Count available reviewers
    available_count = db.query(Reviewer).filter(
        Reviewer.is_available == True
    ).count()
    
    return ReviewerSuggestionsResponse(
        analysis_id=analysis_id,
        manuscript_keywords=manuscript_keywords,
        suggestions=[
            ReviewerSuggestion(
                reviewer_id=s.reviewer_id,
                user_id=s.user_id,
                username=s.username,
                match_score=s.match_score,
                matched_keywords=s.matched_keywords,
                match_method=s.match_method,
                institution=s.institution,
                expertise_keywords=s.expertise_keywords,
                available_slots=s.available_slots
            )
            for s in suggestions
        ],
        total_available_reviewers=available_count
    )


@router.post("/analysis/{analysis_id}/assign/{reviewer_id}", response_model=ReviewerMatchResponse)
async def assign_reviewer(
    analysis_id: int,
    reviewer_id: int,
    request: ReviewerAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Assign a reviewer to a manuscript analysis.
    """
    # Get the analysis
    analysis = db.query(ManuscriptAnalysis).filter(
        ManuscriptAnalysis.id == analysis_id
    ).first()
    
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found"
        )
    
    # Check permission
    if analysis.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to assign reviewers to this analysis"
        )
    
    # Get the reviewer
    reviewer = db.query(Reviewer).filter(Reviewer.id == reviewer_id).first()
    
    if not reviewer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reviewer not found"
        )
    
    if not reviewer.is_accepting_reviews:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reviewer is not accepting new assignments"
        )
    
    # Check if already assigned
    existing_match = db.query(ReviewerMatch).filter(
        ReviewerMatch.analysis_id == analysis_id,
        ReviewerMatch.reviewer_id == reviewer_id
    ).first()
    
    if existing_match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reviewer is already assigned to this analysis"
        )
    
    try:
        # Calculate match score
        matcher = get_reviewer_matcher()
        keyword_score, matched_keywords = matcher.calculate_keyword_similarity(
            analysis.keywords or [],
            reviewer.expertise_keywords or []
        )
        
        # Create match record
        match = ReviewerMatch(
            analysis_id=analysis_id,
            reviewer_id=reviewer_id,
            match_score=keyword_score,
            matched_keywords=matched_keywords,
            match_method="keyword",
            status="invited" if request.send_invitation else "suggested",
            invited_at=datetime.utcnow() if request.send_invitation else None
        )
        
        db.add(match)
        
        # Update reviewer's current assignments
        reviewer.current_assignments += 1
        
        db.commit()
        db.refresh(match)
        
        logger.info(f"Assigned reviewer {reviewer_id} to analysis {analysis_id}")
        
        return ReviewerMatchResponse(
            id=match.id,
            analysis_id=match.analysis_id,
            reviewer_id=match.reviewer_id,
            reviewer_username=reviewer.user.username if reviewer.user else "Unknown",
            match_score=match.match_score,
            matched_keywords=match.matched_keywords,
            status=match.status,
            created_at=match.created_at,
            invited_at=match.invited_at,
            responded_at=match.responded_at
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to assign reviewer: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign reviewer"
        )


@router.get("/my-assignments", response_model=List[ReviewerMatchResponse])
async def get_my_assignments(
    status_filter: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get review assignments for the current user's reviewer profile."""
    # Get user's reviewer profile
    reviewer = db.query(Reviewer).filter(Reviewer.user_id == current_user.id).first()
    
    if not reviewer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No reviewer profile found"
        )
    
    query = db.query(ReviewerMatch).filter(ReviewerMatch.reviewer_id == reviewer.id)
    
    if status_filter:
        query = query.filter(ReviewerMatch.status == status_filter)
    
    matches = query.order_by(ReviewerMatch.created_at.desc()).all()
    
    return [
        ReviewerMatchResponse(
            id=m.id,
            analysis_id=m.analysis_id,
            reviewer_id=m.reviewer_id,
            reviewer_username=current_user.username,
            match_score=m.match_score,
            matched_keywords=m.matched_keywords,
            status=m.status,
            created_at=m.created_at,
            invited_at=m.invited_at,
            responded_at=m.responded_at
        )
        for m in matches
    ]


@router.put("/assignments/{match_id}/status", response_model=ReviewerMatchResponse)
async def update_assignment_status(
    match_id: int,
    request: ReviewerMatchStatus,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update the status of a review assignment.
    
    Reviewers can accept or decline invitations.
    """
    # Get the match
    match = db.query(ReviewerMatch).filter(ReviewerMatch.id == match_id).first()
    
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found"
        )
    
    # Check permission (must be the assigned reviewer)
    reviewer = db.query(Reviewer).filter(Reviewer.user_id == current_user.id).first()
    
    if not reviewer or reviewer.id != match.reviewer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this assignment"
        )
    
    # Validate status transition
    valid_statuses = ["accepted", "declined", "completed"]
    if request.status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {valid_statuses}"
        )
    
    try:
        old_status = match.status
        match.status = request.status
        match.responded_at = datetime.utcnow()
        
        # Update reviewer's assignment count
        if request.status == "declined" and old_status != "declined":
            reviewer.current_assignments = max(0, reviewer.current_assignments - 1)
        elif request.status == "completed" and old_status != "completed":
            reviewer.current_assignments = max(0, reviewer.current_assignments - 1)
        
        db.commit()
        db.refresh(match)
        
        logger.info(f"Updated assignment {match_id} status to {request.status}")
        
        return ReviewerMatchResponse(
            id=match.id,
            analysis_id=match.analysis_id,
            reviewer_id=match.reviewer_id,
            reviewer_username=current_user.username,
            match_score=match.match_score,
            matched_keywords=match.matched_keywords,
            status=match.status,
            created_at=match.created_at,
            invited_at=match.invited_at,
            responded_at=match.responded_at
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update assignment status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update assignment status"
        )
