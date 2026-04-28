"""
Rate limiting middleware using Redis backend (shared with cache) or in-memory fallback.
"""

import logging
import time
from collections import defaultdict
from typing import Tuple

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

logger = logging.getLogger(__name__)

# Reuse the Redis client already established by cache.py to avoid duplicate connections
try:
    from app.core.cache import REDIS_AVAILABLE, redis_client

    if REDIS_AVAILABLE and redis_client:
        logger.info("Rate limiter using shared Redis connection")
    else:
        logger.info("Rate limiter using in-memory fallback (Redis unavailable)")
except Exception as e:
    redis_client = None
    REDIS_AVAILABLE = False
    logger.warning(
        f"Rate limiter could not import Redis client: {e}. Using in-memory fallback."
    )


class InMemoryRateLimiter:
    """Simple in-memory rate limiter using sliding window."""

    _MAX_KEYS = 50_000  # Cap to prevent unbounded growth

    def __init__(self):
        self._requests: dict = defaultdict(list)
        self._cleanup_counter = 0

    def reset(self):
        """Clear all rate limit counters (useful for testing)."""
        self._requests.clear()

    def _periodic_cleanup(self):
        """Remove empty keys every 100 requests to prevent memory leak."""
        self._cleanup_counter += 1
        if self._cleanup_counter >= 100:
            self._cleanup_counter = 0
            empty_keys = [k for k, v in self._requests.items() if not v]
            for k in empty_keys:
                del self._requests[k]
            # If still too many keys, evict oldest
            if len(self._requests) > self._MAX_KEYS:
                sorted_keys = sorted(
                    self._requests.keys(),
                    key=lambda k: self._requests[k][0] if self._requests[k] else 0,
                )
                for k in sorted_keys[: len(sorted_keys) // 4]:
                    del self._requests[k]

    def is_allowed(
        self, key: str, max_requests: int, window_seconds: int
    ) -> Tuple[bool, int]:
        """
        Check if request is allowed under rate limit.

        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        self._periodic_cleanup()

        now = time.time()
        window_start = now - window_seconds

        # Clean old requests
        self._requests[key] = [
            req_time for req_time in self._requests[key] if req_time > window_start
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

    def is_allowed(
        self, key: str, max_requests: int, window_seconds: int
    ) -> Tuple[bool, int]:
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
        count, period = rate_limit_str.split("/")
        count = int(count)

        period_seconds = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}

        seconds = period_seconds.get(period.lower(), 3600)
        return count, seconds
    except Exception:
        # Default: 60 requests per hour
        return 60, 3600


# Create global rate limiter instance
if REDIS_AVAILABLE and redis_client:
    rate_limiter = RedisRateLimiter(redis_client)
else:
    rate_limiter = InMemoryRateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware for FastAPI.

    Applies different rate limits for authenticated vs anonymous users,
    with tighter limits on sensitive auth endpoints.
    """

    # Paths to exclude from rate limiting
    EXCLUDED_PATHS = {"/health", "/docs", "/redoc", "/api/openapi.json", "/"}

    # Auth endpoints get a much tighter limit to deter brute-force attacks
    AUTH_PATHS = {"/api/v1/auth/login", "/api/v1/auth/register"}
    AUTH_MAX_REQUESTS = 10
    AUTH_WINDOW_SECONDS = 600  # 10 per 10 minutes

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for excluded paths
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        # Determine client identifier
        client_id = self._get_client_id(request)

        # Tighter limit for auth endpoints (brute-force protection)
        if request.url.path in self.AUTH_PATHS:
            is_allowed, remaining = rate_limiter.is_allowed(
                f"rate:auth:{client_id}",
                self.AUTH_MAX_REQUESTS,
                self.AUTH_WINDOW_SECONDS,
            )
            max_requests = self.AUTH_MAX_REQUESTS
            window_seconds = self.AUTH_WINDOW_SECONDS
        else:
            # General rate limit based on auth status
            is_authenticated = self._is_authenticated(request)
            if is_authenticated:
                max_requests, window_seconds = parse_rate_limit(
                    settings.RATE_LIMIT_USER
                )
                key_prefix = "rate:user"
            else:
                max_requests, window_seconds = parse_rate_limit(
                    settings.RATE_LIMIT_ANON
                )
                key_prefix = "rate:anon"

            rate_key = f"{key_prefix}:{client_id}"
            is_allowed, remaining = rate_limiter.is_allowed(
                rate_key, max_requests, window_seconds
            )

        if not is_allowed:
            logger.warning(f"Rate limit exceeded for {client_id}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
                headers={
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(window_seconds),
                    "Retry-After": str(window_seconds),
                },
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


def reset_rate_limiter() -> None:
    """Reset all in-memory rate limit counters. Intended for use in tests only."""
    if isinstance(rate_limiter, InMemoryRateLimiter):
        rate_limiter.reset()
