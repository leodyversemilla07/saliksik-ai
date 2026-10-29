"""
DOI verification service.

Resolves the DOIs that the citation analyser found against the CrossRef REST
API. The verification is optional (see ``ENABLE_DOI_VERIFICATION``) and always
best effort: a DOI that cannot be resolved is reported as unverified, never as
an error of the analysis.

CrossRef offers a "polite pool" for clients that identify themselves with a
contact address; set ``CROSSREF_MAILTO`` to use it.
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

CROSSREF_WORKS_URL = "https://api.crossref.org/works/{doi}"

# DOIs look like "10.1234/abc.def" - the registrant prefix is 10.4xxx.
_DOI_PATTERN = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)


@dataclass
class DoiInfo:
    """Result of a single DOI lookup."""

    doi: str
    found: bool = False
    title: Optional[str] = None
    type: Optional[str] = None
    year: Optional[int] = None
    publisher: Optional[str] = None
    source: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "doi": self.doi,
            "found": self.found,
            "title": self.title,
            "type": self.type,
            "year": self.year,
            "publisher": self.publisher,
            "source": self.source,
        }


def normalize_doi(doi: str) -> str:
    """Normalise a DOI (lowercase, without resolver prefixes)."""
    cleaned = (doi or "").strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "doi:", "DOI:"):
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix) :]
            break
    return cleaned.strip().rstrip(".").lower()


def extract_dois(text: str) -> List[str]:
    """Extract the DOIs of a text, without duplicates and in order of appearance."""
    seen: set[str] = set()
    dois: List[str] = []
    for match in _DOI_PATTERN.finditer(text or ""):
        doi = normalize_doi(match.group(0))
        if doi and doi not in seen:
            seen.add(doi)
            dois.append(doi)
    return dois


class DoiVerifier:
    """Verifies DOIs against CrossRef."""

    def __init__(
        self,
        timeout: Optional[float] = None,
        mailto: Optional[str] = None,
        max_dois: Optional[int] = None,
        client_factory: Optional[Callable[..., httpx.Client]] = None,
    ):
        self.timeout = timeout if timeout is not None else settings.DOI_VERIFICATION_TIMEOUT
        self.mailto = mailto if mailto is not None else settings.CROSSREF_MAILTO
        self.max_dois = max_dois if max_dois is not None else settings.DOI_VERIFICATION_MAX_DOIS
        # Seam for tests: the factory is called with timeout and headers.
        self._client_factory = client_factory or httpx.Client
        # Cached lookups, keyed by DOI. Successful lookups are kept longer
        # because they do not change.
        self._cache: Dict[str, tuple[float, DoiInfo]] = {}
        self._cache_ttl = 7 * 24 * 3600

    # -- cache ------------------------------------------------------------

    def _cached(self, doi: str) -> Optional[DoiInfo]:
        entry = self._cache.get(doi)
        if not entry:
            return None
        expires_at, info = entry
        if expires_at < time.time():
            self._cache.pop(doi, None)
            return None
        return info

    def _remember(self, doi: str, info: DoiInfo) -> None:
        self._cache[doi] = (time.time() + self._cache_ttl, info)

    # -- lookup -----------------------------------------------------------

    def _request_url(self, doi: str) -> str:
        url = CROSSREF_WORKS_URL.format(doi=doi)
        if self.mailto:
            url = f"{url}?mailto={self.mailto}"
        return url

    def fetch(self, doi: str, client: httpx.Client) -> DoiInfo:
        """Perform a single lookup. Overridden in tests."""
        response = client.get(self._request_url(doi))
        if response.status_code == 404:
            return DoiInfo(doi=doi, found=False, error="not found")
        response.raise_for_status()
        message = response.json().get("message", {})

        year: Optional[int] = None
        for key in ("published-print", "published-online", "issued", "created"):
            parts = message.get(key, {}).get("date-parts") or []
            if parts and parts[0] and parts[0][0]:
                year = int(parts[0][0])
                break

        titles = message.get("title") or []
        return DoiInfo(
            doi=doi,
            found=True,
            title=titles[0] if titles else None,
            type=message.get("type"),
            year=year,
            publisher=message.get("publisher"),
            source="crossref",
        )

    def verify_sync(self, dois: List[str]) -> Dict[str, DoiInfo]:
        """Verify a list of DOIs (blocking)."""
        results: Dict[str, DoiInfo] = {}
        pending = []

        limited = dois[: self.max_dois]
        if len(dois) > self.max_dois:
            logger.info("Only the first %s of %s DOIs are verified", self.max_dois, len(dois))

        for doi in limited:
            cached = self._cached(doi)
            if cached is not None:
                results[doi] = cached
            else:
                pending.append(doi)

        if not pending:
            return results

        try:
            with self._client_factory(timeout=self.timeout, headers={"User-Agent": self._user_agent()}) as client:
                for doi in pending:
                    try:
                        info = self.fetch(doi, client)
                    except httpx.HTTPStatusError as exc:
                        logger.info("DOI %s could not be verified: %s", doi, exc.response.status_code)
                        info = DoiInfo(doi=doi, found=False, error=f"http {exc.response.status_code}")
                    except Exception as exc:
                        logger.warning("DOI %s could not be verified: %s", doi, exc)
                        info = DoiInfo(doi=doi, found=False, error=str(exc)[:200])
                    self._remember(doi, info)
                    results[doi] = info
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("DOI verification is unavailable: %s", exc)
            for doi in pending:
                results.setdefault(doi, DoiInfo(doi=doi, found=False, error="verification unavailable"))

        return results

    async def verify(self, dois: List[str]) -> Dict[str, DoiInfo]:
        """Verify a list of DOIs without blocking the event loop."""
        if not dois:
            return {}
        return await asyncio.to_thread(self.verify_sync, dois)

    def _user_agent(self) -> str:
        contact = f" (mailto:{self.mailto})" if self.mailto else ""
        return f"saliksik-ai/{settings.VERSION}{contact}"


_verifier: Optional[DoiVerifier] = None


def get_doi_verifier() -> DoiVerifier:
    """Get or create the shared DOI verifier."""
    global _verifier
    if _verifier is None:
        _verifier = DoiVerifier()
    return _verifier
