"""
Administrative endpoints.

All endpoints require the `admin` role. They let an administrator inspect the
platform, manage user accounts and change their roles without touching the
database directly.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select

from app.api.responses import COMMON_RESPONSES
from app.core.deps import AdminUser, DbSession
from app.models.analysis import ManuscriptAnalysis
from app.models.document_fingerprint import DocumentFingerprint
from app.models.reviewer import Reviewer, ReviewerMatch
from app.models.user import User
from app.schemas.admin import (
    AdminStatsResponse,
    AdminUserListResponse,
    AdminUserResponse,
    AdminUserUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/stats", response_model=AdminStatsResponse, responses=COMMON_RESPONSES)
async def admin_stats(db: DbSession, current_user: AdminUser):
    """Aggregated statistics for the admin dashboard."""
    total_users = await db.scalar(select(func.count()).select_from(User))
    active_users = await db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True)))
    verified_users = await db.scalar(select(func.count()).select_from(User).where(User.is_email_verified.is_(True)))

    total_analyses = await db.scalar(select(func.count()).select_from(ManuscriptAnalysis))
    completed_analyses = await db.scalar(
        select(func.count()).select_from(ManuscriptAnalysis).where(ManuscriptAnalysis.status == "COMPLETED")
    )
    failed_analyses = await db.scalar(
        select(func.count()).select_from(ManuscriptAnalysis).where(ManuscriptAnalysis.status == "FAILED")
    )

    total_reviewers = await db.scalar(select(func.count()).select_from(Reviewer))
    available_reviewers = await db.scalar(
        select(func.count()).select_from(Reviewer).where(Reviewer.is_available.is_(True))
    )
    total_assignments = await db.scalar(select(func.count()).select_from(ReviewerMatch))
    indexed_documents = await db.scalar(select(func.count()).select_from(DocumentFingerprint))

    return AdminStatsResponse(
        total_users=total_users or 0,
        active_users=active_users or 0,
        verified_users=verified_users or 0,
        total_analyses=total_analyses or 0,
        completed_analyses=completed_analyses or 0,
        failed_analyses=failed_analyses or 0,
        total_reviewers=total_reviewers or 0,
        available_reviewers=available_reviewers or 0,
        total_assignments=total_assignments or 0,
        indexed_documents=indexed_documents or 0,
    )


@router.get("/users", response_model=AdminUserListResponse, responses=COMMON_RESPONSES)
async def list_users(
    db: DbSession,
    current_user: AdminUser,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of users per page"),
    role: Optional[str] = Query(None, description="Filter by role (user, editor, admin)"),
    is_active: Optional[bool] = Query(None, description="Filter by account status"),
    search: Optional[str] = Query(None, max_length=100, description="Search in username or email"),
):
    """List the platform users with optional filters."""
    conditions = []
    if role:
        conditions.append(User.role == role)
    if is_active is not None:
        conditions.append(User.is_active.is_(is_active))
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(or_(User.username.ilike(pattern), User.email.ilike(pattern)))

    total_count = await db.scalar(select(func.count()).select_from(User).where(*conditions))

    stmt = (
        select(User).where(*conditions).order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    result = await db.execute(stmt)
    users = result.scalars().all()

    return AdminUserListResponse(
        results=[AdminUserResponse.model_validate(user) for user in users],
        total_count=total_count or 0,
        page=page,
        page_size=page_size,
        has_next=page * page_size < (total_count or 0),
        has_previous=page > 1,
    )


@router.get("/users/{user_id}", response_model=AdminUserResponse, responses=COMMON_RESPONSES)
async def get_user(user_id: int, db: DbSession, current_user: AdminUser):
    """Get a single user account."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return AdminUserResponse.model_validate(user)


@router.patch("/users/{user_id}", response_model=AdminUserResponse, responses=COMMON_RESPONSES)
async def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    db: DbSession,
    current_user: AdminUser,
):
    """Update the role or the status of a user account."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Guard against locking the platform out: an admin cannot remove their own
    # admin role or deactivate their own account.
    if user.id == current_user.id:
        if payload.role is not None and payload.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An administrator cannot remove their own admin role",
            )
        if payload.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An administrator cannot deactivate their own account",
            )

    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.is_email_verified is not None:
        user.is_email_verified = payload.is_email_verified

    await db.commit()
    await db.refresh(user)

    logger.info("Admin %s updated user %s", current_user.username, user.username)
    return AdminUserResponse.model_validate(user)
