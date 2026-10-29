"""Regression tests for authentication and security hardening.

These cover defects found during the full-codebase review:

* refresh tokens being accepted as access tokens,
* logout not actually revoking access tokens,
* inactive users being able to log in / keep using issued tokens,
* bcrypt raising on passwords longer than 72 bytes,
* placeholder/weak signing secrets being accepted,
* error responses losing the ``WWW-Authenticate`` header,
* request IDs and query strings being written to logs unsanitised.
"""

import bcrypt
import pytest
from pydantic import ValidationError
from starlette.datastructures import QueryParams

from app.core.config import Settings, settings
from app.core.logging import _safe_query_string, _safe_request_id
from app.core.security import (
    blacklist_token,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    get_password_hash,
    verify_password,
)
from app.models.user import User


@pytest.fixture(autouse=True)
def in_memory_blacklist(monkeypatch):
    """Force the in-memory blacklist so tests do not depend on Redis."""
    monkeypatch.setattr("app.core.security._get_redis", lambda: (None, False))
    from app.core import security

    security._token_blacklist.clear()
    yield
    security._token_blacklist.clear()


# ---------------------------------------------------------------------------
# Token type confusion / revocation
# ---------------------------------------------------------------------------


def test_refresh_token_is_not_accepted_as_access_token():
    refresh_token = create_refresh_token({"sub": "1"})

    assert decode_refresh_token(refresh_token) is not None
    assert decode_access_token(refresh_token) is None


def test_access_token_is_not_accepted_as_refresh_token():
    access_token = create_access_token({"sub": "1"})

    assert decode_access_token(access_token) is not None
    assert decode_refresh_token(access_token) is None


def test_blacklisted_access_token_is_rejected():
    token = create_access_token({"sub": "1"})

    assert decode_access_token(token) is not None
    assert blacklist_token(token) is True
    assert decode_access_token(token) is None


def test_blacklisted_refresh_token_is_rejected():
    token = create_refresh_token({"sub": "1"})

    assert decode_refresh_token(token) is not None
    assert blacklist_token(token) is True
    assert decode_refresh_token(token) is None


def test_tampered_token_is_rejected():
    token = create_access_token({"sub": "1"})
    tampered = token[:-2] + ("aa" if not token.endswith("aa") else "bb")

    assert decode_access_token(tampered) is None


# ---------------------------------------------------------------------------
# Password handling
# ---------------------------------------------------------------------------


def test_password_longer_than_bcrypt_limit_roundtrips():
    password = "x" * 200

    hashed = get_password_hash(password)

    assert len(hashed) < 100
    assert verify_password(password, hashed) is True
    assert verify_password("x" * 199, hashed) is False


def test_password_with_multibyte_characters_longer_than_72_bytes():
    password = "é" * 60  # 120 bytes in UTF-8

    hashed = get_password_hash(password)

    assert verify_password(password, hashed) is True
    assert verify_password("e" * 60, hashed) is False


def test_legacy_raw_bcrypt_hash_is_still_verifiable():
    legacy_hash = bcrypt.hashpw(b"legacy-password", bcrypt.gensalt()).decode("utf-8")

    assert verify_password("legacy-password", legacy_hash) is True
    assert verify_password("wrong-password", legacy_hash) is False


def test_verify_password_with_garbage_hash_returns_false():
    assert verify_password("password", "not-a-bcrypt-hash") is False
    assert verify_password("password", "") is False


# ---------------------------------------------------------------------------
# Secret key validation
# ---------------------------------------------------------------------------


def test_placeholder_secret_key_is_rejected():
    with pytest.raises(ValidationError):
        Settings(SECRET_KEY="your-secret-key-here-change-in-production", _env_file=None)


def test_short_secret_key_is_rejected():
    with pytest.raises(ValidationError):
        Settings(SECRET_KEY="short", _env_file=None)


def test_low_diversity_secret_key_is_rejected():
    with pytest.raises(ValidationError):
        Settings(SECRET_KEY="a" * 64, _env_file=None)


def test_valid_secret_key_is_accepted():
    configured = Settings(SECRET_KEY="a-strong-and-unique-development-secret", _env_file=None)

    assert configured.SECRET_KEY == "a-strong-and-unique-development-secret"


