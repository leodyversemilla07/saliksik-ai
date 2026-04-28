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
from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import utc_now


class ManuscriptAnalysis(Base):
    """Store manuscript analysis results."""

    __tablename__ = "manuscript_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # Input information
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input_type: Mapped[str] = mapped_column(String(10), default="text")  # 'text' or 'pdf'
    manuscript_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Analysis results
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)  # Nullable until processed
    keywords: Mapped[dict] = mapped_column(JSON, default=list)
    language_quality: Mapped[dict] = mapped_column(JSON, default=dict)

    # Enhancement features results
    detected_language: Mapped[str | None] = mapped_column(String(10), nullable=True)  # ISO 639-1 code
    citation_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Citation analysis results

    # Async Task Info
    status: Mapped[str] = mapped_column(
        String(20), default="PENDING", index=True
    )  # PENDING, PROCESSING, COMPLETED, FAILED
    task_id: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True, index=True)

    # Metadata
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=utc_now, index=True)
    processing_time: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="analyses")
    fingerprint: Mapped[Optional["DocumentFingerprint"]] = relationship(
        "DocumentFingerprint",
        back_populates="analysis",
        uselist=False,
        cascade="all, delete-orphan",
    )
    reviewer_matches: Mapped[list["ReviewerMatch"]] = relationship(
        "ReviewerMatch", back_populates="analysis", cascade="all, delete-orphan"
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
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=utc_now, index=True)

    # Composite index for error analysis
    __table_args__ = (
        Index("ix_processing_errors_type_date", "error_type", "created_at"),
    )
