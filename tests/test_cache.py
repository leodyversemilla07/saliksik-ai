"""
Tests for the cache module (in-memory fallback and Redis).
"""
import time
import pytest
from app.core.cache import (
    AIResultCache,
    _memory_cache,
    _MEMORY_CACHE_MAX_SIZE,
    cleanup_expired_cache,
    invalidate_cache,
)


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear in-memory cache before and after each test."""
    _memory_cache.clear()
    yield
    _memory_cache.clear()


class TestAIResultCache:
    def test_generate_cache_key_deterministic(self):
        key1 = AIResultCache._generate_cache_key("Hello World")
        key2 = AIResultCache._generate_cache_key("hello world")  # normalized
        key3 = AIResultCache._generate_cache_key("  Hello World  ")
        assert key1 == key2 == key3

    def test_generate_cache_key_different_texts(self):
        key1 = AIResultCache._generate_cache_key("text A")
        key2 = AIResultCache._generate_cache_key("text B")
        assert key1 != key2

    def test_cache_and_retrieve(self):
        text = "sample manuscript for caching test"
        result = {"summary": "test summary", "keywords": ["a", "b"]}

        assert AIResultCache.get_cached_result(text) is None
        assert AIResultCache.cache_result(text, result, ttl=60) is True
        cached = AIResultCache.get_cached_result(text)
        assert cached == result

    def test_cache_miss_returns_none(self):
        assert AIResultCache.get_cached_result("nonexistent text") is None

    def test_cache_expiration(self):
        text = "expiring text"
        result = {"data": "expires soon"}
        AIResultCache.cache_result(text, result, ttl=1)

        # Should be available immediately
        assert AIResultCache.get_cached_result(text) is not None

        # Manually expire it
        cache_key = AIResultCache._generate_cache_key(text)
        if cache_key in _memory_cache:
            _memory_cache[cache_key]["expires_at"] = time.time() - 1

        assert AIResultCache.get_cached_result(text) is None

    def test_clear_all_cache(self):
        AIResultCache.cache_result("text1", {"a": 1})
        AIResultCache.cache_result("text2", {"b": 2})
        assert len(_memory_cache) == 2

        AIResultCache.clear_all_cache()
        assert len(_memory_cache) == 0

    def test_cache_stats_memory(self):
        AIResultCache.cache_result("s1", {"x": 1})
        AIResultCache.cache_result("s2", {"y": 2})
        stats = AIResultCache.get_cache_stats()
        assert stats["backend"] == "memory"
        assert stats["entries"] == 2


class TestCacheCleanup:
    def test_cleanup_expired_removes_old_entries(self):
        _memory_cache["expired1"] = {"value": "a", "expires_at": time.time() - 100}
        _memory_cache["expired2"] = {"value": "b", "expires_at": time.time() - 50}
        _memory_cache["valid"] = {"value": "c", "expires_at": time.time() + 3600}

        removed = cleanup_expired_cache()
        assert removed == 2
        assert "valid" in _memory_cache
        assert "expired1" not in _memory_cache

    def test_cache_eviction_on_overflow(self):
        """Cache should evict oldest 25% when max size is exceeded."""
        # Fill cache to max
        for i in range(_MEMORY_CACHE_MAX_SIZE):
            _memory_cache[f"key_{i}"] = {
                "value": i,
                "expires_at": time.time() + 3600
            }

        # Adding one more should trigger eviction
        AIResultCache.cache_result("overflow_text", {"new": True})
        assert len(_memory_cache) < _MEMORY_CACHE_MAX_SIZE + 1

    def test_invalidate_cache_by_pattern(self):
        _memory_cache["ai_analysis:abc"] = {"value": 1, "expires_at": time.time() + 100}
        _memory_cache["ai_analysis:def"] = {"value": 2, "expires_at": time.time() + 100}
        _memory_cache["other:key"] = {"value": 3, "expires_at": time.time() + 100}

        count = invalidate_cache("ai_analysis:*")
        assert count == 2
        assert "other:key" in _memory_cache
