"""
Tests for account lockout after repeated failed login attempts.
"""
import pytest
from app.models.user import User
from app.core.security import get_password_hash, reset_login_attempts


@pytest.fixture(autouse=True)
def clear_lockout_state():
    """Reset in-memory lockout state before each test for isolation."""
    reset_login_attempts()
    yield
    reset_login_attempts()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def create_user(db_session, username: str, email: str, password: str = "correctpass123"):
    user = User(
        username=username,
        email=email,
        hashed_password=get_password_hash(password),
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def attempt_login(client, username: str, password: str):
    return await client.post("/api/v1/auth/login", data={
        "username": username,
        "password": password,
    })


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_failed_login_returns_remaining_attempts(client, db_session):
    """Each failed attempt should report how many attempts remain."""
    await create_user(db_session, "lockout_user1", "lockout1@example.com")

    resp = await attempt_login(client, "lockout_user1", "wrongpass")
    assert resp.status_code == 401
    assert "attempt(s) remaining" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_account_locks_after_max_attempts(client, db_session):
    """Account should be locked after MAX_LOGIN_ATTEMPTS failures."""
    from app.core.config import settings
    await create_user(db_session, "lockout_user2", "lockout2@example.com")

    for _ in range(settings.MAX_LOGIN_ATTEMPTS - 1):
        resp = await attempt_login(client, "lockout_user2", "wrongpass")
        assert resp.status_code == 401

    # Final attempt triggers lockout
    resp = await attempt_login(client, "lockout_user2", "wrongpass")
    assert resp.status_code == 429
    assert "locked" in resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_locked_account_rejects_correct_password(client, db_session):
    """Once locked, even the correct password should be rejected."""
    from app.core.config import settings
    await create_user(db_session, "lockout_user3", "lockout3@example.com")

    for _ in range(settings.MAX_LOGIN_ATTEMPTS):
        await attempt_login(client, "lockout_user3", "wrongpass")

    # Correct password still rejected while locked
    resp = await attempt_login(client, "lockout_user3", "correctpass123")
    assert resp.status_code == 429
    assert "locked" in resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_successful_login_clears_failed_attempts(client, db_session):
    """Successful login should reset the failed attempts counter."""
    from app.core.config import settings
    await create_user(db_session, "lockout_user4", "lockout4@example.com")

    # Fail a few times (but not enough to lock)
    for _ in range(settings.MAX_LOGIN_ATTEMPTS - 2):
        await attempt_login(client, "lockout_user4", "wrongpass")

    # Successful login clears counter
    resp = await attempt_login(client, "lockout_user4", "correctpass123")
    assert resp.status_code == 200

    # Should now be able to fail again without immediate lockout
    resp = await attempt_login(client, "lockout_user4", "wrongpass")
    assert resp.status_code == 401
    assert "attempt(s) remaining" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_nonexistent_user_attempts_are_tracked(client, db_session):
    """Failed attempts for non-existent usernames should also be tracked."""
    from app.core.config import settings

    for _ in range(settings.MAX_LOGIN_ATTEMPTS - 1):
        resp = await attempt_login(client, "ghost_user_xyz", "anypass")
        assert resp.status_code == 401

    resp = await attempt_login(client, "ghost_user_xyz", "anypass")
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_lockout_response_has_timing_info(client, db_session):
    """Locked account response should include time-until-unlock in the message."""
    from app.core.config import settings
    await create_user(db_session, "lockout_user5", "lockout5@example.com")

    for _ in range(settings.MAX_LOGIN_ATTEMPTS):
        await attempt_login(client, "lockout_user5", "wrongpass")

    resp = await attempt_login(client, "lockout_user5", "wrongpass")
    assert resp.status_code == 429
    assert "minute" in resp.json()["error"]["message"].lower()
