"""
System-level verification tests.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from main import app

@pytest.mark.asyncio
async def test_health_check():
    """Verify that the application is running and the health endpoint returns 200."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        # Status can be "healthy" or "degraded" depending on service availability
        assert data["status"] in ["healthy", "degraded"]
        assert "version" in data
        assert "environment" in data
        assert "services" in data

@pytest.mark.asyncio
async def test_root_endpoint():
    """Verify the root endpoint returns 200 (serves landing page or JSON info)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        # The endpoint serves static/index.html when present (HTML response),
        # or falls back to a JSON info dict when no static file exists.
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            data = response.json()
            assert "name" in data
            assert "docs" in data
        else:
            # HTML landing page — just verify it has some content
            assert len(response.content) > 0
