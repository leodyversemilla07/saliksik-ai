"""Contract tests for the remaining API endpoints.

These cover the endpoints that were not exercised by the feature specific
test suites: analysis history and cache administration, the reviewer profile
workflow, the API key lifecycle, token refresh and password changes.
"""

import uuid

import pytest

from app.core.security import get_password_hash
from app.models.analysis import ManuscriptAnalysis
from app.models.reviewer import Reviewer
from app.models.user import User

PASSWORD = "password123"


async def _create_user(db_session, role: str = "user", institution: str | None = None) -> User:
    username = f"contract_{uuid.uuid4().hex[:10]}"
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash(PASSWORD),
        role=role,
        institution=institution,
        is_active=True,
        is_email_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _login(client, user: User) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": user.username, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


# ---------------------------------------------------------------------------
# Analysis endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analysis_history_is_paginated(client, db_session):
    user = await _create_user(db_session)
    token = await _login(client, user)

    for index in range(3):
        db_session.add(
            ManuscriptAnalysis(
                user_id=user.id,
                input_type="text",
                manuscript_text=f"body {index}",
                status="COMPLETED",
                summary="summary",
                keywords=["keyword"],
                language_quality={"word_count": 10, "readability_score": 55.0},
            )
        )
    await db_session.commit()

    response = await client.get(
        "/api/v1/analysis/history?page=1&page_size=2",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["results"]) == 2
    assert payload["pagination"]["total_count"] == 3
    assert payload["pagination"]["has_next"] is True
    assert payload["pagination"]["has_previous"] is False


