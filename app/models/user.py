"""
User model for authentication.
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.core.database import Base


def utc_now():
    """Return current UTC time."""
    return datetime.now(timezone.utc)


class User(Base):
    """User model for authentication."""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    api_key = Column(String, unique=True, index=True, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    analyses = relationship("ManuscriptAnalysis", back_populates="user")
    reviewer_profile = relationship(
        "Reviewer", 
        back_populates="user", 
        uselist=False,
        cascade="all, delete-orphan"
    )
