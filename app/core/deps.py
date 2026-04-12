"""
Authentication dependencies and utilities.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Annotated
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

# Schemes
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)

# DbSession can be defined immediately since get_db is already imported
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_user_by_api_key(
    api_key: Annotated[Optional[str], Depends(api_key_header)], db: DbSession
) -> Optional[User]:
    """
    Get user by API key from header.
    """
    if not api_key:
        return None

    result = await db.execute(select(User).filter(User.api_key == api_key))
    return result.scalar_one_or_none()


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], db: DbSession
) -> User:
    """
    Dependency to get current authenticated user.
    """
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: int = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Async query
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_authenticated_user(
    db: DbSession,
    api_key_user: Annotated[Optional[User], Depends(get_user_by_api_key)],
    token: Annotated[Optional[str], Depends(oauth2_scheme)],
) -> User:
    """
    Unified authentication dependency - supports both JWT and API Key.
    """
    # 1. Try API Key first (common for external API access)
    if api_key_user:
        return api_key_user

    # 2. Try JWT
    if token:
        try:
            return await get_current_user(token, db)
        except HTTPException:
            pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated. Provide a valid JWT token in Authorization header or X-API-KEY header.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user_optional(
    token: Annotated[Optional[str], Depends(oauth2_scheme)], db: DbSession
) -> Optional[User]:
    """
    Optional authentication - returns user if authenticated, None otherwise.
    """
    if token is None:
        return None

    try:
        return await get_current_user(token, db)
    except HTTPException:
        return None


# Type aliases defined AFTER function definitions to avoid forward-reference errors
CurrentUser = Annotated[User, Depends(get_current_user)]
AuthenticatedUser = Annotated[User, Depends(get_authenticated_user)]
OptionalUser = Annotated[Optional[User], Depends(get_current_user_optional)]


async def get_admin_user(current_user: AuthenticatedUser) -> User:
    """
    Dependency that requires the current user to have admin role.
    Raises 403 Forbidden if the user is not an admin.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return current_user


AdminUser = Annotated[User, Depends(get_admin_user)]
