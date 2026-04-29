from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import utc_now

if TYPE_CHECKING:
    from app.models.document_fingerprint import DocumentFingerprint
    from app.models.reviewer import ReviewerMatch
    from app.models.user import User


class ManuscriptAnalysis(Base):
    """Store manuscript analysis results."""

    __tablename__ = "manuscript_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # Input information
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input_type: Mapped[str] = mapped_column(String(10), default="text")
    manuscript_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Analysis results
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    language_quality: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)

    # Enhancement features results
    detected_language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    citation_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Async Task Info
    status: Mapped[str] = mapped_column(
        String(20), default="PENDING", index=True
    )  # PENDING, PROCESSING, COMPLETED, FAILED
    task_id: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True, index=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    processing_time: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="analyses")
    fingerprint: Mapped[DocumentFingerprint | None] = relationship(
        "DocumentFingerprint",
        back_populates="analysis",
        uselist=False,
        cascade="all, delete-orphan",
    )
    reviewer_matches: Mapped[list[ReviewerMatch]] = relationship(
        "ReviewerMatch",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )

    # Composite indexes for common query patterns
    __table_args__ = (
        Index("ix_manuscript_analyses_user_status", "user_id", "status"),
        Index("ix_manuscript_analyses_user_created", "user_id", "created_at"),
    )


class ProcessingError(Base):
    """Log processing errors for debugging."""

    __tablename__ = "processing_errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    error_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    input_type: Mapped[str] = mapped_column(String(10), default="text")
    input_size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    # Composite index for error analysis
    __table_args__ = (Index("ix_processing_errors_type_date", "error_type", "created_at"),)