# ---------------------------------------------------------------------------
# API level behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_logout_revokes_the_access_token(client, db_session):
    user = User(
        username="logoutuser",
        email="logout@example.com",
        hashed_password=get_password_hash("password123"),
        is_active=True,
        is_email_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    login = await client.post("/api/v1/auth/login", data={"username": "logoutuser", "password": "password123"})
    assert login.status_code == 200
    access_token = login.json()["access_token"]

    profile = await client.get("/api/v1/auth/profile", headers={"Authorization": f"Bearer {access_token}"})
    assert profile.status_code == 200

    logout = await client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {access_token}"})
    assert logout.status_code == 200
    assert logout.json()["tokens_blacklisted"] >= 1

    after_logout = await client.get("/api/v1/auth/profile", headers={"Authorization": f"Bearer {access_token}"})
    assert after_logout.status_code == 401


@pytest.mark.asyncio
async def test_inactive_user_cannot_log_in(client, db_session):
    user = User(
        username="inactiveuser",
        email="inactive@example.com",
        hashed_password=get_password_hash("password123"),
        is_active=False,
        is_email_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    response = await client.post("/api/v1/auth/login", data={"username": "inactiveuser", "password": "password123"})

    assert response.status_code == 401
    assert "access_token" not in response.json()


@pytest.mark.asyncio
async def test_token_of_deactivated_user_is_rejected(client, db_session):
    user = User(
        username="deactivateduser",
        email="deactivated@example.com",
        hashed_password=get_password_hash("password123"),
        is_active=True,
        is_email_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    login = await client.post("/api/v1/auth/login", data={"username": "deactivateduser", "password": "password123"})
    assert login.status_code == 200
    access_token = login.json()["access_token"]

    user.is_active = False
    await db_session.commit()

    response = await client.get("/api/v1/auth/profile", headers={"Authorization": f"Bearer {access_token}"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_api_key_of_inactive_user_is_rejected(client, db_session):
    user = User(
        username="inactivekeyuser",
        email="inactivekey@example.com",
        hashed_password=get_password_hash("password123"),
        api_key="sk_inactive_key",
        is_active=False,
        is_email_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    response = await client.get("/api/v1/plagiarism/stats", headers={"X-API-Key": "sk_inactive_key"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_api_key_authenticates_without_a_bearer_token(client, db_session):
    """An API key must work on its own: the strict OAuth2 scheme used to
    reject the request before the API key was even looked at."""
    user = User(
        username="activekeyuser",
        email="activekey@example.com",
        hashed_password=get_password_hash("password123"),
        api_key="sk_active_key",
        is_active=True,
        is_email_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    response = await client.get("/api/v1/plagiarism/stats", headers={"X-API-Key": "sk_active_key"})

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_invalid_api_key_is_rejected(client):
    response = await client.get("/api/v1/plagiarism/stats", headers={"X-API-Key": "sk_not_a_real_key"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_response_keeps_www_authenticate_header(client):
    response = await client.get("/api/v1/auth/profile")

    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"


@pytest.mark.asyncio
async def test_rate_limit_response_keeps_retry_after_header(client, monkeypatch):
    from app.core.rate_limit import rate_limiter

    monkeypatch.setattr(rate_limiter, "is_allowed", lambda *args, **kwargs: (False, 30))

    response = await client.get("/api/v1/auth/profile")

    assert response.status_code == 429
    assert response.headers.get("Retry-After") is not None


# ---------------------------------------------------------------------------
# Logging hygiene
# ---------------------------------------------------------------------------


def test_request_id_is_sanitised():
    generated = _safe_request_id("bad\nvalue")
    assert "\n" not in generated
    assert generated != "bad\nvalue"

    assert _safe_request_id("trace-123") == "trace-123"
    assert len(_safe_request_id("x" * 500)) == 36


def test_sensitive_query_parameters_are_redacted():
    query = QueryParams("token=secretvalue&password=hunter2&api_key=abc&code=xyz&page=2")

    rendered = _safe_query_string(query)

    assert "secretvalue" not in rendered
    assert "hunter2" not in rendered
    assert "abc" not in rendered
    assert "xyz" not in rendered
    assert "page=2" in rendered
    assert rendered.count("REDACTED") == 4


def test_configured_secret_is_not_the_example_placeholder():
    assert settings.SECRET_KEY != "your-secret-key-here-change-in-production"
