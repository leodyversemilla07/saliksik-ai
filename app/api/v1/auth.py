"""
Authentication endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from datetime import datetime, timezone
from typing import Optional
from app.core.database import get_db
from app.core.security import (
    verify_password, get_password_hash, create_access_token,
    create_token_pair, decode_refresh_token, blacklist_token,
    generate_api_key, ACCESS_TOKEN_EXPIRE_MINUTES
)
from app.models.user import User
from app.schemas.user import (
    UserRegister, UserLogin, TokenResponse, UserResponse,
    RefreshTokenRequest, RefreshTokenResponse,
    ApiKeyResponse, ApiKeyRotateResponse,
    LogoutRequest, PasswordChangeRequest
)
from app.core.deps import get_current_user
from app.core.security_utils import validate_email, validate_username, validate_password, sanitize_string
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api-key", response_model=ApiKeyResponse)
async def get_or_create_api_key(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate or get current API Key.
    """
    if not current_user.api_key:
        current_user.api_key = generate_api_key()
        await db.commit()
        logger.info(f"API Key generated for user: {current_user.username}")
    
    return ApiKeyResponse(
        api_key=current_user.api_key,
        created_at=current_user.created_at
    )


@router.post("/api-key/rotate", response_model=ApiKeyRotateResponse)
async def rotate_api_key(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Rotate (revoke and regenerate) API Key.
    The previous key is immediately invalidated.
    """
    old_key_existed = current_user.api_key is not None
    current_user.api_key = generate_api_key()
    await db.commit()
    
    logger.info(f"API Key rotated for user: {current_user.username}")
    
    return ApiKeyRotateResponse(
        api_key=current_user.api_key,
        previous_key_revoked=old_key_existed
    )


@router.delete("/api-key")
async def revoke_api_key(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Revoke (delete) API Key without generating a new one.
    """
    if not current_user.api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No API key to revoke"
        )
    
    current_user.api_key = None
    await db.commit()
    
    logger.info(f"API Key revoked for user: {current_user.username}")
    
    return {"message": "API key revoked successfully"}


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    responses={
        400: {"description": "Invalid input or user already exists"},
        422: {"description": "Validation error"}
    }
)
async def register(user_data: UserRegister, db: AsyncSession = Depends(get_db)):
    """
    Register a new user account.
    
    - **username**: Unique username (3-50 characters, alphanumeric and underscores)
    - **email**: Valid email address
    - **password**: Strong password (min 8 characters, must include letter and number)
    
    Returns access and refresh tokens on successful registration.
    """
    
    # Validate and sanitize inputs
    is_valid, error = validate_username(user_data.username)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    
    is_valid, error = validate_email(user_data.email)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    
    is_valid, error = validate_password(user_data.password)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    
    # Sanitize username
    clean_username = sanitize_string(user_data.username, max_length=50)
    clean_email = user_data.email.strip().lower()
    
    # Check if user exists
    stmt = select(User).filter(
        or_(User.username == clean_username, User.email == clean_email)
    )
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        username=clean_username,
        email=clean_email,
        hashed_password=hashed_password
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    # Create access and refresh tokens
    access_token, refresh_token = create_token_pair(new_user.id)
    
    logger.info(f"New user registered: {new_user.username}")
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES,
        user=UserResponse.model_validate(new_user)
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login to get access token",
    responses={
        401: {"description": "Invalid credentials"}
    }
)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """
    Authenticate user and return access/refresh tokens.
    
    Uses OAuth2 password flow compatible with Swagger UI.
    
    - **username**: Your registered username
    - **password**: Your password
    
    Returns access token (short-lived) and refresh token (long-lived).
    """
    
    # Find user
    stmt = select(User).filter(User.username == form_data.username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update last login
    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    
    # Create access and refresh tokens
    access_token, refresh_token = create_token_pair(user.id)
    
    logger.info(f"User logged in: {user.username}")
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES,
        user=UserResponse.model_validate(user)
    )


@router.get("/profile", response_model=UserResponse)
async def get_profile(current_user: User = Depends(get_current_user)):
    """Get current user profile."""
    return UserResponse.model_validate(current_user)


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_access_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a new access token using a refresh token.
    The refresh token remains valid until it expires or is blacklisted.
    """
    payload = decode_refresh_token(request.refresh_token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    # Verify user still exists and is active
    stmt = select(User).filter(User.id == int(user_id))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Create new access token
    access_token = create_access_token(data={"sub": str(user.id)})
    
    logger.info(f"Access token refreshed for user: {user.username}")
    
    return RefreshTokenResponse(
        access_token=access_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES
    )


@router.post("/logout")
async def logout(
    request: LogoutRequest = None,
    authorization: Optional[str] = Header(None),
    current_user: User = Depends(get_current_user)
):
    """
    Logout user by blacklisting tokens.
    Optionally blacklist refresh token if provided.
    """
    tokens_blacklisted = 0
    
    # Blacklist access token from header
    if authorization and authorization.startswith("Bearer "):
        access_token = authorization.split(" ")[1]
        if blacklist_token(access_token):
            tokens_blacklisted += 1
    
    # Blacklist refresh token if provided
    if request and request.refresh_token:
        if blacklist_token(request.refresh_token):
            tokens_blacklisted += 1
    
    logger.info(f"User logged out: {current_user.username} ({tokens_blacklisted} tokens blacklisted)")
    
    return {
        "message": "Logged out successfully",
        "tokens_blacklisted": tokens_blacklisted
    }


@router.post("/change-password")
async def change_password(
    request: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Change user password. Requires current password verification.
    """
    # Verify current password
    if not verify_password(request.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Validate new password
    is_valid, error = validate_password(request.new_password)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    
    # Update password
    current_user.hashed_password = get_password_hash(request.new_password)
    await db.commit()
    
    logger.info(f"Password changed for user: {current_user.username}")
    
    return {"message": "Password changed successfully"}
