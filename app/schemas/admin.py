"""
Pydantic schemas for the admin API.
"""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

UserRole = Literal["user", "editor", "admin"]


class AdminUserResponse(BaseModel):
    """User representation for administrators."""

    id: int
    username: str
    email: str
    role: str
    institution: Optional[str] = None
    is_active: bool
    is_email_verified: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AdminUserListResponse(BaseModel):
    """Paginated list of users."""

    results: List[AdminUserResponse]
    total_count: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool


class AdminUserUpdate(BaseModel):
    """Administrative changes to a user account."""

    role: Optional[UserRole] = Field(None, description="New role of the account")
    is_active: Optional[bool] = Field(None, description="Activate or deactivate the account")
    is_email_verified: Optional[bool] = Field(None, description="Mark the email address as verified")


class AdminStatsResponse(BaseModel):
    """Aggregated system statistics for the admin dashboard."""

    total_users: int
    active_users: int
    verified_users: int
    total_analyses: int
    completed_analyses: int
    failed_analyses: int
    total_reviewers: int
    available_reviewers: int
    total_assignments: int
    indexed_documents: int
