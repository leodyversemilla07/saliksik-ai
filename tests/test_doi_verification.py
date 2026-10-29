"""
Tests for the optional DOI verification.

The CrossRef lookups are mocked, so the tests never touch the network.
"""

import pytest

from app.core.config import settings
from app.services.citation_analyzer import analyze_citations
from app.services.doi_verifier import DoiInfo, DoiVerifier, extract_dois, normalize_doi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError(
                f"status {self.status_code}",
                request=None,
                response=None,
            )


class FakeClient:
    """Minimal stand-in for httpx.Client."""

    def __init__(self, responses=None, **kwargs):
        self.responses = responses or {}
        self.requested = []
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url):
        self.requested.append(url)
        doi = url.split("/works/")[1].split("?")[0]
        response = self.responses.get(doi)
        if response is None:
            return FakeResponse({}, status_code=404)
        return response


def _crossref_payload(title="A verified title", year=2020):
    return {
        "message": {
            "title": [title],
            "type": "journal-article",
            "publisher": "Test Publisher",
            "issued": {"date-parts": [[year]]},
        }
    }


# ---------------------------------------------------------------------------
# DOI extraction
# ---------------------------------------------------------------------------


def test_normalize_doi_removes_resolver_prefixes():
    assert normalize_doi("https://doi.org/10.1234/ABC.def") == "10.1234/abc.def"
    assert normalize_doi("doi:10.1234/abc.def") == "10.1234/abc.def"
    assert normalize_doi("  10.1234/abc.def.  ") == "10.1234/abc.def"


def test_extract_dois_removes_duplicates_and_keeps_the_order():
    text = "First 10.1000/one, then 10.1000/two. Again https://doi.org/10.1000/one and 10.5555/three."

    assert extract_dois(text) == ["10.1000/one", "10.1000/two", "10.5555/three"]


def test_extract_dois_ignores_text_without_dois():
    assert extract_dois("A manuscript without any identifier.") == []


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def test_verify_reports_found_and_missing_dois():
    client = FakeClient({"10.1000/one": FakeResponse(_crossref_payload())})
    verifier = DoiVerifier(client_factory=lambda **kwargs: client)

    results = verifier.verify_sync(["10.1000/one", "10.1000/missing"])

    assert results["10.1000/one"].found is True
    assert results["10.1000/one"].title == "A verified title"
    assert results["10.1000/one"].year == 2020
    assert results["10.1000/one"].publisher == "Test Publisher"
    assert results["10.1000/missing"].found is False
    assert results["10.1000/missing"].error == "not found"


def _fake_fetch(verifier: DoiVerifier, doi: str, client):
    """Replacement for DoiVerifier.fetch that uses the fake client."""
    response = client.get(verifier._request_url(doi))
    if response.status_code == 404:
        return DoiInfo(doi=doi, found=False, error="not found")
    response.raise_for_status()
    message = response.json().get("message", {})
    years = message.get("issued", {}).get("date-parts") or []
    return DoiInfo(
        doi=doi,
        found=True,
        title=(message.get("title") or [None])[0],
        type=message.get("type"),
        year=years[0][0] if years and years[0] else None,
        publisher=message.get("publisher"),
        source="crossref",
    )


def test_verify_caches_the_results(monkeypatch):
    verifier = DoiVerifier(client_factory=lambda **kwargs: FakeClient())
    calls = []

    def fake_fetch(doi, client):
        calls.append(doi)
        return DoiInfo(doi=doi, found=True)

    monkeypatch.setattr(verifier, "fetch", fake_fetch)

    verifier.verify_sync(["10.1000/one"])
    verifier.verify_sync(["10.1000/one"])

    assert calls == ["10.1000/one"]


def test_verify_limits_the_number_of_dois(monkeypatch):
    verifier = DoiVerifier(max_dois=2, client_factory=lambda **kwargs: FakeClient())
    seen = []

    def fake_fetch(doi, client):
        seen.append(doi)
        return DoiInfo(doi=doi, found=True)

    monkeypatch.setattr(verifier, "fetch", fake_fetch)

    verifier.verify_sync([f"10.1000/{index}" for index in range(5)])

    assert len(seen) == 2


@pytest.mark.asyncio
async def test_analyze_citations_without_verification(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_DOI_VERIFICATION", False)

    text = (
        "Introduction\n"
        "Prior work has explored this topic [Smith, 2019].\n\n"
        "References\n"
        "Smith, J. (2019). A study. Journal of Testing, 12(3), 45-67. doi:10.1000/one\n"
    )

    result = await analyze_citations(text)

    assert result.total_citations == 1
    assert result.verified_dois == 0
    assert result.unverified_dois == 0
    assert result.doi_details == []


@pytest.mark.asyncio
async def test_analyze_citations_with_verification(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_DOI_VERIFICATION", True)

    from app.services import doi_verifier

    verifier = DoiVerifier()
    monkeypatch.setattr(doi_verifier, "_verifier", verifier)

    def fake_fetch(doi, client):
        return DoiInfo(doi=doi, found=True, title="Verified", year=2021)

    monkeypatch.setattr(verifier, "fetch", fake_fetch)

    text = (
        "Introduction\n"
        "Prior work has explored this topic [Smith, 2019].\n\n"
        "References\n"
        "Smith, J. (2019). A study. Journal of Testing, 12(3), 45-67. doi:10.1000/one\n"
    )

    result = await analyze_citations(text)

    assert result.verified_dois == 1
    assert result.unverified_dois == 0
    assert result.doi_details[0]["doi"] == "10.1000/one"
    assert result.doi_details[0]["found"] is True


@pytest.mark.asyncio
async def test_verification_failures_do_not_break_the_analysis(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_DOI_VERIFICATION", True)

    from app.services import doi_verifier

    verifier = DoiVerifier()

    def failing_fetch(doi, client):
        raise RuntimeError("network down")

    monkeypatch.setattr(verifier, "fetch", failing_fetch)
    monkeypatch.setattr(doi_verifier, "_verifier", verifier)

    text = (
        "Introduction\n"
        "Prior work has explored this topic [Smith, 2019].\n\n"
        "References\n"
        "Smith, J. (2019). A study. Journal of Testing, 12(3), 45-67. doi:10.1000/one\n"
    )

    result = await analyze_citations(text)

    assert result.total_citations == 1
    assert result.verified_dois == 0
    assert result.unverified_dois == 1
