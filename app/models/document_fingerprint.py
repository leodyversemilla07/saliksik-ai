"""
Document fingerprint model for plagiarism detection.
Stores MinHash fingerprints for efficient similarity comparison.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


if TYPE_CHECKING:
    from app.models.analysis import ManuscriptAnalysis


class DocumentFingerprint(Base):
    """
    Store document fingerprints for plagiarism detection.
    """

    __tablename__ = "document_fingerprints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    analysis_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("manuscript_analyses.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # Serialized MinHash object
    fingerprint_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    # Store shingles for debugging and segment matching
    shingles: Mapped[list] = mapped_column(JSON, default=list)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    # Relationship to the analysis
    analysis: Mapped["ManuscriptAnalysis"] = relationship(
        "ManuscriptAnalysis", back_populates="fingerprint", uselist=False
    )

    def __repr__(self):
        return f"<DocumentFingerprint(id={self.id}, analysis_id={self.analysis_id})>"
