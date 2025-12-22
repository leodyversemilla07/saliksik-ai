"""
Cache utilities using Redis or in-memory fallback.
"""
import hashlib
import logging
from typing import Optional, Dict, Any
import json
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
    logger.warning("Redis not available, using in-memory cache")

# Fallback in-memory cache
_memory_cache: Dict[str, Any] = {}


class AIResultCache:
    """Cache manager for AI processing results."""
    
    KEY_PREFIX = "ai_analysis"
    DEFAULT_TTL = settings.CACHE_TTL
    
    @staticmethod
    def _generate_cache_key(text: str) -> str:
        """Generate unique cache key from text."""
        normalized = text.strip().lower()
        text_hash = hashlib.sha256(normalized.encode('utf-8')).hexdigest()
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
                result = _memory_cache.get(cache_key)
                if result:
                    logger.info(f"Cache HIT (Memory): {cache_key[:20]}...")
                    return result
            
            logger.info(f"Cache MISS: {cache_key[:20]}...")
            return None
        except Exception as e:
            logger.error(f"Cache retrieval error: {str(e)}")
            return None
    
    @staticmethod
    def cache_result(text: str, result: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Cache analysis result."""
        cache_key = AIResultCache._generate_cache_key(text)
        ttl = ttl or AIResultCache.DEFAULT_TTL
        
        try:
            if REDIS_AVAILABLE and redis_client:
                redis_client.setex(cache_key, ttl, json.dumps(result))
                logger.info(f"Cached to Redis: {cache_key[:20]}... (TTL: {ttl}s)")
            else:
                _memory_cache[cache_key] = result
                logger.info(f"Cached to Memory: {cache_key[:20]}...")
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
                info = redis_client.info('stats')
                stats.update({
                    "keyspace_hits": info.get('keyspace_hits', 0),
                    "keyspace_misses": info.get('keyspace_misses', 0),
                })
                hits = stats.get('keyspace_hits', 0)
                misses = stats.get('keyspace_misses', 0)
                total = hits + misses
                if total > 0:
                    stats['hit_rate'] = round((hits / total) * 100, 2)
            else:
                stats['entries'] = len(_memory_cache)
        except Exception as e:
            logger.debug(f"Could not retrieve cache stats: {str(e)}")
        
        return stats
