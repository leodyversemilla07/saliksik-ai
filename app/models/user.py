from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from app.core.database import Base
from app.core.utils import utc_now


class User(Base):
    """User model for authentication."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    api_key: Mapped[str | None] = mapped_column(String, unique=True, index=True, nullable=True)
    role: Mapped[str] = mapped_column(String, default="user", index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verification_token: Mapped[str | None] = mapped_column(String, unique=True, index=True, nullable=True)
    verification_token_expires_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=utc_now)
    last_login: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    analyses: Mapped[list["ManuscriptAnalysis"]] = relationship("ManuscriptAnalysis", back_populates="user")
    reviewer_profile: Mapped[Optional["Reviewer"]] = relationship(
        "Reviewer", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
