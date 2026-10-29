"""
Tests for the administrative API:

- Only users with the `admin` role can reach the admin endpoints.
- The user list supports pagination and filters.
- Roles can be changed and accounts can be deactivated.
- An administrator cannot demote or deactivate their own account.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import get_password_hash
from app.models.user import User


async def _create_user(db_session, username: str, role: str = "user", email: str | None = None) -> User:
    user = User(
        username=username,
        email=email or f"{username}@example.com",
        hashed_password=get_password_hash("Password1!"),
        role=role,
        is_active=True,
        is_email_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _login(client: AsyncClient, username: str) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": "Password1!"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_admin_endpoints_require_admin_role(client: AsyncClient, db_session):
    user = await _create_user(db_session, "regularuser")
    token = await _login(client, user.username)

    response = await client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "HTTP_ERROR"


@pytest.mark.asyncio
async def test_admin_endpoints_require_authentication(client: AsyncClient):
    response = await client.get("/api/v1/admin/stats")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_can_list_users(client: AsyncClient, db_session):
    admin = await _create_user(db_session, "listadmin", role="admin")
    await _create_user(db_session, "firstmember")
    await _create_user(db_session, "secondmember")
    token = await _login(client, admin.username)

    response = await client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_count"] >= 3
    assert len(body["results"]) >= 3
    assert {entry["username"] for entry in body["results"]} >= {"firstmember", "secondmember"}


@pytest.mark.asyncio
async def test_admin_user_list_filters(client: AsyncClient, db_session):
    admin = await _create_user(db_session, "filteradmin", role="admin")
    await _create_user(db_session, "editoruser", role="editor")
    await _create_user(db_session, "plainuser", role="user")
    token = await _login(client, admin.username)

    response = await client.get(
        "/api/v1/admin/users",
        params={"role": "editor"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_count"] == 1
    assert body["results"][0]["username"] == "editoruser"


@pytest.mark.asyncio
async def test_admin_can_change_a_role(client: AsyncClient, db_session):
    admin = await _create_user(db_session, "roleadmin", role="admin")
    member = await _create_user(db_session, "promoteme")
    token = await _login(client, admin.username)

    response = await client.patch(
        f"/api/v1/admin/users/{member.id}",
        json={"role": "editor"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["role"] == "editor"

    result = await db_session.execute(select(User).where(User.id == member.id))
    updated = result.scalar_one()
    assert updated.role == "editor"


@pytest.mark.asyncio
async def test_admin_can_deactivate_an_account(client: AsyncClient, db_session):
    admin = await _create_user(db_session, "deactivateadmin", role="admin")
    member = await _create_user(db_session, "deactivateme")
    token = await _login(client, admin.username)

    response = await client.patch(
        f"/api/v1/admin/users/{member.id}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["is_active"] is False

    # The deactivated user can no longer log in.
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": member.username, "password": "Password1!"},
    )
    assert login.status_code == 401


@pytest.mark.asyncio
async def test_admin_cannot_demote_themselves(client: AsyncClient, db_session):
    admin = await _create_user(db_session, "selfadmin", role="admin")
    token = await _login(client, admin.username)

    response = await client.patch(
        f"/api/v1/admin/users/{admin.id}",
        json={"role": "user"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_admin_cannot_deactivate_themselves(client: AsyncClient, db_session):
    admin = await _create_user(db_session, "selfdeactivate", role="admin")
    token = await _login(client, admin.username)

    response = await client.patch(
        f"/api/v1/admin/users/{admin.id}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_admin_stats(client: AsyncClient, db_session):
    admin = await _create_user(db_session, "statsadmin", role="admin")
    token = await _login(client, admin.username)

    response = await client.get("/api/v1/admin/stats", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_users"] >= 1
    assert body["active_users"] >= 1
    assert "total_analyses" in body
    assert "indexed_documents" in body


@pytest.mark.asyncio
async def test_unknown_user_returns_404(client: AsyncClient, db_session):
    admin = await _create_user(db_session, "missingadmin", role="admin")
    token = await _login(client, admin.username)

    response = await client.get("/api/v1/admin/users/999999", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 404
