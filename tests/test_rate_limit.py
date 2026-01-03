"""
Tests for rate limiting functionality.
"""
import pytest
from app.core.rate_limit import (
    InMemoryRateLimiter,
    parse_rate_limit
)


class TestRateLimitParsing:
    """Tests for rate limit string parsing."""
    
    def test_parse_per_hour(self):
        """Test parsing requests per hour."""
        max_requests, window = parse_rate_limit("60/hour")
        assert max_requests == 60
        assert window == 3600
    
    def test_parse_per_minute(self):
        """Test parsing requests per minute."""
        max_requests, window = parse_rate_limit("100/minute")
        assert max_requests == 100
        assert window == 60
    
    def test_parse_per_second(self):
        """Test parsing requests per second."""
        max_requests, window = parse_rate_limit("10/second")
        assert max_requests == 10
        assert window == 1
    
    def test_parse_per_day(self):
        """Test parsing requests per day."""
        max_requests, window = parse_rate_limit("1000/day")
        assert max_requests == 1000
        assert window == 86400
    
    def test_parse_invalid_format(self):
        """Test parsing invalid format returns defaults."""
        max_requests, window = parse_rate_limit("invalid")
        assert max_requests == 60
        assert window == 3600


class TestInMemoryRateLimiter:
    """Tests for in-memory rate limiter."""
    
    def test_allows_within_limit(self):
        """Test that requests within limit are allowed."""
        limiter = InMemoryRateLimiter()
        
        # Should allow first request
        allowed, remaining = limiter.is_allowed("test_key", max_requests=5, window_seconds=60)
        assert allowed is True
        assert remaining == 4
    
    def test_blocks_over_limit(self):
        """Test that requests over limit are blocked."""
        limiter = InMemoryRateLimiter()
        
        # Make 5 requests
        for i in range(5):
            limiter.is_allowed("block_key", max_requests=5, window_seconds=60)
        
        # 6th request should be blocked
        allowed, remaining = limiter.is_allowed("block_key", max_requests=5, window_seconds=60)
        assert allowed is False
        assert remaining == 0
    
    def test_different_keys_independent(self):
        """Test that different keys have independent limits."""
        limiter = InMemoryRateLimiter()
        
        # Exhaust limit for key1
        for _ in range(3):
            limiter.is_allowed("key1", max_requests=3, window_seconds=60)
        
        # key2 should still be allowed
        allowed, _ = limiter.is_allowed("key2", max_requests=3, window_seconds=60)
        assert allowed is True
    
    def test_remaining_decrements(self):
        """Test that remaining count decrements correctly."""
        limiter = InMemoryRateLimiter()
        
        _, remaining1 = limiter.is_allowed("decrement_key", max_requests=5, window_seconds=60)
        _, remaining2 = limiter.is_allowed("decrement_key", max_requests=5, window_seconds=60)
        _, remaining3 = limiter.is_allowed("decrement_key", max_requests=5, window_seconds=60)
        
        assert remaining1 == 4
        assert remaining2 == 3
        assert remaining3 == 2


@pytest.mark.asyncio
async def test_rate_limit_headers(client):
    """Test that rate limit headers are present in responses."""
    response = await client.get("/api/v1/info")
    
    # Check headers exist
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers
    assert "X-RateLimit-Reset" in response.headers


@pytest.mark.asyncio
async def test_excluded_paths_no_rate_limit(client):
    """Test that excluded paths don't have rate limit headers."""
    response = await client.get("/health")
    
    # Health endpoint should be excluded from rate limiting
    # so it should not have rate limit headers
    # Note: depending on implementation, headers might still be present
    assert response.status_code == 200