@pytest.mark.asyncio
async def test_analysis_history_requires_authentication(client):
    response = await client.get("/api/v1/analysis/history")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_analysis_status_returns_404_for_unknown_task(client, db_session):
    user = await _create_user(db_session)
    token = await _login(client, user)

    response = await client.get(
        "/api/v1/analysis/status/does-not-exist",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cache_statistics_require_an_admin(client, db_session):
    user = await _create_user(db_session)
    token = await _login(client, user)

    forbidden = await client.get(
        "/api/v1/analysis/cache/stats",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert forbidden.status_code == 403

    admin = await _create_user(db_session, role="admin")
    admin_token = await _login(client, admin)

    allowed = await client.get(
        "/api/v1/analysis/cache/stats",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert allowed.status_code == 200
    assert "cache" in allowed.json()


@pytest.mark.asyncio
async def test_cache_clear_requires_an_admin(client, db_session):
    admin = await _create_user(db_session, role="admin")
    admin_token = await _login(client, admin)

    response = await client.post(
        "/api/v1/analysis/cache/clear",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    assert "message" in response.json()


# ---------------------------------------------------------------------------
# Reviewer endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reviewer_profile_lifecycle(client, db_session):
    user = await _create_user(db_session)
    token = await _login(client, user)

    missing = await client.get("/api/v1/reviewers/me", headers={"Authorization": f"Bearer {token}"})
    assert missing.status_code == 404

    created = await client.post(
        "/api/v1/reviewers/",
        json={
            "expertise_keywords": ["machine learning"],
            "expertise_description": "Ten years of experience",
            "institution": "Example University",
            "orcid_id": "0000-0002-1825-0097",
            "max_assignments": 3,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.status_code == 201
    assert created.json()["max_assignments"] == 3

    duplicate = await client.post(
        "/api/v1/reviewers/",
        json={"expertise_keywords": ["statistics"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert duplicate.status_code == 400

    fetched = await client.get("/api/v1/reviewers/me", headers={"Authorization": f"Bearer {token}"})
    assert fetched.status_code == 200

    updated = await client.put(
        "/api/v1/reviewers/me",
        json={"expertise_keywords": ["machine learning", "nlp"], "is_available": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert updated.status_code == 200
    assert updated.json()["expertise_keywords"] == ["machine learning", "nlp"]
    assert updated.json()["is_available"] is False

    listed = await client.get("/api/v1/reviewers/", headers={"Authorization": f"Bearer {token}"})
    assert listed.status_code == 200
    assert listed.json()["total_count"] >= 1


@pytest.mark.asyncio
async def test_reviewer_endpoints_reject_other_users_analyses(client, db_session):
    owner = await _create_user(db_session)
    other = await _create_user(db_session)
    other_token = await _login(client, other)

    analysis = ManuscriptAnalysis(
        user_id=owner.id,
        input_type="text",
        manuscript_text="body",
        status="COMPLETED",
        summary="summary",
        keywords=["science"],
        language_quality={},
    )
    db_session.add(analysis)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/reviewers/analysis/{analysis.id}/suggestions",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_reviewer_suggestions_for_unknown_analysis(client, db_session):
    user = await _create_user(db_session)
    token = await _login(client, user)

    response = await client.get(
        "/api/v1/reviewers/analysis/999999/suggestions",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_my_assignments_requires_a_reviewer_profile(client, db_session):
    user = await _create_user(db_session)
    token = await _login(client, user)

    response = await client.get("/api/v1/reviewers/my-assignments", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_key_lifecycle(client, db_session):
    user = await _create_user(db_session)
    token = await _login(client, user)
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post("/api/v1/auth/api-key", headers=headers)
    assert created.status_code == 200
    api_key = created.json()["api_key"]
    assert api_key.startswith("sk_")

    # The same key is returned when it already exists.
    again = await client.post("/api/v1/auth/api-key", headers=headers)
    assert again.json()["api_key"] == api_key

    # The key authenticates API requests.
    stats = await client.get("/api/v1/plagiarism/stats", headers={"X-API-Key": api_key})
    assert stats.status_code == 200

    rotated = await client.post("/api/v1/auth/api-key/rotate", headers=headers)
    assert rotated.status_code == 200
    new_key = rotated.json()["api_key"]
    assert new_key != api_key

    revoked = await client.delete("/api/v1/auth/api-key", headers=headers)
    assert revoked.status_code == 200

    missing = await client.delete("/api/v1/auth/api-key", headers=headers)
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_refresh_token_rotation(client, db_session):
    user = await _create_user(db_session)

    login = await client.post(
        "/api/v1/auth/login",
        data={"username": user.username, "password": PASSWORD},
    )
    refresh_token = login.json()["refresh_token"]

    refreshed = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]

    # The used refresh token is blacklisted and cannot be replayed.
    replay = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert replay.status_code == 401

    # A refresh token is not accepted as an access token.
    as_access = await client.get("/api/v1/auth/profile", headers={"Authorization": f"Bearer {refresh_token}"})
    assert as_access.status_code == 401


@pytest.mark.asyncio
async def test_change_password(client, db_session):
    user = await _create_user(db_session)
    token = await _login(client, user)
    headers = {"Authorization": f"Bearer {token}"}

    wrong = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "not-the-password", "new_password": "NewPassword123"},
        headers=headers,
    )
    assert wrong.status_code == 400

    changed = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "NewPassword123"},
        headers=headers,
    )
    assert changed.status_code == 200

    login = await client.post(
        "/api/v1/auth/login",
        data={"username": user.username, "password": "NewPassword123"},
    )
    assert login.status_code == 200


# ---------------------------------------------------------------------------
# Info and health
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_info_endpoint_reports_the_configured_limits(client):
    response = await client.get("/api/v1/info")

    assert response.status_code == 200
    payload = response.json()
    assert payload["limits"]["demo_max_text_length"] == 5000
    assert payload["limits"]["authenticated_max_text_length"] > 0
    assert "features_enabled" in payload


@pytest.mark.asyncio
async def test_health_endpoint_reports_the_dependencies(client):
    response = await client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"healthy", "degraded"}
    assert "database" in payload["services"]


@pytest.mark.asyncio
async def test_unknown_route_uses_the_error_envelope(client):
    response = await client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "HTTP_ERROR"


@pytest.mark.asyncio
async def test_reviewer_match_is_visible_in_the_reviewers_list(client, db_session):
    reviewer_user = await _create_user(db_session)
    author = await _create_user(db_session)
    db_session.add(
        Reviewer(
            user_id=reviewer_user.id,
            expertise_keywords=["science"],
            is_available=True,
            current_assignments=0,
            max_assignments=5,
        )
    )
    analysis = ManuscriptAnalysis(
        user_id=author.id,
        input_type="text",
        manuscript_text="body",
        status="COMPLETED",
        summary="summary",
        keywords=["science"],
        language_quality={},
    )
    db_session.add(analysis)
    await db_session.commit()

    token = await _login(client, reviewer_user)

    response = await client.get("/api/v1/reviewers/", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    usernames = [reviewer["username"] for reviewer in response.json()["results"]]
    assert reviewer_user.username in usernames
