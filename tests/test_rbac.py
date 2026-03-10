"""
Tests for role-based access control (RBAC).

Verifies that admin-only endpoints return 403 for regular users
and 200 for users with role="admin".
"""
import pytest
from app.models.user import User
from app.core.security import get_password_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def register_and_login(client, username: str, email: str, password: str = "password123") -> str:
    """Register a user and return their access token."""
    resp = await client.post("/api/v1/auth/register", json={
        "username": username,
        "email": email,
        "password": password,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


async def create_admin_and_login(client, db_session, username: str, email: str, password: str = "adminpass123") -> str:
    """Create a user with role='admin' directly in the DB, then login and return token."""
    user = User(
        username=username,
        email=email,
        hashed_password=get_password_hash(password),
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()

    resp = await client.post("/api/v1/auth/login", data={
        "username": username,
        "password": password,
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# /api/v1/analysis/cache/stats  (GET, admin-only)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_stats_requires_auth(client):
    response = await client.get("/api/v1/analysis/cache/stats")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_cache_stats_forbidden_for_regular_user(client, db_session):
    token = await register_and_login(client, "rbac_user1", "rbac1@example.com")
    response = await client.get(
        "/api/v1/analysis/cache/stats",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_cache_stats_allowed_for_admin(client, db_session):
    token = await create_admin_and_login(client, db_session, "rbac_admin1", "rbac_admin1@example.com")
    response = await client.get(
        "/api/v1/analysis/cache/stats",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# /api/v1/analysis/cache/clear  (POST, admin-only)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_clear_requires_auth(client):
    response = await client.post("/api/v1/analysis/cache/clear")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_cache_clear_forbidden_for_regular_user(client, db_session):
    token = await register_and_login(client, "rbac_user2", "rbac2@example.com")
    response = await client.post(
        "/api/v1/analysis/cache/clear",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_cache_clear_allowed_for_admin(client, db_session):
    token = await create_admin_and_login(client, db_session, "rbac_admin2", "rbac_admin2@example.com")
    response = await client.post(
        "/api/v1/analysis/cache/clear",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# /api/v1/plagiarism/index/rebuild  (POST, admin-only)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_index_rebuild_requires_auth(client):
    response = await client.post("/api/v1/plagiarism/index/rebuild")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_index_rebuild_forbidden_for_regular_user(client, db_session):
    token = await register_and_login(client, "rbac_user3", "rbac3@example.com")
    response = await client.post(
        "/api/v1/plagiarism/index/rebuild",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_index_rebuild_allowed_for_admin(client, db_session):
    token = await create_admin_and_login(client, db_session, "rbac_admin3", "rbac_admin3@example.com")
    response = await client.post(
        "/api/v1/plagiarism/index/rebuild",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Registration returns role in UserResponse
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_returns_default_role(client, db_session):
    resp = await client.post("/api/v1/auth/register", json={
        "username": "rbac_role_check",
        "email": "rbac_role_check@example.com",
        "password": "password123",
    })
    assert resp.status_code == 201
    assert resp.json()["user"]["role"] == "user"
