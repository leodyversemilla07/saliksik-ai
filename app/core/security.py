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

# Redis key prefixes for token blacklist entries
_BLACKLIST_PREFIX = "blacklist:token:"
_LOCKOUT_ATTEMPTS_PREFIX = "lockout:attempts:"
_LOCKOUT_UNTIL_PREFIX = "lockout:until:"

# In-memory fallback blacklist (used when Redis is unavailable)
_token_blacklist: set = set()

# In-memory fallback for login attempt tracking
_failed_attempts: dict = {}
_locked_until: dict = {}


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


def is_account_locked(username: str) -> tuple:
    """
    Check if an account is locked due to too many failed login attempts.
    Returns (is_locked: bool, seconds_remaining: int).
    """
    redis_client, redis_available = _get_redis()
    if redis_available and redis_client:
        raw = redis_client.get(f"{_LOCKOUT_UNTIL_PREFIX}{username}")
        if raw:
            locked_until = datetime.fromtimestamp(float(raw), tz=timezone.utc)
            remaining = (locked_until - datetime.now(timezone.utc)).total_seconds()
            if remaining > 0:
                return True, int(remaining)
            redis_client.delete(f"{_LOCKOUT_UNTIL_PREFIX}{username}")
            redis_client.delete(f"{_LOCKOUT_ATTEMPTS_PREFIX}{username}")
    else:
        locked_until = _locked_until.get(username)
        if locked_until:
            remaining = (locked_until - datetime.now(timezone.utc)).total_seconds()
            if remaining > 0:
                return True, int(remaining)
            _locked_until.pop(username, None)
            _failed_attempts.pop(username, None)
    return False, 0


def record_failed_login(username: str) -> int:
    """
    Record a failed login attempt for a username.
    Locks the account if MAX_LOGIN_ATTEMPTS is reached.
    Returns the current attempt count.
    """
    redis_client, redis_available = _get_redis()
    window_seconds = settings.LOCKOUT_MINUTES * 60

    if redis_available and redis_client:
        key = f"{_LOCKOUT_ATTEMPTS_PREFIX}{username}"
        count = redis_client.incr(key)
        redis_client.expire(key, window_seconds)
        if count >= settings.MAX_LOGIN_ATTEMPTS:
            locked_until = datetime.now(timezone.utc) + timedelta(minutes=settings.LOCKOUT_MINUTES)
            redis_client.setex(
                f"{_LOCKOUT_UNTIL_PREFIX}{username}",
                window_seconds,
                str(locked_until.timestamp()),
            )
        return count
    else:
        _failed_attempts[username] = _failed_attempts.get(username, 0) + 1
        count = _failed_attempts[username]
        if count >= settings.MAX_LOGIN_ATTEMPTS:
            _locked_until[username] = datetime.now(timezone.utc) + timedelta(minutes=settings.LOCKOUT_MINUTES)
        return count


def clear_failed_logins(username: str) -> None:
    """Clear failed login counters after a successful login."""
    redis_client, redis_available = _get_redis()
    if redis_available and redis_client:
        redis_client.delete(f"{_LOCKOUT_ATTEMPTS_PREFIX}{username}")
        redis_client.delete(f"{_LOCKOUT_UNTIL_PREFIX}{username}")
    else:
        _failed_attempts.pop(username, None)
        _locked_until.pop(username, None)


def reset_login_attempts() -> None:
    """Clear all in-memory login attempt state (for tests only)."""
    _failed_attempts.clear()
    _locked_until.clear()
    # Also purge Redis lockout keys when Redis is available
    redis_client, redis_available = _get_redis()
    if redis_available and redis_client:
        keys = (
            redis_client.keys(f"{_LOCKOUT_ATTEMPTS_PREFIX}*") +
            redis_client.keys(f"{_LOCKOUT_UNTIL_PREFIX}*")
        )
        if keys:
            redis_client.delete(*keys)


def generate_api_key() -> str:
    """Generate a secure API key."""
    return f"sk_{secrets.token_urlsafe(32)}"


def rotate_api_key() -> str:
    """Generate a new API key for rotation."""
    return generate_api_key()
