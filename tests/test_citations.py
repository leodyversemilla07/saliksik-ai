"""Tests for the citation analysis endpoint."""

import uuid

import pytest

from app.core.security import get_password_hash
from app.models.user import User

SAMPLE_MANUSCRIPT = """
Introduction

Machine learning has improved text classification [Smith, 2019]. Earlier work
used simple statistical models [Doe, 2015].

References

Smith, J. (2019). A study of automated screening. Journal of Testing, 12(3), 45-67.
Doe, A. (2015). Statistical methods for screening. Journal of Testing, 8(1), 10-22.
"""


@pytest.fixture
async def reviewer_user(db_session):
    # The test database keeps committed rows between tests, so every test uses
    # its own account.
    username = f"citationuser_{uuid.uuid4().hex[:8]}"
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash("password123"),
        is_active=True,
        is_email_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_analyze_citations_requires_authentication(client):
    response = await client.post("/api/v1/citations/analyze", json={"manuscript_text": SAMPLE_MANUSCRIPT})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_analyze_citations_returns_the_analysis(client, reviewer_user):
    token = await _login(client, reviewer_user.username)

    response = await client.post(
        "/api/v1/citations/analyze",
        json={"manuscript_text": SAMPLE_MANUSCRIPT},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_citations"] >= 1
    assert payload["format_detected"] in {"apa", "mla", "ieee", "chicago", "unknown"}
    assert 0 <= payload["format_consistency"] <= 100
    assert "issues" in payload


@pytest.mark.asyncio
async def test_analyze_citations_rejects_short_text(client, reviewer_user):
    token = await _login(client, reviewer_user.username)

    response = await client.post(
        "/api/v1/citations/analyze",
        json={"manuscript_text": "too short"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_analyze_citations_can_be_disabled(client, reviewer_user, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "ENABLE_CITATION_ANALYSIS", False)
    token = await _login(client, reviewer_user.username)

    response = await client.post(
        "/api/v1/citations/analyze",
        json={"manuscript_text": SAMPLE_MANUSCRIPT},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 503


async def _login(client, username: str) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": "password123"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]
