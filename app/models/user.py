from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.utils import utc_now


class User(Base):
    """User model for authentication."""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    api_key = Column(String, unique=True, index=True, nullable=True)
    role = Column(String, default="user", index=True, nullable=False)
    is_active = Column(Boolean, default=True)
    is_email_verified = Column(Boolean, default=False, nullable=False)
    verification_token = Column(String, unique=True, index=True, nullable=True)
    verification_token_expires_at = Column(DateTime, nullable=True)
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
