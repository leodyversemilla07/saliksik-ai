"""
Input validation and security utilities.
"""

import html
import re
from typing import List, Optional, Tuple

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Maximum request body sizes (in bytes)
MAX_JSON_SIZE = 1 * 1024 * 1024  # 1MB for JSON
MAX_FILE_SIZE = settings.MAX_FILE_SIZE_MB * 1024 * 1024  # From config
MAX_TEXT_LENGTH = 100_000  # 100K characters for manuscript text

# Patterns for dangerous content
SCRIPT_PATTERN = re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
EVENT_HANDLER_PATTERN = re.compile(r"\bon\w+\s*=", re.IGNORECASE)
SQL_INJECTION_PATTERNS = [
    re.compile(
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE)\b)", re.IGNORECASE
    ),
    re.compile(r"(--|#|/\*|\*/)", re.IGNORECASE),
    re.compile(r"(\bOR\b|\bAND\b)\s+\d+\s*=\s*\d+", re.IGNORECASE),
]


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to limit request body size to prevent DoS attacks.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        content_length = request.headers.get("content-length")
        content_type = request.headers.get("content-type", "")

        if content_length:
            size = int(content_length)

            # Check file upload size
            if "multipart/form-data" in content_type:
                if size > MAX_FILE_SIZE:
                    logger.warning(f"Request too large: {size} bytes (file upload)")
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File too large. Maximum size is {settings.MAX_FILE_SIZE_MB}MB",
                    )
            # Check JSON body size
            elif "application/json" in content_type:
                if size > MAX_JSON_SIZE:
                    logger.warning(f"Request too large: {size} bytes (JSON)")
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Request body too large. Maximum size is 1MB",
                    )

        return await call_next(request)


def sanitize_string(value: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize a string input by removing potentially dangerous content.

    Args:
        value: The string to sanitize
        max_length: Optional maximum length to truncate to

    Returns:
        Sanitized string
    """
    if not value:
        return value

    # Trim whitespace
    value = value.strip()

    # Remove null bytes
    value = value.replace("\x00", "")

    # Escape HTML entities to prevent XSS
    value = html.escape(value)

    # Truncate if needed
    if max_length and len(value) > max_length:
        value = value[:max_length]

    return value


def sanitize_html(value: str) -> str:
    """
    Remove HTML/script tags from input while preserving text content.
    For cases where we want to strip HTML rather than escape it.
    """
    if not value:
        return value

    # Remove script tags
    value = SCRIPT_PATTERN.sub("", value)

    # Remove event handlers
    value = EVENT_HANDLER_PATTERN.sub("", value)

    # Remove all HTML tags but keep content
    value = re.sub(r"<[^>]+>", "", value)

    return value.strip()


def sanitize_manuscript_text(text: str) -> str:
    """
    Sanitize manuscript text while preserving legitimate content.
    Less aggressive than general sanitization.
    """
    if not text:
        return text

    # Remove null bytes
    text = text.replace("\x00", "")

    # Remove script tags (keep other HTML for now as manuscripts might have formatting)
    text = SCRIPT_PATTERN.sub("", text)

    # Remove event handlers
    text = EVENT_HANDLER_PATTERN.sub("", text)

    # Limit length
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH]
        logger.warning(f"Manuscript text truncated to {MAX_TEXT_LENGTH} characters")

    return text.strip()


def sanitize_keywords(keywords: List[str], max_count: int = 50) -> List[str]:
    """
    Sanitize a list of keywords.

    Args:
        keywords: List of keyword strings
        max_count: Maximum number of keywords allowed

    Returns:
        Sanitized list of keywords
    """
    if not keywords:
        return []

    sanitized = []
    for kw in keywords[:max_count]:
        # Sanitize each keyword
        clean_kw = sanitize_string(kw, max_length=100)
        # Only keep non-empty keywords
        if clean_kw and len(clean_kw) >= 2:
            sanitized.append(clean_kw.lower())

    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for kw in sanitized:
        if kw not in seen:
            seen.add(kw)
            unique.append(kw)

    return unique


def validate_email(email: str) -> Tuple[bool, str]:
    """
    Validate email format.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not email:
        return False, "Email is required"

    email = email.strip().lower()

    if len(email) > 254:
        return False, "Email too long"

    # Basic email pattern
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        return False, "Invalid email format"

    return True, ""


def validate_username(username: str) -> Tuple[bool, str]:
    """
    Validate username format.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not username:
        return False, "Username is required"

    username = username.strip()

    if len(username) < 3:
        return False, "Username must be at least 3 characters"

    if len(username) > 50:
        return False, "Username must be at most 50 characters"

    # Only allow alphanumeric and underscores
    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        return False, "Username can only contain letters, numbers, and underscores"

    return True, ""


def validate_password(password: str) -> Tuple[bool, str]:
    """
    Validate password strength.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not password:
        return False, "Password is required"

    if len(password) < 8:
        return False, "Password must be at least 8 characters"

    if len(password) > 128:
        return False, "Password too long"

    # Check for at least one letter and one number
    if not re.search(r"[a-zA-Z]", password):
        return False, "Password must contain at least one letter"

    if not re.search(r"\d", password):
        return False, "Password must contain at least one number"

    return True, ""


def check_sql_injection(value: str) -> bool:
    """
    Check if a string contains potential SQL injection patterns.

    Returns:
        True if suspicious patterns found
    """
    if not value:
        return False

    for pattern in SQL_INJECTION_PATTERNS:
        if pattern.search(value):
            logger.warning(f"Potential SQL injection detected: {value[:100]}...")
            return True

    return False


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal attacks.
    """
    if not filename:
        return "unnamed"

    # Remove path components
    filename = filename.replace("\\", "/").split("/")[-1]

    # Remove dangerous characters
    filename = re.sub(r'[<>:"|?*\x00-\x1f]', "", filename)

    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
        max_name_len = 255 - len(ext) - 1 if ext else 255
        filename = f"{name[:max_name_len]}.{ext}" if ext else name[:255]

    return filename or "unnamed"


def rate_limit_key(request: Request, prefix: str = "rl") -> str:
    """
    Generate a rate limit key for the request.
    Uses user ID if authenticated, otherwise IP address.
    """
    # Try to get user from request state (set by auth middleware)
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"{prefix}:user:{user_id}"

    # Fall back to IP address
    client_ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()

    return f"{prefix}:ip:{client_ip}"
