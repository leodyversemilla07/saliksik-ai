"""
Shared utilities used across the application.
"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return current UTC time. Use as default for SQLAlchemy DateTime columns."""
    return datetime.now(timezone.utc)
