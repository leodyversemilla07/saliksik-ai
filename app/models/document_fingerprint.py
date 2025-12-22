"""
Document fingerprint model for plagiarism detection.
Stores MinHash fingerprints for efficient similarity comparison.
"""
from sqlalchemy import Column, Integer, LargeBinary, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class DocumentFingerprint(Base):
    """
    Store document fingerprints for plagiarism detection.
    
    Each manuscript analysis can have an associated fingerprint
    that enables efficient similarity checking using MinHash LSH.
    """
    
    __tablename__ = "document_fingerprints"
    
    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(
        Integer, 
        ForeignKey("manuscript_analyses.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )
    
    # Serialized MinHash object
    fingerprint_hash = Column(LargeBinary, nullable=False)
    
    # Store shingles for debugging and segment matching
    # JSON array of n-gram strings
    shingles = Column(JSON, default=list)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationship to the analysis
    analysis = relationship(
        "ManuscriptAnalysis",
        back_populates="fingerprint",
        uselist=False
    )
    
    def __repr__(self):
        return f"<DocumentFingerprint(id={self.id}, analysis_id={self.analysis_id})>"
