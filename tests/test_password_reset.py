"""
Tests for the password reset flow:

- ``POST /api/v1/auth/forgot-password`` always returns the same response,
  whether or not the address belongs to an account (no user enumeration).
- A reset token is stored on the user row with an expiry.
- ``POST /api/v1/auth/reset-password`` accepts the token and stores the new hash.
- The token is single use: a second attempt fails.
- Expired tokens are rejected.
- Unknown tokens are rejected.
- Weak passwords are rejected before the token is consumed.
"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import verify_password
from app.models.user import User

NEW_PASSWORD = "BrandNew1!"


async def _get_user_by_email(db_session, email: str) -> User:
    result = await db_session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def _register(client: AsyncClient, suffix: str):
    email = f"resetuser{suffix}@example.com"
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "username": f"resetuser{suffix}",
            "email": email,
            "password": "Password1!",
        },
    )
    assert resp.status_code in (200, 201), resp.text
    return email


@pytest.mark.asyncio
async def test_forgot_password_never_reveals_whether_the_account_exists(client: AsyncClient):
    known = await _register(client, "1")

    response_known = await client.post("/api/v1/auth/forgot-password", json={"email": known})
    response_unknown = await client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})

    assert response_known.status_code == 200
    assert response_unknown.status_code == 200
    assert response_known.json() == response_unknown.json()


@pytest.mark.asyncio
async def test_forgot_password_stores_a_reset_token(client: AsyncClient, db_session):
    email = await _register(client, "2")

    await client.post("/api/v1/auth/forgot-password", json={"email": email})

    user = await _get_user_by_email(db_session, email)
    assert user is not None
    assert user.password_reset_token
    assert user.password_reset_token_expires_at is not None


@pytest.mark.asyncio
async def test_reset_password_changes_the_password(client: AsyncClient, db_session):
    email = await _register(client, "3")

    await client.post("/api/v1/auth/forgot-password", json={"email": email})
    user = await _get_user_by_email(db_session, email)
    token = user.password_reset_token

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 200, response.text

    user = await _get_user_by_email(db_session, email)
    assert verify_password(NEW_PASSWORD, user.hashed_password)
    assert user.password_reset_token is None

    # The new password works for logging in.
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": user.username, "password": NEW_PASSWORD},
    )
    assert login.status_code == 200, login.text


@pytest.mark.asyncio
async def test_reset_token_is_single_use(client: AsyncClient, db_session):
    email = await _register(client, "4")

    await client.post("/api/v1/auth/forgot-password", json={"email": email})
    user = await _get_user_by_email(db_session, email)
    token = user.password_reset_token

    first = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": NEW_PASSWORD},
    )
    assert first.status_code == 200

    second = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "AnotherOne1!"},
    )
    assert second.status_code == 400


@pytest.mark.asyncio
async def test_expired_reset_token_is_rejected(client: AsyncClient, db_session):
    email = await _register(client, "5")

    await client.post("/api/v1/auth/forgot-password", json={"email": email})
    user = await _get_user_by_email(db_session, email)
    token = user.password_reset_token

    user.password_reset_token_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_unknown_reset_token_is_rejected(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": "x" * 43, "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_weak_password_does_not_consume_the_token(client: AsyncClient, db_session):
    email = await _register(client, "6")

    await client.post("/api/v1/auth/forgot-password", json={"email": email})
    user = await _get_user_by_email(db_session, email)
    token = user.password_reset_token

    weak = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "short"},
    )
    assert weak.status_code == 422  # schema minimum length

    user = await _get_user_by_email(db_session, email)
    assert user.password_reset_token == token

    # The token still works for a valid password.
    ok = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": NEW_PASSWORD},
    )
    assert ok.status_code == 200
