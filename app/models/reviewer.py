"""
Reviewer models for reviewer matching feature.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import utc_now

if TYPE_CHECKING:
    from app.models.analysis import ManuscriptAnalysis
    from app.models.user import User


class Reviewer(Base):
    """
    Reviewer profile for manuscript-reviewer matching.
    """

    __tablename__ = "reviewers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # Expertise information
    expertise_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    expertise_embedding: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    expertise_description: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Professional information
    institution: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    orcid_id: Mapped[str | None] = mapped_column(String(50), nullable=True, unique=True)

    # Availability settings
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    current_assignments: Mapped[int] = mapped_column(Integer, default=0)
    max_assignments: Mapped[int] = mapped_column(Integer, default=5)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="reviewer_profile")
    matches: Mapped[list["ReviewerMatch"]] = relationship(
        "ReviewerMatch", back_populates="reviewer", cascade="all, delete-orphan"
    )

    # Composite index for finding available reviewers
    __table_args__ = (Index("ix_reviewers_available_assignments", "is_available", "current_assignments"),)

    def __repr__(self):
        return f"<Reviewer(id={self.id}, user_id={self.user_id})>"

    @property
    def available_slots(self) -> int:
        """Number of available review slots."""
        return max(0, self.max_assignments - self.current_assignments)

    @property
    def is_accepting_reviews(self) -> bool:
        """Whether reviewer is accepting new assignments."""
        return bool(self.is_available and self.available_slots > 0)


class ReviewerMatch(Base):
    """
    Record of a manuscript-reviewer match suggestion or assignment.
    """

    __tablename__ = "reviewer_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    analysis_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("manuscript_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("reviewers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Match details
    match_score: Mapped[float] = mapped_column(Float, nullable=False)
    matched_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    match_method: Mapped[str] = mapped_column(String(50), default="keyword")

    # Status tracking
    status: Mapped[str] = mapped_column(
        String(20), default="suggested", index=True
    )  # suggested, invited, accepted, declined, completed

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
    invited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    reviewer: Mapped["Reviewer"] = relationship("Reviewer", back_populates="matches")
    analysis: Mapped["ManuscriptAnalysis"] = relationship("ManuscriptAnalysis", back_populates="reviewer_matches")

    # Composite indexes for common query patterns
    __table_args__ = (
        Index("ix_reviewer_matches_analysis_status", "analysis_id", "status"),
        Index("ix_reviewer_matches_reviewer_status", "reviewer_id", "status"),
        Index("ix_reviewer_matches_score", "analysis_id", "match_score"),
    )

    def __repr__(self):
        return (
            f"<ReviewerMatch(id={self.id}, "
            f"analysis_id={self.analysis_id}, "
            f"reviewer_id={self.reviewer_id}, "
            f"score={self.match_score})>"
        )
