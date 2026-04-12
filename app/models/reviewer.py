"""
Reviewer models for reviewer matching feature.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, JSON, LargeBinary, Index
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.utils import utc_now


class Reviewer(Base):
    """
    Reviewer profile for manuscript-reviewer matching.
    
    Each reviewer has expertise keywords and an optional embedding
    for semantic similarity matching.
    """
    
    __tablename__ = "reviewers"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )
    
    # Expertise information
    expertise_keywords = Column(JSON, default=list)  # List of keyword strings
    expertise_embedding = Column(LargeBinary, nullable=True)  # Serialized embedding vector
    expertise_description = Column(String(1000), nullable=True)  # Free-text description
    
    # Professional information
    institution = Column(String(255), nullable=True)
    department = Column(String(255), nullable=True)
    orcid_id = Column(String(50), nullable=True, unique=True)
    
    # Availability settings
    is_available = Column(Boolean, default=True, index=True)
    current_assignments = Column(Integer, default=0)
    max_assignments = Column(Integer, default=5)
    
    # Timestamps
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    user = relationship("User", back_populates="reviewer_profile")
    matches = relationship("ReviewerMatch", back_populates="reviewer", cascade="all, delete-orphan")
    
    # Composite index for finding available reviewers
    __table_args__ = (
        Index('ix_reviewers_available_assignments', 'is_available', 'current_assignments'),
    )
    
    def __repr__(self):
        return f"<Reviewer(id={self.id}, user_id={self.user_id})>"
    
    @property
    def available_slots(self) -> int:
        """Number of available review slots."""
        return max(0, self.max_assignments - self.current_assignments)
    
    @property
    def is_accepting_reviews(self) -> bool:
        """Whether reviewer is accepting new assignments."""
        return self.is_available and self.available_slots > 0


class ReviewerMatch(Base):
    """
    Record of a manuscript-reviewer match suggestion or assignment.
    """
    
    __tablename__ = "reviewer_matches"
    
    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(
        Integer, 
        ForeignKey("manuscript_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    reviewer_id = Column(
        Integer, 
        ForeignKey("reviewers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Match details
    match_score = Column(Float, nullable=False)  # 0.0 - 1.0
    matched_keywords = Column(JSON, default=list)  # Keywords that matched
    match_method = Column(String(50), default="keyword")  # keyword, semantic, hybrid
    
    # Status tracking
    status = Column(
        String(20), 
        default="suggested",
        index=True
    )  # suggested, invited, accepted, declined, completed
    
    # Timestamps
    created_at = Column(DateTime, default=utc_now, index=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    invited_at = Column(DateTime, nullable=True)
    responded_at = Column(DateTime, nullable=True)
    
    # Relationships
    reviewer = relationship("Reviewer", back_populates="matches")
    analysis = relationship("ManuscriptAnalysis", back_populates="reviewer_matches")
    
    # Composite indexes for common query patterns
    __table_args__ = (
        Index('ix_reviewer_matches_analysis_status', 'analysis_id', 'status'),
        Index('ix_reviewer_matches_reviewer_status', 'reviewer_id', 'status'),
        Index('ix_reviewer_matches_score', 'analysis_id', 'match_score'),
    )
    
    def __repr__(self):
        return f"<ReviewerMatch(id={self.id}, analysis_id={self.analysis_id}, reviewer_id={self.reviewer_id}, score={self.match_score})>"
