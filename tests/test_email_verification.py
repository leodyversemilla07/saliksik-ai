"""
Tests for email verification feature:
- Register sets is_email_verified=False
- Valid token verifies email
- Expired token returns 400
- Invalid/unknown token returns 400
- Resend verification creates a new token
- Resend fails when already verified
- Double-verification is idempotent (second attempt returns 400)
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from app.models.user import User
from datetime import datetime, timezone, timedelta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_user_by_username(db_session, username: str) -> User:
    result = await db_session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def _register(client: AsyncClient, suffix: str = ""):
    resp = await client.post("/api/v1/auth/register", json={
        "username": f"emailtest{suffix}",
        "email": f"emailtest{suffix}@example.com",
        "password": "Password1!",
    })
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_sets_unverified(client: AsyncClient):
    """Registration response contains is_email_verified=False."""
    data = await _register(client, "1")
    assert data["user"]["is_email_verified"] is False


@pytest.mark.asyncio
async def test_register_stores_verification_token(client: AsyncClient, db_session):
    """After registration the user row has a verification token stored."""
    await _register(client, "2")
    user = await _get_user_by_username(db_session, "emailtest2")
    assert user is not None
    assert user.is_email_verified is False
    assert user.verification_token is not None
    assert user.verification_token_expires_at is not None


@pytest.mark.asyncio
async def test_verify_email_valid_token(client: AsyncClient, db_session):
    """A valid token marks the user as verified and clears the token."""
    await _register(client, "3")
    user = await _get_user_by_username(db_session, "emailtest3")
    token = user.verification_token

    resp = await client.post(f"/api/v1/auth/verify-email?token={token}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["is_email_verified"] is True

    # Refresh from DB
    await db_session.refresh(user)
    assert user.is_email_verified is True
    assert user.verification_token is None
    assert user.verification_token_expires_at is None


@pytest.mark.asyncio
async def test_verify_email_invalid_token(client: AsyncClient):
    """An unknown token returns 400."""
    resp = await client.post("/api/v1/auth/verify-email?token=totally-invalid-token")
    assert resp.status_code == 400
    assert "invalid" in resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_verify_email_expired_token(client: AsyncClient, db_session):
    """An expired token returns 400 without verifying the user."""
    await _register(client, "4")
    user = await _get_user_by_username(db_session, "emailtest4")
    token = user.verification_token

    # Expire the token
    user.verification_token_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await db_session.commit()

    resp = await client.post(f"/api/v1/auth/verify-email?token={token}")
    assert resp.status_code == 400
    assert "invalid" in resp.json()["error"]["message"].lower()

    await db_session.refresh(user)
    assert user.is_email_verified is False


@pytest.mark.asyncio
async def test_verify_email_double_use_returns_400(client: AsyncClient, db_session):
    """Using the token a second time returns 400 (token cleared after first use)."""
    await _register(client, "5")
    user = await _get_user_by_username(db_session, "emailtest5")
    token = user.verification_token

    r1 = await client.post(f"/api/v1/auth/verify-email?token={token}")
    assert r1.status_code == 200

    r2 = await client.post(f"/api/v1/auth/verify-email?token={token}")
    assert r2.status_code == 400


@pytest.mark.asyncio
async def test_resend_verification_creates_new_token(client: AsyncClient, db_session):
    """resend-verification generates a fresh token for an unverified account."""
    login_data = await _register(client, "6")
    headers = {"Authorization": f"Bearer {login_data['access_token']}"}

    user = await _get_user_by_username(db_session, "emailtest6")
    old_token = user.verification_token

    resp = await client.post("/api/v1/auth/resend-verification", headers=headers)
    assert resp.status_code == 200, resp.text

    await db_session.refresh(user)
    assert user.verification_token is not None
    assert user.verification_token != old_token


@pytest.mark.asyncio
async def test_resend_verification_already_verified_returns_400(
    client: AsyncClient, db_session
):
    """resend-verification returns 400 when the email is already verified."""
    login_data = await _register(client, "7")
    headers = {"Authorization": f"Bearer {login_data['access_token']}"}

    user = await _get_user_by_username(db_session, "emailtest7")
    token = user.verification_token

    # Verify first
    r = await client.post(f"/api/v1/auth/verify-email?token={token}")
    assert r.status_code == 200

    # Try to resend — should fail
    resp = await client.post("/api/v1/auth/resend-verification", headers=headers)
    assert resp.status_code == 400
    assert "already verified" in resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_resend_verification_requires_auth(client: AsyncClient):
    """resend-verification endpoint is protected (requires authentication)."""
    resp = await client.post("/api/v1/auth/resend-verification")
    assert resp.status_code == 401
