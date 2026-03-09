import bcrypt
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from jose import JWTError, jwt
from app.core.config import settings

# Token types
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"

# Refresh token settings
REFRESH_TOKEN_EXPIRE_DAYS = 30
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

# Redis key prefix for token blacklist entries
_BLACKLIST_PREFIX = "blacklist:token:"

# In-memory fallback blacklist (used when Redis is unavailable)
_token_blacklist: set = set()


def _get_redis():
    """Lazily import Redis client to avoid circular imports at module load."""
    try:
        from app.core.cache import redis_client, REDIS_AVAILABLE
        return redis_client, REDIS_AVAILABLE
    except Exception:
        return None, False


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'), 
        hashed_password.encode('utf-8') if isinstance(hashed_password, str) else hashed_password
    )


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "type": TOKEN_TYPE_ACCESS,
        "iat": datetime.now(timezone.utc)
    })
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token with longer expiration."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    # Add a unique token ID for blacklisting
    token_id = secrets.token_hex(16)
    
    to_encode.update({
        "exp": expire,
        "type": TOKEN_TYPE_REFRESH,
        "iat": datetime.now(timezone.utc),
        "jti": token_id  # JWT ID for blacklisting
    })
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_token_pair(user_id: int) -> Tuple[str, str]:
    """Create both access and refresh tokens."""
    data = {"sub": str(user_id)}
    access_token = create_access_token(data)
    refresh_token = create_refresh_token(data)
    return access_token, refresh_token


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and verify JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        # Check if token is blacklisted
        jti = payload.get("jti")
        if jti and is_token_blacklisted(jti):
            return None
        
        return payload
    except JWTError:
        return None


def decode_refresh_token(token: str) -> Optional[dict]:
    """Decode and verify refresh token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        # Verify it's a refresh token
        if payload.get("type") != TOKEN_TYPE_REFRESH:
            return None
        
        # Check if token is blacklisted
        jti = payload.get("jti")
        if jti and is_token_blacklisted(jti):
            return None
        
        return payload
    except JWTError:
        return None


def blacklist_token(token: str) -> bool:
    """Add a token to the blacklist (Redis-backed with in-memory fallback)."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": False}  # Allow expired tokens to be blacklisted
        )
        jti = payload.get("jti")
        identifier = jti if jti else hashlib.sha256(token.encode()).hexdigest()

        # TTL = remaining lifetime of the token + 60s buffer so the key self-cleans
        exp = payload.get("exp")
        if exp:
            remaining = int(exp - datetime.now(timezone.utc).timestamp())
            ttl = max(remaining, 0) + 60
        else:
            ttl = int(timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS).total_seconds())

        redis_client, redis_available = _get_redis()
        if redis_available and redis_client:
            redis_client.setex(f"{_BLACKLIST_PREFIX}{identifier}", ttl, "1")
        else:
            _token_blacklist.add(identifier)

        return True
    except JWTError:
        return False


def is_token_blacklisted(jti: str) -> bool:
    """Check if a token ID is blacklisted."""
    redis_client, redis_available = _get_redis()
    if redis_available and redis_client:
        return redis_client.exists(f"{_BLACKLIST_PREFIX}{jti}") > 0
    return jti in _token_blacklist


def generate_api_key() -> str:
    """Generate a secure API key."""
    return f"sk_{secrets.token_urlsafe(32)}"


def rotate_api_key() -> str:
    """Generate a new API key for rotation."""
    return generate_api_key()
