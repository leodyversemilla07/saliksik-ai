"""
Manuscript analysis model.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Float,
    ForeignKey,
    JSON,
    Index,
)
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.utils import utc_now


class ManuscriptAnalysis(Base):
    """Store manuscript analysis results."""

    __tablename__ = "manuscript_analyses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # Input information
    original_filename = Column(String(255), nullable=True)
    input_type = Column(String(10), default="text")  # 'text' or 'pdf'
    manuscript_text = Column(Text, nullable=False)

    # Analysis results
    summary = Column(Text, nullable=True)  # Nullable until processed
    keywords = Column(JSON, default=list)
    language_quality = Column(JSON, default=dict)

    # Enhancement features results
    detected_language = Column(String(10), nullable=True)  # ISO 639-1 code
    citation_analysis = Column(JSON, nullable=True)  # Citation analysis results

    # Async Task Info
    status = Column(
        String(20), default="PENDING", index=True
    )  # PENDING, PROCESSING, COMPLETED, FAILED
    task_id = Column(String(50), unique=True, nullable=True, index=True)

    # Metadata
    created_at = Column(DateTime, default=utc_now, index=True)
    processing_time = Column(Float, nullable=True)

    # Relationships
    user = relationship("User", back_populates="analyses")
    fingerprint = relationship(
        "DocumentFingerprint",
        back_populates="analysis",
        uselist=False,
        cascade="all, delete-orphan",
    )
    reviewer_matches = relationship(
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

    id = Column(Integer, primary_key=True, index=True)
    error_type = Column(String(100), nullable=False, index=True)
    error_message = Column(Text, nullable=False)
    input_type = Column(String(10), default="text")
    input_size = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=utc_now, index=True)

    # Composite index for error analysis
    __table_args__ = (
        Index("ix_processing_errors_type_date", "error_type", "created_at"),
    )
