"""
Manuscript analysis model.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class ManuscriptAnalysis(Base):
    """Store manuscript analysis results."""
    
    __tablename__ = "manuscript_analyses"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    
    # Input information
    original_filename = Column(String(255), nullable=True)
    input_type = Column(String(10), default='text')  # 'text' or 'pdf'
    manuscript_text = Column(Text, nullable=False)
    
    # Analysis results
    summary = Column(Text, nullable=True)  # Nullable until processed
    keywords = Column(JSON, default=list)
    language_quality = Column(JSON, default=dict)
    
    # Async Task Info
    status = Column(String(20), default='PENDING', index=True)  # PENDING, PROCESSING, COMPLETED, FAILED
    task_id = Column(String(50), unique=True, nullable=True, index=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    processing_time = Column(Float, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="analyses")


class ProcessingError(Base):
    """Log processing errors for debugging."""
    
    __tablename__ = "processing_errors"
    
    id = Column(Integer, primary_key=True, index=True)
    error_type = Column(String(100), nullable=False)
    error_message = Column(Text, nullable=False)
    input_type = Column(String(10), default='text')
    input_size = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
