"""
Pydantic schemas for reviewer matching.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ReviewerCreate(BaseModel):
    """Schema for creating a reviewer profile."""

    expertise_keywords: List[str] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="List of expertise keywords (1-20 keywords)",
    )
    expertise_description: Optional[str] = Field(
        None, max_length=1000, description="Free-text description of expertise"
    )
    institution: Optional[str] = Field(
        None, max_length=255, description="Institution or organization name"
    )
    department: Optional[str] = Field(
        None, max_length=255, description="Department or division"
    )
    orcid_id: Optional[str] = Field(
        None,
        pattern=r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$",
        description="ORCID identifier (format: 0000-0000-0000-0000)",
    )
    max_assignments: int = Field(
        default=5, ge=1, le=20, description="Maximum concurrent review assignments"
    )


class ReviewerUpdate(BaseModel):
    """Schema for updating a reviewer profile."""

    expertise_keywords: Optional[List[str]] = Field(
        None, max_length=20, description="Updated expertise keywords"
    )
    expertise_description: Optional[str] = Field(
        None, max_length=1000, description="Updated expertise description"
    )
    institution: Optional[str] = Field(
        None, max_length=255, description="Updated institution"
    )
    department: Optional[str] = Field(
        None, max_length=255, description="Updated department"
    )
    orcid_id: Optional[str] = Field(None, description="Updated ORCID identifier")
    is_available: Optional[bool] = Field(
        None, description="Whether accepting new reviews"
    )
    max_assignments: Optional[int] = Field(
        None, ge=1, le=20, description="Updated max assignments"
    )


class ReviewerPublicResponse(BaseModel):
    """Public response schema for reviewer profile (safe for any authenticated user to see).

    Omits PII (email) and internal fields (user_id, assignment counters, timestamps).
    """

    id: int
    username: str
    expertise_keywords: List[str]
    expertise_description: Optional[str] = None
    institution: Optional[str] = None
    department: Optional[str] = None
    orcid_id: Optional[str] = None
    is_available: bool
    available_slots: int

    model_config = ConfigDict(from_attributes=True)


class ReviewerResponse(BaseModel):
    """Response schema for reviewer profile."""

    id: int
    user_id: int
    username: str
    email: str
    expertise_keywords: List[str]
    expertise_description: Optional[str]
    institution: Optional[str]
    department: Optional[str]
    orcid_id: Optional[str]
    is_available: bool
    current_assignments: int
    max_assignments: int
    available_slots: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewerSuggestion(BaseModel):
    """A suggested reviewer match for a manuscript."""

    reviewer_id: int
    username: str
    match_score: float = Field(..., ge=0.0, le=1.0, description="Match score (0-1)")
    matched_keywords: List[str] = Field(default_factory=list)
    match_method: str = Field(..., description="keyword, semantic, or hybrid")
    institution: Optional[str] = None
    expertise_keywords: List[str] = Field(default_factory=list)
    available_slots: int = 0

    model_config = ConfigDict(from_attributes=True)


class ReviewerMatchResponse(BaseModel):
    """Response for a reviewer match/assignment."""

    id: int
    analysis_id: int
    reviewer_id: int
    reviewer_username: str
    match_score: float
    matched_keywords: List[str]
    status: str
    created_at: datetime
    invited_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ReviewerAssignRequest(BaseModel):
    """Request to assign a reviewer to a manuscript."""

    send_invitation: bool = Field(
        default=True, description="Whether to send an invitation notification"
    )
    message: Optional[str] = Field(
        None, max_length=500, description="Optional message to include with invitation"
    )


class ReviewerMatchStatus(BaseModel):
    """Request to update reviewer match status."""

    status: str = Field(..., description="New status: accepted, declined, completed")
    response_message: Optional[str] = Field(
        None, max_length=500, description="Optional response message"
    )


class ReviewerListResponse(BaseModel):
    """Paginated list of reviewers (public view)."""

    results: List[ReviewerPublicResponse]
    total_count: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool


class ReviewerSuggestionsResponse(BaseModel):
    """Response containing reviewer suggestions for a manuscript."""

    analysis_id: int
    manuscript_keywords: List[str]
    suggestions: List[ReviewerSuggestion]
    total_available_reviewers: int
