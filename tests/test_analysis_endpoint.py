"""
Tests for the analysis API endpoints.
"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.asyncio
class TestAnalysisEndpoints:

    async def test_pre_review_requires_auth(self, client):
        """Unauthenticated requests should be rejected."""
        response = await client.post("/api/v1/analysis/pre-review", json={
            "text": "A sample manuscript for testing."
        })
        assert response.status_code in (401, 403)

    async def test_pre_review_with_text(self, client, db_session):
        """Authenticated user can submit text for analysis."""
        # Register and login
        await client.post("/api/v1/auth/register", json={
            "username": "analyst1",
            "email": "analyst1@test.com",
            "password": "Test1234!"
        })

        login_resp = await client.post("/api/v1/auth/login", data={
            "username": "analyst1",
            "password": "Test1234!"
        })
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Submit analysis
        response = await client.post("/api/v1/analysis/pre-review",
            json={"text": "This is a test manuscript with enough content for analysis."},
            headers=headers
        )
        # Should succeed (200 or 201) or return 202 for async processing
        assert response.status_code in (200, 201, 202)

    async def test_pre_review_empty_text_rejected(self, client, db_session):
        """Empty or too-short text should be rejected."""
        login_resp = await client.post("/api/v1/auth/register", json={
            "username": "analyst2",
            "email": "analyst2@test.com",
            "password": "Test1234!"
        })
        login_resp = await client.post("/api/v1/auth/login", data={
            "username": "analyst2",
            "password": "Test1234!"
        })
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.post("/api/v1/analysis/pre-review",
            json={"text": ""},
            headers=headers
        )
        assert response.status_code in (400, 422)


@pytest.mark.asyncio
class TestHealthEndpoint:

    async def test_health_returns_status(self, client):
        """Health endpoint should return a status field."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert data["status"] in ("healthy", "degraded")

    async def test_root_returns_project_info(self, client):
        """Root endpoint should return project metadata."""
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
