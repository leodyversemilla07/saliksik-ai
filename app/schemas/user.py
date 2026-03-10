"""
User schemas for authentication.
"""
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from datetime import datetime


class UserRegister(BaseModel):
    """User registration schema."""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    """User login schema."""
    username: str
    password: str


class UserResponse(BaseModel):
    """User response schema."""
    id: int
    username: str
    email: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """Token response schema with access and refresh tokens."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int = Field(default=10080, description="Access token expiration in minutes")
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    """Request to refresh access token."""
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    """Response with new access and refresh tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(default=60, description="Access token expiration in minutes")


class ApiKeyResponse(BaseModel):
    """API key response schema."""
    api_key: str
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    message: str = "API key generated successfully"


class ApiKeyRotateResponse(BaseModel):
    """API key rotation response."""
    api_key: str
    previous_key_revoked: bool = True
    message: str = "API key rotated successfully"


class LogoutRequest(BaseModel):
    """Logout request with optional refresh token."""
    refresh_token: Optional[str] = None


class PasswordChangeRequest(BaseModel):
    """Password change request."""
    current_password: str
    new_password: str = Field(..., min_length=8)
