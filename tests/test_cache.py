"""
Tests for the cache module (in-memory fallback and Redis).
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from app.core.cache import (
    _MEMORY_CACHE_MAX_SIZE,
    AIResultCache,
    _memory_cache,
    cleanup_expired_cache,
    invalidate_cache,
)


@pytest.fixture(autouse=True)
def force_memory_cache():
    """Force in-memory cache for all cache tests, even when Redis is available."""
    _memory_cache.clear()
    with patch("app.core.cache.REDIS_AVAILABLE", False), patch("app.core.cache.redis_client", None):
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

    def test_generate_cache_key_different_namespaces(self):
        default_key = AIResultCache._generate_cache_key("same text")
        demo_key = AIResultCache._generate_cache_key("same text", namespace="demo")
        authenticated_key = AIResultCache._generate_cache_key("same text", namespace="authenticated")

        assert default_key != demo_key
        assert demo_key != authenticated_key
        assert demo_key == AIResultCache._generate_cache_key(" SAME TEXT ", namespace="demo")
        assert ":demo:" in demo_key
        assert ":authenticated:" in authenticated_key

    def test_cache_isolation_between_namespaces(self):
        text = "manuscript text used by more than one endpoint"
        demo_result = {"summary": "demo result"}
        authenticated_result = {"summary": "authenticated result"}

        AIResultCache.cache_result(text, demo_result, namespace="demo")
        AIResultCache.cache_result(text, authenticated_result, namespace="authenticated")

        assert AIResultCache.get_cached_result(text, namespace="demo") == demo_result
        assert AIResultCache.get_cached_result(text, namespace="authenticated") == authenticated_result
        assert AIResultCache.get_cached_result(text) is None

    def test_namespace_miss_does_not_use_default_entry(self):
        text = "result cached without a namespace"
        AIResultCache.cache_result(text, {"summary": "default result"})

        assert AIResultCache.get_cached_result(text, namespace="demo") is None
        assert AIResultCache.get_cached_result(text) == {"summary": "default result"}

    def test_redis_backend_uses_namespaced_key(self):
        text = "redis namespaced text"
        fake_redis = MagicMock()
        fake_redis.get.return_value = None

        with patch("app.core.cache.REDIS_AVAILABLE", True), patch("app.core.cache.redis_client", fake_redis):
            AIResultCache.cache_result(text, {"summary": "redis result"}, ttl=60, namespace="demo")
            assert AIResultCache.get_cached_result(text, namespace="demo") is None

        expected_key = AIResultCache._generate_cache_key(text, namespace="demo")
        fake_redis.setex.assert_called_once()
        assert fake_redis.setex.call_args.args[0] == expected_key
        fake_redis.get.assert_called_once_with(expected_key)

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
            _memory_cache[f"key_{i}"] = {"value": i, "expires_at": time.time() + 3600}

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
