"""Tests for the request size limit middleware and the language detector."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.services.language_detector import LanguageDetector


@pytest.mark.asyncio
async def test_invalid_content_length_is_rejected(app_fixture):
    transport = ASGITransport(app=app_fixture)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/info", headers={"Content-Length": "not-a-number"})

    assert response.status_code == 400
    assert response.json()["error"]["message"] == "Invalid Content-Length header"


@pytest.mark.asyncio
async def test_oversized_json_body_is_rejected(app_fixture):
    transport = ASGITransport(app=app_fixture)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/analysis/demo",
            content=b"{}",
            headers={"Content-Type": "application/json", "Content-Length": str(2 * 1024 * 1024)},
        )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "HTTP_ERROR"


@pytest.mark.asyncio
async def test_oversized_upload_is_rejected(app_fixture):
    transport = ASGITransport(app=app_fixture)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/analysis/pre-review",
            content=b"x" * 1024,
            headers={"Content-Type": "multipart/form-data; boundary=x", "Content-Length": str(200 * 1024 * 1024)},
        )

    assert response.status_code == 413
    assert "File too large" in response.json()["error"]["message"]


def test_language_detector_uses_the_configured_language_list(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "SUPPORTED_LANGUAGES", "en,fr")

    detector = LanguageDetector(default_language="en")

    assert detector.enabled_languages == {"en", "fr"}
    assert detector.is_supported("fr") is True
    assert detector.is_supported("de") is False
    assert set(detector.get_supported_languages()) == {"en", "fr"}


def test_language_detector_falls_back_for_disabled_languages(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "SUPPORTED_LANGUAGES", "en")

    detector = LanguageDetector(default_language="en")

    # A detected language outside the configured list falls back to English.
    result = detector.detect_language(
        "Dieser Satz ist auf Deutsch geschrieben und sollte nicht erkannt werden, weil nur Englisch erlaubt ist."
    )

    assert result.code == "en"
