"""
Rate limiting middleware using in-memory or Redis backend.
"""
import time
import logging
from typing import Optional, Tuple
from collections import defaultdict
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings

logger = logging.getLogger(__name__)

# Try to import Redis
try:
    import redis
    if settings.REDIS_URL:
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        REDIS_AVAILABLE = True
    else:
        REDIS_AVAILABLE = False
        redis_client = None
except ImportError:
    REDIS_AVAILABLE = False
    redis_client = None


class InMemoryRateLimiter:
    """Simple in-memory rate limiter using sliding window."""
    
    def __init__(self):
        self._requests: dict = defaultdict(list)
    
    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int]:
        """
        Check if request is allowed under rate limit.
        
        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        now = time.time()
        window_start = now - window_seconds
        
        # Clean old requests
        self._requests[key] = [
            req_time for req_time in self._requests[key]
            if req_time > window_start
        ]
        
        current_count = len(self._requests[key])
        
        if current_count >= max_requests:
            return False, 0
        
        self._requests[key].append(now)
        return True, max_requests - current_count - 1


class RedisRateLimiter:
    """Redis-based rate limiter using sliding window."""
    
    def __init__(self, client):
        self.client = client
    
    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int]:
        """
        Check if request is allowed under rate limit.
        
        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        now = time.time()
        window_start = now - window_seconds
        
        pipe = self.client.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(key, 0, window_start)
        # Count current entries
        pipe.zcard(key)
        # Add current request
        pipe.zadd(key, {str(now): now})
        # Set expiry on the key
        pipe.expire(key, window_seconds)
        
        results = pipe.execute()
        current_count = results[1]
        
        if current_count >= max_requests:
            return False, 0
        
        return True, max_requests - current_count - 1


def parse_rate_limit(rate_limit_str: str) -> Tuple[int, int]:
    """
    Parse rate limit string like '60/hour' or '100/minute'.
    
    Returns:
        Tuple of (max_requests, window_seconds)
    """
    try:
        count, period = rate_limit_str.split('/')
        count = int(count)
        
        period_seconds = {
            'second': 1,
            'minute': 60,
            'hour': 3600,
            'day': 86400
        }
        
        seconds = period_seconds.get(period.lower(), 3600)
        return count, seconds
    except Exception:
        # Default: 60 requests per hour
        return 60, 3600


# Create global rate limiter instance
if REDIS_AVAILABLE and redis_client:
    rate_limiter = RedisRateLimiter(redis_client)
    logger.info("Using Redis-based rate limiter")
else:
    rate_limiter = InMemoryRateLimiter()
    logger.info("Using in-memory rate limiter")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware for FastAPI.
    
    Applies different rate limits for authenticated vs anonymous users.
    """
    
    # Paths to exclude from rate limiting
    EXCLUDED_PATHS = {'/health', '/docs', '/redoc', '/api/openapi.json', '/'}
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for excluded paths
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)
        
        # Determine client identifier
        client_id = self._get_client_id(request)
        
        # Check if user is authenticated
        is_authenticated = self._is_authenticated(request)
        
        # Get appropriate rate limit
        if is_authenticated:
            max_requests, window_seconds = parse_rate_limit(settings.RATE_LIMIT_USER)
            key_prefix = "rate:user"
        else:
            max_requests, window_seconds = parse_rate_limit(settings.RATE_LIMIT_ANON)
            key_prefix = "rate:anon"
        
        rate_key = f"{key_prefix}:{client_id}"
        
        # Check rate limit
        is_allowed, remaining = rate_limiter.is_allowed(rate_key, max_requests, window_seconds)
        
        if not is_allowed:
            logger.warning(f"Rate limit exceeded for {client_id}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
                headers={
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(window_seconds),
                    "Retry-After": str(window_seconds)
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(window_seconds)
        
        return response
    
    def _get_client_id(self, request: Request) -> str:
        """Get unique client identifier from request."""
        # Try to get user ID from auth header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            # Use token hash as identifier for authenticated users
            import hashlib
            token = auth_header[7:]
            return hashlib.sha256(token.encode()).hexdigest()[:16]
        
        # Try API key
        api_key = request.headers.get("X-API-KEY", "")
        if api_key:
            import hashlib
            return hashlib.sha256(api_key.encode()).hexdigest()[:16]
        
        # Fall back to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        return request.client.host if request.client else "unknown"
    
    def _is_authenticated(self, request: Request) -> bool:
        """Check if request appears to be authenticated."""
        auth_header = request.headers.get("Authorization", "")
        api_key = request.headers.get("X-API-KEY", "")
        return bool(auth_header.startswith("Bearer ") or api_key)
