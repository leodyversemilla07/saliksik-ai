"""
Tests for the analysis API endpoints.
"""

from uuid import uuid4

import pytest

from app.models.analysis import ManuscriptAnalysis


async def _register_user(client) -> tuple[str, int, dict[str, str]]:
    """Register a unique user and return username, id, and auth headers."""
    username = f"status_{uuid4().hex[:10]}"
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "Password123!",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    return username, payload["user"]["id"], {"Authorization": f"Bearer {payload['access_token']}"}


async def _create_analysis(db_session, user_id: int, analysis_status: str, **fields):
    """Insert an analysis row in a specific state for status polling tests."""
    manuscript_text = fields.pop(
        "manuscript_text",
        "A manuscript used to verify the analysis status polling contract.",
    )
    analysis = ManuscriptAnalysis(
        user_id=user_id,
        manuscript_text=manuscript_text,
        input_type="text",
        status=analysis_status,
        task_id=fields.pop("task_id", f"status-{uuid4().hex}"),
        **fields,
    )
    db_session.add(analysis)
    await db_session.commit()
    await db_session.refresh(analysis)
    return analysis


@pytest.mark.asyncio
class TestAnalysisEndpoints:
    async def test_pre_review_requires_auth(self, client):
        """Unauthenticated requests should be rejected."""
        response = await client.post(
            "/api/v1/analysis/pre-review",
            json={"text": "A sample manuscript for testing."},
        )
        assert response.status_code in (401, 403)

    @pytest.mark.skip(reason="Requires Celery task integration fix")
    async def test_pre_review_with_text(self, client, db_session):
        """Authenticated user can submit text for analysis."""
        # Register and login
        await client.post(
            "/api/v1/auth/register",
            json={
                "username": "analyst1",
                "email": "analyst1@test.com",
                "password": "Test1234!",
            },
        )

        login_resp = await client.post("/api/v1/auth/login", data={"username": "analyst1", "password": "Test1234!"})
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Submit analysis
        response = await client.post(
            "/api/v1/analysis/pre-review",
            json={"text": "This is a test manuscript with enough content for analysis."},
            headers=headers,
        )
        # Should succeed (200 or 201) or return 202 for async processing
        assert response.status_code in (200, 201, 202)

    async def test_pre_review_empty_text_rejected(self, client, db_session):
        """Empty or too-short text should be rejected."""
        login_resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "analyst2",
                "email": "analyst2@test.com",
                "password": "Test1234!",
            },
        )
        login_resp = await client.post("/api/v1/auth/login", data={"username": "analyst2", "password": "Test1234!"})
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.post(
            "/api/v1/analysis/pre-review",
            json={"text": ""},
            headers=headers,
        )
        assert response.status_code in (400, 422)


@pytest.mark.asyncio
class TestAnalysisStatusContract:
    """Polling responses must keep a stable shape for every terminal state."""

    @pytest.mark.parametrize("analysis_status", ["PENDING", "PROCESSING"])
    async def test_in_progress_status_shape(self, client, db_session, analysis_status):
        _, user_id, headers = await _register_user(client)
        analysis = await _create_analysis(db_session, user_id, analysis_status)

        response = await client.get(f"/api/v1/analysis/status/{analysis.task_id}", headers=headers)

        assert response.status_code == 200
        assert response.json() == {
            "task_id": analysis.task_id,
            "status": analysis_status,
            "message": "Analysis in progress...",
        }

    async def test_failed_status_shape(self, client, db_session):
        _, user_id, headers = await _register_user(client)
        analysis = await _create_analysis(db_session, user_id, "FAILED")

        response = await client.get(f"/api/v1/analysis/status/{analysis.task_id}", headers=headers)

        assert response.status_code == 200
        assert response.json() == {
            "task_id": analysis.task_id,
            "status": "FAILED",
            "message": "Analysis failed. Please try again.",
        }

    async def test_completed_status_payload(self, client, db_session):
        username, user_id, headers = await _register_user(client)
        manuscript_text = "Completed manuscript text used for the status contract."
        analysis = await _create_analysis(
            db_session,
            user_id,
            "COMPLETED",
            manuscript_text=manuscript_text,
            summary="A completed analysis summary.",
            keywords=["machine learning", "peer review"],
            language_quality={
                "word_count": 120,
                "unique_words": 80,
                "sentence_count": 6,
                "named_entities": 3,
                "readability_score": 55.5,
            },
            processing_time=1.239,
        )

        response = await client.get(f"/api/v1/analysis/status/{analysis.task_id}", headers=headers)

        assert response.status_code == 200
        payload = response.json()
        assert payload["summary"] == "A completed analysis summary."
        assert payload["keywords"] == ["machine learning", "peer review"]
        assert payload["language_quality"]["word_count"] == 120
        assert payload["language_quality"]["unique_words"] == 80
        assert payload["language_quality"]["sentence_count"] == 6
        assert payload["language_quality"]["named_entities"] == 3
        assert payload["language_quality"]["readability_score"] == 55.5
        assert payload["language_quality"]["grammar_issues"] is None
        assert payload["language_quality"]["grammar_check_available"] is None
        assert payload["metadata"]["analysis_id"] == analysis.id
        assert payload["metadata"]["input_length"] == len(manuscript_text)
        assert abs(payload["metadata"]["processing_time"] - 1.24) < 1e-9
        assert payload["metadata"]["user"] == username
        assert payload["metadata"]["timestamp"] is not None
        assert payload["metadata"]["cached"] is False
        assert payload["metadata"]["demo"] is False

    async def test_unknown_task_returns_404(self, client):
        _, _, headers = await _register_user(client)

        response = await client.get(f"/api/v1/analysis/status/{uuid4().hex}", headers=headers)

        assert response.status_code == 404
        assert response.json()["error"]["message"] == "Analysis task not found"

    async def test_other_users_task_returns_404(self, client, db_session):
        _, owner_id, _ = await _register_user(client)
        _, _, other_headers = await _register_user(client)
        analysis = await _create_analysis(db_session, owner_id, "PENDING")

        response = await client.get(f"/api/v1/analysis/status/{analysis.task_id}", headers=other_headers)

        assert response.status_code == 404
        assert response.json()["error"]["message"] == "Analysis task not found"

    async def test_status_requires_auth(self, client):
        response = await client.get(f"/api/v1/analysis/status/{uuid4().hex}")

        assert response.status_code in (401, 403)


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
        """Root serves the landing page; the metadata lives in /api/v1/info."""
        landing = await client.get("/")
        assert landing.status_code == 200
        assert "Saliksik AI" in landing.text

        response = await client.get("/api/v1/info")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
