"""
Cache utilities using Redis or in-memory fallback.
"""

import hashlib
import logging
import time
import functools
from typing import Optional, Dict, Any, Callable, TypeVar
from datetime import datetime, timezone
import json
from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Try to import Redis
try:
    import redis

    if settings.REDIS_URL:
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        # Test connection
        try:
            redis_client.ping()
            REDIS_AVAILABLE = True
        except redis.ConnectionError:
            REDIS_AVAILABLE = False
            redis_client = None
            logger.warning("Redis connection failed, using in-memory cache")
    else:
        REDIS_AVAILABLE = False
        redis_client = None
except ImportError:
    REDIS_AVAILABLE = False
    redis_client = None
    logger.warning("Redis not available, using in-memory cache")

# Fallback in-memory cache with expiration tracking
_memory_cache: Dict[
    str, Dict[str, Any]
] = {}  # {key: {"value": ..., "expires_at": ...}}
_MEMORY_CACHE_MAX_SIZE = 10_000  # Cap to prevent unbounded growth


class AIResultCache:
    """Cache manager for AI processing results."""

    KEY_PREFIX = "ai_analysis"
    DEFAULT_TTL = settings.CACHE_TTL

    @staticmethod
    def _generate_cache_key(text: str) -> str:
        """Generate unique cache key from text."""
        normalized = text.strip().lower()
        text_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return f"{AIResultCache.KEY_PREFIX}:{text_hash}"

    @staticmethod
    def get_cached_result(text: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached result."""
        cache_key = AIResultCache._generate_cache_key(text)

        try:
            if REDIS_AVAILABLE and redis_client:
                result = redis_client.get(cache_key)
                if result:
                    logger.info(f"Cache HIT (Redis): {cache_key[:20]}...")
                    return json.loads(result)
            else:
                cached = _memory_cache.get(cache_key)
                if cached:
                    # Check expiration
                    if cached.get("expires_at", 0) > time.time():
                        logger.info(f"Cache HIT (Memory): {cache_key[:20]}...")
                        return cached["value"]
                    else:
                        # Expired, remove from cache
                        del _memory_cache[cache_key]

            logger.info(f"Cache MISS: {cache_key[:20]}...")
            return None
        except Exception as e:
            logger.error(f"Cache retrieval error: {str(e)}")
            return None

    @staticmethod
    def cache_result(
        text: str, result: Dict[str, Any], ttl: Optional[int] = None
    ) -> bool:
        """Cache analysis result."""
        cache_key = AIResultCache._generate_cache_key(text)
        ttl = ttl or AIResultCache.DEFAULT_TTL

        try:
            if REDIS_AVAILABLE and redis_client:
                redis_client.setex(cache_key, ttl, json.dumps(result))
                logger.info(f"Cached to Redis: {cache_key[:20]}... (TTL: {ttl}s)")
            else:
                # Auto-cleanup if cache is growing too large
                if len(_memory_cache) >= _MEMORY_CACHE_MAX_SIZE:
                    cleanup_expired_cache()
                    # If still too large after cleanup, evict oldest entries
                    if len(_memory_cache) >= _MEMORY_CACHE_MAX_SIZE:
                        sorted_keys = sorted(
                            _memory_cache.keys(),
                            key=lambda k: _memory_cache[k].get("expires_at", 0),
                        )
                        for k in sorted_keys[: len(sorted_keys) // 4]:  # Evict 25%
                            del _memory_cache[k]
                _memory_cache[cache_key] = {
                    "value": result,
                    "expires_at": time.time() + ttl,
                }
                logger.info(f"Cached to Memory: {cache_key[:20]}... (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Cache storage error: {str(e)}")
            return False

    @staticmethod
    def clear_all_cache() -> bool:
        """Clear all cache entries."""
        try:
            if REDIS_AVAILABLE and redis_client:
                pattern = f"{AIResultCache.KEY_PREFIX}:*"
                keys = redis_client.keys(pattern)
                if keys:
                    redis_client.delete(*keys)
                logger.info(f"Cleared {len(keys)} Redis cache entries")
            else:
                _memory_cache.clear()
                logger.info("Cleared in-memory cache")
            return True
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return False

    @staticmethod
    def get_cache_stats() -> Dict[str, Any]:
        """Get cache statistics."""
        stats = {
            "backend": "redis" if REDIS_AVAILABLE else "memory",
            "enabled": True,
        }

        try:
            if REDIS_AVAILABLE and redis_client:
                info = redis_client.info("stats")
                stats.update(
                    {
                        "keyspace_hits": info.get("keyspace_hits", 0),
                        "keyspace_misses": info.get("keyspace_misses", 0),
                    }
                )
                hits = stats.get("keyspace_hits", 0)
                misses = stats.get("keyspace_misses", 0)
                total = hits + misses
                if total > 0:
                    stats["hit_rate"] = round((hits / total) * 100, 2)
            else:
                # Count non-expired entries
                now = time.time()
                valid_entries = sum(
                    1 for v in _memory_cache.values() if v.get("expires_at", 0) > now
                )
                stats["entries"] = valid_entries
                stats["total_entries"] = len(_memory_cache)
        except Exception as e:
            logger.debug(f"Could not retrieve cache stats: {str(e)}")

        return stats


def cached_response(ttl: int = 300, key_prefix: str = "response"):
    """
    Decorator for caching endpoint responses.

    Args:
        ttl: Time-to-live in seconds (default 5 minutes)
        key_prefix: Prefix for cache keys

    Usage:
        @router.get("/items")
        @cached_response(ttl=60)
        async def get_items():
            return {"items": [...]}
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            key_parts = [key_prefix, func.__name__]

            # Add relevant kwargs to key (skip db sessions and user objects)
            for k, v in sorted(kwargs.items()):
                if k not in ("db", "current_user", "request") and v is not None:
                    if isinstance(v, (str, int, float, bool)):
                        key_parts.append(f"{k}={v}")

            cache_key = ":".join(key_parts)
            key_hash = hashlib.md5(cache_key.encode()).hexdigest()
            full_key = f"{key_prefix}:{key_hash}"

            # Try to get from cache
            try:
                if REDIS_AVAILABLE and redis_client:
                    cached = redis_client.get(full_key)
                    if cached:
                        logger.debug(f"Response cache HIT: {func.__name__}")
                        return json.loads(cached)
                else:
                    cached = _memory_cache.get(full_key)
                    if cached and cached.get("expires_at", 0) > time.time():
                        logger.debug(f"Response cache HIT: {func.__name__}")
                        return cached["value"]
            except Exception as e:
                logger.debug(f"Cache read error: {e}")

            # Execute function
            result = await func(*args, **kwargs)

            # Cache the result
            try:
                # Convert Pydantic models to dict if needed
                cache_value = result
                if hasattr(result, "model_dump"):
                    cache_value = result.model_dump()
                elif hasattr(result, "dict"):
                    cache_value = result.dict()

                if REDIS_AVAILABLE and redis_client:
                    redis_client.setex(
                        full_key, ttl, json.dumps(cache_value, default=str)
                    )
                else:
                    _memory_cache[full_key] = {
                        "value": cache_value,
                        "expires_at": time.time() + ttl,
                    }
                logger.debug(f"Response cached: {func.__name__} (TTL: {ttl}s)")
            except Exception as e:
                logger.debug(f"Cache write error: {e}")

            return result

        return wrapper

    return decorator


def invalidate_cache(pattern: str = "*") -> int:
    """
    Invalidate cache entries matching a pattern.

    Args:
        pattern: Glob pattern for keys to invalidate

    Returns:
        Number of keys invalidated
    """
    count = 0
    try:
        if REDIS_AVAILABLE and redis_client:
            keys = redis_client.keys(pattern)
            if keys:
                count = redis_client.delete(*keys)
        else:
            # For in-memory, we need to match keys manually
            import fnmatch

            keys_to_delete = [
                k for k in _memory_cache.keys() if fnmatch.fnmatch(k, pattern)
            ]
            for key in keys_to_delete:
                del _memory_cache[key]
                count += 1
        logger.info(f"Invalidated {count} cache entries matching '{pattern}'")
    except Exception as e:
        logger.error(f"Cache invalidation error: {e}")
    return count


def cleanup_expired_cache() -> int:
    """
    Remove expired entries from in-memory cache.
    Should be called periodically in production.

    Returns:
        Number of entries removed
    """
    if REDIS_AVAILABLE:
        return 0  # Redis handles expiration automatically

    now = time.time()
    expired_keys = [
        k for k, v in _memory_cache.items() if v.get("expires_at", 0) <= now
    ]

    for key in expired_keys:
        del _memory_cache[key]

    if expired_keys:
        logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")

    return len(expired_keys)
